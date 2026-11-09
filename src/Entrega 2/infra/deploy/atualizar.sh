#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · publica uma branch/tag do GitHub em /opt/asa (rodar NA VM, como root)
#
#   sudo bash /opt/asa/infra/deploy/atualizar.sh                 # branch entrega2/nuvem
#   sudo REF=v1.0.0 bash /opt/asa/infra/deploy/atualizar.sh      # outra branch/tag
#   sudo SEM_RELOAD=1 bash .../atualizar.sh                      # só copia o código
#
# Clona/atualiza o repositório em /var/lib/asa-src e copia "src/Entrega 2" para /opt/asa
# SEM tocar em .env, backups/ e data/. Depois: build das imagens e systemctl reload asa.
# =============================================================================
set -euo pipefail
REPO="${REPO:-https://github.com/2026-2-NCC5/Projeto3.git}"
REF="${REF:-entrega2/nuvem}"
SRC=/var/lib/asa-src
APP="${DIR_APP:-/opt/asa}"
[ "$(id -u)" = 0 ] || { echo "rode com sudo" >&2; exit 1; }
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch -q --depth 1 origin "$REF"
  git -C "$SRC" checkout -q -f FETCH_HEAD
else
  git clone -q --depth 1 -b "$REF" "$REPO" "$SRC"
fi
echo "[atualizar] $REF @ $(git -C "$SRC" rev-parse --short HEAD)"
install -d -m 0750 -o asa -g asa "$APP"
rsync -a --delete --exclude .env --exclude backups/ --exclude data/ --exclude node_modules/ \
  "$SRC/src/Entrega 2/" "$APP/"
chown -R asa:asa "$APP"
[ -f "$APP/.env" ] && chmod 600 "$APP/.env"
git -C "$SRC" rev-parse HEAD > "$APP/.versao"
if [ "${SEM_RELOAD:-0}" != 1 ] && [ -f "$APP/.env" ]; then
  sudo -u asa docker compose --project-directory "$APP" build -q
  systemctl reload-or-restart asa
  echo "[atualizar] serviço recarregado"
fi
