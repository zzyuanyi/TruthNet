// 织网鉴真 TruthNet - 企业画像页
// T3: 5 区块（概览/财务/股权/舆情/证据），使用新组件

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
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
} from 'lucide-react';
import { truthnetAPI, type EvidenceLookupData } from '@/lib/api-client';
import { EquityGraph } from '@/components/truthnet/EquityGraph';
import { RuleCard } from '@/components/truthnet/RuleCard';
import { SimilarCases } from '@/components/truthnet/SimilarCases';
import { RiskTimeline } from '@/components/truthnet/RiskTimeline';
import { EvidenceChain } from '@/components/truthnet/EvidenceChain';
import { RelatedPartyTable } from '@/components/truthnet/RelatedPartyTable';
import { Skeleton } from '@/components/ui/skeleton';
import type { FinanceResponseData, EventsResponseData, EquityResponseData, RiskResponseData, RiskLevel, FinanceRuleItem, TimelineEvent, EventCluster, RiskEvidence, EvidenceCategory, SimilarCasesResult, Company, DerivationChain } from '@/types/truthnet';

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
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<Company | null>(null);
  const [financialAnomalies, setFinancialAnomalies] = useState<FinanceRuleItem[]>([]);
  const [equityData, setEquityData] = useState<EquityResponseData | null>(null);
  const [sentimentEvents, setSentimentEvents] = useState<TimelineEvent[]>([]);
  const [eventClusters, setEventClusters] = useState<EventCluster[]>([]);
  const [riskData, setRiskData] = useState<RiskResponseData | null>(null);
  const [derivationChains, setDerivationChains] = useState<DerivationChain[]>([]);

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
  const [similarCases, setSimilarCases] = useState<SimilarCasesResult | null>(null);
  const [activeSection, setActiveSection] = useState('overview');
  const [evidenceDialogOpen, setEvidenceDialogOpen] = useState(false);
  const [evidenceDialogTitle, setEvidenceDialogTitle] = useState('证据详情');
  const [evidenceDialogItems, setEvidenceDialogItems] = useState<Array<{
    evidenceId: string;
    data?: EvidenceLookupData;
    error?: string;
  }>>([]);
  const [evidenceDialogLoading, setEvidenceDialogLoading] = useState(false);

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
      setFinancialAnomalies(financeRes.data?.rules || []);
      setSimilarCases(financeRes.data?.similar_cases || null);
      setEquityData(equityRes.data);
      setSentimentEvents(eventsRes.data?.timeline || []);
      setEventClusters(eventsRes.data?.event_clusters || []);
       setRiskData(riskRes.data);
      setDerivationChains(riskRes.data?.derivation_chains || []);
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
            </div>
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-muted/30 to-muted/10 px-6 py-3 border-b border-border/50">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  <span className="text-sm font-semibold text-foreground">风险概览</span>
                </div>
              </div>
              <CardContent className="pt-5">
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">综合风险等级</p>
                    <p className="text-2xl font-bold">{riskConfig.label}</p>
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">触发规则数</p>
                    <p className="text-2xl font-bold">{financialAnomalies.filter(r => r.status === "triggered").length}</p>
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">舆情事件数</p>
                    <p className="text-2xl font-bold">{sentimentEvents.length}</p>
                  </div>
                </div>
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
                      {chain.signals.map((signal, si) => (
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
                          {signal.data_refs.length > 0 && (
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

          {/* 相似案例 */}
          {similarCases && similarCases.cases.length > 0 && (
            <div className="mt-6">
              <SimilarCases data={similarCases} />
            </div>
          )}

          <Separator className="my-6" />

          {/* 股权穿透区块 - 使用 RelatedPartyTable 组件 */}
          <div ref={sectionRefs.equity} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <GitBranch className="h-5 w-5" />
              股权穿透图
            </h2>
            {equityData ? (
              <Card>
                <CardContent className="p-4">
                  <RelatedPartyTable equityData={equityData} />
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

          {/* 影响建议区块 (Phase E P0-1) */}
          <div ref={sectionRefs.impact} className="mb-8">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-foreground">
              <TrendingUp className="h-5 w-5" />
              影响与建议
            </h2>
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
            ) : (
              <Card className="border-dashed">
                <CardContent className="py-8 text-center text-muted-foreground">
                  <p>暂无影响建议</p>
                  <p className="text-xs mt-1">风险分析完成后将自动生成影响与建议</p>
                </CardContent>
              </Card>
            )}
          </div>

      </Dialog>
    </div>
  );
}
