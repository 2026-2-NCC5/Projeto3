#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · restauração do banco a partir de um backup de backup.sh
#
#   infra/scripts/restore.sh backups/asa_20261103_031500.dump          # pergunta antes
#   infra/scripts/restore.sh backups/asa_20261103_031500.dump --sim    # sem perguntar
#   (--local | --url escolhem o destino, como no backup.sh)
#
# Passos: confere o sha256 -> mostra as contagens atuais -> substitui os
# objetos do schema public pelos do backup (pg_restore --clean --if-exists)
# -> mostra as contagens depois -> pede ao PostgREST para reler o schema.
# ATENÇÃO: sobrescreve os dados atuais da aplicação.
# =============================================================================
set -euo pipefail
# shellcheck source=infra/scripts/_comum.sh
source "$(dirname "${BASH_SOURCE[0]}")/_comum.sh"

arquivo=""
sim=0
for arg in "$@"; do
  case "$arg" in
    --sim) sim=1 ;;
    --local) MODO=local ;;
    --url) MODO=url ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) log "opção desconhecida: $arg"; exit 2 ;;
    *) arquivo="$arg" ;;
  esac
done
if [ -z "$arquivo" ] || [ ! -f "$arquivo" ]; then
  log "uso: restore.sh <arquivo.dump> [--sim] [--local|--url]"
  exit 2
fi

if [ -f "$arquivo.sha256" ]; then
  (cd "$(dirname "$arquivo")" && sha256sum -c "$(basename "$arquivo").sha256" >/dev/null) \
    || { log "FALHA: sha256 não confere, arquivo corrompido"; exit 1; }
  log "sha256 conferido"
else
  log "aviso: sem $arquivo.sha256, integridade não conferida"
fi

modo="$(detectar_modo)"
log "destino: modo $modo"
log "contagens ANTES:"
contagens "$modo" | sed 's/^/  /' >&2 || log "(banco vazio ou inacessível)"

if [ "$sim" = 0 ]; then
  printf 'Isto SUBSTITUI os dados atuais pelos do backup %s. Digite "restaurar" para continuar: ' "$(basename "$arquivo")" >&2
  read -r resposta
  [ "$resposta" = "restaurar" ] || { log "cancelado"; exit 1; }
fi

log "restaurando..."
saida="$(mktemp)"
lista="$(mktemp)"
trap 'rm -f "$saida" "$lista"' EXIT
# Sumário do backup sem as tabelas exclusivas da stack local (dumps antigos podem tê-las)
filtro="$(printf '%s\n' $TABELAS_FORA_DO_BACKUP | paste -sd'|' -)"
# e sem o schema public nem os DEFAULT ACL (pertencem à plataforma Supabase, não à aplicação)
docker run --rm -i "$IMAGEM_PG_CLIENTE" pg_restore --list < "$arquivo" \
  | grep -Ev " (${filtro})( |$)" | grep -Ev "SCHEMA - public |- SCHEMA public |DEFAULT ACL " > "$lista"
chmod 644 "$lista"
if [ "$modo" = "local" ]; then
  (cd "$RAIZ" && docker compose cp "$lista" db:/tmp/asa_restore.list >/dev/null 2>&1)
  caminho_lista=/tmp/asa_restore.list
else
  PG_DOCKER_ARGS="-v $lista:/tmp/asa_restore.list:ro"
  caminho_lista=/tmp/asa_restore.list
fi
# --clean --if-exists: apaga e recria cada objeto do backup. --no-owner: o dono vira o usuário conectado.
# --single-transaction: ou restaura tudo, ou nada muda.
if ! pg_exec "$modo" pg_restore --clean --if-exists --no-owner --single-transaction --exit-on-error \
      --use-list="$caminho_lista" < "$arquivo" 2> "$saida"; then
  log "FALHA no pg_restore (nada foi alterado, transação desfeita):"
  sed 's/^/  /' "$saida" >&2
  exit 1
fi

log "contagens DEPOIS:"
contagens "$modo" | sed 's/^/  /' >&2

# PostgREST relê o schema (views e funções recriadas)
pg_exec "$modo" psql -X -q -c "notify pgrst, 'reload schema'" >/dev/null 2>&1 || true
log "restauração concluída"
