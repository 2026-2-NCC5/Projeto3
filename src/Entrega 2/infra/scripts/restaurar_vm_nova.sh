#!/usr/bin/env bash
# Runbook de desastre, passo 5: restaura auth + public de um backup no Postgres NOVO
# (vazio) do projeto principal, sem derrubar nada. Ver runbook_desastre.md.
#   infra/scripts/restaurar_vm_nova.sh backups/asa_<ts>.dump
set -euo pipefail
PROJETO=asa-turbo MANTER=1 exec "$(dirname "$0")/teste_restauracao.sh" "$@"
