#!/usr/bin/env python3
"""
Gera os embeddings de todos os chunks da base de conhecimento - Entrega 2
=========================================================================
Modelo: @cf/baai/bge-m3 (Cloudflare Workers AI), 1024 dimensões, multilíngue.

Por que mudou em relação à Entrega 1
------------------------------------
A Entrega 1 usava BAAI/bge-small-en-v1.5 via Hugging Face. Dois problemas:
o token da Hugging Face ficou sem créditos (HTTP 402), e aquele modelo é
treinado em inglês enquanto a base é toda em português - o que inflava a
similaridade de perguntas fora de escopo e tornava o limiar de abstenção
impossível de calibrar.

Não existe mais fallback TF-IDF: misturar vetores de métodos diferentes no
mesmo índice produz similaridades que não significam nada. Se a vetorização
falhar, o chunk fica sem embedding e o script avisa, para você rodar de novo.

Pré-requisitos
--------------
1. Rodar db/migracao_entrega2_1024.sql no SQL Editor do Supabase (troca a
   coluna embedding para vector(1024) e recria a RPC e o índice).
2. Um arquivo .env nesta pasta (veja .env.example).

Uso
---
    python3 gerar_embeddings.py              # só os chunks que faltam
    python3 gerar_embeddings.py --tudo       # refaz todos, do zero
    python3 gerar_embeddings.py --verificar  # só mostra o estado, não escreve

O script é retomável: por padrão processa apenas chunks com embedding nulo,
então se a conexão cair ou a cota acabar, é só rodar de novo.

Dependências: requests. Nada além disso (sem SDK do Supabase, sem dotenv).
"""

import argparse
import json
import os
import sys
import time

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))

CF_MODEL = "@cf/baai/bge-m3"
VECTOR_DIM = 1024
TAMANHO_LOTE = 25       # textos por chamada à Cloudflare
MAX_TENTATIVAS = 5
TIMEOUT = 60


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def carregar_env():
    """Lê o .env desta pasta sem depender do pacote python-dotenv.
    Variáveis já definidas no ambiente têm prioridade."""
    caminho = os.path.join(AQUI, ".env")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave, valor = chave.strip(), valor.strip().strip('"').strip("'")
                os.environ.setdefault(chave, valor)

    faltando = [v for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY",
                            "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
                if not os.environ.get(v)]
    if faltando:
        sys.exit(
            "Faltam variáveis de ambiente: " + ", ".join(faltando) +
            f"\nCrie o arquivo {caminho} a partir do .env.example."
        )

    return {
        "url": os.environ["SUPABASE_URL"].rstrip("/"),
        "key": os.environ["SUPABASE_SERVICE_KEY"],
        "cf_account": os.environ["CLOUDFLARE_ACCOUNT_ID"],
        "cf_token": os.environ["CLOUDFLARE_API_TOKEN"],
    }


# ---------------------------------------------------------------------------
# Supabase (PostgREST direto)
# ---------------------------------------------------------------------------

def cabecalhos(cfg):
    return {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }


def contar(cfg, filtro=""):
    resp = requests.head(
        f"{cfg['url']}/rest/v1/documentos_chunks?select=id{filtro}",
        headers={**cabecalhos(cfg), "Prefer": "count=exact", "Range": "0-0"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return int(resp.headers.get("content-range", "0-0/0").split("/")[-1])


def buscar_chunks(cfg, apenas_faltantes=True):
    """Baixa os chunks a vetorizar, paginando (o PostgREST corta em 1000)."""
    filtro = "&embedding=is.null" if apenas_faltantes else ""
    todos, passo, offset = [], 1000, 0
    while True:
        resp = requests.get(
            f"{cfg['url']}/rest/v1/documentos_chunks"
            f"?select=id,conteudo{filtro}&order=id&limit={passo}&offset={offset}",
            headers=cabecalhos(cfg), timeout=TIMEOUT,
        )
        resp.raise_for_status()
        pagina = resp.json()
        todos.extend(pagina)
        if len(pagina) < passo:
            return todos
        offset += passo


def salvar_embedding(cfg, chunk_id, vetor):
    resp = requests.patch(
        f"{cfg['url']}/rest/v1/documentos_chunks?id=eq.{chunk_id}",
        headers={**cabecalhos(cfg), "Prefer": "return=minimal"},
        json={"embedding": vetor},
        timeout=TIMEOUT,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"PATCH {resp.status_code}: {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Cloudflare Workers AI
# ---------------------------------------------------------------------------

def extrair_vetores(payload):
    """A Cloudflare já devolveu o vetor em result.data, result.response e
    direto em result dependendo do modelo e da versão. Aceita os três."""
    if payload.get("success") is False:
        raise RuntimeError(f"Cloudflare recusou: "
                           f"{payload.get('errors') or payload.get('messages')}")

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
        raise RuntimeError(f"Formato inesperado: {str(payload)[:300]}")

    vetores = bruto if bruto and isinstance(bruto[0], list) else [bruto]
    for v in vetores:
        if len(v) != VECTOR_DIM:
            raise RuntimeError(f"Embedding com {len(v)} dimensões, "
                               f"esperado {VECTOR_DIM}")
    return [[float(x) for x in v] for v in vetores]


def normalizar(vetor):
    """Norma L2 = 1, para o operador <=> do pgvector dar cosseno de verdade."""
    norma = sum(v * v for v in vetor) ** 0.5
    return [v / norma for v in vetor] if norma > 0 else vetor


def vetorizar_lote(textos, cfg):
    """Vetoriza uma lista de textos, com retry e backoff exponencial em
    429 (cota/rate limit) e erros 5xx."""
    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{cfg['cf_account']}/ai/run/{CF_MODEL}")
    cabecalho = {"Authorization": f"Bearer {cfg['cf_token']}"}

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resp = requests.post(url, headers=cabecalho,
                                 json={"text": textos}, timeout=TIMEOUT)
            if resp.status_code == 200:
                vetores = extrair_vetores(resp.json())
                if len(vetores) != len(textos):
                    raise RuntimeError(
                        f"Pedi {len(textos)} embeddings, recebi {len(vetores)}")
                return [normalizar(v) for v in vetores]

            if resp.status_code in (429, 500, 502, 503, 504):
                espera = min(2 ** tentativa, 30)
                print(f"    HTTP {resp.status_code}; nova tentativa em {espera}s "
                      f"({tentativa}/{MAX_TENTATIVAS})")
                time.sleep(espera)
                continue

            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        except requests.RequestException as e:
            if tentativa == MAX_TENTATIVAS:
                raise
            espera = min(2 ** tentativa, 30)
            print(f"    {type(e).__name__}; nova tentativa em {espera}s "
                  f"({tentativa}/{MAX_TENTATIVAS})")
            time.sleep(espera)

    raise RuntimeError(f"Falhou após {MAX_TENTATIVAS} tentativas")


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def relatar(cfg):
    total = contar(cfg)
    vazios = contar(cfg, "&embedding=is.null")
    print(f"  chunks na base:      {total}")
    print(f"  já vetorizados:      {total - vazios}")
    print(f"  faltando vetorizar:  {vazios}")
    return total, vazios


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tudo", action="store_true",
                    help="refaz todos os embeddings, não só os que faltam")
    ap.add_argument("--verificar", action="store_true",
                    help="só mostra o estado da base, sem escrever nada")
    ap.add_argument("--lote", type=int, default=TAMANHO_LOTE,
                    help=f"textos por chamada (padrão {TAMANHO_LOTE})")
    args = ap.parse_args()

    cfg = carregar_env()

    print("Estado da base de conhecimento:")
    relatar(cfg)
    if args.verificar:
        return

    chunks = buscar_chunks(cfg, apenas_faltantes=not args.tudo)
    if not chunks:
        print("\nNada a fazer: todos os chunks já têm embedding.")
        print("Use --tudo para refazer do zero.")
        return

    print(f"\nVetorizando {len(chunks)} chunks com {CF_MODEL} "
          f"(lotes de {args.lote})...\n")

    ok, falhas = 0, []
    inicio = time.time()

    for i in range(0, len(chunks), args.lote):
        lote = chunks[i:i + args.lote]
        n_lote = i // args.lote + 1
        total_lotes = (len(chunks) + args.lote - 1) // args.lote
        print(f"  lote {n_lote}/{total_lotes} ({len(lote)} chunks)...", end=" ", flush=True)

        try:
            vetores = vetorizar_lote([c["conteudo"] for c in lote], cfg)
        except Exception as e:
            print(f"FALHOU: {e}")
            falhas.extend(c["id"] for c in lote)
            continue

        gravados = 0
        for chunk, vetor in zip(lote, vetores):
            try:
                salvar_embedding(cfg, chunk["id"], vetor)
                gravados += 1
            except Exception as e:
                print(f"\n    erro ao gravar {chunk['id']}: {e}")
                falhas.append(chunk["id"])

        ok += gravados
        print(f"ok ({ok}/{len(chunks)})")

    duracao = time.time() - inicio
    print(f"\nConcluído em {duracao:.0f}s. {ok} embeddings gravados.")

    if falhas:
        print(f"\n{len(falhas)} chunks falharam. Rode o script de novo "
              f"(ele retoma só o que falta).")

    print("\nEstado final:")
    relatar(cfg)


if __name__ == "__main__":
    main()
