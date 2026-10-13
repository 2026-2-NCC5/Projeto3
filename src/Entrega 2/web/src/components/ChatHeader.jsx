import styles from './ChatHeader.module.css'

export default function ChatHeader({ titulo, subtitulo = [], mock, botaoMenuRef, botaoMenu }) {
  return (
    <header>
      {mock && (
        <p className={styles.mock} role="status">
          Modo de teste: as respostas são simuladas no navegador e não vêm da API.
        </p>
      )}
      <div className={styles.barra}>
        <button
          type="button"
          ref={botaoMenuRef}
          className={styles.menu}
          onClick={botaoMenu.aoClicar}
          aria-label={botaoMenu.rotulo}
          aria-controls="sidebar"
          aria-expanded={botaoMenu.expandido}
          title={botaoMenu.rotulo}
        >
          {/* Celular: o painel abre sobre a tela (hambúrguer). Desktop: o painel é fixo e o botão o recolhe (ícone de painel). */}
          <svg className={styles.iconeMenu} aria-hidden="true" width="20" height="20" viewBox="0 0 20 20"><path d="M3 5.5h14M3 10h14M3 14.5h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          <svg className={styles.iconePainel} aria-hidden="true" width="20" height="20" viewBox="0 0 20 20">
            <path className={styles.painelAberto} d="M5.5 4H8v12H5.5A2.5 2.5 0 0 1 3 13.5v-7A2.5 2.5 0 0 1 5.5 4Z" fill="currentColor" stroke="none" />
            <rect x="3" y="4" width="14" height="12" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
            <path d="M8 4v12" stroke="currentColor" strokeWidth="1.8" />
          </svg>
        </button>
        <div className={styles.textos}>
          <h1 className={styles.titulo}>{titulo}</h1>
          {subtitulo.length > 0 && (
            // Cada parte não quebra por dentro: em tela estreita a linha só quebra no separador " · ".
            <p className={styles.subtitulo}>
              {subtitulo.map((parte, i) => (
                <span key={parte}>
                  <span className={styles.parte}>{parte}</span>
                  {i < subtitulo.length - 1 && ' · '}
                </span>
              ))}
            </p>
          )}
        </div>
      </div>
    </header>
  )
}
