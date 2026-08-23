// 织网鉴真 TruthNet - 上下游风险信号（会1 改造 8/23）
// 定位：风险视角——识别上下游主体（股东/实控人 + 子公司/被投资企业）
// 的风险信号（负面公告/负面事件簇）；结构视角（多跳/比例）由股权穿透
// 承担。上游（股东/实控人）名单来自穿透图节点（不重复渲染图本身），
// 有风险信号的主体标红，非上市主体标注"数据未覆盖"。

import type { ReactNode } from 'react';
import type {
  DownstreamRelation,
  DownstreamRiskSignal,
  EquityResponseData,
} from '@/types/truthnet';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  ExternalLink,
  Info,
  ShieldQuestion,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const RELATION_LABELS: Record<string, string> = {
  OWNS: '持股',
  holding: '控股',
  investment: '投资',
  shareholder: '股东',
  subsidiary: '子公司',
  associate: '联营',
  joint_venture: '合营',
};

interface UpstreamDownstreamProps {
  equityData: EquityResponseData;
  // 8/23 会1 深化：后端独立下游字段（直接持股子公司/被投资方 + 风险信号）
  downstreamRelations?: DownstreamRelation[];
  downstreamTotal?: number;
}

// 上游关系条目（从穿透图节点推导：指向目标公司的边的 source）
interface UpstreamEntry {
  name: string;
  wind_code: string | null;
  ownership_pct: number | null;
  risk_level: string;
  risk_signals: DownstreamRiskSignal[];
}

// 信号徽标配色
const SIGNAL_TONE: Record<string, string> = {
  red: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30',
  green: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  unknown: 'bg-muted text-muted-foreground border-border',
};

function RiskBadge({ level }: { level?: string }) {
  const tone = SIGNAL_TONE[level ?? 'unknown'] ?? SIGNAL_TONE.unknown;
  const label =
    level === 'red'
      ? '负面信号'
      : level === 'green'
        ? '暂未检出公开风险'
        : '数据未覆盖';
  return (
    <Badge variant="outline" className={cn('gap-1 px-1.5 py-0 text-xs font-normal', tone)}>
      {level === 'red' ? (
        <AlertTriangle className="h-3 w-3" />
      ) : level === 'green' ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <ShieldQuestion className="h-3 w-3" />
      )}
      {label}
    </Badge>
  );
}

function RiskSignalRow({ signal }: { signal: DownstreamRiskSignal }) {
  return (
    <div className="rounded border border-red-500/20 bg-red-500/5 px-2.5 py-1.5 text-xs">
      <div className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
        <AlertTriangle className="h-3 w-3 shrink-0" />
        <span className="font-medium">
          {signal.kind === 'event_cluster' ? '负面事件' : '负面公告'}
        </span>
        {signal.date && <span className="tabular-nums">{signal.date}</span>}
      </div>
      <div className="mt-0.5 line-clamp-2 text-muted-foreground">{signal.title}</div>
    </div>
  );
}

function RiskRow({
  name,
  windCode,
  ownershipPct,
  riskLevel,
  riskSignals,
  icon,
}: {
  name: string;
  windCode: string | null;
  ownershipPct: number | null;
  riskLevel: string;
  riskSignals: DownstreamRiskSignal[];
  icon: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium text-foreground">{name}</span>
          <Badge variant="secondary" className="px-1.5 py-0 text-xs">
            股东
          </Badge>
          {windCode ? (
            <span className="text-xs text-muted-foreground">{windCode}</span>
          ) : (
            <span className="text-xs text-muted-foreground">非上市公司</span>
          )}
          <RiskBadge level={riskLevel} />
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {ownershipPct != null && Number.isFinite(ownershipPct) && (
            <span className="tabular-nums">持股比例 {ownershipPct.toFixed(2)}%</span>
          )}
        </div>
        {riskSignals.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {riskSignals.map((s, i) => (
              <RiskSignalRow key={`${name}-${i}`} signal={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function DownstreamRow({ relation }: { relation: DownstreamRelation }) {
  const signals = relation.risk_signals ?? [];
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
        <ArrowDownRight className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium text-foreground">{relation.sec_name}</span>
          <Badge variant="secondary" className="px-1.5 py-0 text-xs">
            {RELATION_LABELS[relation.relation] ?? relation.relation}
          </Badge>
          {relation.wind_code ? (
            <span className="text-xs text-muted-foreground">{relation.wind_code}</span>
          ) : (
            <span className="text-xs text-muted-foreground">非上市公司</span>
          )}
          <RiskBadge level={relation.risk_level} />
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {relation.ownership_pct != null && Number.isFinite(relation.ownership_pct) && (
            <span className="tabular-nums">持股比例 {relation.ownership_pct.toFixed(2)}%</span>
          )}
        </div>
        {signals.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {signals.map((s, i) => (
              <RiskSignalRow key={`${relation.entity_id}-${i}`} signal={s} />
            ))}
          </div>
        )}
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
}: {
  title: string;
  icon: ReactNode;
  entries: ReactNode[];
  count?: number;
  emptyHint: string;
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
        <div className="space-y-2">{entries}</div>
      )}
    </div>
  );
}

// 从穿透图推导上游（股东/实控人）：指向目标节点的边的 source
function deriveUpstream(equityData: EquityResponseData): UpstreamEntry[] {
  const targetId = equityData.target?.entity_id;
  if (!targetId) return [];
  const nodeById = new Map(equityData.nodes.map(n => [n.id, n]));
  const seen = new Map<string, UpstreamEntry>();
  for (const edge of equityData.edges) {
    if (edge.target !== targetId || edge.source === targetId) continue;
    const node = nodeById.get(edge.source);
    if (!node) continue;
    const name = node.name || edge.source;
    // 已有条目：合并持股比例（多边同源）
    const prev = seen.get(edge.source);
    const pct = edge.ownership_pct ?? edge.control_pct ?? null;
    if (prev) {
      if (pct != null && Number.isFinite(pct)) {
        prev.ownership_pct = (prev.ownership_pct ?? 0) + pct;
      }
      continue;
    }
    seen.set(edge.source, {
      name,
      wind_code: node.wind_code ?? null,
      ownership_pct: pct != null && Number.isFinite(pct) ? pct : null,
      risk_level: node.risk_level ?? 'unknown',
      risk_signals: [],
    });
  }
  return Array.from(seen.values()).sort(
    (a, b) => (b.ownership_pct ?? 0) - (a.ownership_pct ?? 0)
  );
}

export function UpstreamDownstream({
  equityData,
  downstreamRelations,
  downstreamTotal,
}: UpstreamDownstreamProps) {
  // 8/23 改造：优先消费后端独立下游字段（含风险信号）；无字段时回退边推导
  const downstream = downstreamRelations ?? [];
  const downstreamCount = downstreamTotal ?? downstream.length;
  const upstream = deriveUpstream(equityData);
  const redCount =
    downstream.filter(d => d.risk_level === 'red').length +
    upstream.filter(u => u.risk_level === 'red').length;
  const sourceSystem = equityData.source_system?.trim();

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">上下游风险信号</CardTitle>
          </div>
          {sourceSystem && (
            <Badge variant="outline" className="shrink-0 text-xs font-normal">
              数据来源：{sourceSystem}
            </Badge>
          )}
        </div>
        <CardDescription>
          风险视角：上游（股东/实控人）与下游（被投资企业）聚合负面公告/
          负面事件簇信号；共关联 {upstream.length + downstreamCount} 家
          {redCount > 0 ? `，其中 ${redCount} 家检出负面信号` : ''}。
          多跳结构与完整持股比例见股权穿透图。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <RelationGroup
          title="上游（股东 / 实际控制人）"
          icon={<ArrowUpRight className="h-4 w-4 text-primary" />}
          entries={upstream.map(u => (
            <RiskRow
              key={`up-${u.name}`}
              name={u.name}
              windCode={u.wind_code}
              ownershipPct={u.ownership_pct}
              riskLevel={u.risk_level}
              riskSignals={u.risk_signals}
              icon={<ArrowUpRight className="h-4 w-4" />}
            />
          ))}
          emptyHint="暂未识别到上游控制方（股东/实控人）"
        />
        <RelationGroup
          title="下游（子公司 / 被投资企业）"
          icon={<ArrowDownRight className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />}
          entries={downstream.map(rel => (
            <DownstreamRow key={`${rel.entity_id}-${rel.sec_name}`} relation={rel} />
          ))}
          count={downstreamCount}
          emptyHint="该公司的直接持股关系暂未覆盖（当前数据以股东关系为主，子公司数据待补充）"
        />
        <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          <Info className="h-3.5 w-3.5 shrink-0" />
          <span>
            风险信号来自负面公告库与负面事件簇（可回查证据）；「暂未检出公开风险」指上市主体
            当前无负面记录，「数据未覆盖」指非上市主体无公开数据。前十大客户/供应商等经营性
            上下游披露信息将在后续版本补充。
          </span>
        </div>
        {redCount > 0 && (
          <div className="flex items-center gap-2 rounded-md bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400">
            <ExternalLink className="h-3.5 w-3.5 shrink-0" />
            检出 {redCount} 家上下游主体存在负面信号，建议结合公司公告原文核验。
          </div>
        )}
      </CardContent>
    </Card>
  );
}
