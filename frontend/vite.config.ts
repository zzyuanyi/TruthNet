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
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return;
          if (id.includes('/d3-') || id.includes('/d3/') || id.includes('d3-selection') || id.includes('d3-interpolate')) return 'vendor-d3';
          if (id.includes('recharts') || id.includes('victory-vendor') || id.includes('/d3')) return 'vendor-charts';
          if (id.includes('react-syntax-highlighter') || id.includes('refractor') || id.includes('prismjs') || id.includes('highlight.js')) return 'vendor-syntax';
          if (id.includes('react-markdown') || id.includes('remark') || id.includes('unified') || id.includes('micromark') || id.includes('mdast')) return 'vendor-markdown';
        },
      },
    },
  },
})
