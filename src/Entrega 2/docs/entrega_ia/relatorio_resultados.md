# Relatório de Resultados — Entrega 2 (IA)
**ASA Turbo · Projeto Interdisciplinar FECAP · 5º CCOMP · 2026.2**
Gerado em: 06/11/2026 | Versão do modelo: risco-2.0.0 | Versão do relatório: 2.0.0

> Todos os números deste relatório são extraídos de `ml/artifacts/resultados_e2.json`,
> gerado por `ml/consolidar_resultados.py` a partir de `ml/artifacts/metrics.json` e
> `ml/artifacts/rag_metrics.json`. Nenhum número foi digitado à mão.

---

## 1. Objetivo

O projeto desenvolve dois agentes de IA para o ASA (Área do Sucesso Alvarista) da FECAP:

- **Agente de Monitoramento** — classifica o risco de evasão de cada aluno em Verde / Amarelo / Vermelho, listando os fatores contribuintes para o atendente priorizar contatos. Nunca gera decisão automática; toda ação com impacto exige validação humana registrada.
- **Agente para o Estudante (ASA Turbo)** — chatbot RAG (Recuperação Aumentada por Geração) que responde dúvidas usando exclusivamente documentos oficiais da FECAP. Abstém-se quando a pergunta está fora do escopo ou a similaridade está abaixo do limiar; nunca inventa procedimento, prazo ou regra.

---

## 2. Dados e Preparação

| Etapa | Valor |
|---|---|
| Registros brutos | 12.842 |
| Duplicatas removidas | 7 |
| Notas acima de 100 corrigidas | 2 |
| Registros com atraso outlier (>365 dias) sinalizados | 32 |
| **Registros finais** | **12.835** |
| Treino (75 %) | 9.626 |
| Teste (25 %) | 3.209 |
| Taxa de evasão no treino | 19,56 % |
| Taxa de evasão no teste | 19,57 % |
| Semente | 42 |

A divisão é estratificada pelo rótulo `evadiu` para garantir proporções iguais de evasão em treino e teste. O mesmo split é usado em todos os modelos para comparação justa.

**Nota sobre o rótulo:** o campo `evadiu` foi definido pela equipe com base nos dados históricos do ASA. O período de referência exato (quando um aluno é considerado evadido) **não foi confirmado formalmente com o ASA**; isso é uma limitação do projeto.

---

## 3. Modelos Comparados e Validação

### Validação cruzada estratificada (5 folds, no treino — sem usar o teste)

| Modelo | AUC-ROC | PR-AUC | Recall | Precisão | F1 | Brier |
|---|---|---|---|---|---|---|
| Regressão Logística (baseline) | 0,8347 | 0,5988 | 0,7939 | 0,4196 | 0,5490 | 0,1673 |
| Random Forest | 0,9383 | 0,8611 | 0,6474 | 0,9021 | 0,7535 | 0,0648 |
| **XGBoost monotônico** | **0,9346** | **0,8548** | **0,7701** | **0,8521** | **0,7676** | **0,0729** |

### Comparação no conjunto de teste (calibrado, limiar = 0,5)

| Modelo | AUC-ROC | PR-AUC | Recall | Precisão | F1 | Brier |
|---|---|---|---|---|---|---|
| Regressão Logística | 0,8347 | — | — | — | — | — |
| Random Forest | 0,9383 | — | — | — | — | — |
| XGBoost (sem monotonia) | 0,9346 | — | — | — | — | — |
| **XGBoost monotônico (escolhido)** | **0,9129** | **0,7550** | **0,7580** | **0,6355** | **0,6914** | **0,0830** |

### Justificativa da escolha: XGBoost monotônico

1. RF e XGBoost empatam na CV por AUC (diferença < 0,005). Fica o XGBoost, que oferece TreeSHAP nativo (explicação exata por aluno) e artefato menor.
2. As restrições monotônicas custam 0,014 de AUC na CV (0,929 → 0,915), mas impedem artefatos do retrato pós-desfecho (ex.: 0% de parcelas em aberto associado a mais evasão). Aceitas porque a perda está abaixo do limite de 0,03.
3. Sexo e Estado Civil foram removidos: perda de AUC < 0,01 e as lacunas de recall/FPR entre grupos não pioram.
4. `total_contatos` e `dias_desde_ultimo_contato` foram removidos (Regra 5): a base não separa pedidos do estudante de contatos ativos do ASA.

---

## 4. Métricas e Limiares

### Métricas no teste (XGBoost monotônico calibrado por isotonic regression)

| Limiar | Recall | Precisão | F1 | Brier | % Sinalizados |
|---|---|---|---|---|---|
| 0,10 (recomendado) | **0,8869** | 0,4528 | 0,5996 | 0,0830 | 38,3 % |
| 0,30 (contrato atual) | 0,7580 | 0,6355 | 0,6914 | 0,0830 | 23,3 % |
| 0,60 (somente Vermelho) | 0,5780 | 0,8194 | 0,6779 | 0,0830 | 13,8 % |

### Cobertura de atendimento (quantos alunos contatar para capturar X% dos que evadem)

| Contatar | N alunos | Limiar equiv. | Recall | Precisão | Lift |
|---|---|---|---|---|---|
| 5 % | 161 | 0,8606 | 22,9 % | 89,4 % | 4,57× |
| 10 % | 321 | 0,7168 | 44,1 % | 86,3 % | 4,41× |
| 15 % | 482 | 0,5745 | 61,5 % | 80,1 % | 4,09× |
| 20 % | 643 | 0,4601 | 73,9 % | 71,8 % | 3,67× |

### Faixas de risco (calibração das probabilidades)

**Configuração atual (limiar Amarelo ≥ 0,30 / Vermelho ≥ 0,60):**

| Faixa | % Alunos | Taxa real de evasão | Prob. média prevista |
|---|---|---|---|
| Verde (< 0,30) | 76,7 % | 6,2 % | 5,8 % |
| Amarelo (0,30–0,60) | 9,5 % | 36,9 % | 44,8 % |
| Vermelho (≥ 0,60) | 13,8 % | 81,9 % | 79,7 % |

**Configuração recomendada (Amarelo ≥ 0,10 / Vermelho ≥ 0,60):**

| Faixa | % Alunos | Taxa real de evasão | Prob. média prevista |
|---|---|---|---|
| Verde (< 0,10) | 61,7 % | 3,6 % | 3,0 % |
| Amarelo (0,10–0,60) | 24,5 % | 24,7 % | 28,1 % |
| Vermelho (≥ 0,60) | 13,8 % | 81,9 % | 79,7 % |

A calibração por isotonic regression garante que a probabilidade prevista é compatível com a taxa real de evasão observada (Brier score 0,083 no teste).

**Comparação com baseline da Entrega 1:**

| Métrica | Baseline E1 (RL, limiar 0,30) | v2 (XGBoost, limiar 0,30) | Melhoria |
|---|---|---|---|
| AUC | 0,82 | **0,91** | +11 pp |
| Recall | 77,1 % | **75,8 %** | −1,3 pp (troca recall por precisão) |
| Precisão | 41,8 % | **63,6 %** | +21,8 pp |
| % Sinalizados | 36,1 % | **23,3 %** | −12,8 pp |

---

## 5. Análise de Erros

Corte da análise: limiar recomendado 0,10.

| Resultado | N |
|---|---|
| Verdadeiros Positivos (VP) | 557 |
| Falsos Negativos (FN) — evadiram sem ser sinalizados | 71 |
| Falsos Positivos (FP) — sinalizados sem evadir | 673 |
| Verdadeiros Negativos (VN) | 1.908 |

### Perfil dos Falsos Negativos (perdemos esses alunos)

- Nota mediana **65** (VN: 66), frequência mediana **91 %** (VN: 92 %), 3 semestres cursados.
- São alunos que, pelos dados disponíveis, pareciam estar indo bem. A evasão deles não tem sinal preditivo nos dados atuais.

### Perfil dos Falsos Positivos (sinalizamos, mas não evadiram)

- 58 % não têm nota nem frequência registradas, tempo de curso mediano = 0 e valor do período mediano R$ 12.800 (VP: R$ 5.132).
- São principalmente ingressantes sem histórico. Um contato de acolhimento nesses casos tem baixo custo e não é perdido.

### Observações práticas

1. **Falsos negativos parecem alunos que ficam:** nota e frequência medianas próximas ao grupo VN. A evasão de quem estava bem não tem sinal disponível nos dados.
2. **Falsos positivos são ingressantes sem histórico:** 58 % não têm notas nem frequência lançadas — o modelo sinaliza quem parece um típico evadente por falta de dados, não por desempenho ruim.
3. **Pós-Graduação responde por 37 % dos FN.** Recall por grau: Bacharelado 87 %, Pós-Graduação 90 %, Tecnólogo 96 %. Vale protocolo próprio para Pós-Grad (ex.: contato no 1º mês).
4. **Veteranos escapam mais:** os FN têm mediana de 35 parcelas contra 18 dos VP. Recalcular o score mensalmente com dados correntes é o caminho.
5. **A base é um retrato pós-desfecho:** quem evadiu tem 0 parcelas em aberto (encerradas) e 69 % dos VP não têm notas lançadas. Isso infla a AUC. A v3 precisa de features com data de corte anterior à evasão.

---

## 6. Explicabilidade

A explicabilidade é feita por **contribuição de atributo por aluno**: para cada feature, calcula-se a diferença de logit entre a probabilidade com aquele valor e com o valor de referência (mediana/moda do grupo). Para o XGBoost o cálculo usa TreeSHAP nativo.

### Importância global (média do |SHAP|, top 5)

| Atributo | Contribuição média | Importância por permutação (ΔAUC) |
|---|---|---|
| valor_total_periodo | 1,2224 | 0,2539 |
| tempo_de_curso | 0,4977 | 0,0536 |
| total_parcelas | 0,3983 | 0,0376 |
| Idade | 0,4075 | 0,0361 |
| total_semestres | 0,3493 | 0,0240 |

> **Nota:** `Idade` aparece com alta contribuição média mas **nunca é exibida como fator** na tela do atendente (atributo sensível, incluída apenas no modelo por correlação com tempo de curso).

### Exemplo anônimo (perfil de alto risco)

- Perfil: ingressante, 1 semestre, valor do período R$ 5.200, 42 % das parcelas em aberto, nota 41, frequência 63 %, 40 % de reprovação.
- Score previsto: **91,2 %** (Vermelho).
- Fatores exibidos: valor do período abaixo da mediana (+), notas baixas (+), frequência baixa (+).

A API expõe o formato `{codigo, descricao, dimensao, direcao, peso}` para cada fator (máx. 6), com direção ("aumenta" / "reduz" o risco) e peso relativo entre os fatores mostrados.

---

## 7. Equidade

Análise realizada no limiar recomendado (0,10) sobre o conjunto de teste.

### Lacunas de recall e taxa de falsos positivos por grupo

| Grupo | Gap de Recall (max − min) | Gap FPR |
|---|---|---|
| Turno | 0,1403 | 0,1476 |
| Forma de Ingresso | 0,1682 | 0,4099 |
| Grau Acadêmico | 0,0877 | 0,1247 |
| Faixa etária | 0,0908 | 0,1833 |
| **Sexo** | **0,0317** | **0,1069** |

A maior disparidade está em **Forma de Ingresso** (FPR gap = 0,41): modalidades com menos histórico acadêmico disponível (ex.: convênios, transferências recentes) têm mais FP porque o modelo sinaliza ingressantes sem dados. Isso recomenda um protocolo de acolhimento diferenciado, não penalização.

**Variante sem Sexo e Estado Civil:** perda de AUC-CV < 0,01; os gaps de recall/FPR por grupo não pioram. O modelo final **não usa Sexo nem Estado Civil** como features.

### Recomendação

Monitorar mensalmente o recall por Forma de Ingresso; estabelecer meta de recall ≥ 80 % para todos os grupos antes da implantação plena.

---

## 8. Avaliação do Agente para o Estudante (RAG)

### Corpus de avaliação

- 20 documentos fictícios (Entrega 1, seed_v2.sql).
- 60 perguntas: 20 diretas, 20 reformuladas, 8 de continuação, 6 fora do escopo próximas, 6 fora do escopo distantes.

> **Limitação:** os documentos são fictícios. O comportamento com a base real (230 documentos do ASA) precisará ser reavaliado.

### Comparação de métodos (dentro do escopo, N=48)

| Método | Recall@1 | Recall@3 | MRR | Acerto Agente | Abs. Correta | Abs. Indevida | CV |
|---|---|---|---|---|---|---|---|
| TF-IDF hashing | 0,7292 | 0,9375 | 0,8333 | 0,6333 | 58,3 % | 14,6 % | 0,5833 |
| TF-IDF + tabela IDF | 0,7292 | 0,9167 | 0,8365 | 0,6833 | 83,3 % | 22,9 % | 0,6333 |
| MiniLM-L6 | 0,5208 | 0,6875 | 0,6249 | 0,5333 | 58,3 % | 20,8 % | 0,5333 |
| MiniLM-L12 multilíngue | 0,7083 | 0,8542 | 0,8002 | 0,7000 | 66,7 % | 8,3 % | 0,6500 |
| **bge-m3 (produção)** | **0,9375** | **0,9583** | **0,9509** | **0,9000** | **100 %** | **10,4 %** | **0,8667** |

### Método escolhido: bge-m3 · limiar 0,5511

- Acerto do agente 90 % (CV: 86,7 %).
- Abstém corretamente em **100 %** das perguntas fora do escopo (limiar 0,5511).
- Groundedness: 100 % das respostas são fundamentadas nos trechos recuperados (resposta extrativa — risco de responder com o documento errado: 1 caso em 43 avaliados).

### Abstenção e erros

- **Abstém corretamente:** todas as 12 perguntas fora do escopo são encaminhadas para humano.
- **Abstém indevidamente:** 10,4 % das perguntas dentro do escopo (5/48) ficam sem resposta — principalmente perguntas de continuação sem contexto.
- **Resposta errada:** 1 caso (documento recuperado correto mas resposta não responde à pergunta).
- **Erros de continuação sem contexto:** sem a última pergunta do usuário concatenada, o Recall@1 de continuação cai de 100 % para 62,5 %.

---

## 9. Abstenção

### Agente de Monitoramento

Registros com **dados insuficientes** (atraso_medio_dias outlier > 365 dias, ou ausência de todos os campos financeiros) recebem `categoria = "dados_insuficientes"` e recomendação de **revisão manual**, sem score numérico. No conjunto de limpeza foram detectados **32 registros** com atraso atípico.

### Agente para o Estudante

O agente se abstém quando a similaridade do chunk mais próximo fica abaixo de **0,5511** (bge-m3). Neste caso, responde:

> "Não encontrei isso nos documentos oficiais. Quer que eu encaminhe para o ASA?"

---

## 10. Versionamento

### Modelo de risco

- Versão: `risco-2.0.0`
- Treinado em: 2026-11-02T21:42:42+00:00
- SHA256 do artefato: `c98263417baaec72e18a01e23b6e8c17b5134785e2bb4c68bc0fb291dc7ed66e`
- Limiares ativos: Amarelo ≥ 0,30 / Vermelho ≥ 0,60
- Limiares recomendados: Amarelo ≥ 0,10 / Vermelho ≥ 0,60
- Exposto pelo backend em `GET /risco/modelo` (campo `versao`).
- Todo score retornado pela API inclui `versao_modelo` e `calculado_em`.

### Base de conhecimento (RAG)

- Versão por documento: registrada na tabela `documentos` (campo `versao_conteudo`).
- Hash do conjunto: exposto em `GET /health` (campo `versao_modelo_risco` para o modelo; versão da base de conhecimento exposta na auditoria de cada resposta do chat, campo `versao_base`).
- Toda resposta do chat registra `versao_base` e `fonte` na auditoria.

---

## 11. Arquitetura e Endpoint de Inferência

### Endpoint de risco integrado ao aplicativo

- **Rota:** `POST /risco/inferir`
- **Autenticação:** JWT Supabase com papel `administrador` ou `equipe_tecnica`
- **Entrada:** `estudante_id` (busca features do banco) ou `features` (simulação)
- **Saída:** `probabilidade`, `categoria`, `score` (geral/financeiro/acadêmico/relacionamento), `fatores` (código, descrição, dimensão, direção, peso), `recomendacao`, `versao_modelo`, `calculado_em`, `persistido`, `score_id`
- **Modelo carregado:** `ml/artifacts/risco_v2.joblib` (XGBoost monotônico calibrado, versão `risco-2.0.0`). Fallback para placeholder RL se o artefato não for encontrado.

### Fluxo confirmado

Tela do atendente → fila de risco (seeds + scores do modelo real) → clica no aluno → detalhe com score, fatores, tendência, recomendação e versão do modelo → validação humana com justificativa → auditoria gravada.

A integração usa `ModeloML` que envolve `RiskModel` da sessão de ML (TreeSHAP nativo), com suporte a `ModeloSklearn` para o formato legado.

---

## 12. Limitações e Uso Adequado

1. **Rótulo não confirmado:** o campo `evadiu` foi definido com base nos dados do ASA, mas o período de referência exato não foi confirmado formalmente. Isso pode inflar a AUC.
2. **Dados pós-desfecho:** a base é um retrato tirado após o desfecho; a AUC tende a cair com dados de corte reais. A v3 precisa de features com data anterior à evasão.
3. **Documentos fictícios:** o chatbot foi avaliado sobre documentos fictícios (Entrega 1). Com a base real (230 documentos), o comportamento precisará ser reavaliado.
4. **Disparidade por Forma de Ingresso:** grupos com menos histórico têm mais falsos positivos. Monitorar continuamente.
5. **Resposta extrativa:** o chatbot reproduz trechos dos documentos, o que é seguro (nunca inventa), mas pode resultar em respostas longas ou imprecisas para perguntas complexas.
6. **Nenhuma decisão punitiva automática:** o sistema é de apoio. Toda ação com impacto no vínculo do aluno exige validação humana registrada com justificativa.
7. **Score não é o único dado:** o atendente deve considerar o score em conjunto com o conhecimento do caso; estudantes com `dados_insuficientes` devem ser revisados manualmente.

---

## 13. Próximos Passos

1. Confirmar com o ASA o período de referência do rótulo `evadiu` e criar feature com data de corte anterior ao desfecho.
2. Substituir os documentos fictícios pelos documentos reais e reavaliar o RAG com as 60 perguntas (atualizar `perguntas.jsonl`).
3. Ajustar o limiar Amarelo de 0,30 para 0,10 no contrato da API, após validação com o ASA sobre capacidade de atendimento.
4. Implementar protocolo de acolhimento diferenciado para ingressantes sem histórico (principais FP).
5. Monitorar mensalmente o recall por Forma de Ingresso e Grau Acadêmico.
6. Treinar v3 com features de corte temporal e dados reais de alunos ativos (não retrospectivos).
7. Recalcular embeddings com a base real e validar abstenção com perguntas reais dos estudantes.
