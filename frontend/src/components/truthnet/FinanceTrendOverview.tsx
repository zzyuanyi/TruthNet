// 织网鉴真 TruthNet - 核心财务指标趋势总览
// 会4 补全：多指标 sparkline 总览，一眼看清核心指标跨期趋势

import { useMemo } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import type { FinanceRuleItem } from '@/types/truthnet';

interface FinanceTrendOverviewProps {
  rules: FinanceRuleItem[];
}

// 与 RuleCard 保持一致的核心指标映射（rule_id → history 数值字段）
const chartMetricConfig: Partial<Record<string, { seriesKey: string }>> = {
  R1: { seriesKey: 'gap' },
  R2: { seriesKey: 'cf_to_profit_ratio' },
  R3: { seriesKey: 'cash_to_assets' },
  R4: { seriesKey: 'growth_gap' },
  R5: { seriesKey: 'gross_margin' },
};

const displayUnit: Record<string, string> = {
  percent: '%',
  percentage_point: '%',
  ratio: '',
  quarters: '个季度',
  days: '天',
  bool: '',
  yuan: '元',
  times: '倍',
};

function extractSeriesValue(item: Record<string, unknown>, key: string): number | null {
  const v = item[key];
  if (typeof v === 'number') return v;
  if (v && typeof v === 'object' && typeof (v as { value?: unknown }).value === 'number') {
    return (v as { value: number }).value;
  }
  return null;
}

function formatValue(value: number, unit?: string): string {
  const digits = unit === 'ratio' ? 2 : unit === 'percent' || unit === 'percentage_point' || unit === 'days' ? 1 : 0;
  const u = unit ? (displayUnit[unit] ?? unit) : '';
  return `${value.toFixed(digits)}${u}`;
}

// 期次显示：20251231 → 2025-12；2025-12-31 → 2025-12（缩略图 tooltip 用短格式）
function formatPeriod(period: string): string {
  if (/^\d{8}$/.test(period)) return `${period.slice(0, 4)}-${period.slice(4, 6)}`;
  if (/^\d{4}-\d{2}/.test(period)) return period.slice(0, 7);
  return period;
}

const severityStroke: Record<string, string> = {
  red: '#ef4444',
  orange: '#f97316',
  yellow: '#eab308',
  blue: '#3b82f6',
  green: '#22c55e',
  unknown: '#94a3b8',
};

function getSeverityColor(severity: string): string {
  return severityStroke[severity] ?? '#94a3b8';
}

interface TrendSeries {
  ruleId: string;
  name: string;
  severity: string;
  currentValue: number;
  currentUnit: string;
  isExtremeValue: boolean;
  trendPct: number;
  points: Array<{ period: string; value: number }>;
}

export function FinanceTrendOverview({ rules }: FinanceTrendOverviewProps) {
  const series = useMemo<TrendSeries[]>(() => {
    return rules
      .map((rule) => {
        const config = chartMetricConfig[rule.rule_id];
        const key = config?.seriesKey;
        const points = (rule.history || [])
          .map((item) => {
            const k = key || Object.keys(item).find((kk) => kk !== 'period' && extractSeriesValue(item, kk) !== null);
            if (!k) return null;
            const value = extractSeriesValue(item, k);
            if (value === null) return null;
            return { period: String(item.period ?? ''), value };
          })
          .filter((p): p is { period: string; value: number } => p !== null);

        if (points.length < 2) return null;

        const currentMetric = key && key in rule.current ? key : Object.keys(rule.current)[0];
        const current = currentMetric ? rule.current[currentMetric] : undefined;
        const first = points[0].value;
        const last = points[points.length - 1].value;
        const trendPct = first === 0 ? 0 : ((last - first) / Math.abs(first)) * 100;

        return {
          ruleId: rule.rule_id,
          name: rule.rule_name,
          severity: rule.severity,
          currentValue: current?.value ?? last,
          currentUnit: current?.unit ?? '',
          isExtremeValue: currentMetric === 'cf_to_profit_ratio' && Math.abs(current?.value ?? last) > 100,
          trendPct,
          points,
        } satisfies TrendSeries;
      })
      .filter((s): s is TrendSeries => s !== null);
  }, [rules]);

  if (series.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">核心指标趋势</CardTitle>
          <span className="text-xs text-muted-foreground">近 {series[0]?.points.length ?? 0} 期</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {series.map((s) => {
            const color = getSeverityColor(s.severity);
            const rising = s.trendPct > 0.05;
            const falling = s.trendPct < -0.05;
            return (
              <div
                key={s.ruleId}
                className="rounded-lg border border-border/60 bg-muted/10 p-3 cursor-pointer transition-colors hover:border-primary/50 hover:bg-muted/20"
                title={`定位到「${s.name}」明细`}
                onClick={() => {
                  document.getElementById(`rule-${s.ruleId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-foreground">{s.name}</p>
                    <p className="text-[10px] text-muted-foreground">{s.ruleId}</p>
                  </div>
                  <span className="shrink-0 text-sm font-semibold" style={{ color }}>
                    {s.isExtremeValue ? '极端值（需核查）' : formatValue(s.currentValue, s.currentUnit)}
                  </span>
                </div>

                <div className="mt-2 h-16">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={s.points} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                      <defs>
                        <linearGradient id={`fintrend-${s.ruleId}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.35} />
                          <stop offset="95%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      {/* 隐藏 XAxis：让 tooltip 按 period 取值而非数组索引（悬浮显示 0,1,2.. 的修复） */}
                      <XAxis dataKey="period" hide />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: 6,
                          fontSize: 12,
                        }}
                        labelFormatter={(label) => formatPeriod(String(label ?? ''))}
                        formatter={(v: number | string) => [
                          s.isExtremeValue && Math.abs(Number(v)) > 100
                            ? '极端值（查看规则卡原始金额）'
                            : formatValue(Number(v), s.currentUnit),
                          s.name,
                        ]}
                      />
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke={color}
                        strokeWidth={2}
                        fill={`url(#fintrend-${s.ruleId})`}
                        dot={false}
                        activeDot={{ r: 3 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div className="mt-1.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                  {rising ? (
                    <ArrowUpRight className="h-3 w-3" />
                  ) : falling ? (
                    <ArrowDownRight className="h-3 w-3" />
                  ) : (
                    <Minus className="h-3 w-3" />
                  )}
                  <span>
                    {s.isExtremeValue
                      ? '波动极端（需核查）'
                      : `${Math.abs(s.trendPct).toFixed(1)}% ${rising ? '上升' : falling ? '下降' : '持平'}`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
