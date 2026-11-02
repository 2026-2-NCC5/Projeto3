import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'

// true/false conforme a conexão do navegador.
function assinarOnline(cb) {
  window.addEventListener('online', cb)
  window.addEventListener('offline', cb)
  return () => { window.removeEventListener('online', cb); window.removeEventListener('offline', cb) }
}
export function useOnline() {
  return useSyncExternalStore(assinarOnline, () => navigator.onLine, () => true)
}

export function useMidia(consulta) {
  const assinar = useCallback((cb) => {
    const mq = window.matchMedia(consulta)
    mq.addEventListener('change', cb)
    return () => mq.removeEventListener('change', cb)
  }, [consulta])
  return useSyncExternalStore(assinar, () => window.matchMedia(consulta).matches, () => false)
}

// Carrega dados com estados { dados, erro, carregando } e cancela a anterior ao mudar a chave.
// `recarregar()` refaz a chamada mantendo os dados atuais na tela.
export function useCarregar(fn, deps) {
  const [estado, setEstado] = useState({ dados: null, erro: null, carregando: true })
  const [versao, setVersao] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    const controle = new AbortController()
    setEstado((e) => ({ ...e, erro: null, carregando: true }))
    fnRef.current({ signal: controle.signal })
      .then((dados) => { if (!controle.signal.aborted) setEstado({ dados, erro: null, carregando: false }) })
      .catch((erro) => { if (!controle.signal.aborted) setEstado((e) => ({ ...e, erro, carregando: false })) })
    return () => controle.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao])

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])
  const definir = useCallback((dados) => setEstado({ dados, erro: null, carregando: false }), [])
  return { ...estado, recarregar, definir }
}

export function useDebounce(valor, ms = 300) {
  const [v, setV] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return v
}

export function useTituloPagina(titulo) {
  useEffect(() => {
    document.title = titulo ? `${titulo} · ASA Turbo` : 'ASA Turbo'
  }, [titulo])
}
