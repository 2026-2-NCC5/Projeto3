# infra/ · banco, containers e operação

| Caminho | Conteúdo |
|---|---|
| `sql/001_schema_base.sql` | Estado do banco em produção: o schema da Entrega 1 com embeddings em 1024d. Só para banco novo. |
| `sql/002_contrato_v09.sql` | Ajustes para o contrato v0.9: tabelas de risco, versões de documento, RLS completo e a view `vw_fila_risco`. Idempotente. |
| `sql/historico/` | Scripts que já rodaram antes desta organização. Ficam só como registro. |

Regras:
- Migrations novas recebem o próximo número (`003_...sql`). Nunca edite uma migration que já rodou.
- Docker, compose, Caddyfile, backup e teste de carga entram na Fase 2.

Testado na Fase 0 num Postgres 16 + pgvector local, com um stub do schema `auth`. A sequência 001 → base de conhecimento → 002 → 002 → seed → seed rodou sem erro, e as policies foram conferidas: o estudante vê 0 scores e o atendente vê 1.800.
