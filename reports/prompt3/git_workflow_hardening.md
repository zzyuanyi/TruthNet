# Git 协作流程硬化审计报告

> 审计时间：2026-07-02
> 审计工具：`scripts/git_safety_check.py --ci`

## 10 项审计问答

### 1. 是否禁止自动 commit？

✅ **是。** 已写入：
- `CLAUDE.md` — "Claude Code 不得自动 commit"
- `.claude/skills/github-workflow/SKILL.md` — 核心铁律第一条
- `docs/GIT_WORKFLOW.md` — 核心铁律
- `README.md` — Git 协作铁律表格

### 2. 是否禁止自动 push？

✅ **是。** 已写入：
- `CLAUDE.md` — "Claude Code 不得自动 push"
- `.claude/skills/github-workflow/SKILL.md` — 核心铁律第二条
- `docs/GIT_WORKFLOW.md` — 核心铁律
- `README.md` — Git 协作铁律表格

### 3. 是否禁止自动 merge？

✅ **是。** 已写入：
- `CLAUDE.md` — "Claude Code 不得自动 merge"
- `.claude/skills/github-workflow/SKILL.md` — 核心铁律第三条
- `docs/GIT_WORKFLOW.md` — 核心铁律
- `README.md` — Git 协作铁律表格

### 4. 是否建立每位开发者独立分支规范？

✅ **是。** 已写入：
- `CLAUDE.md` — `feature/<github-username>-<module>`
- `.claude/skills/github-workflow/SKILL.md` — 分支命名规范表格
- `docs/GIT_WORKFLOW.md` — 完整分支命名规范与示例

### 5. 是否建立开发开始前远程对齐询问？

✅ **是。** 已建立：
- `scripts/start_session.py` — 交互式询问流程
- `.claude/skills/github-workflow/SKILL.md` — "每次进入编辑任务前必须执行"
- `docs/GIT_WORKFLOW.md` — 开始开发前（每次）章节

### 6. 是否建立编辑结束后本地保存/提交询问？

✅ **是。** 已建立：
- `scripts/end_session.py` — 交互式询问流程（4 选项）
- `.claude/skills/github-workflow/SKILL.md` — "每次修改完成后必须展示"
- `docs/GIT_WORKFLOW.md` — 结束编辑后（每次）章节

### 7. 是否区分共同文件和个人文件？

✅ **是。** 已区分：
- `scripts/git_safety_check.py` — 自动分类"可提交文件"和"应保留本地文件"
- `.claude/skills/github-workflow/SKILL.md` — 完整表格（哪些可以/不能提交）
- `docs/GIT_WORKFLOW.md` — 完整表格
- `CLAUDE.md` — "个人化内容不提交；共同开发可复用内容才提交"

### 8. 是否有脚本辅助？

✅ **是。** 已创建：
- `scripts/git_safety_check.py` — Git 分支与文件安全检查
- `scripts/start_session.py` — 开发会话开始辅助
- `scripts/end_session.py` — 开发会话结束辅助

### 9. 是否会在 main 分支开发时报错？

✅ **是。** 
- `scripts/git_safety_check.py` — main 分支返回 FAIL
- `scripts/start_session.py` — main 分支给出警告并提供切换选项
- `scripts/doctor.py` — main 分支给出 WARN

### 10. 是否还有需要用户确认的 GitHub 设置？

✅ **是。** 以下需要仓库 owner 手动配置：
- main 分支保护规则（Settings → Branches → Add rule）
- dev 分支保护规则（Settings → Branches → Add rule）
- 要求 PR 审阅后才能合并
- 要求 status checks 通过

## 硬性禁止项验证

| 禁止项 | 已写入位置 | 脚本强制 | 
|--------|-----------|---------|
| 自动 commit | CLAUDE.md, github-workflow SKILL.md, GIT_WORKFLOW.md, README.md | end_session.py 只建议不执行 |
| 自动 push | CLAUDE.md, github-workflow SKILL.md, GIT_WORKFLOW.md, README.md | end_session.py 只建议不执行 |
| 自动 merge | CLAUDE.md, github-workflow SKILL.md, GIT_WORKFLOW.md, README.md | 无脚本触发 merge |
| 直接 push main | CLAUDE.md, github-workflow SKILL.md, GIT_WORKFLOW.md, README.md | git_safety_check.py FAIL |
| 多人共用一个分支 | CLAUDE.md, github-workflow SKILL.md, GIT_WORKFLOW.md | 分支命名强制个人化 |

## 需要用户手动配置的 GitHub 设置

参见 [user_confirmation_needed.md](user_confirmation_needed.md)。

## 结论

Git 人工确认式协作流程已全面硬化到规范、skills、文档和脚本中。所有硬性禁止项均有文档和脚本双重保障。

**状态：PASSED**
