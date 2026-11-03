import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const raiz = dirname(fileURLToPath(import.meta.url))

// Em `npm run dev` o app usa o modo mock por padrão (src/config.js).
// Com VITE_API_MOCK=false, as rotas do contrato vão para o backend local (docker compose).
// As mesmas rotas também são páginas do app (/chat, /admin...): pedidos de HTML ficam com o Vite.
const BACKEND_LOCAL = process.env.ASA_BACKEND_URL || 'http://localhost:8000'
const paraBackend = {
  target: BACKEND_LOCAL,
  changeOrigin: true,
  bypass: (req) => (req.headers.accept?.includes('text/html') ? req.url : undefined),
}

// Build sem mock quando VITE_API_MOCK=false (produção/Docker): os módulos de src/api/mock/
// ficam fora do bundle. Em `npm run dev` o mock continua disponível.
const COM_MOCK = process.env.VITE_API_MOCK !== 'false'

export default defineConfig({
  plugins: [react()],
  define: { __COM_MOCK__: JSON.stringify(COM_MOCK) },
  build: {
    rollupOptions: {
      // design-system.html: página de referência dos tokens e primitivas (CSS puro).
      input: {
        main: resolve(raiz, 'index.html'),
        'design-system': resolve(raiz, 'design-system.html'),
      },
    },
  },
  server: {
    proxy: Object.fromEntries(['/me', '/chat', '/casos', '/risco', '/admin', '/health'].map((p) => [p, paraBackend])),
  },
})
