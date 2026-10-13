import { SUGESTOES, USUARIO_DEMO } from '../data/demo.js'
import styles from './WelcomeScreen.module.css'

// Agrupa as sugestões por tema, mantendo a ordem de SUGESTOES.
function agruparPorTema(sugestoes) {
  const grupos = new Map()
  for (const s of sugestoes) {
    if (!grupos.has(s.tema)) grupos.set(s.tema, [])
    grupos.get(s.tema).push(s.pergunta)
  }
  return [...grupos]
}

export default function WelcomeScreen({ onEscolher, desabilitado }) {
  const primeiroNome = USUARIO_DEMO.nome.split(' ')[0]

  return (
    <section className={styles.welcome} aria-labelledby="welcome-titulo">
      <h2 id="welcome-titulo" className={styles.titulo}>
        Olá, {primeiroNome}. O que você precisa resolver hoje?
      </h2>
      <p className={styles.intro}>
        Pergunte sobre matrícula, documentos, financeiro ou regras acadêmicas.
        Cada resposta mostra o documento oficial de onde ela saiu e quando ele foi atualizado.
      </p>

      <div className={styles.sugestoes}>
        <h3 className={styles.sugestoesTitulo}>Comece por uma destas perguntas</h3>
        {agruparPorTema(SUGESTOES).map(([tema, perguntas]) => (
          <div key={tema} className={styles.grupo}>
            <span className={styles.tema}>{tema}</span>
            <ul>
              {perguntas.map((p) => (
                <li key={p}>
                  <button type="button" className={styles.pergunta} onClick={() => onEscolher(p)} disabled={desabilitado}>
                    {p}
                    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14"><path d="M3 7h8M7.5 3.5 11 7l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}
