// Modelo de risco em uso (GET /risco/modelo): versão, métricas, limiares e variáveis.
import { api } from '../api/api.js'
import { EstadoErro, Esqueleto } from '../componentes/comum.jsx'
import { useCarregar, useTituloPagina } from '../util/hooks.js'
import { dataHora, pct } from '../util/formatar.js'
import { AvisoDecisao } from './atendente/pecas.jsx'

// Nome legível de cada variável do modelo (o código técnico vai no title).
const NOME_VARIAVEL = {
  tempo_de_curso: 'Tempo de curso',
  mora_sp_capital: 'Mora na capital (SP)',
  total_parcelas: 'Total de parcelas do contrato',
  pct_parcelas_em_aberto: 'Parcelas em aberto (%)',
  pct_parcelas_acordo: 'Parcelas em acordo (%)',
  atraso_medio_dias: 'Atraso médio nos pagamentos',
  valor_total_periodo: 'Valor do período (faixa, nunca o valor exato)',
  media_notas: 'Média de notas',
  media_assiduidade: 'Frequência média',
  pct_reprovacao: 'Reprovações (%)',
  tendencia_notas: 'Tendência das notas',
  tendencia_assiduidade: 'Tendência da frequência',
  total_semestres: 'Semestres cursados',
  tem_bolsa: 'Bolsa ou financiamento',
  sem_historico_academico: 'Sem histórico acadêmico lançado',
  forma_ingresso: 'Forma de ingresso',
  grau_academico: 'Grau acadêmico',
  turno: 'Turno',
}

export default function Modelo() {
  useTituloPagina('Modelo de risco')
  const { dados: m, erro, recarregar } = useCarregar(({ signal }) => api.modeloRisco({ signal }), [])
  return (
    <>
      <div className="cabecalho-pagina">
        <div>
          <h1>Modelo de risco</h1>
          <p>Como o score da fila é calculado. Toda faixa passa por avaliação humana antes de qualquer ação.</p>
        </div>
        <AvisoDecisao />
      </div>
      {erro && !m ? <EstadoErro erro={erro} titulo="Não foi possível carregar o modelo" onTentar={recarregar} />
        : !m ? <Esqueleto linhas={6} rotulo="Carregando o modelo" /> : (
          <div style={{ display: 'grid', gap: 'var(--esp-4)', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 20rem), 1fr))', alignItems: 'start' }}>
            <section className="painel" style={{ padding: 'var(--esp-4) var(--esp-5)', display: 'grid', gap: 'var(--esp-3)' }} aria-labelledby="t-m">
              <h2 id="t-m" className="rotulo-secao">Versão em uso</h2>
              <dl className="definicoes">
                <dt>Versão</dt><dd>{m.versao}</dd>
                <dt>Algoritmo</dt><dd>{m.algoritmo}</dd>
                <dt>Treinado em</dt><dd>{dataHora(m.treinado_em)}</dd>
                <dt>Faixa Amarelo</dt><dd>a partir de {pct(m.limiares.amarelo)}</dd>
                <dt>Faixa Vermelho</dt><dd>a partir de {pct(m.limiares.vermelho)}</dd>
              </dl>
            </section>
            <section className="painel" style={{ padding: 'var(--esp-4) var(--esp-5)', display: 'grid', gap: 'var(--esp-3)' }} aria-labelledby="t-met">
              <h2 id="t-met" className="rotulo-secao">Desempenho na validação</h2>
              <dl className="definicoes">
                {m.metricas.auc != null && <><dt>AUC</dt><dd>{m.metricas.auc.toLocaleString('pt-BR')}</dd></>}
                {m.metricas.recall != null && <><dt>Recall</dt><dd>{pct(m.metricas.recall)}</dd></>}
                {m.metricas.precisao != null && <><dt>Precisão</dt><dd>{pct(m.metricas.precisao)}</dd></>}
                {m.metricas.f1 != null && <><dt>F1</dt><dd>{m.metricas.f1.toLocaleString('pt-BR')}</dd></>}
              </dl>
              <p className="texto-meta">Recall: de cada 100 estudantes que evadiram, quantos o modelo teria sinalizado.</p>
            </section>
            {m.features?.length > 0 && (
              <section className="painel" style={{ padding: 'var(--esp-4) var(--esp-5)', display: 'grid', gap: 'var(--esp-3)' }} aria-labelledby="t-f">
                <h2 id="t-f" className="rotulo-secao">Variáveis consideradas</h2>
                <ul style={{ paddingLeft: 'var(--esp-4)', fontSize: 'var(--texto-sm)', display: 'grid', gap: 2 }}>
                  {m.features.map((f) => <li key={f} title={f}>{NOME_VARIAVEL[f] ?? f.replaceAll('_', ' ')}</li>)}
                </ul>
                <p className="texto-meta">Contatos e pedidos de ajuda ao ASA não entram no modelo: procurar o ASA nunca muda o score. Sexo e estado civil também ficam de fora.</p>
              </section>
            )}
          </div>
        )}
    </>
  )
}
