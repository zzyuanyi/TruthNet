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
  getEvents: (code: string) =>
    request<EventsData>('GET', `/companies/${encodeURIComponent(code)}/events`),

  // 股权穿透: GET /api/v1/companies/{code}/equity
  getEquity: (code: string, depth: number = 5) =>
    request<EquityData>('GET', `/companies/${encodeURIComponent(code)}/equity`, {
      params: { depth },
    }),

  // 风险评估: GET /api/v1/companies/{code}/risk
  getRisk: (code: string) =>
    request<RiskData>('GET', `/companies/${encodeURIComponent(code)}/risk`),

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

  // 证据详情: GET /api/v1/evidence/{evidence_id}
  getEvidence: (evidenceId: string) =>
    request<EvidenceLookupData>('GET', `/evidence/${encodeURIComponent(evidenceId)}`),

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

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        onMessage(msg);
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

    ws.onclose = () => {
      if (!closeRequested && !connectionErrorReported) {
        onMessage({ event_type: 'error', payload: { message: '连接已断开，请重试' } });
      }
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
