#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · simulação de falhas na VM (roda na SUA máquina, via SSH)
#
#   infra/scripts/simular_falhas.sh container   # mata o backend (SIGKILL) e mede a volta
#   infra/scripts/simular_falhas.sh disco       # enche o disco até o alerta DiscoQuaseCheio disparar e limpa
#   infra/scripts/simular_falhas.sh reboot      # reinicia a VM e mede até o HTTPS responder de novo
#
# Cada execução grava falha_<tipo>_<AAAAMMDD_HHMMSS>.txt na pasta de evidências.
# =============================================================================
set -uo pipefail
TIPO="${1:?container|disco|reboot}"
HOST="${HOST:-asa-vm}"
URL="${URL:-https://54-207-148-68.sslip.io}"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
DIR="${EVIDENCIAS_DIR:-$RAIZ/../../documentos/Entrega 2/Sistemas Operacionais e Computação em Nuvem/evidencias}/falhas"
mkdir -p "$DIR"
OUT="$DIR/falha_${TIPO}_$(date '+%Y%m%d_%H%M%S').txt"
exec > >(tee "$OUT") 2>&1
t() { date '+%H:%M:%S.%3N'; }
seg() { date +%s.%N; }
dur() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.1f", b-a}'; }
saude() { curl -s -o /dev/null -m 3 -w '%{http_code}' "$URL/api/health"; }
D='sudo -u asa docker compose --project-directory /opt/asa'
alertas() { ssh "$HOST" "curl -s http://127.0.0.1:9090/api/v1/alerts" | python3 -c 'import json,sys;a=json.load(sys.stdin)["data"]["alerts"];print(", ".join(f"{x["labels"]["alertname"]}={x["state"]}" for x in a) or "nenhum")'; }

echo "# Simulação de falha: $TIPO · $(date '+%F %T %Z') · $URL"
case "$TIPO" in
container)
  echo "[$(t)] estado inicial: $(ssh "$HOST" "$D ps backend --format '{{.Name}} {{.Status}}'") · /api/health=$(saude)"
  echo "[$(t)] docker kill -s KILL no backend (simula crash do processo)"
  ssh "$HOST" "sudo docker kill -s KILL asa-turbo-backend-1" >/dev/null
  t0=$(seg); primeira_falha=""
  while :; do
    c=$(saude); agora=$(seg)
    [ "$c" != 200 ] && [ -z "$primeira_falha" ] && primeira_falha=$c && echo "[$(t)] /api/health=$c (fora do ar)"
    if [ "$c" = 200 ] && [ -n "$primeira_falha" ]; then break; fi
    if [ "$c" = 200 ] && [ "$(dur "$t0" "$agora" | cut -d. -f1)" -gt 5 ]; then break; fi
    sleep 0.5
  done
  echo "[$(t)] /api/health=200 de novo após $(dur "$t0" "$(seg)") s"
  ssh "$HOST" "sudo docker inspect asa-turbo-backend-1 --format 'RestartCount={{.RestartCount}} Status={{.State.Status}} Health={{.State.Health.Status}} StartedAt={{.State.StartedAt}}'; sudo docker events --since 3m --until 0s --filter container=asa-turbo-backend-1 --format '{{.Time}} {{.Action}}' | tail -n 6"
  ;;
disco)
  ssh "$HOST" "df -h /" ; echo "[$(t)] alertas: $(alertas)"
  # alvo: 88% de uso (alerta em 85%), arquivo em /var/tmp (fora dos volumes)
  ssh "$HOST" 'set -e; read tam usado <<<"$(df -B1 --output=size,used / | tail -1)"; alvo=$(( tam * 88 / 100 - usado )); [ $alvo -gt 0 ] && sudo fallocate -l $alvo /var/tmp/asa_enche_disco.bin; df -h /'
  echo "[$(t)] disco cheio; esperando o alerta (for: 1m + avaliação 15 s)"
  t0=$(seg)
  for _ in $(seq 1 40); do
    a=$(alertas); case "$a" in *DiscoQuaseCheio=firing*) break ;; esac; sleep 10
  done
  echo "[$(t)] alertas: $a (após $(dur "$t0" "$(seg)") s)"
  echo "[$(t)] o app continua respondendo? /api/health=$(saude)"
  ssh "$HOST" 'sudo rm -f /var/tmp/asa_enche_disco.bin; df -h /'
  sleep 45; echo "[$(t)] depois da limpeza: $(alertas)"
  ;;
reboot)
  echo "[$(t)] uptime antes: $(ssh "$HOST" uptime -s) · /api/health=$(saude)"
  echo "[$(t)] sudo reboot"
  ssh "$HOST" "sudo systemd-run --on-active=2 /usr/bin/systemctl reboot" >/dev/null 2>&1 || true
  t0=$(seg); sleep 5
  until [ "$(saude)" != 200 ]; do sleep 1; done; echo "[$(t)] fora do ar"
  until ssh -o ConnectTimeout=3 -o BatchMode=yes "$HOST" true 2>/dev/null; do sleep 2; done
  echo "[$(t)] SSH de volta após $(dur "$t0" "$(seg)") s"
  until [ "$(saude)" = 200 ]; do sleep 1; done
  echo "[$(t)] /api/health=200 após $(dur "$t0" "$(seg)") s (sem intervenção manual)"
  ssh "$HOST" "uptime -s; systemctl is-enabled asa; systemctl is-active asa; $D ps --format '{{.Service}}: {{.Status}}'; journalctl -u asa -b --no-pager | tail -n 6"
  ;;
*) echo "tipo desconhecido: $TIPO"; exit 2 ;;
esac
echo "# evidência: ${OUT##*/}"
