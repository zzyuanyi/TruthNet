"""风险评分服务 — Phase C 后端任务 6/11.

统一风险评分：
  - 输入：finance / equity / events 模块结果 + 评级拐点 + 行业基准 + 交叉验证
  - 输出：RiskOutput（综合分/分项/权重/贡献/覆盖/置信度/模式匹配/证据）
  - 权重与阈值集中管理（本模块唯一来源）
  - 缺失模块不得按 0 风险计算：移除缺失维度权重并按剩余权重归一化，
    同时明确记录 mitigating_factor 与 coverage
  - 不得因 events/benchmarks 缺失而自动绿色
  - 数据覆盖 < MIN_COVERAGE_FOR_GREEN 时 risk_level 返回 unknown（不输出绿色）
  - 股权结果由调用方注入（Full Profile 走 Neo4j），本服务不实例化任何图实现
  - pattern 匹配唯一来源 fraud_patterns.yaml（match_patterns）
  - 无 except: pass
"""

from __future__ import annotations

from app.domain.risk.fraud_patterns import match_patterns
from app.domain.risk.models import (
    RiskDataCoverage,
    RiskEvidence,
    RiskOutput,
    RiskPatternMatch,
    RiskSubScore,
)

# ── 权重配置（唯一来源）────────────────────────────────────
DEFAULT_WEIGHTS: dict[str, float] = {
    "finance": 0.40,
    "equity": 0.30,
    "events": 0.20,
    "benchmarks": 0.10,
}

STRATEGY_VERSION = "1.0.0"

# 等级阈值
_LEVEL_RED = 0.60
_LEVEL_ORANGE = 0.35
_LEVEL_YELLOW = 0.15

# 数据覆盖阈值：低于该值时不得输出绿色/黄色（数据不足）
MIN_COVERAGE_FOR_LEVEL = 0.50

# 股权分阈值
_EQUITY_CHAIN_RED = 2
_EQUITY_CHAIN_YELLOW = 0

# 基准分（公司分位）阈值
_BM_PCT_ORANGE = 90.0
_BM_PCT_YELLOW = 75.0


async def assemble_and_score(
    code: str,
    as_of: str,
    *,
    rule_set_version: str = "",
    dataset_version: str = "",
) -> RiskOutput:
    """收集模块数据并计算风险（Router 调用的顶层入口）。

    - 公司解析走 CompanyResolver（MySQL）
    - 股权按 GRAPH_BACKEND 分支：full → Neo4j，lite → NetworkX；
      Neo4j 不可用 → partial 空图（不降级 NetworkX 冒充）
    - 财务走真实规则引擎；事件走真实公告
    - 行业基准走 metric_registry（与 Finance/Benchmarks 同口径）
    """
    from app.agents.state import EquityResult, EventsResult, FinanceResult
    from app.application.services.company_resolver import resolve_company
    from app.core.config import settings
    from app.domain.finance.rule_engine import evaluate_all_rules

    rec = await resolve_company(code)
    if rec is None:
        # 与 V12 错误码契约一致（COMPANY_NOT_FOUND 已更名为 COMPANY_NOT_COVERED）
        raise ValueError(f"COMPANY_NOT_COVERED: {code}")
    wind_code = rec.wind_code
    sec_name = rec.sec_name
    industry_l1 = rec.industry_l1 or ""
    as_of_str = as_of or settings.DEFAULT_AS_OF or "20260331"

    # ── 1. 财务 ──
    finance_result: FinanceResult | None = None
    try:
        results = evaluate_all_rules(wind_code, as_of_str)
        rules = list(results.values())
        finance_result = FinanceResult(
            rule_statuses={r.rule_id: r.status for r in rules},
            rules=rules,
            warnings=[],
            evidence=[],
        )
    except Exception:  # noqa: BLE001 — 财务失败 → 模块缺失（不按 0 风险）
        finance_result = None

    # ── 2. 股权（profile 感知，Router 不 new NetworkX）──
    equity_result: EquityResult | None = None
    try:
        use_neo4j = settings.GRAPH_BACKEND == "neo4j"
        if use_neo4j:
            from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

            adapter = Neo4jEquityGraph()
            if await adapter.check_connection():
                graph = await adapter.get_graph(wind_code, depth=5)
                equity_result = EquityResult(
                    graph=graph.model_dump() if hasattr(graph, "model_dump") else {},
                    chains=getattr(graph, "control_chains", []) or [],
                    evidence=[],
                )
            else:
                # Neo4j 不可用 → 空图（不冒充 NetworkX）
                equity_result = EquityResult(graph={}, chains=[], evidence=[])
        else:
            from app.infrastructure.graph.networkx.equity_graph import (
                NetworkXEquityGraph,
            )

            adapter = NetworkXEquityGraph()
            graph = await adapter.get_graph(wind_code.split(".")[0], depth=5)
            equity_result = EquityResult(
                graph=graph.model_dump() if hasattr(graph, "model_dump") else {},
                chains=getattr(graph, "control_chains", []) or [],
                evidence=[],
            )
    except Exception:  # noqa: BLE001
        equity_result = None

    # ── 3. 事件（真实公告）──
    events_result: EventsResult | None = None
    try:
        from app.domain.finance._fetch import _get_engine
        from app.domain.events.fcode_taxonomy import classify_sentiment
        from sqlalchemy import text

        engine = _get_engine()
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT ann_dt, n_info_title, n_info_fcode, sentiment "
                        "FROM announcements WHERE wind_code = :c AND is_latest = 1 "
                        "ORDER BY ann_dt ASC"
                    ),
                    {"c": wind_code},
                )
                .mappings()
                .fetchall()
            )
        timeline = []
        for r in rows:
            raw_fcode = str(r["n_info_fcode"] or "")
            sentiment, _method, _conf = classify_sentiment(raw_fcode)
            stored = str(r["sentiment"] or "")
            if stored in ("positive", "negative", "neutral"):
                sentiment = stored
            timeline.append(
                {
                    "date": str(r["ann_dt"] or ""),
                    "title": str(r["n_info_title"] or ""),
                    "sentiment": sentiment,
                }
            )
        events_result = EventsResult(timeline=timeline, clusters=[], evidence=[])
    except Exception:  # noqa: BLE001
        events_result = None

    # ── 4. 行业基准（公司分位）──
    benchmarks: dict[str, dict] = {}
    if industry_l1:
        try:
            from app.domain.benchmarks.calculator import (
                MIN_PEER_SAMPLE,
                compute_metric_values,
                percentile_rank,
            )
            from app.domain.benchmarks.metric_registry import all_metrics
            from app.domain.finance._fetch import _get_engine

            engine = _get_engine()
            for metric in all_metrics():
                try:
                    pairs = compute_metric_values(
                        engine, metric, industry_l1, as_of_str
                    )
                    values = [v for _, v in pairs]
                    company_value = next((v for c, v in pairs if c == wind_code), None)
                    if len(values) >= MIN_PEER_SAMPLE and company_value is not None:
                        benchmarks[metric.metric_id] = {
                            "company_percentile": percentile_rank(
                                company_value, values
                            ),
                            "sample_count": len(values),
                        }
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            benchmarks = {}

    svc = RiskScoringService()
    return svc.score(
        wind_code=wind_code,
        as_of=as_of_str,
        sec_name=sec_name,
        finance_result=finance_result,
        equity_result=equity_result,
        events_result=events_result,
        benchmarks=benchmarks,
        rule_set_version=rule_set_version or settings.RULE_SET_VERSION,
        dataset_version=dataset_version or settings.DATASET_VERSION,
    )


class RiskScoringService:
    """风险评分服务（无状态，同步）。"""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = dict(weights or DEFAULT_WEIGHTS)

    # ── 分项计算（复用模块结果，不重复计算规则）─────────────

    def _finance_score(self, finance_result) -> tuple[float, str, str]:
        if finance_result is None:
            return 0.0, "skipped", "财务模块未执行"
        statuses = getattr(finance_result, "rule_statuses", {}) or {}
        triggered = [rid for rid, s in statuses.items() if s == "triggered"]
        if not triggered:
            return 0.0, "success", "无触发规则"
        red = sum(
            1
            for r in getattr(finance_result, "rules", []) or []
            if getattr(r, "severity", None) == "red"
        )
        orange = sum(
            1
            for r in getattr(finance_result, "rules", []) or []
            if getattr(r, "severity", None) == "orange"
        )
        if red == 0 and orange == 0:
            # rule_statuses 只有状态无 severity 时，按触发数保守给分
            return min(1.0, 0.15 + len(triggered) * 0.05), "success", None
        score = min(1.0, red * 0.25 + orange * 0.15 + len(triggered) * 0.05)
        return score, "success", None

    def _equity_score(self, equity_result) -> tuple[float, str, str]:
        if equity_result is None:
            return 0.0, "skipped", "股权模块未执行"
        chains = getattr(equity_result, "chains", []) or []
        graph = getattr(equity_result, "graph", {}) or {}
        n_chains = len(chains)
        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        if not nodes and n_chains == 0:
            return 0.0, "skipped", "股权图无数据"
        if n_chains > _EQUITY_CHAIN_RED:
            return 0.3, "success", None
        if n_chains > _EQUITY_CHAIN_YELLOW:
            return 0.1, "success", None
        return 0.0, "success", None

    def _events_score(self, events_result) -> tuple[float, str, str]:
        if events_result is None:
            return 0.0, "skipped", "事件模块未执行"
        timeline = getattr(events_result, "timeline", []) or []
        if not timeline:
            return 0.0, "skipped", "无公告数据"
        negative = sum(1 for t in timeline if t.get("sentiment") == "negative")
        ratio = negative / len(timeline)
        return min(1.0, ratio * 3), "success", None

    def _benchmark_score(self, benchmarks) -> tuple[float, str, str]:
        """行业基准分：基于公司分位（percentile）。"""
        if not benchmarks:
            return 0.0, "skipped", "行业基准数据未就绪"
        # benchmarks: {metric_id: {"company_percentile": .., "sample_count": ..}}
        percentiles = [
            v.get("company_percentile")
            for v in benchmarks.values()
            if v.get("company_percentile") is not None
        ]
        if not percentiles:
            return 0.0, "skipped", "无有效公司分位"
        pct = max(percentiles)
        if pct >= _BM_PCT_ORANGE:
            return 0.4, "success", None
        if pct >= _BM_PCT_YELLOW:
            return 0.2, "success", None
        return 0.0, "success", None

    # ── 综合 ──────────────────────────────────────────────

    def score(
        self,
        *,
        wind_code: str,
        as_of: str,
        sec_name: str = "",
        finance_result=None,
        equity_result=None,
        events_result=None,
        benchmarks: dict | None = None,
        rating_inflections: list | None = None,
        cross_validation=None,
        has_related_party: bool = False,
        rule_set_version: str = "",
        dataset_version: str = "",
    ) -> RiskOutput:
        """计算综合风险评分。"""
        sub_scores: list[RiskSubScore] = []
        coverage = RiskDataCoverage()
        all_evidence: list[RiskEvidence] = []
        claim_ids: list[str] = []
        warnings: list[str] = []

        # ── 分项计算 ──
        fin_score, fin_status, fin_warn = self._finance_score(finance_result)
        eq_score, eq_status, eq_warn = self._equity_score(equity_result)
        ev_score, ev_status, ev_warn = self._events_score(events_result)
        bm_score, bm_status, bm_warn = self._benchmark_score(benchmarks)

        coverage.finance = finance_result is not None
        coverage.equity = equity_result is not None
        coverage.events = events_result is not None and bool(
            getattr(events_result, "timeline", [])
        )
        coverage.benchmarks = bool(benchmarks)

        # ── 证据与 Claim 收集 ──
        for label, mod_result, mod_name in [
            ("finance", finance_result, "finance"),
            ("equity", equity_result, "equity"),
            ("events", events_result, "events"),
        ]:
            if mod_result is None:
                continue
            for ev in getattr(mod_result, "evidence", []):
                all_evidence.append(
                    RiskEvidence(
                        evidence_id=ev.evidence_id,
                        source_type=getattr(ev, "source_type", "") or mod_name,
                        summary=f"{label} 模块证据",
                        claim_ids=getattr(ev, "claim_ids", []) or [],
                    )
                )
            # 模块级 claim_ids
            for cid in getattr(mod_result, "claim_ids", []) or []:
                if cid not in claim_ids:
                    claim_ids.append(cid)

        # ── 权重归一化（缺失模块移除 + 归一化）──
        used_weights: dict[str, float] = {}
        for dim in ("finance", "equity", "events", "benchmarks"):
            status = {
                "finance": fin_status,
                "equity": eq_status,
                "events": ev_status,
                "benchmarks": bm_status,
            }[dim]
            if status in ("skipped", "failed"):
                continue
            used_weights[dim] = self._weights[dim]
        total_weight = sum(used_weights.values()) or 0.0
        if total_weight <= 0:
            return RiskOutput(
                wind_code=wind_code,
                sec_name=sec_name,
                as_of=as_of,
                overall_score=0.0,
                risk_level="unknown",
                data_coverage=coverage,
                confidence=0.0,
                warnings=["无任何可用模块数据，无法评分"],
            )

        # ── 分项入表 ──
        labels = {
            "finance": "财务勾稽",
            "equity": "股权穿透",
            "events": "舆情事件",
            "benchmarks": "行业基准",
        }
        scores = {
            "finance": fin_score,
            "equity": eq_score,
            "events": ev_score,
            "benchmarks": bm_score,
        }
        statuses = {
            "finance": fin_status,
            "equity": eq_status,
            "events": ev_status,
            "benchmarks": bm_status,
        }
        for dim, weight in used_weights.items():
            normalized_weight = weight / total_weight
            contribution = scores[dim] * normalized_weight
            sub_scores.append(
                RiskSubScore(
                    dimension=dim,
                    label=labels[dim],
                    score=round(scores[dim], 3),
                    weight=round(normalized_weight, 4),
                    contribution=round(contribution, 3),
                    status=statuses[dim],
                )
            )

        overall_score = round(sum(s.contribution for s in sub_scores), 3)
        total_possible_weight = sum(DEFAULT_WEIGHTS.values()) or 1.0
        coverage.coverage_ratio = round(
            sum(used_weights.values()) / total_possible_weight, 3
        )
        coverage.missing_modules = [
            d
            for d in ("finance", "equity", "events", "benchmarks")
            if d not in used_weights
        ]

        # ── 等级（无数据不绿色）──
        if coverage.coverage_ratio < MIN_COVERAGE_FOR_LEVEL:
            risk_level = "unknown"
            warnings.append(
                f"数据覆盖不足（{coverage.coverage_ratio:.0%}），风险等级标记 unknown"
            )
        elif overall_score >= _LEVEL_RED:
            risk_level = "red"
        elif overall_score >= _LEVEL_ORANGE:
            risk_level = "orange"
        elif overall_score >= _LEVEL_YELLOW:
            risk_level = "yellow"
        else:
            risk_level = "green"

        # ── 置信度 ──
        success_count = sum(1 for s in sub_scores if s.status == "success")
        confidence = min(0.95, 0.3 + success_count * 0.2)

        # ── 关键贡献因素 ──
        key_contributors = [
            f"{s.label}({s.score:.2f})" for s in sub_scores if s.contribution >= 0.05
        ]

        # ── 缓解因素（缺失模块说明）──
        mitigating_factors: list[str] = []
        if "events" not in used_weights:
            mitigating_factors.append(
                "无公告数据 → 舆情维度不参与综合分（不按 0 风险）"
            )
        if "benchmarks" not in used_weights:
            mitigating_factors.append(
                "行业分位未就绪 → 基准维度不参与综合分（不按 0 风险）"
            )
        if "equity" not in used_weights:
            mitigating_factors.append("股权模块缺失 → 股权维度不参与综合分")

        # ── 模式匹配（唯一来源 fraud_patterns.yaml）──
        rule_dict: dict[str, dict] = {}
        if finance_result is not None:
            statuses_map = getattr(finance_result, "rule_statuses", {}) or {}
            rules = getattr(finance_result, "rules", None) or []
            for rid, st in statuses_map.items():
                sev = "green"
                for r in rules:
                    if getattr(r, "rule_id", None) == rid:
                        sev = getattr(r, "severity", "green")
                        break
                rule_dict[rid] = {"status": st, "severity": sev}
        pattern_matches: list[RiskPatternMatch] = []
        if rule_dict:
            for m in match_patterns(rule_dict, has_related_party=has_related_party):
                pattern_matches.append(
                    RiskPatternMatch(
                        pattern_id=m.pattern_id,
                        pattern_name=m.pattern_name,
                        triggered_rules=m.triggered_rules,
                        confidence=m.confidence,
                        reasoning=m.reasoning,
                        partial_coverage=m.partial_coverage,
                    )
                )

        # ── 评级拐点补充 warning ──
        if rating_inflections:
            orange_inf = [i for i in rating_inflections if i.severity == "orange"]
            if orange_inf:
                warnings.append(
                    f"评级拐点: {len(orange_inf)} 家公司季度出现多家机构下调"
                )

        # ── 交叉验证汇总 ──
        if cross_validation is not None:
            checks = getattr(cross_validation, "checks", []) or []
            failed = [c.check_type for c in checks if c.status == "fail"]
            if failed:
                warnings.append(f"交叉验证发现不一致: {failed}")

        evidence_ids = [e.evidence_id for e in all_evidence]
        return RiskOutput(
            wind_code=wind_code,
            sec_name=sec_name,
            as_of=as_of,
            overall_score=overall_score,
            risk_level=risk_level,
            sub_scores=sub_scores,
            weights={k: round(v / total_weight, 4) for k, v in used_weights.items()},
            contributions={s.dimension: round(s.contribution, 3) for s in sub_scores},
            strategy_version=STRATEGY_VERSION,
            rule_set_version=rule_set_version,
            data_coverage=coverage,
            confidence=round(confidence, 3),
            key_contributors=key_contributors,
            mitigating_factors=mitigating_factors,
            pattern_matches=pattern_matches,
            claim_ids=claim_ids,
            evidence_ids=evidence_ids,
            warnings=warnings,
        )
