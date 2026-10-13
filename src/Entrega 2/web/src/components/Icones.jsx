// Ícones dos avisos da conversa, no estilo Lucide (ISC), desenhados inline: sem dependência nova.
// Todos são decorativos (aria-hidden): o texto ao lado já diz o que o aviso significa.
// Mesmo tamanho (18 px, proporcional ao texto de 16 px) e mesmo traço (~1,7 px renderizado) entre si.
function Base({ children }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.25"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  )
}

// Abstenção: informação (não é erro, é uma ressalva).
export function IconeInfo() {
  return (
    <Base>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </Base>
  )
}

// Erro: alerta.
export function IconeAlerta() {
  return (
    <Base>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </Base>
  )
}

// Pedido de atendimento: atendimento humano.
export function IconeAtendimento() {
  return (
    <Base>
      <path d="M3 11h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Zm0 0a9 9 0 1 1 18 0m0 0v5a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3Z" />
      <path d="M21 16v2a4 4 0 0 1-4 4h-5" />
    </Base>
  )
}
