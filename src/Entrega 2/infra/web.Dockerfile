# syntax=docker/dockerfile:1.7
# =============================================================================
# ASA Turbo · imagem do web: build do Vite + Caddy servindo o estático e fazendo
# proxy da API (/api/* -> backend) e do login (/auth/v1/* -> Supabase local).
# Contexto = raiz do projeto (src/Entrega 2):
#   docker build -f infra/web.Dockerfile -t asa-turbo-web:0.9.0 .
# Variáveis VITE_* são PÚBLICAS (entram no JS). Nunca passe segredo aqui.
# =============================================================================
FROM node:20-alpine AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ARG VITE_API_BASE_URL="/api"
ENV VITE_API_MOCK=false \
    VITE_SUPABASE_URL=${VITE_SUPABASE_URL} \
    VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM caddy:2.8.4-alpine AS runtime
LABEL org.opencontainers.image.title="asa-turbo-web" org.opencontainers.image.version="0.9.0"
# Usuário sem privilégios; o binário do Caddy já tem cap_net_bind_service (portas 80/443).
RUN addgroup -S -g 10002 web && adduser -S -u 10002 -G web -h /srv web \
 && mkdir -p /data /config /var/log/caddy \
 && chown -R web:web /data /config /var/log/caddy
COPY --from=build --chown=web:web /app/dist /srv
COPY --chown=web:web infra/caddy/Caddyfile /etc/caddy/Caddyfile
USER web
ENV XDG_DATA_HOME=/data XDG_CONFIG_HOME=/config
EXPOSE 80 443
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:2019/config/ >/dev/null || exit 1
