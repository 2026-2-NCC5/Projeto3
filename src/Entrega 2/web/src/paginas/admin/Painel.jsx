// Painel da administração: só indicadores agregados (GET /admin/dashboard).
import { useState } from 'react'
import { api } from '../../api/api.js'
import { Link } from '../../rotas/roteador.jsx'
import { EstadoErro, Esqueleto } from '../../componentes/comum.jsx'
import { BarraDistribuicao, ColunasRisco, GraficoBarras } from '../../componentes/graficos.jsx'
import g from '../../componentes/graficos.module.css'
import { useCarregar, useTituloPagina } from '../../util/hooks.js'
import { ROTULO, dataCurta, dataHora, diaMes, mesAbreviado, mesAno, numero, pct } from '../../util/formatar.js'
import s from './Admin.module.css'

const PERIODOS = [[7, '7 dias'], [30, '30 dias'], [90, '90 dias']]

function intervalo(dias) {
  const ate = new Date()
  const de = new Date(ate.getTime() - (dias - 1) * 86400000)
  const iso = (d) => d.toLocaleDateString('sv-SE') // AAAA-MM-DD no fuso local
  return { de: iso(de), ate: iso(ate) }
}

export default function Painel() {
  useTituloPagina('Painel')
  const [dias, setDias] = useState(30)
  const { dados: d, erro, carregando, recarregar } = useCarregar(({ signal }) => api.dashboard(intervalo(dias), { signal }), [dias])

  return (
    <>
      <div className="cabecalho-pagina">
        <div>
          <h1>Painel</h1>
          <p>Uso do ASA Turbo e acompanhamento de risco. Só números agregados, sem dados individuais.</p>
        </div>
        <div className={s.periodo} role="group" aria-label="Período">
          {PERIODOS.map(([n, r]) => (
            <button key={n} type="button" className="chip" aria-pressed={dias === n} onClick={() => setDias(n)}>{r}</button>
          ))}
        </div>
      </div>

      {erro && !d ? <EstadoErro erro={erro} titulo="Não foi possível carregar o painel" onTentar={recarregar} />
        : !d ? <Esqueleto linhas={8} rotulo="Carregando o painel" />
          : <Conteudo d={d} atualizando={carregando} />}
    </>
  )
}

function Conteudo({ d, atualizando }) {
  const c = d.chat
  const totalFeedback = c.feedback.util + c.feedback.nao_util
  const totalVal = d.validacoes.confirmado + d.validacoes.ajustado + d.validacoes.rejeitado
  const riscoTotal = d.risco.distribuicao.verde + d.risco.distribuicao.amarelo + d.risco.distribuicao.vermelho

  return (
    <div className={atualizando ? s.atualizando : undefined} aria-busy={atualizando}>
      <p className="texto-meta" style={{ marginBottom: 'var(--esp-3)' }}>
        De {dataCurta(d.periodo.de)} a {dataCurta(d.periodo.ate)} · atualizado em {dataHora(d.atualizado_em)}
      </p>

      <h2 className={s.secao}>Chat do estudante</h2>
      <dl className={s.indicadores}>
        <Indicador rotulo="Perguntas" valor={numero(c.perguntas)} nota={`${numero(c.conversas)} conversas`} />
        <Indicador rotulo="Estudantes ativos" valor={numero(c.estudantes_ativos)} />
        <Indicador rotulo="Taxa de abstenção" valor={pct(c.taxa_abstencao, 1)} nota="Respostas encaminhadas ao ASA" />
        <Indicador rotulo="Avaliadas como úteis" valor={totalFeedback ? pct(c.feedback.util / totalFeedback) : '—'} nota={`${numero(totalFeedback)} avaliações`} />
        <Indicador rotulo="Confiança média" valor={pct(c.confianca_media)} />
        <Indicador rotulo="Tempo de resposta (p95)" valor={c.latencia_p95_ms ? `${(c.latencia_p95_ms / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s` : '—'} />
      </dl>

      <div className={s.grade2}>
        <section className={`painel ${s.bloco} ${s.largo}`} aria-labelledby="t-perguntas">
          <h3 id="t-perguntas" className="rotulo-secao">Perguntas por dia</h3>
          {c.perguntas_por_dia?.length ? (
            <GraficoBarras titulo="Perguntas por dia, respondidas e encaminhadas"
              series={[{ chave: 'respondidas', nome: 'Respondidas', classe: g.serieA }, { chave: 'abstencoes', nome: 'Encaminhadas ao ASA', classe: g.serieB }]}
              dados={c.perguntas_por_dia.map((x) => ({ rotulo: diaMes(x.dia), rotuloLongo: dataCurta(x.dia), respondidas: x.total - x.abstencoes, abstencoes: x.abstencoes }))} />
          ) : <p className="texto-meta">Sem perguntas no período.</p>}
        </section>

        <section className={`painel ${s.bloco}`} aria-labelledby="t-docs">
          <h3 id="t-docs" className="rotulo-secao">Documentos mais citados</h3>
          {c.principais_documentos?.length ? (
            <ol className={s.ranking}>
              {c.principais_documentos.map((doc) => {
                const max = c.principais_documentos[0].citacoes || 1
                return (
                  <li key={doc.titulo}>
                    {doc.documento_id ? <Link to={`/admin/documentos/${doc.documento_id}`}>{doc.titulo}</Link> : <span>{doc.titulo}</span>}
                    <span className="numero">{numero(doc.citacoes)}</span>
                    <span className={s.rankBarra}><span style={{ width: `${(doc.citacoes / max) * 100}%` }} /></span>
                  </li>
                )
              })}
            </ol>
          ) : <p className="texto-meta">Nenhuma resposta com fonte no período.</p>}
        </section>

        <section className={`painel ${s.bloco}`} aria-labelledby="t-enc">
          <h3 id="t-enc" className="rotulo-secao">Encaminhamentos ao ASA</h3>
          <dl className={s.lista3}>
            <div><dt>Abertos</dt><dd className="numero">{numero(d.encaminhamentos.abertos)}</dd></div>
            <div><dt>Em atendimento</dt><dd className="numero">{numero(d.encaminhamentos.em_andamento)}</dd></div>
            <div><dt>Resolvidos</dt><dd className="numero">{numero(d.encaminhamentos.resolvidos)}</dd></div>
          </dl>
        </section>
      </div>

      <h2 className={s.secao}>Risco de evasão</h2>
      <div className={s.grade2}>
        <section className={`painel ${s.bloco}`} aria-labelledby="t-dist">
          <h3 id="t-dist" className="rotulo-secao">Distribuição atual · {numero(riscoTotal)} estudantes</h3>
          <BarraDistribuicao titulo="Estudantes por faixa de risco" partes={['vermelho', 'amarelo', 'verde'].map((k) => ({ chave: k, nome: ROTULO.categoria[k], valor: d.risco.distribuicao[k], cor: `var(--risco-${k}-ponto)` }))} />
          <p className="texto-meta">Modelo {d.risco.versao_modelo}</p>
        </section>

        <section className={`painel ${s.bloco}`} aria-labelledby="t-mensal">
          <h3 id="t-mensal" className="rotulo-secao">Faixas mês a mês (proporção)</h3>
          {d.risco.distribuicao_mensal?.length ? (
            <ColunasRisco titulo="Proporção de estudantes por faixa em cada mês"
              dados={d.risco.distribuicao_mensal.map((x) => ({ ...x, rotulo: mesAbreviado(x.competencia), rotuloLongo: mesAno(x.competencia) }))} />
          ) : <p className="texto-meta">Sem histórico mensal.</p>}
        </section>

        <section className={`painel ${s.bloco}`} aria-labelledby="t-val">
          <h3 id="t-val" className="rotulo-secao">Avaliações humanas · {numero(totalVal)}</h3>
          <dl className={s.lista3}>
            {['confirmado', 'ajustado', 'rejeitado'].map((k) => (
              <div key={k}><dt>{ROTULO.decisao[k]}</dt><dd className="numero">{numero(d.validacoes[k])} <span className="texto-meta">{totalVal ? pct(d.validacoes[k] / totalVal) : ''}</span></dd></div>
            ))}
          </dl>
          {d.validacoes.tempo_medio_ate_validacao_horas != null && (
            <p className="texto-meta">Tempo médio até a avaliação: {d.validacoes.tempo_medio_ate_validacao_horas.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} h</p>
          )}
        </section>

        <section className={`painel ${s.bloco}`} aria-labelledby="t-status">
          <h3 id="t-status" className="rotulo-secao">Casos por situação</h3>
          <dl className={s.lista3}>
            {Object.entries(d.risco.casos_por_status ?? {}).map(([k, v]) => <div key={k}><dt>{ROTULO.status[k] ?? k}</dt><dd className="numero">{numero(v)}</dd></div>)}
          </dl>
          <Link to="/fila" className="btn btn--secundario btn--sm" style={{ justifySelf: 'start' }}>Abrir a fila de risco</Link>
        </section>
      </div>
    </div>
  )
}

function Indicador({ rotulo, valor, nota }) {
  return (
    <div className={s.indicador}>
      <dt>{rotulo}</dt>
      <dd><strong>{valor}</strong>{nota && <span>{nota}</span>}</dd>
    </div>
  )
}
