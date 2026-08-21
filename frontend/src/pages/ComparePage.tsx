// 织网鉴真 TruthNet - 跨公司对比页
// Phase 3: 多公司对比分析

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import {
  ArrowLeft,
  AlertTriangle,
  BarChart3,
  Building2,
  Search,
  X,
} from 'lucide-react';
import { truthnetAPI } from '@/lib/api-client';
import type {
  BenchmarksResponseData,
  CompanyRiskSummary,
  ComparisonsResponseData,
  RiskLevel,
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
  quarters: '个季度',
  ratio: '比率',
  yuan: '元',
  times: '倍',
};

// 后端对比服务已有完整财务规则分析缓存；请求 7 条规则可一次性展示，
// 不增加后端计算量（evaluate_all_rules 本就全量执行，仅多透出 current 值）。
const DEFAULT_COMPARISON_RULES = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'];

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

  const riskText = ranked
    .map((c, i) => `${i + 1}. ${c.sec_name}：${riskLevelConfig[c.risk_level as RiskLevel]?.label ?? c.risk_level}（${c.partial ? '暂无评分' : `${c.overall_score.toFixed(3)} 分`}）`)
    .join('；');
  conclusions.push(`风险排序：${riskText}`);

  const commonRules = new Set<string>();
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

  const patterns = companies
    .filter(c => (c.pattern_matches?.length ?? 0) > 0)
    .map(c => `${c.sec_name}：${c.pattern_matches!.join('、')}`);
  if (patterns.length > 0) {
    conclusions.push(`风险模式：${patterns.join('；')}。`);
  }

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

  useEffect(() => {
    const loadCompanies = async () => {
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
      }
    };

    loadCompanies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const ruleMatrix = useMemo(() => buildRuleMatrix(companies), [companies]);
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
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-lg font-medium">跨公司对比</h1>
        <Badge variant="secondary">
          {companies.length} 家公司
        </Badge>
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


            {/* 指标对比 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  指标对比
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {(comparisonData?.indicators && comparisonData.indicators.length > 0 ? comparisonData.indicators : comparisonData?.companies?.[0] ? [
                    { indicator: 'risk_level', label: '风险等级', companies: comparisonData.companies.map(c => ({ wind_code: c.wind_code, sec_name: c.sec_name, value: 0, unit: '', severity: c.risk_level, status: '' })) },
                    { indicator: 'overall_score', label: '综合评分', companies: comparisonData.companies.map(c => ({ wind_code: c.wind_code, sec_name: c.sec_name, value: c.overall_score, unit: '分', severity: '', status: '' })) },
                    { indicator: 'triggered_rules', label: '触发规则数', companies: comparisonData.companies.map(c => ({ wind_code: c.wind_code, sec_name: c.sec_name, value: c.triggered_rules.length, unit: '条', severity: '', status: '' })) },
                    { indicator: 'coverage', label: '数据覆盖率', companies: comparisonData.companies.map(c => ({ wind_code: c.wind_code, sec_name: c.sec_name, value: c.coverage, unit: '%', severity: '', status: '' })) },
                    { indicator: 'pattern_matches', label: '模式匹配', companies: comparisonData.companies.map(c => ({ wind_code: c.wind_code, sec_name: c.sec_name, value: c.pattern_matches?.length ?? 0, unit: '个', severity: '', status: '' })) },
                  ] : []).map((indicator) => {
                    return (
                      <div key={indicator.indicator} className="space-y-2">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <BarChart3 className="h-4 w-4 text-muted-foreground" />
                          {indicator.label}
                        </div>
                        <div className="grid grid-cols-3 gap-4">
                          {indicator.companies.map((ci) => {
                            const isRisk = indicator.indicator === 'risk_level';
                            const displayValue = ci.value == null
                              ? '暂无数据'
                              : indicator.indicator === 'coverage'
                                ? `${(ci.value * 100).toFixed(0)}%`
                                : `${ci.value}${ci.unit || ''}`;
                            return (
                              <div
                                key={ci.wind_code}
                                className="p-3 rounded-lg border bg-card text-center"
                              >
                                {isRisk ? (
                                  <Badge className={cn('text-xs', getRiskLevelStyle(ci.severity || String(ci.value ?? '')))}>
                                    {riskLevelConfig[ci.severity as RiskLevel]?.label || ci.severity || String(ci.value ?? '-')}
                                  </Badge>
                                ) : (
                                  <span className="text-lg font-medium">
                                    {displayValue}
                                  </span>
                                )}

                                  {!isRisk && ci.status && ci.status !== 'not_applicable' && (
                                    <p className="mt-1 text-[10px] text-muted-foreground">
                                      {ci.status === 'triggered'
                                        ? '规则已触发'
                                        : ci.status === 'insufficient_data'
                                          ? '数据不足'
                                          : ci.status}
                                    </p>
                                  )}
                                  {!isRisk && ci.severity && ['red', 'orange', 'yellow', 'blue', 'green', 'unknown'].includes(ci.severity) && (
                                    <Badge className={cn('mt-1 text-[10px]', getRiskLevelStyle(ci.severity))}>
                                      {riskLevelConfig[ci.severity as RiskLevel]?.label}
                                    </Badge>
                                  )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
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
