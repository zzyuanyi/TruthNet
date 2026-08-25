// 织网鉴真 TruthNet - 会话侧边栏

import { useAutoAnimate } from '@formkit/auto-animate/react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Plus, MessageSquare, Trash2, Building2, BarChart3, PanelLeftClose } from 'lucide-react';
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
  onCollapse?: () => void;
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
  onCollapse,
}: SessionSidebarProps) {
  const [listParent] = useAutoAnimate();
  const navigate = useNavigate();

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* 头部：新建会话按钮 + 收起 */}
      <div className="flex items-center gap-2 border-b border-border p-4">
        <Button
          className="flex-1 justify-start gap-2"
          variant="outline"
          onClick={onNewSession}
          disabled={isBusy}
        >
          <Plus className="h-4 w-4" />
          新建对话
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0 text-muted-foreground hover:text-foreground"
          aria-label="收起会话侧边栏"
          title="收起会话侧边栏"
          onClick={onCollapse}
        >
          <PanelLeftClose className="h-4 w-4" />
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
                'group w-full min-w-0 rounded-md px-3 py-2 cursor-pointer transition-colors',
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
              <div className="min-w-0" title={session.title}>
                <div className="line-clamp-2 text-sm font-medium leading-5">
                  {session.title}
                </div>
              </div>

              <div className="mt-1 flex items-center justify-between gap-2">
                <div className="text-xs text-muted-foreground">
                  {session.turn_count > 0 ? `${session.turn_count} 轮问答` : '新对话'}
                </div>

                <div className="shrink-0">
                  {/* 删除按钮 */}
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="h-6 w-6 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100"
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
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
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