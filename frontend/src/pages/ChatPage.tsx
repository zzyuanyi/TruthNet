// 织网鉴真 TruthNet - 对话主页
// T1: 三栏布局（会话侧边栏 + 对话区 + 分析面板）

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { SessionSidebar } from '@/components/truthnet/SessionSidebar';
import { ChatInterface } from '@/components/truthnet/ChatInterface';
import { AnalysisPanel } from '@/components/truthnet/AnalysisPanel';
import { mockSessions, mockMessages, mockPanelData } from '@/data/mock';
import type { Session, Message, PanelData, PanelState } from '@/types/truthnet';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ChatPage() {
  // 状态管理
  const [sessions, setSessions] = useState<Session[]>(mockSessions);
  const [currentSessionId, setCurrentSessionId] = useState<string>(mockSessions[0]?.id || '');
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [panelData, setPanelData] = useState<PanelData | null>(mockPanelData);
  const [panelState, setPanelState] = useState<PanelState>('done');
  const [panelCollapsed, setPanelCollapsed] = useState(false);

  // 当前会话
  const currentSession = sessions.find(s => s.id === currentSessionId);

  // 创建新会话
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

  // 切换会话
  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    // 实际项目中，这里应该从后端加载对应会话的消息和面板数据
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      setMessages(mockMessages.filter(m => m.session_id === sessionId));
      setPanelState('done');
    }
  };

  // 删除会话
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

  // 发送消息
  const handleSendMessage = (content: string) => {
    // 添加用户消息
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      session_id: currentSessionId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages([...messages, userMessage]);
    setPanelState('thinking');

    // 模拟 AI 响应（实际项目中通过 WebSocket）
    setTimeout(() => {
      const assistantMessage: Message = {
        id: `msg-${Date.now() + 1}`,
        session_id: currentSessionId,
        role: 'assistant',
        content: `收到您的问题："${content}"\n\n正在分析中...\n\n这是模拟的 AI 响应。实际项目中，这里会通过 WebSocket 流式返回分析结果。`,
        created_at: new Date().toISOString(),
        thinking: '正在获取数据...正在执行分析...',
        structured_data: mockPanelData,
        follow_ups: ['查看更多细节', '对比同行业公司', '查看股权穿透图'],
      };
      setMessages(prev => [...prev, assistantMessage]);
      setPanelData(mockPanelData);
      setPanelState('done');
    }, 2000);
  };

  // 点击追问建议
  const handleFollowUp = (suggestion: string) => {
    handleSendMessage(suggestion);
  };

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
          isLoading={panelState === 'thinking' || panelState === 'streaming'}
        />
      </div>

      {/* 右侧：分析面板 */}
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
            company={currentSession ? {
              code: currentSession.company_code,
              name: currentSession.company_name,
            } : undefined}
            onFollowUp={handleFollowUp}
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
