
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
  // 对齐后端 CompanyProfileV1（schemas/companies.py:43-58，v11 迁移新增字段）
  aliases?: string[];
  exchange?: string;
  industry_l1?: string;
  industry_l2?: string;
  sw_indu_code?: string;
  comp_type_code?: string | number | null;
  company_type?: string;
  listing_date?: string; // 后端字段为 listing_date（审计修正，原误写 list_date）
  data_quality?: Record<string, unknown>;
  risk_summary?: Record<string, unknown>;
}

// ============ 公司歧义确认（对齐 WS company.candidates 事件） ============

// v3.1 mention 分组协议：多候选时后端 candidates 为空、候选在 mentions[]；
// 每个 mention 携带 mention_id，确认需回传 mention_id + revision。
export interface PendingCompanyMention {
  mention_id: string;
  text: string;
  candidates: Array<{ wind_code: string; sec_name: string }>;
}

export interface PendingCompanyCandidates {
  turn_id: string;
  revision: number;
  mentions: PendingCompanyMention[];
}

// ============ 会话 ============

export interface Session {
  session_id: string;      // 后端是 session_id，不是 id
  user_id?: string | null;
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
  show_evidence_status?: boolean;
  is_streaming?: boolean;
  thinking?: string;
  follow_ups?: string[];
  // v3.3.4 收口复核清单 §5：结构化比较下一步（后端 next_steps 只读透出）
  next_steps?: ComparisonNextStep[];
  sources?: Array<{
    id: string;
    title: string;
    source: string;
    url?: string;
  }>;
}

// ============ 面板状态 ============

export type PanelState = 'empty' | 'idle' | 'loading' | 'ready' | 'error' | 'thinking' | 'streaming' | 'done';

export interface TriggeredRuleInfo {
  rule_id: string;
  rule_name: string;
  evidence_ids: string[];
  /** 2026-08-16 面板可读性：后端 turn.completed.finance.triggered_rules 透传 */
  severity?: string;
  explanation?: string;
}

export interface PanelData {
  risk_level?: RiskLevel;
  triggered_rules?: TriggeredRuleInfo[];
  key_metrics?: Record<string, number>;
  follow_ups?: string[];
  // v3.3.4 收口复核清单 §5：结构化比较下一步（优先于 follow_ups 渲染）
  next_steps?: ComparisonNextStep[];
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
  /** 相似指标案例（后端 FinanceRuleItem.similar_cases，仅触发规则可能非空） */
  similar_cases?: SimilarCasesResult | null;
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
}

export interface IndustryBenchmark {
  industry_l1: string;
  peer_count: number;
  percentile: Record<string, number | null>;
  warnings: string[];
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
}

export interface DataQuality {
  periods_available: number;
  periods_requested: number;
  statement_scope: string;
  gaps: string[];
  warnings: string[];
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
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
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
}

// ============ 相似案例 (对齐 SimilarCase / SimilarCasesResult) ============

export interface SimilarCaseSource {
  source_table: string;
  row_id?: number | null;
  source_record_id?: string | null;
  wind_code: string;
  report_period: string;
  report_statement_type?: string;
  period_role?: 'current' | 'prior';
  fields?: string[];
}

export interface SimilarCaseItem {
  company_code: string;
  company_name: string;
  industry: string;
  period: string;
  metric: Record<string, unknown>;
  distance: number;
  statement_type?: string;
  report_statement_type?: string;
  sources?: SimilarCaseSource[];
  evidence_ids?: string[];
}

export interface SimilarCasesResult {
  status: 'ok' | 'empty' | 'error' | 'not_supported';
  reason?: string;
  cases: SimilarCaseItem[];
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
  /** 公告 object_id：调用公告 PDF 摘要端点定位原文 */
  object_id?: string;
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
  // 舆情影响结论（后端 events.py:134/138；GET 需 include_impacts=true）
  impact_conclusions: ImpactConclusion[];
  impact_warnings: string[];
  evidence_ids: string[];
  announcements_available: boolean;
  months_covered: number;
  warnings: string[];
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
}

// ============ 舆情影响结论 (对齐 schemas/events.py ImpactConclusion) ============

export interface CausalityStep {
  text: string;
  statement_type: string; // observed | inference | projection
  evidence_ids: string[];
}

export interface ImpactConclusion {
  conclusion: string;
  impact_type: string; // equity_structure | operation | financing | market
  direction: string; // positive | negative | neutral
  severity: string; // low | medium | high
  evidence_ids: string[];
  causality_chain: CausalityStep[];
  statement_type: string; // observed | inference | projection
  display_tag: string;
}

// 推导链: RiskResponseData.derivation_chains (Phase E)
export interface DerivationDataRef {
  evidence_id: string;
  source_type: string;
  field_path: string;
  period: string;
  value?: string | null;
  unit?: string | null;
}

export interface DerivationSignal {
  signal_id: string;
  signal_type: string;
  label: string;
  severity: string;
  explanation: string;
  current: Record<string, unknown>;
  industry_percentile?: number | null;
  data_refs: DerivationDataRef[];
  evidence_ids: string[];
}

export interface DerivationChain {
  conclusion_id: string;
  conclusion_type: string;
  conclusion: string;
  risk_level: string;
  signals: DerivationSignal[];
  evidence_ids: string[];
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
  phase?: string;
  alternative_explanation?: string;
  regulatory_hint?: string;
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
  evidence: RiskEvidence[]; // /risk 返回 RiskEvidence（审计 P1-1 修正原 ChatEvidenceV1）
  warnings: string[];
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
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
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
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
  // 后端 schemas/equity.py:126,135-146 新增字段（前端暂未消费，契约对齐用）
  equity_chains?: Array<Record<string, unknown>>;
  requested_depth?: number;
  max_observed_hops?: number;
  truncated?: boolean;
  coverage_note?: string;
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
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
  // 对齐后端 comparisons.py TriggeredRuleDetail（规则级指标值/方向/单位/证据）
  triggered_rule_details?: TriggeredRuleDetail[];
  partial?: boolean;
  warnings?: string[];
  /** 推导链 (Phase E) */
  derivation_chains?: DerivationChain[];
}

// ============ 触发规则详情 (对齐 comparisons.py TriggeredRuleDetail/RuleMetricValue) ============

export interface RuleMetricValue {
  key: string;
  label: string;
  value: number | string | boolean | null;
  unit: string;
  // higher_is_riskier / lower_is_riskier / neutral（D2 元数据）
  risk_direction: string;
}

export interface TriggeredRuleDetail {
  rule_id: string;
  label: string;
  status: string;
  severity: string;
  as_of: string;
  metrics: RuleMetricValue[];
  evidence_ids: string[];
  explanation: string;
}

export interface ComparisonsResponseData {
  period: string;
  statement_scope: string;
  companies: CompanyRiskSummary[];
  indicators: IndicatorCompare[];
  dataset_version: string;
  warnings: string[];
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
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
  items: RiskEvidence[];  // 画像页证据链消费 RiskEvidence（审计 P1-1）
}

// Chat 响应结论声明（对齐后端 ClaimV1，对齐审计 P2-6）
export interface ClaimV1 {
  claim_id: string;
  text: string;
  claim_type: string;
  severity: string;
  confidence: number | null;
  rule_id: string | null;
  rule_version: string | null;
  evidence_ids: string[];
  verification_status: string;
  limitations: string[];
}

// 模块状态（对齐后端 ModuleStatusV1 typed 对象，非字符串）
export type ModuleStatusState =
  | 'pending'
  | 'running'
  | 'success'
  | 'partial'
  | 'failed'
  | 'skipped'
  | 'cancelled';

export interface ModuleStatusV1 {
  state: ModuleStatusState;
  error_code: string | null;
  recoverable: boolean;
  duration_ms: number | null;
}

export interface ChatDataV1 {
  answer: string;
  evidence: ChatEvidenceV1[];
  claims: ClaimV1[];
  module_status: Record<string, ModuleStatusV1>;
  risk_level: RiskLevel;
  graph: Record<string, unknown>;
  timeline: Array<Record<string, unknown>>;
  risk_score: Record<string, unknown>;
  warnings: string[];
  missing_modules: string[];
  trace_id: string;
  follow_ups: string[];
  intent?: string;
  // 2026-08-08 追加：可展示证据子集（叶子 Claim 引用、排除综合 risk）
  supporting_evidence?: ChatEvidenceV1[];
  // 2026-08-08 追加：用户请求中的期次原文（如"2025年报"）
  requested_period_text?: string;
  // 2026-08-14 追加：v3.3.4 轻量整体对比只读载荷（后端 ChatDataV1）
  comparison_mode?: string;
  overview_rows?: OverviewMetricRow[];
  requested_scope?: string;
  next_steps?: ComparisonNextStep[];
  // B2 舆情影响结论（后端 chat.py:283-289 与 events 同构）
  impact_conclusions?: ImpactConclusion[];
  impact_warnings?: string[];
  // 审计 item 10.7：后端 ChatDataV1 已就绪、前端类型缺失的字段（契约对齐用）
  session_id?: string;
  company_candidates?: Array<Record<string, unknown>>;
  company_mentions?: Array<Record<string, unknown>>;
  needs_confirmation?: boolean;
  segmentation_alternatives?: Array<Record<string, unknown>>;
  entity_resolution_issues?: Array<Record<string, unknown>>;
  pattern_matches?: Array<Record<string, unknown>>;
  equity_chains?: Array<Record<string, unknown>>;
}

// ============ 轻量整体对比（对齐 v3.3.4 Preview First 载荷）============

export type ComparisonNextStepKind =
  | 'open_full_comparison'
  | 'open_industry_comparison'
  | 'open_multi_company_comparison'
  | 'choose_comparison_pair'
  | 'compare_metric';

export interface ComparisonNextStep {
  kind: ComparisonNextStepKind;
  label: string;
  target: string;
  participant_codes: string[];
  params: Record<string, string>;
}

export interface OverviewComparisonValue {
  company_code: string;
  sec_name: string;
  metric_id: string;
  metric_label: string;
  period: string;
  value: number | string;
  unit: string;
  observations?: Array<Record<string, unknown>>;
}

export interface OverviewMetricRow {
  metric_id: string;
  metric_label: string;
  status: 'ok' | 'insufficient_data' | 'unsupported';
  unit: string;
  period: string;
  values: OverviewComparisonValue[];
  difference: number | string | null;
  difference_unit: string;
  conclusion: string;
  warnings: string[];
  /** 推导链 (Phase E) */
  derivation_chains: DerivationChain[];
}

// ============ 报告 ============
// 报告任务状态类型以 api-client.ts 的 ReportJobStatus 为准（对齐后端
// schemas/reports.py ReportJobStatusData：report_id + queued/running/
// succeeded/failed/cancelled + progress + download_available 等）。
// 后端无「报告内容」详情端点，摘要/关键发现在 PDF 文件里，不做内容类型。

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
