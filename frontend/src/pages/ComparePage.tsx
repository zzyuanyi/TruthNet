// 织网鉴真 TruthNet - 跨公司对比页
// Phase 3: 多公司对比分析

import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ArrowLeft,
  TrendingUp,
  AlertTriangle,
  GitBranch,
  Newspaper,
  BarChart3,
  Building2,
} from 'lucide-react';
import { truthnetAPI } from '@/lib/api-client';
import type { CompanyRiskSummary, ComparisonsResponseData, RiskLevel } from '@/types/truthnet';

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string }> = {
  red: { label: '高危', color: 'bg-red-500 text-white' },
  orange: { label: '中高危', color: 'bg-orange-500 text-white' },
  yellow: { label: '中等', color: 'bg-yellow-500 text-white' },
  blue: { label: '低风险', color: 'bg-blue-500 text-white' },
  green: { label: '正常', color: 'bg-green-500 text-white' },
  unknown: { label: '未知', color: 'bg-gray-500 text-white' },
};

// 对比指标
const comparisonMetrics = [
  { key: 'risk_level', label: '风险等级', icon: AlertTriangle },
  { key: 'triggered_rules', label: '触发规则数', icon: AlertTriangle },
  { key: 'coverage', label: '数据覆盖率', icon: Newspaper },
  { key: 'overall_score', label: '综合评分', icon: TrendingUp },
  { key: 'evidence_count', label: '证据数量', icon: GitBranch },
];

export default function ComparePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<CompanyRiskSummary[]>([]);
  const [comparisonData, setComparisonData] = useState<ComparisonsResponseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadCompanies = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 获取对比公司代码
        const codes = searchParams.get('codes')?.split(',').filter(Boolean) || [];
        
        if (codes.length === 0) {
          setError('请选择要对比的公司');
          setLoading(false);
          return;
        }
        
        // 调用对比 API
        const response = await truthnetAPI.compareCompanies(codes);
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
  }, [searchParams]);

  // 获取指标值
  const getMetricValue = (company: CompanyRiskSummary, metricKey: string) => {
    switch (metricKey) {
      case 'risk_level':
        return company.risk_level;
      case 'triggered_rules':
        return company.triggered_rules.length;
      case 'coverage':
        return `${(company.coverage * 100).toFixed(0)}%`;
      case 'overall_score':
        return company.overall_score.toFixed(1);
      case 'evidence_count':
        return company.evidence_ids.length;
      default:
        return '-';
    }
  };

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

  if (error) {
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
            <AlertTriangle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <p className="text-muted-foreground">{error}</p>
            <Button variant="outline" className="mt-4" onClick={() => navigate(-1)}>
              返回
            </Button>
          </div>
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
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

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
                  {comparisonMetrics.map((metric) => {
                    const Icon = metric.icon;
                    return (
                      <div key={metric.key} className="space-y-2">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <Icon className="h-4 w-4 text-muted-foreground" />
                          {metric.label}
                        </div>
                        <div className="grid grid-cols-3 gap-4">
                          {companies.map((company) => {
                            const value = getMetricValue(company, metric.key);
                            return (
                              <div
                                key={company.wind_code}
                                className="p-3 rounded-lg border bg-card text-center"
                              >
                                {metric.key === 'risk_level' ? (
                                  <Badge className={cn('text-xs', getRiskLevelStyle(value as string))}>
                                    {riskLevelConfig[value as RiskLevel]?.label}
                                  </Badge>
                                ) : (
                                  <span className="text-lg font-medium">
                                    {value}
                                  </span>
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
                  {companies.map((company) => (
                    <div key={company.wind_code} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{company.sec_name}</span>
                        <Badge variant="secondary" className="text-xs">
                          {company.triggered_rules.length} 条规则
                        </Badge>
                      </div>
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
                    </div>
                  ))}
                </div>
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
