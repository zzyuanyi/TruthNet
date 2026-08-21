// 织网鉴真 TruthNet - 股权隐含关系解读（会2）
// 在股权穿透图下方补充「发现了什么」分析段落，不只画图。
// 数据来源优先后端文案（coverage_note / equity_chains.risk_reasons），
// 并叠加前端结构性检测（交叉持股、穿透深度、高持股、实控人识别）。

import type { EquityResponseData, EquityEdgeDTO, EquityNodeDTO } from '@/types/truthnet';
import { Sparkles, AlertCircle, ShieldCheck, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface EquityInsightProps {
  equityData: EquityResponseData;
}

// 邻接表 DFS 检测循环持股（与 RelatedPartyTable 逻辑一致，独立实现避免耦合）
function hasCircularHolding(edges: EquityEdgeDTO[]): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    if (!edge.source || !edge.target) continue;
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    adjacency.get(edge.source)!.push(edge.target);
  }

  const visited = new Set<string>();
  const stack = new Set<string>();

  const dfs = (nodeId: string): boolean => {
    if (stack.has(nodeId)) return true;
    if (visited.has(nodeId)) return false;
    visited.add(nodeId);
    stack.add(nodeId);
    for (const neighbor of adjacency.get(nodeId) ?? []) {
      if (dfs(neighbor)) return true;
    }
    stack.delete(nodeId);
    return false;
  };

  for (const nodeId of adjacency.keys()) {
    if (dfs(nodeId)) return true;
  }
  return false;
}

function maxPathDepth(equityData: EquityResponseData): number {
  const paths = equityData.paths ?? [];
  if (paths.length === 0) return equityData.max_observed_hops ?? 0;
  return Math.max(...paths.map(p => p.depth || 0));
}

interface Finding {
  level: 'red' | 'orange' | 'blue' | 'neutral';
  text: string;
}

function buildFindings(equityData: EquityResponseData): Finding[] {
  const findings: Finding[] = [];
  const { edges, nodes } = equityData;

  // 1. 后端穿透覆盖说明（若有）
  const coverageNote = equityData.coverage_note?.trim();
  if (coverageNote) {
    findings.push({ level: 'neutral', text: coverageNote });
  }

  // 2. 后端链路风险文案（去重）
  const chains = equityData.equity_chains ?? [];
  const reasons: string[] = [];
  for (const chain of chains) {
    const level = String((chain as Record<string, unknown>).risk_level ?? 'green');
    if (!['red', 'orange', 'yellow'].includes(level)) continue;
    const rs = (chain as Record<string, unknown>).risk_reasons;
    if (Array.isArray(rs)) {
      for (const r of rs) {
        const t = String(r ?? '').trim();
        if (t && !reasons.includes(t)) reasons.push(t);
      }
    }
  }
  for (const reason of reasons.slice(0, 4)) {
    findings.push({ level: 'orange', text: reason });
  }

  // 3. 交叉持股检测
  if (hasCircularHolding(edges)) {
    findings.push({ level: 'red', text: '检测到循环持股结构，可能存在资本虚增或控制关系隐藏风险。' });
  }

  // 4. 穿透深度
  const depth = maxPathDepth(equityData);
  if (depth > 3) {
    findings.push({ level: 'orange', text: `股权穿透深度达 ${depth} 层，多层嵌套结构使真实控制关系更隐蔽。` });
  }

  // 5. 高持股比例
  const highOwnershipEdges = edges.filter(e => (e.ownership_pct ?? 0) > 50);
  if (highOwnershipEdges.length > 0) {
    findings.push({ level: 'blue', text: `存在 ${highOwnershipEdges.length} 条持股超过 50% 的关系，形成绝对控股。` });
  }

  // 6. 结构概览（兜底）
  if (findings.length === 0) {
    findings.push({
      level: 'neutral',
      text: `共 ${nodes.length} 个关联主体、${edges.length} 条持股关系，未发现显著的结构性风险信号。`,
    });
  }

  return findings;
}

export function EquityInsight({ equityData }: EquityInsightProps) {
  const findings = buildFindings(equityData);
  const hasRisk = findings.some(f => f.level === 'red' || f.level === 'orange');

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">发现了什么</CardTitle>
          <Badge variant={hasRisk ? 'destructive' : 'secondary'} className="text-xs">
            {hasRisk ? '识别到风险信号' : '结构基本正常'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {findings.map((finding, index) => {
          const icon =
            finding.level === 'red' ? (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500 animate-pulse" />
            ) : finding.level === 'orange' ? (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-orange-500 animate-pulse" />
            ) : finding.level === 'blue' ? (
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
            ) : (
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            );
          return (
            <div key={index} className="flex items-start gap-2.5 rounded-md bg-muted/40 px-3 py-2.5">
              {icon}
              <p className="text-sm leading-6 text-foreground">{finding.text}</p>
            </div>
          );
        })}
        <p className="pt-1 text-xs text-muted-foreground">
          解读结合股权穿透链路、持股比例与后端风险判定综合生成，仅供参考，不构成投资建议。
        </p>
      </CardContent>
    </Card>
  );
}