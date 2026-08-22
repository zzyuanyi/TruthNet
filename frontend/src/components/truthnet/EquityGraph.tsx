import { useEffect, useMemo, useRef, useState } from 'react';
import { Circle, ExtensionCategory, Graph, register } from '@antv/g6';
import type { EquityNodeDTO, EquityEdgeDTO } from '@/types/truthnet';

interface EquityGraphProps {
  nodes: EquityNodeDTO[];
  edges: EquityEdgeDTO[];
  targetId: string;
}

const RISK_LEVEL_COLORS: Record<string, string> = {
  red: '#ef4444',
  orange: '#f97316',
  yellow: '#eab308',
  blue: '#3b82f6',
  unknown: '#6b7280',
};

const RISK_LEVEL_LABELS: Record<string, string> = {
  red: '高危',
  orange: '中高危',
  yellow: '中等',
  blue: '低风险',
  unknown: '未知',
};

// 后端 entity_type 值域 → 节点内部标签（ListedCompany/Company → 空、Person → 人、其他 → 机构）
function mapEntityType(entityType: string): string {
  if (entityType === 'Person') return 'person';
  if (entityType === 'ListedCompany' || entityType === 'Company') return 'company';
  return 'fund';
}

const NODE_RADIUS: Record<string, number> = {
  target: 30,
  company: 22,
  person: 18,
  fund: 16,
};

interface GraphLayoutNode extends EquityNodeDTO {
  nodeType: string;
  hop: number;
  x: number;
  y: number;
}

interface GraphLayout {
  width: number;
  height: number;
  nodes: GraphLayoutNode[];
  layerCount: number;
  maxHop: number;
  radiusScale: number;
}

function truncateLabel(name: string, max = 10): string {
  if (!name) return '未命名';
  return name.length > max ? `${name.slice(0, max)}…` : name;
}

function computeGraphLayout(
  nodes: EquityNodeDTO[],
  edges: EquityEdgeDTO[],
  targetId: string,
  containerWidth: number,
): GraphLayout {
  // 无向 BFS 计算每个节点距目标公司的 hop（不可达节点排到最右）
  const adj = new Map<string, string[]>();
  nodes.forEach(n => adj.set(n.id, []));
  edges.forEach(e => {
    adj.get(e.source)?.push(e.target);
    adj.get(e.target)?.push(e.source);
  });

  const hops = new Map<string, number>();
  const targetNode = nodes.find(n => n.id === targetId || n.entity_id === targetId);
  if (targetNode) {
    const queue: string[] = [targetNode.id];
    hops.set(targetNode.id, 0);
    while (queue.length > 0) {
      const cur = queue.shift()!;
      const curHop = hops.get(cur)!;
      for (const nb of adj.get(cur) || []) {
        if (!hops.has(nb)) {
          hops.set(nb, curHop + 1);
          queue.push(nb);
        }
      }
    }
  }
  const maxHop = Math.max(0, ...hops.values());
  nodes.forEach(n => {
    if (!hops.has(n.id)) hops.set(n.id, maxHop + 1);
  });

  const byHop = new Map<number, GraphLayoutNode[]>();
  nodes.forEach(n => {
    const nodeType =
      n.id === targetId || n.entity_id === targetId
        ? 'target'
        : mapEntityType(n.entity_type || '');
    const h = hops.get(n.id)!;
    if (!byHop.has(h)) byHop.set(h, []);
    byHop.get(h)!.push({ ...n, nodeType, hop: h, x: 0, y: 0 });
  });

  const layerCount = Math.max(1, maxHop + 1);
  const layerWidth = Math.max(190, (Math.max(containerWidth, 760) - 120) / layerCount);
  const width = Math.max(containerWidth, 70 + layerCount * layerWidth + 90);

  // 每层节点纵向均布；节点多时动态加高并适度缩小节点半径，避免字符重叠
  const maxPerLayer = Math.max(1, ...Array.from(byHop.values()).map(g => g.length));
  const spacing = maxPerLayer <= 8 ? 84 : Math.max(56, Math.min(76, 720 / maxPerLayer));
  const height = Math.max(560, 104 + maxPerLayer * spacing + 28);
  const radiusScale = maxPerLayer > 10 ? 0.78 : 1;

  const layoutNodes: GraphLayoutNode[] = [];
  byHop.forEach((group, h) => {
    const x = 70 + h * layerWidth;
    group.forEach((n, i) => {
      const y = 64 + spacing * (i + 0.5);
      const placed = { ...n, x, y };
      layoutNodes.push(placed);
      byHop.get(h)![i] = placed;
    });
  });

  return { width, height, nodes: layoutNodes, layerCount, maxHop, radiusScale };
}

function nodeFill(d: GraphLayoutNode): string {
  if (d.risk_level && RISK_LEVEL_COLORS[d.risk_level]) return RISK_LEVEL_COLORS[d.risk_level];
  return d.nodeType === 'target' ? '#ef4444' : '#94a3b8';
}

function nodeInnerText(d: GraphLayoutNode): string {
  if (d.nodeType === 'target') return '目标';
  if (d.nodeType === 'person') return '人';
  if (d.nodeType === 'fund') return '机构';
  return '';
}

function tooltipContent(d: GraphLayoutNode): string {
  const typeLabel =
    d.nodeType === 'target'
      ? '目标公司'
      : d.nodeType === 'person'
        ? '自然人'
        : d.nodeType === 'fund'
          ? '机构投资者'
          : '公司';
  const risk = d.risk_level ? `风险等级：${RISK_LEVEL_LABELS[d.risk_level] || d.risk_level}` : '';
  return `<div style="font-weight:600;margin-bottom:4px">${d.name}（第 ${d.hop} 层）</div><div>类型：${typeLabel}</div>${risk ? `<div>${risk}</div>` : ''}`;
}

function isRiskNode(d: GraphLayoutNode): boolean {
  return d.risk_level === 'red' || d.risk_level === 'orange' || d.risk_level === 'yellow';
}

// 风险节点呼吸光环：创建后让 halo 光晕循环放大呼吸
class BreathingCircle extends Circle {
  onCreate() {
    const halo = (
      this as unknown as {
        shapeMap?: { halo?: { animate: (keyframes: unknown[], options: unknown) => void } };
      }
    ).shapeMap?.halo;
    if (halo) {
      halo.animate([{ opacity: 0.5 }, { opacity: 0.05 }], {
        duration: 1500,
        iterations: Infinity,
        direction: 'alternate',
        easing: 'ease-in-out',
      });
    }
  }
}

register(ExtensionCategory.NODE, 'breathing-circle', BreathingCircle);

export function EquityGraph({ nodes, edges, targetId }: EquityGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 520 });

  // Handle resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width } = containerRef.current.getBoundingClientRect();
        setDimensions({ width: Math.max(600, width - 32), height: 520 });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const layout = useMemo(
    () => computeGraphLayout(nodes, edges, targetId, dimensions.width),
    [nodes, edges, targetId, dimensions.width],
  );

  // 用 G6 渲染（Canvas 渲染器）；主题色经 getComputedStyle 读取，主题切换时需重新渲染
  useEffect(() => {
    if (!containerRef.current || layout.nodes.length === 0) return;

    const cs = getComputedStyle(document.documentElement);
    const textColor = cs.getPropertyValue('--color-foreground').trim() || '#0a0a0a';
    const mutedColor = cs.getPropertyValue('--color-muted-foreground').trim() || '#64748b';
    const bgColor = cs.getPropertyValue('--color-background').trim() || '#ffffff';

    // P0-3 修复：render() 为异步（G6 v5 generator，内部 await animation/autoFit）。
    // effect 重跑（layout 变化）时 cleanup 会 destroy 旧实例，旧 render 恢复时
    // 访问已销毁的 context 会抛 "Cannot read properties of undefined (reading
    // 'draw')"——必须 .catch 吞掉该 rejection（销毁后完成属预期）。
    // disposed 标记 + 强制清空容器 canvas 兜底。
    let disposed = false;
    const container = containerRef.current;

    const graph = new Graph({
      container,
      width: layout.width,
      height: layout.height,
      autoFit: 'view',
      data: {
        nodes: layout.nodes.map(n => ({
          id: n.id,
          data: { ...n },
        })),
        edges: edges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          data: { ...e },
        })),
      },
      node: {
        type: (d: any) =>
          isRiskNode(d.data as GraphLayoutNode) ? 'breathing-circle' : 'circle',
        style: {
          x: (d: any) => d.data.x as number,
          y: (d: any) => d.data.y as number,
          r: (d: any) => (NODE_RADIUS[d.data.nodeType] || 20) * layout.radiusScale,
          fill: (d: any) => nodeFill(d.data as GraphLayoutNode),
          stroke: '#ffffff',
          lineWidth: (d: any) => (isRiskNode(d.data as GraphLayoutNode) ? 3.5 : 2.5),
          fillOpacity: 0.92,
          labelText: (d: any) =>
            truncateLabel(d.data.name, layout.radiusScale < 1 ? 8 : 10),
          labelPlacement: 'bottom',
          labelFill: textColor,
          labelFontSize: layout.radiusScale < 1 ? 10 : 11,
          labelOffsetY: 6,
          iconText: (d: any) => nodeInnerText(d.data as GraphLayoutNode),
          iconFill: '#ffffff',
          iconFontSize: 10,
          halo: (d: any) => isRiskNode(d.data as GraphLayoutNode),
          haloFill: (d: any) => nodeFill(d.data as GraphLayoutNode),
          haloStroke: (d: any) => nodeFill(d.data as GraphLayoutNode),
          haloLineWidth: 2,
          haloOpacity: 0.4,
        },
        state: {
          active: { lineWidth: 4, fillOpacity: 1, haloOpacity: 0.9 },
          inactive: {
            fillOpacity: 0.12,
            opacity: 0.3,
            labelOpacity: 0.15,
            haloOpacity: 0.05,
          },
        },
      },
      edge: {
        type: 'line',
        style: {
          stroke: mutedColor,
          lineWidth: 1.6,
          strokeOpacity: 0.65,
          endArrow: true,
          labelText: (d: any) => {
            const rel = d.data.relation_type || '持股';
            const pct = d.data.ownership_pct != null ? ` ${d.data.ownership_pct.toFixed(1)}%` : '';
            return `${rel}${pct}`;
          },
          labelFill: textColor,
          labelFontSize: 10,
          labelBackground: true,
          labelBackgroundFill: bgColor,
          labelBackgroundOpacity: 0.85,
        },
        state: {
          active: { strokeOpacity: 0.95, lineWidth: 2.6 },
          inactive: { strokeOpacity: 0.06, labelOpacity: 0.05 },
        },
      },
      behaviors: [
        'drag-canvas',
        'zoom-canvas',
        'drag-element',
        {
          type: 'hover-activate',
          degree: 1,
          state: 'active',
          inactiveState: 'inactive',
          enable: (e: any) => e.targetType === 'node',
        },
      ],
      plugins: [
        {
          type: 'tooltip',
          getContent: (_evt: any, items: any[]) => {
            const first = items && items[0];
            if (!first || !first.data) return '';
            const d = first.data as GraphLayoutNode;
            if (d.hop === undefined) {
              const e = first.data as EquityEdgeDTO & { relation_type?: string };
              const rel = e.relation_type || '持股';
              const pct = e.ownership_pct != null ? `${e.ownership_pct.toFixed(1)}%` : '';
              return `<div style="font-weight:600">${rel}${pct ? ` ${pct}` : ''}</div>`;
            }
            return tooltipContent(d);
          },
        },
      ] as any,
    });

    // render 为异步：销毁后完成的 promise 属预期（.catch 吞掉 rejection），
    // 未销毁时若失败则静默降级（图不渲染但页面不崩）。
    graph.render().catch(() => {
      if (disposed) return;
      // 非销毁导致的失败：清空容器 canvas，避免残留半渲染状态
      container?.querySelectorAll('canvas').forEach(c => c.remove());
    });
    graphRef.current = graph;

    return () => {
      disposed = true;
      if (graphRef.current === graph) graphRef.current = null;
      try {
        graph.destroy();
      } catch {
        /* 已销毁 */
      }
      // 兜底：清空容器内残留 canvas（G6 destroy 与异步 render 竞态时可能遗留）
      if (container) {
        container.querySelectorAll('canvas').forEach(c => c.remove());
      }
    };
  }, [layout, edges]);

  const handleZoomIn = () => graphRef.current?.zoomBy(1.3);
  const handleZoomOut = () => graphRef.current?.zoomBy(0.7);
  const handleResetZoom = () => graphRef.current?.zoomTo(1);

  return (
    <div ref={containerRef} className="relative border border-border rounded-md bg-muted/20">
      {/* G6 canvas 将挂载于此容器，overlay 元素（图例/按钮）absolute 叠于其上 */}

      {/* 风险等级图例（节点颜色语义） */}
      <div className="absolute bottom-3 left-3 z-10 flex flex-wrap gap-2 bg-background/90 backdrop-blur-sm border border-border rounded-md p-2 text-xs">
        {Object.entries(RISK_LEVEL_LABELS).map(([level, label]) => (
          <span key={level} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: RISK_LEVEL_COLORS[level] }} />
            {label}
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#94a3b8' }} />
          未评级
        </span>
      </div>

      {/* Zoom controls */}
      <div className="absolute top-3 left-3 z-10 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="w-8 h-8 bg-background/90 backdrop-blur-sm border border-border rounded-md flex items-center justify-center hover:bg-muted transition-colors"
          title="放大"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
          </svg>
        </button>
        <button
          onClick={handleZoomOut}
          className="w-8 h-8 bg-background/90 backdrop-blur-sm border border-border rounded-md flex items-center justify-center hover:bg-muted transition-colors"
          title="缩小"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
          </svg>
        </button>
        <button
          onClick={handleResetZoom}
          className="w-8 h-8 bg-background/90 backdrop-blur-sm border border-border rounded-md flex items-center justify-center hover:bg-muted transition-colors"
          title="重置"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>
      </div>

      {/* Hint */}
      <div className="absolute top-3 right-3 z-10 bg-background/90 backdrop-blur-sm border border-border rounded-md px-2 py-1 text-xs text-muted-foreground">
        分层穿透视图 · 滚轮缩放 · 拖拽平移
      </div>
    </div>
  );
}