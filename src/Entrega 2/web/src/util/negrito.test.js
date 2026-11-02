import { test } from 'node:test'
import assert from 'node:assert/strict'
import { dividirNegrito, removerNegrito } from './negrito.js'

test('texto puro não vira negrito', () => {
  assert.deepEqual(dividirNegrito('sem marcação'), [{ texto: 'sem marcação', negrito: false }])
})

test('separa trechos em negrito', () => {
  assert.deepEqual(dividirNegrito('na aba **Documentos**, opção **Declarações**.'), [
    { texto: 'na aba ', negrito: false },
    { texto: 'Documentos', negrito: true },
    { texto: ', opção ', negrito: false },
    { texto: 'Declarações', negrito: true },
    { texto: '.', negrito: false },
  ])
})

test('marcação sem fechamento fica literal', () => {
  assert.deepEqual(dividirNegrito('aberto **sem fim'), [{ texto: 'aberto **sem fim', negrito: false }])
})

test('não atravessa linhas nem aceita negrito vazio', () => {
  assert.deepEqual(dividirNegrito('a **b\nc** d'), [{ texto: 'a **b\nc** d', negrito: false }])
  assert.deepEqual(dividirNegrito('****'), [{ texto: '****', negrito: false }])
})

test('removerNegrito tira só a marcação', () => {
  assert.equal(removerNegrito('aba **Documentos** e **PDF**'), 'aba Documentos e PDF')
  assert.equal(removerNegrito('sem nada'), 'sem nada')
})
