# TruthNet 前端

## 状态

**当前状态：NOT_RUN — 待 pnpm 安装后初始化**

> Prompt3 (2026-07-02)：Node.js v26.1.0 可用，但 pnpm 未安装。前端项目尚未初始化。
> 后端 HTTP/WebSocket 端点已可测，前端开发可随时启动。

## 技术栈

- **框架**: React 18+
- **构建工具**: Vite
- **语言**: TypeScript
- **包管理**: pnpm
- **UI 组件**: shadcn/ui
- **图表**: Recharts / d3 / visx
- **Markdown**: react-markdown

## 初始化（待执行）

### 前置条件

```bash
# 1. 安装 pnpm
npm install -g pnpm

# 2. 验证
pnpm --version
```

### 创建项目

```bash
# 使用 Vite 创建 React + TypeScript 项目
pnpm create vite frontend --template react-ts

# 上述命令会将项目创建到 frontend/ 目录下。
# 如果目录已存在内容，请先备份再操作。
```

## 安装与启动

```bash
cd frontend
pnpm install
pnpm dev
```

## 接口开发指南

### Contract-First 原则

前端开发必须遵循 `docs/API_CONTRACT.md` 中的接口定义和 mock JSON。

### 后端端点（当前可用）

| 端点 | 类型 | 状态 |
|------|------|------|
| `GET /health` | HTTP REST | ✅ 已实现 |
| `POST /api/v1/chat` | HTTP REST | 🔶 Mock 占位 |
| `WS /api/v1/chat/ws` | WebSocket | 🔶 Mock 实现（Prompt3） |

### Mock 开发方案

推荐使用 `msw` (Mock Service Worker)：

```bash
pnpm add -D msw
```

在 `src/mocks/` 中根据 `docs/API_CONTRACT.md` 的 mock JSON 创建 handler。

### 开发流程

1. 阅读 `docs/API_CONTRACT.md` 了解接口
2. 复制 mock JSON 到本地 mock handler
3. 基于 mock 数据开发 UI
4. 后端就绪后切换到真实 API

### 禁止事项

- ❌ 前端不得私自修改后端定义的字段名和类型
- ❌ 前端不得依赖后端未写入 `docs/API_CONTRACT.md` 的临时字段
- ❌ 接口变更不走 `docs/INTERFACE_CHANGELOG.md` 流程

如发现接口设计问题，在 `docs/INTERFACE_CHANGELOG.md` 提出变更建议。
