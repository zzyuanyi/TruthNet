// 织网鉴真 TruthNet - 企业画像页
// T3: 5 区块（概览/财务/股权/舆情/证据）

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
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
  Building2,
  User,
  Landmark,
} from 'lucide-react';
import { mockCompanyProfile } from '@/data/mock';
import { EquityGraph } from '@/components/truthnet/EquityGraph';
import type { CompanyProfile, RiskLevel, FinancialAnomaly, SentimentEvent, EquityNode } from '@/types/truthnet';

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string }> = {
  red: { label: '高危', color: 'bg-red-500 text-white' },
  orange: { label: '中高危', color: 'bg-orange-500 text-white' },
  yellow: { label: '中等', color: 'bg-yellow-500 text-white' },
  blue: { label: '低风险', color: 'bg-blue-500 text-white' },
  green: { label: '正常', color: 'bg-green-500 text-white' },
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
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [activeSection, setActiveSection] = useState('overview');
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 加载企业画像数据
    setProfile(mockCompanyProfile);
  }, [code]);

  // 滚动监听：当用户滚动时自动更新 activeSection
  useEffect(() => {
    const contentEl = contentRef.current;
    if (!contentEl) return;

    const handleScroll = () => {
      const sections = navItems.map(item => ({
        id: item.id,
        el: document.getElementById(item.id),
      }));

      for (let i = sections.length - 1; i >= 0; i--) {
        const section = sections[i];
        if (section.el) {
          const rect = section.el.getBoundingClientRect();
          if (rect.top <= 150) {
            setActiveSection(section.id);
            break;
          }
        }
      }
    };

    contentEl.addEventListener('scroll', handleScroll);
    return () => contentEl.removeEventListener('scroll', handleScroll);
  }, []);

  // 点击锚点导航时平滑滚动到对应区块
  const handleNavClick = (id: string) => {
    setActiveSection(id);
    const el = document.getElementById(id);
    if (el && contentRef.current) {
      contentRef.current.scrollTo({
        top: el.offsetTop - 20,
        behavior: 'smooth',
      });
    }
  };

  if (!profile) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  const riskConfig = riskLevelConfig[profile.risk_overview.risk_level];

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* 左侧锚点导航 */}
      <div className="w-[160px] border-r border-border bg-muted/30 p-4">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 mb-4"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </Button>
        <nav className="space-y-1">
          {navItems.map(item => (
            <button
              key={item.id}
              type="button"
              className={cn(
                'flex w-full items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors text-left',
                activeSection === item.id
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent text-muted-foreground hover:text-foreground'
              )}
              onClick={() => handleNavClick(item.id)}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 右侧内容区 */}
      <div className="flex-1 overflow-auto" ref={contentRef}>
        <div className="p-6 max-w-4xl mx-auto space-y-8">
          {/* 标题 */}
          <div>
            <h1 className="text-2xl font-bold">{profile.name}</h1>
            <p className="text-muted-foreground">
              {profile.code} · {profile.industry} · {profile.market}
            </p>
          </div>

          {/* 概览 */}
          <section id="overview" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                  风险概览
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className={cn('px-4 py-2 rounded-full text-sm font-medium', riskConfig.color)}>
                    {riskConfig.label}
                  </div>
                  <div className="text-sm">
                    <span className="text-muted-foreground">触发规则：</span>
                    <span className="font-medium">{profile.risk_overview.triggered_rules_count} 条</span>
                  </div>
                  <div className="text-sm">
                    <span className="text-muted-foreground">负面公告占比：</span>
                    <span className="font-medium">{(profile.risk_overview.negative_announcement_ratio * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  {profile.risk_overview.summary}
                </p>
              </CardContent>
            </Card>
          </section>

          {/* 财务异常 */}
          <section id="financial" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  财务异常检测
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {profile.financial_anomalies.map(anomaly => (
                    <FinancialAnomalyItem key={anomaly.rule_id} anomaly={anomaly} />
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>

          {/* 股权穿透图 */}
          <section id="equity" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitBranch className="h-5 w-5" />
                  股权穿透图
                </CardTitle>
              </CardHeader>
              <CardContent>
                <EquityGraph nodes={profile.equity_chain.nodes} edges={profile.equity_chain.edges} companyName={profile.name} />
              </CardContent>
            </Card>
          </section>

          {/* 舆情时间线 */}
          <section id="sentiment" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Newspaper className="h-5 w-5" />
                  舆情时间线
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {profile.sentiment_events.map(event => (
                    <SentimentEventItem key={event.id} event={event} />
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>

          {/* 证据引用 */}
          <section id="evidence" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  证据引用
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {profile.evidence.map(category => (
                    <div key={category.category}>
                      <h4 className="text-sm font-medium mb-2">{category.category}</h4>
                      <div className="space-y-2">
                        {category.items.map(item => (
                          <div key={item.id} className="p-3 rounded-md bg-muted/50">
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-sm font-medium">{item.title}</p>
                              <Badge variant="outline" className="text-xs">
                                相关度 {item.relevance_score}%
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {item.source} · {item.date}
                            </p>
                            <p className="text-xs mt-1">{item.content}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>
        </div>
      </div>
    </div>
  );
}

// 财务异常项
function FinancialAnomalyItem({ anomaly }: { anomaly: FinancialAnomaly }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="flex items-center justify-between w-full p-3 rounded-md bg-muted/50 hover:bg-muted transition-colors">
        <div className="flex items-center gap-3">
          {anomaly.triggered ? (
            <AlertTriangle className="h-4 w-4 text-destructive" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <div className="text-left">
            <p className="text-sm font-medium">{anomaly.rule_name}</p>
            <p className="text-xs text-muted-foreground">
              当前: {anomaly.current_value} | 预期: {anomaly.expected_value}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {anomaly.triggered && (
            <Badge variant="destructive" className="text-xs">
              P{anomaly.industry_percentile}
            </Badge>
          )}
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pb-3 pt-2">
        <p className="text-xs text-muted-foreground">{anomaly.explanation}</p>
      </CollapsibleContent>
    </Collapsible>
  );
}
// 舆情事件项
function SentimentEventItem({ event }: { event: SentimentEvent }) {
  const typeConfig = {
    positive: { color: 'bg-green-500', label: '正面' },
    negative: { color: 'bg-red-500', label: '负面' },
    neutral: { color: 'bg-gray-500', label: '中性' },
  };

  const config = typeConfig[event.type];

  return (
    <div className="flex gap-4">
      {/* 时间线 */}
      <div className="flex flex-col items-center">
        <div className={cn('w-3 h-3 rounded-full', config.color)} />
        <div className="w-px flex-1 bg-border" />
      </div>

      {/* 内容 */}
      <div className="flex-1 pb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-muted-foreground">{event.date}</span>
          <Badge variant="outline" className="text-xs">
            {config.label}
          </Badge>
          <Badge variant="secondary" className="text-xs">
            影响度 {event.impact_score}
          </Badge>
        </div>
        <p className="text-sm font-medium">{event.title}</p>
        <p className="text-xs text-muted-foreground mt-1">{event.summary}</p>
        <p className="text-xs text-muted-foreground mt-1">来源: {event.source}</p>
      </div>
    </div>
  );
}
