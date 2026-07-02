# 外部 Skill 搜索与安全审计报告

**日期**：2024-07-02（Prompt1），2026-07-02 补充（Prompt2）
**执行人**：Claude Code

---

## Prompt2 补充声明

> **`.claude/skills/` 下已创建的 8 个 skills 全部为 TruthNet 项目自定义 skills（project-custom-rewritten）。**
> 没有任何 skill 是从 Anthropic 官方仓库直接下载或从第三方引入的。
> 它们参考了 Claude Code 官方 skill 的组织方式（`.claude/skills/<name>/SKILL.md` 目录结构 + YAML frontmatter 格式），内容全部由项目团队编写，针对 TruthNet 项目的环境、Git、API、数据、Agent 等特定需求。
> 详细审计见 `reports/prompt2/skill_source_audit.md`。

---

## 搜索范围

搜索 Claude Code 生态中可用的 skills、hooks、commands 资源，评估是否适合引入 TruthNet 项目。

---

## 发现的资源

### 1. Claude Code 官方 Bundled Skills

| 属性 | 内容 |
|------|------|
| **名称** | skill-creator, code-review, verify, loop, run 等 |
| **来源** | Anthropic 官方内置 |
| **许可证** | 随 Claude Code 发布 |
| **是否官方** | ✅ 是 |
| **是否建议引入** | ✅ 建议直接使用 |
| **风险** | 极低 |
| **本项目处理方式** | 作为 Claude Code 内置功能直接使用，无需安装。技能如 `skill-creator` 可帮助团队创建和评测自定义 skills，写入文档作为可选工具。 |

### 2. Anthropic 官方 Skill Marketplace / Plugin Registry

| 属性 | 内容 |
|------|------|
| **名称** | Claude Code plugins ecosystem |
| **来源** | docs.anthropic.com |
| **许可证** | 各插件独立 |
| **是否官方** | ✅ 由 Anthropic 管理 |
| **是否建议引入** | 🔶 按需评估，单个审计 |
| **风险** | 低（有官方审核门槛） |
| **本项目处理方式** | 未来如果需要，按 `safe-skill-import` skill 流程逐个审计后再引入。当前不主动引入。 |

### 3. GitHub Awesome Lists

| 属性 | 内容 |
|------|------|
| **名称** | awesome-claude-code, awesome-claude 等社区列表 |
| **来源** | GitHub 社区 |
| **许可证** | 各项目独立（常见 MIT/Apache-2.0） |
| **是否官方** | ❌ 非官方 |
| **是否建议引入** | ❌ 不直接引入可执行内容 |
| **风险** | 中等（质量参差不齐、可能含恶意代码） |
| **本项目处理方式** | 只参考目录组织方式，不复制任何可执行脚本。如需引入特定项目，必须按 `safe-skill-import` 流程审计。 |

### 4. 社区 Claude Code Skills 仓库

| 属性 | 内容 |
|------|------|
| **名称** | 各类 GitHub 上的 `.claude/skills/` 示例 |
| **来源** | 分散的 GitHub 仓库 |
| **许可证** | 各项目独立 |
| **是否官方** | ❌ 非官方 |
| **是否建议引入** | ❌ 不直接引入 |
| **风险** | 高（无质量保证、可能修改 git config、上传代码） |
| **本项目处理方式** | 只参考结构（目录组织、SKILL.md frontmatter 格式），内容全部自行编写。严禁自动执行 curl \| bash 或下载未知二进制。 |

### 5. MCP (Model Context Protocol) Servers

| 属性 | 内容 |
|------|------|
| **名称** | MCP ecosystem（如 filesystem、github、postgres servers） |
| **来源** | GitHub: modelcontextprotocol/servers |
| **许可证** | MIT / Apache-2.0 |
| **是否官方** | ✅ 由 Anthropic 主导 |
| **是否建议引入** | 🔶 按需引入（现阶段不需要） |
| **风险** | 低（官方维护，代码公开） |
| **本项目处理方式** | 当前 MVP 阶段不需要 MCP server。后续如需接入数据库或文件系统操作，优先评估官方 MCP server。 |

---

## 审计结论

### 当前建议

1. **直接使用**：Claude Code 官方内置 skills（skill-creator, code-review, verify, loop, run 等）
2. **参考结构**：社区 `.claude/skills/` 的目录组织和 YAML frontmatter 格式
3. **保持观望**：MCP servers、官方 marketplace 插件
4. **禁止引入**：未审计的第三方可执行脚本、未知二进制

### 安全原则（写入 `safe-skill-import` skill）

- 优先使用官方来源
- 所有外部引入必须经过安全审计
- 不直接 vendoring 外部代码
- 提取思想，重写成本项目 skill
- 绝不自动执行 `curl | bash`

---

## 相关文件

- `.claude/skills/safe-skill-import/SKILL.md` — 安全引入流程
- `docs/SKILL_INDEX.md` — 项目 skills 索引
