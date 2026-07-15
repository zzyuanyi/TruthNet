# CLAUDE.md — TruthNet 开发上下文

## 一句话目标

织网鉴真：面向个人投资者的财报反欺诈智能问答系统，支持长上下文推理、股权穿透、舆情溯源与可解释财务勾稽。

## 设计文档

> 设计方案、API 契约、数据模型、开发计划等权威文档在竞赛管理仓库，不在本仓库。

| 文档 | 路径 | 用途 |
|------|------|------|
| **综合设计方案 V11** | `../竞赛管理/docs/design/TruthNet_综合设计方案_V11.md` | 产品、前端、Agent、数据、API、工程统一基线 |
| **开发实践手册** | `../竞赛管理/docs/开发实践手册.md` | 每阶段每组任务、交付物、验收标准 |
| **数据文档** | `../竞赛管理/data/README.md` | 数据目录、字段说明、覆盖率 |
| **规则公式** | `../竞赛管理/docs/design/data-computation-checklist.md` | 7 条勾稽规则公式+阈值+字段 |

## 当前状态（V11 基线 · 2026-07-15）

- 设计文档 V11 定稿，API 契约、WS 事件、Evidence/Claim 模型已冻结
- Phase A 契约统一阶段（7/15-7/18）：后端产出 OpenAPI，前端生成类型
- 后端：FastAPI 骨架就绪，29/29 测试通过，需按 V11 重构 Pydantic DTO 和 API 路径
- 前端：React + Vite + TypeScript 最小项目已初始化，`pnpm build` 通过
- 协作：`main ← PR ← feature/<user>-<task>`

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Python 3.11 / FastAPI / WebSocket | REST + WS 统一入口 |
| Agent 编排 | LangGraph StateGraph | 条件路由、并行节点、checkpoint 持久化 |
| 结构化存储 | MySQL 8.0 | 三表+公司+股东+公告+研报 |
| 图存储 | Neo4j 5.x | 股权穿透、关联方查询 |
| 向量存储 | ChromaDB | 研报/公告语义检索 |
| 嵌入模型 | BGE-small-zh-v1.5 | 中文向量化 |
| LLM | DeepSeek V4（主）/ Qwen（备） | Provider 模式，不绑定单一模型 |
| 数据契约 | Pydantic V2 | API、Agent State、Port 边界 |
| 前端 | React 18 / Vite / TypeScript 5 | shadcn/ui + Tailwind CSS |
| 图表 | Recharts | 财务趋势、行业分位 |
| 图谱 | D3.js | 股权穿透图 |
| 测试 | pytest / Ruff / pre-commit / CI | PR 合并门禁 |
| 协作 | Git / GitHub / Claude Code | |

## 目录结构

```
TruthNet/
  README.md
  CLAUDE.md              — 本文档
  requirements.txt       — 唯一 Python 依赖文件（== 固定版本）
  .python-version        — Python 3.11
  .gitignore
  .gitattributes         — LF 强制
  .editorconfig
  .pre-commit-config.yaml
  .env.example           — 环境变量模板

  backend/
    app/
      main.py            — FastAPI 入口
      api/v1/
        routers/         — REST 路由
        schemas/         — Pydantic DTO（Request/Response/WS 事件）
        dependencies.py
        exception_handlers.py
      application/
        use_cases/       — 业务用例
        ports/           — Port 接口
        dto/             — 应用层 DTO
      domain/
        company/         — 公司模型
        finance/         — 财务规则
        equity/          — 股权模型
        events/          — 舆情事件
        risk/            — 风险评分
        evidence/        — Claim/Evidence
        conversation/    — 会话模型
      agents/
        graph.py         — LangGraph 编排定义
        state.py         — AgentState（TypedDict）
        reducers.py      — 自定义 Reducer
        nodes/           — 各节点实现
      infrastructure/
        persistence/mysql/     — MySQL 实现
        graph/neo4j/           — Neo4j 实现
        vector/chroma/         — ChromaDB 实现
        llm/deepseek/          — DeepSeek Provider
        llm/qwen/              — Qwen Provider（备选）
        external/akshare/      — 外部数据
        reporting/             — PDF 报告
      core/
        config.py
        enums.py
        errors.py
    tests/
      unit/ contract/ integration/ websocket/

  frontend/
    src/
      app/
      pages/              — 对话主页 / 企业画像页 / 对比页 / 报告页
      components/ui/      — shadcn/ui 基础组件
      components/chat/    — 对话区、输入框、模块进度
      components/analysis/— 分析面板、规则卡
      components/company/ — 股权图、关联方表、时间线、证据链
      components/compare/ — 跨公司对比
      components/report/  — 报告状态页
      api/generated/      — OpenAPI 自动生成类型
      api/websocket/      — WS 客户端和 Reducer
      state/              — 状态管理
      types/              — 前端 ViewModel 类型
      mocks/              — Mock JSON

  data/
    raw/                  — 原始数据（不提交）
    canonical/            — 标准化数据（不提交）
    fixtures/             — 测试用 fixture

  docs/
    ARCHITECTURE.md
    API_CONTRACT_V1.md
    WEBSOCKET_CONTRACT_V1.md
    RULES_SPEC.md
    ADR/

  scripts/
    doctor.py             — 跨平台环境检测
    encoding_path_audit.py— 编码/路径审计
    git_safety_check.py   — Git 安全检查

  .github/workflows/ci.yml
```

## 开发总规则

### 编码与路径

1. 全项目文本文件 UTF-8，LF 换行。
2. Python 文件读写文本必须显式 `encoding="utf-8"`。
3. 路径使用 `pathlib.Path`。
4. 禁止硬编码盘符、用户名、绝对路径。
5. 写入文件时使用 `newline="\n"` 确保 LF。

### Git 协作

6. **Claude Code 不得自动 commit/push/merge。**
7. 每位开发者创建自己的分支：`feature/<github-username>-<module>`
8. 从 main 拉最新代码 → 创建分支 → 自由开发 → 向 main 提 PR → 专人 merge
9. 个人化内容不提交；共同开发可复用内容才提交。
10. main 受保护，合并必须通过 PR。
11. **每次 push 后必须检查 CI 状态**：如果 CI 失败，Claude Code 必须读取失败日志并给出修复建议。不得在 CI 失败时声称任务完成。
12. Claude Code 不得自动 merge PR，不得直接向 main push。

### 接口与架构

13. **接口先行**：Pydantic schema → OpenAPI 文档 → Mock JSON → 实现。
14. **API 路径统一 `/api/v1`**，响应格式 `{ data, meta, warnings }`。
15. **WS 事件统一信封**：`{ schema_version, event_id, event_type, session_id, turn_id, sequence, timestamp, trace_id, payload }`。
16. **单一 requirements.txt**：所有包用 `==` 固定版本。
17. **密钥不提交**：`.env` 在 `.gitignore`，只提交 `.env.example`。
18. **Pydantic schema 是后端接口事实来源**。
19. **前端类型优先由 OpenAPI/事件 Schema 生成**，手写类型仅用于 ViewModel。
20. **Evidence 强制追溯**：每条 Claim 至少挂一个 EvidenceRef，LLM 不得编造 evidence_id。

### 环境

21. **每人本地安装 MySQL 8.0 + Neo4j 5.x**，连接配置写入本地 `.env`。
22. 无 conda 时提供安全安装引导，不得无确认自动下载安装器。
23. 镜像/代理配置只保存在本地，不写入仓库。

## Claude Code 工作规则

- 动手前先读竞赛管理仓库的 V11 相关章节 + 本仓库 `docs/` 下对应文档。
- 先计划再改文件。
- 每次改动后运行：`python scripts/doctor.py` 或 `python -m pytest backend/tests`。
- 不要跳过失败测试，不要删除重要逻辑。
- 不要把本地路径、密钥、代理地址写死进任何代码。
- 不要在 `main.py` 中堆砌业务逻辑。
- **不要自动执行 git commit、git push、git merge、gh pr create。**
- **当用户要求提交、push 或修复 CI 时，必须在 push 后主动检查 GitHub Actions 状态。**

## 常用命令

```bash
# ===== 环境 =====
conda activate truthnet
pip install -r requirements.txt

# ===== 检查 =====
python scripts/doctor.py
python scripts/encoding_path_audit.py
python scripts/git_safety_check.py
python -m pytest backend/tests -v
pre-commit run --all-files

# ===== 后端 =====
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# ===== 前端 =====
cd frontend && pnpm install && pnpm dev
cd frontend && pnpm build && pnpm typecheck

# ===== 代码质量 =====
ruff check backend/
ruff format backend/
```

## 分支与提交规范

### 分支模型

```
main ← Pull Request ← feature/<github-username>-<task>
                     ← fix/<github-username>-<bug>
                     ← docs/<github-username>-<topic>
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
4. `python -m pytest backend/tests -v`
5. `cd frontend && pnpm build`
6. `pre-commit run --all-files`

### 禁止事项

- 禁止直接 push 到 `main`
- 禁止提交 `.env`、数据库文件、模型权重、大文件
- 禁止不看 diff 就全量提交
- **禁止 Claude Code 自动 commit/push/merge**
