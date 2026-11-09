// =============================================================================
// Prints do Grafana (durante o teste de carga) e do app em produção (Playwright).
// Senhas só por variável de ambiente; nada é gravado além dos PNGs.
//   docker run --rm --ipc=host -v "$PWD/e2e/node_modules:/n/node_modules:ro" \
//     -v "$PWD/infra/loadtest:/t:ro" -v "<saida>:/out" -w /n \
//     -e URL -e ROTULO -e MONITOR_USUARIO -e MONITOR_SENHA -e GRAFANA_USUARIO -e GRAFANA_SENHA \
//     -e APP_EMAIL -e APP_SENHA -e SO_GRAFANA=1 \
//     mcr.microsoft.com/playwright:v1.49.1-noble node /t/prints.mjs
// =============================================================================
import { chromium } from '/n/node_modules/@playwright/test/index.mjs'

const URL = process.env.URL.replace(/\/$/, '')
const ROTULO = process.env.ROTULO || 'agora'
const browser = await chromium.launch()

// --- Grafana: basic auth do Caddy + login do Grafana (usuário de leitura)
{
  const ctx = await browser.newContext({
    viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo',
    httpCredentials: { username: process.env.MONITOR_USUARIO, password: process.env.MONITOR_SENHA },
  })
  const p = await ctx.newPage()
  if (process.env.DEBUG) {
    p.on('console', (m) => m.type() === 'error' && console.log('console:', m.text().slice(0, 300)))
    p.on('pageerror', (e) => console.log('pageerror:', String(e).slice(0, 400)))
    p.on('requestfailed', (r) => console.log('falhou:', r.url().slice(0, 120), r.failure()?.errorText))
    p.on('response', (r) => r.status() >= 400 && console.log('http', r.status(), r.url().slice(0, 120)))
  }
  await p.goto(`${URL}/grafana/login`)
  await p.fill('input[name="user"]', process.env.GRAFANA_USUARIO)
  await p.fill('input[name="password"]', process.env.GRAFANA_SENHA)
  await p.click('button[type="submit"]')
  await p.waitForURL(/\/grafana\/(?!login)/)
  const janela = process.env.JANELA || 'now-15m'
  // kiosk: sem menus; 'from' cobre o teste inteiro
  await p.goto(`${URL}/grafana/d/asa-turbo/?orgId=1&from=${janela}&to=now&kiosk`)
  await p.waitForTimeout(8000)
  await p.screenshot({ path: `/out/grafana_${ROTULO}_1.png` })
  await p.mouse.wheel(0, 1000); await p.waitForTimeout(4000)
  await p.screenshot({ path: `/out/grafana_${ROTULO}_2.png` })
  await p.mouse.wheel(0, 1000); await p.waitForTimeout(4000)
  await p.screenshot({ path: `/out/grafana_${ROTULO}_3.png` })
  await p.mouse.wheel(0, 2000); await p.waitForTimeout(4000)
  await p.screenshot({ path: `/out/grafana_${ROTULO}_4.png` })
  // Prometheus: alertas
  await p.goto(`${URL}/prometheus/alerts`)
  await p.waitForTimeout(3000)
  await p.screenshot({ path: `/out/prometheus_alertas_${ROTULO}.png`, fullPage: true })
  await ctx.close()
}

// --- App em produção (login real, perfil atendente e estudante)
if (!process.env.SO_GRAFANA) {
  for (const [email, nome] of [[process.env.APP_EMAIL_ATENDENTE, 'atendente'], [process.env.APP_EMAIL_ESTUDANTE, 'estudante']]) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'pt-BR' })
    const p = await ctx.newPage()
    await p.goto(URL)
    await p.screenshot({ path: `/out/app_login.png` })
    await p.fill('input[type="email"]', email)
    await p.fill('input[type="password"]', process.env.APP_SENHA)
    await p.keyboard.press('Enter')
    await p.waitForTimeout(5000)
    await p.screenshot({ path: `/out/app_${nome}.png` })
    await ctx.close()
  }
}
await browser.close()
console.log('prints ok')
