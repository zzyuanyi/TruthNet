---
name: safe-skill-import
description: 外部 Skill 安全引入流程。搜索、评估、引入外部 Claude Code skills/hooks/commands 时使用。
---

# 外部 Skill 安全引入

## 当前 skill 来源声明

> **`.claude/skills/` 下的所有 skills 是 TruthNet 项目自定义 skills（project-custom）。**
> 它们参考了 Claude Code 官方 skill 目录结构组织方式，内容由项目团队为 TruthNet 特定需求编写。
> 不是 Anthropic 官方直接下载的 bundled skills。
> 详见 `reports/prompt2/skill_source_audit.md`。

---

## 优先来源（按可信度排序）

1. **Claude Code 官方 bundled skills** — 随 Claude Code 内置
2. **Anthropic 官方 marketplace / plugin registry** — 官方审核
3. **高星开源仓库或官方 awesome list** — 社区但质量较高
4. **个人/小团队博客或 Gist** — 需要最高程度审计

---

## 引入前必须审计

在引入任何外部 skill 前，逐项检查：

### 来源审计
- [ ] 许可证是什么？（MIT / Apache-2.0 / GPL / 无许可证）
- [ ] 最近一次提交是什么时候？（>6 个月未更新 = 风险）
- [ ] 仓库是否有多个贡献者？
- [ ] 是否有 issue/PR 讨论安全问题？

### 代码审计
- [ ] 是否包含 `curl | bash` 或类似危险模式？
- [ ] 是否包含 `rm -rf`、`sudo`、`chmod 777` 等危险命令？
- [ ] 是否访问网络？访问哪些 URL？
- [ ] 是否读取/上传代码、密钥、环境变量？
- [ ] 是否修改 `~/.gitconfig`、`~/.ssh/config`、全局设置？
- [ ] 是否覆盖现有项目规范（如 `.editorconfig`、`requirements.txt`）？
- [ ] 是否下载二进制文件/可执行文件？
- [ ] 是否下载 Anaconda/Miniconda 安装器？
- [ ] 是否自动执行 `pip install` / `npm install -g`？

### 兼容性审计
- [ ] 是否与本项目的 `env-cross-platform` 规则冲突？
- [ ] 是否与本项目的编码/路径规范冲突（UTF-8, LF, pathlib）？
- [ ] 是否与本项目的分支策略冲突？
- [ ] 是否与本项目的 `requirements.txt` 单文件策略冲突？
- [ ] 是否在 Windows/macOS/Linux 上均可运行？

---

## 默认策略

### ❌ 禁止
- 自动执行 `curl | bash`
- 自动提交密钥、token 到仓库
- 修改用户全局 Git/SSH 配置
- 下载未知来源的二进制文件
- 直接复制第三方可执行脚本
- 自动下载 Anaconda/Miniconda 安装器
- 在未确认的情况下自动执行 `conda create` / `pip install`

### ✅ 允许
- 阅读和理解第三方 skill 的**设计思想**
- **重写**成本项目的 `SKILL.md`（不复制代码，只借鉴思路）
- 使用 Claude Code 官方 bundled skills
- 使用 `python scripts/env_bootstrap.py --check` 检测环境

### 🔶 例外（需额外审计记录）
- 如果必须引用外部 skill 的完整文件，放入 `docs/external_audit/` 并撰写审计报告
- 审计报告必须包含：来源、许可证、审计日期、审计结论、风险点

---

## 审计报告模板

```markdown
# 外部 Skill 审计报告

- **名称**：
- **来源 URL**：
- **版本/commit**：
- **许可证**：
- **审计日期**：
- **审计人**：

## 审计发现

### 危险操作
- 无 / 列出具体问题

### 网络访问
- 无 / 列出 URL

### 文件系统影响
- 无 / 列出路径

### 兼容性
- 是否与本项目规范冲突

## 结论
- [ ] 安全引入
- [ ] 安全但需修改（说明修改点）
- [ ] 不安全，拒绝引入（说明原因）
- [ ] 参考思想重写

## 处理方式
```
