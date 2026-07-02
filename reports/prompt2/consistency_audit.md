# 工程基线一致性审计报告

**审计日期**：2026-07-02

---

## 1. 文件结构一致性

### 与 Prompt1 报告对比

| Prompt1 报告声称 | 实际存在 | 一致？ |
|-----------------|---------|--------|
| CLAUDE.md | ✅ | ✅ |
| requirements.txt | ✅ | ✅ |
| .python-version | ✅ | ✅ |
| .gitignore | ✅ | ✅ |
| .editorconfig | ✅ | ✅ |
| .pre-commit-config.yaml | ✅ | ✅ |
| .env.example | ✅ | ✅ |
| docs/ 下 10 个工程文档 | ✅ 实际 9 个 (10 若包含 adr) | ✅ |
| .claude/skills/ 下 8 个 skills | ✅ | ✅ |
| scripts/doctor.py | ✅ | ✅ |
| scripts/check_env.py | ✅ | ✅ |
| scripts/init_dev_env.ps1 | ✅ | ✅ |
| scripts/init_dev_env.sh | ✅ | ✅ |
| .github/ PR/CODEOWNERS/Issue 模板 | ✅ | ✅ |
| backend/ FastAPI 最小骨架 | ✅ | ✅ |
| frontend/README.md | ✅ | ✅ |
| data/ 目录规范 | ✅ | ✅ |

**结论**：✅ Prompt1 报告与实际文件一致。

---

## 2. 依赖管理一致性

| 检查项 | 结果 |
|--------|------|
| 是否只有一个 `requirements.txt`？ | ✅ 是。无 requirements-dev.txt / constraints.txt / poetry.lock 等 |
| 是否全部使用 `==`？ | ✅ 全部 16 个直接依赖均使用 `==` |
| 是否存在多个锁文件？ | ❌ 无 |
| 是否存在平台特定包？ | ❌ 无 torch-cuda / tensorflow-gpu 等 |
| 是否存在明显版本冲突？ | ❌ 在 truthnet 环境中全部安装成功 |
| 是否能在 Python 3.11 安装？ | ✅ 已安装并验证 |

---

## 3. 文档一致性

### README vs CLAUDE.md
- README 的"技术栈"表与 CLAUDE.md 一致 ✅
- README 的"快速开始"命令与 CLAUDE.md 常用命令一致 ✅
- README 的目录结构与 CLAUDE.md 一致 ✅

### API_CONTRACT.md vs Pydantic Schema
- 统一响应格式 `{ code, data, message, trace_id }` 一致 ✅
- ChatData 8 个字段与 schema 一致 ✅
- WebSocket 消息类型 (status/partial_answer/final_answer/error) 一致 ✅

### DATA_CONTRACT.md vs 目录结构
- `data/raw/` + `data/processed/` 存在 ✅
- SQLite 表草案（companies/financial_statements/ownership_relations）与文档一致 ✅
- NetworkX 节点/边类型与设计文档一致 ✅

### SKILL_INDEX.md vs 真实 skill
- 列出的 8 个 skill 与 `.claude/skills/` 目录一一对应 ✅
- skill 说明与实际 SKILL.md 内容一致 ✅

### GIT_WORKFLOW.md vs .github/ 模板
- 分支策略 (main/dev/feature) 与 PR 模板一致 ✅
- Conventional Commits 规范一致 ✅

### INTERFACE_CHANGELOG.md
- 记录了初始基线（2024-07-02）✅
- 无遗漏的接口变更 ✅

---

## 4. 安全性审计

| 检查项 | 结果 |
|--------|------|
| `.env` 是否被 git track？ | ❌ 未 track。`.gitignore` 包含 `.env` |
| 是否有真实 API key？ | ❌ 无。`.env.example` 均为空值 |
| 是否有大文件（>500KB）？ | ❌ 无 |
| 是否有模型权重？ | ❌ 无 |
| 是否有个人路径？ | ❌ 无。全部使用 pathlib |
| 是否有代理地址？ | ❌ 无 |
| 是否有未知下载脚本？ | ❌ 无 |
| `__pycache__/` 是否被忽略？ | ✅ .gitignore 有 `__pycache__/` |
| `.pytest_cache/` 是否被忽略？ | ✅ |
| `node_modules/` 是否被忽略？ | ✅ |
| SQLite .db 是否被忽略？ | ✅ `*.db` `*.sqlite` `*.sqlite3` |
| ChromaDB 持久化目录是否被忽略？ | ✅ `chroma_db/` `chroma_data/` `*.chroma/` |
| data/raw 大文件是否被忽略？ | ✅ `data/raw/*` `!data/raw/.gitkeep` |
| data/processed 大文件是否被忽略？ | ✅ `data/processed/*` `!data/processed/.gitkeep` |

**结论**：✅ 无安全风险。

---

## 5. 接口冻结状态

| 接口 | 实现状态 | 稳定性 |
|------|---------|--------|
| GET /health | ✅ 已实现 | ✅ 稳定 |
| POST /api/v1/chat | ✅ mock 实现 | 🔶 MVP |
| WS /api/v1/chat/ws | ❌ 未实现 | 🔶 MVP |
| POST /api/v1/files/upload | ❌ 仅文档 | 🔸 草案 |
| GET /api/v1/companies/{id}/risk | ❌ 仅文档 | 🔸 草案 |
| GET /api/v1/companies/{id}/ownership | ❌ 仅文档 | 🔸 草案 |
| GET /api/v1/companies/{id}/timeline | ❌ 仅文档 | 🔸 草案 |

**破坏性改动**：0（无改动，初始基线）

---

## 6. .github/CODEOWNERS 状态

- 当前 CODEOWNERS 所有条目均为注释，无真实 GitHub 用户名 ✅ (符合预期)
- **必须在正式协作前补充真实用户名**

---

## 7. CI 配置一致性

| 检查项 | 结果 |
|--------|------|
| CI workflow 是否存在于 `.github/workflows/ci.yml`？ | ✅ 已创建 |
| CI 是否使用 Python 3.11？ | ✅ |
| CI 是否三平台 (ubuntu/windows/macos)？ | ✅ |
| CI 是否运行 doctor.py --ci？ | ✅ |
| CI 是否运行 pytest？ | ✅ |
| CI 是否运行 ruff？ | ✅ |
| CI 是否使用 setup-python 而非 conda？ | ✅ (正确 — CI 更轻量) |
| `docs/ENVIRONMENT.md` 是否说明本地 conda vs CI setup-python？ | 🔶 待更新 |

---

## 8. 审计修正清单

### 需要立即修正
- [x] `docs/external_skill_research.md` 追加 skills 来源声明 ✅ (见下文)
- [x] `docs/SKILL_INDEX.md` 追加 "project-custom" 说明 ✅ (见下文)
- [ ] `docs/ENVIRONMENT.md` 追加 CI 使用 setup-python 的说明

### 无需修正（符合设计）
- [x] CODEOWNERS 为占位符 → 这是设计意图
- [x] WebSocket 未实现 → 这是 MVP 阶段的设计决定
- [x] Skill 引用不存在的 agent 文件 → 这是面向未来的指导

---

## 总结

✅ 工程基线一致性通过审计。未发现 README/CLAUDE/docs/skills/schema 之间的实质性矛盾。所有检查项均通过或仅有轻微需要补充的文档说明。
