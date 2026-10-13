import { useEffect, useRef, useState } from 'react'
import styles from './Composer.module.css'

const ALTURA_MAX = 160
const CELULAR = '(max-width: 560px)' // mesmo breakpoint do Composer.module.css

// true enquanto a tela estiver na largura de celular (atualiza ao girar/redimensionar).
function useCelular() {
  const [celular, setCelular] = useState(() => window.matchMedia(CELULAR).matches)
  useEffect(() => {
    const mq = window.matchMedia(CELULAR)
    const aoMudar = (e) => setCelular(e.matches)
    mq.addEventListener('change', aoMudar)
    return () => mq.removeEventListener('change', aoMudar)
  }, [])
  return celular
}

export default function Composer({ onEnviar, enviando }) {
  const [texto, setTexto] = useState('')
  const campo = useRef(null)
  const celular = useCelular()

  // Cresce com o texto até ALTURA_MAX (recalcula também quando o placeholder muda de tamanho).
  useEffect(() => {
    const el = campo.current
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, ALTURA_MAX) + 'px'
  }, [texto, celular])

  // Devolve o foco ao campo quando uma resposta chega (enviando: true -> false).
  // Não foca ao montar: no celular isso abriria o teclado sem o usuário pedir
  // e tiraria o foco do botão do menu ao trocar de conversa.
  const enviandoAntes = useRef(enviando)
  useEffect(() => {
    if (enviandoAntes.current && !enviando) campo.current?.focus()
    enviandoAntes.current = enviando
  }, [enviando])

  function enviar(e) {
    e?.preventDefault()
    if (onEnviar(texto)) setTexto('')
  }

  function aoTeclar(e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) enviar(e)
  }

  const podeEnviar = texto.trim().length > 0 && !enviando

  return (
    <form className={styles.wrap} onSubmit={enviar}>
      <div className={styles.composer}>
        <label htmlFor="pergunta" className="sr-only">Sua pergunta</label>
        <textarea
          id="pergunta"
          ref={campo}
          rows={1}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={aoTeclar}
          placeholder={celular ? 'Escreva sua pergunta…' : 'Pergunte sobre rematrícula, documentos, prazos…'}
          className={styles.campo}
        />
        {/* O nome acessível é fixo; aria-busy sinaliza o carregamento (a resposta é anunciada pelo role="log"). */}
        <button type="submit" className={styles.enviar} disabled={!podeEnviar} aria-label="Enviar pergunta" aria-busy={enviando}>
          {enviando ? (
            <span className={styles.carregando} aria-hidden="true" />
          ) : (
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20">
              <path d="M10 15.5v-11M5 9.5l5-5 5 5" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>
      </div>
      <p className={styles.dica}>
        Respostas a partir de documentos oficiais da FECAP.
        <span className={styles.atalhos}> Enter envia, Shift+Enter pula linha.</span>
      </p>
    </form>
  )
}
