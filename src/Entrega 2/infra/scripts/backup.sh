#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · backup do banco (schema public: dados da aplicação)
#
#   infra/scripts/backup.sh            # detecta o modo
#   infra/scripts/backup.sh --local    # serviço db do compose (stack local)
#   infra/scripts/backup.sh --url      # DATABASE_URL do .env (Supabase gerenciado)
#
# Gera BACKUP_DIR/asa_<AAAAMMDD_HHMMSS>.dump (pg_dump formato custom) + .sha256,
# confere o arquivo (pg_restore --list) e apaga backups com mais de
# BACKUP_RETENCAO_DIAS dias. Usuários do Auth (schema auth) ficam a cargo do
# backup do próprio Supabase; aqui vai tudo o que a aplicação grava.
# Cron diário (03:15), como usuário asa na VM:
#   15 3 * * * cd /opt/asa-turbo && infra/scripts/backup.sh >> backups/backup.log 2>&1
# =============================================================================
set -euo pipefail
# shellcheck source=infra/scripts/_comum.sh
source "$(dirname "${BASH_SOURCE[0]}")/_comum.sh"

for arg in "$@"; do
  case "$arg" in
    --local) MODO=local ;;
    --url) MODO=url ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) log "opção desconhecida: $arg"; exit 2 ;;
  esac
done

modo="$(detectar_modo)"
dir="$(ler_env BACKUP_DIR "$RAIZ/backups")"
case "$dir" in /*) ;; *) dir="$RAIZ/${dir#./}" ;; esac
retencao="$(ler_env BACKUP_RETENCAO_DIAS 7)"
mkdir -p "$dir"
chmod 700 "$dir"
umask 077

arquivo="$dir/asa_$(date '+%Y%m%d_%H%M%S').dump"
log "backup (modo $modo) -> $arquivo"

excluir=()
for t in $TABELAS_FORA_DO_BACKUP; do excluir+=(--exclude-table="public.$t"); done
if ! pg_exec "$modo" pg_dump -Fc -Z 6 -n public --no-owner "${excluir[@]}" > "$arquivo.parcial"; then
  rm -f "$arquivo.parcial"
  log "FALHA no pg_dump"
  exit 1
fi
mv "$arquivo.parcial" "$arquivo"

# Arquivo íntegro? (lista o sumário do dump)
itens="$( (cd "$RAIZ" && docker run --rm -i "$IMAGEM_PG_CLIENTE" pg_restore --list) < "$arquivo" | grep -cv '^;' || true)"
if [ "${itens:-0}" -lt 10 ]; then
  log "FALHA: dump com só ${itens:-0} itens"
  exit 1
fi

(cd "$dir" && sha256sum "$(basename "$arquivo")" > "$(basename "$arquivo").sha256")
tamanho="$(du -h "$arquivo" | cut -f1)"
log "ok: $tamanho, $itens itens no sumário, sha256 em $(basename "$arquivo").sha256"

apagados="$(find "$dir" -maxdepth 1 -name 'asa_*.dump*' -type f -mtime +"$retencao" -print -delete | wc -l)"
log "retenção de $retencao dias: $apagados arquivo(s) antigo(s) removido(s)"
printf '%s\n' "$arquivo"
