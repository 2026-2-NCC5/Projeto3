// E2E do ASA Turbo contra a stack local (docker compose) em http://localhost:8080.
// Rodar: ./rodar.sh   (usa a imagem oficial do Playwright; não precisa de node no host)
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './testes',
  fullyParallel: false,
  workers: 1, // os fluxos escrevem no mesmo banco de demonstração
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: process.env.RELATORIO_DIR || 'relatorio', open: 'never' }],
    ['json', { outputFile: `${process.env.RELATORIO_DIR || 'relatorio'}/resultado.json` }],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8080',
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1280, height: 900 } } },
  ],
})
