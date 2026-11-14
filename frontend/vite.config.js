import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: process.env.FIGMA ? Number(process.env.PORT || 5173) : 5173,
    host: process.env.FIGMA ? (process.env.FIGMA_DEV_SERVER_HOST || '0.0.0.0') : true,
    strictPort: Boolean(process.env.FIGMA),
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
