#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · provisionamento de VM Ubuntu 24.04 (idempotente)
#
#   sudo bash infra/deploy/provision.sh             # aplica
#   sudo bash infra/deploy/provision.sh --dry-run   # só mostra o que faria
#
# Pode rodar quantas vezes quiser: cada passo confere antes de agir.
#   1. Atualiza pacotes + unattended-upgrades (atualizações de segurança diárias)
#   2. Docker Engine + plugin compose (repositório oficial da Docker)
#   3. Firewall ufw: nega entrada por padrão, libera só 22, 80 e 443
#   4. SSH só por chave, sem login de root (drop-in validado com sshd -t)
#   5. fail2ban protegendo o sshd
#   6. Usuário de serviço "asa" (sem senha, sem sudo, shell nologin)
#   7. /opt/asa (dono asa, 750), backups/ (700) e .env (600)
#   8. systemd: asa.service (compose no boot) + asa-backup.timer (backup diário)
#   9. logrotate para os logs do host (backup.log e afins)
# Não copia o código nem cria o .env: ver infra/deploy/README.md.
# =============================================================================
set -euo pipefail

DIR_APP="${DIR_APP:-/opt/asa}"
USUARIO="${USUARIO:-asa}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --fail2ban) ;;  # compatibilidade: o fail2ban agora é sempre instalado
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '\n[provision] %s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then printf '  (dry-run) %s\n' "$*"; else "$@"; fi; }
escrever() { # escrever <arquivo> <modo>  (conteúdo pelo stdin; só reescreve se mudou)
  local destino="$1" modo="$2" tmp
  tmp="$(mktemp)"; cat > "$tmp"
  if [ "$DRY" = 1 ]; then echo "  (dry-run) escrever $destino"; rm -f "$tmp"; return 1; fi
  if [ -f "$destino" ] && cmp -s "$tmp" "$destino"; then rm -f "$tmp"; return 1; fi
  install -m "$modo" "$tmp" "$destino"; rm -f "$tmp"
  echo "  escrito: $destino"; return 0
}
tem_systemd() { command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; }

if [ "$DRY" = 0 ] && [ "$(id -u)" -ne 0 ]; then echo "Rode como root (sudo)." >&2; exit 1; fi
# shellcheck disable=SC1091
[ -r /etc/os-release ] && . /etc/os-release
[ "${ID:-}" = ubuntu ] || echo "Aviso: testado em Ubuntu 24.04; este sistema é ${PRETTY_NAME:-desconhecido}." >&2
CODENAME="${VERSION_CODENAME:-noble}"
export DEBIAN_FRONTEND=noninteractive
# Fuso de São Paulo: horário do timer de backup e das evidências
if [ "$(timedatectl show -p Timezone --value 2>/dev/null)" != "America/Sao_Paulo" ]; then
  run timedatectl set-timezone America/Sao_Paulo
fi
APT_OPTS=(-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

# ----------------------------------------------------------------- 1. pacotes
log "1/9 atualização de pacotes e unattended-upgrades"
run apt-get update -y
run apt-get "${APT_OPTS[@]}" upgrade
run apt-get install "${APT_OPTS[@]}" --no-install-recommends \
  ca-certificates curl gnupg ufw fail2ban unattended-upgrades logrotate htop jq rsync lsb-release
escrever /etc/apt/apt.conf.d/20auto-upgrades 0644 <<'EOF' || true
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# ------------------------------------------------------------------ 2. docker
log "2/9 Docker Engine + compose"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "  Docker já instalado: $(docker --version)"
else
  run install -m 0755 -d /etc/apt/keyrings
  [ -f /etc/apt/keyrings/docker.asc ] || run curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  run chmod a+r /etc/apt/keyrings/docker.asc
  ARQ="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
  echo "deb [arch=${ARQ} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
    | escrever /etc/apt/sources.list.d/docker.list 0644 || true
  run apt-get update -y
  run apt-get install "${APT_OPTS[@]}" docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
# Rotação dos logs dos containers no daemon (o compose também define a sua)
run install -d -m 0755 /etc/docker
if escrever /etc/docker/daemon.json 0644 <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" },
  "live-restore": true
}
EOF
then tem_systemd && systemctl restart docker; fi
tem_systemd && run systemctl enable --now docker

# --------------------------------------------------------------------- 3. ufw
log "3/9 firewall: só 22, 80 e 443"
run ufw default deny incoming
run ufw default allow outgoing
run ufw allow 22/tcp
run ufw allow 80/tcp
run ufw allow 443/tcp
run ufw --force enable
# Portas publicadas pelo Docker não passam pelo ufw (iptables próprio). Por isso o
# compose publica só 80/443 (Caddy); Grafana/Prometheus ficam em 127.0.0.1 ou atrás do Caddy.

# --------------------------------------------------------------------- 4. ssh
log "4/9 SSH só por chave e sem login de root"
# 00- vem antes do 50-cloud-init.conf: no sshd vale a PRIMEIRA ocorrência de cada opção.
if escrever /etc/ssh/sshd_config.d/00-asa-hardening.conf 0644 <<'EOF'
# ASA Turbo · gerado por infra/deploy/provision.sh
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
EOF
then
  if sshd -t; then
    tem_systemd && systemctl reload ssh
  else
    echo "  sshd -t falhou: removendo o drop-in para não trancar o acesso" >&2
    rm -f /etc/ssh/sshd_config.d/00-asa-hardening.conf; exit 1
  fi
fi

# ---------------------------------------------------------------- 5. fail2ban
log "5/9 fail2ban (sshd)"
if escrever /etc/fail2ban/jail.d/asa-sshd.local 0644 <<'EOF'
[sshd]
enabled  = true
backend  = systemd
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
then tem_systemd && systemctl restart fail2ban; fi
tem_systemd && run systemctl enable --now fail2ban

# ----------------------------------------------------------------- 6. usuário
log "6/9 usuário de serviço '$USUARIO'"
if id "$USUARIO" >/dev/null 2>&1; then
  echo "  já existe: $(id "$USUARIO")"
else
  run useradd --system --create-home --home-dir "/home/$USUARIO" --shell /usr/sbin/nologin "$USUARIO"
fi
run passwd -l "$USUARIO" >/dev/null
# grupo docker = pode falar com o daemon (equivale a root no host). É o preço de rodar o
# compose sem sudo; o usuário não tem senha, não tem shell de login e não está no sudoers.
getent group docker >/dev/null && run usermod -aG docker "$USUARIO"

# -------------------------------------------------------------- 7. diretórios
log "7/9 $DIR_APP (750), backups (700), .env (600)"
run install -d -m 0750 -o "$USUARIO" -g "$USUARIO" "$DIR_APP"
run install -d -m 0700 -o "$USUARIO" -g "$USUARIO" "$DIR_APP/backups"
if [ -f "$DIR_APP/.env" ]; then
  run chown "$USUARIO:$USUARIO" "$DIR_APP/.env"; run chmod 600 "$DIR_APP/.env"
  echo "  .env: $(stat -c '%A %U:%G' "$DIR_APP/.env")"
else
  echo "  .env ainda não existe (ver infra/deploy/README.md)"
fi

# ----------------------------------------------------------------- 8. systemd
log "8/9 systemd: asa.service e asa-backup.timer"
recarregar=0
for u in asa.service asa-backup.service asa-backup.timer; do
  if [ -f "$AQUI/$u" ]; then
    escrever "/etc/systemd/system/$u" 0644 < "$AQUI/$u" && recarregar=1
  else
    echo "  $u não encontrado ao lado deste script" >&2
  fi
done
# nome antigo da unidade (versão anterior deste script)
if [ -f /etc/systemd/system/asa-turbo.service ]; then
  run systemctl disable --now asa-turbo.service || true; run rm -f /etc/systemd/system/asa-turbo.service; recarregar=1
fi
if tem_systemd; then
  [ "$recarregar" = 1 ] && run systemctl daemon-reload
  run systemctl enable asa.service asa-backup.timer
  run systemctl start asa-backup.timer
fi

# --------------------------------------------------------------- 9. logrotate
log "9/9 logrotate"
escrever /etc/logrotate.d/asa 0644 <<EOF || true
# ASA Turbo · logs do host (os dos containers giram no driver json-file do Docker)
$DIR_APP/backups/*.log /var/log/asa/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su $USUARIO $USUARIO
}
EOF
run install -d -m 0750 -o "$USUARIO" -g "$USUARIO" /var/log/asa

log "pronto. Próximo: código em $DIR_APP, .env (600) e 'systemctl start asa' (infra/deploy/README.md)."
