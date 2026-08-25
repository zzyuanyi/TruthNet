# DESIGN.md — TruthNet 前端设计规范

> 交叉审阅结论：taste(反 AI 味) × design-md-collection(产业规范性，对标 Stripe / Revolut)。
> 产品属 Operate 模式（数据密集工具），不是营销页。设计准则：可扫读、一致、克制，品牌藏于精确细节。

## 品牌与视觉方向

- 产品：织网鉴真，财报反欺诈智能问答系统（面向个人投资者）。
- 气质：理性、可信、可解释。强调「证据链 / 股权穿透 / 口径透明」的可解释性底色。
- 意象锚点：**金融审计终端 / 财报法证台**（对标 Bloomberg / 万得 Wind / Stripe Dashboard），而非营销页。

## Design Read（一句话设计定位）

> 深海军蓝 ink 作为品牌基色，冷调中性底 + 头发丝级 1px 分隔线，等宽数字对齐财务指标，语义色（红/橙/黄/绿）只标注风险数据、绝不做按钮；克制到几乎无装饰性动效。

## 三旋钮（Operate 模式基线）

- DESIGN_VARIANCE: 3（对称、可预测、专业工具）
- MOTION_INTENSITY: 2（几乎静态，仅 hover / focus 状态反馈）
- VISUAL_DENSITY: 7（数据密集，1px hairline 分隔，等宽数字）

## Design Tokens

### 色彩（核心：去「科技蓝」AI 味）

- 主色 `--color-primary`：深海军蓝 `#0f3a5d`（Stripe ink 家族），**禁止** `#2563eb` 这类高饱和科技蓝 / 蓝紫渐变。
- 文本主色 `--color-foreground`：深海军蓝 ink `#0d253d`（非纯黑）。
- 背景 `--color-background`：冷调 off-white `#f6f8fa`（Stripe canvas-soft），非 slate 冷灰、非暖纸色。
- 边框 `--color-border`：hairline `#e3e8ee`，**边框优先于阴影**（Revolut 规范：无传统 drop-shadow，靠 hairline + 表面亮度分层）。
- 暗色主题：深海军蓝近黑 `#0a1622` 为底，主色用亮海军蓝 `#4f8cc6`，保持蓝家族一致并保证对比。

### 语义色（风险数据标注专用，6 级，后端契约不可改）

- `red` 高危 / `orange` 中高危 / `yellow` 中等 / `blue` 低风险 / `green` 正常 / `unknown` 未知。
- 语义色**只用于数据标注与图表**，绝不做主按钮 / 品牌强调色。

### 字体

- 字体族：`IBM Plex Sans`（UI）+ `IBM Plex Mono`（数据/数字/代码）。**弃用 Inter**（AI 味默认），走 `.cn` 域 `fonts.googleapis.cn`。
- 中文回退：PingFang SC / Microsoft YaHei。
- 数字：财务指标全局 `font-variant-numeric: tabular-nums`（Stripe「金融静默信号」）。

### 圆角 / 阴影

- 圆角：仅 `--radius` 派生，禁止写死像素。
- 阴影：以 hairline 边框为主，阴影仅在需要真实层级时使用且须 tint 到背景色相（禁纯黑投影）。

### 卡片（去玻璃拟态）

- 卡片：实底 `--color-card` + hairline 边框。**移除** `backdrop-blur` 磨砂玻璃与 `body::before` 微纹理径向渐变（Operate 工具不使用玻璃拟态）。

## 布局与响应式

- 断点基线：375 / 768 / 1440。
- 画像页左侧锚点导航 + 主内容列，影响建议区块置于核心结论之后（首屏可见）。

## 组件规范

- 表格（Markdown / 数据表）：表头 `bg-muted`，单元格 `border-border`，数字列 `tabular-nums`。
- 图 / 明细标签统一主题语义类，不混用 Tailwind 原生色（语义风险色例外）。

## 动效与交互

- 卡片：**移除自动入场浮入动画**（工具型产品不应有加载干扰），hover 仅边框颜色微调（可点性提示）、**不做位移和大阴影**。
- 聚焦：输入框用克制的边框加深 + `--ring`，**移除发光环**。
- 骨架屏：shimmer 扫光（加载反馈，有功能意义）。
- 风险信号：红/橙风险图标 `animate-pulse` 呼吸（传达实时语义，非装饰）。
- 减少动画：`--reduce-motion: reduce`（Settings 开关）时禁用所有 `animation` / `transition`。

## 可访问性

- 深色模式文字用 `text-foreground` / `text-muted-foreground`，禁止硬编码黑/白。
- 聚焦主线：主按钮白字对深海军蓝底对比 ≥ 4.5:1（light `#0f3a5d` 白字约 9:1）。
- 交互元素保留 focus-visible 轮廓。

## 设计禁忌

- 禁止蓝紫渐变、科技蓝 `#2563eb` + 圆角卡片式 AI 味模板。
- 禁止玻璃拟态、mesh 渐变背景、发光环、卡片自动入场浮入动画。
- 禁止 Inter 作默认字体、禁止三栏等分无区分卡片、禁止为「好看」堆叠无信息量动画。
- 禁止全角标点（代码 / className 中）。