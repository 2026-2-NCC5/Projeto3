# Runbook de desastre · ASA Turbo

**Objetivos:** RPO de 24 h e RTO de 30 min. Os valores medidos estão na seção 4.

- **RPO (perda máxima de dados): 24 h.** O backup roda todo dia às 03:15 (`asa-backup.timer`) e a cópia para fora da VM às 04:00 (`puxar_backups.sh` na máquina da equipe). Antes de qualquer mudança arriscada, rode um backup manual (`sudo systemctl start asa-backup`).
- **RTO (tempo até voltar ao ar): 30 min.** Inclui criar a VM na AWS, rodar o `provision.sh`, buildar as imagens e restaurar. O tempo medido no ensaio está na seção 4.

## 1. Cenários

| Cenário | Detecção | Ação |
|---|---|---|
| Container do backend morre | alerta `BackendFora`; `docker ps` | nada a fazer: `restart: unless-stopped` + healthcheck (testado, ver `evidencias/falhas/`) |
| VM reinicia | o site some por cerca de 1 min | nada a fazer: `asa.service` (enabled) sobe o compose no boot (testado) |
| Disco enchendo | alerta `DiscoQuaseCheio` (> 85%) | `docker system prune -af --filter until=168h`; conferir `backups/` e os logs; aumentar o volume gp3 no console da AWS (sem desligar) |
| Dados corrompidos ou apagados por engano | usuário ou equipe | `restore.sh backups/asa_<ts>.dump` (transação única; pede confirmação) |
| **VM perdida** (instância encerrada, disco corrompido, conta comprometida) | site fora, sem SSH | seção 2 |

## 2. VM perdida: passo a passo

Pré-requisitos, fora da VM: a cópia `~/asa-backups-vm/` (com dump, auth, config com `.env` e sha256), a chave SSH da equipe e o acesso ao console da AWS.

1. **Nova VM.** No console da AWS (sa-east-1): Ubuntu 24.04, m7i-flex.large, gp3 de 30 GB e o mesmo security group (80/443 abertas, 22 só para o IP da equipe). **Reassocie o IP elástico 54.207.148.68** à nova instância, para o nome `54-207-148-68.sslip.io` continuar valendo e o Caddy obter o certificado de novo. Atualize o `HostName` de `asa-vm` no `~/.ssh/config`, se mudar.
2. **Provisionar**, de uma vez e idempotente:
   ```bash
   ssh asa-vm 'curl -fsSL https://raw.githubusercontent.com/2026-2-NCC5/Projeto3/entrega2/nuvem/src/Entrega%202/infra/deploy/atualizar.sh | sudo SEM_RELOAD=1 bash && sudo bash /opt/asa/infra/deploy/provision.sh'
   ```
3. **Devolver o `.env` e os backups** da máquina da equipe:
   ```bash
   B=$(ls -t ~/asa-backups-vm/asa_*.dump | head -1); B=${B%.dump}
   rsync -a --rsync-path="sudo rsync" "$B".* "$B"_* asa-vm:/opt/asa/backups/
   ssh asa-vm "sudo tar -C /opt/asa -xzf /opt/asa/backups/$(basename $B)_config.tar.gz .env && sudo chown -R asa:asa /opt/asa && sudo chmod 600 /opt/asa/.env"
   ```
4. **Subir sem o seed de demonstração** (o banco vai receber o backup):
   ```bash
   ssh asa-vm 'D="sudo -u asa docker compose --project-directory /opt/asa"; $D build -q && $D up -d --wait db gotrue'
   ```
5. **Restaurar** auth e public no Postgres novo:
   ```bash
   ssh asa-vm "cd /tmp && sudo -u asa /opt/asa/infra/scripts/restaurar_vm_nova.sh /opt/asa/backups/$(basename $B).dump"
   ```
6. **Subir o resto e validar:**
   ```bash
   ssh asa-vm 'sudo systemctl start asa'
   SMOKE_SENHA=... ANON_KEY=... scripts/smoke.sh https://54-207-148-68.sslip.io
   ```
7. **Pós-incidente:** recriar o usuário `professor` no Grafana (`criar_usuario_leitura.sh`; o volume do Grafana não está no backup), rodar `evidencias.sh` e registrar a causa e os tempos. Se houve suspeita de comprometimento, **rotacionar todos os segredos** (`politica_segredos.md`, seção 3) em vez de reaproveitar o `.env`.

## 3. O que NÃO está coberto

- **Histórico do Prometheus e o banco do Grafana.** São reconstruíveis: o painel vem de arquivo e o histórico de métricas se perde.
- **Certificado TLS.** É emitido de novo automaticamente (limite do Let's Encrypt: 5 certificados duplicados por semana).
- **Falha da região sa-east-1 inteira.** Seria preciso subir em outra região com outro IP, e então o nome sslip.io muda (`SITE_ADDRESS`, `PUBLIC_URL`, `CORS_ORIGINS` no `.env` + `docker compose build web`).

## 4. Ensaio medido

O ensaio cronometrado deste runbook está em `src/Entrega 2/infra/scripts/ensaio_desastre.sh` (log em `evidencias/backup/ensaio_desastre_*.txt`). Os tempos de cada etapa e o RTO medido estão no relatório, seção 7.4.

Dois achados do ensaio já foram incorporados acima:
1. O `/opt/asa` é 750, então o `.env` é extraído com `tar -C` sob `sudo`, e não com `cd`.
2. Com a VM perdida não há como fazer um backup "agora": vale a última cópia externa, que define o RPO real.
