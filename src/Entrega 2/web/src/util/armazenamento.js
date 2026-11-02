// Preferências locais (localStorage), sempre por usuário e sem conteúdo de conversa.
// Guardamos só: ids de conversas ocultadas e o nome que o estudante deu a uma conversa.
// Tudo é apagado ao sair. O token fica a cargo do supabase-js.
const prefixo = (usuarioId) => `asa:${usuarioId}:`

export function lerLocal(usuarioId, chave, padrao) {
  try {
    const v = localStorage.getItem(prefixo(usuarioId) + chave)
    return v ? JSON.parse(v) : padrao
  } catch { return padrao }
}

export function gravarLocal(usuarioId, chave, valor) {
  try { localStorage.setItem(prefixo(usuarioId) + chave, JSON.stringify(valor)) } catch { /* sem storage: vale só nesta sessão */ }
}

export function limparPreferenciasLocais(usuarioId) {
  try {
    for (const k of Object.keys(localStorage)) if (k.startsWith(prefixo(usuarioId))) localStorage.removeItem(k)
  } catch { /* sem storage */ }
}
