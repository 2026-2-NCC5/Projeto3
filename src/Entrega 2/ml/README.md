# ml/ · modelo de risco e avaliação do RAG (sessão ml)

| Pasta | Conteúdo |
|---|---|
| `rag/gerar_embeddings.py` | Gera os embeddings (Cloudflare `@cf/baai/bge-m3`, 1024d) dos trechos da base de conhecimento. Lê `../.env`. |
| `artifacts/` | Métricas e figuras (JSON/PNG, versionados). `*.joblib`/`*.pkl` ficam fora do Git por padrão (veja `.gitignore`). |

## Formato das features (igual à base real e ao seed sintético)
`ID_ALUNO, evadiu, Forma de Ingresso, Grau Acadêmico, Turno, tempo_de_curso, Idade, Estado Civil, Sexo, mora_sp_capital, total_parcelas, pct_parcelas_em_aberto, pct_parcelas_acordo, atraso_medio_dias, tem_bolsa, valor_total_periodo, media_notas, media_assiduidade, pct_reprovacao, tendencia_notas, tendencia_assiduidade, total_semestres, total_contatos, dias_desde_ultimo_contato`

- **Dados reais:** `../data/base_unificada_asa-final.csv`. Ficam só na máquina local, fora do Git, e nunca são copiados para outra pasta.
- **Dados sintéticos para testes:** `../seeds/estudantes_sinteticos.csv`.
- **Baseline da Entrega 1:** `documentos/Entrega1/Inteligência Artifical e Aprendizado de Máquina/Entrega1_Monitoramento_ASA.ipynb`, na raiz do repositório. É uma RL com `class_weight=balanced`, AUC 0,82 e Recall 77%, com faixas 0,30 e 0,60.

## Pendências levantadas na Fase 0 (ver `../docs/decisoes/0001-fase0.md`)
1. **Regra 5:** `total_contatos` e `dias_desde_ultimo_contato` não podem contar pedidos do estudante ao ASA.
2. **Atributos sensíveis:** `Sexo`, `Estado Civil` e `Idade` exigem análise de viés. Eles nunca são exibidos como fator.
3. O artefato servido pelo backend precisa expor versão, fatores (direção e peso) e score por dimensão (financeira, acadêmica, relacionamento), no formato `Fator` do contrato.
