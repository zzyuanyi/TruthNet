# Skill Index

> Claude Code 项目级 Skills 索引。
> 每个 Skill 对应 `.claude/skills/<name>/SKILL.md`。

---

## 重要声明

> **当前 `.claude/skills/` 下的 8 个 skills 是 TruthNet 项目自定义 skills（project-custom），不是 Anthropic 官方直接下载的 bundled skills。**
> 它们参考了 Claude Code 官方 skill 的目录结构（`.claude/skills/<name>/SKILL.md` + YAML frontmatter）组织方式，内容由项目团队为 TruthNet 特定需求编写。
> 详见 `reports/prompt2/skill_source_audit.md`。

---

## Skills 清单

### 1. env-cross-platform
- **路径**：`.claude/skills/env-cross-platform/SKILL.md`
- **用途**：每次涉及环境、依赖、路径、脚本时自动提醒跨平台兼容
- **Prompt3 更新**：新增编码/换行/路径硬性规定、环境检测决策树、Windows UTF-8 输出保护、conda 安全安装引导
- **适用成员**：全部
- **是否执行命令**：否（只提供规则检查）
- **是否需要用户确认**：否（自动提醒）
- **维护人**：待分配

### 2. github-workflow
- **路径**：`.claude/skills/github-workflow/SKILL.md`
- **用途**：帮助不熟悉 Git/GitHub 的成员完成分支、提交、PR 操作
- **Prompt4 更新**：简化为两层模型（main ← PR ← feature），移除强制 dev 分支，每位成员独立分支向 main 提 PR
- **适用成员**：非计算机背景成员
- **是否执行命令**：否（提供指令，用户自行执行）
- **是否需要用户确认**：是（开始/结束编辑时询问）
- **维护人**：待分配

### 3. api-contract-first
- **路径**：`.claude/skills/api-contract-first/SKILL.md`
- **用途**：保证接口先行、稳定、可 mock
- **适用成员**：后端+前端开发者
- **是否执行命令**：否
- **是否需要用户确认**：接口变更时提示用户审阅
- **维护人**：待分配

### 4. software-engineering
- **路径**：`.claude/skills/software-engineering/SKILL.md`
- **用途**：统一设计模式、分层架构、代码规范
- **适用成员**：后端开发者
- **是否执行命令**：否
- **是否需要用户确认**：否
- **维护人**：待分配

### 5. interface-review
- **路径**：`.claude/skills/interface-review/SKILL.md`
- **用途**：修改接口、schema、数据库时的审查清单
- **适用成员**：全部
- **是否执行命令**：否（提供检查清单）
- **是否需要用户确认**：破坏性修改时要求用户确认
- **维护人**：待分配

### 6. safe-skill-import
- **路径**：`.claude/skills/safe-skill-import/SKILL.md`
- **用途**：审计和引入外部 skills/hooks/commands 的安全流程
- **Prompt3 更新**：新增当前 skill 来源声明、conda 下载/安装检查项、环境自检测引导
- **适用成员**：全部
- **是否执行命令**：否（审计指导）
- **是否需要用户确认**：引入外部资源时需确认
- **维护人**：待分配

### 7. data-finance-contract
- **路径**：`.claude/skills/data-finance-contract/SKILL.md`
- **用途**：数据组、财务规则、标注、评测统一
- **适用成员**：数据组 + 后端
- **是否执行命令**：否
- **是否需要用户确认**：否
- **维护人**：待分配

### 8. agent-architecture
- **路径**：`.claude/skills/agent-architecture/SKILL.md`
- **用途**：后端 Agent/Skill 实现时统一架构
- **适用成员**：后端开发者
- **是否执行命令**：否
- **是否需要用户确认**：否
- **维护人**：待分配

---

## 脚本索引（Prompt3 新增）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `scripts/encoding_path_audit.py` | 编码/路径/换行符审计 | `python scripts/encoding_path_audit.py [--ci]` |
| `scripts/git_safety_check.py` | Git 分支与文件安全检查 | `python scripts/git_safety_check.py [--ci]` |
| `scripts/start_session.py` | 开发会话开始（交互式） | `python scripts/start_session.py [--ci]` |
| `scripts/end_session.py` | 开发会话结束（交互式） | `python scripts/end_session.py [--ci]` |
| `scripts/env_bootstrap.py` | 环境自适应检测与配置 | `python scripts/env_bootstrap.py [--check\|--apply\|--ci]` |

---

## 使用方式

在 Claude Code 对话中使用：

```
/skill-name
```

或 Claude Code 会根据上下文自动激活相关 skill。

---

## 维护说明

- 新 Skill 必须在此文件登记
- 修改 Skill 的 `SKILL.md` 后，如有重大变更，需更新此文件的对应说明
- 维护人字段由实际负责的团队成员填写
