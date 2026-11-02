// Fila de risco (atendente/administração). Filtros ficam na URL: dá para voltar do
// detalhe sem perder nada e compartilhar o link com a equipe.
import { useEffect, useState } from 'react'
import { api } from '../../api/api.js'
import { Link, navegar, useLocalizacao } from '../../rotas/roteador.jsx'
import { BadgeRisco, EstadoErro, EstadoVazio, Paginacao } from '../../componentes/comum.jsx'
import { useCarregar, useDebounce, useMidia, useTituloPagina } from '../../util/hooks.js'
import { ROTULO, dataCurta, diaMes, pct } from '../../util/formatar.js'
import { AvisoDecisao, Tendencia } from './pecas.jsx'
import s from './Fila.module.css'

const CATEGORIAS = ['vermelho', 'amarelo', 'verde']
const ORDENS = [
  ['prioridade', 'Prioridade'],
  ['-score', 'Maior score'],
  ['-variacao', 'Maior alta no mês'],
  ['prazo', 'Prazo mais próximo'],
  ['score', 'Menor score'],
  ['nome', 'Nome (A–Z)'],
]
const POR_PAGINA = 25

function lerFiltros(busca) {
  return {
    categoria: busca.getAll('categoria').filter((c) => CATEGORIAS.includes(c)),
    status: busca.get('status') ?? '',
    responsavel: busca.get('responsavel') ?? '',
    busca: busca.get('busca') ?? '',
    ordenar: busca.get('ordenar') ?? 'prioridade',
    pagina: Math.max(1, Number(busca.get('pagina')) || 1),
  }
}

function urlDosFiltros(f) {
  const p = new URLSearchParams()
  f.categoria.forEach((c) => p.append('categoria', c))
  if (f.status) p.set('status', f.status)
  if (f.responsavel) p.set('responsavel', f.responsavel)
  if (f.busca) p.set('busca', f.busca)
  if (f.ordenar !== 'prioridade') p.set('ordenar', f.ordenar)
  if (f.pagina > 1) p.set('pagina', String(f.pagina))
  const q = p.toString()
  return q ? `/fila?${q}` : '/fila'
}

export default function Fila() {
  useTituloPagina('Fila de risco')
  const { busca: params, url } = useLocalizacao()
  const filtros = lerFiltros(params)
  const [textoBusca, setTextoBusca] = useState(filtros.busca)
  const buscaDebounce = useDebounce(textoBusca.trim(), 350)
  const largo = useMidia('(min-width: 900px)')

  const mudar = (parcial, { manterPagina = false } = {}) =>
    navegar(urlDosFiltros({ ...filtros, ...parcial, pagina: manterPagina ? (parcial.pagina ?? filtros.pagina) : 1 }), { substituir: true })

  useEffect(() => {
    if (buscaDebounce !== filtros.busca) mudar({ busca: buscaDebounce })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaDebounce])

  const chave = url
  const { dados, erro, carregando, recarregar } = useCarregar(({ signal }) => api.listarCasos({
    categoria: filtros.categoria, status: filtros.status || undefined, responsavel: filtros.responsavel || undefined,
    busca: filtros.busca || undefined, ordenar: filtros.ordenar, pagina: filtros.pagina, por_pagina: POR_PAGINA,
  }, { signal }), [chave])

  const alternarCategoria = (c) => {
    const atual = new Set(filtros.categoria)
    atual.has(c) ? atual.delete(c) : atual.add(c)
    mudar({ categoria: CATEGORIAS.filter((x) => atual.has(x)) })
  }
  const temFiltro = filtros.categoria.length || filtros.status || filtros.responsavel || filtros.busca
  const limpar = () => { setTextoBusca(''); navegar('/fila', { substituir: true }) }

  return (
    <>
      <div className="cabecalho-pagina">
        <div>
          <h1>Fila de risco</h1>
          <p>Estudantes ordenados por prioridade de contato. O estudante nunca vê esta tela.</p>
        </div>
        <AvisoDecisao />
      </div>

      <section className={s.contagem} aria-label="Estudantes por faixa de risco">
        {CATEGORIAS.map((c) => (
          <button key={c} type="button" className={`${s.faixa} ${s[`faixa_${c}`]}`} aria-pressed={filtros.categoria.includes(c)} onClick={() => alternarCategoria(c)}>
            <span className={s.faixaRotulo}><BadgeRisco categoria={c} /></span>
            <span className={s.faixaNumero}>{dados ? dados.contagem[c].toLocaleString('pt-BR') : '–'}</span>
            <span className={s.faixaDica}>{filtros.categoria.includes(c) ? 'Filtrando' : 'Filtrar'}</span>
          </button>
        ))}
      </section>

      <div className={s.filtros}>
        <div className={`campo ${s.busca}`}>
          <label className="campo__rotulo" htmlFor="fila-busca">Buscar</label>
          <input id="fila-busca" className="input" type="search" placeholder="RA ou nome" value={textoBusca}
            onChange={(e) => setTextoBusca(e.target.value)} autoComplete="off" inputMode="search" />
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="fila-status">Situação do caso</label>
          <select id="fila-status" className="select" value={filtros.status} onChange={(e) => mudar({ status: e.target.value })}>
            <option value="">Todas</option>
            {Object.entries(ROTULO.status).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
          </select>
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="fila-resp">Responsável</label>
          <select id="fila-resp" className="select" value={filtros.responsavel} onChange={(e) => mudar({ responsavel: e.target.value })}>
            <option value="">Qualquer</option>
            <option value="eu">Meus casos</option>
            <option value="nenhum">Sem responsável</option>
          </select>
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="fila-ordem">Ordenar por</label>
          <select id="fila-ordem" className="select" value={filtros.ordenar} onChange={(e) => mudar({ ordenar: e.target.value })}>
            {ORDENS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
          </select>
        </div>
        {temFiltro ? <button type="button" className={`btn btn--fantasma btn--sm ${s.limpar}`} onClick={limpar}>Limpar filtros</button> : null}
      </div>

      <div aria-live="polite" aria-busy={carregando}>
        {erro && !dados ? (
          <EstadoErro erro={erro} titulo="Não foi possível carregar a fila" onTentar={recarregar} />
        ) : !dados ? (
          <EsqueletoFila />
        ) : dados.itens.length === 0 ? (
          <EstadoVazio titulo={filtros.busca ? `Nenhum estudante encontrado para “${filtros.busca}”` : 'Nenhum caso com esses filtros'}
            acoes={temFiltro ? <button type="button" className="btn btn--secundario btn--sm" onClick={limpar}>Limpar filtros</button> : null}>
            {filtros.busca ? 'Confira o RA ou tente parte do nome.' : 'Tente incluir outra faixa de risco ou outra situação.'}
          </EstadoVazio>
        ) : (
          <>
            {erro && <p className="campo__erro" role="alert">Não foi possível atualizar a lista. Mostrando o resultado anterior. <button type="button" className="btn btn--fantasma btn--sm" onClick={recarregar}>Tentar de novo</button></p>}
            <div className={carregando ? s.atualizando : undefined}>
              {largo ? <Tabela itens={dados.itens} voltar={url} /> : <ListaCompacta itens={dados.itens} voltar={url} />}
            </div>
            <Paginacao total={dados.total} pagina={dados.pagina} porPagina={dados.por_pagina} rotulo="estudantes"
              onMudar={(p) => { mudar({ pagina: p }, { manterPagina: true }); window.scrollTo(0, 0) }} />
            <p className="texto-meta">Modelo {dados.itens[0].versao_modelo} · scores atualizados em {dataCurta(dados.itens[0].atualizado_em)}</p>
          </>
        )}
      </div>
    </>
  )
}

const linkCaso = (item, voltar) => `/fila/${item.estudante.id}?volta=${encodeURIComponent(voltar)}`

function Tabela({ itens, voltar }) {
  return (
    <div className="tabela-container">
      <table className={`tabela ${s.tabela}`}>
        <caption className="sr-only">Fila de risco de evasão</caption>
        <thead>
          <tr>
            <th scope="col">Estudante</th>
            <th scope="col">Curso</th>
            <th scope="col" className="num">Score</th>
            <th scope="col">Faixa</th>
            <th scope="col">Tendência</th>
            <th scope="col">Prioridade</th>
            <th scope="col">Situação</th>
            <th scope="col">Prazo</th>
            <th scope="col">Responsável</th>
          </tr>
        </thead>
        <tbody>
          {itens.map((c) => {
            const ajustada = c.categoria !== c.categoria_modelo
            return (
              <tr key={c.estudante.id}>
                <td className={s.colEstudante}>
                  <span className={s.duasLinhas}>
                    <Link to={linkCaso(c, voltar)}>{c.estudante.nome}</Link>
                    <span className={s.ra}>RA {c.estudante.ra}</span>
                  </span>
                </td>
                <td className={s.colCurso}><span className={s.duasLinhas}><span className={s.curso}>{c.estudante.curso}</span><span className={s.ra}>{c.estudante.semestre}º semestre</span></span></td>
                <td className="num"><strong>{pct(c.score_geral)}</strong></td>
                <td>
                  <BadgeRisco categoria={c.categoria} ajustada={ajustada} />
                  {ajustada && <span className={s.ajustada} title={`Modelo: ${ROTULO.categoria[c.categoria_modelo]}`}>ajustada</span>}
                </td>
                <td><Tendencia tendencia={c.tendencia} variacao={c.variacao} /></td>
                <td>{c.prioridade ? <Prioridade p={c.prioridade} /> : <span className={s.nada}>—</span>}</td>
                <td>{c.status ? <span className="etiqueta">{ROTULO.status[c.status]}</span> : <span className={s.nada}>Sem caso</span>}</td>
                <td className="numero">{c.prazo ? diaMes(c.prazo) : <span className={s.nada}>—</span>}</td>
                <td className={s.colResp}>{c.responsavel?.nome ?? <span className={s.nada}>—</span>}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// Celular: lista compacta, uma linha por estudante, tudo clicável.
function ListaCompacta({ itens, voltar }) {
  return (
    <ul className={s.lista}>
      {itens.map((c) => (
        <li key={c.estudante.id}>
          <Link to={linkCaso(c, voltar)} className={s.itemLista}>
            <span className={s.itemTopo}>
              <span className={s.itemNome}>{c.estudante.nome}</span>
              <strong className={s.itemScore}>{pct(c.score_geral)}</strong>
            </span>
            <span className={s.itemMeio}>
              <BadgeRisco categoria={c.categoria} ajustada={c.categoria !== c.categoria_modelo} />
              <Tendencia tendencia={c.tendencia} variacao={c.variacao} compacta />
              {c.prioridade && <Prioridade p={c.prioridade} />}
            </span>
            <span className={s.itemBase}>
              RA {c.estudante.ra} · {c.status ? ROTULO.status[c.status] : 'Sem caso'}{c.prazo ? ` · prazo ${diaMes(c.prazo)}` : ''}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Prioridade({ p }) {
  return <span className={`${s.prioridade} ${s[`p_${p}`]}`}>{ROTULO.prioridade[p]}</span>
}

function EsqueletoFila() {
  return (
    <div className="tabela-container" aria-busy="true">
      <span className="sr-only">Carregando a fila</span>
      <div className={s.esqueleto}>
        {Array.from({ length: 8 }, (_, i) => <span key={i} className="esqueleto" style={{ width: `${92 - (i % 3) * 9}%` }} />)}
      </div>
    </div>
  )
}

