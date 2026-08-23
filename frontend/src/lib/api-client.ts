/**
 * TruthNet 织网鉴真 — 前端 API 客户端
 *
 * 对接后端 13 个 REST 端点 + WebSocket
 * 响应格式: V12 { data, meta, warnings } 信封
 *
 * 开发模式通过 Vite proxy 转发到 http://localhost:8000
 */

import type {
  V12Response,
  Company,
  FinanceResponseData,
  EventsResponseData,
  EquityResponseData,
  RiskResponseData,
  BenchmarksResponseData,
  ComparisonsResponseData,
  ComparisonAnalysisData,
  ChatDataV1,
  Session,
  Message,
  PanelData,
  RiskEvidence,
  EquityNodeDTO,
  EquityEdgeDTO,
  TimelineEvent,
  EventCluster,
  FinanceRuleItem,
  CompanyRiskSummary,
  ImpactAdviceData,
} from '@/types/truthnet';

// 会话列表响应（V12 envelope: data.sessions + data.total）
interface SessionListData {
  sessions: Session[];
  total: number;
}

// 公司搜索候选（对齐后端 CompanyCandidateV1）
export interface CompanyCandidate {
  entity_id: string;
  wind_code: string;
  sec_name: string;
  exchange?: string | null;
  industry_l1?: string | null;
  industry_l2?: string | null;
  comp_type_code?: string | number | null;
  company_type?: string | null;
  listing_date?: string | null;
}

// 公司搜索响应（对齐后端 CompanySearchData: {query, total, candidates}）
export interface CompanySearchData {
  query: string;
  total: number;
  candidates: CompanyCandidate[];
}

export interface EvidenceLookupData {
  evidence: Record<string, unknown>;
  claims: Array<Record<string, unknown>>;
  source: {
    resolved?: boolean;
    record?: Record<string, unknown>;
    [key: string]: unknown;
  };
}

// 公告 PDF 摘要（后端按需下载→提取→摘要→删除临时 PDF）
export interface AnnouncementSummaryData {
  object_id: string;
  title: string;
  evidence_id: string;
  source_uri: string | null;
  summary: string;
  method: 'pdf_llm' | 'text_excerpt' | 'title_only';
}

// 声明追溯: GET /claims/{claim_id}
export interface ClaimLookupData {
  claim: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  turn: Record<string, unknown> | null;
}

// 整轮溯源: GET /traces/{trace_id}/provenance
export interface TraceProvenanceData {
  trace_id: string;
  claims: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
}

// 规则定义: GET /rules/definitions
export interface RuleMetricMeta {
  key: string;
  label: string;
  unit?: string;
  formula?: string;
  risk_direction?: string;
}
export interface RuleParameterMeta {
  key: string;
  unit?: string;
  description?: string;
  value?: number | null;
}
export interface RuleConditions {
  red: string;
  orange: string;
  yellow: string;
}
export interface RuleDefinition {
  rule_id: string;
  name: string;
  description?: string;
  enabled: boolean;
  thresholds: Record<string, number>;
  metrics: RuleMetricMeta[];
  parameters: RuleParameterMeta[];
  conditions: RuleConditions;
}
export interface RulesDefinitionsData {
  version: string;
  execution_version?: string;
  rules: RuleDefinition[];
  evaluation_config_hash: string;
  definition_hash: string;
  source?: string;
  is_overridden?: boolean;
}

// 就绪检查: GET /readyz
export interface ReadyData {
  status: string;
  profile: string;
  checks: Record<string, Record<string, unknown>>;
}

// 报告任务状态（对齐后端 schemas/reports.py ReportJobStatusData；
// 后端无「报告内容」详情端点——摘要/发现等内容在 PDF 文件里）
export interface ReportJobStatus {
  report_id: string;
  status: string; // queued / running / succeeded / failed / cancelled
  progress: number; // 0-100
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  download_available: boolean;
  file_sha256?: string | null;
  company_code?: string | null;
  session_id?: string | null;
}
// 会话历史轮次（GET /sessions/{id} 的 turns 元素）
export interface SessionTurnData {
  turn_id: string;
  turn_index: number;
  question: string;
  answer: string | null;
  company_code?: string | null;
  trace_id?: string | null;
  module_status?: Record<string, unknown> | null;
  panel_data?: PanelData | null; // 面板摘要（v7；历史旧数据为 null）
  evidence_ids?: string[];
  // P1-3：历史会话来源链接（与 WS sources 同构 {id,title,source,url}）
  sources?: Array<{
    id: string;
    title: string;
    source: string;
    url?: string;
  }>;
  created_at?: string;
}

// 会话详情响应（V12 envelope: data.session + data.turns）
interface SessionDetailData {
  session: Session;
  turns: SessionTurnData[];
}

// 创建会话响应（后端 POST /sessions 不返回 turn_count，Omit 掉保持真实契约）
type SessionCreateData = Omit<Session, 'turn_count'>;

// 类型别名：API 方法返回类型
type FinanceData = FinanceResponseData;
type EventsData = EventsResponseData;
type EquityData = EquityResponseData;
type RiskData = RiskResponseData;
type BenchmarkData = BenchmarksResponseData;
type ChatResponse = ChatDataV1;

// ---------------------------------------------------------------------------
// 基础请求函数
// ---------------------------------------------------------------------------

const API_BASE = '/api/v1';

async function request<T>(
  method: string,
  path: string,
  options?: RequestInit & { params?: Record<string, string | number | boolean | undefined> }
): Promise<V12Response<T>> {
  const { params, ...fetchOptions } = options || {};

  let url = `${API_BASE}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.set(key, String(value));
    });
    const query = searchParams.toString();
    if (query) url += `?${query}`;
  }

  const res = await fetch(url, {
    ...fetchOptions,
    method,
    headers: {
      'Content-Type': 'application/json',
      ...fetchOptions.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({
      type: 'about:blank',
      title: 'Network Error',
      status: res.status,
      detail: res.statusText,
    }));
    throw new Error(`${error.title}: ${error.detail}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// API 客户端
// ---------------------------------------------------------------------------

export const truthnetAPI = {
  // 健康检查（后端实际路径为 /api/v1/healthz，审计 P2-1 修正原 /health 404）
  health: () => request<{ status: string; version?: string; profile?: string }>('GET', '/healthz'),

  // 公司搜索: GET /api/v1/companies?query=xxx（data={query,total,candidates}，审计 P1-6）
  searchCompanies: (query: string) =>
    request<CompanySearchData>('GET', '/companies', { params: { query } }),

  // 公司详情: GET /api/v1/companies/{code}
  getCompanyProfile: (code: string) =>
    request<Company>('GET', `/companies/${encodeURIComponent(code)}`),

  // 财务分析: GET /api/v1/companies/{code}/finance
  getFinance: (code: string) =>
    request<FinanceData>('GET', `/companies/${encodeURIComponent(code)}/finance`),

  // 舆情事件: GET /api/v1/companies/{code}/events
  // B2 契约修复：默认 include_impacts=true（画像页影响与建议区块消费
  // impact_conclusions；后端默认 false 时恒为空列表）
  getEvents: (code: string, includeImpacts: boolean = true) =>
    request<EventsData>('GET', `/companies/${encodeURIComponent(code)}/events`, {
      params: { include_impacts: includeImpacts },
    }),

  // 股权穿透: GET /api/v1/companies/{code}/equity
  getEquity: (code: string, depth: number = 5) =>
    request<EquityData>('GET', `/companies/${encodeURIComponent(code)}/equity`, {
      params: { depth },
    }),

  // 风险评估: GET /api/v1/companies/{code}/risk
  getRisk: (code: string) =>
    request<RiskData>('GET', `/companies/${encodeURIComponent(code)}/risk`),

  getImpactAdvice: (code: string) =>
    request<ImpactAdviceData>(
      'GET',
      `/companies/${encodeURIComponent(code)}/impact-advice`,
    ),

  // 行业基准: GET /api/v1/companies/{code}/benchmarks
  getBenchmarks: (code: string) =>
    request<BenchmarkData>('GET', `/companies/${encodeURIComponent(code)}/benchmarks`),

  // 跨公司对比: POST /api/v1/comparisons
  compareCompanies: (companyCodes: string[], period?: string, indicators?: string[]) =>
    request<ComparisonsResponseData>('POST', '/comparisons', {
      body: JSON.stringify({
        company_codes: companyCodes,
        ...(period ? { period } : {}),
        ...(indicators && indicators.length > 0 ? { indicators } : {}),
      }),
    }),

  // 8/23 会7 深化：跨公司 LLM 综合分析: GET /api/v1/comparisons/analysis
  getComparisonAnalysis: (companyCodes: string[]) =>
    request<ComparisonAnalysisData>('GET', '/comparisons/analysis', {
      params: { codes: companyCodes.join(',') },
    }),

  // 证据详情: GET /api/v1/evidence/{evidence_id}
  getEvidence: (evidenceId: string) =>
    request<EvidenceLookupData>('GET', `/evidence/${encodeURIComponent(evidenceId)}`),

  // 公告 PDF 摘要: GET /api/v1/companies/{code}/announcements/{object_id}/summary
  getAnnouncementSummary: (companyCode: string, objectId: string) =>
    request<AnnouncementSummaryData>(
      'GET',
      `/companies/${encodeURIComponent(companyCode)}/announcements/${encodeURIComponent(objectId)}/summary`,
    ),

  // 会话列表: GET /api/v1/sessions（V12 envelope: data.sessions + total）
  getSessions: () => request<SessionListData>('GET', '/sessions'),

  // 会话详情: GET /api/v1/sessions/{sessionId}（session + turns 历史）
  getSession: (sessionId: string) =>
    request<SessionDetailData>('GET', `/sessions/${encodeURIComponent(sessionId)}`),

  // 创建会话: POST /api/v1/sessions（后端创建接口不返回 turn_count，用 Omit 表达）
  createSession: (title: string = '新对话') =>
    request<SessionCreateData>('POST', '/sessions', {
      body: JSON.stringify({ title }),
    }),

  // 删除会话: DELETE /api/v1/sessions/{sessionId}
  deleteSession: (sessionId: string) =>
    request<{ deleted: boolean; session_id: string }>(
      'DELETE',
      `/sessions/${sessionId}`,
    ),

  // 发送消息: POST /api/v1/chat

  // 声明追溯: GET /api/v1/claims/{claim_id}
  getClaim: (claimId: string) =>
    request<ClaimLookupData>('GET', `/claims/${encodeURIComponent(claimId)}`),

  // 整轮溯源: GET /api/v1/traces/{trace_id}/provenance
  getTraceProvenance: (traceId: string) =>
    request<TraceProvenanceData>('GET', `/traces/${encodeURIComponent(traceId)}/provenance`),

  // 规则定义: GET /api/v1/rules/definitions
  getRuleDefinitions: () =>
    request<RulesDefinitionsData>('GET', '/rules/definitions'),
  // 8/23 会7 深化：覆盖保存阈值（完整 rules 结构）/ 重置恢复默认
  updateRuleConfig: (body: Record<string, unknown>) =>
    request<RulesDefinitionsData>('PUT', '/rules/config', {
      body: JSON.stringify(body),
    }),
  resetRuleConfig: () =>
    request<RulesDefinitionsData>('DELETE', '/rules/config'),

  // 就绪检查: GET /api/v1/readyz
  readyz: () => request<ReadyData>('GET', '/readyz'),

  // 创建报告任务: POST /api/v1/reports（后端必填 company_code → 202 任务状态）
  createReport: (companyCode: string, sessionId?: string) =>
    request<ReportJobStatus>('POST', '/reports', {
      body: JSON.stringify({ company_code: companyCode, session_id: sessionId }),
    }),

  // 报告任务状态: GET /api/v1/reports/{report_id}
  getReport: (reportId: string) =>
    request<ReportJobStatus>('GET', `/reports/${encodeURIComponent(reportId)}`),

  // 报告下载: GET /api/v1/reports/{report_id}/file
  getReportDownloadUrl: (reportId: string) =>
    `${API_BASE}/reports/${reportId}/file`,

  sendChatMessage: (question: string, sessionId?: string) =>
    request<ChatResponse>('POST', '/chat', {
      body: JSON.stringify({
        question,
        session_id: sessionId,
      }),
    }),
};

// ---------------------------------------------------------------------------
// WebSocket 客户端
// ---------------------------------------------------------------------------

export interface WSMessage {
  // V12 信封字段
  schema_version?: string;
  event_id?: string;
  event_type: string;
  session_id?: string;
  turn_id?: string;
  sequence?: number;
  timestamp?: string;
  trace_id?: string;
  payload?: unknown;
  // 旧格式兼容
  type?: string;
  content?: string;
  data?: unknown;
}

export const wsClient = {
  create: (sessionId: string, onMessage: (msg: WSMessage) => void) => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/chat/ws?session_id=${sessionId}`;
    const ws = new WebSocket(wsUrl);
    const pendingQuestions: string[] = [];
    let closeRequested = false;
    let connectionErrorReported = false;
      // 缺口 #33：按 V12 信封 sequence 去重；新连接重连后 sequence 可能重开，
      // 重连时重置为 0 避免把有效事件当重复丢弃。
      let lastSequence = 0;

    const sendQuestion = (question: string) => {
      ws.send(JSON.stringify({
        event_type: 'chat.query',
        // V12 契约: payload.session_id 是会话归属的唯一来源（审计 P0-1）
        payload: { text: question, session_id: sessionId },
        type: 'chat.query',
        question,
      }));
    };

    ws.onopen = () => {
      while (pendingQuestions.length > 0) {
        sendQuestion(pendingQuestions.shift()!);
      }
    };
        if (false) {  // legacy dedup block disabled; actual dedup is inside onmessage
          const msg: WSMessage = { event_type: 'ignored' };

          if (typeof msg.sequence === 'number' && msg.sequence > 0) {
              if (lastSequence > 0 && msg.sequence <= lastSequence) {
                console.warn(`[WS] drop duplicate sequence=${msg.sequence} (last=${lastSequence})`);
                return;
              }
              lastSequence = msg.sequence;
          }
        }
    ws.onmessage = (event) => {
      if (closeRequested) return;  // 8/17：正常关闭后忽略迟到消息（防污染新会话）
      try {
            const msg: WSMessage = JSON.parse(event.data);
          if (typeof msg.sequence === 'number' && msg.sequence > 0) {
              if (lastSequence > 0 && msg.sequence <= lastSequence) {
                console.warn(`[WS] drop duplicate sequence=${msg.sequence} (last=${lastSequence})`);
                return;
              }
              lastSequence = msg.sequence;
          }
        const parsedMsg = msg;
          onMessage(parsedMsg);
      } catch (e) {
        console.error('WebSocket message parse error:', e);
        onMessage({ event_type: 'error', payload: { message: '消息解析错误' } });
      }
    };

    ws.onerror = (error) => {
      if (closeRequested) return;
      console.error('WebSocket error:', error);
      connectionErrorReported = true;
      onMessage({ event_type: 'error', payload: { message: '连接错误' } });
    };

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectAttempts = 0;

    const tryReconnect = () => {
      if (reconnectAttempts >= 5) return;
      const delay = Math.min(1000 * 2 ** reconnectAttempts, 30000);
      reconnectAttempts++;
      console.log(`[WS] Reconnecting in ${delay}ms (${reconnectAttempts}/5)`);
      reconnectTimer = setTimeout(() => {
        try {
          lastSequence = 0; // 新连接 sequence 重新开始
            const newWs = new WebSocket(wsUrl);
          newWs.onopen = () => {
            reconnectAttempts = 0;
            newWs.send(JSON.stringify({ event_type: 'stream.resume', payload: { session_id: sessionId } }));
          };
          // Re-use the same handler setup logic
          newWs.onmessage = ws.onmessage;
          newWs.onerror = ws.onerror;
          newWs.onclose = ws.onclose;
        } catch (e) {
          tryReconnect();
        }
      }, delay);
    };

    ws.onclose = (event) => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      // 8/17：主动关闭（切换会话/组件卸载）后绝不重连——closeRequested
      // 已置位，异常断开（code≠1000/1001）也不得重建旧会话连接，
      // 否则旧 turn 事件回流污染新会话面板。
      if (closeRequested) return;
      if (event.code !== 1000 && event.code !== 1001) tryReconnect();
    };

    return {
      send: (question: string) => {
        if (ws.readyState === WebSocket.OPEN) {
          sendQuestion(question);
        } else if (ws.readyState === WebSocket.CONNECTING) {
          pendingQuestions.push(question);
        } else {
          onMessage({ event_type: 'error', payload: { message: '连接不可用，请稍后重试' } });
        }
      },
      // 8.11：公司歧义确认——携带选中公司重跑原问题（company.confirm 事件）。
      // v3.1 mention 分组协议：多候选场景必须带 mention_id + revision（后端
      // ws.py CompanyConfirmPayload 要求成对提供，缺一会被拒）；旧协议单候选
      // 场景可不带（后端兼容路径）。
      confirmCompany: (
        turnId: string,
        companyRef: string,
        mentionId?: string,
        revision?: number,
      ) => {
        if (ws.readyState !== WebSocket.OPEN) {
          onMessage({ event_type: 'error', payload: { message: '连接不可用，无法确认公司' } });
          return;
        }
        // 审查修复：mention_id 与 revision 必须成对发送——后端
        // is_mention_protocol 判定「任一存在即走新协议」，只带 revision 不带
        // mention_id 会被 INVALID_COMPANY_CONFIRM 拒绝；旧协议两者都不带。
        const mentionProtocol = Boolean(mentionId) && revision !== undefined;
        ws.send(JSON.stringify({
          event_type: 'company.confirm',
          payload: {
            company_ref: companyRef,
            session_id: sessionId,
            turn_id: turnId,
            ...(mentionProtocol ? { mention_id: mentionId, revision } : {}),
          },
          type: 'company.confirm',
        }));
      },
      close: () => {
        closeRequested = true;
        pendingQuestions.length = 0;
        ws.close();
      },
    };
  },
};

// ---------------------------------------------------------------------------
// 兼容旧接口
// ---------------------------------------------------------------------------

export const apiClient = {
  getSessions: truthnetAPI.getSessions,
  getSession: truthnetAPI.getSession,
  createSession: truthnetAPI.createSession,
  deleteSession: truthnetAPI.deleteSession,
  sendChatMessage: truthnetAPI.sendChatMessage,
};

export default truthnetAPI;
