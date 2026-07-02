# 需用户确认的事项

> 以下事项需要用户（仓库 owner）手动确认或操作。
> Claude Code 不会自动执行这些操作。

## 1. GitHub 仓库设置（需 owner 权限）

### 分支保护规则

在 GitHub 仓库 `Settings → Branches → Branch protection rules` 添加：

**main 分支保护**：
- [ ] Require a pull request before merging
- [ ] Require approvals (建议 ≥1)
- [ ] Require status checks to pass before merging
- [ ] Require conversation resolution before merging
- [ ] Do not allow bypassing the above settings

**dev 分支保护**：
- [ ] Require a pull request before merging
- [ ] Require status checks to pass before merging

### GitHub Actions 启用

- [ ] 确认 GitHub Actions 已在仓库中启用
- [ ] 推送代码到 GitHub 后确认 CI workflow 正常触发

## 2. 前端初始化（需用户执行）

当前 pnpm 未安装，前端未初始化。如需初始化：

```bash
# Step 1: 安装 pnpm
npm install -g pnpm

# Step 2: 初始化前端项目
cd frontend
pnpm create vite . --template react-ts
pnpm install

# Step 3: 验证
pnpm build
```

或者用户可以选择稍后由前端开发人员初始化。

## 3. 当前在 main 分支的提交安排

Prompt3 的工作（规范硬化、脚本、文档）当前在 `main` 分支上。建议：

```bash
# 选项 A：创建 dev 分支并提交
git checkout -b dev
git add .
git commit -m "chore(project): Prompt3 编码/路径/Git/环境规范硬化"

# 选项 B：直接推送到 main（仅限此次规范硬化，后续严格禁止）
# 不推荐，但 Prompt1-3 为初始工程基线

# 选项 C：创建新分支提交 Prompt3 变更
git checkout -b chore/yuanyi-prompt3-hardening
git add .
git commit -m "chore(project): Prompt3 编码/路径/Git/环境规范硬化"
```

## 4. 推送并验证 CI

```bash
# 推送后 CI 将自动运行
git push origin <branch-name>

# 在 GitHub Actions 页面查看 CI 结果
# https://github.com/zzyuanyi/TruthNet/actions
```

## 5. 创建 dev 分支（如尚未创建）

```bash
# 从当前 main 创建 dev 分支
git checkout -b dev
git push origin dev
```

## 6. pnpm 安装确认

```bash
# 如需前端开发，安装 pnpm
npm install -g pnpm

# 国内镜像加速（可选，仅本机）
pnpm config set registry https://registry.npmmirror.com
```

## 7. 后续开发提醒

- [ ] 每位开发者创建个人 feature 分支前，先运行 `python scripts/start_session.py`
- [ ] 完成编辑后运行 `python scripts/end_session.py`
- [ ] 提交前运行完整检查：
  ```bash
  python scripts/doctor.py
  python scripts/encoding_path_audit.py
  python scripts/git_safety_check.py
  python -m pytest backend/tests -v
  pre-commit run --all-files
  ```
- [ ] 不在 main 上直接开发（git_safety_check.py 会报 FAIL）
- [ ] 个人化文件不提交

## 8. 无需用户操作（已自动完成）

以下事项已在本轮自动完成，无需用户手动操作：

- ✅ `.gitattributes` 已创建
- ✅ 所有脚本已创建并测试
- ✅ 所有 skills 已更新
- ✅ 所有文档已更新
- ✅ WebSocket 最小 mock 端点已实现
- ✅ 编码审计脚本已创建并运行
- ✅ Git 安全检查脚本已创建并运行
- ✅ 环境引导脚本已创建并运行
- ✅ CI workflow 已更新
- ✅ 29/29 后端测试通过
- ✅ 39/39 doctor 检查通过
- ✅ pre-commit hooks 通过
