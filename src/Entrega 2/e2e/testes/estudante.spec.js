import { test, expect } from '@playwright/test'
import { entrar } from './apoio.js'

test('estudante: pergunta, vê fonte e data, avalia, recebe abstenção e acha a conversa no histórico', async ({ page }) => {
  await entrar(page, 'estudante')
  await expect(page).toHaveURL(/\/chat/)
  await expect(page).toHaveTitle(/ASA Turbo/)

  // 1. Pergunta dentro da base: resposta com fonte e data de atualização
  await page.getByLabel('Sua pergunta').fill('Como tiro o atestado de matrícula?')
  await page.getByRole('button', { name: 'Enviar pergunta' }).click()
  const mensagens = page.getByRole('log', { name: 'Mensagens' })
  const resposta = mensagens.locator('li').filter({ has: page.getByText(/^Fontes?$/) }).last()
  await expect(resposta).toBeVisible({ timeout: 25_000 })
  await expect(resposta.getByText('Atestado de matrícula').first()).toBeVisible()
  await expect(resposta.getByText(/atualizado em \d{2}\/\d{2}\/\d{4}/).first()).toBeVisible()

  // 2. Feedback útil
  await resposta.getByRole('button', { name: 'Útil', exact: true }).click()
  await expect(resposta.getByRole('button', { name: 'Útil', exact: true })).toHaveAttribute('aria-pressed', 'true')
  // depois do voto o app oferece um comentário opcional (com foco); recusamos
  await resposta.getByRole('button', { name: 'Agora não' }).click()
  await expect(resposta.getByRole('status')).toContainText('Obrigado')

  // 3. Fora do escopo: abstenção com encaminhamento ao ASA
  await page.locator('#campo-pergunta').fill('Qual a receita de bolo de cenoura?')
  await page.getByRole('button', { name: 'Enviar pergunta' }).click()
  const abst = mensagens.locator('li').filter({ hasText: 'Não encontrei isso nos documentos oficiais' }).last()
  await expect(abst).toBeVisible({ timeout: 25_000 })
  await abst.getByRole('button', { name: 'Falar com o ASA' }).click()
  await expect(abst.getByRole('status')).toContainText('Pedido enviado ao ASA')
  await expect(abst.getByRole('status')).toContainText('Protocolo')

  // 4. A conversa aparece na lista de conversas anteriores
  const url = page.url()
  await page.goto('/chat')
  const lista = page.getByRole('navigation', { name: 'Conversas anteriores' })
  const link = lista.locator(`a[href="${new URL(url).pathname}"]`)
  await expect(link).toBeVisible()
  await link.click()
  await expect(page.getByRole('log', { name: 'Mensagens' })).toContainText('Como tiro o atestado de matrícula?')
  await expect(page.getByRole('log', { name: 'Mensagens' })).toContainText('receita de bolo')
})

test('estudante não acessa a fila de risco', async ({ page }) => {
  await entrar(page, 'estudante')
  await page.goto('/fila')
  await expect(page.getByRole('heading', { name: 'Seu perfil não tem acesso a esta área' })).toBeVisible()
  await expect(page).toHaveTitle('Sem acesso · ASA Turbo')
  await expect(page.getByRole('table')).toHaveCount(0)
  // e a API também recusa
  const status = await page.evaluate(async () => (await fetch('/api/casos')).status)
  expect([401, 403]).toContain(status)
})
