"""全球金融舆情脉搏 — Market Pulse.

聚合多个免费公开 RSS 源（CNBC / WSJ / MarketWatch / 华尔街见闻 / 36氪 / BBC），
为前端「旋转地球舆情监控」提供数据：每条资讯映射到国家坐标并按国家聚合成
热点强度（intensity），热点国家在球面上亮起更强的点。

数据策略（2026-08-25 定稿，为评委演示优化）：
- 保留 24h 内存量（当天全量），不再做 10 分钟窗口过滤——演示时永远有数据；
- 缓存 10 分钟（前端每 10 分钟轮询一次即可）；
- 按国家聚合 clusters：count / severity 分布 / intensity(0-1) / 最新标题，
  前端点大小与亮度 ∝ intensity（「中国 A 股多条 → 中国区点亮得狠」）。

数据流：RSS(httpx) → xml.etree 解析 → 10min 进程内缓存 → /api/v1/market-pulse
单源失败自动跳过并降级为 warning，不影响整体可用性。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# 严重度关键词规则（命中即定级，critical 优先于 warning）
_SEVERITY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "critical",
        (
            "fraud", "scandal", "probe", "investigation", "indict", "sue",
            "lawsuit", "bankrupt", "collapse", "crash", "plunge", "downgrade",
            "recall", "layoff", "违约", "爆雷", "退市", "造假", "欺诈", "调查", "诉讼", "破产", "崩盘", "暴跌", "裁员",
        ),
    ),
    (
        "warning",
        (
            "warning", "risk", "fall", "drop", "decline", "slump", "loss",
            "misses", "cuts", "halt", "probe", "tension", "tariff", "下跌", "预警", "风险", "亏损", "下滑", "停牌", "关税", "紧张",
        ),
    ),
)


def _infer_severity(title: str) -> str:
    """按标题关键词推断严重度：critical > warning > info。"""
    lowered = title.lower()
    for level, keywords in _SEVERITY_RULES:
        if any(kw in lowered for kw in keywords):
            return level
    return "info"


@dataclass(frozen=True)
class PulseSource:
    """一个 RSS 监控源及其地理归属。"""

    key: str
    name: str
    url: str
    region_code: str
    country: str
    lat: float
    lng: float


# 覆盖四大金融区域：美国（东西海岸）、中国（沪深港）、欧洲（伦敦/法兰克福）、亚洲市场
_SOURCES: tuple[PulseSource, ...] = (
    PulseSource(
        key="cnbc-top",
        name="CNBC 要闻",
        url="https://www.cnbc.com/id/100003114/device/rss/rss.html",
        region_code="US",
        country="美国",
        lat=40.71,
        lng=-74.01,
    ),
    PulseSource(
        key="mw-top",
        name="MarketWatch 头条",
        url="https://feeds.content.dowjones.io/public/rss/mw_topstories",
        region_code="US",
        country="美国",
        lat=41.88,
        lng=-87.63,
    ),
    PulseSource(
        key="wsj-markets",
        name="WSJ 市场",
        url="https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        region_code="US",
        country="美国",
        lat=37.77,
        lng=-122.42,
    ),
    PulseSource(
        key="wscn",
        name="华尔街见闻",
        url="https://dedicated.wallstreetcn.com/rss.xml",
        region_code="CN",
        country="中国",
        lat=31.23,
        lng=121.47,
    ),
    PulseSource(
        key="36kr",
        name="36氪",
        url="https://36kr.com/feed",
        region_code="CN",
        country="中国",
        lat=39.90,
        lng=116.41,
    ),
    PulseSource(
        key="cnbc-asia",
        name="CNBC 亚洲市场",
        url="https://www.cnbc.com/id/15837362/device/rss/rss.html",
        region_code="ASIA",
        country="中国香港",
        lat=22.32,
        lng=114.17,
    ),
    PulseSource(
        key="cnbc-europe",
        name="CNBC 欧洲",
        url="https://www.cnbc.com/id/19794221/device/rss/rss.html",
        region_code="EU",
        country="欧洲",
        lat=50.11,
        lng=8.68,
    ),
    PulseSource(
        key="bbc-biz",
        name="BBC 商业",
        url="https://www.bbc.co.uk/news/business/rss.xml",
        region_code="EU",
        country="英国",
        lat=51.51,
        lng=-0.13,
    ),
)

_PER_SOURCE_LIMIT = 15  # 当天全量：单源最多收 15 条
_FETCH_TIMEOUT = 8.0
_CACHE_TTL = 600.0  # 10 分钟更新一次（对齐前端轮询节奏）
_ITEM_WINDOW = timedelta(hours=24)  # 保留一天存量
# 国家聚合强度：intensity = 0.25 + 0.75 * count / _INTENSITY_SAT
_INTENSITY_SAT = 12.0
_SEV_RANK = {"info": 1, "warning": 2, "critical": 3}

_cache: dict[str, Any] = {"ts": 0.0, "payload": None, "ok_sources": 0}
_lock = asyncio.Lock()


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_feed(xml_text: str, source: PulseSource) -> list[dict[str, Any]]:
    """解析 RSS 2.0 / Atom，返回前 N 条条目 dict。"""
    root = ET.fromstring(xml_text)
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []

    # RSS 2.0：<channel><item>
    entries = root.findall("./channel/item")
    if not entries:
        # Atom：<feed><entry>
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for entry in entries[: _PER_SOURCE_LIMIT + 2]:
        title = link = pub_date = None
        for child in entry:
            tag = _strip_ns(child.tag)
            if tag == "title" and title is None:
                title = (child.text or "").strip()
            elif tag == "link" and link is None:
                link = (child.get("href") or child.text or "").strip()
            elif tag == "pubDate" and pub_date is None:
                try:
                    pub_date = parsedate_to_datetime((child.text or "").strip())
                except (TypeError, ValueError):
                    pub_date = None
            elif tag == "published" and pub_date is None:  # Atom
                try:
                    pub_date = datetime.fromisoformat(
                        (child.text or "").strip().replace("Z", "+00:00")
                    )
                except ValueError:
                    pub_date = None

        if not title or not link:
            continue

        if pub_date is None:
            pub_date = now
        elif pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)

        # 国家聚合模式：坐标即源锚点（一个国家一个亮点，无需散布防重叠）
        digest = hashlib.md5(link.encode("utf-8")).hexdigest()[:12]
        items.append(
            {
                "id": f"mp_{digest}",
                "title": title,
                "url": link,
                "source_name": source.name,
                "region_code": source.region_code,
                "country": source.country,
                "lat": source.lat,
                "lng": source.lng,
                "published_at": pub_date,
                "severity": _infer_severity(title),
            }
        )
        if len(items) >= _PER_SOURCE_LIMIT:
            break
    return items


async def _fetch_one(client: httpx.AsyncClient, source: PulseSource) -> list[dict[str, Any]]:
    try:
        resp = await client.get(source.url, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        return _parse_feed(resp.text, source)
    except Exception as exc:  # noqa: BLE001 — 单源失败必须降级
        logger.warning("market-pulse 源 %s 拉取失败: %s", source.key, exc)
        return []


def _build_clusters(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按国家聚合：count 驱动 intensity（点大小/亮度），severity 取最高级。"""
    clusters: dict[str, dict[str, Any]] = {}
    for it in items:
        c = clusters.setdefault(
            it["country"],
            {
                "country": it["country"],
                "region_code": it["region_code"],
                "lat": it["lat"],
                "lng": it["lng"],
                "count": 0,
                "critical": 0,
                "warning": 0,
                "info": 0,
                "top_severity": "info",
                "top_title": it["title"],
                "latest_published_at": it["published_at"],
            },
        )
        c["count"] += 1
        c[it["severity"]] += 1
        if _SEV_RANK[it["severity"]] > _SEV_RANK[c["top_severity"]]:
            c["top_severity"] = it["severity"]
        if it["published_at"] > c["latest_published_at"]:
            c["latest_published_at"] = it["published_at"]
            c["top_title"] = it["title"]

    for c in clusters.values():
        c["intensity"] = round(min(1.0, 0.25 + 0.75 * c["count"] / _INTENSITY_SAT), 2)
    return sorted(clusters.values(), key=lambda c: c["count"], reverse=True)


async def fetch_market_pulse() -> dict[str, Any]:
    """聚合所有源；结果缓存 10 分钟（前端每 10 分钟轮询一次）。"""
    now_ts = asyncio.get_event_loop().time()
    async with _lock:
        if _cache["payload"] is not None and now_ts - _cache["ts"] < _CACHE_TTL:
            return _cache["payload"]

        fetched_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            results = await asyncio.gather(
                *(_fetch_one(client, src) for src in _SOURCES)
            )

        items: list[dict[str, Any]] = []
        failed: list[str] = []
        ok_sources = 0
        for source, entries in zip(_SOURCES, results):
            if entries:
                ok_sources += 1
                items.extend(entries)
            else:
                failed.append(source.name)

        # 只保留 24h 内存量（当天的全都收），按发布时间倒序
        window_start = fetched_at - _ITEM_WINDOW
        items = [it for it in items if it["published_at"] >= window_start]
        items.sort(key=lambda x: x["published_at"], reverse=True)

        payload = {
            "fetched_at": fetched_at,
            "ttl_seconds": int(_ITEM_WINDOW.total_seconds()),
            "poll_seconds": int(_CACHE_TTL),
            "regions": sorted({s.region_code for s in _SOURCES if s.region_code}),
            "items": items,
            "clusters": _build_clusters(items),
            "ok_sources": ok_sources,
            "failed_sources": failed,
        }
        _cache.update(ts=now_ts, payload=payload, ok_sources=ok_sources)
        return payload


def pulse_freshness_hint() -> str:
    """供 meta 使用的简单提示（当日存量条目数）。"""
    payload = _cache.get("payload")
    if not payload:
        return ""
    return f"items={len(payload.get('items', []))}"
