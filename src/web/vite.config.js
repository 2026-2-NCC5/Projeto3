import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento, /api/* é repassado para a API de produção.
// Assim o `npm run dev` funciona sem Vercel CLI e sem segredos locais.
const API_PROXY_TARGET = 'https://projeto-ia-rho.vercel.app'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: API_PROXY_TARGET, changeOrigin: true },
    },
  },
})
