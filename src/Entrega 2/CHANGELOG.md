# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [0.9.1] · 2026-11-04

Fechamento para a apresentação: integração na `main`, modo de demonstração e container único para a nuvem.

### Adicionado
- `DEMO_MODE=true`: seeds em memória (`seeds/demo_snapshot.json.gz`), com as mesmas telas e a mesma API, sem Supabase nem rede.
  - Login de demo emitido pelo backend (`/api/demo/entrar`, `/api/demo/estado`, `/api/demo/reiniciar`).
  - Botões "Acessar como demonstração" na tela de login.
- Curadoria da demo:
  - 3 vermelhos no topo da fila (queda de notas, inadimplência, frequência), com a trajetória de inadimplência pontuada pelo modelo real (`seeds/curar_snapshot_demo.py`);
  - uso do chat dos últimos 30 dias simulado no painel;
  - 6 perguntas sugeridas validadas.
- Container único (`Dockerfile` da raiz):
  - o FastAPI serve o build do web (`app/web.py`), com os mesmos cabeçalhos de segurança do Caddy;
  - usuário não-root, `$PORT` e healthcheck.
- `render.yaml` (na raiz do repositório), `fly.toml` e `DEPLOY.md`.
- `scripts/smoke.sh <URL>` e `scripts/reset_demo.sh [URL]`.
- Warm-up no início (índice lexical e embeddings), configurável por `AQUECER_AO_INICIAR`.

### Alterado
- O repositório em memória passou de `tests/fakes.py` para `app/db/memoria.py`. Os testes herdam dele.
- No modo demo, o `/health` reporta `busca_lexical` no lugar de `embeddings`.

## [0.9.0] · 2026-11-03

Primeira versão de ponta a ponta: login por papel, chat com fontes e abstenção, fila de risco com validação humana, painel da administração, deploy containerizado e observabilidade.

### Adicionado
- **Estudante:**
  - chat ASA Turbo com contexto das últimas mensagens;
  - fontes e data de atualização em cada resposta;
  - abstenção com encaminhamento ao ASA;
  - feedback útil/não útil;
  - histórico de conversas.
- **Atendente:**
  - fila de risco filtrável (categoria, prioridade, situação, busca);
  - detalhe com score geral e por dimensão, fatores (direção e peso), tendência de 6 meses, recomendação, versão do modelo e data;
  - validação humana (confirmar, ajustar, rejeitar) com justificativa obrigatória;
  - linha do tempo do caso.
- **Administração:**
  - painel agregado (uso do chat, distribuição Verde/Amarelo/Vermelho, abstenção, feedback, validações, encaminhamentos);
  - base de conhecimento (cadastrar, nova versão, desativar).
- **Equipe técnica:** página do modelo de risco.
- **API FastAPI** (`backend/`) implementando todo o `docs/api-contract.yaml`:
  - RBAC por papel e auditoria de toda escrita;
  - logs JSON, `/health` e `/metrics`;
  - rate limit no `/chat`;
  - embeddings com fallback Cloudflare → Hugging Face → lexical local;
  - cache de embeddings para perguntas repetidas.
- **Modelo de risco `risco-2.0.0`** (`ml/`):
  - XGBoost monotônico calibrado, sem sexo, estado civil e contatos com o ASA;
  - AUC de 0,91 no teste;
  - explicação por TreeSHAP.
- **Avaliação do RAG** (`ml/avaliar_rag.py`) e notebook de Álgebra Linear.
- **Migrations** 002 (risco, versões de documento, RLS completo), 003 (RPCs transacionais do backend) e 004 (textos exibidos).
- **`docker compose`:**
  - backend e web (Caddy) com usuário não-root, healthchecks e logs rotacionados;
  - stack Supabase local (Postgres, PostgREST, GoTrue) para rodar sem chaves;
  - profile `monitoring` com Prometheus, cAdvisor e Grafana com painel pronto.
- **Deploy em VM** (`infra/deploy/`):
  - provisionamento idempotente (Docker, ufw 22/80/443, usuário de serviço, `.env` com permissão 600);
  - unit systemd e HTTPS automático pelo Caddy.
- **Operação:** backup e restauração testados, coleta de evidências Linux, teste de carga com k6 (50 usuários).
- **Testes:** backend (173), ML (16), e2e Playwright dos três fluxos (4) e axe (0 violações).
- **PWA:** manifest, ícones, service worker com cache só do shell, página offline.

### Alterado
- O front deixou de ser a página única da Entrega 2 e virou um app React por papel. O mock fica fora do bundle de produção.
- O backend usa Python 3.12, exigência do XGBoost 3.4 do artefato final.
- Headers de segurança e CSP no Caddy; corpo da API limitado a 1 MB; `/metrics` nunca exposto pelo proxy.

### Corrigido
- O backend caía no modelo placeholder porque não reconhecia o formato do artefato final do ML.
- O chat não salvava as respostas na stack local: faltava `extensions` no `search_path` do PostgREST. Com isso, feedback e histórico davam 404.
- O admin não conseguia cadastrar documentos quando nenhum provedor de embeddings estava configurado.
- A tendência do detalhe divergia da fila para o mesmo estudante.
- Iniciais do avatar, fontes repetidas no rodapé do chat e textos técnicos na linha do tempo.
- O fallback lexical não juntava flexões ("cancelo"/"cancelamento").

### Segurança
- Varredura com gitleaks: nenhum segredo em todo o histórico (`docs/evidencias/gitleaks.txt`).
- Dados reais continuam fora do Git; a limpeza do histórico segue pendente (`docs/PENDENCIAS.md`).

## [0.2.0] · Entrega 2 (out/2026)
- Embeddings migrados para a Cloudflare (bge-m3, 1024d); deploy no Vercel; frontend React.

## [0.1.0] · Entrega 1 (set/2026)
- Protótipo do agente com RAG sobre seeds fictícios e baseline de risco (Regressão Logística, AUC 0,82).
