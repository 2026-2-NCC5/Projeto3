// Negrito em texto puro: **assim**. Só isso; nenhuma outra marcação é interpretada.
// Marcação sem fechamento fica como texto literal. A API atual envia texto puro,
// então sem "**" o resultado é simplesmente sem negrito.
const NEGRITO = /\*\*([^*\n]+?)\*\*/g

// "a **b** c" -> [{ texto: 'a ', negrito: false }, { texto: 'b', negrito: true }, { texto: ' c', negrito: false }]
export function dividirNegrito(texto) {
  const partes = []
  let fim = 0
  for (const m of texto.matchAll(NEGRITO)) {
    if (m.index > fim) partes.push({ texto: texto.slice(fim, m.index), negrito: false })
    partes.push({ texto: m[1], negrito: true })
    fim = m.index + m[0].length
  }
  if (fim < texto.length) partes.push({ texto: texto.slice(fim), negrito: false })
  return partes
}

// Texto sem a marcação: para copiar e para comparar a resposta com o trecho da fonte.
export function removerNegrito(texto) {
  return texto.replace(NEGRITO, '$1')
}
