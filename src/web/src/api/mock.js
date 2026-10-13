// 🧪 MOCK: respostas SIMULADAS para desenvolver os estados visuais
// enquanto a busca do backend não devolve respostas reais.
//
// Como ativar: abra http://localhost:5173/?mock
// Para abrir direto na conversa com todos os estados: http://localhost:5173/?mock=galeria
// Só funciona em `npm run dev` (ou se VITE_ENABLE_MOCK=true no build).
//
// O mock imita a API no nível do fetch (devolve um Response com o MESMO JSON
// do contrato), então a resposta passa pela mesma normalização da API real.
// Textos e fontes copiados do seed_v2.sql (dados fictícios).
//
// Palavras-chave para forçar cenários:
//   "erro"  -> falha de rede          "debug" -> resposta [DEBUG] do servidor
//   "lento" -> demora 25 s (timeout)  sem tema conhecido -> abstenção
//   "formatação" -> texto de teste com parágrafos, lista e link (sem fontes)

export function modoMockAtivo() {
  const permitido = import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCK === 'true'
  return permitido && new URLSearchParams(window.location.search).has('mock')
}

const BASE = [
  {
    chaves: ['declara', 'comprovante de matr'],
    titulo: 'Declaração de Matrícula',
    fonte: 'Portal do Aluno - Central de Documentos',
    atualizado_em: '2026-07-03T00:00:00+00:00',
    trecho: 'A declaração de matrícula pode ser emitida na aba Documentos, opção Declarações, em formato PDF, com validade de 90 dias, sem custo.',
  },
  {
    chaves: ['rematr'],
    titulo: 'Rematrícula',
    fonte: 'Manual do Aluno - Seção 4.2',
    atualizado_em: '2026-08-12T00:00:00+00:00',
    trecho: 'A rematrícula exige ausência de pendências financeiras e envio do comprovante de endereço atualizado. O prazo se encerra 10 dias antes do início do semestre letivo.',
  },
  {
    chaves: ['tranc', 'suspend', 'pausar'],
    titulo: 'Trancamento de Matrícula',
    fonte: 'Regulamento Acadêmico - Art. 27',
    atualizado_em: '2026-02-20T00:00:00+00:00',
    trecho: 'O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.',
  },
  {
    chaves: ['fies', 'prouni', 'bolsa', 'financiamento'],
    titulo: 'Bolsas e Financiamentos',
    fonte: 'Manual do Aluno - Seção 6.1',
    atualizado_em: '2026-01-15T00:00:00+00:00',
    trecho: 'Bolsas e financiamentos, incluindo FIES e PROUNI, precisam ser renovados a cada semestre. A renovação abre 30 dias antes do início do período letivo, direto pelo portal financeiro.',
  },
  {
    chaves: ['falta', 'frequ', 'reprova'],
    titulo: 'Reprovação por Frequência',
    fonte: 'Regulamento Acadêmico - Art. 14',
    atualizado_em: '2026-03-08T00:00:00+00:00',
    trecho: 'O estudante que ultrapassar 25% de faltas em qualquer disciplina fica automaticamente reprovado por frequência, independente da nota obtida.',
  },
  {
    chaves: ['segunda chamada', 'perdi a prova', 'perdi prova'],
    titulo: 'Segunda Chamada de Prova',
    fonte: 'Regulamento Acadêmico - Art. 18',
    atualizado_em: '2026-02-10T00:00:00+00:00',
    trecho: 'A segunda chamada de prova pode ser solicitada em até 3 dias úteis após a data original da avaliação, mediante justificativa e comprovante (atestado médico, atestado de óbito ou declaração de trabalho).',
  },
  {
    chaves: ['atestado', 'médico', 'medico', 'doente'],
    titulo: 'Atestado Médico e Justificativa de Falta',
    fonte: 'Regulamento Acadêmico - Art. 16',
    atualizado_em: '2026-02-15T00:00:00+00:00',
    trecho: 'Faltas por motivo de saúde podem ser justificadas com atestado médico enviado em até 48 horas pelo portal do aluno, mas não isentam o estudante do conteúdo e das avaliações perdidas.',
  },
]

const TEXTO_ABSTENCAO =
  'Não encontrei essa informação com confiança suficiente nas fontes oficiais disponíveis. Vou te encaminhar para um atendente do ASA.'

// Texto SÓ para testar a formatação. Não é conteúdo institucional.
const TEXTO_FORMATACAO = `[Teste de formatação do mock] Este parágrafo verifica o espaçamento entre blocos de texto.
Esta linha vem depois de uma quebra simples.

Lista com marcadores:
- primeiro item
- segundo item, um pouco mais longo, para ver a quebra de linha dentro do item

1. passo numerado um
2. passo numerado dois

Link de teste: https://www.fecap.br/asa/ (página do ASA citada no README).`

// Conversa "Galeria de estados": mostra todos os estados de uma vez para revisão visual.
// Aparece só no modo ?mock. Fontes copiadas do seed_v2.sql.
export function conversaGaleria() {
  const [declaracao, rematricula, trancamento] = BASE
  const ev = (doc, s) => {
    const { titulo, fonte, atualizado_em, trecho } = evidencia(doc, s)
    return { titulo, fonte, similaridade: s, atualizadoEm: atualizado_em, trecho }
  }
  return {
    id: 'mock-galeria',
    titulo: 'Galeria de estados (mock)',
    demo: true,
    mensagens: [
      { id: 'g1', autor: 'estudante', texto: 'Como emitir a declaração de matrícula?' },
      { id: 'g2', autor: 'asa', tipo: 'resposta', texto: declaracao.trecho, confianca: 0.82, evidencias: [ev(declaracao, 0.82), ev(rematricula, 0.41), ev(trancamento, 0.34)] },
      { id: 'g3', autor: 'estudante', texto: 'Teste de formatação' },
      { id: 'g4', autor: 'asa', tipo: 'resposta', texto: TEXTO_FORMATACAO, confianca: 0.8, evidencias: [] },
      { id: 'g5', autor: 'estudante', texto: 'Qual a capital da França?' },
      { id: 'g6', autor: 'asa', tipo: 'abstencao', texto: TEXTO_ABSTENCAO, confianca: 0.09, evidencias: [] },
      { id: 'g7', autor: 'asa', tipo: 'encaminhamento' },
      // "Tentar de novo" reenvia a MESMA pergunta do balão; no mock ela volta com resposta e fonte.
      { id: 'g8', autor: 'estudante', texto: 'Quando renovo o FIES ou a bolsa?' },
      { id: 'g9', autor: 'asa', tipo: 'erro', motivo: 'rede', pergunta: 'Quando renovo o FIES ou a bolsa?' },
      // Carregamento estático: fica assim de propósito, só para revisar o visual.
      { id: 'g10', autor: 'estudante', texto: 'Com quantas faltas eu reprovo?' },
      { id: 'g11', autor: 'asa', tipo: 'carregando', pergunta: 'Com quantas faltas eu reprovo?' },
    ],
  }
}

export async function fetchMock(_url, options) {
  const { pergunta } = JSON.parse(options.body)
  const p = pergunta.toLowerCase()

  await esperar(p.includes('lento') ? 25000 : 900 + Math.random() * 700, options.signal)

  if (p.includes('erro')) throw new TypeError('Failed to fetch (simulado)')
  if (p.includes('debug')) return json({ resposta: '[DEBUG] RuntimeError: falha simulada', confianca: 0, abstencao: true, evidencias: [] })
  if (p.includes('formata')) return json({ resposta: TEXTO_FORMATACAO, confianca: 0.8, abstencao: false, evidencias: [] })

  const encontrados = BASE.filter((doc) => doc.chaves.some((c) => p.includes(c)))
  if (encontrados.length === 0) {
    return json({
      resposta: TEXTO_ABSTENCAO,
      confianca: 0.09,
      abstencao: true,
      evidencias: BASE.slice(4, 6).map((doc, i) => evidencia(doc, 0.09 - i * 0.02)),
    })
  }

  const [principal, ...outros] = encontrados
  const relacionados = outros.length ? outros : [BASE.find((d) => d !== principal)]
  return json({
    resposta: principal.trecho,
    confianca: 0.82,
    abstencao: false,
    evidencias: [evidencia(principal, 0.82), ...relacionados.slice(0, 2).map((d, i) => evidencia(d, 0.41 - i * 0.07))],
  })
}

function evidencia(doc, similaridade) {
  const { titulo, fonte, atualizado_em, trecho } = doc
  return { titulo, fonte, similaridade: Math.round(similaridade * 10000) / 10000, atualizado_em, trecho }
}

function json(corpo, status = 200) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function esperar(ms, signal) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new DOMException('Aborted', 'AbortError'))
    })
  })
}
