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
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type {
  Session,
  Message,
  PanelData,
  PanelState,
  ChatDataV1,
  RiskLevel,
  ModuleStatusV1,
  ComparisonNextStep,
  PendingCompanyCandidates,
} from '@/types/truthnet';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

// 8/23：本对话涉及公司（code + 名称，侧边栏展示"名称（代码）"）。
// 名称缺失（公司不在库中/旧数据）时回退纯代码。
export interface InvolvedCompany {
  code: string;
  name: string;
}

function collectInvolvedCompanies(
  turns: Array<{ company_code?: string | null; company_name?: string | null }>,
): InvolvedCompany[] {
  const seen = new Map<string, string>();
  for (const t of turns) {
    const code = t.company_code;
    if (!code || seen.has(code)) continue;
    seen.set(code, t.company_name || '');
  }
  return [...seen.entries()].map(([code, name]) => ({ code, name }));
}

export default function ChatPage() {
  useDocumentTitle('智能问答');
  const navigate = useNavigate();
  // 状态管理
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [currentCompanyCode, setCurrentCompanyCode] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [panelState, setPanelState] = useState<PanelState>('empty');
  const [panelCollapsed, setPanelCollapsed] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<ReturnType<typeof wsClient.create> | null>(null);
  // 8/17：WS 连接代数（epoch）——每次 create 递增；旧连接迟到的
  // 事件（error/turn.failed）经 epoch 校验被丢弃，不污染新会话面板。
  const wsEpochRef = useRef(0);
  // 8.11：待确认公司候选（后端 company.candidates 事件，选择后重跑原问题）
  // v3.1 mention 分组协议：多候选时后端 candidates 为空、候选在 mentions[] 中，
  // 每个 mention 携带 mention_id + revision，确认时需原样回传。
  const [pendingCandidates, setPendingCandidates] = useState<PendingCompanyCandidates | null>(null);
  // v3.3.1 §8.2：分段歧义澄清提示（后端 entity.clarification_required，无可点选候选）
  const [clarificationIssue, setClarificationIssue] = useState<string | null>(null);
  // 8.11（C9）：本对话涉及的公司列表（按 company_code 去重，每公司一个画像入口）
  const [involvedCompanies, setInvolvedCompanies] = useState<InvolvedCompany[]>([]);

  // Task 7: 面板联动状态（8/23：删除规则点击→证据定位联动——证据 ID
  // 对用户无意义，面板卡片改为只读展示）

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
        // 8.11（C9）：聚合本对话涉及的公司（去重；8/23 带公司名展示）
        setInvolvedCompanies(collectInvolvedCompanies(turns));
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
      // 8/17：分析中新建会话 → 旧请求作废（连接 epoch 隔离），复位加载态
      setIsLoading(false);
      setCurrentCompanyCode(null);
      setInvolvedCompanies([]);
      setPendingCandidates(null);
      setClarificationIssue(null);
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  // 切换会话
  const handleSelectSession = (sessionId: string) => {
    if (sessionId === currentSessionId) return;
    // 8/17：允许在分析中切换——旧请求由连接 epoch 隔离（其结果不再
    // 更新本页），此处立即复位加载态与面板，避免"本次请求未完成"。
    setIsLoading(false);
    setPanelState('empty');
    setCurrentSessionId(sessionId);
    // 切换会话时清空待确认候选（8.11）与澄清提示
    setPendingCandidates(null);
    setClarificationIssue(null);
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
        setClarificationIssue(null);
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
          // 8/23：不再联动筛选证据（证据 ID 对用户无意义），仅回填消息证据链
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
        setClarificationIssue(null);
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
          // 契约修复：turn.completed 不含 module_status/missing_modules
          // （模块进度由 module.started/module.completed 事件驱动）
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
                severity?: string;
                explanation?: string;
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
                  severity: r.severity,
                  explanation: r.explanation,
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
        // 契约修复：后端 turn.completed 不含 module_status/missing_modules——
        // 模块进度由 module.started/module.completed 事件驱动，此处不再清空。
        void loadSessions(false);
        // WS completed 载荷不含 company_code，完成后从会话详情同步画像入口。
        void apiClient.getSession(currentSessionId).then(res => {
          const turns = res.data?.turns || [];
          const latestCompanyCode = [...turns]
            .reverse()
            .find(turn => turn.company_code)?.company_code || null;
          setCurrentCompanyCode(latestCompanyCode);
          setInvolvedCompanies(collectInvolvedCompanies(turns));
        }).catch(() => undefined);
        break;
      }
      case 'turn.failed':
        setPendingCandidates(null);
        setPanelState('error');
        setIsLoading(false);
        break;
      case 'turn.cancelled': {
        // 契约修复（接口审计 CONFIRMED）：后端取消确认终态——用户显式 turn.cancel、
        // 断线清理、stream.resume 断线重连回放均发此事件；本 turn 不会再发
        // turn.completed/turn.failed。若不处理，重连回放的 turn.cancelled 会被静默
        // 丢弃 → isLoading 恒真、面板卡在 loading，只能刷新或切会话恢复。
        const cancelled = payload as { turn_id?: string; message?: string };
        console.warn('[WS] turn cancelled:', cancelled.message || '当前轮次已取消');
        setPendingCandidates(null);
        setPanelState('error');
        setIsLoading(false);
        break;
      }
      case 'company.candidates': {
        // 契约修复：mention 分组协议优先——多候选时后端 candidates 为空、
        // 候选在 mentions[]（每 mention 带 mention_id，payload 带 revision）。
        const cand = payload as {
          turn_id?: string;
          revision?: number;
          mentions?: Array<{
            mention_id?: string;
            text?: string;
            status?: string;
            candidates?: Array<{ company?: { wind_code?: string; sec_name?: string } }>;
          }>;
          candidates?: Array<{ wind_code?: string; sec_name?: string }>;
        };
        const mentions = (cand.mentions || [])
          .filter(m => m.status === 'needs_confirmation' && m.mention_id)
          .map(m => ({
            mention_id: m.mention_id!,
            text: m.text || '',
            candidates: (m.candidates || [])
              .filter(c => c.company?.wind_code && c.company?.sec_name)
              .map(c => ({ wind_code: c.company!.wind_code!, sec_name: c.company!.sec_name! })),
          }))
          .filter(m => m.candidates.length > 0);
        if (mentions.length > 0) {
          setPendingCandidates({
            turn_id: cand.turn_id || '',
            revision: cand.revision ?? 0,
            mentions,
          });
          setClarificationIssue(null);
          break;
        }
        // 旧协议兼容（恰好一个可确认候选）：扁平 candidates
        const flat = (cand.candidates || [])
          .filter(c => c.wind_code && c.sec_name)
          .map(c => ({ wind_code: c.wind_code!, sec_name: c.sec_name! }));
        if (flat.length > 0) {
          setPendingCandidates({
            turn_id: cand.turn_id || '',
            revision: 0,
            mentions: [{ mention_id: '', text: '', candidates: flat }],
          });
          setClarificationIssue(null);
        }
        break;
      }
      case 'entity.clarification_required': {
        // v3.3.1 §8.2 契约修复：分段歧义、无可确认候选 → 提示用户重述问题
        const clar = payload as { issues?: Array<{ message?: string }> };
        setPendingCandidates(null);
        setClarificationIssue(
          clar.issues?.[0]?.message ||
            '公司名称存在歧义，请使用更明确的说法重新提问（如完整公司名称）',
        );
        break;
      }
      case 'module.completed': {
        // 契约修复：后端 module.started → module.completed 成对发送，
        // completed 载荷 {module, status:"success", duration_ms}
        const done = payload as { module?: string; status?: string; duration_ms?: number };
        const moduleName = done.module || 'unknown';
        setModuleStatus(prev => ({
          ...(prev || {}),
          [moduleName]: {
            state: done.status === 'success' ? 'success' : 'failed',
            error_code: done.status === 'success' ? null : (done.status || 'failed'),
            recoverable: true,
            duration_ms: done.duration_ms ?? null,
          },
        }));
        break;
      }
      case 'company.confirm_ack': {
        // 契约修复：后端逐 mention 确认回执（部分确认不重发 company.candidates，
        // 只回 confirm_ack{resolved,remaining_mentions,revision}）。
        const ack = payload as {
          turn_id?: string;
          mention_id?: string;
          wind_code?: string;
          remaining_mentions?: string[];
          resolved?: boolean;
          revision?: number;
          resume_status?: string;
          relation_status?: string;
        };
        if (ack.resolved) {
          setPendingCandidates(null);
          if (ack.resume_status === 'completed') {
            // 幂等重放已完成：T+1 早已跑完，直接刷新会话
            setIsLoading(false);
            setPanelState('done');
            void loadSessions(false);
          } else {
            // resume 进行中：等 turn.accepted → turn.completed
            setPanelState('loading');
            setIsLoading(true);
          }
          break;
        }
        // 部分确认/阻断：移除已确认 mention，保留剩余分组与最新 revision
        const remainingIds = ack.remaining_mentions || [];
        if (remainingIds.length === 0) {
          setPendingCandidates(null);
          setIsLoading(false);
          setClarificationIssue(
            ack.relation_status === 'needs_clarification'
              ? '公司身份已确认，但问题中的比较关系不明确，请重新描述问题'
              : '该问题暂无法继续分析，请重新描述问题',
          );
          break;
        }
        setPendingCandidates(prev => {
          if (!prev) return prev;
          const mentions = prev.mentions
            .filter(m => m.mention_id !== ack.mention_id)
            .filter(m => remainingIds.includes(m.mention_id) || !m.mention_id);
          if (mentions.length === 0) return null;
          return { ...prev, revision: ack.revision ?? prev.revision, mentions };
        });
        setIsLoading(false);
        break;
      }
      case 'heartbeat':
        break;
    }
  }, [currentSessionId, loadSessions]);

  // 连接 WebSocket
  useEffect(() => {
    if (!currentSessionId) return;

    // 8/17：连接代数隔离——每次会话切换/重连递增，旧连接的事件
    // 回调（闭包捕获旧 epoch）在 epoch 不匹配时直接丢弃。
    const epoch = ++wsEpochRef.current;
    wsRef.current = wsClient.create(currentSessionId, (msg) => {
      if (epoch !== wsEpochRef.current) return;  // 旧连接事件 → 忽略
      handleWSEvent(msg);
    });

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

  // 8.11/契约修复：确认候选公司。卡片清空与 loading 由 company.confirm_ack
  // 驱动（部分确认 resolved=False 时卡片保留、可继续点选剩余 mention）。
  const handleConfirmCompany = useCallback(
    (turnId: string, mentionId: string, revision: number, windCode: string) => {
      setClarificationIssue(null);
      if (!wsRef.current) {
        setClarificationIssue('连接不可用，请稍后重试');
        return;
      }
      wsRef.current.confirmCompany(turnId, windCode, mentionId || undefined, revision);
    },
    [],
  );

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

  useEffect(() => {
    if (currentCompanyCode) {
      sessionStorage.setItem('truthnet.currentCompanyCode', currentCompanyCode);
    } else {
      sessionStorage.removeItem('truthnet.currentCompanyCode');
    }
    window.dispatchEvent(new Event('truthnet:company-change'));
  }, [currentCompanyCode]);

  return (
    <div className="relative flex h-[calc(100dvh-3.5rem)] min-h-0 overflow-hidden">
      {/* 左侧：会话侧边栏（可收起） */}
      <div
        className={cn(
          'relative h-full min-h-0 shrink-0 transition-[width] duration-300',
          sidebarCollapsed ? 'w-0' : 'w-60 border-r border-border',
        )}
      >
        {!sidebarCollapsed && (
          <SessionSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            currentCompanyCode={currentCompanyCode}
            involvedCompanies={involvedCompanies}
            isBusy={isLoading}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onDeleteSession={handleDeleteSession}
            onCollapse={() => setSidebarCollapsed(true)}
          />
        )}
        {sidebarCollapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-0 top-2 z-20 h-8 w-8 translate-x-1/2 rounded-l-none border border-border bg-background/90 shadow-sm hover:bg-accent"
            aria-label="展开会话侧边栏"
            title="展开会话侧边栏"
            onClick={() => setSidebarCollapsed(false)}
          >
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* 中间：对话区（h-full：父级 h-[calc(100vh-64px)] 为 definite，补齐百分比高度链，否则 ChatInterface h-full 失效导致聊天区无滚动） */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col h-full">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          pendingCandidates={pendingCandidates}
          onConfirmCompany={handleConfirmCompany}
          clarificationIssue={clarificationIssue}
          onDismissClarification={() => setClarificationIssue(null)}
          onNavigateStep={handleNavigateStep}
        />
      </div>

      {/* 右侧：分析面板 */}
      <div
        className={cn(
          'relative h-full min-h-0 shrink-0 border-l border-border transition-[width] duration-300',
          panelCollapsed ? 'w-0' : 'w-[clamp(360px,25vw,440px)]',
        )}
      >
        {!panelCollapsed && (
          <AnalysisPanel
            state={panelState}
            data={panelData}
            company={undefined}
            moduleStatus={moduleStatus}
            missingModules={missingModules}
            onFollowUp={handleFollowUp}
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
          {panelCollapsed ? <PanelRightOpen className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
