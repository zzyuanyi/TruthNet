import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Globe, { type GlobeMethods } from 'react-globe.gl';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { truthnetFetch } from '@/lib/api-client';
import { TruthNetMark } from '@/components/truthnet/TruthNetMark';

/** 单条市场舆情（后端 /api/v1/market-pulse，truthnetFetch 已解包 data） */
interface PulseItem {
  id: string;
  title: string;
  url: string;
  source_name: string;
  published_at: string;
  region_code: string;
  country: string;
  lat: number;
  lng: number;
  severity: 'info' | 'warning' | 'critical';
}

interface PulseData {
  items: PulseItem[];
  ok_sources: number;
  failed_sources: string[];
  fetched_at: string;
}

/** 10 分钟：超过 TTL 的消息自动从地球上清除 */
const ITEM_TTL_MS = 10 * 60 * 1000;
/** 前端轮询间隔：10 秒 */
const POLL_INTERVAL_MS = 10 * 1000;
/** 每个坐标点最多聚合条数（防止一个区域爆点） */
const MAX_PER_POINT = 4;

const SEVERITY_COLOR: Record<PulseItem['severity'], string> = {
  info: '#3b82f6',
  warning: '#f59e0b',
  critical: '#ef4444',
};

const SEVERITY_LABEL: Record<PulseItem['severity'], string> = {
  info: '资讯',
  warning: '预警',
  critical: '高危',
};

/** 地球贴图（本地资产，public/assets/globe/，无 CDN 依赖；深色主题用城市灯光夜景）*/
const GLOBE_TEXTURE = {
  day: '/assets/globe/earth-blue-marble.jpg',
  night: '/assets/globe/earth-night.jpg',
};

/** 抖动坐标，避免同一城市的多条消息重叠成一个点 */
function jitter(v: number, seed: number): number {
  const r = Math.sin(seed * 9973) * 10000;
  const frac = r - Math.floor(r);
  return v + (frac - 0.5) * 6;
}

/**
 * 市场舆情地球：旋转 3D 地球 + 每 10 秒抓取最新全球财经舆情，
 * 各国亮点闪现，点击亮点弹出该坐标的舆情列表；10 分钟外的消息自动清除。
 * 上方悬浮织网鉴真「眼睛」，凝视全球市场。
 */
export function MarketPulseGlobe() {
  const globeWrap = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const [size, setSize] = useState({ width: 600, height: 420 });
  const [items, setItems] = useState<PulseItem[]>([]);
  const [failedSources, setFailedSources] = useState(0);
  const [tick, setTick] = useState(0); // TTL 清理驱动
  const [selectedPoint, setSelectedPoint] = useState<{ lat: number; lng: number; items: PulseItem[] } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isDark, setIsDark] = useState(false);

  // 主题跟随：深色主题切换为夜景地球（城市灯光）
  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setIsDark(root.classList.contains('dark'));
    sync();
    const mo = new MutationObserver(sync);
    mo.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => mo.disconnect();
  }, []);

  // 尺寸自适应
  useEffect(() => {
    const el = globeWrap.current;
    if (!el) return undefined;
    const update = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) setSize({ width: rect.width, height: rect.height });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // 10 秒轮询
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await truthnetFetch<PulseData>('/api/v1/market-pulse');
        if (!alive) return;
        setItems(data.items ?? []);
        setFailedSources(Array.isArray(data.failed_sources) ? data.failed_sources.length : 0);
        setLastUpdated(new Date());
      } catch {
        /* 网络异常时保留旧点，下次轮询重试 */
      }
    };
    load();
    const timer = window.setInterval(load, POLL_INTERVAL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  // 每 30 秒检查一次 TTL，把过期消息清掉
  useEffect(() => {
    const timer = window.setInterval(() => setTick((t) => t + 1), 30 * 1000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    setItems((prev) => {
      const now = Date.now();
      const next = prev.filter((it) => now - new Date(it.published_at).getTime() < ITEM_TTL_MS);
      return next.length === prev.length ? prev : next;
    });
  }, [tick]);

  // 自动旋转
  useEffect(() => {
    if (!globeRef.current) return undefined;
    const g = globeRef.current;
    g.controls().autoRotate = true;
    g.controls().autoRotateSpeed = 0.6;
    g.controls().enableZoom = false;
    g.pointOfView({ lat: 22, lng: 105, altitude: 2.4 }, 0);
    return () => {
      g.controls().autoRotate = false;
    };
  }, []);

  // 聚合：同一坐标附近的点合并展示
  const points = useMemo(() => {
    const byKey = new Map<string, PulseItem[]>();
    items.forEach((it, idx) => {
      const key = `${it.lat.toFixed(0)}:${it.lng.toFixed(0)}`;
      const bucket = byKey.get(key) ?? [];
      if (bucket.length < MAX_PER_POINT) bucket.push({ ...it, lat: jitter(it.lat, idx + 1), lng: jitter(it.lng, idx + 11) });
      byKey.set(key, bucket);
    });
    return Array.from(byKey.values())
      .flat()
      .map((it) => ({
        ...it,
        // 环形柱：半径 0.35、高度按严重度
        lat: it.lat,
        lng: it.lng,
        color: SEVERITY_COLOR[it.severity] ?? SEVERITY_COLOR.info,
        altitude: it.severity === 'critical' ? 0.5 : it.severity === 'warning' ? 0.32 : 0.2,
      }));
  }, [items]);

  const onPointClick = useCallback((point: (typeof points)[number]) => {
    // 找回同区域的全部消息（含被聚合截断的）
    const near = items.filter(
      (it) => Math.abs(it.lat - point.lat) < 4 && Math.abs(it.lng - point.lng) < 4,
    );
    setSelectedPoint({ lat: point.lat, lng: point.lng, items: near });
  }, [items]);

  const infoCount = items.filter((i) => i.severity === 'info').length;
  const warnCount = items.filter((i) => i.severity === 'warning').length;
  const critCount = items.filter((i) => i.severity === 'critical').length;

  return (
    <div>
      {/* 区块标题 */}
      <div className="mb-2 flex items-center justify-between px-1 font-mono text-[10px] tracking-widest text-muted-foreground">
        <span>MARKET PULSE · 全球舆情脉搏</span>
        <span className="hidden sm:inline">LIVE</span>
      </div>

      <div className="relative">
        {/* 眼睛悬在地球上空 */}
        <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-1/2">
          <TruthNetMark className="h-12 w-16 text-primary drop-shadow-md" />
        </div>

      <div ref={globeWrap} className="relative h-[380px] w-full overflow-hidden rounded-lg border border-border bg-card sm:h-[420px]">
        <Globe
          ref={globeRef as never}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          globeImageUrl={isDark ? GLOBE_TEXTURE.night : GLOBE_TEXTURE.day}
          bumpImageUrl="/assets/globe/earth-topology.png"
          showGraticules
          showAtmosphere
          atmosphereColor="#4f8cc6"
          atmosphereAltitude={0.16}
          pointsData={points}
          pointLat="lat"
          pointLng="lng"
          pointColor="color"
          pointAltitude="altitude"
          pointRadius={0.32}
          pointResolution={12}
          onPointClick={onPointClick as never}
          labelsData={[]}
        />
        {/* 顶部渐隐遮罩，避免地球顶部和卡片边缘生硬相接 */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-14 bg-gradient-to-b from-background/60 to-transparent" />
      </div>
      </div>

      {/* 状态条 */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 px-1 font-mono text-[10px] tracking-wider text-muted-foreground">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            资讯 {infoCount}
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            预警 {warnCount}
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
            高危 {critCount}
          </span>
        </div>
        <span>
          10s 轮询 · 10min 留存 {lastUpdated ? `· ${lastUpdated.toLocaleTimeString('zh-CN', { hour12: false })}` : ''}
          {failedSources > 0 ? ` · ${failedSources} 源不可用` : ''}
        </span>
      </div>

      {/* 点击亮点弹出舆情详情 */}
      <Dialog open={selectedPoint !== null} onOpenChange={(open) => !open && setSelectedPoint(null)}>
        <DialogContent className="max-h-[70vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <span className="inline-block h-2 w-2 rounded-full bg-primary" />
              {selectedPoint?.items[0]?.country ?? '舆情'} · {selectedPoint?.items.length ?? 0} 条
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {selectedPoint?.items.map((it) => (
              <a
                key={it.id}
                href={it.url}
                target="_blank"
                rel="noreferrer"
                className="block rounded-md border border-border bg-card p-3 transition-colors hover:border-primary"
              >
                <div className="mb-1 flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={
                      it.severity === 'critical'
                        ? 'border-red-500/50 text-red-600 dark:text-red-400'
                        : it.severity === 'warning'
                          ? 'border-amber-500/50 text-amber-600 dark:text-amber-400'
                          : 'border-blue-500/50 text-blue-600 dark:text-blue-400'
                    }
                  >
                    {SEVERITY_LABEL[it.severity]}
                  </Badge>
                  <span className="font-mono text-[10px] text-muted-foreground">{it.source_name}</span>
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                    {new Date(it.published_at).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <p className="text-sm font-medium leading-snug">{it.title}</p>
                <p className="mt-1 font-mono text-[10px] tracking-wider text-muted-foreground">{it.region_code}</p>
              </a>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
