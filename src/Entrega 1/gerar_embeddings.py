"""
Gera os vetores (embeddings) de todos os chunks + calcula uma tabela de IDF
(peso por raridade do termo) a partir do corpus inteiro, e salva os dois:
- embeddings -> direto no Supabase (coluna embedding)
- tabela de IDF -> arquivo idf_table.json (precisa ser commitado no repositório,
  porque a API no Vercel usa esse MESMO arquivo para pesar a pergunta do
  estudante do jeito certo, no fallback)

A vetorização principal usa a Hugging Face Inference API (modelo
BAAI/bge-small-en-v1.5, 384 dimensões). Se a chamada falhar
por qualquer motivo (token ausente, timeout, rate limit, etc.), cai
automaticamente para o método antigo (hashing + TF-IDF) — só loga o motivo.
A tabela de IDF continua sendo calculada e salva sempre, pra esse fallback
funcionar tanto aqui quanto em api/perguntar.py.

Rode isso sempre que adicionar/editar documentos na base de conhecimento.

.env necessário (mesma pasta):
    SUPABASE_URL=https://SEU-PROJETO.supabase.co
    SUPABASE_SERVICE_KEY=sua-chave-aqui
    HF_API_TOKEN=hf_sua-chave-aqui
"""

import truststore
truststore.inject_into_ssl()

import os
import re
import json
import math
import hashlib
import unicodedata
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
VECTOR_DIM = 384
HF_API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5"
HF_TIMEOUT = 10  # segundos

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

STOPWORDS = {
    "a","o","as","os","de","da","do","das","dos","que","e","é","para","com",
    "um","uma","no","na","nos","nas","em","por","se","meu","minha","tenho",
    "preciso","como","qual","quais","sobre","ao","aos","esse","essa","isso",
    "eu","voce","você","tem","ter","vou","vai","sera","será","ser","sao","são",
    "ou","mais","muito","ja","já","ainda","depois","antes","entao","então"
}

SYNONYMS = {
    "suspender":"trancar","suspendo":"trancar","suspensao":"trancar","suspensão":"trancar",
    "pausar":"trancar","pauso":"trancar","parar":"trancar","paro":"trancar",
    "cancelar":"cancelamento","cancelo":"cancelamento","cancelado":"cancelamento",
    "trancamento":"trancar","tranco":"trancar","trancando":"trancar","trancado":"trancar",
    "desistir":"cancelamento","desistencia":"cancelamento","desistência":"cancelamento",
    "boleto":"financeiro","boletos":"financeiro","mensalidade":"financeiro","mensalidades":"financeiro",
    "pagamento":"financeiro","pagar":"financeiro","divida":"financeiro","dívida":"financeiro",
    "desconto":"financeiro","valor":"financeiro","preco":"financeiro","preço":"financeiro",
    "auxilio":"auxiliofinanceiro","auxílio":"auxiliofinanceiro","emergencial":"auxiliofinanceiro",
    "vulnerabilidade":"auxiliofinanceiro",
    "comprovante":"declaracao","comprovantes":"declaracao","atestado":"declaracao",
    "declaracoes":"declaracao","declaração":"declaracao","declaraçao":"declaracao",
    "certidao":"declaracao","certidão":"declaracao",
    "fies":"financiamento","prouni":"financiamento","bolsas":"financiamento","bolsa":"financiamento",
    "bolsista":"financiamento","financiado":"financiamento",
    "reprovado":"desempenho","reprovacao":"desempenho","reprovação":"desempenho","reprovar":"desempenho",
    "reprovando":"desempenho","nota":"desempenho","notas":"desempenho","media":"desempenho","média":"desempenho",
    "falta":"desempenho","faltas":"desempenho","faltei":"desempenho","frequencia":"desempenho","frequência":"desempenho",
    "presenca":"desempenho","presença":"desempenho",
    "prova":"avaliacao","provas":"avaliacao","avaliacao":"avaliacao","avaliação":"avaliacao",
    "exame":"avaliacao","teste":"avaliacao",
    "segundachamada":"segundachamada","2achamada":"segundachamada",
    "reposicao":"segundachamada","reposição":"segundachamada","perdi":"segundachamada",
    "revisao":"revisaonota","revisão":"revisaonota","recurso":"revisaonota","contestar":"revisaonota",
    "errada":"revisaonota","corrigir":"revisaonota",
    "dispensa":"aproveitamento","dispensar":"aproveitamento","equivalencia":"aproveitamento",
    "equivalência":"aproveitamento","aproveitar":"aproveitamento",
    "trocar":"transferencia","troca":"transferencia","mudar":"transferencia","mudanca":"transferencia",
    "mudança":"transferencia","transferir":"transferencia","transferência":"transferencia",
    "periodo":"turno","período":"turno","horario":"turno","horário":"turno",
    "estagio":"estagio","estágio":"estagio","estagiar":"estagio","estagiario":"estagio",
    "tcc":"tcc","monografia":"tcc","orientador":"tcc","orientacao":"tcc","orientação":"tcc",
    "livro":"biblioteca","livros":"biblioteca","emprestimo":"biblioteca","empréstimo":"biblioteca",
    "emprestar":"biblioteca","devolver":"biblioteca","devolucao":"biblioteca","devolução":"biblioteca",
    "carreira":"carreira","emprego":"carreira","vaga":"carreira","vagas":"carreira",
    "curriculo":"carreira","currículo":"carreira","entrevista":"carreira",
    "medico":"atestadomedico","médico":"atestadomedico","saude":"atestadomedico","saúde":"atestadomedico",
    "doente":"atestadomedico","doenca":"atestadomedico","doença":"atestadomedico",
    "diploma":"certificado","certificado":"certificado","formatura":"certificado",
    "colacao":"certificado","colação":"certificado","formar":"certificado",
    "intercambio":"intercambio","intercâmbio":"intercambio","exterior":"intercambio","fora":"intercambio",
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


def vectorize(text: str, idf_table, dim: int = VECTOR_DIM):
    tokens = tokenize(text)
    counts = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1

    vec = [0.0] * dim
    for t, c in counts.items():
        idx = hash_token(t, dim)
        tf = 1.0 + math.log(c)
        vec[idx] += tf * idf_table[idx]

    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def vectorize_hf(texto: str, timeout: int = HF_TIMEOUT):
    """Gera o embedding semântico chamando a Hugging Face Inference API
    (BAAI/bge-small-en-v1.5, 384 dimensões).
    Levanta exceção se algo der errado (token ausente, timeout, rate limit,
    formato inesperado) — quem chama decide o fallback."""
    hf_token = os.environ.get("HF_API_TOKEN", "")
    if not hf_token:
        raise RuntimeError("HF_API_TOKEN não configurado")

    resposta = requests.post(
        HF_API_URL,
        headers={"Authorization": f"Bearer {hf_token}"},
        json={"inputs": texto, "options": {"wait_for_model": True}},
        timeout=timeout,
    )
    resposta.raise_for_status()
    dados = resposta.json()

    if isinstance(dados, dict) and "error" in dados:
        raise RuntimeError(f"Hugging Face retornou erro: {dados['error']}")

    if isinstance(dados, list) and dados and isinstance(dados[0], (int, float)):
        # Formato A: a API já devolve o vetor da frase pronto.
        vetor = [float(v) for v in dados]
    elif isinstance(dados, list) and dados and isinstance(dados[0], list):
        # Formato B: a API devolve um vetor por token -> mean pooling manual.
        matriz = dados[0] if dados[0] and isinstance(dados[0][0], list) else dados
        n_tokens = len(matriz)
        dim = len(matriz[0])
        vetor = [sum(tok[i] for tok in matriz) / n_tokens for i in range(dim)]
    else:
        raise RuntimeError(f"Formato de resposta inesperado da Hugging Face: {dados!r}")

    if len(vetor) != VECTOR_DIM:
        raise RuntimeError(f"Embedding HF com dimensão {len(vetor)}, esperado {VECTOR_DIM}")

    norm = sum(v * v for v in vetor) ** 0.5
    return [v / norm for v in vetor] if norm > 0 else vetor


def vectorize_com_fallback(texto: str, idf_table):
    """Tenta o embedding semântico (Hugging Face); se falhar por qualquer
    motivo, cai automaticamente no método antigo (hashing + TF-IDF) — só
    loga o motivo da falha."""
    try:
        return vectorize_hf(texto)
    except Exception as e:
        print(f"  [vectorize_hf] falhou ({type(e).__name__}: {e}); usando fallback TF-IDF")
        return vectorize(texto, idf_table)


def calcular_idf(todos_tokens, dim: int = VECTOR_DIM):
    n_docs = len(todos_tokens)
    doc_freq = [0] * dim

    for tokens in todos_tokens:
        buckets_no_doc = set(hash_token(t, dim) for t in tokens)
        for b in buckets_no_doc:
            doc_freq[b] += 1

    idf_table = [
        math.log((n_docs + 1) / (df + 1)) + 1
        for df in doc_freq
    ]
    return idf_table


def main():
    print("Buscando todos os chunks...")
    resposta = supabase.table("documentos_chunks").select("id, conteudo").execute()
    chunks = resposta.data

    if not chunks:
        print("Nenhum chunk encontrado. Rode o seed_v2.sql primeiro.")
        return

    print(f"{len(chunks)} chunks encontrados. Calculando tabela de IDF...")
    todos_tokens = [tokenize(c["conteudo"]) for c in chunks]
    idf_table = calcular_idf(todos_tokens)

    with open("idf_table.json", "w", encoding="utf-8") as f:
        json.dump(idf_table, f)
    print("idf_table.json salvo. IMPORTANTE: comite esse arquivo no GitHub também!")

    print("Gerando e salvando embeddings (Hugging Face, com fallback TF-IDF)...")
    for chunk in chunks:
        embedding = vectorize_com_fallback(chunk["conteudo"], idf_table)
        supabase.table("documentos_chunks").update(
            {"embedding": embedding}
        ).eq("id", chunk["id"]).execute()
        print(f"  ok: chunk {chunk['id']}")

    print(f"\nConcluído! {len(chunks)} chunks vetorizados.")


if __name__ == "__main__":
    main()
