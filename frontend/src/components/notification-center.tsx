'use client';

import { useState, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Server,
  FileCheck,
  X,
  Check,
  Trash2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ─── Types ─── */
type NotifType = 'success' | 'warning' | 'info' | 'error';
type NotifCategory = 'model' | 'service' | 'approval' | 'system';

interface Notification {
  id: string;
  type: NotifType;
  category: NotifCategory;
  title: string;
  description: string;
  time: string;
  read: boolean;
  actionUrl?: string;
}

/* ─── Mock Notifications ─── */
const INITIAL_NOTIFICATIONS: Notification[] = [
  {
    id: 'n1',
    type: 'success',
    category: 'model',
    title: '模型训练完成',
    description: '反欺诈实时风控模型 v3.2 训练完成，AUC=0.967',
    time: '3 分钟前',
    read: false,
    actionUrl: '/repository/1',
  },
  {
    id: 'n2',
    type: 'error',
    category: 'service',
    title: '服务异常告警',
    description: '信用评分服务 API 响应超时率上升至 5.2%，P99 延迟 > 2000ms',
    time: '15 分钟前',
    read: false,
    actionUrl: '/service',
  },
  {
    id: 'n3',
    type: 'info',
    category: 'approval',
    title: '审批待处理',
    description: '反欺诈模型 v3.2 等待合规确认，审批人：王五',
    time: '1 小时前',
    read: false,
    actionUrl: '/repository/1',
  },
  {
    id: 'n4',
    type: 'success',
    category: 'service',
    title: '服务部署成功',
    description: '贷前风控评分卡服务已上线，当前 QPS: 128',
    time: '2 小时前',
    read: true,
    actionUrl: '/service',
  },
  {
    id: 'n5',
    type: 'warning',
    category: 'model',
    title: '模型漂移预警',
    description: '客户流失预测模型 PSI=0.18，超过阈值 0.15，建议重新训练',
    time: '3 小时前',
    read: true,
    actionUrl: '/repository/3',
  },
  {
    id: 'n6',
    type: 'info',
    category: 'system',
    title: '数据接入完成',
    description: 'credit_data_2025.csv 已完成数据探查，共 856,423 行 36 列',
    time: '5 小时前',
    read: true,
    actionUrl: '/tasks',
  },
  {
    id: 'n7',
    type: 'success',
    category: 'approval',
    title: '审批已通过',
    description: '贷前风控评分卡模型合规确认已通过，可部署上线',
    time: '昨天 16:30',
    read: true,
    actionUrl: '/repository/2',
  },
];

/* ─── Helpers ─── */
const typeIcon: Record<NotifType, typeof CheckCircle2> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  info: Clock,
  error: AlertTriangle,
};

const typeColor: Record<NotifType, string> = {
  success: 'text-emerald-500',
  warning: 'text-amber-500',
  info: 'text-blue-500',
  error: 'text-red-500',
};

const categoryIcon: Record<NotifCategory, typeof Server> = {
  model: FileCheck,
  service: Server,
  approval: CheckCircle2,
  system: Clock,
};

const categoryLabel: Record<NotifCategory, string> = {
  model: '模型',
  service: '服务',
  approval: '审批',
  system: '系统',
};

/* ─── Component ─── */
export function NotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>(INITIAL_NOTIFICATIONS);
  const [isOpen, setIsOpen] = useState(false);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const deleteNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  // Auto-mark as read when popover opens
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(markAllRead, 2000);
      return () => clearTimeout(timer);
    }
  }, [isOpen, markAllRead]);

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button className="relative flex items-center justify-center rounded-lg p-2 text-gray-500 transition-all duration-200 hover:bg-gray-100 hover:scale-110 active:scale-95">
          <Bell className="h-5.5 w-5.5" />
          {unreadCount > 0 && (
            <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        side="right"
        className="w-[calc(100vw-2rem)] sm:w-[380px] p-0 rounded-xl shadow-xl border-border/60"
        sideOffset={8}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold">通知中心</h4>
            {unreadCount > 0 && (
              <Badge className="bg-red-100 text-red-700 text-[10px] px-1.5 py-0 hover:bg-red-100">
                {unreadCount} 条未读
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            {notifications.length > 0 && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-[11px] gap-1 text-muted-foreground hover:text-foreground"
                  onClick={markAllRead}
                >
                  <Check className="h-3 w-3" />
                  全部已读
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-[11px] gap-1 text-muted-foreground hover:text-red-600"
                  onClick={clearAll}
                >
                  <Trash2 className="h-3 w-3" />
                  清空
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Notification List */}
        <ScrollArea className="h-[420px]">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Bell className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-sm">暂无通知</p>
            </div>
          ) : (
            <div className="divide-y divide-border/40">
              {notifications.map((notif) => {
                const TypeIcon = typeIcon[notif.type];
                const CatIcon = categoryIcon[notif.category];
                return (
                  <div
                    key={notif.id}
                    className={cn(
                      'group relative px-4 py-3 transition-colors hover:bg-accent/30 cursor-pointer',
                      !notif.read && 'bg-blue-50/40'
                    )}
                    onClick={() => markAsRead(notif.id)}
                  >
                    {/* Unread dot */}
                    {!notif.read && (
                      <span className="absolute left-1.5 top-1/2 -translate-y-1/2 h-1.5 w-1.5 rounded-full bg-blue-500" />
                    )}
                    <div className="flex gap-3">
                      <div className={cn('mt-0.5 shrink-0', typeColor[notif.type])}>
                        <TypeIcon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={cn('text-sm font-medium truncate', !notif.read && 'font-semibold')}>
                            {notif.title}
                          </span>
                          <Badge
                            variant="outline"
                            className="text-[9px] px-1 py-0 shrink-0 bg-muted/50"
                          >
                            <CatIcon className="h-2.5 w-2.5 mr-0.5" />
                            {categoryLabel[notif.category]}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                          {notif.description}
                        </p>
                        <span className="text-[10px] text-muted-foreground/60 mt-1 inline-block">
                          {notif.time}
                        </span>
                      </div>
                      {/* Delete button */}
                      <button
                        className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5 h-5 w-5 flex items-center justify-center rounded text-muted-foreground hover:text-red-500 hover:bg-red-50"
                        onClick={(e) => { e.stopPropagation(); deleteNotification(notif.id); }}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        {notifications.length > 0 && (
          <>
            <Separator />
            <div className="px-4 py-2 text-center">
              <span className="text-[11px] text-muted-foreground">
                共 {notifications.length} 条通知
              </span>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
