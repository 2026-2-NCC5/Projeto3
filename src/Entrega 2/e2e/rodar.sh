#!/bin/sh
# Roda os testes e2e (Playwright) contra a stack local já no ar (docker compose up).
# Relatório HTML e JSON em docs/evidencias/e2e/.
set -eu
cd "$(dirname "$0")"
[ -d node_modules ] || ./run.sh npm ci --no-audit --no-fund
./run.sh env RELATORIO_DIR=/evidencias/e2e npx playwright test "$@"
