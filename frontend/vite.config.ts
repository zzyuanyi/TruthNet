import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// 后端服务地址（开发模式下通过 Vite proxy 转发，生产模式下由 Nginx 等反代）
const AGENT_API = process.env.AGENT_API_URL || 'http://127.0.0.1:8000'
const FILE_API = process.env.FILE_API_URL || 'http://127.0.0.1:8001'
const DEPLOY_API = process.env.DEPLOY_API_URL || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: parseInt(process.env.DEPLOY_RUN_PORT || process.env.FRONTEND_PORT || '3000'),
    host: true,
    proxy: {
      // ─── Agent API (端口 8000): 认证、会话管理、SSE对话、仪表盘、系统配置、搜索 ───
      '/api/auth': { target: AGENT_API, changeOrigin: true },
      '/api/sessions': { target: AGENT_API, changeOrigin: true, ws: true },
      '/api/dashboard': { target: AGENT_API, changeOrigin: true },
      '/api/system': { target: AGENT_API, changeOrigin: true },
      '/api/config': { target: AGENT_API, changeOrigin: true },
      '/api/enums': { target: AGENT_API, changeOrigin: true },
      '/api/quick-prompts': { target: AGENT_API, changeOrigin: true },
      '/api/recent-activities': { target: AGENT_API, changeOrigin: true },
      '/api/user': { target: AGENT_API, changeOrigin: true },
      '/output': { target: AGENT_API, changeOrigin: true },

            '/ws': { target: AGENT_API, changeOrigin: true, ws: true },

      // ─── File Upload API (端口 8001): 文件上传、解析、列表、状态 ───
      '/api/upload': { target: FILE_API, changeOrigin: true },
      '/api/files': { target: FILE_API, changeOrigin: true },

      // ─── Model Deploy Manager (端口 5000): 模型项目、版本、服务实例、流水线、推理、监控、Schema ───
      '/api/model-versions': { target: DEPLOY_API, changeOrigin: true },
      '/api/service-instances': { target: DEPLOY_API, changeOrigin: true },
      '/api/service-monitor': { target: DEPLOY_API, changeOrigin: true },
      '/api/pipelines': { target: DEPLOY_API, changeOrigin: true },
      '/api/schema': { target: DEPLOY_API, changeOrigin: true },
      '/api/modeling-runs': { target: DEPLOY_API, changeOrigin: true },
      '/api/repository': { target: DEPLOY_API, changeOrigin: true },
      '/api/models': { target: DEPLOY_API, changeOrigin: true },

      // 兜底：未匹配的 /api 请求转发到 Agent API
      '/api': { target: AGENT_API, changeOrigin: true },
    },
  },
})
