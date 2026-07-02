# Git 协作工作流（人工确认式 · 简化版）

> 本文档写给不熟悉 Git 的团队成员。请先读完再操作。
> **重要：本项目采用人工确认式协作流程。Claude Code 不会自动 commit/push/merge。**

---

## 基础概念

### Git 是什么
Git 是一个"版本控制"工具。它就像一个带时间机器的文档管理器：
- 保存你的每次修改
- 可以回到任何历史版本
- 多人同时修改同一个项目不会互相覆盖

### GitHub 是什么
GitHub 是一个存放 Git 仓库的网站。你可以把它理解为"项目的云端备份 + 协作平台"。

### 核心概念

| 概念 | 通俗解释 |
|------|----------|
| **仓库 (Repo)** | 项目的完整文件夹，包含所有文件和历史记录 |
| **克隆 (Clone)** | 把云端仓库下载到你的电脑 |
| **分支 (Branch)** | 一条独立的开发线，不影响其他人 |
| **提交 (Commit)** | 保存一次修改，附带说明信息 |
| **推送 (Push)** | 把你本地的修改上传到 GitHub |
| **拉取 (Pull)** | 把 GitHub 上新的修改下载到本地 |
| **PR (Pull Request)** | 请求把你的修改合并到团队分支 |
| **合并 (Merge)** | 把两个分支的修改合在一起 |
| **冲突 (Conflict)** | 两个人的修改撞车了，需要手动解决 |

---

## 核心铁律

> **Claude Code 不得在用户未明确确认的情况下执行 git commit、git push、git merge、gh pr create。**

### 硬性禁止

1. ❌ Claude Code 不得自动 commit
2. ❌ Claude Code 不得自动 push
3. ❌ Claude Code 不得自动 merge
4. ❌ 不得直接向 main push
5. ❌ 不允许多人长期共用一个 feature 分支
6. ❌ 不看 diff 就 `git add .` 全量提交

### 硬性要求

7. ✅ 每位开发者必须有自己的分支
8. ✅ 每次开始编辑前，提醒/询问是否拉取远程 main 对齐
9. ✅ 每次编辑完成后，展示改动，询问是否保存/提交
10. ✅ 个人化内容不提交；共同开发可复用内容才提交

---

## 分支策略（简化版 · Prompt4）

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

> **历史说明**（Prompt4）：早期版本使用了 `main → dev → feature` 三层分支模型。Prompt4 起简化为 `main ← feature` 两层模型，降低团队协作复杂度。dev 分支不再强制要求，仓库中如有 dev 分支可保留作为历史参考。

---

## 首次配置

打开终端（Windows: Git Bash 或 PowerShell），输入：

```bash
git config --global user.name "你的姓名"
git config --global user.email "你的邮箱"
```

---

## 每位成员标准工作方式

### 开始开发前（每次）

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

在自己的分支上可以自由修改、提交、推送。**不会影响其他人。**

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

### 推送并提 PR

```bash
# 推送你的分支
git push origin feature/your-name-task

# 然后在 GitHub 页面：
# 1. 点击 "Compare & pull request"
# 2. base: main ← compare: 你的分支
# 3. 按 PR 模板填写
# 4. 在 PR 中说明：是否改接口？是否改数据？是否改前端类型？
# 5. 请求专人 review
# 6. Review 通过后由专人 merge
```

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
- 前端 `dist/`（构建产物由 CI 生成）

---

## 提交信息规范 (Conventional Commits)

每条提交信息必须遵循以下格式：

```
<类型>(<范围>): <简短描述>
```

### 类型

| 类型 | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(backend): 添加股权穿透接口` |
| `fix` | 修复 bug | `fix(frontend): 修复图表不显示问题` |
| `docs` | 文档修改 | `docs(readme): 更新快速开始流程` |
| `test` | 测试相关 | `test(api): 添加 chat 接口测试` |
| `refactor` | 重构代码 | `refactor(agent): 简化编排逻辑` |
| `chore` | 杂项（依赖更新等） | `chore(deps): 更新 pandas 版本` |

---

## GitHub main 分支保护建议

> 以下设置由仓库 owner 在 GitHub `Settings → Branches → Branch protection rules` 中手动配置。

建议对 main 分支启用：
- [ ] Require a pull request before merging
- [ ] Require approvals（至少 1 人）
- [ ] Require status checks to pass before merging
- [ ] Do not allow force pushes
- [ ] Do not allow deletions

---

## 合并冲突处理

当两个人的修改撞车时：

1. **不要慌**，Git 会标记冲突的文件
2. 打开冲突文件，找到 `<<<<<<<` 和 `>>>>>>>` 标记
3. 和对方沟通，手动选择保留谁的修改，删除标记符号
4. 保存文件
5. `git add .` → `git commit`

> 如果你不确定怎么处理，在群里问计算机背景的队友帮忙。

---

## 网络问题与代理

如果你在学校或公司网络，可能需要代理才能访问 GitHub。

### 设置代理

```bash
# 只在你自己电脑上设置，不要改仓库文件
git config --global http.proxy http://your-proxy-address:port
git config --global https.proxy http://your-proxy-address:port
```

### 取消代理

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

---

## 提交后怎么确认有没有跑通？（CI 自检）

如果你刚 push 了代码，需要确认 CI（自动检查）是否通过。

### 使用脚本（推荐）

```bash
# 检查当前分支 CI 状态
python scripts/ci_status.py --branch <your-branch>

# 持续监控直到完成
python scripts/ci_status.py --branch <your-branch> --watch

# 如果失败，拉取失败日志
python scripts/ci_status.py --branch <your-branch> --failed-logs
```

### 手动检查

1. 打开 https://github.com/zzyuanyi/TruthNet/actions
2. 找到你的分支最近一次运行
3. **绿色勾** ✅ = 通过，可以提 PR 或请求合并
4. **红色叉** ❌ = 失败，**不要合并**
5. 点击失败的 job → 看哪个 step 红了
6. 把失败日志复制下来，交给 Claude Code 请求帮助

### 失败后怎么做

```text
看日志 → 定位失败步骤 → 本地修复 → 运行检查 → commit → push → 再看 Actions
↓
直到变绿 ✅
↓
再提 PR 或请求合并
```

**记住**：红叉时不要合并，先修到变绿。

---

## 常见错误排查

### "Permission denied" / 没有权限
→ 你没有被加入仓库协作者。联系仓库 owner 添加你的 GitHub 用户名。

### "Authentication failed"
→ 检查 GitHub 登录凭证。推荐使用 GitHub CLI：
```bash
gh auth login
```

### "failed to push some refs" / push rejected
→ 可能远程有新的提交。先拉取再推送：
```bash
git pull origin main
git push origin your-branch
```

### "Your branch is behind"
→ 你的分支落后了。拉取并合并：
```bash
git checkout main
git pull origin main
git checkout your-branch
git merge main
```

### "CONFLICT"
→ 见上文"合并冲突处理"章节。

### "fatal: unable to access ... / Connection timed out"
→ 网络问题。检查代理设置，或确认 GitHub 未被屏蔽。
