"""Caso de uso do chat: RAG + persistência + auditoria + métricas."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core import metricas
from app.core.auth import Usuario
from app.core.config import Settings
from app.core.erros import ErroAPI
from app.db.repositorio import ErroRepositorio, RegistroNaoEncontrado, Repositorio
from app.rag.embeddings import CadeiaEmbeddings, FalhaVetorizacao, Vetorizacao
from app.rag.recuperacao import ConfigRAG, FalhaBusca, Recuperacao, recuperar
from app.rag.reescrita import Mensagem
from app.rag.resposta import compor_resposta
from app.schemas import ChatPergunta, ChatResposta, FeedbackEntrada
from app.services.auditoria import auditar
from app.services.indice import CacheIndiceLexical

log = logging.getLogger("asa.chat")
PRAZO_ENCAMINHAMENTO = timedelta(days=2)


class LimitadorTaxa:
    """Janela deslizante de 60 s por usuário (em memória, por instância)."""

    def __init__(self, por_minuto: int) -> None:
        self._limite = por_minuto
        self._eventos: dict[str, deque[float]] = {}
        self._trava = threading.Lock()

    def verificar(self, chave: str) -> None:
        if self._limite <= 0:
            return
        agora = time.monotonic()
        with self._trava:
            fila = self._eventos.setdefault(chave, deque())
            while fila and agora - fila[0] > 60:
                fila.popleft()
            if len(fila) >= self._limite:
                espera = max(1, int(60 - (agora - fila[0])) + 1)
                raise ErroAPI("limite_excedido", headers={"Retry-After": str(espera)})
            fila.append(agora)


def _versao_pipeline(settings: Settings, rec: Recuperacao) -> str:
    if rec.metodo == "lexical":
        return f"{settings.rag_versao}+tfidf"
    modelo = (rec.modelo_embedding or settings.embedding_model).split("/")[-1].lower()
    return f"{settings.rag_versao}+{modelo}"


def _fonte(t: Any) -> dict[str, Any]:
    return {
        "documento_id": t.documento_id,
        "titulo": t.titulo,
        "fonte": t.fonte,
        "data_atualizacao": t.data_atualizacao,
        "trecho": t.conteudo,
        "similaridade": min(max(t.similaridade, 0.0), 1.0),
    }


class ServicoChat:
    def __init__(
        self, repo: Repositorio, embeddings: CadeiaEmbeddings, indice: CacheIndiceLexical, settings: Settings
    ) -> None:
        self.repo = repo
        self.embeddings = embeddings
        self.indice = indice
        self.settings = settings
        self.limitador = LimitadorTaxa(settings.chat_rate_limit_por_minuto)
        self.config = ConfigRAG(
            limiar=settings.confidence_threshold,
            top_k=settings.rag_top_k,
            fallback_lexical=settings.rag_fallback_lexical,
            limiar_lexical=settings.rag_limiar_lexical,
        )

    # ------------------------------------------------------------------ helpers
    def _estudante_id(self, usuario: Usuario) -> str:
        if not usuario.estudante_id:
            raise ErroAPI("sem_permissao", "Seu cadastro de estudante não foi encontrado. Procure o ASA.")
        return usuario.estudante_id

    def _conversa_do_estudante(self, conversa_id: str, estudante_id: str) -> dict[str, Any]:
        try:
            conversa = self.repo.obter_conversa(conversa_id)
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        if not conversa or str(conversa["estudante_id"]) != estudante_id:
            raise ErroAPI("nao_encontrado", "Conversa não encontrada.")
        return conversa

    def _vetorizar(self, texto: str) -> Vetorizacao:
        return self.embeddings.vetorizar(texto)

    def _buscar(self, vetor: list[float], k: int) -> list[dict[str, Any]]:
        try:
            return self.repo.buscar_chunks_similares(vetor, k)
        except ErroRepositorio as e:
            raise FalhaBusca(str(e)) from e

    # ------------------------------------------------------------------ POST /chat
    def responder(self, usuario: Usuario, pergunta: ChatPergunta) -> ChatResposta:
        estudante_id = self._estudante_id(usuario)
        self.limitador.verificar(usuario.id)
        inicio = time.perf_counter()
        conversa_id = str(pergunta.conversa_id) if pergunta.conversa_id else None

        historico: list[Mensagem] = []
        if conversa_id:
            self._conversa_do_estudante(conversa_id, estudante_id)
            try:
                salvas = self.repo.historico_conversa(conversa_id, self.settings.rag_historico_max)
                historico = [
                    Mensagem("estudante" if m["remetente"] == "estudante" else "agente", m["conteudo"]) for m in salvas
                ]
            except ErroRepositorio:
                log.warning("histórico salvo indisponível; usando o enviado pelo cliente")
        if not historico:  # atalho do cliente (contrato)
            historico = [Mensagem(m.papel, m.conteudo) for m in pergunta.historico][-self.settings.rag_historico_max :]

        texto = pergunta.mensagem.strip()
        rec = recuperar(
            texto,
            historico,
            vetorizar=self._vetorizar,
            buscar_vetorial=self._buscar,
            indice_lexical=self.indice.obter,
            config=self.config,
        )
        resposta_txt, usados = compor_resposta(rec)
        # Em abstenção, as fontes trazem os candidatos fracos (contrato), se houver.
        fontes_trechos = usados if not rec.abstencao else rec.trechos
        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        versao = _versao_pipeline(self.settings, rec)
        agora = datetime.now(UTC)

        resposta_id = str(uuid.uuid4())
        encaminhamento = None
        try:
            salvo = self.repo.registrar_resposta_chat(
                {
                    "estudante_id": estudante_id,
                    "conversa_id": conversa_id,
                    "resposta_id": resposta_id,
                    "titulo": texto[:80],
                    "pergunta": texto,
                    "resposta": resposta_txt,
                    "confianca": rec.confianca,
                    "abstencao": rec.abstencao,
                    "versao_modelo": versao,
                    "modelo_embedding": rec.modelo_embedding,
                    "latencia_ms": latencia_ms,
                    "evidencias": [
                        {"chunk_id": t.chunk_id, "similaridade": t.similaridade, "posicao": i}
                        for i, t in enumerate(rec.trechos, start=1)
                    ],
                    "encaminhar": rec.abstencao,
                    "motivo_encaminhamento": f"Abstenção do agente ({rec.motivo_abstencao})",
                    "prazo_encaminhamento": (agora + PRAZO_ENCAMINHAMENTO).isoformat(),
                }
            )
            conversa_id = str(salvo["conversa_id"])
            encaminhamento = salvo.get("encaminhamento")
        except RegistroNaoEncontrado as e:
            raise ErroAPI("nao_encontrado", "Conversa não encontrada.") from e
        except ErroRepositorio:
            # O estudante ainda recebe a resposta; o histórico desta troca se perde (alerta no log).
            log.error("falha ao persistir a resposta do chat", extra={"resposta_id": resposta_id})
            conversa_id = conversa_id or str(uuid.uuid4())

        # métricas
        metricas.chat_respostas_total.labels(str(rec.abstencao).lower()).inc()
        metricas.rag_recuperacoes_total.labels(rec.metodo).inc()
        if rec.abstencao and rec.motivo_abstencao:
            metricas.chat_abstencoes_total.labels(rec.motivo_abstencao).inc()
        if rec.usou_fallback:
            metricas.rag_fallback_total.inc()

        auditar(
            self.repo,
            usuario,
            "resposta_gerada",
            "respostas_agente",
            resposta_id,
            entrada={
                "pergunta": texto,
                "consulta": rec.consulta,
                "reescrita": rec.reescrita,
                "conversa_id": conversa_id,
            },
            resultado={
                "abstencao": rec.abstencao,
                "motivo": rec.motivo_abstencao,
                "confianca": rec.confianca,
                "metodo": rec.metodo,
                "provedor": rec.provedor,
                "chunks": [t.chunk_id for t in rec.trechos],
                "latencia_ms": latencia_ms,
                "falhas": rec.falhas,
            },
            versao=versao,
        )
        log.info(
            "chat respondido",
            extra={
                "abstencao": rec.abstencao,
                "motivo": rec.motivo_abstencao,
                "metodo": rec.metodo,
                "confianca": rec.confianca,
                "reescrita": rec.reescrita,
                "latencia_ms": latencia_ms,
            },
        )

        return ChatResposta(
            resposta=resposta_txt,
            fontes=[_fonte(t) for t in fontes_trechos],
            confianca=min(max(rec.confianca, 0.0), 1.0),
            abstencao=rec.abstencao,
            motivo_abstencao=rec.motivo_abstencao,
            encaminhamento=encaminhamento,
            resposta_id=resposta_id,
            conversa_id=conversa_id,
            versao_modelo=versao,
            gerada_em=agora,
        )

    # ------------------------------------------------------------------ conversas
    def listar(self, usuario: Usuario, pagina: int, por_pagina: int) -> dict[str, Any]:
        estudante_id = self._estudante_id(usuario)
        try:
            itens, total = self.repo.listar_conversas(estudante_id, pagina, por_pagina)
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "itens": [self._resumo(c) for c in itens]}

    @staticmethod
    def _resumo(c: dict[str, Any]) -> dict[str, Any]:
        ultima = c.get("ultima_mensagem")
        return {
            "id": c["id"],
            "titulo": c.get("titulo") or "Conversa",
            "status": c["status"],
            "iniciada_em": c["iniciada_em"],
            "atualizada_em": c.get("atualizado_em") or c["iniciada_em"],
            "ultima_mensagem": (ultima[:137] + "...") if ultima and len(ultima) > 140 else ultima,
        }

    def detalhe(self, usuario: Usuario, conversa_id: str) -> dict[str, Any]:
        estudante_id = self._estudante_id(usuario)
        conversa = self._conversa_do_estudante(conversa_id, estudante_id)
        try:
            mensagens = self.repo.mensagens_conversa(conversa_id)
            enc = self.repo.encaminhamento_da_conversa(conversa_id)
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        resumo = self._resumo({**conversa, "ultima_mensagem": mensagens[-1]["conteudo"] if mensagens else None})
        return {**resumo, "mensagens": mensagens, "encaminhamento": enc}

    # ------------------------------------------------------------------ feedback
    def feedback(self, usuario: Usuario, entrada: FeedbackEntrada) -> dict[str, Any]:
        estudante_id = self._estudante_id(usuario)
        resposta_id = str(entrada.resposta_id)
        try:
            if self.repo.dono_da_resposta(resposta_id) != estudante_id:
                raise ErroAPI("nao_encontrado", "Resposta não encontrada.")
            salvo = self.repo.salvar_feedback(resposta_id, estudante_id, entrada.avaliacao, entrada.comentario)
        except RegistroNaoEncontrado as e:
            raise ErroAPI("nao_encontrado", "Resposta não encontrada.") from e
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        metricas.chat_feedback_total.labels(entrada.avaliacao).inc()
        auditar(
            self.repo,
            usuario,
            "feedback_resposta",
            "feedback_respostas",
            str(salvo["id"]),
            entrada={
                "resposta_id": resposta_id,
                "avaliacao": entrada.avaliacao,
                "tem_comentario": bool(entrada.comentario),
            },
            resultado={"id": str(salvo["id"])},
        )
        return {
            "id": salvo["id"],
            "resposta_id": resposta_id,
            "avaliacao": salvo["avaliacao"],
            "comentario": salvo.get("comentario"),
            "criado_em": salvo["criado_em"],
        }


__all__ = ["FalhaVetorizacao", "LimitadorTaxa", "ServicoChat"]
