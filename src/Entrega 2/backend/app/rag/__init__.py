"""Recuperação (RAG) isolada e testável. API pública para o backend e para ml/."""

from app.rag.chunking import dividir_em_chunks
from app.rag.embeddings import (
    CadeiaEmbeddings,
    CloudflareEmbedding,
    FalhaVetorizacao,
    HuggingFaceEmbedding,
    Vetorizacao,
)
from app.rag.lexical import IndiceLexical
from app.rag.recuperacao import ConfigRAG, FalhaBusca, Recuperacao, Trecho, recuperar
from app.rag.reescrita import Mensagem, Reescrita, eh_continuacao, reescrever_pergunta
from app.rag.resposta import TEXTO_ABSTENCAO, TEXTO_FALHA, compor_resposta

__all__ = [
    "TEXTO_ABSTENCAO",
    "TEXTO_FALHA",
    "CadeiaEmbeddings",
    "CloudflareEmbedding",
    "ConfigRAG",
    "FalhaBusca",
    "FalhaVetorizacao",
    "HuggingFaceEmbedding",
    "IndiceLexical",
    "Mensagem",
    "Recuperacao",
    "Reescrita",
    "Trecho",
    "Vetorizacao",
    "compor_resposta",
    "dividir_em_chunks",
    "eh_continuacao",
    "recuperar",
    "reescrever_pergunta",
]
