# Skill 来源审计报告

**审计日期**：2026-07-02
**审计范围**：`.claude/skills/` 下全部 8 个 skills

---

## 审计方法

读取每个 skill 的 `SKILL.md` 文件，检查：
1. YAML frontmatter 格式
2. 是否有来源 URL、commit hash、许可证声明
3. 是否有下载自官方仓库的证据
4. 内容是否引用项目特定路径和规则
5. 是否有危险命令

---

## 逐项审计结果

| # | skill_name | path | exists | has_yaml_frontmatter | frontmatter_name | description_quality | referenced_files_exist | contains_scripts | contains_shell_commands | dangerous_command_risk | source_type | source_evidence | license_evidence | recommended_action |
|---|------------|------|--------|---------------------|------------------|--------------------|-----------------------|-----------------|------------------------|------------------------|-------------|-----------------|-------------------|--------------------|
| 1 | env-cross-platform | `.claude/skills/env-cross-platform/SKILL.md` | ✅ | ✅ | env-cross-platform | 清晰 — 跨平台兼容规则 | ✅ (pathlib, .python-version, scripts/doctor.py 等均存在) | ❌ | 仅有文档示例 | 无 | project-custom-rewritten; inspired by official skill structure | 内容引用本项目 pathlib 规范、conda+pip 单 requirements 方案、.python-version、scripts/doctor.py — 全部为项目自定义 | 无外部许可证 | keep |
| 2 | github-workflow | `.claude/skills/github-workflow/SKILL.md` | ✅ | ✅ | github-workflow | 清晰 — 面向非技术成员 Git 教程 | ✅ (TruthNet 仓库 URL、分支策略等均正确) | ❌ | 仅有文档示例 | 无 | project-custom-rewritten | 引用本项目 GitHub 仓库地址 (zzyuanyi/TruthNet)、项目分支策略 (main/dev/feature) | 无外部许可证 | keep |
| 3 | api-contract-first | `.claude/skills/api-contract-first/SKILL.md` | ✅ | ✅ | api-contract-first | 清晰 — 接口先行流程完整 | ✅ (docs/API_CONTRACT.md, backend/app/schemas/ 等均存在) | ❌ | 仅有文档示例 | 无 | project-custom-rewritten | 引用本项目统一响应结构、WebSocket 消息类型、API_CONTRACT.md、INTERFACE_CHANGELOG.md | 无外部许可证 | keep |
| 4 | software-engineering | `.claude/skills/software-engineering/SKILL.md` | ✅ | ✅ | software-engineering | 清晰 — 分层架构 + 设计模式 | ⚠️ 引用文件 `backend/app/agents/finance_agent.py` 等尚未创建 | ❌ | 仅有代码示例 | 无 | project-custom-rewritten | 引用本项目分层 (Agent/Skill/Service/Repository) 和设计模式位置，但具体 agent 文件尚未实现 | 无外部许可证 | keep (引用文件待后续实现) |
| 5 | interface-review | `.claude/skills/interface-review/SKILL.md` | ✅ | ✅ | interface-review | 清晰 — 审查清单完整 | ✅ (docs/API_CONTRACT.md, docs/DATA_CONTRACT.md, docs/INTERFACE_CHANGELOG.md 均存在) | ❌ | 仅有文档引用 | 无 | project-custom-rewritten | 引用本项目文档体系 | 无外部许可证 | keep |
| 6 | safe-skill-import | `.claude/skills/safe-skill-import/SKILL.md` | ✅ | ✅ | safe-skill-import | 清晰 — 安全审计流程完整 | ✅ | ❌ | 仅有文档示例 | 无 | project-custom-rewritten; inspired by official Claude Code plugin ecosystem docs | 引用 Anthropic 官方 bundled skills 和 marketplace 概念，但流程和模板均为项目自定义 | 无外部许可证 | keep |
| 7 | data-finance-contract | `.claude/skills/data-finance-contract/SKILL.md` | ✅ | ✅ | data-finance-contract | 清晰 — 财务勾稽规则格式 + 评测指标完整 | ✅ (data/ raw/ processed/ 目录结构正确) | ❌ | 仅有 JSON 示例 | 无 | project-custom-rewritten | 引用本项目数据目录规范、SQLite schema、财务勾稽规则格式 — 全部为赛题自定义 | 无外部许可证 | keep |
| 8 | agent-architecture | `.claude/skills/agent-architecture/SKILL.md` | ✅ | ✅ | agent-architecture | 清晰 — Agent 执行顺序 + 容错规则完整 | ⚠️ 引用文件 `backend/app/agents/orchestrator.py` 等尚未创建 | ❌ | 仅有代码示例 | 无 | project-custom-rewritten | 引用本项目 Agent 架构设计 (编排/记忆/勾稽/问答 + 股权穿透/舆情 Skill) | 无外部许可证 | keep (引用文件待后续实现) |

---

## 审计结论

### 来源判断

- **全部 8 个 skills 均为 `project-custom-rewritten`**
- **没有任何 skill 是 `anthropic-official-downloaded`**
- **没有任何 skill 是 `third-party-downloaded`**

### 证据

1. 所有 8 个 skill 的 `SKILL.md` 文件中**均未包含**：
   - 官方下载 URL
   - 原始仓库路径
   - commit hash
   - 许可证声明
   - 原始作者信息
   - 任何外部引用链接

2. 所有 skill 引用的路径（如 `backend/app/schemas/`、`docs/API_CONTRACT.md`、`scripts/doctor.py`、`data/raw/`）均为 **TruthNet 项目特定路径**。

3. 所有 skill 的内容（如 conda+pip 流程、TruthNet 仓库地址、财务勾稽规则格式、Agent 执行顺序）均为 **针对本项目的自定义规则**。

4. Skills 的 YAML frontmatter 结构（`name` + `description`）是 Claude Code 的通用规范格式，并非来自任何特定外部来源 — 所有 skill 都遵循此格式是标准做法。

### 结构合规性

- ✅ 所有 8 个 skill 均有正确的目录结构：`.claude/skills/<name>/SKILL.md`
- ✅ 所有 8 个 skill 均有有效的 YAML frontmatter
- ✅ 所有 8 个 skill 的 `name` 字段与目录名一致
- ✅ 所有 8 个 skill 的 `description` 清晰描述了用途

### 安全审计

- ✅ 没有任何 skill 包含 `curl | bash`、`rm -rf`、`sudo` 等危险命令
- ✅ 没有任何 skill 包含读取密钥、上传代码、修改全局配置的指令
- ✅ 没有任何 skill 包含下载未知二进制或执行外部脚本的指令
- ✅ 没有任何 skill 硬编码真实路径、密钥、代理地址

### 引用完整性

- ⚠️ skill 4 (software-engineering) 引用了 `backend/app/agents/finance_agent.py`、`backend/app/core/llm.py`、`backend/app/core/factory.py` 等文件，这些文件尚不存在（属于后续实现内容）
- ⚠️ skill 8 (agent-architecture) 引用了 `backend/app/agents/orchestrator.py`、`backend/app/skills/ownership_skill.py` 等文件，这些文件尚不存在
- 这不算错误 — skill 是为将来开发准备的指导性文档

### 与 Prompt1 报告的一致性

Prompt1 报告称 "已创建 8 个 project skills"，结论与此一致。Prompt1 报告中**没有**错误地将这些 skills 描述为 "官方 installed skills" 或 "downloaded from Anthropic"。

然而，`docs/external_skill_research.md` 中未明确说明 "当前 skills 是项目自定义而非官方下载" — 这是一个轻微模糊点，应在本次审计中修正。

---

## 修正建议

1. ✅ 保持所有 8 个 skills 不变 — 结构合规、内容完整、安全无风险
2. ✅ 更新 `docs/SKILL_INDEX.md`，明确标注所有 skills 为 "project-custom skill"
3. ✅ 更新 `docs/external_skill_research.md`，追加声明

---

## 最终结论

> **当前 `.claude/skills/` 下的 8 个 skills 是 TruthNet 项目自定义 skills，不是 Anthropic 官方直接下载的 bundled skills。它们参考了 Claude Code 官方 skill 的目录结构和 YAML frontmatter 组织方式（这是 Claude Code 的标准规范），用于项目内协作规范，不应被描述为"已安装官方 skill"。**
