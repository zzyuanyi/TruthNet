# 软件工程规范

## 编码与路径规范（Prompt3 硬化）

### 编码

1. 全项目文本文件统一 UTF-8。
2. **所有** Python 文件读写文本必须显式 `encoding="utf-8"`。
3. Windows 控制台输出必须有 UTF-8 保护。
4. 写入文件时使用 `newline="\n"` 确保 LF 换行。

```python
# ✅ 正确
Path("file.md").read_text(encoding="utf-8")
Path("file.md").write_text(content, encoding="utf-8", newline="\n")
open("file.txt", "w", encoding="utf-8")

# ❌ 错误
Path("file.md").read_text()          # 可能使用系统默认编码
open("file.txt", "w")                # 可能使用系统默认编码
```

### 路径

5. 所有 Python 路径使用 `pathlib.Path`。
6. 禁止硬编码盘符（`C:\`, `D:\`, `E:\`, `F:\`）、用户名、绝对路径。
7. 禁止在业务代码里写死 `\` 或 `/` 作为路径拼接。
8. 使用 `ROOT / "data" / "raw" / "file.csv"` 风格拼接。

```python
# ✅ 正确
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
data_file = ROOT / "data" / "raw" / "file.csv"

# ❌ 错误
data_path = "C:\\Users\\admin\\project\\data\\raw\\file.csv"
data_path = "/home/user/TruthNet/data/raw/file.csv"
```

### 换行符

9. Git 仓库统一 LF 换行符（`.gitattributes` 已配置）。
10. `.editorconfig` 已配置 `end_of_line = lf`。

### Windows UTF-8 保护模板

所有脚本入口应包括：

```python
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

### CI 与本地行为分离

- CI 模式：非交互，通过 `--ci` 参数控制
- 本地模式：可提示用户确认，不自动执行危险操作

---

## 分层架构

```text
┌─────────────────────────────────────┐
│  API Layer (app/api/)               │  ← 只处理 HTTP/WebSocket 请求/响应、参数校验
├─────────────────────────────────────┤
│  Agent Layer (app/agents/)          │  ← 编排推理流程：记忆 → 意图 → 工具 → 回答
├─────────────────────────────────────┤
│  Skill Layer (app/skills/)          │  ← 确定性工具能力：股权穿透、舆情查询
├─────────────────────────────────────┤
│  Service Layer (app/services/)      │  ← 业务服务：财报分析、风险评分
├─────────────────────────────────────┤
│  Repository Layer (app/core/)       │  ← 数据访问：SQLite、NetworkX、ChromaDB
├─────────────────────────────────────┤
│  Schema Layer (app/schemas/)        │  ← Pydantic 数据契约，所有跨层传输的 DTO
└─────────────────────────────────────┘
```

### 各层职责

| 层 | 允许 | 禁止 |
|----|------|------|
| **API** | 参数校验、路由、调用 Agent、组装响应 | ❌ 业务逻辑、财务规则、SQL |
| **Agent** | 编排推理流程、工具调用决策 | ❌ 直接写 SQL、直接操作 ChromaDB |
| **Skill** | 确定性算法、图谱遍历、数据聚合 | ❌ LLM 调用决策（那是 Agent 的事） |
| **Service** | 可复用的业务计算 | ❌ HTTP 相关逻辑 |
| **Repository** | 数据库/图/向量库的增删改查 | ❌ 业务判断 |
| **Schema** | 数据结构定义、校验规则 | ❌ 任何运行时逻辑 |

---

## Git 协作规范（Prompt3 硬化）

### 人工确认式流程

1. Claude Code 不得自动 commit
2. Claude Code 不得自动 push
3. Claude Code 不得自动 merge
4. 每位开发者使用个人 feature 分支（`feature/用户名-模块名`）
5. 开始编辑前询问是否对齐远程 main/dev
6. 结束编辑后询问是否保存/提交
7. 提交前运行完整检查

详见 `docs/GIT_WORKFLOW.md`。

---

## 设计模式

### Strategy（策略模式）
**位置**：财务勾稽规则、风险评分策略
```python
# 不同勾稽规则可互换
class RevenueCashCheck(CheckStrategy):
    def check(self, data): ...

class InventoryTurnoverCheck(CheckStrategy):
    def check(self, data): ...
```

### Adapter（适配器模式）
**位置**：不同 LLM 提供商、不同嵌入模型、不同数据源
```python
class LLMAdapter(ABC):
    @abstractmethod
    def chat(self, messages): ...

class OpenAIAdapter(LLMAdapter): ...
class LocalModelAdapter(LLMAdapter): ...
```

### Facade（外观模式）
**位置**：`backend/app/agents/orchestrator.py`
- 对前端统一暴露一个问答入口
- 内部隐藏编排、记忆、Skill 调度的复杂性

### Factory（工厂模式）
**位置**：创建 Agent、Skill、LLM Client
```python
class AgentFactory:
    @staticmethod
    def create_memory_agent(): ...
    @staticmethod
    def create_finance_agent(): ...
```

### Repository（仓库模式）
**位置**：隔离数据访问
```python
class CompanyRepository:
    def get_by_id(self, company_id: str) -> Company: ...

class GraphRepository:
    def get_ownership_chain(self, company_id: str, depth: int) -> nx.DiGraph: ...
```

### DTO / Schema
**位置**：`backend/app/schemas/`
- 所有跨层传输必须使用 Pydantic 模型
- 不允许用 `dict` 或裸 `list` 跨层传递

---

## 命名规范

### Python
| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `ownership_skill.py` |
| 类 | PascalCase | `ChatRequest` |
| 函数/方法 | snake_case | `get_company_risk()` |
| 变量 | snake_case | `risk_score` |
| 常量 | UPPER_SNAKE | `MAX_OWNERSHIP_DEPTH` |
| 私有成员 | _leading_underscore | `_build_graph()` |

### TypeScript/React
| 类型 | 规范 | 示例 |
|------|------|------|
| 组件文件 | PascalCase | `ChatPanel.tsx` |
| 工具文件 | camelCase | `formatCurrency.ts` |
| 接口/类型 | PascalCase | `ChatResponse` |
| 函数/变量 | camelCase | `handleSend` |

---

## 测试规范

### 最低要求
- 每个 `agents/` 模块 ≥ 1 个 smoke test
- 每个 `skills/` 模块 ≥ 1 个单元测试
- 每个 `api/` 路由 ≥ 1 个集成测试（test client）
- 关键业务规则必须有测试覆盖
- 编码/路径规范必须有策略验证测试

### 测试结构
```text
backend/tests/
  test_health.py              — 健康检查
  test_api_contract_smoke.py  — chat 接口契约 smoke
  test_stack_smoke.py         — 技术栈 smoke
  test_websocket_smoke.py     — WebSocket smoke (Prompt3)
  test_encoding_path_policy.py — 编码/路径策略验证 (Prompt3)
  test_agents/                — Agent 测试
  test_skills/                — Skill 测试
  test_services/              — Service 测试
```

### 运行
```bash
python -m pytest backend/tests -v
```

---

## 错误处理规范

1. API 层使用 FastAPI 的 `HTTPException`，不返回裸 traceback。
2. Agent 层错误不向上抛，而是填充 `missing_modules` 和降级响应。
3. Service 层抛自定义异常，API 层统一转换为 HTTP 错误。
4. 所有错误必须包含 `trace_id`。

---

## 日志 / trace_id 规范

1. 每个请求生成唯一 `trace_id`（UUID4）。
2. `trace_id` 贯穿所有 Agent → Skill → Service 调用链。
3. 日志格式：
```text
[%(asctime)s] [%(levelname)s] [trace_id=%(trace_id)s] %(message)s
```
4. 工具调用日志必须记录：输入摘要、输出摘要、耗时、错误。

---

## 接口稳定性规范

1. `docs/API_CONTRACT.md` 是前后端共同事实来源。
2. `backend/app/schemas/` 是后端实现的事实来源。
3. 接口一旦进入 `dev` 分支，视为稳定，不做破坏性修改。
4. 必须修改时：
   - 记录在 `docs/INTERFACE_CHANGELOG.md`
   - 注明影响范围
   - 提供迁移方案
   - 项目负责人审阅

---

## 文档同步规范

| 改动 | 需同步的文档 |
|------|------------|
| 新接口/改接口 | `API_CONTRACT.md`, `INTERFACE_CHANGELOG.md`, 对应 schema |
| 新数据表/改结构 | `DATA_CONTRACT.md`, `INTERFACE_CHANGELOG.md` |
| 架构调整 | `ARCHITECTURE.md`, ADR |
| 新 Skill | `SKILL_INDEX.md`, `SKILL.md` |
| 环境变更 | `ENVIRONMENT.md` |
| 编码/路径规范变更 | `SOFTWARE_ENGINEERING.md`（本文档） |
