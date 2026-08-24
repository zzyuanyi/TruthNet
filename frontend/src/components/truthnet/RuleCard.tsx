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
  // A2（8/9 老师要求）：证据在信号下方直接平铺（弹窗仅作次级入口）
  evidenceSummaries?: RuleEvidenceSummary[];
}

// 平铺用证据摘要（由画像页批量拉取 /evidence 后注入）
export interface RuleEvidenceSummary {
  evidenceId: string;
  title: string;
  sourceType: string;
  period: string;
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

// 单位可读化：百分比与百分点表达不同的规则语义，避免把差值误读为比例。
const displayUnitLabels: Record<string, string> = {
  percent: '%',
  percentage_point: '个百分点',
  pp: '个百分点',
  ratio: '',
  quarters: '个季度',
  days: '天',
  bool: '',
  yuan: '元',
  times: '倍',
};

const calculationDescriptions: Record<string, string> = {
  R1: '比较应收账款与营业收入的同比增速差，并以当期与上年同期数据计算同比。',
  R2: '观察经营活动现金流与净利润（不含少数股东损益）的多期关系，并统计“净利润为正、经营现金流为负”的连续期数。',
  R3: '计算货币资金占总资产比例、有息负债占总资产比例，并结合利息费用交叉核验。',
  R4: '比较存货与营业收入的同比增速差，并结合存货周转天数判断积压风险。',
  R5: '先计算毛利率和期间费用率，再将当期指标与历史平均水平比较，识别异常偏离。',
  R6: '计算其他应收款占总资产比例及同比变化，并与应收账款等科目交叉核验。',
  R7: '比较扣非净利润、净利润、营业收入和经营现金流的关系，识别利润质量与增长背离。',
};

const calculationFieldLabels: Record<string, string> = {
  acct_rcv: '应收账款',
  oper_rev: '营业收入',
  net_cash_flows_oper_act: '经营活动现金流量净额',
  net_profit_excl_min_int_inc: '净利润（不含少数股东损益）',
  monetary_cap: '货币资金',
  tot_assets: '资产总计',
  st_borrow: '短期借款',
  lt_borrow: '长期借款',
  fin_exp: '财务费用',
  inventories: '存货',
  less_oper_cost: '营业成本',
  less_selling_dist_exp: '销售费用',
  less_gerl_admin_exp: '管理费用',
  selling_exp: '销售费用',
  admin_exp: '管理费用',
  oth_rcv: '其他应收款',
  net_profit: '净利润',
  core_profit: '扣非净利润',
  oper_profit: '营业利润',
  tot_profit: '利润总额',
};

const sourceTableLabels: Record<string, string> = {
  income_statement: '利润表',
  balance_sheet: '资产负债表',
  cash_flow_statement: '现金流量表',
  cash_flow: '现金流量表',
};

function formatCalculationPeriod(period: string): string {
  const match = /^(\d{4})(\d{2})(\d{2})$/.exec(period);
  if (!match) return period;
  const [, year, month] = match;
  const labels: Record<string, string> = {
    '03': '一季度',
    '06': '二季度',
    '09': '三季度',
    '12': '年报',
  };
  return `${year}年${labels[month] || `${Number(month)}月`}`;
}

function formatCalculationValue(value: number | string, unit?: string): string {
  const numericValue = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numericValue)) return String(value);
  if (unit === 'percent') return `${numericValue.toFixed(2)}%`;
  if (unit === 'percentage_point' || unit === 'pp') return `${numericValue.toFixed(2)} 个百分点`;
  if (Math.abs(numericValue) >= 100_000_000) return `${(numericValue / 100_000_000).toFixed(2)} 亿元`;
  if (Math.abs(numericValue) >= 10_000) return `${(numericValue / 10_000).toFixed(2)} 万元`;
  return `${numericValue.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}${unit === 'yuan' || unit === 'CNY' || unit === '元' ? ' 元' : ''}`;
}

function calculationFieldLabel(fieldPath: string, role?: string): string {
  const field = fieldPath.split('.').at(-1) || fieldPath;
  const roleField = role?.replace(/@\d{8}$/, '');
  return calculationFieldLabels[field] || (roleField ? calculationFieldLabels[roleField] : undefined) || roleField || fieldPath;
}

type CalculationInputs = NonNullable<FinanceRuleItem['calculation_trace']>['inputs'];

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

function calculationDataCheckWarnings(ruleId: string, inputs: CalculationInputs): string[] {
  const warnings: string[] = [];
  const latestPeriod = inputs.reduce((latest, input) => input.period > latest ? input.period : latest, '');

  // R2 的分母过小会把现金流/利润比放大，必须把原始金额和口径提示一起呈现。
  if (ruleId === 'R2') {
    const cashflow = inputs.find(input => input.period === latestPeriod && input.field_path === 'net_cash_flows_oper_act');
    const profit = inputs.find(input => input.period === latestPeriod && input.field_path === 'net_profit_excl_min_int_inc');
    const cashflowValue = cashflow ? Number(cashflow.value) : NaN;
    const profitValue = profit ? Number(profit.value) : NaN;
    if (Number.isFinite(cashflowValue) && Number.isFinite(profitValue) && profitValue !== 0) {
      const ratio = cashflowValue / Math.abs(profitValue);
      if (Math.abs(ratio) > 100) {
        warnings.push(`${formatCalculationPeriod(latestPeriod)}现金流/净利润比为 ${ratio.toFixed(1)}；净利润基数较小会放大该比值，请核对母公司报表范围与原始披露。`);
      }
    }
  }

  const byField = new Map<string, typeof inputs>();
  for (const input of inputs) {
    const entries = byField.get(input.field_path) || [];
    entries.push(input);
    byField.set(input.field_path, entries);
  }
  for (const fieldInputs of byField.values()) {
    const ordered = [...fieldInputs].sort((a, b) => a.period.localeCompare(b.period));
    const latest = ordered.at(-1);
    const reference = ordered.slice(-5, -1)
      .map(input => Math.abs(Number(input.value)))
      .filter(Number.isFinite)
      .filter(value => value > 0);
    const current = latest ? Math.abs(Number(latest.value)) : NaN;
    const baseline = median(reference);
    if (!latest || baseline === null || !Number.isFinite(current) || current === 0) continue;
    const relative = current / baseline;
    if (relative <= 0.1) {
      warnings.push(`${calculationFieldLabel(latest.field_path, latest.role)}最新绝对值较前四个可比报告期中位数低 ${((1 - relative) * 100).toFixed(1)}%，建议核对期次、报表范围与原始披露。`);
    } else if (relative >= 10) {
      warnings.push(`${calculationFieldLabel(latest.field_path, latest.role)}最新绝对值约为前四个可比报告期中位数的 ${relative.toFixed(1)} 倍，建议核对期次、报表范围与原始披露。`);
    }
  }
  return [...new Set(warnings)].slice(0, 3);
}

function formatRuleValue(value: number | undefined, unit: string | undefined): string {
  if (typeof value !== 'number') return '--';
  if (unit === 'bool') return value ? '是' : '否';
  const digits = unit === 'ratio' ? 2 : unit === 'percent' || unit === 'percentage_point' || unit === 'days' ? 1 : 0;
  const text = value.toFixed(digits);
  const unitText = displayUnitLabels[unit || ''] ?? (unit || '');
  return unitText ? `${text}${unitText}` : text;
}

function latestHistoryPeriod(rule: FinanceRuleItem): string {
  const last = rule.history?.at(-1);
  if (!last || typeof last.period !== 'string') return '';
  return last.period;
}

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

export function RuleCard({ rule, onViewEvidence, onViewDetail, evidenceSummaries }: RuleCardProps) {
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
  const calculationWarnings = rule.calculation_trace
    ? calculationDataCheckWarnings(rule.rule_id, rule.calculation_trace.inputs)
    : [];
  const hasExtremeCurrentRatio = currentMetric === 'cf_to_profit_ratio'
    && typeof currentValue?.value === 'number'
    && Math.abs(currentValue.value) > 100;

  return (
    <Card
      id={`rule-${rule.rule_id}`}
      className={cn(
      'transition-all hover:shadow-md scroll-mt-20',
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

        {/* 触发原因置顶：先解释为什么触发，再看指标/证据 */}
        {rule.status === 'triggered' && (
          <div className="mx-6 mb-4 rounded-md border border-orange-500/30 bg-orange-500/5 px-3 py-2">
            <p className="text-xs font-semibold text-orange-700 dark:text-orange-400">
              为什么触发
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              {rule.explanation || '规则指标超过预设阈值，详见下方指标与证据。'}
            </p>
          </div>
        )}

      <CardContent className="space-y-4">
        {/* 当前值与行业基准（industry_metrics typed 分位，R3/R4/R5 多指标逐行） */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-muted-foreground mb-1">当前值</div>
            <div className="text-lg font-semibold">
              {hasExtremeCurrentRatio ? '极端值（需核查）' : formatRuleValue(currentValue?.value, currentValue?.unit)}
              <span className="text-xs text-muted-foreground ml-1">
                
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              {hasExtremeCurrentRatio ? '最近 4 期平均比值不直接展示' : currentMetric}
            </div>
              {latestHistoryPeriod(rule) && (
                <div className="text-[10px] text-muted-foreground">
                  数据期：{latestHistoryPeriod(rule)}
                </div>
              )}
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

        {/* 触发原因已置顶，此处不再重复展示；下方为直接展开的证据列表 */}
        <p className="hidden">
          {rule.explanation}
        </p>

        {rule.calculation_trace && rule.calculation_trace.inputs.length > 0 && (
          <details className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-foreground">
              查看核查计算依据
            </summary>
            <div className="mt-2 space-y-2 text-xs text-muted-foreground">
              <p className="leading-5 text-foreground">
                {calculationDescriptions[rule.calculation_trace.formula_id] || '根据下列报表原始数据，按规则口径计算并与触发线比较。'}
              </p>
              <div className="max-h-48 overflow-y-auto rounded border border-border/60 bg-background">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-muted/80 text-[10px] text-muted-foreground">
                    <tr>
                      <th className="px-2 py-1.5 font-medium">核查字段</th>
                      <th className="px-2 py-1.5 font-medium">数据期</th>
                      <th className="px-2 py-1.5 text-right font-medium">报表值</th>
                      <th className="px-2 py-1.5 font-medium">来源</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rule.calculation_trace.inputs.map((input, index) => (
                      <tr key={`${input.field_path}-${input.period}-${index}`} className="border-t border-border/50">
                        <td className="px-2 py-1.5 font-medium text-foreground">{calculationFieldLabel(input.field_path, input.role)}</td>
                        <td className="px-2 py-1.5">{formatCalculationPeriod(input.period)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-foreground">{formatCalculationValue(input.value, input.unit)}</td>
                        <td className="px-2 py-1.5">{sourceTableLabels[input.source_table] || input.source_table}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details className="pt-1">
                <summary className="cursor-pointer text-[10px] text-muted-foreground">技术口径（公式与版本）</summary>
                <p className="mt-1 break-words font-mono text-[10px] leading-4 text-muted-foreground">
                  {rule.calculation_trace.formula}
                  {rule.calculation_trace.calculation_version && `（${rule.calculation_trace.calculation_version}）`}
                </p>
              </details>
              {calculationWarnings.length > 0 && (
                <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 px-2.5 py-2 text-xs text-yellow-900 dark:text-yellow-200">
                  <p className="font-medium">数据核查提示</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4 leading-5">
                    {calculationWarnings.map(warning => <li key={warning}>{warning}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </details>
        )}

        {/* A2（8/9 老师要求）：关联证据直接平铺在信号下方，点击可进详情弹窗（次级入口） */}
        {false && (
          <div className="rounded-lg border border-border/60 bg-muted/20 p-2.5">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-medium text-foreground">关联证据</span>
              <span className="text-[10px] text-muted-foreground">共 {rule.evidence_ids.length} 条</span>
            </div>
            <div className="space-y-1.5">
              {evidenceSummaries!.slice(0, 3).map(item => (
                <button
                  key={item.evidenceId}
                  onClick={() => onViewEvidence?.(rule.rule_id)}
                  className="w-full rounded-md border border-border/50 bg-background px-2.5 py-1.5 text-left transition-colors hover:border-primary/40 hover:bg-muted/30"
                >
                  <p className="text-xs text-foreground line-clamp-1">{item.title}</p>
                  <p className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span className="rounded bg-muted px-1">{item.sourceType || '证据'}</span>
                    {item.period && <span>{item.period}</span>}
                  </p>
                </button>
              ))}
              {rule.evidence_ids.length > 3 && (
                <p className="text-center text-[10px] text-muted-foreground">
                  还有 {rule.evidence_ids.length - 3} 条，点击「查看证据」展开全部
                </p>
              )}
            </div>
          </div>
        )}

          {/* A2（8/9 老师要求）：关联证据默认直接展开平铺，点下方按钮看来源记录 */}
          {(evidenceSummaries?.length ?? 0) > 0 && (
            <div className="rounded-lg border border-border/60 bg-muted/20 p-2.5">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-medium text-foreground">关联证据（已展开）</span>
                <span className="text-[10px] text-muted-foreground">
                  展示 {evidenceSummaries!.length}/{rule.evidence_ids.length} 条
                </span>
              </div>
                <p className="mb-1.5 text-[10px] text-muted-foreground">
                  触发证据基于最新数据期{latestHistoryPeriod(rule) ? `（${latestHistoryPeriod(rule)}）` : ''}；历史曲线为趋势参考
                </p>
              <div className="max-h-64 space-y-1.5 overflow-y-auto pr-0.5">
                {evidenceSummaries!.map(item => (
                  <div
                    key={item.evidenceId}
                    className="rounded-md border border-border/50 bg-background px-2.5 py-1.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs leading-5 text-foreground">{item.title}</p>
                      {item.period && (
                        <span className="shrink-0 rounded bg-muted px-1 text-[10px] text-muted-foreground">
                          {item.period}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="rounded bg-muted px-1">{item.sourceType || '证据'}</span>
                      <span className="font-mono">{item.evidenceId}</span>
                    </p>
                  </div>
                ))}
              </div>
              {rule.evidence_ids.length > evidenceSummaries!.length && (
                <p className="mt-1.5 text-center text-[10px] text-muted-foreground">
                  还有 {rule.evidence_ids.length - evidenceSummaries!.length} 条，点击下方「查看证据」查看全部来源记录
                </p>
              )}
            </div>
          )}

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
