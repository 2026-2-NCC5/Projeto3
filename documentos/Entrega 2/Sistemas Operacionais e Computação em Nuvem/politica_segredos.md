# Política de segredos e rotação · ASA Turbo (VM AWS)

## 1. Inventário

| Segredo | Onde vive | Quem usa | Sai da VM? |
|---|---|---|---|
| `POSTGRES_PASSWORD` (papéis do Postgres local) | `/opt/asa/.env` | db, GoTrue, PostgREST, scripts de backup | só dentro do `asa_<ts>_config.tar.gz` |
| `SUPABASE_JWT_SECRET` (assina/valida JWT) | `/opt/asa/.env` | GoTrue, PostgREST, backend | idem |
| `SUPABASE_SERVICE_KEY` (service_role, ignora RLS) | `/opt/asa/.env` | **só o backend** | idem; nunca vai para o front |
| `SUPABASE_ANON_KEY` | `/opt/asa/.env` e o JS do front | navegador | é pública por definição |
| `DEMO_PASSWORD` (contas `*.demo@example.com` e de carga) | `/opt/asa/.env` + hash bcrypt em `auth.users` | GoTrue | entregue ao professor por canal privado |
| `MONITOR_HASH` (basic auth, bcrypt custo 14) | `/opt/asa/.env` | Caddy | o hash não é segredo forte; a senha em texto só existe fora do Git |
| `GRAFANA_ADMIN_PASSWORD` | `/opt/asa/.env` | Grafana | não |
| Senha do usuário `professor` no Grafana (Viewer) | banco do Grafana (volume) | professor | entregue por canal privado |
| Chave SSH ed25519 da equipe | máquina da equipe | acesso à VM | nunca vai para a VM (só a pública) |
| Certificado TLS (Let's Encrypt) | volume `caddy-data` | Caddy | renovado sozinho |

As senhas em texto (app, monitoramento e Grafana) ficam **só** em `~/.asa-segredos/vm.txt` (modo 600) na máquina da equipe, e daí num gerenciador de senhas. Não há segredo no repositório. O `.env.example` e o `infra/deploy/.env.producao.example` têm só nomes e placeholders.

## 2. Regras

1. **Nada de segredo no Git.** O `.env`, `backups/`, `*.dump` e `data/` estão no `.gitignore`. O gitleaks roda no histórico inteiro antes de cada push (ver `evidencias/gitleaks.txt`).
2. **O `.env` é `600` e o dono é `asa`.** O `/opt/asa` é `750`, o `backups/` é `700` e os arquivos de backup são `600`. O usuário `ubuntu` só lê com `sudo`.
3. **Os segredos são gerados na própria VM** (`preparar_env.py` + `/dev/urandom`). Não trafegam pela máquina da equipe, exceto as senhas que precisam ser entregues a pessoas.
4. **A `service_role` existe só no backend.** O front recebe só a chave `anon`, e as RLS do Postgres valem para ela.
5. **Os scripts nunca imprimem o `.env`.** O `evidencias.sh` mostra só dono e modo, e mascara qualquer `eyJ...`, `*_PASSWORD=` ou `*_HASH=` que escape. Senhas passam por stdin ou variável de ambiente, nunca por argumento de linha de comando (que aparece no `ps`).
6. **Os logs não registram token, chave nem texto do estudante** (`backend/app/core/logs.py`).
7. **Os backups contêm o `.env`** (dentro do `*_config.tar.gz`), porque sem ele não há recuperação. Por isso a cópia externa (`~/asa-backups-vm`) também é `700` e não pode ir para um bucket público nem para o Git.

## 3. Rotação sem derrubar o serviço

O compose recria **só** os containers cuja configuração mudou. O Caddy continua no ar e o healthcheck segura o tráfego até o backend novo responder. O backend sobe em cerca de 10 s. Durante a troca, as requisições ao `/api` podem receber 502 por alguns segundos. Para zero erro seria preciso uma segunda réplica (ver "Limitações" no relatório).

| O que trocar | Como | Impacto |
|---|---|---|
| Senha do monitoramento (basic auth) | `docker run --rm caddy:2.8.4-alpine caddy hash-password` → `MONITOR_HASH='...'` no `.env` → `sudo -u asa docker compose --project-directory /opt/asa up -d web` | recria só o Caddy (~2 s). O certificado fica no volume e não é pedido de novo |
| Senha do professor no Grafana | `GRAFANA_ADMIN_SENHA=... NOVA_SENHA=... bash infra/monitoring/criar_usuario_leitura.sh` (redefine se o usuário já existe) | nenhum |
| `DEMO_PASSWORD` | atualizar o `.env` + `docker compose up -d db-init` (reaplica o hash em `auth.users`, idempotente) | nenhum. As sessões abertas continuam até o JWT expirar (1 h) |
| `SUPABASE_JWT_SECRET` + chaves `anon`/`service_role` | `preparar_env.py` numa pasta temporária → copiar as 3 linhas para o `.env` → `docker compose build web` (a anon entra no JS) → `up -d` | recria GoTrue, PostgREST, backend e web. **Todos os usuários precisam logar de novo** (os tokens antigos deixam de valer). Fazer fora do horário de uso |
| `POSTGRES_PASSWORD` | `ALTER ROLE authenticator, supabase_auth_admin, postgres ... PASSWORD '<nova>'` via `docker compose exec db psql` → atualizar o `.env` → `up -d gotrue postgrest` | alguns segundos de reconexão do PostgREST/GoTrue |
| Chave SSH da equipe | adicionar a nova em `~ubuntu/.ssh/authorized_keys`, testar em outro terminal e só então remover a antiga | nenhum |
| Vazamento confirmado de qualquer item | trocar **imediatamente** pelo procedimento acima, apagar os backups antigos que contêm o `.env` velho e registrar no relatório | conforme o item |

Periodicidade sugerida: senhas de pessoas a cada 90 dias ou na saída de alguém da equipe; JWT secret e chaves uma vez por semestre; SSH quando a máquina da equipe mudar.

## 4. Controle de acesso

| Camada | Quem | Como |
|---|---|---|
| Rede | todos | security group da AWS + ufw: 80/443 abertas, 22 só para o IP da equipe |
| SSH | equipe | só por chave ed25519; root e senha desligados; fail2ban (5 falhas em 10 min = 1 h de bloqueio) |
| App | estudante, atendente, administrador | login no GoTrue (JWT), RBAC no backend (`exigir_papeis` em `app/core/auth.py`) e RLS no Postgres. O estudante recebe 403 em `/casos` (testado no smoke) |
| Monitoramento | professor (leitura) e equipe | HTTPS + basic auth no Caddy + login do Grafana (professor = Viewer). A equipe também pode usar o túnel SSH (`ssh -L 3000:127.0.0.1:3000 asa-vm`) |
| `/metrics` | só o Prometheus | rede interna do compose; pelo proxy, responde 404 |
| Banco | só os containers | sem porta publicada |
