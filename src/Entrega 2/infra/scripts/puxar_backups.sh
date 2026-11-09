#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · cópia dos backups PARA FORA DA VM (roda na SUA máquina)
#
#   infra/scripts/puxar_backups.sh                  # asa-vm -> ~/asa-backups-vm
#   DESTINO=/mnt/hd/asa infra/scripts/puxar_backups.sh
#
# rsync por SSH (sudo rsync do lado da VM, porque backups/ é 700 do usuário asa).
# Confere o sha256 de cada conjunto copiado. Retenção local: 30 dias.
# Cron sugerido na sua máquina (04:00, depois do backup das 03:15 na VM):
#   0 4 * * * /caminho/src/Entrega\ 2/infra/scripts/puxar_backups.sh >> ~/asa-backups-vm/puxar.log 2>&1
# ATENÇÃO: os arquivos *_config.tar.gz contêm o .env de produção (segredos).
# =============================================================================
set -euo pipefail
HOST="${HOST:-asa-vm}"
DESTINO="${DESTINO:-$HOME/asa-backups-vm}"
install -d -m 700 "$DESTINO"
umask 077
inicio=$(date +%s)
rsync -a --rsync-path="sudo rsync" --include='asa_*' --include='backup.log' --exclude='*' \
  "$HOST:/opt/asa/backups/" "$DESTINO/"
ok=0; falhas=0
for s in "$DESTINO"/asa_*.sha256; do
  [ -e "$s" ] || continue
  if (cd "$DESTINO" && sha256sum -c --quiet "$(basename "$s")" 2>/dev/null); then ok=$((ok+1)); else falhas=$((falhas+1)); echo "FALHA: $(basename "$s")"; fi
done
find "$DESTINO" -maxdepth 1 -name 'asa_*' -type f -mtime +30 -delete
echo "[$(date '+%F %T')] $HOST -> $DESTINO em $(( $(date +%s) - inicio )) s · conjuntos íntegros: $ok · falhas: $falhas · total: $(du -sh "$DESTINO" | cut -f1)"
[ "$falhas" = 0 ]
