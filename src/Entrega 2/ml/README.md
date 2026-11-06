# ml/ · modelo de risco e avaliação do RAG (sessão ml)

| Caminho | Conteúdo |
|---|---|
| `Entrega2_Monitoramento_ASA.ipynb` | Modelo de risco v2: comparação, calibração, limiares, equidade, explicabilidade, erros. |
| `Algebra_Linear_E2.ipynb` | PCA por autovalores, mínimos quadrados e efeito da redução de dimensionalidade. |
| `Avaliacao_RAG.ipynb` · `avaliar_rag.py` | Avaliação da recuperação (Recall@k, MRR, abstenção, groundedness). |
| `treinar.py` · `avaliar.py` | Scripts do modelo de risco (o notebook chama os mesmos). |
| `risco/` | Pacote usado pelo backend: `modelo.py` (`RiskModel`), `dados.py` (limpeza da E1), `graficos.py`. |
| `rag/` | Recuperação local (mesma interface do backend) e `gerar_embeddings.py`. |
| `rag_eval/perguntas.jsonl` | Conjunto de avaliação do RAG. |
| `artifacts/` | `risco_v2.joblib`, `metrics.json`, `MODEL_VERSION.json`, `rag_metrics.json`. |
| `tests/` | `pytest` da interface do modelo. |

Figuras: `../docs/evidencias/risco_*.png`, `algebra_*.png`, `rag_*.png`.

## Como rodar

```bash
cd "src/Entrega 2"
python3 -m venv ml/.venv && ml/.venv/bin/pip install -r ml/requirements.txt
export ASA_DATA_DIR=/caminho/para/data      # pasta local com base_unificada_asa-final.csv (fora do Git)
ml/.venv/bin/python ml/treinar.py           # treina e salva ml/artifacts/risco_v2.joblib (~2 min)
ml/.venv/bin/python ml/avaliar.py           # figuras, metrics.json e MODEL_VERSION.json
ml/.venv/bin/python -m pytest ml/tests
```

Os dados reais **nunca** são copiados: os scripts leem de `ASA_DATA_DIR` (padrão `data/`) e só gravam agregados.

## Interface para o backend

```python
import sys; sys.path.insert(0, "ml")
from risco.modelo import RiskModel

modelo = RiskModel.carregar("ml/artifacts/risco_v2.joblib")
modelo.predict(features)   # InferenciaResultado: probabilidade, categoria, score{geral,financeiro,academico,relacionamento},
                           # fatores[Fator], recomendacao, versao_modelo, calculado_em, aviso
modelo.explicar(features)  # list[Fator]: codigo, descricao, dimensao, direcao, peso (soma 1)
modelo.info()              # ModeloInfo: versao, algoritmo, treinado_em, limiares, metricas, features
```

- `features` aceita os nomes do contrato (`FeaturesRisco`, snake_case) ou os da base. Campos ausentes são imputados.
- Dependências em produção: `numpy`, `pandas`, `scikit-learn`, `xgboost`, `joblib`. A explicação usa o TreeSHAP nativo do XGBoost (sem `shap`).
- O artefato não contém linhas de treino (auditado em `treinar.auditar_artefato`).

## Modelo em uso: `risco-2.0.0`
XGBoost com restrições monotônicas, calibrado (isotônica), **sem** `Sexo`, `Estado Civil`, `total_contatos` e `dias_desde_ultimo_contato`.
Detalhes e justificativa em `artifacts/MODEL_VERSION.json`.

- **Limiares ativos:** 0,30 / 0,60 (o contrato fixa `const`).
- **Limiares recomendados:** Amarelo ≥ 0,10 / Vermelho ≥ 0,60 (≈62/25/14% dos alunos; recall de Amarelo+ ~89%). A troca exige mudar `ModeloInfo.limiares` no contrato.
- **Regra 5:** contatos com o ASA não entram no modelo, porque a base não separa pedido do estudante de contato ativo.
- **Sensíveis:** idade é entrada, mas nunca aparece como fator. Sexo e estado civil não entram.

## Pendências
1. A base é um retrato pós-desfecho (parcelas encerradas, notas não lançadas para quem saiu). A AUC é otimista; a v3 precisa de features com data de corte.
2. Confirmar com o ASA a janela temporal do rótulo `evadiu`.
