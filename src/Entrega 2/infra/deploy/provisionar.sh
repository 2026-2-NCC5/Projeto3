#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · provisionamento de VM Ubuntu 24.04 (idempotente)
#
#   sudo bash infra/deploy/provisionar.sh             # aplica
#   sudo bash infra/deploy/provisionar.sh --dry-run   # só mostra o que faria
#   sudo bash infra/deploy/provisionar.sh --fail2ban  # inclui fail2ban (SSH)
#
# O que faz (pode rodar quantas vezes quiser):
#   1. Pacotes base + atualizações automáticas de segurança (unattended-upgrades)
#   2. Docker Engine + plugin compose pelo repositório oficial da Docker
#   3. Firewall ufw: nega entrada por padrão, libera só 22, 80 e 443
#   4. Usuário de serviço "asa" (sem senha, no grupo docker)
#   5. Diretório /opt/asa-turbo (dono asa) e .env com permissão 600
#   6. Unidade systemd asa-turbo.service (sobe no boot, reinicia se cair)
# Não copia o código nem o .env: isso é o passo seguinte do README.
# =============================================================================
set -euo pipefail

DIR_APP="${DIR_APP:-/opt/asa-turbo}"
USUARIO="${USUARIO:-asa}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY=0
FAIL2BAN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --fail2ban) FAIL2BAN=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '\n[provisionar] %s\n' "$*"; }
run() {
  if [ "$DRY" = 1 ]; then printf '  (dry-run) %s\n' "$*"; else "$@"; fi
}
tem_systemd() { command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; }

if [ "$DRY" = 0 ] && [ "$(id -u)" -ne 0 ]; then
  echo "Rode como root (sudo)." >&2
  exit 1
fi

if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  if [ "${ID:-}" != "ubuntu" ]; then
    echo "Aviso: testado em Ubuntu 24.04; este sistema é ${PRETTY_NAME:-desconhecido}." >&2
  fi
fi
CODENAME="${VERSION_CODENAME:-noble}"
export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------------------- 1. base
log "1/6 pacotes base e atualizações automáticas"
run apt-get update -y
run apt-get install -y --no-install-recommends ca-certificates curl gnupg ufw unattended-upgrades htop jq
if [ "$DRY" = 0 ]; then
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
else
  echo "  (dry-run) escrever /etc/apt/apt.conf.d/20auto-upgrades"
fi

# ---------------------------------------------------------------- 2. docker
log "2/6 Docker Engine + compose (repositório oficial)"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "  Docker já instalado: $(docker --version)"
else
  run install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    run curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    run chmod a+r /etc/apt/keyrings/docker.asc
  fi
  ARQ="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
  LINHA="deb [arch=${ARQ} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable"
  if [ "$DRY" = 0 ]; then
    echo "$LINHA" > /etc/apt/sources.list.d/docker.list
  else
    echo "  (dry-run) /etc/apt/sources.list.d/docker.list <- $LINHA"
  fi
  run apt-get update -y
  run apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
# Rotação de log também no daemon (os serviços do compose já definem a sua)
if [ "$DRY" = 0 ] && [ ! -f /etc/docker/daemon.json ]; then
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" },
  "live-restore": true
}
EOF
  if tem_systemd; then systemctl restart docker || true; fi
fi
if tem_systemd; then
  run systemctl enable --now docker
fi

# ------------------------------------------------------------------ 3. ufw
log "3/6 firewall: só 22, 80 e 443"
run ufw default deny incoming
run ufw default allow outgoing
run ufw allow 22/tcp
run ufw allow 80/tcp
run ufw allow 443/tcp
run ufw --force enable
# Portas publicadas pelo Docker passam por fora do ufw (iptables próprio).
# Por isso o compose publica só 80/443 (web) e o Grafana só em 127.0.0.1.

if [ "$FAIL2BAN" = 1 ]; then
  log "fail2ban (SSH)"
  run apt-get install -y fail2ban
  if [ "$DRY" = 0 ]; then
    mkdir -p /etc/fail2ban/jail.d
    cat > /etc/fail2ban/jail.d/asa-sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
EOF
    if tem_systemd; then systemctl enable --now fail2ban; systemctl restart fail2ban; fi
  fi
fi

# --------------------------------------------------------------- 4. usuário
log "4/6 usuário de serviço '$USUARIO'"
if id "$USUARIO" >/dev/null 2>&1; then
  echo "  usuário já existe"
else
  run useradd --system --create-home --home-dir "/home/$USUARIO" --shell /bin/bash "$USUARIO"
fi
if getent group docker >/dev/null 2>&1; then
  run usermod -aG docker "$USUARIO"
fi

# -------------------------------------------------------------- 5. diretório
log "5/6 diretório $DIR_APP e .env (600)"
run install -d -m 0750 -o "$USUARIO" -g "$USUARIO" "$DIR_APP"
run install -d -m 0750 -o "$USUARIO" -g "$USUARIO" "$DIR_APP/backups"
if [ -f "$DIR_APP/.env" ]; then
  run chown "$USUARIO:$USUARIO" "$DIR_APP/.env"
  run chmod 600 "$DIR_APP/.env"
  echo "  .env existente: dono $USUARIO, permissão 600"
else
  echo "  .env ainda não existe: copie infra/deploy/.env.producao.example para $DIR_APP/.env e preencha"
fi

# ---------------------------------------------------------------- 6. systemd
log "6/6 unidade systemd asa-turbo.service"
if [ -f "$AQUI/asa-turbo.service" ]; then
  run install -m 0644 "$AQUI/asa-turbo.service" /etc/systemd/system/asa-turbo.service
  if tem_systemd; then
    run systemctl daemon-reload
    run systemctl enable asa-turbo.service
    echo "  habilitada (sobe no boot). Inicie com: sudo systemctl start asa-turbo"
  else
    echo "  systemd não está ativo neste ambiente; unidade copiada, habilite depois."
  fi
else
  echo "  asa-turbo.service não encontrado ao lado deste script" >&2
fi

log "pronto. Próximos passos em infra/deploy/README.md (código, .env, migrations, subir)."
