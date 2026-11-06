# backend/ · API FastAPI do ASA Turbo

Implementa **todo** o contrato `../docs/api-contract.yaml` (v0.9.0): chat RAG com fontes e abstenção,
fila de risco com fatores, tendência e recomendação, validação humana, dashboard, base de conhecimento,
`/health` e `/metrics`. Python 3.11, FastAPI, Supabase (PostgREST com a chave `service_role`).

## Rodar local

```bash
cd "src/Entrega 2/backend"
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# variáveis: o backend lê ../.env (raiz do projeto) e backend/.env. Veja "Configuração".
uvicorn app.main:app --reload --port 8000
# http://localhost:8000/docs  (desligado quando APP_ENV=producao)
```

Banco: aplique `../infra/sql/003_backend_rpcs.sql` depois do 001/002 (ordem completa em `../seeds/README.md`).
Sem `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`, a API sobe mesmo assim: `/metrics` funciona, `/health`
responde 503 e as rotas que usam o banco respondem `indisponivel`.

## Docker

```bash
cd "src/Entrega 2"
docker build -f infra/backend.Dockerfile -t asa-turbo-backend:0.9.0 .
docker run --env-file .env -p 8000:8000 asa-turbo-backend:0.9.0
```

Imagem multi-stage (`python:3.11-slim`), usuário não-root (uid 10001), `HEALTHCHECK` em `/health`.
`infra/backend.Dockerfile.dockerignore` é uma lista de **permissão**: só entram `backend/app`,
`backend/requirements.txt`, `ml/artifacts/` e `seeds/estudantes_sinteticos.csv` (nunca `data/` nem `.env`).
Um processo por container: o limite de mensagens do chat é em memória, então escale com réplicas
e um limite no proxy, se precisar.

## Testar

```bash
ruff check . && ruff format --check .
pytest                      # 162 testes, sem rede e sem banco (repositório em memória)
```

| Arquivo | O que cobre |
|---|---|
| `tests/test_rbac.py` | 401 sem token/expirado/assinatura inválida; matriz papel × rota (menor privilégio); estudante nunca acessa `/casos`, `/risco` ou `/admin`; papel vem de `perfis`, não do token |
| `tests/test_rag.py` | reescrita de continuação ("e o prazo?"), limiar e abstenção, resposta só com conteúdo recuperado |
| `tests/test_embeddings_fallback.py` | Cloudflare com 5xx/429/timeout/dimensão errada → Hugging Face → TF-IDF local → abstenção; nada de vetor TF-IDF no pgvector |
| `tests/test_chat.py` | contrato de `/chat`, encaminhamento, contexto salvo, persistência, auditoria, feedback, 404 em conversa alheia, 429 |
| `tests/test_casos.py` | contrato de `/casos` (fila, filtros, contagem, detalhe, histórico); fator sensível nunca exibido |
| `tests/test_validacao.py` | confirmar/ajustar/rejeitar, justificativa ≥ 20 caracteres, 409 com score desatualizado, auditoria, nada automático |
| `tests/test_risco.py` | `RiskModel.predict`, faixas, recomendação por regra (sem termos punitivos), carga do artefato |
| `tests/test_admin.py` | dashboard, cadastro/versão/desativação de documento, 503 sem embeddings |
| `tests/test_operacao.py` | `/health`, `/metrics`, `X-Request-ID`, erro 500 no formato do contrato, CORS, log JSON |

Os corpos de resposta são validados **contra os schemas do próprio `api-contract.yaml`** (`tests/contrato.py`).

### Teste de integração (opcional, Postgres + PostgREST reais)

`tests/test_integracao_postgrest.py` exercita o `SupabaseRepositorio` e o fluxo completo pela API
(chat → fila → detalhe → validação → histórico → dashboard). Ele **escreve** no banco: use um banco descartável.

```bash
# Postgres 16 + pgvector com 001, base_conhecimento_oficial, 002, usuários demo, seed_demo e 003 aplicados,
# e um PostgREST com PGRST_JWT_SECRET apontando para ele.
ASA_TESTE_POSTGREST_URL=http://localhost:3000 ASA_TESTE_JWT_SECRET=<segredo> pytest tests/test_integracao_postgrest.py
```

## Configuração

Todas por variável de ambiente (`app/core/config.py`). As do `../.env.example` valem; estas são novas:

| Variável | Padrão | Uso |
|---|---|---|
| `HF_API_TOKEN` | vazio | Provedor reserva de embeddings (Hugging Face Inference). Sem token, fica de fora. |
| `HF_EMBEDDING_MODEL` | `BAAI/bge-m3` | Mesmo modelo/espaço (1024d) da Cloudflare. **Não** trocar por modelo de outra dimensão. |
| `EMBEDDING_TIMEOUT_S` | `8` | Timeout por provedor. |
| `EMBEDDING_COOLDOWN_S` | `30` | Tempo que um provedor que falhou fica fora da rotação. |
| `RAG_FALLBACK_LEXICAL` | `true` | Liga o fallback TF-IDF local quando nenhum provedor responde. |
| `RAG_LIMIAR_LEXICAL` | `0.35` | Limiar de abstenção do fallback (cosseno TF-IDF). |
| `RAG_CACHE_LEXICAL_S` | `600` | Validade do índice lexical em memória (invalidado ao salvar documento). |
| `RISK_SEEDS_PATH` | `seeds/estudantes_sinteticos.csv` | Base do modelo placeholder. |
| `JWT_AUDIENCE` | `authenticated` | Audiência do JWT do Supabase. |
| `PERFIL_CACHE_TTL_S` | `30` | Cache do papel lido em `perfis`. |

JWT: com `SUPABASE_JWT_SECRET` valida HS256 (chave legacy). Sem ela, usa as chaves públicas do projeto
(`/auth/v1/.well-known/jwks.json`, ES256/RS256).

## Como funciona

```
app/
  core/      config, logs JSON (request_id, usuário, rota, status, latência), erros do contrato,
             middleware ASGI (X-Request-ID + métricas + rede de segurança 500), auth/RBAC, métricas
  rag/       MÓDULO ISOLADO, sem I/O próprio — a sessão de ML reutiliza para avaliar o RAG
  risk/      RiskModel, atributos (dimensão, frases, sensíveis), recomendação por regra
  db/        Protocol Repositorio + SupabaseRepositorio (PostgREST + RPCs da migration 003)
  services/  casos de uso (chat, casos, risco, documentos, auditoria)
  api/       rotas finas, uma por grupo do contrato
```

### RAG (`app/rag/`)

1. **Reescrita** (`reescrita.py`): pergunta curta ou com conector/anáfora ("e o prazo?", "isso vale para EAD?")
   recebe o assunto da última pergunta do estudante. Usa o histórico salvo da conversa (ou o enviado pelo cliente).
2. **Embedding** (`embeddings.py`): Cloudflare `@cf/baai/bge-m3` → Hugging Face `BAAI/bge-m3` (mesmo espaço 1024d).
3. **Busca** `buscar_chunks_similares` (top-k). **Limiar** `CONFIDENCE_THRESHOLD` (0,55).
4. **Fallback** se nenhum provedor responde: TF-IDF **local** sobre o texto dos trechos ativos (`lexical.py`),
   com limiar próprio. Ver "Decisões" abaixo.
5. **Resposta extrativa** (`resposta.py`): só o texto dos trechos oficiais; enumerações viram passos numerados.
   Abaixo do limiar ou com falha: abstenção + encaminhamento para o ASA (nunca 5xx).

Uso pela sessão de ML (sem banco, sem FastAPI):

```python
from app.rag import ConfigRAG, IndiceLexical, recuperar, compor_resposta

r = recuperar(
    pergunta,
    historico,
    vetorizar=minha_funcao,
    buscar_vetorial=minha_busca,
    indice_lexical=lambda: indice,
    config=ConfigRAG(limiar=0.55),
)
r.abstencao, r.motivo_abstencao, r.confianca, r.metodo, [t.titulo for t in r.trechos]
```

### Risco (`app/risk/`)

- `carregar_modelo`: usa `RISK_MODEL_PATH` (artefato da sessão de ML) ou, na falta dele, treina um
  **placeholder** (RL `class_weight=balanced`, sem atributos sensíveis) com os seeds fictícios — versão
  `rl-placeholder-seeds-0.1`. O log avisa em WARNING. **Não é o modelo real.**
- Formato esperado do artefato (`joblib`, dict): `modelo` (estimador com `predict_proba(DataFrame)`),
  `features` (nomes da API), `referencia` (valor típico de cada feature), `versao`, `algoritmo`,
  `treinado_em`, `metricas`. Detalhes em `app/risk/modelo.py`.
- Fatores: contribuição de cada atributo = `logit(p(x)) − logit(p(x com o atributo no valor de referência))`.
  Funciona com qualquer algoritmo; na RL é exatamente `coef × (x − ref)`. Sensíveis nunca viram fator;
  valor monetário nunca aparece.
- Score por dimensão (financeira/acadêmica/relacionamento) em 0–1, como o contrato pede (o front exibe 0–100).
- Recomendação por regra sobre a categoria **vigente** (após validação), sempre "Sugestão: ... A decisão é do atendente."

### Observabilidade

- Log JSON por requisição: `nivel`, `request_id`, `usuario_id`, `papel`, `rota`, `status`, `latencia_ms`.
  Nunca token, chave nem texto do estudante (esse vai só para `auditoria_logs`).
- `/metrics`: `http_requests_total{rota,metodo,status}`, `http_request_duration_seconds`, `http_erros_total`,
  `chat_respostas_total{abstencao}`, `chat_abstencoes_total{motivo}`, `chat_feedback_total`,
  `embedding_falhas_total{provedor}`, `rag_fallback_total`, `rag_recuperacoes_total{metodo}`,
  `risco_inferencias_total{versao_modelo}`, `validacoes_total{decisao}`.
- `/health`: banco (com latência), embeddings (sem gastar cota: estado do último uso) e modelo de risco.
  Sem banco responde 503.

## Decisões e pontos de atenção

- **Fallback TF-IDF:** o `CLAUDE.md` e a decisão 0001 dizem "sem fallback TF-IDF" porque um vetor TF-IDF
  não é comparável aos embeddings bge-m3 no pgvector. O fallback aqui **não** usa o pgvector nem o
  `idf_table.json` da Entrega 1: é lexical, local, com IDF da própria base e limiar calibrado
  (0,35: na base oficial, perguntas fora do escopo ficam em ≤ 0,27). Pode ser desligado com
  `RAG_FALLBACK_LEXICAL=false`, voltando ao comportamento da decisão 0001.
- **Migration 003:** RPCs transacionais para cada escrita com várias tabelas; `documentos_chunks.ativo`
  (versão nova desativa os trechos antigos em vez de apagar, porque as respostas antigas os citam);
  `vw_fila_risco_busca` (busca sem acento); RPCs só executáveis pelo `service_role`.
- **Rejeitar** um alerta deixa a categoria vigente em `verde` e arquiva o caso (salvo `status` informado).
- **Estudante sem caso** (em geral verde) no `GET /casos/{id}`: o contrato exige `caso.status`/`prioridade`;
  devolvemos `novo`/`baixa` com `caso.id = null` (nada é criado).
- **Dashboard:** campos opcionais sem valor são omitidos (o contrato não os declara anuláveis);
  `chat.latencia_media_ms` é um campo extra, aditivo.
