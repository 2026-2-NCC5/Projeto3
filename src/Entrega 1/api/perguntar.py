"""
API do Agente para o Estudante (ASA/FECAP) - v3 com embeddings semânticos
------------------------------------------------------------------
Cada arquivo dentro de /api vira uma rota automaticamente no Vercel:
este arquivo fica disponível em /api/perguntar sem precisar de vercel.json.

A vetorização principal usa a Hugging Face Inference API (modelo
BAAI/bge-small-en-v1.5, 384 dimensões). Se a chamada
falhar por qualquer motivo (token ausente, timeout, rate limit, etc.),
cai automaticamente para o método antigo (hashing + TF-IDF), usando a
MESMA lógica e a tabela de IDF (idf_table.json) do gerar_embeddings.py —
por isso os dois precisam ficar sincronizados (rode gerar_embeddings.py
de novo sempre que atualizar os documentos, e comite o idf_table.json).

Variáveis de ambiente necessárias (Vercel > Project Settings > Environment Variables):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    HF_API_TOKEN   (token grátis da Hugging Face; veja README/.env.example)
"""

import os
import re
import json
import math
import hashlib
import unicodedata
import requests
from http.server import BaseHTTPRequestHandler
from supabase import create_client

VECTOR_DIM = 384
CONFIDENCE_THRESHOLD = 0.15
HF_API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5"
HF_TIMEOUT = 10  # segundos

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


def normalize(text):
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", text)


def tokenize(text):
    tokens = normalize(text).split()
    tokens = [t for t in tokens if len(t) > 2 and t not in STOPWORDS]
    return [SYNONYMS.get(t, t) for t in tokens]


def hash_token(token, dim=VECTOR_DIM):
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % dim


def carregar_idf_table():
    """Carrega a tabela de IDF gerada pelo gerar_embeddings.py. Se não achar
    o arquivo (ex: esqueceram de commitar), cai para peso uniforme (1.0),
    que ainda funciona, só que sem o benefício do TF-IDF."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho = os.path.join(base_dir, "idf_table.json")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return [1.0] * VECTOR_DIM


IDF_TABLE = carregar_idf_table()


def vectorize(text, dim=VECTOR_DIM):
    tokens = tokenize(text)
    counts = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1

    vec = [0.0] * dim
    for t, c in counts.items():
        idx = hash_token(t, dim)
        tf = 1.0 + math.log(c)
        vec[idx] += tf * IDF_TABLE[idx]

    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def vectorize_hf(texto, timeout=HF_TIMEOUT):
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


def vectorize_com_fallback(texto):
    """Tenta o embedding semântico (Hugging Face); se falhar por qualquer
    motivo, cai automaticamente no método antigo (hashing + TF-IDF) pra não
    quebrar a resposta ao estudante — só loga o motivo da falha."""
    try:
        return vectorize_hf(texto)
    except Exception as e:
        print(f"[vectorize_hf] falhou ({type(e).__name__}: {e}); usando fallback TF-IDF")
        return vectorize(texto)


def processar_pergunta(pergunta):
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        return {
            "resposta": "[DEBUG] Variáveis SUPABASE_URL / SUPABASE_SERVICE_KEY não encontradas no servidor.",
            "confianca": 0.0,
            "abstencao": True,
            "evidencias": [],
        }

    try:
        supabase = create_client(supabase_url, supabase_key)
        query_embedding = vectorize_com_fallback(pergunta)

        resultado = supabase.rpc(
            "buscar_chunks_similares",
            {
                "query_embedding": query_embedding,
                "limite": 3,
                "limiar_similaridade": 0.0,
            },
        ).execute()

        chunks = resultado.data or []

        evidencias = [
            {
                "titulo": c["titulo_documento"],
                "fonte": c["fonte_documento"],
                "similaridade": round(c["similaridade"], 4),
                "atualizado_em": c.get("data_atualizacao"),
                "trecho": c["conteudo"],
            }
            for c in chunks
        ]

        if not chunks or chunks[0]["similaridade"] < CONFIDENCE_THRESHOLD:
            return {
                "resposta": (
                    "Não encontrei essa informação com confiança suficiente nas fontes "
                    "oficiais disponíveis. Vou te encaminhar para um atendente do ASA."
                ),
                "confianca": chunks[0]["similaridade"] if chunks else 0.0,
                "abstencao": True,
                "evidencias": evidencias,
            }

        melhor = chunks[0]
        return {
            "resposta": melhor["conteudo"],
            "confianca": round(melhor["similaridade"], 4),
            "abstencao": False,
            "evidencias": evidencias,
        }

    except Exception as e:
        return {
            "resposta": f"[DEBUG] {type(e).__name__}: {str(e)}",
            "confianca": 0.0,
            "abstencao": True,
            "evidencias": [],
        }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            pergunta = data.get("pergunta", "")

            resultado = processar_pergunta(pergunta)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(resultado).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "resposta": f"[DEBUG] Erro no handler: {type(e).__name__}: {str(e)}",
                "confianca": 0.0,
                "abstencao": True,
                "evidencias": [],
            }).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
