import { useEffect, useId, useState } from 'react'
import TextoFormatado from './TextoFormatado.jsx'
import FichaFonte from './FichaFonte.jsx'
import { IconeAlerta, IconeAtendimento, IconeInfo } from './Icones.jsx'
import styles from './Message.module.css'

export default function Message({ mensagem, onTentarDeNovo, onEncaminhar }) {
  if (mensagem.autor === 'estudante') {
    return (
      <li className={styles.estudante}>
        <span className="sr-only">Você perguntou:</span>
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
        <Conteudo m={mensagem} onTentarDeNovo={onTentarDeNovo} onEncaminhar={onEncaminhar} />
      </div>
    </li>
  )
}

function Resposta({ m }) {
  const idRotulo = useId()
  const [principal, ...outras] = m.evidencias ?? []
  // Na API atual, a resposta É o trecho do 1º documento; não repetir o mesmo texto na ficha.
  const trechoRepetido = principal && principal.trecho.trim() === m.texto.trim()

  return (
    <>
      <TextoFormatado texto={m.texto} />

      {principal && (
        // role="group" (e não <section>) para não criar uma região de navegação por resposta.
        <div className={styles.fontes} role="group" aria-labelledby={idRotulo}>
          <p id={idRotulo} className={styles.rotulo}>Fonte</p>
          <FichaFonte evidencia={principal} ocultarTrecho={trechoRepetido} />
          {outras.length > 0 && <OutrosDocumentos evidencias={outras} />}
        </div>
      )}
    </>
  )
}

function OutrosDocumentos({ evidencias }) {
  const [aberto, setAberto] = useState(false)
  const id = useId()
  return (
    <div className={styles.outros}>
      <button type="button" className={styles.botaoTexto} aria-expanded={aberto} aria-controls={id} onClick={() => setAberto((a) => !a)}>
        {aberto ? 'Ocultar outros documentos consultados' : `Outros documentos consultados (${evidencias.length})`}
      </button>
      <div id={id} hidden={!aberto} className={styles.outrosLista}>
        {evidencias.map((ev, i) => <FichaFonte key={i} evidencia={ev} compacta />)}
      </div>
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
      <span>{demorando ? 'Ainda consultando, isso pode levar alguns segundos…' : 'Consultando documentos oficiais…'}</span>
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
