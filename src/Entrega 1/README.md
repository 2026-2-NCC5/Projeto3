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
requirements.txt     -> só o pacote supabase
gerar_embeddings.py  -> script LOCAL para vetorizar os documentos (rodar 1x)
connect_supabase.py  -> script LOCAL de testes gerais
.env.example          -> modelo de variáveis de ambiente (uso local)
```

## Passo a passo

### 1. Banco de dados
Se ainda não fez: rode `schema.sql` e depois `seed.sql` no SQL Editor do Supabase.

### 2. Gerar os embeddings
1. `pip install supabase python-dotenv truststore`
2. Copie `.env.example` para `.env`, preencha `SUPABASE_URL` e a chave
   `service_role`
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
