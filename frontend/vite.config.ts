import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  // Vite 配置运行在 Node 侧，需显式加载 .env；浏览器侧由 src/config.ts 读取同名变量。
  const env = loadEnv(mode, process.cwd(), '')
  const backendApi = env.VITE_API_BASE_URL || 'http://127.0.0.1:8001'
  const frontendPort = parseInt(env.DEPLOY_RUN_PORT || env.FRONTEND_PORT || '5000')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: frontendPort,
      host: true,
      proxy: {
        // TruthNet 后端 API（完整演示默认端口 8001，可由 VITE_API_BASE_URL 覆盖）
        '/api/v1': { target: backendApi, changeOrigin: true },

        // WebSocket 对话
        '/api/v1/chat/ws': {
          target: backendApi.replace('http', 'ws'),
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      minify: 'terser',
      chunkSizeWarningLimit: 1300,
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return;
            // three.js + react-globe.gl 单独拆包（体积大且仅地球组件使用）
            if (id.includes('react-globe.gl') || id.includes('globe.gl') || id.includes('three-globe') || id.includes('three-render-objects')) return 'vendor-globe';
            if (id.includes('/three/examples/')) return 'vendor-three-ext';
            if (id.includes('/three/')) return 'vendor-three';
            if (id.includes('/d3-') || id.includes('/d3/') || id.includes('d3-selection') || id.includes('d3-interpolate')) return 'vendor-d3';
            if (id.includes('recharts') || id.includes('victory-vendor') || id.includes('/d3')) return 'vendor-charts';
            if (id.includes('react-syntax-highlighter') || id.includes('refractor') || id.includes('prismjs') || id.includes('highlight.js')) return 'vendor-syntax';
            if (id.includes('react-markdown') || id.includes('remark') || id.includes('unified') || id.includes('micromark') || id.includes('mdast')) return 'vendor-markdown';
          },
        },
      },
    },
  }
})
