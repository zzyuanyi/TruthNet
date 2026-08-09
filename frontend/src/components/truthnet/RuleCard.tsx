// 织网鉴真 TruthNet - 规则卡片组件
// Phase 2: 规则卡 + Recharts 折线图

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { AlertTriangle, CheckCircle, HelpCircle, TrendingUp } from 'lucide-react';
import type { FinanceRuleItem, RiskLevel } from '@/types/truthnet';
import { cn } from '@/lib/utils';

interface RuleCardProps {
  rule: FinanceRuleItem;
  onViewEvidence?: (ruleId: string) => void;
  onViewDetail?: (ruleId: string) => void;
}

// 风险等级颜色映射
const riskLevelColors: Record<RiskLevel, string> = {
  red: 'bg-red-500/10 text-red-600 border-red-500/20',
  orange: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
  blue: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  green: 'bg-green-500/10 text-green-600 border-green-500/20',
  unknown: 'bg-gray-500/10 text-gray-600 border-gray-500/20',
};

const riskLevelBadgeColors: Record<RiskLevel, string> = {
  red: 'bg-red-500',
  orange: 'bg-orange-500',
  yellow: 'bg-yellow-500',
  blue: 'bg-blue-500',
  green: 'bg-green-500',
  unknown: 'bg-gray-500',
};

// 状态图标映射
const statusIcons = {
  triggered: <AlertTriangle className="h-4 w-4 text-red-500" />,
  not_triggered: <CheckCircle className="h-4 w-4 text-green-500" />,
  not_applicable: <HelpCircle className="h-4 w-4 text-gray-500" />,
  insufficient_data: <HelpCircle className="h-4 w-4 text-yellow-500" />,
};

// 状态文本映射
const statusLabels = {
  triggered: '已触发',
  not_triggered: '未触发',
  not_applicable: '不适用',
  insufficient_data: '数据不足',
};

// 图表指标映射：rule_id → history 数值字段 + 行业基准 metric_id
// R6/R7 无配置（R7 无行业指标）→ 回退找第一个数值字段
const chartMetricConfig: Partial<Record<string, { seriesKey: string; benchmarkId: string }>> = {
  R1: { seriesKey: 'gap', benchmarkId: 'r1_gap' },
  R2: { seriesKey: 'cf_to_profit_ratio', benchmarkId: 'r2_cf_ratio' },
  R3: { seriesKey: 'cash_to_assets', benchmarkId: 'r3_cash_to_assets' },
  R4: { seriesKey: 'growth_gap', benchmarkId: 'r4_growth_gap' },
  R5: { seriesKey: 'gross_margin', benchmarkId: 'r5_gross_margin' },
};

// history 值可能是裸数值（R1）或 {value, unit} 对象（R2-R7 由 rule_engine 兜底填充 current），统一提取
function extractSeriesValue(item: Record<string, unknown>, key: string): number | null {
  const v = item[key];
  if (typeof v === 'number') return v;
  if (v && typeof v === 'object' && typeof (v as { value?: unknown }).value === 'number') {
    return (v as { value: number }).value;
  }
  return null;
}

export function RuleCard({ rule, onViewEvidence, onViewDetail }: RuleCardProps) {
  const chartConfig = chartMetricConfig[rule.rule_id];
  // 动态从 history 中提取折线图数据（优先配置的 seriesKey，R6/R7 回退找第一个数值字段）
  const chartData = rule.history.map(item => {
    const period = (item.period as string) || '';
    let valueKey: string | undefined;
    let value: number | null = null;
    if (chartConfig) {
      valueKey = chartConfig.seriesKey;
      value = extractSeriesValue(item, chartConfig.seriesKey);
    } else {
      valueKey = Object.keys(item).find(k => k !== 'period' && extractSeriesValue(item, k) !== null);
      value = valueKey ? extractSeriesValue(item, valueKey) : null;
    }
    return { period, value, valueKey };
  });
  // 获取用于展示的指标名
  const chartMetricName = chartData.length > 0 && chartData[0].valueKey
    ? chartData[0].valueKey
    : Object.keys(rule.current)[0];

  // 行业基准参考指标（按配置 benchmarkId 从 typed industry_metrics 找，不再读已废弃 rule.industry）
  const benchmarkMetric = chartConfig
    ? rule.industry_metrics?.find(m => m.metric_id === chartConfig.benchmarkId)
    : undefined;

  // 当前值指标：优先图表配置的 seriesKey（R1 gap / R4 growth_gap 与折线、P50 可比），无配置时取第一个
  const preferredMetric = chartConfig?.seriesKey;
  const currentMetric =
    preferredMetric && preferredMetric in rule.current
      ? preferredMetric
      : Object.keys(rule.current)[0];
  const currentValue = currentMetric ? rule.current[currentMetric] : undefined;

  return (
    <Card className={cn(
      'transition-all hover:shadow-md',
      rule.status === 'triggered' && 'border-red-500/50'
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {statusIcons[rule.status]}
            <CardTitle className="text-sm font-medium">
              {rule.rule_name}
            </CardTitle>
          </div>
          <Badge
            variant="outline"
            className={cn(
              'text-xs',
              riskLevelColors[rule.severity]
            )}
          >
            <span className={cn(
              'w-2 h-2 rounded-full mr-1',
              riskLevelBadgeColors[rule.severity]
            )} />
            {rule.severity === 'red' ? '高危' :
             rule.severity === 'orange' ? '中高危' :
             rule.severity === 'yellow' ? '中等' :
             rule.severity === 'blue' ? '低风险' : '正常'}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 当前值与行业基准（industry_metrics typed 分位，R3/R4/R5 多指标逐行） */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-muted-foreground mb-1">当前值</div>
            <div className="text-lg font-semibold">
              {typeof currentValue?.value === 'number' ? currentValue.value.toFixed(2) : '--'}
              <span className="text-xs text-muted-foreground ml-1">
                {currentValue?.unit}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              {currentMetric}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">行业基准</div>
            {rule.industry_metrics && rule.industry_metrics.length > 0 ? (
              rule.industry_metrics.map(m => (
                <div key={m.metric_id} className="text-xs leading-5">
                  <span className="font-medium">
                    {m.label}: P50 {m.p50 != null ? m.p50.toFixed(2) : '--'} |
                    P75 {m.p75 != null ? m.p75.toFixed(2) : '--'} |
                    P95 {m.p95 != null ? m.p95.toFixed(2) : '--'}
                  </span>
                  <span className="text-muted-foreground ml-1">
                    {m.company_percentile != null ? `(分位 ${m.company_percentile.toFixed(1)}%)` : ''}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-sm text-muted-foreground">--</div>
            )}
          </div>
        </div>

        {/* 折线图 */}
        <div className="h-32 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 10 }}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                className="text-muted-foreground"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px'
                }}
              />
              {/* 行业基准参考线（仅指标匹配且有 P50 时显示，不再读已废弃 rule.industry） */}
              {typeof benchmarkMetric?.p50 === 'number' && (
                <ReferenceLine
                  y={benchmarkMetric.p50}
                  stroke="hsl(var(--muted-foreground))"
                  strokeDasharray="3 3"
                  label={{ value: 'P50', position: 'right', fontSize: 10 }}
                />
              )}
              <Line
                type="monotone"
                dataKey="value"
                stroke={
                  rule.severity === 'red' ? '#ef4444' :
                  rule.severity === 'orange' ? '#f97316' :
                  rule.severity === 'yellow' ? '#eab308' :
                  rule.severity === 'blue' ? '#3b82f6' : '#22c55e'
                }
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* 说明文字 */}
        <p className="text-xs text-muted-foreground line-clamp-2">
          {rule.explanation}
        </p>

        {/* 操作按钮 */}
        <div className="flex gap-2 pt-2">
          {onViewEvidence && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => onViewEvidence(rule.rule_id)}
            >
              查看证据 ({rule.evidence_ids.length})
            </Button>
          )}
          {onViewDetail && (
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => onViewDetail(rule.rule_id)}
            >
              <TrendingUp className="h-3 w-3 mr-1" />
              查看详情
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// 规则卡片列表组件
interface RuleCardListProps {
  rules: FinanceRuleItem[];
  onViewEvidence?: (ruleId: string) => void;
  onViewDetail?: (ruleId: string) => void;
}

export function RuleCardList({ rules, onViewEvidence, onViewDetail }: RuleCardListProps) {
  // 按状态排序：triggered 优先
  const sortedRules = [...rules].sort((a, b) => {
    if (a.status === 'triggered' && b.status !== 'triggered') return -1;
    if (a.status !== 'triggered' && b.status === 'triggered') return 1;
    return 0;
  });

  return (
    <div className="space-y-3">
      {sortedRules.map(rule => (
        <RuleCard
          key={rule.rule_id}
          rule={rule}
          onViewEvidence={onViewEvidence}
          onViewDetail={onViewDetail}
        />
      ))}
    </div>
  );
}
