import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.VITE_DEV_PORT || '5173', 10),
    hmr: false,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || `http://localhost:${process.env.VITE_TFRUNNER_PORT || '7621'}`,
        changeOrigin: true,
        ws: true,
      }
    }
  }
})
