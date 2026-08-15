// 织网鉴真 TruthNet - 相似案例展示
// Phase D: 展示财务指标相似的公司案例（不表述为"同类造假"）

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { SimilarCasesResult, SimilarCaseItem } from '@/types/truthnet';
import { GitCompare, AlertTriangle, Info, ExternalLink } from 'lucide-react';

interface SimilarCasesProps {
  data: SimilarCasesResult | null | undefined;
  className?: string;
}

export function SimilarCases({ data, className }: SimilarCasesProps) {
  if (!data) return null;

  if (data.status === 'not_supported' || data.status === 'empty') {
    return null; // 静默降级，不展示空白卡片
  }

  if (data.status === 'error') {
    return (
      <Card className={cn('border-destructive/30', className)}>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            相似案例检索失败
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">{data.reason || '未知错误'}</p>
        </CardContent>
      </Card>
    );
  }

  if (data.cases.length === 0) return null;

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <GitCompare className="h-4 w-4" />
          相似指标案例
          <Badge variant="secondary" className="ml-1 text-xs">
            {data.cases.length}
          </Badge>
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          以下公司与当前企业在财务指标上存在相似性，仅供参考
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {data.cases.map((item, index) => (
            <SimilarCaseCard key={`${item.company_code}-${index}`} item={item} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function SimilarCaseCard({ item }: { item: SimilarCaseItem }) {
  const metricEntries = Object.entries(item.metric || {});
  const mainMetric = metricEntries[0];

  return (
    <div className="p-3 rounded-lg border bg-card hover:bg-muted/30 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{item.company_name}</span>
          <Badge variant="outline" className="text-xs">
            {item.industry}
          </Badge>
        </div>
        <span className="text-xs text-muted-foreground">{item.period}</span>
      </div>

      {/* 主要指标 */}
      {mainMetric && (
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs text-muted-foreground">{mainMetric[0]}</span>
          <span className="text-sm font-mono font-medium">{String(mainMetric[1])}</span>
        </div>
      )}

      {/* 相似度 */}
      <div className="flex items-center gap-2 text-xs">
        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary/60"
            style={{ width: `${Math.max(0, Math.min(100, (1 - item.distance) * 100))}%` }}
          />
        </div>
        <span className="text-muted-foreground shrink-0">
          相似度 {(1 - item.distance * 100).toFixed(0)}%
        </span>
      </div>

      {/* 其他指标 */}
      {metricEntries.length > 1 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {metricEntries.slice(1).map(([key, val]) => (
            <span key={key} className="text-xs text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
              {key}: {String(val)}
            </span>
          ))}
        </div>
      )}

      {/* 来源 */}
      {item.evidence_ids && item.evidence_ids.length > 0 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground/60">
          <Info className="h-3 w-3" />
          {item.evidence_ids.length} 条来源
        </div>
      )}
    </div>
  );
}

export default SimilarCases;