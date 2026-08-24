// 织网鉴真 TruthNet - 会话侧边栏

import { useAutoAnimate } from '@formkit/auto-animate/react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Plus, MessageSquare, Trash2, Building2, BarChart3 } from 'lucide-react';
import type { Session } from '@/types/truthnet';
import type { InvolvedCompany } from '@/pages/ChatPage';

interface SessionSidebarProps {
  sessions: Session[];
  currentSessionId: string;
  currentCompanyCode?: string | null;
  // 8.11（C9）：本对话涉及的公司（去重后的 code 列表，每公司一个画像入口）
  // 8/23：携带公司名，展示"名称（代码）"
  involvedCompanies?: InvolvedCompany[];
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
  const [listParent] = useAutoAnimate();
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
            {involvedCompanies.map(company => (
              <Button
                key={company.code}
                variant="ghost"
                className="w-full justify-start gap-2 h-9"
                onClick={() => navigate(`/company/${encodeURIComponent(company.code)}`)}
                disabled={isBusy}
                title={`查看 ${company.name || company.code} 企业画像`}
              >
                <Building2 className="h-4 w-4 shrink-0" />
                <span className="truncate text-xs">
                  {company.name ? `${company.name}（${company.code}）` : company.code}
                </span>
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
      <div className="flex-1 min-h-0 min-w-0 overflow-y-auto">
        <div ref={listParent} className="w-full min-w-0 p-2 space-y-1">
          {sessions.map(session => (
            <div
              key={session.session_id}
              className={cn(
                'group flex w-full min-w-0 items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors',
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
                size="sm"
                className="h-7 shrink-0 gap-1 px-1.5 text-xs text-muted-foreground hover:text-destructive"
                aria-label={`删除会话：${session.title}`}
                title="删除会话"
                disabled={isBusy}
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm(`确认删除对话“${session.title}”？此操作不可恢复。`)) {
                    onDeleteSession(session.session_id);
                  }
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
                删除
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
      </div>
    </div>
  );
}
