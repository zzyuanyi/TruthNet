// 织网鉴真 TruthNet - 会话侧边栏

import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Plus, MessageSquare, Trash2, Building2, BarChart3 } from 'lucide-react';
import type { Session } from '@/types/truthnet';

interface SessionSidebarProps {
  sessions: Session[];
  currentSessionId: string;
  currentCompanyCode?: string | null;
  // 8.11（C9）：本对话涉及的公司（去重后的 code 列表，每公司一个画像入口）
  involvedCompanies?: string[];
  isBusy?: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
}

export function SessionSidebar({
  sessions,
  currentSessionId,
  currentCompanyCode,
  involvedCompanies = [],
  isBusy = false,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}: SessionSidebarProps) {
  const navigate = useNavigate();

  return (
    <div className="w-60 border-r border-border flex flex-col bg-muted/30 h-full">
      {/* 头部：新建会话按钮 */}
      <div className="p-4 border-b border-border">
        <Button
          className="w-full justify-start gap-2"
          variant="outline"
          onClick={onNewSession}
          disabled={isBusy}
        >
          <Plus className="h-4 w-4" />
          新建对话
        </Button>
      </div>

      {/* 快捷入口 */}
      <div className="p-2 border-b border-border space-y-1">
        {/* 8.11（C9）：本对话每家公司一个画像入口；Header 的"当前公司"仍表示最近一家 */}
        {involvedCompanies.length > 0 ? (
          <>
            <p className="px-2 pt-1 text-[10px] text-muted-foreground">
              本对话涉及公司（{involvedCompanies.length}）
            </p>
            {involvedCompanies.map(code => (
              <Button
                key={code}
                variant="ghost"
                className="w-full justify-start gap-2 h-9"
                onClick={() => navigate(`/company/${encodeURIComponent(code)}`)}
                disabled={isBusy}
                title={`查看 ${code} 企业画像`}
              >
                <Building2 className="h-4 w-4 shrink-0" />
                <span className="truncate text-xs">{code}</span>
              </Button>
            ))}
          </>
        ) : (
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 h-9"
            onClick={() => currentCompanyCode && navigate(`/company/${encodeURIComponent(currentCompanyCode)}`)}
            disabled={!currentCompanyCode || isBusy}
            title={currentCompanyCode ? `查看 ${currentCompanyCode} 企业画像` : '当前会话尚未解析企业'}
          >
            <Building2 className="h-4 w-4" />
            企业画像
          </Button>
        )}
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9"
          onClick={() => navigate('/compare')}
          disabled={isBusy}
        >
          <BarChart3 className="h-4 w-4" />
          跨公司对比
        </Button>
      </div>

      {/* 会话列表（min-h-0：flex item 默认 min-height:auto 会按内容高度阻止收缩，导致列表撑开布局） */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-2 space-y-1">
          {sessions.map(session => (
            <div
              key={session.session_id}
              className={cn(
                'group flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors',
                'hover:bg-accent',
                isBusy && session.session_id !== currentSessionId && 'cursor-not-allowed opacity-60',
                currentSessionId === session.session_id && 'bg-accent'
              )}
              onClick={() => {
                if (!isBusy || session.session_id === currentSessionId) {
                  onSelectSession(session.session_id);
                }
              }}
              aria-disabled={isBusy && session.session_id !== currentSessionId}
            >
              {/* 会话信息 */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {session.title}
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {session.turn_count > 0 ? `${session.turn_count} 轮问答` : '新对话'}
                </div>
              </div>

              {/* 会话轮数徽标 */}
              <Badge variant="secondary" className="shrink-0 text-xs px-1.5 py-0">
                {isBusy && session.session_id === currentSessionId ? '分析中' : session.turn_count}
              </Badge>

              {/* 删除按钮 */}
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0 opacity-60 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"
                aria-label={`删除会话：${session.title}`}
                title="删除会话"
                disabled={isBusy}
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.session_id);
                }}
              >
                <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
              </Button>
            </div>
          ))}

          {sessions.length === 0 && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
              暂无对话
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
