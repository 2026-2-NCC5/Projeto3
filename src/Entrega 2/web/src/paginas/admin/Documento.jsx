// Documento da base: conteúdo vigente, versões, nova versão e desativação (com confirmação).
import { useEffect, useRef, useState } from 'react'
import { api, erroDoCampo } from '../../api/api.js'
import { Link, useLocalizacao } from '../../rotas/roteador.jsx'
import { Dialogo, EstadoErro, Esqueleto } from '../../componentes/comum.jsx'
import { useCarregar, useOnline, useTituloPagina } from '../../util/hooks.js'
import { dataCurta, dataHora } from '../../util/formatar.js'
import { rotuloCategoriaDoc } from './Documentos.jsx'
import { Campo } from './NovoDocumento.jsx'
import s from './Admin.module.css'

export default function Documento({ documentoId }) {
  const { busca } = useLocalizacao()
  const doc = useCarregar(({ signal }) => api.obterDocumento(documentoId, { signal }), [documentoId])
  const [editando, setEditando] = useState(false)
  const [aviso, setAviso] = useState(busca.get('criado') ? 'Documento cadastrado e disponível para o chat.' : '')
  const [desativando, setDesativando] = useState(false)
  const refAviso = useRef(null)
  useTituloPagina(doc.dados?.titulo ?? 'Documento')
  useEffect(() => { if (aviso) refAviso.current?.focus() }, [aviso])

  const voltar = <Link to="/admin/documentos" className="voltar"><span aria-hidden="true">←</span> Base de conhecimento</Link>
  if (doc.erro && !doc.dados) return <>{voltar}<EstadoErro erro={doc.erro} titulo="Não foi possível abrir o documento" onTentar={doc.erro.codigo === 'nao_encontrado' ? undefined : doc.recarregar} /></>
  if (!doc.dados) return <>{voltar}<Esqueleto linhas={8} rotulo="Carregando o documento" /></>
  const d = doc.dados

  return (
    <>
      {voltar}
      <div className="cabecalho-pagina">
        <div>
          <h1>{d.titulo}</h1>
          <p>{rotuloCategoriaDoc(d.categoria)} · {d.fonte} · versão {d.versao} · atualizado em {dataCurta(d.data_atualizacao)}</p>
        </div>
        {d.ativo && !editando && <button type="button" className="btn btn--primario" onClick={() => { setEditando(true); setAviso('') }}>Publicar nova versão</button>}
      </div>

      {aviso && <div className={s.sucesso} role="status" tabIndex={-1} ref={refAviso} style={{ marginBottom: 'var(--esp-4)' }}>{aviso}</div>}
      {!d.ativo && (
        <div className={s.desativado} role="status">
          <strong>Documento desativado</strong> em {dataHora(d.desativado_em)}. Ele não é mais usado nas respostas do chat.
          {d.motivo_desativacao && <> Motivo: {d.motivo_desativacao}</>}
        </div>
      )}

      <div className={s.docGrade}>
        {editando ? (
          <NovaVersao doc={d} onCancelar={() => setEditando(false)} onPublicado={(novo) => { doc.definir(novo); setEditando(false); setAviso(`Versão ${novo.versao} publicada. As próximas respostas já usam o texto novo.`) }} />
        ) : (
          <section className={`painel ${s.bloco}`} aria-labelledby="t-conteudo">
            <h2 id="t-conteudo" className="rotulo-secao">Conteúdo vigente</h2>
            <div className={s.conteudoDoc} tabIndex={0} aria-label="Conteúdo do documento">{d.conteudo}</div>
            <p className="texto-meta">{d.total_chunks} trechos indexados{d.chunks_sem_embedding > 0 ? ` · ${d.chunks_sem_embedding} aguardando vetorização` : ''}</p>
          </section>
        )}

        <div style={{ display: 'grid', gap: 'var(--esp-4)' }}>
          <section className={`painel ${s.bloco}`} aria-labelledby="t-versoes">
            <h2 id="t-versoes" className="rotulo-secao">Versões</h2>
            <ol className={s.versoes}>
              {d.versoes.map((v) => (
                <li key={v.versao}>
                  <strong>Versão {v.versao}{v.versao === d.versao ? ' (vigente)' : ''}</strong>
                  {v.motivo && <span>{v.motivo}</span>}
                  <span className="texto-meta">Publicada em {dataHora(v.criado_em)}{v.alterado_por ? ` por ${v.alterado_por}` : ''} · vale a partir de {dataCurta(v.data_atualizacao)}</span>
                </li>
              ))}
            </ol>
          </section>

          {d.ativo && (
            <section className={`painel ${s.bloco}`} aria-labelledby="t-desativar">
              <h2 id="t-desativar" className="rotulo-secao">Desativar</h2>
              <p className="texto-meta">O documento deixa de ser usado nas respostas. O histórico e as versões continuam guardados.</p>
              <button type="button" className="btn btn--perigo" onClick={() => setDesativando(true)}>Desativar documento</button>
            </section>
          )}
        </div>
      </div>

      <Desativar aberto={desativando} doc={d} onFechar={() => setDesativando(false)}
        onDesativado={(novo) => { doc.definir(novo); setDesativando(false); setAviso('Documento desativado. Ele não aparece mais nas respostas do chat.') }} />
    </>
  )
}

function NovaVersao({ doc, onCancelar, onPublicado }) {
  const online = useOnline()
  const [c, setC] = useState({ titulo: doc.titulo, fonte: doc.fonte, conteudo: doc.conteudo, motivo: '', data: '' })
  const [erro, setErro] = useState(null)
  const [locais, setLocais] = useState({})
  const [enviando, setEnviando] = useState(false)
  const set = (k) => (e) => setC((x) => ({ ...x, [k]: e.target.value }))
  const msg = (k) => locais[k] ?? erroDoCampo(erro, k)

  async function enviar(e) {
    e.preventDefault()
    const l = {}
    if (c.conteudo.trim().length < 20) l.conteudo = 'O conteúdo precisa ter pelo menos 20 caracteres.'
    if (c.motivo.trim().length < 10) l.motivo = 'Explique o que mudou em pelo menos 10 caracteres.'
    if (c.titulo.trim().length < 3) l.titulo = 'Use pelo menos 3 caracteres.'
    setLocais(l)
    setErro(null)
    if (Object.keys(l).length) { document.getElementById(`nv-${Object.keys(l)[0]}`)?.focus(); return }
    setEnviando(true)
    try {
      const novo = await api.novaVersaoDocumento(doc.id, {
        versao_base: doc.versao, titulo: c.titulo.trim(), fonte: c.fonte.trim(), conteudo: c.conteudo, motivo: c.motivo.trim(),
        ...(c.data ? { data_atualizacao: new Date(`${c.data}T00:00:00Z`).toISOString() } : {}),
      })
      onPublicado(novo)
    } catch (err) { setErro(err) } finally { setEnviando(false) }
  }

  return (
    <form className={`painel ${s.bloco} ${s.form}`} onSubmit={enviar} noValidate aria-labelledby="t-nova">
      <h2 id="t-nova" className="rotulo-secao">Nova versão (a partir da v{doc.versao})</h2>
      <Campo id="nv-titulo" rotulo="Título" erro={msg('titulo')}><input id="nv-titulo" className="input" value={c.titulo} onChange={set('titulo')} maxLength={200} /></Campo>
      <div className={s.form2}>
        <Campo id="nv-fonte" rotulo="Referência oficial" erro={msg('fonte')}><input id="nv-fonte" className="input" value={c.fonte} onChange={set('fonte')} maxLength={300} /></Campo>
        <Campo id="nv-data" rotulo="Data de atualização" ajuda="Vazio = hoje."><input id="nv-data" className="input" type="date" value={c.data} onChange={set('data')} /></Campo>
      </div>
      <Campo id="nv-conteudo" rotulo="Conteúdo" erro={msg('conteudo')}><textarea id="nv-conteudo" className={`textarea ${s.conteudoCampo}`} value={c.conteudo} onChange={set('conteudo')} maxLength={100000} autoFocus /></Campo>
      <Campo id="nv-motivo" rotulo="O que mudou" erro={msg('motivo')} ajuda="Fica registrado no histórico de versões e na auditoria.">
        <input id="nv-motivo" className="input" value={c.motivo} onChange={set('motivo')} maxLength={500} placeholder="Ex.: prazo de rematrícula atualizado para 2027" />
      </Campo>
      {erro && erro.codigo !== 'validacao' && (
        <div className={s.erroForm} role="alert">
          <span>{erro.codigo === 'conflito' ? 'Outra pessoa publicou uma versão enquanto você editava. Copie seu texto, recarregue e aplique de novo.' : erro.codigo === 'indisponivel' ? 'Não foi possível vetorizar a nova versão agora. Nada foi alterado; tente de novo em instantes.' : erro.mensagem}</span>
          {erro.codigo === 'conflito' && <button type="button" className="btn btn--secundario btn--sm" onClick={() => window.location.reload()}>Recarregar documento</button>}
        </div>
      )}
      <div className={s.acoesForm}>
        <button type="submit" className="btn btn--primario" aria-busy={enviando} disabled={enviando || !online}>{enviando ? 'Publicando…' : 'Publicar versão'}</button>
        <button type="button" className="btn btn--secundario" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  )
}

function Desativar({ aberto, doc, onFechar, onDesativado }) {
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  useEffect(() => { if (aberto) { setMotivo(''); setErro('') } }, [aberto])

  async function confirmar(e) {
    e.preventDefault()
    if (motivo.trim().length < 10) { setErro('Explique o motivo em pelo menos 10 caracteres.'); return }
    setEnviando(true)
    try {
      onDesativado(await api.desativarDocumento(doc.id, { motivo: motivo.trim() }))
    } catch (err) {
      setErro(erroDoCampo(err, 'motivo') ?? err.mensagem)
    } finally { setEnviando(false) }
  }

  return (
    <Dialogo aberto={aberto} onFechar={onFechar} titulo="Desativar este documento?" rotulo="desativar-doc"
      descricao={`“${doc.titulo}” deixa de ser usado nas respostas do chat a partir de agora. As versões continuam guardadas.`}>
      <form onSubmit={confirmar} noValidate style={{ display: 'grid', gap: 'var(--esp-4)' }}>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="motivo-desativar">Motivo</label>
          <textarea id="motivo-desativar" className="textarea" value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={500} autoFocus
            aria-invalid={Boolean(erro) || undefined} aria-describedby={erro ? 'motivo-desativar-erro' : 'motivo-desativar-ajuda'} />
          {erro ? <span className="campo__erro" id="motivo-desativar-erro" role="alert">{erro}</span> : <span className="campo__ajuda" id="motivo-desativar-ajuda">Fica registrado na auditoria.</span>}
        </div>
        <div className="dialogo__acoes">
          <button type="button" className="btn btn--secundario" onClick={onFechar}>Cancelar</button>
          <button type="submit" className="btn btn--perigo" aria-busy={enviando} disabled={enviando}>{enviando ? 'Desativando…' : 'Desativar documento'}</button>
        </div>
      </form>
    </Dialogo>
  )
}
