// Configuração do front. Tudo aqui é PÚBLICO (vai para o JavaScript do navegador).
// Nunca coloque segredo em variável VITE_*.

const env = import.meta.env

// Modo mock: o cliente da API (src/api/cliente.js) responde com dados fictícios fiéis ao
// contrato (docs/api-contract.yaml), e o login aceita os 3 usuários de demonstração sem Supabase.
// Padrão: ligado em `npm run dev`, desligado no build. Force com VITE_API_MOCK=true|false.
// Em dev também dá para alternar pela URL: ?mock=1 ou ?mock=0 (vale até fechar a aba).
function lerModoMock() {
  if (env.DEV && typeof window !== 'undefined') {
    const p = new URLSearchParams(window.location.search).get('mock')
    try {
      if (p === '1' || p === '0') sessionStorage.setItem('asa:mock', p)
      const salvo = sessionStorage.getItem('asa:mock')
      if (salvo) return salvo === '1'
    } catch { /* sem storage: segue a variável de ambiente */ }
  }
  if (env.VITE_API_MOCK === 'true') return true
  if (env.VITE_API_MOCK === 'false') return false
  return Boolean(env.DEV)
}

export const MODO_MOCK = lerModoMock()

// Base da API FastAPI (sem barra no fim). Vazio = mesma origem (/me, /chat...).
export const API_BASE = (env.VITE_API_BASE_URL || '').replace(/\/$/, '')

// Supabase Auth: a chave anon é pública por definição; o acesso real é controlado pelo backend.
export const SUPABASE_URL = env.VITE_SUPABASE_URL || ''
export const SUPABASE_ANON_KEY = env.VITE_SUPABASE_ANON_KEY || ''

export const TIMEOUT_MS = 25000

// Página inicial de cada papel.
export const INICIO_POR_PAPEL = {
  estudante: '/chat',
  atendente: '/fila',
  administrador: '/admin',
  equipe_tecnica: '/modelo',
}
