// Provedor de autenticação: Supabase Auth (e-mail e senha) ou, no modo mock, os usuários de
// demonstração de seeds/README.md. A mesma interface para os dois.
//
// Armazenamento: o supabase-js guarda a própria sessão (token) no localStorage, como ele
// gerencia por padrão. Nada mais de sessão é gravado. No mock, o token falso fica no
// sessionStorage (some ao fechar a aba).
import { MODO_MOCK, SUPABASE_ANON_KEY, SUPABASE_URL } from '../config.js'

export class ErroLogin extends Error {
  constructor(codigo, mensagem) {
    super(mensagem)
    this.codigo = codigo
  }
}

const MSG = {
  credenciais: 'E-mail ou senha não conferem. Confira e tente de novo.',
  nao_confirmado: 'Este e-mail ainda não foi confirmado. Procure a mensagem de confirmação na sua caixa de entrada.',
  limite: 'Muitas tentativas seguidas. Espere um minuto e tente de novo.',
  rede: 'Sem conexão com o servidor de login. Verifique sua internet e tente de novo.',
  configuracao: 'O login não está configurado neste ambiente (faltam as variáveis do Supabase). Avise a equipe técnica.',
  senha_fraca: 'A senha precisa ter pelo menos 8 caracteres.',
  desconhecido: 'Não foi possível entrar agora. Tente de novo em instantes.',
}

function traduzirErroSupabase(e) {
  const texto = `${e?.message ?? ''} ${e?.code ?? ''}`.toLowerCase()
  if (e?.status === 429 || texto.includes('rate')) return new ErroLogin('limite', MSG.limite)
  if (texto.includes('invalid login') || texto.includes('invalid_credentials')) return new ErroLogin('credenciais', MSG.credenciais)
  if (texto.includes('not confirmed')) return new ErroLogin('nao_confirmado', MSG.nao_confirmado)
  if (texto.includes('password') && texto.includes('least')) return new ErroLogin('senha_fraca', MSG.senha_fraca)
  if (texto.includes('fetch') || texto.includes('network')) return new ErroLogin('rede', MSG.rede)
  return new ErroLogin('desconhecido', MSG.desconhecido)
}

// ------------------------------------------------------------------------ Supabase
let clientePromise = null
function cliente() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return Promise.reject(new ErroLogin('configuracao', MSG.configuracao))
  // Import sob demanda: o supabase-js só é baixado quando o login real é usado.
  clientePromise ??= import('@supabase/supabase-js').then(({ createClient }) =>
    createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } }))
  return clientePromise
}

const supabaseProvedor = {
  async token() {
    try {
      const sb = await cliente()
      const { data } = await sb.auth.getSession()
      return data.session?.access_token ?? null
    } catch { return null }
  },
  async temSessao() { return Boolean(await this.token()) },
  async entrar(email, senha) {
    const sb = await cliente()
    let r
    try { r = await sb.auth.signInWithPassword({ email, password: senha }) } catch (e) { throw traduzirErroSupabase(e) }
    if (r.error) throw traduzirErroSupabase(r.error)
  },
  async sair() {
    try { const sb = await cliente(); await sb.auth.signOut({ scope: 'local' }) } catch { /* já sem sessão */ }
  },
  async recuperarSenha(email) {
    const sb = await cliente()
    const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/entrar?redefinir=1` })
    if (error) throw traduzirErroSupabase(error)
  },
  async definirSenha(senha) {
    const sb = await cliente()
    const { error } = await sb.auth.updateUser({ password: senha })
    if (error) throw traduzirErroSupabase(error)
  },
  // callback(evento): 'saiu' (sessão encerrada/refresh falhou) | 'recuperacao' (link de redefinir senha)
  async ouvir(callback) {
    try {
      const sb = await cliente()
      const { data } = sb.auth.onAuthStateChange((evento) => {
        if (evento === 'SIGNED_OUT') callback('saiu')
        if (evento === 'PASSWORD_RECOVERY') callback('recuperacao')
      })
      return () => data.subscription.unsubscribe()
    } catch { return () => {} }
  },
}

// ---------------------------------------------------------------------------- mock
const CHAVE_MOCK = 'asa:mock-token'
const SENHA_DEMO = 'AsaTurbo#Demo2026'
const espera = (ms) => new Promise((r) => setTimeout(r, ms))

const mockProvedor = {
  async token() {
    const { lerTokenMock } = await import('../api/mock/token.js')
    let t = null
    try { t = sessionStorage.getItem(CHAVE_MOCK) } catch { /* sem storage */ }
    return lerTokenMock(t) ? t : null
  },
  async temSessao() { return Boolean(await this.token()) },
  async entrar(email, senha) {
    await espera(500)
    if (!navigator.onLine) throw new ErroLogin('rede', MSG.rede)
    const [{ USUARIOS }, { criarTokenMock }] = await Promise.all([import('../api/mock/dados.js'), import('../api/mock/token.js')])
    const usuario = Object.values(USUARIOS).find((u) => u.email === email.trim().toLowerCase())
    if (!usuario || senha !== SENHA_DEMO) throw new ErroLogin('credenciais', MSG.credenciais)
    try { sessionStorage.setItem(CHAVE_MOCK, criarTokenMock(usuario.papel)) } catch { /* sem storage */ }
  },
  async sair() { try { sessionStorage.removeItem(CHAVE_MOCK) } catch { /* sem storage */ } },
  async recuperarSenha() { await espera(500) },
  async definirSenha() { await espera(300) },
  async ouvir() { return () => {} },
}

export const provedor = MODO_MOCK ? mockProvedor : supabaseProvedor
export const SENHA_DEMONSTRACAO = MODO_MOCK ? SENHA_DEMO : null
