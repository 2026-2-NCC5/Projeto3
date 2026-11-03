#!/usr/bin/env bash
# Funções comuns aos scripts de operação (backup, restore). Use com `source`.
# Lê o .env SEM executá-lo (nunca dá `source` no .env: valores podem ter $, # etc.).

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARQ_ENV="${ARQ_ENV:-$RAIZ/.env}"
# Imagem do cliente Postgres para o modo --url. Use a MESMA versão major do servidor
# (Supabase novo = 17; projeto antigo em 15: IMAGEM_PG_CLIENTE=postgres:15-alpine).
# No modo --local, os binários do próprio container db são usados.
IMAGEM_PG_CLIENTE="${IMAGEM_PG_CLIENTE:-postgres:17.2-alpine}"
# Tabelas que existem só na stack local (controle do init-db) e ficam fora do backup
# shellcheck disable=SC2034  # usada por backup.sh e restore.sh
TABELAS_FORA_DO_BACKUP="_asa_migracoes"

ler_env() { # ler_env CHAVE [padrao]
  local chave="$1" padrao="${2:-}" valor=""
  if [ -f "$ARQ_ENV" ]; then
    valor="$(grep -E "^${chave}=" "$ARQ_ENV" | tail -n1 | cut -d= -f2- || true)"
    valor="${valor%\"}"; valor="${valor#\"}"; valor="${valor%\'}"; valor="${valor#\'}"
  fi
  if [ -n "${!chave:-}" ]; then valor="${!chave}"; fi  # variável de ambiente tem prioridade
  printf '%s' "${valor:-$padrao}"
}

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; }

# Decide o modo: "local" (serviço db do compose rodando) ou "url" (DATABASE_URL, ex. Supabase)
detectar_modo() {
  if [ -n "${MODO:-}" ]; then printf '%s' "$MODO"; return; fi
  if (cd "$RAIZ" && docker compose ps --status running -q db 2>/dev/null | grep -q .); then
    printf 'local'
  else
    printf 'url'
  fi
}

# Executa um binário do cliente Postgres (pg_dump, pg_restore, psql) no modo escolhido.
# stdin/stdout passam direto (dump e restore por pipe, sem arquivo dentro do container).
pg_exec() { # pg_exec MODO BINARIO [args...]
  local modo="$1"; shift
  local bin="$1"; shift
  if [ "$modo" = "local" ]; then
    local senha
    senha="$(ler_env POSTGRES_PASSWORD)"
    (cd "$RAIZ" && docker compose exec -T -e PGPASSWORD="$senha" db \
      "$bin" -h localhost -U postgres -d postgres "$@")
  else
    local url
    url="$(ler_env DATABASE_URL)"
    if [ -z "$url" ]; then log "DATABASE_URL vazio no .env"; return 1; fi
    # shellcheck disable=SC2086  # PG_DOCKER_ARGS pode ter vários argumentos (ex.: -v lista)
    docker run --rm -i --network host ${PG_DOCKER_ARGS:-} "$IMAGEM_PG_CLIENTE" "$bin" --dbname="$url" "$@"
  fi
}

# Tabelas conferidas depois de backup/restore
TABELAS_CONFERENCIA="perfis estudantes estudante_features scores_risco casos_risco validacoes_caso eventos_caso contatos_asa conversas mensagens respostas_agente feedback_respostas encaminhamentos documentos_oficiais documentos_chunks documentos_versoes auditoria_logs"

contagens() { # contagens MODO -> "tabela|linhas" por linha
  local sql="" t
  for t in $TABELAS_CONFERENCIA; do
    sql="${sql}select '${t}' as tabela, count(*) from public.${t} union all "
  done
  sql="${sql% union all }"
  pg_exec "$1" psql -X -A -t -F '|' -c "$sql"
}
