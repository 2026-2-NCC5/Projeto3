// Dados FICTÍCIOS do modo mock. Mesmo vocabulário de seeds/gerar_seeds.py (nomes genéricos,
// RA com prefixo 99, fórmula sintética de score), gerados de forma determinística no navegador.
// Nenhuma linha vem de pessoa real.

export const VERSAO_MODELO = 'seed-sintetico-0'
export const VERSAO_RAG = 'rag-0.9+bge-m3'
export const AVISO_SCORE = 'Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana.'

export const USUARIOS = {
  estudante: { id: 'd0000000-0000-4000-8000-000000000001', nome: 'Júlia Prado', email: 'estudante.demo@example.com', papel: 'estudante',
    estudante: { id: 'd0000000-0000-4000-8000-000000000001', ra: '99999901', curso: 'Administração', semestre: 3 } },
  atendente: { id: 'd0000000-0000-4000-8000-000000000002', nome: 'Renata Lopes', email: 'atendente.demo@example.com', papel: 'atendente', estudante: null },
  administrador: { id: 'd0000000-0000-4000-8000-000000000003', nome: 'Carlos Monteiro', email: 'admin.demo@example.com', papel: 'administrador', estudante: null },
  equipe_tecnica: { id: 'd0000000-0000-4000-8000-000000000004', nome: 'Equipe Técnica', email: 'tecnica.demo@example.com', papel: 'equipe_tecnica', estudante: null },
}
const OUTROS_ATENDENTES = [{ id: 'd0000000-0000-4000-8000-000000000005', nome: 'Marcos Teixeira' }]

// ------------------------------------------------------------------- aleatório
function mulberry32(semente) {
  let a = semente >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const rng = mulberry32(20261106)
const escolher = (lista) => lista[Math.floor(rng() * lista.length)]
const entre = (min, max) => min + rng() * (max - min)
const inteiro = (min, max) => Math.floor(entre(min, max + 1))
const limitar = (v, min, max) => Math.max(min, Math.min(max, v))
const sigmoide = (x) => 1 / (1 + Math.exp(-x))
const arred = (v, casas = 4) => Math.round(v * 10 ** casas) / 10 ** casas

let contadorUuid = 0
export function uuid(prefixo = 'f') {
  contadorUuid += 1
  return `${prefixo.padEnd(8, '0').slice(0, 8)}-0000-4000-8000-${String(contadorUuid).padStart(12, '0')}`
}

// ------------------------------------------------------------------- vocabulário
const PRENOMES = ['Ana', 'Beatriz', 'Bruna', 'Camila', 'Carolina', 'Clara', 'Daniela', 'Eduarda', 'Fernanda', 'Gabriela', 'Helena', 'Isabela', 'Júlia', 'Larissa', 'Letícia', 'Lívia', 'Luana', 'Mariana', 'Natália', 'Paula', 'Rafaela', 'Sofia', 'Tainá', 'Vitória', 'André', 'Arthur', 'Bruno', 'Caio', 'Daniel', 'Diego', 'Eduardo', 'Felipe', 'Gabriel', 'Gustavo', 'Henrique', 'Igor', 'João', 'Leonardo', 'Lucas', 'Mateus', 'Murilo', 'Otávio', 'Pedro', 'Rafael', 'Renan', 'Samuel', 'Thiago', 'Vinícius']
const SOBRENOMES = ['Almeida', 'Alves', 'Andrade', 'Antunes', 'Araújo', 'Barbosa', 'Barros', 'Batista', 'Cardoso', 'Carvalho', 'Castro', 'Cordeiro', 'Correia', 'Costa', 'Dias', 'Duarte', 'Farias', 'Fernandes', 'Freitas', 'Gomes', 'Lima', 'Lopes', 'Machado', 'Martins', 'Melo', 'Mendes', 'Monteiro', 'Moraes', 'Moreira', 'Nascimento', 'Nogueira', 'Nunes', 'Oliveira', 'Pereira', 'Pinto', 'Prado', 'Ramos', 'Rezende', 'Rocha', 'Santana', 'Santos', 'Silva', 'Siqueira', 'Soares', 'Souza', 'Teixeira', 'Vieira', 'Xavier']
const CURSOS = [['Administração', 8], ['Ciências Contábeis', 8], ['Ciências Econômicas', 8], ['Relações Internacionais', 8], ['Ciência da Computação', 8], ['Publicidade e Propaganda', 8], ['Gestão Financeira', 4], ['Marketing', 4]]
const REGIOES = [['Centro - SP', 'ate_5km'], ['Zona Oeste - SP', '5_15km'], ['Zona Sul - SP', '5_15km'], ['Zona Norte - SP', '5_15km'], ['Zona Leste - SP', '15_30km'], ['Grande SP - ABC', '15_30km'], ['Grande SP - Guarulhos', '15_30km'], ['Interior/Litoral - SP', 'acima_30km']]
const MOTIVOS_CONTATO = ['Acompanhamento de frequência', 'Convite para plantão de monitoria', 'Orientação sobre negociação de parcelas', 'Apresentação de bolsas disponíveis', 'Retorno de caso em acompanhamento', 'Convite para conversa com coach acadêmico']

export const COMPETENCIAS = ['2026-05-01', '2026-06-01', '2026-07-01', '2026-08-01', '2026-09-01', '2026-10-01']
const CALCULADO_EM = '2026-11-01T06:00:00-03:00'

export function categoria(p) {
  if (p >= 0.6) return 'vermelho'
  if (p >= 0.3) return 'amarelo'
  return 'verde'
}

// ------------------------------------------------------------- score sintético
// Mesma fórmula de seeds/gerar_seeds.py. NÃO é o modelo real.
function termos(f) {
  const pct = (v) => `${Math.round(v * 100)}%`
  return [
    ['parcelas_em_aberto', 'financeira', 4.0 * (f.pctAberto - 0.10), `${pct(f.pctAberto)} das parcelas em aberto`],
    ['atraso_medio', 'financeira', 0.03 * (f.atraso - 2), `Atraso médio de ${Math.round(f.atraso)} dias nos pagamentos`],
    ['parcelas_em_acordo', 'financeira', 2.0 * (f.pctAcordo - 0.05), `${pct(f.pctAcordo)} das parcelas em acordo`],
    ['bolsa', 'financeira', f.bolsa ? -0.4 : 0, 'Possui bolsa ou financiamento'],
    ['media_notas', 'academica', -0.06 * (f.notas - 70), `Média de notas ${Math.round(f.notas)}/100`],
    ['assiduidade', 'academica', -0.08 * (f.assiduidade - 85), `Assiduidade média de ${Math.round(f.assiduidade)}%`],
    ['reprovacoes', 'academica', 3.0 * (f.reprovacao - 0.10), `${pct(f.reprovacao)} das disciplinas com reprovação`],
    ['tendencia_notas', 'academica', -0.05 * f.tendNotas, f.tendNotas < 0 ? 'Notas em queda no período' : 'Notas em melhora no período'],
    ['semestre_inicial', 'relacionamento', f.semestres <= 2 ? 0.5 : 0, 'Primeiros semestres do curso'],
    ['sem_contato_ativo', 'relacionamento', 0.004 * (f.diasSemContato - 90), `${f.diasSemContato} dias sem contato ativo do ASA`],
  ]
}

export function pontuar(f) {
  const ts = termos(f)
  const dim = { financeira: 0, academica: 0, relacionamento: 0 }
  for (const [, d, v] of ts) dim[d] += v
  const geral = sigmoide(-1.1 + 0.45 * (dim.financeira + dim.academica + dim.relacionamento))
  const relevantes = ts.filter((t) => Math.abs(t[2]) >= 0.05).sort((a, b) => Math.abs(b[2]) - Math.abs(a[2])).slice(0, 5)
  const total = relevantes.reduce((s, t) => s + Math.abs(t[2]), 0) || 1
  return {
    score: {
      geral: arred(geral),
      financeiro: arred(sigmoide(-1 + 1.6 * dim.financeira)),
      academico: arred(sigmoide(-1 + 1.6 * dim.academica)),
      relacionamento: arred(sigmoide(-1 + 1.6 * dim.relacionamento)),
    },
    categoria: categoria(geral),
    fatores: relevantes.map(([codigo, dimensao, v, descricao]) => ({
      codigo, descricao, dimensao, direcao: v > 0 ? 'aumenta' : 'reduz', peso: arred(Math.abs(v) / total, 2),
    })),
  }
}

const RECOMENDACOES = {
  financeira: 'Oferecer conversa sobre negociação de parcelas e bolsas disponíveis (Cesta de Serviços: Bolsas e Financiamentos).',
  academica: 'Convidar para plantão de monitoria ou coach acadêmico e acompanhar a frequência nas próximas duas semanas.',
  relacionamento: 'Fazer contato de acolhimento e apresentar os serviços do ASA para o semestre.',
}
export function recomendar(cat, fatores) {
  if (cat === 'verde') return 'Sem ação imediata. Manter acompanhamento de rotina.'
  const aumenta = fatores.find((f) => f.direcao === 'aumenta')
  const prefixo = cat === 'vermelho' ? 'Prioridade: contato nesta semana. ' : ''
  return prefixo + RECOMENDACOES[aumenta?.dimensao ?? 'relacionamento']
}

// ------------------------------------------------------------------- estudantes
function gerarFeatures(perfil) {
  const ruim = perfil
  return {
    pctAberto: limitar(entre(0, 0.12) + ruim * entre(0.05, 0.5), 0, 1),
    atraso: limitar(entre(0, 6) + ruim * entre(5, 40), 0, 90),
    pctAcordo: limitar(entre(0, 0.06) + ruim * entre(0, 0.25), 0, 1),
    bolsa: rng() < 0.35,
    notas: limitar(entre(68, 92) - ruim * entre(5, 30), 0, 100),
    assiduidade: limitar(entre(82, 98) - ruim * entre(5, 25), 0, 100),
    reprovacao: limitar(entre(0, 0.08) + ruim * entre(0, 0.35), 0, 1),
    tendNotas: entre(-4, 4) - ruim * entre(0, 8),
    semestres: inteiro(1, 8),
    diasSemContato: inteiro(20, 120) + Math.round(ruim * inteiro(0, 120)),
  }
}

function evoluir(f, deriva) {
  return {
    ...f,
    pctAberto: limitar(f.pctAberto + deriva * entre(0.01, 0.05), 0, 1),
    atraso: limitar(f.atraso + deriva * entre(0.5, 4), 0, 90),
    notas: limitar(f.notas - deriva * entre(0.5, 2.5), 0, 100),
    assiduidade: limitar(f.assiduidade - deriva * entre(0.5, 2), 0, 100),
    tendNotas: f.tendNotas - deriva * entre(0, 0.6),
    diasSemContato: Math.max(0, f.diasSemContato + 30),
  }
}

function dataMaisDias(base, dias) {
  const d = new Date(base + 'T12:00:00-03:00')
  d.setDate(d.getDate() + dias)
  return d.toISOString().slice(0, 10)
}

function gerarEstudantes() {
  const lista = []
  for (let i = 0; i < 300; i++) {
    const [curso, duracao] = escolher(CURSOS)
    const [regiao, faixa] = escolher(REGIOES)
    const sorteio = rng()
    const perfil = sorteio < 0.55 ? entre(0, 0.25) : sorteio < 0.82 ? entre(0.3, 0.7) : entre(0.75, 1)
    const deriva = entre(-1, 1.2) // > 0: piorando ao longo dos meses
    let f = gerarFeatures(perfil)
    // começa 5 meses "antes", ajustando no sentido oposto da deriva
    f = { ...f, pctAberto: limitar(f.pctAberto - deriva * 0.12, 0, 1), notas: limitar(f.notas + deriva * 6, 0, 100), assiduidade: limitar(f.assiduidade + deriva * 5, 0, 100), diasSemContato: Math.max(0, f.diasSemContato - 150) }
    const serie = []
    for (const comp of COMPETENCIAS) {
      const r = pontuar(f)
      serie.push({ competencia: comp, features: f, ...r, score_id: uuid('5c0e') })
      f = evoluir(f, deriva)
    }
    const id = `e${String(i + 1).padStart(7, '0')}-0000-4000-8000-${String(i + 1).padStart(12, '0')}`
    lista.push({
      estudante: {
        id, ra: `99${String(100000 + i * 37).slice(-6)}`,
        nome: `${escolher(PRENOMES)} ${escolher(SOBRENOMES)} ${escolher(SOBRENOMES)}`,
        curso, semestre: inteiro(1, duracao), faixa_distancia: faixa, regiao,
      },
      serie,
    })
  }
  return lista
}

// ------------------------------------------------------------------------ casos
const PRIORIDADE_ORDEM = { urgente: 0, alta: 1, media: 2, baixa: 3 }
export { PRIORIDADE_ORDEM }

function montarCasos(lista) {
  const atendente = { id: USUARIOS.atendente.id, nome: USUARIOS.atendente.nome }
  for (const e of lista) {
    const atual = e.serie.at(-1)
    const anterior = e.serie.at(-2)
    e.variacao = arred(atual.score.geral - anterior.score.geral, 4)
    e.categoriaVigente = atual.categoria
    e.validacoes = []
    e.eventos = []
    e.caso = null

    // eventos de score (um por mês)
    for (const s of e.serie) {
      e.eventos.push({ id: uuid('ev'), tipo: 'score', ocorrido_em: `${dataMaisDias(s.competencia, 31).slice(0, 7)}-01T06:00:00-03:00`,
        descricao: `Score calculado: ${Math.round(s.score.geral * 100)}% (${rotuloCategoria(s.categoria)})`, usuario: null,
        dados: { score_geral: s.score.geral, categoria: s.categoria, versao_modelo: VERSAO_MODELO } })
    }

    if (atual.categoria === 'verde') continue
    const p = atual.score.geral
    const prioridade = p >= 0.75 ? 'urgente' : p >= 0.6 ? 'alta' : p >= 0.45 ? 'media' : 'baixa'
    const status = escolher(['novo', 'novo', 'novo', 'em_acompanhamento', 'contatado'])
    const temResponsavel = status !== 'novo' || rng() < 0.15
    const responsavel = temResponsavel ? (rng() < 0.7 ? atendente : OUTROS_ATENDENTES[0]) : null
    e.caso = {
      id: uuid('ca50'), status, prioridade,
      prazo: dataMaisDias('2026-11-02', prioridade === 'urgente' ? inteiro(0, 3) : prioridade === 'alta' ? inteiro(2, 7) : inteiro(5, 20)),
      responsavel,
    }
    e.eventos.push({ id: uuid('ev'), tipo: 'criado', ocorrido_em: '2026-11-01T06:05:00-03:00', descricao: `Caso aberto com prioridade ${rotuloPrioridade(prioridade).toLowerCase()}`, usuario: null, dados: {} })
    if (responsavel) {
      e.eventos.push({ id: uuid('ev'), tipo: 'responsavel', ocorrido_em: '2026-11-01T09:20:00-03:00', descricao: `${responsavel.nome} assumiu o caso`, usuario: responsavel, dados: { de: null, para: responsavel.nome } })
    }
    if (status === 'contatado' || status === 'em_acompanhamento') {
      e.eventos.push({ id: uuid('ev'), tipo: 'contato', ocorrido_em: '2026-10-29T15:40:00-03:00', descricao: `Contato ativo por telefone: ${escolher(MOTIVOS_CONTATO).toLowerCase()}`, usuario: responsavel,
        dados: { origem: 'contato_ativo', canal: 'telefone', motivo: escolher(MOTIVOS_CONTATO), resultado: 'Estudante atendeu e aceitou acompanhamento' } })
    }
    if (status === 'em_acompanhamento' && responsavel) {
      const v = {
        id: uuid('va1d'), score_id: e.serie.at(-2).score_id, decisao: 'confirmado',
        justificativa: 'Conversei com o estudante; a situação descrita pelos fatores confere com o relato.',
        categoria_ajustada: null, prioridade, prazo: e.caso.prazo, atendente: responsavel, versao_modelo: VERSAO_MODELO, criado_em: '2026-10-20T10:15:00-03:00',
      }
      e.validacoes.push(v)
      e.eventos.push(eventoValidacao(v))
    }
  }
}

export function eventoValidacao(v) {
  const texto = { confirmado: 'confirmou a categoria do modelo', ajustado: `ajustou a categoria para ${rotuloCategoria(v.categoria_ajustada)}`, rejeitado: 'rejeitou o alerta' }[v.decisao]
  return { id: uuid('ev'), tipo: 'validacao', ocorrido_em: v.criado_em, descricao: `${v.atendente.nome} ${texto}`, usuario: v.atendente, dados: v }
}

export function rotuloCategoria(c) { return { verde: 'Verde', amarelo: 'Amarelo', vermelho: 'Vermelho' }[c] ?? c }
export function rotuloPrioridade(p) { return { baixa: 'Baixa', media: 'Média', alta: 'Alta', urgente: 'Urgente' }[p] ?? p }

export const estudantes = gerarEstudantes()
montarCasos(estudantes)
export { CALCULADO_EM }

// ------------------------------------------------------------ base de conhecimento
// Trechos públicos da Cesta de Serviços ASA (seeds/base_conhecimento_oficial.sql).
export const DOCUMENTOS = [
  { id: '0c66e0d5-4e7b-56a3-838a-7a44a4405079', titulo: 'Atestado de matrícula', categoria: 'documentos_academicos', fonte: 'Cesta de Serviços ASA - Documentos Acadêmicos', data_atualizacao: '2026-10-15T00:00:00+00:00',
    conteudo: 'Atestado de matrícula: Precisa do atestado de matrícula? É super simples: basta acessar o portal, escolher a opção Relatórios e emitir o documento. Ficou com dúvidas? Entre em contato por meio dos nossos canais de atendimento.\n\nAtendimento: Setor responsável: Secretaria Acadêmica. Local: Área do Sucesso Alvarista. Horário de atendimento: Segunda a Sexta, das 7h00 às 21h00 | Sábado, das 09h00 às 12h30.',
    chaves: ['atestado de matr', 'comprovante de matr', 'declaração de matr', 'declaracao de matr'],
    resposta: 'Para emitir o atestado de matrícula:\n1. Acesse o portal.\n2. Escolha a opção Relatórios.\n3. Emita o documento.',
    trecho: 'Precisa do atestado de matrícula? É super simples: basta acessar o portal, escolher a opção Relatórios e emitir o documento.' },
  { id: 'e1b22c41-d859-5a7b-8c54-8259c3d7cc44', titulo: 'Rematrícula', categoria: 'servicos_academicos', fonte: 'Cesta de Serviços ASA - Serviços Acadêmicos', data_atualizacao: '2026-10-15T00:00:00+00:00',
    conteudo: 'Rematrícula: Agora a rematrícula é AUTOMÁTICA! Assim que você é aprovado(a), o boleto de rematrícula já fica disponível no Portal do Aluno > Financeiro, para pagamento até o dia o 07/01.\n\nCondições: Não possuir débitos financeiros referentes ao ano letivo anterior.',
    chaves: ['rematr'],
    resposta: 'A rematrícula é automática depois da aprovação. Para concluir:\n1. Acesse o Portal do Aluno e abra Financeiro.\n2. Pague o boleto de rematrícula até 07/01.\n\nÉ preciso não ter débitos do ano letivo anterior.',
    trecho: 'Assim que você é aprovado(a), o boleto de rematrícula já fica disponível no Portal do Aluno > Financeiro, para pagamento até o dia 07/01.' },
  { id: '33333333-3333-3333-3333-333333333333', titulo: 'Trancamento de Matrícula', categoria: 'servicos_academicos', fonte: 'Regulamento Acadêmico - Art. 27', data_atualizacao: '2026-02-20T00:00:00+00:00',
    conteudo: 'Trancamento de Matrícula: O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.',
    chaves: ['tranc', 'pausar o curso', 'parar o curso'],
    resposta: 'O trancamento precisa ser pedido com 15 dias de antecedência do início do semestre. Se você tem bolsa ou financiamento, ele pode ser afetado, então vale conversar com o ASA antes.',
    trecho: 'O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.' },
  { id: 'a0000000-0000-0000-0000-000000000004', titulo: 'Trabalho de Conclusão de Curso (TCC)', categoria: 'servicos_academicos', fonte: 'Manual do Aluno - Seção 7.3', data_atualizacao: '2026-05-10T00:00:00+00:00',
    conteudo: 'Trabalho de Conclusão de Curso (TCC): O TCC deve ser iniciado no penúltimo semestre do curso, com orientador definido até o final do primeiro mês de aula, e entregue conforme cronograma da coordenação.',
    chaves: ['tcc', 'conclusão de curso', 'conclusao de curso', 'orientador'],
    resposta: 'O TCC começa no penúltimo semestre do curso. O orientador precisa estar definido até o fim do primeiro mês de aula, e a entrega segue o cronograma da coordenação.',
    trecho: 'O Trabalho de Conclusão de Curso (TCC) deve ser iniciado no penúltimo semestre do curso, com orientador definido até o final do primeiro mês de aula.' },
  { id: '68457609-deb8-5186-89be-2b9ac7e9cbd5', titulo: 'Abono ou Compensação de Faltas', categoria: 'servicos_academicos', fonte: 'Cesta de Serviços ASA - Serviços Acadêmicos', data_atualizacao: '2026-10-15T00:00:00+00:00',
    conteudo: 'Abono ou Compensação de Faltas: Precisou faltar nas aulas por motivo de saúde, alistamento militar ou outras razões previstas em lei? Envie o atestado e solicite a análise para o abono das faltas pelo Portal do Aluno > Menu > Secretaria/Requerimentos > Abono de Faltas.',
    chaves: ['abono', 'abonar', 'justificar falta', 'atestado médico', 'atestado medico'],
    resposta: 'Faltas por saúde, alistamento militar ou outros motivos previstos em lei podem ser abonadas:\n1. Acesse o Portal do Aluno.\n2. Vá em Menu > Secretaria/Requerimentos > Abono de Faltas.\n3. Anexe o atestado e envie para análise.',
    trecho: 'Envie o atestado e solicite a análise para o abono das faltas pelo Portal do Aluno > Menu > Secretaria/Requerimentos > Abono de Faltas.' },
  { id: '55555555-5555-5555-5555-555555555555', titulo: 'Reprovação por Frequência', categoria: 'servicos_academicos', fonte: 'Regulamento Acadêmico - Art. 14', data_atualizacao: '2026-03-08T00:00:00+00:00',
    conteudo: 'Reprovação por Frequência: O estudante que ultrapassar 25% de faltas em qualquer disciplina fica automaticamente reprovado por frequência, independente da nota obtida.',
    chaves: ['faltas', 'frequência', 'frequencia', 'reprovo'],
    resposta: 'Quem passa de 25% de faltas em uma disciplina é reprovado por frequência, mesmo com nota suficiente.',
    trecho: 'O estudante que ultrapassar 25% de faltas em qualquer disciplina fica automaticamente reprovado por frequência, independente da nota obtida.' },
  { id: 'd1b538bd-9824-5348-b4cf-7456189a07cb', titulo: 'FIES – Aditamento para Renovação', categoria: 'bolsas_financiamentos', fonte: 'Cesta de Serviços ASA - Bolsas e Financiamentos', data_atualizacao: '2026-10-15T00:00:00+00:00',
    conteudo: 'FIES – Aditamento para Renovação: Quer realizar a renovação (Aditamento) semestral do FIES e não sabe como? Entre em contato por meio dos canais de atendimento do Asa e nós te orientaremos sobre o processo de aditamento para renovação (simplificado ou não simplificado).\n\nAtendimento: Setor responsável: Financeiro. Local: Área do Sucesso Alvarista.',
    chaves: ['fies', 'aditamento'],
    resposta: 'A renovação do FIES é semestral (aditamento, simplificado ou não). O setor Financeiro orienta o processo na Área do Sucesso Alvarista, de segunda a sexta, das 7h às 21h, e aos sábados, das 9h às 12h30.',
    trecho: 'Quer realizar a renovação (Aditamento) semestral do FIES e não sabe como? Entre em contato por meio dos canais de atendimento do Asa e nós te orientaremos.' },
  { id: '089e200a-28bb-5c67-9c7c-129bd43323ea', titulo: 'Solicitação de Boleto', categoria: 'servicos_academicos', fonte: 'Cesta de Serviços ASA - Serviços Acadêmicos', data_atualizacao: '2026-10-15T00:00:00+00:00',
    conteudo: 'Solicitação de Boleto: orientações para emissão de boletos pelo Portal do Aluno.', chaves: [], resposta: null, trecho: '' },
  { id: 'cece73b7-3da0-5ea8-b9b5-cb99a5a22787', titulo: 'Aproveitamento de Disciplinas', categoria: 'servicos_academicos', fonte: 'Cesta de Serviços ASA - Serviços Acadêmicos', data_atualizacao: '2026-10-15T00:00:00+00:00',
    conteudo: 'Aproveitamento de Disciplinas: análise de disciplinas cursadas em outra instituição.', chaves: [], resposta: null, trecho: '' },
  { id: 'a0000000-0000-0000-0000-000000000002', titulo: 'Cancelamento de Matrícula', categoria: 'servicos_academicos', fonte: 'Regulamento Acadêmico', data_atualizacao: '2026-02-20T00:00:00+00:00',
    conteudo: 'Cancelamento de Matrícula: O cancelamento de matrícula é definitivo e diferente do trancamento: encerra o vínculo do estudante com a instituição e não garante direito a retorno automático no futuro.', chaves: ['cancelar', 'cancelamento'],
    resposta: 'O cancelamento é definitivo e diferente do trancamento: encerra o vínculo com a FECAP e não garante retorno automático. Se a ideia é dar uma pausa, o trancamento costuma ser o caminho.',
    trecho: 'O cancelamento de matrícula é definitivo e diferente do trancamento: encerra o vínculo do estudante com a instituição.' },
].map((d) => ({ ...d, versao: 1, ativo: true, versoes: [{ versao: 1, data_atualizacao: d.data_atualizacao, motivo: 'Carga inicial da Cesta de Serviços ASA', alterado_por: 'Carga inicial', criado_em: '2026-10-15T10:00:00-03:00' }], desativado_em: null, motivo_desativacao: null }))

// Completa a lista com os demais títulos reais (sem conteúdo no mock), para a tabela ter volume.
const OUTROS_TITULOS = [
  ['Bolsa Ex-Aluno', 'alumni'], ['Diploma', 'alumni'], ['Diploma – 2ª via', 'alumni'], ['Coach Acadêmico', 'aprendizagem'], ['Monitoria de estudos', 'aprendizagem'], ['Nivelamento', 'aprendizagem'],
  ['Biblioteca - Empréstimo de Livros', 'biblioteca'], ['Renovação de Materiais', 'biblioteca'], ['Pagamento de Multas', 'biblioteca'], ['Auxílio Financeiro Emergencial', 'bolsas_financiamentos'],
  ['Bolsa Estágio', 'bolsas_financiamentos'], ['ProUni: Atualização', 'bolsas_financiamentos'], ['Aconselhamento de Carreira', 'carreira_empregabilidade'], ['Estágio Obrigatório', 'carreira_empregabilidade'],
  ['Alteração de dados cadastrais', 'dados_cadastrais'], ['Declaração de Notas', 'documentos_academicos'], ['Declaração de adimplência', 'documentos_financeiros'], ['Calendário Acadêmico', 'servicos_academicos'],
  ['Prova Substitutiva', 'servicos_academicos'], ['Solicitação de DP', 'servicos_academicos'], ['Transferência de turno', 'servicos_academicos'], ['Destrancamento de Curso', 'servicos_academicos'],
]
for (const [titulo, cat] of OUTROS_TITULOS) {
  DOCUMENTOS.push({ id: uuid('d0c'), titulo, categoria: cat, fonte: `Cesta de Serviços ASA - ${titulo}`, data_atualizacao: '2026-10-15T00:00:00+00:00', conteudo: `${titulo}: conteúdo oficial da Cesta de Serviços ASA (resumido no modo de demonstração).`, chaves: [], resposta: null, trecho: '', versao: 1, ativo: true,
    versoes: [{ versao: 1, data_atualizacao: '2026-10-15T00:00:00+00:00', motivo: 'Carga inicial da Cesta de Serviços ASA', alterado_por: 'Carga inicial', criado_em: '2026-10-15T10:00:00-03:00' }], desativado_em: null, motivo_desativacao: null })
}
// Um documento já desativado, para o filtro "Inativos" ter conteúdo.
DOCUMENTOS.push({ id: uuid('d0c'), titulo: 'Ingressantes – Lista de Material (2025)', categoria: 'servicos_academicos', fonte: 'Cesta de Serviços ASA - Serviços Acadêmicos', data_atualizacao: '2025-12-01T00:00:00+00:00', conteudo: 'Lista de material do semestre 2025.2.', chaves: [], resposta: null, trecho: '', versao: 2, ativo: false,
  versoes: [{ versao: 2, data_atualizacao: '2025-12-01T00:00:00+00:00', motivo: 'Atualização da lista', alterado_por: 'Carlos Monteiro', criado_em: '2025-12-01T10:00:00-03:00' }, { versao: 1, data_atualizacao: '2025-06-01T00:00:00+00:00', motivo: null, alterado_por: 'Carga inicial', criado_em: '2025-06-01T10:00:00-03:00' }],
  desativado_em: '2026-10-15T10:00:00-03:00', motivo_desativacao: 'Substituído pela lista de 2026 publicada no portal.' })

// ---------------------------------------------------------- conversas do estudante demo
export const conversasDemo = [
  {
    id: 'c0000000-0000-4000-8000-000000000001', titulo: 'Atestado de matrícula', status: 'encerrada',
    iniciada_em: '2026-10-28T19:12:00-03:00', atualizada_em: '2026-10-28T19:12:03-03:00', encaminhamento: null,
    mensagens: [
      { id: uuid('m'), remetente: 'estudante', conteudo: 'Como tiro o atestado de matrícula?', criado_em: '2026-10-28T19:12:00-03:00', resposta: null },
      { id: uuid('m'), remetente: 'agente', conteudo: DOCUMENTOS[0].resposta, criado_em: '2026-10-28T19:12:03-03:00',
        resposta: { resposta_id: 'r0000000-0000-4000-8000-000000000001', confianca: 0.7124, abstencao: false, feedback: 'util',
          fontes: [{ documento_id: DOCUMENTOS[0].id, titulo: DOCUMENTOS[0].titulo, fonte: DOCUMENTOS[0].fonte, data_atualizacao: DOCUMENTOS[0].data_atualizacao, trecho: DOCUMENTOS[0].trecho, similaridade: 0.7124 }] } },
    ],
  },
  {
    id: 'c0000000-0000-4000-8000-000000000002', titulo: 'Animais no campus', status: 'encaminhada_humano',
    iniciada_em: '2026-10-30T21:40:00-03:00', atualizada_em: '2026-10-30T21:40:03-03:00',
    encaminhamento: { id: 'f0000000-0000-4000-8000-000000000001', status: 'aberto', setor_destino: 'ASA', prazo: '2026-11-01T21:40:00-03:00' },
    mensagens: [
      { id: uuid('m'), remetente: 'estudante', conteudo: 'Posso levar meu cachorro para a aula?', criado_em: '2026-10-30T21:40:00-03:00', resposta: null },
      { id: uuid('m'), remetente: 'agente', conteudo: 'Não encontrei isso nos documentos oficiais. Quer que eu encaminhe para o ASA?', criado_em: '2026-10-30T21:40:03-03:00',
        resposta: { resposta_id: 'r0000000-0000-4000-8000-000000000002', confianca: 0.421, abstencao: true, feedback: null, fontes: [] } },
    ],
  },
]
