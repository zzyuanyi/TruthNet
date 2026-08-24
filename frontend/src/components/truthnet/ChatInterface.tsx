// 织网鉴真 TruthNet - 对话界面

import { useState, useRef, useEffect } from 'react';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { cn } from '@/lib/utils';
import { ThinkingBubble } from '@/components/thinking-bubble';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, User, Bot, Shield, TrendingUp, Zap, FileText, Info } from 'lucide-react';
import type { Message, RiskLevel, ComparisonNextStep, PendingCompanyCandidates } from '@/types/truthnet';
import { MarkdownRenderer } from '@/components/markdown-renderer';

// 来源类型中文标签（与画像页 sourceTypeIcons 口径一致）
const SOURCE_TYPE_LABELS: Record<string, string> = {
  financial_statement: '母公司报表',
  announcement: '公告',
  research_report: '研报',
  news: '新闻',
  regulation: '监管',
  equity: '股权',
  event: '舆情',
  risk: '风险',
  web_search: '联网检索',
};

interface AnswerSection {
  title: string;
  body: string;
  tone: 'red' | 'blue' | 'orange' | 'gray';
}

function splitStructuredAnswer(content: string): {
  preamble: string;
  ruleDetails: string;
  sections: AnswerSection[];
} {
  const chunks = content.split(/(?=【[^】]+】)/g).map(s => s.trim()).filter(Boolean);
  const preamble = chunks[0] || '';
  const ruleMarker = '触发规则明细：';
  const ruleIndex = preamble.indexOf(ruleMarker);
  const summary = ruleIndex >= 0 ? preamble.slice(0, ruleIndex).trim() : preamble;
  const ruleDetails = ruleIndex >= 0 ? preamble.slice(ruleIndex + ruleMarker.length).trim() : '';

  const toneFor = (title: string): AnswerSection['tone'] => {
    if (title.includes('预警')) return 'red';
    if (title.includes('数据对比')) return 'blue';
    if (title.includes('可能模式')) return 'orange';
    return 'gray';
  };

  const sections = chunks.slice(1).map(raw => {
    const match = raw.match(/^【([^】]+)】/);
    const title = match?.[1]?.trim() || '分段';
    const body = raw.replace(/^【[^】]+】/, '').trim();
    return { title, body, tone: toneFor(title) };
  });

  return { preamble: summary, ruleDetails, sections };
}

const SECTION_TONES: Record<AnswerSection['tone'], string> = {
  red: 'border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-400',
  blue: 'border-blue-500/30 bg-blue-500/5 text-blue-700 dark:text-blue-400',
  orange: 'border-orange-500/30 bg-orange-500/5 text-orange-700 dark:text-orange-400',
  gray: 'border-border bg-muted/40 text-muted-foreground',
};

function StructuredAnswer({ content }: { content: string }) {
  if (!content.includes('【')) {
    return <MarkdownRenderer content={content} />;
  }
  const { preamble, ruleDetails, sections } = splitStructuredAnswer(content);
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {preamble && (
        <div className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
          <p className="mb-1 text-xs font-semibold text-primary">分析概要</p>
          <MarkdownRenderer content={preamble} />
        </div>
      )}
      {ruleDetails && (
        <details className="rounded-md border border-border/60 bg-muted/20 px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium text-foreground">
            触发规则明细
          </summary>
          <div className="mt-2">
            <MarkdownRenderer content={ruleDetails} />
          </div>
        </details>
      )}
      {sections.map((section, index) => (
        <details key={`${section.title}-${index}`} open={index === 0} className="rounded-md border border-border/60 bg-muted/20 px-3 py-2">
          <summary className={`cursor-pointer text-xs font-semibold ${SECTION_TONES[section.tone]}`}>
            {section.title}
          </summary>
          <div className="mt-2">
            <MarkdownRenderer content={section.body} />
          </div>
        </details>
      ))}
    </div>
  );
}


interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  // 8.11：公司歧义候选确认（后端 company.candidates → 点选 → company.confirm 重跑）
  // 契约修复：v3.1 mention 分组协议（多候选在 mentions[]，带 mention_id+revision）
  pendingCandidates?: PendingCompanyCandidates | null;
  onConfirmCompany?: (turnId: string, mentionId: string, revision: number, windCode: string) => void;
  // v3.3.1 §8.2 契约修复：分段歧义澄清提示（entity.clarification_required）
  clarificationIssue?: string | null;
  onDismissClarification?: () => void;
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
  pendingCandidates,
  onConfirmCompany,
  clarificationIssue,
  onDismissClarification,
  onNavigateStep,
}: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const [confirmingCode, setConfirmingCode] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [msgParent] = useAutoAnimate();

  // 8.11 P0（审查）+ 契约修复：新候选轮次（turn_id 或 revision 变化）重置确认状态，
  // 避免第二次歧义或同轮后续 mention 确认时按钮全部被禁用
  useEffect(() => {
    setConfirmingCode(null);
  }, [pendingCandidates?.turn_id, pendingCandidates?.revision]);

  // 8.11/契约修复：确认候选公司（点击后禁用重复选择，等待后端重跑原问题）
  // mention 分组协议：mention_id 原样回传（旧协议空 mention_id 走后端兼容路径）
  const handleConfirm = (mentionId: string, windCode: string) => {
    if (!pendingCandidates || confirmingCode) return;
    setConfirmingCode(windCode);
    onConfirmCompany?.(pendingCandidates.turn_id, mentionId, pendingCandidates.revision, windCode);
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
        <div ref={msgParent} className="p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-8">
              <Shield className="h-10 w-10 text-primary/40 mx-auto mb-3" />
              <h3 className="text-base font-medium text-foreground mb-1">织网鉴真 · 财报反欺诈助手</h3>
              <p className="text-xs text-muted-foreground mb-6">输入上市公司名称或股票代码，穿透股权 · 交叉验证 · 对齐舆情</p>
              <div className="grid grid-cols-2 gap-2 max-w-lg mx-auto">
                {[
                  { icon: TrendingUp, label: '财务核查', text: '分析金牌家居的财务风险，并给出量化参考和核查建议' },
                  { icon: FileText, label: '证据回查', text: '解释比亚迪现金流–利润背离的原始财报证据' },
                  { icon: Zap, label: '股权穿透', text: '查看金牌家居的主要股东与股权穿透链路' },
                  { icon: Shield, label: '横向对比', text: '对比华峰化学、中泰化学和利尔化学的财务风险' },
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

          {messages.map(message => (
            <MessageBubble
              key={message.id}
              message={message}
              onFollowUp={onSendMessage}
              onNavigateStep={onNavigateStep}
            />
          ))}

          {/* v3.3.1 §8.2 契约修复：分段歧义澄清提示 */}
          {clarificationIssue && (
            <div className="max-w-[70%] rounded-lg border border-yellow-500/40 bg-yellow-500/5 p-3">
              <p className="text-sm font-medium text-foreground mb-1">需要澄清</p>
              <p className="text-xs text-muted-foreground">{clarificationIssue}</p>
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 h-7 px-2 text-xs"
                onClick={onDismissClarification}
              >
                知道了
              </Button>
            </div>
          )}

          {/* 8.11 契约修复：公司歧义候选确认卡片（mention 分组协议） */}
          {pendingCandidates && pendingCandidates.mentions.length > 0 && (
            <div className="max-w-[70%] rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-3">
              <p className="text-sm font-medium text-foreground">
                检测到多家公司，请选择您想问的是哪一家：
              </p>
              {pendingCandidates.mentions.map(mention => (
                <div key={mention.mention_id || `flat-${mention.text || '0'}`} className="space-y-1.5">
                  {mention.text && (
                    <p className="text-xs text-muted-foreground">关于「{mention.text}」：</p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {mention.candidates.map(c => (
                      <Button
                        key={`${mention.mention_id || 'flat'}-${c.wind_code}`}
                        variant={confirmingCode === c.wind_code ? 'default' : 'outline'}
                        size="sm"
                        className="h-auto py-1.5 text-xs"
                        disabled={Boolean(confirmingCode)}
                        onClick={() => handleConfirm(mention.mention_id, c.wind_code)}
                      >
                        {c.sec_name}
                        <span className="ml-1 text-[10px] opacity-70">{c.wind_code}</span>
                      </Button>
                    ))}
                  </div>
                </div>
              ))}
              {confirmingCode && (
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
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
            placeholder="输入问题，如：分析金牌家居的财务风险并查看核查建议..."
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
  onFollowUp,
  onNavigateStep,
}: {
  message: Message;
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
      )}>
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
            <StructuredAnswer content={message.content} />
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

        {/* 来源引用（演示整改：标题=规则名·期次，来源类型仅非财务类展示，避免整列同质化） */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <p className="text-xs text-muted-foreground mb-1">来源：</p>
            <div className="space-y-1">
              {message.sources.map(source => {
                const typeLabel = SOURCE_TYPE_LABELS[source.source] || '';
                return (
                  <div key={source.id} className="flex items-start gap-1 text-xs text-muted-foreground">
                    <span className="shrink-0">•</span>
                    <span className="min-w-0">
                      <span className="text-foreground/80">{source.title}</span>
                      {typeLabel && source.source !== 'financial_statement' && (
                        <span className="ml-1.5 rounded bg-muted px-1 text-[10px]">{typeLabel}</span>
                      )}
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
                    </span>
                  </div>
                );
              })}
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

        {/* 会4 收口：数据与口径限制说明模块 */}
        {!isUser && (
          <div className="mt-2 pt-2 border-t border-border/30">
            <div className="flex items-start gap-2 rounded-md bg-muted/40 px-3 py-2">
              <Info className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                数据与口径限制：以上分析基于已接入的财报及公开披露数据，可能存在数据时滞或缺失；
                触发阈值与规则口径为团队配置，结果仅供参考，不构成投资建议。
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
