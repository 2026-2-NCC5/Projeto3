# Auditoria inicial (09/11/2026, antes desta entrega)

O que já existia no repositório para cada item do enunciado, antes do trabalho da branch `entrega2/nuvem`.

| Item do enunciado | Status antes | Arquivo |
|---|---|---|
| Empacotamento Docker multi-stage, não-root, HEALTHCHECK | pronto | `infra/backend.Dockerfile`, `infra/web.Dockerfile`, `Dockerfile` |
| Limites de CPU e memória por serviço | ausente | `docker-compose.yml` |
| `.env` / `.env.example` / `.dockerignore` | pronto | `.env.example`, `infra/deploy/.env.producao.example`, `*.dockerignore` |
| Proxy com HTTPS e headers | pronto, mas nunca testado com certificado real | `infra/caddy/Caddyfile` |
| Banco | parcial: Postgres + pgvector self-hosted só no profile `local`; o Supabase gerenciado sem as migrations 002 a 004 | `docker-compose.yml`, `infra/sql/` |
| Provisionamento da VM | parcial: sem hardening de SSH, logrotate e `/opt/asa`; nunca rodou numa VM | `infra/deploy/provisionar.sh` |
| systemd | pronto, não testado | `infra/deploy/asa-turbo.service` |
| Logs JSON com `request_id` e latência | pronto | `backend/app/core/logs.py`, `middleware.py` |
| `/metrics` (requisições, latência, erros, abstenções, fallback) | pronto | `backend/app/core/metricas.py` |
| Prometheus + Grafana + cAdvisor | parcial: sem node-exporter, alertas, p50/p99 nem painéis de host e disco | `infra/monitoring/` |
| Monitoramento com acesso controlado | ausente (só túnel SSH) | – |
| Teste de carga | parcial: 50 VUs na máquina local, sem rampa até 100, sem `/health` nem login | `infra/loadtest/carga.js` |
| Backup e restauração | parcial: só o banco; sem config e modelo, sem timer, sem cópia externa, sem teste em Postgres limpo, sem RPO/RTO | `infra/scripts/backup.sh`, `restore.sh` |
| Evidências Linux | parcial: rodava no host, não via SSH; sem fail2ban nem `id` | `infra/scripts/evidencias.sh` |
| Deploy em nuvem | ausente: só a demo `asa-turbo.onrender.com` (DEMO_MODE, dados em memória) | `render.yaml`, `fly.toml` |
| Relatório de monitoramento | ausente | – |
