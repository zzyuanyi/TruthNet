// 织网鉴真 TruthNet - 对话界面

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ThinkingBubble } from '@/components/thinking-bubble';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, User, Bot, Shield, TrendingUp, Zap, FileText } from 'lucide-react';
import type { Message, RiskLevel, ComparisonNextStep } from '@/types/truthnet';
import { MarkdownRenderer } from '@/components/markdown-renderer';

interface CompanyCandidate {
  wind_code: string;
  sec_name: string;
}

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  highlightedEvidenceIds?: string[] | null;
  activeRuleName?: string | null;
  onClearEvidenceHighlight?: () => void;
  // 8.11：公司歧义候选确认（后端 company.candidates → 点选 → company.confirm 重跑）
  pendingCandidates?: { turn_id: string; candidates: CompanyCandidate[] } | null;
  onConfirmCompany?: (turnId: string, windCode: string) => void;
  // v3.3.4 收口复核清单 §5：结构化比较下一步导航
  onNavigateStep?: (step: ComparisonNextStep) => void;
}

// 风险等级颜色
const riskColors: Record<RiskLevel, string> = {
  red: 'text-red-500 bg-red-500/10 border-red-500/20',
  orange: 'text-orange-500 bg-orange-500/10 border-orange-500/20',
  yellow: 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20',
  blue: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
  green: 'text-green-500 bg-green-500/10 border-green-500/20',
  unknown: 'text-gray-500 bg-gray-500/10 border-gray-500/20',
};

export function ChatInterface({
  messages,
  onSendMessage,
  isLoading,
  highlightedEvidenceIds,
  activeRuleName,
  onClearEvidenceHighlight,
  pendingCandidates,
  onConfirmCompany,
  onNavigateStep,
}: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const [confirmingCode, setConfirmingCode] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 8.11 P0（审查）：新的候选轮次（turn_id 变化）重置确认状态，
  // 避免第二次歧义时按钮全部被禁用
  useEffect(() => {
    setConfirmingCode(null);
  }, [pendingCandidates?.turn_id]);

  // 8.11：确认候选公司（点击后禁用重复选择，等待后端重跑原问题）
  const handleConfirm = (windCode: string) => {
    if (!pendingCandidates || confirmingCode) return;
    setConfirmingCode(windCode);
    onConfirmCompany?.(pendingCandidates.turn_id, windCode);
  };

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // 发送消息
  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  // 回车发送（Shift+Enter 换行）
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 消息列表（min-h-0：防止 flex item 被内容撑开，确保内部滚动 + 自动滚底生效） */}
      <ScrollArea className="flex-1 min-h-0" ref={scrollRef}>
        {highlightedEvidenceIds && highlightedEvidenceIds.length > 0 && (
          <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-primary/20 bg-background/95 px-4 py-2 text-xs backdrop-blur-sm">
            <span className="truncate text-primary">
              已定位 {activeRuleName || '当前规则'}的 {highlightedEvidenceIds.length} 条证据
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 shrink-0 px-2 text-xs"
              onClick={onClearEvidenceHighlight}
            >
              取消定位
            </Button>
          </div>
        )}
        <div className="p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-8">
              <Shield className="h-10 w-10 text-primary/40 mx-auto mb-3" />
              <h3 className="text-base font-medium text-foreground mb-1">织网鉴真 · 财报反欺诈助手</h3>
              <p className="text-xs text-muted-foreground mb-6">输入上市公司名称或股票代码，穿透股权 · 交叉验证 · 对齐舆情</p>
              <div className="grid grid-cols-2 gap-2 max-w-lg mx-auto">
                {[
                  { icon: TrendingUp, label: '财务勾稽', text: '分析康美药业是否存在收入虚增' },
                  { icon: Zap, label: '股权穿透', text: '查看金牌家居的实际控制人链路' },
                  { icon: FileText, label: '舆情对齐', text: '核对康美药业近期公告与财务数据' },
                  { icon: Shield, label: '综合风险', text: '综合评估贵州茅台的财务、股权与舆情风险' },
                ].map((card, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(card.text); setTimeout(() => { if (card.text.trim()) onSendMessage(card.text.trim()); setInput(''); }, 0); }}
                    className="text-left p-3 rounded-md border border-border/60 hover:border-primary/30 hover:bg-muted/30 transition-colors group"
                  >
                    <card.icon className="h-4 w-4 text-primary/60 mb-1.5 group-hover:text-primary transition-colors" />
                    <p className="text-xs font-medium text-foreground mb-0.5">{card.label}</p>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">{card.text}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(message => {
            const isEvidenceMatch = Boolean(
              highlightedEvidenceIds?.length &&
              message.role === 'assistant' &&
              (message.evidence_ids || []).some(id => highlightedEvidenceIds.includes(id))
            );
            return (
              <MessageBubble
                key={message.id}
                message={message}
                evidenceHighlighted={isEvidenceMatch}
                onFollowUp={onSendMessage}
                onNavigateStep={onNavigateStep}
              />
            );
          })}

          {/* 8.11：公司歧义候选确认卡片 */}
          {pendingCandidates && pendingCandidates.candidates.length > 0 && (
            <div className="max-w-[70%] rounded-lg border border-primary/30 bg-primary/5 p-3">
              <p className="text-sm font-medium text-foreground mb-2">
                检测到多家公司，请选择您想问的是哪一家：
              </p>
              <div className="flex flex-wrap gap-2">
                {pendingCandidates.candidates.map(c => (
                  <Button
                    key={c.wind_code}
                    variant={confirmingCode === c.wind_code ? 'default' : 'outline'}
                    size="sm"
                    className="h-auto py-1.5 text-xs"
                    disabled={Boolean(confirmingCode)}
                    onClick={() => handleConfirm(c.wind_code)}
                  >
                    {c.sec_name}
                    <span className="ml-1 text-[10px] opacity-70">{c.wind_code}</span>
                  </Button>
                ))}
              </div>
              {confirmingCode && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  已确认，正在重新分析该公司的数据...
                </p>
              )}
            </div>
          )}

          {/* 加载指示器 */}
          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">正在处理...</span>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* 输入区域 */}
      <div className="border-t border-border p-4 bg-gradient-to-t from-muted/20 to-background">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题，如：分析康美药业的财务异常..."
            className="min-h-[60px] max-h-[200px] resize-none"
            disabled={isLoading}
          />
          <Button
            size="icon"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="h-[60px] w-[60px]"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          按 Enter 发送，Shift + Enter 换行
        </p>
      </div>
    </div>
  );
}

// 消息气泡组件
function MessageBubble({
  message,
  evidenceHighlighted = false,
  onFollowUp,
  onNavigateStep,
}: {
  message: Message;
  evidenceHighlighted?: boolean;
  onFollowUp?: (suggestion: string) => void;
  onNavigateStep?: (step: ComparisonNextStep) => void;
}) {
  const isUser = message.role === 'user';

  return (
    <div
      id={message.id}
      className={cn(
        'flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300',
        isUser ? 'justify-end' : 'justify-start',
      )}
    >
      {/* 头像 */}
      <div className={cn(
        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted',
        evidenceHighlighted && 'ring-2 ring-primary/50 bg-primary/5'
      )}>
        {evidenceHighlighted && (
          <Badge variant="outline" className="mb-2 border-primary/30 bg-background text-xs text-primary">
            匹配当前规则
          </Badge>
        )}
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* 消息内容 */}
      <div className={cn(
        'max-w-[70%] rounded-lg p-3',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
      )}>
        {/* 思考过程 */}
        {message.thinking && !isUser && (
          <ThinkingBubble content={message.thinking} />
        )}

        {/* 主要内容 */}
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <MarkdownRenderer content={message.content} />
          </div>
        )}

        {/* v3.3.4 收口复核清单 §5.2-4：结构化比较下一步优先于旧追问 */}
        {!isUser && message.next_steps && message.next_steps.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border/50">
            {message.next_steps.map((step, i) => (
              <Button
                key={`${step.kind}-${i}`}
                variant="default"
                size="sm"
                className="h-auto py-1.5 text-xs"
                onClick={() => onNavigateStep?.(step)}
              >
                {step.label}
              </Button>
            ))}
          </div>
        )}

        {/* 追问建议 */}
        {message.follow_ups && message.follow_ups.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border/50">
            {message.follow_ups.map((suggestion, i) => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                className="h-auto py-1.5 text-xs"
                onClick={() => onFollowUp?.(suggestion)}
              >
                {suggestion}
              </Button>
            ))}
          </div>
        )}

        {/* 来源引用 */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <p className="text-xs text-muted-foreground mb-1">来源：</p>
            <div className="space-y-1">
              {message.sources.map(source => (
                <div key={source.id} className="text-xs text-muted-foreground">
                  • {source.title} - {source.source}
                  {source.url && (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-1.5 text-blue-500 hover:underline"
                    >
                      查看原文
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 证据分级标注 */}
        {!isUser && message.show_evidence_status && (
          <div className="mt-2 pt-2 border-t border-border/30">
            {message.evidence_ids && message.evidence_ids.length > 0 ? (
              <div className="flex items-center gap-1 flex-wrap">
                <Badge variant="outline" className="text-xs bg-green-500/10 text-green-600 border-green-500/20">
                  有据可查
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {message.evidence_ids.length} 条证据支撑
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <Badge variant="outline" className="text-xs bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
                  仅供参考
                </Badge>
                <span className="text-xs text-muted-foreground">
                  无直接证据支撑
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
