# AGENTS.md — TruthNet 前端开发规范

## 项目概览

TruthNet（织网鉴真）前端，财报反欺诈智能问答系统。与后端 FastAPI（8000 端口）+ WebSocket 协作，前端通过 Vite proxy 转发 `/api/*` 与 `/ws/*`。

## 技术栈

- React 18 + Vite 6 + TypeScript 5.6
- shadcn/ui + Tailwind CSS v4
- 图表：Recharts；图谱可视化：D3.js
- Markdown：react-markdown + remark-gfm + react-syntax-highlighter（PrismLight 按需注册）
- 动效：@formkit/auto-animate、react-hotkeys-hook、cmdk（⌘K 命令面板）

## 目录结构

```
frontend/src/
  pages/           7 个路由页（ChatPage / CompanyProfilePage / ComparePage / ReportPage / RulesPage / SettingsPage / NotFoundPage）
  components/
    ui/            shadcn/ui 基础组件（card / badge / skeleton / dialog 等）
    truthnet/      业务组件（ChatInterface / EquityGraph / EquityInsight / UpstreamDownstream / RelatedPartyTable / RiskTimeline / RuleCard / EvidenceChain 等）
  lib/             api-client.ts（REST + WS 封装）、utils.ts（cn）
  types/truthnet.ts  数据契约类型（与后端 schemas 对齐）
  hooks/           useDocumentTitle 等
```

## 构建与测试命令

```bash
cd frontend
pnpm install               # 安装依赖（仅允许 pnpm，禁止 npm/yarn）
pnpm dev                   # 开发（Vite HMR）
pnpm ts-check              # tsc -p tsconfig.app.json --noEmit（类型检查）
pnpm build                 # vite build（生产构建）
pnpm lint                  # ESLint
```

## 关键约定与红线

- **verbatimModuleSyntax**：类型导入必须用 `import type { X }`。
- **禁止硬编码颜色**：使用 `globals.css` 主题变量与 Tailwind 语义类（`bg-background` / `text-muted-foreground` / `bg-primary/10`）。唯一例外是金融风控业务语义色（红/橙/绿风险等级）。
- **禁止硬编码圆角像素**：用 `rounded-md/lg` 等基于 `--radius` 的类。
- **Hydration 安全**：`Date.now()` / `Math.random()` 等动态值必须在 `useEffect + useState` 内，禁止在 JSX 渲染中直接调用。
- **大文件分段写入**：超出 2000 行或 15000 token 的文件禁止单次 `write_file` 全量写入。
- **字体**：Google Fonts 走 `.cn` 域（`fonts.googleapis.cn`），在 `index.css` 顶部 `@import`（必须位于其它语句之前）。

## 数据契约注意

- `types/truthnet.ts` 与后端 `backend/app/schemas` 对齐，字段变更需同步。
- `FinanceRuleItem.similar_cases` 字段仍保留（后端 finance 端点检索能力），但前端画像页已改为「上下游企业关系」（`UpstreamDownstream`），不再渲染 `SimilarCases`。
- WebSocket 采用 V12 信封协议（`event_type` + `payload`）。

## 端口与代理

- 前端 dev 端口由 `${DEPLOY_RUN_PORT}` 决定，代理 `http://127.0.0.1:8000`。
- 沙箱预览仅跑前端，后端未运行时 `/api/*` 会 ECONNREFUSED（属预期）。