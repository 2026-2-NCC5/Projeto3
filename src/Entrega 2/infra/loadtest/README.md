# infra/loadtest/ · teste de carga (k6)

## Entrega 2 de Nuvem (VM AWS): rampa 10 → 50 → 100 e estresse

| Arquivo | Para quê |
|---|---|
| `criar_usuarios_rampa.sh` | 100 estudantes + 10 atendentes fictícios (`carga.e001@...`, `carga.a01@...`), idempotente |
| `rampa.js` | login + `/health` + `/chat` + `/casos`, rampa de 10 → 50 → 100 VUs (~9,5 min) |
| `estresse.js` | modelo aberto: `/casos` de 10 → 120 req/s + `/chat` a 15 req/s, para achar a saturação |
| `rodar_rampa.sh` | roda o k6 da sua máquina contra a VM e coleta `docker stats` da VM (`ROTEIRO=estresse.js` para o estresse) |
| `exportar_series.sh` | exporta do Prometheus da VM as séries de req/s, p50/p95/p99 e CPU em CSV |
| `tabela_comparativa.py` | gera as tabelas antes × depois a partir dos JSON/CSV (números nunca digitados) |
| `prints.mjs` | prints do Grafana/Prometheus/app com Playwright |

Os resultados e a análise do gargalo estão em `documentos/Entrega 2/Sistemas Operacionais e Computação em Nuvem/`.

## Entrega anterior (stack local, 50 VUs)

`carga.js` simula **50 usuários simultâneos** por 2m45s:
- **40 estudantes** no `/chat`, com 10 perguntas que se repetem e uma pausa de 4 a 8 s entre elas, ritmo de quem lê a resposta e abaixo do limite de 20 mensagens por minuto;
- **10 atendentes** na fila (`/casos`, com e sem filtro de categoria), abrindo um caso a cada 2 a 5 s.

Cada usuário virtual faz login no GoTrue uma vez e reaproveita o token.

## Rodar (stack local)

```bash
sh infra/loadtest/criar_usuarios_carga.sh      # 50 estudantes + 5 atendentes fictícios (só na stack local)
set -a; . ./.env; set +a
docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "$PWD/infra/loadtest:/t:ro" -v "$PWD/docs/evidencias/carga:/out" \
  -e DEMO_PASSWORD -e ANON_KEY="$SUPABASE_ANON_KEY" \
  grafana/k6:0.54.0 run --summary-export /out/k6_resumo_final.json /t/carga.js
```

**Atenção:** o teste grava conversas e auditoria no banco. Antes de uma apresentação, recrie o banco local com `docker compose --profile local down -v` e depois `docker compose up -d`.

## Resultado (03/11/2026, notebook de desenvolvimento, stack local completa)

Saída completa em `docs/evidencias/carga/`: `k6_saida_final.txt`, `k6_resumo_final.json` e `docker_stats_final.txt`.

| Métrica | Valor | Meta |
|---|---|---|
| Requisições | 1.831 (10,7/s) | |
| Falhas HTTP | 0,00% | < 2% |
| 5xx | 0 | < 1% |
| `/chat` p95 | 28,7 ms | < 2 s |
| `/casos` (fila) p95 | 44,5 ms | < 1,5 s |
| `/casos/{id}` (detalhe) p95 | 19,5 ms | |
| Taxa de abstenção | 42% | (ver gargalo 3) |

Numa primeira rodada, feita enquanto outras sessões gravavam no mesmo banco (`k6_saida_antes.txt`), saíram 2 erros isolados do PostgREST, entre 1.843 requisições. Eles não se repetiram com a stack limpa nem em 180 consultas seguidas da fila.

## Gargalos e ajustes

1. **Na produção, a latência do chat vem do provedor de embeddings, não da API.** Localmente não há chave da Cloudflare e o chat usa o fallback lexical em memória, que leva cerca de 1 ms. Com a Cloudflare, cada pergunta custa uma chamada externa de cerca de 200 a 1.000 ms, segundo a medição de 10/2026 em `web/api/perguntar.py`.
   - **Ajuste feito:** cache LRU de embeddings para perguntas repetidas (`EMBEDDING_CACHE_MAX=2000`, TTL de 1 h), com a métrica `embedding_cache_acertos_total`. Neste teste, as 10 perguntas se repetem: depois da primeira de cada, nenhuma iria à Cloudflare.
2. **Pool de conexões.** O PostgREST usa um pool de 20 conexões (`PGRST_DB_POOL`). O backend usa um único cliente HTTP com keep-alive (supabase-py/httpx), e em leituras repete uma vez se a conexão tiver caído. Com 50 usuários, os picos de CPU (amostras a cada 10 s em `docker_stats_final.txt`) foram 23% no backend, 15% no Postgres e 5% no PostgREST. Memória: 175 MiB no backend, incluindo o modelo XGBoost, e 143 MiB no Postgres. Não foi preciso aumentar o pool.
   - O backend roda em **1 processo**, porque o limite de mensagens do chat fica em memória. Para mais carga: réplicas atrás do Caddy, com o limite movido para o proxy ou para um Redis.
3. **A abstenção de 42% é qualidade do fallback, não carga.** Sem embeddings, a busca é por palavras.
   - **Ajuste feito:** agrupar as palavras por prefixo ("cancelo" e "cancelamento" contam como a mesma). Nas 14 perguntas do escopo, as respondidas passaram de 7 para 11, e as 8 fora do escopo continuam com abstenção.
   - A abstenção deste teste foi medida **antes** desse ajuste.
   - Ainda ficam sem resposta "Quais bolsas a FECAP oferece?" e "Onde fica o ASA?", perguntas genéricas demais para busca por palavras. Com a Cloudflare configurada, a busca semântica resolve a maior parte disso.
4. **A fila é a rota mais cara**, com p95 de 45 ms: são 4 consultas, a página e mais a contagem por categoria. Dá para juntar tudo numa RPC só se a fila crescer muito. Com 300 estudantes, não compensa.
