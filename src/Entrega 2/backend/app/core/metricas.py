"""Métricas Prometheus (GET /metrics). Nomes definidos no contrato."""

from __future__ import annotations

import os

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest, multiprocess

http_requests_total = Counter("http_requests_total", "Requisições HTTP", ["rota", "metodo", "status"])
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Latência das requisições HTTP",
    ["rota", "metodo"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15),
)
http_erros_total = Counter("http_erros_total", "Respostas de erro por código", ["rota", "codigo"])

chat_respostas_total = Counter("chat_respostas_total", "Respostas do chat", ["abstencao"])
chat_abstencoes_total = Counter("chat_abstencoes_total", "Abstenções do chat por motivo", ["motivo"])
chat_feedback_total = Counter("chat_feedback_total", "Feedback das respostas", ["avaliacao"])
embedding_cache_acertos_total = Counter(
    "embedding_cache_acertos_total", "Perguntas repetidas servidas pelo cache de embeddings"
)
embedding_falhas_total = Counter("embedding_falhas_total", "Falhas de vetorização", ["provedor"])
rag_recuperacoes_total = Counter(
    "rag_recuperacoes_total", "Recuperações do RAG por método (vetorial|lexical|nenhum)", ["metodo"]
)
rag_fallback_total = Counter("rag_fallback_total", "Uso do fallback lexical (TF-IDF) do RAG")
risco_inferencias_total = Counter("risco_inferencias_total", "Inferências do modelo de risco", ["versao_modelo"])
validacoes_total = Counter("validacoes_total", "Validações humanas de casos", ["decisao"])


def exportar() -> tuple[bytes, str]:
    # Com UVICORN_WORKERS > 1, cada processo grava em PROMETHEUS_MULTIPROC_DIR e o
    # /metrics soma todos (senão cada raspagem veria só o worker que atendeu).
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registro = CollectorRegistry()
        multiprocess.MultiProcessCollector(registro)  # type: ignore[no-untyped-call]
        return generate_latest(registro), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
