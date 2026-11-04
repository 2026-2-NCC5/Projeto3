// Chat ASA Turbo (estudante): tela cheia, conversas na lateral (gaveta no celular).
import { useEffect, useRef, useState } from 'react'
import { useSessao } from '../../auth/SessaoContext.jsx'
import { Link } from '../../rotas/roteador.jsx'
import { Dialogo, EstadoErro, FaixaOffline } from '../../componentes/comum.jsx'
import { MODO_MOCK } from '../../config.js'
import { useMidia, useOnline, useTituloPagina } from '../../util/hooks.js'
import { dataCurta, iniciais } from '../../util/formatar.js'
import { useChat } from './useChat.js'
import { Digitando, MensagemAgente, MensagemEstudante } from './Mensagem.jsx'
import s from './Chat.module.css'

// Temas reais da base (Cesta de Serviços ASA / Manual do Aluno).
const SUGESTOES = [
  // Validadas contra a base oficial (backend/tests/test_demo.py). A última não está na base:
  // mostra a abstenção com encaminhamento para o ASA.
  { tema: 'Trancamento', pergunta: 'Como faço para trancar a matrícula?' },
  { tema: 'Documentos', pergunta: 'Como emito o atestado de matrícula?' },
  { tema: 'Estágio', pergunta: 'Como funciona o estágio obrigatório?' },
  { tema: 'Atividades', pergunta: 'Como solicito atividades complementares?' },
  { tema: 'Provas', pergunta: 'Perdi uma prova, como faço a prova substitutiva?' },
  { tema: 'Campus', pergunta: 'Qual é o cardápio do restaurante hoje?' },
]

export default function Chat({ conversaId = null }) {
  const { me, sair } = useSessao()
  const chat = useChat(me.id, conversaId)
  const desktop = useMidia('(min-width: 900px)')
  const [gavetaAberta, setGavetaAberta] = useState(false)
  const online = useOnline()
  const { conversa } = chat
  useTituloPagina(conversa.titulo ?? 'Nova conversa')

  useEffect(() => { if (desktop) setGavetaAberta(false) }, [desktop])

  const lateral = (
    <Lateral
      chat={chat} ativaId={conversa.id} me={me} onSair={sair}
      onEscolher={() => setGavetaAberta(false)}
      onFechar={desktop ? null : () => setGavetaAberta(false)}
    />
  )

  return (
    <div className={s.app}>
      <a className="skip-link" href="#campo-pergunta">Pular para a pergunta</a>
      {desktop ? <aside className={s.lateral} aria-label="Conversas">{lateral}</aside> : (
        <Dialogo aberto={gavetaAberta} onFechar={() => setGavetaAberta(false)} titulo="Conversas" rotulo="gaveta" classe="gaveta" tituloOculto>
          {lateral}
        </Dialogo>
      )}

      <section className={s.principal} aria-label="Conversa">
        <header className={s.cabecalho}>
          {!desktop && (
            <button type="button" className={s.botaoIcone} onClick={() => setGavetaAberta(true)} aria-label="Abrir conversas" aria-expanded={gavetaAberta}>
              <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
            </button>
          )}
          <div className={s.titulos}>
            <h1 className={s.tituloConversa}>{conversa.id ? (conversa.titulo ?? 'Conversa') : 'Nova conversa'}</h1>
            {conversa.status === 'encaminhada_humano' && <p className={s.subtitulo}>Encaminhada ao ASA</p>}
          </div>
          {MODO_MOCK && <span className={s.etiquetaDemo} title="Dados fictícios, sem backend">Demonstração</span>}
          {!desktop && conversa.id && (
            <Link to="/chat" className={s.botaoIcone} aria-label="Nova conversa">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18"><path d="M9 3.5v11M3.5 9h11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
            </Link>
          )}
        </header>
        <FaixaOffline />

        <Conversa chat={chat} />

        <Composer key={conversa.id ?? 'nova'} onEnviar={chat.enviar} enviando={chat.enviando} online={online} />
      </section>
    </div>
  )
}

// ----------------------------------------------------------------------- lateral
function Lateral({ chat, ativaId, me, onSair, onEscolher, onFechar }) {
  const { lista } = chat
  const [editando, setEditando] = useState(null)
  const [excluindo, setExcluindo] = useState(null)

  return (
    <div className={s.lateralConteudo}>
      <div className={s.marca}>
        <span className={s.logo}><img src="/marca.png" alt="" /></span>
        <div>
          <p className={s.nomeMarca}>ASA Turbo</p>
          <p className={s.subMarca}>Área do Sucesso Alvarista</p>
        </div>
        {onFechar && (
          <button type="button" className={s.fecharGaveta} onClick={onFechar} aria-label="Fechar conversas">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18"><path d="M4.5 4.5l9 9M13.5 4.5l-9 9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          </button>
        )}
      </div>

      <Link to="/chat" className={s.nova} onClick={onEscolher} aria-current={!ativaId ? 'page' : undefined}>
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        Nova conversa
      </Link>

      <nav className={s.lista} aria-label="Conversas anteriores">
        <h2 className={s.grupoTitulo}>Conversas</h2>
        {lista.carregando && lista.itens.length === 0 && (
          <div className={s.listaEsqueleto} aria-busy="true"><span className="sr-only">Carregando conversas</span>{[0, 1, 2].map((i) => <span key={i} className="esqueleto" />)}</div>
        )}
        {lista.erro && (
          <div className={s.listaErro} role="alert">
            <p>Não foi possível carregar suas conversas.</p>
            <button type="button" className={s.linkClaro} onClick={chat.recarregarLista}>Tentar de novo</button>
          </div>
        )}
        {!lista.carregando && !lista.erro && lista.itens.length === 0 && <p className={s.listaVazia}>Suas conversas aparecem aqui depois da primeira pergunta.</p>}
        <ul>
          {lista.itens.map((c) => (
            <li key={c.id} className={s.item}>
              {editando === c.id ? (
                <Renomear titulo={c.titulo} onSalvar={(t) => { chat.renomear(c.id, t); setEditando(null) }} onCancelar={() => setEditando(null)} />
              ) : (
                <>
                  <Link to={`/chat/${c.id}`} className={s.itemLink} aria-current={c.id === ativaId ? 'page' : undefined} onClick={onEscolher} title={c.titulo}>
                    <span className={s.itemTitulo}>{c.titulo}</span>
                    <span className={s.itemMeta}>{dataCurta(c.atualizada_em)}{c.status === 'encaminhada_humano' ? ' · com o ASA' : ''}</span>
                  </Link>
                  <MenuItem titulo={c.titulo} onRenomear={() => setEditando(c.id)} onExcluir={() => setExcluindo(c)} />
                </>
              )}
            </li>
          ))}
        </ul>
      </nav>

      <div className={s.usuario}>
        <span className={s.avatar} aria-hidden="true">{iniciais(me.nome)}</span>
        <div className={s.usuarioTexto}>
          <span>{me.nome}</span>
          {me.estudante && <span className={s.usuarioMeta}>RA {me.estudante.ra} · {me.estudante.curso}</span>}
        </div>
        <button type="button" className={s.sair} onClick={onSair}>Sair</button>
      </div>

      <Dialogo aberto={Boolean(excluindo)} onFechar={() => setExcluindo(null)} titulo="Excluir esta conversa?" rotulo="excluir-conversa"
        descricao="Ela sai da sua lista neste navegador. O registro do atendimento continua guardado pelo ASA.">
        <p className={s.dialogoNome}>{excluindo?.titulo}</p>
        <div className="dialogo__acoes">
          <button type="button" className="btn btn--secundario" onClick={() => setExcluindo(null)}>Cancelar</button>
          <button type="button" className="btn btn--perigo" onClick={() => { chat.excluir(excluindo.id); setExcluindo(null) }}>Excluir da lista</button>
        </div>
      </Dialogo>
    </div>
  )
}

function MenuItem({ titulo, onRenomear, onExcluir }) {
  const [aberto, setAberto] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!aberto) return
    const fora = (e) => { if (!ref.current?.contains(e.target)) setAberto(false) }
    const esc = (e) => { if (e.key === 'Escape') { setAberto(false); ref.current?.querySelector('button')?.focus() } }
    document.addEventListener('pointerdown', fora)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('pointerdown', fora); document.removeEventListener('keydown', esc) }
  }, [aberto])
  return (
    <div className={s.menuItem} ref={ref}>
      <button type="button" className={s.menuBotao} aria-label={`Opções da conversa ${titulo}`} aria-expanded={aberto} onClick={() => setAberto((a) => !a)}>
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><circle cx="3.5" cy="8" r="1.3" fill="currentColor" /><circle cx="8" cy="8" r="1.3" fill="currentColor" /><circle cx="12.5" cy="8" r="1.3" fill="currentColor" /></svg>
      </button>
      {aberto && (
        <div className={s.menu}>
          <button type="button" onClick={() => { setAberto(false); onRenomear() }} autoFocus>Renomear</button>
          <button type="button" onClick={() => { setAberto(false); onExcluir() }}>Excluir da lista</button>
        </div>
      )}
    </div>
  )
}

function Renomear({ titulo, onSalvar, onCancelar }) {
  const [valor, setValor] = useState(titulo)
  return (
    <form className={s.renomear} onSubmit={(e) => { e.preventDefault(); onSalvar(valor) }}>
      <label className="sr-only" htmlFor="renomear-conversa">Novo nome da conversa</label>
      <input id="renomear-conversa" className="input" value={valor} maxLength={80} autoFocus onChange={(e) => setValor(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); onCancelar() } }} onFocus={(e) => e.target.select()} />
      <div className={s.renomearAcoes}>
        <button type="submit" className={s.linkClaro}>Salvar</button>
        <button type="button" className={s.linkClaro} onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------- conversa
function Conversa({ chat }) {
  const { conversa, enviando } = chat
  const fim = useRef(null)
  const rolagem = useRef(null)
  const total = conversa.mensagens.length

  useEffect(() => {
    const reduzir = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    fim.current?.scrollIntoView({ block: 'end', behavior: reduzir || total < 3 ? 'auto' : 'smooth' })
  }, [total, enviando, conversa.id])

  if (conversa.carregando) {
    return (
      <div className={s.rolagem}><div className={s.coluna}>
        <div className={s.esqueletoConversa} aria-busy="true"><span className="sr-only">Carregando a conversa</span>
          <span className="esqueleto" style={{ width: '45%', marginLeft: 'auto' }} /><span className="esqueleto" /><span className="esqueleto" style={{ width: '80%' }} /><span className="esqueleto" style={{ width: '60%' }} />
        </div>
      </div></div>
    )
  }
  if (conversa.erro) {
    return (
      <div className={s.rolagem}><div className={s.coluna}>
        <EstadoErro erro={conversa.erro} titulo={conversa.erro.codigo === 'nao_encontrado' ? 'Conversa não encontrada' : 'Não foi possível abrir a conversa'}
          onTentar={conversa.erro.codigo === 'nao_encontrado' ? undefined : chat.reabrir}>
          {conversa.erro.codigo === 'nao_encontrado' && <div className="estado__acoes"><Link to="/chat" className="btn btn--primario btn--sm">Começar uma conversa nova</Link></div>}
        </EstadoErro>
      </div></div>
    )
  }

  if (total === 0) {
    return (
      <div className={s.rolagem} ref={rolagem}>
        <div className={`${s.coluna} ${s.boasVindas}`}>
          <h2 className={s.boasVindasTitulo}>Como posso ajudar hoje?</h2>
          <p className={s.boasVindasTexto}>Respondo com base nos documentos oficiais do ASA e mostro de onde veio cada informação. Quando não encontro, encaminho para uma pessoa da equipe.</p>
          <h3 className="rotulo-secao">Perguntas frequentes</h3>
          <ul className={s.sugestoes}>
            {SUGESTOES.map((x) => (
              <li key={x.pergunta}>
                <button type="button" className={s.sugestao} onClick={() => chat.enviar(x.pergunta)} disabled={enviando}>
                  <span className={s.sugestaoTema}>{x.tema}</span>
                  <span>{x.pergunta}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  const pendente = conversa.mensagens.some((m) => m.estado === 'pendente')
  return (
    <div className={s.rolagem} ref={rolagem}>
      {/* role="log" num wrapper: no próprio <ol> ele apagaria a semântica de lista dos <li> */}
      <div role="log" aria-live="polite" aria-relevant="additions" aria-label="Mensagens">
      <ol className={s.coluna}>
        {conversa.mensagens.map((m) => (m.remetente === 'estudante'
          ? <MensagemEstudante key={m.id} m={m} onTentarDeNovo={chat.tentarDeNovo} desabilitado={enviando} />
          : <MensagemAgente key={m.id} m={m} encaminhamentoConversa={conversa.encaminhamento} onAvaliar={chat.avaliar} />))}
        {pendente && <Digitando />}
        <li ref={fim} aria-hidden="true" className={s.fim} />
      </ol>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------- composer
const ALTURA_MAX = 160

function Composer({ onEnviar, enviando, online }) {
  const [texto, setTexto] = useState('')
  const campo = useRef(null)
  const enviandoAntes = useRef(enviando)

  useEffect(() => {
    const el = campo.current
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, ALTURA_MAX) + 'px'
  }, [texto])

  useEffect(() => {
    if (enviandoAntes.current && !enviando && window.matchMedia('(pointer: fine)').matches) campo.current?.focus()
    enviandoAntes.current = enviando
  }, [enviando])

  function enviar(e) {
    e?.preventDefault()
    if (!online) return
    if (onEnviar(texto)) setTexto('')
  }

  const podeEnviar = texto.trim().length > 0 && !enviando && online
  const restante = 1000 - texto.length

  return (
    <form className={s.composerWrap} onSubmit={enviar}>
      <div className={s.composer}>
        <label htmlFor="campo-pergunta" className="sr-only">Sua pergunta</label>
        <textarea
          id="campo-pergunta" ref={campo} rows={1} value={texto} maxLength={1000}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) enviar(e) }}
          placeholder="Pergunte sobre rematrícula, documentos, prazos…"
          className={s.campo}
          aria-describedby="dica-composer"
        />
        <button type="submit" className={s.enviar} disabled={!podeEnviar} aria-label="Enviar pergunta" aria-busy={enviando}>
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20"><path d="M10 15.5v-11M5 9.5l5-5 5 5" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
      <p className={s.dica} id="dica-composer">
        {!online ? 'Sem conexão: você pode escrever, e envia quando a internet voltar.'
          : restante < 100 ? `${restante} caracteres restantes.`
            : <>Respostas a partir dos documentos oficiais da FECAP.<span className={s.atalhos}> Enter envia, Shift+Enter pula linha.</span></>}
      </p>
    </form>
  )
}

