// Sessão do usuário: quem está logado (GET /me), entrar/sair e sessão expirada.
// Sessão expirada (401 da API ou refresh do Supabase falhou): abre um diálogo de login
// POR CIMA da tela atual. Nada é desmontado, então o que foi digitado continua lá, e a
// chamada que falhou é repetida depois do novo login.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, configurarSessao, ErroApi } from '../api/api.js'
import { provedor } from './provedor.js'
import { limparPreferenciasLocais } from '../util/armazenamento.js'

const SessaoContext = createContext(null)

export function SessaoProvider({ children }) {
  const [estado, setEstado] = useState({ status: 'carregando', me: null, erro: null })
  const [reautenticando, setReautenticando] = useState(false)
  const [recuperandoSenha, setRecuperandoSenha] = useState(false)
  const pendente = useRef(null) // { promessa, resolver, rejeitar }
  const estadoRef = useRef(estado)
  estadoRef.current = estado

  const pedirReautenticacao = useCallback(() => {
    if (estadoRef.current.status !== 'autenticado') return Promise.reject(new ErroApi({ codigo: 'nao_autenticado', mensagem: 'Sessão encerrada.' }))
    if (!pendente.current) {
      let resolver, rejeitar
      const promessa = new Promise((res, rej) => { resolver = res; rejeitar = rej })
      pendente.current = { promessa, resolver, rejeitar }
      setReautenticando(true)
    }
    return pendente.current.promessa
  }, [])

  useEffect(() => {
    configurarSessao({ token: () => provedor.token(), expirou: pedirReautenticacao })
  }, [pedirReautenticacao])

  const carregarMe = useCallback(async () => {
    setEstado((e) => ({ ...e, status: 'carregando', erro: null }))
    if (!(await provedor.temSessao())) {
      setEstado({ status: 'anonimo', me: null, erro: null })
      return null
    }
    try {
      const me = await api.me()
      setEstado({ status: 'autenticado', me, erro: null })
      return me
    } catch (e) {
      if (e.codigo === 'nao_autenticado') {
        await provedor.sair()
        setEstado({ status: 'anonimo', me: null, erro: null })
        return null
      }
      setEstado({ status: 'erro', me: null, erro: e })
      return null
    }
  }, [])

  useEffect(() => { carregarMe() }, [carregarMe])

  useEffect(() => {
    let desligar = () => {}
    provedor.ouvir((evento) => {
      if (evento === 'recuperacao') setRecuperandoSenha(true)
      if (evento === 'saiu' && estadoRef.current.status === 'autenticado' && !saindo.current) pedirReautenticacao().catch(() => {})
    }).then((fn) => { desligar = fn })
    return () => desligar()
  }, [pedirReautenticacao])

  const saindo = useRef(false)

  const entrar = useCallback(async (email, senha, papelDemo = null) => {
    if (papelDemo) await provedor.entrarComo(papelDemo)
    else await provedor.entrar(email, senha)
    const anterior = estadoRef.current.me
    const me = await api.me().catch(async (e) => {
      await provedor.sair()
      throw e
    })
    if (pendente.current) {
      if (anterior && anterior.id !== me.id) {
        // Outra pessoa entrou no lugar: descarta tudo da sessão anterior.
        pendente.current.rejeitar(new ErroApi({ codigo: 'nao_autenticado', mensagem: 'Sessão trocada.' }))
        pendente.current = null
        window.location.assign('/')
        return me
      }
      pendente.current.resolver()
      pendente.current = null
      setReautenticando(false)
    }
    setEstado({ status: 'autenticado', me, erro: null })
    return me
  }, [])

  const sair = useCallback(async () => {
    saindo.current = true
    const me = estadoRef.current.me
    await provedor.sair()
    if (me) limparPreferenciasLocais(me.id)
    if (pendente.current) {
      pendente.current.rejeitar(new ErroApi({ codigo: 'nao_autenticado', mensagem: 'Sessão encerrada.' }))
      pendente.current = null
    }
    setReautenticando(false)
    setEstado({ status: 'anonimo', me: null, erro: null })
    saindo.current = false
  }, [])

  const valor = useMemo(() => ({
    ...estado, reautenticando, recuperandoSenha, encerrarRecuperacao: () => setRecuperandoSenha(false),
    entrar, sair, recarregar: carregarMe,
    recuperarSenha: (email) => provedor.recuperarSenha(email),
    definirSenha: (senha) => provedor.definirSenha(senha),
  }), [estado, reautenticando, recuperandoSenha, entrar, sair, carregarMe])

  return <SessaoContext.Provider value={valor}>{children}</SessaoContext.Provider>
}

export function useSessao() {
  const ctx = useContext(SessaoContext)
  if (!ctx) throw new Error('useSessao fora do SessaoProvider')
  return ctx
}
