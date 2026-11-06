# syntax=docker/dockerfile:1.7
# =============================================================================
# ASA Turbo · CONTAINER ÚNICO (API FastAPI + web PWA) para Render / Fly / Cloud Run.
# O FastAPI serve o build do web (app/web.py): /api/* -> API, /health, resto -> SPA.
#   docker build -t asa-turbo:0.9.0 .
#   docker run --rm -p 8080:8080 -e PORT=8080 asa-turbo:0.9.0     # DEMO_MODE=true por padrão
# Para usar o Supabase real: DEMO_MODE=false + SUPABASE_* (ver DEPLOY.md) e rebuild com
# --build-arg VITE_SUPABASE_URL=... --build-arg VITE_SUPABASE_ANON_KEY=... (valores públicos).
# O .dockerignore da raiz é lista de PERMISSÃO: data/ e .env nunca entram no contexto.
# =============================================================================

# ---------- 1. build do web (Vite), sem mock, API em /api
FROM node:20-alpine AS web
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ENV VITE_API_MOCK=false VITE_API_BASE_URL=/api \
    VITE_SUPABASE_URL=${VITE_SUPABASE_URL} VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
RUN npm run build

# ---------- 2. dependências Python num venv
FROM python:3.12-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY backend/requirements.txt /build/requirements.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r /build/requirements.txt

# ---------- 3. runtime enxuto, usuário não-root
FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.title="asa-turbo" org.opencontainers.image.version="0.9.0" \
      org.opencontainers.image.description="ASA Turbo: chat RAG do estudante + monitoramento de risco (API + web)"
ENV PATH="/opt/venv/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_ENV=producao PORT=8080 DEMO_MODE=true WEB_DIST_DIR=web/dist LOG_LEVEL=INFO
RUN groupadd --system --gid 10001 asa \
 && useradd --system --uid 10001 --gid asa --home-dir /srv --shell /usr/sbin/nologin asa
COPY --from=deps /opt/venv /opt/venv
WORKDIR /srv/backend
COPY --chown=asa:asa backend/app ./app
COPY --chown=asa:asa ml/artifacts /srv/ml/artifacts
COPY --chown=asa:asa ml/risco /srv/ml/risco
COPY --chown=asa:asa seeds/estudantes_sinteticos.csv seeds/demo_snapshot.json.gz /srv/seeds/
COPY --from=web --chown=asa:asa /app/dist /srv/web/dist
USER asa
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8080')}/health\", timeout=4).status == 200 else 1)"]
# 1 processo: o estado da demo e o limite do chat ficam em memória
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
