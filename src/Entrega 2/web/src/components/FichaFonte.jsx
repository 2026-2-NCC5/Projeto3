// Ficha de fonte: mostra SOMENTE o que veio da API (ou do mock identificado).
// Campo ausente = informação omitida; nada é inventado.
import { useId, useState } from 'react'
import { EXIBIR_CORRESPONDENCIA, formatarData, nivelCorrespondencia } from '../utils/formatar.js'
import { IconeAbrir } from './Icones.jsx'
import styles from './FichaFonte.module.css'

// rotulo: pequeno título em caixa-alta no topo do cartão (só na fonte principal).
// demonstracao: mostra o "Abrir" DESABILITADO; a API não envia a URL do documento (ver Message.jsx).
export default function FichaFonte({ evidencia, ocultarTrecho = false, compacta = false, rotulo, demonstracao = false }) {
  const [aberta, setAberta] = useState(false)
  const idTrecho = useId()
  const idTitulo = useId()
  const data = formatarData(evidencia.atualizadoEm)
  const temTrecho = !ocultarTrecho && evidencia.trecho

  return (
    <article className={compacta ? `${styles.ficha} ${styles.compacta}` : styles.ficha} aria-labelledby={idTitulo}>
      {rotulo && <p className={styles.rotulo}>{rotulo}</p>}
      <div className={styles.topo}>
        {/* Ícone file-text (estilo Lucide), só decorativo: o título já diz que é um documento. */}
        <span className={styles.icone} aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
            <path d="M14 2v4a2 2 0 0 0 2 2h4" />
            <path d="M10 9H8" />
            <path d="M16 13H8" />
            <path d="M16 17H8" />
          </svg>
        </span>

        <div className={styles.info}>
          <p id={idTitulo} className={styles.titulo}>{evidencia.titulo}</p>

          {/* Documento · data, em uma linha secundária. Os separadores são CSS. */}
          <dl className={styles.meta}>
            {evidencia.fonte && (
              <div>
                <dt className="sr-only">Documento</dt>
                <dd>{evidencia.fonte}</dd>
              </div>
            )}
            {data && (
              <div>
                <dt className="sr-only">Atualização</dt>
                <dd>Atualizado em {data}</dd>
              </div>
            )}
            {EXIBIR_CORRESPONDENCIA && (
              <div>
                <dt className="sr-only">Correspondência</dt>
                <dd>Correspondência {nivelCorrespondencia(evidencia.similaridade)} ({Math.round(evidencia.similaridade * 100)}%)</dd>
              </div>
            )}
          </dl>
        </div>

        {demonstracao && !compacta && (
          <button
            type="button"
            className={styles.abrir}
            disabled
            aria-label="Abrir documento (indisponível na demonstração)"
            title="Disponível quando o documento tiver um link"
          >
            Abrir
            <IconeAbrir tamanho={14} />
          </button>
        )}
      </div>

      {temTrecho && (
        <div className={styles.expansao}>
          <button
            type="button"
            className={styles.alternar}
            aria-expanded={aberta}
            aria-controls={idTrecho}
            onClick={() => setAberta((a) => !a)}
          >
            {aberta ? 'Ocultar trecho' : 'Ver trecho do documento'}
            <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12" className={aberta ? styles.setaAberta : undefined}>
              <path d="M3 4.5 6 7.5l3-3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <blockquote id={idTrecho} className={styles.trecho} hidden={!aberta}>
            {evidencia.trecho}
          </blockquote>
        </div>
      )}
    </article>
  )
}
