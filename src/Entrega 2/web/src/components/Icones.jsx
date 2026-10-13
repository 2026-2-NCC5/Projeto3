// Ícones dos avisos da conversa, no estilo Lucide (ISC), desenhados inline: sem dependência nova.
// Todos são decorativos (aria-hidden): o texto ao lado já diz o que o aviso significa.
// Mesmo tamanho (18 px, proporcional ao texto de 16 px) e mesmo traço (~1,7 px renderizado) entre si.
function Base({ children, tamanho = 18 }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={tamanho}
      height={tamanho}
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

// Ações sob a resposta (Lucide): copiar, útil, não ajudou; e o "abrir" e a seta da ficha.
export function IconeCopiar() {
  return (
    <Base>
      <rect x="8" y="8" width="14" height="14" rx="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </Base>
  )
}
export function IconePolegarCima() {
  return (
    <Base>
      <path d="M7 10v12" />
      <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
    </Base>
  )
}
export function IconePolegarBaixo() {
  return (
    <Base>
      <path d="M17 14V2" />
      <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
    </Base>
  )
}
export function IconeAbrir({ tamanho }) {
  return (
    <Base tamanho={tamanho}>
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </Base>
  )
}
export function IconeSeta({ tamanho }) {
  return (
    <Base tamanho={tamanho}>
      <path d="m9 18 6-6-6-6" />
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
