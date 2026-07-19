# 织网鉴真 · 财报反欺诈智能问答系统

## 综合设计方案 V12（产品、前端、Agent、数据与工程统一基线）

> 第五届中国研究生金融科技创新大赛 · 东吴证券赛题
> 文档日期：2026-07-15
> 文档状态：接口冻结前的统一设计基线
> 合并来源：`design-v9`、`前端设计_v3`、`TruthNet_design_v10_reviewed`
> 适用对象：产品组、前端组、后端组、数据组、测试与答辩材料编写人员

---

### 快速导航（按角色 · 30 秒定位）

> **不要全读。** 找到你的角色，只读对应章节。

| 角色                | 必读章节                                                                       | 页数参考 |
| ------------------- | ------------------------------------------------------------------------------ | :------: |
| **前端组**    | §1 产品概述 → §4-5 前端设计 → §11-12 REST/WS 契约 → 附录A 类型           | ~200 行 |
| **后端组**    | §1 产品概述 → §6-9 架构+Agent+证据 → §10 数据架构 → §11-13 REST/WS/性能 | ~350 行 |
| **数据组**    | §1 产品概述 → §1.4 数据全景 → §8.1 规则引擎 → §10 数据架构              | ~150 行 |
| **全组**      | §1-3 产品概述+创新点+功能清单                                                 |  ~80 行  |
| **队长/答辩** | §2 核心创新 + §26 最终结论                                                   |  ~20 行  |

> 各阶段具体任务、交付物、验收标准见 [开发实践手册.md](../../开发实践手册.md)。

---

## 0. 文档目标与决策摘要

### 0.1 文档目标

本文不是增量修改清单，而是 TruthNet 当前阶段的**完整设计基线**。它覆盖：

1. 产品定位、竞赛要求、用户场景与功能边界；
2. 对话主页、企业画像页、跨公司对比页和报告状态页的完整界面设计；
3. 前端组件、状态管理、响应式、无障碍和实时交互设计；
4. FastAPI、LangGraph、Pydantic、MySQL、Neo4j、ChromaDB 和 LLM Provider 的整体架构；
5. Agent 编排、记忆、财务勾稽、股权穿透、舆情事件、证据生成和风险评分；
6. REST、WebSocket、错误、部分成功、版本、幂等和兼容迁移契约；
7. 数据库、图谱、向量索引、数据血缘、修订版本和质量控制；
8. 安全、AI 风险治理、可观测性、测试、CI、环境、部署和开发计划。

### 0.2 核心技术与工程决策

| 领域 | 最终决策 | 定位 |
| Python | Python 3.11 | 现有环境继续使用 |
| 环境管理 | conda 主环境，venv fallback | 保持跨平台和成员一致性 |
| 依赖管理 | 根目录唯一 `requirements.txt`，全部 `==` 固定 | 防止多人协作依赖漂移 |
| Web 后端 | FastAPI | REST、WebSocket、OpenAPI 和依赖注入入口 |
| Agent 编排 | LangGraph StateGraph | 条件路由、并行节点、持久化和可恢复执行 |
| 数据契约 | Pydantic V2 | API、Agent State、Port 和 Adapter 的统一类型边界 |
| 正式结构化存储 | MySQL 8.4 | 完整数据、多用户查询和正式演示 |
| 正式图存储 | Neo4j | 持久化股权图、多跳穿透和图查询 |
| 向量存储 | ChromaDB | 公告、研报和证据文本的语义检索 |
| LLM | Provider Adapter；DeepSeek 为主、Qwen/Mock 备选 | 不将业务代码绑定单一模型 |
| 前端 | React + Vite + TypeScript | 组件化、类型安全和快速开发 |
| UI | shadcn/ui + Tailwind CSS | 可定制、轻量和设计一致性 |
| 图表 | Recharts | 财务趋势、行业分位和比较图 |
| 图谱 | D3.js；必要时封装为独立 Canvas/SVG 层 | 股权穿透交互与风险热力图 |
| 测试与质量 | pytest、Ruff、pre-commit、CI | 作为 PR 合并门禁 |
| 编码与路径 | UTF-8、LF、`pathlib.Path`、禁止硬编码盘符 | Windows/Linux/macOS 一致 |
| Git | 成员分支 → PR → main；专人审核合并 | 简单协作、main 受保护 |
| 改造策略 | 保留原仓库工程基线，渐进式重构 | 不全面推倒重建 |

### 0.3 架构设计依据

本方案吸收以下公开标准和优秀工程方法：

- 采用 Ports and Adapters，将核心业务与数据库、图引擎、模型和 UI 解耦；
- REST 契约采用 OpenAPI 3.1.x，与 FastAPI 当前自动生成能力一致；
- WebSocket 事件采用 AsyncAPI 风格的机器可读契约；
- HTTP 错误采用 RFC 9457 Problem Details；
- LangGraph 使用 thread/checkpointer 保存短期会话状态和中间执行快照；
- 证据血缘参考 W3C PROV 的 Entity、Activity、Agent 和派生关系思想；
- AI 风险管理参考 NIST AI RMF 的 Govern、Map、Measure、Manage；
- API 安全基线覆盖 OWASP API Security Top 10；
- 前端可访问性以 WCAG 2.2 AA 为目标；
- 日志、指标和链路追踪按 OpenTelemetry 的统一上下文思想设计。

### 0.4 金融问答与反欺诈研究映射

本方案还吸收金融智能问答与可解释分析研究中的以下设计思想：

| 研究/项目 | 可借鉴设计 | TruthNet 落地 |
| FinQA | 将复杂金融数值问题表示为可执行推理程序，并保留专家标注的推理过程 | 财务数值由规则程序计算，答案引用规则、输入字段和中间结果 |
| TAT-QA | 同时处理表格与文本，并覆盖加减乘除、比较、排序和组合推理 | 三表结构化数据与公告/研报文本通过统一 Evidence 模型汇合 |
| DocFinQA | 长文档上下文下的金融问答与证据定位 | 财报、公告和研报按来源、页码/片段、哈希和版本检索 |
| FinRobot | 分层金融 Agent 平台、专业 Agent 与多源模型解耦 | Application、Agent、DataOps/Adapter 和 Provider 分层 |
| 可解释财务造假知识图谱研究 | 使用财务变量关系和知识图谱增强风险解释 | 财务规则、股权图和 Claim–Evidence 联合展示，不以黑盒分数替代证据 |
| Temporal Provenance | 将时间作为数据和派生关系的重要维度 | 所有财务、图关系、事件、规则和报告均包含 `as_of`、有效期和版本 |

这些研究只作为架构与评测思路参考；TruthNet 当前 MVP 仍采用可复现规则、图查询和检索增强，而不在缺乏标注数据时直接引入复杂 GNN 或端到端黑盒造假分类器。

---

# 1. 产品概述

## 1.1 产品定位

**产品名称**：织网鉴真 · 财报反欺诈智能问答系统

**产品定位**：面向个人投资者的财报反欺诈智能问答助手。用户通过自然语言询问上市公司的财务异常、股权关系、关联方风险、公告舆情和行业位置，系统以确定性计算与 Agentic AI 协同方式完成分析，返回带数据口径、时间范围、证据链、风险等级和不确定性说明的结果。

**核心表达原则**：

- 系统识别的是“异常信号”和“风险模式”，不是代替监管、审计或司法机构作出造假认定；
- 数值结论来自规则引擎、图算法和统计程序；
- LLM 负责意图理解、信息组织和自然语言解释；
- 每项事实性结论必须能够回到结构化数据或原始文本证据。

## 1.2 目标用户

| 用户类型 | 主要需求 | 产品响应 |
| 个人投资者 | 快速判断公司是否存在值得关注的风险 | 自然语言诊断、风险摘要和证据链 |
| 财经爱好者 | 理解财报指标和异常逻辑 | 规则解释、趋势图、行业分位 |
| 金融专业学生 | 学习股权穿透和财务勾稽 | 可视化路径、公式来源和交叉验证 |
| 竞赛评审人员 | 验证系统完整性、创新性和可解释性 | 完整演示闭环、可复现结果和性能指标 |
| 项目研究人员 | 进行公司风险初筛和案例研究 | 企业画像、跨公司对比和报告导出 |

## 1.3 赛题痛点与系统映射

| 赛题痛点           | 问题表现                             | 系统能力                                   | 前端体现                       |
| ------------------ | ------------------------------------ | ------------------------------------------ | ------------------------------ |
| 长对话记忆遗忘     | 超过 10 轮后主体、指标和时间范围丢失 | 记忆节点、服务端会话、LangGraph checkpoint | 会话列表、上下文恢复、主体提示 |
| 工具路由困难       | 不知道何时查询财务、图谱或舆情       | Planner + 条件编排 + 结果级交叉验证        | 实时展示模块进度               |
| 隐性资本关系穿透难 | 间接控股、交叉持股、资管计划链路复杂 | Neo4j 多跳路径、权重连乘、实体对齐         | 可拖拽股权穿透图和路径高亮     |
| 财报粉饰隐蔽       | 单表正常但跨科目矛盾                 | 7 条财务勾稽规则、行业分位、历史趋势       | 规则卡、折线图、风险等级       |
| 舆情碎片化         | 公告和研报缺乏事件脉络               | 事件聚类、时间线和评级拐点                 | 事件时间线和筛选器             |
| 分析缺乏证据       | 回答不可核验                         | Claim–Evidence 模型和数据血缘             | 证据折叠、来源跳转、字段定位   |

## 1.4 数据全景

| 数据集     |                                                    当前规模 | 主要用途                       | 关键限制                        |
| ---------- | ----------------------------------------------------------: | ------------------------------ | ------------------------------- |
| 问答测试集 |                  35 会话、1,410 问；77 深度题、1,333 简单题 | 多轮和复杂 Query 评测          | 无固定标准答案                  |
| 股东数据   |                                    6,161 只股票、约 646K 条 | 股权穿透、一致行动人、持股变化 | 名称实体对齐存在噪声            |
| 公司公告   |                               2,585 只股票、7,311 条、33 类 | 舆情、监管、风险事件           | 标题粒度有限，部分需补正文      |
| 三表 CSV   |                            约 6,700 只股票、3.5 年、10 季度 | 财务规则和趋势                 | 当前主要为母公司口径            |
| 研报       |                                                   55,214 篇 | RAG、评级拐点、行业分类        | `rating_change` 约 87.5% 覆盖 |
| 行业分类   | 三表股票 45.6% 可匹配到研报行业分类（研报字段覆盖率 99.3%） | 行业分位和同行比较             | 需通过 akshare 补全至 ≥90%     |

**数据口径约束**：三表当前主要为 `statement_type=408006000` 的母公司报表口径。商誉、固定资产、在建工程等字段覆盖率不足时，不进入依赖这些字段的规则；任何“不适用”必须与“未触发”分开显示。

## 1.5 评分方式

赛方确认的评测思路：

```text
总分 = 0.5 × 多轮 QA 平均准确率 + 0.5 × 最终复杂 Query 准确率
单项准确率 = 0.6 × 结果正确 + 0.4 × 语义相似
```

产品设计由此强调：

1. 简单查询必须直接、精确，不应为了展示 Agent 能力强制调用所有模块；
2. 深度 Query 必须形成跨模块推理链；
3. 文本表达需要清楚、完整、与问题语义一致；
4. 最终答案必须包含可验证的结构化结果，不能只优化语言相似度。

## 1.6 外部数据许可与来源原则

| 数据类型 | 使用状态 | 来源原则 |
| 行情与基本信息 | 允许 | akshare 等公开渠道；保存抓取时间和来源 |
| 财报附注、审计报告、问询函 | 允许 | 巨潮资讯网等公开渠道；保存文档哈希 |
| 行业分类 | 部分补全 | 研报字段优先，公开来源补全 |
| 新闻和自媒体 | 谨慎使用 | 只能作为线索，不得替代监管公告事实 |

## 1.7 产品负责与不负责

### 系统负责

- 基于当前数据识别异常信号；
- 给出规则、图谱、事件和行业对标证据；
- 展示时间范围、数据版本和缺失情况；
- 支持多轮追问、主体消歧和报告生成；
- 在模块超时或数据不足时返回部分结果；
- 区分确定事实、算法判断、LLM 解释和建议性追问。

### 系统不负责

- 提供具体买卖指令；
- 将风险信号直接认定为财务造假；
- 在无数据来源时生成具体数值或关系；
- 用 LLM 替代财务计算、持股连乘和行业统计；
- 把事件时间先后默认标记为因果；
- 对不在数据覆盖范围内的公司伪造完整画像。

---

# 2. 核心价值与创新设计

## 2.1 多维度交叉验证

财务、股权和舆情三类信号既能独立回答，也能在综合诊断中相互验证：

```text
财务异常
  ├─ 核查同期大股东减持、质押、冻结或控制链变化
  └─ 核查同期负面公告、问询、处罚和评级变化

股权异常
  ├─ 核查关联公司或目标公司的现金流、应收和其他应收款
  └─ 核查控制人、关联方和担保事件

舆情异常
  ├─ 核查同期财务指标是否出现可量化印证
  └─ 核查事件影响节点和控制关系是否变化
```

实现上不重复执行已完成的模块，而是在三类模块返回后进入 `CrossValidate` 节点，使用已有结构化结果执行轻量规则和证据组合。

## 2.2 造假模式识别：类型与阶段

多条规则同时触发时，将信号组合与版本化模式库进行匹配，例如：

```text
应收增速远高于营收
+ 经营现金流持续弱于利润
+ 毛利率或收入增长显著偏离行业
→ 疑似收入确认或虚增收入类风险模式
```

模式输出必须包含：

- 模式名称；
- 匹配规则；
- 支撑证据；
- 置信度计算方法；
- 当前阶段；
- 可能的替代解释；
- “风险模式不等于监管认定”的提示。

阶段模型建议：

```text
early_signal      早期信号
accumulating      信号积累
high_risk         高风险期
regulatory_action 监管介入
confirmed_case    已有权威事实确认
unknown           数据不足
```

## 2.3 行业智能对标

每个规则尽量同时展示：

1. 当期绝对值；
2. 公司历史趋势；
3. 行业中位数、P25、P75；
4. 目标公司的行业百分位；
5. 有效同行样本数；
6. 样本不足说明；
7. 相似历史案例，但不得将相似性直接表述为同类造假。

## 2.4 多源风险评分

风险评分聚合但不掩盖分项：

```text
综合风险
  = 财务规则分
  + 股权关系风险分
  + 公告与监管事件分
  + 研报评级变化分
  + 数据质量惩罚/不确定性调整
```

综合风险使用五级加未知：

```text
red / orange / yellow / blue / green / unknown
```

所有阈值在 `rule_definitions` 或 `risk_policy` 中版本化，不把“触发 3 条就必定红色”等演示逻辑硬编码为永久标准。

## 2.5 企业画像与风险热力图

企业画像是公司的统一风险入口：基本信息、财务规则、股权图、关联方风险、事件时间线、行业对标和证据均围绕同一个 `CompanyRef` 和 `as_of` 快照组织。

图谱节点颜色表示风险等级，但颜色必须同时伴随文字或图标，避免仅靠颜色表达。

## 2.6 结构化问答与递进式交互

回答分为四层：

1. 一句话结论；
2. 三类核心信号摘要；
3. 可展开的证据和图表；
4. 贴合当前结论的追问建议。

追问建议不是固定模板，而由当前缺失证据和已触发规则生成，例如：

- “查看应收账款近 8 季度趋势”；
- “查看实控人控制的其他上市公司”；
- “对比同行业应收增速分位”；
- “查看该事件对应公告原文”。

---

# 3. 功能范围与优先级

| 编号 | 功能                 | 优先级 | 交付标准                               |
| ---- | -------------------- | :----: | -------------------------------------- |
| F1   | 自然语言反欺诈问答   |   P0   | 支持简单查询和综合诊断；流式输出       |
| F2   | 多轮会话记忆         |   P0   | 10 轮以上主体、指标和时间引用可恢复    |
| F3   | 公司主体消歧         |   P0   | 名称或代码模糊搜索、候选确认           |
| F4   | 股权穿透             |   P0   | 支持 3 层以上、最大深度 10、路径与权重 |
| F5   | 财务异常检测         |   P0   | 7 条规则、适用性、趋势、行业分位       |
| F6   | 舆情事件溯源         |   P0   | 事件簇、时间线、关系类型、评级变化     |
| F7   | 企业画像页           |   P0   | 摘要首屏 + 子资源按需加载              |
| F8   | 证据链               |   P0   | Claim 至少挂载一个 Evidence            |
| F9   | 数据与规则版本       |   P0   | 每次结果含`as_of`、数据和规则版本    |
| F10  | 模块降级和部分成功   |   P0   | 单模块失败不阻塞已有结果               |
| F11  | 跨公司比较           |   P1   | 2–5 家公司，指标表、分位图和风险对比  |
| F12  | WebSocket 重连与取消 |   P1   | 序号恢复、取消轮次、幂等               |
| F13  | PDF 报告任务         |   P1   | 创建任务、查询状态、下载文件           |
| F14  | 响应式和无障碍       |   P1   | 桌面、平板、手机；WCAG 2.2 AA 目标     |
| F15  | 行情查询             |   P2   | 作为辅助信息，不参与核心造假评分       |
| F16  | 暗色模式             |   P2   | 保证风险颜色和对比度一致               |

---

# 4. 信息架构与页面路由

## 4.1 页面结构

```text
织网鉴真
├── 对话主页 (/)
│   ├── 会话侧边栏
│   ├── 对话与流式分析区
│   └── 分析摘要面板
│
├── 企业画像页 (/company/:code)
│   ├── 公司基本信息与风险标签
│   ├── 财务异常检测
│   ├── 股权穿透图
│   ├── 关联方风险
│   ├── 舆情事件时间线
│   ├── 证据引用
│   └── 行业对比入口
│
├── 跨公司对比页 (/compare?codes=...)
│   ├── 公司选择器
│   ├── 风险等级对比
│   ├── 指标对比表
│   ├── 行业分位图
│   └── 证据差异摘要
│
└── 报告任务页 (/reports/:reportId)
    ├── 任务状态
    ├── 生成阶段
    ├── 警告与缺失模块
    └── 下载或重新生成
```

## 4.2 路由设计

| 路由                   | 页面         | 优先级 | 数据策略                     |
| ---------------------- | ------------ | :----: | ---------------------------- |
| `/`                  | 对话主页     |   P0   | WebSocket 主通道 + 会话 REST |
| `/company/:code`     | 企业画像页   |   P0   | 摘要接口首屏，子资源并行加载 |
| `/compare?codes=...` | 跨公司对比页 |   P1   | 2–5 家公司按需请求          |
| `/reports/:reportId` | 报告任务页   |   P1   | 轮询或事件更新任务状态       |
| `/settings`          | 本地展示设置 |   P2   | 主题、动画、默认回溯范围     |

---

# 5. 前端详细设计

## 5.1 对话主页

### 5.1.1 桌面端整体预览

```text
┌──────────────────────────────────────────────────────────────────────┐
│  织网鉴真 · 财报反欺诈智能问答                  数据截至 2026-06-30 │
├────────────┬──────────────────────────────────────┬──────────────────┤
│            │                                      │                  │
│ 会话侧边栏  │               对话区                 │    分析面板      │
│  240px     │              flex-1                  │  360–440px       │
│            │                                      │                  │
│ [+新建会话] │ [系统欢迎消息]                       │ [风险等级]       │
│            │                                      │ 🔴 红色 · 高危   │
│ ● 康美分析  │ 用户：康美药业的财务数据有无异常？    │                  │
│   3条异常   │                                      │ [模块状态]       │
│   12:30    │ 系统：正在分析财务报表……              │ 财务 ✓ 股权 ✓    │
│            │ 系统：正在穿透股权关系……              │ 舆情 ⚠ 部分      │
│ ○ 乐视分析  │                                      │                  │
│   5条异常   │ 康美药业存在以下值得关注的信号……      │ [规则触发清单]   │
│   昨天      │                                      │ R1 触发 🔴       │
│            │ 1. 应收增速显著高于营收……             │ R2 触发 🔴       │
│            │ 2. 经营现金流与利润背离……             │ R3 触发 🟠       │
│            │                                      │ R4 未触发        │
│            │ [查看完整画像 →] [对比同行 →]         │                  │
│            │                                      │ [事件时间线]     │
│            │ ┌──────────────────────────────┐     │ [证据链]        │
│            │ │ 请输入你的问题……       [发送]│     │                  │
│            │ └──────────────────────────────┘     │                  │
├────────────┴──────────────────────────────────────┴──────────────────┤
│  本系统用于风险研究与信息辅助，不构成投资建议。                     │
└──────────────────────────────────────────────────────────────────────┘
```

保留原三栏布局思想：会话栏固定宽度、对话区自适应、分析面板为摘要。完整图谱、详细趋势和全部证据不塞入侧面板。

### 5.1.2 会话侧边栏

| 元素     | 行为                                       |
| -------- | ------------------------------------------ |
| 新建会话 | 创建空会话并生成服务端`session_id`       |
| 会话名称 | 默认取首轮问题前 15 字；允许手动重命名     |
| 会话摘要 | 显示目标公司、风险等级、异常数量、更新时间 |
| 活跃状态 | 高亮当前会话，设置`aria-current`         |
| 删除会话 | 二次确认；服务端软删除，支持短时间撤销     |
| 会话切换 | 立即恢复本地缓存，同时从服务端校验最新状态 |
| 搜索会话 | P1；按公司、标题和消息内容过滤             |

会话列表不把红色 Badge 当作唯一信息，必须同时显示“3 条异常”等文本。

### 5.1.3 对话区

**消息类型**：

| 类型           | 展示                                                     |
| -------------- | -------------------------------------------------------- |
| 用户消息       | 右对齐气泡；保留原问题文本                               |
| Assistant 文本 | 左对齐 Markdown；支持列表、表格和引用                    |
| 模块进度       | 小型步骤条，不展示模型内部思维过程，只展示可公开执行状态 |
| 候选公司       | 可键盘选择的候选卡片                                     |
| 结构化卡片     | 规则摘要、图谱入口、时间线摘要、证据摘要                 |
| 警告           | 数据不足、超时、降级和时间口径提示                       |
| 追问建议       | 可点击发送；允许编辑后再发                               |

**标准对话流程**：

```text
用户输入
→ turn.accepted
→ 主体识别/候选确认
→ module.started × N
→ answer.delta（可与结构化结果交错）
→ artifact.upsert × N
→ turn.completed / turn.failed
```

**输入框规则**：

- Enter 发送，Shift+Enter 换行；
- 空输入不可发送；
- 执行中允许编辑下一条，但默认不并发提交同一会话；
- 提供“停止生成”按钮，对应 `turn.cancel`；
- 网络断开时保留草稿；
- 显示当前主体和 `as_of`，减少隐式上下文误解。

### 5.1.4 分析面板

面板从上到下展示：

1. **综合风险等级**：颜色、图标、文字和一句话结论；
2. **数据快照**：数据截至日期、规则版本、模块完整度；
3. **规则触发清单**：7 条规则的触发、未触发、不适用、数据不足；
4. **关键事件时间线**：3–5 个高相关事件；
5. **证据链摘要**：按财务、股权、舆情分组；
6. **警告与缺失模块**：partial 状态必须可见。

面板状态：

```text
empty
loading
partial
success
unavailable
failed
```

点击规则卡后：

- 对话区滚动到对应解释；
- 企业画像页链接带上锚点；
- 若图谱已加载，高亮关联节点；
- 证据区筛选到对应 `evidence_id`。

## 5.2 企业画像页

### 5.2.1 完整页面预览

```text
┌──────────────────────────────────────────────────────────────────┐
│ ← 返回对话  康美药业（600518.SH）· 中药 · 🔴 红色               │
│             数据截至 2026-06-30  规则版本 finance-rules-1.0.0  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ┌── 基本信息 ─────────────┐  ┌── 风险标签 ─────────────────┐   │
│ │ 上市：2001-03-19        │  │ 🔴 负面诚信 → 财务风险      │   │
│ │ 实控人：马兴田           │  │ 🟠 监管处罚 → 行政处罚      │   │
│ │ 行业：中药               │  │ 🟡 诉讼仲裁                 │   │
│ │ 报表：母公司口径         │  │ 数据完整度：82%             │   │
│ └─────────────────────────┘  └─────────────────────────────┘   │
│                                                                  │
│ ┌── 财务异常（3/7 条触发）────────────────────────────────┐   │
│ │ R1 应收-营收背离     🔴 47.2% vs 12.1%  行业前 8%       │   │
│ │ R2 现金流-利润背离   🔴 经营现金流为负、净利润为正       │   │
│ │ R3 存贷双高          🟠 货币资金与有息负债同时较高       │   │
│ │ R4 未触发 · R5 数据不足 · R6 不适用 · R7 未触发          │   │
│ │ [查看全部规则、趋势与证据]                               │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ ┌── 股权穿透（可拖拽、缩放、筛选、导出）──────────────────┐   │
│ │                                                          │   │
│ │  马兴田(🔴) ─99.7%→ 康美实业(🟠) ─30.1%→ 康美药业(🔴)   │   │
│ │                         │                                │   │
│ │                         └────────→ 关联公司 C(🟡)        │   │
│ │                                                          │   │
│ │ 深度：[1] [2] [3] [5]  [只看控制链] [只看高风险] [PNG] │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ ┌── 关联方风险一览 ───────────────────────────────────────┐   │
│ │ 公司        关系      异常信号          风险   数据截至   │   │
│ │ 关联公司 C  同控      R1 应收/营收背离   🟡    2026Q2    │   │
│ │ 关联公司 D  担保      负面公告密度偏高   🟠    2026Q2    │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ ┌── 舆情与监管事件时间线 ─────────────────────────────────┐   │
│ │ 2018.10  自媒体质疑财务数据                possibly_related │ │
│ │ 2018.12  收到证监会立案调查                temporal_precedes│ │
│ │ 2019.04  会计差错更正，调减货币资金 299 亿 supports        │ │
│ │ 2019.05  实施 ST                           temporal_precedes│ │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ ┌── 证据引用 ─────────────────────────────────────────────┐   │
│ │ 📋 财务证据（3）  展开 ▼                                 │   │
│ │  · 应收增速 47.2% — 资产负债表 acct_rcv，2025Q3         │   │
│ │  · 营收增速 12.1% — 利润表 oper_rev，2025Q3             │   │
│ │ 🔗 股权证据（2）  ▶                                      │   │
│ │ 📰 公告与研报（3）▶                                      │   │
│ │ ⚠ 数据缺失与适用性（1）▶                                │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ ┌── 行业对比 ─────────────────────────────────────────────┐   │
│ │ [查看康美药业与同行业公司的完整对比 →]                  │   │
│ └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2.2 基本信息与风险标签

基本信息字段：

- 股票代码、简称、交易所；
- 申万一级、二级行业；
- 上市日期；
- 实际控制人；
- 审计机构（有可靠来源时）；
- 当前报表口径；
- 数据截至日期；
- 数据完整度和质量提示。

风险标签采用三层：

```text
一级：负面诚信 / 监管处罚 / 诉讼仲裁 / 股权风险 / 财务异常
二级：财务数据问题 / 行政处罚 / 股权冻结 / 高质押等
三级：具体事件或规则结论
```

标签中“监管处罚”“立案”“判决”等词只能在权威来源明确支持时展示；算法推断使用“疑似”“风险信号”“模式匹配”。

### 5.2.3 财务异常区域

每条规则包含：

- 规则编号和名称；
- `triggered / not_triggered / not_applicable / insufficient_data`；
- 当前指标和比较对象；
- 近 4–10 期趋势；
- 行业分位和有效样本数；
- 严重等级；
- 规则版本；
- 数据质量；
- 关联 Claim 和 Evidence。

趋势图使用 Recharts，支持：

- hover 查看精确值；
- 切换季度/年度；
- 显示母公司或合并口径标签；
- 不连续数据使用断线，不做虚假插值；
- 支持导出 CSV 或复制数据表。

### 5.2.4 股权穿透图

**图形编码**：

| 节点类型 | 形状 | 示例 |
| 自然人 | 圆形 | 实际控制人、股东 |
| 非上市公司 | 圆角方形 | 控股平台、关联公司 |
| 上市公司 | 菱形或强调边框方形 | 目标公司和关联上市公司 |
| 资管计划/基金 | 六边形 | 资管、私募、信托计划 |
| 未识别实体 | 虚线轮廓 | 实体对齐不确定 |

**边类型**：持股、控制、一致行动、关联、担保等；边显示比例、有效期和来源状态。

**交互**：

- 拖拽、缩放、适配视口；
- 深度 1/2/3/5 或自定义上限；
- 只显示控制链、全部持股、关联方或高风险节点；
- 点击节点打开详情抽屉；
- 点击证据高亮节点和边；
- 点击路径锁定整条控制链；
- 导出 PNG；P2 支持导出结构化 JSON；
- 超过 50 个节点默认聚合，用户主动展开；
- 提供“列表模式”，让键盘和屏幕阅读器用户访问同一信息。

### 5.2.5 关联方风险一览

列建议：

```text
实体名称
关系类型
路径摘要
最终控制比例
财务异常数量
负面事件数量
风险等级
数据截至日期
证据数量
```

支持点击一行后在图中聚焦对应节点。

### 5.2.6 舆情时间线

事件按时间排序，支持正面、负面、中性、监管、诉讼、股权、评级分类。关系只使用以下受约束枚举：

```text
temporal_precedes
same_event_cluster
supports
contradicts
possibly_related
explicitly_caused_by
```

只有公告、监管文件或司法材料明确说明因果时，才使用 `explicitly_caused_by`。

### 5.2.7 证据区

每条证据展示：

- Claim 文本；
- 来源标题和来源类型；
- 表名、字段、报告期或文档页码/文本片段；
- 数据版本和检索时间；
- 是否为原始数据、派生计算或 LLM 摘要；
- 打开原文、复制引用、查看计算过程。

## 5.3 跨公司对比页

### 5.3.1 页面预览

```text
┌────────────────────────────────────────────────────────────────┐
│ ← 返回   跨公司对比：康美药业 vs 云南白药 vs 片仔癀           │
│          同行业：中药 · 数据截至 2026-06-30                   │
├────────────────────────────────────────────────────────────────┤
│ [添加公司] [移除] [统一报告期▼] [导出对比]                    │
│                                                                │
│ ┌── 风险等级对比 ─────────────────────────────────────────┐   │
│ │ 康美药业 🔴 高危   云南白药 🟢 正常   片仔癀 🟢 正常     │   │
│ │ 完整度 82%          完整度 91%          完整度 89%       │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                │
│ ┌── 核心指标对比表 ───────────────────────────────────────┐   │
│ │ 指标             康美药业       云南白药       片仔癀     │   │
│ │ 应收增速          47.2%          8.3%          12.1%      │   │
│ │ 营收增速          12.1%          10.5%         15.3%      │   │
│ │ 经营现金流        -2.3 亿        15.2 亿       8.7 亿     │   │
│ │ 触发规则数        3/7            0/7           1/7        │   │
│ │ 负面事件数        12             2             1          │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                │
│ ┌── 行业分位对比 ─────────────────────────────────────────┐   │
│ │ [雷达图 / 平行坐标 / 分位条，可切换]                    │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                │
│ ┌── 关键差异与证据 ───────────────────────────────────────┐   │
│ │ · 康美药业应收增速处于行业第 92 百分位                  │   │
│ │ · 其他两家公司同口径下未触发 R1                         │   │
│ │ [展开计算和证据]                                         │   │
│ └───────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### 5.3.2 对比规则

- 默认最多比较 5 家公司；
- 比较前统一报表口径、报告期和单位；
- 缺失值显示“无数据”，不填 0；
- 行业不同的公司必须给出明显提示；
- 公司数据截至日期不同，应显示差异；
- 雷达图只用于归一化指标，原始数值仍在表格中展示；
- 横向滚动时固定指标列和公司表头。

## 5.4 报告任务页

```text
┌──────────────────────────────────────────────────────────────┐
│  康美药业风险分析报告 · rpt_01                               │
├──────────────────────────────────────────────────────────────┤
│ 状态：生成中  65%                                            │
│                                                              │
│ ✓ 数据快照                                                   │
│ ✓ 财务规则计算                                               │
│ ✓ 股权图渲染                                                 │
│ ⚠ 舆情模块部分数据缺失                                       │
│ … PDF 排版                                                   │
│                                                              │
│ [取消任务] [返回画像]                                        │
└──────────────────────────────────────────────────────────────┘
```

完成后显示：下载 PDF、查看生成参数、警告、数据版本和重新生成。

## 5.5 响应式设计

| 断点         | 布局                                         |
| ------------ | -------------------------------------------- |
| ≥1920px     | 三栏；侧栏 240px；面板约 420px               |
| 1200–1919px | 三栏；面板 36–40%，可折叠                   |
| 768–1199px  | 会话栏 + 对话区；分析面板为右侧抽屉          |
| <768px       | 单栏；会话栏为顶部抽屉；分析面板为底部 Sheet |

### 平板预览

```text
┌──────────────────────────────────────────────┐
│ [☰ 会话] 织网鉴真          [分析面板 3]     │
├──────────────────────────────────────────────┤
│                                              │
│              对话与流式结果                  │
│                                              │
│                                              │
├──────────────────────────────────────────────┤
│ 输入问题……                         [发送]     │
└──────────────────────────────────────────────┘
```

### 手机预览

```text
┌────────────────────────────┐
│ ☰ 织网鉴真       风险：红  │
├────────────────────────────┤
│ 用户：康美有风险吗？       │
│                            │
│ 系统：正在分析……           │
│ 康美药业存在以下信号……     │
│                            │
│ [查看分析摘要]             │
│ [查看完整画像]             │
├────────────────────────────┤
│ 输入问题……          [发送] │
└────────────────────────────┘
```

## 5.6 组件规范

### 5.6.1 基础组件

| 组件                  | 用途                               |
| --------------------- | ---------------------------------- |
| Button                | 主操作、次操作、危险操作、链接操作 |
| Badge                 | 风险等级、异常数、模块状态         |
| Card                  | 规则、公司、候选主体和摘要容器     |
| Collapsible/Accordion | 证据和规则明细                     |
| ScrollArea            | 会话和长列表                       |
| Dialog/AlertDialog    | 删除确认、风险说明                 |
| Sheet/Drawer          | 平板和手机分析面板                 |
| Toast                 | 短时错误和成功提示                 |
| Skeleton              | 页面和卡片加载                     |
| Progress              | 报告任务和模块执行进度             |
| Tabs                  | 图谱/列表、趋势/表格切换           |
| Tooltip               | 图标和缩写解释                     |
| Table                 | 比较、关联方和证据列表             |

### 5.6.2 业务组件

| 组件 | 建议文件 | 职责 |
| SessionSidebar | `layout/SessionSidebar.tsx` | 会话新建、切换、删除、搜索 |
| ChatInterface | `chat/ChatInterface.tsx` | 消息列表、输入和流式状态 |
| ModuleProgress | `chat/ModuleProgress.tsx` | 公开执行步骤，不展示私有思维过程 |
| CandidateSelector | `chat/CandidateSelector.tsx` | 公司候选确认 |
| AnalysisPanel | `analysis/AnalysisPanel.tsx` | 四类核心摘要 |
| RuleCard | `analysis/RuleCard.tsx` | 规则状态、趋势和证据入口 |
| CompanyProfilePage | `company/CompanyProfilePage.tsx` | 画像页编排 |
| EquityGraph | `company/EquityGraph.tsx` | D3 图谱和列表替代视图 |
| RelatedPartyTable | `company/RelatedPartyTable.tsx` | 关联方风险表 |
| RiskTimeline | `company/RiskTimeline.tsx` | 事件和关系 |
| EvidenceChain | `company/EvidenceChain.tsx` | Claim–Evidence 展示 |
| ComparePage | `compare/ComparePage.tsx` | 多公司比较 |
| ReportStatusPage | `report/ReportStatusPage.tsx` | 长任务状态和下载 |
| DataSnapshotBadge | `common/DataSnapshotBadge.tsx` | `as_of`、版本和口径 |
| PartialWarning | `common/PartialWarning.tsx` | 模块缺失和降级说明 |

## 5.7 风险视觉规范

| 等级 | 语义 | 视觉要求 |
| red | 高风险 | 红色 + 警示图标 + “高风险”文字 |
| orange | 中高风险 | 橙色 + 文字 |
| yellow | 中等关注 | 黄色 + 文字 |
| blue | 低风险/轻度关注 | 蓝色 + 文字 |
| green | 当前未见明显异常 | 绿色 + 文字 |
| unknown | 数据不足或无法评估 | 灰色 + 问号图标 + 解释 |

不能仅凭触发规则数量直接定义所有公司风险；具体阈值由版本化风险策略决定。视觉色值通过 CSS 变量配置，并验证亮色、暗色、高对比度模式。

## 5.8 无障碍设计

目标为 WCAG 2.2 AA：

- 所有输入均有可访问标签；
- 键盘能够完成会话切换、候选确认、折叠和图谱列表访问；
- 焦点样式清晰，Dialog 打开后正确管理焦点；
- 风险不只依赖颜色；
- 流式输出区域使用适当 `aria-live`，避免逐字过度播报；
- 尊重 `prefers-reduced-motion`，可关闭打字机和力导向动画；
- 图表同时提供表格或文本摘要；
- 股权图提供可搜索的列表/树视图；
- 触控目标和间距符合移动端操作需要。

## 5.9 前端状态与数据流

### 5.9.1 状态域

```ts
type SessionViewState = {
  sessionId: string
  title: string
  activeCompany?: CompanyRef
  messages: MessageView[]
  panelData: AnalysisPanelData | null
  moduleStatus: Record<ModuleName, ModuleStatus>
  connectionState: WsConnectionState
  activeTurnId?: string
  lastReceivedSequence: number
  warnings: WarningItem[]
}
```

前端保存 UI 状态、草稿、页面缓存和已接收序号；服务端保存真实会话、消息、主体、Agent checkpoint、模块结果和证据。

### 5.9.2 WebSocket Reducer

```text
turn.accepted       → 创建 activeTurn
company.candidates  → 打开候选卡片
module.started      → 模块状态 running
module.completed    → success/partial/failed
answer.delta        → 追加 Assistant 文本
artifact.upsert     → 按 artifact_id + revision 更新面板
turn.completed      → 写入最终状态和追问建议
turn.failed         → 显示错误并保留已有部分结果
heartbeat           → 更新连接健康时间
```

未知事件只记录日志并忽略，不中断客户端。

---

# 6. 系统总体架构

## 6.1 架构全景

```text
┌────────────────────────────────────────────────────────────────┐
│ React + Vite + TypeScript                                      │
│ 对话 / 企业画像 / 对比 / 报告任务                              │
└───────────────────────────┬────────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼────────────────────────────────────┐
│ FastAPI API 层                                                  │
│ Router · Pydantic DTO · Exception Handler · Auth 预留 · Trace  │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ Application 层                                                 │
│ SearchCompany · AnalyzeCompany · Compare · CreateReport         │
│ 会话 · 幂等 · 超时 · 缓存 · 部分成功 · Adapter 选择            │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ LangGraph Agent 层                                             │
│ LoadContext → ResolveEntity → Plan → Parallel Modules           │
│ → CrossValidate → BuildClaims → Generate → Validate → Persist   │
└──────────────┬──────────────────┬──────────────────┬────────────┘
               │                  │                  │
        Finance Port        Graph Port        Retrieval/LLM Port
               │                  │                  │
┌──────────────▼──────────────────▼──────────────────▼────────────┐
│ Infrastructure Adapters                                        │
│ MySQL · Neo4j · ChromaDB · LLM Providers                       │
│ akshare · 文件解析 · 报告渲染                                  │
└────────────────────────────────────────────────────────────────┘
```

## 6.2 分层职责

### API 层

- 请求解析和鉴权预留；
- Pydantic 校验；
- HTTP/WebSocket 契约；
- 错误转换；
- 不包含财务计算和数据库查询细节。

### Application 层

- 执行业务用例；
- 决定是否调用 Agent 或直接查询；
- 管理 deadline、幂等、缓存和降级；
- 组合 Port；
- 返回 Domain DTO。

### Domain 层

- 公司、财务规则、股权、事件、证据、风险和会话的核心模型；
- 规则计算和不变量；
- 不依赖 FastAPI、MySQL、Neo4j 或 SDK。

### Agent 层

- 自然语言意图和主体消歧；
- 生成执行计划；
- 编排确定性工具；
- 交叉验证结构化结果；
- 生成基于证据的回答。

### Infrastructure 层

- SQL、图、向量、外部数据、模型和报告实现；
- 实现 Application Port；
- 可切换、可测试、可降级。

## 6.3 运行环境

开发与演示统一使用 MySQL + Neo4j + ChromaDB + DeepSeek。每人本地安装对应服务。

## 6.4 推荐目录

```text
TruthNet/
  requirements.txt
  .python-version
  .env.example
  CLAUDE.md

  backend/app/
    main.py
    api/v1/
      routers/
      schemas/
      dependencies.py
      exception_handlers.py
    application/
      use_cases/
      ports/
      services/
      dto/
    domain/
      company/
      finance/
      equity/
      events/
      risk/
      evidence/
      conversation/
    agents/
      graph.py
      state.py
      reducers.py
      nodes/
    infrastructure/
      persistence/mysql/
      persistence/migrations/
      graph/neo4j/
      vector/chroma/
      llm/mock/
      llm/deepseek/
      llm/qwen/
      external/akshare/
      reporting/
    observability/
      logging.py
      tracing.py
      metrics.py
    core/
      config.py
      enums.py
      errors.py

  backend/tests/
    unit/
    contract/
    integration/
    websocket/
    regression/

  frontend/
    src/
      app/
      pages/
      components/ui/
      components/chat/
      components/analysis/
      components/company/
      components/compare/
      components/report/
      api/generated/
      api/websocket/
      state/
      types/
      mocks/

  data/
    raw/
    canonical/
    derived/
    fixtures/

  docs/
    ARCHITECTURE.md
    API_CONTRACT_V1.md
    WEBSOCKET_CONTRACT_V1.md
    DATA_CONTRACT.md
    FRONTEND_DESIGN.md
    SECURITY.md
    ADR/

  scripts/
  reports/
```

---

# 7. Agent 与 LangGraph 设计

## 7.1 节点流程

```text
LoadContext
  ↓
ResolveEntity
  ├─ 唯一命中 → Continue
  ├─ 多候选 → AwaitCompanyConfirmation
  └─ 无命中 → ReturnCoverageWarning
  ↓
PlanModules
  ├─ simple_query → 单模块或直接查询
  └─ diagnose → Finance + Equity + Events 并行
  ↓
ParallelModules
  ↓
CrossValidate
  ↓
BuildClaimsAndEvidence
  ↓
GenerateAnswer
  ↓
ValidateEvidenceAndSchema
  ↓
PersistTurn
```

## 7.2 节点职责

| 节点 | 输入 | 输出 |
| LoadContext | session_id、thread_id | 消息、当前主体、结构化记忆 |
| ResolveEntity | 用户问题、上下文实体 | CompanyRef 或候选列表 |
| PlanModules | 意图、主体、时间范围 | ExecutionPlan |
| Finance | CompanyRef、as_of | FinanceResult、Evidence |
| Equity | CompanyRef、as_of、depth | EquityResult、Evidence |
| Events | CompanyRef、时间窗 | EventResult、Evidence |
| CrossValidate | 三类结果 | CrossSignal、模式候选 |
| BuildClaims | 结果和 Evidence | Claim 列表 |
| GenerateAnswer | Claim、问题、上下文 | 自然语言答案和追问建议 |
| ValidateEvidence | 文本和 Claim | 校验通过或降级模板 |
| PersistTurn | 完整 State | 会话、checkpoint、审计日志 |

## 7.3 强类型 State

```python
class CompanyRef(BaseModel):
    entity_id: str
    wind_code: str
    sec_name: str
    exchange: str
    industry_l1: str | None = None

class ExecutionPlan(BaseModel):
    intent: str
    requested_modules: list[str]
    cross_checks: list[str]
    as_of: date | None
    deadline_ms: int

class ModuleStatus(BaseModel):
    state: Literal[
        "pending", "running", "success", "partial",
        "failed", "skipped", "cancelled"
    ]
    error_code: str | None = None
    recoverable: bool = False
    duration_ms: int | None = None

class RuntimeState(BaseModel):
    request_id: str
    trace_id: str
    session_id: str
    thread_id: str
    turn_id: str
    sequence: int = 0
    warnings: list[WarningItem] = Field(default_factory=list)

class AgentState(TypedDict):
    user_query: str
    company: CompanyRef | None
    messages: Annotated[list, add_messages]
    plan: ExecutionPlan | None
    module_status: Annotated[dict[str, ModuleStatus], merge_module_status]
    results: Annotated[ModuleResults, merge_module_results]
    evidence: Annotated[list[EvidenceRef], merge_evidence]
    claims: Annotated[list[Claim], merge_claims]
    final_response: FinalResponse | None
    runtime: RuntimeState
```

所有并行节点只能写入自己负责的命名空间，Reducer 必须满足确定性、幂等和可测试。

## 7.4 交叉验证策略

`PlanModules` 一次决定基础模块。综合诊断时三模块只执行一次；`CrossValidate` 使用已有结果完成：

- 同期时间对齐；
- 公司和关联实体对齐；
- 信号组合；
- 支持、冲突和缺失证据识别；
- 风险模式匹配；
- 生成进一步查询建议。

若基础计划只调用财务模块，但财务结果触发“需要股权核查”，可创建新的 `FollowUpTask`；同一个 `task_key` 不得重复执行。

## 7.5 幂等、取消和恢复

```text
task_key = session_id + turn_id + module + canonical_parameters_hash
```

- 重复提交相同请求：返回已有 turn 或继续已有执行；
- WebSocket 重连：按 sequence 补发事件；
- 取消：设置取消标志，节点在安全检查点停止；
- 已完成节点不重跑；
- 模块重试保留 attempt 编号和错误历史。

## 7.6 记忆

### 短期记忆

- LangGraph checkpointer 按 `thread_id` 保存每个 super-step；
- 最近 N 轮完整消息进入上下文；
- 更早消息压缩为结构化事实；
- 当前主体、指标、时间和口径单独保存，避免仅依赖摘要文本。

### 长期语义记忆

ChromaDB 保存可检索事实，但不是会话真实状态：

```json
{
  "session_id": "ses_01",
  "source_turn_id": "turn_03",
  "fact_type": "active_company",
  "entity_id": "company_600518_SH",
  "text": "当前会话分析对象为康美药业",
  "valid_from": "2026-07-15T10:00:00+08:00"
}
```

## 7.7 LLM Provider

统一接口：

```python
class LLMProvider(Protocol):
    async def generate_structured(
        self,
        request: LLMRequest,
        response_model: type[BaseModel],
    ) -> BaseModel: ...
```

Provider 实现：DeepSeek、Qwen、Mock。业务层不直接导入具体 SDK。

LLM 失败策略：

1. 同 Provider 可恢复重试一次；
2. 可配置切换备选 Provider；
3. 仍失败则使用模板化结构化结果；
4. 不影响已完成的确定性计算；
5. 在 `warnings` 中明确说明。

---

# 8. 财务、风险与事件业务设计

## 8.1 财务规则引擎

首期规则族建议如下，最终公式、阈值和适用条件以版本化规则定义为准：

| 规则 | 规则族                   | 核心信号                                     | 适用性要求                 |
| ---- | ------------------------ | -------------------------------------------- | -------------------------- |
| R1   | 应收–营收背离           | 应收增速显著高于营收增速                     | 至少连续两期可比数据       |
| R2   | 现金流–利润背离         | 净利润为正但经营现金流弱或持续为负           | 利润和现金流同口径         |
| R3   | 存贷双高                 | 货币资金和有息负债同时较高                   | 货币资金、借款字段有效     |
| R4   | 存货–营收背离           | 存货增速或存货周转显著恶化                   | 存货字段可用；行业可比     |
| R5   | 毛利率/费用率异常        | 毛利率、销售费用率或管理费用率偏离历史及行业 | 成本和费用字段完整         |
| R6   | 其他应收款与关联占用风险 | 其他应收款异常增长并存在关联关系信号         | 其他应收款和关联方数据可用 |
| R7   | 盈利质量与非经常性依赖   | 利润增长与现金、主营收入或扣非利润不一致     | 扣非字段不足时标记不适用   |

每条规则配置：

```text
rule_id
rule_version
name
formula
input_fields
applicability_gate
absolute_threshold
industry_threshold
history_window
severity_mapping
explanation_template
effective_from/effective_to
```

## 8.2 规则输出

```json
{
  "rule_id": "R1",
  "rule_version": "1.0.0",
  "rule_name": "应收-营收背离",
  "status": "triggered",
  "severity": "red",
  "current": {
    "acct_rcv_growth": {"value": 47.2, "unit": "percent"},
    "oper_rev_growth": {"value": 12.1, "unit": "percent"},
    "gap": {"value": 35.1, "unit": "percentage_point"}
  },
  "history": [],
  "industry": {
    "percentile": 92,
    "median": 18.5,
    "peer_count": 67
  },
  "quality": {
    "statement_scope": "parent_company",
    "completeness": 0.96
  },
  "claim_ids": ["claim_r1_01"],
  "evidence_ids": ["ev_bs_01", "ev_is_01"]
}
```

## 8.3 风险评分

风险评分由版本化策略执行：

```text
financial_score
+ equity_score
+ event_score
+ rating_score
- data_quality_penalty
= raw_score
→ calibrated_level
```

输出必须同时返回：

- 综合分；
- 分项分；
- 风险等级；
- 评分策略版本；
- 数据质量；
- 关键贡献因素；
- 反向证据或缓解因素；
- 是否经过统计校准。

## 8.4 置信度

```json
{
  "score": 0.83,
  "level": "high",
  "method": "rule_weighted_v1",
  "calibrated": false,
  "coverage": 0.82
}
```

置信度不能只由 LLM 自报，应综合证据覆盖、规则一致性、数据质量和冲突信号。

## 8.5 舆情事件

事件构建：

```text
公告/研报文本
→ 规则标签
→ 向量检索或聚类
→ 事件簇
→ 摘要
→ 关系判断
→ Evidence 绑定
```

LLM 只用于事件命名和摘要；事件日期、公告类型、评级变化和来源由确定性数据提供。

## 8.6 股权关系

- 持股比例按边原始数据保存；
- 路径最终比例由查询时连乘；
- `level` 是查询结果，不持久化为边属性；
- 一致行动关系单独建边或组实体；
- 实控认定规则需独立版本化；
- LLM 抽取关系先进入候选区，不直接进入正式图谱。

---

# 9. 证据、结论与数据血缘

## 9.1 EvidenceRef

```python
class EvidenceRef(BaseModel):
    evidence_id: str
    source_type: str
    source_record_id: str
    company_code: str | None = None
    field_path: str | None = None
    period: str | None = None
    value: Decimal | str | None = None
    unit: str | None = None
    statement_scope: str | None = None
    source_title: str
    source_uri: str | None = None
    source_excerpt: str | None = None
    dataset_version: str
    checksum: str | None = None
    retrieved_at: datetime
```

## 9.2 Claim

```python
class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: str
    severity: RiskLevel
    confidence: Confidence | None
    rule_id: str | None
    rule_version: str | None
    evidence_ids: list[str]
    verification_status: str
    limitations: list[str]
```

规则：

- 事实型 Claim 至少一个 Evidence；
- LLM 只能引用已提供的 `evidence_id`；
- 无证据内容只能作为解释、假设或追问建议；
- Claim 与 Evidence 均带版本和时间；
- 证据失效或被新修订替代时，旧分析仍可重现。

## 9.3 血缘模型

借鉴 W3C PROV 思想：

- Entity：原始记录、标准记录、派生指标、Claim、报告；
- Activity：导入、标准化、规则计算、图构建、检索、回答生成；
- Agent：脚本版本、模型 Provider、人工审核者；
- `wasDerivedFrom`：派生指标到原始记录；
- `wasGeneratedBy`：Claim 到规则或模型执行；
- `wasAssociatedWith`：执行到软件、模型或人员。

MVP 不要求实现完整 RDF，但字段设计应支持这些关系。

---

# 10. 数据架构

## 10.1 数据分层

```text
raw_*        原始数据，追加写，不覆盖
canonical_*  字段、代码、日期、单位和口径统一
normalized_* 实体对齐、去重和质量标记
 derived_*   增速、分位、规则结果、风险快照
 serving_*   面向 API 和前端的聚合缓存
```

## 10.2 公共系统字段

## 10.2 公共系统字段

所有业务记录建议增加：

```text
id
source_record_id
source_file
source_row
source_type
dataset_version
revision_no
is_latest
ingested_at
updated_at
quality_flags
checksum
```

## 10.3 companies

| 字段 | 类型 | 说明 |
| `entity_id` | VARCHAR PK | 内部稳定实体 ID |
| `wind_code` | VARCHAR UNIQUE | 如 `600519.SH` |
| `sec_name` | VARCHAR | 证券简称 |
| `aliases` | JSON/TEXT | 曾用名和别名 |
| `exchange_code` | VARCHAR | XSHG/XSHE |
| `industry_l1` | VARCHAR | 申万一级行业 |
| `industry_l2` | VARCHAR | 申万二级行业 |
| `sw_indu_code` | VARCHAR | 申万行业代码 |
| `comp_type_code` | SMALLINT | 公司类型 |
| `listing_date` | DATE | 上市日期 |
| `industry_source` | VARCHAR | 行业来源 |
| `industry_as_of` | DATE | 行业分类有效日期 |

## 10.4 财务三表

### balance_sheet

保留 V9 核心字段：

```text
wind_code, report_period, statement_type, ann_dt,
monetary_cap, acct_rcv, oth_rcv, inventories,
tot_cur_assets, fix_assets, goodwill, tot_assets,
st_borrow, lt_borrow, acct_payable,
tot_cur_liab, tot_liab, tot_shrhldr_eqy_incl_min_int
```

### income_statement

```text
wind_code, report_period, statement_type, ann_dt,
oper_rev, tot_oper_rev, less_oper_cost,
less_selling_dist_exp, less_gerl_admin_exp, less_fin_exp,
oper_profit, tot_profit,
net_profit_excl_min_int_inc, net_profit_after_ded_nr_lp
```

### cash_flow

```text
wind_code, report_period, statement_type, ann_dt,
net_cash_flows_oper_act, net_cash_flows_inv_act,
net_cash_flows_fnc_act, net_incr_cash_cash_equ,
free_cash_flow
```

财务表唯一约束建议：

```text
(wind_code, report_period, statement_type, ann_dt, revision_no)
```

不要只用 `(wind_code, report_period)`，因为同一报告期可能存在更正和重述。

## 10.5 top_shareholders

```text
wind_code
ann_dt
s_holder_enddate
s_holder_name
s_holder_aname
s_holder_pct
s_holder_quantity
s_holder_holdercategory
s_holder_sequence
report_period
holder_entity_id
entity_match_confidence
```

## 10.6 announcements

```text
object_id
wind_code
ann_dt
n_info_title
n_info_fcode
sentiment
sentiment_method
source_uri
content_hash
```

不优先使用 MySQL ENUM，使用 VARCHAR + CHECK 或字典表，便于扩展。

## 10.7 research_reports

```text
report_id
wind_code
sec_code
exchange_code
sec_name
org_name
title
publish_date
abstract
rating_org
rating_change
industry_l1
sw_indu_code
source_uri
content_hash
```

在入库阶段统一生成 `wind_code`，不要让每次查询临时拼接后缀。

## 10.8 派生与运行表

新增：

```text
rule_definitions
rule_evaluations
risk_policies
risk_assessments
event_clusters
event_relations
claims
evidence_refs
conversation_sessions
conversation_turns
module_executions
report_jobs
data_quality_reports
```

## 10.9 图数据

### 节点

```text
Entity
  entity_id
  entity_type
  canonical_name
  aliases[]
  registration_code?
  wind_code?
```

标签：`ListedCompany`、`Company`、`Person`、`Plan`。

### 关系

```text
HOLDS
CONTROLS
ACTS_IN_CONCERT_WITH
RELATED_TO
GUARANTEES
```

公共属性：

```text
pct
quantity
effective_from
effective_to
report_period
ann_dt
source_id
source_type
confidence
verification_status
graph_version
```

### LLM 候选关系

```text
verification_status=pending
extraction_method=llm
confidence=<score>
```

结构化数据、多源一致、规则验证或人工审核通过后，才升级为 verified。

## 10.10 ChromaDB

| Collection | 内容 | Metadata |
| `announcement_chunks` | 公告标题、摘要或正文块 | source_id、wind_code、ann_dt、fcode、sentiment、hash |
| `research_report_chunks` | 研报摘要分块 | report_id、wind_code、publish_date、org、rating_change |
| `evidence_text_chunks` | 可定位原文片段 | evidence_id、source_id、page/span、hash |
| `conversation_memory` | 长期可检索事实 | session_id、turn_id、fact_type、entity_id |

所有 collection metadata 增加：

```text
chunk_index
chunker_version
embedding_model
embedding_model_version
text_hash
dataset_version
language
```

---

# 11. REST API 契约

## 11.1 版本与命名

公开接口统一使用 `/api/v1`。资源使用复数名词，公司的财务、股权、事件和风险作为公司子资源。

## 11.2 端点总览

| 能力         | 方法 | 端点                                      | 优先级 |
| ------------ | :--: | ----------------------------------------- | :----: |
| 存活检查     | GET | `/healthz`                              |   P0   |
| 就绪检查     | GET | `/readyz`                               |   P0   |
| 公司搜索     | GET | `/api/v1/companies?query=康美&limit=10` |   P0   |
| 企业画像摘要 | GET | `/api/v1/companies/{code}`              |   P0   |
| 财务分析     | GET | `/api/v1/companies/{code}/finance`      |   P0   |
| 股权穿透     | GET | `/api/v1/companies/{code}/equity`       |   P0   |
| 舆情事件     | GET | `/api/v1/companies/{code}/events`       |   P0   |
| 综合风险     | GET | `/api/v1/companies/{code}/risk`         |   P0   |
| 行业对标     | GET | `/api/v1/companies/{code}/benchmarks`   |   P0   |
| 会话列表     | GET | `/api/v1/sessions`                      |   P0   |
| 创建会话     | POST | `/api/v1/sessions`                      |   P0   |
| 会话详情     | GET | `/api/v1/sessions/{session_id}`         |   P0   |
| 非流式问答   | POST | `/api/v1/chat`                          |   P0   |
| 流式问答     |  WS  | `/api/v1/chat/ws`                       |   P0   |
| 创建比较     | POST | `/api/v1/comparisons`                   |   P1   |
| 创建报告     | POST | `/api/v1/reports`                       |   P1   |
| 报告状态     | GET | `/api/v1/reports/{report_id}`           |   P1   |
| 报告下载     | GET | `/api/v1/reports/{report_id}/file`      |   P1   |

## 11.3 公共查询参数

| 参数                | 用途                                     |
| ------------------- | ---------------------------------------- |
| `as_of`           | 指定数据快照日期                         |
| `statement_scope` | `parent_company / consolidated / auto` |
| `include`         | 指定摘要接口包含的可选区域               |
| `periods`         | 财务历史期数                             |
| `months`          | 事件回溯月数                             |
| `depth`           | 股权穿透深度，1–10                      |
| `include_related` | 是否包含关联方                           |

## 11.4 成功响应

```json
{
  "data": {},
  "meta": {
    "request_id": "req_01",
    "trace_id": "trace_01",
    "schema_version": "1.0",
    "generated_at": "2026-07-15T10:00:00+08:00",
    "data_as_of": "2026-06-30",
    "dataset_version": "official-2026-07-12",
    "rule_set_version": "finance-rules-1.0.0",
    "graph_version": "equity-2026Q2"
  },
  "warnings": []
}
```

## 11.5 部分成功

```json
{
  "data": {
    "status": "partial",
    "finance": {},
    "equity": null,
    "events": {}
  },
  "meta": {},
  "warnings": [
    {
      "code": "EQUITY_TIMEOUT",
      "module": "equity",
      "message": "股权模块超过本轮时限，已返回其余结果。",
      "recoverable": true
    }
  ]
}
```

## 11.6 错误响应

使用 `application/problem+json`：

```json
{
  "type": "https://truthnet/errors/module-timeout",
  "title": "Module execution timed out",
  "status": 503,
  "detail": "Equity analysis exceeded its deadline.",
  "instance": "/api/v1/companies/600518.SH/risk",
  "error_code": "EQUITY_TIMEOUT",
  "trace_id": "trace_01",
  "recoverable": true
}
```

### 错误码

| HTTP | `error_code`               | 含义                   |
| ---: | ---------------------------- | ---------------------- |
|  400 | `INVALID_ARGUMENT`         | 参数格式错误           |
|  404 | `COMPANY_NOT_COVERED`      | 公司不在数据覆盖范围   |
|  409 | `TURN_ALREADY_RUNNING`     | 同会话已有互斥轮次     |
|  422 | `SCHEMA_VALIDATION_FAILED` | 请求或模型输出校验失败 |
|  429 | `RATE_LIMITED`             | 频率受限               |
|  503 | `LLM_TIMEOUT`              | 模型超时               |
|  503 | `GRAPH_UNAVAILABLE`        | 图服务不可用           |
|  503 | `DATASTORE_UNAVAILABLE`    | 结构化存储不可用       |
|  500 | `INTERNAL_ERROR`           | 未预期错误             |

## 11.7 公司搜索

```http
GET /api/v1/companies?query=康美&limit=10
```

```json
{
  "data": {
    "query": "康美",
    "total": 2,
    "candidates": [
      {
        "entity_id": "company_600518_SH",
        "wind_code": "600518.SH",
        "sec_name": "康美药业",
        "exchange": "上交所",
        "industry_l1": "中药",
        "listing_date": "2001-03-19",
        "match_score": 0.99
      }
    ]
  },
  "meta": {},
  "warnings": []
}
```

## 11.8 企业画像摘要

```http
GET /api/v1/companies/600518.SH?include=risk_summary,finance_summary,equity_preview,event_summary&as_of=2026-06-30
```

返回基本信息、风险标签和各模块摘要，不返回完整图谱和全部历史序列。

## 11.9 股权穿透

```http
GET /api/v1/companies/600518.SH/equity?depth=5&include_related=true&as_of=2026-06-30
```

结果使用统一 `nodes + edges + paths`，避免同一节点在每条 chain 中重复：

```json
{
  "data": {
    "target": {"entity_id": "company_600518_SH", "wind_code": "600518.SH", "name": "康美药业"},
    "nodes": [],
    "edges": [],
    "paths": [
      {
        "path_id": "path_01",
        "node_ids": ["person_01", "company_02", "company_600518_SH"],
        "edge_ids": ["edge_01", "edge_02"],
        "final_control_pct": 30.0,
        "risk_level": "red"
      }
    ],
    "concerted_groups": [],
    "related_anomalies": []
  },
  "meta": {},
  "warnings": []
}
```

## 11.10 财务分析

```http
GET /api/v1/companies/600518.SH/finance?periods=8&statement_scope=parent_company
```

返回 `risk_level`、`rules`、`industry_benchmark`、`data_quality`、`claim_ids` 和 `evidence_ids`。

## 11.11 舆情事件

```http
GET /api/v1/companies/600518.SH/events?months=36
```

返回：

```text
sentiment_summary
event_clusters
timeline
rating_changes
keyword_summary
evidence_ids
```

事件关系使用受约束枚举，不再默认 `leads_to`。

## 11.12 综合风险

```http
GET /api/v1/companies/600518.SH/risk?as_of=2026-06-30
```

返回：综合分、等级、分项贡献、风险标签、模式匹配、置信度、数据覆盖、缓解因素和证据。

## 11.13 行业对标

```http
GET /api/v1/companies/600518.SH/benchmarks?period=2026Q2
```

行业样本少于 5 时返回 warning，并仅展示通用阈值，不伪造稳定分位。

## 11.14 比较

```http
POST /api/v1/comparisons
```

```json
{
  "company_codes": ["600518.SH", "000538.SZ", "600436.SH"],
  "period": "2026Q2",
  "indicators": ["R1", "R2", "R3"],
  "statement_scope": "parent_company"
}
```

## 11.15 报告长任务

```http
POST /api/v1/reports
```

返回 HTTP 202：

```json
{
  "data": {
    "report_id": "rpt_01",
    "status": "queued",
    "status_url": "/api/v1/reports/rpt_01"
  },
  "meta": {},
  "warnings": []
}
```

## 11.16 兼容接口

开发迁移期间：

```text
/chat/ws → /api/v1/chat/ws
/api/search → /api/v1/companies
/api/company/{code} → /api/v1/companies/{code}
/api/equity/{code} → /api/v1/companies/{code}/equity
/api/finance/{code} → /api/v1/companies/{code}/finance
/api/sentiment/{code} → /api/v1/companies/{code}/events
```

兼容路由标记 deprecated、记录调用量，并在前端和评测脚本全部迁移后删除。

---

# 12. WebSocket 契约

## 12.1 统一事件信封

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01",
  "event_type": "answer.delta",
  "session_id": "ses_01",
  "turn_id": "turn_01",
  "sequence": 8,
  "timestamp": "2026-07-15T10:00:05+08:00",
  "trace_id": "trace_01",
  "payload": {}
}
```

## 12.2 Client → Server

| `event_type`      | Payload                          |
| ------------------- | -------------------------------- |
| `chat.query`      | text、session_id、可选 as_of     |
| `company.confirm` | company_ref、session_id、turn_id |
| `chat.follow_up`  | text、session_id                 |
| `turn.cancel`     | turn_id                          |
| `stream.resume`   | turn_id、last_received_sequence  |
| `ping`            | client_time                      |

## 12.3 Server → Client

| `event_type`         | 说明                               |
| ---------------------- | ---------------------------------- |
| `turn.accepted`      | 请求已接收，分配 turn_id           |
| `company.candidates` | 候选公司                           |
| `module.started`     | 模块开始                           |
| `module.completed`   | 模块终态和耗时                     |
| `answer.delta`       | 文本增量                           |
| `artifact.upsert`    | 规则、图、时间线、证据等结构化更新 |
| `warning.raised`     | 数据不足、超时、降级               |
| `turn.completed`     | 最终结果、追问建议和快照信息       |
| `turn.failed`        | 本轮无法继续                       |
| `heartbeat`          | 服务端心跳                         |

## 12.4 artifact.upsert

```json
{
  "event_type": "artifact.upsert",
  "payload": {
    "artifact_type": "finance_rules",
    "artifact_id": "finance_600518_2026Q2",
    "revision": 2,
    "operation": "replace",
    "data": {}
  }
}
```

## 12.5 完整时序

```text
Client → chat.query
Server → turn.accepted
Server → company.candidates                // 需要消歧时
Client → company.confirm
Server → module.started(finance)
Server → module.started(equity)
Server → module.started(events)
Server → answer.delta
Server → artifact.upsert(finance_rules)
Server → module.completed(finance)
Server → artifact.upsert(equity_graph)
Server → module.completed(equity)
Server → warning.raised(events_partial)     // 可选
Server → artifact.upsert(event_timeline)
Server → answer.delta
Server → turn.completed
```

## 12.6 重连恢复

前端保存最后序号：

```json
{
  "event_type": "stream.resume",
  "payload": {
    "turn_id": "turn_01",
    "last_received_sequence": 17
  }
}
```

服务端可补发则从 18 开始；执行已完成则返回最终事件；事件缓存失效时返回 `STREAM_RESUME_UNAVAILABLE`，前端加载持久化 turn 结果。

---

# 13. 性能、缓存、超时与降级

## 13.1 目标

| 场景              |                           目标 |
| ----------------- | -----------------------------: |
| 公司搜索          |                   P95 ≤ 500ms |
| 企业摘要          |                      P95 ≤ 1s |
| 单模块查询        | P95 ≤ 2s；复杂图查询允许 ≤4s |
| Chat 请求接收事件 |                      P95 ≤ 1s |
| Chat 首文本       |                      P95 ≤ 3s |
| Chat 完整结果     |        P95 ≤ 8s，允许 partial |
| 页面切换缓存命中  |                        ≤200ms |
| 报告创建          |               ≤500ms 返回 202 |

## 13.2 模块 deadline

```text
entity_resolution: 1s
finance: 3s
equity: 4s
events: 3s
cross_validate: 1s
answer_generation: 4s
overall_deadline: 8s（可配置）
```

overall deadline 到达后，返回已完成结果和 warnings，不把“未执行”表示为“无异常”。

## 13.3 缓存

| 缓存对象 | Key | 失效 |
| 公司搜索 | query + dataset_version | 公司表更新 |
| 财务规则 | company + as_of + scope + rule_version | 数据或规则变更 |
| 图路径 | company + as_of + depth + graph_version | 图版本变更 |
| 行业分位 | industry + period + rule_version | 行业数据重算 |
| 画像摘要 | company + as_of + include | 任一依赖版本变更 |

MVP 可使用进程内有界缓存；正式部署预留共享缓存 Adapter，但不在当前技术栈中强制引入 Redis。

## 13.4 降级

```text
LLM 不可用 → 模板化结构化摘要
ChromaDB 不可用 → 仅使用结构化公告/研报过滤
报告渲染失败 → 保留 JSON 分析结果并允许重试
```

所有降级必须进入 `warnings`、日志和报告页。

---

# 14. 安全、隐私与 AI 风险治理

## 14.1 API 安全

覆盖 OWASP API 风险：

- 对 `company_code`、`session_id`、`report_id` 做对象级授权预留；
- 请求和响应使用白名单 Pydantic 模型，避免过度暴露和 Mass Assignment；
- 限制搜索长度、比较公司数量、图深度、回溯月数；
- 对 WebSocket 进行连接数、消息大小和频率控制；
- API Key、数据库密码和模型凭证只来自环境变量；
- 错误不返回堆栈和敏感配置；
- 报告下载使用不可猜测 ID 和有效期；
- 外部 URL 抓取采用域名白名单，防止 SSRF；
- Markdown 渲染禁止不受信任 HTML，链接添加安全属性。

## 14.2 Prompt Injection 与 RAG 安全

公告和研报文本视为不可信数据：

- 文档内容不得改变系统指令；
- 工具调用参数来自结构化 Planner，不直接执行文档中的命令；
- 检索文本与系统提示使用明确隔离；
- LLM 输出只允许引用白名单 Evidence；
- 关系抽取进入候选区；
- 对异常内容记录来源和哈希。

## 14.3 AI 风险管理

按 NIST AI RMF 思路：

### Govern

- 明确产品边界和免责声明；
- 规则、模型和数据负责人；
- 变更评审和事故响应流程。

### Map

- 描述用户、数据、风险和受影响场景；
- 区分算法信号和权威事实；
- 识别误报、漏报、过度依赖和过时数据风险。

### Measure

- 结果准确率、证据覆盖率；
- 多轮主体保持率；
- 无证据 Claim 比例；
- partial 比例和模块超时；
- 风险等级校准；
- 不同行业和数据完整度下的表现。

### Manage

- 低置信度降级；
- 高风险结论强制显示证据；
- 模型或数据异常时回滚版本；
- 记录并修复错误案例。

## 14.4 隐私

当前核心数据为公开企业数据，但会话仍可能包含用户研究偏好：

- 日志不记录完整敏感输入，必要时脱敏；
- 会话删除采用软删除 + 到期清理；
- 不向第三方模型发送不必要的完整历史；
- 外部模型请求记录 Provider、模型和数据范围，不记录密钥。

---

# 15. 可观测性

## 15.1 统一上下文

```text
request_id
trace_id
session_id
thread_id
turn_id
task_key
module
adapter
attempt
```

## 15.2 日志字段

```text
timestamp
level
trace_id
turn_id
module
adapter
duration_ms
status
error_code
data_version
rule_version
graph_version
model_version
```

## 15.3 指标

```text
http_request_latency
ws_active_connections
turn_time_to_first_event
turn_time_to_first_text
turn_total_latency
module_latency
module_timeout_count
partial_response_rate
adapter_fallback_count
llm_retry_count
evidence_validation_failure
ws_resume_success_rate
report_job_duration
```

## 15.4 Trace

一个完整 turn 的 span 层级：

```text
chat.turn
  entity.resolve
  plan.create
  finance.analyze
  equity.traverse
  events.retrieve
  cross_validate
  answer.generate
  evidence.validate
  session.persist
```

OpenTelemetry 作为标准接口，MVP 可先输出结构化日志，后续接入具体后端。

---

# 16. 测试与 CI

## 16.1 测试层级

| 类型 | 内容 | Profile |
| Unit | 财务公式、风险策略、Reducer、实体匹配 | test |
| Schema | Pydantic、OpenAPI、事件 JSON Schema | test |
| Port Contract | MySQL、Neo4j 一致行为 | full |
| Agent Graph | 分支、并行、取消、超时、恢复 | test |
| API Contract | 成功、错误、partial、兼容路由 | full |
| WebSocket | 序号、幂等、重连、未知事件 | full |
| Integration | MySQL、Neo4j、ChromaDB、Provider mock | full |
| Frontend Unit | Reducer、组件和格式化 | mock |
| Frontend E2E | 对话、候选、画像、partial、重连 | full |
| Regression | 已有后端测试和 doctor | 原环境 |

## 16.2 必须保留的本地检查

```bash
ruff check .
ruff format --check .
python -m pytest backend/tests -v
pre-commit run --all-files
python scripts/encoding_path_audit.py
python scripts/doctor.py
```

前端：

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## 16.3 CI Jobs

```text
  
frontend:
  lint + typecheck + test + build

contract:
  OpenAPI 3.1 validation
  AsyncAPI/WebSocket schema validation
  generated TypeScript types clean
  breaking change detection

integration:
  Linux
  MySQL + Neo4j + ChromaDB
  main、定时任务或带标签 PR

security:
  dependency audit
  secret scan
  basic API security tests
```

## 16.4 契约冻结条件

- 所有 Pydantic DTO 已定义；
- OpenAPI 和 WebSocket 契约可生成；
- 风险、模块状态和事件枚举统一；
- Evidence/Claim 模型固定；
- 数值单位、报表口径和 null 语义明确；
- MySQL、Neo4j Port 已定义；
- 前端类型由契约生成；
- 兼容路径和弃用策略明确；
- 现有测试无回归。

---

# 17. 环境、依赖与跨平台规范

## 17.1 Python

```text
Python 3.11
conda env: truthnet
venv: fallback
根目录唯一 requirements.txt
```

新增依赖：

1. 使用 `==` 固定版本；
2. 写入唯一 `requirements.txt`；
3. 更新 doctor 和 smoke；
4. 验证 Windows/Linux/macOS；
5. 镜像作为可配置加速，不写死单一镜像；
6. 不修改系统 CUDA 或高风险全局环境。

## 17.2 前端

- pnpm 管理；
- 提交 `pnpm-lock.yaml`；
- 不提交 `node_modules`；
- API 地址通过环境变量；
- 依赖版本固定并由 CI 验证。

## 17.3 外部服务

MySQL 和 Neo4j 需要本地安装：

- 可使用 Windows 原生服务；
- Linux/macOS 原生服务；
- 团队共享开发实例；
- 容器化为可选方案；
- CI 基础 Job 不要求安装完整服务。

## 17.4 编码和路径

- UTF-8；
- LF；
- `.gitattributes` 强制文本规范；
- 所有 Python 文本读写显式 `encoding="utf-8"`；
- 使用 `pathlib.Path`；
- 禁止硬编码 `C:\`、`E:\` 或 `/home/user`；
- 不假定当前工作目录；
- PowerShell 与 shell 脚本语义一致。

---

# 18. 部署设计

## 18.1 MVP 演示部署

```text
Reverse Proxy（可选）
  ├─ 前端静态资源
  └─ FastAPI
       ├─ MySQL
       ├─ Neo4j
       ├─ ChromaDB persistent
       └─ LLM API
```

MVP 可为单机部署，但仍保持 Adapter 边界，不提前拆微服务。

## 18.2 健康检查

- `/healthz`：进程存活；
- `/readyz`：关键依赖可用状态；
- 返回每个 Adapter 状态，但不暴露凭证和内部地址；
- degraded profile 可 ready，但需明确 `status=degraded`。

## 18.3 配置

```env
SQL_BACKEND=mysql
GRAPH_BACKEND=neo4j
VECTOR_BACKEND=chroma
LLM_BACKEND=deepseek
DEFAULT_AS_OF=
API_V1_ENABLED=true
LEGACY_API_ENABLED=true
```

---

# 19. 原项目迁移策略

## 19.1 总体决策

不全面重建。保留：

- Python 3.11 和 conda 环境；
- 唯一 requirements；
- FastAPI、LangGraph、Pydantic、ChromaDB；
- pytest、Ruff、pre-commit、CI；
- UTF-8/LF/路径审计；
- Git 流程、文档、scripts、skills 和已有测试。

重构：

- API schemas；
- WebSocket 协议；
- Agent State；
- Application/Port/Adapter 分层；
- Evidence/Claim；
- 数据访问和版本；
- 服务端会话持久化。

新增：

- MySQL Adapter；
- Neo4j Adapter；
- SQLAlchemy/Alembic；
- OpenAPI/AsyncAPI 契约文件；
- 契约测试；
- 报告任务；
- 可观测性字段。

## 19.2 迁移阶段

### M0：统一契约

输出：

```text
docs/API_CONTRACT_V1.md
docs/WEBSOCKET_CONTRACT_V1.md
docs/DATA_CONTRACT.md
docs/FRONTEND_DESIGN.md
```

### M1：建立新分层，继续使用轻量 Adapter

- Mock LLM；
- ChromaDB local；
- 保留旧端点兼容。

### M2：前端接入 V1 契约

- 类型自动生成；
- 新 WebSocket reducer；
- partial、unknown、重连、取消；
- 三页面使用 mock 到真实接口平滑切换。

### M3：强类型 Agent 与会话持久化

- Reducer；
- checkpointer；
- 10 轮恢复；
- task_key 幂等。

### M4：MySQL Adapter

- 迁移脚本；
- 数据版本和修订可追踪。

### M5：Neo4j Adapter

- 时间和来源；
- 故障自动降级。

### M6：业务能力和报告

- 7 条规则；
- 事件聚类；
- 交叉验证；
- Claim/Evidence；
- PDF 长任务。

### M7：兼容接口退役评审

只有前端、评测脚本和测试都无旧路径依赖后，才删除兼容路由。

---

# 20. 开发计划与当前状态

## 20.1 当前文档记录的实现状态

前端 V3 文档报告以下内容已完成，但应在仓库中通过 build、测试和代码审计再次确认：

- React + Vite + TypeScript 骨架；
- vintage-grey 主题和部分 shadcn/ui 组件；
- 对话主页三栏布局；
- 企业画像页骨架；
- 康美药业 mock 数据；
- 初版 TypeScript 类型。

后端已有工程基线包括 FastAPI HTTP/WebSocket mock、ChromaDB smoke、跨平台环境、编码路径检查和已有测试。正式迁移以仓库实际状态为准，不仅依据文档自报。

## 20.2 重新基线后的阶段计划

| 阶段             | 时间建议   | 后端                                             | 前端                           | 数据                                               | 验收             |
| ---------------- | ---------- | ------------------------------------------------ | ------------------------------ | -------------------------------------------------- | ---------------- |
| Phase A 契约统一 | 7/15–7/18 | V1 DTO、Port、WS、错误                           | 类型生成、mock 对齐            | 字段与版本确认                                     | 契约评审通过     |
| Phase B 最小 E2E | 7/19–7/30 | MySQL/Neo4j/ChromaDB/DeepSeek 搜索/画像/股权/WS  | 三页面动态+WS 对接             | 全量入库、全量图谱、行业补全                       | E2E 对话闭环     |
| Phase C 核心业务 | 7/31–8/9  | 7 规则、事件、交叉验证、Claim/Evidence、风险评分 | 面板联动、证据链、对比页       | 事件聚类、评级拐点、分位计算、造假模式库、评测框架 | 真实公司全量分析 |
| Phase D 稳定联调 | 8/10–8/14 | 降级、幂等、性能、PDF、Docker                    | 错误状态、重连、响应式、报告页 | 评测脚本、白皮书初稿                               | 可部署可演示     |
| Phase E 交付     | 8/15–8/20 | Bug 修复、部署                                   | UI 打磨、视频                  | 跑分、白皮书终稿、PPT                              | 全部交付物齐     |

---

# 21. 验收标准

## 21.1 产品验收

- 综合诊断可完成主体识别、三模块分析、交叉验证和证据展示；
- 简单查询不会无意义调用全部模块；
- 10 轮后仍能正确解析“它”“上一家公司”“刚才的指标”；
- 结论不把风险信号描述为已认定事实；
- 数据不足和模块超时清晰显示。

## 21.2 前端验收

- 桌面三栏；
- WebSocket 流式、取消和重连；
- 图谱支持筛选、拖拽、缩放和列表替代视图；
- 对比页统一口径；
- 风险不只靠颜色；
- 键盘完成主要流程；
- build、typecheck、测试通过。

## 21.3 后端验收

- `/api/v1` 契约稳定；
- OpenAPI 3.1 可生成并校验；
- WebSocket schema 可验证；
- MySQL 和 Neo4j Port Contract 通过；
- Agent 并行无 State 覆盖；
- partial、超时、重试和幂等测试通过；
- Claim 无无效 Evidence 引用。

## 21.4 数据验收

- 原始记录和标准记录可追溯；
- 更正和重述不覆盖历史；
- 数值单位和报表口径明确；
- 行业样本数和数据完整度可见；
- 图关系具有时间和来源；
- 向量索引可按版本重建。

## 21.5 工程验收

- 原有测试无回归；
- Ruff、format、pytest、pre-commit、doctor、encoding audit 全部通过；
- Windows/Linux/macOS CI 通过；
- full integration 通过；
- main 仅通过 PR 合并。

---

# 22. 风险与应对

| 风险                     | 应对                                                  |
| ------------------------ | ----------------------------------------------------- |
| 母公司报表字段缺失       | 适用性 Gate、数据质量、口径提示，不适用与未触发分开   |
| 行业分类覆盖不足         | 多来源补全、版本记录、样本不足降级                    |
| LLM 结构化输出不稳       | Pydantic 校验、Evidence 白名单、重试、模板降级        |
| LLM 限流或故障           | Provider Adapter、缓存和备选 Provider                 |
| Agent 并发复杂           | 命名空间 State、Reducer、task_key、节点单测           |
| API 漂移                 | OpenAPI/AsyncAPI、生成类型、breaking change CI        |
| 图谱实体错配             | 稳定 entity_id、别名、置信度和候选审核                |
| LLM 抽取污染正式图谱     | CandidateRelation → Verification → VerifiedRelation |
| 图节点过多导致卡顿       | 节点上限、聚合、按需展开、Canvas/列表模式             |
| 报告生成超时             | 202 长任务、状态页和重试                              |
| Windows 外部服务安装阻塞 | Docker Compose 统一环境                               |
| 数据修订无法追踪         | revision_no、is_latest、dataset_version               |
| 事件误标因果             | 关系枚举和明确来源 Gate                               |
| 误报导致用户过度依赖     | 风险说明、替代解释、证据和免责声明                    |

---

# 23. 附录 A：前端核心类型

```typescript
type RiskLevel = 'red' | 'orange' | 'yellow' | 'blue' | 'green' | 'unknown'
type ModuleState = 'pending' | 'running' | 'success' | 'partial' | 'failed' | 'skipped' | 'cancelled'

interface ApiMeta {
  requestId: string
  traceId: string
  schemaVersion: string
  generatedAt: string
  dataAsOf?: string
  datasetVersion?: string
  ruleSetVersion?: string
  graphVersion?: string
}

interface ApiResponse<T> {
  data: T
  meta: ApiMeta
  warnings: WarningItem[]
}

interface WSMessage<T = unknown> {
  schemaVersion: string
  eventId: string
  eventType: string
  sessionId: string
  turnId: string
  sequence: number
  timestamp: string
  traceId: string
  payload: T
}

interface PanelData {
  riskLevel: RiskLevel
  riskLabel: string
  dataAsOf?: string
  moduleStatus: Record<string, ModuleStatus>
  rules: RuleTrigger[]
  timeline: EventSummary[]
  evidenceSummary: EvidenceSummary
  warnings: WarningItem[]
  followUps: FollowUpSuggestion[]
}
```

TypeScript 类型优先由 OpenAPI/事件 schema 生成，手写类型只用于前端 ViewModel。

---

# 24. 附录 B：康美药业 Mock 示例

> Mock 仅用于 UI 和契约测试，不应被当作当前事实数据。

```text
风险等级：红色（演示）
R1 应收–营收背离：47.2% vs 12.1%
R2 现金流–利润背离：经营现金流 -2.3 亿，净利润 1.5 亿
R3 存贷双高：货币资金 150.5 亿，短期借款 120.3 亿

股权路径：
马兴田 ─99.7%→ 康美实业 ─30.1%→ 康美药业

事件：
2018-10 自媒体质疑
2018-12 立案调查
2019-04 会计差错更正
2019-05 实施 ST
```

Mock 数据必须带 `mock=true` 或独立 fixture，不得进入正式数据库。

---

# 25. 附录 C：参考标准与设计资料

1. OpenAPI Specification：项目 REST 契约采用 FastAPI 可直接生成的 OpenAPI 3.1.x。https://spec.openapis.org/oas/v3.1.0.html
2. FastAPI OpenAPI 与客户端生成说明。https://fastapi.tiangolo.com/advanced/generate-clients/
3. AsyncAPI：用于 WebSocket/异步事件契约。https://www.asyncapi.com/docs/reference/specification/latest
4. RFC 9457 Problem Details for HTTP APIs。https://www.rfc-editor.org/rfc/rfc9457
5. AWS Prescriptive Guidance：Hexagonal Architecture / Ports and Adapters。https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html
6. LangGraph Persistence：thread、checkpointer 和 checkpoint。https://docs.langchain.com/oss/python/langgraph/persistence
7. W3C PROV-O：数据与结论血缘的概念参考。https://www.w3.org/TR/prov-o/
8. NIST AI RMF 与 Generative AI Profile。https://www.nist.gov/itl/ai-risk-management-framework
9. OWASP API Security Top 10 2023。https://owasp.org/API-Security/editions/2023/en/0x11-t10/
10. OpenTelemetry：日志、指标和 trace 的统一上下文。https://opentelemetry.io/docs/
11. WCAG 2.2。https://www.w3.org/TR/WCAG22/
12. Alembic：SQLAlchemy 数据库迁移。https://alembic.sqlalchemy.org/
13. FinQA：带可执行推理程序的金融数值问答数据集。https://arxiv.org/abs/2109.00122
14. TAT-QA：表格与文本联合金融问答。https://aclanthology.org/2021.acl-long.254/
15. DocFinQA：长上下文金融推理数据集。https://arxiv.org/abs/2401.06915
16. FinRobot：面向金融应用的开源 Agent 平台。https://arxiv.org/abs/2405.14767
17. Temporal Provenance Model：时间感知的数据血缘模型。
    https://arxiv.org/abs/1211.5009

---

# 26. 最终结论

TruthNet 的最终工程方向是：

```text
完整产品设计与页面表达
+ 契约优先的前后端协作
+ 强类型、可恢复的 LangGraph 编排
+ 确定性计算与 LLM 解读分离
+ Claim–Evidence–Provenance 证据体系
+ MySQL 与 Neo4j 统一存储
+ 数据、规则、图谱和模型版本化
+ 部分成功、降级、可观测和安全治理
```

项目不需要全面重建。应保留已经验证的环境、代码质量体系、轻量存储、图算法和测试，通过 Application/Port/Adapter 逐步接入正式数据库和图服务。对外稳定的是 `/api/v1`、WebSocket 事件、Evidence/Claim 和页面 ViewModel；内部数据库、模型、Agent 节点与实现可以继续演进。
