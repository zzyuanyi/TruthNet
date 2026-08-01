import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { EquityNode, EquityEdge } from '@/types/truthnet';

interface EquityGraphProps {
  nodes: EquityNode[];
  edges: EquityEdge[];
  companyName: string;
}

const NODE_COLORS: Record<string, string> = {
  target: '#ef4444',
  company: '#f97316',
  person: '#3b82f6',
  fund: '#8b5cf6',
};

const NODE_RADIUS: Record<string, number> = {
  target: 32,
  company: 24,
  person: 20,
  fund: 18,
};

export function EquityGraph({ nodes, edges, companyName }: EquityGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const simulationRef = useRef<d3.Simulation<any, any> | null>(null);

  // Handle resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width } = containerRef.current.getBoundingClientRect();
        setDimensions({ width: Math.max(600, width - 32), height: 500 });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

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
      .attr('refX', 30)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#94a3b8');

    // Transform nodes to include type classification
    const simNodes = nodes.map(n => ({
      ...n,
      nodeType: n.is_target ? 'target' : n.type,
    }));

    // Transform edges to links
    const simLinks = edges.map(e => ({
      ...e,
      source: e.source,
      target: e.target,
    }));

    // Create force simulation
    const simulation = d3.forceSimulation(simNodes as any)
      .force('link', d3.forceLink(simLinks as any).id((d: any) => d.id).distance(140))
      .force('charge', d3.forceManyBody().strength(-500))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(45));

    simulationRef.current = simulation;

    // Draw links
    const link = g.append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', 2)
      .attr('marker-end', 'url(#arrowhead)');

    // Draw link labels
    const linkLabel = g.append('g')
      .selectAll('g')
      .data(simLinks)
      .join('g');

    linkLabel.append('text')
      .attr('font-size', '11px')
      .attr('fill', '#64748b')
      .attr('text-anchor', 'middle')
      .attr('dy', -5)
      .text(d => d.relation);

    linkLabel.append('text')
      .attr('font-size', '10px')
      .attr('fill', '#94a3b8')
      .attr('text-anchor', 'middle')
      .attr('dy', 10)
      .text(d => d.ratio != null ? `${d.ratio.toFixed(1)}%` : '');

    // Draw nodes
    const node = g.append('g')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .call(d3.drag<SVGGElement, any>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // Node circles
    node.append('circle')
      .attr('r', d => NODE_RADIUS[d.nodeType] || 20)
      .attr('fill', d => NODE_COLORS[d.nodeType] || '#6b7280')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2.5)
      .attr('opacity', 0.9);

    // Node labels
    node.append('text')
      .attr('dy', d => (NODE_RADIUS[d.nodeType] || 20) + 16)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('font-weight', '500')
      .attr('fill', '#1e293b')
      .text(d => d.name);

    // Node type labels (inside circle)
    node.append('text')
      .attr('dy', 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('fill', '#fff')
      .attr('font-weight', 'bold')
      .text(d => {
        if (d.nodeType === 'target') return '目标';
        if (d.nodeType === 'person') return '人';
        if (d.nodeType === 'fund') return '机构';
        return '';
      });

    // Tooltip
    node.append('title')
      .text(d => {
        let text = `${d.name}`;
        if (d.nodeType === 'target') text += '\n类型: 目标公司';
        else if (d.nodeType === 'person') text += '\n类型: 自然人';
        else if (d.nodeType === 'fund') text += '\n类型: 机构投资者';
        else text += '\n类型: 公司';
        if (d.share_ratio) text += `\n持股比例: ${d.share_ratio.toFixed(1)}%`;
        return text;
      });

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      linkLabel.attr('transform', (d: any) => 
        `translate(${(d.source.x + d.target.x) / 2},${(d.source.y + d.target.y) / 2})`
      );

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // Store zoom functions for external access
    (svgRef.current as any).__zoomIn = () => svg.transition().duration(300).call(zoom.scaleBy, 1.3);
    (svgRef.current as any).__zoomOut = () => svg.transition().duration(300).call(zoom.scaleBy, 0.7);
    (svgRef.current as any).__resetZoom = () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity);

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, dimensions]);

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
        width={dimensions.width}
        height={dimensions.height}
        className="cursor-grab active:cursor-grabbing"
      />
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
      {/* Legend */}
      <div className="absolute bottom-3 left-3 bg-background/90 backdrop-blur-sm border border-border rounded-md p-2 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span>目标公司</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-orange-500" />
            <span>公司</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span>自然人</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-purple-500" />
            <span>机构</span>
          </div>
        </div>
      </div>
      {/* Hint */}
      <div className="absolute top-3 right-3 bg-background/90 backdrop-blur-sm border border-border rounded-md px-2 py-1 text-xs text-muted-foreground">
        拖拽节点 · 滚轮缩放
      </div>
    </div>
  );
}
