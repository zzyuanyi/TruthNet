"""TruthNet 评测指标 — 9 项自动化指标（V12 §14.3 Measure）."""

from typing import Any


# ══════════════════════════════════════════════════════════
# 1. 结果准确率
# ══════════════════════════════════════════════════════════


def accuracy(ground_truth: list, predictions: list) -> float:
    """规则触发/不触发的二分类准确率."""
    if not ground_truth:
        return 0.0
    correct = sum(1 for gt, pred in zip(ground_truth, predictions) if gt == pred)
    return correct / len(ground_truth)


# ══════════════════════════════════════════════════════════
# 2. 证据覆盖率
# ══════════════════════════════════════════════════════════


def evidence_coverage(claims: list[dict]) -> float:
    """有证据支撑的 Claim 占比（目标 1.0）."""
    if not claims:
        return 0.0
    with_evidence = sum(
        1 for c in claims if c.get("evidence_ids") and len(c["evidence_ids"]) > 0
    )
    return with_evidence / len(claims)


# ══════════════════════════════════════════════════════════
# 3. 多轮主体保持率
# ══════════════════════════════════════════════════════════


def entity_retention_rate(
    turns: list[dict],
    expected_entity: str | list[str] | dict,
    field: str = "company_code",
    id_key: str = "turn_id",
) -> float:
    """多轮对话中系统正确记住当前主体的比例.

    expected_entity 三种形态（2026-08-12 六轮审查 P2-2 修订）：
      - str：全局预期（兼容既有调用），分母为 turns 数；
      - list：按轮位置对齐，**长度必须与 turns 一致**（先检查长度、
        再处理空输入——turns=[] 而 expected=["A"] 必须抛错），
        不猜测缺失位置；
      - dict：按 id_key（默认 turn_id）关联，{turn_id: 预期公司}——
        键与实际 id_key 强制非空字符串；预期轮次作分母、缺失预期
        ID 计错；**额外实际轮次（不在预期中的 ID）报输入错误**；
        重复实际 ID 报输入错误。
    """
    if isinstance(expected_entity, (list, tuple)):
        if len(expected_entity) != len(turns):
            raise ValueError(
                f"expected_entity 长度 {len(expected_entity)} 与 turns 长度 "
                f"{len(turns)} 不一致：拒绝按位置对齐（无法判断缺失位置），"
                "请使用 dict 按 turn_id 关联"
            )
        if not turns:
            return 0.0  # 长度一致且为空 → 无数据
        correct = sum(
            1 for t, exp in zip(turns, expected_entity) if t.get(field) == exp
        )
        return correct / len(turns)
    if isinstance(expected_entity, dict):
        # 先规范化所有预期键，构造字典前检查规范化键重复
        # （{1: "A", "1": "B"} → 规范化后 "1" 重复 → 报错，不静默覆盖）
        expected_norm: dict[str, object] = {}
        for k, v in expected_entity.items():
            nk = str(k).strip()
            if not nk:
                raise ValueError("expected_entity dict 键不得为空字符串")
            if nk in expected_norm:
                raise ValueError(f"预期键重复（规范化后）: {nk!r}")
            expected_norm[nk] = v
        if not expected_norm:
            if not turns:
                return 0.0  # 预期与实际都为空
            raise ValueError("空预期 + 非空实际：实际轮次全部超出预期")
        if not turns:
            return 0.0  # 预期非空、实际全缺失 → 0.0
        seen_ids: set[str] = set()
        actual_by_id: dict[str, object] = {}
        for t in turns:
            tid = str(t.get(id_key) or "").strip()
            if not tid:
                raise ValueError(f"turns 缺少非空 {id_key}，无法按 ID 对齐")
            if tid in seen_ids:
                raise ValueError(f"重复 {id_key}: {tid!r}，无法对齐")
            seen_ids.add(tid)
            actual_by_id[tid] = t.get(field)
        extra = sorted(set(actual_by_id) - set(expected_norm))
        if extra:
            raise ValueError(f"实际轮次超出预期: {extra}（缺失预期计错、额外实际报错）")
        correct = sum(
            1 for tid, exp in expected_norm.items() if actual_by_id.get(tid) == exp
        )
        return correct / len(expected_norm)
    if not turns:
        return 0.0
    correct = sum(1 for t in turns if t.get(field) == expected_entity)
    return correct / len(turns)


# ══════════════════════════════════════════════════════════
# 4. 无证据 Claim 比例
# ══════════════════════════════════════════════════════════


def unverified_claim_ratio(claims: list[dict]) -> float:
    """无证据支撑的 Claim 占比（目标 0.0）.

    空输入（无 Claim）→ 0.0（无 Claim 即无"无证据 Claim"，不得判 100%）。
    """
    if not claims:
        return 0.0
    return 1.0 - evidence_coverage(claims)


# ══════════════════════════════════════════════════════════
# 5. partial 比例
# ══════════════════════════════════════════════════════════


def partial_response_rate(module_statuses: list[dict]) -> float:
    """返回部分结果的模块占比."""
    if not module_statuses:
        return 0.0
    partial_or_failed = sum(
        1 for m in module_statuses if m.get("state") in ("partial", "failed")
    )
    return partial_or_failed / len(module_statuses)


# ══════════════════════════════════════════════════════════
# 6. 模块超时率
# ══════════════════════════════════════════════════════════


def module_timeout_rate(
    modules: list[dict],
    deadlines: dict[str, float] | None = None,
) -> dict[str, float]:
    """每个模块超过 deadline 的比例."""
    if deadlines is None:
        deadlines = {"finance": 3000, "equity": 4000, "events": 3000}
    if not modules:
        return {}
    counts: dict[str, int] = {}
    timeouts: dict[str, int] = {}
    for m in modules:
        name = m.get("module_name", "unknown")
        counts[name] = counts.get(name, 0) + 1
        deadline = deadlines.get(name, 8000)
        # duration_ms=None（未采集耗时的模块）不算超时，避免 NoneType 比较崩溃
        duration = m.get("duration_ms")
        if duration is not None and duration > deadline:
            timeouts[name] = timeouts.get(name, 0) + 1
    return {name: timeouts.get(name, 0) / cnt for name, cnt in counts.items()}


# ══════════════════════════════════════════════════════════
# 7. 风险等级校准
# ══════════════════════════════════════════════════════════


def risk_calibration(
    predicted_levels: list[str],
    ground_truth_levels: list[str],
) -> dict[str, Any]:
    """系统风险等级 vs 人工标注的混淆矩阵统计."""
    if not predicted_levels:
        return {"accuracy": 0.0, "kappa": 0.0, "confusion": {}}

    correct = sum(1 for p, g in zip(predicted_levels, ground_truth_levels) if p == g)
    acc = correct / len(predicted_levels)

    levels = ["red", "orange", "yellow", "green", "unknown"]
    confusion: dict[str, dict[str, int]] = {
        level: {l2: 0 for l2 in levels} for level in levels
    }
    for p, g in zip(predicted_levels, ground_truth_levels):
        confusion.setdefault(p, {})
        confusion[p][g] = confusion[p].get(g, 0) + 1

    po = acc
    n = len(predicted_levels)
    pe = 0.0
    for level in levels:
        row_sum = sum(confusion[level].values())
        col_sum = sum(confusion[l2].get(level, 0) for l2 in confusion)
        if n > 0:
            pe += (row_sum / n) * (col_sum / n)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 0.0

    return {"accuracy": round(acc, 3), "kappa": round(kappa, 3), "confusion": confusion}


# ══════════════════════════════════════════════════════════
# 8. 行业分位差异
# ══════════════════════════════════════════════════════════


def industry_variance(
    results: list[dict],
    metric_key: str = "accuracy",
) -> dict[str, Any]:
    """按行业分组后某项指标的方差."""
    if not results:
        return {"std_dev": 0.0, "max_gap": 0.0}

    by_industry: dict[str, list[float]] = {}
    for r in results:
        ind = r.get("industry_l1", "unknown")
        val = r.get(metric_key, 0)
        by_industry.setdefault(ind, []).append(val)

    means = {
        ind: sum(vals) / len(vals) if vals else 0.0 for ind, vals in by_industry.items()
    }
    if not means:
        return {"std_dev": 0.0, "max_gap": 0.0}

    mean_of_means = sum(means.values()) / len(means)
    variance = sum((v - mean_of_means) ** 2 for v in means.values()) / len(means)
    std_dev = variance**0.5

    sorted_inds = sorted(means.items(), key=lambda x: x[1])
    max_gap = sorted_inds[-1][1] - sorted_inds[0][1] if len(sorted_inds) >= 2 else 0.0

    return {
        "std_dev": round(std_dev, 4),
        "max_gap": round(max_gap, 4),
        "min_industry": sorted_inds[0][0],
        "max_industry": sorted_inds[-1][0],
        "by_industry": {k: round(v, 4) for k, v in means.items()},
    }


# ══════════════════════════════════════════════════════════
# 9. LLM 输出格式合规率
# ══════════════════════════════════════════════════════════


def schema_compliance_rate(
    responses: list[dict],
    schema_fields: list[str] | None = None,
) -> float:
    """LLM 输出是否符合预定义 Schema."""
    if schema_fields is None:
        schema_fields = ["rule_id", "severity", "evidence_ids"]
    if not responses:
        return 0.0
    compliant = sum(
        1 for r in responses if all(f in r and r[f] is not None for f in schema_fields)
    )
    return compliant / len(responses)


# ══════════════════════════════════════════════════════════
# 汇总
# ══════════════════════════════════════════════════════════


def evaluate_all(
    ground_truth: dict,
    predictions: dict,
    claims: list[dict],
    turns: list[dict],
    module_statuses: list[dict],
    modules: list[dict],
    expected_entity: str | list[str] | dict[str, str] = "",
) -> dict[str, Any]:
    """一站式评测：计算全部 9 项指标并返回报告."""
    return {
        "1_accuracy": accuracy(
            ground_truth.get("rule_results", []),
            predictions.get("rule_results", []),
        ),
        "2_evidence_coverage": evidence_coverage(claims),
        "3_entity_retention_rate": entity_retention_rate(turns, expected_entity),
        "4_unverified_claim_ratio": unverified_claim_ratio(claims),
        "5_partial_response_rate": partial_response_rate(module_statuses),
        "6_module_timeout_rate": module_timeout_rate(modules),
        "7_risk_calibration": risk_calibration(
            predictions.get("risk_levels", []),
            ground_truth.get("risk_levels", []),
        ),
        "8_industry_variance": industry_variance(
            predictions.get("per_industry", []),
        ),
        "9_schema_compliance_rate": schema_compliance_rate(
            predictions.get("llm_outputs", []),
        ),
    }
