# ASA - Agente para o Estudante — Protótipo Avançado

Frontend + API (FastAPI) + Supabase (pgvector), tudo deployado junto no Vercel.

## Estrutura
```
index.html          -> chat widget embutido no portal (frontend)
api/index.py         -> API do agente (backend, roda no Vercel)
vercel.json          -> configuração de rotas do Vercel
requirements.txt     -> dependências Python da API
gerar_embeddings.py  -> script LOCAL para vetorizar os documentos (rodar 1x)
.env.example          -> modelo de variáveis de ambiente
```

## Passo a passo

### 1. Banco de dados
1. Crie um projeto em supabase.com
2. Rode `schema.sql` no SQL Editor (arquivo enviado anteriormente)
3. Rode `seed.sql` no SQL Editor

### 2. Gerar os embeddings dos documentos
1. `pip install supabase python-dotenv`
2. Copie `.env.example` para `.env` e preencha com a `SUPABASE_URL` e a chave
   `service_role` (Project Settings > API Keys)
3. Rode: `python gerar_embeddings.py`
4. Isso preenche a coluna `embedding` de cada chunk no Supabase

### 3. Deploy no Vercel
1. Suba esta pasta inteira para um repositório no GitHub
2. Em vercel.com, importe o repositório
3. Em **Project Settings > Environment Variables**, adicione:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY` (a mesma chave `service_role` do passo anterior)
4. Clique em Deploy

### 4. Testar
Abra a URL gerada pelo Vercel, clique no ícone de chat no canto inferior
direito e pergunte algo como "Posso suspender meu curso esse semestre?".
A resposta vem da API, que busca no Supabase via `pgvector`.

## Como funciona o fluxo completo
```
Aluno digita pergunta no chat (index.html)
        │
        ▼
POST /api/perguntar  (api/index.py, rodando no Vercel)
        │
        ▼
Vetoriza a pergunta (hashing + normalização L2)
        │
        ▼
Chama a função buscar_chunks_similares() no Supabase (pgvector, cosseno)
        │
        ▼
Retorna os documentos mais similares + resposta + score de confiança
        │
        ▼
Frontend exibe resposta, fonte e painel "Ver evidências"
```

## Observações importantes para o pitch
- A chave `service_role` do Supabase **só existe no backend** (variável de
  ambiente do Vercel) — nunca é exposta ao navegador. Isso é o padrão
  correto de segurança.
- Se quiser evoluir ainda mais: trocar o "hashing trick" por embeddings de
  um modelo de linguagem real (ex: `sentence-transformers`) rodando fora do
  Vercel (ele tem limite de tamanho de função), como em um Cloud Run/EC2 —
  aí sim usando o "Projeto Interdisciplinar" completo com nuvem própria.
