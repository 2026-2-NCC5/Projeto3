// Gráficos feitos à mão em SVG (sem biblioteca). Desenhados na largura real do contêiner,
// para o texto não encolher no celular. Cada gráfico tem: dica ao passar o mouse ou focar
// (teclado), rótulo acessível e uma tabela equivalente para leitor de tela.
// Cores: verde da marca para séries comuns; semáforo SÓ quando a série é a faixa de risco.
import { useEffect, useId, useRef, useState } from 'react'
import s from './graficos.module.css'

function useLargura() {
  const ref = useRef(null)
  const [largura, setLargura] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setLargura(Math.floor(e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, largura]
}

const COR_RISCO = { verde: 'var(--risco-verde-ponto)', amarelo: 'var(--risco-amarelo-ponto)', vermelho: 'var(--risco-vermelho-ponto)' }
const ROTULO_RISCO = { verde: 'Verde', amarelo: 'Amarelo', vermelho: 'Vermelho' }

function Dica({ dica }) {
  if (!dica) return null
  return (
    <div className="dica-grafico" style={{ left: dica.x, top: dica.y }} role="presentation">
      <strong>{dica.valor}</strong>
      {dica.linhas.map((l) => <span key={l} style={{ display: 'block' }}>{l}</span>)}
    </div>
  )
}

// ---------------------------------------------------------------- linha (tendência)
// pontos: [{ rotulo, rotuloLongo, valor (0..1), categoria }]
export function GraficoTendencia({ pontos, titulo, altura = 200 }) {
  const [ref, largura] = useLargura()
  const [ativo, setAtivo] = useState(null)
  const id = useId()
  const m = { topo: 16, dir: 44, base: 28, esq: 36 }
  const w = Math.max(0, largura - m.esq - m.dir)
  const h = altura - m.topo - m.base
  const max = Math.max(0.8, Math.ceil(Math.max(...pontos.map((p) => p.valor)) * 10) / 10)
  const x = (i) => m.esq + (pontos.length === 1 ? w / 2 : (i * w) / (pontos.length - 1))
  const y = (v) => m.topo + h - (v / max) * h
  const caminho = pontos.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.valor).toFixed(1)}`).join(' ')
  const resumo = `${titulo}: ${pontos.map((p) => `${p.rotuloLongo} ${Math.round(p.valor * 100)}%`).join(', ')}.`
  const dica = ativo !== null && largura ? {
    x: x(ativo), y: y(pontos[ativo].valor),
    valor: `${Math.round(pontos[ativo].valor * 100)}%`,
    linhas: [pontos[ativo].rotuloLongo, `Faixa ${ROTULO_RISCO[pontos[ativo].categoria]}`],
  } : null

  return (
    <figure className={s.figura}>
      <div ref={ref} className={s.area} onMouseLeave={() => setAtivo(null)}>
        {largura > 0 && (
          <svg width={largura} height={altura} role="img" aria-labelledby={`${id}-r`}>
            <title id={`${id}-r`}>{resumo}</title>
            {/* grade recessiva: 0, limiares e topo */}
            {[0, 0.3, 0.6].filter((v) => v <= max).map((v) => (
              <g key={v}>
                <line x1={m.esq} x2={m.esq + w} y1={y(v)} y2={y(v)} className={v === 0 ? s.eixo : s.limiar} />
                <text x={m.esq - 6} y={y(v)} className={s.rotuloY} textAnchor="end" dominantBaseline="middle">{Math.round(v * 100)}%</text>
              </g>
            ))}
            {max >= 0.3 && <text x={m.esq + w + 6} y={y(0.3)} className={s.rotuloLimiar} dominantBaseline="middle">Amarelo</text>}
            {max >= 0.6 && <text x={m.esq + w + 6} y={y(0.6)} className={s.rotuloLimiar} dominantBaseline="middle">Vermelho</text>}
            <path d={caminho} className={s.linha} />
            {pontos.map((p, i) => (
              <g key={p.rotulo}
                tabIndex={0} role="img" aria-label={`${p.rotuloLongo}: ${Math.round(p.valor * 100)}%, faixa ${ROTULO_RISCO[p.categoria]}`}
                onMouseEnter={() => setAtivo(i)} onFocus={() => setAtivo(i)} onBlur={() => setAtivo(null)}
                className={s.ponto}>
                <rect x={x(i) - Math.max(12, w / pontos.length / 2)} y={m.topo} width={Math.max(24, w / pontos.length)} height={h} fill="transparent" />
                {ativo === i && <line x1={x(i)} x2={x(i)} y1={m.topo} y2={m.topo + h} className={s.guia} />}
                <circle cx={x(i)} cy={y(p.valor)} r={ativo === i ? 6 : 5} fill={COR_RISCO[p.categoria]} className={s.marcador} />
                <text x={x(i)} y={altura - 8} textAnchor="middle" className={s.rotuloX}>{p.rotulo}</text>
              </g>
            ))}
            {/* rótulo direto só no último ponto */}
            <text x={x(pontos.length - 1)} y={y(pontos.at(-1).valor) - 12} textAnchor="middle" className={s.valorFinal}>{Math.round(pontos.at(-1).valor * 100)}%</text>
          </svg>
        )}
        <Dica dica={dica} />
      </div>
      <table className="sr-only">
        <caption>{titulo}</caption>
        <thead><tr><th scope="col">Mês</th><th scope="col">Score</th><th scope="col">Faixa</th></tr></thead>
        <tbody>{pontos.map((p) => <tr key={p.rotulo}><th scope="row">{p.rotuloLongo}</th><td>{Math.round(p.valor * 100)}%</td><td>{ROTULO_RISCO[p.categoria]}</td></tr>)}</tbody>
      </table>
    </figure>
  )
}

// ------------------------------------------------- barras por dia (2 séries empilhadas)
// dados: [{ rotulo, rotuloLongo, a, b }]; series: [{ chave:'a', nome, classe }, ...]
export function GraficoBarras({ dados, series, titulo, altura = 180, formatar = (n) => n.toLocaleString('pt-BR') }) {
  const [ref, largura] = useLargura()
  const [ativo, setAtivo] = useState(null)
  const id = useId()
  const m = { topo: 12, dir: 8, base: 24, esq: 36 }
  const w = Math.max(0, largura - m.esq - m.dir)
  const h = altura - m.topo - m.base
  const total = (d) => series.reduce((acc, se) => acc + d[se.chave], 0)
  const bruto = Math.max(1, ...dados.map(total))
  const passo = 10 ** Math.floor(Math.log10(bruto))
  const max = Math.ceil(bruto / passo) * passo
  const banda = dados.length ? w / dados.length : 0
  const larguraBarra = Math.max(2, Math.min(24, banda - 2))
  const y = (v) => m.topo + h - (v / max) * h
  const cadaRotulo = Math.ceil(dados.length / Math.max(1, Math.floor(w / 56)))

  const dica = ativo !== null && largura ? {
    x: m.esq + banda * ativo + banda / 2, y: y(total(dados[ativo])),
    valor: `${formatar(total(dados[ativo]))} no total`,
    linhas: [dados[ativo].rotuloLongo, ...series.map((se) => `${se.nome}: ${formatar(dados[ativo][se.chave])}`)],
  } : null

  return (
    <figure className={s.figura}>
      <Legenda series={series} />
      <div ref={ref} className={s.area} onMouseLeave={() => setAtivo(null)}>
        {largura > 0 && (
          <svg width={largura} height={altura} role="img" aria-labelledby={`${id}-r`}>
            <title id={`${id}-r`}>{titulo}. Detalhes na tabela a seguir.</title>
            {[0, max / 2, max].map((v) => (
              <g key={v}>
                <line x1={m.esq} x2={m.esq + w} y1={y(v)} y2={y(v)} className={v === 0 ? s.eixo : s.grade} />
                <text x={m.esq - 6} y={y(v)} className={s.rotuloY} textAnchor="end" dominantBaseline="middle">{formatar(v)}</text>
              </g>
            ))}
            {dados.map((d, i) => {
              let acumulado = 0
              const cx = m.esq + banda * i + banda / 2
              return (
                <g key={d.rotulo} onMouseEnter={() => setAtivo(i)}>
                  <rect x={m.esq + banda * i} y={m.topo} width={banda} height={h} fill="transparent" />
                  {series.map((se, k) => {
                    const v = d[se.chave]
                    const y0 = y(acumulado)
                    acumulado += v
                    const y1 = y(acumulado)
                    const alto = Math.max(0, y0 - y1 - (k > 0 ? 1 : 0))
                    return alto > 0 ? <rect key={se.chave} x={cx - larguraBarra / 2} y={y1} width={larguraBarra} height={alto} className={se.classe} rx={k === series.length - 1 ? 1.5 : 0} /> : null
                  })}
                  {i % cadaRotulo === 0 && <text x={cx} y={altura - 6} textAnchor="middle" className={s.rotuloX}>{d.rotulo}</text>}
                </g>
              )
            })}
            {ativo !== null && <rect x={m.esq + banda * ativo} y={m.topo} width={banda} height={h} className={s.realce} />}
          </svg>
        )}
        <Dica dica={dica} />
      </div>
      <details className={s.tabelaDados}>
        <summary>Ver dados em tabela</summary>
        <div className="tabela-container">
          <table className="tabela">
            <caption className="sr-only">{titulo}</caption>
            <thead><tr><th scope="col">Dia</th>{series.map((se) => <th key={se.chave} scope="col" className="num">{se.nome}</th>)}</tr></thead>
            <tbody>{dados.map((d) => <tr key={d.rotulo}><th scope="row">{d.rotuloLongo}</th>{series.map((se) => <td key={se.chave} className="num">{formatar(d[se.chave])}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

export function Legenda({ series }) {
  return (
    <ul className={s.legenda}>
      {series.map((se) => <li key={se.chave}><span className={`${s.amostra} ${se.classe}`} aria-hidden="true" />{se.nome}</li>)}
    </ul>
  )
}

// ---------------------------------------------- barra única empilhada (distribuição)
// partes: [{ chave, nome, valor, cor }]
export function BarraDistribuicao({ partes, titulo }) {
  const total = partes.reduce((a, p) => a + p.valor, 0) || 1
  return (
    <figure className={s.figura}>
      <div className={s.barraUnica} role="img" aria-label={`${titulo}: ${partes.map((p) => `${p.nome} ${p.valor} (${Math.round((p.valor / total) * 100)}%)`).join(', ')}`}>
        {partes.filter((p) => p.valor > 0).map((p) => (
          <span key={p.chave} style={{ flexGrow: p.valor, background: p.cor }} title={`${p.nome}: ${p.valor} (${Math.round((p.valor / total) * 100)}%)`} />
        ))}
      </div>
      <ul className={s.legendaValores}>
        {partes.map((p) => (
          <li key={p.chave}>
            <span className={s.amostra} style={{ background: p.cor }} aria-hidden="true" />
            <span>{p.nome}</span>
            <strong className="numero">{p.valor.toLocaleString('pt-BR')}</strong>
            <span className="numero texto-meta">{Math.round((p.valor / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </figure>
  )
}

// --------------------------------------- colunas mensais empilhadas (faixas de risco)
// dados: [{ rotulo, rotuloLongo, verde, amarelo, vermelho }]
export function ColunasRisco({ dados, titulo, altura = 170 }) {
  const [ref, largura] = useLargura()
  const [ativo, setAtivo] = useState(null)
  const m = { topo: 8, dir: 4, base: 24, esq: 4 }
  const w = Math.max(0, largura - m.esq - m.dir)
  const h = altura - m.topo - m.base
  const banda = dados.length ? w / dados.length : 0
  const lb = Math.min(48, banda * 0.6)
  const ordem = ['vermelho', 'amarelo', 'verde'] // vermelho embaixo, perto do eixo: é o que importa comparar
  const dica = ativo !== null && largura ? (() => {
    const d = dados[ativo]
    const t = d.verde + d.amarelo + d.vermelho || 1
    return { x: m.esq + banda * ativo + banda / 2, y: m.topo + 8, valor: d.rotuloLongo, linhas: ordem.map((c) => `${ROTULO_RISCO[c]}: ${d[c]} (${Math.round((d[c] / t) * 100)}%)`) }
  })() : null

  return (
    <figure className={s.figura}>
      <Legenda series={ordem.map((c) => ({ chave: c, nome: ROTULO_RISCO[c], classe: s[`risco_${c}`] }))} />
      <div ref={ref} className={s.area} onMouseLeave={() => setAtivo(null)}>
        {largura > 0 && (
          <svg width={largura} height={altura} role="img" aria-label={`${titulo}. Detalhes na tabela a seguir.`}>
            {dados.map((d, i) => {
              const t = d.verde + d.amarelo + d.vermelho || 1
              let acc = 0
              const cx = m.esq + banda * i + banda / 2
              return (
                <g key={d.rotulo} onMouseEnter={() => setAtivo(i)}>
                  <rect x={m.esq + banda * i} y={m.topo} width={banda} height={h} fill="transparent" />
                  {ordem.map((c, k) => {
                    const alto = (d[c] / t) * h
                    const y0 = m.topo + h - acc - alto
                    acc += alto
                    return <rect key={c} x={cx - lb / 2} y={y0 + (k ? 0 : 0)} width={lb} height={Math.max(0, alto - 2)} className={s[`risco_${c}`]} />
                  })}
                  <text x={cx} y={altura - 6} textAnchor="middle" className={s.rotuloX}>{d.rotulo}</text>
                </g>
              )
            })}
          </svg>
        )}
        <Dica dica={dica} />
      </div>
      <table className="sr-only">
        <caption>{titulo}</caption>
        <thead><tr><th scope="col">Mês</th>{ordem.map((c) => <th key={c} scope="col">{ROTULO_RISCO[c]}</th>)}</tr></thead>
        <tbody>{dados.map((d) => <tr key={d.rotulo}><th scope="row">{d.rotuloLongo}</th>{ordem.map((c) => <td key={c}>{d[c]}</td>)}</tr>)}</tbody>
      </table>
    </figure>
  )
}

// --------------------------------------------------------- barra horizontal simples
export function Medidor({ valor, max = 1, rotulo, classe = '' }) {
  return (
    <span className={`${s.medidor} ${classe}`} role="img" aria-label={rotulo}>
      <span style={{ width: `${Math.max(0, Math.min(1, valor / max)) * 100}%` }} />
    </span>
  )
}
