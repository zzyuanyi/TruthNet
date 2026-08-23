"""Finance — V12 §8.1. 财务分析节点。

Phase C 口径修正: 调用真实规则引擎（evaluate_all_rules），固定母公司报表口径。
- 项目财务规则固定采用母公司报表（statement_type=408006000，scope=parent_company），
  不再使用"合并报表优先、母公司降级"，不再输出"降级" warning。
- 模块执行时始终将统一口径说明（SCOPE_NOTE）放入 results.finance.warnings，恰好一次；
  规则 field 级 warning 去重（保持顺序）后追加。
- 规则证据 source_type=408006000、source_title 标记"母公司报表"。
- 规则引擎不可用（无 DB / 异常）时返回 failed + 明确 warning，绝不返回 Mock 触发结果。
- 全部规则因数据不足/不适用而无有效信号时返回 partial，标注数据真实缺失。
"""

from app.agents.state import (
    AgentState,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
    ModuleStatus,
)
from app.application.services.similar_case_provider import (
    SimilarCaseProvider,
    compute_similar_cases,
)
from app.application.services.finance_evidence import display_period
from app.domain.finance import parent_scope
from app.domain.finance.parent_scope import (
    PARENT_STATEMENT_TYPE,
    SCOPE_NOTE,
    W_COMPANY_TYPE_UNKNOWN,
)

_RULES = [f"R{i}" for i in range(1, 8)]

# 相似指标案例 Provider（模块级可注入，供测试替换 FakeProvider）
_similar_case_provider: SimilarCaseProvider | None = None


def set_similar_case_provider(provider: SimilarCaseProvider | None) -> None:
    """注入/重置相似案例 Provider（测试替换 FakeProvider）。"""
    global _similar_case_provider
    _similar_case_provider = provider


def get_similar_case_provider() -> SimilarCaseProvider:
    """返回当前相似案例 Provider（默认惰性建真实实现）。"""
    global _similar_case_provider
    if _similar_case_provider is None:
        from app.application.services.similar_case_provider import (
            RealSimilarCaseProvider,
        )

        _similar_case_provider = RealSimilarCaseProvider()
    return _similar_case_provider


# 规则证据 ID 中的表代码 → 真实表名
_TABLE_CODE_MAP = {
    "bs": "balance_sheet",
    "is": "income_statement",
    "cf": "cash_flow",
}

# 证据字段 → 报表真实列名（规则层字段名与列名不一致时的别名）
# 取值时按别名读 resolve_source 返回的记录；borrow 拆为两项拼接。
_FIELD_ALIASES: dict[str, str | tuple[str, str]] = {
    "net_profit": "net_profit_excl_min_int_inc",
    "core_profit": "net_profit_after_ded_nr_lp",
    "oper": "net_cash_flows_oper_act",
    "oper_cf": "net_cash_flows_oper_act",
    "oper_cost": "less_oper_cost",
    "borrow": ("st_borrow", "lt_borrow"),
}


def _parse_rule_evidence(ev_id: str, as_of: str) -> tuple[str, str]:
    """解析规则引擎证据 ID → (source_table, field_path).

    形如 ev_bs_acct_rcv_20260331 → ("balance_sheet", "acct_rcv")。
    无法解析时返回 ("financial_statement", ev_id)。
    """
    if ev_id.startswith("ev_"):
        parts = ev_id.split("_")
        if len(parts) >= 3:
            table = _TABLE_CODE_MAP.get(parts[1], "financial_statement")
            if ev_id.endswith(f"_{as_of}"):
                field = "_".join(parts[2:-1])
            else:
                field = "_".join(parts[2:])
            if field:
                return table, field
    return "financial_statement", ev_id


def _dedup(items: list[str]) -> list[str]:
    """去重并保持原顺序（禁止 set() 导致顺序随机）。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _resolve_record(
    cache: dict, table: str, src_record_id: str
) -> tuple[dict, str | None]:
    """按 (table, src_record_id) 缓存 resolve_source 的报表记录。

    返回 (record, 实际报告期)——请求期可能晚于最新已披露报表，
    以记录中的 report_period 为准（None 表示未解析到记录）。
    """
    key = (table, src_record_id)
    if key not in cache:
        try:
            from app.application.services.source_resolver import resolve_source

            record = resolve_source(
                source_type="financial_statement",
                source_record_id=src_record_id,
                source_table=table,
            ).get("record", {})
        except Exception:  # noqa: BLE001 — 解析失败按无记录处理
            record = {}
        cache[key] = record
    record = cache[key]
    actual = record.get("report_period") if record else None
    return record, str(actual) if actual else None


def _field_value(
    cache: dict, table: str, src_record_id: str, field: str
) -> tuple[str | None, str | None]:
    """取证据字段的原始报表值（货币字段 unit=CNY）。

    无法解析或字段不存在 → (None, None)，不回退 explanation。
    """
    rec, _ = _resolve_record(cache, table, src_record_id)
    alias = _FIELD_ALIASES.get(field, field)
    if isinstance(alias, tuple):
        vals = [rec.get(a) for a in alias]
        if any(v is not None for v in vals):
            return ("|".join(str(v) for v in vals if v is not None), "CNY")
        return (None, "CNY")
    v = rec.get(alias)
    if v is None:
        return (None, None)
    return (str(v), "CNY")


_INTERP_MARKERS = ("【预警点】", "【数据对比】", "【可能模式】", "【限制说明】")


def _validate_interpretation(text: str, source_json: str) -> bool:
    """解读事实与格式验收：四段标记齐全 + 数值全部可溯源原文。

    任一不满足 → 拒绝（调用方回退 explanation），防止 LLM 输出
    缺段/编造数值（如新增 999%）被原样采用。

    数值提取前先移除规则 ID（正则 ``R\\d+``）——否则 R1 会贡献合法数字 1，
    使 LLM 编造的 "1%" 通过溯源校验。
    """
    if not all(m in text for m in _INTERP_MARKERS):
        return False
    import re

    def _nums(s: str) -> set[str]:
        # 先整体移除规则 ID（R1/R2…，含其数字），再移除其余字母序列，
        # 避免 R1 的数字 1 污染数值集合（编造 "1%" 会因此通过校验）
        cleaned = re.sub(r"R\d+", "", s)
        cleaned = re.sub(r"[A-Za-z]+", "", cleaned)
        return set(re.findall(r"-?\d+(?:\.\d+)?", cleaned))

    out_nums = _nums(text)
    src_nums = _nums(source_json)
    if not out_nums <= src_nums:
        return False
    return True


def _build_llm_interpretation(rule_details: dict, rule_statuses: dict) -> str:
    """Phase D #12: LLM 组织固定四段财务解读（预警点/数据对比/可能模式/限制说明）。

    数据来源：仅 rule_details 原文（rule_name/explanation/severity/current 数值）。
    LLM 失败/超时/无 key/输出未过验收（缺段/编造数值）→ 回退规则 explanation 串。
    """
    triggered = [
        rid
        for rid, st in rule_statuses.items()
        if st == "triggered" and rid in rule_details
    ]
    if not triggered:
        return ""

    # 构造仅含原文的数据摘要（数值原文透传，供 LLM 组织，禁止新增事实）
    detail_json = {
        rid: {
            "rule_name": rule_details[rid].get("rule_name", ""),
            "severity": rule_details[rid].get("severity", ""),
            "explanation": rule_details[rid].get("explanation", ""),
            "current": rule_details[rid].get("current", {}),
        }
        for rid in sorted(triggered)
    }

    source_json = f"规则触发结果（JSON，仅作数据来源，不得新增数值）：\n{detail_json}"
    messages = [
        {
            "role": "system",
            "content": (
                "你是财报反欺诈分析师。规则明细已单独列出（含全部数值），"
                "你的解读段不得重复罗列数值，聚焦因果解释与手法判断。"
                "输出固定四段，每段 1-2 句，总字数 350 字以内："
                "【预警点】这些指标异常说明什么；"
                "【数据对比】只说关键对比关系（一句话）；"
                "【可能模式】指向什么造假手法（不确定写'需进一步验证'）；"
                "【限制说明】数据口径限制。"
                "铁律：数值必须取自给定 JSON 原文，禁止新增任何未经给出的数据或事实；"
                "不要编造规则 ID、指标或数值。每段一行。"
            ),
        },
        {"role": "user", "content": source_json},
    ]

    try:
        from app.agents.llm_sync import run_llm_chat

        text = run_llm_chat(messages)
    except Exception:  # noqa: BLE001 — LLM 链路异常回退 explanation
        text = ""
    if not text or not _validate_interpretation(text, source_json):
        # 回退：规则 explanation 串（LLM 失败/无 key/输出未过验收时保持信息不丢失）
        parts = [
            str(rule_details[rid].get("explanation", "")).rstrip("。；; ")
            for rid in sorted(triggered)
            if rule_details[rid].get("explanation")
        ]
        return "【预警点】" + "；".join(parts) if parts else ""
    return text


def _resolve_as_of(state: AgentState) -> str:
    plan = state.get("plan")
    if plan is not None and plan.as_of:
        return plan.as_of.strftime("%Y%m%d")
    # 2026-08-16 口径整改：未传期次时从库内真实期次推导，禁止硬编码默认
    company = state.get("company")
    code = ""
    if company is not None:
        code = (
            getattr(company, "wind_code", "") or getattr(company, "entity_id", "") or ""
        )
    if code:
        try:
            from app.domain.finance.data_as_of import resolve_company_data_as_of

            derived = resolve_company_data_as_of(code)
            if derived:
                return derived
        except Exception:  # noqa: BLE001 — 推导失败如实返回空串
            pass
    return ""


def finance_node(state: AgentState) -> dict:
    company = state.get("company")
    plan = state.get("plan")

    # 未选中 → no-op（plan 缺失时保守执行）
    if plan is not None and "finance" not in plan.requested_modules:
        return {
            "module_status": {"finance": ModuleStatus(state="skipped")},
            "results": ModuleResults(finance=None),
        }

    if company is None:
        return {
            "module_status": {"finance": ModuleStatus(state="skipped")},
            "results": ModuleResults(finance=None),
        }

    code = company.wind_code or company.entity_id
    as_of = _resolve_as_of(state)

    # 模块耗时采集（duration_ms → module_status，供评测指标 6 与前端状态展示）
    from time import perf_counter

    _module_start = perf_counter()

    try:
        from app.domain.finance.rule_engine import evaluate_all_rules

        results = evaluate_all_rules(code, as_of)
    except Exception as e:  # noqa: BLE001 — 规则引擎异常降级，不伪造结果
        # 必须 dict 包装（与 risk/equity/events 一致）：module_status reducer
        # 是 {**a, **b}，裸 ModuleStatus 会让合并抛 TypeError 导致 graph 崩溃
        return {
            "module_status": {
                "finance": ModuleStatus(
                    state="failed",
                    error_code="RULE_ENGINE_ERROR",
                    recoverable=True,
                    duration_ms=round((perf_counter() - _module_start) * 1000),
                )
            },
            "results": ModuleResults(
                finance=FinanceResult(
                    rule_statuses={},
                    warnings=[f"财务规则引擎执行失败，财务模块降级: {e}"],
                    evidence=[],
                )
            ),
        }

    rule_statuses: dict[str, str] = {}
    rules_list: list = []
    rule_details: dict[str, dict] = {}
    warnings: list[str] = []
    evidence: list[EvidenceRef] = []
    unknown_type = False
    runtime = state.get("runtime")
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    from app.core.config import settings as _settings
    from app.application.services.finance_evidence import (
        normalize_rule_evidence_id,
    )

    record_cache: dict = {}
    for rid in _RULES:
        r = results.get(rid)
        if r is None:
            continue
        rule_statuses[rid] = r.status
        rules_list.append(r)
        # 规则明细（含触发解释/严重度/指标数值/本规则证据 ID/quality，
        # 供回答展开规则清单 + build_claims 按规则归属绑定证据；
        # quality 透传简化模式/字段可用性，#1/#2 Claim 文案与严重度同源）
        rule_details[rid] = {
            "rule_name": r.rule_name or "",
            "explanation": str(r.explanation or ""),
            "severity": r.severity or "",
            "current": dict(getattr(r, "current", None) or {}),
            "evidence_ids": [],
            "quality": dict(r.quality or {}),
            "calculation_trace": (
                r.calculation_trace.model_dump(mode="json")
                if getattr(r, "calculation_trace", None) is not None
                else None
            ),
        }
        if r.status == "insufficient_data" and W_COMPANY_TYPE_UNKNOWN in r.warnings:
            unknown_type = True
        for w in r.warnings:
            if w:
                warnings.append(w)
        generated_ids: list[str] = []
        trace = getattr(r, "calculation_trace", None)
        if trace is not None and trace.inputs:
            for item in trace.inputs:
                period = str(item.period)
                evidence_id = normalize_rule_evidence_id(
                    item.field_path,
                    code,
                    as_of,
                    period=period,
                )
                generated_ids.append(evidence_id)
                evidence.append(
                    EvidenceRef(
                        evidence_id=evidence_id,
                        source_type="financial_statement",
                        source_record_id=f"{code}|{period}",
                        source_table=item.source_table,
                        field_path=item.field_path,
                        period=period,
                        value=str(item.value),
                        unit=item.unit,
                        source_title=(
                            f"{r.rule_name or rid} · {display_period(period)} · 母公司报表"
                        ),
                        source_excerpt=(
                            f"{item.source_table}.{item.field_path}="
                            f"{item.value} {item.unit}"
                        ),
                        statement_scope="parent_company",
                        module="finance",
                        rule_id=rid,
                        turn_id=turn_id,
                        trace_id=trace_id,
                        company_code=code,
                        dataset_version=_settings.DATASET_VERSION,
                    )
                )
            rule_details[rid]["evidence_ids"] = _dedup(generated_ids)
            continue

        # 兼容尚未提供 calculation_trace 的旧规则/测试桩。
        for ev_id in r.evidence_ids:
            table, field = _parse_rule_evidence(ev_id, as_of)
            req_src = f"{code}|{as_of}|{PARENT_STATEMENT_TYPE}"
            # 真实报告期：请求期可能晚于最新已披露报表（如 20260331 → 20251231），
            # 以 resolve 返回的实际期间为准（无记录时回退请求期）
            record, actual_period = _resolve_record(record_cache, table, req_src)
            period = actual_period or as_of
            # 8/23 双轨 ID 统一：与 /finance 路由同一 canonical normalize
            # （两段式 source_record_id + 无 rule_id 段——同一字段跨规则共享
            # 同一 Evidence 只落库一次）；落库 source_record_id 同步两段式，
            # 修复画像页 /risk 返回 ev_fin_* 在 evidence_refs 查不到的问题。
            src_record_id = f"{code}|{period}"
            evidence_id = normalize_rule_evidence_id(ev_id, code, as_of, period=period)
            generated_ids.append(evidence_id)
            value, unit = _field_value(record_cache, table, req_src, field)
            evidence.append(
                EvidenceRef(
                    evidence_id=evidence_id,
                    source_type="financial_statement",
                    source_record_id=src_record_id,
                    source_table=table,
                    field_path=field,
                    period=period,
                    value=value,
                    unit=unit,
                    # 来源标题可读性（演示整改）：规则中文名 + 期次 + 口径
                    # （保留"母公司报表"字样：test_parent_scope_consistency 断言）
                    source_title=(
                        f"{r.rule_name or rid} · {display_period(period)} · 母公司报表"
                    ),
                    source_excerpt=(
                        f"{table}.{field}={value} {unit or ''}"
                        if value is not None
                        else None
                    ),
                    statement_scope="parent_company",
                    module="finance",
                    rule_id=rid,
                    turn_id=turn_id,
                    trace_id=trace_id,
                    company_code=code,
                    dataset_version=_settings.DATASET_VERSION,
                )
            )
        rule_details[rid]["evidence_ids"] = _dedup(generated_ids)

    # 相似指标案例（任务①）：仅对触发规则调用 Provider，metric_value 来自
    # RuleResult.current（不内部自算）；comp_type 非 1 → not_supported；
    # Provider 异常 → error（compute_similar_cases 内部捕获，不抛出不阻塞）。
    triggered_rids = [rid for rid in _RULES if rule_statuses.get(rid) == "triggered"]
    if triggered_rids:
        try:
            comp_type = parent_scope.fetch_company_field(code, "comp_type_code")
            industry_l1 = parent_scope.fetch_company_field(code, "industry_l1")
        except Exception:  # noqa: BLE001 — 公司字段读取失败不阻塞财务分析
            comp_type = None
            industry_l1 = None
        provider = get_similar_case_provider()
        for rid in triggered_rids:
            r = results.get(rid)
            current = dict(getattr(r, "current", None) or {})
            sc_result = compute_similar_cases(
                provider,
                rule_id=rid,
                company_code=code,
                current=current,
                industry=industry_l1,
                as_of=as_of,
                comp_type_code=comp_type,
            )
            rule_details[rid]["similar_cases"] = sc_result.model_dump(mode="json")

    # 统一口径说明恰好一次（规则实际执行时才有意义）
    if rule_statuses:
        warnings.insert(0, SCOPE_NOTE)
    # 规则级去重（保持顺序）
    warnings = _dedup(warnings)

    if not rule_statuses:
        status = "failed"
        warnings.append("财务规则引擎未返回任何结果")
    elif any(s == "triggered" for s in rule_statuses.values()):
        status = "success"
    elif unknown_type:
        # 公司类型未知 → 数据不足，不得标记 success / 输出"未发现风险"
        status = "partial"
        warnings.append("公司类型缺失，无法判断是否适用非金融财务规则，规则未执行")
    elif all(
        s in ("insufficient_data", "not_applicable") for s in rule_statuses.values()
    ):
        status = "partial"
        warnings.append(
            "财务规则因数据不足/不适用未产出有效信号（statement_scope/coverage 见各规则 quality）"
        )
    else:
        status = "success"

    # periods_available：真实母公司财务期数（B1 验收）
    periods_available = _query_periods_available(code, as_of)
    industry_benchmark = _query_industry_benchmark(code, as_of)

    # #7：财务解读不再由 LLM 自由生成——四段解读在 generate_answer 基于
    # 最终状态确定性构造（预警点/数据对比/可能模式/限制说明/重要说明）。
    # interpretation 字段保留兼容（外部消费方不受影响），值恒为空。
    interpretation = ""

    return {
        "module_status": {
            "finance": ModuleStatus(
                state=status, duration_ms=round((perf_counter() - _module_start) * 1000)
            )
        },
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses=rule_statuses,
                rules=rules_list,
                periods_available=periods_available,
                industry_benchmark=industry_benchmark,
                rule_details=rule_details,
                interpretation=interpretation,
                warnings=warnings,
                evidence=evidence,
            )
        ),
    }


def _query_periods_available(company_code: str, as_of: str) -> int:
    """真实可用母公司财务期数。"""
    try:
        from app.domain.finance._fetch import _get_engine
        from sqlalchemy import text

        engine = _get_engine()
        with engine.connect() as conn:
            n = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT report_period) FROM balance_sheet "
                    "WHERE wind_code = :c AND statement_type = :stmt "
                    "AND report_period <= :asof"
                ),
                {"c": company_code, "stmt": "408006000", "asof": as_of},
            ).scalar()
        return int(n or 0)
    except Exception:  # noqa: BLE001
        return 0


def _query_industry_benchmark(company_code: str, as_of: str) -> dict:
    """行业分位（行业已知时实时计算公司百分位）。"""
    try:
        from app.domain.benchmarks.calculator import (
            MIN_PEER_SAMPLE,
            compute_metric_values,
            percentile_rank,
        )
        from app.domain.benchmarks.metric_registry import get_metric
        from app.domain.finance._fetch import _get_engine, fetch_company_field

        industry = fetch_company_field(company_code, "industry_l1")
        if not industry:
            return {
                "industry_l1": "",
                "percentiles": {},
                "warnings": ["INDUSTRY_UNKNOWN"],
            }
        engine = _get_engine()
        percentiles = {}
        for metric_id in (
            "r1_gap",
            "r2_cf_ratio",
            "r3_cash_to_assets",
            "r4_growth_gap",
            "r6_oth_rcv_to_assets",
        ):
            try:
                metric = get_metric(metric_id)
                pairs = compute_metric_values(engine, metric, industry, as_of)
                values = [v for _, v in pairs]
                company_value = next((v for c, v in pairs if c == company_code), None)
                if len(values) >= MIN_PEER_SAMPLE and company_value is not None:
                    percentiles[metric_id] = percentile_rank(company_value, values)
            except Exception:  # noqa: BLE001
                continue
        return {
            "industry_l1": industry,
            "percentiles": percentiles,
            "warnings": ["行业分位样本不足"] if not percentiles else [],
        }
    except Exception:  # noqa: BLE001
        return {"industry_l1": "", "percentiles": {}, "warnings": []}
