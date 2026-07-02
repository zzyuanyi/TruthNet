# CI 自检流程

> 更新日期：2026-07-02

## 标准流程

```text
本地开发
→ 本地检查 (ruff / pytest / doctor / pre-commit)
→ git commit
→ git push 当前个人分支
→ 查看 GitHub Actions
   ├── 使用脚本: python scripts/ci_status.py --watch
   └── 或手动: https://github.com/zzyuanyi/TruthNet/actions
→ 如果 CI 通过 ✅
   └── 可以请求 PR review
→ 如果 CI 失败 ❌
   ├── 拉取失败日志: python scripts/ci_status.py --failed-logs
   ├── 分类失败:
   │   ├── lint → 修正代码格式
   │   ├── test → 修复测试
   │   ├── dependency → 检查 requirements.txt
   │   ├── frontend → 检查 TypeScript 类型和构建
   │   └── platform-specific → 检查平台相关路径/编码问题
   ├── 本地修复
   ├── 运行完整本地检查
   ├── git commit fix
   ├── git push same branch
   └── 再次检查 Actions（回到上一步）
```

## 新增脚本

### `scripts/ci_status.py`

```bash
# 检查当前分支最近一次 Actions run
python scripts/ci_status.py

# 指定分支
python scripts/ci_status.py --branch feature/yuanyi-fix

# 持续监控直到完成
python scripts/ci_status.py --watch

# 拉取失败日志
python scripts/ci_status.py --failed-logs

# JSON 输出（用于自动化）
python scripts/ci_status.py --json

# CI 模式（不查远程）
python scripts/ci_status.py --ci
```

**依赖**：GitHub CLI (`gh`)。如果 `gh` 不可用，脚本会给出 Web 手动检查指引。

## 写入规则

### `github-workflow` skill

- ✅ 每次 push 必须检查 CI
- ✅ CI 失败必须拉日志修复
- ✅ 不得在 CI 未通过时请求 merge
- ✅ CI 通过后才请求 PR review

### `CLAUDE.md`

- ✅ push 后主动检查 GitHub Actions 状态
- ✅ CI 失败必须读取日志并修复
- ✅ 不得在 CI 失败时声称任务完成
- ✅ 不得自动 merge PR

### `docs/GIT_WORKFLOW.md`

- ✅ 提交后怎么确认有没有跑通（非技术成员可理解）
- ✅ 红叉 → 点击 → 看失败 step → 交给 Claude Code → 修复 → 再 push → 直到变绿
- ✅ 红叉时不要合并

### `scripts/doctor.py`

- ✅ 检查 `ci_status.py` 是否存在
- ✅ 检查 GitHub CLI (`gh`) 是否安装

### `scripts/end_session.py`

- ✅ 结束开发时提示运行 `ci_status.py --watch`

### `README.md`

- ✅ 提交前检查加入 ruff check
- ✅ 新增 Push 后 CI 检查章节

## 远程 CI 验证

当前 run (28571655027) 失败于 windows-latest 的 Ruff check 步骤。修复已完成，待 push 后重新触发 CI 验证三平台通过。
