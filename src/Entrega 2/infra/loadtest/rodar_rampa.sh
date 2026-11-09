#!/usr/bin/env bash
# =============================================================================
# Roda rampa.js da SUA máquina contra a VM e coleta docker stats da VM a cada 15 s.
#   infra/loadtest/rodar_rampa.sh antes
#   infra/loadtest/rodar_rampa.sh depois
# Saída: $SAIDA/k6_<rotulo>.json, k6_<rotulo>.txt, stats_<rotulo>.txt
# A senha dos usuários de carga e a chave anon vêm da VM por SSH, só em variáveis de ambiente.
# =============================================================================
set -euo pipefail
ROTULO="${1:?rotulo (antes|depois)}"
HOST="${HOST:-asa-vm}"
URL="${URL:-https://54-207-148-68.sslip.io}"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
SAIDA="${SAIDA:-$RAIZ/../../documentos/Entrega 2/Sistemas Operacionais e Computação em Nuvem/evidencias/carga}"
mkdir -p "$SAIDA"; chmod 777 "$SAIDA" 2>/dev/null || true
DEMO_PASSWORD="$(ssh "$HOST" "sudo grep '^DEMO_PASSWORD=' /opt/asa/.env | cut -d= -f2-")"
ANON_KEY="$(ssh "$HOST" "sudo grep '^SUPABASE_ANON_KEY=' /opt/asa/.env | cut -d= -f2-")"
export DEMO_PASSWORD ANON_KEY

# docker stats da VM durante o teste
ssh "$HOST" "while true; do date '+%T'; sudo docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'; sleep 15; done" \
  > "$SAIDA/stats_${ROTULO}.txt" 2>&1 &
STATS=$!
trap 'kill $STATS 2>/dev/null || true' EXIT

echo "início: $(date '+%F %T')  config da VM: $(ssh "$HOST" "sudo grep -E '^(UVICORN_WORKERS|PGRST_DB_POOL|BACKEND_CPUS|EMBEDDING_CACHE_MAX)=' /opt/asa/.env | tr '\n' ' '")" \
  | tee "$SAIDA/k6_${ROTULO}.txt"
docker run --rm -v "$RAIZ/infra/loadtest:/t:ro" -v "$SAIDA:/out" \
  -e BASE_URL="$URL" -e DEMO_PASSWORD -e ANON_KEY -e ROTULO="$ROTULO" -e FATOR_TEMPO="${FATOR_TEMPO:-1}" \
  grafana/k6:0.54.0 run --quiet /t/rampa.js 2>&1 | tee -a "$SAIDA/k6_${ROTULO}.txt"
echo "fim: $(date '+%F %T')" | tee -a "$SAIDA/k6_${ROTULO}.txt"
