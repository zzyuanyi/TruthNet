// 织网鉴真 TruthNet - 企业画像页
// T3: 5 区块（概览/财务/股权/舆情/证据），使用新组件

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { cn } from '@/lib/utils';
const sourceTypeIcons: Record<string, string> = {
  announcement: '公告',
  news: '新闻',
  research_report: '研报',
  regulation: '监管',
};
function formatChainPct(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '比例缺失';
  if (value === 0) return '0%';
  if (value >= 0.01) return `${value.toFixed(2)}%`;
  if (value >= 0.0001) return `${value.toFixed(4)}%`;
  return `${value.toExponential(2)}%`;
}


import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ArrowLeft,
  AlertTriangle,
  TrendingUp,
  GitBranch,
  Newspaper,
  FileText,
  ChevronDown,
  ChevronRight,
  Shield,
  Loader2,
} from 'lucide-react';
import { truthnetAPI, type EvidenceLookupData } from '@/lib/api-client';
import { EquityGraph } from '@/components/truthnet/EquityGraph';
import { RelatedPartyTable } from '@/components/truthnet/RelatedPartyTable';
import { RuleCard, type RuleEvidenceSummary } from '@/components/truthnet/RuleCard';
import { SimilarCases } from '@/components/truthnet/SimilarCases';
import { RiskTimeline } from '@/components/truthnet/RiskTimeline';
import { EvidenceChain } from '@/components/truthnet/EvidenceChain';

import { Skeleton } from '@/components/ui/skeleton';
import type { FinanceResponseData, EventsResponseData, EquityResponseData, RiskResponseData, RiskLevel, FinanceRuleItem, TimelineEvent, EventCluster, RiskEvidence, EvidenceCategory, SimilarCasesResult, Company, DerivationChain, ImpactConclusion, DataQuality } from '@/types/truthnet';

// 证据按来源分组工具函数
function groupEvidenceBySource(evidences: RiskEvidence[]): EvidenceCategory[] {
  const sourceToCategory: Record<string, string> = {
    finance: 'finance',
    equity: 'equity',
    event: 'event',
    announcement: 'event',
    news: 'event',
    audit: 'audit',
    regulation: 'regulatory',
    regulatory: 'regulatory',
  };
  const categoryLabels: Record<string, string> = {
    finance: '财务证据',
    equity: '股权证据',
    event: '舆情证据',
    audit: '审计证据',
    regulatory: '监管证据',
  };

  const groups = new Map<string, RiskEvidence[]>();
  for (const e of evidences) {
    const cat = sourceToCategory[e.source_type] || e.source_type;
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat)!.push(e);
  }

  return Array.from(groups.entries()).map(([cat, items]) => ({
    category: cat,
    label: categoryLabels[cat] || cat,
    items,
  }));
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

// 锚点导航项
const navItems = [
  { id: 'overview', label: '概览', icon: AlertTriangle },
  { id: 'financial', label: '财务异常', icon: TrendingUp },
  { id: 'equity', label: '股权穿透', icon: GitBranch },
  { id: 'sentiment', label: '舆情时间线', icon: Newspaper },
  { id: 'evidence', label: '证据引用', icon: FileText },
];

export default function CompanyProfilePage() {
  // 契约修复：路由 param 是 :companyCode（App.tsx:39），旧代码读 code 恒为
  // undefined → loadData 永不执行、页面永远卡骨架屏。
  const { companyCode } = useParams<{ companyCode: string }>();
  const code = companyCode;
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<Company | null>(null);
  useDocumentTitle(profile?.sec_name || '企业画像');
  const [financialAnomalies, setFinancialAnomalies] = useState<FinanceRuleItem[]>([]);
  const [equityData, setEquityData] = useState<EquityResponseData | null>(null);
  const [sentimentEvents, setSentimentEvents] = useState<TimelineEvent[]>([]);
  const [eventClusters, setEventClusters] = useState<EventCluster[]>([]);
  const [riskData, setRiskData] = useState<RiskResponseData | null>(null);
  const [derivationChains, setDerivationChains] = useState<DerivationChain[]>([]);
  // 2026-08-16 口径整改：覆盖判定用真实数据存在性信号
  const [financeQuality, setFinanceQuality] = useState<DataQuality | null>(null);
  const [announcementsAvailable, setAnnouncementsAvailable] = useState<boolean | null>(null);

  const getRiskColor = (level: string) => {
    const colors: Record<string, string> = { red: '#ef4444', orange: '#f97316', yellow: '#eab308', blue: '#3b82f6', unknown: '#6b7280' };
    return colors[level] || '#6b7280';
  };
  const getRiskBadgeStyle = (level: string) => {
    const styles: Record<string, string> = {
      red: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      orange: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
      yellow: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      unknown: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    };
    return styles[level] || styles.unknown;
  };
  const [similarCasesByRule, setSimilarCasesByRule] = useState<
    Array<{ rule_id: string; rule_name: string; data: SimilarCasesResult }>
  >([]);
  // B2 舆情影响结论（后端 events.impact_conclusions，需 include_impacts=true）
  const [impactConclusions, setImpactConclusions] = useState<ImpactConclusion[]>([]);
  // A2（8/9 老师要求）：触发规则关联证据的摘要（evidenceId → 平铺摘要）
  const [ruleEvidenceSummary, setRuleEvidenceSummary] = useState<Record<string, RuleEvidenceSummary>>({});
  // A2：批量拉取触发规则的证据摘要用于平铺（去重 + 上限 30）。
  // 注意：本 effect 必须在 early return 之前注册（Rules of Hooks）；
  // 依赖稳定字符串键（避免数组身份变化导致无限重跑）。
  const triggeredEvidenceKey = financialAnomalies
    .filter(r => r.status === 'triggered')
    .flatMap(r => r.evidence_ids || [])
    .join(',');
  useEffect(() => {
    const ids = [...new Set(triggeredEvidenceKey.split(',').filter(Boolean))].slice(0, 30);
    if (ids.length === 0) return;
    let cancelled = false;
    void (async () => {
      const settled = await Promise.allSettled(ids.map(id => truthnetAPI.getEvidence(id)));
      if (cancelled) return;
      const map: Record<string, RuleEvidenceSummary> = {};
      settled.forEach((res, i) => {
        if (res.status === 'fulfilled') {
          const ev = (res.value.data?.evidence || {}) as Record<string, unknown>;
          map[ids[i]] = {
            evidenceId: ids[i],
            title: String(ev.source_title || ev.field_path || ids[i]),
            sourceType: String(ev.source_type || ''),
            period: String(ev.period || ''),
          };
        }
      });
      setRuleEvidenceSummary(map);
    })();
    return () => { cancelled = true; };
  }, [code, triggeredEvidenceKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const [activeSection, setActiveSection] = useState('overview');
  const [evidenceDialogOpen, setEvidenceDialogOpen] = useState(false);
  const [evidenceDialogTitle, setEvidenceDialogTitle] = useState('证据详情');
  const [evidenceDialogItems, setEvidenceDialogItems] = useState<Array<{
    evidenceId: string;
    data?: EvidenceLookupData;
    error?: string;
  }>>([]);
  const [evidenceDialogLoading, setEvidenceDialogLoading] = useState(false);
  // 报告生成（P1：画像页入口 → 创建任务 → 跳报告页，状态轮询由 ReportPage 接管）
  const [reportCreating, setReportCreating] = useState(false);

  // 生成报告：POST /reports（必填 company_code）→ 跳 /reports/{id}
  const handleGenerateReport = async () => {
    if (!profile || reportCreating) return;
    setReportCreating(true);
    try {
      const res = await truthnetAPI.createReport(profile.wind_code);
      navigate(`/reports/${res.data.report_id}`);
    } catch (err) {
      console.error('创建报告失败:', err);
      setReportCreating(false);
    }
  };

  const sectionRefs = {
    overview: useRef<HTMLDivElement>(null),
    conclusions: useRef<HTMLDivElement>(null),
    evidence: useRef<HTMLDivElement>(null),
    impact: useRef<HTMLDivElement>(null),
    financial: useRef<HTMLDivElement>(null),
    equity: useRef<HTMLDivElement>(null),
    sentiment: useRef<HTMLDivElement>(null),
  };

  useEffect(() => {
    if (code) {
      loadData();
    }
  }, [code]);

  const loadData = async () => {
    if (!code) return;
    setLoading(true);
    setError(null);
    try {
      const [profileRes, financeRes, equityRes, eventsRes, riskRes] = await Promise.all([
        truthnetAPI.getCompanyProfile(code),
        truthnetAPI.getFinance(code),
        truthnetAPI.getEquity(code),
        truthnetAPI.getEvents(code),
        truthnetAPI.getRisk(code),
      ]);
      setProfile(profileRes.data);
      const rules = financeRes.data?.rules || [];
      setFinancialAnomalies(rules);
      // 契约修复：相似案例在后端 FinanceRuleItem.similar_cases（逐规则），
      // 顶层 finance.similar_cases 不存在——按触发规则聚合展示。
      setSimilarCasesByRule(
        rules
          .filter(r => r.similar_cases && (r.similar_cases.status === 'ok' || r.similar_cases.status === 'error'))
          .map(r => ({
            rule_id: r.rule_id,
            rule_name: r.rule_name || r.rule_id,
            data: r.similar_cases as SimilarCasesResult,
          })),
      );
      setEquityData(equityRes.data);
      setSentimentEvents(eventsRes.data?.timeline || []);
      setEventClusters(eventsRes.data?.event_clusters || []);
      // B2 契约修复：消费后端 impact_conclusions（include_impacts=true 时返回）
      setImpactConclusions(eventsRes.data?.impact_conclusions || []);
      setRiskData(riskRes.data);
              const allChains = riskRes.data?.derivation_chains || [];
        setDerivationChains([
          ...allChains.filter(c => c.conclusion_type === 'risk_level'),
          ...allChains.filter(c => c.conclusion_type === 'pattern_match').slice(0, 3),
        ]);
      setFinanceQuality(financeRes.data?.data_quality || null);
      setAnnouncementsAvailable(eventsRes.data?.announcements_available ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleNavClick = (id: string) => {
    setActiveSection(id);
    const ref = sectionRefs[id as keyof typeof sectionRefs];
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const openEvidenceDetails = async (evidenceIds: string[], title: string) => {
    setEvidenceDialogTitle(title);
    setEvidenceDialogItems(evidenceIds.map(evidenceId => ({ evidenceId })));
    setEvidenceDialogLoading(true);
    setEvidenceDialogOpen(true);
    const results = await Promise.allSettled(
      evidenceIds.map(evidenceId => truthnetAPI.getEvidence(evidenceId)),
    );
    setEvidenceDialogItems(results.map((result, index) => ({
      evidenceId: evidenceIds[index],
      ...(result.status === 'fulfilled'
        ? { data: result.value.data }
        : { error: result.reason instanceof Error ? result.reason.message : '证据加载失败' }),
    })));
    setEvidenceDialogLoading(false);
  };

  const handleViewRuleEvidence = (ruleId: string) => {
    const rule = financialAnomalies.find(item => item.rule_id === ruleId);
    if (rule) {
      void openEvidenceDetails(rule.evidence_ids, `${rule.rule_name || rule.rule_id} · 证据详情`);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-background">
        <div className="w-40 border-r border-border p-4">
          <Skeleton className="h-full w-full" />
        </div>
        <div className="flex-1 overflow-auto p-6">
          <Skeleton className="mb-4 h-8 w-64" />
          <Skeleton className="mb-4 h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Card className="w-96">
          <CardContent className="pt-6 text-center">
            <p className="text-destructive">{error || '加载失败'}</p>
            <Button className="mt-4" onClick={() => navigate(-1)}>返回</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const riskConfig = riskLevelConfig[(riskData?.risk_level || 'unknown') as RiskLevel];
  // A3（8/9 老师要求）：触发的规则（风险提示集中展示 + 财务区筛选口径一致）
  const triggeredRules = financialAnomalies.filter(r => r.status === 'triggered');

  // 核心结论压缩：只展示 overall 风险链 + 风险模式链；
  // 逐规则推导链与财务异常区重复，不再在概览区完整展开。
  const overallConclusion = derivationChains.find(c => c.conclusion_type === 'risk_level');
  const patternConclusions = derivationChains
    .filter(c => c.conclusion_type === 'pattern_match')
    .slice(0, 3);
  const coreConclusionChains = [overallConclusion, ...patternConclusions].filter(
    (c): c is NonNullable<typeof c> => Boolean(c),
  );
  const patternMatches = riskData?.pattern_matches || [];
  const patternByConclusionId = new Map<string, (typeof patternMatches)[number]>(
    patternMatches.map(p => [`pattern:${p.pattern_id}`, p]),
  );

  // 2026-08-16 口径整改：覆盖判定改用"真实数据存在性"，废弃后端
  // coverage_ratio（其为模块执行成功占比，曾把"舆情无公告数据"算进 100%）。
  const financeHasData = (financeQuality?.periods_available ?? 0) > 0;
  const equityHasData = (equityData?.nodes?.length ?? 0) > 0;
  const eventsHasData =
    (announcementsAvailable ?? false) ||
    eventClusters.length > 0 ||
    sentimentEvents.length > 0;
  const benchmarksHasData = financialAnomalies.some(r =>
    (r.industry_metrics ?? []).some(m => (m.sample_count ?? 0) > 0),
  );
  const coverageGaps: string[] = [];
  if (!financeHasData) {
    coverageGaps.push('财务无报表数据');
  } else if (
    financeQuality &&
    financeQuality.periods_available < financeQuality.periods_requested
  ) {
    coverageGaps.push(`财务 ${financeQuality.periods_available}/${financeQuality.periods_requested} 期`);
  }
  if (!equityHasData) coverageGaps.push('股权无数据');
  if (!eventsHasData) coverageGaps.push('舆情无公告数据');
  if (!benchmarksHasData) coverageGaps.push('行业基准无样本');
  const coverageModulesText = riskData
    ? `${[financeHasData, equityHasData, eventsHasData, benchmarksHasData].filter(Boolean).length}/4 有数据`
    : '-';
  const coverageStatusText = !riskData
    ? '-'
    : coverageGaps.length === 0
      ? '完整'
      : '部分覆盖';
  const coverageGapText =
    coverageGaps.length > 0 ? `数据说明：${coverageGaps.join(' · ')}` : '';

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 bg-background">
      {/* 左侧锚点导航 */}
      <div className="w-40 border-r border-border bg-card">
        <div className="p-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')} className="mb-4 w-full justify-start">
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                  activeSection === item.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* 右侧内容区 */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl p-6">
          {/* 概览区块 */}
          <div ref={sectionRefs.overview} className="mb-8">
            <div className="mb-4 flex items-center gap-4">
              <h1 className="text-2xl font-bold text-foreground">{profile.sec_name}</h1>
              <Badge className={riskConfig.color}>{riskConfig.label}</Badge>
              <span className="text-sm text-muted-foreground">{profile.wind_code}</span>
              <Button
                variant="outline"
                size="sm"
                className="ml-auto gap-1.5"
                onClick={handleGenerateReport}
                disabled={reportCreating}
              >
                {reportCreating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FileText className="h-3.5 w-3.5" />
                )}
                生成报告
              </Button>
            </div>
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-muted/30 to-muted/10 px-6 py-3 border-b border-border/50">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  <span className="text-sm font-semibold text-foreground">风险概览</span>
                </div>
              </div>
              <CardContent className="pt-5 space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">综合风险等级</p>
                    <p className="text-2xl font-bold">{riskConfig.label}</p>
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">触发规则数</p>
                    <p className="text-2xl font-bold">{triggeredRules.length}</p>
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">舆情事件数</p>
                    <p className="text-2xl font-bold">{sentimentEvents.length}</p>
                  </div>
                </div>

                {/* A3（8/9 老师要求）：数据截止日 / 数据模块 / 覆盖状态
                    （2026-08-16 口径整改：截止日由后端从库内真实期次推导；
                    覆盖率不再显示百分比，改为真实数据模块数 x/4） */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="rounded-md border border-border/60 p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">数据截止日</p>
                    <p className="text-sm font-semibold">{riskData?.as_of || '-'}</p>
                  </div>
                  <div className="rounded-md border border-border/60 p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">数据模块</p>
                    <p className="text-sm font-semibold">{coverageModulesText}</p>
                  </div>
                  <div className="rounded-md border border-border/60 p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">覆盖状态</p>
                    <p className="text-sm font-semibold">{coverageStatusText}</p>
                  </div>
                </div>
                {coverageGapText && (
                  <p className="rounded-md border border-dashed border-border/60 p-2 text-xs text-muted-foreground">
                    {coverageGapText}
                  </p>
                )}

                {/* A3：top 触发规则（点击跳转财务异常区） */}
                {triggeredRules.length > 0 && (
                  <div className="rounded-md border border-border/60 p-3">
                    <p className="text-xs text-muted-foreground mb-2">主要风险信号（点击查看详情）</p>
                    <div className="flex flex-wrap gap-2">
                      {triggeredRules.slice(0, 5).map(r => (
                        <button
                          key={r.rule_id}
                          onClick={() => handleNavClick('financial')}
                          className={cn(
                            'flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
                            'border-border/60 bg-background hover:border-primary/50 hover:bg-muted/50',
                          )}
                        >
                          <span className="text-foreground">{r.rule_name || r.rule_id}</span>
                          <span className={`rounded-full px-1.5 py-0.5 ${getRiskBadgeStyle(r.severity)}`}>
                            {r.severity}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* A3：risk warnings 集中展示 */}
                {(riskData?.warnings?.length ?? 0) > 0 && (
                  <div className="rounded-md border border-yellow-500/40 bg-yellow-500/5 p-3 space-y-1">
                    {riskData!.warnings.map((w, wi) => (
                      <p key={wi} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                        <AlertTriangle className="h-3.5 w-3.5 text-yellow-600 shrink-0 mt-0.5" />
                        {w}
                      </p>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          
          {/* 核心结论区块 (Phase E P0-1) */}
          <div ref={sectionRefs.conclusions} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <FileText className="h-5 w-5" />
              核心结论
            </h2>
            {derivationChains.length > 0 ? (
              <div className="space-y-4">
                {derivationChains.map((chain, ci) => (
                  <Card key={ci} className="border-l-4" style={{ borderLeftColor: getRiskColor(chain.risk_level) }}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getRiskBadgeStyle(chain.risk_level)}`}>
                          {chain.risk_level}
                        </span>
                        <span className="text-sm font-medium">{chain.conclusion}</span>
                      </div>
                    </CardHeader>
                    <CardContent className="pb-3">
                      {(chain.conclusion_type === 'risk_level' ? chain.signals.slice(0, 3) : []).map((signal, si) => (
                        <div key={si} className="mb-3 rounded-lg border bg-muted/30 p-3">
                          <div className="mb-1 flex items-center justify-between">
                            <span className="text-sm font-medium">{signal.label}</span>
                            <span className="text-xs text-muted-foreground">{signal.severity}</span>
                          </div>
                          <p className="mb-2 text-sm text-muted-foreground">{signal.explanation}</p>
                          {signal.industry_percentile != null && (
                            <p className="mb-1 text-xs text-muted-foreground">
                              行业分位: {signal.industry_percentile}%
                            </p>
                          )}
                          {false && (
                            <div className="mt-2 space-y-1">
                              {signal.data_refs.map((ref, ri) => (
                                <div key={ri} className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <span className="rounded bg-muted px-1.5 py-0.5">{ref.period}</span>
                                  <span>{ref.field_path}: {ref.value ?? '-'}{ref.unit ?? ''}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                        {chain.conclusion_type === 'pattern_match' && (() => {
                          const pattern = patternByConclusionId.get(chain.conclusion_id);
                          if (!pattern) return null;
                          return (
                            <div className="rounded-lg border border-border/60 bg-muted/30 p-3 text-xs space-y-1.5">
                              <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
                                <span>置信度：{pattern.confidence || '-'}</span>
                                {pattern.phase && <span>阶段：{pattern.phase}</span>}
                                {pattern.triggered_rules.length > 0 && (
                                  <span>关联规则：{pattern.triggered_rules.join('、')}</span>
                                )}
                              </div>
                              {pattern.reasoning && (
                                <p className="leading-5">匹配理由：{pattern.reasoning}</p>
                              )}
                              {pattern.alternative_explanation && (
                                <p className="leading-5">替代解释：{pattern.alternative_explanation}</p>
                              )}
                              {pattern.regulatory_hint && (
                                <p className="leading-5 text-amber-700 dark:text-amber-400">
                                  监管提示：{pattern.regulatory_hint}
                                </p>
                              )}
                            </div>
                          );
                        })()}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="border-dashed">
                <CardContent className="py-8 text-center text-muted-foreground">
                  <p>暂无结论数据</p>
                  <p className="text-xs mt-1">选择公司后将自动加载风险分析结论</p>
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 财务规则区块 - 使用 RuleCard 组件 */}
          <div ref={sectionRefs.financial} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <TrendingUp className="h-5 w-5" />
              财务异常
            </h2>
            {financialAnomalies.length > 0 ? (
              <div className="space-y-3">
                {financialAnomalies.map((anomaly) => (
                    <RuleCard
                      key={anomaly.rule_id}
                      rule={anomaly}
                      onViewEvidence={handleViewRuleEvidence}
                      // A2：触发规则证据直接平铺在信号下方（弹窗仅作次级入口）
                      evidenceSummaries={
                        anomaly.status === 'triggered'
                          ? (anomaly.evidence_ids || [])
                              .map(id => ruleEvidenceSummary[id])
                              .filter((x): x is RuleEvidenceSummary => Boolean(x))
                          : undefined
                      }
                    />
                  ))}
              </div>
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无财务异常数据
                </CardContent>
              </Card>
            )}
          </div>

          {/* 相似案例（契约修复：逐规则渲染 rules[].similar_cases） */}
          {similarCasesByRule.length > 0 && (
            <div className="mt-6 space-y-4">
              {similarCasesByRule.map(r => (
                <SimilarCases key={r.rule_id} data={r.data} ruleName={r.rule_name} />
              ))}
            </div>
          )}

          <Separator className="my-6" />

          {/* 股权穿透区块：移除缺列关联方表，保留多跳分层穿透图 */}
          <div ref={sectionRefs.equity} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <GitBranch className="h-5 w-5" />
              股权穿透图
            </h2>
            {equityData ? (
              <Card>
                <CardContent className="p-4">
                  <RelatedPartyTable equityData={equityData} />

                    {/* 间接持股链路：消费后端 equity_chains，补齐多跳最终持股视图 */}
                    {(equityData.equity_chains?.length ?? 0) > 0 && (
                      <div className="mb-4 rounded-lg border border-border/60 bg-muted/20 p-3">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground">间接持股链路（多跳）</span>
                          <span className="text-[10px] text-muted-foreground">表格仅直接持股；最终持股=各跳比例连乘，多跳时会稀释到极小值</span>
                        </div>
                        <div className="space-y-1.5">
                          {(equityData.equity_chains as Array<Record<string, unknown>>).slice(0, 6).map((chain, index) => {
                            const names = Array.isArray(chain.path_names)
                              ? chain.path_names.map(String).filter(Boolean)
                              : [];
                            const pct = typeof chain.final_control_pct === 'number'
                              ? chain.final_control_pct
                              : null;
                              const nodeIds = Array.isArray(chain.node_ids)
                                ? chain.node_ids.map(String)
                                : [];
                              const edgeIds = Array.isArray(chain.edge_ids)
                                ? chain.edge_ids.map(String)
                                : [];
                              const firstEdge = equityData.edges.find(edge => {
                                if (edgeIds.length > 0 && edge.relationship_id && edgeIds[0] === edge.relationship_id) {
                                  return true;
                                }
                                return nodeIds.length >= 2
                                  && edge.source === nodeIds[0]
                                  && edge.target === nodeIds[1];
                              });
                              const firstPct = firstEdge?.ownership_pct ?? null;
                            const pathType = String(chain.path_type || 'ownership');
                            const riskLevel = String(chain.risk_level || 'green');
                            return (
                              <div key={String(chain.chain_id || index)} className="rounded-md border border-border/50 bg-background px-2.5 py-2">
                                <div className="flex items-start justify-between gap-3">
                                  <p className="min-w-0 flex-1 text-xs leading-5 text-foreground">
                                    {names.length > 0 ? names.join(' → ') : '未命名链路'}
                                  </p>
                                  <span className="shrink-0 text-xs font-semibold text-foreground">
                                    {pct != null
                                        ? `${pathType === 'control' ? '最终控制' : '最终持股'} ${formatChainPct(pct)}${firstPct != null ? ` · 首层 ${formatChainPct(firstPct)}` : ''}`
                                        : '比例缺失'}
                                  </span>
                                </div>
                                <div className="mt-1 flex items-center gap-2">
                                  <span className={`rounded px-1.5 py-0.5 text-[10px] ${getRiskBadgeStyle(riskLevel)}`}>
                                    {riskLevel === 'red' ? '高危'
                                      : riskLevel === 'orange' ? '中高危'
                                      : riskLevel === 'yellow' ? '中等'
                                      : riskLevel === 'blue' ? '低风险' : '正常'}
                                  </span>
                                  <span className="text-[10px] text-muted-foreground">
                                    {Array.isArray(chain.risk_reasons) && chain.risk_reasons.length > 0
                                      ? String(chain.risk_reasons[0]).slice(0, 60)
                                      : '未发现附加风险说明'}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">{equityData.nodes.length} 个节点</Badge>
                      <Badge variant="outline">{equityData.edges.length} 条边</Badge>
                      <Badge variant="outline">
                        {equityData.paths.length > 0 ? `${equityData.paths.length} 条穿透路径` : '暂无路径'}
                      </Badge>
                      <Badge variant="outline">
                        最深 {equityData.max_observed_hops ?? Math.max(0, ...equityData.paths.map(p => p.depth || 0))} 跳
                      </Badge>
                      <span>从左到右为向上穿透层级，可滚轮缩放、按住拖拽</span>
                    </div>
                  <div className="mt-4">
                    <EquityGraph
                      nodes={equityData.nodes}
                      edges={equityData.edges}
                      targetId={equityData.target?.entity_id || ''}
                    />
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无股权穿透数据
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 舆情时间线区块 - 使用 RiskTimeline 组件 */}
          <div ref={sectionRefs.sentiment} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <Newspaper className="h-5 w-5" />
              舆情时间线
            </h2>
            {sentimentEvents.length > 0 ? (
              <RiskTimeline
                events={sentimentEvents}
                  companyCode={code}
                clusters={eventClusters}
                onEventClick={() => {
                  const evidenceSection = sectionRefs.evidence;
                  evidenceSection.current?.scrollIntoView({ behavior: 'smooth' });
                }}
              />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无舆情事件数据
                </CardContent>
              </Card>
            )}
          </div>

          <Separator className="my-6" />

          {/* 证据引用区块 - 使用 EvidenceChain 组件 */}
          <div ref={sectionRefs.evidence} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <FileText className="h-5 w-5" />
              证据引用
            </h2>
            {riskData && riskData.evidence.length > 0 ? (
              <EvidenceChain
                categories={groupEvidenceBySource(riskData.evidence)}
                onViewSource={evidence => {
                  void openEvidenceDetails([evidence.evidence_id], `${evidence.evidence_id} · 来源详情`);
                }}
              />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  暂无证据数据
                </CardContent>
              </Card>
            )}
          </div>

            <Separator className="my-6" />

            {/* 影响与建议：从 Dialog 外移回主内容列，并压缩为摘要 + 可展开因果链 */}
            <div ref={sectionRefs.impact} className="mb-8">
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
                <TrendingUp className="h-5 w-5" />
                影响与建议
              </h2>
              {impactConclusions.length > 0 ? (
                <div className="space-y-2">
                  {impactConclusions.map((ic, i) => (
                    <Card key={i} className="bg-muted/20">
                      <CardContent className="p-3">
                        <div className="flex items-start gap-2">
                          <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${getRiskBadgeStyle({ high: 'red', medium: 'yellow', low: 'blue' }[ic.severity] || 'unknown')}`}>
                            {ic.display_tag}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium leading-snug">{ic.conclusion}</p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {ic.impact_type} · {ic.direction} · {ic.evidence_ids.length} 条证据
                            </p>
                          </div>
                        </div>
                        {ic.causality_chain.length > 0 && (
                          <Collapsible className="mt-2">
                            <CollapsibleTrigger className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                              <ChevronRight className="h-3.5 w-3.5" />
                              查看因果链（{ic.causality_chain.length} 步）
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="mt-2 flex flex-wrap items-start gap-1.5">
                                {ic.causality_chain.map((step, si) => (
                                  <span key={si} className="flex items-center gap-1.5">
                                    {si > 0 && <span className="text-muted-foreground text-xs">→</span>}
                                    <span className={`rounded-md border px-2 py-1 text-xs text-foreground ${
                                      step.statement_type === 'observed'
                                        ? 'border-green-500/40 bg-green-500/5'
                                        : step.statement_type === 'inference'
                                          ? 'border-yellow-500/40 bg-yellow-500/5'
                                          : 'border-gray-500/40 bg-muted/30'
                                    }`}>
                                      {step.text}
                                    </span>
                                  </span>
                                ))}
                              </div>
                            </CollapsibleContent>
                          </Collapsible>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <Card className="border-dashed">
                  <CardContent className="py-6 text-center text-sm text-muted-foreground">
                    暂无影响建议（舆情影响分析完成后自动生成）
                  </CardContent>
                </Card>
              )}
            </div>
        </div>
      </div>
      <Dialog open={evidenceDialogOpen} onOpenChange={setEvidenceDialogOpen}>
        <DialogContent className="max-h-[80vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{evidenceDialogTitle}</DialogTitle>
            <DialogDescription>
              证据 ID、报表记录和关联声明均来自后端 provenance 查询。
            </DialogDescription>
          </DialogHeader>
          {evidenceDialogLoading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">正在加载证据详情…</div>
          ) : (
            <div className="space-y-4">
              {evidenceDialogItems.map(item => {
                const evidence = item.data?.evidence || {};
                const source = item.data?.source || {};
                const record = source.record || {};
                return (
                  <div key={item.evidenceId} className="rounded-md border border-border p-4">
                    <code className="text-xs text-muted-foreground">{item.evidenceId}</code>
                    {item.error ? (
                      <p className="mt-2 text-sm text-destructive">{item.error}</p>
                    ) : (
                      <>
                        <dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
                          <div><dt className="text-xs text-muted-foreground">来源标题</dt><dd>{String(evidence.source_title || '-')}</dd></div>
                          <div><dt className="text-xs text-muted-foreground">来源类型</dt><dd>{String(evidence.source_type || '-')}</dd></div>
                          <div><dt className="text-xs text-muted-foreground">记录</dt><dd>{String(evidence.source_record_id || '-')}</dd></div>
                          <div><dt className="text-xs text-muted-foreground">报表期间</dt><dd>{String(evidence.period || '-')}</dd></div>
                          <div><dt className="text-xs text-muted-foreground">字段</dt><dd>{String(evidence.field_path || '-')}</dd></div>
                          <div><dt className="text-xs text-muted-foreground">解析状态</dt><dd>{source.resolved ? '已解析' : '未解析'}</dd></div>
                        </dl>
                        {Object.keys(record).length > 0 && (
                          <details className="mt-3">
                            <summary className="cursor-pointer text-xs text-muted-foreground">查看来源记录</summary>
                            <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(record, null, 2)}</pre>
                          </details>
                        )}
                        {item.data?.claims?.length ? (
                          <div className="mt-3 border-t border-border pt-3">
                            <div className="text-xs text-muted-foreground">关联声明</div>
                            {item.data.claims.map((claim, index) => (
                              <p key={String(claim.claim_id || index)} className="mt-1 text-sm">{String(claim.text || claim.claim_id || '-')}</p>
                            ))}
                          </div>
                        ) : null}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
          {false && (
          /* 影响建议区块 (Phase E P0-1) — 旧版完整卡（新摘要版已在主列 647-706 行，此块临时禁用待删除） */
          <div ref={sectionRefs.impact} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <TrendingUp className="h-5 w-5" />
              影响与建议
            </h2>
            {/* B2 契约修复：消费后端 events.impact_conclusions（include_impacts=true） */}
            {impactConclusions.length > 0 && (
              <div className="space-y-3">
                {impactConclusions.map((ic, i) => (
                  <Card key={i} className="bg-muted/20">
                    <CardHeader className="pb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getRiskBadgeStyle({ high: 'red', medium: 'yellow', low: 'blue' }[ic.severity] || 'unknown')}`}>
                          {ic.display_tag}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {ic.impact_type} · {ic.direction}
                        </span>
                      </div>
                      <p className="text-sm font-medium pt-1">{ic.conclusion}</p>
                    </CardHeader>
                    {(ic.causality_chain.length > 0 || ic.evidence_ids.length > 0) && (
                      <CardContent className="pb-3">
                        {/* B2：事理图谱式因果传导（A→B→C，按陈述性质着色） */}
                        {ic.causality_chain.length > 0 && (
                          <>
                            <div className="flex flex-wrap items-start gap-1.5">
                              {ic.causality_chain.map((step, si) => {
                                const stBorder =
                                  step.statement_type === 'observed'
                                    ? 'border-green-500/40 bg-green-500/5'
                                    : step.statement_type === 'inference'
                                      ? 'border-yellow-500/40 bg-yellow-500/5'
                                      : 'border-gray-500/40 bg-muted/30';
                                return (
                                  <span key={si} className="flex items-center gap-1.5">
                                    {si > 0 && <span className="text-muted-foreground text-xs">→</span>}
                                    <span className={`rounded-md border px-2 py-1 text-xs text-foreground ${stBorder}`}>
                                      {step.text}
                                      <span className="ml-1 text-[10px] text-muted-foreground">
                                        ({step.statement_type})
                                      </span>
                                    </span>
                                  </span>
                                );
                              })}
                            </div>
                            <p className="mt-1.5 text-[10px] text-muted-foreground">
                              绿框=已发生事实 · 黄框=推断 · 灰框=预测
                            </p>
                          </>
                        )}
                        {ic.evidence_ids.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {ic.evidence_ids.slice(0, 5).map((eid, ei) => (
                              <span key={ei} className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                {eid}
                              </span>
                            ))}
                            {ic.evidence_ids.length > 5 && (
                              <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                +{ic.evidence_ids.length - 5} 条
                              </span>
                            )}
                          </div>
                        )}
                      </CardContent>
                    )}
                  </Card>
                ))}
              </div>
            )}
            {derivationChains.length > 0 ? (
              <div className="space-y-4">
                {derivationChains.map((chain, ci) => (
                  <Card key={ci} className="bg-muted/20">
                    <CardHeader className="pb-2">
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getRiskBadgeStyle(chain.risk_level)}`}>
                          影响等级: {chain.risk_level}
                        </span>
                        <span className="text-sm font-medium">{chain.conclusion}</span>
                      </div>
                    </CardHeader>
                    <CardContent className="pb-3">
                      <p className="text-sm text-muted-foreground">
                        共触发 {chain.signals.length} 个异常信号，涉及 {chain.evidence_ids.length} 条证据。建议关注相关财务指标变动，结合行业分位数据综合判断。
                      </p>
                      {chain.evidence_ids.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {chain.evidence_ids.slice(0, 5).map((eid, ei) => (
                            <span key={ei} className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                              {eid}
                            </span>
                          ))}
                          {chain.evidence_ids.length > 5 && (
                            <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                              +{chain.evidence_ids.length - 5} 条
                            </span>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : impactConclusions.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="py-8 text-center text-muted-foreground">
                  <p>暂无影响建议</p>
                  <p className="text-xs mt-1">风险分析完成后将自动生成影响与建议</p>
                </CardContent>
              </Card>
            ) : null}
          </div>

          )}
      </Dialog>
    </div>
  );
}
