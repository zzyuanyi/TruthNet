# ADR-0001: 项目工程基线决策

**日期**：2024-07-02
**状态**：已采纳
**决策者**：项目负责人

---

## 背景

TruthNet 项目启动时，仓库为空或仅含极少量文件。需要在开发业务功能之前建立工程基线，确保团队（多数为金融背景，仅1人计算机背景）能高效协作。

---

## 决策 1：conda + pip + 单 requirements.txt

**选择**：使用 conda 管理 Python 环境隔离和版本，pip 从唯一的 `requirements.txt` 安装依赖，所有包固定版本。

**原因**：
- conda 跨平台（Windows/macOS/Linux）统一体验
- 单一文件降低非计算机成员的认知负担
- 固定版本消除"在我电脑上能跑"的问题
- 拒绝 `requirements-dev.txt`、`constraints.txt` 等多文件方案

**替代方案**：
- Poetry：功能强大但学习成本高，不适用非计算机成员
- 纯 pip + venv：可行但跨平台环境管理不如 conda 便利
- 多个 requirements 文件：增加维护负担，团队易混淆

---

## 决策 2：使用 `.claude/skills/` 项目级 skills

**选择**：在 `.claude/skills/` 下创建项目级 Claude Code skills，覆盖环境、协作、接口、工程、数据、Agent 架构等。

**原因**：
- Claude Code 是团队主要 AI 编程助手
- Skills 提供可复用的上下文规则，无需每次都重复说明
- 面向非计算机成员设计的 skills（如 github-workflow）降低协作门槛

**替代方案**：
- 只在 CLAUDE.md 中写规则：规则太多会导致上下文过长
- 使用外部 skill 仓库：安全审计成本高，不可控

---

## 决策 3：Contract-First（接口先行）

**选择**：所有接口开发前先定 Pydantic schema → 更新 API_CONTRACT.md → 提供 mock JSON → 再实现。

**原因**：
- 前后端可独立并行开发
- Pydantic 提供自动校验，减少运行时错误
- Mock JSON 让非技术成员也能理解接口行为
- 接口稳定后减少返工

**替代方案**：
- Code-First（先写实现再提取接口）：前端无法并行，后期接口不稳定
- 只用口头约定：不可追溯、不可验证

---

## 决策 4：main/dev/feature 分支模型

**选择**：`main`（稳定）← `dev`（集成）← `feature/*`（功能开发）。

**原因**：
- 简单，非计算机成员容易理解
- `dev` 保护 `main` 不接收未验证代码
- feature 分支隔离各人的开发，互不影响

**替代方案**：
- GitHub Flow（main + feature）：缺少集成分支，多特性并行时风险高
- Git Flow（含 release/hotfix）：对当前团队规模过度复杂

---

## 决策 5：MVP 使用 NetworkX 而非 Neo4j

**选择**：MVP 阶段使用 NetworkX 内存图分析。

**原因**：
- 零部署依赖，团队成员不需要安装和配置 Neo4j
- 适合当前规模的股权穿透测试（数百到数千节点）
- Python 原生，与数据分析工具链（pandas/numpy）无缝集成
- 后续可按需升级到 Neo4j（通过 Repository 模式隔离）

---

## 决策 6：MVP 使用 SQLite

**选择**：MVP 阶段使用 SQLite 作为关系数据库。

**原因**：
- 零配置，单个文件，跨平台
- 适合原型阶段和单人/少量并发场景
- 项目最终交付可能需要演示平台，SQLite 可轻松打包
- 后续可升级到 PostgreSQL（通过 Repository 模式隔离）

---

## 风险与后续可调整点

| 风险 | 缓解措施 | 触发升级条件 |
|------|----------|------------|
| SQLite 并发写入瓶颈 | 后续加读写分离或换 PostgreSQL | 需要 5+ 同时写入 |
| NetworkX 内存不足 | 大图惰性加载或迁移 Neo4j | 图谱节点 > 10 万 |
| conda 在某些机器安装失败 | 提供 venv 备选方案 | 团队反馈 |
| 单 requirements.txt 体积增长 | 按需加入，不过早引入 | — |
| Claude Code skills 需要维护 | 由计算机背景成员维护 | — |

---

## 参考

- [ENVIRONMENT.md](../ENVIRONMENT.md)
- [GIT_WORKFLOW.md](../GIT_WORKFLOW.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
