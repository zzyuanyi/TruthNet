import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { FileText, Download, AlertTriangle, CheckCircle, Clock, Loader2, ArrowLeft, Shield } from 'lucide-react';
import truthnetAPI from '@/lib/api-client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ReportDetail {
  id: string;
  status: string;
  title?: string;
  company_name?: string;
  risk_level?: string;
  risk_score?: number;
  evidence_count?: number;
  claim_count?: number;
  summary: string;
  key_findings: string[];
  detailed_analysis: string;
  details?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string | null;
  format?: string;
  download_url?: string | null;
}

export default function ReportPage() {
  useDocumentTitle('报告详情');
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reportId) return;
    let cancelled = false;

    const fetchReport = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await truthnetAPI.getReport(reportId);
        if (!cancelled) {
          setReport(response.data.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '获取报告失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    // 轮询直到报告完成
    const poll = async () => {
      try {
        const response = await truthnetAPI.getReport(reportId);
        if (!cancelled) {
          setReport(response.data.data);
          if (response.data.data.status === 'completed' || response.data.data.status === 'failed') {
            setLoading(false);
            return;
          }
        }
      } catch {
        // 继续轮询
      }
      if (!cancelled) {
        setTimeout(poll, 2000);
      }
    };

    fetchReport().then(() => {
      if (report?.status === 'pending' || report?.status === 'processing') {
        poll();
      }
    });

    return () => { cancelled = true; };
  }, [reportId]);

  const handleDownload = () => {
    if (!reportId) return;
    const url = truthnetAPI.getReportDownloadUrl(reportId);
    window.open(url, '_blank');
  };

  const statusConfig: Record<string, { icon: React.ReactNode; label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    pending: { icon: <Clock className="w-4 h-4" />, label: '等待中', variant: 'secondary' },
    processing: { icon: <Loader2 className="w-4 h-4 animate-spin" />, label: '生成中', variant: 'secondary' },
    completed: { icon: <CheckCircle className="w-4 h-4" />, label: '已完成', variant: 'default' },
    failed: { icon: <AlertTriangle className="w-4 h-4" />, label: '失败', variant: 'destructive' },
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground text-lg">正在加载报告...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto" />
          <p className="text-muted-foreground text-lg">{error || '报告不存在'}</p>
          <Button asChild variant="outline">
            <Link to="/">
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回首页
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const status = statusConfig[report.status] || statusConfig.pending;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between">
          <Button asChild variant="ghost" size="sm">
            <Link to="/">
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Link>
          </Button>
          {report.status === 'completed' && (
            <Button onClick={handleDownload} size="sm">
              <Download className="w-4 h-4 mr-2" />
              下载 {report.format?.toUpperCase() || 'PDF'}
            </Button>
          )}
        </div>

        {/* 报告头部 */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <FileText className="w-6 h-6 text-primary" />
                  <CardTitle className="text-2xl">{report.title}</CardTitle>
                </div>
                {report.company_name && (
                  <p className="text-muted-foreground">
                    分析对象：{report.company_name}
                    {report.risk_level && (
                      <Badge variant="outline" className="ml-2">
                        <Shield className="w-3 h-3 mr-1" />
                        {report.risk_level}
                      </Badge>
                    )}
                  </p>
                )}
              </div>
              <Badge variant={status.variant} className="flex items-center gap-1.5">
                {status.icon}
                {status.label}
              </Badge>
            </div>
          </CardHeader>
          {report.status === 'completed' && (
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 bg-muted/50 rounded-lg">
                  <div className="text-2xl font-bold text-primary">{report.evidence_count}</div>
                  <div className="text-xs text-muted-foreground">证据项</div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg">
                  <div className="text-2xl font-bold text-primary">{report.claim_count}</div>
                  <div className="text-xs text-muted-foreground">结论</div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg">
                  <div className="text-2xl font-bold text-primary">{report.risk_score?.toFixed(1) || '-'}</div>
                  <div className="text-xs text-muted-foreground">风险评分</div>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* 报告内容（仅完成时显示） */}
        {report.status === 'completed' && (
          <>
            {/* 摘要 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">摘要</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">{report.summary}</p>
              </CardContent>
            </Card>

            {/* 关键发现 */}
            {report.key_findings && report.key_findings.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">关键发现</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {report.key_findings.map((finding, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <Shield className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                        <span className="text-muted-foreground">{finding}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            <Separator />

            {/* 详细分析 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">详细分析</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="max-h-[600px]">
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <div className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                      {report.details}
                    </div>
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </>
        )}

        {/* 失败状态 */}
        {report.status === 'failed' && (
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="text-destructive text-lg flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" />
                报告生成失败
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">{report.error_message || '未知错误，请稍后重试'}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}