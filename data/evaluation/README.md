# 语义识别回归测试 — 手标数据集说明

> Phase E Task B4。本数据集用于评估公司实体语义识别（确定性 + suggest 语义层），
> 供 `scripts/evaluate_company_entity_linking.py` 消费。所有样本手工标注，基于
> truthnet_test 真库（已种子 10 家公司）的真实确定性行为 + 人类意图核对。

## 文件

- `company_entity_linking.jsonl` — 50 条样本（一条 JSON 一行）。

## Schema

```jsonc
{
  // 多轮样本才有：
  "session_id": "sess_sem_1",      // 会话标识
  "turn_index": 0,                  // 轮次（0 起）

  "query": "分析康美药业的财务状况",

  "expected": {
    "expected_selected_codes": ["600518.SH"],  // 期望绑定 wind_code 集（无绑定则省略）
    "expected_relation": "single",             // single / comparison / no_company / ambiguous / continuation / switch
    "expected_roles": {"600518.SH": "primary"},// 角色（primary / comparison_peer）
    "expected_nil": false,                     // 期望零绑定
    "requires_confirmation": false,            // true=样本存在歧义，任何新绑定都算安全违规
    // 多轮样本才有：
    "expected_active_after": "600518.SH"       // 该轮结束后期望的 active 公司
  }
}
```

## 覆盖类别（50 条）

| 类别 | 条数 | 说明 |
|------|------|------|
| A 精确公司名 | 7 | 完整 sec_name，确定性可精确命中 |
| B 简称 | 4 | 康美/茅台等常见简称 |
| C 动作词吞 sub_span | 3 | 「业绩点评」「存货周转率」等吞实体，检验 sub_span 恢复 |
| D 歧义 | 4 | 平安→{平安银行/中国平安/平安电工}，requires_confirmation=true |
| E 非公司语境 | 7 | 市场情绪/研报/行业景气度 → no_company |
| F 不存在实体 | 3 | 飞天科技/星尘科技/紫微科技 → nil |
| G 多公司比较 | 6 | 谁更赚钱/谁先跌/对比 → comparison |
| H 指标语义 | 5 | 存贷双高/应收账款周转率 → 指标 vs 公司边界 |
| I 对抗性 | 6 | 否定句（茅台不是茅台镇）/地名（茅台镇）/歧义对比/动词前置 |
| J 多轮 | 5 | sess_sem_1 的 5 轮（continuation/switch/那康美呢） |

## 判别性样本（确定性基线刻意失败，观察语义层是否改善）

| 样本 | 期望 | 确定性行为 | 语义层观察点 |
|------|------|-----------|-------------|
| 存贷双高是什么意思 | no_company | ambiguous | mentionness 非公司语境删除 |
| 康美和茅台谁更赚钱 | comparison | no_company | 比较意图识别 |
| 茅台和康美的股价，谁先跌的 | comparison | no_company | 比较意图识别 |
| 分析康美的存贷比 | single 600518 | 零绑定 | LLM 建议 select 600518（suggest 只读不应用） |
| 分析茅台不是茅台镇 | no_company | no_company | **suggest 误绑定 600519（否定语境 sub_span 重链）** |
| 为什么星尘科技和茅台都跌了 | ambiguous/nil | no_company | 安全（零绑定） |

## 安全违规定义（评估器 `_safety`）

- `fabricated_code`：绑定 wind_code 不在该 mention 候选集内（结构违规）。
- `auto_bind_on_ambiguity`：`requires_confirmation=true` 的样本上，结果产生确定性
  基线之外的新绑定（suggest/mentionness 重链不得在歧义样本自动绑定新身份）。
  零绑定 no_company / 基线已确认绑定均安全。

## 使用

```bash
# 在 truthnet conda 环境内运行（conda activate truthnet，然后 python …）
# B0 确定性基线（score-target=deterministic：对确定性输出评分）
PYTHONIOENCODING=utf-8 python scripts/evaluate_company_entity_linking.py \
  --input data/evaluation/company_entity_linking.jsonl \
  --output data/reports/company_entity_linking_baseline.jsonl \
  --db truthnet_test --selector-mode off --interpreter-mode off \
  --score-target deterministic --authority-strict on

# B1 suggest（score-target=result：对 suggest 输出评分，selector 只读）
PYTHONIOENCODING=utf-8 python scripts/evaluate_company_entity_linking.py \
  --input data/evaluation/company_entity_linking.jsonl \
  --output data/reports/company_entity_linking_suggest.jsonl \
  --db truthnet_test --selector-mode suggest --interpreter-mode off \
  --score-target result --authority-strict off
```
