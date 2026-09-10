# ASA - Agente para o Estudante — Protótipo (v2, config zero no Vercel)

## Por que mudou
A versão anterior usava FastAPI + vercel.json manual, que quebrava com
`FUNCTION_INVOCATION_FAILED` sem explicação — conflito entre o formato antigo
de configuração do Vercel (`builds`/`routes`) e a forma atual dele detectar
apps Python. Esta versão usa o padrão mais simples e estável: **um arquivo
Python por rota, dentro de `/api`**, sem framework e sem vercel.json.

## Estrutura
```
index.html          -> frontend (chat estilo Claude/ChatGPT)
api/perguntar.py     -> vira automaticamente a rota POST /api/perguntar
requirements.txt     -> pacotes supabase + requests
gerar_embeddings.py  -> script LOCAL para vetorizar os documentos (rodar 1x)
connect_supabase.py  -> script LOCAL de testes gerais
.env.example          -> modelo de variáveis de ambiente (uso local)
idf_table.json        -> tabela de IDF usada só no fallback (ver abaixo)
```

## Vetorização: embeddings semânticos (Hugging Face)
A pergunta do estudante e os documentos da base são vetorizados com o
modelo `BAAI/bge-small-en-v1.5` (384 dimensões) via **Hugging Face Inference
API**, gratuita. Isso entende contexto e sinônimos de verdade, ao contrário
do método antigo.

> Por que não `sentence-transformers/all-MiniLM-L6-v2` (modelo originalmente
> planejado)? Ele foi descontinuado para a tarefa `feature-extraction` na API
> gratuita da HF — desde a migração pro sistema de "Inference Providers", esse
> modelo só é servido como `sentence-similarity` (compara frases, não devolve
> vetor). `bge-small-en-v1.5` tem a mesma dimensão (384) e está confirmado
> funcionando; é otimizado para inglês, então a qualidade semântica em
> português fica um pouco abaixo do ideal, mas ainda deve superar bastante o
> hashing trick + TF-IDF anterior. Se a HF mudar isso de novo no futuro, é só
> trocar o valor de `HF_API_URL` nos dois arquivos.

Se a chamada à Hugging Face falhar por qualquer motivo (token não
configurado, timeout, rate limit, etc.), o sistema cai automaticamente no
método antigo (hashing trick + TF-IDF + dicionário de sinônimos) como
fallback — a resposta ao estudante nunca quebra, só fica registrado no log
o motivo da falha. Por isso o `idf_table.json` continua sendo gerado e
commitado: é ele que alimenta esse fallback.

**Gerar o token grátis:** crie uma conta em [huggingface.co](https://huggingface.co) →
**Settings > Access Tokens** → "Create new token" → tipo **Fine-grained** →
marque a permissão **"Make calls to Inference Providers"** (sem ela a chamada
volta com erro 403) → copie o valor (começa com `hf_`) e use como
`HF_API_TOKEN`.

## Passo a passo

### 1. Banco de dados
Se ainda não fez: rode `schema.sql` e depois `seed.sql` no SQL Editor do Supabase.

### 2. Gerar os embeddings
1. `pip install -r requirements-local.txt`
2. Copie `.env.example` para `.env`, preencha `SUPABASE_URL`, a chave
   `service_role` e o `HF_API_TOKEN` (veja como gerar acima)
3. `python gerar_embeddings.py`

### 3. Deploy no Vercel
1. Apague o projeto anterior no Vercel (ou crie um novo) para evitar cache
   de configuração antiga
2. Suba esta pasta pro GitHub (substituindo os arquivos antigos: remova
   `vercel.json` e `api/index.py` do repositório se existirem)
3. Importe o repositório no Vercel — **não precisa mexer em nenhuma
   configuração de build**, ele detecta sozinho
4. Em Project Settings > Environment Variables, adicione:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `HF_API_TOKEN` (sem ela, a API funciona normalmente, só usa direto o
     fallback TF-IDF — veja "Vetorização" acima)
5. Deploy

### 4. Testar
No console do navegador (F12), na página já deployada:
```javascript
fetch('/api/perguntar', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pergunta:'teste'})}).then(r=>r.json()).then(console.log)
```
Deve retornar um JSON com `resposta`, `confianca`, `abstencao` e `evidencias`.
Se `resposta` começar com `[DEBUG]`, a mensagem já diz exatamente qual é o problema.

## Removendo o modo debug (antes da entrega final)
Em `api/perguntar.py`, o bloco `try/except` dentro de `processar_pergunta`
devolve o erro técnico na própria resposta (`[DEBUG] ...`). Isso é ótimo pra
testar agora, mas antes de entregar o projeto, troque essas mensagens de
debug por algo mais amigável ao estudante, tipo "Ocorreu um erro, tente
novamente" — e, se quiser manter rastreabilidade (RF10), registre o erro real
num log em vez de expor pro usuário final.
