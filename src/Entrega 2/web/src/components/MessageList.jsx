import { useEffect, useRef } from 'react'
import Message from './Message.jsx'
import styles from './MessageList.module.css'

export default function MessageList({ conversaId, mensagens, onTentarDeNovo, onEncaminhar }) {
  const fim = useRef(null)
  const ultima = mensagens[mensagens.length - 1]

  // Rola até o fim ao trocar de conversa e quando a última mensagem muda (nova pergunta ou resposta).
  useEffect(() => {
    fim.current?.scrollIntoView({ block: 'end' })
  }, [conversaId, ultima?.id, ultima?.tipo])

  return (
    // role="log": leitores de tela anunciam as mensagens novas sem roubar o foco.
    <div role="log" aria-label="Conversa" className={styles.wrap}>
      <ol className={styles.lista}>
        {mensagens.map((m) => (
          <Message key={m.id} mensagem={m} onTentarDeNovo={onTentarDeNovo} onEncaminhar={onEncaminhar} />
        ))}
      </ol>
      <div ref={fim} />
    </div>
  )
}
