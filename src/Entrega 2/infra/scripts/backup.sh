#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · backup do banco (schema public: dados da aplicação)
#
#   infra/scripts/backup.sh            # detecta o modo
#   infra/scripts/backup.sh --local    # serviço db do compose (stack local)
#   infra/scripts/backup.sh --url      # DATABASE_URL do .env (Supabase gerenciado)
#
# Gera em BACKUP_DIR, com o mesmo carimbo <AAAAMMDD_HHMMSS>:
#   asa_<ts>.dump              pg_dump -Fc do schema public (dados da aplicação)
#   asa_<ts>_auth.sql.gz       só no modo local (Postgres na VM): dados de auth.users e
#                              auth.identities (no Supabase gerenciado, o próprio Supabase guarda)
#   asa_<ts>_config.tar.gz     compose, .env (segredos!), Caddyfile, monitoring, deploy e
#                              artefatos do modelo (ml/artifacts)
#   asa_<ts>.contagens         linhas por tabela no momento do backup (conferência do restore)
#   asa_<ts>.sha256            sha256 de todos os arquivos acima
# Confere o dump (pg_restore --list) e apaga o que tiver mais de BACKUP_RETENCAO_DIAS dias.
# BACKUP_DIR é 700 e os arquivos 600: o tar contém o .env.
# Na VM roda todo dia às 03:15 pelo asa-backup.timer (infra/deploy/).
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

ts="$(date '+%Y%m%d_%H%M%S')"
arquivo="$dir/asa_${ts}.dump"
inicio=$(date +%s)
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

log "dump ok: $(du -h "$arquivo" | cut -f1), $itens itens no sumário"
arquivos=("asa_${ts}.dump")

# Usuários do Auth (só quando o Postgres é nosso, na VM)
if [ "$modo" = local ]; then
  pg_exec local pg_dump --data-only --column-inserts --on-conflict-do-nothing \
      -t auth.users -t auth.identities | gzip -6 > "$dir/asa_${ts}_auth.sql.gz"
  arquivos+=("asa_${ts}_auth.sql.gz")
  log "auth ok: $(du -h "$dir/asa_${ts}_auth.sql.gz" | cut -f1)"
fi

# Configuração e artefatos do modelo
( cd "$RAIZ" && tar -czf "$dir/asa_${ts}_config.tar.gz" --ignore-failed-read \
    docker-compose.yml .env infra/caddy infra/monitoring infra/deploy infra/sql ml/artifacts 2>/dev/null ) \
  || { log "FALHA ao empacotar a configuração"; exit 1; }
arquivos+=("asa_${ts}_config.tar.gz")
log "config ok: $(du -h "$dir/asa_${ts}_config.tar.gz" | cut -f1)"

contagens "$modo" > "$dir/asa_${ts}.contagens" || true
arquivos+=("asa_${ts}.contagens")

(cd "$dir" && sha256sum "${arquivos[@]}" > "asa_${ts}.sha256")
log "ok em $(( $(date +%s) - inicio )) s: ${arquivos[*]} (+ asa_${ts}.sha256)"

apagados="$(find "$dir" -maxdepth 1 -name 'asa_*' -type f -mtime +"$retencao" -print -delete | wc -l)"
log "retenção de $retencao dias: $apagados arquivo(s) antigo(s) removido(s)"
printf '%s\n' "$arquivo"
