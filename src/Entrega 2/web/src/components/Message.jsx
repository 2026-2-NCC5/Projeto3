import { useEffect, useId, useRef, useState } from 'react'
import TextoFormatado from './TextoFormatado.jsx'
import FichaFonte from './FichaFonte.jsx'
import { IconeAlerta, IconeAtendimento, IconeCopiar, IconeInfo, IconePolegarBaixo, IconePolegarCima, IconeSeta } from './Icones.jsx'
import { formatarHora } from '../utils/formatar.js'
import { removerNegrito } from '../utils/negrito.js'
import { modoMockAtivo } from '../api/mock.js'
import styles from './Message.module.css'

// Horário só quando a mensagem foi criada nesta sessão (conversas de exemplo não têm).
function Hora({ ms }) {
  const hora = formatarHora(ms)
  if (!hora) return null
  return <time className={styles.hora} dateTime={new Date(ms).toISOString()}>{hora}</time>
}

export default function Message({ mensagem, onTentarDeNovo, onEncaminhar }) {
  if (mensagem.autor === 'estudante') {
    return (
      <li className={styles.estudante}>
        <span className="sr-only">Você perguntou:</span>
        <Hora ms={mensagem.criadoEm} />
        <div className={styles.bolha}>{mensagem.texto}</div>
      </li>
    )
  }

  const Conteudo = {
    carregando: Carregando,
    resposta: Resposta,
    abstencao: Abstencao,
    erro: Erro,
    encaminhamento: Encaminhamento,
  }[mensagem.tipo]

  return (
    <li className={styles.asa}>
      <span className={styles.avatar} aria-hidden="true">
        <img src="/logo-asaturbo.png" alt="" />
      </span>
      <div className={styles.corpo}>
        <span className="sr-only">ASA respondeu:</span>
        {mensagem.tipo !== 'carregando' && <Hora ms={mensagem.criadoEm} />}
        <Conteudo m={mensagem} onTentarDeNovo={onTentarDeNovo} onEncaminhar={onEncaminhar} />
      </div>
    </li>
  )
}

function Resposta({ m }) {
  const [principal, ...outras] = m.evidencias ?? []
  const [outrosAbertos, setOutrosAbertos] = useState(false)
  const idOutros = useId()
  // Na API atual, a resposta É o trecho do 1º documento; não repetir o mesmo texto na ficha.
  // Comparação sem a marcação de negrito, que não existe no trecho.
  const trechoRepetido = principal && principal.trecho.trim() === removerNegrito(m.texto).trim()
  const demonstracao = modoMockAtivo()

  return (
    <>
      <TextoFormatado texto={m.texto} />

      {principal && (
        // role="group" (e não <section>) para não criar uma região de navegação por resposta.
        <div className={styles.fontes} role="group" aria-label="Fonte">
          <FichaFonte evidencia={principal} ocultarTrecho={trechoRepetido} rotulo="Fonte" demonstracao={demonstracao} />
        </div>
      )}

      <div className={styles.rodape}>
        {outras.length > 0 ? (
          <button type="button" className={styles.botaoToggle} aria-expanded={outrosAbertos} aria-controls={idOutros} onClick={() => setOutrosAbertos((a) => !a)}>
            <span className={outrosAbertos ? styles.setaAberta : undefined}><IconeSeta tamanho={14} /></span>
            {outrosAbertos ? 'Ocultar outros documentos consultados' : 'Outros documentos consultados (' + outras.length + ')'}
          </button>
        ) : (
          <span />
        )}
        <AcoesResposta texto={removerNegrito(m.texto)} demonstracao={demonstracao} />
      </div>

      {outras.length > 0 && (
        <div id={idOutros} hidden={!outrosAbertos} className={styles.outrosLista}>
          {outras.map((ev, i) => <FichaFonte key={i} evidencia={ev} compacta />)}
        </div>
      )}
    </>
  )
}

// Ícones sob a resposta. Todos com nome acessível (aria-label) e dica (title).
// Copiar é real. Os polegares existem SÓ na demonstração (?mock) e não registram nada:
// o clique só mostra o aviso, sem marcar o botão (nada sugere que o voto foi enviado).
const AVISOS = {
  copiado: 'Copiado',
  falhou: 'Não foi possível copiar',
  voto: 'Demonstração: seu voto não é enviado.',
}
const AVISO_MS = 2500

function AcoesResposta({ texto, demonstracao }) {
  const [aviso, setAviso] = useState('')
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])

  function mostrar(chave) {
    setAviso(chave)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setAviso(''), AVISO_MS)
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto)
      mostrar('copiado')
    } catch {
      mostrar('falhou') // sem permissão, contexto não seguro ou navegador sem a API
    }
  }

  return (
    <div className={styles.acoesResposta}>
      <div className={styles.icones}>
        <button type="button" className={styles.iconeBotao} onClick={copiar} aria-label="Copiar resposta" title="Copiar resposta">
          <IconeCopiar />
        </button>
        {demonstracao && (
          <>
            <button type="button" className={styles.iconeBotao} onClick={() => mostrar('voto')} aria-label="Resposta útil (demonstração)" title="Resposta útil (demonstração)">
              <IconePolegarCima />
            </button>
            <button type="button" className={styles.iconeBotao} onClick={() => mostrar('voto')} aria-label="Resposta não ajudou (demonstração)" title="Resposta não ajudou (demonstração)">
              <IconePolegarBaixo />
            </button>
          </>
        )}
      </div>
      <p role="status" className={styles.confirmacao}>{AVISOS[aviso]}</p>
    </div>
  )
}
const ESPERA_LONGA_MS = 6000

function Carregando() {
  const [demorando, setDemorando] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setDemorando(true), ESPERA_LONGA_MS)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className={styles.carregando}>
      <span className={styles.pontos} aria-hidden="true"><i /><i /><i /></span>
      {/* Antes da espera longa, só os pontos; o texto fica só para leitor de tela. */}
      <span className={demorando ? undefined : 'sr-only'}>
        {demorando ? 'Ainda consultando, isso pode levar alguns segundos…' : 'Consultando a base de documentos'}
      </span>
    </div>
  )
}

// Aviso da conversa (abstenção, erro, atendimento): mesma estrutura (ícone, título, texto, ação);
// só o tom muda. Abstenção e erro pedem atenção e levam fundo suave; o aviso informativo fica sem fundo.
function Aviso({ tom, icone, titulo, children }) {
  return (
    <div className={`${styles.aviso} ${styles[tom]}`}>
      <span className={styles.avisoIcone}>{icone}</span>
      <div className={styles.avisoCorpo}>
        <p className={styles.avisoTitulo}>{titulo}</p>
        {children}
      </div>
    </div>
  )
}

// Texto próprio do frontend. O backend responde "Vou te encaminhar para um atendente",
// mas o encaminhamento ainda não existe de verdade; não repetimos uma promessa que não se cumpre.
function Abstencao({ onEncaminhar }) {
  return (
    <Aviso tom="tomAbstencao" icone={<IconeInfo />} titulo="Não encontrei essa informação">
      <p>
        Nas fontes oficiais disponíveis, não há confiança suficiente para responder.
        Você pode reformular a pergunta ou solicitar atendimento.
      </p>
      <p className={styles.avisoSecundario}>Demonstração: nenhuma solicitação real é enviada.</p>
      <div className={styles.acoes}>
        <button type="button" className={styles.botao} onClick={onEncaminhar}>Falar com atendente (demonstração)</button>
      </div>
    </Aviso>
  )
}

const ERROS = {
  rede: ['Sem conexão com o ASA', 'Não foi possível falar com o servidor. Verifique sua internet e tente de novo.'],
  timeout: ['O ASA demorou demais para responder', 'O servidor não respondeu a tempo. Tente de novo em instantes.'],
  servidor: ['O ASA encontrou um problema', 'O servidor não conseguiu processar a pergunta. Tente de novo em instantes.'],
  resposta_invalida: ['Resposta inesperada do servidor', 'O servidor respondeu em um formato que não reconhecemos. Tente de novo.'],
}

function Erro({ m, onTentarDeNovo }) {
  const [titulo, texto] = ERROS[m.motivo] ?? ERROS.servidor
  return (
    // Sem role="alert": o erro entra dentro do role="log", que já o anuncia. Um alert aninhado
    // seria um segundo anúncio do mesmo texto.
    <Aviso tom="tomErro" icone={<IconeAlerta />} titulo={titulo}>
      <p>{texto}</p>
      <div className={styles.acoes}>
        <button type="button" className={`${styles.botao} ${styles.botaoNeutro}`} onClick={() => onTentarDeNovo(m)}>Tentar de novo</button>
      </div>
    </Aviso>
  )
}

// Encaminhamento SIMULADO: nada é enviado a lugar nenhum (igual à interface antiga).
function Encaminhamento() {
  return (
    <Aviso tom="tomInfo" icone={<IconeAtendimento />} titulo="Atendimento ainda não disponível">
      <p>
        Esta é uma demonstração: nenhum pedido foi enviado. Na versão final, um atendente do ASA
        continuaria a conversa a partir deste histórico.
      </p>
    </Aviso>
  )
}
