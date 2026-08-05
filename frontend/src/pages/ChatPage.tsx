// 织网鉴真 TruthNet - 对话主页
// T1: 三栏布局（会话侧边栏 + 对话区 + 分析面板）
// Phase 1: 对接真实 API

import { useState, useEffect, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import { SessionSidebar } from '@/components/truthnet/SessionSidebar';
import { ChatInterface } from '@/components/truthnet/ChatInterface';
import { AnalysisPanel } from '@/components/truthnet/AnalysisPanel';
import { apiClient, wsClient } from '@/lib/api-client';
import type { Session, Message, PanelData, PanelState, ChatDataV1 } from '@/types/truthnet';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ChatPage() {
  // 状态管理
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [panelState, setPanelState] = useState<PanelState>('empty');
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<ReturnType<typeof wsClient.create> | null>(null);

  // Task 7: 面板联动状态
  const [activeRuleId, setActiveRuleId] = useState<string | null>(null);
  const [filteredEvidenceIds, setFilteredEvidenceIds] = useState<string[] | null>(null);

  // 当前会话
  const currentSession = sessions.find(s => s.session_id === currentSessionId);

  // 加载会话列表
  useEffect(() => {
    const loadSessions = async () => {
      try {
        const response = await apiClient.getSessions();
        // 后端 V12 envelope: data.sessions（对象内数组）；兼容旧结构 data 直接为数组
        const data = response.data as { sessions?: Session[] } | Session[] | null;
        const sessionsData = Array.isArray(data) ? data : (data?.sessions || []);
        setSessions(sessionsData);
        if (sessionsData.length > 0 && !currentSessionId) {
          setCurrentSessionId(sessionsData[0].session_id);
        }
      } catch (error) {
        console.error('Failed to load sessions:', error);
      }
    };
    loadSessions();
  }, []);

  // 加载会话消息
  useEffect(() => {
    if (!currentSessionId) return;
    
    // 会话消息通过 WebSocket 实时获取，这里不需要额外加载
    setMessages([]);
    setPanelState('done');
  }, [currentSessionId]);

  // 创建新会话
  const handleNewSession = async () => {
    try {
      const response = await apiClient.createSession('新对话');
      const newSession: Session = {
        session_id: response.data?.session_id || `session-${Date.now()}`,
        title: '新对话',
        created_at: response.data?.created_at || new Date().toISOString(),
        updated_at: response.data?.updated_at || new Date().toISOString(),
        message_count: 0,
      };
      setSessions([newSession, ...sessions]);
      setCurrentSessionId(newSession.session_id);
      setMessages([]);
      setPanelData(null);
      setPanelState('empty');
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  // 切换会话
  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  // 删除会话
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await apiClient.deleteSession(sessionId);
      const newSessions = sessions.filter(s => s.session_id !== sessionId);
      setSessions(newSessions);
      if (currentSessionId === sessionId) {
        setCurrentSessionId(newSessions[0]?.session_id || '');
        setMessages([]);
        setPanelData(null);
        setPanelState('empty');
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  // 处理 WebSocket 事件 (V12 信封协议)
  const handleWSEvent = useCallback((event: { event_type: string; payload?: unknown; type?: string; data?: unknown }) => {
    const eventType = event.event_type || event.type || '';
    const payload = event.payload || event.data;
    switch (eventType) {
      case 'thinking':
        setPanelState('thinking');
        break;
      case 'text_chunk': {
        const chunk = payload as { content: string };
        setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + chunk.content }];
          }
          return [...prev, { id: `msg-${Date.now()}`, role: 'assistant', content: chunk.content, created_at: new Date().toISOString() }];
        });
        setPanelState('streaming');
        break;
      }
      case 'structured_data': {
        setPanelData(payload as PanelData);
        break;
      }
      case 'evidence': {
        const ev = payload as { evidence_ids: string[] };
        if (ev.evidence_ids) {
          setFilteredEvidenceIds(ev.evidence_ids);
          setMessages(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant') {
                updated[i] = { ...updated[i], evidence_ids: ev.evidence_ids };
                break;
              }
            }
            return updated;
          });
        }
        break;
      }
      case 'done': {
        const result = payload as { follow_ups?: string[]; evidence_ids?: string[]; trace_id?: string };
        if (result?.follow_ups) {
          setMessages(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant') {
                updated[i] = { ...updated[i], follow_ups: result.follow_ups };
                break;
              }
            }
            return updated;
          });
        }
        setPanelState('done');
        setIsLoading(false);
        break;
      }
      case 'error':
        console.error('WebSocket error:', payload);
        setPanelState('error');
        setIsLoading(false);
        break;
      // 旧格式兼容
      case 'turn.accepted':
        setPanelState('thinking');
        break;
      case 'answer.delta': {
        const delta = payload as { content: string };
        setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + delta.content }];
          }
          return [...prev, { id: `msg-${Date.now()}`, role: 'assistant', content: delta.content, created_at: new Date().toISOString() }];
        });
        setPanelState('streaming');
        break;
      }
      case 'turn.completed': {
        const result = payload as { follow_ups?: string[]; evidence_ids?: string[]; trace_id?: string };
        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant') {
              updated[i] = { ...updated[i], evidence_ids: result?.evidence_ids || [], follow_ups: result?.follow_ups || [] };
              break;
            }
          }
          return updated;
        });
        setPanelState('done');
        setIsLoading(false);
        break;
      }
      case 'turn.failed':
        setPanelState('error');
        setIsLoading(false);
        break;
      case 'company.candidates':
        break;
      case 'heartbeat':
        break;
    }
  }, [currentSessionId]);

  // 连接 WebSocket
  useEffect(() => {
    if (!currentSessionId) return;
    
    wsRef.current = wsClient.create(currentSessionId, handleWSEvent);
    
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [currentSessionId, handleWSEvent]);

  // 发送消息
  const handleSendMessage = async (content: string) => {
    if (!currentSessionId || isLoading) return;
    
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setPanelState('thinking');

    try {
      wsRef.current?.send(content);
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsLoading(false);
      setPanelState('error');
    }
  };

  // 点击追问建议
  const handleFollowUp = (suggestion: string) => {
    handleSendMessage(suggestion);
  };

  // Task 7: 面板联动 - 点击规则
  const handleRuleClick = useCallback((ruleId: string) => {
    setActiveRuleId(ruleId);
    const msgIndex = messages.findIndex(m => 
      m.role === 'assistant' && m.evidence_ids && m.evidence_ids.length > 0
    );
    if (msgIndex >= 0) {
      const msgElement = document.getElementById(`msg-${msgIndex}`);
      msgElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setPanelCollapsed(false);
  }, [messages]);

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* 左侧：会话侧边栏 */}
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* 中间：对话区 */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
        />
      </div>

      {/* 右侧：分析面板 */}
      <div
        className={cn(
          'transition-all duration-300 border-l border-border',
          panelCollapsed ? 'w-0 overflow-hidden' : 'w-[clamp(360px,25vw,440px)]'
        )}
      >
        {!panelCollapsed && (
          <AnalysisPanel
            state={panelState}
            data={panelData}
            company={undefined}
            onFollowUp={handleFollowUp}
            onRuleClick={handleRuleClick}
          />
        )}
      </div>

      {/* 面板折叠/展开按钮 */}
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
