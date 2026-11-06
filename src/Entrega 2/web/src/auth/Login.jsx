// Tela de login (/entrar). Depois de entrar, vai para a página pedida (?volta=) ou para a
// página inicial do papel.
import { useEffect, useState } from 'react'
import FormLogin from './FormLogin.jsx'
import { useSessao } from './SessaoContext.jsx'
import { navegar, useLocalizacao } from '../rotas/roteador.jsx'
import { INICIO_POR_PAPEL, MODO_MOCK } from '../config.js'
import { SENHA_DEMONSTRACAO, estadoDemonstracao } from './provedor.js'
import { useTituloPagina } from '../util/hooks.js'
import { podeAcessar } from '../rotas/permissoes.js'
import s from './Login.module.css'

export function destinoDepoisDoLogin(me, volta) {
  if (volta && volta.startsWith('/') && !volta.startsWith('//') && podeAcessar(me.papel, volta.split('?')[0])) return volta
  return INICIO_POR_PAPEL[me.papel] ?? '/'
}

export default function Login() {
  const { busca } = useLocalizacao()
  const sessao = useSessao()
  const [modo, setModo] = useState(busca.get('redefinir') ? 'redefinir' : 'entrar') // entrar | esqueci | enviado | redefinir
  const [emailEsqueci, setEmailEsqueci] = useState('')
  useTituloPagina(modo === 'entrar' ? 'Entrar' : 'Recuperar acesso')

  const modoAtual = sessao.recuperandoSenha ? 'redefinir' : modo

  return (
    <div className={s.pagina}>
      <main className={s.painel} id="conteudo">
        <div className={s.marca}>
          <span className={s.logo}><img src="/marca.png" alt="" /></span>
          <div>
            <p className={s.nome}>ASA Turbo</p>
            <p className={s.subtitulo}>Área do Sucesso Alvarista · FECAP</p>
          </div>
        </div>

        {modoAtual === 'entrar' && (
          <>
            <h1 className={s.titulo}>Entrar</h1>
            <p className={s.texto}>Use o e-mail e a senha da sua conta FECAP.</p>
            <FormLogin
              onSucesso={(me) => navegar(destinoDepoisDoLogin(me, busca.get('volta')), { substituir: true })}
              onEsqueci={(email) => { setEmailEsqueci(email); setModo('esqueci') }}
            />
            {MODO_MOCK && <AjudaDemo />}
            <AcessoDemo onSucesso={(me) => navegar(destinoDepoisDoLogin(me, busca.get('volta')), { substituir: true })} />
          </>
        )}

        {modoAtual === 'esqueci' && (
          <Esqueci emailInicial={emailEsqueci} onVoltar={() => setModo('entrar')} onEnviado={(email) => { setEmailEsqueci(email); setModo('enviado') }} />
        )}

        {modoAtual === 'enviado' && (
          <>
            <h1 className={s.titulo}>Confira seu e-mail</h1>
            <p className={s.texto}>
              Se <strong>{emailEsqueci}</strong> tiver uma conta, você vai receber um link para criar uma senha nova.
              Ele pode levar alguns minutos para chegar; confira também a caixa de spam.
            </p>
            <button type="button" className="btn btn--secundario" onClick={() => setModo('entrar')}>Voltar para o login</button>
          </>
        )}

        {modoAtual === 'redefinir' && <Redefinir onConcluir={() => { sessao.encerrarRecuperacao(); setModo('entrar'); navegar('/entrar', { substituir: true }) }} />}
      </main>
      <p className={s.rodape}>Dúvidas sobre o acesso? Procure a Área do Sucesso Alvarista.</p>
    </div>
  )
}

function Esqueci({ emailInicial, onVoltar, onEnviado }) {
  const { recuperarSenha } = useSessao()
  const [email, setEmail] = useState(emailInicial)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e) {
    e.preventDefault()
    const em = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) { setErro('Digite um e-mail válido, como nome@edu.fecap.br.'); return }
    setErro('')
    setEnviando(true)
    try {
      await recuperarSenha(em)
      onEnviado(em)
    } catch (err) {
      setErro(err.message || 'Não foi possível enviar agora. Tente de novo em instantes.')
    } finally { setEnviando(false) }
  }

  return (
    <>
      <h1 className={s.titulo}>Recuperar acesso</h1>
      <p className={s.texto}>Informe seu e-mail. Enviaremos um link para você criar uma senha nova.</p>
      <form className={s.form} onSubmit={enviar} noValidate>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="esqueci-email">E-mail</label>
          <input id="esqueci-email" className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
            aria-invalid={Boolean(erro) || undefined} aria-describedby={erro ? 'esqueci-erro' : undefined} autoFocus />
          {erro && <span className="campo__erro" id="esqueci-erro" role="alert">{erro}</span>}
        </div>
        <button type="submit" className={`btn btn--primario ${s.botao}`} aria-busy={enviando}>{enviando ? 'Enviando…' : 'Enviar link'}</button>
        <button type="button" className="btn btn--fantasma" onClick={onVoltar}>Voltar para o login</button>
      </form>
    </>
  )
}

function Redefinir({ onConcluir }) {
  const { definirSenha } = useSessao()
  const [senha, setSenha] = useState('')
  const [confirma, setConfirma] = useState('')
  const [erro, setErro] = useState('')
  const [pronto, setPronto] = useState(false)

  async function enviar(e) {
    e.preventDefault()
    if (senha.length < 8) { setErro('A senha precisa ter pelo menos 8 caracteres.'); return }
    if (senha !== confirma) { setErro('As duas senhas não são iguais.'); return }
    setErro('')
    try { await definirSenha(senha); setPronto(true) } catch (err) { setErro(err.message) }
  }

  if (pronto) {
    return (
      <>
        <h1 className={s.titulo}>Senha alterada</h1>
        <p className={s.texto}>Pronto. Use a senha nova para entrar.</p>
        <button type="button" className="btn btn--primario" onClick={onConcluir}>Ir para o login</button>
      </>
    )
  }
  return (
    <>
      <h1 className={s.titulo}>Criar senha nova</h1>
      <form className={s.form} onSubmit={enviar} noValidate>
        {erro && <p className={s.erroGeral} role="alert">{erro}</p>}
        <div className="campo">
          <label className="campo__rotulo" htmlFor="nova-senha">Senha nova</label>
          <input id="nova-senha" className="input" type="password" autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} aria-describedby="nova-senha-ajuda" />
          <span className="campo__ajuda" id="nova-senha-ajuda">Pelo menos 8 caracteres.</span>
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="nova-senha-2">Repita a senha</label>
          <input id="nova-senha-2" className="input" type="password" autoComplete="new-password" value={confirma} onChange={(e) => setConfirma(e.target.value)} />
        </div>
        <button type="submit" className={`btn btn--primario ${s.botao}`}>Salvar senha</button>
      </form>
    </>
  )
}

function AjudaDemo() {
  return (
    <details className={s.demo}>
      <summary>Contas de demonstração</summary>
      <p>Modo de demonstração: os dados são fictícios. Senha de todas: <code>{SENHA_DEMONSTRACAO}</code></p>
      <ul>
        <li><code>estudante.demo@example.com</code> · chat</li>
        <li><code>atendente.demo@example.com</code> · fila de risco</li>
        <li><code>admin.demo@example.com</code> · painel e base</li>
      </ul>
    </details>
  )
}

const ROTULO_PAPEL = { estudante: 'Estudante', atendente: 'Atendente', administrador: 'Administrador' }
const DESCRICAO_PAPEL = { estudante: 'Chat com a base oficial', atendente: 'Fila de risco e casos', administrador: 'Painel e base de conhecimento' }

// Só aparece quando o backend está em DEMO_MODE=true (GET /demo/estado responde).
function AcessoDemo({ onSucesso }) {
  const { entrar } = useSessao()
  const [demo, setDemo] = useState(null)
  const [entrando, setEntrando] = useState(null)
  const [erro, setErro] = useState('')
  useEffect(() => { let vivo = true; estadoDemonstracao().then((d) => vivo && setDemo(d)); return () => { vivo = false } }, [])
  if (!demo) return null

  async function como(papel) {
    setErro('')
    setEntrando(papel)
    try { onSucesso(await entrar(null, null, papel)) } catch (e) { setErro(e.message || 'Não foi possível entrar agora.') } finally { setEntrando(null) }
  }

  return (
    <section className={s.acessoDemo} aria-labelledby="titulo-demo">
      <h2 id="titulo-demo" className={s.acessoDemoTitulo}>Acessar como demonstração</h2>
      <p className={s.acessoDemoTexto}>Dados fictícios. Nenhum dado real de estudante é usado.</p>
      <div className={s.acessoDemoBotoes}>
        {demo.perfis.map((p) => (
          <button key={p.papel} type="button" className={`btn btn--secundario ${s.acessoDemoBotao}`}
            onClick={() => como(p.papel)} disabled={Boolean(entrando)} aria-busy={entrando === p.papel}>
            <span className={s.acessoDemoPapel}>{ROTULO_PAPEL[p.papel] ?? p.papel}</span>
            <span className={s.acessoDemoDescricao}>{entrando === p.papel ? 'Entrando…' : DESCRICAO_PAPEL[p.papel]}</span>
          </button>
        ))}
      </div>
      {erro && <p className={s.erroGeral} role="alert">{erro}</p>}
    </section>
  )
}
