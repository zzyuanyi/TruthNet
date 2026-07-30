// 织网鉴真 TruthNet - 对话主页
// T1: 三栏布局（会话侧边栏 + 对话区 + 分析面板）
// Phase B: 会话管理本地 mock，对话通过 V12 WebSocket 连接后端

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { SessionSidebar } from '@/components/truthnet/SessionSidebar';
import { ChatInterface } from '@/components/truthnet/ChatInterface';
import { AnalysisPanel } from '@/components/truthnet/AnalysisPanel';
import { mockSessions, mockMessages } from '@/data/mock';
import type { Session, Message, PanelData, PanelState } from '@/types/truthnet';
import type { WSEvent } from '@/types/truthnet';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

/** 按当前页面协议和 host 生成 WS URL */
function wsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/v1/chat/ws`;
}

export default function ChatPage() {
  // ── 会话管理（Phase B 本地 mock） ──
  const [sessions, setSessions] = useState<Session[]>(mockSessions);
  const [currentSessionId, setCurrentSessionId] = useState<string>(mockSessions[0]?.id || '');
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [panelState, setPanelState] = useState<PanelState>('done');
  const [panelError, setPanelError] = useState<string>('');
  const [panelCollapsed, setPanelCollapsed] = useState(false);

  // ── 活动 WebSocket（useRef 避免闭包陈旧值，卸载时关闭） ──
  const wsRef = useRef<WebSocket | null>(null);
  const pendingMsgRef = useRef<string>(''); // 本轮待累积的回答文本

  // 组件卸载 → 关闭连接
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const closeWs = () => {
    wsRef.current?.close();
    wsRef.current = null;
  };

  const currentSession = sessions.find(s => s.id === currentSessionId);

  // ── 会话操作（Phase B 本地 mock，不做后端持久化） ──
  const handleNewSession = () => {
    const newSession: Session = {
      id: `session-${Date.now()}`,
      title: '新对话',
      company_code: '',
      company_name: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    };
    setSessions([newSession, ...sessions]);
    setCurrentSessionId(newSession.id);
    setMessages([]);
    setPanelData(null);
    setPanelState('empty');
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      setMessages(mockMessages.filter(m => m.session_id === sessionId));
      setPanelState('done');
    }
  };

  const handleDeleteSession = (sessionId: string) => {
    const newSessions = sessions.filter(s => s.id !== sessionId);
    setSessions(newSessions);
    if (currentSessionId === sessionId) {
      setCurrentSessionId(newSessions[0]?.id || '');
      setMessages([]);
      setPanelData(null);
      setPanelState('empty');
    }
  };

  // ── 发送消息 → V12 WebSocket ──
  const handleSendMessage = (content: string) => {
    // 关闭上一次连接（如果有）
    closeWs();

    // 用户消息
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      session_id: currentSessionId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);
    setPanelState('thinking');
    pendingMsgRef.current = '';

    // 占位 assistant 消息
    const assistantId = `msg-${Date.now() + 1}`;
    const assistantMessage: Message = {
      id: assistantId,
      session_id: currentSessionId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    // 建立 WebSocket
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        event_type: 'chat.query',
        payload: { text: content, session_id: currentSessionId },
      }));
    };

    ws.onmessage = (event) => {
      let msg: WSEvent;
      try {
        msg = JSON.parse(event.data) as WSEvent;
      } catch {
        return;
      }

      switch (msg.event_type) {
        case 'module.started':
        case 'module.completed':
          setPanelState('streaming');
          break;

        case 'answer.delta':
          // 累积流式文本
          pendingMsgRef.current += (msg.payload?.text as string) || '';
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, content: pendingMsgRef.current }
              : m
          ));
          break;

        case 'artifact.upsert': {
          // 当前后端仅提供 risk_level，补齐空数组避免面板崩溃
          const raw = (msg.payload?.data || {}) as Record<string, unknown>;
          const level = raw.risk_level as string | undefined;
          const VALID_LEVELS = ['red', 'orange', 'yellow', 'blue', 'green'];
          if (level && VALID_LEVELS.includes(level)) {
            setPanelData({
              risk_level: level as PanelData['risk_level'],
              triggered_rules: [],
              key_metrics: [],
            });
          }
          break;
        }

        case 'turn.completed': {
          const payload = msg.payload as Record<string, unknown>;
          const answer = (payload?.answer as string) || pendingMsgRef.current;
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? {
                  ...m,
                  content: answer,
                  follow_ups: (payload?.follow_ups as string[]) || [],
                }
              : m
          ));
          setPanelState('done');
          setPanelError('');
          closeWs();
          break;
        }

        case 'turn.failed': {
          const reason = (msg.payload as Record<string, unknown>)?.message as string || '处理请求时发生内部错误';
          setPanelState('error');
          setPanelError(reason);
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, content: `⚠️ ${reason}` }
              : m
          ));
          closeWs();
          break;
        }

        case 'turn.cancelled':
          setPanelState('done');
          setPanelError('');
          closeWs();
          break;
      }
    };

    ws.onerror = () => {
      setPanelState('error');
      setPanelError('网络连接失败，请检查后端服务是否启动');
      closeWs();
    };
  };

  // ── 追问 ──
  const handleFollowUp = (suggestion: string) => {
    handleSendMessage(suggestion);
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={panelState === 'thinking' || panelState === 'streaming'}
        />
      </div>

      <div
        className={cn(
          'transition-all duration-300 border-l border-border',
          panelCollapsed ? 'w-0 overflow-hidden' : 'w-[380px]'
        )}
      >
        {!panelCollapsed && (
          <AnalysisPanel
            state={panelState}
            data={panelData}
            errorMessage={panelError}
            company={currentSession ? {
              code: currentSession.company_code,
              name: currentSession.company_name,
            } : undefined}
            onFollowUp={handleFollowUp}
          />
        )}
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="absolute right-4 top-20 z-10"
        onClick={() => setPanelCollapsed(!panelCollapsed)}
      >
        {panelCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
      </Button>
    </div>
  );
}
