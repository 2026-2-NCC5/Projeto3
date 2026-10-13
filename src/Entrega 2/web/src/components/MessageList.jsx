import { useEffect, useId, useRef } from 'react'
import Message from './Message.jsx'
import styles from './MessageList.module.css'

// Só depois de uma resposta, abstenção ou atendimento: nunca durante o carregamento nem sobre um erro.
const TIPOS_COM_SUGESTAO = ['resposta', 'abstencao', 'encaminhamento']

export default function MessageList({ conversaId, mensagens, sugestoes = [], desabilitado, onTentarDeNovo, onEncaminhar, onEscolher }) {
  const fim = useRef(null)
  const ultima = mensagens[mensagens.length - 1]

  // Rola até o fim ao trocar de conversa e quando a última mensagem muda (nova pergunta ou resposta).
  useEffect(() => {
    fim.current?.scrollIntoView({ block: 'end' })
  }, [conversaId, ultima?.id, ultima?.tipo])

  const idSugestoes = useId()
  const mostrarSugestoes = sugestoes.length > 0 && TIPOS_COM_SUGESTAO.includes(ultima?.tipo)

  return (
    <div className={styles.wrap}>
      {/* role="log": leitores de tela anunciam as mensagens novas sem roubar o foco. */}
      <div role="log" aria-label="Conversa">
        <ol className={styles.lista}>
          {mensagens.map((m) => (
            <Message key={m.id} mensagem={m} onTentarDeNovo={onTentarDeNovo} onEncaminhar={onEncaminhar} />
          ))}
        </ol>
      </div>

      {/* Sugestões de continuação: no fluxo, depois da última mensagem (não fixas sobre o campo). */}
      {mostrarSugestoes && (
        <div className={styles.continuar}>
          <p id={idSugestoes} className={styles.continuarRotulo}>Você também pode perguntar:</p>
          <ul className={styles.sugestoes} aria-labelledby={idSugestoes}>
            {sugestoes.map((s) => (
              <li key={s}>
                <button type="button" className={styles.chip} onClick={() => onEscolher(s)} disabled={desabilitado}>{s}</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div ref={fim} />
    </div>
  )
}
