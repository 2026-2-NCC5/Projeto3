// Estado das conversas, só em memória (some ao recarregar, como na interface antiga).
// Mensagem do ASA: { id, autor: 'asa', tipo: 'carregando' | 'resposta' | 'abstencao' | 'erro' | 'encaminhamento', ... }
import { useCallback, useReducer, useRef, useState } from 'react'
import { perguntar } from '../api/perguntar.js'
import { CONVERSAS_DEMO } from '../data/demo.js'
import { conversaGaleria, modoMockAtivo } from '../api/mock.js'

const TAMANHO_TITULO = 32

let seq = 0
const novoId = (prefixo) => `${prefixo}-${Date.now()}-${++seq}`

function novaConversa() {
  return { id: novoId('c'), titulo: 'Nova conversa', demo: false, mensagens: [] }
}

function estadoInicial() {
  const primeira = novaConversa()
  const exemplos = modoMockAtivo() ? [conversaGaleria(), ...CONVERSAS_DEMO] : CONVERSAS_DEMO
  const abrirGaleria = modoMockAtivo() && new URLSearchParams(window.location.search).get('mock') === 'galeria'
  return { conversas: [primeira, ...exemplos], ativaId: abrirGaleria ? 'mock-galeria' : primeira.id }
}

function atualizarConversa(state, conversaId, fn) {
  return { ...state, conversas: state.conversas.map((c) => (c.id === conversaId ? fn(c) : c)) }
}

function reducer(state, acao) {
  switch (acao.tipo) {
    case 'nova': {
      // Se a conversa ativa ainda está vazia, reaproveita em vez de empilhar conversas vazias.
      const ativa = state.conversas.find((c) => c.id === state.ativaId)
      if (ativa && ativa.mensagens.length === 0) return state
      const conversa = novaConversa()
      return { conversas: [conversa, ...state.conversas], ativaId: conversa.id }
    }
    case 'selecionar':
      return { ...state, ativaId: acao.conversaId }

    case 'perguntar':
      return atualizarConversa(state, acao.conversaId, (c) => ({
        ...c,
        titulo: c.mensagens.length === 0 ? resumir(acao.texto) : c.titulo,
        mensagens: [
          ...c.mensagens,
          { id: novoId('m'), autor: 'estudante', texto: acao.texto, criadoEm: Date.now() },
          { id: acao.respostaId, autor: 'asa', tipo: 'carregando', pergunta: acao.texto },
        ],
      }))

    case 'tentarDeNovo':
      return substituirMensagem(state, acao.conversaId, acao.respostaId, (m) => ({ id: m.id, autor: 'asa', tipo: 'carregando', pergunta: m.pergunta }))

    case 'responder':
      return substituirMensagem(state, acao.conversaId, acao.respostaId, (m) => ({ ...acao.resultado, id: m.id, autor: 'asa', pergunta: m.pergunta, criadoEm: Date.now() }))

    case 'encaminhar':
      return atualizarConversa(state, acao.conversaId, (c) => ({
        ...c,
        mensagens: [...c.mensagens, { id: novoId('m'), autor: 'asa', tipo: 'encaminhamento', criadoEm: Date.now() }],
      }))

    default:
      return state
  }
}

function substituirMensagem(state, conversaId, mensagemId, fn) {
  return atualizarConversa(state, conversaId, (c) => ({
    ...c,
    mensagens: c.mensagens.map((m) => (m.id === mensagemId ? fn(m) : m)),
  }))
}

function resumir(texto) {
  return texto.length > TAMANHO_TITULO ? texto.slice(0, TAMANHO_TITULO).trimEnd() + '…' : texto
}

export function useConversas() {
  const [state, dispatch] = useReducer(reducer, undefined, estadoInicial)
  const [enviando, setEnviando] = useState(false)
  const enviandoRef = useRef(false) // trava síncrona contra clique duplo

  const buscar = useCallback(async (conversaId, respostaId, texto) => {
    enviandoRef.current = true
    setEnviando(true)
    const resultado = await perguntar(texto)
    dispatch({ tipo: 'responder', conversaId, respostaId, resultado })
    enviandoRef.current = false
    setEnviando(false)
  }, [])

  const enviar = useCallback((texto) => {
    const pergunta = texto.trim()
    if (!pergunta || enviandoRef.current) return false
    const respostaId = novoId('m')
    dispatch({ tipo: 'perguntar', conversaId: state.ativaId, texto: pergunta, respostaId })
    buscar(state.ativaId, respostaId, pergunta)
    return true
  }, [state.ativaId, buscar])

  const tentarDeNovo = useCallback((conversaId, mensagem) => {
    if (enviandoRef.current) return
    dispatch({ tipo: 'tentarDeNovo', conversaId, respostaId: mensagem.id })
    buscar(conversaId, mensagem.id, mensagem.pergunta)
  }, [buscar])

  return {
    conversas: state.conversas,
    ativa: state.conversas.find((c) => c.id === state.ativaId),
    enviando,
    nova: () => dispatch({ tipo: 'nova' }),
    selecionar: (conversaId) => dispatch({ tipo: 'selecionar', conversaId }),
    enviar,
    tentarDeNovo,
    encaminhar: (conversaId) => dispatch({ tipo: 'encaminhar', conversaId }),
  }
}
