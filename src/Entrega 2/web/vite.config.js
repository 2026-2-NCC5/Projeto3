import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const raiz = dirname(fileURLToPath(import.meta.url))

// Em desenvolvimento, /api/* é repassado para a API de produção.
// Assim o `npm run dev` funciona sem Vercel CLI e sem segredos locais.
const API_PROXY_TARGET = 'https://projeto-ia-rho.vercel.app'

export default defineConfig({
  plugins: [react()],
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
    proxy: {
      '/api': { target: API_PROXY_TARGET, changeOrigin: true },
    },
  },
})
