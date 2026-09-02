"""
API do Agente para o Estudante (ASA/FECAP)
--------------------------------------------
Roda como Serverless Function no Vercel (@vercel/python).
Recebe a pergunta do estudante, vetoriza (hashing + normalização),
busca os chunks mais similares no Supabase (pgvector) e devolve a
resposta com evidências, fonte e score de confiança.

Variáveis de ambiente necessárias (configurar no painel do Vercel,
em Project Settings > Environment Variables):
    SUPABASE_URL           -> Project Settings > Data API > Project URL
    SUPABASE_SERVICE_KEY   -> Project Settings > API Keys > service_role
                              (NUNCA exponha essa chave no frontend — aqui é seguro
                               porque este código roda só no servidor)
"""

import os
import re
import hashlib
import unicodedata
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

# =============================================================================
# Configuração
# =============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

VECTOR_DIM = 384
CONFIDENCE_THRESHOLD = 0.20  # limiar de similaridade de cosseno para responder com confiança

app = FastAPI(title="ASA Agente para o Estudante - API")

# Em produção, troque "*" pela URL exata do seu projeto no Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Motor de vetorização (Feature Hashing + normalização)
# Mesma lógica do protótipo em JS, agora rodando no backend e persistida
# no Supabase via pgvector — isso é o que torna a busca "real": ao invés de
# recalcular tudo no navegador a cada pergunta, o vetor da pergunta é gerado
# aqui e comparado com os vetores já armazenados no banco.
# =============================================================================

STOPWORDS = {
    "a","o","as","os","de","da","do","das","dos","que","e","é","para","com",
    "um","uma","no","na","nos","nas","em","por","se","meu","minha","tenho",
    "preciso","como","qual","quais","sobre","ao","aos","esse","essa","isso",
    "eu","voce","você","tem","ter","vou","vai","sera","será"
}

SYNONYMS = {
    "suspender": "trancar", "pausar": "trancar", "parar": "trancar",
    "cancelar": "trancar", "trancamento": "trancar",
    "boleto": "financeiro", "mensalidade": "financeiro", "pagamento": "financeiro",
    "divida": "financeiro",
    "comprovante": "declaracao", "atestado": "declaracao", "declaracoes": "declaracao",
    "fies": "financiamento", "prouni": "financiamento", "bolsas": "financiamento",
    "bolsa": "financiamento",
    "reprovado": "desempenho", "reprovacao": "desempenho", "reprovar": "desempenho",
    "nota": "desempenho", "notas": "desempenho", "falta": "desempenho",
    "faltas": "desempenho", "frequencia": "desempenho",
}


def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text


def tokenize(text: str) -> List[str]:
    tokens = normalize(text).split()
    tokens = [t for t in tokens if len(t) > 2 and t not in STOPWORDS]
    tokens = [SYNONYMS.get(t, t) for t in tokens]
    return tokens


def hash_token(token: str, dim: int = VECTOR_DIM) -> int:
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % dim


def vectorize(text: str, dim: int = VECTOR_DIM) -> List[float]:
    """Gera um vetor de dimensão fixa via 'hashing trick' (feature hashing),
    a mesma técnica usada em bibliotecas como o HashingVectorizer do scikit-learn.
    """
    vec = [0.0] * dim
    tokens = tokenize(text)
    for t in tokens:
        idx = hash_token(t, dim)
        vec[idx] += 1.0

    # normalização L2 (norma do vetor = 1) — deixa o vetor pronto para
    # comparação por similaridade de cosseno
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


# =============================================================================
# Modelos de request/response
# =============================================================================

class PerguntaRequest(BaseModel):
    pergunta: str
    estudante_id: Optional[str] = None
    conversa_id: Optional[str] = None


class Evidencia(BaseModel):
    titulo: str
    fonte: str
    similaridade: float
    atualizado_em: Optional[str] = None
    trecho: str


class RespostaAgente(BaseModel):
    resposta: str
    confianca: float
    abstencao: bool
    evidencias: List[Evidencia]


# =============================================================================
# Rotas
# =============================================================================

@app.get("/api")
def raiz():
    return {"status": "ok", "servico": "ASA Agente para o Estudante"}


@app.post("/api/perguntar", response_model=RespostaAgente)
def perguntar(payload: PerguntaRequest):
    if not supabase:
        return RespostaAgente(
            resposta="Erro de configuração: variáveis de ambiente do Supabase não encontradas no servidor.",
            confianca=0.0,
            abstencao=True,
            evidencias=[],
        )

    query_embedding = vectorize(payload.pergunta)

    # Chama a função de busca vetorial criada no schema.sql (pgvector)
    resultado = supabase.rpc(
        "buscar_chunks_similares",
        {
            "query_embedding": query_embedding,
            "limite": 3,
            "limiar_similaridade": 0.0,  # trazemos tudo e decidimos o limiar aqui
        },
    ).execute()

    chunks = resultado.data or []

    evidencias = [
        Evidencia(
            titulo=c["titulo_documento"],
            fonte=c["fonte_documento"],
            similaridade=round(c["similaridade"], 4),
            atualizado_em=c.get("data_atualizacao"),
            trecho=c["conteudo"],
        )
        for c in chunks
    ]

    if not chunks or chunks[0]["similaridade"] < CONFIDENCE_THRESHOLD:
        resposta_final = RespostaAgente(
            resposta=(
                "Não encontrei essa informação com confiança suficiente nas fontes "
                "oficiais disponíveis. Vou te encaminhar para um atendente do ASA."
            ),
            confianca=chunks[0]["similaridade"] if chunks else 0.0,
            abstencao=True,
            evidencias=evidencias,
        )
    else:
        melhor = chunks[0]
        resposta_final = RespostaAgente(
            resposta=melhor["conteudo"],
            confianca=round(melhor["similaridade"], 4),
            abstencao=False,
            evidencias=evidencias,
        )

    # Auditoria best-effort (RF10) — não derruba a resposta se falhar
    try:
        supabase.table("auditoria_logs").insert({
            "acao": "resposta_gerada",
            "entidade": "respostas_agente",
            "detalhes": {
                "pergunta": payload.pergunta,
                "confianca": resposta_final.confianca,
                "abstencao": resposta_final.abstencao,
                "estudante_id": payload.estudante_id,
                "conversa_id": payload.conversa_id,
            },
        }).execute()
    except Exception:
        pass

    return resposta_final
