import { test, expect } from '@playwright/test'
import { entrar, marca } from './apoio.js'

test('admin: painel, cadastra documento, publica nova versão e desativa', async ({ page }) => {
  await entrar(page, 'admin')
  await expect(page).toHaveURL(/\/admin/)
  await expect(page).toHaveTitle('Painel · ASA Turbo')

  // Painel: distribuição de risco, abstenção e feedback
  await expect(page.getByRole('region', { name: /Distribuição atual/ })).toContainText('Vermelho')
  await expect(page.getByText('Taxa de abstenção')).toBeVisible()
  await expect(page.getByText('Avaliadas como úteis')).toBeVisible()

  // Base de conhecimento
  await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Base de conhecimento' }).click()
  await expect(page).toHaveTitle('Base de conhecimento · ASA Turbo')
  await expect(page.getByRole('table', { name: 'Documentos da base de conhecimento' }).locator('tbody tr').first()).toBeVisible()

  // Cadastrar
  const titulo = `Plantão de dúvidas de teste e2e ${marca()}`
  await page.getByRole('link', { name: 'Cadastrar documento' }).click()
  await page.getByLabel('Título').fill(titulo)
  await page.getByLabel('Categoria').selectOption({ index: 1 })
  await page.getByLabel('Referência oficial').fill('Documento de teste automatizado (e2e)')
  await page.getByLabel('Conteúdo').fill('Plantão de dúvidas de teste: 1) acesse o portal; 2) escolha Monitoria; 3) agende o horário.')
  await page.getByRole('button', { name: 'Cadastrar documento' }).click()
  await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Versões' })).toContainText('Versão 1')

  // Nova versão
  await page.getByRole('button', { name: 'Publicar nova versão' }).click()
  await page.getByLabel('Conteúdo').fill('Plantão de dúvidas de teste (revisado): 1) acesse o portal; 2) escolha Monitoria; 3) agende; 4) compareça.')
  await page.getByLabel('O que mudou').fill('Inclui o passo de comparecer ao plantão.')
  await page.getByRole('button', { name: 'Publicar versão' }).click()
  await expect(page.getByRole('region', { name: 'Versões' })).toContainText('Versão 2 (vigente)')

  // Desativar
  await page.getByRole('button', { name: 'Desativar documento' }).click()
  const dialogo = page.getByRole('dialog', { name: 'Desativar este documento?' })
  await dialogo.getByRole('textbox').fill('Documento de teste automatizado, não é oficial.')
  await dialogo.getByRole('button', { name: 'Desativar documento' }).click()
  await expect(page.getByRole('status').filter({ hasText: /desativado/i }).first()).toBeVisible()
})
