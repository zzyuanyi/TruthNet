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
  // 健康检查
  health: () => request<{ status: string }>('GET', '/health'),

  // 公司搜索: GET /api/v1/companies?query=xxx
  searchCompanies: (query: string) =>
    request<Company[]>('GET', '/companies', { params: { query } }),

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
        period: period || '2023',
        indicators: indicators || [],
      }),
    }),

  // 会话列表: GET /api/v1/sessions（V12 envelope: data.sessions + total）
  getSessions: () => request<SessionListData>('GET', '/sessions'),

  // 创建会话: POST /api/v1/sessions（后端创建接口不返回 turn_count，用 Omit 表达）
  createSession: (title: string = '新对话') =>
    request<SessionCreateData>('POST', '/sessions', {
      body: JSON.stringify({ title }),
    }),

  // 删除会话: DELETE /api/v1/sessions/{sessionId}
  deleteSession: (sessionId: string) =>
    request<{ ok: boolean }>('DELETE', `/sessions/${sessionId}`),

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
      console.error('WebSocket error:', error);
      onMessage({ event_type: 'error', payload: { message: '连接错误' } });
    };

    ws.onclose = () => {
      onMessage({ event_type: 'done' });
    };

    return {
      send: (question: string) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            event_type: 'chat.query',
            payload: { text: question },
            type: 'chat.query',
            question,
          }));
        }
      },
      close: () => ws.close(),
    };
  },
};

// ---------------------------------------------------------------------------
// 兼容旧接口
// ---------------------------------------------------------------------------

export const apiClient = {
  getSessions: truthnetAPI.getSessions,
  createSession: truthnetAPI.createSession,
  deleteSession: truthnetAPI.deleteSession,
  sendChatMessage: truthnetAPI.sendChatMessage,
};

export default truthnetAPI;
