// Detalhe do caso: score geral e por dimensão, tendência de 6 meses, fatores, recomendação,
// validação humana (confirmar/ajustar/rejeitar com justificativa) e linha do tempo.
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/api.js'
import { Link, useLocalizacao } from '../../rotas/roteador.jsx'
import { BadgeRisco, EstadoErro, Esqueleto } from '../../componentes/comum.jsx'
import { GraficoTendencia, Medidor } from '../../componentes/graficos.jsx'
import { useCarregar, useOnline, useTituloPagina } from '../../util/hooks.js'
import { ROTULO, dataCurta, dataHora, mesAbreviado, mesAno, pct } from '../../util/formatar.js'
import { AvisoDecisao, Tendencia } from './pecas.jsx'
import s from './Caso.module.css'

export default function Caso({ estudanteId }) {
  const { busca } = useLocalizacao()
  const volta = busca.get('volta')?.startsWith('/fila') ? busca.get('volta') : '/fila'
  const caso = useCarregar(({ signal }) => api.obterCaso(estudanteId, { signal }), [estudanteId])
  const [versaoHistorico, setVersaoHistorico] = useState(0)
  useTituloPagina(caso.dados ? caso.dados.estudante.nome : 'Caso')

  const voltar = <Link to={volta} className="voltar"><span aria-hidden="true">←</span> Fila de risco</Link>

  if (caso.erro && !caso.dados) {
    return (
      <>
        {voltar}
        <EstadoErro erro={caso.erro} titulo={caso.erro.codigo === 'nao_encontrado' ? 'Estudante não encontrado' : 'Não foi possível abrir o caso'}
          onTentar={caso.erro.codigo === 'nao_encontrado' ? undefined : caso.recarregar} />
      </>
    )
  }
  if (!caso.dados) return <>{voltar}<Esqueleto linhas={8} rotulo="Carregando o caso" /></>

  const d = caso.dados
  const e = d.estudante
  const tendenciaGeral = d.tendencia.length > 1 ? d.tendencia.at(-1).score_geral - d.tendencia.at(-2).score_geral : null
  const sentido = tendenciaGeral === null ? 'estavel' : tendenciaGeral > 0.02 ? 'subindo' : tendenciaGeral < -0.02 ? 'caindo' : 'estavel'

  return (
    <>
      {voltar}
      <header className={s.cabecalho}>
        <div>
          <h1>{e.nome}</h1>
          <p className={s.meta}>
            RA <span className="numero">{e.ra}</span> · {e.curso} · {e.semestre}º semestre
            {e.regiao && <> · {e.regiao}{e.faixa_distancia ? ` (${ROTULO.faixa[e.faixa_distancia]} do campus)` : ''}</>}
          </p>
        </div>
        <div className={s.situacao}>
          <span className="etiqueta">{ROTULO.status[d.caso.status]}</span>
          <span className="etiqueta">Prioridade {ROTULO.prioridade[d.caso.prioridade].toLowerCase()}</span>
          {d.caso.prazo && <span className="etiqueta">Prazo {dataCurta(d.caso.prazo)}</span>}
          <span className="etiqueta">{d.caso.responsavel ? `Com ${d.caso.responsavel.nome}` : 'Sem responsável'}</span>
        </div>
      </header>

      <div className={s.avisoFixo}><AvisoDecisao texto={d.aviso} /></div>

      <div className={s.grade}>
        <div className={s.colunaPrincipal}>
          <section className={`painel ${s.bloco}`} aria-labelledby="t-score">
            <h2 id="t-score" className="rotulo-secao">Risco de evasão</h2>
            <div className={s.score}>
              <strong className={s.scoreValor}>{pct(d.score.geral)}</strong>
              <div className={s.scoreLado}>
                <BadgeRisco categoria={d.categoria} />
                {d.categoria !== d.categoria_modelo && <span className="texto-meta">Ajustada por atendente · modelo indicou {ROTULO.categoria[d.categoria_modelo]}</span>}
                <Tendencia tendencia={sentido} variacao={tendenciaGeral} />
              </div>
            </div>
            <dl className={s.dimensoes}>
              {[['financeiro', 'Financeira'], ['academico', 'Acadêmica'], ['relacionamento', 'Relacionamento']].map(([k, r]) => (
                <div key={k} className={s.dimensao}>
                  <dt>{r}</dt>
                  <dd><Medidor valor={d.score[k]} rotulo={`${r}: ${pct(d.score[k])}`} /><span className="numero">{pct(d.score[k])}</span></dd>
                </div>
              ))}
            </dl>
            <p className="texto-meta">Modelo <span className="numero">{d.versao_modelo}</span> · calculado em {dataHora(d.atualizado_em)}</p>
          </section>

          <section className={`painel ${s.bloco}`} aria-labelledby="t-tendencia">
            <h2 id="t-tendencia" className="rotulo-secao">Tendência dos últimos 6 meses</h2>
            <GraficoTendencia titulo="Score geral por mês"
              pontos={d.tendencia.map((p) => ({ rotulo: mesAbreviado(p.competencia), rotuloLongo: mesAno(p.competencia), valor: p.score_geral, categoria: p.categoria }))} />
          </section>

          <section className={`painel ${s.bloco}`} aria-labelledby="t-fatores">
            <h2 id="t-fatores" className="rotulo-secao">O que mais pesou</h2>
            <div className={s.fatores}>
              <ListaFatores titulo="Aumentam o risco" fatores={d.fatores.filter((f) => f.direcao === 'aumenta')} classe={s.aumenta} vazio="Nenhum fator relevante aumentando o risco." />
              <ListaFatores titulo="Reduzem o risco" fatores={d.fatores.filter((f) => f.direcao === 'reduz')} classe={s.reduz} vazio="Nenhum fator relevante reduzindo o risco." />
            </div>
            <p className="texto-meta">As barras mostram o peso relativo de cada fator neste score. Dados pessoais sensíveis nunca entram como fator.</p>
          </section>
        </div>

        <div className={s.colunaLateral}>
          <section className={`${s.bloco} ${s.recomendacao}`} aria-labelledby="t-rec">
            <h2 id="t-rec" className="rotulo-secao">Recomendação sugerida</h2>
            <p>{d.recomendacao}</p>
          </section>

          <Validacao caso={d} estudanteId={estudanteId}
            onValidado={() => { caso.recarregar(); setVersaoHistorico((v) => v + 1) }} onRecarregar={caso.recarregar} />

          <Historico estudanteId={estudanteId} versao={versaoHistorico} />
        </div>
      </div>
    </>
  )
}

function ListaFatores({ titulo, fatores, classe, vazio }) {
  const maior = Math.max(0.01, ...fatores.map((f) => f.peso))
  return (
    <div>
      <h3 className={s.fatoresTitulo}>{titulo}</h3>
      {fatores.length === 0 ? <p className="texto-meta">{vazio}</p> : (
        <ul className={s.listaFatores}>
          {fatores.map((f) => (
            <li key={f.codigo}>
              <span className={s.fatorTexto}>{f.descricao}</span>
              <span className={s.fatorDimensao}>{ROTULO.dimensao[f.dimensao]}</span>
              <span className={s.fatorBarra}><span className={classe} style={{ width: `${(f.peso / maior) * 100}%` }} /></span>
              <span className={`numero ${s.fatorPeso}`}>{Math.round(f.peso * 100)}%</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ validação humana
const DECISOES = [
  { valor: 'confirmado', titulo: 'Confirmar', texto: 'Concordo com a faixa indicada.' },
  { valor: 'ajustado', titulo: 'Ajustar', texto: 'A faixa deveria ser outra.' },
  { valor: 'rejeitado', titulo: 'Rejeitar', texto: 'O alerta não procede. O caso é arquivado.' },
]

function Validacao({ caso, estudanteId, onValidado, onRecarregar }) {
  const online = useOnline()
  const [decisao, setDecisao] = useState('')
  const [categoria, setCategoria] = useState('')
  const [justificativa, setJustificativa] = useState('')
  const [prioridade, setPrioridade] = useState('')
  const [prazo, setPrazo] = useState('')
  const [assumir, setAssumir] = useState(true)
  const [erro, setErro] = useState(null)
  const [errosCampo, setErrosCampo] = useState({})
  const [enviando, setEnviando] = useState(false)
  const [sucesso, setSucesso] = useState(null)
  const refSucesso = useRef(null)
  const refJust = useRef(null)

  useEffect(() => { if (sucesso) refSucesso.current?.focus() }, [sucesso])

  async function enviar(e) {
    e.preventDefault()
    const novos = {}
    if (!decisao) novos.decisao = 'Escolha confirmar, ajustar ou rejeitar.'
    if (decisao === 'ajustado' && !categoria) novos.categoria_ajustada = 'Escolha a nova faixa.'
    if (justificativa.trim().length < 20) novos.justificativa = `Explique a decisão em pelo menos 20 caracteres (faltam ${20 - justificativa.trim().length}).`
    setErrosCampo(novos)
    setErro(null)
    if (Object.keys(novos).length) {
      document.getElementById(novos.decisao ? 'val-decisao-confirmado' : novos.categoria_ajustada ? 'val-categoria' : 'val-just')?.focus()
      return
    }
    setEnviando(true)
    try {
      const v = await api.validarCaso(estudanteId, {
        score_id: caso.score_id, decisao, justificativa: justificativa.trim(),
        categoria_ajustada: decisao === 'ajustado' ? categoria : null,
        prioridade: prioridade || null, prazo: prazo || null, assumir_caso: assumir,
      })
      setSucesso(v)
      setDecisao(''); setCategoria(''); setJustificativa(''); setPrioridade(''); setPrazo('')
      onValidado()
    } catch (err) {
      if (err.codigo === 'validacao') {
        setErrosCampo(Object.fromEntries(err.detalhes.map((x) => [x.campo, x.mensagem])))
        refJust.current?.focus()
      }
      setErro(err)
    } finally { setEnviando(false) }
  }

  const ultima = caso.ultima_validacao
  return (
    <section className={`painel ${s.bloco}`} aria-labelledby="t-val">
      <h2 id="t-val" className="rotulo-secao">Sua avaliação</h2>
      {ultima && (
        <p className={s.ultima}>
          Última: <strong>{ROTULO.decisao[ultima.decisao]}</strong>{ultima.categoria_ajustada ? ` para ${ROTULO.categoria[ultima.categoria_ajustada]}` : ''} por {ultima.atendente.nome} em {dataCurta(ultima.criado_em)}.
        </p>
      )}
      {sucesso && (
        <div className={s.sucesso} role="status" tabIndex={-1} ref={refSucesso}>
          <strong>Avaliação registrada.</strong> {ROTULO.decisao[sucesso.decisao]} em {dataHora(sucesso.criado_em)}, com o modelo {sucesso.versao_modelo}. Já está na linha do tempo do caso.
        </div>
      )}
      <form className={s.form} onSubmit={enviar} noValidate>
        <fieldset className="opcoes" aria-describedby={errosCampo.decisao ? 'val-decisao-erro' : undefined}>
          <legend>Decisão sobre a faixa {ROTULO.categoria[caso.categoria_modelo]} ({pct(caso.score.geral)})</legend>
          {DECISOES.map((o) => (
            <label key={o.valor} className="opcao">
              <input type="radio" name="decisao" id={`val-decisao-${o.valor}`} value={o.valor} checked={decisao === o.valor} onChange={() => setDecisao(o.valor)} />
              <strong>{o.titulo}</strong>
              <span>{o.texto}</span>
            </label>
          ))}
          {errosCampo.decisao && <span className="campo__erro" id="val-decisao-erro">{errosCampo.decisao}</span>}
        </fieldset>

        {decisao === 'ajustado' && (
          <div className="campo">
            <label className="campo__rotulo" htmlFor="val-categoria">Nova faixa</label>
            <select id="val-categoria" className="select" value={categoria} onChange={(e) => setCategoria(e.target.value)}
              aria-invalid={Boolean(errosCampo.categoria_ajustada) || undefined} aria-describedby={errosCampo.categoria_ajustada ? 'val-categoria-erro' : undefined}>
              <option value="">Escolha</option>
              {['verde', 'amarelo', 'vermelho'].filter((c) => c !== caso.categoria_modelo).map((c) => <option key={c} value={c}>{ROTULO.categoria[c]}</option>)}
            </select>
            {errosCampo.categoria_ajustada && <span className="campo__erro" id="val-categoria-erro">{errosCampo.categoria_ajustada}</span>}
          </div>
        )}

        <div className="campo">
          <label className="campo__rotulo" htmlFor="val-just">Justificativa</label>
          <textarea id="val-just" ref={refJust} className="textarea" value={justificativa} onChange={(e) => setJustificativa(e.target.value)} maxLength={2000}
            aria-invalid={Boolean(errosCampo.justificativa) || undefined} aria-describedby={`val-just-ajuda${errosCampo.justificativa ? ' val-just-erro' : ''}`}
            placeholder={decisao === 'rejeitado' ? 'Ex.: conversei com o estudante; as parcelas em aberto já foram negociadas.' : 'O que você observou ou conversou com o estudante?'} />
          <span className="campo__ajuda" id="val-just-ajuda">Obrigatória, mínimo de 20 caracteres. Fica no histórico do caso e na auditoria.</span>
          {errosCampo.justificativa && <span className="campo__erro" id="val-just-erro">{errosCampo.justificativa}</span>}
        </div>

        <details className={s.extras}>
          <summary>Prioridade, prazo e responsável</summary>
          <div className={s.extrasCampos}>
            <div className="campo">
              <label className="campo__rotulo" htmlFor="val-pri">Prioridade</label>
              <select id="val-pri" className="select" value={prioridade} onChange={(e) => setPrioridade(e.target.value)}>
                <option value="">Manter ({ROTULO.prioridade[caso.caso.prioridade]})</option>
                {Object.entries(ROTULO.prioridade).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
              </select>
            </div>
            <div className="campo">
              <label className="campo__rotulo" htmlFor="val-prazo">Prazo do próximo contato</label>
              <input id="val-prazo" className="input" type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
            </div>
          </div>
          <label className={s.check}><input type="checkbox" checked={assumir} onChange={(e) => setAssumir(e.target.checked)} /> Assumir este caso</label>
        </details>

        {erro && erro.codigo !== 'validacao' && (
          <div className={s.erroForm} role="alert">
            <p>{erro.codigo === 'conflito' ? erro.mensagem : erro.codigo === 'rede' ? 'Sem conexão. Sua avaliação não foi enviada; o texto continua aqui.' : erro.mensagem}</p>
            {erro.codigo === 'conflito' && <button type="button" className="btn btn--secundario btn--sm" onClick={() => { setErro(null); onRecarregar() }}>Recarregar o score</button>}
          </div>
        )}

        <button type="submit" className="btn btn--primario" aria-busy={enviando} disabled={enviando || !online}>
          {enviando ? 'Registrando…' : 'Registrar avaliação'}
        </button>
        {!online && <p className="texto-meta">Sem conexão. Você pode continuar escrevendo e registrar quando a internet voltar.</p>}
      </form>
    </section>
  )
}

// ------------------------------------------------------------------ linha do tempo
const POR_PAGINA_HIST = 8

function Historico({ estudanteId, versao }) {
  const [paginas, setPaginas] = useState(1)
  const h = useCarregar(({ signal }) => api.historicoCaso(estudanteId, { pagina: 1, por_pagina: POR_PAGINA_HIST * paginas }, { signal }), [estudanteId, versao, paginas])
  return (
    <section className={`painel ${s.bloco}`} aria-labelledby="t-hist">
      <h2 id="t-hist" className="rotulo-secao">Histórico do caso</h2>
      {h.erro && !h.dados ? <EstadoErro erro={h.erro} titulo="Não foi possível carregar o histórico" onTentar={h.recarregar} />
        : !h.dados ? <Esqueleto linhas={4} rotulo="Carregando o histórico" />
          : h.dados.itens.length === 0 ? <p className="texto-meta">Nada registrado ainda.</p> : (
            <>
              <ol className={s.linhaTempo}>
                {h.dados.itens.map((ev) => (
                  <li key={ev.id} className={s[`ev_${ev.tipo}`]}>
                    <p className={s.evTexto}>{ev.descricao}</p>
                    {ev.tipo === 'validacao' && ev.dados?.justificativa && <p className={s.evJust}>“{ev.dados.justificativa}”</p>}
                    {ev.tipo === 'contato' && ev.dados?.resultado && <p className={s.evJust}>{ev.dados.resultado}</p>}
                    {['status', 'prioridade'].includes(ev.tipo) && ev.dados && <p className={s.evJust}>{rotuloMudanca(ev)}</p>}
                    <p className="texto-meta"><time dateTime={ev.ocorrido_em}>{dataHora(ev.ocorrido_em)}</time>{ev.usuario ? ` · ${ev.usuario.nome}` : ' · sistema'}{ev.tipo === 'score' && ev.dados?.versao_modelo ? ` · ${ev.dados.versao_modelo}` : ''}</p>
                  </li>
                ))}
              </ol>
              {h.dados.total > h.dados.itens.length && (
                <button type="button" className="btn btn--fantasma btn--sm" onClick={() => setPaginas((p) => p + 1)} aria-busy={h.carregando}>
                  {h.carregando ? 'Carregando…' : `Ver mais (${h.dados.total - h.dados.itens.length})`}
                </button>
              )}
            </>
          )}
    </section>
  )
}

function rotuloMudanca(ev) {
  const mapa = ev.tipo === 'status' ? ROTULO.status : ROTULO.prioridade
  return `${mapa[ev.dados.de] ?? '—'} → ${mapa[ev.dados.para] ?? '—'}`
}

