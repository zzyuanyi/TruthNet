// 织网鉴真 TruthNet - 跨公司对比页
// Phase 3: 多公司对比分析

import { useState, useEffect, useMemo, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { ExportSnapshotButton } from '@/components/ExportSnapshotButton';
import {
  ArrowLeft,
  AlertTriangle,
  BarChart3,
  Building2,
  Search,
  X,
  Loader2,
  FileText,
  Newspaper,
} from 'lucide-react';
import { truthnetAPI } from '@/lib/api-client';
import { MarkdownRenderer } from '@/components/markdown-renderer';
import type {
  BenchmarksResponseData,
  CompanyRiskSummary,
  ComparisonAnalysisCompany,
  ComparisonAnalysisData,
  ComparisonAnalysisSegment,
  ComparisonsResponseData,
  IndicatorCompare,
  RiskLevel,
  TimelineEvent,
} from '@/types/truthnet';
import type { CompanyCandidate } from '@/lib/api-client';

// 对比公司选择器（无 codes 默认入口，审计 P1-2）
function CompanySelector({ onSelect }: { onSelect: (codes: string[]) => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CompanyCandidate[]>([]);
  const [selected, setSelected] = useState<CompanyCandidate[]>([]);
  const [searching, setSearching] = useState(false);
  const MAX_COMPANIES = 5;

  const doSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await truthnetAPI.searchCompanies(query.trim());
      setResults(res.data?.candidates || []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const toggle = (c: CompanyCandidate) => {
    setSelected(prev => {
      if (prev.find(x => x.wind_code === c.wind_code)) {
        return prev.filter(x => x.wind_code !== c.wind_code);
      }
      if (prev.length >= MAX_COMPANIES) return prev;
      return [...prev, c];
    });
  };

  return (
    <div className="w-full text-left">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="输入公司名称或代码（如 金牌家居 / 600518）"
          onKeyDown={e => e.key === 'Enter' && doSearch()}
        />
        <Button onClick={doSearch} disabled={searching || !query.trim()}>
          <Search className="h-4 w-4 mr-1" />
          {searching ? '搜索中…' : '搜索'}
        </Button>
      </div>
      {results.length > 0 && (
        <div className="mt-3 border rounded-lg divide-y max-h-64 overflow-auto">
          {results.map(c => {
            const isSelected = selected.some(x => x.wind_code === c.wind_code);
            return (
              <button
                key={c.wind_code}
                onClick={() => toggle(c)}
                className="w-full flex items-center justify-between px-3 py-2 hover:bg-accent text-left"
              >
                <div>
                  <div className="text-sm font-medium">{c.sec_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {c.wind_code} · {c.exchange || '-'}
                  </div>
                </div>
                <Badge variant={isSelected ? 'default' : 'outline'}>
                  {isSelected ? '已选' : '选择'}
                </Badge>
              </button>
            );
          })}
        </div>
      )}
      {selected.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-muted-foreground mb-1">
            已选 {selected.length}/{MAX_COMPANIES}：
          </p>
          <div className="flex flex-wrap gap-2">
            {selected.map(c => (
              <Badge key={c.wind_code} variant="secondary" className="gap-1 pr-1">
                {c.sec_name}
                <button
                  onClick={() => toggle(c)}
                  className="ml-1 rounded-sm hover:bg-muted p-0.5"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
          <Button
            className="mt-3 w-full"
            disabled={selected.length < 2}
            onClick={() => onSelect(selected.map(c => c.wind_code))}
          >
            {selected.length < 2 ? '至少选择 2 家公司' : `开始对比（${selected.length} 家）`}
          </Button>
        </div>
      )}
    </div>
  );
}

// v3.3.4 收口复核清单 §5.2-6：choose_comparison_pair 入口——
// 打开选两家界面并预填全部已识别代码（不自动选前两家）
function ChoosePair({ candidateCodes }: { candidateCodes: string[] }) {
  const navigate = useNavigate();
  const [names, setNames] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const key = candidateCodes.join(',');

  useEffect(() => {
    let cancelled = false;
    candidateCodes.forEach(code => {
      truthnetAPI
        .getCompanyProfile(code)
        .then(res => {
          if (!cancelled && res.data?.sec_name) {
            setNames(prev => ({ ...prev, [code]: res.data!.sec_name! }));
          }
        })
        .catch(() => undefined);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const toggle = (code: string) => {
    // 收口复核审查 P2b：choose_comparison_pair 语义 = 恰好选择两家
    // （已选 2 家时不得继续增加，与文案「选择两家对比」一致）
    setSelected(prev =>
      prev.includes(code)
        ? prev.filter(c => c !== code)
        : prev.length >= 2
          ? prev
          : [...prev, code],
    );
  };

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="w-full max-w-xl">
        <div className="text-center mb-6">
          <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <h2 className="text-lg font-medium">从已识别公司中选择两家对比</h2>
          <p className="text-sm text-muted-foreground mt-1">
            对话一次仅支持两家数值比较；以下为已识别的全部公司，请勾选其中两家
          </p>
        </div>
        <div className="flex flex-wrap gap-2 justify-center">
          {candidateCodes.map(code => {
            const isSelected = selected.includes(code);
            const disabled = selected.length >= 2 && !isSelected;
            return (
              <button
                key={code}
                onClick={() => toggle(code)}
                disabled={disabled}
                className={cn(
                  'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors',
                  isSelected
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-muted/50',
                  disabled && 'opacity-50 cursor-not-allowed',
                )}
              >
                <span className="font-medium">{names[code] || code}</span>
                <span className="text-xs text-muted-foreground">{code}</span>
                <Badge variant={isSelected ? 'default' : 'outline'}>
                  {isSelected ? '已选' : '选择'}
                </Badge>
              </button>
            );
          })}
        </div>
        <Button
          className="mt-6 w-full"
          disabled={selected.length < 2}
          onClick={() => navigate(`/compare?codes=${selected.join(',')}`)}
        >
          {selected.length < 2
            ? `请选择 2 家公司（已选 ${selected.length}）`
            : `开始对比（${selected.length} 家）`}
        </Button>
      </div>
    </div>
  );
}

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string }> = {
  red: { label: '高危', color: 'bg-red-500 text-white' },
  orange: { label: '中高危', color: 'bg-orange-500 text-white' },
  yellow: { label: '中等', color: 'bg-yellow-500 text-white' },
  blue: { label: '低风险', color: 'bg-blue-500 text-white' },
  green: { label: '正常', color: 'bg-green-500 text-white' },
  unknown: { label: '未知', color: 'bg-gray-500 text-white' },
};

// 后端 D2 元数据单位为英文键（D3 参数评审前），前端映射为展示单位
const unitLabelMap: Record<string, string> = {
  percent: '%',
  percentage_point: '%',
  pp: '个百分点',
  quarters: '个季度',
  ratio: '比率',
  yuan: '元',
  times: '倍',
  days: '天',
  'CNY': '元',
  percent_pct: '%',
};

// 8/23 可读性：指标状态中文映射（后端返回英文状态码）
const INDICATOR_STATUS_LABELS: Record<string, string> = {
  triggered: '已触发',
  not_triggered: '未触发',
  insufficient_data: '数据不足',
  not_applicable: '不适用',
  unknown: '未知',
};

// 后端对比服务已有完整财务规则分析缓存；请求 7 条规则可一次性展示，
// 不增加后端计算量（evaluate_all_rules 本就全量执行，仅多透出 current 值）。
const DEFAULT_COMPARISON_RULES = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'];

function formatFinancialValue(value: number | null, unit: string): string {
  if (value == null) return '暂无数据';
  if (unit === 'CNY') return `${(value / 100000000).toFixed(2)} 亿元`;
  if (unit === 'percent') return `${value.toFixed(2)}%`;
  if (unit === 'ratio') return `${value.toFixed(2)}×`;
  if (unit === 'pp') return `${value.toFixed(2)} 个百分点`;
  if (unit === 'days') return `${value.toFixed(2)} 天`;
  return `${value}${unit}`;
}

function formatRuleMetricValue(value: number | null, unit: string): string {
  if (value == null) return '暂无数据';
  if (unit === 'bool') return Number(value) === 1 ? '是' : '否';
  if (unit === 'ratio') return `${value.toFixed(2)}×`;
  if (unit === 'pp' || unit === 'percentage_point') return `${value.toFixed(1)} 个百分点`;
  if (unit === 'percent') return `${value.toFixed(1)}%`;
  if (unit === 'days') return `${value.toFixed(0)} 天`;
  return `${value}${unitLabelMap[unit] ?? unit}`;
}

function formatReportPeriod(period: string): string {
  return /^\d{8}$/.test(period)
    ? `${period.slice(0, 4)}-${period.slice(4, 6)}-${period.slice(6)}`
    : period || '暂无数据';
}

const RISK_ORDER: Record<string, number> = {
  red: 5,
  orange: 4,
  yellow: 3,
  blue: 2,
  green: 1,
  unknown: 0,
};

interface RuleMatrixCell {
  code: string;
  name: string;
  triggered: boolean;
  severity: string;
  explanation: string;
  metrics: Array<{ label: string; text: string; riskDirection?: string }>;
  asOf?: string;
  evidenceCount: number;
}

interface RuleMatrixRow {
  ruleId: string;
  label: string;
  cells: RuleMatrixCell[];
}

interface IndicatorTableRow extends IndicatorCompare {
  relatedRules: string[];
}

const RISK_SEVERITY_LABELS: Record<string, string> = {
  red: '高危预警',
  orange: '中高危预警',
  yellow: '中等预警',
  blue: '低风险提示',
  green: '正常',
  unknown: '数据不足',
};

function buildIndicatorTableRows(indicators: IndicatorCompare[]): IndicatorTableRow[] {
  const rows = new Map<string, IndicatorTableRow>();
  indicators.forEach(indicator => {
    const key = indicator.label || indicator.indicator;
    const ruleId = indicator.indicator.match(/^(R\d+)/i)?.[1]?.toUpperCase();
    const existing = rows.get(key);
    if (!existing) {
      rows.set(key, {
        ...indicator,
        companies: [...indicator.companies],
        relatedRules: ruleId ? [ruleId] : [],
      });
      return;
    }
    if (ruleId && !existing.relatedRules.includes(ruleId)) existing.relatedRules.push(ruleId);
    const cells = new Map(existing.companies.map(cell => [cell.wind_code, cell]));
    indicator.companies.forEach(cell => {
      const current = cells.get(cell.wind_code);
      if (!current || (current.value == null && cell.value != null)) cells.set(cell.wind_code, cell);
    });
    existing.companies = Array.from(cells.values());
  });
  return Array.from(rows.values());
}

function buildRuleMatrix(companies: CompanyRiskSummary[]): RuleMatrixRow[] {
  const ruleIds = new Set<string>();
  const labelByRule = new Map<string, string>();
  companies.forEach(c => {
    c.triggered_rules?.forEach(id => ruleIds.add(id));
    c.triggered_rule_details?.forEach(d => {
      ruleIds.add(d.rule_id);
      labelByRule.set(d.rule_id, d.label || d.rule_id);
    });
  });

  return Array.from(ruleIds)
    .sort()
    .map(ruleId => ({
      ruleId,
      label: labelByRule.get(ruleId) || ruleId,
      cells: companies.map(c => {
        const detail = c.triggered_rule_details?.find(d => d.rule_id === ruleId);
        return {
          code: c.wind_code,
          name: c.sec_name,
          triggered: c.triggered_rules?.includes(ruleId) || Boolean(detail),
          severity: detail?.severity || (c.triggered_rules?.includes(ruleId) ? 'yellow' : 'green'),
          explanation: detail?.explanation || '',
          metrics: (detail?.metrics || []).map(m => ({
            label: m.label || m.key,
            text: m.value != null ? `${m.value}${unitLabelMap[m.unit] ?? (m.unit || '')}` : '-',
            riskDirection: m.risk_direction,
          })),
          asOf: detail?.as_of || undefined,
          evidenceCount: detail?.evidence_ids?.length || 0,
        };
      }),
    }));
}

function buildComparisonConclusions(companies: CompanyRiskSummary[]): string[] {
  const ranked = [...companies].sort((a, b) => {
    const levelDiff = (RISK_ORDER[b.risk_level] ?? 0) - (RISK_ORDER[a.risk_level] ?? 0);
    if (levelDiff !== 0) return levelDiff;
    const scoreA = a.partial ? Number.NEGATIVE_INFINITY : a.overall_score;
    const scoreB = b.partial ? Number.NEGATIVE_INFINITY : b.overall_score;
    return scoreB - scoreA;
  });
  const conclusions: string[] = [];

  const highestRisk = ranked[0];
  const relativelyStable = ranked[ranked.length - 1];
  const riskText = ranked
    .map((c, i) => `${i + 1}. ${c.sec_name}：${riskLevelConfig[c.risk_level as RiskLevel]?.label ?? c.risk_level}（${c.partial ? '暂无评分' : `${c.overall_score.toFixed(3)} 分`}）`)
    .join('；');
  conclusions.push(`风险排序：${riskText}`);
  if (highestRisk && relativelyStable) {
    conclusions.push(
      `当前相对风险较低的是${relativelyStable.sec_name}，风险最集中的是${highestRisk.sec_name}；两者差异主要看综合评分、触发规则数量和是否存在高危模式。`,
    );
  }

  const commonRules = new Set<string>();
  const uniqueRulesByCompany = companies.map(c => ({
    name: c.sec_name,
    rules: (c.triggered_rules || []).filter(rid =>
      !companies.some(other => other.wind_code !== c.wind_code && (other.triggered_rules || []).includes(rid)),
    ),
  }));
  companies.forEach((c, idx) => {
    const own = new Set(c.triggered_rules || []);
    companies.slice(idx + 1).forEach(other => {
      (other.triggered_rules || []).forEach(rid => {
        if (own.has(rid)) commonRules.add(rid);
      });
    });
  });
  if (commonRules.size > 0) {
    conclusions.push(`共同触发规则：${Array.from(commonRules).sort().join('、')}，建议优先对比这些维度的指标值与证据。`);
  } else {
    conclusions.push(`${companies.length} 家公司没有共同触发规则，风险差异主要来自各自财务指标结构。`);
  }

  const uniqueRuleTexts = uniqueRulesByCompany
    .filter(item => item.rules.length > 0)
    .map(item => `${item.name} 的独有规则：${item.rules.slice(0, 3).join('、')}`);
  if (uniqueRuleTexts.length > 0) {
    conclusions.push(uniqueRuleTexts.join('；'));
  }

  const patterns = companies
    .filter(c => (c.pattern_matches?.length ?? 0) > 0)
    .map(c => `${c.sec_name}：${c.pattern_matches!.join('、')}`);
  if (patterns.length > 0) {
    conclusions.push(`风险模式：${patterns.join('；')}。`);
  }

  const coverageText = companies
    .map(c => `${c.sec_name}${c.partial || c.coverage <= 0 ? '覆盖不足' : `覆盖 ${(c.coverage * 100).toFixed(0)}%`}`)
    .join('；');
  conclusions.push(`数据覆盖：${coverageText}。`);

  return conclusions;
}

export default function ComparePage() {
  useDocumentTitle('跨公司对比');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<CompanyRiskSummary[]>([]);
  const [comparisonData, setComparisonData] = useState<ComparisonsResponseData | null>(null);
  const [industryBenchmarks, setIndustryBenchmarks] = useState<BenchmarksResponseData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [industryUnavailable, setIndustryUnavailable] = useState(false);
  // 8/23 会7 深化：跨公司 LLM 综合分析（8/23 SSE 流式——分片状态渐进渲染）
  const [analysisSections, setAnalysisSections] = useState<string[]>([]);
  const [analysisSegments, setAnalysisSegments] = useState<ComparisonAnalysisSegment[]>([]);
  const [analysisCompanies, setAnalysisCompanies] = useState<ComparisonAnalysisCompany[]>([]);
  const [analysisMethod, setAnalysisMethod] = useState('');
  const [analysisWarnings, setAnalysisWarnings] = useState<string[]>([]);
  const [analysisProgress, setAnalysisProgress] = useState<{ ready: number; total: number } | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [showAllIndicators, setShowAllIndicators] = useState(false);
  // 8/23 舆情信号：每家公司负面事件（评分保底/舆情维度的证据展示）
  const [negativeEvents, setNegativeEvents] = useState<Record<string, TimelineEvent[]>>({});
  const [eventsLoading, setEventsLoading] = useState(false);

  // v3.3.4 收口复核清单 §5.3：读取 codes + scope（默认 full）；
  // choose_comparison_pair 入口用 candidates 参数（预填全部代码）
  const codesParam = [
    ...new Set(
      (searchParams.get('codes') || '')
        .split(',')
        .map(c => c.trim())
        .filter(Boolean),
    ),
  ].slice(0, 5);
  const scope = searchParams.get('scope') ?? 'full';
  const candidateCodes = [
    ...new Set(
      (searchParams.get('candidates') || '')
        .split(',')
        .map(c => c.trim())
        .filter(Boolean),
    ),
  ].slice(0, 5);

  // 8/23 StrictMode 防重：dev 双 effect 会发起两套对比请求（analysis 的
  // LLM 并发超时 → 降级覆盖 LLM 内容）；同 codes 的第二次调用直接跳过。
  const loadInFlight = useRef(false);
  const loadForCodes = useRef('');

  useEffect(() => {
    const loadCompanies = async () => {
      const key = codesParam.join(',');
      if (candidateCodes.length === 0 && codesParam.length > 0) {
        if (loadInFlight.current && loadForCodes.current === key) return;
        loadInFlight.current = true;
        loadForCodes.current = key;
      }
      setLoading(true);
      setError(null);
      setIndustryUnavailable(false);
      setIndustryBenchmarks([]);

      // 选两家入口：不自动查询，等待用户在预填列表中勾选
      if (candidateCodes.length > 0) {
        setLoading(false);
        return;
      }

      if (codesParam.length === 0) {
        setError('请选择要对比的公司');
        setLoading(false);
        return;
      }

      if (scope === 'industry') {
        try {
          const results = await Promise.all(
            codesParam.map(code => truthnetAPI.getBenchmarks(code)),
          );
          const benchmarkData = results
            .map(result => result.data)
            .filter((data): data is BenchmarksResponseData => Boolean(data));
          if (benchmarkData.length === 0) setIndustryUnavailable(true);
          else setIndustryBenchmarks(benchmarkData);
        } catch (err) {
          setError(err instanceof Error ? err.message : '行业基准加载失败');
        } finally {
          setLoading(false);
          loadInFlight.current = false;
        }
        return;
      }

      try {
        // 调用对比 API
        const response = await truthnetAPI.compareCompanies(codesParam, undefined, DEFAULT_COMPARISON_RULES);
        const data = response.data;
        if (!data) {
          setError('无对比数据');
          setLoading(false);
          return;
        }
        setCompanies(data.companies);
        setComparisonData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败');
      } finally {
        setLoading(false);
        loadInFlight.current = false;
      }
    };

    loadCompanies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 8/23 舆情信号：并行获取各家公司负面事件（证据展示——如立案事件
  // 导致 signal_floor 保底高危，这里可见依据）
  useEffect(() => {
    if (codesParam.length === 0 || candidateCodes.length > 0) return;
    let cancelled = false;
    setEventsLoading(true);
    Promise.allSettled(
      codesParam.map(code =>
        truthnetAPI.getEvents(code).then(res => {
          const timeline = (res.data?.timeline || []) as TimelineEvent[];
          const negative = timeline.filter(t => t.sentiment === 'negative');
          return { code, negative };
        }),
      ),
    ).then(results => {
      if (cancelled) return;
      const map: Record<string, TimelineEvent[]> = {};
      results.forEach(r => {
        if (r.status === 'fulfilled') map[r.value.code] = r.value.negative;
      });
      setNegativeEvents(map);
      setEventsLoading(false);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 8/23 会7 深化：跨公司 LLM 综合分析（SSE 流式：阶段进度 + 分节推送；
  // 连接失败时 REST 兜底一次性获取）
  const analysisInFlight = useRef(false);
  const analysisForCodes = useRef('');
  useEffect(() => {
    if (codesParam.length < 2 || candidateCodes.length > 0) return;
    const key = codesParam.join(',');
    // 8/23 StrictMode 防重：同 codes 双 effect 只发一次（LLM 并发超时
    // 会降级覆盖 LLM 内容）
    if (analysisInFlight.current && analysisForCodes.current === key) return;
    analysisInFlight.current = true;
    analysisForCodes.current = key;
    let cancelled = false;
    let es: EventSource | null = null;
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysisSections([]);
    setAnalysisSegments([]);
    setAnalysisCompanies([]);
    setAnalysisMethod('');
    setAnalysisWarnings([]);
    setAnalysisProgress(null);

    const finish = (method: string, warnings: string[], companies: unknown[]) => {
      if (cancelled) return;
      setAnalysisMethod(method);
      setAnalysisWarnings(Array.isArray(warnings) ? warnings as string[] : []);
      setAnalysisCompanies((companies || []) as ComparisonAnalysisCompany[]);
      setAnalysisLoading(false);
      analysisInFlight.current = false;
    };

    // REST 兜底（SSE 失败时调用）
    const fallbackREST = () => {
      if (cancelled || analysisInFlight.current === false) return;
      truthnetAPI
        .getComparisonAnalysis(codesParam)
        .then(res => {
          if (cancelled || !res.data) return;
          setAnalysisSections([res.data.overall]);
          setAnalysisSegments(res.data.segments || []);
          finish(res.data.method || '', res.data.warnings || [], res.data.companies || []);
        })
        .catch(err => {
          if (!cancelled) {
            setAnalysisError(err instanceof Error ? err.message : '综合分析失败');
            setAnalysisLoading(false);
            analysisInFlight.current = false;
          }
        });
    };

    try {
      es = truthnetAPI.streamComparisonAnalysis(codesParam, evt => {
        if (cancelled) return;
        const payload = evt.payload || {};
        switch (evt.event_type) {
          case 'analysis.started':
            setAnalysisProgress({ ready: 0, total: Number(payload.total) || codesParam.length });
            break;
          case 'analysis.company_ready':
            setAnalysisProgress(prev => ({
              ready: (prev?.ready ?? 0) + 1,
              total: Number(payload.total) || codesParam.length,
            }));
            break;
          case 'analysis.company_failed':
            setAnalysisWarnings(prev => [...prev, `公司 ${String(payload.code || '')} 风险分析失败`]);
            break;
          case 'analysis.section':
            setAnalysisSections(prev => [...prev, String(payload.text || '')]);
            break;
          case 'analysis.segment':
            setAnalysisSegments(prev => [
              ...prev,
              {
                company_code: String(payload.company_code || ''),
                title: String(payload.title || ''),
                detail: String(payload.detail || ''),
              },
            ]);
            break;
          case 'analysis.completed':
            finish(
              String(payload.method || ''),
              (payload.warnings as string[]) || [],
              (payload.companies as unknown[]) || [],
            );
            break;
          default:
            break;
        }
      }, msg => {
        // SSE 失败 → REST 兜底
        if (!cancelled) fallbackREST();
      });
    } catch {
      fallbackREST();
    }

    return () => {
      cancelled = true;
      if (es) es.close();
      // 8/23 关键：cleanup 复位 in-flight——StrictMode 双 effect 时序下
      // 第一次 effect 的 cleanup 关闭 SSE 后，第二次 effect 才能重新发起
      // （否则防重把第二次拦掉 → 无请求在跑 → 永久 loading）
      analysisInFlight.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const ruleMatrix = useMemo(() => buildRuleMatrix(companies), [companies]);
  const indicatorTableRows = useMemo(
    () => buildIndicatorTableRows(comparisonData?.indicators || []),
    [comparisonData],
  );
  const priorityIndicatorRows = indicatorTableRows.filter(row =>
    row.companies.some(cell => cell.status === 'triggered'),
  );
  const visibleIndicatorRows = showAllIndicators ? indicatorTableRows : priorityIndicatorRows;
  const comparisonConclusions = useMemo(
    () => buildComparisonConclusions(companies),
    [companies],
  );


  // 获取风险等级样式
  const getRiskLevelStyle = (level: string) => {
    return riskLevelConfig[level as RiskLevel]?.color || 'bg-gray-500 text-white';
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col bg-background">
        <header className="border-b px-6 py-4 flex items-center gap-4">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-6 w-32" />
        </header>
        <div className="flex-1 p-6 space-y-4">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  // v3.3.4 收口复核清单 §5.2-6：choose_comparison_pair 选两家入口
  if (candidateCodes.length > 0) {
    return (
      <div className="h-full flex flex-col bg-background">
        <header className="border-b px-6 py-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-lg font-medium">跨公司对比</h1>
        </header>
        <ChoosePair candidateCodes={candidateCodes} />
      </div>
    );
  }

  if (industryUnavailable) {
    return (
      <div className="h-full flex flex-col bg-background">
        <header className="border-b px-6 py-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-lg font-medium">跨公司对比 · 行业对比</h1>
        </header>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center max-w-md">
            <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-lg font-medium">行业基准暂无数据</h2>
            <p className="text-sm text-muted-foreground mt-2">
              当前公司或期间没有足够的同行样本，无法展示可靠的行业分位。
              可先查看这些公司的普通完整对比。
            </p>
            <Button
              className="mt-4"
              onClick={() => navigate(`/compare?codes=${codesParam.join(',')}`)}
            >
              查看普通完整对比
            </Button>
            <Button variant="outline" className="mt-4 ml-2" onClick={() => navigate(-1)}>
              返回
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (scope === 'industry' && industryBenchmarks.length > 0) {
    return (
      <div className="h-full flex flex-col bg-background">
        <header className="border-b px-6 py-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-lg font-medium">跨公司对比 · 行业基准</h1>
        </header>
        <div className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-5xl space-y-4">
            {industryBenchmarks.map(data => (
              <Card key={data.wind_code}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">
                    {data.sec_name}（{data.wind_code}） · {data.industry_l1 || '行业未知'}
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    期间：{data.period}；口径：{data.statement_scope}；同行样本：{data.peer_count}
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs text-muted-foreground">
                          <th className="px-2 py-2">指标</th>
                          <th className="px-2 py-2">公司值</th>
                          <th className="px-2 py-2">行业 P50</th>
                          <th className="px-2 py-2">公司分位</th>
                          <th className="px-2 py-2">有效样本</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.percentiles.map(metric => (
                          <tr key={metric.indicator} className="border-b last:border-0">
                            <td className="px-2 py-2">{metric.label || metric.indicator}</td>
                            <td className="px-2 py-2">{metric.company_value != null ? `${metric.company_value}${metric.unit || ''}` : '暂无数据'}</td>
                            <td className="px-2 py-2">{metric.p50 != null ? `${metric.p50}${metric.unit || ''}` : '暂无数据'}</td>
                            <td className="px-2 py-2">{metric.company_percentile != null ? `${metric.company_percentile}%` : '暂无数据'}</td>
                            <td className="px-2 py-2">{metric.sample_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {(data.warnings?.length ?? 0) > 0 && (
                    <p className="mt-3 text-xs text-muted-foreground">{data.warnings.join('；')}</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    // 无 codes 默认入口 → 内置选股器（审计 P1-2，替代原"请选择公司"错误页）
    const showSelector = error === '请选择要对比的公司';
    return (
      <div className="h-full flex flex-col bg-background">
        <header className="border-b px-6 py-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-lg font-medium">跨公司对比</h1>
        </header>
        <div className="flex-1 flex items-center justify-center p-6">
          {showSelector ? (
            <div className="w-full max-w-xl">
              <div className="text-center mb-6">
                <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                <h2 className="text-lg font-medium">选择要对比的公司</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  支持 2~5 家，搜索后勾选即可
                </p>
              </div>
              <CompanySelector
                onSelect={codes => navigate(`/compare?codes=${codes.join(',')}`)}
              />
            </div>
          ) : (
            <div className="text-center">
              <AlertTriangle className="h-12 w-12 text-destructive mx-auto mb-4" />
              <p className="text-muted-foreground">{error}</p>
              <Button variant="outline" className="mt-4" onClick={() => navigate(-1)}>
                返回
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (companies.length === 0) {
    return (
      <div className="h-full flex flex-col bg-background">
        <header className="border-b px-6 py-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-lg font-medium">跨公司对比</h1>
        </header>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">未找到公司数据</p>
            <Button variant="outline" className="mt-4" onClick={() => navigate(-1)}>
              返回
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background">
      {/* 头部 */}
      <header className="border-b px-6 py-4 flex items-center gap-4">
        <Button variant="ghost" size="icon" data-no-print onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-lg font-medium">跨公司对比</h1>
        <Badge variant="secondary">
          {companies.length} 家公司
        </Badge>
        <ExportSnapshotButton className="ml-auto gap-1.5" />
      </header>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-6">
        <ScrollArea className="h-full">
          <div className="space-y-6">
            {/* 公司概览 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  公司概览
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  {companies.map((company) => (
                    <div key={company.wind_code} className="p-4 rounded-lg border bg-card">
                      <div className="font-medium">{company.sec_name}</div>
                      <div className="text-xs text-muted-foreground mb-2">
                        {company.wind_code}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={cn('text-xs', getRiskLevelStyle(company.risk_level))}>
                          {riskLevelConfig[company.risk_level as RiskLevel]?.label}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {company.industry_l1}
                        </span>
                      </div>

                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded bg-muted/50 px-2 py-1">
                            <span className="text-muted-foreground">综合评分 </span>
                            <span className="font-medium">{company.partial ? '暂无数据' : company.overall_score.toFixed(3)}</span>
                          </div>
                          <div className="rounded bg-muted/50 px-2 py-1">
                            <span className="text-muted-foreground">触发规则 </span>
                            <span className="font-medium">{company.triggered_rules.length} 条</span>
                          </div>
                          <div className="rounded bg-muted/50 px-2 py-1">
                            <span className="text-muted-foreground">风险模式 </span>
                            <span className="font-medium">{company.pattern_matches?.length ?? 0} 个</span>
                          </div>
                          <div className="rounded bg-muted/50 px-2 py-1">
                            <span className="text-muted-foreground">数据覆盖 </span>
                            <span className="font-medium">{company.partial || company.coverage <= 0 ? '暂无数据' : `${(company.coverage * 100).toFixed(0)}%`}</span>
                          </div>
                        </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* 8/23 舆情信号：负面事件证据（舆情维度评分与风险等级保底的依据——
                如立案事件导致 signal_floor 保底高危，这里可见依据） */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Newspaper className="h-4 w-4" />
                  舆情信号
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  负面事件是舆情维度评分的依据；重大负面事件（如立案/处罚）会保底风险等级，即使财务规则触发少。
                </p>
              </CardHeader>
              <CardContent>
                {eventsLoading ? (
                  <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在加载舆情事件…
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {comparisonData.companies.map(company => {
                      const events = negativeEvents[company.wind_code] || [];
                      return (
                        <div key={company.wind_code} className="rounded-lg border border-border/60 p-3">
                          <p className="mb-2 text-xs font-medium text-muted-foreground">
                            {company.sec_name}
                          </p>
                          {events.length === 0 ? (
                            <p className="text-xs text-muted-foreground">
                              近 36 个月无负面舆情事件
                            </p>
                          ) : (
                            <div className="space-y-1.5">
                              {events.slice(0, 3).map((evt, i) => (
                                <div key={i} className="flex items-start gap-1.5 text-xs">
                                  <AlertTriangle className="h-3 w-3 text-red-500 shrink-0 mt-0.5" />
                                  <span className="min-w-0">
                                    <span className="text-[10px] text-muted-foreground">
                                      {evt.date}
                                    </span>
                                    <span className="block truncate" title={evt.title}>
                                      {evt.title}
                                    </span>
                                  </span>
                                </div>
                              ))}
                              {events.length > 3 && (
                                <p className="text-[10px] text-muted-foreground">
                                  另有 {events.length - 3} 条…
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

              {/* 对比结论：由后端返回的风险摘要/触发规则/模式匹配直接推导 */}
              {comparisonConclusions.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      对比结论
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {comparisonConclusions.map((text, index) => (
                      <div key={index} className="flex items-start gap-2 text-sm">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                        <p className="leading-relaxed text-muted-foreground">{text}</p>
                      </div>
                    ))}
                    <p className="text-[11px] text-muted-foreground/70">
                      结论仅由当前规则引擎评分、触发规则与模式匹配结果汇总，不构成投资建议。
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 8/23 会7 深化：跨公司 LLM 综合分析（SSE 流式渐进渲染） */}
              {(analysisLoading || analysisError || analysisSections.length > 0 || analysisSegments.length > 0) && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      综合分析
                      {analysisMethod === 'llm' && (
                        <Badge variant="outline" className="text-[10px] text-primary">
                          大模型生成
                        </Badge>
                      )}
                    </CardTitle>
                    {analysisCompanies.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {analysisCompanies
                          .map(c => `${c.sec_name}（${riskLevelConfig[c.risk_level as RiskLevel]?.label ?? c.risk_level}${c.overall_score != null ? ` ${c.overall_score.toFixed(3)}` : ' 暂无评分'}）`)
                          .join(' vs ')}
                      </p>
                    )}
                  </CardHeader>
                  <CardContent>
                    {analysisError && !analysisLoading && analysisSections.length === 0 ? (
                      <p className="text-sm text-destructive">{analysisError}</p>
                    ) : (
                      <div className="space-y-3">
                        {analysisLoading && (
                          <div className="flex items-center gap-2 py-1 text-sm text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            {analysisProgress && analysisProgress.total > 0
                              ? `正在获取风险数据（${analysisProgress.ready}/${analysisProgress.total} 家）…`
                              : '正在综合分析各家公司风险画像…'}
                          </div>
                        )}
                        {/* 8/23 可读性：LLM 对比分析为 Markdown 分节（SSE 分节到达即渲染） */}
                        {analysisSections.length > 0 && (
                          <MarkdownRenderer
                            content={analysisSections.join('\n\n')}
                            className="text-sm leading-6 text-foreground"
                          />
                        )}
                        {analysisSegments.map((seg, i) => {
                          const comp = analysisCompanies.find(c => c.wind_code === seg.company_code);
                          return (
                            <div key={`${seg.company_code}-${i}`} className="border-l-2 border-primary/40 pl-3">
                              <p className="text-xs font-medium text-muted-foreground">
                                {comp?.sec_name || seg.company_code}
                              </p>
                              <p className="mt-0.5 text-sm leading-6">{seg.detail}</p>
                            </div>
                          );
                        })}
                        {analysisWarnings.length > 0 && (
                          <p className="text-xs text-muted-foreground">{analysisWarnings.join('；')}</p>
                        )}
                        <p className="text-[11px] text-muted-foreground/70">
                          分析基于各家综合风险等级、评分与触发规则（大模型输出，数字与规则名已锁定），不构成投资建议。
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}


            {/* 标准财报科目：供财务人员横向核对原始数值、期间和差值
                （8/23 多期对比：每科目一卡，行=期次、列=公司） */}
            {(comparisonData?.financial_indicators?.length ?? 0) > 0 && (
              <Card className="mb-4">
                <CardHeader>
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" />
                    财报数据对比
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    母公司报表口径；金额统一换算为亿元，缺失值不按 0 处理；每个科目展示近 4 期走势（A 股累计口径：Q1 为单季、中报为半年、年报为全年）。
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {comparisonData.financial_indicators.map((row: IndicatorCompare) => {
                      // 期次行：优先 series（近 4 期），无 series 回退单期
                      const periods = row.series && row.series.length > 0
                        ? row.series
                        : row.period
                          ? [{ period: row.period, companies: row.companies }]
                          : [];
                      return (
                        <div key={row.indicator} className="overflow-hidden rounded-md border border-border/60">
                          <div className="flex items-center justify-between gap-2 bg-muted/40 px-3 py-2">
                            <span className="text-sm font-medium">{row.label} 对比</span>
                            {row.period && (
                              <span className="text-[11px] text-muted-foreground">
                                最新共同期 {formatReportPeriod(row.period)}
                              </span>
                            )}
                          </div>
                          <div className="overflow-x-auto">
                            <table className="w-full min-w-[560px] text-sm">
                              <thead className="text-left text-xs text-muted-foreground">
                                <tr className="bg-background">
                                  <th className="px-3 py-1.5 font-medium">期次</th>
                                  {comparisonData.companies.map(company => (
                                    <th key={company.wind_code} className="px-3 py-1.5 font-medium">
                                      {company.sec_name}
                                    </th>
                                  ))}
                                  {comparisonData.companies.length === 2 && (
                                    <th className="px-3 py-1.5 font-medium">差值（第一家-第二家）</th>
                                  )}
                                </tr>
                              </thead>
                              <tbody className="divide-y">
                                {periods.map(p => (
                                  <tr key={p.period}>
                                    <td className="whitespace-nowrap px-3 py-1.5 text-muted-foreground">
                                      {formatReportPeriod(p.period)}
                                    </td>
                                    {comparisonData.companies.map(company => {
                                      const item = p.companies?.find(
                                        value => value.wind_code === company.wind_code,
                                      );
                                      return (
                                        <td key={company.wind_code} className="px-3 py-1.5 align-middle">
                                          <div className="flex min-h-10 flex-col justify-center">
                                            <div>{formatFinancialValue(item?.value ?? null, item?.unit ?? '')}</div>
                                            <div className="mt-0.5 min-h-3 text-[10px] text-muted-foreground">
                                              {item?.status && item.status !== 'ok' ? '数据不足' : '\u00A0'}
                                            </div>
                                          </div>
                                        </td>
                                      );
                                    })}
                                    {comparisonData.companies.length === 2 && (
                                      <td className="whitespace-nowrap px-3 py-1.5 font-medium">
                                        {(() => {
                                          const a = p.companies?.[0]?.value;
                                          const b = p.companies?.[1]?.value;
                                          if (a == null || b == null) return '—';
                                          return formatFinancialValue(
                                            a - b,
                                            p.companies?.[0]?.unit ?? '',
                                          );
                                        })()}
                                      </td>
                                    )}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 指标对比 */}
            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  风险指标对比
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setShowAllIndicators(value => !value)}
                >
                  {showAllIndicators ? '仅看异常指标' : '展开全部指标'}
                </Button>
              </CardHeader>
              <CardContent>
                <p className="mb-3 text-xs text-muted-foreground">
                  {showAllIndicators ? '展示全部规则计算指标；同名指标已合并并标注关联规则。' : '默认仅展示至少一家触发预警的指标，便于横向定位异常。'}
                </p>
                {visibleIndicatorRows.length > 0 ? (
                  <div className="overflow-x-auto rounded-md border border-border/60">
                    <table className="w-full min-w-[760px] text-sm">
                      <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                        <tr>
                          <th className="w-48 px-3 py-2 font-medium">指标</th>
                          <th className="w-20 px-3 py-2 font-medium">关联规则</th>
                          {companies.map(company => (
                            <th key={company.wind_code} className="min-w-44 px-3 py-2 font-medium">{company.sec_name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/70">
                        {visibleIndicatorRows.map(row => (
                          <tr key={row.indicator} className="align-middle">
                            <td className="px-3 py-2.5 font-medium text-foreground">{row.label}</td>
                            <td className="px-3 py-2.5 text-xs text-muted-foreground">{row.relatedRules.join(' / ') || '—'}</td>
                            {companies.map(company => {
                              const cell = row.companies.find(item => item.wind_code === company.wind_code);
                              const insufficient = !cell || cell.status === 'insufficient_data' || cell.value == null;
                              const severity = insufficient ? 'unknown' : (cell.severity || 'green');
                              return (
                                <td key={company.wind_code} className="px-3 py-2.5">
                                  <div className="flex min-h-11 flex-col justify-center gap-1">
                                    <span className={cn('font-semibold', insufficient ? 'text-muted-foreground' : 'text-foreground')}>
                                      {formatRuleMetricValue(cell?.value ?? null, cell?.unit ?? '')}
                                    </span>
                                    {insufficient ? (
                                      <span className="text-[11px] text-muted-foreground">数据不足</span>
                                    ) : cell?.status === 'triggered' ? (
                                      <Badge className={cn('w-fit text-[10px]', getRiskLevelStyle(severity))}>
                                        {RISK_SEVERITY_LABELS[severity] ?? RISK_SEVERITY_LABELS.unknown}
                                      </Badge>
                                    ) : (
                                      <span className="text-[11px] text-muted-foreground">未触发</span>
                                    )}
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="py-5 text-center text-sm text-muted-foreground">当前没有可横向比较的触发指标。</p>
                )}
              </CardContent>
            </Card>

            {/* 触发规则对比 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  触发规则对比
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {companies.map((company) => {
                    // #17（8/9 清单）：优先消费后端 triggered_rule_details（含指标值/方向/单位/证据），
                    // 旧 triggered_rules（仅规则 ID）作降级兜底
                    const details = company.triggered_rule_details || [];
                    return (
                      <div key={company.wind_code} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{company.sec_name}</span>
                          <Badge variant="secondary" className="text-xs">
                            {details.length || company.triggered_rules.length} 条规则
                          </Badge>
                        </div>
                        {details.length > 0 ? (
                          <div className="space-y-2">
                            {details.slice(0, 3).map(detail => (
                              <div key={detail.rule_id} className="rounded-lg border border-border/60 p-3">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-xs font-medium">
                                    {detail.label || detail.rule_id}
                                  </span>
                                  <div className="flex items-center gap-2">
                                    {detail.as_of && (
                                      <span className="text-[10px] text-muted-foreground">
                                        {detail.as_of}
                                      </span>
                                    )}
                                    <Badge className={cn('text-[10px]', getRiskLevelStyle(detail.severity))}>
                                      {detail.severity === 'red' ? '高危'
                                        : detail.severity === 'orange' ? '中高危'
                                        : detail.severity === 'yellow' ? '中等'
                                        : detail.severity === 'blue' ? '低风险' : detail.severity}
                                    </Badge>
                                  </div>
                                </div>
                                {detail.metrics.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {detail.metrics.map(m => (
                                      <span
                                        key={m.key}
                                        className="rounded bg-muted/60 px-2 py-0.5 text-[11px] text-muted-foreground"
                                      >
                                        {m.label || m.key}: {m.value != null ? `${m.value}${unitLabelMap[m.unit] ?? (m.unit || '')}` : '-'}
                                        {m.risk_direction && m.risk_direction !== 'neutral'
                                          ? `（${m.risk_direction === 'higher_is_riskier' ? '偏高为风险' : '偏低为风险'}）`
                                          : ''}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {detail.explanation && (
                                  <p className="mt-1.5 text-[11px] text-muted-foreground line-clamp-2">
                                    {detail.explanation}
                                  </p>
                                )}
                                {detail.evidence_ids.length > 0 && (
                                  <p className="mt-1 text-[10px] text-muted-foreground">
                                    {detail.evidence_ids.length} 条证据可回查
                                  </p>
                                )}
                              </div>
                            ))}
                            {details.length > 3 && (
                              <div className="text-xs text-muted-foreground text-center">
                                +{details.length - 3} 条更多规则
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {company.triggered_rules.slice(0, 3).map((rule, index) => (
                              <div
                                key={index}
                                className="flex items-center justify-between text-xs p-2 rounded bg-muted/50"
                              >
                                <span>{rule}</span>
                              </div>
                            ))}
                            {company.triggered_rules.length > 3 && (
                              <div className="text-xs text-muted-foreground text-center">
                                +{company.triggered_rules.length - 3} 条更多规则
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

              {/* 触发规则矩阵：同一规则横向对比各公司状态/指标，替代逐公司堆叠 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    触发规则矩阵
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    同一规则横向对比：绿色=未触发，彩色=触发严重度，附指标值与触发原因
                  </p>
                </CardHeader>
                <CardContent>
                  {ruleMatrix.length > 0 ? (
                    <div className="space-y-3">
                      {ruleMatrix.map(row => (
                        <div key={row.ruleId} className="rounded-lg border border-border/60 p-3">
                          <div className="mb-2 flex items-center justify-between">
                            <span className="text-sm font-medium">{row.label}</span>
                            <span className="text-xs text-muted-foreground">{row.ruleId}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-3">
                            {row.cells.map(cell => (
                              <div
                                key={cell.code}
                                className={cn(
                                  'rounded-md border p-2.5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md',
                                  cell.triggered
                                    ? 'border-orange-500/30 bg-orange-500/5 hover:border-orange-500/60'
                                    : 'border-border/60 bg-muted/20 hover:border-primary/40',
                                )}
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="truncate text-xs font-medium">{cell.name}</span>
                                  <Badge className={cn('shrink-0 text-[10px]', getRiskLevelStyle(cell.triggered ? cell.severity : 'green'))}>
                                    {cell.triggered
                                      ? (cell.severity === 'red' ? '高危'
                                        : cell.severity === 'orange' ? '中高危'
                                        : cell.severity === 'yellow' ? '中等'
                                        : cell.severity === 'blue' ? '低风险'
                                        : cell.severity)
                                      : '未触发'}
                                  </Badge>
                                </div>
                                {cell.metrics.length > 0 && (
                                  <div className="mt-2 space-y-1">
                                    {cell.metrics.map((m, mi) => (
                                      <p key={mi} className="text-[11px] text-muted-foreground">
                                        {m.label}：<span className="font-medium text-foreground">{m.text}</span>
                                        {m.riskDirection && m.riskDirection !== 'neutral'
                                          ? `（${m.riskDirection === 'higher_is_riskier' ? '偏高为风险' : '偏低为风险'}）`
                                          : ''}
                                      </p>
                                    ))}
                                  </div>
                                )}
                                {cell.triggered && cell.asOf && (
                                  <p className="mt-1 text-[10px] text-muted-foreground">
                                    期次：{cell.asOf}
                                    {cell.evidenceCount > 0 ? ` · ${cell.evidenceCount} 条证据可回查` : ''}
                                  </p>
                                )}
                                {cell.triggered && cell.explanation && (
                                  <p className="mt-1.5 line-clamp-2 text-[11px] text-muted-foreground">
                                    {cell.explanation}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      两家公司均无触发规则
                    </p>
                  )}
                </CardContent>
              </Card>


            {/* 免责声明 */}
            <div className="text-center text-xs text-muted-foreground py-4">
              以上数据仅供参考，不构成投资建议
            </div>
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
