// Moldura das telas da equipe (atendente, administração, equipe técnica):
// barra superior com marca, navegação por papel, usuário e "Sair".
import { Link, useLocalizacao } from '../rotas/roteador.jsx'
import { NAVEGACAO } from '../rotas/permissoes.js'
import { useSessao } from '../auth/SessaoContext.jsx'
import { FaixaOffline } from './comum.jsx'
import { MODO_MOCK } from '../config.js'
import { ROTULO, iniciais } from '../util/formatar.js'
import s from './Shell.module.css'

export default function Shell({ children }) {
  const { me, sair } = useSessao()
  const { caminho } = useLocalizacao()
  const itens = NAVEGACAO[me.papel] ?? []
  const ativo = (i) => (i.exato ? caminho === i.para : caminho === i.para || caminho.startsWith(i.para + '/'))
  // O item mais específico vence (/admin/documentos não acende "Painel").
  const atual = itens.filter(ativo).sort((a, b) => b.para.length - a.para.length)[0]

  return (
    <div className={s.app}>
      <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
      <header className={s.topo}>
        <div className={s.linha}>
          <Link to={itens[0]?.para ?? '/'} className={s.marca} aria-label="ASA Turbo, início">
            <img src="/marca.png" alt="" width="28" height="28" />
            <span>ASA Turbo</span>
          </Link>
          <nav className={s.nav} aria-label="Principal">
            <ul>
              {itens.map((i) => (
                <li key={i.para}><Link to={i.para} aria-current={atual === i ? 'page' : undefined}>{i.rotulo}</Link></li>
              ))}
            </ul>
          </nav>
          <div className={s.usuario}>
            {MODO_MOCK && <span className={s.demo} title="Dados fictícios, sem backend">Demonstração</span>}
            <span className={s.avatar} aria-hidden="true">{iniciais(me.nome)}</span>
            <span className={s.nomeUsuario}>
              <span>{me.nome}</span>
              <span className={s.papel}>{ROTULO.papel[me.papel]}</span>
            </span>
            <button type="button" className={s.sair} onClick={sair}>Sair</button>
          </div>
        </div>
      </header>
      <FaixaOffline />
      <main id="conteudo" className={s.conteudo} tabIndex={-1}>{children}</main>
    </div>
  )
}
