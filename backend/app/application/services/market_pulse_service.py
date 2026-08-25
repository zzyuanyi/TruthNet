"""全球舆情脉搏服务：当日存量累积 + 每 10 分钟后台定点增量爬取。

数据链路（真实后端能力，非前端假数据）：
1. 进程启动即全量爬取 8 个 RSS 源，写入本地 SQLite（data/market_pulse.db）
2. 后台任务每 10 分钟定点再爬一轮，按 URL 指纹去重合并 —— 当天越晚存量越厚
3. API 永远读库返回「过去 24h 全部存量」，跨天自动物理清理
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/market_pulse.db")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS pulse_items (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    source_name  TEXT NOT NULL,
    region_code  TEXT NOT NULL,
    country      TEXT NOT NULL,
    lat          REAL NOT NULL,
    lng          REAL NOT NULL,
    published_at TEXT NOT NULL,
    severity     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pulse_published ON pulse_items(published_at);
"""

_PER_SOURCE_LIMIT = 25  # 单源每轮最多收 25 条（当日累积靠多轮合并）
_FETCH_TIMEOUT = 8.0
_CRAWL_INTERVAL = 600.0  # 每 10 分钟定点更新一轮
_ITEM_WINDOW = timedelta(hours=24)  # 保留一天存量
_INTENSITY_SAT = 12.0
_SEV_RANK = {"info": 1, "warning": 2, "critical": 3}
_CN_TZ = ZoneInfo("Asia/Shanghai")

_STATE: dict[str, object] = {
    "task": None,
    "last_crawl_at": datetime.min.replace(tzinfo=timezone.utc),
    "ok_sources": 0,
    "failed_sources": [],
    "last_new_count": 0,
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class PulseSource:
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


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# ---------------------------------------------------------------------------
# 内容级地理识别：标题命中关键词 → 覆盖源默认国别（哪块有新闻哪块亮）
# 坐标一律取首都（用户要求：亮点落在相应国家的首都位置）
# ---------------------------------------------------------------------------
_GEO_RULES: tuple[tuple[str, str, float, float, tuple[str, ...]], ...] = (
    # (country, region_code, lat, lng, keywords) —— 顺序即优先级：香港先于中国
    ("中国香港", "ASIA", 22.32, 114.17, ("hong kong", "hang seng", "香港", "恒生")),
    ("中国", "CN", 39.90, 116.41,
     ("china", "chinese", "beijing", "shanghai", "shenzhen", "yuan",
      "中国", "北京", "上海", "深圳", "人民币", "A股", "a股")),
    ("美国", "US", 38.90, -77.04,
     ("u.s.", "us stocks", "us fed", "wall street", "nasdaq", "dow jones",
      "the dow", "s&p", "washington", "treasury", "white house",
      "美股", "美元", "美联储", "纳斯达克", "华盛顿", "白宫")),
    ("日本", "ASIA", 35.68, 139.69,
     ("japan", "tokyo", "nikkei", "yen", "boj", "日本", "东京", "日经", "日元", "日本央行")),
    ("韩国", "ASIA", 37.57, 126.98, ("korea", "seoul", "kospi", "韩国", "首尔")),
    ("印度", "ASIA", 28.61, 77.21, ("india", "mumbai", "rupee", "印度", "孟买", "卢比")),
    ("新加坡", "ASIA", 1.35, 103.82, ("singapore", "新加坡")),
    ("澳大利亚", "ASIA", -35.28, 149.13, ("australia", "sydney", "aussie", "澳大利亚", "悉尼")),
    ("德国", "EU", 52.52, 13.40,
     ("germany", "german", "berlin", "frankfurt", "dax", "德国", "柏林", "法兰克福")),
    ("法国", "EU", 48.86, 2.35, ("france", "french", "paris", "法国", "巴黎")),
    ("英国", "EU", 51.51, -0.13,
     ("britain", "london", "ftse", "sterling", "pound", "英国", "伦敦", "英镑")),
    ("俄罗斯", "EU", 55.76, 37.62, ("russia", "moscow", "ruble", "俄罗斯", "莫斯科", "卢布")),
    ("加拿大", "US", 45.42, -75.70, ("canada", "toronto", "加拿大", "多伦多")),
)

# 聚合兜底：未命中内容识别的国家也统一锚定首都（如「欧洲」→ 布鲁塞尔）
_COUNTRY_CAPITALS: dict[str, tuple[float, float]] = {
    country: (lat, lng) for country, _, lat, lng, _ in _GEO_RULES
}
_COUNTRY_CAPITALS["欧洲"] = (50.85, 4.35)  # 布鲁塞尔（欧盟总部）


def _detect_geo(title: str) -> tuple[str, str, float, float] | None:
    """标题关键词 → (国家, 区域, 首都纬度, 首都经度)；未命中返回 None 走源默认。"""
    text = title.lower()
    for country, region, lat, lng, keywords in _GEO_RULES:
        if any(kw in text or kw in title for kw in keywords):
            return country, region, lat, lng
    return None


_SEVERITY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "fraud", "崩盘", "爆雷", "退市", "立案", "调查", "处罚", "罚款",
            "违规", "造假", "假账", "虚增", "做空", "暴跌", "闪崩", "panic",
            "crash", "plunge", "selloff", "lawsuit", "probe", "bankrupt",
        ),
        "critical",
    ),
    (
        (
            "警告", "下滑", "亏损", "下跌", "风险", "警告", "担忧", "诉讼",
            "下调", "警示", "跌", "warn", "decline", "loss", "drop", "fall",
            "risk", "concern", "cut",
        ),
        "warning",
    ),
)


def _infer_severity(title: str) -> str:
    text = title.lower()
    for keywords, level in _SEVERITY_RULES:
        if any(kw in text or kw in title for kw in keywords):
            return level
    return "info"


def _parse_feed(xml_text: str, source: PulseSource) -> list[dict[str, object]]:
    """解析 RSS 2.0 / Atom，返回条目 dict 列表。"""
    root = ET.fromstring(xml_text)
    now = datetime.now(timezone.utc)
    items: list[dict[str, object]] = []

    entries = root.findall("./channel/item")
    if not entries:
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

        digest = hashlib.md5(link.encode("utf-8")).hexdigest()[:12]
        geo = _detect_geo(title)  # 内容级识别：标题指向哪国，亮点就落在该国首都
        items.append(
            {
                "id": f"mp_{digest}",
                "title": title,
                "url": link,
                "source_name": source.name,
                "region_code": geo[1] if geo else source.region_code,
                "country": geo[0] if geo else source.country,
                "lat": geo[2] if geo else source.lat,
                "lng": geo[3] if geo else source.lng,
                "published_at": pub_date,
                "severity": _infer_severity(title),
            }
        )
        if len(items) >= _PER_SOURCE_LIMIT:
            break
    return items


async def _fetch_one(client: httpx.AsyncClient, source: PulseSource) -> list[dict[str, object]]:
    try:
        resp = await client.get(source.url, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        return _parse_feed(resp.text, source)
    except Exception as exc:  # noqa: BLE001 — 单源失败必须降级
        logger.warning("market-pulse 源 %s 拉取失败: %s", source.key, exc)
        return []


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _store_items(items: list[dict[str, object]], fetched_at: datetime) -> int:
    """按 id 去重入库（累积当日存量），并物理清理 24h 窗口外的旧行。"""
    if not items:
        return 0
    cutoff = (fetched_at - _ITEM_WINDOW).isoformat()
    new_count = 0
    conn = _connect()
    try:
        with conn:
            for it in items:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO pulse_items
                    (id, title, url, source_name, region_code, country,
                     lat, lng, published_at, severity, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        it["id"],
                        it["title"],
                        it["url"],
                        it["source_name"],
                        it["region_code"],
                        it["country"],
                        it["lat"],
                        it["lng"],
                        it["published_at"].isoformat(),
                        it["severity"],
                        fetched_at.isoformat(),
                    ),
                )
                new_count += cur.rowcount
            conn.execute("DELETE FROM pulse_items WHERE published_at < ?", (cutoff,))
    finally:
        conn.close()
    return new_count


async def crawl_once() -> dict[str, object]:
    """爬一轮全部源并入库。返回统计信息。"""
    fetched_at = datetime.now(timezone.utc)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(*(_fetch_one(client, src) for src in _SOURCES))

    ok_sources = 0
    failed: list[str] = []
    all_items: list[dict[str, object]] = []
    for source, entries in zip(_SOURCES, results):
        if entries:
            ok_sources += 1
            all_items.extend(entries)
        else:
            failed.append(source.name)

    new_count = await asyncio.to_thread(_store_items, all_items, fetched_at)
    _STATE.update(
        last_crawl_at=fetched_at,
        ok_sources=ok_sources,
        failed_sources=failed,
        last_new_count=new_count,
    )
    logger.info(
        "market-pulse 定点爬取完成: 源 %d/%d 成功, 本轮新增 %d 条",
        ok_sources, len(_SOURCES), new_count,
    )
    return {"ok_sources": ok_sources, "failed": failed, "new": new_count}


async def _scheduler_loop() -> None:
    # 启动立即爬一轮，之后每 10 分钟定点更新（当日存量随之累积）
    while True:
        try:
            await crawl_once()
        except Exception:  # noqa: BLE001 — 调度循环必须永续
            logger.exception("market-pulse 调度轮次失败，等待下一周期")
        await asyncio.sleep(_CRAWL_INTERVAL)


def start_pulse_scheduler() -> None:
    if _STATE["task"] is None or (task := _STATE["task"]) is None or task.done():
        _STATE["task"] = asyncio.create_task(_scheduler_loop())
        logger.info("market-pulse 后台调度已启动：每 %d 秒定点增量爬取", int(_CRAWL_INTERVAL))


def stop_pulse_scheduler() -> None:
    task = _STATE["task"]
    if task is not None and not task.done():
        task.cancel()
    _STATE["task"] = None


def _build_clusters(items: list[dict[str, object]]) -> list[dict[str, object]]:
    """按国家聚合：count 驱动 intensity（点大小/亮度），severity 取最高级。"""
    clusters: dict[str, dict[str, object]] = {}
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
        c["count"] = int(c["count"]) + 1
        c[it["severity"]] = int(c[it["severity"]]) + 1
        if _SEV_RANK[it["severity"]] > _SEV_RANK[c["top_severity"]]:
            c["top_severity"] = it["severity"]
        if it["published_at"] > c["latest_published_at"]:
            c["latest_published_at"] = it["published_at"]
            c["top_title"] = it["title"]

    for c in clusters.values():
        # 亮点统一锚定该国首都（历史行坐标可能是源城市，如上海 → 北京）
        cap = _COUNTRY_CAPITALS.get(str(c["country"]))
        if cap:
            c["lat"], c["lng"] = cap
        c["intensity"] = round(min(1.0, 0.25 + 0.75 * c["count"] / _INTENSITY_SAT), 2)
    return sorted(clusters.values(), key=lambda c: c["count"], reverse=True)


def _load_window_items() -> list[dict[str, object]]:
    """读库：当日 0 点起 ∪ 过去 24h 滚动（取更早者），演示永有存量。"""
    now = datetime.now(timezone.utc)
    rolling = now - _ITEM_WINDOW
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = min(rolling, midnight).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, title, url, source_name, region_code, country,
                   lat, lng, published_at, severity
            FROM pulse_items WHERE published_at >= ?
            ORDER BY published_at DESC
            """,
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "url": r["url"],
            "source_name": r["source_name"],
            "region_code": r["region_code"],
            "country": r["country"],
            "lat": r["lat"],
            "lng": r["lng"],
            "published_at": datetime.fromisoformat(r["published_at"]),
            "severity": r["severity"],
        }
        for r in rows
    ]


async def fetch_market_pulse() -> dict[str, object]:
    """读库返回过去 24h 全部存量（后台任务负责每 10 分钟增量爬取入库）。"""
    # 若调度器尚未跑完首轮（进程刚起），先同步触发一轮爬取
    task = _STATE["task"]
    if (task is None or task.done()) and not _load_window_items():
        await crawl_once()

    items = await asyncio.to_thread(_load_window_items)
    return {
        "fetched_at": _STATE["last_crawl_at"],
        "ttl_seconds": int(_ITEM_WINDOW.total_seconds()),
        "poll_seconds": int(_CRAWL_INTERVAL),
        "regions": sorted({s.region_code for s in _SOURCES if s.region_code}),
        "items": items,
        "clusters": _build_clusters(items),
        "ok_sources": _STATE["ok_sources"],
        "failed_sources": list(_STATE["failed_sources"]),  # type: ignore[arg-type]
    }


def pulse_freshness_hint() -> str:
    return f"items={len(_load_window_items())}"
