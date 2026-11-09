#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · ENSAIO do runbook de desastre ("VM perdida"), com tempo medido.
# Roda na SUA máquina. DESTRUTIVO: apaga Docker (pacotes + /var/lib/docker, ou seja,
# volumes do banco, certificado, Grafana e Prometheus), /opt/asa, o clone e as unidades.
#   infra/scripts/ensaio_desastre.sh --destruir-de-verdade
#
# Sem credenciais da AWS não dá para criar outra instância: a "VM nova" é a mesma VM
# com a camada do serviço apagada (o SO, o IP elástico e o usuário ubuntu continuam).
# Depois segue runbook_desastre.md: provision -> .env e backups da cópia externa ->
# db + GoTrue -> restaurar_vm_nova.sh -> systemctl start asa -> smoke.sh.
# =============================================================================
set -euo pipefail
[ "${1:-}" = "--destruir-de-verdade" ] || { sed -n '2,13p' "$0"; exit 2; }
HOST="${HOST:-asa-vm}"
URL="${URL:-https://54-207-148-68.sslip.io}"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
COPIA="${DESTINO:-$HOME/asa-backups-vm}"
DIR="$RAIZ/../../documentos/Entrega 2/Sistemas Operacionais e Computação em Nuvem/evidencias/backup"
mkdir -p "$DIR"; OUT="$DIR/ensaio_desastre_$(date '+%Y%m%d_%H%M%S').txt"
exec > >(tee "$OUT") 2>&1
seg() { date +%s.%N; }
dur() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.1f", b-a}'; }
etapa() { echo; echo "[$(date '+%H:%M:%S')] ===== $*"; }
D='sudo -u asa docker compose --project-directory /opt/asa'
declare -a T_NOMES=() T_VALS=()
marca() { T_NOMES+=("$1"); T_VALS+=("$(dur "$2" "$(seg)")"); echo "    -> $1: ${T_VALS[-1]} s"; }

echo "# Ensaio de desastre (VM perdida) · $(date '+%F %T %Z') · $URL"

etapa "0. preparação: cópia externa dos backups"
if ssh "$HOST" 'systemctl is-active --quiet asa'; then
  echo "    serviço no ar: backup fresco + cópia (RPO deste ensaio ~ 0)"
  ssh "$HOST" 'sudo systemctl start asa-backup && sudo tail -n 2 /opt/asa/backups/backup.log'
  "$RAIZ/infra/scripts/puxar_backups.sh"
else
  echo "    serviço FORA do ar: usando a última cópia externa já existente (como num desastre real)"
fi
B="$(ls -t "$COPIA"/asa_*.dump | head -1)"; B="${B%.dump}"; N="$(basename "$B")"
echo "    backup escolhido: $N"
cat "$B.contagens" | tr '\n' ' '; echo

etapa "1. DESASTRE: apagando Docker, volumes, /opt/asa, clone, unidades e configs"
ssh "$HOST" 'sudo systemctl disable --now asa.service asa-backup.timer >/dev/null 2>&1 || true
  sudo docker ps -aq | xargs -r sudo docker rm -f >/dev/null 2>&1 || true
  sudo systemctl stop docker docker.socket containerd >/dev/null 2>&1 || true
  sudo DEBIAN_FRONTEND=noninteractive apt-get purge -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
  sudo rm -rf /var/lib/docker /var/lib/containerd /etc/docker /opt/asa /var/lib/asa-src /var/log/asa \
    /etc/systemd/system/asa*.service /etc/systemd/system/asa*.timer /etc/logrotate.d/asa /etc/apt/sources.list.d/docker.list
  sudo systemctl daemon-reload
  echo "    docker: $(command -v docker || echo ausente) · /opt/asa: $(ls -d /opt/asa 2>/dev/null || echo ausente)"'
echo "    site: HTTP $(curl -s -o /dev/null -m 5 -w '%{http_code}' "$URL/" || true) (000 = fora do ar)"

T0=$(seg)
etapa "2. provisionar (atualizar.sh + provision.sh, direto do GitHub)"
t=$(seg)
ssh "$HOST" 'curl -fsSL https://raw.githubusercontent.com/2026-2-NCC5/Projeto3/entrega2/nuvem/src/Entrega%202/infra/deploy/atualizar.sh | sudo SEM_RELOAD=1 bash && sudo bash /opt/asa/infra/deploy/provision.sh > /tmp/provision_dr.log 2>&1 && tail -n 1 /tmp/provision_dr.log && docker --version'
marca "provisionamento (Docker incluso)" "$t"

etapa "3. devolver .env e backup a partir da cópia externa"
t=$(seg)
rsync -a --rsync-path="sudo rsync" "$B".* "${B}"_* "$HOST:/opt/asa/backups/"
ssh "$HOST" "sudo tar -C /opt/asa -xzf /opt/asa/backups/${N}_config.tar.gz .env && sudo chown -R asa:asa /opt/asa && sudo chmod 600 /opt/asa/.env && sudo ls -l /opt/asa/.env"
marca "cópia do .env e do backup" "$t"

etapa "4. build das imagens + db e GoTrue (banco novo, vazio)"
t=$(seg)
ssh "$HOST" "$D build -q 2>&1 | tail -n 2; $D up -d --wait db gotrue 2>&1 | tail -n 1"
marca "build + banco no ar" "$t"

etapa "5. restaurar auth + public"
t=$(seg)
ssh "$HOST" "cd /tmp && sudo -u asa /opt/asa/infra/scripts/restaurar_vm_nova.sh /opt/asa/backups/${N}.dump" | sed 's/^/    /'
marca "restauração" "$t"

etapa "6. subir o resto (systemctl start asa) e esperar o HTTPS"
t=$(seg)
ssh "$HOST" 'sudo systemctl start asa && systemctl is-active asa'
until [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$URL/api/health")" = 200 ]; do sleep 2; done
marca "serviço + certificado novo" "$t"
echo | openssl s_client -servername "${URL#https://}" -connect "${URL#https://}:443" 2>/dev/null | openssl x509 -noout -issuer -dates | sed 's/^/    /'

etapa "7. validar com smoke.sh"
ANON_KEY="$(ssh "$HOST" "sudo grep '^SUPABASE_ANON_KEY=' /opt/asa/.env | cut -d= -f2-")"
SMOKE_SENHA="$(ssh "$HOST" "sudo grep '^DEMO_PASSWORD=' /opt/asa/.env | cut -d= -f2-")"
export ANON_KEY SMOKE_SENHA
"$RAIZ/scripts/smoke.sh" "$URL" | sed 's/^/    /'
TOTAL="$(dur "$T0" "$(seg)")"

echo
echo "===== RESUMO"
for i in "${!T_NOMES[@]}"; do printf '  %-36s %8s s\n' "${T_NOMES[$i]}" "${T_VALS[$i]}"; done
printf '  %-36s %8s s (%s min)\n' "RTO medido (VM 'nova' -> smoke OK)" "$TOTAL" "$(awk -v t="$TOTAL" 'BEGIN{printf "%.1f", t/60}')"
echo "  RPO deste ensaio: backup feito imediatamente antes (em operação normal: até 24 h)"
