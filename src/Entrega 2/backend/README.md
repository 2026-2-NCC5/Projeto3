# backend/ · API FastAPI (sessão backend)

Ainda vazio: é a Fase 1 da sessão backend.

- **Contrato:** `../docs/api-contract.yaml`. A implementação segue o contrato. Se precisar mudar o contrato, pare e combine antes.
- **Banco:** `../infra/sql/` (001 + 002). Use a chave `service_role` só aqui.
- **Ponto de partida do RAG:** `../web/api/perguntar.py`, a função serverless em produção no Vercel. Dela vêm a vetorização via Cloudflare (bge-m3, 1024d), a RPC `buscar_chunks_similares`, o limiar 0,55 e as regras de abstenção. Porte essa lógica para cá. A pasta `web/api/` só sai depois que o deploy apontar para este backend.
- Python 3.11, pydantic-settings, logs JSON, `ruff` + `pytest`, Docker.
