// Formatação para pt-BR.

// Datas que chegam à meia-noite UTC (data_atualizacao, competência) são formatadas em UTC
// para não "voltarem" um dia no fuso de Brasília.
function data(iso) {
  if (!iso) return null
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso)
  return Number.isNaN(d.getTime()) ? null : d
}
const ehMeiaNoiteUtc = (d) => d.getUTCHours() === 0 && d.getUTCMinutes() === 0

export function dataCurta(iso) { // 15/10/2026
  const d = data(iso)
  if (!d) return '—'
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', ...(ehMeiaNoiteUtc(d) ? { timeZone: 'UTC' } : {}) })
}

export function diaMes(iso) { // 05/11
  const d = data(iso)
  if (!d) return '—'
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', ...(ehMeiaNoiteUtc(d) ? { timeZone: 'UTC' } : {}) })
}

export function dataHora(iso) { // 28/10/2026 às 19:12
  const d = data(iso)
  if (!d) return '—'
  return `${d.toLocaleDateString('pt-BR')} às ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
}

export function hora(iso) {
  const d = data(iso)
  return d ? d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : ''
}

export function mesAbreviado(iso) { // "out"
  const d = data(iso)
  return d ? d.toLocaleDateString('pt-BR', { month: 'short', timeZone: 'UTC' }).replace('.', '') : ''
}
export function mesAno(iso) { // "outubro de 2026"
  const d = data(iso)
  return d ? d.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' }) : ''
}

export const pct = (p, casas = 0) => (p === null || p === undefined ? '—' : `${(p * 100).toLocaleString('pt-BR', { maximumFractionDigits: casas, minimumFractionDigits: casas })}%`)
export const numero = (n) => (n === null || n === undefined ? '—' : n.toLocaleString('pt-BR'))

// variação de score em pontos percentuais: "+9 p.p."
export function pontos(v) {
  if (v === null || v === undefined) return '—'
  const pp = Math.round(v * 100)
  if (pp === 0) return '0 p.p.'
  return `${pp > 0 ? '+' : '−'}${Math.abs(pp)} p.p.`
}

export const ROTULO = {
  categoria: { verde: 'Verde', amarelo: 'Amarelo', vermelho: 'Vermelho' },
  prioridade: { urgente: 'Urgente', alta: 'Alta', media: 'Média', baixa: 'Baixa' },
  status: { novo: 'Novo', em_acompanhamento: 'Em acompanhamento', contatado: 'Contatado', resolvido: 'Resolvido', arquivado: 'Arquivado' },
  tendencia: { subindo: 'Subindo', estavel: 'Estável', caindo: 'Caindo' },
  decisao: { confirmado: 'Confirmado', ajustado: 'Ajustado', rejeitado: 'Rejeitado' },
  dimensao: { financeira: 'Financeira', academica: 'Acadêmica', relacionamento: 'Relacionamento' },
  faixa: { ate_5km: 'até 5 km', '5_15km': '5 a 15 km', '15_30km': '15 a 30 km', acima_30km: 'mais de 30 km' },
  papel: { estudante: 'Estudante', atendente: 'Atendente', administrador: 'Administração', equipe_tecnica: 'Equipe técnica' },
}

export function iniciais(nome = '') {
  const p = nome.trim().split(/\s+/)
  return ((p[0]?.[0] ?? '') + (p.length > 1 ? p.at(-1)[0] : '')).toUpperCase()
}
