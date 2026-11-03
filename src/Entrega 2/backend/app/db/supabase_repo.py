"""Implementação do Repositorio sobre o Supabase (PostgREST) com a chave service_role.

A chave service_role ignora RLS: este módulo só roda no servidor. A
autorização acontece antes, nas dependências de RBAC das rotas, e as RPCs
de escrita (migration 003) são executáveis só pelo service_role.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

import httpx
from postgrest.exceptions import APIError
from supabase import Client, ClientOptions, create_client

from app.core.config import Settings
from app.db.repositorio import (
    ConflitoVersao,
    ErroRepositorio,
    FiltrosFila,
    PaginaFila,
    RegistroNaoEncontrado,
)

log = logging.getLogger("asa.db")
T = TypeVar("T")

_ORDENACAO = {
    # (coluna, desc, nullsfirst)
    "prioridade": [("prioridade", True, False), ("score_geral", True, False)],
    "-score": [("score_geral", True, False)],
    "score": [("score_geral", False, False)],
    "prazo": [("prazo", False, False), ("score_geral", True, False)],
    "-variacao": [("variacao", True, False), ("score_geral", True, False)],
    "nome": [("nome_exibicao", False, False)],
}
_PAGINA_INTERNA = 1000  # limite padrão de linhas do PostgREST


def criar_cliente(settings: Settings) -> Client:
    opcoes = ClientOptions(
        postgrest_client_timeout=settings.supabase_timeout_s, auto_refresh_token=False, persist_session=False
    )
    return create_client(settings.supabase_url, settings.supabase_service_key.get_secret_value(), opcoes)


class SupabaseRepositorio:
    def __init__(self, cliente: Client) -> None:
        self.c = cliente

    # ------------------------------------------------------------------ util
    @staticmethod
    def _exec(fn: Callable[[], T], *, idempotente: bool = True) -> T:
        """Executa e traduz erros. Leituras tentam de novo UMA vez em erro de transporte
        (conexão keep-alive que o servidor já fechou); escritas nunca repetem, para não duplicar."""
        try:
            try:
                return fn()
            except httpx.TransportError:
                if not idempotente:
                    raise
                log.warning("conexão com o banco reiniciada; repetindo a leitura")
                return fn()
        except APIError as e:
            if e.code == "PT404":
                raise RegistroNaoEncontrado(e.message) from e
            if e.code == "PT409":
                raise ConflitoVersao(e.message) from e
            log.error("erro do PostgREST", extra={"codigo_pg": e.code, "detalhe": e.message})
            raise ErroRepositorio(e.message or "erro no banco") from e
        except (httpx.HTTPError, OSError) as e:
            log.error("banco inacessível", extra={"erro": type(e).__name__})
            raise ErroRepositorio(str(e)) from e

    def _rows(self, query: Any) -> list[dict[str, Any]]:
        return self._exec(lambda: query.execute()).data or []

    def _um(self, query: Any) -> dict[str, Any] | None:
        dados = self._rows(query.limit(1))
        return dados[0] if dados else None

    def _rpc(self, nome: str, params: dict[str, Any], *, escrita: bool = True) -> Any:
        return self._exec(lambda: self.c.rpc(nome, params).execute(), idempotente=not escrita).data

    @staticmethod
    def _faixa(pagina: int, por_pagina: int) -> tuple[int, int]:
        ini = (pagina - 1) * por_pagina
        return ini, ini + por_pagina - 1

    # ------------------------------------------------------------------ operação
    def ping(self) -> None:
        self._rows(self.c.table("perfis").select("id").limit(1))

    # ------------------------------------------------------------------ sessão
    def obter_perfil(self, usuario_id: str) -> dict[str, Any] | None:
        return self._um(self.c.table("perfis").select("id,papel,nome_completo,email,ativo").eq("id", usuario_id))

    def obter_estudante_por_perfil(self, perfil_id: str) -> dict[str, Any] | None:
        return self._um(
            self.c.table("estudantes").select("id,ra,curso,semestre_atual,nome_exibicao").eq("perfil_id", perfil_id)
        )

    def nomes_perfis(self, ids: list[str]) -> dict[str, str]:
        ids = sorted({i for i in ids if i})
        if not ids:
            return {}
        linhas = self._rows(self.c.table("perfis").select("id,nome_completo").in_("id", ids))
        return {str(r["id"]): r["nome_completo"] for r in linhas}

    # ------------------------------------------------------------------ RAG
    def buscar_chunks_similares(self, vetor: list[float], limite: int) -> list[dict[str, Any]]:
        dados = self._rpc(
            "buscar_chunks_similares",
            {"query_embedding": vetor, "limite": limite, "limiar_similaridade": 0.0},
            escrita=False,
        )
        return dados if isinstance(dados, list) else []

    def listar_chunks_ativos(self) -> list[dict[str, Any]]:
        saida: list[dict[str, Any]] = []
        ini = 0
        while True:
            lote = self._rows(
                self.c.table("documentos_chunks")
                .select("id,documento_id,conteudo,documentos_oficiais!inner(titulo,fonte,data_atualizacao,ativo)")
                .eq("ativo", True)
                .eq("documentos_oficiais.ativo", True)
                .order("id")
                .range(ini, ini + _PAGINA_INTERNA - 1)
            )
            for r in lote:
                d = r.pop("documentos_oficiais") or {}
                saida.append(
                    {
                        "chunk_id": r["id"],
                        "documento_id": r["documento_id"],
                        "conteudo": r["conteudo"],
                        "titulo_documento": d.get("titulo"),
                        "fonte_documento": d.get("fonte"),
                        "data_atualizacao": d.get("data_atualizacao"),
                    }
                )
            if len(lote) < _PAGINA_INTERNA:
                return saida
            ini += _PAGINA_INTERNA

    # ------------------------------------------------------------------ chat
    def obter_conversa(self, conversa_id: str) -> dict[str, Any] | None:
        return self._um(
            self.c.table("conversas")
            .select("id,estudante_id,status,titulo,iniciada_em,atualizado_em")
            .eq("id", conversa_id)
        )

    def historico_conversa(self, conversa_id: str, limite: int) -> list[dict[str, Any]]:
        if limite <= 0:
            return []
        linhas = self._rows(
            self.c.table("mensagens")
            .select("remetente,conteudo,criado_em")
            .eq("conversa_id", conversa_id)
            .order("criado_em", desc=True)
            .limit(limite)
        )
        return list(reversed(linhas))

    def registrar_resposta_chat(self, dados: dict[str, Any]) -> dict[str, Any]:
        return self._rpc("registrar_resposta_chat", {"p": dados})

    def listar_conversas(self, estudante_id: str, pagina: int, por_pagina: int) -> tuple[list[dict[str, Any]], int]:
        ini, fim = self._faixa(pagina, por_pagina)
        res = self._exec(
            lambda: (
                self.c.table("conversas")
                .select("id,titulo,status,iniciada_em,atualizado_em", count="exact")
                .eq("estudante_id", estudante_id)
                .order("atualizado_em", desc=True)
                .range(ini, fim)
                .execute()
            )
        )
        itens = res.data or []
        if itens:
            ids = [i["id"] for i in itens]
            msgs = self._rows(
                self.c.table("mensagens")
                .select("conversa_id,conteudo,criado_em")
                .in_("conversa_id", ids)
                .order("criado_em", desc=True)
            )
            ultima: dict[str, str] = {}
            for m in msgs:
                ultima.setdefault(m["conversa_id"], m["conteudo"])
            for i in itens:
                i["ultima_mensagem"] = ultima.get(i["id"])
        return itens, res.count or 0

    def mensagens_conversa(self, conversa_id: str) -> list[dict[str, Any]]:
        sel = (
            "id,remetente,conteudo,criado_em,"
            "respostas_agente(id,confianca_score,abstencao,"
            "resposta_evidencias(similaridade,posicao_ranking,"
            "documentos_chunks(conteudo,documento_id,documentos_oficiais(titulo,fonte,data_atualizacao))),"
            "feedback_respostas(avaliacao,criado_em))"
        )
        linhas = self._rows(self.c.table("mensagens").select(sel).eq("conversa_id", conversa_id).order("criado_em"))
        saida = []
        for m in linhas:
            resp = (m.pop("respostas_agente") or [None])[0]
            item = {k: m[k] for k in ("id", "remetente", "conteudo", "criado_em")}
            if resp:
                fontes = []
                for ev in sorted(resp.get("resposta_evidencias") or [], key=lambda e: e["posicao_ranking"]):
                    ch = ev.get("documentos_chunks") or {}
                    doc = ch.get("documentos_oficiais") or {}
                    fontes.append(
                        {
                            "documento_id": ch.get("documento_id"),
                            "titulo": doc.get("titulo"),
                            "fonte": doc.get("fonte"),
                            "data_atualizacao": doc.get("data_atualizacao"),
                            "trecho": ch.get("conteudo"),
                            "similaridade": ev.get("similaridade"),
                        }
                    )
                fbs = sorted(resp.get("feedback_respostas") or [], key=lambda f: f["criado_em"])
                item["resposta"] = {
                    "resposta_id": resp["id"],
                    "confianca": resp["confianca_score"],
                    "abstencao": resp["abstencao"],
                    "fontes": fontes,
                    "feedback": fbs[-1]["avaliacao"] if fbs else None,
                }
            saida.append(item)
        return saida

    def encaminhamento_da_conversa(self, conversa_id: str) -> dict[str, Any] | None:
        return self._um(
            self.c.table("encaminhamentos")
            .select("id,status,setor_destino,prazo")
            .eq("conversa_id", conversa_id)
            .order("criado_em", desc=True)
        )

    def dono_da_resposta(self, resposta_id: str) -> str | None:
        r = self._um(
            self.c.table("respostas_agente")
            .select("id,mensagens!inner(conversas!inner(estudante_id))")
            .eq("id", resposta_id)
        )
        if not r:
            return None
        return str(((r.get("mensagens") or {}).get("conversas") or {}).get("estudante_id") or "") or None

    def salvar_feedback(
        self, resposta_id: str, estudante_id: str, avaliacao: str, comentario: str | None
    ) -> dict[str, Any]:
        return self._rpc(
            "salvar_feedback",
            {
                "p_resposta": resposta_id,
                "p_estudante": estudante_id,
                "p_avaliacao": avaliacao,
                "p_comentario": comentario,
            },
        )

    # ------------------------------------------------------------------ casos
    def _filtrar_fila(self, q: Any, f: FiltrosFila, com_categoria: bool) -> Any:
        if com_categoria and f.categorias:
            q = q.in_("categoria", f.categorias)
        if f.prioridades:
            q = q.in_("prioridade", f.prioridades)
        if f.status:
            q = q.in_("status", f.status)
        if f.responsavel == "eu" and f.usuario_id:
            q = q.eq("atendente_responsavel", f.usuario_id)
        elif f.responsavel == "nenhum":
            q = q.is_("atendente_responsavel", "null")
        if f.busca:
            q = q.ilike("busca", f"%{f.busca}%")
        return q

    def listar_fila(self, filtros: FiltrosFila) -> PaginaFila:
        ini, fim = self._faixa(filtros.pagina, filtros.por_pagina)
        q = self._filtrar_fila(self.c.table("vw_fila_risco_busca").select("*", count="exact"), filtros, True)
        for col, desc, nf in _ORDENACAO.get(filtros.ordenar, _ORDENACAO["prioridade"]):
            q = q.order(col, desc=desc, nullsfirst=nf)
        q = q.order("estudante_id")  # desempate estável para a paginação
        res = self._exec(lambda: q.range(ini, fim).execute())
        contagem = {}
        for cat in ("verde", "amarelo", "vermelho"):
            qc = self._filtrar_fila(
                self.c.table("vw_fila_risco_busca").select("estudante_id", count="exact", head=True), filtros, False
            )
            contagem[cat] = self._exec(lambda qc=qc, cat=cat: qc.eq("categoria", cat).execute()).count or 0
        return PaginaFila(itens=res.data or [], total=res.count or 0, contagem=contagem)

    def obter_item_fila(self, estudante_id: str) -> dict[str, Any] | None:
        return self._um(self.c.table("vw_fila_risco").select("*").eq("estudante_id", estudante_id))

    def obter_score(self, score_id: str) -> dict[str, Any] | None:
        return self._um(self.c.table("scores_risco").select("*").eq("id", score_id))

    def serie_scores(self, estudante_id: str, limite: int) -> list[dict[str, Any]]:
        linhas = self._rows(
            self.c.table("scores_risco")
            .select("id,competencia,probabilidade,categoria,versao_modelo,calculado_em")
            .eq("estudante_id", estudante_id)
            .order("competencia", desc=True)
            .order("calculado_em", desc=True)
            .limit(limite * 3)
        )
        por_mes: dict[str, dict[str, Any]] = {}
        for r in linhas:  # um ponto por competência (o mais recente)
            por_mes.setdefault(str(r["competencia"]), r)
        return sorted(por_mes.values(), key=lambda r: str(r["competencia"]))[-limite:]

    def ultima_validacao(self, caso_id: str) -> dict[str, Any] | None:
        return self._um(
            self.c.table("validacoes_caso").select("*").eq("caso_id", caso_id).order("criado_em", desc=True)
        )

    def registrar_validacao(self, dados: dict[str, Any]) -> dict[str, Any]:
        return self._rpc("registrar_validacao_caso", {"p": dados})

    def eventos_historico(self, estudante_id: str) -> dict[str, list[dict[str, Any]]]:
        caso = self._um(self.c.table("casos_risco").select("id").eq("estudante_id", estudante_id))
        scores = self._rows(
            self.c.table("scores_risco")
            .select("id,competencia,probabilidade,categoria,versao_modelo,calculado_em")
            .eq("estudante_id", estudante_id)
        )
        contatos = self._rows(
            self.c.table("contatos_asa")
            .select("id,atendente_id,origem,canal,motivo,resultado,ocorrido_em")
            .eq("estudante_id", estudante_id)
        )
        validacoes, eventos = [], []
        if caso:
            validacoes = self._rows(self.c.table("validacoes_caso").select("*").eq("caso_id", caso["id"]))
            eventos = self._rows(self.c.table("eventos_caso").select("*").eq("caso_id", caso["id"]))
        return {"scores": scores, "contatos": contatos, "validacoes": validacoes, "eventos": eventos}

    def estudante_existe(self, estudante_id: str) -> bool:
        return self._um(self.c.table("estudantes").select("id").eq("id", estudante_id)) is not None

    def features_recentes(self, estudante_id: str) -> dict[str, Any] | None:
        return self._um(
            self.c.table("estudante_features")
            .select("*")
            .eq("estudante_id", estudante_id)
            .order("competencia", desc=True)
        )

    def registrar_score(self, dados: dict[str, Any]) -> str:
        return str(self._rpc("registrar_score_risco", {"p": dados}))

    # ------------------------------------------------------------------ admin
    def dashboard(self, de: date, ate: date) -> dict[str, Any]:
        return self._rpc("dashboard_agregados", {"p_de": de.isoformat(), "p_ate": ate.isoformat()}, escrita=False)

    def listar_documentos(
        self, busca: str | None, categoria: str | None, ativo: bool | None, pagina: int, por_pagina: int
    ) -> tuple[list[dict[str, Any]], int]:
        ini, fim = self._faixa(pagina, por_pagina)
        q = self.c.table("vw_documentos_resumo").select("*", count="exact")
        if busca:
            q = q.ilike("busca", f"%{busca}%")
        if categoria:
            q = q.eq("categoria", categoria)
        if ativo is not None:
            q = q.eq("ativo", ativo)
        res = self._exec(lambda: q.order("titulo").order("id").range(ini, fim).execute())
        return res.data or [], res.count or 0

    def obter_documento(self, documento_id: str) -> dict[str, Any] | None:
        doc = self._um(self.c.table("vw_documentos_resumo").select("*").eq("id", documento_id))
        if not doc:
            return None
        versoes = self._rows(
            self.c.table("documentos_versoes")
            .select("versao,conteudo,data_atualizacao,motivo,alterado_por,criado_em")
            .eq("documento_id", documento_id)
            .order("versao", desc=True)
        )
        nomes = self.nomes_perfis([v["alterado_por"] for v in versoes if v.get("alterado_por")])
        vigente = next((v for v in versoes if v["versao"] == doc["versao"]), None)
        if vigente:
            doc["conteudo"] = vigente["conteudo"]
        else:
            chunks = self._rows(
                self.c.table("documentos_chunks")
                .select("conteudo")
                .eq("documento_id", documento_id)
                .eq("ativo", True)
                .order("ordem")
            )
            doc["conteudo"] = "\n\n".join(c["conteudo"] for c in chunks)
        doc["versoes"] = [
            {
                "versao": v["versao"],
                "data_atualizacao": v["data_atualizacao"],
                "motivo": v["motivo"],
                "alterado_por": nomes.get(str(v.get("alterado_por"))),
                "criado_em": v["criado_em"],
            }
            for v in versoes
        ]
        return doc

    def criar_documento(self, dados: dict[str, Any]) -> str:
        return str(self._rpc("publicar_documento", {"p": dados}))

    def nova_versao_documento(self, dados: dict[str, Any]) -> None:
        self._rpc("publicar_nova_versao_documento", {"p": dados})

    def desativar_documento(self, documento_id: str, motivo: str, usuario_id: str) -> None:
        self._rpc("desativar_documento", {"p_documento": documento_id, "p_motivo": motivo, "p_usuario": usuario_id})

    # ------------------------------------------------------------------ auditoria
    def registrar_auditoria(self, registro: dict[str, Any]) -> None:
        self._exec(lambda: self.c.table("auditoria_logs").insert(registro).execute(), idempotente=False)
