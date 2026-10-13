import Sidebar from './components/Sidebar.jsx'
import ChatHeader from './components/ChatHeader.jsx'
import WelcomeScreen from './components/WelcomeScreen.jsx'
import MessageList from './components/MessageList.jsx'
import Composer from './components/Composer.jsx'
import { useConversas } from './hooks/useConversas.js'
import { useMenuLateral } from './hooks/useMenuLateral.js'
import { modoMockAtivo } from './api/mock.js'
import { proximasSugestoes } from './data/demo.js'
import { fonteMaisRecente } from './utils/formatar.js'
import styles from './App.module.css'

export default function App() {
  const chat = useConversas()
  const menu = useMenuLateral()
  const { ativa } = chat
  const vazia = ativa.mensagens.length === 0
  const dataFonte = fonteMaisRecente(ativa.mensagens)
  // Uma só linha secundária sob o título: "Conversa de demonstração · Fonte mais recente: ...".
  const subtitulo = [
    ativa.demo && 'Conversa de demonstração',
    dataFonte && `Fonte mais recente: ${dataFonte}`,
  ].filter(Boolean)

  // No celular, escolher algo no menu fecha o painel (e devolve o foco ao botão do menu).
  const fecharSeAberto = () => menu.aberto && menu.fechar()

  return (
    <div className={styles.app}>
      <Sidebar
        conversas={chat.conversas}
        ativaId={ativa.id}
        onNova={() => { chat.nova(); fecharSeAberto() }}
        onSelecionar={(id) => { chat.selecionar(id); fecharSeAberto() }}
        onFechar={menu.fechar}
        aberta={menu.aberto}
        recolhida={menu.recolhida}
        painelRef={menu.painelRef}
      />
      {menu.aberto && <div className={styles.fundo} onClick={menu.fechar} aria-hidden="true" />}

      <main className={styles.main} ref={menu.conteudoRef}>
        <ChatHeader
          titulo={vazia ? 'Nova conversa' : ativa.titulo}
          subtitulo={subtitulo}
          mock={modoMockAtivo()}
          botaoMenuRef={menu.botaoRef}
          botaoMenu={menu.botao}
        />

        <div className={styles.rolagem}>
          {vazia ? (
            <WelcomeScreen onEscolher={chat.enviar} desabilitado={chat.enviando} />
          ) : (
            <MessageList
              conversaId={ativa.id}
              mensagens={ativa.mensagens}
              sugestoes={proximasSugestoes(ativa.mensagens)}
              desabilitado={chat.enviando}
              onTentarDeNovo={(m) => chat.tentarDeNovo(ativa.id, m)}
              onEncaminhar={() => chat.encaminhar(ativa.id)}
              onEscolher={chat.enviar}
            />
          )}
        </div>

        <Composer
          key={ativa.id}
          onEnviar={chat.enviar}
          enviando={chat.enviando}
        />
      </main>
    </div>
  )
}
