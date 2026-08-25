import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Globe, { type GlobeMethods } from 'react-globe.gl';
import * as THREE from 'three';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { truthnetFetch } from '@/lib/api-client';

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

/** 国家热点聚合：count 驱动 intensity（条数越多，点亮得越狠） */
interface PulseCluster {
  country: string;
  region_code: string;
  lat: number;
  lng: number;
  count: number;
  critical: number;
  warning: number;
  info: number;
  top_severity: 'info' | 'warning' | 'critical';
  top_title: string;
  intensity: number;
  latest_published_at: string;
}

interface PulseData {
  items: PulseItem[];
  clusters: PulseCluster[];
  ok_sources: number;
  failed_sources: string[];
  fetched_at: string;
}

/** 联网深挖结果（后端 /market-pulse/dig，truthnetFetch 已解包 data） */
interface DigItem {
  title: string;
  url: string;
  snippet: string;
  domain: string;
  published_at: string | null;
}

/** 前端轮询间隔：10 分钟（后端同为 10 分钟缓存，天然对齐） */
const POLL_INTERVAL_MS = 10 * 60 * 1000;

const SEVERITY_COLOR: Record<PulseItem['severity'], string> = {
  info: '#5da2ff',
  warning: '#f5b042',
  critical: '#ff5d5d',
};

const SEVERITY_LABEL: Record<PulseItem['severity'], string> = {
  info: '资讯',
  warning: '预警',
  critical: '高危',
};

/** 地球贴图：夜景城市灯光（电影感，本地资产，无 CDN 依赖） */
const GLOBE_NIGHT_TEXTURE = '/assets/globe/earth-night.jpg';
const GLOBE_DAY_TEXTURE = '/assets/globe/earth-blue-marble.jpg';

/** 确定性星空（种子随机，避免重渲闪烁；透过球体边缘缝隙点缀深空） */
const STARS = (() => {
  let seed = 20260825;
  const rnd = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  return Array.from({ length: 48 }, (_, i) => ({
    id: i,
    left: rnd() * 100,
    top: rnd() * 100,
    size: 0.8 + rnd() * 1.6,
    opacity: 0.22 + rnd() * 0.5,
    delay: rnd() * 4,
    duration: 2.6 + rnd() * 3.2,
  }));
})();

/** #rrggbb → rgba()，用于涟漪环随扩散渐隐 */
function hexAlpha(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.replace(/(.)/g, '$1$1') : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${Math.max(0, Math.min(1, alpha)).toFixed(3)})`;
}

type ClusterPoint = PulseCluster & { color: string };

// ---------------------------------------------------------------------------
// 信号灯标记：径向渐变光晕贴图（中心白核 → severity 色 → 渐隐）
// 呈现「监控大屏信号灯」质感，替代潦草的六边形柱
// ---------------------------------------------------------------------------
const glowTextureCache = new Map<string, THREE.Texture>();

function getGlowTexture(color: string): THREE.Texture {
  let tex = glowTextureCache.get(color);
  if (tex) return tex;
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas 2d unavailable');
  const h = color.replace('#', '');
  const n = parseInt(h, 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, 'rgba(255,255,255,0.98)');
  grad.addColorStop(0.16, `rgba(${r},${g},${b},0.92)`);
  grad.addColorStop(0.40, `rgba(${r},${g},${b},0.36)`);
  grad.addColorStop(0.72, `rgba(${r},${g},${b},0.10)`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  tex = new THREE.CanvasTexture(canvas);
  glowTextureCache.set(color, tex);
  return tex;
}

/**
 * 市场舆情地球：半圆舷窗包裹旋转地球，融入对话主界面的网格底板。
 * 每 10 分钟抓取一次全球财经舆情，保留当日存量；按国家聚合成热点强度，
 * 条数越多亮点越大越亮（中国 A 股多条 → 中国区点亮得狠）。
 * 点击亮点弹出该国舆情列表；上方织网鉴真「眼睛」俯瞰全球市场。
 */
export function MarketPulseGlobe() {
  const globeWrap = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const [size, setSize] = useState({ width: 640, height: 640 });
  const [items, setItems] = useState<PulseItem[]>([]);
  const [clusters, setClusters] = useState<PulseCluster[]>([]);
  const [failedSources, setFailedSources] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [selected, setSelected] = useState<PulseCluster | null>(null);
  const [isDark, setIsDark] = useState(true);
  const [netError, setNetError] = useState(false);
  // 联网深挖：按需对该国实时联网搜索（与 RSS 监控互补）
  const [digging, setDigging] = useState(false);
  const [digItems, setDigItems] = useState<DigItem[] | null>(null);

  // 切换国家/关闭弹窗时清空上一轮深挖结果
  useEffect(() => {
    setDigItems(null);
    setDigging(false);
  }, [selected?.country]);

  const runDig = useCallback(async (country: string) => {
    setDigging(true);
    setDigItems(null);
    try {
      const data = await truthnetFetch<{ items: DigItem[] }>(
        `/market-pulse/dig?country=${encodeURIComponent(country)}`,
      );
      setDigItems(data.items ?? []);
    } catch {
      setDigItems([]);
    } finally {
      setDigging(false);
    }
  }, []);

  // 主题跟随：暗色=夜景地球+深空窗；亮色=蓝色大理石地球+白昼窗
  useEffect(() => {
    const el = document.documentElement;
    const sync = () => setIsDark(el.classList.contains('dark'));
    sync();
    const mo = new MutationObserver(sync);
    mo.observe(el, { attributes: true, attributeFilter: ['class'] });
    return () => mo.disconnect();
  }, []);

  // 画布尺寸自适应：画布为正方形（宽 = 半圆宽），球心锚定半圆圆心
  useEffect(() => {
    const el = globeWrap.current;
    if (!el) return undefined;
    const update = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) setSize({ width: rect.width, height: rect.width });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // 10 分钟轮询；失败后退避快速重试（15s 起步、加倍、上限 60s，成功后重置），避免后端重启窗口期长时间显示 0
  useEffect(() => {
    let alive = true;
    let retryTimer = 0;
    let retryDelay = 15_000;
    const load = async () => {
      try {
        const data = await truthnetFetch<PulseData>('/market-pulse');
        if (!alive) return;
        setItems(data.items ?? []);
        setClusters(data.clusters ?? []);
        setFailedSources(Array.isArray(data.failed_sources) ? data.failed_sources.length : 0);
        setLastUpdated(new Date());
        setNetError(false);
        retryDelay = 15_000;
      } catch {
        /* 网络异常时保留旧点，退避后快速重试 */
        if (alive) {
          setNetError(items.length === 0);
          window.clearTimeout(retryTimer);
          retryTimer = window.setTimeout(load, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 60_000);
        }
      }
    };
    load();
    const timer = window.setInterval(load, POLL_INTERVAL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.clearTimeout(retryTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 自动旋转 + 取景：球体几乎填满半圆，边缘被薄壳裁掉一点，包裹感更强
  useEffect(() => {
    if (!globeRef.current) return undefined;
    const g = globeRef.current;
    g.controls().autoRotate = true;
    g.controls().autoRotateSpeed = 0.5;
    g.controls().enableZoom = false;
    g.pointOfView({ lat: 18, lng: 108, altitude: 1.05 }, 0);
    return () => {
      g.controls().autoRotate = false;
    };
  }, []);

  // 亮点：一个国家一个点，大小/高度 ∝ 热点强度
  const points = useMemo<ClusterPoint[]>(
    () =>
      clusters.map((c) => ({
        ...c,
        color: SEVERITY_COLOR[c.top_severity] ?? SEVERITY_COLOR.info,
      })),
    [clusters],
  );

  // 涟漪环：有预警/高危热点的国家加扩散环（环半径随强度）
  const rings = useMemo(
    () =>
      points
        .filter((p) => p.top_severity !== 'info' || p.intensity >= 0.9)
        .slice(0, 6)
        .map((p) => ({
          lat: p.lat,
          lng: p.lng,
          color: p.color,
          maxR: 2.5 + p.intensity * 3.5,
          speed: 1.4,
          period: 1900,
        })),
    [points],
  );

  const onPointClick = useCallback((point: ClusterPoint) => setSelected(point), []);

  // 信号灯光晕：Sprite 贴在球面坐标（参与深度遮挡，转到球背面自动隐没）；
  // 暗色用叠加混合出「发光体」质感，亮色用普通混合保持清晰
  const objectThreeObject = useCallback(
    (d: object) => {
      const c = d as ClusterPoint;
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: getGlowTexture(c.color),
          blending: isDark ? THREE.AdditiveBlending : THREE.NormalBlending,
          depthWrite: false,
          transparent: true,
        }),
      );
      sprite.scale.setScalar(6.5 + c.intensity * 11);
      return sprite;
    },
    [isDark],
  );

  const totalCount = items.length;
  const topClusters = clusters.slice(0, 4);

  return (
    <div>
      {/* 区块标题 */}
      <div className="mb-1 flex items-center justify-between px-1 font-mono text-[10px] tracking-widest text-muted-foreground">
        <span>MARKET PULSE · 全球舆情脉搏</span>
        <span className="hidden items-center gap-1.5 sm:flex">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          LIVE
        </span>
      </div>

      {/* 半圆舷窗：正好包裹地球，外圈一层薄壳，其余透出页面网格底板 */}
      <div className="relative mx-auto w-full max-w-[660px]">
        <div
          className={`relative aspect-[2/1] w-full overflow-hidden rounded-t-full ${isDark ? 'ring-1 ring-white/[0.10]' : 'ring-1 ring-black/[0.08]'}`}
          style={
            isDark
              ? {
                  background:
                    'linear-gradient(180deg, color-mix(in srgb, var(--color-primary) 10%, #01040a) 0%, ' +
                    'color-mix(in srgb, var(--color-primary) 20%, #020a14) 60%, ' +
                    'color-mix(in srgb, var(--color-primary) 36%, #041527) 100%)',
                  boxShadow:
                    'inset 0 1px 1px rgba(255,255,255,0.10), ' +
                    '0 -22px 70px -26px color-mix(in srgb, var(--color-primary) 45%, transparent)',
                }
              : {
                  // 白昼模式：浅色天穹渐变，地球换蓝色大理石，避免黑乎乎一团
                  background:
                    'linear-gradient(180deg, color-mix(in srgb, var(--color-primary) 5%, #f3f7fc) 0%, ' +
                    'color-mix(in srgb, var(--color-primary) 10%, #e3edf8) 60%, ' +
                    'color-mix(in srgb, var(--color-primary) 18%, #cfe0f2) 100%)',
                  boxShadow:
                    'inset 0 1px 1px rgba(255,255,255,0.80), ' +
                    '0 -22px 60px -30px color-mix(in srgb, var(--color-primary) 30%, transparent)',
                }
          }
        >
          {/* 星空：仅暗色模式的深空点缀 */}
          {isDark && (
            <div className="pointer-events-none absolute inset-0 z-0">
              {STARS.map((s) => (
                <span
                  key={s.id}
                  className="tn-star absolute rounded-full bg-white"
                  style={
                    {
                      left: `${s.left}%`,
                      top: `${s.top}%`,
                      width: s.size,
                      height: s.size,
                      '--star-o': s.opacity,
                      '--star-delay': `${s.delay}s`,
                      '--star-d': `${s.duration}s`,
                    } as CSSProperties
                  }
                />
              ))}
            </div>
          )}

          {/* 地球：正方形画布锚定半圆（球心=半圆圆心），下半被裁，只露上半球 */}
          <div
            ref={globeWrap}
            className="absolute inset-x-0 top-0 z-[1] mx-auto aspect-square w-full"
          >
            <Globe
              ref={globeRef as never}
              width={size.width}
              height={size.height}
              backgroundColor="rgba(0,0,0,0)"
              globeImageUrl={isDark ? GLOBE_NIGHT_TEXTURE : GLOBE_DAY_TEXTURE}
              showAtmosphere
              atmosphereColor="#7fb0e8"
              atmosphereAltitude={0.25}
              pointsData={points}
              pointLat="lat"
              pointLng="lng"
              pointColor={() => '#ffffff'}
              pointAltitude={0.008}
              pointRadius={((d: object) => {
                // 白色亮核（信号灯的芯），高级感的光晕由 objects 层负责
                const c = d as ClusterPoint;
                return 0.1 + c.intensity * 0.13;
              }) as never}
              pointLabel={((d: object) => {
                const c = d as ClusterPoint;
                return `<div style="font:11px ui-monospace,monospace;background:rgba(2,8,18,0.86);border:1px solid rgba(127,176,232,0.35);border-radius:6px;padding:4px 8px;color:#dbe9f7">${c.country} · ${c.count} 条 · 强度 ${(c.intensity * 100).toFixed(0)}%</div>`;
              }) as never}
              pointResolution={14}
              pointsMerge={false}
              onPointClick={onPointClick as never}
              objectsData={points}
              objectLat="lat"
              objectLng="lng"
              objectAltitude={0.012}
              objectThreeObject={objectThreeObject as never}
              onObjectClick={onPointClick as never}
              ringsData={rings}
              ringLat="lat"
              ringLng="lng"
              ringColor={({ color }: { color: string }) => (t: number) => hexAlpha(color, 0.5 * (1 - t))}
              ringMaxRadius="maxR"
              ringPropagationSpeed="speed"
              ringRepeatPeriod="period"
            />
          </div>

          {/* 暗角渐晕：边缘收束，向页面底板自然过渡（暗色压暗 / 亮色提白） */}
          <div
            className="pointer-events-none absolute inset-0 z-[2]"
            style={{
              background: isDark
                ? 'radial-gradient(120% 120% at 50% 100%, transparent 52%, rgba(2,8,18,0.42) 88%, rgba(2,8,18,0.72) 100%)'
                : 'radial-gradient(120% 120% at 50% 100%, transparent 52%, rgba(243,247,252,0.46) 88%, rgba(227,237,248,0.78) 100%)',
            }}
          />
        </div>
      </div>

      {/* 状态条：总量 + 热点国家 + 更新节奏 */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 px-1 font-mono text-[10px] tracking-wider text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-foreground/80">
            {netError && totalCount === 0 ? (
              <span className="text-warning-600/90 dark:text-warning-400/90">信号中断，重连中…</span>
            ) : (
              `当日 ${totalCount} 条`
            )}
          </span>
          {topClusters.map((c) => (
            <span key={c.country} className="flex items-center gap-1">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: SEVERITY_COLOR[c.top_severity], opacity: 0.55 + c.intensity * 0.45 }}
              />
              {c.country} {c.count}
            </span>
          ))}
        </div>
        <span>
          每 10 分钟更新 · 保留当日 {lastUpdated ? `· ${lastUpdated.toLocaleTimeString('zh-CN', { hour12: false })}` : ''}
          {failedSources > 0 ? ` · ${failedSources} 源不可用` : ''}
        </span>
      </div>

      {/* 点击国家亮点弹出该国舆情列表 */}
      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[70vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: selected ? SEVERITY_COLOR[selected.top_severity] : undefined }}
              />
              {selected?.country} · {selected?.count ?? 0} 条 · 热点强度{' '}
              {selected ? `${(selected.intensity * 100).toFixed(0)}%` : ''}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {selected
              ? items
                  .filter((it) => it.country === selected.country)
                  .map((it) => (
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
                    </a>
                  ))
              : null}
          </div>

          {/* 联网深挖：按需对该国实时联网搜索，补充 RSS 固定源的盲区 */}
          <div className="mt-4 border-t border-border pt-3">
            <button
              type="button"
              onClick={() => selected && runDig(selected.country)}
              disabled={digging || !selected}
              className="inline-flex items-center gap-2 rounded-md border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-60"
            >
              {digging ? (
                <>
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-primary/40 border-t-primary" />
                  联网检索中…
                </>
              ) : (
                <>
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                  联网深挖该国舆情
                </>
              )}
            </button>

            {digItems !== null && !digging && (
              <div className="mt-3 space-y-2">
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  联网检索 · {digItems.length} 条命中 · 来源为公开网络
                </p>
                {digItems.map((d) => (
                  <a
                    key={d.url}
                    href={d.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block rounded-md border border-dashed border-border bg-muted/30 p-3 transition-colors hover:border-primary"
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <Badge variant="outline" className="border-primary/50 text-primary">
                        联网
                      </Badge>
                      <span className="truncate font-mono text-[10px] text-muted-foreground">
                        {d.domain}
                      </span>
                      {d.published_at && (
                        <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                          {d.published_at.slice(5, 16).replace('T', ' ')}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-medium leading-snug">{d.title}</p>
                    {d.snippet && (
                      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                        {d.snippet}
                      </p>
                    )}
                  </a>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
