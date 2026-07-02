# GitHub 协作流程简化审计

> 审计时间：2026-07-02
> 目标：从 `main→dev→feature` 三层简化为 `main←PR←feature` 两层

## 变更摘要

### 旧模型（Prompt1-3）
```
main ← dev ← feature/xxx  三层：必须通过 dev 中转
```

### 新模型（Prompt4）
```
main ← PR ← feature/<username>-<task>  两层：直接从 main 拉分支，向 main 提 PR
```

## 变更理由

1. **降低复杂度**：金融背景团队成员不需要理解三层分支关系
2. **减少合并次数**：不需要 feature→dev→main 两次合并
3. **更直观**：每位成员从 main 拉取，完成后直接向 main 提 PR
4. **专人审核**：main 受保护，由专人 review + merge，质量可控

## 已更新文件清单

| 文件 | 变更内容 |
|------|----------|
| `.claude/skills/github-workflow/SKILL.md` | 完全重写：移除 dev，改为 main 直接模型 |
| `docs/GIT_WORKFLOW.md` | 完全重写：移除 dev 流程，简化分支策略图 |
| `CLAUDE.md` | 更新分支模型和 Git 协作规则 |
| `README.md` | 更新 Git 协作表格，移除 dev 引用 |
| `scripts/start_session.py` | 对齐基准从 origin/dev 改为 origin/main |
| `scripts/end_session.py` | 对齐基准已统一 |
| `scripts/git_safety_check.py` | dev 引用改为 main |
| `.github/workflows/ci.yml` | push 触发从 `[main, dev]` 改为 `[main]` |

## 未变更但需用户配置

| 项目 | 说明 |
|------|------|
| GitHub main 分支保护 | 需 owner 在 Settings 中手动启用 |
| PR 审阅人 | 需指定专人负责 review |
| dev 分支 | 仓库中已有的 dev 分支保留为历史参考，不再强制使用 |

## 每位成员工作方式（新）

```bash
# 1. 从 main 开始
git checkout main
git pull origin main

# 2. 创建个人分支
git checkout -b feature/<username>-<task>

# 3. 自由开发（在自己的分支上可以随意 commit/push）
# ...

# 4. 检查
python scripts/doctor.py
python -m pytest backend/tests -v
cd frontend && pnpm build
pre-commit run --all-files

# 5. Push 并提 PR
git push origin feature/<username>-<task>
# → GitHub 上创建 PR: base=main ← compare=你的分支
# → 在 PR 中说明改了什么
# → 请求专人 review
# → Review 通过后专人 merge
```

## 硬性禁止（不变）

1. ❌ Claude Code 不得自动 commit
2. ❌ Claude Code 不得自动 push
3. ❌ Claude Code 不得自动 merge
4. ❌ 不得直接 push 到 main
5. ❌ 不允许多人共用一个 feature 分支

## 结论

GitHub 协作流程已成功从三层简化为两层。所有文档、skills、脚本已同步更新。main 分支保护建议已写入文档，由仓库 owner 手动配置。

**状态：PASSED**
