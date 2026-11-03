import { expect } from '@playwright/test'

export const SENHA = process.env.DEMO_PASSWORD || 'AsaTurbo#Demo2026'

export async function entrar(page, papel) {
  await page.goto('/entrar')
  await page.getByLabel('E-mail').fill(`${papel}.demo@example.com`)
  await page.getByLabel('Senha', { exact: true }).fill(SENHA)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/entrar/)
}

export const marca = () => new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
