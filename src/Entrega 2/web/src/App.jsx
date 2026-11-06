// Rotas por papel, carregadas sob demanda (o estudante não baixa o código da equipe).
import { lazy, Suspense, useEffect } from 'react'
import { SessaoProvider, useSessao } from './auth/SessaoContext.jsx'
import Login, { destinoDepoisDoLogin } from './auth/Login.jsx'
import FormLogin from './auth/FormLogin.jsx'
import Shell from './componentes/Shell.jsx'
import { Dialogo, EstadoErro, Esqueleto } from './componentes/comum.jsx'
import { casar, Link, navegar, useLocalizacao } from './rotas/roteador.jsx'
import { podeAcessar } from './rotas/permissoes.js'
import { INICIO_POR_PAPEL } from './config.js'
import { useTituloPagina } from './util/hooks.js'

const Chat = lazy(() => import('./paginas/estudante/Chat.jsx'))
const Fila = lazy(() => import('./paginas/atendente/Fila.jsx'))
const Caso = lazy(() => import('./paginas/atendente/Caso.jsx'))
const Painel = lazy(() => import('./paginas/admin/Painel.jsx'))
const Documentos = lazy(() => import('./paginas/admin/Documentos.jsx'))
const Documento = lazy(() => import('./paginas/admin/Documento.jsx'))
const NovoDocumento = lazy(() => import('./paginas/admin/NovoDocumento.jsx'))
const Modelo = lazy(() => import('./paginas/Modelo.jsx'))

// shell: false = a tela desenha a própria moldura (chat em tela cheia).
const ROTAS = [
  { padrao: '/chat', Pagina: Chat, shell: false },
  { padrao: '/chat/:conversaId', Pagina: Chat, shell: false },
  { padrao: '/fila', Pagina: Fila },
  { padrao: '/fila/:estudanteId', Pagina: Caso },
  { padrao: '/admin', Pagina: Painel },
  { padrao: '/admin/documentos', Pagina: Documentos },
  { padrao: '/admin/documentos/novo', Pagina: NovoDocumento },
  { padrao: '/admin/documentos/:documentoId', Pagina: Documento },
  { padrao: '/modelo', Pagina: Modelo },
]

export default function App() {
  return (
    <SessaoProvider>
      <Roteamento />
      <DialogoSessaoExpirada />
    </SessaoProvider>
  )
}

function Redirecionar({ para }) {
  useEffect(() => { navegar(para, { substituir: true }) }, [para])
  return null
}

function CarregandoTela() {
  return <div className="tela-carregando"><Esqueleto linhas={3} rotulo="Carregando a página" /></div>
}

function Roteamento() {
  const sessao = useSessao()
  const { caminho, url } = useLocalizacao()

  if (sessao.status === 'carregando') return <CarregandoTela />
  if (sessao.status === 'erro') {
    return (
      <main className="tela-carregando" id="conteudo">
        <EstadoErro erro={sessao.erro} titulo="Não foi possível abrir sua conta" onTentar={sessao.recarregar} />
      </main>
    )
  }

  if (caminho === '/entrar') {
    if (sessao.status === 'autenticado' && !sessao.recuperandoSenha) {
      return <Redirecionar para={destinoDepoisDoLogin(sessao.me, new URLSearchParams(window.location.search).get('volta'))} />
    }
    return <Login />
  }

  if (sessao.status !== 'autenticado') {
    const volta = caminho === '/' ? '' : `?volta=${encodeURIComponent(url)}`
    return <Redirecionar para={`/entrar${volta}`} />
  }

  const { me } = sessao
  if (caminho === '/') return <Redirecionar para={INICIO_POR_PAPEL[me.papel] ?? '/entrar'} />

  let encontrada = null
  for (const r of ROTAS) {
    const params = casar(r.padrao, caminho)
    if (params) { encontrada = { ...r, params }; break }
  }

  if (!encontrada) return <Moldura shell={me.papel !== 'estudante'}><NaoEncontrada inicio={INICIO_POR_PAPEL[me.papel]} /></Moldura>
  if (!podeAcessar(me.papel, caminho)) return <Moldura shell={me.papel !== 'estudante'}><SemAcesso inicio={INICIO_POR_PAPEL[me.papel]} /></Moldura>

  const { Pagina, params, shell = true } = encontrada
  return (
    <Moldura shell={shell}>
      <Suspense fallback={<Esqueleto linhas={5} rotulo="Carregando a página" />}>
        <Pagina {...params} />
      </Suspense>
    </Moldura>
  )
}

function Moldura({ shell, children }) {
  return shell ? <Shell>{children}</Shell> : <main id="conteudo" className="pagina-solta">{children}</main>
}

function NaoEncontrada({ inicio }) {
  useTituloPagina('Página não encontrada')
  return (
    <div className="estado" role="status">
      <h1 className="estado__titulo">Página não encontrada</h1>
      <p className="estado__texto">O endereço pode ter mudado ou o registro não existe mais.</p>
      <div className="estado__acoes"><Link to={inicio} className="btn btn--primario btn--sm">Ir para o início</Link></div>
    </div>
  )
}

function SemAcesso({ inicio }) {
  useTituloPagina('Sem acesso')
  return (
    <div className="estado" role="status">
      <h1 className="estado__titulo">Seu perfil não tem acesso a esta área</h1>
      <p className="estado__texto">Se você precisa dela para o seu trabalho, peça a liberação à administração do ASA.</p>
      <div className="estado__acoes"><Link to={inicio} className="btn btn--primario btn--sm">Ir para o início</Link></div>
    </div>
  )
}

// Sessão expirada: login por cima da tela atual. O que estava digitado continua na tela.
function DialogoSessaoExpirada() {
  const { reautenticando, me, sair } = useSessao()
  return (
    <Dialogo aberto={reautenticando} titulo="Sua sessão expirou" rotulo="sessao-expirada" fecharComEsc={false}
      descricao="Entre de novo para continuar. O que você estava fazendo continua na tela.">
      <FormLogin emailInicial={me?.email ?? ''} emailFixo={Boolean(me?.email)} textoBotao="Entrar e continuar" />
      <button type="button" className="btn btn--fantasma" style={{ marginTop: 'var(--esp-2)' }}
        onClick={async () => { await sair(); navegar('/entrar', { substituir: true }) }}>
        Sair e entrar com outra conta
      </button>
    </Dialogo>
  )
}
