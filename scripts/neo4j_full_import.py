#!/usr/bin/env python
"""TruthNet — Neo4j 全量股权图谱构建 (Phase B Task 2, 集成版).

设计原则：
  - 默认幂等增量写入（不删除已有数据）
  - --replace-graph-version 为显式危险操作
  - 实体节点是稳定实体（graph_version 记录创建版本，不覆盖）
  - 关系节点通过 relationship_id 保留历史快照
  - 统一使用 normalizer 的 Wind Code / entity_id 方法
  - 一致行动人检测按 wind_code + report_period + sequence 分组
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
_backend_root = _repo_root / "backend"
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.app.core.config import settings  # noqa: E402
from backend.app.infrastructure.graph.neo4j.equity_graph import (  # noqa: E402
    Neo4jEquityGraph,
    make_relationship_id,
)
from backend.app.infrastructure.graph.normalizer import (  # noqa: E402
    make_listed_company_entity_id,
    normalize_wind_code,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 实体对齐
# ═══════════════════════════════════════════════════════════


def _normalize_report_period(value, fallback) -> str:
    """规范化报告期为 YYYYMMDD（真实日期校验）。

    - date/datetime/Timestamp → strftime("%Y%m%d")
    - 整数及整数浮点（20251231.0）→ int
    - 字符串清理 .0 / - / /
    - 最终用 datetime.strptime 校验真实日期（拒绝 20250229/20251301）
    无效回退 fallback；两者无效返回 ""（调用方跳过该关系）。
    """
    from datetime import datetime

    for v in (value, fallback):
        if v is None or pd.isna(v):
            continue
        s = ""
        if isinstance(v, (datetime,)):
            s = v.strftime("%Y%m%d")
        elif isinstance(v, (int, float)):
            s = str(int(v)) if float(v) == int(v) else ""
        else:
            s = str(v).strip().replace(".0", "").replace("-", "").replace("/", "")
        if not s or not s.isdigit() or len(s) != 8:
            continue
        try:
            datetime.strptime(s, "%Y%m%d")
            return s
        except ValueError:
            continue  # 非法日期（如 20250229）
    return ""


def build_holder_to_listed_mapping() -> dict[str, tuple[str, str]]:
    """股东名 → 上市公司 (wind_code, listed_entity_id) 归一化映射（P0-2）。

    来源：MySQL companies 表（is_latest=1，sec_name 已由 security_master
    审计修复）。规则：归一化后唯一精确匹配才映射；同名多 code（异常）
    不进入映射（ambiguous 报告在调用方输出）。
    """
    from sqlalchemy import create_engine, text

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT wind_code, sec_name FROM companies "
                    "WHERE is_latest = 1 AND sec_name IS NOT NULL "
                    "AND TRIM(sec_name) != ''"
                )
            ).fetchall()
    finally:
        engine.dispose()

    by_name: dict[str, list[str]] = {}
    for wc, name in rows:
        norm = normalize_entity_name(str(name))
        if not norm:
            continue
        by_name.setdefault(norm, []).append(str(wc))

    mapping: dict[str, tuple[str, str]] = {}
    ambiguous: list[tuple[str, list[str]]] = []
    skipped: list[str] = []
    for norm, codes in by_name.items():
        if len(codes) == 1:
            wc = codes[0]
            try:
                mapping[norm] = (wc, make_listed_company_entity_id(wc))
            except ValueError:  # 异常代码（如 A23140.SZ）不进入映射
                skipped.append(wc)
        else:
            ambiguous.append((norm, codes))
    if skipped:
        logger.warning("无法解析的代码（跳过映射）: %s", skipped[:10])
    logger.info(
        "股东归一化映射: 唯一匹配 %d 家, 同名多 code %d 组",
        len(mapping),
        len(ambiguous),
    )
    if ambiguous:
        logger.warning("归一化同名冲突（不自动连边）: %s", ambiguous[:10])
    return mapping


# 公司后缀剥离（P0-2 归一化）：股东名常为全称（"中信证券股份有限公司"），
# 上市公司 sec_name 为简称（"中信证券"）；剥离后缀后两端才能唯一精确匹配。
_COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "集团有限公司",
    "控股集团有限公司",
    "有限公司",
    "控股有限公司",
    "（集团）股份有限公司",
)


def normalize_entity_name(name: str) -> str:
    """标准化实体名称（NFKC + 全角→半角 + 去空白 + 剥离公司后缀）."""
    import unicodedata

    if not name or pd.isna(name):
        return ""
    name = str(name)
    name = unicodedata.normalize("NFKC", name)
    # 全角转半角
    result = []
    for ch in name:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(" ")
        else:
            result.append(ch)
    s = "".join(result).strip()
    # 剥离公司后缀（先长后短，避免"股份有限"残留）
    for suf in _COMPANY_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
            break
    return s


def build_entity_id(
    name: str,
    wind_code: str | None = None,
    holder_category: int | None = None,
) -> str:
    """为股东实体生成稳定 entity_id。

    上市公司: company_{code}_{exchange}
    个人股东: person_{name_hash}
    企业股东: corp_{name_hash}
    """
    if wind_code:
        return make_listed_company_entity_id(wind_code)

    name_hash = hashlib.sha256(name.encode()).hexdigest()[:12]
    if holder_category == 1:
        return f"person_{name_hash}"
    else:
        return f"corp_{name_hash}"


# ═══════════════════════════════════════════════════════════
# 一致行动人检测
# ═══════════════════════════════════════════════════════════


def detect_concerted_parties(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """检测一致行动人。

    按 (wind_code, report_period, sequence) 分组，
    同组多个股东的持股比例合并。

    s_holder_sequence 的语义需验证；仅在 sequence 有明确
    一致行动含义时才合并。
    """
    groups = []
    for (wind_code, period, seq), group in df.groupby(
        ["wind_code", "report_period", "s_holder_sequence"]
    ):
        if seq is None or pd.isna(seq) or len(group) <= 1:
            continue

        names = group["s_holder_aname"].fillna(group["s_holder_name"]).tolist()
        total_pct = group["s_holder_pct"].sum()

        groups.append(
            {
                "wind_code": normalize_wind_code(str(wind_code)),
                "report_period": str(period),
                "sequence": int(seq),
                "members": [normalize_entity_name(n) for n in names],
                "combined_pct": float(total_pct),
                "confidence": 0.7,  # heuristic, not confirmed
                "method": "sequence_grouping",
            }
        )

    return groups


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Neo4j 全量股权图谱构建")

    p.add_argument("--data-file", required=True, help="十大股东 Excel/CSV 路径")
    p.add_argument("--graph-version", default=settings.GRAPH_VERSION)
    p.add_argument("--dataset-version", default=settings.DATASET_VERSION)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mock", action="store_true", help="标记为 mock 数据")
    p.add_argument(
        "--replace-graph-version",
        action="store_true",
        help="[!]危险：替换指定 graph_version 的全部关系（保留实体节点）",
    )
    p.add_argument(
        "--concerted-only",
        action="store_true",
        help="仅运行一致行动人检测并输出 CSV",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # P0-2：dry-run 与替换互斥（dry-run 只解析统计，禁止任何写操作）
    if args.dry_run and args.replace_graph_version:
        logger.error("[!]--dry-run 与 --replace-graph-version 互斥，不能同时使用")
        return 1

    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error("数据文件不存在: %s", data_path)
        return 1

    # 读取数据
    if data_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, low_memory=False)

    logger.info("读取 %d 条股东记录", len(df))

    # 仅一致行动人检测模式
    if args.concerted_only:
        concerted = detect_concerted_parties(df)
        out_path = data_path.parent / "concerted_parties.csv"
        pd.DataFrame(concerted).to_csv(out_path, index=False)
        logger.info("一致行动人: %d 组 → %s", len(concerted), out_path)
        return 0

    # 初始化 Neo4j adapter
    adapter = Neo4jEquityGraph()
    if not adapter._driver:
        logger.error("Neo4j 连接不可用，请检查 NEO4J_URI 配置")
        return 2

    import asyncio

    async def _run():
        await adapter.check_connection()
        await adapter.ensure_constraints()

        # 替换模式（P0-2 防误删保护）：**导入前不清理旧图**。
        # 旧关系在导入+验收全部成功后按 seen_run_id 删除（delete_stale_relationships），
        # 失败时本次新建被 delete_relationships_by_run 清理（防误删保护；
        # 被 MERGE 覆盖的旧属性不回滚）。
        if args.replace_graph_version:
            logger.warning(
                "[!]替换模式：导入并验收成功后删除 graph_version=%s 的旧关系",
                args.graph_version,
            )

        # 股东名 → 上市公司归一化映射（P0-2：股东身份与上市公司身份打通）
        holder_mapping = build_holder_to_listed_mapping()

        datetime.now(timezone.utc).isoformat()

        # Step 1: 构建实体节点
        entities: dict[str, dict] = {}
        for _, row in df.iterrows():
            wind_code = str(row.get("s_info_windcode", ""))
            try:
                normalized_code = normalize_wind_code(wind_code)
            except ValueError:
                continue

            # 上市公司实体
            listed_entity_id = make_listed_company_entity_id(normalized_code)
            if listed_entity_id not in entities:
                entities[listed_entity_id] = {
                    "entity_id": listed_entity_id,
                    "canonical_name": normalize_entity_name(wind_code),
                    "display_name": normalize_entity_name(wind_code),
                    "entity_type": "ListedCompany",
                    "wind_code": normalized_code,
                    "aliases": [],
                    "match_confidence": 1.0,
                    "source_id": str(uuid.uuid4()),
                }

            # 股东实体
            holder_name = str(row.get("s_holder_aname") or row.get("s_holder_name", ""))
            holder_name = normalize_entity_name(holder_name)
            if not holder_name:
                continue

            holder_category = int(row.get("s_holder_holdercategory", 0) or 0)
            # P0-2：归一化命中上市公司的股东不建 corp_* 节点
            # （身份统一为 company_*，避免无关系孤立 corp_* 反复出现）
            if holder_mapping.get(holder_name) is not None:
                continue

            holder_entity_id = build_entity_id(
                holder_name, holder_category=holder_category
            )

            if holder_entity_id not in entities:
                entity_type = "Person" if holder_category == 1 else "Company"
                # [!]特殊实体类型校正
                if any(
                    kw in holder_name
                    for kw in ["国资委", "财政局", "人民政府", "国有资产"]
                ):
                    entity_type = "Government"

                entities[holder_entity_id] = {
                    "entity_id": holder_entity_id,
                    "canonical_name": holder_name,
                    "display_name": holder_name,
                    "entity_type": entity_type,
                    "wind_code": "",
                    "aliases": [],
                    "match_confidence": 0.9,
                    "source_id": str(uuid.uuid4()),
                }

        logger.info(f"去重后实体: {len(entities)}")

        # Step 2: 导入实体
        if not args.dry_run:
            n_entities = await adapter.import_entities_batch(
                list(entities.values()),
                graph_version=args.graph_version,
                mock=args.mock,
            )
            logger.info("导入实体: %d", n_entities)

        # Step 3: 构建关系
        relationships: list[dict] = []
        # (index, wind_code, report_period) 记录，用于快照级 is_latest（R6）
        rel_period_meta: list[tuple[int, str, str]] = []
        matched_holders = 0
        skipped_self_loops = 0
        skipped_bad_periods = 0
        for _, row in df.iterrows():
            wind_code = str(row.get("s_info_windcode", ""))
            try:
                normalized_code = normalize_wind_code(wind_code)
            except ValueError:
                continue

            holder_name = normalize_entity_name(
                str(row.get("s_holder_aname") or row.get("s_holder_name", ""))
            )
            if not holder_name:
                continue

            holder_category = int(row.get("s_holder_holdercategory", 0) or 0)
            # P0-2：股东本身是上市公司时，边 source 直接用 company_* 身份
            # （归一化唯一精确匹配），不再新建 corp_* 身份节点。
            mapped = holder_mapping.get(holder_name)
            if mapped is not None:
                src_id = mapped[1]
                matched_holders += 1
            else:
                src_id = build_entity_id(holder_name, holder_category=holder_category)
            tgt_id = make_listed_company_entity_id(normalized_code)

            # 自环防护：股东归一化后与目标公司同一实体（公司持有自身）→ 跳过
            if src_id == tgt_id:
                skipped_self_loops += 1
                continue

            pct = float(row.get("s_holder_pct", 0) or 0)
            # 期次规范化（P0-1）：真实日期校验，主期次无效回退 s_holder_enddate，
            # 两者无效跳过该关系（"nan"/非法日期不进入 is_latest 比较）
            report_period = _normalize_report_period(
                row.get("report_period"), row.get("s_holder_enddate")
            )
            if not report_period:
                skipped_bad_periods += 1
                continue
            ann_dt = str(row.get("ann_dt", ""))

            # 使用稳定行标识符（非随机 UUID）确保重复导入幂等
            row_key = f"{normalized_code}|{holder_name}|{report_period}|{ann_dt}"
            stable_row_id = hashlib.sha256(row_key.encode()).hexdigest()[:16]

            rel_id = make_relationship_id(
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                relation_type="OWNS",
                report_period=report_period,
                ann_dt=ann_dt,
                source_record_id=stable_row_id,
            )

            relationships.append(
                {
                    "source_entity_id": src_id,
                    "target_entity_id": tgt_id,
                    "relation_type": "OWNS",
                    "ownership_pct": pct,
                    "quantity": float(row.get("s_holder_quantity", 0) or 0),
                    "ann_dt": ann_dt,
                    "report_period": report_period,
                    "source_id": rel_id,
                    "source_record_id": rel_id,
                    "match_confidence": 0.9,
                    # R6：快照级 is_latest 在下方统一计算（先占位 True）
                    "is_latest": True,
                }
            )
            rel_period_meta.append(
                (len(relationships) - 1, normalized_code, report_period)
            )

        # R6：快照级 is_latest——每个目标公司的"最新完整股东快照"全边 True，
        # 更早快照全 False（不是按 (code, holder) 取最大期，已退出前十大的
        # 旧股东记录不会被误标为最新）。
        latest_period: dict[str, str] = {}
        for _, code, period in rel_period_meta:
            if period > latest_period.get(code, ""):
                latest_period[code] = period
        for idx, code, period in rel_period_meta:
            relationships[idx]["is_latest"] = period == latest_period[code]

        # P0-2（核验修订）：按 relationship_id 全局去重——RETURN count(r) 对
        # 重复输入行重复计数，去重后 imported 才是真实唯一关系数。
        # 同 ID 载荷不一致（pct/quantity/is_latest 不同）→ 显式报告并采用
        # 最后一条（与 MERGE SET 后写覆盖语义一致），不静默丢弃；
        # 真实数据实测 134/64 万 ≈ 0.02%，失败关闭会阻断整个导入。
        dedup_map: dict[str, dict] = {}
        dup_rows = 0
        conflict_rows = 0
        conflict_samples: list[str] = []
        for rel in relationships:
            rid = str(rel["source_id"])
            prev = dedup_map.get(rid)
            if prev is None:
                dedup_map[rid] = rel
                continue
            dup_rows += 1
            diff = [
                f
                for f in ("ownership_pct", "quantity", "is_latest")
                if prev.get(f) != rel.get(f)
            ]
            if diff:
                conflict_rows += 1
                if len(conflict_samples) < 10:
                    conflict_samples.append(
                        f"{rid}: {','.join(diff)} "
                        f"({prev.get('ownership_pct')!r} → {rel.get('ownership_pct')!r})"
                    )
            dedup_map[rid] = rel  # 后写覆盖（与 MERGE SET 一致）
        if conflict_rows:
            logger.warning(
                "关系载荷冲突 %d 条（同 relationship_id 不同数据，采用最后一条）:",
                conflict_rows,
            )
            for s in conflict_samples:
                logger.warning("  冲突 %s", s)
        if dup_rows:
            logger.warning("重复 relationship_id %d 条（载荷一致，已去重）", dup_rows)
        relationships = list(dedup_map.values())

        logger.info(
            "关系总数: %d（股东归一化匹配上市公司 %d 条，跳过自环 %d 条，"
            "跳过非法期次 %d 条，去重 %d 条）",
            len(relationships),
            matched_holders,
            skipped_self_loops,
            skipped_bad_periods,
            dup_rows,
        )

        # Step 4: 导入关系（P0-2 防误删保护：导入前不清理旧图；
        # 失败只删本次新建，replace 模式验收成功后删旧图——
        # 注意：被 MERGE 覆盖的旧关系属性不会回滚，非完整事务）
        if not args.dry_run:
            run_id = uuid.uuid4().hex[:12]
            try:
                result = await adapter.import_relationships_batch(
                    relationships,
                    graph_version=args.graph_version,
                    mock=args.mock,
                    import_run_id=run_id,
                )
                logger.info(
                    "导入关系: %d/%d (run_id=%s)",
                    result["imported"],
                    result["total"],
                    run_id,
                )

                # Step 5: 仅显式替换（--replace-graph-version）才删旧图：
                #   中间验收限定 seen_run_id=本次（核验修订：不得混合旧图关系）
                #   → 通过后才删除 stale 旧关系 → 清理孤儿节点
                # 普通幂等增量导入不删任何关系，仅清除本次 seen 标记。
                if args.replace_graph_version:
                    if adapter._driver:
                        depth3 = await adapter.count_multi_hop_paths(
                            args.graph_version, min_depth=3, import_run_id=run_id
                        )
                        logger.info(
                            "多跳链路中间验收: 本次关系 depth≥3 路径 %d 条", depth3
                        )
                        if depth3 <= 0:
                            raise RuntimeError(
                                "中间验收失败: 本次导入关系 depth≥3 路径为 0，取消替换旧图"
                            )
                    await adapter.delete_stale_relationships(args.graph_version, run_id)
                    await adapter.cleanup_orphan_corporate_nodes()
                else:
                    await adapter.clear_run_markers(run_id)
            except Exception as e:  # noqa: BLE001 — 失败清理本次新增，旧图保留
                logger.error("导入失败，清理本次新增数据: %s", e)
                try:
                    await adapter.delete_relationships_by_run(run_id)
                except Exception as ce:  # noqa: BLE001
                    logger.error("失败清理异常: %s", ce)
                return 1

        # Step 6: 最终验证（replace 模式：删旧后全图最终验收，不得假阳性）
        n_entities_neo = await adapter.count_entities(args.graph_version)
        n_rels_neo = await adapter.count_relationships(args.graph_version)
        logger.info(
            "Neo4j 验证: 实体=%d, 关系=%d (graph_version=%s)",
            n_entities_neo,
            n_rels_neo,
            args.graph_version,
        )
        if not args.dry_run and args.replace_graph_version and adapter._driver:
            final_depth3 = await adapter.count_multi_hop_paths(
                args.graph_version, min_depth=3
            )
            logger.info("最终验收: 删旧后全图 depth≥3 路径 %d 条", final_depth3)
            if final_depth3 <= 0:
                logger.error("最终验收失败: 删除旧图后 depth≥3 路径为 0，数据异常")
                return 1

        return 0

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
