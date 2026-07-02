# 需用户确认的事项

> 以下事项需要用户（仓库 owner）手动确认或操作。

## 1. GitHub main 分支保护（需 owner 权限）

在 `Settings → Branches → Branch protection rules → Add rule`：

- **Branch name pattern**: `main`
- [ ] Require a pull request before merging
- [ ] Require approvals（建议 ≥1）
- [ ] Require status checks to pass before merging
- [ ] Do not allow force pushes
- [ ] Do not allow deletions

## 2. 推送代码并触发 CI

```bash
# 当前所有 Prompt1-4 变更在 main 分支，尚未 push
git push origin main

# 如果 main 受保护无法 push，创建 PR 分支：
git checkout -b chore/yuanyi-prompt4-baseline
git push origin chore/yuanyi-prompt4-baseline
# → 向 main 提 PR
```

## 3. CI 远程验证

Push 后访问 https://github.com/zzyuanyi/TruthNet/actions 确认：
- Python job（3 平台 × Python 3.11）通过
- Frontend job（typecheck + build）通过

## 4. 前端实际运行验证（可选）

```bash
# 终端 1：启动后端
cd backend && uvicorn app.main:app --reload

# 终端 2：启动前端
cd frontend && pnpm dev

# 浏览器访问 http://localhost:5173
# 输入问题 → 点击发送 → 验证 HTTP 和 WS 通信
```

## 5. 添加团队成员为协作者

在 GitHub 仓库 `Settings → Collaborators` 添加团队成员。

## 6. CODEOWNERS 更新

`.github/CODEOWNERS` 中指定专人负责 PR review：

```text
* @zzyuanyi
```

## 7. pnpm 安装方式建议

如果团队成员需要安装 pnpm，推荐使用 corepack（Node.js 16+ 内置）：

```bash
corepack enable
corepack prepare pnpm@latest --activate
pnpm --version
```

或者 npm 全局安装：

```bash
npm install -g pnpm
```

## 8. 无需用户操作（已自动完成）

- ✅ GitHub 协作流程简化为 `main ← PR ← feature`
- ✅ 所有文档和 skills 已更新
- ✅ 前端 React + Vite + TypeScript 项目已初始化
- ✅ `pnpm install` + `pnpm build` 验证通过
- ✅ 前后端类型已对齐
- ✅ risk_score 已升级为结构化对象
- ✅ 接口已冻结
- ✅ CI workflow 已包含前端 job
- ✅ 29/29 后端测试通过
- ✅ 39/39 doctor 通过
- ✅ pre-commit 通过
