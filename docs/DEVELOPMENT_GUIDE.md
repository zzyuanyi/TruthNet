# 织网鉴真 · 开发实践手册

> 2026-07-15 | 织网鉴真队 | 提交截止 2026-08-20
>
> **定位**：施工手册。每个阶段每组具体做什么、交付什么、怎么验收、用了什么标准。
> **蓝图参考**：[TruthNet_综合设计方案_V12.md](design/TruthNet_综合设计方案_V12.md)
> **使用方式**：每周末各组填入"实际结果"，Phase 结束时组长汇总。
>
> ---

## 团队分工

| 组 | 人数 | 成员 | 职责 |
|------|:--:|------|------|
| 前端组 | 1 人 | | React 页面、组件、状态管理、WS 对接 |
| 后端组 | 3 人 | | FastAPI、Agent/Skill、Neo4j/MySQL、部署 |
| 数据组 | 2 人 | | ETL、规则公式、评测、白皮书、PPT |

---

## 各组入口文档

| 组 | 必读 | 选读 |
|------|------|------|
| 前端组 | V11 §4-5（页面/组件/状态）、§11-12（API/WS）、附录A（类型） | V11 §13（性能）、§5.8（无障碍） |
| 后端组 | V11 §6-9（架构/Agent/证据）、§11-13（契约/性能）、§7.3（State） | V11 §14-15（安全/可观测） |
| 数据组 | V12 §1.4（数据全景）、§10（数据架构）、§8.1（规则） | [data-computation-checklist.md](design/data-computation-checklist.md) |

---

# Phase 0 · 开发环境就绪（7/15-7/16，与 Phase A 并行，1天）

### 阶段目标

> **每人本地环境跑通，代码仓库能启动，数据能访问。阻塞问题在群里当天解决。**

---

### 全员 · 环境搭建

#### 1. 安装清单

每人本地安装以下软件：

| 软件 | 版本要求 | 验证命令 |
|------|------|------|
| Python | 3.11.x | `python --version` |
| Conda | 最新 | `conda --version` |
| Node.js | 18+ | `node --version` |
| pnpm | 最新 | `pnpm --version` |
| MySQL | 8.0.x | `mysql -u root -p` 能登入 |
| Neo4j | 5.x | `cypher-shell` 或浏览器 `localhost:7474` 能打开 |

> MySQL 和 Neo4j 安装方式自选：Windows 原生安装包、Docker Desktop、或使用团队共享开发实例均可。

#### 2. 克隆代码仓库

```bash
git clone https://github.com/zzyuanyi/TruthNet.git
cd TruthNet
git checkout main
```

#### 3. Python 环境

```bash
conda create -n truthnet python=3.11 -y
conda activate truthnet
pip install -r requirements.txt
```

#### 4. MySQL 初始化

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS truthnet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

> 表结构由数据组 Phase B 提供建表脚本，Phase 0 只需确认数据库可连接。

#### 5. Neo4j 初始化

```bash
# 浏览器打开 http://localhost:7474
# 首次登录：用户名 neo4j，密码 neo4j，按提示修改密码
```

> 图谱数据由数据组 Phase B 导入，Phase 0 只需确认 Neo4j 服务运行中。

---

### 全员 · 启动验证

按角色执行对应命令，确认输出无报错：

```bash
# ===== 后端（全员可跑） =====
conda activate truthnet
python scripts/doctor.py                   # 环境检测
python -m pytest backend/tests -v          # 现有测试（29 个）

# ===== 后端 · 启动服务 =====
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# 浏览器打开 http://localhost:8000/docs 看到 Swagger 页面

# ===== 前端 =====
cd frontend
pnpm install
pnpm build && pnpm typecheck              # 构建 + 类型检查
pnpm dev                                   # 启动开发服务器（默认 http://localhost:5173）
```

---

### Phase A 交接约定

| 交接物 | 产出方 | 接收方 | 方式 |
|------|:--:|:--:|------|
| OpenAPI 3.1 YAML | 后端组 | 前端组 | 提交到代码仓库 `docs/openapi.yaml`，前端 `git pull` 后从该文件生成类型 |
| WS 事件 Schema（JSON） | 后端组 | 前端组 | 同上，提交到 `docs/ws-events.json` |
| 字段映射表 | 数据组 | 后端组 | 提交到代码仓库 `docs/FIELD_MAPPING.md` |
| `RULES_SPEC.md` | 数据组 | 后端组 | 提交到代码仓库 `docs/RULES_SPEC.md` |

> 原则：**所有交接物通过代码仓库传递，不在微信里传文件。** 每组产出后 commit + push，别组 `git pull` 获取。

---

### 遇到问题找谁

| 问题类型 | 联系人 |
|------|------|
| Python/Conda 环境 | 后端组 |
| MySQL/Neo4j 安装 | 后端组 |
| 前端编译/依赖 | 前端组 |
| 数据文件路径/内容 | 数据组 |
| 设计文档理解 | 队长 |

---

### Phase 0 完成标志

```
✅ 每人能跑通 python scripts/doctor.py（或知道报错原因并在群里同步）
✅ 后端能启动 uvicorn 看到 Swagger 页面
✅ 前端能 pnpm dev 看到空白页面
✅ MySQL 能登入，Neo4j 浏览器能打开
✅ 数据组已将原始数据复制到位
✅ 各组知道 Phase A 自己该做什么、产出放哪
```

---

# Phase A · 契约统一（7/15-7/18，4天）

### 阶段目标

> **三组对接口格式达成完全一致，后端产出可生成类型的 OpenAPI/WS Schema，前端按 Schema 生成类型文件并通过验证。**

---

### 前端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 从后端生成的 OpenAPI YAML/JSON 生成 TypeScript 类型 | `api/generated/` 目录 | `pnpm typecheck` 无报错 |
| 2 | 按 V11 §5 的 ViewModel 定义手写前端专用类型（PanelData/MessageView 等） | `types/view-model.ts` | 对照 V11 附录A 字段一一检查 |
| 3 | Mock JSON 文件按 V11 §11 响应格式编写（每个 P0 端点 1 份） | `mocks/` 目录下 10+ 个 JSON 文件 | 用 JSON Schema 校验通过 |
| 4 | 三页面骨架按 V11 §5.1-5.4 的桌面端 ASCII 搭建静态布局 | 三个页面路由可访问 | `pnpm build` 通过，浏览器无明显布局错误 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| OpenAPI 3.1 YAML | 后端组 | 待接收 |
| WS 事件 Schema | 后端组 | 待接收 |

---

### 后端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 按 V11 §11.2 定义全部 Pydantic DTO（Request/Response）+ FastAPI Router 骨架 | `backend/app/api/v1/schemas/` | OpenAPI 3.1 JSON/YAML 能由 FastAPI 自动生成 |
| 2 | 按 V11 §12 定义 WS 事件 Schema（Client→Server + Server→Client） | `backend/app/api/v1/schemas/ws_events.py` | JSON Schema 可导出，事件名与 V11 §12.2-12.3 一致 |
| 3 | 实现 §11.16 兼容路由转发（旧路径 `/api/search` → `/api/v1/companies` 等） | `backend/app/api/v1/compat.py` | 旧路径返回 301 + `Deprecation` header |
| 4 | 按 V11 §7.3 定义 AgentState + LangGraph 空图骨架 | `backend/app/agents/state.py` + `graph.py` | `graph.invoke({"user_query": "test"})` 不报错，State 各字段能读写 |
| 5 | 错误处理骨架：按 V11 §11.6 RFC 9457 格式 + V11 §11.5 部分成功格式 | `exception_handlers.py` | 故意触 400 → 返回 `{type, title, status, detail, error_code, trace_id}` |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 无外部依赖 | — | — |

---

### 数据组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 对照 V11 §10.4-10.8 确认 MySQL 表结构字段→三表 CSV 列映射 | 映射表文档 | 每个字段能找到 CSV 来源列名 |
| 2 | 确认 `statement_type=408006000` 数据量、时间范围、字段覆盖率 | 覆盖率报告初版 | 与 V11 §1.4 的数据规模核对，不一致之处记录 |
| 3 | 确认 Neo4j 实体对齐规则（`s_holder_aname` + `s_holder_sequence`） | 实体对齐脚本初步版本 | 跑 10 只股票，人工抽查节点没有明显重名误合并 |
| 4 | 规则公式从 `data-computation-checklist.md` 整理为统一格式（公式+阈值+适用条件+输入字段+输出字段） | `docs/RULES_SPEC.md` | 7 条规则都有完整五要素 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 三表/股东/公告/研报 CSV | `data/` 目录 | 已有 |

---

### 阶段标准与工具

| 类别 | 标准/工具 | 版本 | 用途 |
|------|------|------|------|
| API 契约 | OpenAPI | 3.1.x | REST 接口描述，FastAPI 自动生成 |
| WS 契约 | AsyncAPI 风格 | — | WebSocket 事件 Schema |
| HTTP 错误 | RFC 9457 Problem Details | — | 错误响应格式 |
| 前端类型 | openapi-typescript | 最新 | 从 OpenAPI 生成 TS 类型 |
| Python 校验 | Pydantic | V2 | DTO 定义 |
| 代码规范 | Ruff + Prettier | 最新 | 后端/前端格式化 |

---

### Phase A 实际结果

> （各组完成后填写）

| 组 | 完成情况 | 遇到的问题 | 解决方案 |
|------|:--:|------|------|
| 前端组 | | | |
| 后端组 | | | |
| 数据组 | | | |

---

# Phase B · 最小 E2E 打通（7/19-7/30，12天）

### 阶段目标

> **MySQL + Neo4j + DeepSeek 全部就位。搜索/画像/股权穿透/WS 对话可用。前端对接真实接口。"康美药业有造假风险吗"→ 编排调度 → 结构化 JSON → 前端完整展示。**

---

### 前端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | WebSocket 接入真实后端，按 V11 §5.9.2 Reducer 处理全部 10 种事件 | `api/websocket/reducer.ts` | 后端发真实事件序列，前端正确渲染每步状态 |
| 2 | 对话页完整实现：用户输入→模块进度→流式文本→结构化卡片→追问建议 | `/` 页面 | 能走完 V11 §12.5 完整时序，面板四模块+模块状态可见 |
| 3 | 面板实现六状态（empty→loading→partial→success→unavailable→failed） | `AnalysisPanel.tsx` | 6 种状态各 mock 一次，UI 有明显区分 |
| 4 | 多会话管理：新建/切换/删除/重命名，切换时面板跟随 | `SessionSidebar.tsx` | 创建 3 个会话各聊几句，来回切换数据不串 |
| 5 | 企业画像页对接真实 API，各区块独立 loading | `/company/:code` | 首屏先出摘要，各区块独立 loading 逐个出现 |
| 6 | 股权穿透图 D3 实现：拖拽/缩放/深度筛选/节点详情 | `EquityGraph.tsx` | 50+ 节点不卡，路径高亮正确 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 后端 WS 实时消息 | 后端组 Phase B | 待对接 |
| 后端 REST 接口 | 后端组 Phase B | 待对接 |

---

### 后端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | MySQL 数据库建表（按 V11 §10.4-10.8）+ Alembic 迁移脚本 | `infrastructure/persistence/mysql/` + `alembic/` | 7 张表创建成功，与 V11 字段定义对照一致 |
| 2 | Neo4j 图构建脚本（实体对齐 + 一致行动人合并 + 边创建） | `infrastructure/graph/neo4j/` | 走康美 wind_code → 输出控制链路径+权重 |
| 3 | ChromaDB 研报分块入库（按 V11 §10.11 metadata 规范） | `infrastructure/vector/chroma/` | collection 有数据，metadata 完整 |
| 4 | DeepSeek Provider 接入 | `infrastructure/llm/deepseek/` | 能正常调用 API 并 parse 结构化输出 |
| 5 | `/api/v1/companies?query=` 搜索接口 | REST 端点 | `curl` 查"康美"返回 2-5 个候选 |
| 6 | `/api/v1/companies/{code}` 画像摘要接口（`?include=` 可选） | REST 端点 | `curl` 康美返回基本信息+风险标签 |
| 7 | `/api/v1/companies/{code}/equity` 股权穿透接口 | REST 端点 | `curl` 返回 nodes+edges+paths |
| 8 | LangGraph 编排骨架：LoadContext→ResolveEntity→PlanModules→并行模块→返回 | `graph.py` | 输入"康美有风险吗"→State 走完整节点流转 |
| 9 | `/api/v1/chat/ws` WebSocket：处理 `chat.query` → 编排调度 → 返回 `answer.delta` + `artifact.upsert` + `turn.completed` | WS 端点 | 前端能连上并收到完整事件序列 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| MySQL 全量数据 | 数据组 Phase B | 待接收 |
| Neo4j 全量图谱 | 数据组 Phase B | 待接收 |
| ChromaDB 研报分块 | 数据组 Phase B | 待接收 |

---

### 数据组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | MySQL 环境搭建 + 全量数据入库（三表+公司+股东+公告+研报） | MySQL 全量数据库 | `SELECT COUNT(*)` 与原始 CSV 行数核对一致 |
| 2 | Neo4j 环境搭建 + 全量图谱构建（~6161 股，节点+边） | Neo4j 图数据库 | 按 `graph_version` 给版本号，关键股票抽样查询正确 |
| 3 | ChromaDB 研报摘要分块入库（按 V11 §10.11 metadata 规范） | ChromaDB collections | collection 有数据，metadata 含 `source_id/wind_code/embedding_model` |
| 4 | 公告情绪映射表（33 类 fcode→正/负/中性）写入 MySQL | announcements 表含 `sentiment` 字段 | 33 类全覆盖，分布合理 |
| 5 | 行业分类 akshare 补全，覆盖率写到 `companies.industry_source` | 覆盖率报告 | 补全后覆盖率 ≥90% |
| 6 | 康美药业全链路 Mock 数据（三表+股东+公告+研报，覆盖 3 个报告期） | `data/fixtures/kangmei.sql` | 字段与 V11 数据模型一致 |
| 7 | `RULES_SPEC.md` 初版（7 条规则的公式+阈值+适用条件），标注已确认/[推断] | `docs/RULES_SPEC.md` | 评审会上能逐条讲清楚计算逻辑 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| MySQL/Neo4j 环境 | 自建/Docker | 待就绪 |
| 原始 CSV 数据 | `data/raw/` | 已有 |

---

### 阶段标准与工具

| 类别 | 标准/工具 | 版本 | 用途 |
|------|------|------|------|
| 数据库 | MySQL | 8.0 | 全量结构化存储 |
| 图引擎 | Neo4j | 5.x | 持久化图谱查询 |
| 向量存储 | ChromaDB | 最新 | 研报/公告语义检索 |
| LLM | DeepSeek | V4 | 主用推理 |
| 嵌入模型 | BGE-small-zh-v1.5 | — | 中文向量化 |
| 数据迁移 | Alembic | 最新 | MySQL schema 管理 |
| 行业数据 | akshare | 最新 | 行业分类补全 |
| 前端 WS | WebSocket API | — | 浏览器原生 |
| D3 图谱 | D3.js | 7.x | 股权穿透图 |

---

### Phase B 实际结果

> （各组完成后填写）

| 组 | 完成情况 | 遇到的问题 | 解决方案 |
|------|:--:|------|------|
| 前端组 | | | |
| 后端组 | | | |
| 数据组 | | | |

---

# Phase C · 核心业务（7/31-8/9，10天）

### 阶段目标

> **7 条规则+舆情事件聚类+交叉验证+风险评分+证据链全部完成。全部 REST 端点可用。输入"康美有风险吗"→ 全量分析 → 前端完整展示，结论不把信号说成事实。**

---

### 前端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 画像页全部区块数据完整（基本信息/风险标签/财务规则/股权图/关联方/时间线/证据） | `/company/:code` | 查康美，7 个区块都有数据且无缺块 |
| 2 | 面板规则触发清单加入 Recharts 趋势折线图 | `RuleCard.tsx` | 触警规则显示近 4-8 期折线，hover 有值 |
| 3 | 舆情时间线（按 V11 §5.2.6 关系枚举渲染） | `RiskTimeline.tsx` | 6 种关系类型用不同线条/箭头区分 |
| 4 | 证据链区域完整实现（V11 §5.2.7：Claim 文本+来源+字段+版本+打开原文） | `EvidenceChain.tsx` | 每条证据至少展示 4 个字段 |
| 5 | 关联方风险表实现（V11 §5.2.5 九列）+ 点击聚焦图谱节点 | `RelatedPartyTable.tsx` | 点击行→图谱中对应节点高亮 |
| 6 | 跨公司对比页接入 `/api/v1/comparisons` | `/compare` | 选 3 家公司，指标表+风险并排正确 |
| 7 | 面板联动：点击规则卡→对话区滚动+证据区筛选+图谱节点高亮 | 面板+对话区联动 | 三项联动都生效，不跳白屏 |
| 8 | 无证据内容展示为解释/假设/追问建议（不与事实结论混排） | 全站展示逻辑 | 事实结论有来源链接，LLM 解释有"仅供参考"标识 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 交叉验证结果字段 | 后端组 Phase C | 待确认 |
| Claim/Evidence 结构化数据 | 后端组 Phase C | 待确认 |

---

### 后端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 财务勾稽 Agent 完整实现：7 条规则引擎 + LLM 解读 + 行业分位 | `agents/nodes/finance.py` | 查康美，返回 R1-R7 状态+当前值+历史+分位 |
| 2 | 舆情事件 Skill 完整实现：事件聚类+时间线+情绪统计+评级拐点 | `agents/nodes/events.py` | 查康美，输出时间线有 ≥3 个事件簇 |
| 3 | 交叉验证节点：三模块结果→时间对齐→信号组合→证据对比→冲突检测 | `agents/nodes/cross_validate.py` | 模拟财务异常→自动查股权+舆情，输出交叉信号 |
| 4 | Claim 生成 + 证据绑定：每项事实结论至少挂一个 EvidenceRef | `agents/nodes/build_claims.py` | 输出 Claim 列表中无空 `evidence_ids` |
| 5 | 问答生成 Agent：汇总→结构化 JSON→追问建议（基于缺失证据生成） | `agents/nodes/generate.py` | 追问建议与当轮结论相关，不固定模板 |
| 6 | 风险评分聚合：财务+股权+事件+评级→分级→标签→模式匹配 | `agents/nodes/risk.py` | `/api/v1/companies/{code}/risk` 返回完整字段 |
| 7 | 记忆 Agent：多轮上下文实体提取+指代消解 | `agents/nodes/memory.py` | 模拟 10 轮对话，"它""上次那家"正确消解 |
| 8 | `/api/v1/companies/{code}/finance` 端点 | REST | 对齐 V11 §11.10 格式 |
| 9 | `/api/v1/companies/{code}/events` 端点 | REST | 对齐 V11 §11.11 格式 |
| 10 | 全部端点的 `evidence_ids` 和 `claim_ids` 交叉引用可追踪 | 全局 | 通过 evidence_id 能找到对应 Claim，反之亦然 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 规则计算函数 | 数据组 Phase B | 待接收 |
| 造假模式库 | 数据组 Phase B | 待接收 |
| 事件聚类数据 | 数据组 Phase C | 待接收 |

---

### 数据组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 7 条规则 Python 计算函数（Phase A 公式→代码实现） | `backend/domain/finance/` 或独立脚本 | 挑 100 只股票跑一次，触发率分布合理 |
| 2 | 造假手法库初稿（金融侧给 3-5 条，含信号组合+模式名+典型公司） | `docs/FRAUD_PATTERNS.md` | 至少 2 条能被现有规则触发 |
| 3 | 事件时间线聚合脚本（LLM 跨公告聚类→事件簇→摘要） | `scripts/build_events.py` 或后端独立模块 | 挑公告≥10 条的公司，人工评判聚类合理性 |
| 4 | 研报评级拐点检测（同季度≥2 家下调→橙色预警） | 评级拐点数据写入 MySQL | 跑全量研报，统计触发次数分布 |
| 5 | 行业分位批量计算（每条规则指标 × 每个行业） | 分位数据写入 MySQL | 跑 10 个行业，分位分布合理 |
| 6 | 造假手法库 3 条能被真实数据触发 | 每条手法的触发案例截图 | 在数据里找到真实公司匹配 |
| 7 | 评测脚本初版（9 项指标自动化评测框架） | `tests/evaluation/` | 脚本能跑通不报错，输出占位评分表 |
| 8 | 白皮书 §1-4 初稿（背景/痛点/方案/架构） | Word 文档 | — |

---

### 阶段标准与工具

| 类别 | 标准/工具 | 版本 | 用途 |
|------|------|------|------|
| 证据模型 | V11 §9 EvidenceRef/Claim | — | 结构化证据 |
| 事件关系 | V11 §5.2.6 约束枚举 | — | temporal_precedes 等 6 种 |
| 风险等级 | V11 §5.7 red/orange/yellow/blue/green/unknown | — | 综合+分项 |
| 数据血缘 | W3C PROV 思想 | — | Entity/Activity/Agent |
| 编码规范 | Ruff + Pydantic 校验 | — | Claim 无空 evidence_ids |

---

### Phase C 实际结果

> （各组完成后填写）

| 组 | 完成情况 | 遇到的问题 | 解决方案 |
|------|:--:|------|------|
| 前端组 | | | |
| 后端组 | | | |
| 数据组 | | | |

---

# Phase D · 核心业务（8/3-8/9，7天）

### 阶段目标

> **7 条规则+舆情事件聚类+交叉验证+风险评分+证据链全部完成。输入"康美有风险吗"→ 全量分析 → 前端完整展示，且结论不把信号说成事实。**

---

### 前端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 面板联动：点击规则卡→对话区滚动+证据区筛选+图谱节点高亮（如有） | 面板+对话区联动 | 三项联动都生效，不跳白屏 |
| 2 | 舆情时间线（按 V11 §5.2.6 关系枚举渲染，非 `leads_to`） | `RiskTimeline.tsx` | 6 种关系类型用不同线条/箭头区分 |
| 3 | 证据链区域完整实现（按 V11 §5.2.7：Claim 文本+来源+字段+版本+打开原文） | `EvidenceChain.tsx` | 每条证据至少展示 4 个字段 |
| 4 | 关联方风险表实现（V11 §5.2.5 九列）+ 点击聚焦图谱节点 | `RelatedPartyTable.tsx` | 点击行→图谱中对应节点高亮 |
| 5 | 无证据内容展示为解释/假设/追问建议（不与事实结论混排） | 全站展示逻辑 | 事实结论有来源链接，LLM 解释有"仅供参考"标识 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 交叉验证结果字段 | 后端组 Phase D | 待确认格式 |
| Claim/Evidence 结构化数据 | 后端组 Phase D | 待确认格式 |

---

### 后端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 财务勾稽 Agent 完整实现：7 条规则引擎 + LLM 解读 + 行业分位 | `agents/nodes/finance.py` | 查康美，返回 R1-R7 状态+当前值+历史+分位 |
| 2 | 舆情事件 Skill 完整实现：事件聚类+时间线+情绪统计+评级拐点 | `agents/nodes/events.py` | 查康美，输出时间线有 ≥3 个事件簇 |
| 3 | 交叉验证节点：三模块结果→时间对齐→信号组合→证据对比→冲突检测 | `agents/nodes/cross_validate.py` | 模拟财务异常→自动查股权+舆情，输出交叉信号 |
| 4 | Claim 生成 + 证据绑定：每项事实结论至少挂一个 EvidenceRef | `agents/nodes/build_claims.py` | 输出 Claim 列表中无空 `evidence_ids` |
| 5 | 问答生成 Agent：汇总→结构化 JSON→追问建议（基于缺失证据生成） | `agents/nodes/generate.py` | 追问建议不固定模板，与当轮结论相关 |
| 6 | 风险评分聚合：财务+股权+事件+评级→分级→标签→模式匹配 | `agents/nodes/risk.py` | `/api/v1/companies/{code}/risk` 返回完整字段 |
| 7 | `/api/v1/companies/{code}/finance` 端点 | REST | 对齐 V11 §11.10 格式 |
| 8 | `/api/v1/companies/{code}/events` 端点 | REST | 对齐 V11 §11.11 格式 |
| 9 | 全部端点的 `evidence_ids` 和 `claim_ids` 交叉引用可追踪 | 全局 | 通过 evidence_id 能找到对应 Claim，反之亦然 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 规则计算函数 | 数据组 Phase C | 待接收 |
| 造假模式库 | 数据组 Phase C | 待接收 |
| 事件聚类数据 | 数据组 Phase C | 待接收 |

---

### 数据组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 事件时间线聚合脚本（LLM 跨公告聚类→事件簇→摘要） | `scripts/build_events.py` 或后端独立模块 | 挑公告≥10 条的公司，人工评判聚类合理性 |
| 2 | 研报评级拐点检测（同季度≥2 家下调→橙色预警） | 评级拐点数据写入 MySQL/Cache | 跑全量研报，统计触发次数分布 |
| 3 | 行业分位批量计算（每条规则指标 × 每个行业） | 分位数据写入 MySQL/Cache | 跑 10 个行业，分位分布合理 |
| 4 | 造假手法库 3 条能被真实数据触发 | 每条手法的触发案例截图 | 在数据里找到真实公司匹配 |
| 5 | 评测脚本初版（9 项指标自动化评测框架） | `tests/evaluation/` | 脚本能跑通不报错，输出占位评分表 |
| 6 | 白皮书 §1-4 初稿（背景/痛点/方案/架构） | Word 文档 | — |

---

### 阶段标准与工具

| 类别 | 标准/工具 | 版本 | 用途 |
|------|------|------|------|
| 证据模型 | V11 §9 EvidenceRef/Claim | — | 结构化证据 |
| 事件关系 | V11 §5.2.6 约束枚举 | — | temporal_precedes 等 6 种 |
| 风险等级 | V11 §5.7 red/orange/yellow/blue/green/unknown | — | 综合+分项 |
| 数据血缘 | W3C PROV 思想 | — | Entity/Activity/Agent |
| 编码规范 | Ruff + Pydantic 校验 | — | Claim 无空 evidence_ids |

---

### Phase D 实际结果

> （各组完成后填写）

| 组 | 完成情况 | 遇到的问题 | 解决方案 |
|------|:--:|------|------|
| 前端组 | | | |
| 后端组 | | | |
| 数据组 | | | |

---

# Phase E · 稳定联调（8/10-8/14，5天）

### 阶段目标

> **前后端完全对接，错误场景+降级全覆盖，系统可部署可演示。评测脚本跑通第一轮。**

---

### 前端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 全部错误场景 UI 覆盖：404/429/500/LLM_TIMEOUT/GRAPH_UNAVAILABLE/partial | Toast + 模块内状态 | 后端逐个模拟错误→前端正确显示对应状态 |
| 2 | WebSocket 重连：断线 3s→自动重连→`stream.resume`→补发事件 | WS 重连逻辑 | 拔网线 10s 恢复后数据不丢 |
| 3 | 响应式补齐：平板侧边栏→左侧抽屉、面板→右侧抽屉；手机→单栏 | 断点实现 | 三种尺寸下无布局错位 |
| 4 | 报告任务页（`/reports/:reportId`）实现：创建→轮询状态→进度→下载 | `/reports/:reportId` | 发起报告→看到进度条→下载文件 |
| 5 | UI 打磨：动画（打字机/进度条过渡）、文案统一、间距对齐 | 全站 | 3 人过一遍无明显不适 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 降级模块状态标识 | 后端组 Phase E | 待确认 |
| 报告长任务端点 | 后端组 Phase E | 待确认 |

---

### 后端组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 超时与降级：每个模块设 deadline，超时→返回 warning+partial | `application/services/deadline.py` | 分别停 MySQL/Neo4j/ChromaDB/LLM，每次前端不崩溃 |
| 2 | 降级验证：LLM 不可用→模板化回答、ChromaDB 不可用→结构化过滤、外部服务故障→返回已有结果 | 降级测试用例 | 每级降级 3s 内完成，warnings 正确区分原因 |
| 3 | 幂等：`task_key` 重复提交→返回已有结果 | `application/services/idempotency.py` | 同一问题发 3 次→后端只执行 1 次 |
| 4 | WebSocket 重连恢复：按 `last_received_sequence` 补发事件 | WS 恢复逻辑 | 模拟断线→重连→补事件→事件不重复不丢失 |
| 5 | 全部接口性能达标（V11 §13.1 目标） | — | `time curl` 逐端测 |
| 6 | PDF 报告长任务：创建→后台生成→状态查询→下载 | `/api/v1/reports` 系列 | 创建返回 202，查状态返回百分比，下载返回 PDF |
| 7 | 部署：Docker Compose（FastAPI + MySQL + Neo4j + ChromaDB）+ README | `docker-compose.yml` + `README.md` | 另一人按步骤操作能跑通 |

| 输入依赖 | 来源 | 状态 |
|------|:--:|:--:|
| 评测脚本反馈的 bug | 数据组 Phase E | 待接收 |

---

### 数据组

| # | 任务 | 交付物 | 验收标准 |
|:-:|------|------|------|
| 1 | 评测脚本完整实现：跑 77 道深度题 + 多轮 QA → 输出 9 项指标 | `tests/evaluation/` | 输出表含 Recall/准确率/F1/延迟/盲评率 等 |
| 2 | 第一轮评测：记录原始成绩 + 与目标差距 | 评测报告 v1 | 指标项+当前值+目标值+差距 |
| 3 | 白皮书 §5-8 初稿（功能实现/评测/总结/参考文献） | Word 文档 | — |

---

### 阶段标准与工具

| 类别 | 标准/工具 | 版本 | 用途 |
|------|------|------|------|
| 部署 | Docker Compose | 最新 | 一键启动全部服务 |
| 性能目标 | V11 §13.1 | — | Chat 首字≤3s、完整≤8s、搜索≤500ms |
| 评测指标 | 赛题 9 项 | — | Recall≥90%、F1≥85%… |
| 降级验证 | V11 §13.4 | — | LLM→模板、ChromaDB→结构化过滤 |

---

### Phase E 实际结果

> （各组完成后填写）

| 组 | 完成情况 | 遇到的问题 | 解决方案 |
|------|:--:|------|------|
| 前端组 | | | |
| 后端组 | | | |
| 数据组 | | | |

---

# Phase F · 交付（8/15-8/20，6天）

### 阶段目标

> **评测跑出最终成绩，全部交付物打包：源码+部署说明+白皮书+PPT+演示视频。**

---

### 全员任务

| # | 任务 | 负责 | 交付物 | 验收标准 |
|:-:|------|:--:|------|------|
| 1 | 最终评测跑分 | 数据组 | 评测报告终版 | 9 项指标全部有数值，与目标对照 |
| 2 | 根据评测结果调优 | 后端组+数据组 | 阈值/规则微调 | 跑两轮评测，成绩上升或持平 |
| 3 | Bug 修复 | 后端组+前端组 | — | 已知 bug 清零 |
| 4 | 演示部署验证（外网可访问） | 后端组 | 公网 IP/域名 | 手机 4G 网络能打开 |
| 5 | 白皮书终稿（排版+校对+参考文献） | 数据组 | PDF/Word | 格式统一，无错别字 |
| 6 | PPT 终稿（15-20 页） | 数据组+队长 | PPTX | 逻辑通顺，每页 ≤50 字 |
| 7 | 答辩预演 | 全员 | — | 15 分钟讲完不超时 |
| 8 | 演示视频录制 | 前端组 | MP4 | 5 分钟，含操作+画外音解说 |
| 9 | 源码打包（含 README/Docker 部署说明） | 后端组+前端组 | ZIP | 另一人能解压跑起来 |
| 10 | 最终检查：所有交付物齐全 | 队长 | 交付清单 | — |

---

### Phase F 实际结果

| 组 | 完成情况 | 遇到的问题 | 解决方案 |
|------|:--:|------|------|
| 全员 | | | |

---

# 汇总

## 各阶段标准与工具总览

| Phase | 前端 | 后端 | 数据 |
|:--:|------|------|------|
| A | openapi-typescript, Prettier | FastAPI, Pydantic V2, OpenAPI 3.1, RFC 9457 | 数据字段映射, `RULES_SPEC.md` |
| B | WebSocket API, D3.js | MySQL 8.0, Neo4j 5.x, ChromaDB, DeepSeek V4, LangGraph | MySQL 全量入库, Neo4j 全量图, 行业补全, 康美 fixture |
| C | 面板联动, 证据展示, Recharts | 7 规则引擎, 交叉验证, Claim/Evidence, 风险评分 | 事件聚类, 评级拐点, 分位计算, 造假模式库, 评测框架 |
| D | 错误状态, 重连, 响应式, 报告页 | 降级, 幂等, 性能, PDF, Docker | 评测脚本, 白皮书 |
| E | 视频录制, 打磨 | Bug 修复, 部署 | 跑分, 白皮书终稿, PPT |

## 交付物清单（最终提交）

| # | 交付物 | 形式 | 负责 |
|:--:|------|------|:--:|
| 1 | 源码 | ZIP + GitHub | 后端组+前端组 |
| 2 | 部署说明 | README.md | 后端组 |
| 3 | 技术白皮书 | PDF | 数据组 |
| 4 | 答辩 PPT | PPTX | 数据组+队长 |
| 5 | 演示视频 | MP4（5 分钟） | 前端组 |
| 6 | 评测成绩表 | Excel/Markdown | 数据组 |

---

> 本文档随开发推进持续更新。各 Phase 结束后组长汇总"实际结果"列，作为白皮书素材和答辩支撑材料。
>
> 最后更新：2026-07-15
