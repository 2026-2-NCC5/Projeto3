"""
API do Agente para o Estudante (ASA/FECAP) - Entrega 2
======================================================
Rota: /api/perguntar  (o Vercel transforma cada arquivo de /api numa rota)

Contrato (o frontend depende dele, não altere sem alinhar src/api/perguntar.js):
    POST { "pergunta": str }
      -> { "resposta": str, "confianca": float, "abstencao": bool,
           "evidencias": [ { titulo, fonte, similaridade, atualizado_em, trecho } ] }

O que mudou em relação à Entrega 1
----------------------------------
1. Embeddings: Hugging Face (BAAI/bge-small-en-v1.5, 384d) -> Cloudflare
   Workers AI (@cf/baai/bge-m3, 1024d). Motivo duplo: o token da Hugging Face
   ficou sem créditos (HTTP 402) e o modelo antigo era treinado em inglês,
   enquanto a base de conhecimento é toda em português.

2. Sem SDK do Supabase. A Entrega 1 importava `supabase`, que arrasta pydantic,
   httpx, gotrue e companhia. Isso deixava a função pesada e quebrava no import
   dentro do Vercel (FUNCTION_INVOCATION_FAILED, 500 até no OPTIONS). Aqui a
   busca é um POST direto no PostgREST com `requests` - mesma RPC, uma
   dependência só.

3. Sem fallback TF-IDF. Na Entrega 1, se a vetorização falhasse, o código caía
   num vetor TF-IDF de 384 dimensões. Isso não é mais possível: os embeddings
   guardados agora têm 1024 dimensões, então um vetor TF-IDF nem seria
   comparável - o banco devolveria erro de dimensão. Quando a vetorização
   falha, o agente se abstém e encaminha para atendimento humano, que é o
   comportamento correto segundo os princípios do projeto (abstenção é resposta
   válida; nunca responder sem base).

Variáveis de ambiente (Vercel > Settings > Environment Variables)
-----------------------------------------------------------------
    SUPABASE_URL              https://SEU-PROJETO.supabase.co
    SUPABASE_SERVICE_KEY      chave service_role
    CLOUDFLARE_ACCOUNT_ID     ID da conta na Cloudflare
    CLOUDFLARE_API_TOKEN      token com permissão "Workers AI: Read"
    CONFIDENCE_THRESHOLD      opcional; limiar de abstenção (padrão abaixo)
"""

import os
import json
from http.server import BaseHTTPRequestHandler

import requests

VECTOR_DIM = 1024
CF_MODEL = "@cf/baai/bge-m3"
CF_TIMEOUT = 15      # segundos
DB_TIMEOUT = 10      # segundos
LIMITE_EVIDENCIAS = 3

# Limiar de abstenção. Medido em 15/10/2026 com 10 perguntas dentro do escopo
# (ASA/FECAP) e 8 fora (receita de bolo, capital da França, etc.) contra a
# base real de 693 chunks:
#   dentro do escopo: similaridade do top1 entre 0.60 e 0.75 (média 0.68)
#   fora do escopo:   similaridade do top1 entre 0.29 e 0.47 (média 0.39)
# 0.55 cai no meio do gap (0.47-0.60), com mais margem do lado de evitar
# responder fora de escopo do que do lado de evitar abstenção indevida -
# coerente com o princípio do projeto de que abstenção é resposta válida.
# Dá para ajustar pelo ambiente, sem novo deploy, conforme perguntas reais
# dos estudantes forem aparecendo em auditoria_logs / feedback_respostas.
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.55"))

TEXTO_ABSTENCAO = (
    "Não encontrei essa informação com confiança suficiente nas fontes "
    "oficiais disponíveis. Vou te encaminhar para um atendente do ASA."
)
TEXTO_INDISPONIVEL = (
    "Não consegui consultar a base de conhecimento agora. Para não te passar "
    "uma informação sem fonte, vou te encaminhar para um atendente do ASA."
)


class FalhaDeVetorizacao(Exception):
    """A pergunta não pôde ser transformada em vetor."""


class FalhaDeBusca(Exception):
    """A base de conhecimento não pôde ser consultada."""


def _config():
    """Lê as variáveis de ambiente. Devolve a lista das que faltam em vez de
    estourar, para a API conseguir responder com um diagnóstico útil."""
    cfg = {
        "supabase_url": os.environ.get("SUPABASE_URL", "").rstrip("/"),
        "supabase_key": os.environ.get("SUPABASE_SERVICE_KEY", ""),
        "cf_account": os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
        "cf_token": os.environ.get("CLOUDFLARE_API_TOKEN", ""),
    }
    faltando = [
        nome for nome, chave in [
            ("SUPABASE_URL", "supabase_url"),
            ("SUPABASE_SERVICE_KEY", "supabase_key"),
            ("CLOUDFLARE_ACCOUNT_ID", "cf_account"),
            ("CLOUDFLARE_API_TOKEN", "cf_token"),
        ] if not cfg[chave]
    ]
    return cfg, faltando


def extrair_vetores(payload):
    """Isola o formato de resposta da Cloudflare, que varia entre modelos e
    versões da API: o vetor pode vir em result.data, em result.response, ou
    direto em result. Normaliza tudo para uma lista de vetores."""
    if not isinstance(payload, dict):
        raise FalhaDeVetorizacao(f"resposta não é objeto JSON: {type(payload).__name__}")

    if payload.get("success") is False:
        erros = payload.get("errors") or payload.get("messages") or "sem detalhe"
        raise FalhaDeVetorizacao(f"Cloudflare recusou: {erros}")

    resultado = payload.get("result", payload)

    bruto = None
    if isinstance(resultado, dict):
        for chave in ("data", "response", "embeddings", "vectors"):
            if isinstance(resultado.get(chave), list):
                bruto = resultado[chave]
                break
    elif isinstance(resultado, list):
        bruto = resultado

    if bruto is None:
        raise FalhaDeVetorizacao(f"formato inesperado: {str(payload)[:200]}")

    # Pode ser [[...]] (lista de vetores) ou [...] (um vetor só).
    vetores = bruto if bruto and isinstance(bruto[0], list) else [bruto]

    for v in vetores:
        if len(v) != VECTOR_DIM:
            raise FalhaDeVetorizacao(
                f"embedding com {len(v)} dimensões, esperado {VECTOR_DIM}")
    return [[float(x) for x in v] for v in vetores]


def normalizar(vetor):
    """Normaliza para norma L2 = 1, para o operador <=> do pgvector entregar
    cosseno de verdade. O bge-m3 já devolve normalizado, mas isso é barato e
    protege contra variação do provedor."""
    norma = sum(v * v for v in vetor) ** 0.5
    return [v / norma for v in vetor] if norma > 0 else vetor


def vetorizar(texto, cfg):
    """Gera o embedding da pergunta via Cloudflare Workers AI."""
    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{cfg['cf_account']}/ai/run/{CF_MODEL}")
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {cfg['cf_token']}"},
            json={"text": [texto]},
            timeout=CF_TIMEOUT,
        )
    except requests.RequestException as e:
        raise FalhaDeVetorizacao(f"{type(e).__name__}: {e}") from e

    if resp.status_code != 200:
        raise FalhaDeVetorizacao(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        payload = resp.json()
    except ValueError as e:
        raise FalhaDeVetorizacao(f"resposta não é JSON: {resp.text[:200]}") from e

    return normalizar(extrair_vetores(payload)[0])


def buscar_chunks(vetor, cfg):
    """Chama a RPC buscar_chunks_similares direto no PostgREST do Supabase."""
    url = f"{cfg['supabase_url']}/rest/v1/rpc/buscar_chunks_similares"
    try:
        resp = requests.post(
            url,
            headers={
                "apikey": cfg["supabase_key"],
                "Authorization": f"Bearer {cfg['supabase_key']}",
                "Content-Type": "application/json",
            },
            json={
                "query_embedding": vetor,
                "limite": LIMITE_EVIDENCIAS,
                "limiar_similaridade": 0.0,
            },
            timeout=DB_TIMEOUT,
        )
    except requests.RequestException as e:
        raise FalhaDeBusca(f"{type(e).__name__}: {e}") from e

    if resp.status_code != 200:
        raise FalhaDeBusca(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        dados = resp.json()
    except ValueError as e:
        raise FalhaDeBusca(f"resposta não é JSON: {resp.text[:200]}") from e

    return dados if isinstance(dados, list) else []


def montar_evidencias(chunks):
    return [
        {
            "titulo": c.get("titulo_documento") or "Documento sem título",
            "fonte": c.get("fonte_documento") or "",
            "similaridade": round(float(c.get("similaridade") or 0.0), 4),
            "atualizado_em": c.get("data_atualizacao"),
            "trecho": c.get("conteudo") or "",
        }
        for c in chunks
    ]


def abster(texto, confianca=0.0, evidencias=None):
    return {
        "resposta": texto,
        "confianca": round(float(confianca), 4),
        "abstencao": True,
        "evidencias": evidencias or [],
    }


def processar_pergunta(pergunta):
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return abster("Faça uma pergunta para eu poder ajudar.")

    cfg, faltando = _config()
    if faltando:
        print(f"[config] variáveis ausentes: {', '.join(faltando)}")
        return abster(TEXTO_INDISPONIVEL)

    try:
        vetor = vetorizar(pergunta, cfg)
    except FalhaDeVetorizacao as e:
        # Sem vetor não há busca possível: os embeddings da base têm 1024
        # dimensões e não existe aproximação local comparável a eles.
        print(f"[vetorizar] {e}")
        return abster(TEXTO_INDISPONIVEL)

    try:
        chunks = buscar_chunks(vetor, cfg)
    except FalhaDeBusca as e:
        print(f"[buscar_chunks] {e}")
        return abster(TEXTO_INDISPONIVEL)

    evidencias = montar_evidencias(chunks)
    if not chunks:
        return abster(TEXTO_ABSTENCAO)

    melhor = chunks[0]
    similaridade = float(melhor.get("similaridade") or 0.0)

    if similaridade < CONFIDENCE_THRESHOLD:
        return abster(TEXTO_ABSTENCAO, similaridade, evidencias)

    return {
        "resposta": melhor.get("conteudo") or "",
        "confianca": round(similaridade, 4),
        "abstencao": False,
        "evidencias": evidencias,
    }


class handler(BaseHTTPRequestHandler):
    def _responder(self, status, corpo):
        payload = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            corpo = self.rfile.read(tamanho) if tamanho else b""
            dados = json.loads(corpo) if corpo else {}
            resultado = processar_pergunta(dados.get("pergunta", ""))
            self._responder(200, resultado)
        except json.JSONDecodeError:
            self._responder(400, abster("Não entendi o formato da requisição."))
        except Exception as e:
            # Rede de segurança: o estudante recebe uma abstenção legível, e o
            # diagnóstico fica no log do Vercel em vez de vazar na resposta.
            print(f"[handler] {type(e).__name__}: {e}")
            self._responder(500, abster(TEXTO_INDISPONIVEL))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
