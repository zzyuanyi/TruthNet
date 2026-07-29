// 织网鉴真 TruthNet - 类型定义
// 基于 V12 规范 §11-12

// ============ 基础类型 ============

export interface Company {
  code: string;           // 股票代码，如 "600518.SH"
  name: string;           // 公司名称
  industry: string;       // 行业
  market: string;         // 市场
}

export interface Session {
  id: string;
  title: string;
  company_code: string;
  company_name: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  risk_level?: RiskLevel;
}

export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  // assistant 消息的额外字段
  thinking?: string;
  structured_data?: PanelData;
  follow_ups?: string[];
  sources?: EvidenceSource[];
}

// ============ 风险等级 ============

export type RiskLevel = 'red' | 'orange' | 'yellow' | 'blue' | 'green';

export interface RiskLevelInfo {
  level: RiskLevel;
  label: string;
  color: string;
  description: string;
}

export const RISK_LEVELS: Record<RiskLevel, RiskLevelInfo> = {
  red: { level: 'red', label: '高危', color: 'bg-red-500', description: '≥3 条规则触发' },
  orange: { level: 'orange', label: '中高危', color: 'bg-orange-500', description: '研报评级拐点' },
  yellow: { level: 'yellow', label: '中等', color: 'bg-yellow-500', description: '负面公告占比高' },
  blue: { level: 'blue', label: '低风险', color: 'bg-blue-500', description: '指标正常' },
  green: { level: 'green', label: '正常', color: 'bg-green-500', description: '无异常' },
};

// ============ 分析面板数据 ============

export type PanelState = 'empty' | 'loading' | 'ready' | 'thinking' | 'streaming' | 'done' | 'error';

export interface PanelData {
  risk_level: RiskLevel;
  triggered_rules: TriggeredRule[];
  key_metrics: KeyMetric[];
  company?: Company;
}

export interface TriggeredRule {
  id: string;
  name: string;
  current_value: string;
  threshold: string;
  industry_percentile: number;
  severity: 'high' | 'medium' | 'low';
}

export interface KeyMetric {
  name: string;
  value: string;
  change?: string;
  risk_indicator?: RiskLevel;
  industry_benchmark?: string;
}

// ============ 企业画像 ============

export interface CompanyProfile {
  code: string;
  name: string;
  industry: string;
  market: string;
  risk_overview: RiskOverview;
  financial_anomalies: FinancialAnomaly[];
  equity_chain: EquityChain;
  sentiment_events: SentimentEvent[];
  evidence: EvidenceCategory[];
}

export interface RiskOverview {
  risk_level: RiskLevel;
  triggered_rules_count: number;
  negative_announcement_ratio: number;
  summary: string;
}

export interface FinancialAnomaly {
  rule_id: string;
  rule_name: string;
  triggered: boolean;
  current_value: string;
  expected_value: string;
  deviation: string;
  industry_percentile: number;
  explanation: string;
}

export interface EquityChain {
  target_company: string;
  nodes: EquityNode[];
  edges: EquityEdge[];
}

export interface EquityNode {
  id: string;
  name: string;
  type: 'company' | 'person' | 'fund';
  share_ratio?: number;
  is_target?: boolean;
  x?: number;
  y?: number;
}

export interface EquityEdge {
  source: string;
  target: string;
  relation: string;
  ratio?: number;
}

export interface SentimentEvent {
  id: string;
  date: string;
  title: string;
  type: 'positive' | 'negative' | 'neutral';
  source: string;
  impact_score: number;
  summary: string;
}

export interface EvidenceCategory {
  category: string;
  items: EvidenceItem[];
}

export interface EvidenceItem {
  id: string;
  title: string;
  source: string;
  date: string;
  content: string;
  relevance_score: number;
}

export interface EvidenceSource {
  id: string;
  title: string;
  source: string;
  date: string;
  snippet: string;
}

// ============ WebSocket 消息（V12 event envelope） ============

export type WSEventType =
  | 'turn.accepted' | 'turn.completed' | 'turn.failed' | 'turn.cancelled'
  | 'module.started' | 'module.completed'
  | 'answer.delta' | 'artifact.upsert'
  | 'heartbeat';

export interface WSEvent {
  schema_version: string;
  event_id: string;
  event_type: WSEventType;
  session_id: string;
  turn_id: string;
  sequence: number;
  timestamp: string;
  trace_id: string;
  payload: Record<string, unknown>;
}

// ============ 跨公司对比 ============

export interface CompareData {
  companies: Company[];
  metrics: CompareMetric[];
}

export interface CompareMetric {
  name: string;
  values: Record<string, string>; // company_code -> value
  risk_indicators: Record<string, RiskLevel>;
}
