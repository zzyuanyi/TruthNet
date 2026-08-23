// 织网鉴真 TruthNet - 上下游企业关系（会1）
// 画像页「相似案例」→「上下游企业关系」：基于股权关联数据识别目标公司的
// 上游（股东/实际控制人/投资方）与下游（子公司/被投资方），并标注数据来源。

import type { ReactNode } from 'react';
import type {
  DownstreamRelation,
  EquityResponseData,
  EquityEdgeDTO,
  EquityNodeDTO,
} from '@/types/truthnet';
import { ArrowUpRight, ArrowDownRight, Building2, ExternalLink, Info } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

// 关系类型中文映射（与 RelatedPartyTable 保持一致）
const RELATION_LABELS: Record<string, string> = {
  OWNS: '持股',
  holding: '控股',
  investment: '投资',
  shareholder: '股东',
  subsidiary: '子公司',
  associate: '联营',
  joint_venture: '合营',
  legal_representative: '法定代表人',
  executive: '高管',
  supervisor: '监事',
  director: '董事',
};

interface RelationEntry {
  node: EquityNodeDTO;
  edge: EquityEdgeDTO;
  direction: 'upstream' | 'downstream';
}

interface UpstreamDownstreamProps {
  equityData: EquityResponseData;
  // 8/23 会1 深化：后端独立下游字段（直接持股子公司/被投资方）
  downstreamRelations?: DownstreamRelation[];
  downstreamTotal?: number;
}

// 8/23：后端 downstream_relations → RelationEntry（复用 RelationRow 渲染）
function buildDownstreamEntries(relations: DownstreamRelation[]): RelationEntry[] {
  return relations.map(r => ({
    node: {
      id: r.entity_id,
      entity_id: r.entity_id,
      name: r.sec_name || r.wind_code || r.entity_id,
      entity_type: r.wind_code ? '上市公司' : '企业',
      wind_code: r.wind_code || null,
      match_confidence: null,
      risk_level: null,
      mock: false,
      source_system: 'neo4j',
    },
    edge: {
      id: `ds-${r.entity_id}`,
      source: '',
      target: r.entity_id,
      relation_type: r.relation || 'OWNS',
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
      mock: false,
      source_system: 'neo4j',
    },
    direction: 'downstream' as const,
  }));
}

// 计算目标公司在股权图里的节点 ID（按 entity_id 对齐）
function resolveTargetNodeId(equityData: EquityResponseData): string | null {
  const targetEntityId = equityData.target?.entity_id;
  if (!targetEntityId) return null;

  // 优先精确匹配 entity_id，其次回退到 name
  const byEntity = equityData.nodes.find(n => n.entity_id === targetEntityId);
  if (byEntity) return byEntity.id;

  const byName = equityData.nodes.find(n => n.name === equityData.target?.name);
  return byName?.id ?? null;
}

// 从边集合中提取上下游关系
function resolveRelations(equityData: EquityResponseData): {
  upstream: RelationEntry[];
  downstream: RelationEntry[];
} {
  const targetNodeId = resolveTargetNodeId(equityData);
  if (!targetNodeId) return { upstream: [], downstream: [] };

  const nodeById = new Map(equityData.nodes.map(n => [n.id, n]));
  const upstream: RelationEntry[] = [];
  const downstream: RelationEntry[] = [];

  for (const edge of equityData.edges) {
    // 上游：边指向目标公司 -> source 是上游（股东/实控人/投资方）
    if (edge.target === targetNodeId && edge.source !== targetNodeId) {
      const node = nodeById.get(edge.source);
      if (node) upstream.push({ node, edge, direction: 'upstream' });
    }
    // 下游：边从目标公司出发 -> target 是下游（子公司/被投资方）
    if (edge.source === targetNodeId && edge.target !== targetNodeId) {
      const node = nodeById.get(edge.target);
      if (node) downstream.push({ node, edge, direction: 'downstream' });
    }
  }

  return { upstream, downstream };
}

// 数据来源标注：来源系统 + 报告期/公告日期
function buildSourceLabel(edge: EquityEdgeDTO): string {
  const parts: string[] = [];
  const system = edge.source_system?.trim();
  if (system) parts.push(system);
  if (edge.report_period) parts.push(`报告期 ${edge.report_period}`);
  else if (edge.ann_dt) parts.push(`公告 ${edge.ann_dt}`);
  return parts.length > 0 ? parts.join(' · ') : '数据来源待补充';
}

function RelationRow({ entry }: { entry: RelationEntry }) {
  const { node, edge } = entry;
  const isUpstream = entry.direction === 'upstream';
  const ownership = edge.ownership_pct ?? edge.control_pct;
  const label = RELATION_LABELS[edge.relation_type] ?? edge.relation_type;
  const typeLabel = node.entity_type?.trim() || '企业';

  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5">
      <div
        className={cn(
          'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md',
          isUpstream
            ? 'bg-primary/10 text-primary'
            : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
        )}
      >
        {isUpstream ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium text-foreground">{node.name}</span>
          <Badge variant="secondary" className="px-1.5 py-0 text-xs">
            {label}
          </Badge>
          <span className="text-xs text-muted-foreground">{typeLabel}</span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {ownership != null && Number.isFinite(ownership) && (
            <span className="tabular-nums">持股比例 {ownership.toFixed(2)}%</span>
          )}
          <span className="inline-flex items-center gap-1">
            <Info className="h-3 w-3" />
            {buildSourceLabel(edge)}
          </span>
        </div>
      </div>
    </div>
  );
}

function RelationGroup({
  title,
  icon,
  entries,
  count,
  emptyHint,
  tone,
}: {
  title: string;
  icon: ReactNode;
  entries: RelationEntry[];
  count?: number;
  emptyHint: string;
  tone: 'upstream' | 'downstream';
}) {
  const displayCount = count ?? entries.length;
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2">
        {icon}
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <span className="text-xs text-muted-foreground">
          {displayCount} 家
          {count !== undefined && count > entries.length
            ? `（展示前 ${entries.length} 条）`
            : ''}
        </span>
      </div>
      {entries.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-background/50 px-3 py-5 text-center text-sm text-muted-foreground">
          {emptyHint}
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(entry => (
            <RelationRow key={`${tone}-${entry.edge.id}-${entry.node.id}`} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

export function UpstreamDownstream({
  equityData,
  downstreamRelations,
  downstreamTotal,
}: UpstreamDownstreamProps) {
  const { upstream, downstream: derivedDownstream } = resolveRelations(equityData);
  // 8/23 会1 深化：优先消费后端独立下游字段（直接持股，含非上市被投资方）；
  // 无字段时回退边推导（旧逻辑）
  const downstream = downstreamRelations
    ? buildDownstreamEntries(downstreamRelations)
    : derivedDownstream;
  const downstreamCount = downstreamTotal ?? downstream.length;
  const total = upstream.length + downstream.length;
  const sourceSystem = equityData.source_system?.trim();

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">上下游企业关系</CardTitle>
          </div>
          {sourceSystem && (
            <Badge variant="outline" className="shrink-0 text-xs font-normal">
              数据来源：{sourceSystem}
            </Badge>
          )}
        </div>
        <CardDescription>
          基于股权关联穿透识别目标公司的上游控制方与下游被投资企业，共关联 {total} 家主体。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <RelationGroup
          title="上游（股东 / 实际控制人 / 投资方）"
          icon={<ArrowUpRight className="h-4 w-4 text-primary" />}
          entries={upstream}
          emptyHint="暂未识别到上游控制方"
          tone="upstream"
        />
        <RelationGroup
          title="下游（子公司 / 被投资企业）"
          icon={<ArrowDownRight className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />}
          entries={downstream}
          count={downstreamCount}
          emptyHint="该公司的直接持股关系暂未覆盖（当前数据以股东关系为主，子公司数据待补充）"
          tone="downstream"
        />
        <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
          关系与持股比例来自股权穿透数据，前十大客户/供应商等经营性上下游披露信息将在后续版本补充。
        </div>
      </CardContent>
    </Card>
  );
}