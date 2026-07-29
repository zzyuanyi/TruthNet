// 织网鉴真 TruthNet - 分析面板
// T2: 六状态（empty/loading/ready/thinking/streaming/done）

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  AlertTriangle,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  Brain,
  CheckCircle2,
} from 'lucide-react';
import type { PanelData, PanelState, RiskLevel, TriggeredRule, KeyMetric } from '@/types/truthnet';

interface AnalysisPanelProps {
  state: PanelState;
  data: PanelData | null;
  company?: { code: string; name: string };
  onFollowUp?: (suggestion: string) => void;
  errorMessage?: string;
}

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string; icon: typeof AlertTriangle }> = {
  red: { label: '高危', color: 'bg-red-500 text-white', icon: AlertTriangle },
  orange: { label: '中高危', color: 'bg-orange-500 text-white', icon: AlertTriangle },
  yellow: { label: '中等', color: 'bg-yellow-500 text-white', icon: AlertTriangle },
  blue: { label: '低风险', color: 'bg-blue-500 text-white', icon: CheckCircle2 },
  green: { label: '正常', color: 'bg-green-500 text-white', icon: CheckCircle2 },
};

export function AnalysisPanel({ state, data, company, onFollowUp, errorMessage }: AnalysisPanelProps) {
  return (
    <div className="h-full flex flex-col bg-background">
      {/* 头部 */}
      <div className="p-4 border-b border-border">
        <h2 className="text-lg font-semibold">分析面板</h2>
        {company?.name && (
          <p className="text-sm text-muted-foreground">{company.name} ({company.code})</p>
        )}
      </div>

      {/* 内容区域 */}
      <ScrollArea className="flex-1">
        <div className="p-4">
          {/* 根据状态渲染不同内容 */}
          {state === 'empty' && <EmptyState />}
          {state === 'loading' && <LoadingState />}
          {state === 'thinking' && <ThinkingState />}
          {state === 'streaming' && <StreamingState data={data} />}
          {state === 'ready' && <ReadyState data={data} />}
          {state === 'done' && data && <DoneState data={data} onFollowUp={onFollowUp} />}
          {state === 'done' && !data && <EmptyState />}
          {state === 'error' && <ErrorState message={errorMessage} />}
        </div>
      </ScrollArea>
    </div>
  );
}

// 错误状态
function ErrorState({ message }: { message?: string }) {
  return (
    <div className="text-center py-12">
      <AlertTriangle className="h-12 w-12 mx-auto text-destructive mb-4" />
      <h3 className="text-sm font-medium mb-1">分析失败</h3>
      <p className="text-xs text-muted-foreground">
        {message || '请重新提问'}
      </p>
    </div>
  );
}

// 空状态
function EmptyState() {
  return (
    <div className="text-center py-12">
      <AlertTriangle className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
      <h3 className="text-sm font-medium mb-1">暂无分析数据</h3>
      <p className="text-xs text-muted-foreground">
        在左侧对话中提问，开始财报分析
      </p>
    </div>
  );
}

// 加载状态
function LoadingState() {
  return (
    <div className="text-center py-12">
      <Loader2 className="h-12 w-12 mx-auto text-primary animate-spin mb-4" />
      <h3 className="text-sm font-medium mb-1">正在加载...</h3>
      <p className="text-xs text-muted-foreground">
        获取公司数据中
      </p>
    </div>
  );
}

// 思考状态
function ThinkingState() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-primary">
        <Brain className="h-5 w-5 animate-pulse" />
        <span className="text-sm font-medium">正在分析...</span>
      </div>
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>获取财报数据...</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>执行勾稽规则检查...</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>对比行业基准...</span>
        </div>
      </div>
    </div>
  );
}

// 流式输出状态
function StreamingState({ data }: { data: PanelData | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-primary">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm font-medium">正在生成分析结果...</span>
      </div>
      {data && <RiskLevelCard riskLevel={data.risk_level} />}
    </div>
  );
}

// 就绪状态
function ReadyState({ data }: { data: PanelData | null }) {
  if (!data) return <EmptyState />;
  return <DoneState data={data} />;
}

// 完成状态
function DoneState({ data, onFollowUp }: { data: PanelData; onFollowUp?: (s: string) => void }) {
  return (
    <div className="space-y-4">
      {/* 风险等级 */}
      <RiskLevelCard riskLevel={data.risk_level} />

      {/* 触发规则 */}
      {data.triggered_rules.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              触发规则 ({data.triggered_rules.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.triggered_rules.slice(0, 3).map(rule => (
                <TriggeredRuleItem key={rule.id} rule={rule} />
              ))}
              {data.triggered_rules.length > 3 && (
                <Button variant="link" className="text-xs p-0 h-auto">
                  查看全部 {data.triggered_rules.length} 条规则
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 关键指标 */}
      {data.key_metrics.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">关键指标</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid grid-cols-1 gap-2">
              {data.key_metrics.map((metric, i) => (
                <KeyMetricItem key={i} metric={metric} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 查看详情按钮 */}
      <Button variant="outline" className="w-full gap-2">
        <ExternalLink className="h-4 w-4" />
        查看企业画像详情
      </Button>
    </div>
  );
}

// 风险等级卡片
function RiskLevelCard({ riskLevel }: { riskLevel: RiskLevel }) {
  const config = riskLevelConfig[riskLevel];
  const Icon = config.icon;

  return (
    <Card className={cn('border-2', `border-${riskLevel}-500/50`)}>
      <CardContent className="pt-4">
        <div className="flex items-center gap-3">
          <div className={cn('p-2 rounded-full', config.color)}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">风险等级</p>
            <p className="text-lg font-bold">{config.label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// 触发规则项
function TriggeredRuleItem({ rule }: { rule: TriggeredRule }) {
  return (
    <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{rule.name}</p>
        <p className="text-xs text-muted-foreground">
          当前: {rule.current_value} | 阈值: {rule.threshold}
        </p>
      </div>
      <Badge variant="outline" className="text-xs">
        P{rule.industry_percentile}
      </Badge>
    </div>
  );
}

// 关键指标项
function KeyMetricItem({ metric }: { metric: KeyMetric }) {
  const trendIcon = metric.change?.startsWith('+') ? (
    <TrendingUp className="h-3 w-3 text-red-500" />
  ) : metric.change?.startsWith('-') ? (
    <TrendingDown className="h-3 w-3 text-green-500" />
  ) : (
    <Minus className="h-3 w-3 text-muted-foreground" />
  );

  return (
    <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
      <div>
        <p className="text-xs text-muted-foreground">{metric.name}</p>
        <p className="text-sm font-medium">{metric.value}</p>
      </div>
      <div className="flex items-center gap-1">
        {metric.change && (
          <>
            {trendIcon}
            <span className={cn(
              'text-xs',
              metric.change.startsWith('+') ? 'text-red-500' : 'text-green-500'
            )}>
              {metric.change}
            </span>
          </>
        )}
        {metric.risk_indicator && (
          <Badge
            variant="outline"
            className={cn(
              'text-xs ml-2',
              metric.risk_indicator === 'red' && 'border-red-500 text-red-500',
              metric.risk_indicator === 'orange' && 'border-orange-500 text-orange-500',
              metric.risk_indicator === 'yellow' && 'border-yellow-500 text-yellow-500',
              metric.risk_indicator === 'blue' && 'border-blue-500 text-blue-500',
              metric.risk_indicator === 'green' && 'border-green-500 text-green-500',
            )}
          >
            {metric.risk_indicator === 'red' ? '高危' :
             metric.risk_indicator === 'orange' ? '中高危' :
             metric.risk_indicator === 'yellow' ? '中等' :
             metric.risk_indicator === 'blue' ? '低风险' : '正常'}
          </Badge>
        )}
      </div>
    </div>
  );
}
