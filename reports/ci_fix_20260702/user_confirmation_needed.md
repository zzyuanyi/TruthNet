# 需用户确认的事项

## 1. 提交并 Push 修复

```bash
# 查看变更
git status
git diff --stat

# 提交
git add -A
git commit -m "fix(lint): resolve all 67 ruff violations

- F541: remove extraneous f-string prefixes
- F401: remove unused imports
- E741: rename ambiguous variable 'l'
- F841: remove unused variables

All checks pass: ruff check, ruff format, pytest 29/29, doctor 41/41"

# 推送到当前分支
git push origin main
```

> 注意：当前在 main 分支。如果 main 已配置保护，需创建 feature 分支。

## 2. 验证远程 CI

Push 后访问：https://github.com/zzyuanyi/TruthNet/actions

确认新的 run 在三平台都通过：
- ubuntu-latest ✅
- windows-latest ✅
- macos-latest ✅

## 3. 安装 gh CLI（如尚未安装）

```bash
# 验证
gh auth status

# 如未安装：
# Windows: winget install GitHub.cli
# macOS: brew install gh
# Linux: 见 https://github.com/cli/cli/blob/trunk/docs/install_linux.md
gh auth login
```

## 4. 无需用户操作（已自动完成）

- ✅ 67 个 Ruff violations 全部修复
- ✅ ruff check . 通过
- ✅ ruff format --check . 通过
- ✅ pytest 29/29 通过
- ✅ doctor 41/41 通过
- ✅ encoding_path_audit 通过
- ✅ ci_status.py 已创建
- ✅ github-workflow skill 已更新
- ✅ CLAUDE.md 已更新
- ✅ docs/GIT_WORKFLOW.md 已更新
- ✅ README.md 已更新
- ✅ doctor.py 已更新
- ✅ end_session.py 已更新
- ✅ 所有报告已生成
