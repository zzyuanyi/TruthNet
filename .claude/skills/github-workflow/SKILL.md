---
name: github-workflow
description: Git/GitHub 协作流程指导。帮助非计算机背景成员完成分支、提交、PR、合并操作。强制人工确认式流程，禁止自动提交。
---

# GitHub 协作工作流（人工确认式 · 简化版）

## 核心铁律

> **Claude Code 不得在用户未明确确认的情况下执行 git commit、git push、git merge、gh pr create。**

### 硬性禁止

1. ❌ Claude Code 不得自动 commit
2. ❌ Claude Code 不得自动 push
3. ❌ Claude Code 不得自动 merge
4. ❌ 不得直接向 main push
5. ❌ 不允许多人长期共用一个 feature 分支

### 硬性要求

6. ✅ 每位开发者必须有自己的分支
7. ✅ 每次开始编辑前，提醒/询问是否拉取远程 main 对齐
8. ✅ 每次编辑完成后，展示改动，询问是否保存/提交
9. ✅ 个人化内容不提交；共同开发可复用内容才提交

---

## 分支模型（简化版 · Prompt4）

```text
main ───────────────────────── 唯一稳定主分支（受保护，禁止直接 push）
  │
  ├── feature/yuanyi-frontend  个人功能分支
  ├── feature/alice-data        个人功能分支
  ├── fix/yuanyi-bug-fix        个人修复分支
  └── docs/yuanyi-readme        个人文档分支
```

**规则**：
- `main` 是唯一稳定分支，所有代码最终合并到这里
- 每位成员从 `main` 拉取最新代码，创建自己的分支
- 在自己的分支上自由修改、提交、推送
- 完成后向 `main` 提 Pull Request
- 由专人 review 和 merge
- **永远不要直接向 `main` push**
- **合并必须通过 PR**

> 历史说明：早期版本使用了 `main → dev → feature` 三层模型。Prompt4 起简化为 `main ← feature` 两层模型，降低协作复杂度。dev 分支不再强制要求。

---

## 首次配置

```bash
git config --global user.name "你的姓名"
git config --global user.email "你的邮箱"
```

---

## 每位成员标准工作方式

### 开始开发前

```bash
# 1. 切到 main，拉取最新代码
git checkout main
git pull origin main

# 2. 创建自己的分支
git checkout -b feature/<your-github-username>-<task-name>
```

也可以使用脚本辅助：

```bash
python scripts/start_session.py
```

### 在自己的分支自由开发

在自己的分支上可以自由：
- 修改文件
- `git add` / `git commit`
- `git push origin your-branch`

**Claude Code 不会自动执行 commit/push/merge，你需要自己确认每次操作。**

### 开发完成后的检查

```bash
# 查看修改
git status
git diff --stat

# 运行检查
python scripts/doctor.py
python scripts/encoding_path_audit.py
python scripts/git_safety_check.py
python -m pytest backend/tests -v
pre-commit run --all-files

# 如果前端已初始化
cd frontend && pnpm build
```

也可以使用脚本辅助：

```bash
python scripts/end_session.py
```

### 向 main 提 Pull Request

1. 确保所有修改已 push 到你的分支
2. 打开 GitHub 仓库页面
3. 点击 "Compare & pull request"
4. **base: `main`** ← compare: `你的分支`
5. 按 PR 模板填写描述
6. 在 PR 中明确说明：
   - 是否修改了接口？
   - 是否修改了数据 schema？
   - 是否修改了前端类型？
7. 请求专人 review
8. Review 通过后由专人 merge

---

## 分支命名规范

```text
feature/<github-username>-<module>
fix/<github-username>-<bug>
docs/<github-username>-<topic>
test/<github-username>-<scope>
```

示例：

```text
feature/yuanyi-frontend-chat
feature/alice-data-pipeline
feature/bob-backend-agent
docs/yuanyi-api-contract
fix/alice-data-import-bug
```

---

## 哪些可以提交 / 不能提交

### ✅ 可以提交

- 源码（`.py`, `.ts`, `.tsx`, `.js`, `.jsx`）
- 测试（`tests/` 目录）
- 文档（`.md` 文件）
- `.claude/skills/`
- `.github/`
- mock 数据
- schema（`backend/app/schemas/`）
- 脚本（`scripts/`）
- `.env.example`（模板，不含真实密钥）
- 前端 `pnpm-lock.yaml`
- 小型示例文件

### ❌ 不能提交

- `.env`（真实环境变量）
- API key、token、密码
- 代理地址、账号
- 个人本地路径
- `.venv/`（虚拟环境）
- conda env
- `node_modules/`
- 数据库文件（`*.db`, `*.sqlite`）
- 原始大数据（`data/raw/` 下的文件）
- 模型权重（`*.pkl`, `*.pt`, `*.onnx` 等）
- 本地日志
- IDE 私人配置（`.vscode/`, `.idea/`）
- `.claude/settings.local.json`
- 前端 `.env`（只提交 `.env.example`）

使用 `python scripts/git_safety_check.py` 自动检查。

---

## Conventional Commits 规范

```
feat(scope): 新功能描述
fix(scope): bug修复描述
docs(scope): 文档修改
test(scope): 测试相关
refactor(scope): 重构（不改功能）
chore(scope): 杂项（依赖、配置等）
```

示例：
```bash
git commit -m "feat(api): 添加公司风险评分接口"
git commit -m "fix(agent): 修复股权穿透深度计算错误"
git commit -m "docs(readme): 更新快速开始流程"
```

---

## GitHub main 分支保护建议

> 以下设置由仓库 owner 在 GitHub Settings 中手动配置，Claude Code 不会自动配置。

建议对 main 分支启用：

- [ ] Require a pull request before merging
- [ ] Require approvals（至少 1 人）
- [ ] Require status checks to pass before merging
- [ ] Require branches to be up to date before merging
- [ ] Do not allow force pushes
- [ ] Do not allow deletions

---

## 合并冲突处理

当提示 CONFLICT 时：
1. 打开冲突文件
2. 搜索 `<<<<<<<` 标记
3. 和队友沟通保留谁的修改
4. 删除冲突标记（`<<<<<<<`, `=======`, `>>>>>>>`）
5. 保存后执行：`git add .` → `git commit`

---

## 代理问题

如果 Git 网络不通：
```bash
# 设置代理（只用占位符，不填真实地址）
git config --global http.proxy http://your-proxy:port
git config --global https.proxy http://your-proxy:port

# 取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

⚠️ 不要把真实代理地址、用户名、密码写入仓库文件。

---

## 常见错误

| 错误 | 解决方法 |
|------|----------|
| Permission denied | 联系 owner 添加 GitHub 协作者权限 |
| Authentication failed | 运行 `gh auth login` |
| Push rejected | 先 `git pull origin main` 再 push |
| Branch behind | `git checkout main && git pull && git checkout - && git merge main` |
| Clone timeout | 检查网络/代理 |

---

## 严禁

- ❌ 直接 push 到 `main`
- ❌ 提交 `.env` 文件
- ❌ 提交数据库大文件 / PDF / Excel
- ❌ 提交模型权重
- ❌ 不看 diff 就 `git add .` 全量提交
- ❌ 代理地址写入仓库
- ❌ Claude Code 自动 commit/push/merge
- ❌ 多人共用一个 feature 分支
