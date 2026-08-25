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

---

## 首页欢迎 Hero（暗黑电影感开场，局部专属）

> 2026-08 升级：首页欢迎区（ChatInterface 空状态）参考「暗黑电影感 landing」（NOVA_AI 排版语言），作为**进入工具前的「电影开场」**，与上述 Operate 克制主体形成「开场 → 工具」体验分层。**仅作用于欢迎区**，不扩展到画像页 / 对话流程等产品主体。

### 定位
- 欢迎区 = 首屏沉浸式 hero，营造可信且有仪式感的开场，**配色与主题（明/暗）完全同步**——系统深色则深色、浅色则浅色。

### 配色（语义化，跟随主题变量，不硬编码色值）
- 背景用 `bg-background`，叠加两层 `radial-gradient`：顶部 `color-mix(in srgb, var(--color-primary) 18%, transparent)` → 透明、右侧 `color-mix(in srgb, var(--color-primary) 10%, transparent)` → 透明。
- 叠加极淡网格 `color-mix(in srgb, var(--color-foreground) 5%, transparent)`，营造精细节奏（非 AI 味蓝紫渐变 / mesh）。
- 文本：`text-foreground` / `text-muted-foreground` / `text-primary`；快捷卡片 `bg-card` + `border-border`，hover `bg-primary` + `text-primary-foreground`。

### 字体
- 标题：IBM Plex Sans `font-medium` + `tracking-tight`（延续既有字体，**不引入** Flexo Soft Medium 等外部在线字体资产）。
- 品牌词标 / 版本标注：IBM Plex Mono `font-mono` + `tracking-widest`。

### 布局
- 多行交错大标题：`织网鉴真`（pl-6）→ `财报反欺诈`（无缩进）→ `· 智能问答`（pl-12，`font-light`），营造电影感的视觉纵深与节奏。
- 快捷入口 **1×4 一行四张**（`grid-cols-2 sm:grid-cols-4`，移动端回落 2×2），卡片竖排：图标 + 标题 + 描述。
- 快捷卡描述文案 = **功能直述**，10~15 字以内（如「校验三大报表勾稽关系与粉饰痕迹」），**不用**带具体公司名的示例问句。
- 图标语言：**Phosphor Duotone 双色图标**（`@phosphor-icons/web/duotone`，MIT 开源，本地 npm 依赖）——图标底色层用主题 primary 低饱和、上层描线用 primary，`::before`（底色层）+ `::after`（描线层）天然双层；替代 AI 味过重的 lucide 细线图标，仅欢迎区快捷卡使用，主体界面维持 lucide。
- 快捷卡为**液态玻璃**（`.tn-glass-card`，用户指定参考 Serene 语言）：低透明度底 + `backdrop-blur` + 顶部 1px 高光内阴影 + `mask-composite` 渐变描边；**这是欢迎区专属例外**，产品主体（画像页/表格/对话流）仍遵守「实底 + hairline、禁玻璃拟态」。
- 卡片波浪动画 `tn-wave`：透明度/亮度/位移三通道同周期起伏，`animation-delay` 按索引递增（约 120ms），形成一行扫过的波动节奏；`--reduce-motion` 时静止。

### 动效（欢迎区专属入场）
- Reveal 交错入场：IntersectionObserver（threshold 0.15）触发，`translate-y-8 + opacity-0` → `translate-y-0 + opacity-100`，`duration-700 ease-out`，`transitionDelay` 以 90–120ms 递增。
- 这是**欢迎区专属**的入场动画，主体（Operate）仍保持「无自动入场浮入」原则；完整遵守 `--reduce-motion` 降级。

## Logo 动效（织网鉴真 · 眼）

> 2026-08 升级：队名「织网鉴真」落到品牌标记——「数据点织网 → 融合成一只眼 → 瞳孔持续扫视」，呼应「织网 + 鉴真（观察）」。

### 意象锚点
- 一堆数据点 / 网线从四周汇聚，交织成上下眼睑 + 瞳孔的「眼」；瞳孔左右扫视，寓意「一直在观测、持续鉴真」。

### 实现
- `TruthNetMark`（SVG，`64×40` ≈ 1.6:1）：上下眼睑弧线 + 8 条瞳孔→眼睑辐射线（网） + 8 个数据点节点 + 扫视瞳孔，全程 `currentColor`。
- **瞳孔 = T/N 字母融合字形**（2026-08 按用户要求重构）：瞳环（半透明圆）中央以镜面对称笔画同时读出 T 与 N（横竖笔画共用），科技几何感、**去神秘学**——不做孤立三角/射线光环等共济会式构图。
- 常驻态（header logo，`h-5 w-8 text-primary`）：仅瞳孔 `.tn-scan` 持续扫视（`translateX` 往返，`transform-box: fill-box`）。
- 开场态（`IntroLogo` overlay，`.tn-intro`）：网线 `.tn-line` 逐条描出（`stroke-dashoffset`）→ 节点 `.tn-node` 点亮 → 瞳孔 `.tn-scan` 浮现后扫视 → 整体 `scale(0.14) + opacity-0` 缩小淡出，露出主界面常驻小眼。

### 动效约束
- 所有动画遵守 `--reduce-motion` 全局降级（`[style*="--reduce-motion: reduce"] *` 已禁用动画）。
- 开场 overlay 用 `data-no-print` 排除打印；`z-[100]` 覆盖全屏，约 3s 后自行卸载。

## 企业画像页（公司财报反欺诈画像）

> 2026-08 升级：布局与特效参考「Sentra 单页」的 hero + bento + reveal 语言；颜色与内容一律遵循主题变量，不硬编码色值。

### 布局
- 顶部 hero 头部：eyebrow（mono、字距 `0.3em`）+ 大字号公司名（`text-3xl/4xl`）+ 风险徽章 + wind_code；右侧 `bg-primary/10 + blur-3xl` 光晕；导出/生成报告按钮内置 hero 内。
- 风险概览指标 bento 网格（`grid-cols-2 sm:grid-cols-4`）：综合风险等级横跨 2 列（`from-primary/15 to-primary/5` 渐变主卡），触发规则数/舆情事件数/数据截止日/数据模块各 1 格，覆盖状态横跨 2 列，移动端与桌面端每行均铺满。

### 动效
- 复用 `Reveal`：hero 整体 + 6 个区块标题（核心结论/影响与建议/财务异常/股权穿透图/舆情时间线/证据引用）滚动进入时 `translate-y-8 opacity-0 → translate-y-0 opacity-100` 淡入上浮。

### 配色
- 全程语义化（`bg-card` / `border-border` / `text-foreground` / `text-muted-foreground` / `text-primary`），光晕与渐变用 `bg-primary/*` 透明度，随明暗主题自动切换。

### 素材（公开素材库，Unsplash 免费可商用，已下载至 `public/assets/`）
- `hero-finance.jpg`（深色 K 线蜡烛图）：hero 头部底图，`opacity-10` + 深色渐变遮罩，浅色主题下同样保留（低透明度不干扰）。
- `hero-abstract.jpg`（发光电路板）：风险概览 bento 区底图，`opacity-5`，只做质感不做信息。
- `hero-globe.jpg`（太空地球夜景）：舆情时间线区底图，`opacity-10` + 自下而上渐隐，隐喻"全局监控"。

### 金融级微交互（ui-ux-pro-max 情报落地）
- 数字滚动（`CountUpNumber`）：hero 综合评分（0→score，800ms）+ bento 指标卡（规则数/舆情数/时间线事件数），`requestAnimationFrame` + ease-out，`prefers-reduced-motion` 时直接显示终值。
- 指标卡悬浮：`tn-lift`（-2px 上浮 + shadow-md）+ `tn-card-sheen`（对角高光扫过）。
- 全站噪点：`tn-noise`（SVG feTurbulence，`opacity-[0.035]`，`pointer-events-none`），压住 AI 味的"塑料平涂感"。

## 市场脉搏地球（对话主界面欢迎区，2026-08 新增）

> 用户构想（2026-08-25 修订）：「半圆舷窗正好包裹上半球，其余保持页面网格底板；当日全量存量 + 每 10 分钟更新；国家聚合强度——某区域新闻越多，那个国家的点就点亮得越狠」。

### 数据链路
- 后端 `/api/v1/market-pulse`：聚合 6 个免费公开 RSS 源（CNBC 要闻/MarketWatch 头条/WSJ 市场/华尔街见闻等），覆盖 US/CN/ASIA/EU 四区域；每条含 `lat/lng`（国家锚点 + 确定性抖动防重叠）与 `severity`（标题关键词推断：critical > warning > info，中英双语词表）；600s（10 分钟）进程内缓存，与前端轮询同节奏；单源失败自动降级不计入 items。
- **当日存量模式**（评委演示场景：屏幕不能是空的）：不再只留 10 分钟增量，`published_at` 当天（本地时区）的新闻全部保留，滚动累积到 24 点重置；演示时永远有几十条存量点亮各大洲。
- **国家热点聚合 `clusters`**：按国家分组（美/中/港/日/英/欧盟等约 20 个锚点），`count` 条数 → `intensity ∈ [0.3, 1]`（log 归一 + 严重度加权：critical ×3、warning ×1.5）；某国多条新闻 → 该国亮点半径/高度/透明度按 intensity 放大——「A 股十条 → 中国区点亮得狠」。
- 前端 `MarketPulseGlobe`：10 分钟轮询（`truthnetFetch` 直连，与后端缓存天然对齐）。

### 视觉与交互
- **半圆舷窗**（2026-08-25 定稿）：不再是方形卡片——`aspect-[2/1] rounded-t-full` 拱顶窗口（宽 ≤660px），球心锚定半圆圆心（正方形画布 `top-0` 贴顶，下半被 overflow 裁掉），只露上半球，取景 lat 18 / lng 108 / altitude 1.05（球缘贴满拱顶两侧）；窗口外透出页面网格底板，包裹感强、不打破对话区和谐。
- **深空底色（暗色模式）**：自上而下深空渐变（`#01040a` → 品牌色调和的 `#020a14` → `#041527`，经 `color-mix` 从 `--color-primary` 派生，主题换色时氛围随之变调）；外圈 `ring-1 ring-white/10` 薄壳 + 顶部品牌色外发光。
- **白昼底色（亮色模式，2026-08-25 定稿）**：不再把深空窗硬塞进浅色页面（夜景球在白底上"黑乎乎一团"）——浅色天穹渐变（`#f3f7fc` → `#e3edf8` → `#cfe0f2`，同样经 `color-mix` 派生品牌色调），外圈 `ring-black/[0.08]`，暗角渐晕改为提白；主题切换由 MutationObserver 监听 `documentElement.dark` 实时跟随。
- **贴图随主题昼夜切换**：暗色 = `earth-night.jpg`（城市灯光，电影感）；亮色 = `earth-blue-marble.jpg`（蓝色大理石——科技圈经典风格，深蓝海洋 + 白云，非直白卫星图，满足"科技感"且在浅底上不脏）。贴图一律本地资产 `public/assets/globe/`（禁 unpkg CDN——国内不可达且曾因版本路径 404 导致地球隐形）。
- **眼睛已移除**（2026-08-25 用户决策）：地球上方不再悬浮 TruthNetMark——担心"眼睛俯瞰"引发不好的联想说法；品牌眼睛仅保留在 AppHeader 与开场 overlay。
- **氛围层**（z 序：星空 0 < 地球 1 < 暗角 2）：确定性种子星空 48 颗（`.tn-star` 交错闪烁，reduce-motion 关闭）**仅暗色模式渲染**，亮色模式不撒星（浅底上无意义）；`radial-gradient` 暗角渐晕（暗色压暗 / 亮色提白）让边缘融入窗体。
- 大气辉光 `#7fb0e8` / altitude 0.25（柔和大圈，模拟大气散射）。
- 区块标题：`MARKET PULSE · 全球舆情脉搏` mono eyebrow + `LIVE`（呼吸绿点），让组件在欢迎区可识别。
- **国家亮点**（clusters 驱动，一国家一点）：颜色按该国 `top_severity` 三色分级（info 蓝 `#5da2ff` / warning 琥珀 `#f5b042` / critical 红 `#ff5d5d`，语义风险色专用于数据标注的既有例外）；点半径 `0.3 + intensity × 0.62`、高度 `0.16 + intensity × 0.5`、透明度 `0.55 + intensity × 0.45`；warning/critical 或 intensity ≥ 0.9 的国家附加扩散涟漪环（上限 6，`ringColor` 插值随扩散渐隐至 0）。
- 交互：点击国家亮点弹出该国舆情列表（Dialog，标题可跳原文、来源/时间/级别徽章）；hover 显示国家/条数/强度 tooltip。
- 状态条：当日总量 + Top4 热点国家（色点 + 计数）+ 更新节奏（10 分钟）+ 最近更新时间 + 失效源提示，`font-mono text-[10px]`。

### 构建约束
- three/globe 生态体积大，已按 `manualChunks` 三段拆包：`vendor-three`（three 核心）/ `vendor-three-ext`（examples）/ `vendor-globe`（globe.gl 系列），全部低于 1300kB 告警线；仅被懒加载页面引用，不进首屏主包。