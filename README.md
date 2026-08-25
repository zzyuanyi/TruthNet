# TruthNet — 织网鉴真

面向个人投资者的财报反欺诈智能问答系统。基于 Agentic AI，支持金融长上下文推理、股权穿透、舆情事件溯源、财报跨科目勾稽与可解释问答。

> **当前基线**: V12 (2026-07-17) · 设计文档: `TruthNet_综合设计方案_V12(2).md`
> CI 状态: [![CI](https://github.com/zzyuanyi/TruthNet/actions/workflows/ci.yml/badge.svg)](https://github.com/zzyuanyi/TruthNet/actions/workflows/ci.yml)

## 核心能力

- **长上下文问答**：0.5M+ Tokens 上下文窗口，10 轮以上对话关键事实召回
- **股权穿透**：多跳链路分析，深度 >3 层，真实控制关系识别
- **舆情溯源**：事件簇聚合与时间线构建
- **财报勾稽**：跨科目预警，输出数据对比与可能造假模式
- **可解释输出**：每条结论附带证据链、图谱可视化、风险评分

## 技术架构 (V12)

| 层级 | 技术选型 | Profile |
|------|----------|:---:|
| 后端框架 | Python 3.11 / FastAPI / WebSocket | 通用 |
| Agent 编排 | LangGraph StateGraph | 通用 |
| 数据验证 | Pydantic V2 | 通用 |
| 关系数据库 | MySQL 8.4 (full) / SQLite (lite) | 双模式 |
| ORM & 迁移 | SQLAlchemy 2.0 + Alembic | 通用 |
| 图数据库 | Neo4j 2025.06 (full) / NetworkX (lite) | 双模式 |
| 向量检索 | ChromaDB 0.5.23 persistent | 通用 |
| LLM Provider | DeepSeek (主) / Qwen (备) / Mock (lite) | Adapter |
| 前端 | React 18 / Vite 6 / TypeScript 5.6 | 通用 |
| UI 组件 | shadcn/ui + Tailwind CSS | 🔸 待接入 |
| 图表 | Recharts | 🔸 待接入 |
| 图谱可视化 | D3.js | 🔸 待接入 |
| 测试 | pytest / Ruff / pre-commit / CI (3 OS) | 通用 |

## 新成员最短启动流程（Current · V13 织网鉴真）★ 看这一段即可跑起来

> 一套代码双运行：**沙箱（Coze）** 与 **本地自搭** 都能跑，区别只有一节「联网搜索」。以下以本地为主讲。

### 1. 环境要求

| 项 | 版本 | 说明 |
|---|---|---|
| Node.js | ≥ 20 | 前端 |
| pnpm | 任意较新 | **必须用 pnpm**，禁用 npm/yarn |
| Python | 3.11+ | 后端 |
| SQLite | 内置 | 无需装数据库服务，`data/*.db` 即库 |

### 2. 后端（1 分钟，零配置）

```bash
cd backend
pip install -r requirements.txt          # 依赖清单（约 14 项）
python scripts/seed_db.py                # 一键灌演示数据（康美画像 + 6 簇舆情），库存在则自动跳过
python -m uvicorn app.main:app --app-dir backend --port 8000
```

- 健康检查：`curl http://127.0.0.1:8000/healthz`
- 样例接口：`curl "http://127.0.0.1:8000/api/v1/companies?query=康美"`
- **演示数据**：不含 seed 时画像页是空壳。`seed_db.py` 会从 `data/fixtures/truthnet_seed.sqlite.sql` 重建 `data/truthnet.db`，包含：康美药业完整画像、财务异常规则、股权穿透（上下穿透 + 风险着色）、2018-10 存货质疑 → 2019-08 顶格处罚的 6 簇舆情时间线。测试验收用它。

### 3. 前端（1 分钟，零配置）

```bash
cd ../frontend
pnpm install
pnpm dev                                   # http://localhost:5173（或 .coze 指定端口）
```

- **前后端自动打通**：`vite.config.ts` 已把 `/api/v1` 代理到 `http://127.0.0.1:8000`，本地后端跑在 8000 即可直接用，无需再配。
- **默认主题**：深色 + 中字号，可在右上角设置切换。

### 4. 即插即用（clone 后就能看到效果）vs 需操作

| 功能 | 状态 | 说明 |
|---|---|---|
| 智能问答（本地可跑） | 🟢 即插即用 | 底层走 SQLite + 内置规则 |
| 企业画像 / 股权穿透 / 舆情时间线 | 🟢 即插即用 | `seed` 已灌好康美演示数据 |
| 全球舆情脉搏（地球 + 10min 爬取） | 🟢 即插即用 | 首次启动后约 10 分钟爬到首批 RSS（CNBC/华尔街见闻等） |
| **联网深挖**（点国家亮点实时搜） | 🟡 需配置 Key | 见下节 |
| 聪明问答·大模型生成式回答 | 🟡 需配置 Key | 沙箱内置；本地需配 LLM Key |

### 5. 联网搜索的两种模式（唯一环境差异）

- **网站沙箱（Coze）**：免 Key，`coze_coding_dev_sdk`（沙箱预置）自动启用，联网深挖开箱即用。
- **本地自搭**：该 SDK 是沙箱预置包（PyPI 无），自动降级关闭**不影响其余功能**；如需联网深挖，`.env` 里设：
  ```bash
  cp .env.example .env
  WEB_SEARCH_BACKEND=bocha     # 需 BOCHA_API_KEY
  ```
  可选值：`off`（默认）/ `mock` / `bocha` / `coze`。

### 6. 环境变量样板（`.env`）

```bash
cp .env.example .env                    # 默认值可零改动直接跑
TRUTHNET_PROFILE=full                   # 沙箱用 full / lite
WEB_SEARCH_BACKEND=off                  # 本地默认关闭，演示时按需开
```

### 7. 验证口令

```bash
# 后端
curl http://127.0.0.1:8000/api/v1/market-pulse        # 全球舆情（含 clusters）
curl "http://127.0.0.1:8000/api/v1/companies/600518.SH/equity"  # 股权穿透
# 前端浏览器
http://localhost:5173/company/600518.SH               # 康美画像直达
```

## Lite vs Full Profile

| 维度 | Lite (默认) | Full |
|------|------------|------|
| 数据库 | SQLite | MySQL 8.4 |
| 图分析 | NetworkX (内存) | Neo4j 2025.06 |
| 向量库 | ChromaDB local | ChromaDB persistent |
| LLM | Mock | DeepSeek / Qwen |
| 外部服务 | 不需要 | 需要 MySQL + Neo4j + JDK 21 |
| CI | ✅ 自动运行 | 需显式启用 |
| 适用场景 | 日常开发、CI | 正式演示、全量测试 |

Full profile 部署详见 [docs/SETUP_FULL_PROFILE_WINDOWS.md](docs/SETUP_FULL_PROFILE_WINDOWS.md)。

## 开发会话流程

```bash
# 开始开发
python scripts/start_session.py

# 结束开发
python scripts/end_session.py
```

## 提交前检查

```bash
python scripts/doctor.py
python scripts/encoding_path_audit.py
python scripts/git_safety_check.py
python -m pytest backend/tests -v
ruff check . && ruff format --check .
pre-commit run --all-files
cd frontend && pnpm build
```

## Full Profile 验证

```bash
# 一键启动开发/演示环境（MySQL/Neo4j + 后端 + 前端）
powershell -ExecutionPolicy Bypass -File scripts/services/start_dev.ps1
# 停止前后端（MySQL/Neo4j 保持运行）
powershell -ExecutionPolicy Bypass -File scripts/services/stop_dev.ps1

# 启动服务
powershell -File scripts/services/start_full_stack_dev.ps1

# 验证
python scripts/verify_full_stack.py --profile full --check-external --write-smoke --cleanup

# 外部集成测试
$env:TRUTHNET_RUN_EXTERNAL_TESTS="1"
python -m pytest backend/tests/integration -v -m "integration and external"
```

## 目录结构 (V12)

```text
TruthNet/
  README.md                    — 本文件
  CLAUDE.md                    — AI 开发上下文
  requirements.txt             — 唯一 Python 依赖 (25 包, 全部 == 固定)
  .python-version              — Python 3.11
  alembic.ini                  — Alembic 迁移配置

  backend/app/
    main.py                    — FastAPI 入口 (HTTP + WebSocket)
    api/v1/                    — V12 路由层 (routers / schemas / deps)
    application/               — 应用层 (use_cases / ports / services / dto)
    domain/                    — 领域层 (company / finance / equity / events / risk / evidence / conversation)
    agents/                    — LangGraph Agent (state / graph / reducers / nodes)
    infrastructure/            — 基础设施层
      persistence/sqlite/      — SQLite Adapter (lite)
      persistence/mysql/       — MySQL Adapter (full)
      persistence/migrations/  — Alembic 迁移
      graph/networkx/          — NetworkX Adapter (lite)
      graph/neo4j/             — Neo4j Adapter (full)
      vector/chroma/           — ChromaDB Adapter
      llm/mock/                — Mock LLM Provider
      llm/deepseek/            — DeepSeek Provider (full)
      llm/qwen/                — Qwen Provider (full)
      observability/           — 日志 / 追踪 / 指标
    core/                      — 配置 / 枚举 / 错误模型
    schemas/                   — 旧 Pydantic Schema (兼容保留)

  backend/tests/
    unit/                      — 单元测试
    contract/                  — Port / API / OpenAPI 契约测试
    integration/               — 外部服务集成测试 (需显式启用)
    websocket/                 — WebSocket 测试

  frontend/                    — React 前端 (Vite + TypeScript)
  docs/                        — 项目文档
  scripts/                     — 工具脚本
  reports/                     — 各阶段报告
  .github/workflows/ci.yml    — CI (Python 3.11 × 3 OS + 前端)
  .claude/skills/              — Claude Code skills (8 个, 已更新 V12)
```

## 编码规范

1. 全项目文本文件 UTF-8 + LF 换行
2. Python 文件读写必须 `encoding="utf-8"`
3. 路径必须使用 `pathlib.Path`
4. 禁止硬编码盘符、用户名、绝对路径
5. 脚本入口必须有 Windows UTF-8 输出保护

## Git 协作 (V12)

```text
main ← Pull Request ← 个人分支 (feature/fix/docs/chore/用户名-任务)
```

| ❌ 禁止 | ✅ 必须 |
|---------|--------|
| Claude Code 自动 commit | 用户确认后手动 commit |
| Claude Code 自动 push | 用户确认后手动 push |
| Claude Code 自动 merge | PR → review → merge |
| 直接 push 到 main | 个人分支 → PR → main |
| 提交 .env / 密钥 / 数据库 | 只提交 .env.example 模板 |
| CI 红叉时 merge | CI 绿后再 PR |

## 文档索引

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | V12 系统架构与 Agent 设计 |
| [API_CONTRACT_V1.md](docs/API_CONTRACT_V1.md) | REST API 契约 (18 端点) |
| [WEBSOCKET_CONTRACT_V1.md](docs/WEBSOCKET_CONTRACT_V1.md) | WebSocket 事件契约 |
| [DATA_CONTRACT.md](docs/DATA_CONTRACT.md) | 数据架构与存储契约 |
| [FRONTEND_DESIGN.md](docs/FRONTEND_DESIGN.md) | 前端页面与组件设计 |
| [ENVIRONMENT.md](docs/ENVIRONMENT.md) | 环境配置指南 |
| [SOFTWARE_ENGINEERING.md](docs/SOFTWARE_ENGINEERING.md) | 软件工程规范 |
| [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) | Git 协作流程 |
| [SETUP_LITE_PROFILE.md](docs/SETUP_LITE_PROFILE.md) | Lite Profile 快速开发 |
| [SETUP_FULL_PROFILE_WINDOWS.md](docs/SETUP_FULL_PROFILE_WINDOWS.md) | Full Profile Windows 部署 |
| [INTERFACE_CHANGELOG.md](docs/INTERFACE_CHANGELOG.md) | 接口变更历史 |

## 当前测试状态

| 类别 | 数量 | 结果 |
|------|:---:|:---:|
| 默认 pytest | 92 | ✅ passed |
| External integration (MySQL+Neo4j) | 8 | ✅ passed |
| verify_v12_stack.py | 12 | ✅ passed |
| verify_full_stack.py full | 25 | ✅ passed |
| ruff check | - | ✅ clean |
| ruff format | 113 files | ✅ formatted |
| pre-commit | 9 hooks | ✅ passed |

## 许可证

待定
