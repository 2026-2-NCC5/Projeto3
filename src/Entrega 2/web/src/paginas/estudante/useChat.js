// Estado do chat do estudante, sobre as rotas /chat do contrato.
// - Lista de conversas: GET /chat/conversas (renomear/excluir são só locais, ver armazenamento.js).
// - Conversa aberta: GET /chat/conversas/{id}.
// - Envio: POST /chat com as últimas 6 mensagens como `historico`.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/api.js'
import { gravarLocal, lerLocal } from '../../util/armazenamento.js'
import { navegar } from '../../rotas/roteador.jsx'

const MAX_HISTORICO = 6
let seq = 0
const idLocal = () => `local-${Date.now()}-${++seq}`

function historicoPara(mensagens) {
  return mensagens
    .filter((m) => !m.local || m.estado === 'ok')
    .filter((m) => m.conteudo && !m.erro)
    .slice(-MAX_HISTORICO)
    .map((m) => ({ papel: m.remetente === 'estudante' ? 'estudante' : 'agente', conteudo: m.conteudo.slice(0, 2000) }))
}

export function useChat(usuarioId, conversaIdRota) {
  // ---------------------------------------------------------------- lista lateral
  const [lista, setLista] = useState({ itens: [], carregando: true, erro: null })
  const [prefs, setPrefs] = useState(() => lerLocal(usuarioId, 'conversas', { titulos: {}, ocultas: [] }))
  const salvarPrefs = useCallback((fn) => setPrefs((p) => { const n = fn(p); gravarLocal(usuarioId, 'conversas', n); return n }), [usuarioId])

  const carregarLista = useCallback(async () => {
    setLista((l) => ({ ...l, carregando: true, erro: null }))
    try {
      const r = await api.listarConversas({ por_pagina: 50 })
      setLista({ itens: r.itens, carregando: false, erro: null })
    } catch (erro) {
      setLista((l) => ({ ...l, carregando: false, erro }))
    }
  }, [])
  useEffect(() => { carregarLista() }, [carregarLista])

  const conversas = useMemo(() => lista.itens
    .filter((c) => !prefs.ocultas.includes(c.id))
    .map((c) => ({ ...c, titulo: prefs.titulos[c.id] ?? c.titulo })), [lista.itens, prefs])

  // ------------------------------------------------------------- conversa aberta
  const [conversa, setConversa] = useState({ id: null, titulo: null, status: 'aberta', encaminhamento: null, mensagens: [], carregando: false, erro: null })
  const idAtualRef = useRef(null) // id da conversa cujas mensagens estão na tela
  const [enviando, setEnviando] = useState(false)
  const enviandoRef = useRef(false)

  const abrir = useCallback(async (id, signal) => {
    setConversa({ id, titulo: null, status: 'aberta', encaminhamento: null, mensagens: [], carregando: true, erro: null })
    try {
      const c = await api.obterConversa(id, { signal })
      idAtualRef.current = id
      setConversa({ ...c, carregando: false, erro: null })
    } catch (erro) {
      if (signal?.aborted) return
      setConversa((x) => ({ ...x, carregando: false, erro }))
    }
  }, [])

  useEffect(() => {
    if (!conversaIdRota) {
      if (idAtualRef.current !== null || conversa.mensagens.length) {
        idAtualRef.current = null
        setConversa({ id: null, titulo: null, status: 'aberta', encaminhamento: null, mensagens: [], carregando: false, erro: null })
      }
      return
    }
    // A rota mudou para a conversa que acabamos de criar: as mensagens já estão na tela.
    if (conversaIdRota === idAtualRef.current) return
    const controle = new AbortController()
    abrir(conversaIdRota, controle.signal)
    return () => controle.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversaIdRota, abrir])

  const atualizarMensagem = (id, fn) => setConversa((c) => ({ ...c, mensagens: c.mensagens.map((m) => (m.id === id ? fn(m) : m)) }))

  // ----------------------------------------------------------------------- envio
  const executarEnvio = useCallback(async (texto, idPergunta, mensagensAntes, conversaId) => {
    enviandoRef.current = true
    setEnviando(true)
    try {
      const r = await api.enviarMensagem({ mensagem: texto, conversa_id: conversaId, historico: historicoPara(mensagensAntes) })
      const agora = r.gerada_em
      setConversa((c) => ({
        ...c,
        id: r.conversa_id,
        status: r.abstencao && r.encaminhamento ? 'encaminhada_humano' : c.status,
        encaminhamento: r.encaminhamento ?? c.encaminhamento,
        mensagens: [
          ...c.mensagens.map((m) => (m.id === idPergunta ? { ...m, estado: 'ok', erro: null } : m)),
          {
            id: r.resposta_id, remetente: 'agente', conteudo: r.resposta, criado_em: agora, novo: true,
            resposta: { resposta_id: r.resposta_id, fontes: r.fontes, confianca: r.confianca, abstencao: r.abstencao, motivo_abstencao: r.motivo_abstencao, encaminhamento: r.encaminhamento, feedback: null, versao_modelo: r.versao_modelo },
          },
        ],
      }))
      if (!conversaId) {
        idAtualRef.current = r.conversa_id
        navegar(`/chat/${r.conversa_id}`, { substituir: true })
      }
      carregarLista()
    } catch (erro) {
      atualizarMensagem(idPergunta, (m) => ({ ...m, estado: 'erro', erro }))
    } finally {
      enviandoRef.current = false
      setEnviando(false)
    }
  }, [carregarLista])

  const enviar = useCallback((textoBruto) => {
    const texto = textoBruto.trim()
    if (!texto || enviandoRef.current) return false
    const idPergunta = idLocal()
    const anteriores = conversa.mensagens.filter((m) => m.estado !== 'erro')
    setConversa((c) => ({ ...c, mensagens: [...c.mensagens, { id: idPergunta, local: true, remetente: 'estudante', conteudo: texto, criado_em: new Date().toISOString(), estado: 'pendente' }] }))
    executarEnvio(texto, idPergunta, anteriores, conversa.id)
    return true
  }, [conversa.mensagens, conversa.id, executarEnvio])

  const tentarDeNovo = useCallback((mensagem) => {
    if (enviandoRef.current) return
    const indice = conversa.mensagens.findIndex((m) => m.id === mensagem.id)
    const anteriores = conversa.mensagens.slice(0, indice).filter((m) => m.estado !== 'erro')
    atualizarMensagem(mensagem.id, (m) => ({ ...m, estado: 'pendente', erro: null }))
    executarEnvio(mensagem.conteudo, mensagem.id, anteriores, conversa.id)
  }, [conversa.mensagens, conversa.id, executarEnvio])

  // -------------------------------------------------------------------- feedback
  const avaliar = useCallback(async (respostaId, avaliacao, comentario = null) => {
    await api.enviarFeedback({ resposta_id: respostaId, avaliacao, comentario: comentario || null })
    setConversa((c) => ({
      ...c,
      mensagens: c.mensagens.map((m) => (m.resposta?.resposta_id === respostaId ? { ...m, resposta: { ...m.resposta, feedback: avaliacao } } : m)),
    }))
  }, [])

  // ------------------------------------------------------- renomear/excluir (local)
  const renomear = useCallback((id, titulo) => {
    const t = titulo.trim().slice(0, 80)
    salvarPrefs((p) => {
      const titulos = { ...p.titulos }
      if (t) titulos[id] = t
      else delete titulos[id]
      return { ...p, titulos }
    })
  }, [salvarPrefs])

  const excluir = useCallback((id) => {
    salvarPrefs((p) => ({ ...p, ocultas: [...new Set([...p.ocultas, id])] }))
    if (id === conversa.id) navegar('/chat')
  }, [salvarPrefs, conversa.id])

  const tituloAtual = conversa.id ? (prefs.titulos[conversa.id] ?? conversa.titulo ?? conversas.find((c) => c.id === conversa.id)?.titulo) : null

  return { lista: { ...lista, itens: conversas }, recarregarLista: carregarLista, conversa: { ...conversa, titulo: tituloAtual }, reabrir: () => conversaIdRota && abrir(conversaIdRota), enviando, enviar, tentarDeNovo, avaliar, renomear, excluir }
}
