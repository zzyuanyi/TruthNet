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

## 新成员最短启动流程

```bash
# 1. 克隆仓库
git clone https://github.com/zzyuanyi/TruthNet.git
cd TruthNet

# 2. 创建 conda 环境
conda create -n truthnet python=3.11 -y
conda activate truthnet
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env, 设置 TRUTHNET_PROFILE=lite

# 4. 验证环境
python scripts/doctor.py
python scripts/verify_v12_stack.py
python scripts/verify_full_stack.py --profile lite

# 5. 运行测试
python -m pytest backend/tests -v
ruff check . && ruff format --check .

# 6. 启动后端
uvicorn backend.app.main:app --reload
# → http://127.0.0.1:8000/healthz
# → http://127.0.0.1:8000/api/v1/companies?query=茅台
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
