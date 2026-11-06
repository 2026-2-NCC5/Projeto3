# e2e/ · testes de ponta a ponta (Playwright)

Rodam contra a stack local já no ar (`docker compose up -d`, http://localhost:8080). Não precisa de Node no host: os scripts usam a imagem oficial `mcr.microsoft.com/playwright:v1.49.1-noble`.

```bash
e2e/rodar.sh                 # 4 fluxos (estudante, sem acesso, atendente, admin); relatório em docs/evidencias/e2e/
e2e/run.sh node telas.mjs    # screenshots 390/1280 px + axe em docs/evidencias/telas/ e docs/evidencias/a11y.json
```

Os testes escrevem no banco de demonstração (ajustam um caso e criam/desativam um documento de teste).
