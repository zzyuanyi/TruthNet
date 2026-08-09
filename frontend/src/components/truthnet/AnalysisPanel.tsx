// 织网鉴真 TruthNet - 分析面板
// Phase 3: 面板联动 + 仅供参考标注

import { cn } from '@/lib/utils';
import { AnimatedNumber } from '@/components/animated-number';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  AlertTriangle,
  Loader2,
  Minus,
  ExternalLink,
  Brain,
  CheckCircle2,
  Info,
} from 'lucide-react';
import type { PanelData, PanelState, RiskLevel } from '@/types/truthnet';

interface AnalysisPanelProps {
  state: PanelState;
  data: PanelData | null;
  company?: { code: string; name: string };
  onFollowUp?: (suggestion: string) => void;
  onViewDetails?: (type: 'rules' | 'equity' | 'sentiment' | 'evidence') => void;
  onRuleClick?: (ruleId: string) => void;
  onMetricClick?: (metric: { name: string; value: number }) => void;
  activeRuleId?: string | null; // 规则筛选高亮（对齐审计 P1-3）
}

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string; icon: typeof AlertTriangle }> = {
  red: { label: '高危', color: 'bg-red-500 text-white', icon: AlertTriangle },
  orange: { label: '中高危', color: 'bg-orange-500 text-white', icon: AlertTriangle },
  yellow: { label: '中等', color: 'bg-yellow-500 text-white', icon: AlertTriangle },
  blue: { label: '低风险', color: 'bg-blue-500 text-white', icon: CheckCircle2 },
  green: { label: '正常', color: 'bg-green-500 text-white', icon: CheckCircle2 },
  unknown: { label: '未知', color: 'bg-gray-500 text-white', icon: AlertTriangle },
};

export function AnalysisPanel({
  state,
  data,
  company,
  onFollowUp,
  onViewDetails,
  onRuleClick,
  onMetricClick,
  activeRuleId,
}: AnalysisPanelProps) {
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
          {state === 'done' && data && (
            <DoneState
              data={data}
              onFollowUp={onFollowUp}
              onViewDetails={onViewDetails}
              onRuleClick={onRuleClick}
              onMetricClick={onMetricClick}
              activeRuleId={activeRuleId}
            />
          )}
          {state === 'done' && !data && <EmptyState />}
          {state === 'error' && <ErrorState />}
        </div>
      </ScrollArea>

      {/* 免责声明 */}
      {state === 'done' && data && (
        <div className="p-3 border-t border-border bg-muted/30">
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <Info className="h-3 w-3 flex-shrink-0 mt-0.5" />
            <span>以上分析结果仅供参考，不构成投资建议。数据来源于公开信息，可能存在滞后或偏差。</span>
          </div>
        </div>
      )}
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
      <h3 className="text-sm font-medium mb-1">正在理解问题...</h3>
      <p className="text-xs text-muted-foreground">
        判断意图与可用数据范围
      </p>
    </div>
  );
}

function ErrorState() {
  return (
    <div className="text-center py-12">
      <AlertTriangle className="h-12 w-12 mx-auto text-destructive/70 mb-4" />
      <h3 className="text-sm font-medium mb-1">本次请求未完成</h3>
      <p className="text-xs text-muted-foreground">请检查连接后重新发送问题</p>
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
        <ThinkingStep label="加载上下文" status="done" />
        <ThinkingStep label="识别实体" status="done" />
        <ThinkingStep label="规划分析模块" status="running" />
        <ThinkingStep label="执行财务勾稽" status="pending" />
        <ThinkingStep label="股权穿透" status="pending" />
        <ThinkingStep label="生成结论" status="pending" />
      </div>
    </div>
  );
}

function ThinkingStep({ label, status }: { label: string; status: 'done' | 'running' | 'pending' }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {status === 'done' && <CheckCircle2 className="h-3 w-3 text-green-500" />}
      {status === 'running' && <Loader2 className="h-3 w-3 text-primary animate-spin" />}
      {status === 'pending' && <div className="h-3 w-3 rounded-full border border-muted" />}
      <span className={cn(
        status === 'pending' && 'text-muted-foreground'
      )}>
        {label}
      </span>
    </div>
  );
}

// 流式状态
function StreamingState({ data }: { data: PanelData | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-primary">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm font-medium">{data ? '正在生成分析...' : '正在生成回答...'}</span>
      </div>
      {data && (
        <div className="space-y-3">
          <RiskSummary data={data} />
          <Separator />
          <KeyMetrics data={data} />
        </div>
      )}
    </div>
  );
}

// 就绪状态
function ReadyState({ data }: { data: PanelData | null }) {
  if (!data) return <EmptyState />;

  return (
    <div className="space-y-4">
      <RiskSummary data={data} />
      <Separator />
      <KeyMetrics data={data} />
      <Separator />
      <TriggeredRules data={data} />
    </div>
  );
}

// 完成状态
function DoneState({
  data,
  onFollowUp,
  onViewDetails,
  onRuleClick,
  onMetricClick,
  activeRuleId,
}: {
  data: PanelData;
  onFollowUp?: (suggestion: string) => void;
  onViewDetails?: (type: 'rules' | 'equity' | 'sentiment' | 'evidence') => void;
  onRuleClick?: (rule: string) => void;
  onMetricClick?: (metric: { name: string; value: number }) => void;
  activeRuleId?: string | null;
}) {
  return (
    <div className="space-y-4">
      <RiskSummary data={data} />
      <Separator />
      <KeyMetrics data={data} onMetricClick={onMetricClick} />
      <Separator />
      <TriggeredRules
        data={data}
        onRuleClick={onRuleClick}
        onViewDetails={onViewDetails}
        activeRuleId={activeRuleId}
      />

      {/* 追问建议 */}

      {/* 追问建议 */}
      {data.follow_ups && data.follow_ups.length > 0 && (
        <>
          <Separator />
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">追问建议</h4>
            <div className="flex flex-wrap gap-2">
              {data.follow_ups.map((suggestion, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  className="text-xs h-auto py-1.5"
                  onClick={() => onFollowUp?.(suggestion)}
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// 风险摘要
function RiskSummary({ data }: { data: PanelData }) {
  const riskLevel = data.risk_level || 'green';
  const riskConfig = riskLevelConfig[riskLevel];
  const RiskIcon = riskConfig.icon;
  const triggeredCount = data.triggered_rules?.length || 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <RiskIcon className="h-4 w-4" />
          风险等级
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-3">
          <Badge className={cn('text-sm px-3 py-1', riskConfig.color)}>
            {riskConfig.label}
          </Badge>
          <span className="text-xs text-muted-foreground">
            触发 {triggeredCount} 条规则
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// 关键指标
function KeyMetrics({ data, onMetricClick }: { data: PanelData; onMetricClick?: (metric: { name: string; value: number }) => void }) {
  const metrics = Object.entries(data.key_metrics || {}).map(([name, value]) => ({ name, value }));

  if (metrics.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-medium text-muted-foreground">关键指标</h4>
      <div className="grid grid-cols-3 gap-2">
        {metrics.map((metric, index) => (
          <Card
            key={index}
            className="cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => onMetricClick?.(metric)}
          >
            <CardContent className="p-3">
              <div className="text-xs text-muted-foreground mb-1">
                {metric.name}
              </div>
              <div className="flex items-center gap-1">
                <AnimatedNumber
                  value={metric.value}
                  className="text-lg font-semibold"
                  decimals={metric.value % 1 !== 0 ? 1 : 0}
                />
                <Minus className="h-3 w-3 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// 触发规则
function TriggeredRules({
  data,
  onRuleClick,
  onViewDetails,
  activeRuleId,
}: {
  data: PanelData;
  onRuleClick?: (ruleId: string) => void;
  onViewDetails?: (type: 'rules') => void;
  activeRuleId?: string | null;
}) {
  const rules = data.triggered_rules || [];
  const displayRules = rules.slice(0, 3);
  const hasMore = rules.length > 3;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-muted-foreground">
          触发规则 ({rules.length})
        </h4>
        {hasMore && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={() => onViewDetails?.('rules')}
          >
            查看全部
            <ExternalLink className="h-3 w-3 ml-1" />
          </Button>
        )}
      </div>
      <div className="space-y-2">
        {displayRules.map((rule, index) => (
          <Card
            key={index}
            className={cn(
              'cursor-pointer hover:bg-muted/50 transition-colors',
              activeRuleId === rule.rule_id && 'border-primary/60 bg-primary/5',
            )}
            onClick={() => onRuleClick?.(rule.rule_id)}
          >
            <CardContent className="p-3">
              <div className="text-sm">
                {typeof rule === 'string' ? rule : rule.rule_name}
              </div>
              {typeof rule !== 'string' && rule.evidence_ids && rule.evidence_ids.length > 0 && (
                <>
                  <div className="text-xs text-muted-foreground mt-1">
                    {rule.evidence_ids.length} 条证据
                  </div>
                  {activeRuleId === rule.rule_id && (
                    <div className="mt-2 space-y-1 border-t border-border/60 pt-2">
                      {rule.evidence_ids.map(evidenceId => (
                        <code
                          key={evidenceId}
                          className="block truncate rounded bg-muted px-1.5 py-1 text-[10px] text-muted-foreground"
                          title={evidenceId}
                        >
                          {evidenceId}
                        </code>
                      ))}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
