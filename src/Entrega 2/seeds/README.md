# seeds/ · dados de demonstração

**Tudo nesta pasta é fictício**, com uma exceção explicada abaixo. Os nomes são combinações de listas genéricas, o RA é falso (prefixo `99`) e as distribuições foram escolhidas à mão. Nenhuma linha vem de pessoa real nem foi estimada a partir da base real do ASA.

| Arquivo | O que é |
|---|---|
| `gerar_seeds.py` | Gerador determinístico (semente `20261106`). Pontua com o modelo real, então precisa das dependências de `ml/requirements.txt`. Gera os dois arquivos abaixo. |
| `seed_demo.sql` | 300 estudantes, features e scores de 6 meses (mai–out/2026), casos amarelo/vermelho, validações, contatos e as conversas do estudante demo. **Gerado: não edite à mão.** |
| `estudantes_sinteticos.csv` | Os mesmos 300 estudantes no formato exato de `base_unificada_asa-final.csv` (mês mais recente). Serve para testar o pipeline de ML sem tocar em dado real. |
| `criar_usuarios_demo.py` | Cria os 3 usuários de demonstração no Supabase Auth, mais os perfis. |
| `base_conhecimento_oficial.sql` | **Exceção:** conteúdo institucional público da Cesta de Serviços ASA (230 documentos, 693 trechos). Não tem dado pessoal. Os embeddings ficam nulos e são gerados depois. |

Os scores do seed vêm do **modelo real** (`versao_modelo = 'risco-2.0.0'`, `ml/artifacts/risco_v2.joblib`) aplicado às features sintéticas. Score, categoria, fatores e recomendação são exatamente o que `RiskModel.predict` devolve, o mesmo que o backend vai mostrar.

Como se chega à distribuição da demo sem forçar categoria:
- cada estudante recebe uma probabilidade-alvo para outubro (sorteio 60% verde, 25% amarelo, 15% vermelho) e uma trajetória: estável (~45%), piorando (~25%) ou melhorando (~30%);
- as features são geradas a partir de um nível latente de risco (parcelas em aberto, atraso e reprovação sobem; nota e frequência caem), e o nível é escolhido por busca para o modelo chegar perto do alvo de cada mês;
- resultado em outubro/2026: **58% verde, 27% amarelo, 15% vermelho**; ~90 estudantes mudam de faixa entre maio e outubro.

Nada disso usa linhas da base real: só o artefato do modelo (objetos ajustados e estatísticas agregadas). Atributos sensíveis (sexo, estado civil, idade) existem nas features, mas nunca aparecem como fator.

## Usuários de demonstração

| Papel | E-mail | Senha |
|---|---|---|
| Estudante | `estudante.demo@example.com` | `AsaTurbo#Demo2026` |
| Atendente | `atendente.demo@example.com` | `AsaTurbo#Demo2026` |
| Administrador | `admin.demo@example.com` | `AsaTurbo#Demo2026` |

A senha vem de `DEMO_PASSWORD` no `.env`. Use o valor acima nas apresentações. Esses usuários só servem para demonstração e não dão acesso a nenhum dado real.

## Ordem para montar um banco do zero

```bash
# 1. SQL Editor do Supabase (ou psql), nesta ordem:
infra/sql/001_schema_base.sql           # só em banco novo
seeds/base_conhecimento_oficial.sql
infra/sql/002_contrato_v09.sql

# 2. Usuários de demo (precisa do .env com SUPABASE_URL, SUPABASE_SERVICE_KEY, DEMO_PASSWORD)
python3 seeds/criar_usuarios_demo.py

# 3. Dados fictícios
seeds/seed_demo.sql

# 4. Embeddings da base de conhecimento (Cloudflare)
python3 ml/rag/gerar_embeddings.py
```

No **Supabase atual**, que já tem o 001 e a base de conhecimento, comece pelo `002`.

Para regerar os dados: `ml/.venv/bin/python seeds/gerar_seeds.py` (~2 min). Rodar duas vezes produz arquivos idênticos, desde que o artefato do modelo seja o mesmo. **Se o modelo for retreinado, regere os seeds.**
