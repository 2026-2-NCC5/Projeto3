import { USUARIO_DEMO } from '../data/demo.js'
import styles from './Sidebar.module.css'

export default function Sidebar({ conversas, ativaId, onNova, onSelecionar, onFechar, aberta, recolhida, painelRef }) {
  // Conversa ainda sem mensagem não é histórico: ela é o estado da tela inicial, e o botão
  // "Nova conversa" já leva a ela. Só entra em "Recentes" depois da primeira pergunta.
  const recentes = conversas.filter((c) => !c.demo && c.mensagens.length > 0)
  const exemplos = conversas.filter((c) => c.demo)
  const naTelaInicial = conversas.find((c) => c.id === ativaId)?.mensagens.length === 0

  return (
    <aside
      id="sidebar"
      ref={painelRef}
      className={[styles.sidebar, aberta && styles.aberta, recolhida && styles.recolhida].filter(Boolean).join(' ')}
      aria-label="Conversas"
      role={aberta ? 'dialog' : undefined}
      aria-modal={aberta ? 'true' : undefined}
    >
      <div className={styles.marca}>
        <img src="/logo-asaturbo.png" alt="" className={styles.logo} />
        <div>
          <div className={styles.nome}>ASA</div>
          <div className={styles.subtitulo}>Agente para o Estudante</div>
        </div>
        {/* Só aparece no celular (CSS); no desktop a sidebar é fixa. */}
        <button type="button" className={styles.fechar} onClick={onFechar} aria-label="Fechar conversas">
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18"><path d="M4.5 4.5l9 9M13.5 4.5l-9 9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        </button>
      </div>

      <button type="button" className={styles.nova} onClick={onNova} aria-current={naTelaInicial ? 'true' : undefined}>
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        Nova conversa
      </button>

      <nav className={styles.lista}>
        <Grupo titulo="Recentes" conversas={recentes} ativaId={ativaId} onSelecionar={onSelecionar} />
        <Grupo titulo="Conversas de demonstração" conversas={exemplos} ativaId={ativaId} onSelecionar={onSelecionar} separar={recentes.length > 0} />
      </nav>

      <div className={styles.usuario}>
        <span className={styles.avatar} aria-hidden="true">{USUARIO_DEMO.iniciais}</span>
        <div>
          <div>{USUARIO_DEMO.nome}</div>
          <div className={styles.perfil}>Perfil de demonstração</div>
        </div>
      </div>
    </aside>
  )
}

// separar: divisor sutil acima do grupo (só quando há um grupo antes dele).
function Grupo({ titulo, conversas, ativaId, onSelecionar, separar = false }) {
  if (conversas.length === 0) return null
  return (
    <section className={separar ? styles.grupo + ' ' + styles.separado : styles.grupo}>
      <h2 className={styles.grupoTitulo}>{titulo}</h2>
      <ul>
        {conversas.map((c) => {
          // O título é cortado em 32 caracteres ao criar a conversa; o texto inteiro é a 1ª pergunta.
          const cortado = c.titulo.endsWith('…')
          const completo = cortado ? c.mensagens[0]?.texto ?? c.titulo : c.titulo
          return (
            <li key={c.id}>
              <button
                type="button"
                className={styles.item}
                title={completo}
                aria-label={cortado ? completo : undefined}
                aria-current={c.id === ativaId ? 'page' : undefined}
                onClick={() => onSelecionar(c.id)}
              >
                {c.titulo}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
