// Formata texto puro vindo da API SEM interpretar HTML (nada de dangerouslySetInnerHTML):
// - linha em branco separa parágrafos
// - linhas iniciadas por "- ", "* ", "• " viram lista; "1. " ou "1) " viram lista numerada
// - quebra de linha simples é preservada
// - **assim** vira negrito (só isso; ver utils/negrito.js)
// - endereços http(s) viram links que abrem em nova aba
import { dividirNegrito } from '../utils/negrito.js'
import styles from './TextoFormatado.module.css'

const ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/
const NUMERADO = /^\s*\d+[.)]\s+/
const URL = /(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g

export default function TextoFormatado({ texto }) {
  return (
    <div className={styles.texto}>
      {agrupar(texto).map((grupo, i) => {
        if (grupo.tipo === 'lista') {
          const Lista = NUMERADO.test(grupo.linhas[0]) ? 'ol' : 'ul'
          return (
            // role="list" explícito: com list-style: none, o Safari/VoiceOver deixa de anunciar o <ul> como lista.
            <Lista key={i} role="list">
              {grupo.linhas.map((l, j) => <li key={j}><Inline texto={l.replace(ITEM, '')} /></li>)}
            </Lista>
          )
        }
        return (
          <p key={i}>
            {grupo.linhas.map((l, j) => (
              <span key={j}>{j > 0 && <br />}<Inline texto={l} /></span>
            ))}
          </p>
        )
      })}
    </div>
  )
}

// Divide em blocos por linha em branco e, dentro de cada bloco, junta linhas
// consecutivas do mesmo tipo (texto ou item de lista).
function agrupar(texto) {
  const grupos = []
  for (const bloco of texto.trim().split(/\n\s*\n/)) {
    let atual = null
    for (const linha of bloco.split('\n')) {
      const tipo = ITEM.test(linha) ? 'lista' : 'paragrafo'
      if (!atual || atual.tipo !== tipo) {
        atual = { tipo, linhas: [] }
        grupos.push(atual)
      }
      atual.linhas.push(linha)
    }
  }
  return grupos
}

// Negrito primeiro; dentro de cada trecho, os endereços viram links.
function Inline({ texto }) {
  return dividirNegrito(texto).map((p, i) =>
    p.negrito ? <strong key={i}><Linkificar texto={p.texto} /></strong> : <Linkificar key={i} texto={p.texto} />,
  )
}

function Linkificar({ texto }) {
  return texto.split(URL).map((parte, i) =>
    i % 2 === 1 ? (
      <a key={i} href={parte} target="_blank" rel="noopener noreferrer">
        {parte}<span className="sr-only"> (abre em nova aba)</span>
      </a>
    ) : (
      parte
    ),
  )
}
