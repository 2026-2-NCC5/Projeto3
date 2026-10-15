# ASA · frontend (React + Vite) - Entrega 2

Esta é a versão em produção a partir da Entrega 2, substituindo
`src/Entrega 1/index.html`. A API também mudou: `api/perguntar.py` agora usa
embeddings da Cloudflare Workers AI (`@cf/baai/bge-m3`, 1024 dimensões,
multilíngue) em vez da Hugging Face (`bge-small-en-v1.5`, 384d, inglês) - veja
o cabeçalho de `api/perguntar.py` para o motivo da troca.

**Para publicar esta pasta no Vercel:** Project Settings > General > Root
Directory > `src/Entrega 2/web`. Veja `vercel.json` nesta pasta para a
configuração de build/rotas, e `../.env.example` para as variáveis de
ambiente que a função em `api/` precisa (e que também precisam estar em
Project Settings > Environment Variables).

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
