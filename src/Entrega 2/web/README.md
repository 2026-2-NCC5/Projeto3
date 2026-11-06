# ASA Turbo · web (React 18 + Vite, PWA)

App responsivo e instalável com três áreas, separadas por papel e carregadas sob demanda:

| Papel | Página inicial | O que faz |
|---|---|---|
| estudante | `/chat` | Chat ASA Turbo: respostas com fontes e data, passo a passo, feedback, abstenção com encaminhamento ao ASA |
| atendente | `/fila` | Fila de risco, detalhe do estudante (score, fatores, tendência, recomendação) e validação humana |
| administrador | `/admin` | Painel agregado, fila de risco e base de conhecimento (cadastrar, nova versão, desativar) |
| equipe_tecnica | `/modelo` | Metadados do modelo de risco |

Contrato da API: [`../docs/api-contract.yaml`](../docs/api-contract.yaml). Design system: `src/styles/tokens.css`, `src/styles/base.css` e `/design-system.html`. Extensões do app em `src/styles/app.css`.

## Rodar

```bash
cd "src/Entrega 2/web"
npm install
npm run dev            # http://localhost:5173, em modo mock (sem backend, sem Supabase)
```

Contas de demonstração (modo mock e seeds): `estudante.demo@example.com`, `atendente.demo@example.com`, `admin.demo@example.com`, senha `AsaTurbo#Demo2026`.

### Modo mock

`src/api/api.js` é a única porta para a API. Com o mock ligado, as mesmas funções são respondidas por `src/api/mock/` com dados fictícios no formato exato do contrato (inclusive erros `401`, `403`, `404`, `409`, `422`, `429`).

- Padrão: ligado no `npm run dev`, desligado no build. Force com `VITE_API_MOCK=true|false`.
- Em dev, `?mock=0` ou `?mock=1` na URL alterna até fechar a aba.
- Cenários no chat: pergunta com "lento" (8 s), "erro" (falha de rede), "limite" (429); tema fora da base gera abstenção.
- Sessão expirada: no console, `asaMock.expirarSessao()` faz a próxima chamada responder 401.

### Contra o backend local

```bash
VITE_API_MOCK=false VITE_SUPABASE_URL=... VITE_SUPABASE_ANON_KEY=... npm run dev
```

O `vite.config.js` repassa `/me`, `/chat`, `/casos`, `/risco`, `/admin` e `/health` para `http://localhost:8000` (mude com `ASA_BACKEND_URL`). Em produção, `VITE_API_BASE_URL` vazio usa a mesma origem.

## Decisões

- **Sessão:** Supabase Auth com `@supabase/supabase-js` 2.45.4 (versão fixa), carregado só quando o login real é usado. O token fica no `localStorage` gerenciado pelo supabase-js. Além dele, o app só guarda no `localStorage` o nome dado a uma conversa e as conversas ocultadas, por usuário, e apaga tudo ao sair.
- **Token expirado:** a API responde 401, o app abre o login por cima da tela atual (nada é desmontado, então o texto digitado continua) e repete a chamada depois de entrar.
- **Rotas:** roteador próprio sobre a History API (`src/rotas/`). A guarda por papel espelha `x-papeis` do contrato; quem garante é o backend.
- **PWA:** `public/manifest.webmanifest`, ícones gerados da marca em `public/icones/`, `public/sw.js` com cache do shell (nunca de dados da API) e `public/offline.html`. O service worker só é registrado no build; ao publicar mudanças no shell, troque `VERSAO` em `sw.js`.
- **Gráficos:** SVG feito à mão (`src/componentes/graficos.jsx`), com dica no mouse e no foco, legenda e tabela equivalente para leitor de tela.

## Comandos

- `npm run build`: gera `dist/`
- `npm run preview`: serve o `dist/` (http://localhost:4173)
- `npm test`: testes de `src/util/`

`api/perguntar.py` (função Vercel da Entrega 2) continua aqui até o backend FastAPI assumir o `/chat`. O front novo não chama mais essa função.
