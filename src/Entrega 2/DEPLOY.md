# Deploy do ASA Turbo (container único)

Um único container serve o web (PWA) e a API: `/api/*` vai para a API, `/health` e `/metrics` também, e o resto vai para o app. Em `DEMO_MODE=true`, que é o padrão da imagem, os dados são os seeds fictícios carregados em memória. Nesse modo não há Supabase nem rede externa, e o login entra pelos três perfis de demonstração.

> **Antes de qualquer `git push`:** o commit `ee7c027` ("Adicionado Data") tem os CSVs com dados reais de 12.842 alunos. Ele **não está no GitHub** hoje. Não envie a `main` sem antes limpar o histórico (seção "Limpar o histórico"). Os caminhos A e B abaixo **não precisam de push**.

## 0. Testar a imagem localmente (2 min)

```bash
cd "src/Entrega 2"
docker build -t asa-turbo:0.9.0 .
docker run --rm -p 8080:8080 asa-turbo:0.9.0
scripts/smoke.sh http://localhost:8080        # 8 itens, todos OK
```

## A. Render com imagem pronta (sem git push, recomendado)

1. Publique a imagem no GitHub Container Registry. Para isso, use um token *classic* com escopo `write:packages`:
   ```bash
   echo "$GHCR_TOKEN" | docker login ghcr.io -u <usuario-github> --password-stdin
   docker tag asa-turbo:0.9.0 ghcr.io/<usuario-github>/asa-turbo:0.9.0
   docker push ghcr.io/<usuario-github>/asa-turbo:0.9.0
   ```
   Em github.com → Packages → asa-turbo → Package settings, deixe o pacote **Public**, ou cadastre a credencial no Render.
2. No Render, siga **New → Web Service → Existing Image**. Em *Image URL*, informe `ghcr.io/<usuario-github>/asa-turbo:0.9.0`. Em *Instance type*, escolha **Free**.
3. Em **Advanced**, preencha *Health Check Path* com `/health`. Em *Environment*, use `DEMO_MODE=true`. O `PORT` é injetado pelo próprio Render.
4. Clique em **Deploy**. A URL fica no formato `https://asa-turbo-xxxx.onrender.com` e já tem HTTPS.
5. Rode `scripts/smoke.sh https://asa-turbo-xxxx.onrender.com`.

**Plano grátis do Render:** o serviço dorme depois de 15 min sem acesso, e a primeira requisição depois disso leva cerca de 50 s. **Abra a URL uns 5 min antes de apresentar.** Ao acordar, os dados voltam ao estado inicial.

## B. Fly.io (sem git push, a partir da pasta local)

```bash
curl -L https://fly.io/install.sh | sh          # instala o flyctl
fly auth login
cd "src/Entrega 2"
fly launch --no-deploy --copy-config --name asa-turbo-<sufixo>   # aceite a região gru
fly deploy
scripts/smoke.sh https://asa-turbo-<sufixo>.fly.dev
```

O `fly.toml` mantém uma máquina sempre ligada, então não há espera de cold start.

## C. Render Blueprint (`render.yaml` na raiz do repositório)

Só depois de limpar o histórico. Faça o push da `main` e siga **New → Blueprint**, escolhendo o repositório. O Blueprint usa `rootDir: src/Entrega 2`, `healthCheckPath: /health` e o plano grátis.

## Variáveis de ambiente

| Variável | Demo | Supabase real | Observação |
|---|---|---|---|
| `PORT` | auto | auto | Render, Fly e Cloud Run injetam. O padrão da imagem é 8080. |
| `DEMO_MODE` | `true` | `false` | Liga os seeds em memória, o `/api/demo/*` e o login rápido. |
| `DEMO_PASSWORD` | opcional | — | Senha dos 3 e-mails de demo. O padrão é `AsaTurbo#Demo2026`. |
| `SUPABASE_URL` | — | obrigatória | `https://<projeto>.supabase.co` |
| `SUPABASE_SERVICE_KEY` | — | obrigatória | Chave legacy `service_role` (`eyJ...`). **Só no backend.** |
| `SUPABASE_JWT_SECRET` | — | obrigatória | Em Settings → API → JWT Secret. |
| `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` | — | recomendadas | Embeddings bge-m3. Sem elas, o chat usa o TF-IDF local. |
| `HF_API_TOKEN` | — | opcional | Reserva dos embeddings. |
| `CORS_ORIGINS` | — | opcional | Só se o web estiver em outro domínio. No container único é a mesma origem. |
| `APP_ENV`, `LOG_LEVEL` | `producao`, `INFO` | idem | Logs em JSON no stdout. |

O modo Supabase real também exige rebuild do web com as chaves **públicas**:
`docker build --build-arg VITE_SUPABASE_URL=https://<projeto>.supabase.co --build-arg VITE_SUPABASE_ANON_KEY=<anon> -t asa-turbo:0.9.0 .`

## Painel do Supabase (só com `DEMO_MODE=false`)

1. Em **Authentication → URL Configuration**, preencha *Site URL* com a URL pública (por exemplo `https://asa-turbo-xxxx.onrender.com`). Em *Redirect URLs*, coloque `https://asa-turbo-xxxx.onrender.com/**`.
2. No **SQL Editor**, rode `infra/sql/002`, `003` e `004`, nesta ordem. Depois rode `python3 seeds/criar_usuarios_demo.py` e `seeds/seed_demo.sql`.
3. **CORS:** não precisa configurar no Supabase. O navegador só fala com o Supabase Auth, que aceita a origem cadastrada no passo 1. O backend fica na mesma origem do web.

## Durante a apresentação

- Para voltar ao estado inicial, rode `scripts/reset_demo.sh https://<url>` (leva 2 s). Reiniciar o serviço tem o mesmo efeito.
- O topo da fila mostra 3 vermelhos com tendência de alta: queda de notas, inadimplência e sumiço das aulas (queda de frequência).
- No chat, as 6 perguntas sugeridas foram validadas: as 5 primeiras respondem com fonte, e "cardápio do restaurante" mostra a abstenção com encaminhamento ao ASA.

## Limpar o histórico (antes de qualquer push)

```bash
pip install git-filter-repo
cd /home/ericbittu/Projeto3
git branch backup-antes-limpeza                  # garantia local
git filter-repo --invert-paths --path "src/Entrega 2/data" --path "src/Entrega 2/db" --force
git log --all --oneline -- "src/Entrega 2/data"  # precisa sair vazio
git remote add origin https://github.com/2026-2-NCC5/Projeto3.git   # o filter-repo remove o remote
```

Isso reescreve os hashes de todos os commits a partir de `ee7c027`. Combine com a equipe antes de enviar.
