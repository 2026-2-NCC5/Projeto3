#!/usr/bin/env python3
"""
Gera o .env de DESENVOLVIMENTO para `docker compose up` (stack local completa).
===============================================================================
Cria `src/Entrega 2/.env` com segredos ALEATÓRIOS gerados nesta máquina:
JWT secret, chaves anon/service_role (JWTs HS256 assinados com esse secret)
e senha do Postgres local. Nada disso é versionado, nada é chave real.

Não sobrescreve um .env existente (use --forcar para isso).
Só stdlib.

    python3 infra/local/preparar_env.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / ".env"


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def jwt_hs256(payload: dict, segredo: str) -> str:
    cab = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    corpo = _b64(json.dumps(payload, separators=(",", ":")).encode())
    assinatura = hmac.new(segredo.encode(), f"{cab}.{corpo}".encode(), hashlib.sha256).digest()
    return f"{cab}.{corpo}.{_b64(assinatura)}"


def main() -> None:
    if DESTINO.exists() and "--forcar" not in sys.argv:
        print(f"{DESTINO} já existe; nada a fazer (use --forcar para gerar de novo).")
        return

    segredo = secrets.token_urlsafe(48)
    agora = int(time.time())
    validade = agora + 5 * 365 * 24 * 3600
    anon = jwt_hs256({"role": "anon", "iss": "supabase-local", "iat": agora, "exp": validade}, segredo)
    senha_pg = secrets.token_urlsafe(24)
    servico = jwt_hs256({"role": "service_role", "iss": "supabase-local", "iat": agora, "exp": validade}, segredo)

    conteudo = f"""# =============================================================================
# .env LOCAL gerado por infra/local/preparar_env.py em {time.strftime('%Y-%m-%d %H:%M')}
# Segredos aleatórios desta máquina, só para a stack local. NUNCA commitar.
# Para produção, veja infra/deploy/README.md.
# =============================================================================

# Sobe também Postgres + PostgREST + GoTrue locais (stack "Supabase local")
COMPOSE_PROFILES=local

# --- Web (Caddy)
WEB_PORT=8080
SITE_ADDRESS=:80
PUBLIC_URL=http://localhost:8080

# --- Supabase local
POSTGRES_PASSWORD={senha_pg}
SUPABASE_JWT_SECRET={segredo}
SUPABASE_ANON_KEY={anon}
SUPABASE_SERVICE_KEY={servico}
# backend -> gateway interno (PostgREST em /rest/v1, GoTrue em /auth/v1)
SUPABASE_URL=http://supabase-gw:8000
# navegador -> mesma origem do app (o Caddy repassa /auth/v1 para o GoTrue)
PUBLIC_SUPABASE_URL=http://localhost:8080
DATABASE_URL=postgresql://postgres:{senha_pg}@db:5432/postgres

# --- Embeddings: sem chave, o backend usa o fallback lexical local (TF-IDF)
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
HF_API_TOKEN=

# --- Aplicação
APP_ENV=local
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:8080
CHAT_RATE_LIMIT_POR_MINUTO=20
RISK_MODEL_PATH=ml/artifacts/risco_v2.joblib

# --- Usuários de demonstração (seeds/README.md)
DEMO_PASSWORD=AsaTurbo#Demo2026

# --- Monitoramento (profile "monitoring")
GRAFANA_ADMIN_PASSWORD={secrets.token_urlsafe(12)}
"""
    DESTINO.write_text(conteudo, encoding="utf-8")
    DESTINO.chmod(0o600)
    print(f"Criado {DESTINO} (permissão 600).")


if __name__ == "__main__":
    main()
