// Screenshots (390 e 1280 px) e varredura axe de cada tela principal.
// Saída: /evidencias/telas/*.png e /evidencias/a11y.json (montado de docs/evidencias).
import { chromium } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync, writeFileSync } from 'node:fs'

const B = process.env.BASE_URL || 'http://localhost:8080'
const SENHA = 'AsaTurbo#Demo2026'
const OUT = process.env.OUT || '/evidencias'
mkdirSync(`${OUT}/telas`, { recursive: true })

const TELAS = [
  { nome: 'login', usuario: null, ir: async (p) => p.goto(B + '/entrar') },
  { nome: 'chat-inicio', usuario: 'estudante', ir: async (p) => p.goto(B + '/chat') },
  { nome: 'chat-conversa', usuario: 'estudante', ir: async (p) => {
      await p.goto(B + '/chat')
      await p.getByLabel('Sua pergunta').fill('Como tiro o atestado de matrícula?')
      await p.getByRole('button', { name: 'Enviar pergunta' }).click()
      await p.getByText(/Fonte|Fontes/).first().waitFor({ timeout: 20000 })
    } },
  { nome: 'fila', usuario: 'atendente', ir: async (p) => p.goto(B + '/fila') },
  { nome: 'caso', usuario: 'atendente', ir: async (p) => {
      await p.goto(B + '/fila')
      await p.locator('main a[href^="/fila/"], main a[href^="/admin/documentos/"]:not([href$="/novo"])').first().click()
    } },
  { nome: 'modelo', usuario: 'atendente', ir: async (p) => p.goto(B + '/modelo') },
  { nome: 'painel', usuario: 'admin', ir: async (p) => p.goto(B + '/admin') },
  { nome: 'documentos', usuario: 'admin', ir: async (p) => p.goto(B + '/admin/documentos') },
  { nome: 'documento', usuario: 'admin', ir: async (p) => {
      await p.goto(B + '/admin/documentos')
      await p.locator('main a[href^="/fila/"], main a[href^="/admin/documentos/"]:not([href$="/novo"])').first().click()
    } },
  { nome: 'novo-documento', usuario: 'admin', ir: async (p) => p.goto(B + '/admin/documentos/novo') },
]

async function entrar(p, usuario) {
  await p.goto(B + '/entrar')
  await p.getByLabel('E-mail').fill(`${usuario}.demo@example.com`)
  await p.getByLabel('Senha', { exact: true }).fill(SENHA)
  await p.getByRole('button', { name: 'Entrar' }).click()
  await p.waitForURL((u) => !u.pathname.startsWith('/entrar'))
}

const b = await chromium.launch()
const resultado = []
for (const largura of [390, 1280]) {
  const sessoes = {}
  for (const t of TELAS) {
    if (t.usuario && !sessoes[t.usuario]) {
      const ctx = await b.newContext({ viewport: { width: largura, height: 900 }, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo' })
      const p = await ctx.newPage()
      await entrar(p, t.usuario)
      sessoes[t.usuario] = ctx
    }
    const ctx = t.usuario ? sessoes[t.usuario] : await b.newContext({ viewport: { width: largura, height: 900 }, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo' })
    const p = await ctx.newPage()
    await t.ir(p)
    await p.waitForLoadState('networkidle')
    await p.waitForTimeout(800)
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    await p.screenshot({ path: `${OUT}/telas/${t.nome}-${largura}.png`, fullPage: true })
    const axe = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    const v = axe.violations.map((x) => ({ id: x.id, impacto: x.impact, n: x.nodes.length, ajuda: x.help, alvos: x.nodes.slice(0, 3).map((n) => n.target.join(' ')) }))
    resultado.push({ tela: t.nome, largura, titulo: await p.title(), overflow_px: overflow, violacoes: v })
    console.log(`${t.nome}@${largura} | ${await p.title()} | overflow ${overflow}px | axe ${v.map((x) => `${x.id}(${x.impacto},${x.n})`).join(' ') || 'ok'}`)
    await p.close()
    if (!t.usuario) await ctx.close()
  }
  for (const c of Object.values(sessoes)) await c.close()
}
writeFileSync(`${OUT}/a11y.json`, JSON.stringify(resultado, null, 2))
await b.close()
