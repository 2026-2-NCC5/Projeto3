// Cadastro de documento (versão 1). O backend divide em trechos e gera os vetores.
import { cloneElement, useState } from 'react'
import { api, erroDoCampo } from '../../api/api.js'
import { Link, navegar } from '../../rotas/roteador.jsx'
import { useOnline, useTituloPagina } from '../../util/hooks.js'
import { CATEGORIAS_DOC, rotuloCategoriaDoc } from './Documentos.jsx'
import s from './Admin.module.css'

export default function NovoDocumento() {
  useTituloPagina('Cadastrar documento')
  const online = useOnline()
  const [campos, setCampos] = useState({ titulo: '', categoria: '', fonte: '', conteudo: '', data: '' })
  const [erro, setErro] = useState(null)
  const [locais, setLocais] = useState({})
  const [enviando, setEnviando] = useState(false)
  const set = (k) => (e) => setCampos((c) => ({ ...c, [k]: e.target.value }))
  const msg = (k) => locais[k] ?? erroDoCampo(erro, k)

  async function enviar(e) {
    e.preventDefault()
    const l = {}
    if (campos.titulo.trim().length < 3) l.titulo = 'Use pelo menos 3 caracteres.'
    if (!campos.categoria) l.categoria = 'Escolha a categoria.'
    if (campos.fonte.trim().length < 3) l.fonte = 'Informe a referência oficial (ex.: Manual do Aluno, seção 4.2).'
    if (campos.conteudo.trim().length < 20) l.conteudo = 'O conteúdo precisa ter pelo menos 20 caracteres.'
    setLocais(l)
    setErro(null)
    if (Object.keys(l).length) { document.getElementById(`doc-${Object.keys(l)[0]}`)?.focus(); return }
    setEnviando(true)
    try {
      const doc = await api.cadastrarDocumento({
        titulo: campos.titulo.trim(), categoria: campos.categoria, fonte: campos.fonte.trim(), conteudo: campos.conteudo,
        ...(campos.data ? { data_atualizacao: new Date(`${campos.data}T00:00:00Z`).toISOString() } : {}),
      })
      navegar(`/admin/documentos/${doc.id}?criado=1`, { substituir: true })
    } catch (err) {
      setErro(err)
    } finally { setEnviando(false) }
  }

  return (
    <>
      <Link to="/admin/documentos" className="voltar"><span aria-hidden="true">←</span> Base de conhecimento</Link>
      <div className="cabecalho-pagina">
        <div>
          <h1>Cadastrar documento</h1>
          <p>O documento entra no chat assim que os trechos forem vetorizados. Se a vetorização falhar, nada é gravado.</p>
        </div>
      </div>
      <form className={`painel ${s.bloco} ${s.form}`} onSubmit={enviar} noValidate>
        <Campo id="doc-titulo" rotulo="Título" erro={msg('titulo')}>
          <input id="doc-titulo" className="input" value={campos.titulo} onChange={set('titulo')} maxLength={200} />
        </Campo>
        <div className={s.form2}>
          <Campo id="doc-categoria" rotulo="Categoria" erro={msg('categoria')}>
            <select id="doc-categoria" className="select" value={campos.categoria} onChange={set('categoria')}>
              <option value="">Escolha</option>
              {CATEGORIAS_DOC.map((c) => <option key={c} value={c}>{rotuloCategoriaDoc(c)}</option>)}
            </select>
          </Campo>
          <Campo id="doc-data" rotulo="Data de atualização (opcional)" ajuda="Vazio = hoje. É a data mostrada ao estudante.">
            <input id="doc-data" className="input" type="date" value={campos.data} onChange={set('data')} />
          </Campo>
        </div>
        <Campo id="doc-fonte" rotulo="Referência oficial" erro={msg('fonte')} ajuda="Aparece no rodapé das respostas. Ex.: Regulamento Acadêmico, Art. 27.">
          <input id="doc-fonte" className="input" value={campos.fonte} onChange={set('fonte')} maxLength={300} />
        </Campo>
        <Campo id="doc-conteudo" rotulo="Conteúdo" erro={msg('conteudo')} ajuda="Texto oficial completo. Passos em linhas numeradas ajudam o chat a responder em passo a passo.">
          <textarea id="doc-conteudo" className={`textarea ${s.conteudoCampo}`} value={campos.conteudo} onChange={set('conteudo')} maxLength={100000} />
        </Campo>
        {erro && erro.codigo !== 'validacao' && <div className={s.erroForm} role="alert">{erro.codigo === 'indisponivel' ? 'Não foi possível vetorizar o documento agora, então ele não foi gravado. Tente de novo em instantes.' : erro.mensagem}</div>}
        <div className={s.acoesForm}>
          <button type="submit" className="btn btn--primario" aria-busy={enviando} disabled={enviando || !online}>{enviando ? 'Cadastrando e vetorizando…' : 'Cadastrar documento'}</button>
          <Link to="/admin/documentos" className="btn btn--secundario">Cancelar</Link>
        </div>
      </form>
    </>
  )
}

export function Campo({ id, rotulo, erro, ajuda, children }) {
  const descr = [ajuda && `${id}-ajuda`, erro && `${id}-erro`].filter(Boolean).join(' ') || undefined
  return (
    <div className="campo">
      <label className="campo__rotulo" htmlFor={id}>{rotulo}</label>
      {cloneElement(children, { 'aria-invalid': erro ? true : undefined, 'aria-describedby': descr })}
      {ajuda && <span className="campo__ajuda" id={`${id}-ajuda`}>{ajuda}</span>}
      {erro && <span className="campo__erro" id={`${id}-erro`}>{erro}</span>}
    </div>
  )
}
