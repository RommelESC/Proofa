import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy al backend: evita CORS y deja las rutas relativas en el codigo.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
