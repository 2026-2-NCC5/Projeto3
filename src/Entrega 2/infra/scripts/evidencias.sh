#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · coleta de evidências da VM VIA SSH (roda na SUA máquina)
#
#   infra/scripts/evidencias.sh                      # host asa-vm, URL do sslip.io
#   infra/scripts/evidencias.sh asa-vm https://54-207-148-68.sslip.io [rotulo]
#
# Salva em EVIDENCIAS_DIR (padrão: documentos/Entrega 2/Sistemas Operacionais e
# Computação em Nuvem/evidencias/) o arquivo vm_<AAAAMMDD_HHMMSS>[_rotulo].txt com:
# uname, lsb_release, id do usuário de serviço, permissões do .env, ufw, ss -tlnp,
# docker ps, docker stats, systemctl status, journalctl, df, free, top/ps,
# fail2ban, sshd efetivo, timers e HTTPS. NUNCA lê o conteúdo do .env.
# O IP de quem conecta por SSH (o seu) é mascarado como <ip-admin>.
# Para a VM local (sem SSH), use infra/scripts/evidencias_local.sh.
# =============================================================================
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${1:-asa-vm}"
URL="${2:-https://54-207-148-68.sslip.io}"; URL="${URL%/}"
ROTULO="${3:-}"
DESTINO="${EVIDENCIAS_DIR:-$RAIZ/../../documentos/Entrega 2/Sistemas Operacionais e Computação em Nuvem/evidencias}"
mkdir -p "$DESTINO"
arq="$DESTINO/vm_$(date '+%Y%m%d_%H%M%S')${ROTULO:+_$ROTULO}.txt"

# shellcheck disable=SC2087  # expansão local de $URL é proposital
ssh -o BatchMode=yes "$HOST" "sudo bash -s" <<REMOTO > "$arq" 2>&1
URL='$URL'
APP=/opt/asa
s() { printf '\n==============================================================================\n## %s\n\$ %s\n------------------------------------------------------------------------------\n' "\$1" "\$2"; bash -c "\$2" 2>&1 | head -n "\${3:-60}"; }
echo "# Evidências da VM · ASA Turbo"
echo "# Coletado em: \$(date '+%Y-%m-%d %H:%M:%S %Z') · host: \$(hostname) · via SSH por \$(logname 2>/dev/null || echo ubuntu)"
s "Sistema operacional" "uname -a"
s "Distribuição" "lsb_release -a"
s "Tempo ligado e carga" "uptime"
s "Usuário de serviço (sem senha, sem sudo, shell nologin)" "id asa; getent passwd asa; passwd -S asa; sudo -l -U asa | tail -n 2"
s "Diretório da aplicação e permissões" "ls -ld \$APP \$APP/backups; ls -l \$APP/.env; stat -c 'modo=%a dono=%U grupo=%G %n' \$APP/.env"
s "Firewall (ufw)" "ufw status verbose"
s "Portas em escuta" "ss -tlnp"
s "SSH efetivo (só chave, sem root)" "sshd -T | grep -Ei '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|maxauthtries) '"
s "fail2ban" "fail2ban-client status; fail2ban-client status sshd"
s "Atualizações automáticas" "systemctl is-enabled unattended-upgrades; cat /etc/apt/apt.conf.d/20auto-upgrades"
s "Containers" "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
s "Uso de recursos por container" "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}'"
s "Limites de CPU/memória por container" "for c in \\\$(docker ps -q); do docker inspect --format '{{.Name}} cpus={{.HostConfig.NanoCpus}} mem={{.HostConfig.Memory}} restart={{.HostConfig.RestartPolicy.Name}} user={{.Config.User}}' \\\$c; done"
s "Serviço systemd" "systemctl status asa --no-pager" 20
s "Timer de backup" "systemctl list-timers asa-backup.timer --no-pager; systemctl status asa-backup.service --no-pager | head -n 8"
s "Journal do serviço (últimas 40)" "journalctl -u asa --no-pager -n 40" 45
s "Disco" "df -h -x tmpfs -x devtmpfs -x overlay"
s "Memória" "free -h"
s "top (instantâneo)" "top -b -n 1 | head -n 25"
s "Processos por memória" "ps aux --sort=-%mem | head -n 15"
s "Backups (sem conteúdo)" "ls -l \$APP/backups | tail -n 12; tail -n 8 \$APP/backups/backup.log"
s "logrotate" "cat /etc/logrotate.d/asa"
s "HTTPS: cabeçalhos" "curl -sS -I --max-time 10 \$URL/"
s "Saúde da API" "curl -sS --max-time 10 \$URL/api/health; echo"
s "/metrics não exposto (espera 404)" "curl -s -o /dev/null -w '%{http_code}\n' \$URL/api/metrics"
s "Monitoramento exige senha (espera 401)" "for p in /grafana/ /prometheus/; do printf '%s -> ' \\\$p; curl -s -o /dev/null -w '%{http_code}\n' \$URL\\\$p; done"
s "Certificado TLS" "echo | openssl s_client -servername \${URL#https://} -connect \${URL#https://}:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates"
s "Logs JSON do backend (últimas 3)" "cd \$APP && sudo -u asa docker compose exec -T backend tail -n 3 /var/log/asa/backend.log" 10
REMOTO

# mascara o IP de quem administra (o seu) e qualquer coisa parecida com segredo
meu_ip="$(ssh -o BatchMode=yes "$HOST" 'echo ${SSH_CLIENT%% *}' 2>/dev/null)"
[ -n "$meu_ip" ] && sed -i "s/${meu_ip//./\\.}/<ip-admin>/g" "$arq"
sed -i -E 's/(eyJ[A-Za-z0-9_-]{10,})\.[A-Za-z0-9_.-]+/\1.<omitido>/g; s/(PASSWORD|SECRET|TOKEN|KEY|HASH)=[^ ]+/\1=<omitido>/g' "$arq"
echo "evidências salvas em $arq"
