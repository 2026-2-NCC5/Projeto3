import { test, expect } from '@playwright/test'
import { entrar, marca } from './apoio.js'

test('atendente: filtra a fila, abre o caso, ajusta a faixa com justificativa e vê no histórico', async ({ page }) => {
  await entrar(page, 'atendente')
  await expect(page).toHaveURL(/\/fila/)
  await expect(page).toHaveTitle('Fila de risco · ASA Turbo')

  // Filtro por categoria Vermelho
  await page.getByRole('button', { name: /^Vermelho \d+ Filtrar/ }).click()
  const tabela = page.getByRole('table', { name: 'Fila de risco de evasão' })
  await expect(tabela.locator('tbody tr').first()).toBeVisible()
  const linhas = tabela.locator('tbody tr')
  const n = await linhas.count()
  for (let i = 0; i < n; i++) await expect(linhas.nth(i)).toContainText(/Vermelho/)

  // Busca pelo RA do primeiro da lista
  const primeiro = linhas.first()
  const ra = (await primeiro.textContent()).match(/RA (\d{8})/)[1]
  const nome = await primeiro.getByRole('link').first().textContent()
  await page.getByRole('searchbox', { name: 'Buscar' }).fill(ra)
  await expect(linhas).toHaveCount(1)
  await linhas.first().getByRole('link', { name: nome }).click()

  // Detalhe: score, fatores, tendência, recomendação, versão e data
  await expect(page.getByRole('heading', { level: 1, name: nome })).toBeVisible()
  await expect(page).toHaveTitle(`${nome} · ASA Turbo`)
  const risco = page.getByRole('region', { name: 'Risco de evasão' })
  await expect(risco).toContainText(/\d+%/)
  await expect(risco).toContainText(/Modelo risco-\d+\.\d+\.\d+ · calculado em \d{2}\/\d{2}\/\d{4}/)
  await expect(page.getByRole('region', { name: 'Tendência dos últimos 6 meses' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'O que mais pesou' }).getByRole('listitem').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'Recomendação sugerida' })).toContainText('A decisão é do atendente')

  // Validação "ajustado" com justificativa
  const justificativa = `Acordo de parcelas fechado nesta semana (e2e ${marca()}).`
  await page.getByRole('radio', { name: /Ajustar/ }).check()
  await page.getByLabel('Nova faixa').selectOption({ index: 1 })
  await page.getByLabel('Justificativa').fill(justificativa)
  await page.getByRole('button', { name: 'Registrar avaliação' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Avaliação registrada.' })).toBeVisible()

  // Histórico mostra a validação
  await expect(page.getByRole('region', { name: 'Histórico do caso' })).toContainText(justificativa)
})
