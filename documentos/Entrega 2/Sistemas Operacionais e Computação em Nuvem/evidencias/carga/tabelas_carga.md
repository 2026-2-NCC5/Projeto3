### Teste principal (rampa 10 → 50 → 100 VUs, ~9,5 min)

| Métrica | antes | depois | Variação |
|---|---:|---:|---:|
| Requisições (total) | 13.095 | 13.110 | +0% |
| Throughput médio (req/s) | 22,84 | 22,88 | +0% |
| Taxa de falha HTTP | 0,16% | 0,34% | |
| Taxa de 5xx | 0,00% | 0,00% | |
| Respostas 429 (rate limit do chat) | 21 | 42 | |
| /health p50 (ms) | 8,6 | 8,6 | +1% |
| /health p95 (ms) | 13,7 | 14,0 | +2% |
| /health p99 (ms) | 20,4 | 23,3 | +14% |
| login p50 (ms) | 14,6 | 14,8 | +1% |
| login p95 (ms) | 23,1 | 22,9 | -1% |
| login p99 (ms) | 82,6 | 24,5 | -70% |
| /chat p50 (ms) | 17,6 | 17,2 | -2% |
| /chat p95 (ms) | 32,3 | 31,6 | -2% |
| /chat p99 (ms) | 51,3 | 60,5 | +18% |
| /casos p50 (ms) | 43,3 | 25,2 | -42% |
| /casos p95 (ms) | 73,5 | 42,5 | -42% |
| /casos p99 (ms) | 102,7 | 79,3 | -23% |
| /casos/{id} p50 (ms) | 19,6 | 19,4 | -1% |
| /casos/{id} p95 (ms) | 36,8 | 34,7 | -6% |
| /casos/{id} p99 (ms) | 54,4 | 57,4 | +6% |
| Abstenção do chat | 10,28% | 9,74% | |

### Estresse (taxa de chegada crescente até saturar)

| Rodada | Ajuste | Req/s (k6) | Pico de req/s (Prometheus) | Falhas | /casos atendidos | /casos p50 (ms) | /casos p95 (ms) | Último degrau com p95 < 500 ms | CPU backend (cores, máx) | CPU db (máx) | CPU host (máx) |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| estresse_antes | nenhum (1 worker) | 54,28 | 60,0 | 0,01% | 4.404 | 8.989,8 | 11.646,0 | 44,8 req/s | 0,73 | 0,71 | 99,7% |
| estresse_rls | + policies RLS com InitPlan (005) | 53,39 | 59,3 | 0,04% | 4.306 | 9.216,0 | 11.952,6 | 35,5 req/s | 0,71 | 0,71 | 99,7% |
| estresse_cache | + cache de 10 s da contagem da fila | 77,49 | 91,6 | 0,00% | 6.799 | 5.115,6 | 6.269,7 | 83,9 req/s | 0,80 | 0,55 | 98,5% |
| estresse_workers2 | + UVICORN_WORKERS=2 (revertido) | 70,25 | 82,4 | 0,13% | 6.082 | 5.488,1 | 7.543,5 | 66,6 req/s | 0,88 | 0,52 | 100,0% |
