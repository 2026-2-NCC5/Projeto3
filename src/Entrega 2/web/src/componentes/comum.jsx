// Peças pequenas reaproveitadas por todas as telas. Classes de base.css (design system).
import { useEffect, useRef } from 'react'
import { ROTULO } from '../util/formatar.js'
import { useOnline } from '../util/hooks.js'

export function BadgeRisco({ categoria, ajustada = false }) {
  return (
    <span className={`badge-risco badge-risco--${categoria}`}>
      {ROTULO.categoria[categoria]}
      {ajustada && <span className="sr-only"> (ajustada por atendente)</span>}
    </span>
  )
}

export function Esqueleto({ linhas = 4, rotulo = 'Carregando' }) {
  return (
    <div className="esqueleto-bloco" aria-busy="true" role="status">
      <span className="sr-only">{rotulo}</span>
      <span className="esqueleto esqueleto--titulo" />
      {Array.from({ length: linhas }, (_, i) => <span key={i} className="esqueleto" style={{ width: `${95 - ((i * 17) % 40)}%` }} />)}
    </div>
  )
}

// Estado de erro com "Tentar de novo". Usa a mensagem do contrato quando houver.
export function EstadoErro({ erro, titulo = 'Não foi possível carregar', onTentar, children }) {
  const online = useOnline()
  if (!online || erro?.codigo === 'rede') {
    return (
      <div className="estado estado--offline" role="status">
        <p className="estado__titulo">Você está sem conexão</p>
        <p className="estado__texto">Assim que a internet voltar, tente de novo. Nada do que você preencheu foi perdido.</p>
        {onTentar && <div className="estado__acoes"><button type="button" className="btn btn--secundario btn--sm" onClick={onTentar}>Tentar de novo</button></div>}
      </div>
    )
  }
  return (
    <div className="estado estado--erro" role="alert">
      <p className="estado__titulo">{titulo}</p>
      <p className="estado__texto">{erro?.mensagem ?? 'Algo deu errado. Tente de novo em instantes.'}</p>
      {children}
      {onTentar && <div className="estado__acoes"><button type="button" className="btn btn--primario btn--sm" onClick={onTentar}>Tentar de novo</button></div>}
      {erro?.requestId && <p className="texto-meta">Código para suporte: <span className="numero">{erro.requestId}</span></p>}
    </div>
  )
}

export function EstadoVazio({ titulo, children, acoes }) {
  return (
    <div className="estado" role="status">
      <p className="estado__titulo">{titulo}</p>
      {children && <p className="estado__texto">{children}</p>}
      {acoes && <div className="estado__acoes">{acoes}</div>}
    </div>
  )
}

export function FaixaOffline() {
  const online = useOnline()
  if (online) return null
  return <div className="faixa-aviso" role="status">Você está sem conexão. O que já estava na tela continua visível; as ações voltam quando a internet voltar.</div>
}

// <dialog> nativo: foco preso, Esc fecha, fundo inerte. `aberto` controla showModal/close.
export function Dialogo({ aberto, onFechar, titulo, descricao, children, rotulo, largura = '32rem', fecharComEsc = true, classe = '', tituloOculto = false }) {
  const ref = useRef(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (aberto && !d.open) d.showModal()
    if (!aberto && d.open) d.close()
  }, [aberto])
  return (
    <dialog
      ref={ref}
      className={`dialogo ${classe}`}
      style={{ '--largura-dialogo': largura }}
      aria-labelledby={rotulo ? `${rotulo}-titulo` : undefined}
      aria-describedby={descricao && rotulo ? `${rotulo}-desc` : undefined}
      onCancel={(e) => { e.preventDefault(); if (fecharComEsc) onFechar?.() }}
      onClick={(e) => { if (e.target === e.currentTarget && fecharComEsc) onFechar?.() }}
    >
      {aberto && (
        <div className="dialogo__corpo">
          <h2 id={rotulo ? `${rotulo}-titulo` : undefined} className={tituloOculto ? 'sr-only' : 'dialogo__titulo'}>{titulo}</h2>
          {descricao && <p id={rotulo ? `${rotulo}-desc` : undefined} className="dialogo__descricao">{descricao}</p>}
          {children}
        </div>
      )}
    </dialog>
  )
}

// Paginação simples: "1–25 de 132" + anterior/próxima.
export function Paginacao({ total, pagina, porPagina, onMudar, rotulo = 'itens' }) {
  if (!total) return null
  const paginas = Math.max(1, Math.ceil(total / porPagina))
  const ini = (pagina - 1) * porPagina + 1
  const fim = Math.min(total, pagina * porPagina)
  return (
    <nav className="paginacao" aria-label={`Paginação de ${rotulo}`}>
      <p className="texto-meta numero" aria-live="polite">{ini}–{fim} de {total.toLocaleString('pt-BR')} {rotulo}</p>
      <div className="paginacao__botoes">
        <button type="button" className="btn btn--secundario btn--sm" disabled={pagina <= 1} onClick={() => onMudar(pagina - 1)}>Anterior</button>
        <span className="texto-meta numero">Página {pagina} de {paginas}</span>
        <button type="button" className="btn btn--secundario btn--sm" disabled={pagina >= paginas} onClick={() => onMudar(pagina + 1)}>Próxima</button>
      </div>
    </nav>
  )
}
