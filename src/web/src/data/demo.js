// 🧪 DADOS DE DEMONSTRAÇÃO (fictícios). A API não recebe nem conhece o usuário.
// Mesmos dados da interface antiga (src/Entrega 1/index.html).

export const USUARIO_DEMO = { nome: 'João Silva', iniciais: 'JS', ra: '20260001' }

// Sugestões da tela inicial: só temas que existem na base (seed_v2.sql).
export const SUGESTOES = [
  { tema: 'Documentos', pergunta: 'Como emitir a declaração de matrícula?' },
  { tema: 'Matrícula', pergunta: 'O que preciso para fazer a rematrícula?' },
  { tema: 'Matrícula', pergunta: 'Posso trancar minha matrícula neste semestre?' },
  { tema: 'Financeiro', pergunta: 'Quando renovo o FIES ou a bolsa?' },
  { tema: 'Frequência', pergunta: 'Com quantas faltas eu reprovo?' },
  { tema: 'Provas', pergunta: 'Perdi a prova. Como peço segunda chamada?' },
]

// Conversas de exemplo pré-carregadas, marcadas como demo.
export const CONVERSAS_DEMO = [
  {
    id: 'demo-1',
    titulo: 'Pendência de rematrícula',
    demo: true,
    mensagens: [
      { id: 'demo-1-1', autor: 'estudante', texto: 'Tenho pendência para rematrícula?' },
      {
        id: 'demo-1-2',
        autor: 'asa',
        tipo: 'resposta',
        texto: 'A rematrícula exige ausência de pendências financeiras e envio do comprovante de endereço atualizado. O prazo se encerra 10 dias antes do início do semestre letivo.',
        confianca: 0.87,
        evidencias: [
          { titulo: 'Rematrícula', fonte: 'Manual do Aluno - Seção 4.2', similaridade: 0.87, atualizadoEm: '2026-08-12T00:00:00+00:00', trecho: 'A rematrícula exige ausência de pendências financeiras e envio do comprovante de endereço atualizado. O prazo se encerra 10 dias antes do início do semestre letivo.' },
        ],
      },
    ],
  },
  {
    id: 'demo-2',
    titulo: 'Trancamento de matrícula',
    demo: true,
    mensagens: [
      { id: 'demo-2-1', autor: 'estudante', texto: 'Posso suspender meu curso esse semestre?' },
      {
        id: 'demo-2-2',
        autor: 'asa',
        tipo: 'resposta',
        texto: 'O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.',
        confianca: 0.81,
        evidencias: [
          { titulo: 'Trancamento de Matrícula', fonte: 'Regulamento Acadêmico - Art. 27', similaridade: 0.81, atualizadoEm: '2026-02-20T00:00:00+00:00', trecho: 'O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.' },
        ],
      },
    ],
  },
]
