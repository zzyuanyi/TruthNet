// 织网鉴真 TruthNet - 对话主页
// T1: 三栏布局（会话侧边栏 + 对话区 + 分析面板）
// Phase 1: 对接真实 API

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { SessionSidebar } from '@/components/truthnet/SessionSidebar';
import { ChatInterface } from '@/components/truthnet/ChatInterface';
import { AnalysisPanel } from '@/components/truthnet/AnalysisPanel';
import { apiClient, wsClient } from '@/lib/api-client';
import { comparisonStepToUrl } from '@/lib/comparison-steps';
import type {
  Session,
  Message,
  PanelData,
  PanelState,
  ChatDataV1,
  RiskLevel,
  ModuleStatusV1,
  ComparisonNextStep,
} from '@/types/truthnet';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ChatPage() {
  const navigate = useNavigate();
  // 状态管理
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [currentCompanyCode, setCurrentCompanyCode] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [panelState, setPanelState] = useState<PanelState>('empty');
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<ReturnType<typeof wsClient.create> | null>(null);
  // 8.11：待确认公司候选（后端 company.candidates 事件，选择后重跑原问题）
  const [pendingCandidates, setPendingCandidates] = useState<{
    turn_id: string;
    candidates: Array<{ wind_code: string; sec_name: string }>;
  } | null>(null);
  // 8.11（C9）：本对话涉及的公司列表（按 company_code 去重，每公司一个画像入口）
  const [involvedCompanies, setInvolvedCompanies] = useState<string[]>([]);

  // Task 7: 面板联动状态
  const [activeRuleId, setActiveRuleId] = useState<string | null>(null);
  const [filteredEvidenceIds, setFilteredEvidenceIds] = useState<string[] | null>(null);

  // Phase D: 模块进度追踪
  const [moduleStatus, setModuleStatus] = useState<Record<string, ModuleStatusV1> | null>(null);
  const [missingModules, setMissingModules] = useState<string[] | null>(null);

  const loadSessions = useCallback(async (selectFirst = false) => {
    try {
      const response = await apiClient.getSessions();
      const data = response.data as { sessions?: Session[] } | Session[] | null;
      const sessionsData = Array.isArray(data) ? data : (data?.sessions || []);
      setSessions(sessionsData);
      if (selectFirst && sessionsData.length > 0) {
        setCurrentSessionId(current => current || sessionsData[0].session_id);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }, []);

  // 加载会话列表
  useEffect(() => {
    void loadSessions(true);
  }, [loadSessions]);

  // 加载会话消息：切换会话时从后端拉取历史 turns（GET /sessions/{id}）
  useEffect(() => {
    if (!currentSessionId) return;
    let cancelled = false;
    setMessages([]);
    setPanelData(null);
    setPanelState('loading');
    apiClient
      .getSession(currentSessionId)
      .then(res => {
        if (cancelled) return;
        const turns = res.data?.turns || [];
        const latestCompanyCode = [...turns]
          .reverse()
          .find(turn => turn.company_code)?.company_code || null;
        setCurrentCompanyCode(latestCompanyCode);
        // 8.11（C9）：聚合本对话涉及的公司（去重）
        setInvolvedCompanies(
          [...new Set(
            turns.map(t => t.company_code).filter((c): c is string => Boolean(c)),
          )],
        );
        const msgs: Message[] = turns.flatMap(t => [
          {
            id: `q-${t.turn_id}`,
            role: 'user',
            content: t.question || '',
            created_at: t.created_at || '',
          },
          {
            id: `a-${t.turn_id}`,
            role: 'assistant',
            content: t.answer || '',
            created_at: t.created_at || '',
            // 历史会话证据链：后端 get_session 已带每轮 evidence_ids
            evidence_ids: t.evidence_ids || [],
            // P1-3：历史来源链接（后端已组装 {id,title,source,url}）
            sources: t.sources || [],
            show_evidence_status: Boolean(
              t.company_code || (t.evidence_ids || []).length > 0,
            ),
          },
        ]);
        setMessages(msgs);
        // 面板必须服从最后一轮语义：最后一轮是闲聊时，不复活更早的分析面板。
        const latestPanel = turns.at(-1)?.panel_data || null;
        setPanelData(latestPanel || null);
        setPanelState(latestPanel ? 'done' : 'empty');
      })
      .catch(err => {
        if (cancelled) return;
        console.error('Failed to load session messages:', err);
        setPanelState('empty');
      });
    return () => {
      cancelled = true;
    };
  }, [currentSessionId]);

  // 创建新会话
  const handleNewSession = async () => {
    try {
      const response = await apiClient.createSession('新对话');
      const newSession: Session = {
        session_id: response.data?.session_id || `session-${Date.now()}`,
        title: response.data?.title || '新对话',
        created_at: response.data?.created_at || new Date().toISOString(),
        updated_at: response.data?.updated_at || new Date().toISOString(),
        status: response.data?.status,
        turn_count: 0,
      };
      setSessions([newSession, ...sessions]);
      setCurrentSessionId(newSession.session_id);
      setMessages([]);
      setPanelData(null);
      setPanelState('empty');
      setCurrentCompanyCode(null);
      setInvolvedCompanies([]);
      setPendingCandidates(null);
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  // 切换会话
  const handleSelectSession = (sessionId: string) => {
    if (isLoading && sessionId !== currentSessionId) return;
    setCurrentSessionId(sessionId);
    // 切换会话时清空规则筛选（对齐审计 P1-3）与待确认候选（8.11）
    setActiveRuleId(null);
    setFilteredEvidenceIds(null);
    setPendingCandidates(null);
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
        setCurrentCompanyCode(null);
        setInvolvedCompanies([]);
        setPendingCandidates(null);
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
        setPendingCandidates(null);
        setPanelState('error');
        setIsLoading(false);
        break;
      // 旧格式兼容
      case 'turn.accepted':
        // 8.11 P0（审查）：新一轮开始，作废上一张候选卡
        // （候选确认后重跑的轮次在此清空已确认卡片）
        setPendingCandidates(null);
        setPanelState('loading');
        setModuleStatus(null);
        setMissingModules(null);
        break;
      case 'module.started':
        setPanelState('thinking');
        // Phase D: 跟踪模块启动
        setModuleStatus(prev => {
          const moduleName = (payload as { module?: string })?.module || 'unknown';
          return {
            ...(prev || {}),
            [moduleName]: { state: 'running', error_code: null, recoverable: true, duration_ms: null },
          };
        });
        break;
      case 'answer.delta': {
        // 服务器 V12 契约 payload.text 优先；旧 content 仅作兼容回退
        const delta = payload as { content?: string; text?: string };
        const chunkText = delta.text ?? delta.content ?? '';
        setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + chunkText }];
          }
          return [...prev, { id: `msg-${Date.now()}`, role: 'assistant', content: chunkText, created_at: new Date().toISOString() }];
        });
        setPanelState('streaming');
        break;
      }
      case 'artifact.upsert': {
        // P0-2: V12 artifact 驱动分析面板（risk_assessment → risk_level）
        const artifact = payload as {
          artifact_type?: string;
          data?: { risk_level?: string };
        };
        if (artifact?.artifact_type === 'risk_assessment' && artifact.data?.risk_level) {
          setPanelData(prev => ({
            ...(prev || {}),
            risk_level: artifact.data!.risk_level as RiskLevel,
          }));
        }
        break;
      }
      case 'turn.completed': {
        // turn.completed 带完整 answer（V12 权威值）：delta 流丢失时用最终 answer 覆盖
        const result = payload as {
          answer?: string;
          follow_ups?: string[];
          evidence_ids?: string[];
          sources?: Array<{ id: string; title: string; source: string; url?: string }>;
          evidence_count?: number;
          claims_count?: number;
          intent?: string;
          trace_id?: string;
          risk_level?: string;
          module_status?: Record<string, ModuleStatusV1>;
          missing_modules?: string[];
          // v3.3.4 收口复核清单 §5：轻量比较结构化载荷（只读透出）
          comparison_mode?: string;
          overview_rows?: Array<Record<string, unknown>>;
          requested_scope?: string;
          next_steps?: ComparisonNextStep[];
          finance?: {
            rule_statuses?: Record<string, string>;
            triggered_rules?: Array<{
              rule_id: string;
              rule_name?: string;
              evidence_ids?: string[];
            }>;
          } | null;
        };
        const conversational = ['chitchat', 'guide', 'unsupported'].includes(result.intent || '');
        const analysisIntent = !conversational && result.intent !== 'research';
        const hasAnalysisPayload = analysisIntent && Boolean(
          result.finance ||
          (result.risk_level && result.risk_level !== 'unknown') ||
          (result.claims_count || 0) > 0,
        );
        const showEvidenceStatus = !conversational && Boolean(
          hasAnalysisPayload || result.intent === 'research' || (result.evidence_count || 0) > 0,
        );
        // P0-2: 结构化载荷 → 分析面板（审计：V12 事件未驱动 AnalysisPanel）
        // 优先用后端透出的完整 triggered_rules（canonical evidence_ids）；
        // 旧载荷回退 rule_statuses 拼装（无证据 ID，仅占位）
        const triggeredRules =
          result.finance?.triggered_rules && result.finance.triggered_rules.length > 0
            ? result.finance.triggered_rules.map(r => ({
                rule_id: r.rule_id,
                rule_name: r.rule_name || r.rule_id,
                evidence_ids: r.evidence_ids || [],
              }))
            : result.finance?.rule_statuses
              ? Object.entries(result.finance.rule_statuses)
                  .filter(([, status]) => status === 'triggered')
                  .map(([ruleId]) => ({
                    rule_id: ruleId,
                    rule_name: ruleId,
                    evidence_ids: [],
                  }))
              : undefined;
        // 合并更新：不覆盖 artifact.upsert 已写入的字段
        if (hasAnalysisPayload) {
          setPanelData(prev => ({
            ...(prev || {}),
            risk_level: (result.risk_level as RiskLevel | undefined) ?? prev?.risk_level,
            triggered_rules:
              triggeredRules && triggeredRules.length > 0
                ? triggeredRules
                : prev?.triggered_rules,
            follow_ups: result.follow_ups ?? prev?.follow_ups,
            // v3.3.4：结构化比较下一步优先于旧追问（AnalysisPanel 渲染）
            next_steps: result.next_steps ?? prev?.next_steps,
          }));
        } else {
          setPanelData(null);
        }
        setMessages(prev => {
          const updated = [...prev];
          // 只更新"最后一个 user 消息之后"的 assistant（避免误更新上一轮回答）
          let lastUserIdx = -1;
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'user') {
              lastUserIdx = i;
              break;
            }
          }
          let targetIdx = -1;
          for (let i = updated.length - 1; i > lastUserIdx; i--) {
            if (updated[i].role === 'assistant') {
              targetIdx = i;
              break;
            }
          }
          if (targetIdx >= 0) {
            updated[targetIdx] = {
              ...updated[targetIdx],
              // 最终 answer 为权威值：delta 部分丢失时用其补全（非仅空兜底）
              content: result?.answer || updated[targetIdx].content,
              evidence_ids: result?.evidence_ids || [],
              sources: result?.sources || [],
              follow_ups: result?.follow_ups || [],
              next_steps: result?.next_steps || [],
              show_evidence_status: showEvidenceStatus,
              is_streaming: false,
            };
          } else if (result?.answer) {
            // 无 assistant 消息 → 新建（异常兜底）
            updated.push({
              id: `msg-${Date.now()}`,
              role: 'assistant',
              content: result.answer,
              evidence_ids: result?.evidence_ids || [],
              sources: result?.sources || [],
              follow_ups: result?.follow_ups || [],
              next_steps: result?.next_steps || [],
              show_evidence_status: showEvidenceStatus,
              created_at: new Date().toISOString(),
            });
          }
          return updated;
        });
        setPanelState(hasAnalysisPayload ? 'done' : 'empty');
        // 8.11 P0（审查）：歧义确认轮次（intent=company_disambiguation）的
        // completed 不得清空候选卡片——候选卡片要保留到用户点选
        if ((result.intent || '') !== 'company_disambiguation') {
          setPendingCandidates(null);
        }
        setIsLoading(false);
        // Phase D: 提取模块进度
        setModuleStatus(result.module_status || null);
        setMissingModules(result.missing_modules || null);
        void loadSessions(false);
        // WS completed 载荷不含 company_code，完成后从会话详情同步画像入口。
        void apiClient.getSession(currentSessionId).then(res => {
          const turns = res.data?.turns || [];
          const latestCompanyCode = [...turns]
            .reverse()
            .find(turn => turn.company_code)?.company_code || null;
          setCurrentCompanyCode(latestCompanyCode);
          setInvolvedCompanies(
            [...new Set(
              turns.map(t => t.company_code).filter((c): c is string => Boolean(c)),
            )],
          );
        }).catch(() => undefined);
        break;
      }
      case 'turn.failed':
        setPendingCandidates(null);
        setPanelState('error');
        setIsLoading(false);
        break;
      case 'company.candidates': {
        // 8.11：保存候选供用户点选；本轮无公司照常完成，确认后重跑原问题
        const cand = payload as {
          turn_id?: string;
          candidates?: Array<{ wind_code?: string; sec_name?: string }>;
        };
        const candidates = (cand.candidates || [])
          .filter(c => c.wind_code && c.sec_name)
          .map(c => ({ wind_code: c.wind_code!, sec_name: c.sec_name! }));
        if (candidates.length > 0) {
          setPendingCandidates({ turn_id: cand.turn_id || '', candidates });
        }
        break;
      }
      case 'heartbeat':
        break;
    }
  }, [currentSessionId, loadSessions]);

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
    setPanelData(null);
    setPanelState('loading');
    setActiveRuleId(null);
    setFilteredEvidenceIds(null);

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

  // 8.11：确认候选公司 → 后端以新 turn 重跑原问题
  const handleConfirmCompany = useCallback((turnId: string, windCode: string) => {
    setPendingCandidates(null);
    setPanelState('loading');
    setIsLoading(true);
    wsRef.current?.confirmCompany(turnId, windCode);
  }, []);

  // v3.3.4 收口复核清单 §5.2：结构化比较下一步 → 页面 URL（白名单/
  // 去重/URLSearchParams 编码由纯函数保证；非法 target 不导航）
  const handleNavigateStep = useCallback(
    (step: ComparisonNextStep) => {
      const url = comparisonStepToUrl(step);
      if (!url) return;
      navigate(url);
    },
    [navigate],
  );

  // Task 7: 面板联动 - 点击规则（对齐审计 P1-3：筛选证据而非仅滚动）
  const handleRuleClick = useCallback((ruleId: string) => {
    // 再次点击已激活规则 → 取消筛选
    if (activeRuleId === ruleId) {
      setActiveRuleId(null);
      setFilteredEvidenceIds(null);
      return;
    }
    setActiveRuleId(ruleId);
    const rule = (panelData?.triggered_rules || []).find(r => r.rule_id === ruleId);
    const ids = rule?.evidence_ids && rule.evidence_ids.length > 0 ? rule.evidence_ids : null;
    setFilteredEvidenceIds(ids);
    const msgIndex = messages.findIndex(m =>
      m.role === 'assistant' && m.evidence_ids && m.evidence_ids.length > 0
    );
    if (msgIndex >= 0) {
      const msgElement = document.getElementById(`msg-${msgIndex}`);
      msgElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setPanelCollapsed(false);
  }, [activeRuleId, panelData, messages]);

  useEffect(() => {
    if (currentCompanyCode) {
      sessionStorage.setItem('truthnet.currentCompanyCode', currentCompanyCode);
    } else {
      sessionStorage.removeItem('truthnet.currentCompanyCode');
    }
    window.dispatchEvent(new Event('truthnet:company-change'));
  }, [currentCompanyCode]);

  const activeRuleName = panelData?.triggered_rules?.find(
    rule => rule.rule_id === activeRuleId,
  )?.rule_name || null;

  return (
    <div className="relative flex h-[calc(100dvh-3.5rem)] min-h-0 overflow-hidden">
      {/* 左侧：会话侧边栏 */}
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        currentCompanyCode={currentCompanyCode}
        involvedCompanies={involvedCompanies}
        isBusy={isLoading}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* 中间：对话区（h-full：父级 h-[calc(100vh-64px)] 为 definite，补齐百分比高度链，否则 ChatInterface h-full 失效导致聊天区无滚动） */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col h-full">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          highlightedEvidenceIds={filteredEvidenceIds}
          activeRuleName={activeRuleName}
          onClearEvidenceHighlight={() => {
            setActiveRuleId(null);
            setFilteredEvidenceIds(null);
          }}
          pendingCandidates={pendingCandidates}
          onConfirmCompany={handleConfirmCompany}
          onNavigateStep={handleNavigateStep}
        />
      </div>

      {/* 右侧：分析面板 */}
      <div
        className={cn(
          'relative shrink-0 border-l border-border transition-[width] duration-300',
          panelCollapsed ? 'w-0' : 'w-[clamp(360px,25vw,440px)]',
        )}
      >
        {!panelCollapsed && (
          <AnalysisPanel
            state={panelState}
            data={panelData}
            company={undefined}
            activeRuleId={activeRuleId}
            moduleStatus={moduleStatus}
            missingModules={missingModules}
            onFollowUp={handleFollowUp}
            onRuleClick={handleRuleClick}
            onNavigateStep={handleNavigateStep}
          />
        )}
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 z-20 h-9 w-9 bg-background/90 shadow-sm"
          aria-label={panelCollapsed ? '展开分析面板' : '收起分析面板'}
          title={panelCollapsed ? '展开分析面板' : '收起分析面板'}
          onClick={() => setPanelCollapsed(!panelCollapsed)}
        >
          {panelCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
