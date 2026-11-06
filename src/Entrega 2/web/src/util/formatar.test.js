import { test } from 'node:test'
import assert from 'node:assert/strict'
import { iniciais } from './formatar.js'

test('iniciais ignoram palavras que não começam com letra', () => {
  assert.equal(iniciais('Júlia Prado (demo)'), 'JP')
  assert.equal(iniciais('Marcos Lima'), 'ML')
  assert.equal(iniciais('Renata'), 'R')
  assert.equal(iniciais(''), '')
})
