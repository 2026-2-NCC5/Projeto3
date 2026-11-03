// Peças da área de risco compartilhadas pela fila e pelo detalhe.
import { ROTULO, pontos } from '../../util/formatar.js'
import s from './Fila.module.css'

export const AVISO_PADRAO = 'Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana.'

export function AvisoDecisao({ texto = AVISO_PADRAO }) {
  return (
    <p className="aviso-decisao">
      <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" style={{ flex: 'none', alignSelf: 'center' }}>
        <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M8 7.2v4M8 4.8v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <span><strong>O score é apoio, não veredito.</strong> {texto.replace(/^Apoio à decisão\.\s*/, '')}</span>
    </p>
  )
}

// Seta + variação em pontos percentuais. "Subindo" = risco aumentando.
export function Tendencia({ tendencia, variacao, compacta = false }) {
  const seta = { subindo: 'M8 12V4M4.5 7.5 8 4l3.5 3.5', caindo: 'M8 4v8M4.5 8.5 8 12l3.5-3.5', estavel: 'M3.5 8h9M9.5 5l3 3-3 3' }[tendencia]
  return (
    <span className={`${s.tendencia} ${s[`t_${tendencia}`]}`}>
      <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16"><path d={seta} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
      {compacta ? <span>{pontos(variacao)}</span> : <span>{ROTULO.tendencia[tendencia]} <span>{variacao !== null && variacao !== undefined ? `(${pontos(variacao)})` : ''}</span></span>}
      {compacta && <span className="sr-only"> {ROTULO.tendencia[tendencia]}</span>}
    </span>
  )
}
