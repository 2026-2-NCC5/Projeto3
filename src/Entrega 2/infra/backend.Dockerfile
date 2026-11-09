# syntax=docker/dockerfile:1.7
# =============================================================================
# ASA Turbo · imagem do backend (FastAPI)
# Contexto de build = raiz do projeto (src/Entrega 2):
#   docker build -f infra/backend.Dockerfile -t asa-turbo-backend:0.9.0 .
# O arquivo infra/backend.Dockerfile.dockerignore libera SÓ o necessário
# (data/, .env e afins nunca entram no contexto).
# =============================================================================

# ---------- estágio 1: dependências num venv isolado
FROM python:3.12-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY backend/requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt

# ---------- estágio 2: runtime enxuto, usuário não-root
FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.title="asa-turbo-backend" \
      org.opencontainers.image.version="0.9.0" \
      org.opencontainers.image.description="API do ASA Turbo (chat RAG + monitoramento de risco)"

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=producao \
    PORT=8000

RUN groupadd --system --gid 10001 asa \
 && useradd --system --uid 10001 --gid asa --home-dir /srv --shell /usr/sbin/nologin asa \
 && mkdir -p /var/log/asa && chown asa:asa /var/log/asa

COPY --from=deps /opt/venv /opt/venv
# Layout igual ao do repositório: /srv = raiz do projeto (caminhos relativos do .env funcionam)
WORKDIR /srv/backend
COPY --chown=asa:asa backend/app ./app
COPY --chown=asa:asa ml/artifacts /srv/ml/artifacts
COPY --chown=asa:asa ml/risco /srv/ml/risco
COPY --chown=asa:asa seeds/estudantes_sinteticos.csv /srv/seeds/estudantes_sinteticos.csv

USER asa
EXPOSE 8000

# /health responde 503 sem banco -> container "unhealthy"
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/health\", timeout=4).status == 200 else 1)"]

# UVICORN_WORKERS (padrão 1). Com mais de 1, as métricas vão para PROMETHEUS_MULTIPROC_DIR
# (tmpfs /tmp) e o limite de mensagens do chat, que é em memória, passa a valer por worker.
CMD ["sh", "-c", "W=${UVICORN_WORKERS:-1}; if [ \"$W\" -gt 1 ]; then export PROMETHEUS_MULTIPROC_DIR=/tmp/prom; rm -rf $PROMETHEUS_MULTIPROC_DIR; mkdir -p $PROMETHEUS_MULTIPROC_DIR; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers $W --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
