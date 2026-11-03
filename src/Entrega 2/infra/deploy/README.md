# Deploy em VM Linux (Ubuntu 24.04) com HTTPS

Arquitetura em produção: **uma VM** roda `docker compose` com dois serviços, `web` (Caddy servindo o front e fazendo proxy de `/api`) e `backend` (FastAPI). Banco, login e RLS ficam no **Supabase gerenciado**. O Caddy pede e renova o certificado HTTPS (Let's Encrypt) sozinho. O monitoramento (Prometheus, Grafana e cAdvisor) é opcional.

```
navegador ──HTTPS──> VM :443  [web: Caddy] ──/api/*──> [backend: FastAPI] ──> Supabase (PostgREST + Auth)
              │                     └── estático (React build)
              └──────── login direto no Supabase Auth (chave anon, pública)
```

| Arquivo | Para quê |
|---|---|
| `provisionar.sh` | Prepara a VM (idempotente): Docker oficial, ufw (22/80/443), usuário `asa`, `/opt/asa-turbo`, systemd |
| `asa-turbo.service` | Unidade systemd: sobe o compose no boot e para no shutdown |
| `.env.producao.example` | Modelo do `.env` de produção (sem valores reais) |
| `../scripts/backup.sh`, `restore.sh` | Backup diário e restauração do banco |
| `../scripts/evidencias.sh` | Coleta evidências (htop/ps, journalctl, df, permissões, ufw, HTTPS) em `docs/evidencias/` |

## 1. Criar a VM

- Ubuntu Server 24.04 LTS, mínimo de **2 vCPU e 4 GB de RAM**. O build do front e o modelo XGBoost pedem memória; com 2 GB, use swap. Disco de 20 GB.
- IP público fixo. No firewall do provedor (security group), libere a entrada em **22, 80 e 443**.
- Acesso por chave SSH (sem senha).

## 2. Apontar o domínio

Crie um registro **A** (e AAAA, se houver IPv6), por exemplo `asa.seudominio.com.br` → IP da VM. Confira antes de subir, porque o Let's Encrypt valida pelo DNS:

```bash
dig +short asa.seudominio.com.br     # deve devolver o IP da VM
```

## 3. Provisionar

```bash
ssh ubuntu@IP-DA-VM
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/<org>/<repo>.git /tmp/asa
sudo bash "/tmp/asa/src/Entrega 2/infra/deploy/provisionar.sh" --dry-run   # confere o que vai fazer
sudo bash "/tmp/asa/src/Entrega 2/infra/deploy/provisionar.sh" --fail2ban
```

Pode rodar de novo quantas vezes quiser: cada passo verifica antes de agir.

## 4. Código e `.env`

```bash
# O conteúdo de "src/Entrega 2" vira /opt/asa-turbo (raiz do compose)
sudo rsync -a --delete --exclude data/ --exclude .env "/tmp/asa/src/Entrega 2/" /opt/asa-turbo/
sudo cp /opt/asa-turbo/infra/deploy/.env.producao.example /opt/asa-turbo/.env
sudo nano /opt/asa-turbo/.env                      # preencha domínio, chaves do Supabase, Cloudflare...
sudo chown -R asa:asa /opt/asa-turbo && sudo chmod 600 /opt/asa-turbo/.env
```

Pontos de atenção no `.env`:
- `SITE_ADDRESS` é **só o domínio**, sem `https://`. É ele que faz o Caddy ativar o HTTPS.
- `SUPABASE_SERVICE_KEY` é a chave legacy `service_role` (`eyJ...`). Ela fica só neste arquivo.
- `PUBLIC_SUPABASE_URL` e `SUPABASE_ANON_KEY` entram no build do front, porque o navegador faz login direto no Supabase.
- `CSP_CONNECT_EXTRA` precisa ter a URL do Supabase. Sem ela, o navegador bloqueia o login (CSP).
- `COMPOSE_PROFILES` fica vazio (ou `monitoring`), **nunca** `local`.
- A pasta `data/` (dados reais) **nunca** vai para a VM.

## 5. Banco no Supabase (uma vez)

No SQL Editor do projeto Supabase, na ordem de `seeds/README.md`:

1. `infra/sql/001_schema_base.sql`, só se o projeto for novo.
2. `seeds/base_conhecimento_oficial.sql`
3. `infra/sql/002_contrato_v09.sql`
4. `infra/sql/003_backend_rpcs.sql`

Depois, na VM, crie os usuários de demonstração e os dados fictícios:

```bash
cd /opt/asa-turbo
sudo -u asa docker run --rm -v "$PWD:/w" -w /w --env-file .env python:3.12-slim \
  sh -c "pip -q install requests && python seeds/criar_usuarios_demo.py"
# SQL Editor: rode seeds/seed_demo.sql
# Embeddings da base (Cloudflare):
sudo -u asa docker run --rm -v "$PWD:/w" -w /w --env-file .env python:3.12-slim \
  sh -c "pip -q install requests && python ml/rag/gerar_embeddings.py"
```

## 6. Subir

```bash
sudo systemctl start asa-turbo          # = docker compose up -d (build na 1ª vez, alguns minutos)
sudo systemctl status asa-turbo
sudo -u asa docker compose -f /opt/asa-turbo/docker-compose.yml ps
```

Os containers têm `restart: unless-stopped`, e o systemd sobe o compose a cada boot.

## 7. Verificar

```bash
curl -I https://asa.seudominio.com.br                 # 200, com Strict-Transport-Security
curl -s https://asa.seudominio.com.br/api/health      # "banco": "ok", "embeddings": "ok"
curl -s -o /dev/null -w '%{http_code}\n' https://asa.seudominio.com.br/api/metrics   # 404 (não exposto)
echo | openssl s_client -connect asa.seudominio.com.br:443 -servername asa.seudominio.com.br 2>/dev/null \
  | openssl x509 -noout -issuer -dates              # emissor Let's Encrypt
cd /opt/asa-turbo && sudo -u asa infra/scripts/evidencias.sh https://asa.seudominio.com.br
```

Se o certificado não sair, veja `docker compose logs web`. As causas mais comuns são DNS ainda não propagado ou a porta 80 fechada no provedor (o desafio HTTP-01 do Let's Encrypt usa a 80).

## 8. Backup diário

```bash
sudo -u asa crontab -e
# Backup às 03:15; retenção = BACKUP_RETENCAO_DIAS (padrão 7)
15 3 * * * cd /opt/asa-turbo && infra/scripts/backup.sh >> backups/backup.log 2>&1
```

- `backup.sh` usa `DATABASE_URL` (Supabase) com um container `postgres:17.2-alpine`. Se o projeto Supabase estiver em Postgres 15, rode com `IMAGEM_PG_CLIENTE=postgres:15-alpine`.
- Cada backup gera `backups/asa_<data>.dump` mais o `.sha256`. Copie para fora da VM (outro bucket ou máquina) de tempos em tempos.
- Para restaurar: `infra/scripts/restore.sh backups/asa_<data>.dump`. O script pede confirmação, confere o sha256 e restaura numa única transação.
- O schema `auth` (usuários) fica a cargo do backup do próprio Supabase. O script cobre o schema `public`, que tem tudo o que a aplicação grava.
- Há um teste real de ponta a ponta em `docs/evidencias/backup_restore_teste.txt`.

## 9. Monitoramento (opcional)

```bash
# no .env: COMPOSE_PROFILES=monitoring  (e GRAFANA_ADMIN_PASSWORD)
sudo systemctl reload asa-turbo
# Grafana só escuta em 127.0.0.1. Do seu computador:
ssh -L 3000:127.0.0.1:3000 ubuntu@IP-DA-VM     # abra http://localhost:3000 (usuário admin)
```

O painel "ASA Turbo · Operação" já vem provisionado, com:
- requisições/s e latência p95 por rota;
- erros 5xx e respostas de erro por status;
- CPU e memória por serviço;
- taxa e motivos de abstenção do chat;
- recuperação do RAG por método e uso do fallback de embeddings;
- validações humanas e feedback.

## 10. Atualizar a versão

```bash
cd /tmp/asa && sudo git fetch --tags && sudo git checkout v0.9.1        # a nova tag
sudo rsync -a --delete --exclude data/ --exclude .env --exclude backups/ "/tmp/asa/src/Entrega 2/" /opt/asa-turbo/
sudo chown -R asa:asa /opt/asa-turbo
cd /opt/asa-turbo && sudo -u asa infra/scripts/backup.sh               # backup antes de mudar
sudo -u asa docker compose build && sudo systemctl reload asa-turbo     # recria só o que mudou
```

Se a versão nova tiver uma migration (`infra/sql/00N_*.sql`), aplique-a no Supabase **antes** do `reload`. As migrations são aditivas e idempotentes.

## 11. Rollback

```bash
cd /tmp/asa && sudo git checkout v0.9.0
sudo rsync -a --delete --exclude data/ --exclude .env --exclude backups/ "/tmp/asa/src/Entrega 2/" /opt/asa-turbo/
sudo chown -R asa:asa /opt/asa-turbo
cd /opt/asa-turbo && sudo -u asa docker compose build && sudo systemctl reload asa-turbo
# Só se a versão nova tiver estragado dados:
sudo -u asa infra/scripts/restore.sh backups/asa_<data-anterior>.dump
```

Mantenha as imagens anteriores (`docker image ls asa-turbo-*`) até confirmar a versão nova. Como a tag das imagens segue a versão do compose, voltar o código e rodar `build` recria a imagem anterior.

## Comandos úteis

```bash
journalctl -u asa-turbo -f                                    # systemd
sudo -u asa docker compose -f /opt/asa-turbo/docker-compose.yml logs -f backend   # logs JSON
sudo -u asa docker compose -f /opt/asa-turbo/docker-compose.yml exec backend tail -f /var/log/asa/backend.log
htop ; df -h ; sudo ufw status verbose ; ls -l /opt/asa-turbo/.env   # esperado: -rw------- asa asa
```
