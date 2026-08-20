# DESIGN.md — TruthNet 前端设计规范

## 品牌与视觉方向

- 产品：织网鉴真，财报反欺诈智能问答系统（面向个人投资者）。
- 气质：理性、可信、可解释。强调「证据链 / 股权穿透 / 口径透明」的可解释性底色。
- 意象锚点：审计工作台 —— 克制的中性底色上，以红/橙/绿风险色作为唯一的高饱和信号，避免营销式渐变色。

## Design Tokens

### 色彩

- 基础色板：使用 `globals.css` 的 shadcn 语义变量（`--background` / `--foreground` / `--card` / `--muted` / `--primary` / `--border`），禁止硬编码 Hex / Tailwind 原生色盘。
- 风险等级色（业务语义，例外允许）：
  - 高风险：红（`--destructive` / 红系）
  - 中风险：橙
  - 低风险 / 安全：翠绿
- 图表数据：使用 Semantically 变量 `--chart-1` ~ `--chart-5`。

### 字体

- 字体族：Inter（Google Fonts，走 `.cn` 域 `fonts.googleapis.cn`）。
- 数字：财务指标统一 `font-variant-numeric: tabular-nums`（已由 `AnimatedNumber` 组件处理）。

### 圆角 / 阴影

- 圆角：仅使用 `--radius` 派生的 `rounded-md/lg/xl`，禁止写死像素圆角。
- 阴影：使用语义阴影变量，避免过重投影。

### 卡片与玻璃拟态

- 卡片：`bg-card/80 + backdrop-blur-sm + border-border`，配合全局 `body::before` 微纹理径向渐变，使磨砂效果在浅色下也可见。

## 布局与响应式

- 断点基线：375 / 768 / 1440。
- 画像页采用左侧锚点导航 + 主内容列，影响建议区块置于核心结论之后（首屏可见）。

## 组件规范

- 表格（Markdown / 数据表）：表头 `bg-muted`，单元格 `border-border`，随深浅主题自适应。
- 图 / 明细标签统一主题语义类，不混用 Tailwind 原生色。

## 可访问性

- 深色模式下文字使用 `text-foreground` / `text-muted-foreground`，禁止硬编码黑/白色。
- 交互元素保留 focus-visible 轮廓。

## 设计禁忌

- 禁止蓝紫渐变、科技蓝+圆角卡片式的 AI 味模板。
- 禁止全角标点（代码 / className 中）。
- 禁止为「好看」堆叠无信息量的装饰性动画，动画服务于数据揭示。