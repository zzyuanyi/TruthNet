"""规则定义接口 D2 — 元数据完整性 / 双 hash / API（2026-08-11）.

覆盖：
- R1-R7 metadata 完整（name/metrics/parameters/conditions）；
- metadata.parameters 的 key 与 thresholds 的 key 完全一致（回归防线）；
- metrics 的 key 不重复；
- 双 hash：稳定可复现、16 位 hex；
- GET /api/v1/rules/definitions：200、7 条规则、结构完整。
"""

from fastapi.testclient import TestClient

from app.domain.finance.financial_rule_config import (
    load_financial_rules,
    rule_hashes,
)

_RULE_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


def _config():
    from app.domain.finance.financial_rule_config import (
        clear_financial_rule_config_cache,
    )

    clear_financial_rule_config_cache()  # 确保读取最新文件
    return load_financial_rules()


def test_metadata_complete_for_all_rules():
    cfg = _config()
    assert set(cfg.metadata.keys()) == set(_RULE_IDS)
    for rid in _RULE_IDS:
        meta = cfg.metadata[rid]
        assert meta.name, f"{rid} 缺少名称"
        assert meta.description, f"{rid} 缺少描述"
        assert meta.metrics, f"{rid} 缺少指标"
        assert (
            meta.conditions.red or meta.conditions.orange or meta.conditions.yellow
        ), f"{rid} 缺少判定说明"


def test_parameter_keys_match_threshold_keys():
    cfg = _config()
    for rid in _RULE_IDS:
        rule_cfg = getattr(cfg.rules, rid.lower())
        threshold_keys = set(rule_cfg.thresholds.model_dump().keys())
        param_keys = set(cfg.metadata[rid].parameters.keys())
        assert param_keys == threshold_keys, (
            f"{rid} 参数 key 与阈值 key 不一致: 缺 {threshold_keys - param_keys}, "
            f"多 {param_keys - threshold_keys}"
        )


def test_metric_keys_unique():
    cfg = _config()
    for rid in _RULE_IDS:
        keys = [m.key for m in cfg.metadata[rid].metrics]
        assert len(keys) == len(set(keys)), f"{rid} 指标 key 重复: {keys}"


def test_hashes_stable_and_format():
    h1, h2 = rule_hashes()
    h1b, h2b = rule_hashes()
    assert h1 == h1b, "evaluation_config_hash 不稳定"
    assert h2 == h2b, "definition_hash 不稳定"
    assert h1 != h2, "两个 hash 不应相同（覆盖范围不同）"
    assert len(h1) == 16 and len(h2) == 16
    int(h1, 16)  # hex 格式
    int(h2, 16)


def test_api_definitions_endpoint():
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/rules/definitions")
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    data = body["data"]
    assert data["source"] == "financial_rules.yaml"
    assert data["version"] == "1.1.0"
    rules = {r["rule_id"]: r for r in data["rules"]}
    assert set(rules.keys()) == set(_RULE_IDS)
    assert len(data["evaluation_config_hash"]) == 16
    assert len(data["definition_hash"]) == 16
    # 结构抽查
    r1 = rules["R1"]
    assert r1["name"] == "应收–营收背离"
    assert r1["enabled"] is True
    assert any(m["key"] == "gap" for m in r1["metrics"])
    assert any(p["key"] == "red_consecutive_gap_pp" for p in r1["parameters"])
    assert r1["conditions"]["red"], "R1 red 判定说明为空"
    assert r1["thresholds"]["red_consecutive_gap_pp"] == 50
    # v3.4：parameters 携带实际阈值值（与 thresholds 同源）
    r1_param = next(p for p in r1["parameters"] if p["key"] == "red_consecutive_gap_pp")
    assert r1_param["value"] == 50
    assert r1_param["value"] == r1["thresholds"]["red_consecutive_gap_pp"]


def test_execution_version_consistent_with_settings():
    """v3.4：execution_version 与 RULE_SET_VERSION 尾号一致（Claim/缓存键统一）。"""
    from app.core.config import settings
    from app.domain.finance.financial_rule_config import get_execution_version

    version = get_execution_version()
    assert version == "1.0.0"
    assert settings.RULE_SET_VERSION.endswith(version), (
        f"RULE_SET_VERSION({settings.RULE_SET_VERSION}) 尾号应与 "
        f"execution_version({version}) 一致"
    )


def test_r3_metrics_cover_current_keys():
    """v3.4：R3 展示指标覆盖运行时 current 全部键（cash/debt/implied_rate）。"""
    cfg = _config()
    r3_metric_keys = {m.key for m in cfg.metadata["R3"].metrics}
    assert {"cash_to_assets", "debt_to_assets", "implied_interest_rate"} <= (
        r3_metric_keys
    )


# v3.5：R1-R7 运行时 current 指标 key（与 rule_rN.py 的 current 构造一致）——
# 展示元数据必须覆盖全部运行时 key，缺任一即补 YAML。
_CURRENT_KEYS = {
    "R1": {"acct_rcv_growth", "oper_rev_growth", "gap"},
    "R2": {"cf_to_profit_ratio", "consec_neg_cf"},
    "R3": {
        "cash_to_assets",
        "debt_to_assets",
        "implied_interest_rate",
    },
    "R4": {
        "inventory_yoy",
        "oper_rev_yoy",
        "growth_gap",
        "inventory_turnover_days",
        "turnover_change",
    },
    "R5": {"gross_margin", "gm_deviation", "er_deviation"},
    "R6": {
        "oth_rcv_to_assets",
        "oth_rcv_large",
        "oth_rcv_yoy",
        "oth_rcv_to_acct_rcv",
    },
    "R7": {
        "core_profit_ratio",
        "non_recurring_ratio",
        "net_profit_yoy",
        "quality_divergence",
        "revenue_divergence",
    },
}


def test_all_rules_metrics_cover_current_keys():
    """v3.5：R1-R7 展示指标覆盖全部运行时 current key（不再只查 R3）。"""
    cfg = _config()
    for rid in _RULE_IDS:
        metric_keys = {m.key for m in cfg.metadata[rid].metrics}
        missing = _CURRENT_KEYS[rid] - metric_keys
        assert not missing, f"{rid} 指标元数据缺运行时 key: {sorted(missing)}"


def test_api_execution_version_present():
    """v3.5：/rules/definitions 响应含 execution_version（与 YAML 一致）。"""
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/rules/definitions")
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()["data"]
    assert data["execution_version"] == _config().execution_version == "1.0.0"
