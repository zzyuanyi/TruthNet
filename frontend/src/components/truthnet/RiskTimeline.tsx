// 织网鉴真 TruthNet - 舆情时间线组件
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
// Phase 2: 舆情时间线

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Calendar, ExternalLink, FileText, Loader2, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import type { EventCluster, TimelineEvent } from '@/types/truthnet';
import { cn } from '@/lib/utils';
import { truthnetAPI } from '@/lib/api-client';

interface RiskTimelineProps {
  events: TimelineEvent[];
  clusters?: EventCluster[];
  /** 公司代码：生成公告 PDF 摘要时定位公告归属 */
  companyCode?: string;
  onEventClick?: (event: TimelineEvent) => void;
}

// 情感颜色映射
const sentimentColors = {
  positive: 'bg-green-500/10 text-green-600 border-green-500/20',
  negative: 'bg-red-500/10 text-red-600 border-red-500/20',
  neutral: 'bg-gray-500/10 text-gray-600 border-gray-500/20',
  mixed: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
};

const sentimentIcons = {
  positive: <TrendingUp className="h-3 w-3 text-green-500" />,
  negative: <TrendingDown className="h-3 w-3 text-red-500" />,
  neutral: <Minus className="h-3 w-3 text-gray-500" />,
  mixed: <TrendingUp className="h-3 w-3 text-yellow-500" />,
};

// 来源类型图标
const sourceTypeIcons: Record<string, string> = {
  announcement: '公告',
  news: '新闻',
  research_report: '研报',
  regulation: '监管',
};

export function RiskTimeline({ events, clusters, companyCode, onEventClick }: RiskTimelineProps) {
  // 按日期排序（最新在前）
  const sortedEvents = [...events].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  // 按年月分组
  const groupedEvents = sortedEvents.reduce((groups, event) => {
    const date = new Date(event.date);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(event);
    return groups;
  }, {} as Record<string, TimelineEvent[]>);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            舆情时间线
          </CardTitle>
          {clusters && (
            <Badge variant="outline" className="text-xs">
              {clusters.length} 个事件簇
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-6">
            {Object.entries(groupedEvents).map(([month, monthEvents]) => (
              <div key={month} className="relative">
                {/* 月份标题 */}
                <div className="sticky top-0 z-10 bg-card py-2 mb-3 border-b border-border">
                  <span className="text-sm font-semibold text-muted-foreground">
                    {formatMonth(month)}
                  </span>
                  <Badge variant="secondary" className="ml-2 text-xs">
                    {monthEvents.length} 条
                  </Badge>
                </div>

                {/* 事件列表 */}
                <div className="space-y-3 ml-4 border-l-2 border-border pl-4">
                  {monthEvents.map((event, index) => (
                    <TimelineItem
                      key={`${event.date}-${index}`}
                      event={event}
                        companyCode={companyCode}
                      onClick={() => onEventClick?.(event)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        {/* 事件簇摘要 */}
        {clusters && clusters.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <div className="text-xs font-medium text-muted-foreground mb-2">
              事件簇摘要
            </div>
            <div className="space-y-2">
              {clusters.slice(0, 3).map(cluster => (
                <div
                  key={cluster.event_cluster_id}
                  className="flex items-start gap-2 text-xs p-2 rounded-md bg-muted/50"
                >
                  {sentimentIcons[cluster.sentiment as keyof typeof sentimentIcons]}
                  <div className="flex-1">
                    <div className="font-medium">{cluster.topic}</div>
                    <div className="text-muted-foreground line-clamp-1">
                      {cluster.summary}
                    </div>
                  </div>
                  <Badge variant="outline" className="text-xs flex-shrink-0">
                    {cluster.event_count} 条
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// 时间线单项组件
interface TimelineItemProps {
  event: TimelineEvent;
  companyCode?: string;
  onClick?: () => void;
}

function TimelineItem({ event, companyCode, onClick }: TimelineItemProps) {
  const sentiment = event.sentiment as keyof typeof sentimentColors;
  const [generatedSummary, setGeneratedSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const handleGenerateSummary = async () => {
    if (!companyCode || !event.object_id || summaryLoading) return;
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const res = await truthnetAPI.getAnnouncementSummary(companyCode, event.object_id);
      setGeneratedSummary(res.data?.summary || '');
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : '公告摘要生成失败');
    } finally {
      setSummaryLoading(false);
    }
  };

  return (
    <div
      className={cn(
        'relative group cursor-pointer transition-all hover:bg-muted/50 rounded-lg p-3 -ml-5 pl-5',
        onClick && 'hover:shadow-sm'
      )}
      onClick={onClick}
    >
      {/* 时间点 */}
      <div className={cn(
        'absolute left-[-9px] top-4 w-4 h-4 rounded-full border-2 border-card',
        sentiment === 'negative' ? 'bg-red-500' :
        sentiment === 'positive' ? 'bg-green-500' :
        sentiment === 'mixed' ? 'bg-yellow-500' : 'bg-gray-500'
      )} />

      {/* 事件内容 */}
      <div className="space-y-1">
        {/* 日期和来源 */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatDate(event.date)}</span>
          <span>•</span>
          <span className={cn(
            'px-1.5 py-0.5 rounded',
            sentimentColors[sentiment]
          )}>
            {sourceTypeIcons[event.category] || event.category}
          </span>
        </div>

        {/* 标题 */}
        <div className="font-medium text-sm group-hover:text-primary transition-colors">
          {event.title}
        </div>

        {/* 摘要 */}
        {event.summary && (
          <div className="text-xs text-muted-foreground line-clamp-2">
            {event.summary}
          </div>
        )}

          {/* PDF 公告摘要（按需生成） */}
          {generatedSummary ? (
            <div className="rounded-md border border-blue-500/20 bg-blue-500/5 px-2.5 py-1.5">
              <p className="text-[10px] font-medium text-blue-600 dark:text-blue-400">公告摘要</p>
              <p className="mt-0.5 text-xs leading-5 text-foreground/90">{generatedSummary}</p>
            </div>
          ) : event.object_id && companyCode ? (
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                void handleGenerateSummary();
              }}
              disabled={summaryLoading}
              className="inline-flex items-center gap-1 rounded border border-border/60 bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/40 hover:text-foreground disabled:opacity-60"
            >
              {summaryLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileText className="h-3 w-3" />}
              {summaryLoading ? '正在解析公告原文…' : '生成公告摘要'}
            </button>
          ) : null}
          {summaryError && (
            <p className="text-[11px] text-destructive">{summaryError}</p>
          )}

        {/* 情感标签 */}
        <div className="flex items-center gap-1 pt-1">
          {sentimentIcons[sentiment]}
          <span className={cn(
            'text-xs',
            sentiment === 'negative' ? 'text-red-600' :
            sentiment === 'positive' ? 'text-green-600' :
            sentiment === 'mixed' ? 'text-yellow-600' : 'text-gray-600'
          )}>
            {sentiment === 'negative' ? '负面' :
             sentiment === 'positive' ? '正面' :
             sentiment === 'mixed' ? '混合' : '中性'}
          </span>
        </div>

        {/* 来源链接（公告原文，Wind PDF） */}
        {event.sources && event.sources.filter(Boolean).length > 0 && (
          <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1">
            {event.sources.filter(Boolean).slice(0, 3).map((uri, i) => (
              <a
                key={`${uri}-${i}`}
                href={uri}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-xs text-blue-500 hover:underline"
              >
                查看原文{i + 1}
              </a>
            ))}
          </div>
        )}

        {/* 证据引用 */}
        {event.evidence_ids && event.evidence_ids.length > 0 && (
          <div className="flex items-center gap-1 mt-2 flex-wrap">
            <span className="text-xs text-muted-foreground">证据:</span>
            {event.evidence_ids.slice(0, 3).map(eid => (
              <Badge
                key={eid}
                variant="outline"
                className="text-xs cursor-pointer hover:bg-primary/10"
                onClick={(e) => { e.stopPropagation(); onClick?.(); }}
              >
                {eid}
              </Badge>
            ))}
            {event.evidence_ids.length > 3 && (
              <span className="text-xs text-muted-foreground">
                +{event.evidence_ids.length - 3}
              </span>
            )}
          </div>
        )}
      </div>

      {/* 悬停时显示的外部链接图标 */}
      <ExternalLink className="absolute right-2 top-2 h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}

// 格式化月份
function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  return `${year}年${parseInt(month)}月`;
}

// 格式化日期
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}
