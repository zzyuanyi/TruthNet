// 织网鉴真 TruthNet - 跨公司对比页
// T5: 多公司对比分析

import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  ArrowLeft,
  TrendingUp,
  AlertTriangle,
  GitBranch,
  Newspaper,
} from 'lucide-react';
import { mockCompanyProfile } from '@/data/mock';
import type { CompanyProfile, RiskLevel } from '@/types/truthnet';

// 风险等级配置
const riskLevelConfig: Record<RiskLevel, { label: string; color: string }> = {
  red: { label: '高危', color: 'bg-red-500 text-white' },
  orange: { label: '中高危', color: 'bg-orange-500 text-white' },
  yellow: { label: '中等', color: 'bg-yellow-500 text-white' },
  blue: { label: '低风险', color: 'bg-blue-500 text-white' },
  green: { label: '正常', color: 'bg-green-500 text-white' },
};

// 对比指标
const comparisonMetrics = [
  { key: 'risk_level', label: '风险等级', icon: AlertTriangle },
  { key: 'triggered_rules', label: '触发规则数', icon: AlertTriangle },
  { key: 'negative_ratio', label: '负面公告占比', icon: Newspaper },
  { key: 'anomaly_count', label: '财务异常数', icon: TrendingUp },
  { key: 'equity_depth', label: '股权层级', icon: GitBranch },
];

export default function ComparePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);

  useEffect(() => {
    // 获取对比公司代码
    const codes = searchParams.get('codes')?.split(',') || [];
    
    // 加载公司数据（这里使用 mock 数据，实际应该从 API 获取）
    const loadedCompanies: CompanyProfile[] = [];
    for (let i = 0; i < Math.min(codes.length, 3); i++) {
      // 模拟不同公司的数据
      const mockData = { ...mockCompanyProfile };
      mockData.code = codes[i] || `00000${i}.SZ`;
      mockData.name = `示例公司${i + 1}`;
      loadedCompanies.push(mockData);
    }
    setCompanies(loadedCompanies);
  }, [searchParams]);

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* 顶部导航 */}
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回
          </Button>
          <h1 className="text-xl font-bold">跨公司对比分析</h1>
        </div>
      </div>

      {/* 对比内容 */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {companies.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <p className="text-muted-foreground">请选择要对比的公司</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 公司概览对比 */}
              <Card>
                <CardHeader>
                  <CardTitle>公司概览</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {companies.map(company => {
                      const riskConfig = riskLevelConfig[company.risk_overview.risk_level];
                      return (
                        <div key={company.code} className="p-4 rounded-lg border border-border">
                          <h3 className="font-medium mb-2">{company.name}</h3>
                          <p className="text-xs text-muted-foreground mb-3">
                            {company.code} · {company.industry}
                          </p>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-muted-foreground">风险等级</span>
                              <div className={cn('px-2 py-1 rounded text-xs font-medium', riskConfig.color)}>
                                {riskConfig.label}
                              </div>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-muted-foreground">触发规则</span>
                              <span className="text-sm font-medium">
                                {company.risk_overview.triggered_rules_count} 条
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-muted-foreground">负面公告</span>
                              <span className="text-sm font-medium">
                                {(company.risk_overview.negative_announcement_ratio * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* 财务异常对比 */}
              <Card>
                <CardHeader>
                  <CardTitle>财务异常对比</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left py-2 px-3 font-medium">规则名称</th>
                          {companies.map(company => (
                            <th key={company.code} className="text-center py-2 px-3 font-medium">
                              {company.name}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {mockCompanyProfile.financial_anomalies.map(anomaly => (
                          <tr key={anomaly.rule_id} className="border-b border-border/50">
                            <td className="py-2 px-3">
                              <div className="flex items-center gap-2">
                                {anomaly.triggered && (
                                  <AlertTriangle className="h-3 w-3 text-destructive" />
                                )}
                                <span>{anomaly.rule_name}</span>
                              </div>
                            </td>
                            {companies.map((company, idx) => {
                              // 模拟不同公司的数据
                              const companyAnomaly = company.financial_anomalies.find(
                                a => a.rule_id === anomaly.rule_id
                              ) || { ...anomaly, triggered: idx === 0 ? anomaly.triggered : Math.random() > 0.5 };
                              return (
                                <td key={company.code} className="text-center py-2 px-3">
                                  {companyAnomaly.triggered ? (
                                    <Badge variant="destructive" className="text-xs">
                                      触发
                                    </Badge>
                                  ) : (
                                    <Badge variant="outline" className="text-xs">
                                      正常
                                    </Badge>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* 关键指标对比 */}
              <Card>
                <CardHeader>
                  <CardTitle>关键指标对比</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {comparisonMetrics.map(metric => (
                      <div key={metric.key} className="flex items-center gap-4">
                        <div className="flex items-center gap-2 w-40">
                          <metric.icon className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">{metric.label}</span>
                        </div>
                        <div className="flex-1 grid grid-cols-3 gap-4">
                          {companies.map((company, idx) => {
                            let value = '';
                            switch (metric.key) {
                              case 'risk_level':
                                value = riskLevelConfig[company.risk_overview.risk_level].label;
                                break;
                              case 'triggered_rules':
                                value = `${company.risk_overview.triggered_rules_count} 条`;
                                break;
                              case 'negative_ratio':
                                value = `${(company.risk_overview.negative_announcement_ratio * 100).toFixed(0)}%`;
                                break;
                              case 'anomaly_count':
                                value = `${company.financial_anomalies.filter(a => a.triggered).length} 条`;
                                break;
                              case 'equity_depth':
                                value = `${company.equity_chain.nodes.length} 层`;
                                break;
                            }
                            return (
                              <div key={company.code} className="text-center">
                                <span className={cn(
                                  'text-sm font-medium',
                                  idx === 0 && 'text-primary'
                                )}>
                                  {value}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* 舆情对比 */}
              <Card>
                <CardHeader>
                  <CardTitle>舆情事件对比</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {companies.map(company => (
                      <div key={company.code} className="space-y-2">
                        <h4 className="text-sm font-medium">{company.name}</h4>
                        <div className="space-y-2">
                          {company.sentiment_events.slice(0, 3).map(event => {
                            const typeConfig = {
                              positive: { color: 'bg-green-500', label: '正面' },
                              negative: { color: 'bg-red-500', label: '负面' },
                              neutral: { color: 'bg-gray-500', label: '中性' },
                            };
                            const config = typeConfig[event.type];
                            return (
                              <div key={event.id} className="p-2 rounded-md bg-muted/50">
                                <div className="flex items-center gap-2 mb-1">
                                  <div className={cn('w-2 h-2 rounded-full', config.color)} />
                                  <span className="text-xs text-muted-foreground">{event.date}</span>
                                  <Badge variant="outline" className="text-xs">
                                    {config.label}
                                  </Badge>
                                </div>
                                <p className="text-xs">{event.title}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
