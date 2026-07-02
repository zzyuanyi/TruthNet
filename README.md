# TruthNet — 织网鉴真

面向个人投资者的财报反欺诈智能问答系统。基于 Agentic AI，支持金融长上下文推理、股权穿透、舆情事件溯源、财报跨科目勾稽与可解释问答。

<!--
CI 状态 (需 push 到 GitHub 并启用 Actions 后生效):
[![CI](https://github.com/zzyuanyi/TruthNet/actions/workflows/ci.yml/badge.svg)](https://github.com/zzyuanyi/TruthNet/actions/workflows/ci.yml)
-->

## 核心能力

- **长上下文问答**：0.5M+ Tokens 上下文窗口，10 轮以上对话关键事实召回
- **股权穿透**：多跳链路分析，深度 >3 层，真实控制关系识别
- **舆情溯源**：事件簇聚合与时间线构建
- **财报勾稽**：跨科目预警，输出数据对比与可能造假模式
- **可解释输出**：每条结论附带证据链、图谱可视化、风险评分

## 技术架构

| 层级 | 技术选型 |
|------|----------|
| 后端框架 | Python 3.11 / FastAPI / WebSocket |
| Agent 编排 | LangGraph |
| 图分析 | NetworkX（MVP） |
| 向量检索 | ChromaDB |
| 数据库 | SQLite（MVP） |
| 前端 | React / Vite / TypeScript |

## 新成员最短启动流程

```bash
# 1. 克隆仓库
git clone https://github.com/zzyuanyi/TruthNet.git
cd TruthNet

# 2. 环境检测
python scripts/env_bootstrap.py --check
python scripts/doctor.py

# 3. 创建你的分支
git checkout -b feature/<your-github-username>-<task>

# 4. 后端验证
python -m pytest backend/tests -v

# 5. 前端（如果已初始化）
cd frontend && pnpm install && pnpm dev

# 6. 启动后端
uvicorn backend.app.main:app --reload
```

## 开发会话流程

### 每次开始开发

```bash
python scripts/start_session.py
```

### 每次结束开发

```bash
python scripts/end_session.py
```

## 提交前检查

```bash
python scripts/doctor.py
python scripts/encoding_path_audit.py
python scripts/git_safety_check.py
python -m pytest backend/tests -v
pre-commit run --all-files
cd frontend && pnpm build
```

## 目录结构

```text
TruthNet/
  README.md            — 本文件
  CLAUDE.md            — AI 开发上下文
  requirements.txt     — 唯一 Python 依赖
  backend/             — FastAPI 后端（HTTP + WebSocket）
  frontend/            — React 前端（Vite + TypeScript）
  data/                — 数据目录
  docs/                — 项目文档
  scripts/             — 工具脚本
  reports/             — 各阶段报告
  .github/             — CI + PR 模板
  .claude/skills/      — Claude Code 项目 skills
```

## 编码规范

1. 所有文本文件 UTF-8 + LF 换行
2. Python 文件读写必须 `encoding="utf-8"`
3. 路径必须使用 `pathlib.Path`
4. 禁止硬编码盘符、用户名、绝对路径
5. 脚本入口必须有 Windows UTF-8 输出保护

详见 `docs/SOFTWARE_ENGINEERING.md`。

## Git 协作（简化版 · Prompt4）

```text
main ← Pull Request ← 每个人的个人分支 (feature/用户名-任务)
```

| ❌ 禁止 | ✅ 必须 |
|---------|--------|
| Claude Code 自动 commit | 用户确认后手动 commit |
| Claude Code 自动 push | 用户确认后手动 push |
| Claude Code 自动 merge | 通过 PR，专人 merge |
| 直接 push 到 main | 个人分支 → PR → main |
| 多人共用一个分支 | 每人独立分支 |
| 提交 .env/密钥/数据库 | 只提交 .env.example 模板 |

详见 `docs/GIT_WORKFLOW.md`。

## 团队协作

本仓库面向混合背景团队（金融 + 计算机），所有流程文档化、可执行。

- 开发环境：[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
- Git 工作流：[docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)
- API 接口：[docs/API_CONTRACT.md](docs/API_CONTRACT.md)
- 软件工程：[docs/SOFTWARE_ENGINEERING.md](docs/SOFTWARE_ENGINEERING.md)
- Skill 索引：[docs/SKILL_INDEX.md](docs/SKILL_INDEX.md)

## 许可证

待定
