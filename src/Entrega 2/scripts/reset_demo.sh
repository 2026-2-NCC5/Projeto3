#!/usr/bin/env bash
# Restaura o estado inicial da demonstração (conversas, validações, documentos) em segundos.
#   scripts/reset_demo.sh                       # container local (http://localhost:8080)
#   scripts/reset_demo.sh https://sua-url        # deploy na nuvem
# Precisa de DEMO_MODE=true no servidor. Sem rede? Reiniciar o container também zera tudo.
set -euo pipefail
URL="${1:-http://localhost:8080}"; URL="${URL%/}"
token=$(curl -fsS -m 15 -X POST "$URL/api/demo/entrar" -H 'Content-Type: application/json' \
  --data '{"papel":"administrador"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
curl -fsS -m 60 -X POST "$URL/api/demo/reiniciar" -H "Authorization: Bearer $token" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("Demo restaurada. Topo da fila:"); [print(" -", h["historia"], "·", h["fator_principal"]) for h in d["historias"]]'
