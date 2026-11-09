#!/usr/bin/env bash
# Exporta do Prometheus da VM (por SSH) as séries de um intervalo, a cada 15 s, em CSV:
# tempo, req/s da API, p50/p95/p99 da API e de /casos, CPU do backend/db/postgrest (cores), CPU do host (%).
#   infra/loadtest/exportar_series.sh <inicio "AAAA-MM-DD HH:MM:SS"> <fim> > series.csv
set -euo pipefail
ini=$(date -d "$1" +%s); fim=$(date -d "$2" +%s)
ssh "${HOST:-asa-vm}" "python3 - $ini $fim" <<'PY'
import json, sys, urllib.parse, urllib.request
ini, fim = sys.argv[1], sys.argv[2]
F = 'rota!="/health",rota!="/metrics"'
def cpu(s): return f'sum(rate(container_cpu_usage_seconds_total{{id=~"/system.slice/docker-.+[.]scope"}}[1m]) * on (id) group_left(servico) max by (id, servico) (label_replace(up{{job="docker-nomes",servico="{s}"}}, "id", "/system.slice/docker-$1.scope", "container_id", "(.+)") * 0 + 1))'
Q = {
  'rps_api': f'sum(rate(http_requests_total{{{F}}}[30s]))',
  'p50_api_ms': f'1000*histogram_quantile(0.5, sum by (le) (rate(http_request_duration_seconds_bucket{{{F}}}[30s])))',
  'p95_api_ms': f'1000*histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{{F}}}[30s])))',
  'p99_api_ms': f'1000*histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{{{F}}}[30s])))',
  'p95_casos_ms': '1000*histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{rota="/casos"}[30s])))',
  'cpu_backend': cpu('backend'), 'cpu_db': cpu('db'), 'cpu_postgrest': cpu('postgrest'),
  'cpu_host_pct': '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[30s])))',
}
cols = {}
for k, q in Q.items():
    url = 'http://127.0.0.1:9090/api/v1/query_range?' + urllib.parse.urlencode({'query': q, 'start': ini, 'end': fim, 'step': '15'})
    r = json.load(urllib.request.urlopen(url))['data']['result']
    cols[k] = {int(float(t)): float(v) for t, v in (r[0]['values'] if r else [])}
ts = sorted(set().union(*[c.keys() for c in cols.values()]))
import time
print('hora,' + ','.join(Q))
for t in ts:
    print(time.strftime('%H:%M:%S', time.localtime(t)) + ',' + ','.join('' if t not in cols[k] else f'{cols[k][t]:.3f}' for k in Q))
PY
