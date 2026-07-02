---
name: agent-architecture
description: Agent/Skill 实现架构规范。后端开发时自动激活，确保多 Agent 协作架构一致。
---

# Agent 架构规范

## Agent 角色与职责

### 编排 Agent (Orchestrator)
**文件**：`backend/app/agents/orchestrator.py`

**只负责**：
- 意图识别（用户想问什么？）
- 工具路由（需要调用哪些 Agent/Skill？）
- 并行/串行调度决策
- 降级控制（某模块失败时如何处理）

**不负责**：
- ❌ 具体的财务计算
- ❌ 图谱遍历
- ❌ 嵌入检索
- ❌ 最终回答的格式化

### 对话记忆 Agent (Memory)
**文件**：`backend/app/agents/memory_agent.py`

- **必须最先运行**
- 加载历史对话、关键实体、用户偏好
- 输出结构化记忆上下文

### 财务勾稽 Agent (Finance)
**文件**：`backend/app/agents/finance_agent.py`

- 使用 Strategy 模式执行多规则检查
- 输入：公司代码 + 年份 + 财报数据
- 输出：预警点列表 + 数据对比 + 可能造假模式

### 问答生成 Agent (QA Generator)
**文件**：`backend/app/agents/qa_agent.py`

- **必须最后运行**
- 汇总所有上游 Agent/Skill 的输出
- 生成 Markdown 格式的可解释回答
- 确保证据链完整

### 股权穿透 Skill
**文件**：`backend/app/skills/ownership_skill.py`

- 多跳链路遍历（深度 >3 层）
- 输入：公司代码 + 方向 + 深度
- 输出：图谱 nodes/edges + 控制链

### 舆情事件 Skill
**文件**：`backend/app/skills/event_skill.py`

- 事件簇聚合
- 时间线构建
- 情感分析

## 执行顺序（强制）

```text
1. Memory Agent      ← 先运行
2. Orchestrator      ← 决策路由
3. ┌─ Finance Agent  ← 可并行
   ├─ Ownership Skill
   └─ Event Skill
4. QA Generator      ← 最后运行
```

## 容错规则

- 任一 Skill/Agent 失败时，**不导致全链路崩溃**
- 失败模块在响应的 `missing_modules` 字段中标注
- QA Generator 对缺失模块输出 "该分析暂不可用"

```python
# missing_modules 示例
{
  "missing_modules": [
    {
      "module": "舆情事件 Skill",
      "reason": "该时间段暂无舆情数据",
      "fallback": "仅提供财务分析结果"
    }
  ]
}
```

## LLM 输出校验

所有 LLM 输出必须经过 Pydantic 结构化校验：

```python
from pydantic import ValidationError

try:
    result = FinanceCheckResult.model_validate(llm_output)
except ValidationError:
    # 触发自纠错流程
    result = self_correct(llm_output)
```

## 工具调用追踪

每次工具调用必须记录：

```python
trace = {
    "trace_id": str(uuid4()),
    "tool_name": "ownership_skill",
    "input_summary": "company=600519, depth=3, direction=upstream",
    "output_summary": "found 5 control chains, max depth=4",
    "duration_ms": 234,
    "error": None
}
```

## 自纠错逻辑

至少包含以下阶段：

1. **参数缺失检测** — 提示用户补充必要信息
2. **数据为空检测** — 切换到备选数据源或年份
3. **返回格式校验** — Pydantic 校验失败时，给出修复提示并重试
4. **降级路径** — 一次重试后仍失败，标记 `missing_modules` 并使用降级回答

```python
def self_correct(self, error: Exception, context: dict) -> dict:
    """自纠错：重试一次或降级"""
    if isinstance(error, MissingParameterError):
        return {"needs_input": True, "missing": error.field}
    if isinstance(error, EmptyDataError):
        # 尝试备选年份
        context["fiscal_year"] = context["fiscal_year"] - 1
        return self.retry(context)
    # 其他错误：降级
    return {"degraded": True, "partial_result": ...}
```
