# Model Card — Agente de Monitoramento de Risco de Evasão
**ASA Turbo · FECAP · Versão 2.0.0**

> Todos os números deste Model Card são extraídos de `ml/artifacts/resultados_e2.json`.

---

## Detalhes do Modelo

| Campo | Valor |
|---|---|
| Nome | Agente de Monitoramento de Risco de Evasão |
| Versão | `risco-2.0.0` |
| Tipo | XGBoost com restrições monotônicas + calibração isotônica |
| Tarefa | Classificação binária (evadiu / não evadiu) com score probabilístico |
| Treinado em | 2026-11-02T21:42:42+00:00 |
| SHA256 do artefato | `c98263417baaec72e18a01e23b6e8c17b5134785e2bb4c68bc0fb291dc7ed66e` |
| Artefato | `ml/artifacts/risco_v2.joblib` |
| Versionamento | `ml/artifacts/MODEL_VERSION.json` |
| Linguagem | Python 3.12 · scikit-learn 1.9 · XGBoost 3.4 · joblib 1.6 |

---

## Uso Pretendido

**Para quem:** atendentes do ASA da FECAP, para priorizar quais estudantes contatar preventivamente.

**Como usar:**
1. O atendente acessa a fila de risco na tela do aplicativo.
2. Cada linha mostra score, categoria (Verde/Amarelo/Vermelho), fatores e recomendação.
3. O atendente valida, ajusta ou rejeita a sugestão com justificativa escrita.
4. Toda ação fica no histórico de auditoria.

**O estudante nunca vê o score nem os fatores.**

---

## Uso Fora do Escopo

| Uso proibido | Motivo |
|---|---|
| Cancelar vínculo, bloquear acesso ou aplicar penalidade automaticamente | Regra inegociável do projeto |
| Usar score como único critério de decisão | O modelo apoia, não decide |
| Exibir score ou fatores ao estudante | Privacidade; o estudante pode interpretar como penalização |
| Usar para fins diferentes de apoio ao ASA da FECAP | Fora do escopo de treinamento |
| Usar em contexto com distribuição muito diferente do treino | A base é histórica (pós-desfecho) |
| Usar para discriminar por sexo, estado civil ou idade | Esses atributos foram removidos |

---

## Dados

### Fonte

- Base histórica de matrículas da FECAP fornecida pelo ASA.
- **Dados reais não estão no repositório** (`.gitignore`). No repositório existem apenas métricas e figuras agregadas.
- **O período de referência do rótulo `evadiu` não foi confirmado formalmente com o ASA.** Esta é uma limitação reconhecida.

### Divisão

| Conjunto | N | % Evasão |
|---|---|---|
| Treino (75 %) | 9.626 | 19,56 % |
| Teste (25 %) | 3.209 | 19,57 % |

### Pré-processamento

- 7 duplicatas removidas; 2 notas > 100 corrigidas.
- 32 registros com atraso atípico sinalizados (recebem "dados insuficientes" na inferência).
- Split estratificado pelo rótulo, semente 42.

### Features utilizadas (19)

`tempo_de_curso`, `Idade`, `mora_sp_capital`, `total_parcelas`, `pct_parcelas_em_aberto`, `pct_parcelas_acordo`, `atraso_medio_dias`, `valor_total_periodo`, `media_notas`, `media_assiduidade`, `pct_reprovacao`, `tendencia_notas`, `tendencia_assiduidade`, `total_semestres`, `tem_bolsa`, `sem_historico_academico`, `Forma de Ingresso`, `Grau Acadêmico`, `Turno`

### Features removidas

| Feature | Motivo |
|---|---|
| `Sexo` | Atributo sensível; perda de AUC < 0,01 |
| `Estado Civil` | Atributo sensível; perda de AUC < 0,01 |
| `total_contatos` | Regra 5: contatos do ASA não podem aumentar o score |
| `dias_desde_ultimo_contato` | Mesmo motivo |

---

## Avaliação

### Desempenho no teste (XGBoost monotônico calibrado)

| Limiar | AUC-ROC | PR-AUC | Recall | Precisão | F1 | Brier |
|---|---|---|---|---|---|---|
| 0,10 (recomendado) | 0,9129 | 0,7550 | **0,8869** | 0,4528 | 0,5996 | 0,0830 |
| 0,30 (contrato) | 0,9129 | 0,7550 | 0,7580 | **0,6355** | **0,6914** | 0,0830 |

### Comparação com baseline (Entrega 1)

| Métrica | Baseline RL (E1) | v2 XGBoost (E2) |
|---|---|---|
| AUC | 0,82 | **0,91** |
| Recall (limiar 0,30) | 77,1 % | 75,8 % |
| Precisão (limiar 0,30) | 41,8 % | **63,6 %** |

### Calibração das faixas (configuração recomendada ≥ 0,10 / ≥ 0,60)

| Faixa | % Alunos | Taxa real de evasão |
|---|---|---|
| Verde (< 0,10) | 61,7 % | **3,6 %** |
| Amarelo (0,10–0,60) | 24,5 % | **24,7 %** |
| Vermelho (≥ 0,60) | 13,8 % | **81,9 %** |

As faixas são monotônicas: a taxa real de evasão aumenta conforme o score.

---

## Equidade

| Grupo | Gap de Recall | Gap FPR |
|---|---|---|
| Turno | 0,1403 | 0,1476 |
| Forma de Ingresso | 0,1682 | **0,4099** |
| Grau Acadêmico | 0,0877 | 0,1247 |
| Faixa etária | 0,0908 | 0,1833 |
| Sexo | **0,0317** | 0,1069 |

A maior disparidade está em **Forma de Ingresso**: grupos com menos histórico têm mais falsos positivos. Recomendação: protocolo de acolhimento para ingressantes sem histórico antes da implantação plena.

Variante treinada sem `Sexo` e `Estado Civil` apresenta AUC-CV dentro de 0,01 do modelo completo; os gaps de equidade não pioram. O modelo final **não usa esses atributos**.

---

## Considerações Éticas

1. **Nenhuma decisão automática.** O sistema é de apoio à decisão. Toda ação com impacto no vínculo do estudante exige validação humana registrada com justificativa escrita.
2. **O estudante nunca vê o score.** A exibição do score poderia ser interpretada como penalização ou estigmatização.
3. **Abstenção documentada.** Registros com dados insuficientes recebem "revisar manualmente" em vez de um score, evitando falsa precisão.
4. **Auditoria completa.** Todo score gerado registra: usuário, data/hora, versão do modelo, features usadas (sem dados pessoais brutos), resultado e decisão humana.
5. **LGPD:** nenhum dado pessoal real é versionado. Credenciais estão fora do Git. Features sensíveis (Sexo, Estado Civil, Idade) não são exibidas como fatores.
6. **Regra 5:** contatos legítimos do estudante com o ASA nunca aumentam o score (feature removida).
7. **Uso restrito:** o modelo foi treinado na realidade da FECAP. Aplicar em outra instituição sem re-treinamento é inadequado.

---

## Limitações

1. **Rótulo não confirmado:** o período de referência do campo `evadiu` não foi formalmente confirmado com o ASA. Isso pode inflar as métricas.
2. **Dados pós-desfecho:** a AUC de 0,91 no teste tende a cair com dados de corte reais (antes do desfecho). A v3 deve usar features com data de corte anterior à evasão.
3. **Distribuição histórica:** o modelo captura padrões históricos que podem não refletir o comportamento futuro (mudanças em políticas de bolsas, pandemia, etc.).
4. **Ausência de feedback real:** a precisão do modelo nunca foi validada com um ciclo real de contatos e resultados. Monitorar taxa de resposta (aluno reconectou? continuou?) é essencial para a v3.
5. **Pós-Graduação e Tecnólogo:** recall ligeiramente menor que Bacharelado; recomendar protocolo específico para esses graus.

---

## Histórico de Versões

### v1.0 (Entrega 1 — 2026-10)

- **Algoritmo:** Regressão Logística com `class_weight=balanced`
- **AUC:** 0,82 | **Recall:** 77,1 % | **Precisão:** 41,8 % (limiar 0,30)
- **Features:** 15 (incluindo `total_contatos` e `dias_desde_ultimo_contato`)
- **Sem calibração de probabilidade**
- **Sem análise de equidade nem SHAP**
- **Faixas:** Verde < 30 %, Amarelo 30–60 %, Vermelho ≥ 60 % (sem calibração)

### v2.0.0 (Entrega 2 — 2026-11-02)

- **Algoritmo:** XGBoost com restrições monotônicas + calibração isotônica
- **AUC:** 0,91 | **Recall:** 88,7 % (limiar 0,10) | **Precisão:** 63,6 % (limiar 0,30)
- **Features:** 19 (Sexo e Estado Civil removidos; total_contatos e dias_desde_ultimo_contato removidos)
- **Calibração:** isotonic regression — Brier 0,083
- **Equidade:** análise por turno, forma de ingresso, grau acadêmico, faixa etária e sexo
- **Explicabilidade:** TreeSHAP nativo — 6 fatores por aluno com direção e peso
- **Abstenção:** registros com dados insuficientes recebem categoria `dados_insuficientes`
- **Versionamento:** MODEL_VERSION.json com SHA256, features, limiares e justificativa
- **Integração:** modelo final carregado pelo backend via `ml/artifacts/risco_v2.joblib`

---

*Gerado em 06/11/2026 · ASA Turbo v0.9 · FECAP Projeto Interdisciplinar 5º CCOMP 2026.2*
