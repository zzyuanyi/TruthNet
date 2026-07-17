# CLAUDE.md — TruthNet 开发上下文

## 一句话目标

织网鉴真：面向个人投资者的财报反欺诈智能问答系统，支持长上下文推理、股权穿透、舆情溯源与可解释财务勾稽。

## 当前状态 (V12 Baseline · 2026-07-17)

**设计基线**: `TruthNet_综合设计方案_V12(2).md` (2026-07-15)

- 后端: FastAPI + LangGraph + Pydantic V2，V12 分层架构 (API/Application/Domain/Agent/Infrastructure)
- 数据库: MySQL 8.4 (full) + SQLite (lite)，SQLAlchemy + Alembic
- 图数据库: Neo4j 2025.06 (full) + NetworkX (lite)
- 向量库: ChromaDB 0.5.23 persistent
- LLM: Provider Adapter (DeepSeek/Qwen/Mock)
- 前端: React 18 + Vite 6 + TypeScript 5.6，`pnpm build` 通过
- 接口: `/healthz`, `/readyz`, `/api/v1/companies`, `POST /api/v1/chat`, `WS /api/v1/chat/ws`
- 响应格式: V12 envelope `{data, meta, warnings}` + RFC 9457 Problem Details
- WebSocket: V12 event envelope (turn.accepted / module.started / answer.delta / artifact.upsert / turn.completed / turn.failed / heartbeat)
- 测试: 92 pytest pass, ruff clean, pre-commit 9/9, external integration 8/8
- 协作: `main ← PR ← feature/<user>-<task>` 两层模型
- Profile: `TRUTHNET_PROFILE=lite|full` 双模式

## 赛题硬指标

- **0.5M+ Tokens** 上下文窗口，10 轮以上长对话关键事实召回
- **自适应 API/工具路由** 与自纠错
- **复杂股权穿透**：多跳链路，深度 >3 层
- **舆情事件簇聚合** 与时间线
- **财报跨科目勾稽**：输出预警点、数据对比、可能造假模式或业务风险
- 交付：源码、部署说明、Web 演示平台、技术白皮书、答辩 PPT

## 技术栈 (V12)

| 层级 | 技术 | Profile |
|------|------|:---:|
| 后端框架 | Python 3.11 / FastAPI / WebSocket | 通用 |
| Agent 编排 | LangGraph StateGraph | 通用 |
| 数据契约 | Pydantic V2 | 通用 |
| 对话记忆 | LangGraph checkpointer + ChromaDB 语义记忆 | 通用 |
| 财务勾稽 | 规则引擎 (7 条规则族) + Agent | 通用 |
| 图谱分析 | Neo4j 2025.06 (full) / NetworkX (lite) | 双模式 |
| 向量检索 | ChromaDB 0.5.23 persistent | 通用 |
| 关系数据库 | MySQL 8.4 (full) / SQLite (lite) | 双模式 |
| ORM & 迁移 | SQLAlchemy 2.0 + Alembic | 通用 |
| LLM Provider | DeepSeek (主) / Qwen (备) / Mock (lite) | Adapter |
| 前端 | React 18 / Vite 6 / TypeScript 5.6 | 通用 |
| UI | shadcn/ui + Tailwind CSS | 🔸 待接入 |
| 图表 | Recharts | 🔸 待接入 |
| 图谱可视化 | D3.js | 🔸 待接入 |
| 测试 | pytest / Ruff / pre-commit / CI (3 OS) | 通用 |
| 协作 | Git / GitHub / Claude Code | 通用 |

## 目录结构 (V12)

```text
TruthNet/
  README.md            — 项目介绍
  CLAUDE.md            — 本文档：AI 开发上下文
  requirements.txt     — 唯一 Python 依赖文件（固定版本，25 包）
  .python-version      — Python 3.11
  alembic.ini          — Alembic 迁移配置
  backend/
    app/
      main.py          — FastAPI 入口（HTTP + WebSocket · V12）
      api/v1/          — V12 路由层（routers / schemas / deps / exception_handlers）
      application/     — 应用层（use_cases / ports / services / dto）
      domain/          — 领域层（company / finance / equity / events / risk / evidence / conversation）
      agents/          — LangGraph Agent（state / graph / reducers / nodes）
      infrastructure/  — 基础设施层（persistence / graph / vector / llm / observability）
      schemas/         — 旧 Pydantic Schema（兼容保留 · Prompt4 冻结）
      core/            — 配置 / 枚举 / 错误模型
    tests/
      unit/            — 单元测试
      contract/        — Port / API / OpenAPI 契约测试
      integration/     — 外部服务集成测试（需显式启用）
      websocket/       — WebSocket 测试
  frontend/            — React 前端（Vite + TypeScript）
  docs/                — 项目文档（11 个 V12 文档）
  scripts/             — 工具脚本（含 verify_v12_stack / verify_full_stack / services）
  reports/             — 各阶段报告
  .github/workflows/ci.yml — CI（Python 3.11 × 3 OS + 前端）
  .claude/skills/      — 项目级 Claude Code skills（8 个, V12 已更新）
```

## 开发总规则

### 编码与路径

1. 全项目文本文件 UTF-8，LF 换行。
2. Python 文件读写文本必须显式 `encoding="utf-8"`。
3. Windows 控制台输出使用 `sys.stdout.reconfigure(encoding="utf-8")`。
4. 路径使用 `pathlib.Path`。
5. 禁止硬编码盘符、用户名、绝对路径。
6. 写入文件时使用 `newline="\n"` 确保 LF。

### Git 协作（V12）

7. **Claude Code 不得自动 commit/push/merge。**
8. 每位开发者创建自己的分支：`feature/<github-username>-<module>`
9. 从 main 拉最新代码 → 创建分支 → 自由开发 → 向 main 提 PR → 专人 merge
10. 每次开发会话开始：提示是否拉取远程 main 对齐。
11. 每次编辑完成后：展示改动，询问是否保存/提交。
12. 个人化内容不提交；共同开发可复用内容才提交。
13. main 受保护，合并必须通过 PR。
14. **每次 push 后必须检查 CI 状态**：如果 CI 失败，Claude Code 必须读取失败日志并给出修复建议或直接修复。不得在 CI 失败时声称任务完成。
15. Claude Code 不得自动 merge PR，不得直接向 main push。

### 接口与架构 (V12)

16. **接口先行**：Pydantic schema → 文档 → mock JSON → 实现。
17. **单一 requirements.txt**：所有包用 `==` 固定版本。
18. **密钥不提交**：`.env` 在 `.gitignore`，只提交 `.env.example`。
19. **Pydantic schema 是后端接口事实来源**。
20. **前端 types/api.ts 与 backend schema 严格一致**。
21. **接口一旦冻结，只能追加字段，不得删除/重命名**。
22. **V12 分层架构**：API → Application → Domain → Agent → Infrastructure (Port/Adapter)
23. **Profile 双模式**：lite (SQLite+NetworkX+Mock) / full (MySQL+Neo4j+DeepSeek)
24. **外部服务不阻塞 CI**：MySQL/Neo4j 测试需 `TRUTHNET_RUN_EXTERNAL_TESTS=1` 显式启用

### 虚拟环境

25. 无 conda 时提供安全安装引导，不得无确认自动下载安装器。
26. 镜像/代理配置只保存在本地，不写入仓库。

## Claude Code 工作规则

- 先读 `docs/` 下相关文档和 `backend/app/schemas/`，再写代码。
- 先计划再改文件。
- 每次改动后运行最小检查：`python scripts/doctor.py` 或 `python -m pytest backend/tests`。
- 不要跳过失败测试，不要删除重要逻辑。
- 不要把本地路径、密钥、代理地址写死进任何代码。
- 不要在 `main.py` 中堆砌业务逻辑。
- **不要自动执行 git commit、git push、git merge、gh pr create。**
- **当用户要求提交、push 或修复 CI 时，Claude Code 必须在 push 后主动检查当前分支的 GitHub Actions 状态。若 CI 失败，必须读取失败日志并给出修复建议或直接修复。不得在 CI 失败时声称任务完成。**

## 常用命令

```bash
# ===== 环境 =====
conda activate truthnet
pip install -r requirements.txt
python scripts/env_bootstrap.py --check
python scripts/doctor.py

# ===== V12 验证 =====
python scripts/verify_v12_stack.py
python scripts/verify_full_stack.py --profile lite
python scripts/verify_full_stack.py --profile full --check-external --write-smoke --cleanup

# ===== 检测 =====
python scripts/encoding_path_audit.py
python scripts/git_safety_check.py
ruff check . && ruff format --check .
python -m pytest backend/tests -v
pre-commit run --all-files

# ===== 后端 =====
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# ===== 前端 =====
cd frontend && pnpm install && pnpm dev
cd frontend && pnpm build && pnpm typecheck

# ===== Full Profile 外部测试 =====
$env:TRUTHNET_RUN_EXTERNAL_TESTS="1"
python -m pytest backend/tests/integration -v -m "integration and external"
```

## 分支与提交规范

### 分支模型（V12）

```text
main ← Pull Request ← feature/<github-username>-<task>
                     ← fix/<github-username>-<bug>
                     ← docs/<github-username>-<topic>
                     ← chore/<github-username>-<task>
```

### Conventional Commits
```
feat(scope): 描述
fix(scope): 描述
docs(scope): 描述
test(scope): 描述
refactor(scope): 描述
chore(scope): 描述
```

### 提交前检查清单
1. `git status` / `git diff` — 确认改动
2. `python scripts/doctor.py`
3. `python scripts/encoding_path_audit.py`
4. `python scripts/git_safety_check.py`
5. `python -m pytest backend/tests -v`
6. `cd frontend && pnpm build`
7. `ruff check . && ruff format --check .`
8. `pre-commit run --all-files`

### 禁止事项
- 禁止直接 push 到 `main`
- 禁止提交 `.env`、数据库文件、模型权重、大文件
- 禁止提交 `.local/` 目录内容
- 禁止不看 diff 就全量提交
- **禁止 Claude Code 自动 commit/push/merge**
