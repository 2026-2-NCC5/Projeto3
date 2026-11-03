// Roteador mínimo sobre a History API (sem dependência).
// useLocalizacao() -> { caminho, busca } e reage a voltar/avançar e a navegar().
import { useSyncExternalStore } from 'react'

const EVENTO = 'asa:navegou'

function assinar(cb) {
  window.addEventListener('popstate', cb)
  window.addEventListener(EVENTO, cb)
  return () => {
    window.removeEventListener('popstate', cb)
    window.removeEventListener(EVENTO, cb)
  }
}
const ler = () => window.location.pathname + window.location.search

export function useLocalizacao() {
  const url = useSyncExternalStore(assinar, ler)
  const [caminho, query = ''] = url.split('?')
  return { caminho, busca: new URLSearchParams(query), url }
}

export function navegar(url, { substituir = false } = {}) {
  if (url === ler()) return
  if (substituir) window.history.replaceState(null, '', url)
  else window.history.pushState(null, '', url)
  window.dispatchEvent(new Event(EVENTO))
  if (!substituir) window.scrollTo(0, 0)
}

// "/fila/:id" contra "/fila/abc" -> { id: 'abc' } (ou null)
export function casar(padrao, caminho) {
  const a = padrao.split('/').filter(Boolean)
  const b = caminho.split('/').filter(Boolean)
  if (a.length !== b.length) return null
  const params = {}
  for (let i = 0; i < a.length; i++) {
    if (a[i].startsWith(':')) params[a[i].slice(1)] = decodeURIComponent(b[i])
    else if (a[i] !== b[i]) return null
  }
  return params
}

export function Link({ to, onClick, children, ...resto }) {
  function aoClicar(e) {
    onClick?.(e)
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || resto.target) return
    e.preventDefault()
    navegar(to)
  }
  return <a href={to} onClick={aoClicar} {...resto}>{children}</a>
}
