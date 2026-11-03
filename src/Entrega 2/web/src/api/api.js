// Cliente único da API do ASA Turbo (contrato: docs/api-contract.yaml, v0.9.0).
// - Uma função por operationId do contrato.
// - Envia Authorization: Bearer <access_token> e um X-Request-ID gerado aqui.
// - Erros viram ErroApi com o `codigo` estável do contrato, mais dois do cliente:
//   'rede' (sem conexão) e 'timeout'.
// - 401: pede uma nova autenticação (diálogo de login por cima da tela atual, sem
//   perder o que foi digitado) e repete a chamada uma vez.
// - Modo mock (config.js): a mesma interface, respondida por src/api/mock/.
import { API_BASE, MODO_MOCK, TIMEOUT_MS } from '../config.js'

export class ErroApi extends Error {
  constructor({ codigo, mensagem, status = 0, requestId = null, detalhes = [], retryAfter = null }) {
    super(mensagem)
    this.name = 'ErroApi'
    this.codigo = codigo
    this.status = status
    this.requestId = requestId
    this.detalhes = detalhes
    this.retryAfter = retryAfter
  }
}

const MENSAGENS_PADRAO = {
  rede: 'Sem conexão com o servidor. Verifique sua internet e tente de novo.',
  timeout: 'O servidor demorou demais para responder. Tente de novo em instantes.',
  erro_interno: 'Algo deu errado do nosso lado. Tente de novo em instantes.',
  indisponivel: 'Serviço temporariamente indisponível. Tente de novo em instantes.',
  nao_autenticado: 'Sua sessão expirou. Entre novamente.',
  sem_permissao: 'Seu perfil não tem acesso a esta área.',
  nao_encontrado: 'Não encontramos esse registro.',
}

// ----------------------------------------------------------------- ganchos da sessão
// A sessão (src/auth/SessaoContext.jsx) registra como obter o token e o que fazer no 401.
let obterToken = async () => null
let aoExpirar = async () => { throw new Error('sem sessão') }

export function configurarSessao({ token, expirou }) {
  obterToken = token
  aoExpirar = expirou
}

function novoRequestId() {
  try { return crypto.randomUUID() } catch { return `req-${Date.now()}-${Math.random().toString(16).slice(2)}` }
}

function montarQuery(query) {
  if (!query) return ''
  const p = new URLSearchParams()
  for (const [chave, valor] of Object.entries(query)) {
    if (valor === undefined || valor === null || valor === '') continue
    if (Array.isArray(valor)) valor.forEach((v) => p.append(chave, v))
    else p.append(chave, String(valor))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function transporteHttp({ metodo, caminho, query, corpo, token, requestId, signal }) {
  const headers = { Accept: 'application/json', 'X-Request-ID': requestId }
  if (token) headers.Authorization = `Bearer ${token}`
  if (corpo !== undefined) headers['Content-Type'] = 'application/json'
  const resp = await fetch(API_BASE + caminho + montarQuery(query), {
    method: metodo,
    headers,
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
    signal,
  })
  let dados = null
  const texto = await resp.text()
  if (texto) {
    try { dados = JSON.parse(texto) } catch { dados = null }
  }
  return {
    status: resp.status,
    corpo: dados,
    requestId: resp.headers.get('X-Request-ID') || requestId,
    retryAfter: Number(resp.headers.get('Retry-After')) || null,
  }
}

let transporte = transporteHttp
let mockCarregado = null
async function obterTransporte() {
  if (!MODO_MOCK) return transporte
  // __COM_MOCK__ (vite.config.js) é constante de build: com VITE_API_MOCK=false o Rollup
  // remove este import e os dados fictícios nem entram no bundle de produção.
  if (!mockCarregado) {
    mockCarregado = __COM_MOCK__
      ? import('./mock/index.js').then((m) => m.transporteMock)
      : Promise.reject(new Error('modo mock indisponível neste build'))
  }
  return mockCarregado
}

async function requisitar(metodo, caminho, { query, corpo, signal: sinalExterno, jaRepetiu = false } = {}) {
  const requestId = novoRequestId()
  const controle = new AbortController()
  const timer = setTimeout(() => controle.abort('timeout'), TIMEOUT_MS)
  const abortarExterno = () => controle.abort('cancelado')
  sinalExterno?.addEventListener('abort', abortarExterno)

  let r
  try {
    const enviar = await obterTransporte()
    const token = await obterToken()
    r = await enviar({ metodo, caminho, query, corpo, token, requestId, signal: controle.signal })
  } catch (e) {
    if (sinalExterno?.aborted) throw e
    const codigo = controle.signal.aborted ? 'timeout' : 'rede'
    throw new ErroApi({ codigo, mensagem: MENSAGENS_PADRAO[codigo], requestId })
  } finally {
    clearTimeout(timer)
    sinalExterno?.removeEventListener('abort', abortarExterno)
  }

  if (r.status >= 200 && r.status < 300) return r.corpo

  const erro = r.corpo && typeof r.corpo === 'object' ? r.corpo : {}
  const codigo = erro.codigo || (r.status >= 500 ? 'erro_interno' : 'requisicao_invalida')

  if (r.status === 401 && !jaRepetiu) {
    // Espera o usuário entrar de novo (diálogo por cima da tela) e repete uma vez.
    await aoExpirar()
    return requisitar(metodo, caminho, { query, corpo, signal: sinalExterno, jaRepetiu: true })
  }

  throw new ErroApi({
    codigo,
    mensagem: erro.mensagem || MENSAGENS_PADRAO[codigo] || MENSAGENS_PADRAO.erro_interno,
    status: r.status,
    requestId: erro.request_id || r.requestId,
    detalhes: erro.detalhes || [],
    retryAfter: r.retryAfter,
  })
}

// --------------------------------------------------------------------- operações
const id = (v) => encodeURIComponent(v)

export const api = {
  // Sessão
  me: (opts) => requisitar('GET', '/me', opts),

  // Chat (estudante)
  enviarMensagem: (corpo, opts) => requisitar('POST', '/chat', { ...opts, corpo }),
  listarConversas: (query, opts) => requisitar('GET', '/chat/conversas', { ...opts, query }),
  obterConversa: (conversaId, opts) => requisitar('GET', `/chat/conversas/${id(conversaId)}`, opts),
  enviarFeedback: (corpo, opts) => requisitar('POST', '/chat/feedback', { ...opts, corpo }),

  // Casos (atendente, administrador)
  listarCasos: (query, opts) => requisitar('GET', '/casos', { ...opts, query }),
  obterCaso: (estudanteId, opts) => requisitar('GET', `/casos/${id(estudanteId)}`, opts),
  validarCaso: (estudanteId, corpo, opts) => requisitar('POST', `/casos/${id(estudanteId)}/validacao`, { ...opts, corpo }),
  historicoCaso: (estudanteId, query, opts) => requisitar('GET', `/casos/${id(estudanteId)}/historico`, { ...opts, query }),

  // Risco
  modeloRisco: (opts) => requisitar('GET', '/risco/modelo', opts),
  inferirRisco: (corpo, opts) => requisitar('POST', '/risco/inferir', { ...opts, corpo }),

  // Admin
  dashboard: (query, opts) => requisitar('GET', '/admin/dashboard', { ...opts, query }),
  listarDocumentos: (query, opts) => requisitar('GET', '/admin/documentos', { ...opts, query }),
  cadastrarDocumento: (corpo, opts) => requisitar('POST', '/admin/documentos', { ...opts, corpo }),
  obterDocumento: (documentoId, opts) => requisitar('GET', `/admin/documentos/${id(documentoId)}`, opts),
  novaVersaoDocumento: (documentoId, corpo, opts) => requisitar('POST', `/admin/documentos/${id(documentoId)}/versoes`, { ...opts, corpo }),
  desativarDocumento: (documentoId, corpo, opts) => requisitar('POST', `/admin/documentos/${id(documentoId)}/desativar`, { ...opts, corpo }),
}

// Mensagem de um campo específico (erro 422 com `detalhes`).
export function erroDoCampo(erro, campo) {
  return erro?.detalhes?.find((d) => d.campo === campo)?.mensagem ?? null
}

// Só para testes: troca o transporte HTTP.
export function _usarTransporte(fn) { transporte = fn }
