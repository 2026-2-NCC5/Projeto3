#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · coleta de evidências de operação Linux
#
#   infra/scripts/evidencias.sh                        # usa SITE_ADDRESS/PUBLIC_URL do .env
#   infra/scripts/evidencias.sh https://asa.dominio    # URL pública a testar
#
# Salva tudo em docs/evidencias/linux_<AAAAMMDD_HHMMSS>.txt. Comandos que não
# existem no ambiente (ex.: ufw ou journalctl fora da VM) aparecem como
# "indisponível" em vez de quebrar a coleta.
# NUNCA imprime o conteúdo do .env (só dono e permissões).
# =============================================================================
set -uo pipefail
# shellcheck source=infra/scripts/_comum.sh
source "$(dirname "${BASH_SOURCE[0]}")/_comum.sh"

url="${1:-}"
if [ -z "$url" ]; then
  url="$(ler_env PUBLIC_URL)"
  [ -z "$url" ] && url="http://localhost:$(ler_env WEB_PORT 8080)"
fi

destino_dir="$RAIZ/docs/evidencias"
mkdir -p "$destino_dir"
saida="$destino_dir/linux_$(date '+%Y%m%d_%H%M%S').txt"

secao() { printf '\n==============================================================================\n## %s\n$ %s\n------------------------------------------------------------------------------\n' "$1" "$2"; }
cmd() { # cmd "título" comando...
  local titulo="$1"; shift
  secao "$titulo" "$*"
  if command -v "$1" >/dev/null 2>&1; then
    "$@" 2>&1 | head -n "${LINHAS:-60}"
  else
    echo "(indisponível neste ambiente: '$1' não instalado)"
  fi
}
sh_cmd() { # sh_cmd "título" "pipeline"
  secao "$1" "$2"
  bash -c "$2" 2>&1 | head -n "${LINHAS:-60}"
}

{
  echo "# Evidências de operação · ASA Turbo"
  echo "# Coletado em: $(date '+%Y-%m-%d %H:%M:%S %Z') · host: $(hostname) · usuário: $(id -un)"
  echo "# Diretório: $RAIZ · URL testada: $url"

  cmd "Sistema operacional" uname -a
  sh_cmd "Distribuição" "grep -E '^(PRETTY_NAME|VERSION)=' /etc/os-release"
  cmd "Tempo ligado e carga" uptime
  cmd "Memória" free -h
  cmd "Disco" df -h -x tmpfs -x devtmpfs -x overlay
  LINHAS=15 sh_cmd "Processos por CPU (top 15)" "ps aux --sort=-%cpu | head -n 15"
  LINHAS=25 sh_cmd "top (instantâneo)" "top -b -n 1 | head -n 25"

  sh_cmd "Containers do ASA Turbo" "cd '$RAIZ' && docker compose ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
  sh_cmd "Uso de recursos por container" "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}'"
  sh_cmd "Usuário de cada container (nenhum serviço da aplicação como root)" "cd '$RAIZ' && for s in backend web; do c=\$(docker compose ps -q \$s); [ -n \"\$c\" ] && echo \"\$s: uid=\$(docker exec \$c id -u) (\$(docker exec \$c id -un 2>/dev/null))\"; done"
  sh_cmd "Healthchecks" "docker ps --filter name=asa-turbo --format '{{.Names}}: {{.Status}}'"

  if command -v journalctl >/dev/null 2>&1 && systemctl list-unit-files asa-turbo.service >/dev/null 2>&1 \
     && systemctl list-unit-files asa-turbo.service | grep -q asa-turbo; then
    sh_cmd "Serviço systemd" "systemctl status asa-turbo --no-pager | head -n 15"
    LINHAS=100 sh_cmd "Journal do serviço (últimas 100)" "journalctl -u asa-turbo --no-pager -n 100"
  else
    secao "Serviço systemd" "systemctl status asa-turbo"
    echo "(unidade asa-turbo.service não instalada neste host; na VM ela é instalada por infra/deploy/provisionar.sh)"
  fi

  sh_cmd "Permissões do .env (conteúdo nunca é exibido)" "ls -l '$ARQ_ENV' && stat -c 'modo=%a dono=%U grupo=%G' '$ARQ_ENV'"
  sh_cmd "Permissões dos backups" "ls -ld '$RAIZ/backups' 2>/dev/null && ls -l '$RAIZ/backups' 2>/dev/null | tail -n 5 || echo 'sem backups ainda'"

  if command -v ufw >/dev/null 2>&1; then
    sh_cmd "Firewall (ufw)" "ufw status verbose 2>&1 || sudo -n ufw status verbose 2>&1 || echo 'ufw requer sudo'"
  else
    secao "Firewall (ufw)" "ufw status verbose"
    echo "(ufw não instalado neste host; na VM, provisionar.sh libera só 22/80/443)"
  fi
  sh_cmd "Portas em escuta" "ss -tlnp 2>/dev/null | grep -Ev '127.0.0.53' || netstat -tlnp"

  sh_cmd "HTTP(S) público: cabeçalhos" "curl -sS -I --max-time 10 '$url'"
  sh_cmd "Saúde da API" "curl -sS --max-time 10 '$url/api/health'; echo"
  sh_cmd "/metrics NÃO exposto publicamente (espera 404)" "curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 '$url/api/metrics'"
  case "$url" in
    https://*) sh_cmd "Certificado TLS" "echo | openssl s_client -servername '${url#https://}' -connect '${url#https://}:443' 2>/dev/null | openssl x509 -noout -subject -issuer -dates" ;;
  esac

  LINHAS=8 sh_cmd "Logs JSON do backend (últimas linhas, arquivo rotacionado)" "cd '$RAIZ' && docker compose exec -T backend sh -c 'ls -l /var/log/asa/ && tail -n 3 /var/log/asa/backend.log'"
  LINHAS=6 sh_cmd "Logs de acesso do Caddy (JSON, rotacionado)" "cd '$RAIZ' && docker compose exec -T web sh -c 'ls -l /var/log/caddy/ && tail -n 2 /var/log/caddy/access.log'"
  sh_cmd "Rotação de logs dos containers (driver)" "docker inspect --format '{{.Name}} {{.HostConfig.LogConfig.Type}} {{.HostConfig.LogConfig.Config}}' \$(docker ps -q --filter name=asa-turbo)"
} > "$saida" 2>&1

# Defesa extra: se algo parecido com segredo escapou, mascara antes de salvar
sed -i -E 's/(eyJ[A-Za-z0-9_-]{10,})\.[A-Za-z0-9_.-]+/\1.<omitido>/g; s/(PASSWORD|SECRET|TOKEN|KEY)=[^ ]+/\1=<omitido>/g' "$saida"

echo "evidências salvas em ${saida#"$RAIZ"/}"
