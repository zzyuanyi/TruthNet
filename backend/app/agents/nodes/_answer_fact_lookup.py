"""_answer_fact_lookup — generate_answer 拆分模块（重构生成，函数体与原文件逐字节一致）。"""

from __future__ import annotations

import logging
from ._answer_common import (
    _EXCHANGE_LABELS,
    _FACT_KEYS,
    _WEB_SEARCHABLE_FACTS,
    _clip_evidence_value,
    _emit_segment,
    _format_growth,
    _format_indicator_value,
    _merge_unique,
)
from app.agents.state import AgentState, Claim, EvidenceRef, FinalResponse
from app.core.config import settings
from app.domain.finance.statement_type import PARENT_STATEMENT_TYPE
from app.domain.provenance.id_factory import (
    NS_COMPANY_REGISTRY,
    NS_FINANCE,
    NS_WEB_SEARCH,
    make_claim_id,
    make_evidence_id,
)
from datetime import datetime, timezone
import re

logger = logging.getLogger(__name__)


def _web_search_fill_company_fact(
    *,
    sec_name: str,
    wind_code: str,
    fact_key: str,
    label: str,
    turn_id: str,
    trace_id: str,
) -> tuple[str | None, EvidenceRef | None]:
    """会5：公司事实库内无值 → 联网检索 → 解析 → 构建来源标注证据.

    Returns:
        (value, evidence)：value 为解析出的值（无命中/解析失败 → None）；
        evidence 为 source_type="web_search" 的 EvidenceRef（同上 → None）。
        默认 off 时 web_search 返回 []，本函数返回 (None, None)——
        调用方走原「未覆盖」分支，行为与现状完全一致。
    """
    from app.application.services.web_search_fact_fill import (
        extract_executive_compensation_excerpt,
        extract_ipo_price_from_hits,
        extract_listing_date_from_hits,
    )
    from app.application.services.web_search_service import web_search

    # 8/19 审查：所有候选 query 均保留 wind_code，避免同名公司串线；
    # 不把公司事实降级到质量不稳定的无代码通用检索。
    queries = _company_fact_search_queries(sec_name, wind_code, fact_key, label)
    hits = []
    value: str | None = None
    field = ""
    for query in queries:
        candidate_hits = web_search(query)
        if fact_key == "listing_date":
            candidate_value = extract_listing_date_from_hits(candidate_hits)
            field = "listing_date"
        elif fact_key == "ipo_price":
            candidate_value = extract_ipo_price_from_hits(candidate_hits)
            field = "ipo_price"
        elif fact_key == "executive_compensation":
            candidate_value = extract_executive_compensation_excerpt(candidate_hits)
            field = "executive_compensation"
        else:
            candidate_value = None
        if candidate_value:
            hits = candidate_hits
            value = candidate_value
            break
    if not value:
        return None, None

    hit = next((h for h in hits if (h.snippet or h.title)), None)
    evidence = EvidenceRef(
        evidence_id=make_evidence_id(
            source_namespace=NS_WEB_SEARCH,
            source_type="web_search",
            source_record_id=wind_code,
            field_path=field,
            company_code=wind_code,
        ),
        source_type="web_search",
        source_record_id=wind_code,
        field_path=field,
        value=_clip_evidence_value(value),
        source_title=(
            (hit.title or f"联网检索 · {label}") if hit else f"联网检索 · {label}"
        ),
        source_uri=hit.url if hit else None,
        source_excerpt=(hit.snippet or "") if hit else "",
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=wind_code,
        module="company_fact",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    return value, evidence


def _company_fact_search_queries(
    sec_name: str, wind_code: str, fact_key: str, label: str
) -> list[str]:
    """公司事实联网检索 query 列表。

    先走带代码的精确检索，再走仍带代码的补充检索。
    对于 IPO 价格/高管薪酬，第二条 query 显式补公告语义，避免只命中垂直
    行情/空结果。
    """
    base = f"{sec_name} {wind_code} {label} 交易所"
    if fact_key == "listing_date":
        return [
            base,
            f"{sec_name} {wind_code} 上市日期 上市公告书",
            f"{sec_name} {wind_code} 上市公告 上市日期",
        ]
    if fact_key == "ipo_price":
        return [
            f"{sec_name} {wind_code} 首发价格 发行价 公告",
            f"{sec_name} {wind_code} 首次公开发行 发行价格 上市公告",
        ]
    if fact_key == "executive_compensation":
        return [
            f"{sec_name} {wind_code} 高管薪酬 董监高薪酬 公告",
            f"{sec_name} {wind_code} 年报 高管薪酬 董监高报酬",
        ]
    return [base]


def _answer_company_fact(state: AgentState, fact_key: str) -> dict:
    """R9/R11：公司事实轻量回答（精确模板命中，不跑三大模块）。

    诚实边界：
      - 结构化已覆盖字段（行业/交易所/企业类型/上市日期）直接回答；
      - 未覆盖字段（主营业务/总股本无字段）明确回答"当前数据范围未覆盖"，
        不从股东持股等推算，**不生成虚假 Evidence**；
      - 有真实值 → company_fact Claim（verified）+ company_registry Evidence，
        顶层 claims/evidence 返回（persist_turn 只读顶层，P2-1）。
    """
    company = state.get("company")
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    wind_code = company.wind_code
    sec_name = company.sec_name

    if fact_key not in _FACT_KEYS:
        fact_key = "industry"  # 未知键兜底
    label, source_field, registry_field = _FACT_KEYS[fact_key]

    if source_field == "industry":
        value = (company.industry_l1 or "").strip() or None
    elif source_field == "exchange":
        value = _EXCHANGE_LABELS.get(company.exchange, company.exchange) or None
    elif source_field == "comp_type":
        from app.domain.company.models import company_type_label_from_code

        code_str = (company.comp_type_code or "").strip()
        code_int = int(code_str) if code_str.isdigit() else None
        value = company_type_label_from_code(code_int)
    elif source_field == "listing_date":
        # P2-1：直接消费 company.listing_date（resolve_entity 已一并填充）
        value = (company.listing_date or "").strip() or None
    else:  # business / total_shares：无结构化字段
        value = None

    # Phase E 会5：公司事实库内无值 → 触发联网检索（首个示范触发点：
    # 上市日期等公司事实；默认 off 时 web_search 返回 []，走原分支）
    web_evidence: EvidenceRef | None = None
    if not value and fact_key in _WEB_SEARCHABLE_FACTS:
        value, web_evidence = _web_search_fill_company_fact(
            sec_name=sec_name,
            wind_code=wind_code,
            fact_key=fact_key,
            label=label,
            turn_id=turn_id,
            trace_id=trace_id,
        )

    if value:
        if web_evidence is not None:
            if fact_key == "executive_compensation":
                answer = (
                    f"{sec_name}（{wind_code}）检索到高管薪酬相关公告摘要：{value}。"
                    "（来源链接见证据，具体人员和年度请以公告原文为准。）"
                )
            else:
                answer = (
                    f"{sec_name}（{wind_code}）的{label}为：{value}。"
                    "（该信息来自联网检索，来源链接见证据，建议以官方披露为准。）"
                )
        else:
            answer = f"{sec_name}（{wind_code}）的{label}为：{value}。"
    else:
        answer = (
            f"{sec_name}（{wind_code}）的{label}：当前结构化数据范围未覆盖。"
            "如需进一步核验，请前往企业画像页查看详情。"
        )

    _emit_segment(state, answer)

    # P2-1：无真实值 → 不生成虚假 Evidence/Claim（三者全空）
    if not value:
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=[],
                evidence=[],
            ),
        }

    if web_evidence is not None:
        source_evidence = web_evidence
        limitations = ["联网检索来源，建议以官方披露为准核验"]
    else:
        evidence_id = make_evidence_id(
            source_namespace=NS_COMPANY_REGISTRY,
            source_type="company_registry",
            source_record_id=wind_code,
            field_path=registry_field,
            company_code=wind_code,
        )
        source_evidence = EvidenceRef(
            evidence_id=evidence_id,
            source_type="company_registry",
            source_record_id=wind_code,
            field_path=registry_field,
            value=value,
            source_title=f"{sec_name} · 公司注册信息",
            turn_id=turn_id,
            trace_id=trace_id,
            company_code=wind_code,
            module="company_fact",
        )
        limitations = ["公司注册信息（证券主表）"]
    fact_claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=wind_code,
            claim_type="company_fact",
            claim_text=f"{label}：{value}",
            rule_version="",
        ),
        text=f"{label}为：{value}",
        claim_type="company_fact",
        severity="unknown",
        evidence_ids=[source_evidence.evidence_id],
        verification_status="verified",  # 真实值；来源类型见 source_type/limitations
        limitations=limitations,
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=wind_code,
        module="company_fact",
    )
    return {
        "claims": [fact_claim],
        "evidence": [source_evidence],
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[fact_claim],
            evidence=[source_evidence],
        ),
    }


def _answer_market_quote(state: AgentState, field: str) -> dict:
    """回答单个 AnySearch 行情字段，缺失时按字段诚实降级。"""
    from app.application.services.market_quote_service import (
        MARKET_FIELD_LABELS,
        format_market_value,
        query_market_quote,
    )

    company = state.get("company")
    label = MARKET_FIELD_LABELS.get(field, "行情字段")
    if company is None:
        answer = f"查询{label}需要先指定上市公司或股票代码。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    result = query_market_quote(
        sec_name=company.sec_name,
        wind_code=company.wind_code,
        field=field,
        user_query=state.get("user_query", ""),
    )
    name_code = f"{company.sec_name}（{company.wind_code}）"
    if result.status == "history_required":
        answer = (
            f"当前行情接口缺少回答{name_code}{label}所需的完整历史序列，"
            "无法用单日快照可靠替代。"
        )
    elif result.status == "field_missing":
        date_text = f" {result.trade_date}" if result.trade_date else ""
        answer = (
            f"已获取{name_code}{date_text}的行情快照，但数据源未返回{label}字段，"
            "无法可靠回答。"
        )
    elif result.status != "ok" or result.value is None:
        answer = f"当前未获取到{name_code}可回查的行情数据，无法可靠回答{label}。"
    else:
        rendered = format_market_value(field, result.value)
        date_text = result.trade_date
        if (
            any(word in state.get("user_query", "") for word in ("今天", "今日"))
            and not result.period_start
            and result.trade_date
        ):
            date_text = f"当前可获取的最近交易日为 {result.trade_date}"
        if result.period_start:
            date_text = f"{result.period_start}至{result.trade_date}"
        if field in ("amount", "volume"):
            answer = (
                f"{name_code} {date_text} 的{label}数据源原始值为{rendered}；"
                "接口规范未标明该字段单位。"
            )
        else:
            answer = f"{name_code} {date_text} 的{label}为{rendered}。"

    _emit_segment(state, answer)
    if result.status != "ok" or result.value is None or result.hit is None:
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    evidence_id = make_evidence_id(
        source_namespace=NS_WEB_SEARCH,
        source_type="web_search",
        source_record_id=f"{company.wind_code}:{result.trade_date}",
        field_path=f"market_quote.{field}",
        period=result.trade_date,
        company_code=company.wind_code,
    )
    quote_evidence = EvidenceRef(
        evidence_id=evidence_id,
        source_type="web_search",
        source_record_id=f"{company.wind_code}:{result.trade_date}",
        field_path=f"market_quote.{field}",
        period=result.trade_date,
        value=result.raw_value,
        source_title=result.hit.title or f"{company.sec_name} · AnySearch 行情",
        source_uri=result.hit.url or None,
        source_excerpt=result.hit.snippet or "",
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="market_quote",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    quote_claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="market_quote",
            claim_text=answer,
        ),
        text=answer,
        claim_type="market_quote",
        severity="unknown",
        evidence_ids=[evidence_id],
        verification_status="verified",
        limitations=["联网行情快照；交易日以数据源返回日期为准"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="market_quote",
    )
    return {
        "claims": [quote_claim],
        "evidence": [quote_evidence],
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[quote_claim],
            evidence=[quote_evidence],
        ),
    }


def _answer_multi_metric(state: AgentState) -> dict:
    """一次返回并列指标，缺失字段逐项说明，不把问题强制拆开。"""
    company = state.get("company")
    plan = state.get("plan")
    if company is None:
        return {}
    query = state.get("user_query", "")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    require_exact = bool(plan and plan.as_of_kind == "report_period")
    requested: list[tuple[str, str]] = []
    if "总股本" in query:
        requested.append(("总股本", "unsupported"))
    if "营业收入" in query or "营收" in query:
        requested.append(("营业收入", "operating_revenue"))
    if "净资产" in query:
        requested.append(("净资产", "net_assets"))
    if "收盘价" in query or "收盘" in query:
        requested.append(("收盘价", "unsupported"))
    if "eps" in query.lower() or "每股收益" in query:
        requested.append(("EPS", "unsupported"))
    if not requested:
        answer = "未能识别并列指标，请补充具体财务指标名称。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    from app.application.services.indicator_query_service import query_metric

    lines = [
        f"{company.sec_name}（{company.wind_code}）并列指标结果：",
        "",
        "| 指标 | 数值 | 数据期与口径 |",
        "|---|---:|---|",
    ]
    all_evidence: list[EvidenceRef] = []
    for label, indicator in requested:
        if indicator == "unsupported":
            lines.append(f"| {label} | 暂无数据 | 当前数据范围未覆盖 |")
            continue
        result = query_metric(
            company.wind_code,
            indicator,
            as_of=as_of,
            require_exact_period=require_exact,
        )
        if result.status != "ok" or result.value is None:
            lines.append(f"| {label} | 暂无数据 | 母公司口径 |")
            continue
        period = result.period
        lines.append(
            f"| {label} | {_format_indicator_value(result.value, result.unit)} | "
            f"{period[:4]}-{period[4:6]}-{period[6:]}，母公司口径 |"
        )
        all_evidence.extend(
            _evidence_for_observations(state, company, result.observations)
        )
    answer = "\n".join(lines)
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": all_evidence,
        "final_response": FinalResponse(
            answer=answer, risk_level="unknown", evidence=all_evidence
        ),
    }


def _answer_directional_events(state: AgentState) -> dict | None:
    """只渲染用户请求方向的事件，避免混入相反情绪。"""
    plan = state.get("plan")
    direction = getattr(plan, "event_sentiment", "all") if plan else "all"
    list_requested = (
        bool(getattr(plan, "event_list_requested", False)) if plan else False
    )
    if direction == "all" and not list_requested:
        return None
    results = state.get("results")
    events = results.events if results else None
    if events is None:
        return None
    selected = sorted(
        (
            item
            for item in (events.timeline or [])
            if direction == "all" or str(item.get("sentiment", "") or "") == direction
        ),
        key=lambda item: str(item.get("date") or ""),
        reverse=True,
    )
    company = state.get("company")
    if company is None:
        return None
    name_code = f"{company.sec_name}（{company.wind_code}）"
    direction_label = {"positive": "利好", "negative": "利空"}.get(direction, "")
    query = str(state.get("user_query") or "")
    latest_requested = any(
        cue in query for cue in ("最新公告", "最新动态", "最近公告", "公告内容")
    )
    if not selected:
        label = f"{direction_label}事件" if direction_label else "公告或事件"
        answer = f"{name_code}近期未检出可回查的{label}。"
    else:
        rows = []
        for item in selected[:5]:
            date_text = str(item.get("date") or "")
            title = str(item.get("title") or item.get("category") or "公告")
            category = str(item.get("category") or "")
            evidence_id = ", ".join(
                str(i) for i in (item.get("evidence_ids") or []) if i
            )
            detail = f"{date_text} {title}".strip()
            if category and category not in title:
                detail += f"（{category}）"
            if evidence_id:
                detail += f" [证据: {evidence_id}]"
            rows.append(f"- {detail}")
        label = f"{direction_label}事件" if direction_label else "公告或事件"
        if latest_requested:
            latest_date = str(selected[0].get("date") or "未知")
            answer = (
                f"{name_code}数据集内最新可回查的{label}（截至 {latest_date}）：\n"
                + "\n".join(rows)
                + "\n当前事件数据仅保留公告标题和元数据，未取回公告正文；"
                "因此不能把上述记录表述为当前市场的最新公告。"
            )
        else:
            answer = f"{name_code}近期可回查的{label}：\n" + "\n".join(rows)
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": list(events.evidence or []),
        "final_response": FinalResponse(
            answer=answer, risk_level="unknown", evidence=list(events.evidence or [])
        ),
    }


def _answer_indicator(state: AgentState, indicator: str) -> dict:
    """Phase D #3A：基础财务指标确定性短答与可回查证据。"""
    company = state.get("company")
    if company is None:
        return {}
    # 裸 unsupported（无法识别基础指标，如周转率）走兜底文案
    if indicator == "unsupported":
        answer = "该指标暂未覆盖。当前可查询基础报表指标与资产负债率。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    plan = state.get("plan")
    answer_operation = getattr(plan, "answer_operation", "") if plan else ""
    if not answer_operation:
        from app.agents.nodes.plan_modules import _detect_answer_operation

        answer_operation = _detect_answer_operation(state.get("user_query", ""))
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    require_exact = bool(plan and plan.as_of_kind == "report_period")
    # v3.3.3 批次 B：统一入口——registry 指标（r4/r5）与基础指标同构返回
    from app.application.services.indicator_query_service import (
        query_indicator_cagr,
        query_indicator_trend,
        query_metric,
        query_quarter_mom,
        query_quarter_value,
        query_quarter_yoy,
    )

    base_indicator = indicator.removesuffix("_growth").removesuffix("_mom")
    name_code = f"{company.sec_name}（{company.wind_code}）"
    # 趋势问题先读取年度序列，不能先查询最新单期再决定如何回答。
    if answer_operation in ("trend", "causal_trend", "loss_years"):
        query_text = state.get("user_query", "")
        quarterly_trend = bool(
            re.search(r"(?:第?[一二三四1-4]季度|Q[1-4])", query_text, re.IGNORECASE)
        )
        rows = query_indicator_trend(
            company.wind_code,
            base_indicator,
            as_of=as_of,
            annual_only=not quarterly_trend,
        )
        labels = {
            "operating_revenue": "营业收入",
            "net_profit": "净利润",
            "operating_cash_flow": "经营现金流",
            "total_assets": "总资产",
            "total_liabilities": "总负债",
            "accounts_receivable": "应收账款余额",
            "inventories": "存货",
            "r4_turnover_days": "存货周转天数",
            "r5_gross_margin": "毛利率",
        }
        label = labels.get(base_indicator, base_indicator)
        if len(rows) >= 2:
            from app.domain.benchmarks.metric_registry import REGISTRY

            trend_unit = "CNY"
            if base_indicator in REGISTRY:
                trend_unit = REGISTRY[base_indicator].unit

            def period_label(period: str) -> str:
                if quarterly_trend:
                    quarter = {"0331": "Q1", "0630": "Q2", "0930": "Q3", "1231": "Q4"}
                    return f"{period[:4]}{quarter.get(period[4:], period[4:])}"
                return f"{period[:4]}年"

            sequence_label = "季度" if quarterly_trend else "年度"
            table = [
                f"{name_code}的{label}{sequence_label}序列：",
                "",
                f"| {sequence_label} | {label} |",
                "|---|---:|",
                *[
                    f"| {period_label(row.period)} | "
                    f"{_format_indicator_value(row.value, trend_unit)} |"
                    for row in rows
                ],
            ]
            if answer_operation == "loss_years":
                consecutive = 0
                for row in reversed(rows):
                    if row.value < 0:
                        consecutive += 1
                    else:
                        break
                conclusion = (
                    f"截至最新可用年度，连续亏损 {consecutive} 年。"
                    if consecutive
                    else "截至最新可用年度，未处于连续亏损状态。"
                )
            else:
                conclusion = (
                    "持续下降。"
                    if all(a.value > b.value for a, b in zip(rows, rows[1:]))
                    else "未呈连续下降。"
                )
            answer = "\n".join(table) + "\n\n" + conclusion
            if answer_operation == "causal_trend":
                answer += "仅凭该指标序列无法确认原因，需要结合成本结构和公告证据。"
        else:
            answer = (
                f"{name_code}的{label}：暂不支持多年序列趋势，当前可用年度序列不足，"
                "不会用最新一期结果代替。"
            )
        _emit_segment(state, answer)
        trend_evidence = []
        for row in rows:
            trend_evidence.extend(
                _evidence_for_observations(
                    state, company, getattr(row, "observations", None) or []
                )
            )
        trend_evidence = _merge_unique(
            trend_evidence, key=lambda item: item.evidence_id
        )
        return {
            "claims": [],
            "evidence": trend_evidence,
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", evidence=trend_evidence
            ),
        }
    if answer_operation == "cagr":
        result = query_indicator_cagr(company.wind_code, base_indicator, as_of=as_of)
    elif answer_operation == "quarter_yoy":
        result = query_quarter_yoy(company.wind_code, base_indicator, as_of=as_of)
    elif answer_operation == "quarter_single":
        result = query_quarter_value(company.wind_code, base_indicator, as_of=as_of)
    elif answer_operation == "quarter_mom":
        result = query_quarter_mom(company.wind_code, base_indicator, as_of=as_of)
    else:
        result = query_metric(
            company.wind_code,
            indicator,
            as_of=as_of,
            require_exact_period=require_exact,
        )
    # 2026-08-12 三轮审查修订：带 label 的 unsupported（环比/双字段增速）
    # 与 insufficient_data 分开，不再一律答"数据不足"
    if result.status == "unsupported":
        answer = f"{name_code}的{result.label}：暂不支持该指标的同比/环比计算。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if result.status != "ok" or result.value is None:
        answer = f"{name_code}的{result.label}：数据不足，无法按母公司口径计算。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    # 多年趋势不得退化成最新单期。基础指标有年度序列时直接展示序列；
    # registry 指标暂无序列时也明确说明缺口。
    if answer_operation in ("trend", "causal_trend"):
        rows = query_indicator_trend(company.wind_code, base_indicator, as_of=as_of)
        if len(rows) >= 2:
            values = "；".join(
                f"{row.period[:4]}年 {_format_indicator_value(row.value, result.unit)}"
                for row in rows
            )
            direction = (
                "持续下降"
                if all(a.value > b.value for a, b in zip(rows, rows[1:]))
                else "未呈连续下降"
            )
            answer = f"{name_code}的{result.label}年度序列：{values}。{direction}。"
            if answer_operation == "causal_trend":
                answer += "仅凭该指标序列无法确认原因，需要结合成本结构和公告证据。"
        else:
            answer = (
                f"{name_code}的{result.label}：当前可用年度序列不足，"
                "无法确认多年趋势或原因，不用最新一期代替。"
            )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    # v3.3.3 收口批次 D（方案 §3.6）：「正常吗」类问句走 assessment，
    # 只答数值时不得用泛化话术冒充判断
    if answer_operation == "assessment":
        return _answer_indicator_assessment(state, company, result)

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    value_text = _format_indicator_value(result.value, result.unit)
    period_text = f"{result.period[:4]}-{result.period[4:6]}-{result.period[6:]}"
    # 同比增速答案：正负文案 + 对比基准期（2026-08-12 修订）
    if indicator.endswith("_growth"):
        comparison_text = (
            f"{result.comparison_period[:4]}-{result.comparison_period[4:6]}"
            f"-{result.comparison_period[6:]}"
        )
        answer = (
            f"{name_code}的{result.label}为 {_format_growth(result.value)}"
            f"（{period_text} 较 {comparison_text}，母公司口径）。"
        )
        claim_value_text = _format_growth(result.value)
    elif answer_operation == "turnaround":
        status_text = "已实现扭亏为盈" if result.value >= 0 else "尚未扭亏为盈"
        answer = (
            f"{name_code}的{result.label}为 {value_text}"
            f"（{period_text}，母公司口径），{status_text}。"
        )
        claim_value_text = value_text
    else:
        answer = (
            f"{name_code}的{result.label}为 {value_text}"
            f"（{period_text}，母公司口径）。"
        )
        claim_value_text = value_text

    if answer_operation == "cagr":
        start_period = result.observations[0].period if result.observations else ""
        end_period = (
            result.observations[-1].period if result.observations else result.period
        )
        answer = (
            f"{name_code}的{result.label}为 {result.value:.2f}%"
            f"（{start_period[:4]}-{end_period[:4]}年，母公司口径）。"
        )
        claim_value_text = f"{result.value:.2f}%"
    elif answer_operation == "causal":
        answer += "仅凭该指标当前值无法确认下降原因，需要结合期间序列和公告证据。"
    elif answer_operation == "impact":
        trend_rows = query_indicator_trend(
            company.wind_code,
            base_indicator,
            as_of=as_of,
            annual_only=True,
        )
        answer += _indicator_impact_text(
            base_indicator=base_indicator,
            query=state.get("user_query", ""),
            trend_rows=trend_rows,
            name_code=name_code,
        )

    # 双期间契约（2026-08-12 修订）：逐 observation 用自己的 period 生成
    # source_record_id/evidence_id——同比查询含当前期与去年同期两条证据，
    # 不再共用 result.period 导致两条 evidence_id 相同。
    # v3.3.3 批次 C：构造逻辑提取为 _evidence_for_observations，供指标短答
    # 与轻量比较共用。
    evidence: list[EvidenceRef] = _evidence_for_observations(
        state, company, result.observations
    )
    evidence_ids = [item.evidence_id for item in evidence]
    claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="indicator",
            claim_text=f"{result.label}：{claim_value_text}",
        ),
        text=f"{result.label}为 {claim_value_text}",
        claim_type="indicator",
        severity="unknown",
        evidence_ids=evidence_ids,
        verification_status="verified",
        limitations=["母公司报表口径"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="finance",
    )
    _emit_segment(state, answer)
    return {
        "claims": [claim],
        "evidence": evidence,
        # v3.3.3 批次 B（方案 §5.4）：成功执行的规范指标写入 state，
        # persist_turn 落 response_meta.executed_metrics；失败/unsupported
        # 轮不返回本字段（不得覆盖最近成功指标）
        "executed_metric": {
            "metric_id": indicator,
            "period": result.period,
            "unit": result.unit,
            "status": "ok",
            # v3.3.3 收口批次 B（方案 §3.4）：指标所属公司，防跨主体串用
            "company_code": company.wind_code,
        },
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[claim],
            evidence=evidence,
        ),
    }


def _answer_indicator_assessment(state, company, result) -> dict:
    """v3.3.3 收口批次 D（方案 §3.6）：「正常吗」类 assessment。

    输出：当前值 + 报告期 + 行业基准分位/中位数 + 样本数 + 偏离结论；
    无可靠行业基准 → 明确「已查到当前值，但缺少可比较基准，无法判断
    正常性」，不得用泛化风险话术冒充判断。值本身照常生成 claim/evidence。
    """
    from app.application.services.indicator_query_service import (
        query_industry_benchmark,
    )
    from app.domain.benchmarks.calculator import MIN_PEER_SAMPLE

    name_code = f"{company.sec_name}（{company.wind_code}）"
    value_text = _format_indicator_value(result.value, result.unit)
    period_text = f"{result.period[:4]}-{result.period[4:6]}-{result.period[6:]}"
    base_answer = (
        f"{name_code}的{result.label}为 {value_text}" f"（{period_text}，母公司口径）。"
    )
    industry = getattr(company, "industry_l1", "") or ""
    bench = query_industry_benchmark(industry, result.indicator, result.period)
    sample_count = (bench or {}).get("sample_count") or 0
    if bench is None or sample_count < MIN_PEER_SAMPLE:
        answer = base_answer + "当前数据缺少可比较的行业基准，无法判断是否「正常」。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    # 基准表存 registry 原始口径（ratio 小数/days/pp），展示前换算
    def _bench_display(raw) -> str:
        if raw is None:
            return "—"
        if result.unit == "percent":
            return f"{float(raw) * 100:.2f}%"
        return f"{float(raw):.2f}"

    value_raw = result.value / 100 if result.unit == "percent" else result.value
    query = state.get("user_query", "")
    if "平均" in query:
        mean_value = bench.get("mean_value")
        if mean_value is None:
            answer = base_answer + "行业平均值缺失，无法完成比较。"
        else:
            mean_text = _bench_display(mean_value)
            if "低于" in query:
                relation = "低于" if value_raw < mean_value else "不低于"
            else:
                relation = "高于" if value_raw > mean_value else "不高于"
            answer = (
                base_answer
                + f"{result.label}{relation}行业平均值"
                + f"（平均值 {mean_text}，{sample_count} 家可比公司）。"
            )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    p50 = bench.get("p50")
    p75 = bench.get("p75")
    if p50 is None or p75 is None:
        answer = base_answer + "行业基准分位缺失，无法判断是否「正常」。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    if value_raw <= p50:
        band = (
            f"不高于行业中位数（中位数 {_bench_display(p50)}，"
            f"{sample_count} 家可比公司），处于行业较低水平"
        )
    elif value_raw <= p75:
        band = (
            f"位于行业中位数与 75 分位之间（p75 {_bench_display(p75)}，"
            f"{sample_count} 家可比公司），处于行业中等水平"
        )
    else:
        band = (
            f"高于行业 75 分位（p75 {_bench_display(p75)}，"
            f"{sample_count} 家可比公司），处于行业较高水平"
        )
    answer = base_answer + f"{result.label}相对行业：{band}。"

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    evidence: list[EvidenceRef] = _evidence_for_observations(
        state, company, result.observations
    )
    evidence_ids = [item.evidence_id for item in evidence]
    claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="indicator",
            claim_text=f"{result.label}：{value_text}",
        ),
        text=f"{result.label}为 {value_text}",
        claim_type="indicator",
        severity="unknown",
        evidence_ids=evidence_ids,
        verification_status="verified",
        limitations=["母公司报表口径", "行业基准判断"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="finance",
    )
    _emit_segment(state, answer)
    return {
        "claims": [claim],
        "evidence": evidence,
        "executed_metric": {
            "metric_id": result.indicator,
            "period": result.period,
            "unit": result.unit,
            "status": "ok",
            "company_code": company.wind_code,
        },
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[claim],
            evidence=evidence,
        ),
    }


def _indicator_impact_text(
    *, base_indicator: str, query: str, trend_rows: list, name_code: str
) -> str:
    """为影响类指标问题验证前提，再给出有限的财务解释。"""
    if base_indicator == "operating_cash_flow":
        return "问题未说明具体影响事件，当前数据无法建立该事件与现金流之间的因果关系。"
    if base_indicator != "accounts_receivable":
        return "仅凭该指标当前值无法确认实际影响，需要结合变化趋势和公告证据。"

    if len(trend_rows) >= 2 and trend_rows[-2].value:
        previous, current = trend_rows[-2], trend_rows[-1]
        growth = (current.value / abs(previous.value) - 1) * 100
        change = (
            f"{previous.period[:4]}年至{current.period[:4]}年{_format_growth(growth)}"
        )
        if "激增" in query and growth <= 20:
            return f"现有年度序列显示{change}，不支持“应收账款激增”这一前提。"
        return (
            f"现有年度序列显示{change}。"
            "[推断] 若应收账款增速持续高于营业收入，可能带来回款压力、"
            "坏账减值风险和利润现金含量下降；仍需结合账龄及客户集中度核验。"
        )
    return (
        f"当前数据不足以验证{name_code}应收账款是否激增。"
        "[推断] 若确有激增，可能带来回款压力、坏账减值风险和利润现金含量下降；"
        "不能仅凭单期余额确认。"
    )


def _answer_industry_benchmark(state: AgentState) -> dict:
    """回答无公司行业均值/趋势，使用真实基准行而非任意公司值。"""
    plan = state.get("plan")
    industry = getattr(plan, "industry_l1", "") if plan else ""
    indicator = getattr(plan, "indicator", "") if plan else ""
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    operation = getattr(plan, "answer_operation", "") if plan else ""
    if operation in ("industry_leader", "industry_total"):
        answer = (
            f"当前行业基准只提供行业均值和分位，未覆盖"
            f"{'行业营业收入总额' if operation == 'industry_total' else '按指标排序个股'}；"
            f"无法可靠回答「{industry}」的该问题。"
        )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    from app.application.services.indicator_query_service import (
        query_industry_benchmark_series,
    )

    rows = query_industry_benchmark_series(industry, indicator, as_of=as_of)
    try:
        from app.domain.benchmarks.metric_registry import get_metric

        metric_label = get_metric(indicator).name
    except KeyError:
        metric_label = indicator
    if not rows:
        answer = f"行业「{industry}」暂无{metric_label}的可用母公司口径基准数据。"
    else:
        try:
            from app.domain.benchmarks.metric_registry import get_metric

            is_ratio = get_metric(indicator).unit == "ratio"
        except KeyError:
            is_ratio = False

        def display(value) -> str:
            if value is None:
                return "—"
            return f"{float(value) * 100:.2f}%" if is_ratio else f"{float(value):.2f}"

        if operation == "trend" and len(rows) >= 2:
            values = "；".join(
                f"{row['period'][:4]}年 {display(row['mean_value'])}" for row in rows
            )
            answer = f"行业「{industry}」的{metric_label}年度均值：{values}。"
        else:
            row = rows[-1]
            answer = (
                f"行业「{industry}」最新可用期 {row['period']} 的{metric_label}平均值为 "
                f"{display(row['mean_value'])}（{row['sample_count']} 家可比公司，母公司口径）。"
            )
            if operation == "trend":
                answer += "可用年度序列不足，无法判断多年变化。"
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": [],
        "final_response": FinalResponse(answer=answer, risk_level="unknown"),
    }


def _evidence_for_observations(
    state: AgentState, company, observations: list
) -> list[EvidenceRef]:
    """逐 observation 生成 EvidenceRef（双期间契约，v3.3.3 批次 C 提取）。

    指标短答与轻量比较共用；每条 observation 用自己的 period 生成
    source_record_id/evidence_id。
    """
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    evidence: list[EvidenceRef] = []
    for observation in observations:
        obs_period = getattr(observation, "period", "") or ""
        field_path = getattr(observation, "field_path", "")
        source_table = getattr(observation, "source_table", "")
        value = getattr(observation, "value", "")
        source_record_id = f"{company.wind_code}|{obs_period}|{PARENT_STATEMENT_TYPE}"
        evidence_id = make_evidence_id(
            source_namespace=NS_FINANCE,
            source_type="financial_statement",
            source_record_id=source_record_id,
            field_path=field_path,
            period=obs_period,
            dataset_version=settings.DATASET_VERSION,
            company_code=company.wind_code,
        )
        evidence.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="financial_statement",
                source_record_id=source_record_id,
                source_table=source_table,
                field_path=field_path,
                period=obs_period,
                value=str(value),
                unit="CNY",
                source_title=f"{company.sec_name} · 母公司报表",
                statement_scope="parent_company",
                module="finance",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                dataset_version=settings.DATASET_VERSION,
            )
        )
    return evidence
