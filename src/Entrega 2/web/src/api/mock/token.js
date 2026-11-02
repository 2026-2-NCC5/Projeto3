// Token do modo mock: "mock.<papel>.<expira_em_ms>". Não é JWT e não vale fora do mock.
export const DURACAO_TOKEN_MOCK_MS = 60 * 60 * 1000

export function criarTokenMock(papel) {
  return `mock.${papel}.${Date.now() + DURACAO_TOKEN_MOCK_MS}`
}

export function lerTokenMock(token) {
  if (!token || !token.startsWith('mock.')) return null
  const [, papel, exp] = token.split('.')
  if (!papel || Number(exp) < Date.now()) return null
  return { papel, expiraEm: Number(exp) }
}
