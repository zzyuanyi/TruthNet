import { useEffect, useMemo, useRef, useState } from 'react';
import { Circle, ExtensionCategory, Graph, register } from '@antv/g6';
import type {
  DownstreamRelation,
  DownstreamRiskSignal,
  EquityNodeDTO,
  EquityEdgeDTO,
} from '@/types/truthnet';

interface EquityGraphProps {
  nodes: EquityNodeDTO[];
  edges: EquityEdgeDTO[];
  targetId: string;
  /** 8/25 下游（子公司/被投资企业）直接持股关系：合并进股权图并展示风险信号 */
  downstreamRelations?: DownstreamRelation[];
  /** 节点点击：上报布局节点（含类型/风险等级/信号/持股），由页面弹全量详情 */
  onNodeClick?: (node: EquityNodeDTO) => void;
}

const RISK_LEVEL_COLORS: Record<string, string> = {
  red: '#dc2626',
  orange: '#ea580c',
  yellow: '#ca8a04',
  blue: '#3b82f6',
  // “正常”不再占用高饱和绿色；图中用中性石板色把视觉注意力留给风险节点。
  green: '#64748b',
  unknown: '#94a3b8',
};

const RISK_LEVEL_LABELS: Record<string, string> = {
  red: '高危',
  orange: '中高危',
  yellow: '中等',
  blue: '低风险',
  green: '正常',
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
  direction: 'target' | 'upstream' | 'downstream';
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
  upstreamDepth: number;
  downstreamDepth: number;
  radiusScale: number;
}

const KEY_OWNERSHIP_PCT = 5;

function riskPriority(riskLevel?: string | null): number {
  return ({ red: 5, orange: 4, yellow: 3, blue: 2, green: 1, unknown: 0 })[
    riskLevel || 'unknown'
  ] ?? 0;
}

function truncateLabel(name: string, max = 10): string {
  if (!name) return '未命名';
  return name.length > max ? `${name.slice(0, max)}…` : name;
}

function relationLabel(relationType?: string): string {
  const relation = relationType || '持股';
  if (relation === 'OWNS') return '持股';
  if (relation === 'CONTROLS') return '控制';
  return relation;
}

function isTargetNode(node: EquityNodeDTO, targetId: string): boolean {
  // 画像页传入的是 wind_code（如 603180.SH），图数据内部边使用 entity_id。
  // 三种稳定标识都要识别，否则目标节点缺失会让所有节点退化到同一列。
  return (
    node.id === targetId ||
    node.entity_id === targetId ||
    node.wind_code === targetId ||
    node.direction === 'target'
  );
}

function computeGraphLayout(
  nodes: EquityNodeDTO[],
  edges: EquityEdgeDTO[],
  targetId: string,
  containerWidth: number,
): GraphLayout {
  // 股权边的语义为“持有人(source) → 被持有主体(target)”。因此不能用无向
  // BFS：同为 1 跳的上游股东会被堆到目标公司的同一列。这里分别沿反向/正向
  // 边搜索，得到“上游股东 → 目标公司 → 下游公司”的稳定层级。
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();
  nodes.forEach(n => {
    incoming.set(n.id, []);
    outgoing.set(n.id, []);
  });
  edges.forEach(e => {
    outgoing.get(e.source)?.push(e.target);
    incoming.get(e.target)?.push(e.source);
  });

  const targetNode = nodes.find(n => isTargetNode(n, targetId));
  const walk = (neighbours: Map<string, string[]>) => {
    const hops = new Map<string, number>();
    if (!targetNode) return hops;
    const queue: string[] = [targetNode.id];
    hops.set(targetNode.id, 0);
    while (queue.length > 0) {
      const cur = queue.shift()!;
      const curHop = hops.get(cur)!;
      for (const nb of neighbours.get(cur) || []) {
        if (!hops.has(nb)) {
          hops.set(nb, curHop + 1);
          queue.push(nb);
        }
      }
    }
    return hops;
  };

  const upstreamHops = walk(incoming);
  const downstreamHops = walk(outgoing);
  const maxUpstreamHop = Math.max(0, ...upstreamHops.values());
  const maxDownstreamHop = Math.max(0, ...downstreamHops.values());
  const maxHop = Math.max(maxUpstreamHop, maxDownstreamHop);
  const strongestOwnership = new Map<string, number>();
  edges.forEach((edge) => {
    const ownership = edge.ownership_pct ?? edge.control_pct ?? 0;
    strongestOwnership.set(
      edge.source,
      Math.max(strongestOwnership.get(edge.source) ?? 0, ownership),
    );
    strongestOwnership.set(
      edge.target,
      Math.max(strongestOwnership.get(edge.target) ?? 0, ownership),
    );
  });

  const byLayer = new Map<string, GraphLayoutNode[]>();
  nodes.forEach(n => {
    const isTarget = isTargetNode(n, targetId);
    const isDownstream =
      !isTarget &&
      (n.direction === 'downstream' ||
        (downstreamHops.has(n.id) && !upstreamHops.has(n.id)));
    const nodeType = isTarget ? 'target' : mapEntityType(n.entity_type || '');
    const direction: GraphLayoutNode['direction'] = isTarget
      ? 'target'
      : isDownstream
        ? 'downstream'
        : 'upstream';
    const hop = isTarget
      ? 0
      : direction === 'downstream'
        ? downstreamHops.get(n.id) || 1
        : upstreamHops.get(n.id) || maxUpstreamHop + 1;
    const layerKey = `${direction}:${hop}`;
    if (!byLayer.has(layerKey)) byLayer.set(layerKey, []);
    byLayer.get(layerKey)!.push({ ...n, nodeType, direction, hop, x: 0, y: 0 });
  });

  const layerCount = Math.max(1, maxUpstreamHop + maxDownstreamHop + 1);
  const maxDepth = Math.max(1, maxUpstreamHop, maxDownstreamHop);
  const width = Math.max(containerWidth, 160 + maxDepth * 240 * 2);
  const centerX = width / 2;
  const layerWidth = Math.min(220, (width - 140) / (maxDepth * 2));

  // 同一层纵向均布，目标公司固定在垂直中心；10 个以上股东时仍保留可辨识的
  // 行距，避免自动缩放后节点和持股标签重叠。
  const maxPerLayer = Math.max(1, ...Array.from(byLayer.values()).map(g => g.length));
  const spacing = maxPerLayer <= 6 ? 88 : Math.max(62, Math.min(74, 760 / maxPerLayer));
  const height = Math.max(620, 120 + maxPerLayer * spacing);
  const radiusScale = maxPerLayer > 10 ? 0.78 : 1;

  const layoutNodes: GraphLayoutNode[] = [];
  byLayer.forEach(group => {
    // 同层采用“风险优先、持股比例其次、名称兜底”的稳定顺序。多跳分支在
    // 每次重渲染时不会随机跳位，且关键主体会更靠近视觉焦点。
    group.sort((a, b) => {
      const riskGap = riskPriority(b.risk_level) - riskPriority(a.risk_level);
      if (riskGap !== 0) return riskGap;
      const ownershipGap =
        (strongestOwnership.get(b.id) ?? 0) - (strongestOwnership.get(a.id) ?? 0);
      if (ownershipGap !== 0) return ownershipGap;
      return a.name.localeCompare(b.name, 'zh-CN');
    });
    group.forEach((n, i) => {
      const x =
        n.direction === 'target'
          ? centerX
          : centerX + (n.direction === 'downstream' ? 1 : -1) * n.hop * layerWidth;
      const y =
        n.direction === 'target'
          ? height / 2
          : 70 + ((height - 140) * (i + 1)) / (group.length + 1);
      const placed = { ...n, x, y };
      layoutNodes.push(placed);
      group[i] = placed;
    });
  });

  return {
    width,
    height,
    nodes: layoutNodes,
    layerCount,
    maxHop,
    upstreamDepth: maxUpstreamHop,
    downstreamDepth: maxDownstreamHop,
    radiusScale,
  };
}

function nodeFill(d: GraphLayoutNode): string {
  // 目标公司始终用深蓝作为阅读锚点；风险级别才使用暖色，正常主体保持中性。
  if (d.nodeType === 'target') return '#1d4ed8';
  if (d.risk_level && ['red', 'orange', 'yellow'].includes(d.risk_level)) {
    return RISK_LEVEL_COLORS[d.risk_level];
  }
  return d.direction === 'downstream' ? '#0f766e' : '#64748b';
}

function nodeInnerText(d: GraphLayoutNode): string {
  if (d.nodeType === 'target') return '目标';
  if (d.direction === 'downstream') return '下';
  if (d.nodeType === 'person') return '人';
  if (d.nodeType === 'fund') return '机构';
  return '';
}

function formatOwnership(ownership: number | null): string {
  return ownership != null ? ` ${ownership.toFixed(2)}%` : '';
}

function tooltipContent(
  d: GraphLayoutNode,
  nodeById: Map<string, GraphLayoutNode>,
  relatedEdges: EquityEdgeDTO[],
): string {
  const directionLabel =
    d.direction === 'downstream'
      ? '下游 · 子公司/被投资企业'
      : d.direction === 'target'
        ? '目标公司'
        : '上游 · 股东/关联方';
  const typeLabel =
    d.nodeType === 'person'
      ? '自然人'
      : d.nodeType === 'fund'
        ? '机构投资者'
        : '公司';
  const risk = d.risk_level
    ? `风险等级：${RISK_LEVEL_LABELS[d.risk_level] || d.risk_level}`
    : '';
  const signals =
    d.risk_signals && d.risk_signals.length > 0
      ? `<div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(128,128,128,.35)">负面风险信号：${d.risk_signals
          .map((s) => s.title)
          .join('；')}</div>`
      : '';
  const relations = relatedEdges
    .slice(0, 3)
    .map((edge) => {
      const isSource = edge.source === d.id;
      const other = nodeById.get(isSource ? edge.target : edge.source)?.name || '关联主体';
      const relation = relationLabel(edge.relation_type);
      return `${isSource ? '持有' : '由'} ${other}${relation}${formatOwnership(edge.ownership_pct ?? edge.control_pct)}`;
    })
    .join('<br/>');
  const relationBlock = relations
    ? `<div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(128,128,128,.35)"><div style="font-size:11px;opacity:.75;margin-bottom:2px">直接股权关系</div>${relations}</div>`
    : '';
  return `<div style="font-weight:600;margin-bottom:4px">${d.name}</div><div>${directionLabel} · ${typeLabel}</div>${risk ? `<div>${risk}</div>` : ''}${relationBlock}${signals}`;
}

function isRiskNode(d: GraphLayoutNode): boolean {
  return d.risk_level === 'red' || d.risk_level === 'orange' || d.risk_level === 'yellow';
}

function shouldShowEdgeLabel(
  edge: EquityEdgeDTO,
  nodeById: Map<string, GraphLayoutNode>,
  showAll: boolean,
): boolean {
  if (showAll) return true;
  if (relationLabel(edge.relation_type) === '控制') return true;
  if ((edge.ownership_pct ?? edge.control_pct ?? 0) >= KEY_OWNERSHIP_PCT) return true;
  const sourceNode = nodeById.get(edge.source);
  const targetNode = nodeById.get(edge.target);
  return (
    (sourceNode !== undefined && sourceNode.nodeType !== 'target' && isRiskNode(sourceNode)) ||
    (targetNode !== undefined && targetNode.nodeType !== 'target' && isRiskNode(targetNode))
  );
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

export function EquityGraph({
  nodes,
  edges,
  targetId,
  downstreamRelations,
  onNodeClick,
}: EquityGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 520 });
  const [showAllEdgeLabels, setShowAllEdgeLabels] = useState(false);

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

  // 8/25 下游风险可视化：把下游（子公司/被投资企业）转成节点+边合并进图，
  // 让股权图在展示上游穿透的同时，也呈现下游主体的风险信号。
  const merged = useMemo(() => {
    const relations = downstreamRelations ?? [];
    if (relations.length === 0) return { nodes, edges };
    // 边 source/target 的语义是 node.id；需定位目标节点的真实 id
    const targetNode = nodes.find((n) => isTargetNode(n, targetId));
    const actualTargetId = targetNode?.id ?? targetId;

    const dsNodes: EquityNodeDTO[] = relations.map((r, i) => {
      const key = r.entity_id || r.wind_code || `ds${i}`;
      const id = `downstream:${key}`;
      return {
        id,
        entity_id: r.entity_id || id,
        name: r.sec_name,
        entity_type: 'Company',
        wind_code: r.wind_code || null,
        match_confidence: null,
        risk_level: r.risk_level ?? 'unknown',
        mock: true,
        source_system: 'downstream',
        risk_signals: r.risk_signals ?? [],
        direction: 'downstream' as const,
      };
    });

    const dsEdges: EquityEdgeDTO[] = relations.map((r, i) => {
      const key = r.entity_id || r.wind_code || `ds${i}`;
      return {
        id: `downstream:edge:${key}`,
        source: actualTargetId,
        target: `downstream:${key}`,
        relation_type: r.relation || '持股',
        ownership_pct: r.ownership_pct,
        control_pct: null,
        valid_from: null,
        valid_to: null,
        source_id: null,
        match_confidence: null,
        relationship_id: null,
        source_record_id: null,
        report_period: null,
        ann_dt: null,
        is_latest: true,
        mock: true,
        source_system: 'downstream',
      };
    });

    return { nodes: [...nodes, ...dsNodes], edges: [...edges, ...dsEdges] };
  }, [nodes, edges, downstreamRelations, targetId]);

  const layout = useMemo(
    () => computeGraphLayout(merged.nodes, merged.edges, targetId, dimensions.width),
    [merged, targetId, dimensions.width],
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
    const nodeById = new Map(layout.nodes.map((node) => [node.id, node]));
    const relatedEdgesByNode = new Map<string, EquityEdgeDTO[]>();
    merged.edges.forEach((edge) => {
      relatedEdgesByNode.set(edge.source, [
        ...(relatedEdgesByNode.get(edge.source) ?? []),
        edge,
      ]);
      relatedEdgesByNode.set(edge.target, [
        ...(relatedEdgesByNode.get(edge.target) ?? []),
        edge,
      ]);
    });

    const graph = new Graph({
      container,
      width: layout.width,
      height: layout.height,
      autoFit: 'view',
      // 为顶部阅读动线、底部图例和节点名称保留画布安全边距，避免首尾节点
      // 被覆盖或裁切；缩放后仍能一屏读出股东层级。
      padding: [68, 128, 140, 120],
      animation: false,
      data: {
        nodes: layout.nodes.map(n => ({
          id: n.id,
          data: { ...n },
        })),
        edges: merged.edges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          data: { ...e },
        })),
      },
      node: {
        type: (d: any) => {
          const node = d.data as GraphLayoutNode;
          if (node.nodeType === 'target') return 'hexagon';
          return isRiskNode(node) ? 'breathing-circle' : 'circle';
        },
        style: {
          x: (d: any) => d.data.x as number,
          y: (d: any) => d.data.y as number,
          size: (d: any) =>
            d.data.nodeType === 'target'
              ? [112, 76]
              : (NODE_RADIUS[d.data.nodeType] || 20) * 2 * layout.radiusScale,
          r: (d: any) => (NODE_RADIUS[d.data.nodeType] || 20) * layout.radiusScale,
          fill: (d: any) => nodeFill(d.data as GraphLayoutNode),
          stroke: '#ffffff',
          lineWidth: (d: any) =>
            d.data.nodeType === 'target'
              ? 3.5
              : isRiskNode(d.data as GraphLayoutNode)
                ? 3.5
                : 2.5,
          fillOpacity: 0.92,
          labelText: (d: any) => {
            const node = d.data as GraphLayoutNode;
            return node.nodeType === 'target'
              ? `${truncateLabel(node.name, 8)}\n目标公司`
              : truncateLabel(node.name, layout.radiusScale < 1 ? 8 : 10);
          },
          labelPlacement: (d: any) =>
            d.data.nodeType === 'target' ? 'center' : 'bottom',
          labelFill: (d: any) =>
            d.data.nodeType === 'target' ? '#ffffff' : textColor,
          labelFontSize: (d: any) =>
            d.data.nodeType === 'target' ? 12 : layout.radiusScale < 1 ? 10 : 11,
          labelFontWeight: (d: any) => (d.data.nodeType === 'target' ? 600 : 400),
          labelLineHeight: 17,
          labelOffsetY: 6,
          iconText: (d: any) =>
            d.data.nodeType === 'target'
              ? ''
              : nodeInnerText(d.data as GraphLayoutNode),
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
            if (!shouldShowEdgeLabel(d.data, nodeById, showAllEdgeLabels)) return '';
            const rel = relationLabel(d.data.relation_type);
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
              const rel = relationLabel(e.relation_type);
              const pct = e.ownership_pct != null ? `${e.ownership_pct.toFixed(1)}%` : '';
              return `<div style="font-weight:600">${rel}${pct ? ` ${pct}` : ''}</div>`;
            }
            return tooltipContent(d, nodeById, relatedEdgesByNode.get(d.id) ?? []);
          },
        },
      ] as any,
    });

    // render 为异步：销毁后完成的 promise 属预期（.catch 吞掉 rejection），
    // 未销毁时若失败则静默降级（图不渲染但页面不崩）。
    const renderPromise = graph.render().catch(() => {
      if (disposed) return;
      // 非销毁导致的失败：清空容器 canvas，避免残留半渲染状态
      container?.querySelectorAll('canvas').forEach(c => c.remove());
    });
    graphRef.current = graph;

    // 节点点击 → 页面级详情弹窗（hover 轻提示已由 tooltip 提供）
    graph.on('node:click', (evt: any) => {
      const id = String(evt?.target?.id ?? '');
      const node = merged.nodes.find(n => String(n.id) === id);
      if (node) onNodeClick?.(node);
    });

    return () => {
      disposed = true;
      if (graphRef.current === graph) graphRef.current = null;
      // G6 v5 render() 异步完成前销毁会在内部打印 “graph instance has been
      // destroyed”。等待当前 render 收束后再清理，避免页面切换时的竞态噪声。
      void renderPromise.finally(() => {
        try {
          graph.destroy();
        } catch {
          /* 已销毁 */
        }
        container?.querySelectorAll('canvas').forEach(c => c.remove());
      });
    };
  }, [layout, merged, showAllEdgeLabels]);

  const handleZoomIn = () => graphRef.current?.zoomBy(1.3);
  const handleZoomOut = () => graphRef.current?.zoomBy(0.7);
  const handleResetZoom = () => graphRef.current?.zoomTo(1);

  return (
    <div ref={containerRef} className="relative border border-border rounded-md bg-muted/20">
      {/* G6 canvas 将挂载于此容器，overlay 元素（图例/按钮）absolute 叠于其上 */}

      {/* 与真实跳数同步的阅读动线，避免把多跳图误读为单层股东表 */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-full border border-border/70 bg-background/90 px-3 py-1 text-[10px] font-medium tracking-wide text-muted-foreground shadow-sm backdrop-blur-sm"
      >
        上游 {layout.upstreamDepth} 层 <span className="px-1.5 text-primary">→</span>
        <span className="text-foreground">目标公司</span>
        <span className="px-1.5 text-primary">→</span> 下游 {layout.downstreamDepth} 层
      </div>

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

      <button
        type="button"
        onClick={() => setShowAllEdgeLabels((value) => !value)}
        className="absolute bottom-3 right-3 z-10 rounded-md border border-border bg-background/90 px-2.5 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur-sm transition-colors hover:bg-muted hover:text-foreground"
        title={showAllEdgeLabels ? '仅保留关键持股比例标签' : '显示全部持股比例标签'}
      >
        {showAllEdgeLabels
          ? '隐藏次要比例'
          : `关键比例 ≥ ${KEY_OWNERSHIP_PCT}%`}
      </button>

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
        分层穿透视图 · 悬停摘要 · 点击查看详情
      </div>
    </div>
  );
}
