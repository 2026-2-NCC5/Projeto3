// "2026-08-12T00:00:00+00:00" -> "12 de agosto de 2026" (null se inválida).
// Usa UTC porque a data vem à meia-noite UTC; no fuso de Brasília cairia no dia anterior.
export function formatarData(iso) {
  if (!iso) return null
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return null
  return data.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
}

// O valor é similaridade de cosseno, não probabilidade.
// OCULTO até a busca real voltar e o significado dos valores ser validado com o backend.
// Para reativar: troque para true e revise as faixas abaixo.
export const EXIBIR_CORRESPONDENCIA = false

// Faixas PROVISÓRIAS, não validadas.
export function nivelCorrespondencia(similaridade) {
  if (similaridade >= 0.75) return 'alta'
  if (similaridade >= 0.5) return 'média'
  return 'baixa'
}
