"""跨公司对比路由 — V12 §11.14 + Phase C 任务 13.

POST /api/v1/comparisons

要求（任务 13）:
  - 2-5 家公司，统一 CompanyResolver
  - 正确解析 YYYYMMDD / YYYY-MM-DD / YYYYQ1-YYYYQ4（2026Q2 → 20260630，不得 2026Q201）
  - 每家公司只执行一次规则分析（缓存，不逐指标重复执行）
  - statement_scope 固定 parent_company
  - 单家公司失败 → partial warning（绝不 except: pass 静默吞错）
  - 输出指标、风险、coverage、evidence

v3.5（契约收口）:
  - analysis_run 生命周期：请求开始 status=running → 完成后更新
    completed / partial / failed；失败记录不得标 completed
    （请求级 HTTPException/异常同样标 failed）；
  - 全程复用同一个 ProvenanceService 实例。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.comparisons import (
    CompanyIndicator,
    CompanyRiskSummary,
    ComparisonAnalysisData,
    ComparisonRequest,
    ComparisonsResponseData,
    IndicatorCompare,
    MetricPeriodRow,
    RuleMetricValue,
    TriggeredRuleDetail,
)
from app.core.config import settings

router = APIRouter(tags=["comparisons"])


def _trace() -> str:
    return str(uuid.uuid4())


def _indicator_label(rid: str) -> str:
    """指标标签（单一来源：D2 规则元数据，替代原硬编码 _INDICATOR_LABELS）。"""
    from app.domain.finance.financial_rule_config import load_financial_rules

    meta = load_financial_rules().metadata.get(rid)
    return meta.name if meta else rid


def _metric_label(rid: str, key: str) -> str:
    """规则中间量标签，供多字段指标对比展示。"""
    from app.domain.finance.financial_rule_config import load_financial_rules

    meta = load_financial_rules().metadata.get(rid)
    metric = next(
        (item for item in (meta.metrics if meta else []) if item.key == key), None
    )
    return metric.label if metric else f"{_indicator_label(rid)} · {key}"


_FINANCIAL_REPORT_INDICATORS = (
    "operating_revenue",
    "net_profit",
    "operating_cash_flow",
    "total_assets",
    "total_liabilities",
)


def _quarter_ends(latest_ymd: str, n: int = 4) -> list[str]:
    """从最新期起向前取 n 个季度末期次（YYYYMMDD，从新到旧）。"""
    y = int(latest_ymd[:4])
    m = int(latest_ymd[4:6])
    ends = ("0331", "0630", "0930", "1231")
    idx = {"3": 0, "6": 1, "9": 2, "12": 3}.get(str(((m - 1) // 3) * 3 + 3), 3)
    out: list[str] = []
    yy, ii = y, idx
    for _ in range(n):
        out.append(f"{yy:04d}{ends[ii]}")
        ii -= 1
        if ii < 0:
            ii = 3
            yy -= 1
    return out


def _build_financial_indicators(
    resolved_map: dict, period_ymd: str
) -> list[IndicatorCompare]:
    """构造财务人员可直接阅读的标准财报科目对比。

    8/23 期次回退：请求期为未来期（如默认 2026Q2→20260630，库内最新
    20260331）时精确匹配必然失败——若各公司库内最新期次一致，回退到该
    最新期次（共同交集）；各公司最新期不同或请求期不晚于最新期时保持
    请求期原语义（数据不足如实显示）。

    8/23 多期对比：每个科目附带近 4 期序列（期集 = 各公司最新期最大值
    起向前 4 个季度末），按期次对齐，缺数据如实置空。
    """
    from app.application.services.indicator_query_service import query_metric

    use_period = period_ymd
    try:
        from app.domain.finance.data_as_of import resolve_company_data_as_of

        latest_set = {
            (resolve_company_data_as_of(rec.wind_code) or "")
            for rec in resolved_map.values()
        }
        latest_set.discard("")
        if latest_set and period_ymd > max(latest_set):
            # 请求期晚于所有公司最新披露期 → 回退「共同覆盖的最晚期次」：
            # min(各公司最新期) 是每一家都有数据的最晚共同期次
            # （如比亚迪/隆基 20260331、宁德 20251231 → 共同期 20251231）
            use_period = min(latest_set)
    except Exception:  # noqa: BLE001 — 期次推导失败保持请求期
        pass

    # 8/23 多期序列：期集 = max(各公司最新期) 起向前 4 个季度末
    series_periods: list[str] = []
    try:
        from app.domain.finance.data_as_of import resolve_company_data_as_of

        latest_all = [
            (resolve_company_data_as_of(rec.wind_code) or "")
            for rec in resolved_map.values()
        ]
        latest_all = [x for x in latest_all if x]
        if latest_all:
            series_periods = _quarter_ends(max(latest_all), 4)
    except Exception:  # noqa: BLE001 — 多期序列失败仅缺失序列
        pass

    rows: list[IndicatorCompare] = []
    for metric_id in _FINANCIAL_REPORT_INDICATORS:
        companies: list[CompanyIndicator] = []
        labels: list[str] = []
        periods: list[str] = []
        units: list[str] = []
        for rec in resolved_map.values():
            result = query_metric(
                rec.wind_code,
                metric_id,
                as_of=use_period,
                require_exact_period=True,
            )
            labels.append(result.label or metric_id)
            periods.append(result.period or "")
            units.append(result.unit or "")
            companies.append(
                CompanyIndicator(
                    wind_code=rec.wind_code,
                    sec_name=rec.sec_name,
                    value=(
                        float(result.value)
                        if result.status == "ok" and result.value is not None
                        else None
                    ),
                    unit=result.unit or "",
                    period=result.period or use_period,
                    status=result.status,
                )
            )

        # 8/23 多期序列：逐期次逐公司查询（精确匹配，缺期如实置空）
        series: list[MetricPeriodRow] = []
        if series_periods:
            for p in series_periods:
                pts: list[CompanyIndicator] = []
                for rec in resolved_map.values():
                    r = query_metric(
                        rec.wind_code,
                        metric_id,
                        as_of=p,
                        require_exact_period=True,
                    )
                    pts.append(
                        CompanyIndicator(
                            wind_code=rec.wind_code,
                            sec_name=rec.sec_name,
                            value=(
                                float(r.value)
                                if r.status == "ok" and r.value is not None
                                else None
                            ),
                            unit=r.unit or "",
                            period=p,
                            status=r.status,
                        )
                    )
                series.append(MetricPeriodRow(period=p, companies=pts))

        common_period = (
            periods[0]
            if periods
            and periods[0]
            and all(period == periods[0] for period in periods)
            else ""
        )
        common_unit = (
            units[0]
            if units and units[0] and all(unit == units[0] for unit in units)
            else ""
        )
        difference = None
        if (
            len(companies) == 2
            and all(company.value is not None for company in companies)
            and common_period
            and common_unit
        ):
            difference = companies[0].value - companies[1].value
        rows.append(
            IndicatorCompare(
                indicator=metric_id,
                label=next((label for label in labels if label), metric_id),
                companies=companies,
                period=common_period,
                difference=difference,
                difference_unit=common_unit,
                series=series,
            )
        )
    return rows


def _build_rule_details(
    results, rule_evidence_map: dict[str, list[str]], period_ymd: str
) -> list[TriggeredRuleDetail]:
    """触发规则详情（⑥/③）：D2 元数据 + current 多指标展开。

    证据规则级（v3.4 方向 A）：evidence_ids 从 rule_evidence_map[rid] 取
    ——同一 Evidence 可被多条规则引用（如营业收入被 R1/R4 共用），
    但只落库一次；不再通过 field_path=rule_Rx 反查（历史反查导致
    R4/R7 共享证据丢失）。
    """
    from app.domain.finance.financial_rule_config import load_financial_rules

    meta_map = load_financial_rules().metadata
    details: list[TriggeredRuleDetail] = []
    for rid, r in results.items():
        if r is None or r.status != "triggered":
            continue
        meta = meta_map.get(rid)
        metrics: list[RuleMetricValue] = []
        for key, m in (r.current or {}).items():
            mm = next((x for x in meta.metrics if x.key == key), None) if meta else None
            metrics.append(
                RuleMetricValue(
                    key=key,
                    label=mm.label if mm else key,
                    value=m.get("value") if isinstance(m, dict) else m,
                    unit=(m.get("unit") if isinstance(m, dict) else "")
                    or (mm.unit if mm else ""),
                    risk_direction=mm.risk_direction if mm else "neutral",
                )
            )
        rid_evidence = sorted(rule_evidence_map.get(rid, []))
        details.append(
            TriggeredRuleDetail(
                rule_id=rid,
                label=meta.name if meta else rid,
                status=r.status,
                severity=r.severity,
                as_of=period_ymd,
                metrics=metrics,
                evidence_ids=rid_evidence,
                explanation=r.explanation or "",
            )
        )
    return details


async def _resolve_company(code: str):
    from app.application.services.company_resolver import resolve_company

    return await resolve_company(code)


@router.post("/comparisons", response_model=V12Response[ComparisonsResponseData])
async def create_comparison(body: ComparisonRequest):
    """跨公司对比 — 对 2-5 家公司按指标对比，含风险摘要 + coverage + evidence。"""
    trace_id = _trace()
    warnings: list[WarningItem] = []
    data_warnings: list[str] = []

    # 固定母公司口径（任务 13：不接受其他 scope）
    statement_scope = "parent_company"

    # v3.5：统一复用同一 ProvenanceService + analysis_run 生命周期
    from app.application.services.provenance_service import ProvenanceService

    svc = ProvenanceService()
    run_id: str | None = None
    try:
        run_id = svc.create_analysis_run(
            trace_id=trace_id,
            endpoint="companies/{code}/comparisons",
            company_codes=list(body.company_codes),
            period=body.period,
            status="running",
        )
    except Exception:  # noqa: BLE001 — run 载体失败不阻塞主流程
        run_id = None

    def _finalize(status: str) -> None:
        if run_id:
            try:
                svc.update_analysis_run_status(run_id, status)
            except Exception:  # noqa: BLE001 — 状态更新失败不阻塞响应
                pass

    try:
        return await _create_comparison_impl(
            body, trace_id, warnings, data_warnings, statement_scope, svc, _finalize
        )
    except HTTPException:
        _finalize("failed")  # v3.5：请求级失败不得停留 running
        raise
    except Exception:
        _finalize("failed")
        raise


async def _create_comparison_impl(
    body: ComparisonRequest,
    trace_id: str,
    warnings: list[WarningItem],
    data_warnings: list[str],
    statement_scope: str,
    svc,
    _finalize,
):
    """comparisons 主体（v3.5 拆分：外层统一 finalize 生命周期）。"""
    # period 规范化（2026Q2 → 20260630）
    from app.domain.finance.period import normalize_period

    period_ymd = normalize_period(body.period)
    if period_ymd is None:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://truthnet.dev/errors/invalid-period",
                "title": "Invalid Period",
                "status": 422,
                "detail": f"无法解析期间: {body.period}",
                "error_code": "INVALID_PERIOD",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # ── 1. 解析所有公司 ──
    resolved_map: dict[str, object] = {}
    for code in body.company_codes:
        rec = await _resolve_company(code)
        if rec is None:
            warnings.append(
                WarningItem(
                    code="COMPANY_NOT_COVERED",
                    message=f"{code} 不在数据覆盖范围，已跳过",
                    module="comparisons",
                    recoverable=True,
                )
            )
            continue
        resolved_map[code] = rec

    if len(resolved_map) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://truthnet.dev/errors/insufficient-companies",
                "title": "Insufficient Companies",
                "status": 400,
                "detail": f"需要至少 2 家可对比公司，当前 {len(resolved_map)} 家",
                "error_code": "INSUFFICIENT_COMPANIES",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # ── 2. 每家公司只执行一次规则分析（缓存）+ 证据幂等落库（⑥）──
    #    drafts 与 /finance 同源（finance_evidence 共享纯函数），
    #    落库成功才返回 evidence_ids（不可回查的 ID 不返回）。
    rule_cache: dict[str, dict] = {}
    company_failures: dict[str, str] = {}

    from app.application.services.finance_evidence import (
        build_finance_rule_evidence_drafts,
    )
    from app.domain.finance.rule_engine import evaluate_all_rules

    for code, rec in resolved_map.items():
        try:
            results = evaluate_all_rules(rec.wind_code, period_ymd)
            built = build_finance_rule_evidence_drafts(
                rules=results, wind_code=rec.wind_code, as_of=period_ymd
            )
            drafts = list(built["unique_drafts"].values())
            rule_evidence_map = built["rule_evidence_map"]
            persist_ok = True
            if drafts:
                try:
                    svc.persist_evidence(drafts, trace_id=trace_id, turn_id=trace_id)
                except Exception as exc:  # noqa: BLE001 — 落库失败不伪造可回查 ID
                    persist_ok = False
                    data_warnings.append(
                        f"{code} 证据落库失败（该公司标记 partial，不返回不可回查 ID）: {exc}"
                    )
            rule_cache[code] = {
                "wind_code": rec.wind_code,
                "sec_name": rec.sec_name,
                "industry_l1": rec.industry_l1 or "",
                "results": results,
                "drafts": drafts,
                "rule_evidence_map": rule_evidence_map,
                "persist_ok": persist_ok,
            }
        except Exception as exc:  # noqa: BLE001 — 记录失败，不静默吞掉
            company_failures[code] = str(exc)
            data_warnings.append(f"{code} 分析失败: {exc}")

    # ── 3. 公司风险摘要 ──
    company_summaries: list[CompanyRiskSummary] = []
    for code, rec in resolved_map.items():
        if code in company_failures:
            company_summaries.append(
                CompanyRiskSummary(
                    wind_code=rec.wind_code,
                    sec_name=rec.sec_name,
                    industry_l1=rec.industry_l1 or "",
                    risk_level="unknown",
                    overall_score=0.0,
                    partial=True,
                )
            )
            continue
        entry = rule_cache[code]
        results = entry["results"]
        triggered = [rid for rid, r in results.items() if r.status == "triggered"]
        red_count = sum(1 for r in results.values() if r.severity == "red")
        orange_count = sum(1 for r in results.values() if r.severity == "orange")
        overall_score = min(
            1.0, red_count * 0.25 + orange_count * 0.15 + len(triggered) * 0.05
        )
        risk_level = (
            "red"
            if overall_score >= 0.6
            else (
                "orange"
                if overall_score >= 0.35
                else ("yellow" if overall_score >= 0.15 else "green")
            )
        )
        # coverage：规则 quality 数据完整性均值
        completions = [
            r.quality.get("data_completeness", 0.0)
            for r in results.values()
            if r.quality and r.quality.get("data_completeness") is not None
        ]
        coverage = round(sum(completions) / len(completions), 3) if completions else 0.0
        # 模式匹配（唯一来源 fraud_patterns.yaml）
        pattern_names: list[str] = []
        try:
            from app.domain.risk.fraud_patterns import match_patterns

            rule_dict = {
                rid: {"status": r.status, "severity": r.severity}
                for rid, r in results.items()
            }
            pattern_names = [
                f"{m.pattern_id}({m.pattern_name})" for m in match_patterns(rule_dict)
            ]
        except Exception:  # noqa: BLE001 — pattern 失败不阻塞对比
            pattern_names = []

        # ⑥/③ 触发规则详情（v3.4 失败契约：落库失败 → partial +
        # 详情证据清空 + 结构化 recoverable warning，不返回不可回查 ID）
        details = _build_rule_details(
            entry["results"], entry["rule_evidence_map"], period_ymd
        )
        evidence_ids: list[str] = []
        if entry["persist_ok"]:
            evidence_ids = sorted(
                eid
                for rid in triggered
                for eid in entry["rule_evidence_map"].get(rid, [])
            )
            evidence_ids = sorted(set(evidence_ids))
        else:
            for d in details:
                d.evidence_ids = []
            warnings.append(
                WarningItem(
                    code="EVIDENCE_PERSIST_FAILED",
                    message=f"{entry['sec_name']} 规则证据落库失败，详情证据已清空"
                    "（不返回不可回查 ID）",
                    module="comparisons",
                    recoverable=True,
                )
            )
        company_summaries.append(
            CompanyRiskSummary(
                wind_code=entry["wind_code"],
                sec_name=entry["sec_name"],
                industry_l1=entry["industry_l1"],
                risk_level=risk_level,
                overall_score=round(overall_score, 3),
                triggered_rules=triggered,
                triggered_rule_details=details,
                pattern_matches=pattern_names,
                coverage=coverage,
                evidence_ids=evidence_ids,
                partial=not entry["persist_ok"],
            )
        )

    # ── 4. 指标对比（复用缓存结果）──
    indicator_compares: list[IndicatorCompare] = []
    for ind in body.indicators:
        # current 可能包含多个真实中间量（R3/R4/R5 等）。按字段展开，
        # 不能只取第一个字段，否则对比页会静默丢失指标。
        metric_keys: list[str] = []
        for code in resolved_map:
            if code in company_failures:
                continue
            current = rule_cache[code]["results"].get(ind) or None
            for key in (current.current if current else {}) or {}:
                if key not in metric_keys:
                    metric_keys.append(key)
        if not metric_keys:
            metric_keys = [""]

        for metric_key in metric_keys:
            companies: list[CompanyIndicator] = []
            for code, rec in resolved_map.items():
                if code in company_failures:
                    companies.append(
                        CompanyIndicator(
                            wind_code=rec.wind_code,
                            sec_name=rec.sec_name,
                            status="insufficient_data",
                        )
                    )
                    continue
                entry = rule_cache[code]
                r = entry["results"].get(ind)
                if r is None:
                    companies.append(
                        CompanyIndicator(
                            wind_code=entry["wind_code"],
                            sec_name=entry["sec_name"],
                            status="not_applicable",
                        )
                    )
                    continue
                metric = (r.current or {}).get(metric_key) if metric_key else None
                value = metric.get("value") if isinstance(metric, dict) else None
                unit = metric.get("unit", "") if isinstance(metric, dict) else ""
                companies.append(
                    CompanyIndicator(
                        wind_code=entry["wind_code"],
                        sec_name=entry["sec_name"],
                        value=value,
                        unit=unit,
                        severity=r.severity,
                        status=r.status if metric_key else "insufficient_data",
                    )
                )
            indicator_compares.append(
                IndicatorCompare(
                    indicator=f"{ind}.{metric_key}" if metric_key else ind,
                    label=(
                        _metric_label(ind, metric_key)
                        if metric_key
                        else _indicator_label(ind)
                    ),
                    companies=companies,
                )
            )

    # 标准财报科目单独透出，供对比页以财务表格展示；不混入 R1-R7 风险指标。
    financial_indicators = _build_financial_indicators(resolved_map, period_ymd)

    # v3.5：完成状态——全失败 failed / 有失败 partial / 全部成功 completed
    if company_failures and len(company_failures) == len(resolved_map):
        _finalize("failed")
    elif company_failures or any(not e["persist_ok"] for e in rule_cache.values()):
        _finalize("partial")
    else:
        _finalize("completed")

    return V12Response(
        data=ComparisonsResponseData(
            period=body.period,
            statement_scope=statement_scope,
            companies=company_summaries,
            indicators=indicator_compares,
            financial_indicators=financial_indicators,
            dataset_version=settings.DATASET_VERSION,
            warnings=data_warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
            rule_set_version=settings.RULE_SET_VERSION,
        ),
        warnings=warnings,
    )


@router.get(
    "/comparisons/analysis",
    response_model=V12Response[ComparisonAnalysisData],
    responses={422: {"model": dict}, 500: {"model": dict}},
)
async def get_comparison_analysis(
    codes: str = Query(
        ..., description="对比公司代码，逗号分隔（2-5 家），如 600518.SH,603693.SH"
    ),
) -> V12Response[ComparisonAnalysisData]:
    """8/23 会7 深化：跨公司 LLM 综合分析（等级/评分/触发规则锁定 → 对比分析）。

    单家公司风险分析失败 → partial warning，其余照常；全部失败 → 空结果。
    """
    from app.application.services.comparison_advice_service import (
        assemble_comparison_advice,
    )

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not (2 <= len(code_list) <= 5):
        raise HTTPException(
            status_code=422,
            detail="对比公司数量需为 2-5 家（逗号分隔）。",
        )
    unique = list(dict.fromkeys(code_list))
    result = await assemble_comparison_advice(unique)
    return V12Response(
        data=result,
        meta=ApiMeta(
            request_id=_trace(),
            trace_id=_trace(),
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
            rule_set_version=settings.RULE_SET_VERSION,
        ),
        warnings=[],
    )
