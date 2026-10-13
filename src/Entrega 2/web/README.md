# ASA · novo frontend (React + Vite)

Em construção. O frontend em produção continua sendo `src/Entrega 1/index.html`.
Esta pasta é separada de `src/Entrega 1/` de propósito: a versão em produção (e seu deploy no Vercel) segue intacta até a nova ser aprovada, e o rollback é simplesmente não fazer a troca.

## Rodar localmente

Requisitos: Node 18+ (testado com Node 22.14 / npm 10.9).

```bash
cd "src/Entrega 2/web"
npm install      # só na primeira vez
npm run dev
```

Abra http://localhost:5173. Para parar: `Ctrl+C` no terminal.

Em desenvolvimento, as chamadas a `/api/*` são repassadas para a API de produção
(`https://projeto-ia-rho.vercel.app`) pelo proxy em `vite.config.js`. Não é preciso
Vercel CLI, `.env` nem nenhuma chave.

## Outros comandos

- `npm run build`: gera a versão de produção em `dist/`
- `npm run preview`: serve o `dist/` localmente (http://localhost:4173). Atenção: o `preview` não usa o proxy, então as chamadas `/api` não funcionam nele sem `VITE_API_URL`.

## Variáveis

Veja `.env.example`. Só existe `VITE_API_URL`, que é **pública** (vai parar no JS do navegador).

## Exemplos reais da API

`src/api/__fixtures__/` guarda respostas reais capturadas em 12/10/2026. Veja o README da pasta.
