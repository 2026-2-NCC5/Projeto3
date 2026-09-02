"""
Gera os vetores (embeddings) de todos os chunks cadastrados e salva no Supabase.
Rode isso UMA VEZ localmente, depois de rodar o schema.sql + seed.sql,
e sempre que adicionar/editar documentos na base de conhecimento.

Instalação:
    pip install supabase python-dotenv

.env necessário (mesma pasta):
    SUPABASE_URL=https://SEU-PROJETO.supabase.co
    SUPABASE_SERVICE_KEY=sua-chave-service-role-aqui   <- precisa ser a service_role,
                                                           não a anon (para poder
                                                           atualizar a coluna embedding)
"""

import os
import re
import hashlib
import unicodedata
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
VECTOR_DIM = 384

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

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
    return re.sub(r"[^a-z0-9\s]", " ", text)


def tokenize(text: str):
    tokens = normalize(text).split()
    tokens = [t for t in tokens if len(t) > 2 and t not in STOPWORDS]
    return [SYNONYMS.get(t, t) for t in tokens]


def hash_token(token: str, dim: int = VECTOR_DIM) -> int:
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % dim


def vectorize(text: str, dim: int = VECTOR_DIM):
    vec = [0.0] * dim
    for t in tokenize(text):
        vec[hash_token(t, dim)] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def main():
    print("Buscando chunks sem embedding...")
    resposta = supabase.table("documentos_chunks").select("id, conteudo").execute()
    chunks = resposta.data

    if not chunks:
        print("Nenhum chunk encontrado. Rode o seed.sql primeiro.")
        return

    for chunk in chunks:
        embedding = vectorize(chunk["conteudo"])
        supabase.table("documentos_chunks").update(
            {"embedding": embedding}
        ).eq("id", chunk["id"]).execute()
        print(f"Embedding salvo para chunk {chunk['id']}")

    print(f"\nConcluído! {len(chunks)} chunks vetorizados e salvos no Supabase.")


if __name__ == "__main__":
    main()
