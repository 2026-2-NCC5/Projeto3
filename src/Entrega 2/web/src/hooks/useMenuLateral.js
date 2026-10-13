// Menu lateral.
// Desktop (≥ 769 px): fica aberto na lateral; o botão do cabeçalho recolhe/mostra
// (a escolha é lembrada no localStorage, só neste navegador).
// Celular (≤ 768 px): escondido; o botão abre como painel modal.
// Modal, enquanto aberto: foco preso no painel (Tab/Shift+Tab circulam), Esc fecha,
// o resto da página fica inerte. Ao fechar, o foco volta ao botão que abriu.
import { useCallback, useEffect, useRef, useState } from 'react'

const DESKTOP = '(min-width: 769px)' // mesmo breakpoint do Sidebar.module.css
const CHAVE_RECOLHIDA = 'asa:sidebar-recolhida'
const FOCAVEIS = 'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function lerRecolhida() {
  try { return localStorage.getItem(CHAVE_RECOLHIDA) === '1' } catch { return false }
}

export function useMenuLateral() {
  const [aberto, setAberto] = useState(false)       // painel modal (celular)
  const [recolhida, setRecolhida] = useState(lerRecolhida) // recolhida (desktop)
  const [desktop, setDesktop] = useState(() => window.matchMedia(DESKTOP).matches)
  const botaoRef = useRef(null)    // botão "Abrir conversas"
  const painelRef = useRef(null)   // a sidebar
  const conteudoRef = useRef(null) // o <main>, que fica inerte com o menu aberto

  useEffect(() => {
    const mq = window.matchMedia(DESKTOP)
    const aoMudar = (e) => setDesktop(e.matches)
    mq.addEventListener('change', aoMudar)
    return () => mq.removeEventListener('change', aoMudar)
  }, [])

  const alternarRecolhida = useCallback(() => {
    setRecolhida((r) => {
      try { localStorage.setItem(CHAVE_RECOLHIDA, r ? '0' : '1') } catch { /* sem storage: vale só nesta sessão */ }
      return !r
    })
  }, [])

  const fechar = useCallback(() => {
    setAberto(false)
    // O botão fica dentro do <main>; o navegador não foca elementos inertes,
    // então o inert precisa sair ANTES de devolver o foco.
    if (conteudoRef.current) conteudoRef.current.inert = false
    botaoRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!aberto) return
    const painel = painelRef.current
    const conteudo = conteudoRef.current
    const focaveis = () => [...painel.querySelectorAll(FOCAVEIS)].filter((el) => el.offsetParent !== null)

    focaveis()[0]?.focus()
    if (conteudo) conteudo.inert = true

    function aoTeclar(e) {
      if (e.key === 'Escape') {
        e.preventDefault()
        fechar()
        return
      }
      if (e.key !== 'Tab') return
      const lista = focaveis()
      if (lista.length === 0) return
      const primeiro = lista[0]
      const ultimo = lista[lista.length - 1]
      const dentro = painel.contains(document.activeElement)
      if (e.shiftKey && (document.activeElement === primeiro || !dentro)) {
        e.preventDefault()
        ultimo.focus()
      } else if (!e.shiftKey && (document.activeElement === ultimo || !dentro)) {
        e.preventDefault()
        primeiro.focus()
      }
    }

    // Se a tela crescer para desktop com o menu aberto, fecha (o botão some no desktop).
    const mq = window.matchMedia(DESKTOP)
    const aoMudarTela = (e) => e.matches && setAberto(false)

    document.addEventListener('keydown', aoTeclar)
    mq.addEventListener('change', aoMudarTela)
    return () => {
      document.removeEventListener('keydown', aoTeclar)
      mq.removeEventListener('change', aoMudarTela)
      if (conteudo) conteudo.inert = false
    }
  }, [aberto, fechar])

  // O mesmo botão do cabeçalho serve aos dois modos.
  const botao = desktop
    ? { rotulo: recolhida ? 'Mostrar conversas' : 'Recolher conversas', expandido: !recolhida, aoClicar: alternarRecolhida }
    : { rotulo: 'Abrir conversas', expandido: aberto, aoClicar: () => setAberto(true) }

  return { aberto, recolhida: desktop && recolhida, botao, fechar, botaoRef, painelRef, conteudoRef }
}
