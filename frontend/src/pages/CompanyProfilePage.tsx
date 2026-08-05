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
import { truthnetAPI } from '@/lib/api-client';
import { EquityGraph } from '@/components/truthnet/EquityGraph';
import { RuleCard } from '@/components/truthnet/RuleCard';
import { RiskTimeline } from '@/components/truthnet/RiskTimeline';
import { EvidenceChain } from '@/components/truthnet/EvidenceChain';
import { RelatedPartyTable } from '@/components/truthnet/RelatedPartyTable';
import { Skeleton } from '@/components/ui/skeleton';
import type { FinanceResponseData, EventsResponseData, EquityResponseData, RiskResponseData, RiskLevel, FinanceRuleItem, TimelineEvent, EventCluster, ChatEvidenceV1, EvidenceCategory, Company } from '@/types/truthnet';

// 证据按来源分组工具函数
function groupEvidenceBySource(evidences: ChatEvidenceV1[]): EvidenceCategory[] {
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

  const groups = new Map<string, ChatEvidenceV1[]>();
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
  const [evidences, setEvidences] = useState<ChatEvidenceV1[]>([]);
  const [riskData, setRiskData] = useState<RiskResponseData | null>(null);
  const [activeSection, setActiveSection] = useState('overview');
  const [expandedRules, setExpandedRules] = useState<Set<string>>(new Set());

  const sectionRefs = {
    overview: useRef<HTMLDivElement>(null),
    financial: useRef<HTMLDivElement>(null),
    equity: useRef<HTMLDivElement>(null),
    sentiment: useRef<HTMLDivElement>(null),
    evidence: useRef<HTMLDivElement>(null),
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
      setEquityData(equityRes.data);
      setSentimentEvents(eventsRes.data?.timeline || []);
      setEventClusters(eventsRes.data?.event_clusters || []);
      setEvidences(riskRes.data?.evidence || []);
      setRiskData(riskRes.data);
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

  const toggleRule = (ruleId: string) => {
    setExpandedRules((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) next.delete(ruleId);
      else next.add(ruleId);
      return next;
    });
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
    <div className="flex h-screen bg-background">
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
                    <p className="text-2xl font-bold">{financialAnomalies.length}</p>
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">舆情事件数</p>
                    <p className="text-2xl font-bold">{sentimentEvents.length}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Separator className="my-6" />

          {/* 财务异常区块 - 使用 RuleCard 组件 */}
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
                      onViewEvidence={() => toggleRule(anomaly.rule_id)}
                      onViewDetail={() => toggleRule(anomaly.rule_id)}
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
                  <div className="mt-4 h-96">
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
              <EvidenceChain categories={groupEvidenceBySource(riskData.evidence)} />
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
    </div>
  );
}
