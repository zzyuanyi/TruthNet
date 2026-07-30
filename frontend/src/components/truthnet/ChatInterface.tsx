// 织网鉴真 TruthNet - 对话界面

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, User, Bot, AlertTriangle } from 'lucide-react';
import type { Message, RiskLevel } from '@/types/truthnet';
import ReactMarkdown from 'react-markdown';

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (content: string) => void;
  isLoading: boolean;
}

// 风险等级颜色
const riskColors: Record<RiskLevel, string> = {
  red: 'text-red-500 bg-red-500/10 border-red-500/20',
  orange: 'text-orange-500 bg-orange-500/10 border-orange-500/20',
  yellow: 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20',
  blue: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
  green: 'text-green-500 bg-green-500/10 border-green-500/20',
};

export function ChatInterface({ messages, onSendMessage, isLoading }: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

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
      {/* 消息列表 */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
                <AlertTriangle className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-medium mb-2">开始分析</h3>
              <p className="text-muted-foreground text-sm max-w-md mx-auto">
                输入公司名称或问题，开始财报反欺诈分析。例如："帮我分析康美药业的财务异常情况"
              </p>
            </div>
          )}

          {messages.map(message => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* 加载指示器 */}
          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">正在分析...</span>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* 输入区域 */}
      <div className="border-t border-border p-4">
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
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex gap-3', isUser ? 'justify-end' : 'justify-start')}>
      {/* 头像 */}
      <div className={cn(
        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
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
          <div className="text-xs text-muted-foreground mb-2 italic">
            💭 {message.thinking}
          </div>
        )}

        {/* 主要内容 */}
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* 追问建议 */}
        {message.follow_ups && message.follow_ups.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border/50">
            {message.follow_ups.map((suggestion, i) => (
              <Badge
                key={i}
                variant="outline"
                className="cursor-pointer hover:bg-accent transition-colors"
              >
                {suggestion}
              </Badge>
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
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
