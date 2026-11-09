#!/usr/bin/env bash
# =============================================================================
# Cria (ou redefine a senha de) um usuário SÓ LEITURA (Viewer) no Grafana.
# Roda NA VM. As senhas vêm por variável de ambiente, nunca por argumento:
#   GRAFANA_ADMIN_SENHA=... NOVO_USUARIO=professor NOVA_SENHA=... bash criar_usuario_leitura.sh
# (O basic auth da API do Grafana está desligado; usa login por sessão.)
# =============================================================================
set -euo pipefail
B="${GRAFANA_URL:-http://127.0.0.1:3000/grafana}"
U="${NOVO_USUARIO:-professor}"
J=$(mktemp); D=$(mktemp); trap 'rm -f "$J" "$D"' EXIT
python3 -c 'import json,os;print(json.dumps({"user":"admin","password":os.environ["GRAFANA_ADMIN_SENHA"]}))' > "$D"
curl -sf -o /dev/null -c "$J" -H 'Content-Type: application/json' -X POST "$B/login" --data @"$D"
python3 -c 'import json,os;print(json.dumps({"name":"Leitura: "+os.environ.get("NOVO_USUARIO","professor"),"login":os.environ.get("NOVO_USUARIO","professor"),"email":os.environ.get("NOVO_USUARIO","professor")+"@localhost","password":os.environ["NOVA_SENHA"],"OrgId":1}))' > "$D"
codigo=$(curl -s -o /dev/null -w '%{http_code}' -b "$J" -H 'Content-Type: application/json' -X POST "$B/api/admin/users" --data @"$D")
if [ "$codigo" = 412 ]; then  # já existe: redefine a senha (rotação)
  id=$(curl -s -b "$J" "$B/api/users/lookup?loginOrEmail=$U" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
  python3 -c 'import json,os;print(json.dumps({"password":os.environ["NOVA_SENHA"]}))' > "$D"
  codigo=$(curl -s -o /dev/null -w '%{http_code}' -b "$J" -H 'Content-Type: application/json' -X PUT "$B/api/admin/users/$id/password" --data @"$D")
  echo "senha de '$U' redefinida: HTTP $codigo"
else
  echo "usuário '$U' criado como Viewer: HTTP $codigo"
fi
curl -s -b "$J" "$B/api/org/users" | python3 -c 'import json,sys;[print("  ",u["login"],u["role"]) for u in json.load(sys.stdin)]'
