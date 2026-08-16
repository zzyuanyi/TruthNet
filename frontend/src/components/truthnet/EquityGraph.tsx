import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
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
      byHop.set(h, byHop.get(h)!);
      const arr = byHop.get(h)!;
      arr[i] = placed;
    });
  });

  return { width, height, nodes: layoutNodes, layerCount, maxHop, radiusScale };
}


export function EquityGraph({ nodes, edges, targetId }: EquityGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
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


  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
      return; // 旧布局逻辑已被下方 computeGraphLayout effect 替代（保留仅为最小 diff）

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { width, height } = dimensions;

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    const g = svg.append('g');

    // Create arrow markers
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#94a3b8');

    // ── C2（8/9 老师要求）：按距目标公司的 hop 分层布局 ──
    // 1) 无向 BFS 计算每个节点距目标公司的跳数（不可达节点排到最右）
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

    // 2) 每层内纵向均布（x 按 hop 从左到右）
    const byHop = new Map<number, (EquityNodeDTO & { nodeType: string })[]>();
    nodes.forEach(n => {
      const nodeType = (n.id === targetId || n.entity_id === targetId)
        ? 'target'
        : mapEntityType(n.entity_type || '');
      const h = hops.get(n.id)!;
      if (!byHop.has(h)) byHop.set(h, []);
      byHop.get(h)!.push({ ...n, nodeType });
    });

    const layerCount = Math.max(1, ...byHop.keys());
    const layerWidth = (width - 120) / layerCount;
    const layout = new Map<string, { x: number; y: number }>();
    byHop.forEach((group, h) => {
      const x = 70 + h * layerWidth;
      const spacing = Math.min(95, (height - 90) / Math.max(1, group.length));
      group.forEach((n, i) => {
        layout.set(n.id, { x, y: 55 + spacing * (i + 0.5) });
      });
    });

    // 3) 连线（股东 → 被持股公司，标注关系类型与持股比例）
    const link = g.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', 1.8)
      .attr('stroke-opacity', 0.7)
      .attr('marker-end', 'url(#arrowhead)')
      .attr('x1', (d: any) => layout.get(d.source)?.x ?? 0)
      .attr('y1', (d: any) => layout.get(d.source)?.y ?? 0)
      .attr('x2', (d: any) => layout.get(d.target)?.x ?? 0)
      .attr('y2', (d: any) => layout.get(d.target)?.y ?? 0);

    const linkLabel = g.append('g')
      .selectAll('g')
      .data(edges)
      .join('g')
      .attr('transform', (d: any) => {
        const s = layout.get(d.source) || { x: 0, y: 0 };
        const t = layout.get(d.target) || { x: 0, y: 0 };
        return `translate(${(s.x + t.x) / 2},${(s.y + t.y) / 2})`;
      });

    linkLabel.append('text')
      .attr('font-size', '10px')
      .attr('fill', '#64748b')
      .attr('text-anchor', 'middle')
      .attr('dy', -4)
      .text((d: any) => d.relation_type || '持股');

    linkLabel.append('text')
      .attr('font-size', '11px')
      .attr('font-weight', '600')
      .attr('fill', '#475569')
      .attr('text-anchor', 'middle')
      .attr('dy', 10)
      .text((d: any) => (d.ownership_pct != null ? `${d.ownership_pct.toFixed(1)}%` : ''));

    // 4) 节点（固定分层坐标，颜色按风险等级；未评级回退灰色/目标红）
    const node = g.append('g')
      .selectAll('g')
      .data(Array.from(byHop.values()).flat())
      .join('g')
      .attr('transform', (d: any) => {
        const p = layout.get(d.id) || { x: 0, y: 0 };
        return `translate(${p.x},${p.y})`;
      });

    node.append('circle')
      .attr('r', (d: any) => NODE_RADIUS[d.nodeType] || 20)
      .attr('fill', (d: any) => {
        if (d.risk_level && RISK_LEVEL_COLORS[d.risk_level]) return RISK_LEVEL_COLORS[d.risk_level];
        return d.nodeType === 'target' ? '#ef4444' : '#94a3b8';
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 2.5)
      .attr('opacity', 0.92);

    // 层级标注（第 0 层 = 目标公司，逐层向外）
    node.append('text')
      .attr('dy', (d: any) => (NODE_RADIUS[d.nodeType] || 20) + 15)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('font-weight', '500')
      .attr('fill', '#1e293b')
      .text((d: any) => d.name);

    node.append('text')
      .attr('dy', 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('fill', '#fff')
      .attr('font-weight', 'bold')
      .text((d: any) => {
        if (d.nodeType === 'target') return '目标';
        if (d.nodeType === 'person') return '人';
        if (d.nodeType === 'fund') return '机构';
        return '';
      });

    node.append('title')
      .text((d: any) => {
        let text = `${d.name}`;
        if (d.nodeType === 'target') text += '\n类型: 目标公司';
        else if (d.nodeType === 'person') text += '\n类型: 自然人';
        else if (d.nodeType === 'fund') text += '\n类型: 机构投资者';
        else text += '\n类型: 公司';
        if (d.risk_level) text += `\n风险等级: ${RISK_LEVEL_LABELS[d.risk_level] || d.risk_level}`;
        return text;
      });

    // 层级列标注（第 0 层/第 N 层）
    g.append('text')
      .attr('x', 70)
      .attr('y', 22)
      .attr('font-size', '11px')
      .attr('fill', '#64748b')
      .text('目标公司');

    if (layerCount >= 1) {
      g.append('text')
        .attr('x', 70 + layerCount * layerWidth)
        .attr('y', 22)
        .attr('text-anchor', 'end')
        .attr('font-size', '11px')
        .attr('fill', '#64748b')
        .text(`第 ${layerCount} 层（向上穿透）`);
    }

    // Store zoom functions for external access
    (svgRef.current as any).__zoomIn = () => svg.transition().duration(300).call(zoom.scaleBy, 1.3);
    (svgRef.current as any).__zoomOut = () => svg.transition().duration(300).call(zoom.scaleBy, 0.7);
    (svgRef.current as any).__resetZoom = () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity);

    return () => {
      svg.selectAll('*').remove();
    };
  }, [nodes, edges, dimensions, targetId]);

  // 2026-08-16 修复：使用 computeGraphLayout 预计算动态宽高/间距；
  // 先创建 g 再注册 zoom，并显式设置 touch-action/pointer-events，
  // 解决江苏新能等大图"拖不动、字符重叠"问题。
  useEffect(() => {
    if (!svgRef.current || layout.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { width, height, nodes: layoutNodes, layerCount, radiusScale } = layout;
    const position = new Map(layoutNodes.map(n => [n.id, { x: n.x, y: n.y }]));

    svg
      .attr('width', width)
      .attr('height', height)
      .style('touch-action', 'none')
      .attr('pointer-events', 'all');

    const g = svg.append('g');

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 4])
      .filter((event: any) => {
        if (event.type === 'wheel') return true;
        return event.type === 'mousedown' ? event.button === 0 : !event.button;
      })
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom).on('dblclick.zoom', null);

    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#94a3b8');

    const link = g.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', 1.6)
      .attr('stroke-opacity', 0.65)
      .attr('marker-end', 'url(#arrowhead)')
      .attr('x1', (d: any) => position.get(d.source)?.x ?? 0)
      .attr('y1', (d: any) => position.get(d.source)?.y ?? 0)
      .attr('x2', (d: any) => position.get(d.target)?.x ?? 0)
      .attr('y2', (d: any) => position.get(d.target)?.y ?? 0);

    const linkLabel = g.append('g')
      .selectAll('g')
      .data(edges)
      .join('g')
      .attr('transform', (d: any) => {
        const s = position.get(d.source) || { x: 0, y: 0 };
        const t = position.get(d.target) || { x: 0, y: 0 };
        return `translate(${(s.x + t.x) / 2},${(s.y + t.y) / 2})`;
      });

    linkLabel.append('text')
      .attr('font-size', '10px')
      .style('fill', 'var(--color-foreground)')
      .style('paint-order', 'stroke')
      .style('stroke', 'var(--color-background)')
      .style('stroke-width', 3)
      .style('stroke-linejoin', 'round')
      .attr('text-anchor', 'middle')
      .attr('dy', -1)
      .text((d: any) => d.relation_type || '持股');

    linkLabel.append('text')
      .attr('font-size', '10px')
      .attr('font-weight', '600')
      .style('fill', 'var(--color-foreground)')
      .style('paint-order', 'stroke')
      .style('stroke', 'var(--color-background)')
      .style('stroke-width', 3)
      .style('stroke-linejoin', 'round')
      .attr('text-anchor', 'middle')
      .attr('dy', 9)
      .text((d: any) => (d.ownership_pct != null ? `${d.ownership_pct.toFixed(1)}%` : ''));

    const node = g.append('g')
      .selectAll('g')
      .data(layoutNodes)
      .join('g')
      .attr('transform', (d: any) => `translate(${d.x},${d.y})`);

    node.append('circle')
      .attr('r', (d: any) => (NODE_RADIUS[d.nodeType] || 20) * radiusScale)
      .attr('fill', (d: any) => {
        if (d.risk_level && RISK_LEVEL_COLORS[d.risk_level]) return RISK_LEVEL_COLORS[d.risk_level];
        return d.nodeType === 'target' ? '#ef4444' : '#94a3b8';
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 2.5)
      .attr('opacity', 0.92);

    // 节点名称放在圆下方，用前景色 + 背景描边 halo（CSS 变量经 style 注入；本主题变量为 --color-*）
    node.append('text')
        .attr('class', 'equity-node-name')
      .attr('dy', (d: any) => (NODE_RADIUS[d.nodeType] || 20) * radiusScale + 14)
      .attr('text-anchor', 'middle')
      .attr('font-size', radiusScale < 1 ? '10px' : '11px')
      .attr('font-weight', '500')
      .style('fill', 'var(--color-foreground)')
      .style('paint-order', 'stroke')
      .style('stroke', 'var(--color-background)')
      .style('stroke-width', 3)
      .style('stroke-linejoin', 'round')
      .text((d: any) => truncateLabel(d.name, radiusScale < 1 ? 8 : 10))

    node.append('text')
      .attr('dy', 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('fill', '#fff')
      .attr('font-weight', 'bold')
      .text((d: any) => {
        if (d.nodeType === 'target') return '目标';
        if (d.nodeType === 'person') return '人';
        if (d.nodeType === 'fund') return '机构';
        return '';
      });

    node.append('title')
      .text((d: any) => {
        let text = `${d.name}（第 ${d.hop} 层）`;
        if (d.nodeType === 'target') text += '\n类型: 目标公司';
        else if (d.nodeType === 'person') text += '\n类型: 自然人';
        else if (d.nodeType === 'fund') text += '\n类型: 机构投资者';
        else text += '\n类型: 公司';
        if (d.risk_level) text += `\n风险等级: ${RISK_LEVEL_LABELS[d.risk_level] || d.risk_level}`;
        return text;
      });

    g.append('text')
      .attr('x', 70)
      .attr('y', 22)
      .attr('font-size', '11px')
      .attr('fill', '#64748b')
      .text('目标公司');

    if (layerCount >= 1) {
      g.append('text')
        .attr('x', width - 90)
        .attr('y', 22)
        .attr('text-anchor', 'end')
        .attr('font-size', '11px')
        .attr('fill', '#64748b')
        .text(`第 ${layout.maxHop} 层（向上穿透）`);
    }

    (svgRef.current as any).__zoomIn = () => svg.transition().duration(300).call(zoom.scaleBy, 1.3);
    (svgRef.current as any).__zoomOut = () => svg.transition().duration(300).call(zoom.scaleBy, 0.7);
    (svgRef.current as any).__resetZoom = () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity);

    return () => {
      svg.selectAll('*').remove();
    };
  }, [layout, edges]);


  const handleZoomIn = () => {
    if (svgRef.current && (svgRef.current as any).__zoomIn) {
      (svgRef.current as any).__zoomIn();
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current && (svgRef.current as any).__zoomOut) {
      (svgRef.current as any).__zoomOut();
    }
  };

  const handleResetZoom = () => {
    if (svgRef.current && (svgRef.current as any).__resetZoom) {
      (svgRef.current as any).__resetZoom();
    }
  };

  return (
    <div ref={containerRef} className="relative border border-border rounded-md bg-muted/20">
      <svg
        ref={svgRef}
        width={layout.width}
        height={layout.height}
        className="cursor-grab active:cursor-grabbing text-foreground" style={{ touchAction: 'none' }}
      />

      {/* 风险等级图例（节点颜色语义） */}
      <div className="absolute bottom-3 left-3 flex flex-wrap gap-2 bg-background/90 backdrop-blur-sm border border-border rounded-md p-2 text-xs">
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
      <div className="absolute top-3 left-3 flex flex-col gap-1">
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
      <div className="absolute top-3 right-3 bg-background/90 backdrop-blur-sm border border-border rounded-md px-2 py-1 text-xs text-muted-foreground">
        分层穿透视图 · 滚轮缩放 · 拖拽平移
      </div>
    </div>
  );
}
