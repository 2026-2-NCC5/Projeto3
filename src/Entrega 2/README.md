# ASA Turbo · Entrega 2

Agentes de IA para o ASA (Área do Sucesso Alvarista) da FECAP, com foco em reduzir a evasão.
O **ASA Turbo** responde às dúvidas do estudante com base nos documentos oficiais, citando fonte e data, e encaminha para um atendente quando não tem certeza. O **monitoramento de risco** ajuda o atendente a priorizar contatos, sempre com validação humana. O estudante nunca vê o score.

Projeto Interdisciplinar · 5º CCOMP · 2026.2. Contexto completo e regras em [`CLAUDE.md`](CLAUDE.md).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `backend/` | API FastAPI (Python 3.11, Docker). Valida o JWT do Supabase e aplica RBAC. |
| `web/` | App React + Vite (PWA). Design system em `web/src/styles/` e referência em `web/design-system.html`. |
| `ml/` | Modelo de risco, avaliação do RAG e geração de embeddings (`ml/rag/`). |
| `infra/` | Migrations SQL (`infra/sql/`). Docker, Caddy, backup e carga entram na Fase 2. |
| `seeds/` | Dados **fictícios** de demonstração e os usuários de demo. |
| `docs/` | Contrato da API (`api-contract.yaml`), decisões e evidências. |
| `data/` | Dados reais do ASA. **Fora do Git, só local.** |

## Como rodar local

> Será completado na Fase 2 (`docker compose up`). Por enquanto:

```bash
cp .env.example .env               # preencha (nunca commite o .env)

# Banco: veja seeds/README.md para a ordem (001 → base → 002 → usuários → seed)

# Front atual (usa a API publicada via proxy)
cd web && npm install && npm run dev
# http://localhost:5173 · design system em http://localhost:5173/design-system.html
```

## Referências

- Contrato da API: [`docs/api-contract.yaml`](docs/api-contract.yaml)
- Decisões da Fase 0: [`docs/decisoes/0001-fase0.md`](docs/decisoes/0001-fase0.md)
- Seeds e usuários de demonstração: [`seeds/README.md`](seeds/README.md)
- App publicado (Entrega 2): https://projeto-ia-rho.vercel.app/
