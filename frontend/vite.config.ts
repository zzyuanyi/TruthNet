import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// TruthNet 后端服务地址（开发模式下通过 Vite proxy 转发）
const BACKEND_API = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: parseInt(process.env.DEPLOY_RUN_PORT || process.env.FRONTEND_PORT || '5000'),
    host: true,
    proxy: {
      // TruthNet 后端 API (端口 8000)
      '/api/v1': { target: BACKEND_API, changeOrigin: true },

      // WebSocket 对话
      '/api/v1/chat/ws': {
        target: BACKEND_API.replace('http', 'ws'),
        changeOrigin: true,
        ws: true
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser',
  },
})
