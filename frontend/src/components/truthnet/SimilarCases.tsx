// 织网鉴真 TruthNet - 相似案例展示
// Phase D: 展示财务指标相似的公司案例（不表述为"同类造假"）

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { SimilarCasesResult, SimilarCaseItem } from '@/types/truthnet';
import { GitCompare, AlertTriangle, Info, ExternalLink } from 'lucide-react';

interface SimilarCasesProps {
  data: SimilarCasesResult | null | undefined;
  // 契约修复：相似案例按触发规则携带（FinanceRuleItem.similar_cases），
  // 卡片标题可标注所属规则，避免多规则合并后无法区分口径。
  ruleName?: string;
  className?: string;
}

// IQR 标准化距离没有上界，不能直接用 (1-distance)*100（会出现 -248%）。
// 用单调函数映射到 0-100；低于阈值视为“不相似”，整卡隐藏避免干扰。
const MIN_SIMILARITY = 30;

function similarityFromDistance(distance: number): number {
  const d = Math.max(0, Number.isFinite(distance) ? distance : 99);
  return Math.max(0, Math.round(100 / (1 + d)));
}

export function SimilarCases({ data, ruleName, className }: SimilarCasesProps) {
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

  const visibleCases = (data.cases || [])
    .filter(item => similarityFromDistance(item.distance) >= MIN_SIMILARITY);

  if (visibleCases.length === 0) return null; // 低相似样本不展示

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <GitCompare className="h-4 w-4" />
          相似指标案例
          {ruleName && (
            <Badge variant="outline" className="text-xs">
              {ruleName}
            </Badge>
          )}
          <Badge variant="secondary" className="ml-1 text-xs">
            {visibleCases.length}
          </Badge>
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          以下公司与当前企业在财务指标上存在相似性，仅供参考
        </p>
          {data.cases.length > visibleCases.length && (
            <p className="text-[10px] text-muted-foreground">
              已隐藏 {data.cases.length - visibleCases.length} 条低相似样本
            </p>
          )}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
  
          {visibleCases.map((item, index) => (
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
  const similarity = similarityFromDistance(item.distance);

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
            style={{ width: `${similarity}%` }}
          />
        </div>
        <span className="text-muted-foreground shrink-0">
          相对相似度 {similarity}%
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