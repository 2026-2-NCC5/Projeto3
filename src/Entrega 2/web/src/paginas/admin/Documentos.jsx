// Base de conhecimento: lista de documentos oficiais que alimentam o chat.
import { useEffect, useState } from 'react'
import { api } from '../../api/api.js'
import { Link, navegar, useLocalizacao } from '../../rotas/roteador.jsx'
import { EstadoErro, EstadoVazio, Esqueleto, Paginacao } from '../../componentes/comum.jsx'
import { useCarregar, useDebounce, useMidia, useTituloPagina } from '../../util/hooks.js'
import { dataCurta } from '../../util/formatar.js'
import s from './Admin.module.css'

export const CATEGORIAS_DOC = [
  'servicos_academicos', 'bolsas_financiamentos', 'documentos_academicos', 'servicos_financeiros', 'biblioteca', 'aprendizagem',
  'plataformas_digitais', 'carreira_empregabilidade', 'infraestrutura', 'alumni', 'boas_praticas', 'dados_cadastrais', 'eventos',
  'seguranca', 'documentos_financeiros', 'servicos_candidatos', 'transporte_estacionamento', 'internacionalizacao', 'reservas_recursos',
]
const NOMES_CATEGORIA = {
  servicos_academicos: 'Serviços acadêmicos', bolsas_financiamentos: 'Bolsas e financiamentos', documentos_academicos: 'Documentos acadêmicos',
  servicos_financeiros: 'Serviços financeiros', biblioteca: 'Biblioteca', aprendizagem: 'Aprendizagem', plataformas_digitais: 'Plataformas digitais',
  carreira_empregabilidade: 'Carreira e empregabilidade', infraestrutura: 'Infraestrutura', alumni: 'Alumni', boas_praticas: 'Boas práticas',
  dados_cadastrais: 'Dados cadastrais', eventos: 'Eventos', seguranca: 'Segurança', documentos_financeiros: 'Documentos financeiros',
  servicos_candidatos: 'Serviços para candidatos', transporte_estacionamento: 'Transporte e estacionamento', internacionalizacao: 'Internacionalização',
  reservas_recursos: 'Reservas de recursos',
}
export const rotuloCategoriaDoc = (c) => NOMES_CATEGORIA[c] ?? (c ? c.replaceAll('_', ' ').replace(/^./, (x) => x.toUpperCase()) : '')

export default function Documentos() {
  useTituloPagina('Base de conhecimento')
  const { busca: params, url } = useLocalizacao()
  const f = { busca: params.get('busca') ?? '', categoria: params.get('categoria') ?? '', ativo: params.get('ativo') ?? 'true', pagina: Math.max(1, Number(params.get('pagina')) || 1) }
  const [texto, setTexto] = useState(f.busca)
  const textoDeb = useDebounce(texto.trim(), 350)
  const largo = useMidia('(min-width: 760px)')

  const mudar = (parcial) => {
    const n = { ...f, pagina: 1, ...parcial }
    const p = new URLSearchParams()
    if (n.busca) p.set('busca', n.busca)
    if (n.categoria) p.set('categoria', n.categoria)
    if (n.ativo !== 'true') p.set('ativo', n.ativo)
    if (n.pagina > 1) p.set('pagina', n.pagina)
    navegar(`/admin/documentos${p.toString() ? `?${p}` : ''}`, { substituir: true })
  }
  useEffect(() => { if (textoDeb !== f.busca) mudar({ busca: textoDeb }) }, [textoDeb]) // eslint-disable-line react-hooks/exhaustive-deps

  const { dados, erro, carregando, recarregar } = useCarregar(({ signal }) => api.listarDocumentos({
    busca: f.busca || undefined, categoria: f.categoria || undefined, ativo: f.ativo === 'todos' ? undefined : f.ativo, pagina: f.pagina, por_pagina: 25,
  }, { signal }), [url])

  return (
    <>
      <div className="cabecalho-pagina">
        <div>
          <h1>Base de conhecimento</h1>
          <p>Documentos oficiais que o ASA Turbo usa para responder. A data de atualização aparece nas fontes do chat.</p>
        </div>
        <Link to="/admin/documentos/novo" className="btn btn--primario">Cadastrar documento</Link>
      </div>

      <div className={s.filtrosDocs}>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="doc-busca">Buscar</label>
          <input id="doc-busca" className="input" type="search" placeholder="Título do documento" value={texto} onChange={(e) => setTexto(e.target.value)} />
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="doc-cat">Categoria</label>
          <select id="doc-cat" className="select" value={f.categoria} onChange={(e) => mudar({ categoria: e.target.value })}>
            <option value="">Todas</option>
            {CATEGORIAS_DOC.map((c) => <option key={c} value={c}>{rotuloCategoriaDoc(c)}</option>)}
          </select>
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor="doc-ativo">Situação</label>
          <select id="doc-ativo" className="select" value={f.ativo} onChange={(e) => mudar({ ativo: e.target.value })}>
            <option value="true">Ativos</option>
            <option value="false">Desativados</option>
            <option value="todos">Todos</option>
          </select>
        </div>
      </div>

      <div aria-live="polite" aria-busy={carregando}>
        {erro && !dados ? <EstadoErro erro={erro} titulo="Não foi possível carregar os documentos" onTentar={recarregar} />
          : !dados ? <Esqueleto linhas={8} rotulo="Carregando documentos" />
            : dados.itens.length === 0 ? (
              <EstadoVazio titulo="Nenhum documento encontrado" acoes={<Link to="/admin/documentos/novo" className="btn btn--secundario btn--sm">Cadastrar documento</Link>}>
                {f.busca || f.categoria ? 'Tente outro termo ou outra categoria.' : 'Cadastre o primeiro documento oficial da base.'}
              </EstadoVazio>
            ) : (
              <>
                {largo ? (
                  <div className="tabela-container">
                    <table className="tabela">
                      <caption className="sr-only">Documentos da base de conhecimento</caption>
                      <thead><tr><th scope="col">Documento</th><th scope="col">Categoria</th><th scope="col" className="num">Versão</th><th scope="col">Atualizado em</th><th scope="col" className="num">Trechos</th><th scope="col">Situação</th></tr></thead>
                      <tbody>
                        {dados.itens.map((d) => (
                          <tr key={d.id} className={d.ativo ? undefined : s.inativo}>
                            <td className={s.tituloDoc}><Link to={`/admin/documentos/${d.id}`}>{d.titulo}</Link><span className={s.fonteDoc}>{d.fonte}</span></td>
                            <td>{rotuloCategoriaDoc(d.categoria)}</td>
                            <td className="num">v{d.versao}</td>
                            <td className="numero">{dataCurta(d.data_atualizacao)}</td>
                            <td className="num">{d.total_chunks}{d.chunks_sem_embedding > 0 && <span className={s.pendente}>{d.chunks_sem_embedding} sem vetor</span>}</td>
                            <td><span className="etiqueta">{d.ativo ? 'Ativo' : 'Desativado'}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <ul className={s.listaDocs}>
                    {dados.itens.map((d) => (
                      <li key={d.id}><Link to={`/admin/documentos/${d.id}`}>
                        <strong>{d.titulo}</strong>
                        <span>{rotuloCategoriaDoc(d.categoria)} · v{d.versao} · {dataCurta(d.data_atualizacao)}{d.ativo ? '' : ' · desativado'}</span>
                      </Link></li>
                    ))}
                  </ul>
                )}
                <Paginacao total={dados.total} pagina={dados.pagina} porPagina={dados.por_pagina} rotulo="documentos" onMudar={(p) => mudar({ pagina: p })} />
              </>
            )}
      </div>
    </>
  )
}
