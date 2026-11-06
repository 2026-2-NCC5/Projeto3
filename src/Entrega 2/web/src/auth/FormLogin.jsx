// Formulário de e-mail e senha, usado na tela de login e no diálogo de sessão expirada.
import { useId, useRef, useState } from 'react'
import { useSessao } from './SessaoContext.jsx'
import { useOnline } from '../util/hooks.js'
import s from './Login.module.css'

const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function FormLogin({ emailInicial = '', emailFixo = false, textoBotao = 'Entrar', onSucesso, onEsqueci }) {
  const { entrar } = useSessao()
  const online = useOnline()
  const [email, setEmail] = useState(emailInicial)
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null) // { campo?: 'email'|'senha', mensagem }
  const id = useId()
  const refEmail = useRef(null)
  const refSenha = useRef(null)

  async function enviar(e) {
    e.preventDefault()
    if (enviando) return
    const em = email.trim()
    if (!EMAIL_VALIDO.test(em)) {
      setErro({ campo: 'email', mensagem: 'Digite um e-mail válido, como nome@edu.fecap.br.' })
      refEmail.current?.focus()
      return
    }
    if (!senha) {
      setErro({ campo: 'senha', mensagem: 'Digite sua senha.' })
      refSenha.current?.focus()
      return
    }
    setErro(null)
    setEnviando(true)
    try {
      const me = await entrar(em, senha)
      onSucesso?.(me)
    } catch (err) {
      setErro({ mensagem: err.mensagem ?? err.message ?? 'Não foi possível entrar agora. Tente de novo.' })
      setSenha('')
      refSenha.current?.focus()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className={s.form} onSubmit={enviar} noValidate>
      {erro && !erro.campo && <p className={s.erroGeral} role="alert">{erro.mensagem}</p>}
      {!online && <p className={s.aviso} role="status">Você está sem conexão. Para entrar, é preciso estar online.</p>}

      <div className="campo">
        <label className="campo__rotulo" htmlFor={`${id}-email`}>E-mail</label>
        <input
          ref={refEmail} id={`${id}-email`} className="input" type="email" inputMode="email" autoComplete="username"
          value={email} onChange={(e) => setEmail(e.target.value)} readOnly={emailFixo}
          aria-invalid={erro?.campo === 'email' || undefined} aria-describedby={erro?.campo === 'email' ? `${id}-email-erro` : undefined}
          placeholder="nome@edu.fecap.br" autoFocus={!emailFixo}
        />
        {erro?.campo === 'email' && <span className="campo__erro" id={`${id}-email-erro`}>{erro.mensagem}</span>}
      </div>

      <div className="campo">
        <label className="campo__rotulo" htmlFor={`${id}-senha`}>Senha</label>
        <div className={s.senhaWrap}>
          <input
            ref={refSenha} id={`${id}-senha`} className="input" type={mostrarSenha ? 'text' : 'password'} autoComplete="current-password"
            value={senha} onChange={(e) => setSenha(e.target.value)} autoFocus={emailFixo}
            aria-invalid={erro?.campo === 'senha' || undefined} aria-describedby={erro?.campo === 'senha' ? `${id}-senha-erro` : undefined}
          />
          <button type="button" className={s.mostrar} onClick={() => setMostrarSenha((m) => !m)} aria-pressed={mostrarSenha}>
            {mostrarSenha ? 'Ocultar' : 'Mostrar'}
          </button>
        </div>
        {erro?.campo === 'senha' && <span className="campo__erro" id={`${id}-senha-erro`}>{erro.mensagem}</span>}
        {onEsqueci && <button type="button" className={s.linkBotao} onClick={() => onEsqueci(email.trim())}>Esqueci a senha</button>}
      </div>

      <button type="submit" className={`btn btn--primario ${s.botao}`} aria-busy={enviando} disabled={!online}>
        {enviando ? <><span className={s.giro} aria-hidden="true" />Entrando…</> : textoBotao}
      </button>
    </form>
  )
}
