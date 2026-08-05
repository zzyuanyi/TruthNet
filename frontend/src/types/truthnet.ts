
// 织网鉴真 TruthNet - 类型定义
// 对齐后端 API Schema V12 (2026-08-05)

// ============ V12 统一响应格式 ============

export interface V12Meta {
  request_id: string;
  trace_id: string;
  schema_version: string;
  generated_at: string;
  data_as_of: string;
  dataset_version: string;
  rule_set_version: string;
  graph_version: string;
}

export interface WarningItem {
  code: string;
  message: string;
  module?: string;
  recoverable: boolean;
}

export interface V12Response<T> {
  data: T | null;
  meta: V12Meta;
  warnings: WarningItem[];
}

// RFC 9457 ProblemDetail 错误格式
export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
}

// ============ 风险等级 ============

export type RiskLevel = 'red' | 'orange' | 'yellow' | 'green' | 'blue' | 'unknown';

export interface RiskLevelInfo {
  level: RiskLevel;
  label: string;
  color: string;
}

export const RISK_LEVELS: Record<RiskLevel, RiskLevelInfo> = {
  red: { level: 'red', label: '高危', color: 'bg-red-500' },
  orange: { level: 'orange', label: '中高危', color: 'bg-orange-500' },
  yellow: { level: 'yellow', label: '中等', color: 'bg-yellow-500' },
  blue: { level: 'blue', label: '低风险', color: 'bg-blue-500' },
  green: { level: 'green', label: '正常', color: 'bg-green-500' },
  unknown: { level: 'unknown', label: '未知', color: 'bg-gray-500' },
};

// ============ 公司 ============

export interface Company {
  wind_code: string;
  sec_name: string;
  entity_id?: string;
  company_type?: string;
  industry_l1?: string;
  industry_l2?: string;
  province?: string;
  list_date?: string;
}

// ============ 会话 ============

export interface Session {
  session_id: string;      // 后端是 session_id，不是 id
  title: string;
  status?: string;
  created_at: string;
  updated_at: string;
  turn_count: number;      // 后端是 turn_count（会话轮数），不是 message_count
}

// ============ 消息 ============

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  evidence_ids?: string[];
  is_streaming?: boolean;
  thinking?: string;
  follow_ups?: string[];
  sources?: Array<{
    id: string;
    title: string;
    source: string;
  }>;
}

// ============ 面板状态 ============

export type PanelState = 'empty' | 'idle' | 'loading' | 'ready' | 'error' | 'thinking' | 'streaming' | 'done';

export interface TriggeredRuleInfo {
  rule_id: string;
  rule_name: string;
  evidence_ids: string[];
}

export interface PanelData {
  risk_level?: RiskLevel;
  triggered_rules?: TriggeredRuleInfo[];
  key_metrics?: Record<string, number>;
  follow_ups?: string[];
}

// ============ 财务分析 (对齐 FinanceResponseData) ============

export interface FinanceRuleItem {
  rule_id: string;
  rule_version: string;
  rule_name: string;
  status: 'triggered' | 'not_triggered' | 'not_applicable' | 'insufficient_data';
  severity: string;  // red / orange / yellow / green / unknown
  current: Record<string, { value: number; unit: string }>;
  history: Array<Record<string, unknown>>;  // 每期一条，字段名不固定
  industry: Record<string, number>;  // 旧结构（deprecated）
  industry_metrics?: IndustryPercentile[];  // typed 行业分位（V12 契约）
  quality: Record<string, unknown>;
  explanation: string;
  evidence_ids: string[];
  claim_ids: string[];
  warnings: string[];
}

export interface IndustryBenchmark {
  industry_l1: string;
  peer_count: number;
  percentile: Record<string, number | null>;
  warnings: string[];
}

export interface DataQuality {
  periods_available: number;
  periods_requested: number;
  statement_scope: string;
  gaps: string[];
  warnings: string[];
}

export interface FinanceResponseData {
  wind_code: string;
  sec_name: string;
  risk_level: string;
  rules: FinanceRuleItem[];
  industry_benchmark: IndustryBenchmark;
  data_quality: DataQuality;
  claim_ids: string[];
  evidence_ids: string[];
  warnings: string[];
}

// ============ 舆情事件 (对齐 EventsResponseData) ============

export interface SentimentSummary {
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  total_count: number;
  negative_ratio: number;
}

export interface EventSourceDTO {
  source_id: string;
  source_type: 'announcement' | 'research_report' | 'news' | 'regulation';
  source_record_id: string;
  title: string;
  published_at: string | null;
  source_uri: string | null;
  content_hash: string | null;
  fcode: string | null;
}

export interface EventCluster {
  event_cluster_id: string;  // 后端是 event_cluster_id，不是 cluster_id
  topic: string;
  event_count: number;
  start_date: string;
  end_date: string;
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed' | 'unknown';
  summary: string;
  cluster_method: string;
  cluster_version: string;
  sources: EventSourceDTO[];
  evidence_ids: string[];
}

export interface TimelineEvent {
  date: string;
  title: string;
  category: string;
  fcode_label: string;
  sentiment: string;
  summary: string;
  sources: string[];
  evidence_ids: string[];
}

export interface RatingChange {
  date: string;
  org_name: string;
  prev_rating: string;
  new_rating: string;
  change: 'up' | 'down' | 'maintain';
  title: string;
  evidence_id: string;
}

export interface KeywordSummary {
  top_keywords: Array<{ keyword: string; count: number }>;
  negative_keywords: string[];
}

export interface EventsResponseData {
  wind_code: string;
  sec_name: string;
  sentiment_summary: SentimentSummary;
  event_clusters: EventCluster[];
  timeline: TimelineEvent[];
  rating_changes: RatingChange[];
  keyword_summary: KeywordSummary;
  evidence_ids: string[];
  announcements_available: boolean;
  months_covered: number;
  warnings: string[];
}

// ============ 风险评估 (对齐 RiskResponseData) ============

export interface SubScore {
  dimension: string;
  label: string;
  score: number;
  weight: number;
  contribution: number;
  status: string;
  warning: string | null;
}

export interface RiskTag {
  tag: string;
  category: string;
  confidence: number;
}

export interface PatternMatch {
  pattern_id: string;
  pattern_name: string;
  triggered_rules: string[];
  confidence: string;  // high / medium / low
  reasoning: string;
}

export interface MitigatingFactor {
  factor: string;
  category: string;
  weight: number;
}

export interface DataCoverage {
  finance: boolean;
  equity: boolean;
  events: boolean;
  benchmarks: boolean;
  coverage_ratio: number;
  missing_modules: string[];
}

export interface RiskEvidence {
  evidence_id: string;
  source_type: string;
  claim_ids: string[];
  summary: string;
}

export interface RiskResponseData {
  wind_code: string;
  sec_name: string;
  as_of: string | null;
  overall_score: number;
  risk_level: string;
  sub_scores: SubScore[];
  risk_tags: RiskTag[];
  pattern_matches: PatternMatch[];  // 是对象数组，不是字符串数组
  confidence: number;
  data_coverage: DataCoverage;
  mitigating_factors: MitigatingFactor[];
  strategy_version: string;
  rule_set_version: string;
  evidence: ChatEvidenceV1[];
  warnings: string[];
}

// ============ 行业基准 (对齐 BenchmarksResponseData) ============

export interface IndustryPercentile {
  indicator: string;
  label: string;
  rule_id: string | null;
  metric_id: string | null;
  company_value: number | null;
  company_percentile: number | null;
  unit: string;
  sample_count: number;
  p05: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p95: number | null;
  peer_count: number;
  statement_scope: string;
}

export interface BenchmarksResponseData {
  wind_code: string;
  sec_name: string;
  industry_l1: string;
  period: string;
  percentiles: IndustryPercentile[];
  peer_count: number;
  is_sample_sufficient: boolean;
  generic_thresholds_only: boolean;
  dataset_version: string;
  statement_scope: string;
  warnings: string[];
}

// ============ 股权穿透 (对齐 EquityResponseData) ============

export interface EquityNodeDTO {
  id: string;
  entity_id: string;
  name: string;
  entity_type: string;
  wind_code: string | null;
  match_confidence: number | null;
  risk_level: string | null;
  mock: boolean;
  source_system: string;
}

export interface EquityEdgeDTO {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  ownership_pct: number | null;
  control_pct: number | null;
  valid_from: string | null;
  valid_to: string | null;
  source_id: string | null; // provenance，不是图节点 ID
  match_confidence: number | null;
  relationship_id: string | null;
  source_record_id: string | null;
  report_period: string | null;
  ann_dt: string | null;
  is_latest: boolean;
  mock: boolean;
  source_system: string;
}

export interface EquityPathDTO {
  path_id: string;
  node_ids: string[];
  edge_ids: string[];
  depth: number;
  final_control_pct: number | null;
  path_type: string;
  source_system: string;
}

export interface TargetCompanyDTO {
  entity_id: string;
  wind_code: string;
  name: string;
}

export interface EquityResponseData {
  target: TargetCompanyDTO;
  nodes: EquityNodeDTO[];
  edges: EquityEdgeDTO[];
  paths: EquityPathDTO[];
  as_of: string | null;
  graph_version: string;
  source_system: string;
  partial: boolean;
  warnings: string[];
}

// ============ 跨公司对比 (对齐 ComparisonsResponseData) ============

export interface CompanyIndicator {
  wind_code: string;
  sec_name: string;
  value: number | null;
  unit: string;
  severity: string;
  status: string;
}

export interface IndicatorCompare {
  indicator: string;
  label: string;
  companies: CompanyIndicator[];
}

export interface CompanyRiskSummary {
  wind_code: string;
  sec_name: string;
  industry_l1: string;
  risk_level: string;
  overall_score: number;
  triggered_rules: string[];
  pattern_matches: string[];
  coverage: number;
  evidence_ids: string[];
  warnings: string[];
}

export interface ComparisonsResponseData {
  period: string;
  statement_scope: string;
  companies: CompanyRiskSummary[];
  indicators: IndicatorCompare[];
  dataset_version: string;
  warnings: string[];
}

// ============ Chat 响应 (对齐 ChatDataV1) ============

export interface ChatEvidenceV1 {
  source: string;
  field: string;
  value: string;
  evidence_id: string;
  source_type: string;
  source_record_id: string;
  source_title: string;
  field_path: string | null;
  period: string | null;
  unit: string | null;
  source_uri: string | null;
  dataset_version: string;
}

/** 证据分类（前端聚合用） */
export interface EvidenceCategory {
  category: string;       // 'finance' | 'equity' | 'event' | 'audit' | 'regulatory'
  label: string;          // 中文标签
  items: ChatEvidenceV1[];
}

export interface ChatDataV1 {
  answer: string;
  evidence: ChatEvidenceV1[];
  graph: Record<string, unknown>;
  timeline: Array<Record<string, unknown>>;
  risk_score: Record<string, unknown>;
  warnings: string[];
  missing_modules: string[];
  trace_id: string;
  follow_ups: string[];
}

// ============ WebSocket ============

export type WSMessageType = 'thinking' | 'text_chunk' | 'structured_data' | 'evidence' | 'done' | 'error';

export interface WSMessage {
  type: WSMessageType;
  content?: string;
  data?: unknown;
}

// ============ 兼容旧字段名映射 ============

// types/truthnet.ts 字段 → 后端实际字段 的映射表
// 组件中使用旧字段名时，需要转换
export const FIELD_MAPPINGS = {
  // Company
  'code': 'wind_code',
  'name': 'sec_name',
  
  // Session
  'id': 'session_id',
  
  // EventCluster
  'cluster_id': 'event_cluster_id',
  
  // EquityNode
} as const;

