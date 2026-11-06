// Uma mensagem da conversa: pergunta do estudante, resposta do agente (com fontes e feedback),
// abstenção (cartão "Não encontrei isso...") ou mensagem de atendente humano.
import { useEffect, useId, useRef, useState } from 'react'
import TextoFormatado from '../../componentes/TextoFormatado.jsx'
import { IconeAlerta, IconeAtendimento, IconePolegarBaixo, IconePolegarCima } from '../../componentes/Icones.jsx'
import { dataCurta, dataHora, hora } from '../../util/formatar.js'
import s from './Chat.module.css'

export function MensagemEstudante({ m, onTentarDeNovo, desabilitado }) {
  return (
    <li className={s.linhaEstudante}>
      <span className="sr-only">Você:</span>
      <div className={s.bolha}>{m.conteudo}</div>
      {m.estado === 'erro' && <ErroEnvio erro={m.erro} onTentar={() => onTentarDeNovo(m)} desabilitado={desabilitado} />}
      {m.estado !== 'erro' && m.criado_em && <time className={s.hora} dateTime={m.criado_em}>{hora(m.criado_em)}</time>}
    </li>
  )
}

function ErroEnvio({ erro, onTentar, desabilitado }) {
  const offline = erro?.codigo === 'rede'
  const titulo = offline ? 'Sua pergunta não foi enviada' : erro?.codigo === 'limite_excedido' ? 'Muitas mensagens seguidas' : 'Não consegui responder agora'
  const texto = offline
    ? 'Parece que a conexão caiu. Quando voltar, tente de novo.'
    : erro?.codigo === 'limite_excedido'
      ? `Aguarde ${erro.retryAfter ? `${erro.retryAfter} segundos` : 'alguns segundos'} e tente de novo.`
      : erro?.mensagem ?? 'Tente de novo em instantes.'
  return (
    <div className={s.erroEnvio} role="alert">
      <IconeAlerta />
      <div>
        <p><strong>{titulo}.</strong> {texto}</p>
        <button type="button" className="btn btn--secundario btn--sm" onClick={onTentar} disabled={desabilitado}>Tentar de novo</button>
      </div>
    </div>
  )
}

export function MensagemAgente({ m, encaminhamentoConversa, onAvaliar }) {
  const r = m.resposta
  if (m.remetente === 'atendente') {
    return (
      <li className={s.linhaAgente}>
        <p className={s.autorAtendente}><IconeAtendimento /> Atendimento ASA</p>
        <TextoFormatado texto={m.conteudo} />
        <time className={s.hora} dateTime={m.criado_em}>{dataHora(m.criado_em)}</time>
      </li>
    )
  }
  if (r?.abstencao) {
    return (
      <li className={s.linhaAgente}>
        <span className="sr-only">ASA Turbo:</span>
        <Abstencao encaminhamento={r.encaminhamento ?? encaminhamentoConversa} motivo={r.motivo_abstencao} />
      </li>
    )
  }
  return (
    <li className={s.linhaAgente}>
      <span className="sr-only">ASA Turbo:</span>
      <TextoFormatado texto={m.conteudo} />
      {r?.fontes?.length > 0 && <Fontes fontes={r.fontes} />}
      {r?.resposta_id && <Feedback respostaId={r.resposta_id} atual={r.feedback} onAvaliar={onAvaliar} />}
    </li>
  )
}

// Vários trechos do mesmo documento viram UMA fonte (com os trechos juntos),
// para o rodapé não repetir o mesmo título.
function agruparFontes(fontes) {
  const grupos = new Map()
  for (const f of fontes) {
    const chave = f.documento_id ?? `${f.titulo}|${f.fonte}`
    const g = grupos.get(chave)
    if (g) { if (f.trecho) g.trechos.push(f.trecho) } else grupos.set(chave, { ...f, chave, trechos: f.trecho ? [f.trecho] : [] })
  }
  return [...grupos.values()]
}

function Fontes({ fontes }) {
  const grupos = agruparFontes(fontes)
  return (
    <footer className={s.fontes}>
      <p className={s.fontesRotulo}>{grupos.length > 1 ? 'Fontes' : 'Fonte'}</p>
      <ul>
        {grupos.map((f) => (
          <li key={f.chave}>
            <details>
              <summary>
                <span className={s.fonteTitulo}>{f.titulo}</span>
                <span> · {f.fonte}</span>
                <span className={s.fonteData}> · atualizado em {dataCurta(f.data_atualizacao)}</span>
              </summary>
              {f.trechos.map((t, i) => <blockquote key={i} className={s.trecho}>{t}</blockquote>)}
            </details>
          </li>
        ))}
      </ul>
    </footer>
  )
}

function Feedback({ respostaId, atual, onAvaliar }) {
  const [escolha, setEscolha] = useState(atual)
  const [fase, setFase] = useState('inicio') // inicio | comentario | enviado
  const [comentario, setComentario] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const id = useId()

  async function votar(avaliacao) {
    if (enviando) return
    setEnviando(true)
    setErro('')
    const anterior = escolha
    setEscolha(avaliacao)
    try {
      await onAvaliar(respostaId, avaliacao)
      setFase('comentario')
    } catch (e) {
      setEscolha(anterior)
      setErro(e.codigo === 'rede' ? 'Sem conexão. Sua avaliação não foi enviada.' : 'Não foi possível registrar sua avaliação. Tente de novo.')
    } finally { setEnviando(false) }
  }

  async function enviarComentario(e) {
    e.preventDefault()
    if (!comentario.trim()) { setFase('enviado'); return }
    setEnviando(true)
    setErro('')
    try {
      await onAvaliar(respostaId, escolha, comentario.trim().slice(0, 500))
      setFase('enviado')
    } catch {
      setErro('Não foi possível enviar o comentário. Tente de novo.')
    } finally { setEnviando(false) }
  }

  return (
    <div className={s.feedback}>
      <div className={s.feedbackLinha} role="group" aria-label="Esta resposta ajudou?">
        <span className={s.feedbackPergunta}>Ajudou?</span>
        <button type="button" className={s.voto} aria-pressed={escolha === 'util'} onClick={() => votar('util')} disabled={enviando}>
          <IconePolegarCima /> Útil
        </button>
        <button type="button" className={s.voto} aria-pressed={escolha === 'nao_util'} onClick={() => votar('nao_util')} disabled={enviando}>
          <IconePolegarBaixo /> Não útil
        </button>
        {fase === 'enviado' && <span className={s.feedbackOk} role="status">Obrigado, isso ajuda a melhorar as respostas.</span>}
      </div>
      {fase === 'comentario' && (
        <form className={s.comentario} onSubmit={enviarComentario}>
          <label htmlFor={`${id}-c`} className={s.comentarioRotulo}>
            {escolha === 'nao_util' ? 'O que faltou? (opcional)' : 'Quer comentar algo? (opcional)'}
          </label>
          <textarea id={`${id}-c`} className="textarea" rows={2} maxLength={500} value={comentario} onChange={(e) => setComentario(e.target.value)} autoFocus />
          <div className={s.comentarioAcoes}>
            <button type="submit" className="btn btn--secundario btn--sm" disabled={enviando}>Enviar comentário</button>
            <button type="button" className="btn btn--fantasma btn--sm" onClick={() => setFase('enviado')}>Agora não</button>
          </div>
        </form>
      )}
      {erro && <p className="campo__erro" role="alert">{erro}</p>}
    </div>
  )
}

const MOTIVO_TECNICO = new Set(['falha_vetorizacao', 'falha_busca'])

function Abstencao({ encaminhamento, motivo }) {
  const [pediu, setPediu] = useState(false)
  const tecnico = MOTIVO_TECNICO.has(motivo)
  return (
    <div className={s.abstencao}>
      <p className={s.abstencaoTitulo}>Não encontrei isso nos documentos oficiais</p>
      <p>
        {tecnico
          ? 'Não consegui consultar a base de documentos agora, e prefiro não responder sem ela.'
          : 'Prefiro não arriscar uma resposta sem base oficial.'}
        {' '}Uma pessoa da Área do Sucesso Alvarista pode ajudar com isso.
      </p>
      {!pediu ? (
        <button type="button" className="btn btn--primario btn--sm" onClick={() => setPediu(true)}>Falar com o ASA</button>
      ) : (
        <Encaminhado encaminhamento={encaminhamento} />
      )}
    </div>
  )
}
// Recebe o foco ao aparecer, para o leitor de tela anunciar o resultado do pedido.
function Encaminhado({ encaminhamento }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.focus() }, [])
  return (
    <div className={s.encaminhado} role="status" tabIndex={-1} ref={ref}>
      {encaminhamento ? (
        <>
          <p><strong>Pedido enviado ao ASA.</strong> Um atendente vai continuar a partir desta conversa{encaminhamento.prazo ? `, com retorno previsto até ${dataHora(encaminhamento.prazo)}` : ''}.</p>
          <p className="texto-meta">Protocolo <span className="numero">{encaminhamento.id.slice(0, 8).toUpperCase()}</span> · situação: {ROTULO_ENCAMINHAMENTO[encaminhamento.status] ?? encaminhamento.status}</p>
        </>
      ) : (
        <p><strong>Não consegui registrar o pedido agora.</strong> Procure a Área do Sucesso Alvarista pelos canais de atendimento da FECAP.</p>
      )}
    </div>
  )
}
const ROTULO_ENCAMINHAMENTO = { aberto: 'aguardando atendimento', em_andamento: 'em atendimento', resolvido: 'resolvido' }

export function Digitando() {
  return (
    <li className={s.linhaAgente} aria-live="off">
      <span className={s.digitando} role="status">
        <span aria-hidden="true" className={s.pontos}><i /><i /><i /></span>
        <span className="sr-only">Consultando os documentos oficiais</span>
      </span>
    </li>
  )
}
