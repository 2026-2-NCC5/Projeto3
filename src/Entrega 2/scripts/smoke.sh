#!/usr/bin/env bash
# Smoke test do ASA Turbo contra qualquer URL (local ou nuvem). Só precisa de curl e python3.
#   scripts/smoke.sh https://asa-turbo.onrender.com
#   scripts/smoke.sh http://localhost:8080
# Em DEMO_MODE entra pelos perfis de demo (/api/demo/entrar). Fora dele, informe um token:
#   TOKEN_ESTUDANTE=... TOKEN_ATENDENTE=... TOKEN_ADMIN=... scripts/smoke.sh <URL>
set -uo pipefail
URL="${1:?uso: scripts/smoke.sh <URL>}"; URL="${URL%/}"
API="${API_PREFIXO:-/api}"
falhas=0
ok()    { printf '  OK     %s\n' "$1"; }
falha() { printf '  FALHA  %s  (%s)\n' "$1" "$2"; falhas=$((falhas + 1)); }
campo() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {'d': d}))" "$1" 2>/dev/null; }

req() { # método caminho [token] [json] -> corpo em $CORPO, status em $STATUS
  local args=(-s -m 30 -o /tmp/smoke.$$ -w '%{http_code}' -X "$1" "$URL$2" -H 'Accept: application/json')
  [ -n "${3:-}" ] && args+=(-H "Authorization: Bearer $3")
  [ -n "${4:-}" ] && args+=(-H 'Content-Type: application/json' --data "$4")
  STATUS=$(curl "${args[@]}"); CORPO=$(cat /tmp/smoke.$$ 2>/dev/null); rm -f /tmp/smoke.$$
}

echo "ASA Turbo · smoke em $URL"

req GET /health
if [ "$STATUS" = 200 ]; then ok "/health ($(echo "$CORPO" | campo "d['status'] + ' · modelo ' + str(d['versao_modelo_risco'])"))"; else falha "/health" "HTTP $STATUS"; fi

req GET /
if [ "$STATUS" = 200 ] && grep -qi "<title" <<<"$CORPO"; then ok "página inicial (web)"; else falha "página inicial (web)" "HTTP $STATUS"; fi

token() { # papel
  local var="TOKEN_$(echo "$1" | tr a-z A-Z)"; [ "$1" = administrador ] && var=TOKEN_ADMIN
  if [ -n "${!var:-}" ]; then echo "${!var}"; return; fi
  req POST "$API/demo/entrar" "" "{\"papel\":\"$1\"}"
  [ "$STATUS" = 200 ] && echo "$CORPO" | campo "d['access_token']"
}
TE=$(token estudante); TA=$(token atendente); TD=$(token administrador)
if [ -n "$TE" ] && [ -n "$TA" ] && [ -n "$TD" ]; then ok "login dos 3 perfis de demonstração"; else falha "login de demonstração" "sem token (DEMO_MODE desligado? use TOKEN_*)"; fi

req POST "$API/chat" "$TE" '{"mensagem":"Como faço para trancar a matrícula?"}'
if [ "$STATUS" = 200 ] && [ "$(echo "$CORPO" | campo "len(d['fontes'])>0 and not d['abstencao']")" = True ]; then
  ok "/chat responde com fonte ($(echo "$CORPO" | campo "d['fontes'][0]['titulo']"))"
else falha "/chat" "HTTP $STATUS"; fi

req POST "$API/chat" "$TE" '{"mensagem":"Qual é o cardápio do restaurante hoje?"}'
if [ "$STATUS" = 200 ] && [ "$(echo "$CORPO" | campo "d['abstencao']")" = True ]; then ok "/chat se abstém fora do escopo"; else falha "/chat abstenção" "HTTP $STATUS"; fi

req GET "$API/casos" "$TA"
if [ "$STATUS" = 200 ] && [ "$(echo "$CORPO" | campo "d['total']>0")" = True ]; then
  ok "/casos ($(echo "$CORPO" | campo "str(d['total']) + ' na fila; topo: ' + d['itens'][0]['categoria']"))"
else falha "/casos" "HTTP $STATUS"; fi

req GET "$API/casos" "$TE"
if [ "$STATUS" = 403 ]; then ok "estudante não acessa /casos (403)"; else falha "RBAC /casos" "HTTP $STATUS, esperado 403"; fi

req GET "$API/admin/dashboard" "$TD"
if [ "$STATUS" = 200 ]; then ok "/admin/dashboard ($(echo "$CORPO" | campo "str(d['chat']['perguntas']) + ' perguntas no período'"))"; else falha "/admin/dashboard" "HTTP $STATUS"; fi

echo
if [ "$falhas" -eq 0 ]; then echo "Resultado: tudo OK"; else echo "Resultado: $falhas falha(s)"; fi
exit "$falhas"
