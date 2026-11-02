// Quem pode abrir cada área (espelha `x-papeis` do contrato). O backend é quem garante;
// aqui é só para não mostrar tela que vai responder 403.
export const AREAS = [
  { prefixo: '/chat', papeis: ['estudante'] },
  { prefixo: '/fila', papeis: ['atendente', 'administrador'] },
  { prefixo: '/admin', papeis: ['administrador'] },
  { prefixo: '/modelo', papeis: ['atendente', 'administrador', 'equipe_tecnica'] },
]

export function podeAcessar(papel, caminho) {
  const area = AREAS.find((a) => caminho === a.prefixo || caminho.startsWith(a.prefixo + '/'))
  return area ? area.papeis.includes(papel) : true
}

// Navegação principal da equipe, por papel.
export const NAVEGACAO = {
  atendente: [{ para: '/fila', rotulo: 'Fila de risco' }, { para: '/modelo', rotulo: 'Modelo' }],
  administrador: [
    { para: '/admin', rotulo: 'Painel', exato: true },
    { para: '/fila', rotulo: 'Fila de risco' },
    { para: '/admin/documentos', rotulo: 'Base de conhecimento' },
    { para: '/modelo', rotulo: 'Modelo' },
  ],
  equipe_tecnica: [{ para: '/modelo', rotulo: 'Modelo de risco' }],
}
