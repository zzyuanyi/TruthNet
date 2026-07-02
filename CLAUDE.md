# CLAUDE.md — TruthNet 开发上下文

## 一句话目标

织网鉴真：面向个人投资者的财报反欺诈智能问答系统，支持长上下文推理、股权穿透、舆情溯源与可解释财务勾稽。

## 当前状态 (Prompt4)

- 后端：FastAPI HTTP + WebSocket mock 端点就绪，29/29 测试通过
- 前端：React + Vite + TypeScript 最小项目已初始化，`pnpm build` 通过
- 接口：HTTP chat + WebSocket 已冻结为 MVP 稳定状态
- 协作：简化为 `main ← PR ← feature/<user>-<task>` 两层模型

## 赛题硬指标

- **0.5M+ Tokens** 上下文窗口，10 轮以上长对话关键事实召回
- **自适应 API/工具路由** 与自纠错
- **复杂股权穿透**：多跳链路，深度 >3 层
- **舆情事件簇聚合** 与时间线
- **财报跨科目勾稽**：输出预警点、数据对比、可能造假模式或业务风险
- 交付：源码、部署说明、Web 演示平台、技术白皮书、答辩 PPT

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.11 / FastAPI / WebSocket |
| Agent 编排 | LangGraph |
| 对话记忆 | LangGraph + 自定义 Memory Agent |
| 财务勾稽 | 自定义 Agent + 规则引擎 |
| 图谱分析 | NetworkX（MVP），后续可升级 Neo4j |
| 向量检索 | ChromaDB |
| 数据库 | SQLite（MVP） |
| 前端 | React 18 / Vite 6 / TypeScript 5.6 |
| 协作 | Git / GitHub / Claude Code |

## 目录结构

```text
TruthNet/
  README.md            — 项目介绍
  CLAUDE.md            — 本文档：AI 开发上下文
  requirements.txt     — 唯一 Python 依赖文件（固定版本）
  .python-version      — Python 3.11
  .gitignore
  .gitattributes       — 换行符 LF 强制
  .editorconfig        — 编辑器配置
  .pre-commit-config.yaml
  .env.example         — 环境变量模板
  backend/
    app/
      main.py          — FastAPI 入口（HTTP + WebSocket）
      api/             — 路由层
      agents/          — Agent 层（编排、记忆、勾稽、问答）
      skills/          — Skill 层（股权穿透、舆情事件等）
      services/        — 业务服务层
      schemas/         — Pydantic 数据契约（接口事实来源 · Prompt4 冻结）
      core/            — 配置、日志等
    tests/             — 后端测试
  frontend/            — React 前端（Vite + TypeScript · Prompt4 初始化）
    src/
      main.tsx
      App.tsx
      api/client.ts    — HTTP + WebSocket 客户端
      types/api.ts     — TypeScript 类型（与 backend schema 一致）
      components/      — ChatPanel, RiskPanel, EvidenceList, TimelinePanel, GraphPanel
  data/
    raw/               — 原始数据（不提交大文件）
    processed/         — 处理后数据（不提交大文件）
  docs/
    ARCHITECTURE.md
    ENVIRONMENT.md
    GIT_WORKFLOW.md
    API_CONTRACT.md
    DATA_CONTRACT.md
    INTERFACE_CHANGELOG.md
    SKILL_INDEX.md
    SOFTWARE_ENGINEERING.md
    adr/
  scripts/
    doctor.py               — 跨平台环境检测
    check_env.py            — 轻量环境检查
    encoding_path_audit.py  — 编码/路径审计
    git_safety_check.py     — Git 安全检查
    start_session.py        — 开发会话开始
    end_session.py          — 开发会话结束
    env_bootstrap.py        — 环境引导
    init_dev_env.ps1        — Windows 初始化
    init_dev_env.sh         — macOS/Linux 初始化
  reports/                  — 各阶段报告
  .github/workflows/ci.yml  — CI（Python 3.11×3平台 + 前端）
  .claude/skills/           — 项目级 Claude Code skills (8个)
```

## 开发总规则

### 编码与路径

1. 全项目文本文件 UTF-8，LF 换行。
2. Python 文件读写文本必须显式 `encoding="utf-8"`。
3. Windows 控制台输出使用 `sys.stdout.reconfigure(encoding="utf-8")`。
4. 路径使用 `pathlib.Path`。
5. 禁止硬编码盘符、用户名、绝对路径。
6. 写入文件时使用 `newline="\n"` 确保 LF。

### Git 协作（简化版 · Prompt4）

7. **Claude Code 不得自动 commit/push/merge。**
8. 每位开发者创建自己的分支：`feature/<github-username>-<module>`
9. 从 main 拉最新代码 → 创建分支 → 自由开发 → 向 main 提 PR → 专人 merge
10. 每次开发会话开始：提示是否拉取远程 main 对齐。
11. 每次编辑完成后：展示改动，询问是否保存/提交。
12. 个人化内容不提交；共同开发可复用内容才提交。
13. main 受保护，合并必须通过 PR。

### 接口与架构

14. **接口先行**：Pydantic schema → 文档 → mock JSON → 实现。
15. **单一 requirements.txt**：所有包用 `==` 固定版本。
16. **密钥不提交**：`.env` 在 `.gitignore`，只提交 `.env.example`。
17. **Pydantic schema 是后端接口事实来源**。
18. **前端 types/api.ts 与 backend schema 严格一致**。
19. **接口一旦冻结，只能追加字段，不得删除/重命名**。

### 虚拟环境

20. 无 conda 时提供安全安装引导，不得无确认自动下载安装器。
21. 镜像/代理配置只保存在本地，不写入仓库。

## Claude Code 工作规则

- 先读 `docs/` 下相关文档和 `backend/app/schemas/`，再写代码。
- 先计划再改文件。
- 每次改动后运行最小检查：`python scripts/doctor.py` 或 `python -m pytest backend/tests`。
- 不要跳过失败测试，不要删除重要逻辑。
- 不要把本地路径、密钥、代理地址写死进任何代码。
- 不要在 `main.py` 中堆砌业务逻辑。
- **不要自动执行 git commit、git push、git merge、gh pr create。**

## 常用命令

```bash
# ===== 环境 =====
python scripts/env_bootstrap.py --check
python scripts/env_bootstrap.py --apply
conda activate truthnet
pip install -r requirements.txt

# ===== 会话 =====
python scripts/start_session.py
python scripts/end_session.py

# ===== 检测 =====
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

### 分支模型（Prompt4 简化版）

```text
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
4. `python scripts/git_safety_check.py`
5. `python -m pytest backend/tests -v`
6. `cd frontend && pnpm build`
7. `pre-commit run --all-files`

### 禁止事项
- 禁止直接 push 到 `main`
- 禁止提交 `.env`、数据库文件、模型权重、大文件
- 禁止不看 diff 就全量提交
- **禁止 Claude Code 自动 commit/push/merge**
