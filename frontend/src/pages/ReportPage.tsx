import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { FileText, Download, AlertTriangle, CheckCircle, Clock, Loader2, ArrowLeft, XCircle, Hash } from 'lucide-react';
import truthnetAPI from '@/lib/api-client';
import type { ReportJobStatus } from '@/lib/api-client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// 后端状态机：queued / running / succeeded / failed / cancelled
const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'cancelled']);

function statusConfig(status: string) {
  switch (status) {
    case 'queued':
      return { icon: Clock, label: '排队中', variant: 'secondary' as const };
    case 'running':
      return { icon: Loader2, label: '生成中', variant: 'secondary' as const, spin: true };
    case 'succeeded':
      return { icon: CheckCircle, label: '已完成', variant: 'default' as const };
    case 'failed':
      return { icon: AlertTriangle, label: '失败', variant: 'destructive' as const };
    case 'cancelled':
      return { icon: XCircle, label: '已取消', variant: 'outline' as const };
    default:
      return { icon: Clock, label: status, variant: 'secondary' as const };
  }
}

export default function ReportPage() {
  useDocumentTitle('报告详情');
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<ReportJobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statusRef = useRef<string>('');

  useEffect(() => {
    if (!reportId) return;
    let cancelled = false;
    // 审查修复：切换 reportId 时重置加载/错误状态，避免展示上一个报告
    setLoading(true);
    setError(null);
    statusRef.current = '';

    const fetchStatus = async (first: boolean) => {
      try {
        const response = await truthnetAPI.getReport(reportId);
        if (cancelled) return;
        setReport(response.data);
        statusRef.current = response.data.status;
        setError(null);
        const status = response.data.status;
        if (!TERMINAL_STATUSES.has(status)) {
          // 未到终态 → 2s 后继续轮询
          pollTimerRef.current = setTimeout(() => fetchStatus(false), 2000);
        }
      } catch (err) {
        if (cancelled) return;
        if (first) {
          setError(err instanceof Error ? err.message : '获取报告失败');
        }
        // 审查修复：用 statusRef 判终态，避免闭包读到陈旧的 report 状态
        if (!TERMINAL_STATUSES.has(statusRef.current)) {
          pollTimerRef.current = setTimeout(() => fetchStatus(false), 3000);
        }
      } finally {
        if (cancelled || first) setLoading(false);
      }
    };

    void fetchStatus(true);
    return () => {
      cancelled = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [reportId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDownload = () => {
    if (!reportId) return;
    window.open(truthnetAPI.getReportDownloadUrl(reportId), '_blank');
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

  const cfg = statusConfig(report.status);
  const StatusIcon = cfg.icon;

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
          {report.status === 'succeeded' && report.download_available && (
            <Button onClick={handleDownload} size="sm">
              <Download className="w-4 h-4 mr-2" />
              下载 PDF
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
                  <CardTitle className="text-2xl">分析报告</CardTitle>
                </div>
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Hash className="h-3 w-3" />
                  {report.report_id}
                </p>
                {report.company_code && (
                  <p className="text-muted-foreground">
                    分析对象：{report.company_code}
                  </p>
                )}
              </div>
              <Badge variant={cfg.variant} className="flex items-center gap-1.5">
                <StatusIcon className={`w-3.5 h-3.5 ${cfg.spin ? 'animate-spin' : ''}`} />
                {cfg.label}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 进度（queued/running） */}
            {(report.status === 'queued' || report.status === 'running') && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>报告生成中，请稍候…</span>
                  <span>{report.progress}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${Math.max(2, report.progress)}%` }}
                  />
                </div>
              </div>
            )}

            {/* 失败信息 */}
            {report.status === 'failed' && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                <p className="text-sm text-destructive flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  {report.error_message || '报告生成失败'}
                </p>
                {report.error_code && (
                  <p className="text-xs text-muted-foreground mt-1">
                    错误码：{report.error_code}
                  </p>
                )}
              </div>
            )}

            {/* 已完成 */}
            {report.status === 'succeeded' && (
              <div className="grid grid-cols-2 gap-4 text-center">
                <div className="p-3 bg-muted/50 rounded-lg">
                  <div className="text-sm font-medium text-primary">PDF 已生成</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    点击右上角「下载 PDF」查看
                  </div>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg">
                  <div className="text-sm font-medium text-primary">完成时间</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {report.completed_at
                      ? new Date(report.completed_at).toLocaleString()
                      : '-'}
                  </div>
                </div>
              </div>
            )}

            {/* 元信息 */}
            <div className="text-xs text-muted-foreground space-y-1 border-t border-border/50 pt-3">
              <p>创建时间：{report.created_at ? new Date(report.created_at).toLocaleString() : '-'}</p>
              {report.file_sha256 && (
                <p className="font-mono break-all">SHA-256：{report.file_sha256}</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
