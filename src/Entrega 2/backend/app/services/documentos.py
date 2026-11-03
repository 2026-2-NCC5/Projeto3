"""Base de conhecimento: cadastrar, nova versão, desativar. Reindexa embeddings ao salvar."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.auth import Usuario
from app.core.erros import ErroAPI
from app.db.repositorio import ConflitoVersao, ErroRepositorio, RegistroNaoEncontrado, Repositorio
from app.rag.chunking import dividir_em_chunks
from app.rag.embeddings import CadeiaEmbeddings, FalhaVetorizacao
from app.rag.texto import normalizar
from app.schemas import DocumentoEntrada, NovaVersaoEntrada
from app.services.auditoria import auditar
from app.services.indice import CacheIndiceLexical

log = logging.getLogger("asa.documentos")
LOTE_EMBEDDINGS = 25
MSG_VETORIZACAO = "Não foi possível gerar os embeddings agora, então nada foi gravado. Tente de novo em instantes."


class ServicoDocumentos:
    def __init__(self, repo: Repositorio, embeddings: CadeiaEmbeddings, indice: CacheIndiceLexical) -> None:
        self.repo = repo
        self.embeddings = embeddings
        self.indice = indice

    def _chunks_vetorizados(self, conteudo: str, titulo: str) -> list[dict[str, Any]]:
        """Divide e vetoriza ANTES de gravar: se a vetorização falhar, nada é gravado (contrato: 503)."""
        textos = dividir_em_chunks(conteudo, titulo)
        saida: list[dict[str, Any]] = []
        try:
            for i in range(0, len(textos), LOTE_EMBEDDINGS):
                lote = textos[i : i + LOTE_EMBEDDINGS]
                vetores, _ = self.embeddings.vetorizar_lote(lote)
                saida += [{"conteudo": t, "embedding": v} for t, v in zip(lote, vetores, strict=True)]
        except FalhaVetorizacao as e:
            raise ErroAPI("indisponivel", MSG_VETORIZACAO) from e
        return saida

    def _db(self, fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except RegistroNaoEncontrado as e:
            raise ErroAPI("nao_encontrado", "Documento não encontrado.") from e
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e

    def listar(
        self, busca: str | None, categoria: str | None, ativo: bool | None, pagina: int, por_pagina: int
    ) -> dict[str, Any]:
        itens, total = self._db(
            self.repo.listar_documentos, normalizar(busca) if busca else None, categoria, ativo, pagina, por_pagina
        )
        return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "itens": itens}

    def obter(self, documento_id: str) -> dict[str, Any]:
        doc = self._db(self.repo.obter_documento, documento_id)
        if not doc:
            raise ErroAPI("nao_encontrado", "Documento não encontrado.")
        return doc

    def cadastrar(self, usuario: Usuario, entrada: DocumentoEntrada) -> dict[str, Any]:
        chunks = self._chunks_vetorizados(entrada.conteudo, entrada.titulo)
        data = entrada.data_atualizacao or datetime.now(UTC)
        doc_id = self._db(
            self.repo.criar_documento,
            {
                "titulo": entrada.titulo.strip(),
                "categoria": entrada.categoria.strip(),
                "fonte": entrada.fonte.strip(),
                "conteudo": entrada.conteudo,
                "data_atualizacao": data.isoformat(),
                "usuario_id": usuario.id,
                "chunks": chunks,
            },
        )
        self.indice.invalidar()
        auditar(
            self.repo,
            usuario,
            "documento_cadastrado",
            "documentos_oficiais",
            doc_id,
            entrada={
                "titulo": entrada.titulo,
                "categoria": entrada.categoria,
                "fonte": entrada.fonte,
                "tamanho": len(entrada.conteudo),
            },
            resultado={"versao": 1, "chunks": len(chunks)},
        )
        return self.obter(doc_id)

    def nova_versao(self, usuario: Usuario, documento_id: str, entrada: NovaVersaoEntrada) -> dict[str, Any]:
        atual = self.obter(documento_id)
        if atual["versao"] != entrada.versao_base:
            raise ErroAPI("conflito", "O documento foi alterado por outra pessoa. Recarregue antes de publicar.")
        titulo = entrada.titulo or atual["titulo"]
        chunks = self._chunks_vetorizados(entrada.conteudo, titulo)
        try:
            self.repo.nova_versao_documento(
                {
                    "documento_id": documento_id,
                    "versao_base": entrada.versao_base,
                    "titulo": entrada.titulo,
                    "categoria": entrada.categoria,
                    "fonte": entrada.fonte,
                    "conteudo": entrada.conteudo,
                    "motivo": entrada.motivo,
                    "data_atualizacao": (entrada.data_atualizacao or datetime.now(UTC)).isoformat(),
                    "usuario_id": usuario.id,
                    "chunks": chunks,
                }
            )
        except ConflitoVersao as e:
            raise ErroAPI("conflito", "O documento foi alterado por outra pessoa. Recarregue antes de publicar.") from e
        except RegistroNaoEncontrado as e:
            raise ErroAPI("nao_encontrado", "Documento não encontrado.") from e
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        self.indice.invalidar()
        auditar(
            self.repo,
            usuario,
            "documento_nova_versao",
            "documentos_oficiais",
            documento_id,
            entrada={"versao_base": entrada.versao_base, "motivo": entrada.motivo, "tamanho": len(entrada.conteudo)},
            resultado={"versao": entrada.versao_base + 1, "chunks": len(chunks)},
        )
        return self.obter(documento_id)

    def desativar(self, usuario: Usuario, documento_id: str, motivo: str) -> dict[str, Any]:
        try:
            self.repo.desativar_documento(documento_id, motivo, usuario.id)
        except RegistroNaoEncontrado as e:
            raise ErroAPI("nao_encontrado", "Documento não encontrado.") from e
        except ConflitoVersao as e:
            raise ErroAPI("conflito", "Este documento já está desativado.") from e
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        self.indice.invalidar()
        auditar(
            self.repo,
            usuario,
            "documento_desativado",
            "documentos_oficiais",
            documento_id,
            entrada={"motivo": motivo},
            resultado={"ativo": False},
        )
        return self.obter(documento_id)
