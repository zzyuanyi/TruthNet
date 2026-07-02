# 前端初始化报告

> 时间：2026-07-02

## 初始化结果

**状态：PASSED**

## 技术栈

| 技术 | 版本 |
|------|------|
| React | 18.3.1 |
| Vite | 6.4.3 |
| TypeScript | 5.6.3 |
| pnpm | 11.9.0 |
| Node.js | v26.1.0 |

## 文件清单

```text
frontend/
  README.md                 — 前端开发说明
  package.json              — 依赖与脚本
  pnpm-lock.yaml            — 锁文件（可复现）
  index.html                — 入口 HTML
  vite.config.ts            — Vite 配置（含 /api 代理）
  tsconfig.json             — TS 项目引用
  tsconfig.app.json         — 应用 TS 配置
  tsconfig.node.json        — Node/Vite TS 配置
  .env.example              — 环境变量模板
  src/
    main.tsx                — 入口
    App.tsx                 — 主应用（HTTP + WS 双模式）
    vite-env.d.ts           — Vite 类型声明
    api/
      client.ts             — HTTP fetch + WebSocket 客户端
    types/
      api.ts                — 类型定义（与 backend schema 一致）
    components/
      ChatPanel.tsx          — 输入组件（HTTP/WS 切换）
      RiskPanel.tsx          — 风险评分条
      EvidenceList.tsx       — 证据链表格
      TimelinePanel.tsx      — 事件时间线
      GraphPanel.tsx         — 关系图谱占位
```

## 前端功能

- ✅ HTTP REST 模式：POST /api/v1/chat
- ✅ WebSocket 模式：WS /api/v1/chat/ws（含连接/断开按钮）
- ✅ 回答显示区
- ✅ 风险评分显示区（4 维度进度条：综合/财务/股权/舆情）
- ✅ 证据列表（表格）
- ✅ 事件时间线
- ✅ 关系图谱占位（节点 + 边数据展示）
- ✅ missing_modules 显示
- ✅ trace_id 显示
- ✅ 错误提示

## pnpm 安装方式

pnpm 原本未安装。通过以下方式安装：

```bash
npm install -g pnpm
```

> 注意：如果用 corepack 启用 pnpm 更安全（`corepack enable && corepack prepare pnpm@latest --activate`），但本机 corepack 不在 PATH 中，故用 npm 全局安装。

## 构建验证

```bash
$ pnpm install
Packages: +71
Done

$ pnpm typecheck
# 无错误输出

$ pnpm build
✓ 33 modules transformed.
dist/index.html      0.52 kB
dist/assets/...js  153.75 kB
✓ built in 402ms
```

## esbuild 构建批准

pnpm v10+ 默认不运行构建脚本。需要在首次 install 后批准 esbuild：

```bash
pnpm approve-builds esbuild
```

CI 中使用 corepack 自动启用的 pnpm，不需要手动 approve。

## 未引入的依赖

按照 Prompt4 要求，本轮**未引入**以下复杂依赖：

- ❌ shadcn/ui（UI 组件库）
- ❌ d3 / visx（图表库）
- ❌ Recharts（图表库）
- ❌ react-markdown（Markdown 渲染）
- ❌ msw（Mock Service Worker）
- ❌ ESLint（代码检查）
- ❌ Tailwind CSS

## 风险与限制

| 项目 | 说明 |
|------|------|
| 纯展示组件 | 未实际连接后端验证（需启动后端后测试） |
| 无路由 | 单页面应用，无 React Router |
| 无状态管理 | 仅使用 React useState |
| 无 CSS 框架 | 使用内联样式 |

## 结论

最小前端项目已成功初始化。React + Vite + TypeScript 栈完整可用。`pnpm install` + `pnpm build` 通过。前后端类型定义一致。

**状态：PASSED**
