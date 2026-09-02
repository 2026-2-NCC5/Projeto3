"""
API do Agente para o Estudante (ASA/FECAP) - versão sem framework
--------------------------------------------------------------------
Cada arquivo dentro de /api vira automaticamente uma rota no Vercel:
este arquivo (api/perguntar.py) fica disponível em /api/perguntar
sem precisar de nenhum vercel.json ou configuração extra.

Variáveis de ambiente necessárias (Vercel > Project Settings > Environment Variables):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import re
import json
import hashlib
import unicodedata
from http.server import BaseHTTPRequestHandler
from supabase import create_client

VECTOR_DIM = 384
CONFIDENCE_THRESHOLD = 0.20

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


def vectorize(text, dim=VECTOR_DIM):
    vec = [0.0] * dim
    for t in tokenize(text):
        vec[hash_token(t, dim)] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def processar_pergunta(pergunta):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        return {
            "resposta": "[DEBUG] Variáveis SUPABASE_URL / SUPABASE_SERVICE_KEY não encontradas no servidor.",
            "confianca": 0.0,
            "abstencao": True,
            "evidencias": [],
        }

    try:
        supabase = create_client(supabase_url, supabase_key)
        query_embedding = vectorize(pergunta)

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
