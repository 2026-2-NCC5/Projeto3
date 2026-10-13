// Única porta de entrada do frontend para a API do ASA.
// Contrato (não alterar): POST { pergunta } -> { resposta, confianca, abstencao, evidencias[] }
// Toda resposta é normalizada para:
//   { tipo: 'resposta' | 'abstencao', texto, confianca, evidencias[] }
//   { tipo: 'erro', motivo: 'rede' | 'timeout' | 'servidor' | 'resposta_invalida', detalhe }
import { fetchMock, modoMockAtivo } from './mock.js'

const API_URL = import.meta.env.VITE_API_URL || '/api/perguntar'
const TIMEOUT_MS = 20000 // a API pode esperar até 10 s pela Hugging Face, mais a consulta ao banco

export async function perguntar(pergunta) {
  const fazerFetch = modoMockAtivo() ? fetchMock : fetch
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const resp = await fazerFetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pergunta }),
      signal: controller.signal,
    })

    let dados
    try {
      dados = await resp.json()
    } catch {
      return erro('resposta_invalida', `HTTP ${resp.status}: corpo não é JSON`)
    }

    if (!resp.ok) return erro('servidor', `HTTP ${resp.status}: ${dados?.resposta ?? ''}`)
    return normalizar(dados)
  } catch (e) {
    if (e.name === 'AbortError') return erro('timeout', `Sem resposta em ${TIMEOUT_MS / 1000} s`)
    return erro('rede', e.message)
  } finally {
    clearTimeout(timer)
  }
}

export function normalizar(dados) {
  if (!dados || typeof dados.resposta !== 'string') {
    return erro('resposta_invalida', 'Campo "resposta" ausente')
  }
  // O backend devolve falhas internas como HTTP 200 com texto "[DEBUG] ..."
  if (dados.resposta.startsWith('[DEBUG]')) return erro('servidor', dados.resposta)

  const evidencias = Array.isArray(dados.evidencias)
    ? dados.evidencias.map((ev) => ({
        titulo: ev?.titulo ?? 'Documento sem título',
        fonte: ev?.fonte ?? '',
        similaridade: Number(ev?.similaridade) || 0,
        atualizadoEm: ev?.atualizado_em ?? null,
        trecho: ev?.trecho ?? '',
      }))
    : []

  return {
    tipo: dados.abstencao ? 'abstencao' : 'resposta',
    texto: dados.resposta,
    confianca: Number(dados.confianca) || 0,
    evidencias,
  }
}

function erro(motivo, detalhe) {
  if (import.meta.env.DEV) console.warn(`[ASA] erro na API (${motivo}):`, detalhe)
  return { tipo: 'erro', motivo, detalhe }
}
