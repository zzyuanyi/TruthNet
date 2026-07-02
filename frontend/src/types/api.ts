/**
 * TruthNet 前端 API 类型定义
 *
 * 与 backend/app/schemas/ 和 docs/API_CONTRACT.md 严格一致。
 * 接口冻结后，只能追加新字段，不可删除或重命名已有字段。
 */

// ============================================================
// 统一响应
// ============================================================

export interface UnifiedResponse<T = unknown> {
  code: number;
  data: T | null;
  message: string;
  trace_id: string;
}

// ============================================================
// 健康检查
// ============================================================

export interface HealthData {
  status: string;
  version: string;
}

// ============================================================
// 对话请求
// ============================================================

export interface ChatContext {
  company_code?: string;
  fiscal_year?: number;
  report_type?: string;
}

export interface ChatRequest {
  question: string;
  session_id?: string;
  context?: ChatContext;
}

// ============================================================
// 对话响应
// ============================================================

export interface EvidenceItem {
  source: string;
  field: string;
  value: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  depth?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TimelineEvent {
  date: string;
  title: string;
  category: string;
  summary: string;
  sentiment: string;
  sources: string[];
}

export interface RiskScore {
  overall: number;
  financial: number;
  ownership: number;
  sentiment: number;
}

export interface ChatData {
  answer: string;
  evidence: EvidenceItem[];
  graph: GraphData;
  timeline: TimelineEvent[];
  risk_score: RiskScore;
  warnings: string[];
  missing_modules: string[];
  trace_id: string;
}

// ============================================================
// WebSocket 消息
// ============================================================

export type WSMessageType = 'status' | 'partial_answer' | 'final_answer' | 'error';

export interface WSMessageBase {
  type: WSMessageType;
  data: Record<string, unknown>;
}

export interface WSStatusMessage {
  type: 'status';
  data: {
    message: string;
    trace_id: string;
  };
}

export interface WSPartialAnswerMessage {
  type: 'partial_answer';
  data: {
    text: string;
    sequence: number;
    trace_id: string;
  };
}

export interface WSFinalAnswerMessage {
  type: 'final_answer';
  data: ChatData;
}

export interface WSErrorMessage {
  type: 'error';
  data: {
    code: number;
    message: string;
    trace_id: string;
  };
}

export type WSMessage =
  | WSStatusMessage
  | WSPartialAnswerMessage
  | WSFinalAnswerMessage
  | WSErrorMessage;

// ============================================================
// 客户端发送的 WebSocket 消息
// ============================================================

export interface WSQuestionRequest {
  type: 'question';
  data: {
    question: string;
    context?: ChatContext;
  };
}
