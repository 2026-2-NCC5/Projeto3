// Transporte MOCK: responde às rotas do contrato (docs/api-contract.yaml) em memória.
// Mesma assinatura do transporte HTTP de api.js: recebe {metodo, caminho, query, corpo, token}
// e devolve {status, corpo, requestId}. Erros seguem o schema `Erro` do contrato.
//
// Cenários para testar no chat (palavras na pergunta):
//   "lento" -> demora 8 s      "erro" -> falha de rede      "limite" -> 429
//   tema fora da base          -> abstenção com encaminhamento
// Sessão: window.asaMock.expirarSessao() faz a próxima chamada responder 401.
import {
  AVISO_SCORE, CALCULADO_EM, COMPETENCIAS, DOCUMENTOS, PRIORIDADE_ORDEM, USUARIOS, VERSAO_MODELO, VERSAO_RAG,
  conversasDemo, estudantes, eventoValidacao, recomendar, rotuloCategoria, uuid,
} from './dados.js'
import { lerTokenMock } from './token.js'

const PAPEIS = {
  '/me': ['estudante', 'atendente', 'administrador', 'equipe_tecnica'],
  '/chat': ['estudante'],
  '/casos': ['atendente', 'administrador'],
  '/risco/modelo': ['atendente', 'administrador', 'equipe_tecnica'],
  '/risco/inferir': ['administrador', 'equipe_tecnica'],
  '/admin': ['administrador'],
}

let forcarExpiracao = false
if (typeof window !== 'undefined') {
  window.asaMock = {
    expirarSessao() { forcarExpiracao = true; return 'A próxima chamada à API vai responder 401.' },
  }
}

const esperar = (ms, signal) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms)
  signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('Aborted', 'AbortError')) })
})

function erro(status, codigo, mensagem, requestId, detalhes) {
  return { status, requestId, corpo: { codigo, mensagem, request_id: requestId, ...(detalhes ? { detalhes } : {}) } }
}
const ok = (corpo, status = 200) => ({ status, corpo })

function paginar(itens, query) {
  const pagina = Math.max(1, Number(query?.pagina) || 1)
  const porPagina = Math.min(100, Math.max(1, Number(query?.por_pagina) || 25))
  return { total: itens.length, pagina, por_pagina: porPagina, itens: itens.slice((pagina - 1) * porPagina, pagina * porPagina) }
}

const lista = (v) => (v === undefined || v === null || v === '' ? [] : Array.isArray(v) ? v : [v])
const semAcento = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

// ======================================================================= transporte
export async function transporteMock({ metodo, caminho, query = {}, corpo, token, requestId, signal }) {
  await esperar(250 + Math.random() * 350, signal)
  const r = await responder({ metodo, caminho, query, corpo, token, requestId, signal })
  return { retryAfter: null, ...r, requestId }
}

async function responder({ metodo, caminho, query, corpo, token, requestId, signal }) {
  // ---------------------------------------------------------------- autenticação
  const sessao = lerTokenMock(token)
  if (!sessao || forcarExpiracao) {
    forcarExpiracao = false
    return erro(401, 'nao_autenticado', 'Sua sessão expirou. Entre novamente.', requestId)
  }
  const usuario = USUARIOS[sessao.papel]
  const prefixo = Object.keys(PAPEIS).filter((p) => caminho === p || caminho.startsWith(p + '/')).sort((a, b) => b.length - a.length)[0]
  if (prefixo && !PAPEIS[prefixo].includes(usuario.papel)) {
    return erro(403, 'sem_permissao', 'Seu perfil não tem acesso a esta área.', requestId)
  }

  const partes = caminho.split('/').filter(Boolean)
  const rota = `${metodo} /${partes.map((p, i) => (i > 0 && /^[0-9a-z]{8}-/.test(p) ? ':id' : p)).join('/')}`

  switch (rota) {
    case 'GET /me': return ok(usuario)

    // --------------------------------------------------------------------- chat
    case 'POST /chat': return chat(corpo, requestId, signal)
    case 'GET /chat/conversas': {
      const itens = [...conversasDemo]
        .sort((a, b) => b.atualizada_em.localeCompare(a.atualizada_em))
        .map(({ mensagens, encaminhamento, ...c }) => ({ ...c, ultima_mensagem: (mensagens.at(-1)?.conteudo ?? '').slice(0, 140) }))
      return ok(paginar(itens, query))
    }
    case 'GET /chat/conversas/:id': {
      const c = conversasDemo.find((x) => x.id === partes[2])
      return c ? ok(structuredClone(c)) : erro(404, 'nao_encontrado', 'Não encontramos essa conversa.', requestId)
    }
    case 'POST /chat/feedback': {
      if (!corpo?.resposta_id || !['util', 'nao_util'].includes(corpo.avaliacao)) {
        return erro(422, 'validacao', 'Revise os campos destacados.', requestId, [{ campo: 'avaliacao', mensagem: 'Escolha útil ou não útil.' }])
      }
      for (const c of conversasDemo) for (const m of c.mensagens) if (m.resposta?.resposta_id === corpo.resposta_id) m.resposta.feedback = corpo.avaliacao
      return ok({ id: uuid('fb'), resposta_id: corpo.resposta_id, avaliacao: corpo.avaliacao, comentario: corpo.comentario ?? null, criado_em: new Date().toISOString() }, 201)
    }

    // -------------------------------------------------------------------- casos
    case 'GET /casos': return ok(listarCasos(query, usuario))
    case 'GET /casos/:id': {
      const e = estudantes.find((x) => x.estudante.id === partes[1])
      return e ? ok(detalheCaso(e)) : erro(404, 'nao_encontrado', 'Não encontramos esse estudante.', requestId)
    }
    case 'POST /casos/:id/validacao': return validar(partes[1], corpo, usuario, requestId)
    case 'GET /casos/:id/historico': {
      const e = estudantes.find((x) => x.estudante.id === partes[1])
      if (!e) return erro(404, 'nao_encontrado', 'Não encontramos esse estudante.', requestId)
      const itens = [...e.eventos].sort((a, b) => new Date(b.ocorrido_em) - new Date(a.ocorrido_em))
      return ok(paginar(itens, query))
    }

    // -------------------------------------------------------------------- risco
    case 'GET /risco/modelo': return ok({
      versao: VERSAO_MODELO, algoritmo: 'Fórmula sintética de demonstração (substitui a Regressão Logística no mock)', treinado_em: '2026-10-31T12:00:00-03:00',
      limiares: { amarelo: 0.3, vermelho: 0.6 }, metricas: { auc: 0.82, recall: 0.77, precisao: 0.61, f1: 0.68 },
      features: ['pct_parcelas_em_aberto', 'atraso_medio_dias', 'pct_parcelas_acordo', 'tem_bolsa', 'media_notas', 'media_assiduidade', 'pct_reprovacao', 'tendencia_notas', 'total_semestres', 'dias_desde_ultimo_contato'],
    })

    // -------------------------------------------------------------------- admin
    case 'GET /admin/dashboard': return ok(dashboard(query))
    case 'GET /admin/documentos': {
      let docs = DOCUMENTOS
      if (query.busca) docs = docs.filter((d) => semAcento(d.titulo).includes(semAcento(query.busca)))
      if (query.categoria) docs = docs.filter((d) => d.categoria === query.categoria)
      if (query.ativo === 'true' || query.ativo === true) docs = docs.filter((d) => d.ativo)
      if (query.ativo === 'false' || query.ativo === false) docs = docs.filter((d) => !d.ativo)
      docs = [...docs].sort((a, b) => a.titulo.localeCompare(b.titulo, 'pt-BR'))
      return ok(paginar(docs.map(resumoDocumento), query))
    }
    case 'POST /admin/documentos': {
      const det = validarDocumento(corpo, true)
      if (det.length) return erro(422, 'validacao', 'Revise os campos destacados.', requestId, det)
      const agora = new Date().toISOString()
      const doc = { id: uuid('d0c'), titulo: corpo.titulo.trim(), categoria: corpo.categoria.trim(), fonte: corpo.fonte.trim(), conteudo: corpo.conteudo,
        data_atualizacao: corpo.data_atualizacao || agora, versao: 1, ativo: true, chaves: [], resposta: null, trecho: '', desativado_em: null, motivo_desativacao: null,
        versoes: [{ versao: 1, data_atualizacao: corpo.data_atualizacao || agora, motivo: null, alterado_por: usuario.nome, criado_em: agora }] }
      DOCUMENTOS.push(doc)
      return ok(detalheDocumento(doc), 201)
    }
    case 'GET /admin/documentos/:id': {
      const doc = DOCUMENTOS.find((d) => d.id === partes[2])
      return doc ? ok(detalheDocumento(doc)) : erro(404, 'nao_encontrado', 'Não encontramos esse documento.', requestId)
    }
    case 'POST /admin/documentos/:id/versoes': {
      const doc = DOCUMENTOS.find((d) => d.id === partes[2])
      if (!doc) return erro(404, 'nao_encontrado', 'Não encontramos esse documento.', requestId)
      if (corpo?.versao_base !== doc.versao) return erro(409, 'conflito', 'Outra pessoa publicou uma versão enquanto você editava. Recarregue para ver a versão nova.', requestId)
      const det = validarDocumento(corpo, false)
      if (!corpo?.motivo || corpo.motivo.trim().length < 10) det.push({ campo: 'motivo', mensagem: 'Explique a mudança em pelo menos 10 caracteres.' })
      if (det.length) return erro(422, 'validacao', 'Revise os campos destacados.', requestId, det)
      const agora = new Date().toISOString()
      Object.assign(doc, {
        titulo: corpo.titulo?.trim() || doc.titulo, categoria: corpo.categoria?.trim() || doc.categoria, fonte: corpo.fonte?.trim() || doc.fonte,
        conteudo: corpo.conteudo, versao: doc.versao + 1, data_atualizacao: corpo.data_atualizacao || agora,
      })
      doc.versoes.unshift({ versao: doc.versao, data_atualizacao: doc.data_atualizacao, motivo: corpo.motivo.trim(), alterado_por: usuario.nome, criado_em: agora })
      return ok(detalheDocumento(doc), 201)
    }
    case 'POST /admin/documentos/:id/desativar': {
      const doc = DOCUMENTOS.find((d) => d.id === partes[2])
      if (!doc) return erro(404, 'nao_encontrado', 'Não encontramos esse documento.', requestId)
      if (!doc.ativo) return erro(409, 'conflito', 'Este documento já estava desativado.', requestId)
      if (!corpo?.motivo || corpo.motivo.trim().length < 10) return erro(422, 'validacao', 'Revise os campos destacados.', requestId, [{ campo: 'motivo', mensagem: 'Explique o motivo em pelo menos 10 caracteres.' }])
      Object.assign(doc, { ativo: false, desativado_em: new Date().toISOString(), motivo_desativacao: corpo.motivo.trim() })
      return ok(detalheDocumento(doc))
    }
    default:
      return erro(404, 'nao_encontrado', `Rota não existe no mock: ${rota}`, requestId)
  }
}

// ======================================================================= chat
const ABSTENCAO = 'Não encontrei isso nos documentos oficiais. Quer que eu encaminhe para o ASA?'

async function chat(corpo, requestId, signal) {
  const mensagem = (corpo?.mensagem ?? '').trim()
  if (!mensagem) return erro(422, 'validacao', 'Escreva uma pergunta.', requestId, [{ campo: 'mensagem', mensagem: 'Escreva uma pergunta.' }])
  if (mensagem.length > 1000) return erro(422, 'validacao', 'A pergunta pode ter até 1.000 caracteres.', requestId, [{ campo: 'mensagem', mensagem: 'Use até 1.000 caracteres.' }])
  if (Array.isArray(corpo.historico) && corpo.historico.length > 6) return erro(422, 'validacao', 'Histórico maior que 6 mensagens.', requestId)

  const p = semAcento(mensagem)
  if (p.includes('limite')) return { ...erro(429, 'limite_excedido', 'Muitas mensagens em pouco tempo. Aguarde alguns segundos.', requestId), retryAfter: 10 }
  if (p.includes('erro')) throw new TypeError('Failed to fetch (simulado)')
  await esperar(p.includes('lento') ? 8000 : 700 + Math.random() * 900, signal)

  // Pergunta curta de continuação ("e o prazo?") usa o histórico para achar o tema.
  const contexto = semAcento([mensagem, ...(corpo.historico ?? []).filter((h) => h.papel === 'estudante').map((h) => h.conteudo).slice(-2)].join(' '))
  const encontrado = DOCUMENTOS.find((d) => d.ativo && d.resposta && d.chaves.some((c) => p.includes(semAcento(c))))
    ?? (mensagem.split(/\s+/).length <= 4 ? DOCUMENTOS.find((d) => d.ativo && d.resposta && d.chaves.some((c) => contexto.includes(semAcento(c)))) : null)

  let conversa = conversasDemo.find((c) => c.id === corpo.conversa_id)
  if (corpo.conversa_id && !conversa) return erro(404, 'nao_encontrado', 'Não encontramos essa conversa.', requestId)
  const agora = new Date().toISOString()
  if (!conversa) {
    conversa = { id: uuid('c0'), titulo: mensagem.length > 48 ? mensagem.slice(0, 48).trimEnd() + '…' : mensagem, status: 'aberta', iniciada_em: agora, atualizada_em: agora, encaminhamento: null, mensagens: [] }
    conversasDemo.unshift(conversa)
  }

  const respostaId = uuid('r0')
  let resposta
  if (encontrado) {
    const sim = 0.68 + Math.random() * 0.15
    resposta = {
      resposta: encontrado.resposta,
      fontes: [{ documento_id: encontrado.id, titulo: encontrado.titulo, fonte: encontrado.fonte, data_atualizacao: encontrado.data_atualizacao, trecho: encontrado.trecho, similaridade: Math.round(sim * 10000) / 10000 }],
      confianca: Math.round(sim * 10000) / 10000, abstencao: false, motivo_abstencao: null, encaminhamento: null,
    }
  } else {
    const enc = { id: uuid('f0'), status: 'aberto', setor_destino: 'ASA', prazo: new Date(Date.now() + 2 * 86400000).toISOString() }
    conversa.encaminhamento = enc
    conversa.status = 'encaminhada_humano'
    resposta = { resposta: ABSTENCAO, fontes: [], confianca: 0.31, abstencao: true, motivo_abstencao: 'baixa_similaridade', encaminhamento: enc }
  }
  conversa.atualizada_em = agora
  conversa.mensagens.push(
    { id: uuid('m'), remetente: 'estudante', conteudo: mensagem, criado_em: agora, resposta: null },
    { id: uuid('m'), remetente: 'agente', conteudo: resposta.resposta, criado_em: agora,
      resposta: { resposta_id: respostaId, fontes: resposta.fontes, confianca: resposta.confianca, abstencao: resposta.abstencao, feedback: null } },
  )
  return ok({ ...resposta, resposta_id: respostaId, conversa_id: conversa.id, versao_modelo: VERSAO_RAG, gerada_em: agora })
}

// ======================================================================= casos
function tendencia(variacao) {
  if (variacao > 0.02) return 'subindo'
  if (variacao < -0.02) return 'caindo'
  return 'estavel'
}

function resumoCaso(e) {
  const atual = e.serie.at(-1)
  return {
    estudante: e.estudante, caso_id: e.caso?.id ?? null, score_geral: atual.score.geral,
    categoria: e.categoriaVigente, categoria_modelo: atual.categoria, tendencia: tendencia(e.variacao), variacao: e.variacao,
    status: e.caso?.status ?? null, prioridade: e.caso?.prioridade ?? null, prazo: e.caso?.prazo ?? null, responsavel: e.caso?.responsavel ?? null,
    ultima_decisao: e.validacoes.at(-1)?.decisao ?? null, versao_modelo: VERSAO_MODELO, atualizado_em: CALCULADO_EM,
  }
}

function listarCasos(query, usuario) {
  let itens = estudantes
  const status = lista(query.status)
  const prioridades = lista(query.prioridade)
  if (status.length) itens = itens.filter((e) => status.includes(e.caso?.status))
  if (prioridades.length) itens = itens.filter((e) => prioridades.includes(e.caso?.prioridade))
  if (query.responsavel === 'eu') itens = itens.filter((e) => e.caso?.responsavel?.id === usuario.id)
  if (query.responsavel === 'nenhum') itens = itens.filter((e) => e.caso && !e.caso.responsavel)
  if (query.busca) {
    const b = semAcento(String(query.busca).trim())
    itens = itens.filter((e) => e.estudante.ra.includes(b) || semAcento(e.estudante.nome).includes(b))
  }
  const contagem = { verde: 0, amarelo: 0, vermelho: 0 }
  for (const e of itens) contagem[e.categoriaVigente] += 1
  const categorias = lista(query.categoria)
  if (categorias.length) itens = itens.filter((e) => categorias.includes(e.categoriaVigente))

  const score = (e) => e.serie.at(-1).score.geral
  const ordens = {
    prioridade: (a, b) => (PRIORIDADE_ORDEM[a.caso?.prioridade] ?? 9) - (PRIORIDADE_ORDEM[b.caso?.prioridade] ?? 9) || score(b) - score(a),
    '-score': (a, b) => score(b) - score(a),
    score: (a, b) => score(a) - score(b),
    prazo: (a, b) => (a.caso?.prazo ?? '9999').localeCompare(b.caso?.prazo ?? '9999') || score(b) - score(a),
    '-variacao': (a, b) => b.variacao - a.variacao,
    nome: (a, b) => a.estudante.nome.localeCompare(b.estudante.nome, 'pt-BR'),
  }
  itens = [...itens].sort(ordens[query.ordenar] ?? ordens.prioridade)
  return { ...paginar(itens.map(resumoCaso), query), contagem }
}

function detalheCaso(e) {
  const atual = e.serie.at(-1)
  return {
    estudante: e.estudante, score_id: atual.score_id, score: atual.score, categoria: e.categoriaVigente, categoria_modelo: atual.categoria,
    fatores: atual.fatores,
    tendencia: e.serie.map((s) => ({ competencia: s.competencia, score_geral: s.score.geral, categoria: s.categoria })),
    recomendacao: recomendar(atual.categoria, atual.fatores),
    caso: e.caso ? { ...e.caso } : { id: null, status: 'novo', prioridade: 'baixa', prazo: null, responsavel: null },
    ultima_validacao: e.validacoes.at(-1) ?? null, versao_modelo: VERSAO_MODELO, atualizado_em: CALCULADO_EM, aviso: AVISO_SCORE,
  }
}

function validar(estudanteId, corpo, usuario, requestId) {
  const e = estudantes.find((x) => x.estudante.id === estudanteId)
  if (!e) return erro(404, 'nao_encontrado', 'Não encontramos esse estudante.', requestId)
  const det = []
  if (!['confirmado', 'ajustado', 'rejeitado'].includes(corpo?.decisao)) det.push({ campo: 'decisao', mensagem: 'Escolha confirmar, ajustar ou rejeitar.' })
  if (!corpo?.justificativa || corpo.justificativa.trim().length < 20) det.push({ campo: 'justificativa', mensagem: 'Escreva pelo menos 20 caracteres.' })
  if (corpo?.decisao === 'ajustado' && !['verde', 'amarelo', 'vermelho'].includes(corpo.categoria_ajustada)) det.push({ campo: 'categoria_ajustada', mensagem: 'Escolha a nova categoria.' })
  if (det.length) return erro(422, 'validacao', 'Revise os campos destacados.', requestId, det)
  if (corpo.score_id !== e.serie.at(-1).score_id) return erro(409, 'conflito', 'O score foi atualizado enquanto você analisava. Recarregue para ver a versão nova.', requestId)

  const atendente = { id: usuario.id, nome: usuario.nome }
  const agora = new Date().toISOString()
  if (!e.caso) e.caso = { id: uuid('ca50'), status: 'novo', prioridade: 'baixa', prazo: null, responsavel: null }
  const antes = { ...e.caso }
  const v = {
    id: uuid('va1d'), score_id: corpo.score_id, decisao: corpo.decisao, justificativa: corpo.justificativa.trim(),
    categoria_ajustada: corpo.decisao === 'ajustado' ? corpo.categoria_ajustada : null,
    prioridade: corpo.prioridade ?? null, prazo: corpo.prazo ?? null, atendente, versao_modelo: VERSAO_MODELO, criado_em: agora,
  }
  e.validacoes.push(v)
  e.eventos.push(eventoValidacao(v))
  if (v.decisao === 'ajustado') e.categoriaVigente = v.categoria_ajustada
  if (v.decisao === 'confirmado') e.categoriaVigente = e.serie.at(-1).categoria
  if (corpo.prioridade) e.caso.prioridade = corpo.prioridade
  if (corpo.prazo !== undefined && corpo.prazo !== null) e.caso.prazo = corpo.prazo
  e.caso.status = corpo.status ?? (v.decisao === 'rejeitado' ? 'arquivado' : e.caso.status === 'novo' ? 'em_acompanhamento' : e.caso.status)
  if (corpo.assumir_caso !== false) e.caso.responsavel = atendente
  const mudancas = [
    ['status', 'Status'], ['prioridade', 'Prioridade'], ['prazo', 'Prazo'],
  ]
  for (const [campo, rotulo] of mudancas) {
    if (antes[campo] !== e.caso[campo]) {
      e.eventos.push({ id: uuid('ev'), tipo: campo, ocorrido_em: agora, descricao: `${rotulo} alterado`, usuario: atendente, dados: { de: antes[campo], para: e.caso[campo] } })
    }
  }
  if (antes.responsavel?.id !== e.caso.responsavel?.id) {
    e.eventos.push({ id: uuid('ev'), tipo: 'responsavel', ocorrido_em: agora, descricao: `${atendente.nome} assumiu o caso`, usuario: atendente, dados: { de: antes.responsavel?.nome ?? null, para: atendente.nome } })
  }
  return ok(v, 201)
}

// ======================================================================= admin
function dashboard(query) {
  const ate = query.ate || '2026-11-01'
  const de = query.de || '2026-10-03'
  const dias = Math.max(1, Math.round((new Date(ate) - new Date(de)) / 86400000) + 1)
  const porDia = []
  for (let i = 0; i < dias; i++) {
    const d = new Date(new Date(de + 'T12:00:00Z').getTime() + i * 86400000)
    const semana = d.getUTCDay()
    const base = semana === 0 ? 6 : semana === 6 ? 14 : 38 + ((i * 7) % 17)
    const total = base + ((i * 13) % 9)
    porDia.push({ dia: d.toISOString().slice(0, 10), total, abstencoes: Math.round(total * (0.12 + ((i * 5) % 7) / 100)) })
  }
  const perguntas = porDia.reduce((s, x) => s + x.total, 0)
  const abst = porDia.reduce((s, x) => s + x.abstencoes, 0)
  const dist = { verde: 0, amarelo: 0, vermelho: 0 }
  const mensal = COMPETENCIAS.map((c) => ({ competencia: c, verde: 0, amarelo: 0, vermelho: 0 }))
  const porStatus = {}
  let validacoes = { confirmado: 0, ajustado: 0, rejeitado: 0 }
  for (const e of estudantes) {
    dist[e.categoriaVigente] += 1
    e.serie.forEach((s, i) => { mensal[i][s.categoria] += 1 })
    if (e.caso) porStatus[e.caso.status] = (porStatus[e.caso.status] ?? 0) + 1
    for (const v of e.validacoes) validacoes[v.decisao] += 1
  }
  validacoes = { ...validacoes, tempo_medio_ate_validacao_horas: 31.5 }
  return {
    periodo: { de, ate },
    chat: {
      conversas: Math.round(perguntas / 2.3), perguntas, estudantes_ativos: Math.round(perguntas / 3.1),
      taxa_abstencao: Math.round((abst / perguntas) * 1000) / 1000, confianca_media: 0.71, latencia_p95_ms: 2380,
      feedback: { util: Math.round(perguntas * 0.21), nao_util: Math.round(perguntas * 0.05) },
      perguntas_por_dia: porDia,
      principais_documentos: [
        ['Rematrícula', 88], ['Atestado de matrícula', 74], ['FIES – Aditamento para Renovação', 51], ['Trancamento de Matrícula', 46],
        ['Abono ou Compensação de Faltas', 39], ['Trabalho de Conclusão de Curso (TCC)', 27], ['Reprovação por Frequência', 22],
      ].map(([titulo, n]) => ({ documento_id: DOCUMENTOS.find((d) => d.titulo === titulo)?.id, titulo, citacoes: Math.round((n * dias) / 30) })),
    },
    risco: { distribuicao: dist, distribuicao_mensal: mensal, casos_por_status: porStatus, versao_modelo: VERSAO_MODELO },
    validacoes,
    encaminhamentos: { abertos: Math.round(abst * 0.3), em_andamento: Math.round(abst * 0.2), resolvidos: Math.round(abst * 0.45) },
    atualizado_em: new Date().toISOString(),
  }
}

function contarChunks(doc) { return Math.max(1, Math.ceil(doc.conteudo.length / 400)) }
function resumoDocumento(d) {
  return { id: d.id, titulo: d.titulo, categoria: d.categoria, fonte: d.fonte, versao: d.versao, ativo: d.ativo, data_atualizacao: d.data_atualizacao, total_chunks: contarChunks(d), chunks_sem_embedding: 0 }
}
function detalheDocumento(d) {
  return { ...resumoDocumento(d), conteudo: d.conteudo, desativado_em: d.desativado_em, motivo_desativacao: d.motivo_desativacao, versoes: d.versoes.map((v) => ({ ...v })) }
}
function validarDocumento(c, novo) {
  const det = []
  if (novo || c?.titulo !== undefined) if (!c?.titulo || c.titulo.trim().length < 3) det.push({ campo: 'titulo', mensagem: 'Use pelo menos 3 caracteres.' })
  if (novo) {
    if (!c?.categoria || c.categoria.trim().length < 2) det.push({ campo: 'categoria', mensagem: 'Informe a categoria.' })
    if (!c?.fonte || c.fonte.trim().length < 3) det.push({ campo: 'fonte', mensagem: 'Informe a referência oficial.' })
  }
  if (!c?.conteudo || c.conteudo.trim().length < 20) det.push({ campo: 'conteudo', mensagem: 'O conteúdo precisa ter pelo menos 20 caracteres.' })
  return det
}

export { rotuloCategoria }
