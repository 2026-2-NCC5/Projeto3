#!/bin/sh
# Roda um comando dentro da imagem do Playwright, com a stack local em localhost:8080.
cd "$(dirname "$0")"
exec docker run --rm --network host --ipc=host -u "$(id -u):$(id -g)" -e HOME=/tmp -e CI=1 \
  -v "$PWD":/e2e -v "$PWD/../docs/evidencias":/evidencias -w /e2e \
  mcr.microsoft.com/playwright:v1.49.1-noble "$@"
