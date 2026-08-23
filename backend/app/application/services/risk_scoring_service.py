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

import asyncio

from app.domain.risk.fraud_patterns import match_patterns
from app.domain.risk.models import (
    RiskDataCoverage,
    RiskEvidence,
    RiskOutput,
    RiskPatternMatch,
    RiskSubScore,
)
from app.domain.risk.severity import (
    RISK_LEVEL_RANK,
    event_signal_severity,
    highest_risk_level,
    normalize_risk_level,
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


_TABLE_LABELS: dict[str, str] = {
    "income_statement": "利润表",
    "balance_sheet": "资产负债表",
    "cash_flow": "现金流量表",
    "financial_statement": "财务报表",
}

_FIELD_LABELS: dict[str, str] = {
    "acct_rcv": "应收账款",
    "oper_rev": "营业收入",
    "inventories": "存货",
    "monetary_cap": "货币资金",
    "st_borrow": "短期借款",
    "lt_borrow": "长期借款",
    "tot_assets": "总资产",
    "oth_rcv": "其他应收款",
    "net_profit": "净利润",
    "oper": "经营活动现金流",
    "net_cash_flows_oper_act": "经营活动现金流",
    "net_profit_excl_min_int_inc": "净利润",
    "net_profit_after_ded_nr_lp": "扣非净利润",
    "less_oper_cost": "营业成本",
    "oper_profit": "营业利润",
    "tot_profit": "利润总额",
    "core_profit": "核心利润",
}


def _evidence_context(ev, label: str) -> str:
    """从 EvidenceRef 构造“指标 / 报表 / 期次 / 值”的可读上下文。"""
    parts: list[str] = []
    field = str(getattr(ev, "field_path", "") or "").strip()
    if field:
        parts.append(_FIELD_LABELS.get(field, field))
    table = str(getattr(ev, "source_table", "") or "").strip()
    if table:
        parts.append(_TABLE_LABELS.get(table, table))
    period = str(getattr(ev, "period", "") or "").strip()
    if period:
        parts.append(period)
    value = getattr(ev, "value", None)
    if value is not None and str(value).strip() != "":
        unit = str(getattr(ev, "unit", "") or "").strip()
        parts.append(f"{value}{unit}")
    if parts:
        return " · ".join(parts)
    return f"{label} 模块证据"


def _evidence_summary(ev, label: str) -> str:
    """真实摘要：source_title → source_excerpt → "字段 期次: 值" → 模块兜底。

    8/23：web_search 线索只显示标题（field_path 为内部键如 news_0，
    对用户无意义，不拼上下文）。
    """
    title = str(getattr(ev, "source_title", "") or "").strip()
    if title:
        if (getattr(ev, "source_type", "") or "") == "web_search":
            return title
        context = _evidence_context(ev, label)
        if context and context != f"{label} 模块证据":
            return f"{title}｜{context}"
        return title
    excerpt = str(getattr(ev, "source_excerpt", "") or "").strip()
    if excerpt:
        return excerpt
    field_path = str(getattr(ev, "field_path", "") or "").strip()
    period = str(getattr(ev, "period", "") or "").strip()
    value = getattr(ev, "value", None)
    value_str = "" if value is None else str(value).strip()
    if field_path or period or value_str:
        return f"{field_path} {period}: {value_str}".strip(" :")
    return f"{label} 模块证据"


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
    from datetime import datetime

    from app.agents.nodes.cross_validate import cross_validate_node
    from app.agents.nodes.equity import equity_node
    from app.agents.nodes.events import events_node
    from app.agents.nodes.finance import finance_node
    from app.agents.nodes.risk import risk_node
    from app.agents.state import (
        CompanyRef,
        ExecutionPlan,
        ModuleResults,
        RuntimeState,
    )
    from app.application.services.company_resolver import resolve_company
    from app.core.config import settings

    rec = await resolve_company(code)
    if rec is None:
        # 与 V12 错误码契约一致（COMPANY_NOT_FOUND 已更名为 COMPANY_NOT_COVERED）
        raise ValueError(f"COMPANY_NOT_COVERED: {code}")
    wind_code = rec.wind_code
    # 2026-08-16 口径整改：未传 as_of 时从库内真实期次推导，禁止硬编码默认期
    if not as_of:
        from app.domain.finance.data_as_of import resolve_company_data_as_of

        as_of_str = resolve_company_data_as_of(wind_code) or ""
    else:
        as_of_str = as_of
    company = CompanyRef(
        entity_id=rec.entity_id,
        wind_code=wind_code,
        sec_name=rec.sec_name,
        exchange=rec.exchange_code or "",
        industry_l1=rec.industry_l1,
    )
    state = {
        "user_query": f"分析{rec.sec_name}综合风险",
        "company": company,
        "plan": ExecutionPlan(
            intent="diagnose",
            requested_modules=["finance", "equity", "events"],
            cross_checks=["equity_vs_events", "financial_vs_cashflow"],
            as_of=datetime.strptime(as_of_str, "%Y%m%d").date(),
        ),
        "module_status": {},
        "results": ModuleResults(),
        "evidence": [],
        "claims": [],
        "runtime": RuntimeState(),
    }

    def apply_node_output(output: dict) -> None:
        state["module_status"].update(output.get("module_status") or {})
        node_results = output.get("results")
        if node_results is not None:
            current = state["results"]
            state["results"] = ModuleResults(
                finance=node_results.finance or current.finance,
                equity=node_results.equity or current.equity,
                events=node_results.events or current.events,
            )
        for key in ("cross_validation", "risk_output"):
            if key in output:
                state[key] = output[key]

    def run_nodes() -> None:
        for node in (finance_node, equity_node, events_node, cross_validate_node):
            apply_node_output(node(state))
        apply_node_output(risk_node(state))

    await asyncio.to_thread(run_nodes)
    out = state.get("risk_output")
    if out is None:
        raise RuntimeError("RISK_SCORING_ERROR")
    out.rule_set_version = rule_set_version or settings.RULE_SET_VERSION
    from app.application.services.risk_derivation_service import (
        build_risk_derivation_chains,
    )

    out.derivation_chains = build_risk_derivation_chains(out, state["results"].finance)
    return out


class RiskScoringService:
    """风险评分服务（无状态，同步）。"""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = dict(weights or DEFAULT_WEIGHTS)

    # ── 分项计算（复用模块结果，不重复计算规则）─────────────

    def _finance_score(self, finance_result) -> tuple[float, str, str]:
        if finance_result is None:
            return 0.0, "skipped", "财务模块未执行"
        statuses = getattr(finance_result, "rule_statuses", {}) or {}
        if not statuses:
            return 0.0, "skipped", "财务模块未返回任何规则状态"
        triggered = [rid for rid, s in statuses.items() if s == "triggered"]
        # WARN-1-1（核验修订）：至少存在一条可判定状态（triggered/not_triggered）
        # 才视为有效财务维度；全部 insufficient_data/not_applicable 时财务是
        # "无法判断"而非"无风险"，返回 partial 由聚合层降级（不按 0 风险）。
        # 混合场景（部分可判定 + 部分数据不足）继续视为有效，不丢弃整个维度。
        decidable = [
            rid for rid, s in statuses.items() if s in ("triggered", "not_triggered")
        ]
        if not decidable:
            return 0.0, "partial", "财务规则全部因数据不足/不适用无法判断"
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
        chain_details = getattr(equity_result, "chain_details", []) or []
        graph = getattr(equity_result, "graph", {}) or {}
        n_chains = len(chain_details or chains)
        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        if not nodes and n_chains == 0:
            return 0.0, "skipped", "股权图无数据"
        highest = highest_risk_level(
            [d.get("risk_level") for d in chain_details], default="green"
        )
        if highest == "red":
            return 0.8, "success", None
        if highest == "orange":
            return 0.5, "success", None
        if highest in ("yellow", "blue"):
            return 0.25, "success", None
        if n_chains > _EQUITY_CHAIN_RED:
            return 0.3, "success", None
        if n_chains > _EQUITY_CHAIN_YELLOW:
            return 0.1, "success", None
        return 0.0, "success", None

    def _events_score(self, events_result) -> tuple[float, str, str]:
        if events_result is None:
            return 0.0, "skipped", "事件模块未执行"
        timeline = getattr(events_result, "timeline", []) or []
        ratings = getattr(events_result, "rating_changes", []) or []
        clusters = getattr(events_result, "clusters", []) or []
        if not timeline and not ratings and not clusters:
            return 0.0, "skipped", "无公告、评级或事件簇数据"
        timeline_score = 0.0
        if timeline:
            # 8/23 评分校准：timeline 按负面事件最高严重度分级（与事件簇
            # 同口径：red 0.8/orange 0.5/yellow 0.25）——原「负面占比×3 封顶
            # 1.0」导致单条负面事件即满分（如隆基 1 条 2023 立案事件 → 舆情
            # 维度 1.0 → 综合 0.41 高危，明显失真）
            levels = [event_signal_severity(t) for t in timeline]
            timeline_score = {
                "red": 0.8,
                "orange": 0.5,
                "yellow": 0.25,
            }.get(highest_risk_level(levels, default="green"), 0.0)
        down_count = sum(1 for item in ratings if item.get("direction") == "down")
        rating_score = min(0.6, down_count * 0.15)
        cluster_levels = [event_signal_severity(item) for item in clusters]
        cluster_score = {
            "red": 0.8,
            "orange": 0.5,
            "yellow": 0.25,
        }.get(highest_risk_level(cluster_levels, default="green"), 0.0)
        return max(timeline_score, rating_score, cluster_score), "success", None

    def _signal_floor(
        self, finance_result, equity_result, events_result, cross_validation
    ) -> str:
        """Highest evidence-backed module signal used as a level floor."""
        levels: list[str] = []
        if finance_result is not None:
            statuses = getattr(finance_result, "rule_statuses", {}) or {}
            details = getattr(finance_result, "rule_details", {}) or {}
            rules = getattr(finance_result, "rules", []) or []
            by_rule = {
                getattr(rule, "rule_id", ""): getattr(rule, "severity", "unknown")
                for rule in rules
            }
            for rule_id, status in statuses.items():
                if status == "triggered":
                    levels.append(
                        (details.get(rule_id) or {}).get("severity")
                        or by_rule.get(rule_id)
                        or "unknown"
                    )
        if equity_result is not None:
            levels.extend(
                item.get("risk_level")
                for item in (getattr(equity_result, "chain_details", []) or [])
            )
        if events_result is not None:
            levels.extend(
                event_signal_severity(item)
                for item in (getattr(events_result, "timeline", []) or [])
            )
            levels.extend(
                event_signal_severity(item)
                for item in (getattr(events_result, "clusters", []) or [])
            )
            down_count = sum(
                1
                for item in (getattr(events_result, "rating_changes", []) or [])
                if item.get("direction") == "down"
            )
            if down_count:
                levels.append("orange" if down_count >= 3 else "yellow")
        if cross_validation is not None and any(
            getattr(check, "status", "") == "fail"
            for check in (getattr(cross_validation, "checks", []) or [])
        ):
            levels.append("orange")
        return highest_risk_level(levels)

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

        # 8.09 二轮审查：覆盖布尔全部统一为 status == "success"（与
        # missing_modules/used_weights 同源，杜绝互相矛盾——对象存在但
        # 状态 skipped/failed/partial 时不得宣称该维度"有数据"）。
        coverage.finance = fin_status == "success"
        coverage.equity = eq_status == "success"
        coverage.events = ev_status == "success"
        coverage.benchmarks = bm_status == "success"

        # ── 证据与 Claim 收集（8.11：真实类型 + 真实摘要，按 evidence_id 去重）──
        for label, mod_result, mod_name in [
            ("finance", finance_result, "finance"),
            ("equity", equity_result, "equity"),
            ("events", events_result, "events"),
        ]:
            if mod_result is None:
                continue
            for ev in getattr(mod_result, "evidence", []):
                eid = getattr(ev, "evidence_id", "") or ""
                if not eid or any(e.evidence_id == eid for e in all_evidence):
                    continue
                all_evidence.append(
                    RiskEvidence(
                        evidence_id=eid,
                        source_type=getattr(ev, "source_type", "") or "",
                        summary=_evidence_summary(ev, label),
                        claim_ids=getattr(ev, "claim_ids", []) or [],
                        # 8/23 联网线索标注：web 证据带 URL + is_web 标记
                        source_uri=getattr(ev, "source_uri", None) or None,
                        is_web=(getattr(ev, "source_type", "") or "") == "web_search",
                    )
                )
            # 模块级 claim_ids
            for cid in getattr(mod_result, "claim_ids", []) or []:
                if cid not in claim_ids:
                    claim_ids.append(cid)

        # ── 权重归一化（不可判定/缺失模块移除 + 归一化）──
        # WARN-1-1（核验修订）：只有 status=="success" 的维度参与综合分——
        # partial（执行了但数据不足无法判断）与 skipped/failed 同样剔除，
        # 不允许"无法判断"被当作"有数据、无风险"计入覆盖。
        used_weights: dict[str, float] = {}
        for dim in ("finance", "equity", "events", "benchmarks"):
            status = {
                "finance": fin_status,
                "equity": eq_status,
                "events": ev_status,
                "benchmarks": bm_status,
            }[dim]
            if status != "success":
                continue
            used_weights[dim] = self._weights[dim]
        # 8.09 二轮审查：coverage_ratio/missing_modules 在零权重提前返回
        # 之前统一计算——全维度不可用时覆盖信息不得丢失
        # （曾实测 risk_level=unknown / coverage_ratio=0 / missing_modules=[]）。
        total_possible_weight = sum(DEFAULT_WEIGHTS.values()) or 1.0
        coverage.coverage_ratio = round(
            sum(used_weights.values()) / total_possible_weight, 3
        )
        coverage.missing_modules = [
            d
            for d in ("finance", "equity", "events", "benchmarks")
            if d not in used_weights
        ]
        total_weight = sum(used_weights.values()) or 0.0
        if total_weight <= 0:
            dim_status = {
                "finance": fin_status,
                "equity": eq_status,
                "events": ev_status,
                "benchmarks": bm_status,
            }
            unavailable = "、".join(
                f"{d}={s}" for d, s in dim_status.items() if s != "success"
            )
            return RiskOutput(
                wind_code=wind_code,
                sec_name=sec_name,
                as_of=as_of,
                overall_score=0.0,
                risk_level="unknown",
                data_coverage=coverage,
                confidence=0.0,
                evidence=all_evidence,
                mitigating_factors=[
                    f"全部维度均不可用（{unavailable}），无法评分，不按 0 风险处理"
                ],
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
        # coverage_ratio/missing_modules 已在权重归一化后统一计算
        # （零权重提前返回前），此处不再重复。

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

        signal_floor = self._signal_floor(
            finance_result, equity_result, events_result, cross_validation
        )
        if (
            RISK_LEVEL_RANK[signal_floor]
            > RISK_LEVEL_RANK[normalize_risk_level(risk_level)]
        ):
            risk_level = signal_floor
            warnings.append(f"综合等级按最高有效叶子信号校准为 {risk_level}")

        # WARN-1-1（核验修订 + 8.09 二轮审查）：关键维度保护——财务不可判定
        # （status != "success"，含 partial/skipped/未返回任何规则状态）时
        # 不得输出 green"正常"：若股权/舆情已有明确黄色以上叶子信号则保留该
        # 等级（仅提示财务覆盖不足），否则综合等级必须标记 unknown。
        if fin_status != "success":
            if RISK_LEVEL_RANK[signal_floor] >= RISK_LEVEL_RANK["yellow"]:
                warnings.append(
                    "财务规则未参与评分（数据不足/未执行），综合等级按股权/舆情"
                    "明确信号保留"
                )
            else:
                risk_level = "unknown"
                warnings.append(
                    "财务规则无法判断（数据不足/未执行）且无其他明确风险信号，"
                    "综合等级标记 unknown（不输出正常）"
                )

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
        if fin_status != "success":
            # 8.09 三轮审查：skipped/partial 统一生成财务缺失说明——
            # 曾只有 partial 分支，skipped（未返回任何规则状态）时
            # mitigating_factors 为空
            mitigating_factors.append(
                "财务规则未参与评分（数据不足/未执行）→ 财务维度不参与综合分"
                "（不按 0 风险）"
            )

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
                        # Phase D #16 三要素
                        phase=m.phase,
                        alternative_explanation=m.alternative_explanation,
                        regulatory_hint=m.regulatory_hint,
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
            evidence=all_evidence,
            warnings=warnings,
        )
