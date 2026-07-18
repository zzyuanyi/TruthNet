# 当前仓库清单

> 生成时间：2026-07-17
> 基线：Prompt4（2026-07-02 冻结）

## 根目录文件

| 文件 | 状态 | 说明 |
|------|------|------|
| CLAUDE.md | ✅ 存在 | AI 开发上下文，7779 bytes |
| README.md | ✅ 存在 | 项目介绍，4105 bytes |
| requirements.txt | ✅ 存在 | 19 个包，全部 `==` 固定版本 |
| .python-version | ✅ 存在 | 内容 `3.11` |
| .env.example | ✅ 存在 | 基础模板（11 个变量） |
| .gitignore | ✅ 存在 | 805 bytes |
| .gitattributes | ✅ 存在 | 983 bytes，配置 LF |
| .editorconfig | ✅ 存在 | 311 bytes |
| .pre-commit-config.yaml | ✅ 存在 | pre-commit-hooks + ruff |

## 后端源码 (backend/app/)

| 文件 | 行数 | 说明 |
|------|------|------|
| main.py | 264 | FastAPI 入口，3 个端点（/health, POST /api/v1/chat, WS /api/v1/chat/ws） |
| core/config.py | 47 | pydantic-settings，15 个配置项 |
| schemas/common.py | 42 | UnifiedResponse, HealthResponse, ErrorDetail, ErrorResponse |
| schemas/chat.py | 147 | ChatRequest, ChatData, Evidence, GraphNode/Edge, RiskScore, WS 消息 |
| agents/__init__.py | 1 | 占位 docstring |
| api/__init__.py | 1 | 空 |
| services/__init__.py | 1 | 空 |
| skills/__init__.py | 1 | 空 |

## 后端测试 (backend/tests/)

| 文件 | 说明 |
|------|------|
| test_health.py | GET /health 测试 |
| test_api_contract_smoke.py | REST 契约 smoke 测试 |
| test_websocket_smoke.py | WebSocket smoke 测试（6 个用例） |
| test_stack_smoke.py | 技术栈导入测试 |
| test_encoding_path_policy.py | 编码/路径策略测试 |

**测试结果**：29 个用例，28 pass / 1 fail（sklearn/numpy 兼容，预存问题）

## 前端 (frontend/)

| 类别 | 说明 |
|------|------|
| 框架 | React 18 + Vite 6 + TypeScript 5.6 |
| 组件 | ChatPanel, RiskPanel, EvidenceList, TimelinePanel, GraphPanel |
| 类型 | types/api.ts（与 backend schema 对齐） |
| 构建 | `pnpm build` 通过 |

## 文档 (docs/)

| 文件 | 说明 |
|------|------|
| ARCHITECTURE.md | 架构设计 |
| API_CONTRACT.md | REST + WebSocket 接口契约（7 个端点） |
| DATA_CONTRACT.md | SQLite/NetworkX/ChromaDB 数据边界 |
| INTERFACE_CHANGELOG.md | 接口变更历史 |
| SOFTWARE_ENGINEERING.md | 编码/路径/分层/测试规范 |
| ENVIRONMENT.md | 环境配置指南 |
| GIT_WORKFLOW.md | Git 协作流程 |
| SKILL_INDEX.md | Skill 索引 |
| adr/0001-project-engineering-baseline.md | ADR |

## Claude Code Skills (.claude/skills/)

| Skill | 说明 |
|-------|------|
| agent-architecture | Agent 架构规范 |
| api-contract-first | 接口先行原则 |
| data-finance-contract | 数据/财务契约 |
| env-cross-platform | 跨平台兼容 |
| github-workflow | Git/GitHub 流程 |
| interface-review | 接口变更审查 |
| safe-skill-import | 外部 Skill 引入 |
| software-engineering | 软件工程规范 |

## 脚本 (scripts/)

| 文件 | 说明 |
|------|------|
| doctor.py | 环境检测（CI/local 双模式） |
| env_bootstrap.py | 环境引导 |
| encoding_path_audit.py | 编码/路径审计 |
| git_safety_check.py | Git 安全检查 |
| check_env.py | 轻量环境检查 |
| ci_status.py | CI 状态检查 |
| start_session.py | 开发会话开始 |
| end_session.py | 开发会话结束 |
| init_dev_env.ps1 | Windows 初始化 |
| init_dev_env.sh | macOS/Linux 初始化 |

## CI (.github/workflows/)

| 文件 | 说明 |
|------|------|
| ci.yml | Python 3.11 × 3 平台 + 前端 job |

## 当前接口清单

| 方法 | 路径 | 状态 |
|------|------|------|
| GET | /health | ✅ 稳定 |
| POST | /api/v1/chat | 🔶 MVP（Prompt4 冻结） |
| WS | /api/v1/chat/ws | 🔶 MVP（Prompt3 实现） |

## 当前响应格式

```json
{
  "code": 0,
  "data": {},
  "message": "ok",
  "trace_id": "uuid"
}
```

## 当前技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.115.0 |
| 数据校验 | Pydantic 2.9.2 |
| Agent | LangGraph 0.2.55 |
| 图分析 | NetworkX 3.3 |
| 向量库 | ChromaDB 0.5.23 |
| 数据库 | SQLite（无 ORM，无 migration） |
| LLM | Mock（无真实调用） |
| 测试 | pytest 8.3.3 |
| Lint | ruff 0.6.5 |
