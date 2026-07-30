
import { KSCurveChart, ROCCurveChart, FeatureImportanceChart, LiftGainChart, ConfusionMatrixChart, StrategyCompareChart } from '@/components/charts/financial-charts';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '@/lib/api-client';

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Edit,
  Rocket,
  Download,
  Package,
  CheckCircle2,
  Clock,
  FileText,
  BarChart3,
  Database,
  Hash,
  ArrowLeft,
  AlertCircle,
  GitBranch,
  Archive,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
  Loader2,
  Trash2,
} from 'lucide-react';
import { formatNumber, formatDate, type ModelItem, demoModels } from '@/lib/demo-data';
import { toast } from 'sonner';

// Artifact type mapping
const artifactTypeMap: Record<string, string> = {
  'model.pkl': '模型文件 (Pickle)',
  'model.onnx': '模型文件 (ONNX)',
  'schema.json': '推理 Schema',
  'features.json': '特征定义',
  'features_ordered.json': '特征定义 (有序)',
  'eval_report.pdf': '评估报告',
};

const artifactPhaseMap: Record<string, string> = {
  'model.pkl': '模型训练',
  'model.onnx': '模型训练',
  'schema.json': '服务部署',
  'features.json': '特征工程',
  'features_ordered.json': '特征工程',
  'eval_report.pdf': '模型评估',
};

const artifactSizeMap: Record<string, string> = {
  'model.pkl': '45.7 MB',
  'model.onnx': '38.2 MB',
  'schema.json': '12.4 KB',
  'features.json': '8.2 KB',
  'features_ordered.json': '9.1 KB',
  'eval_report.pdf': '3.2 MB',
};

// Workflow phases adapt to model status
function getWorkflowPhases(modelStatus: string) {
  const phases = [
    { name: '数据处理', icon: Database },
    { name: '特征工程', icon: BarChart3 },
    { name: '模型训练', icon: Rocket },
    { name: '模型评估', icon: CheckCircle2 },
  ];

  if (modelStatus === 'error') {
    return [
      { name: '数据处理', icon: Database, completed: true },
      { name: '特征工程', icon: BarChart3, completed: true },
      { name: '模型训练', icon: Rocket, completed: false, error: true },
      { name: '模型评估', icon: CheckCircle2, completed: false },
    ];
  }
  if (modelStatus === 'stopped') {
    return [
      { name: '数据处理', icon: Database, completed: true },
      { name: '特征工程', icon: BarChart3, completed: true },
      { name: '模型训练', icon: Rocket, completed: true },
      { name: '模型评估', icon: CheckCircle2, completed: true },
    ];
  }
  // running / deploying
  return phases.map((p) => ({ ...p, completed: true }));
}

// Metric display helpers
interface MetricDisplay {
  name: string;
  value: number;
  displayValue: string;
  barPercent: number;
  isLogLoss?: boolean;
}

function getMetricDisplays(metrics: ModelItem['metrics']): MetricDisplay[] {
  return [
    { name: 'Accuracy', value: metrics.accuracy, displayValue: formatNumber(metrics.accuracy), barPercent: Math.round(metrics.accuracy * 100) },
    { name: 'Precision', value: metrics.precision, displayValue: formatNumber(metrics.precision), barPercent: Math.round(metrics.precision * 100) },
    { name: 'Recall', value: metrics.recall, displayValue: formatNumber(metrics.recall), barPercent: Math.round(metrics.recall * 100) },
    { name: 'F1 Score', value: metrics.f1, displayValue: formatNumber(metrics.f1), barPercent: Math.round(metrics.f1 * 100) },
    { name: 'ROC-AUC', value: metrics.auc, displayValue: formatNumber(metrics.auc), barPercent: Math.round(metrics.auc * 100) },
    { name: 'PR-AUC', value: metrics.pr_auc, displayValue: formatNumber(metrics.pr_auc), barPercent: Math.round(metrics.pr_auc * 100) },
    { name: 'Log Loss', value: metrics.log_loss, displayValue: formatNumber(metrics.log_loss), barPercent: metrics.log_loss > 0 ? Math.max(5, Math.round((1 - metrics.log_loss) * 100)) : 0, isLogLoss: true },
    { name: 'Top-K', value: metrics.top_k, displayValue: formatNumber(metrics.top_k), barPercent: Math.round(metrics.top_k * 100) },
  ];
}

function VersionStatusIcon({ status }: { status: string }) {
  if (status === 'current') return <CheckCircle2 className="h-3.5 w-3.5 text-blue-600" />;
  if (status === 'deprecated') return <AlertTriangle className="h-3.5 w-3.5 text-red-400" />;
  return <Archive className="h-3.5 w-3.5 text-gray-400" />;
}

function VersionStatusLabel({ status }: { status: string }) {
  if (status === 'current') return <Badge className="bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-100 text-[11px]">当前版本</Badge>;
  if (status === 'deprecated') return <Badge className="bg-red-50 text-red-500 border-red-200 hover:bg-red-50 text-[11px]">已弃用</Badge>;
  return <Badge className="bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-100 text-[11px]">已归档</Badge>;
}

function MetricDiff({ current, previous }: { current: number; previous: number }) {
  if (previous === 0 && current === 0) return <Minus className="h-3 w-3 text-gray-300" />;
  const diff = current - previous;
  if (Math.abs(diff) < 0.001) return <Minus className="h-3 w-3 text-gray-300" />;
  if (diff > 0) return <span className="flex items-center gap-0.5 text-emerald-600 text-xs font-medium"><TrendingUp className="h-3 w-3" />+{(diff * 100).toFixed(1)}%</span>;
  return <span className="flex items-center gap-0.5 text-red-500 text-xs font-medium"><TrendingDown className="h-3 w-3" />{(diff * 100).toFixed(1)}%</span>;
}

function DownloadDialog({ modelId, modelName, version, artifacts }: { modelId: string; modelName: string; version: string; artifacts: string[] }) {
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleDownload = async (fileName: string) => {
    setDownloading(fileName);
    try {
      const response = await fetch(`/api/models/${modelId}/download/${encodeURIComponent(fileName)}`);
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // Extract filename from Content-Disposition header
      const disposition = response.headers.get('Content-Disposition');
      const match = disposition?.match(/filename="?(.+?)"?$/);
      a.download = match ? decodeURIComponent(match[1]) : fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      // Fallback: open download URL directly
      window.open(`/api/models/${modelId}/download/${encodeURIComponent(fileName)}`, '_blank');
    }
    setTimeout(() => setDownloading(null), 800);
  };

  // handleDeploy moved after state declarations

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700">
          <Download className="h-4 w-4" /> 下载模型
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5 text-blue-600" />
            下载模型文件
          </DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <p className="text-sm text-muted-foreground mb-3">
            <span className="font-medium text-foreground">{modelName}</span>
            <Badge variant="outline" className="ml-2 text-[11px] font-mono">{version}</Badge>
          </p>
          <div className="space-y-2 max-h-[320px] overflow-y-auto">
            {artifacts.map((name) => {
              const info = artifactTypeMap[name] || name;
              const size = artifactSizeMap[name] || '-';
              return (
                <div
                  key={name}
                  className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2.5 hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="h-4 w-4 text-blue-400 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{name}</p>
                      <p className="text-xs text-muted-foreground">{info} · {size}</p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="gap-1 shrink-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                    onClick={() => handleDownload(name)}
                    disabled={downloading === name}
                  >
                    {downloading === name ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Download className="h-3.5 w-3.5" />
                    )}
                    {downloading === name ? '下载中' : '下载'}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function ModelDetailPage() {
  const navigate = useNavigate();
  const params = useParams();
  const modelId = params.id as string;
  const [model, setModel] = useState<ModelItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [deploying, setDeploying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [activeVersionIdx, setActiveVersionIdx] = useState(0);
  const [compareMode, setCompareMode] = useState(false);
  const [compareIdx, setCompareIdx] = useState<number | null>(null);
  const [usingDemoData, setUsingDemoData] = useState(false);
  const [vizData, setVizData] = useState<any>(null);

  const handleDeleteModel = async () => {
    if (!model) return;
    if (!confirm(`确定要删除模型「${model.name}」吗？\n\n删除后将同时清除该模型的所有版本、评估数据、服务实例和关联的物理文件，且不可恢复。`)) return;
    setDeleting(true);
    try {
      await api.modelsDeploy.delete(Number(model.id));
      toast.success('模型已删除', { description: `已删除模型「${model.name}」及关联数据` });
      // 通知任务页面：该模型对应的任务不再入库
      window.dispatchEvent(new CustomEvent('repository:model-deleted', { detail: { modelId: model.id } }));
      navigate('/repository');
    } catch (err) {
      console.error('Failed to delete model:', err);
      toast.error('删除模型失败', { description: String(err) });
    } finally {
      setDeleting(false);
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      if (usingDemoData) {
        toast.info('当前详情页展示的是演示模型，已为您跳转到模型服务页查看示例部署');
        navigate('/service');
        return;
      }
      // Get the latest version ID for this model
      const versionData = await api.modelsDeploy.versions(Number(modelId));
      const versionItems = versionData?.items || [];
      if (versionItems.length === 0) {
        alert('该模型没有可用版本，无法部署');
        return;
      }
      const latestVersion = versionItems[0];
      const versionId = latestVersion.model_version_id;

      // 创建服务实例：自动确认 schema 并启动 worker，直接 running
      await api.services.create(Number(versionId));
      toast.success('部署成功！正在跳转到模型服务页面...');
      navigate('/service');
    } catch (err) {
      const message = err instanceof Error ? err.message : '网络错误';
      console.error('Repository detail deploy fallback:', message, err);
      toast.info('当前模型暂不可直接创建真实服务，已为您跳转到模型服务页查看示例部署');
      navigate('/service');
    } finally {
      setDeploying(false);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        // Fetch model from backend
        setUsingDemoData(false);
        const m = await api.modelsDeploy.get(Number(modelId)) as any;
        // Fetch versions
        let versions: any[] = [];
        try {
          const versionData = await api.modelsDeploy.versions(Number(modelId));
          versions = versionData?.items || [];
        } catch { /* no versions yet */ }
        // Fetch artifacts for this model
        let artifactsList: { name: string; version_id: number; version_tag: string; size: number; file_path: string }[] = [];
        try {
          const artRes = await fetch(`/api/models/${modelId}/artifacts`);
          const artData = await artRes.json();
          if (artData.code === 200 && artData.data?.items) {
            artifactsList = artData.data.items;
          }
        } catch { /* no artifacts yet */ }
        // Fetch evaluation for each version
        const enrichedVersions = await Promise.all(versions.map(async (v: any) => {
          let metrics = { accuracy: 0, precision: 0, recall: 0, f1: 0, auc: 0, pr_auc: 0, log_loss: 0, top_k: 0, ks: 0, psi: 0 };
          try {
            const evalData = await api.modelsDeploy.versionEvaluation(Number(v.model_version_id)) as any;
            if (evalData) {
              const rawMetrics = evalData.metrics_data?.model_evaluation || evalData.metrics_data || evalData.metrics || {};
              metrics = {
                accuracy: rawMetrics.accuracy || 0, precision: rawMetrics.precision || 0, recall: rawMetrics.recall || 0,
                f1: rawMetrics.f1 || rawMetrics.f1_score || 0, auc: rawMetrics.auc || rawMetrics.roc_auc || 0,
                pr_auc: rawMetrics.pr_auc || 0, log_loss: rawMetrics.log_loss || 0, top_k: rawMetrics.top_k || 0,
                ks: rawMetrics.ks || 0, psi: rawMetrics.psi || 0,
              };
            }
          } catch { /* no evaluation yet */ }
          let visualizationData: any = null;
          try {
            const vizRes = await fetch(`/api/model-versions/${v.model_version_id}/visualization`);
            const vizJson = await vizRes.json();
            if (vizJson.code === 200) visualizationData = vizJson.data?.visualization_data || null;
          } catch { /* no visualization yet */ }
          // Collect artifacts for this version
          const versionArtifacts = artifactsList
            .filter(a => a.version_id === v.model_version_id)
            .map(a => a.name);
          // Fallback: if version has a file_path, add it as an artifact
          const vfilePath = v.file_path || v.filePath || '';
          const vfileName = vfilePath.split('/').pop() || '';
          if (vfileName && !versionArtifacts.includes(vfileName)) {
            versionArtifacts.push(vfileName);
          }
          // Also add schema.json and features.json if version has schema
          if (v.schema_json && !versionArtifacts.includes('schema.json')) {
            versionArtifacts.push('schema.json');
          }
          return {
            modelVersionId: v.model_version_id,
            visualizationData,
            version: String(v.version_tag || v.version || '1.0.0'),
            status: 'current' as const,
            createdAt: String(v.created_at || v.createdAt || new Date().toISOString()),
            changelog: String(v.description || '初始版本'),            metrics,
            artifacts: versionArtifacts.length > 0 ? versionArtifacts : [vfileName || 'model.joblib'],
            artifactSizes: Object.fromEntries(
              artifactsList
                .filter(a => a.version_id === v.model_version_id)
                .map(a => [a.name, a.size])
            ),
            fileSize: (() => {
              const va = artifactsList.find(a => a.version_id === v.model_version_id);
              if (va && va.size > 0) {
                const size = va.size;
                if (size > 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
                if (size > 1024) return `${(size / 1024).toFixed(1)} KB`;
                return `${size} B`;
              }
              return '-';
            })(),
            downloadCount: 0,
          };
        }));
        // If no versions from backend, create a placeholder
        if (enrichedVersions.length === 0) {
          enrichedVersions.push({
            modelVersionId: null,
            version: '1.0.0', status: 'current' as const, createdAt: new Date().toISOString(),
            changelog: '初始版本', metrics: { accuracy: 0, precision: 0, recall: 0, f1: 0, auc: 0, pr_auc: 0, log_loss: 0, top_k: 0, ks: 0, psi: 0 },
            artifacts: [] as Array<{ name: string; size: number; type: string }>, artifactSizes: {} as Record<string, number>, fileSize: '-', downloadCount: 0, visualizationData: null,
          });
        }
        // Map backend model to ModelItem
        const mappedModel: ModelItem = {
          id: String(m.model_id),
          name: String(m.name || '未命名模型'),
          modelType: String(m.model_type || m.type || 'sklearn'),
          framework: String(m.model_type || m.type || 'sklearn'),
          status: 'stopped',
          sceneName: String(m.scene_name || m.scene || '通用'),
          version: enrichedVersions.length > 0 ? enrichedVersions[0].version : '1.0.0',
          createdAt: String(m.created_at || m.createdAt || new Date().toISOString()),
          updatedAt: String(m.created_at || m.updatedAt || m.createdAt || new Date().toISOString()),
          sampleCount: 0,
          featuresCount: 0,
          metrics: enrichedVersions.length > 0 ? enrichedVersions[0].metrics : { accuracy: 0, precision: 0, recall: 0, f1: 0, auc: 0, pr_auc: 0, log_loss: 0, top_k: 0, ks: 0, psi: 0 },
          artifacts: enrichedVersions.length > 0 ? enrichedVersions[0].artifacts : [],
          tags: [],
          downloadCount: 0,
          versions: enrichedVersions,
        };
        setModel(mappedModel);
        
      } catch (err) {
        console.error('Failed to load model from backend:', err);
        setModel(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [modelId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">加载中...</p>
        </div>
      </div>
    );
  }

  if (!model) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="w-96 text-center">
          <CardContent className="pt-8 pb-6">
            <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
            <h2 className="text-lg font-semibold mb-2">模型未找到</h2>
            <p className="text-sm text-gray-500 mb-4">ID 为 {modelId} 的模型不存在或已被删除</p>
            <Link to="/repository">
              <Button variant="outline">返回模型仓库</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const activeVersion = model.versions[activeVersionIdx] || model.versions[0];
  const activeMetrics = activeVersion.metrics;
  const activeVizData = (activeVersion as any)?.visualizationData || vizData || null;
  const compareVersion = compareIdx !== null ? model.versions[compareIdx] : null;

  const workflowPhases = getWorkflowPhases(model.status);
  const metricDisplays = getMetricDisplays(activeMetrics);

  // Version artifacts
  const activeArtifacts = activeVersion.artifacts.map((name) => {
    const realSize = (activeVersion as any).artifactSizes?.[name];
    let displaySize = artifactSizeMap[name] || '-';
    if (realSize && realSize > 0) {
      if (realSize > 1024 * 1024) displaySize = `${(realSize / 1024 / 1024).toFixed(1)} MB`;
      else if (realSize > 1024) displaySize = `${(realSize / 1024).toFixed(1)} KB`;
      else displaySize = `${realSize} B`;
    }
    return {
      name,
      type: artifactTypeMap[name] || name.endsWith('.json') ? '配置文件' : name.endsWith('.joblib') || name.endsWith('.pkl') ? '模型文件' : '未知类型',
      phase: artifactPhaseMap[name] || '模型训练',
      size: displaySize,
    };
  });

  // Base info from active version
  const baseInfoItems = [
    { label: '所属场景', value: model.sceneName, icon: Package },
    { label: '版本更新时间', value: formatDate(activeVersion.createdAt), icon: Clock },
    { label: '样本数量', value: model.sampleCount.toLocaleString(), icon: Database },
    { label: '特征数量', value: String(model.featuresCount), icon: Hash },
  ];

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto max-w-[1440px] px-3 sm:px-6 py-4 sm:py-6">
        {/* Header */}
        <div className="mb-4 sm:mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <Link to="/repository" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="h-3.5 w-3.5" /> 返回模型仓库
            </Link>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2">
              {model.name}
            </h1>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              {model.status === 'running' && <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">运行中</Badge>}
              {model.status === 'error' && <Badge className="bg-red-100 text-red-700 border-red-200">异常</Badge>}
              {model.status === 'stopped' && <Badge className="bg-gray-100 text-gray-600 border-gray-200">已停止</Badge>}
              {model.status === 'deploying' && <Badge className="bg-amber-100 text-amber-700 border-amber-200">部署中</Badge>}
              <span className="text-sm text-muted-foreground">{model.modelType}</span>
              <span className="text-sm text-muted-foreground">·</span>
              <span className="text-sm text-muted-foreground">{model.framework}</span>
              <span className="text-sm text-muted-foreground">·</span>
              <span className="flex items-center gap-1 text-sm text-muted-foreground"><Download className="h-3 w-3" />{model.downloadCount.toLocaleString()} 次下载</span>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button variant="outline" size="sm" className="gap-1.5 sm:gap-2">
              <Edit className="h-4 w-4" /> <span className="hidden sm:inline">编辑信息</span>
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5 sm:gap-2" onClick={handleDeploy} disabled={deploying}>
                <Rocket className="h-4 w-4" /> <span className="hidden sm:inline">{deploying ? '部署中...' : '部署'}</span> / 推理
              </Button>
            <DownloadDialog modelId={model.id} modelName={model.name} version={activeVersion.version} artifacts={activeVersion.artifacts} />
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 sm:gap-2 text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
              onClick={handleDeleteModel}
              disabled={deleting}
            >
              {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              <span className="hidden sm:inline">{deleting ? '删除中...' : '删除'}</span>
            </Button>
          </div>
        </div>

        {/* Version Management Section */}
        <Card className="mb-4 border-border/60">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-blue-600" />
                版本管理
                <Badge variant="outline" className="text-[11px]">{model.versions.length} 个版本</Badge>
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  setCompareMode(!compareMode);
                  if (compareMode) setCompareIdx(null);
                }}
              >
                {compareMode ? '退出对比' : '版本对比'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {/* Version Selector */}
            <div className="flex items-center gap-3 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-muted-foreground">当前版本</span>
                <Select
                  value={String(activeVersionIdx)}
                  onValueChange={(val) => setActiveVersionIdx(Number(val))}
                >
                  <SelectTrigger className="w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {model.versions.map((v, idx) => (
                      <SelectItem key={v.version} value={String(idx)}>
                        {v.version} ({v.status === 'current' ? '当前版本' : v.status === 'deprecated' ? '已弃用' : '已归档'}, {new Date(v.createdAt).toLocaleDateString('zh-CN')})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {compareMode && (
                <div className="flex items-center gap-2">
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-sm font-medium text-muted-foreground">对比版本</span>
                  <Select
                    value={compareIdx !== null ? String(compareIdx) : ''}
                    onValueChange={(val) => setCompareIdx(Number(val))}
                  >
                    <SelectTrigger className="w-[200px] border-violet-300 focus:ring-violet-200">
                      <SelectValue placeholder="选择对比版本" />
                    </SelectTrigger>
                    <SelectContent>
                      {model.versions
                        .filter((_, idx) => idx !== activeVersionIdx)
                        .map((v) => {
                          const idx = model.versions.indexOf(v);
                          return (
                            <SelectItem key={v.version} value={String(idx)}>
                              {v.version} ({v.status === 'current' ? '当前版本' : v.status === 'deprecated' ? '已弃用' : '已归档'}, {new Date(v.createdAt).toLocaleDateString('zh-CN')})
                            </SelectItem>
                          );
                        })}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>

            {/* Active Version Changelog */}
            <div className="rounded-lg bg-muted/50 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium">{activeVersion.version} 更新日志</span>
                <Badge variant="outline" className="text-[10px]">{activeVersion.fileSize}</Badge>
                <span className="text-xs text-muted-foreground flex items-center gap-1 ml-auto"><Download className="h-3 w-3" />{activeVersion.downloadCount.toLocaleString()}</span>
              </div>
              <p className="text-sm text-muted-foreground mb-3">{activeVersion.changelog}</p>
              {/* Artifacts Download Links */}
              {activeVersion.artifacts && activeVersion.artifacts.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {activeVersion.artifacts.map((artifact: string) => (
                    <button
                      key={artifact}
                      onClick={() => {
                        const link = document.createElement('a');
                        link.href = `/api/models/${model.id}/download/${artifact}`;
                        link.download = artifact;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white border border-border/60 text-xs font-medium text-gray-700 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50/50 transition-colors"
                    >
                      <Download className="h-3 w-3" />
                      {artifact}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Version Comparison Table */}
            {compareMode && compareVersion && (
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  版本对比
                  <Badge variant="outline" className="font-mono text-[11px]">{activeVersion.version}</Badge>
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  <Badge variant="outline" className="font-mono text-[11px] border-violet-300 text-violet-600">{compareVersion.version}</Badge>
                </h4>
                <div className="rounded-lg border border-border/60 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/50">
                        <th className="px-4 py-2 text-left font-medium text-muted-foreground">指标</th>
                        <th className="px-4 py-2 text-center font-medium text-blue-600">{activeVersion.version}</th>
                        <th className="px-4 py-2 text-center font-medium text-violet-600">{compareVersion.version}</th>
                        <th className="px-4 py-2 text-center font-medium text-muted-foreground">变化</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(['accuracy', 'precision', 'recall', 'f1', 'auc', 'pr_auc', 'log_loss', 'top_k'] as const).map((key) => {
                        const labels: Record<string, string> = { accuracy: 'Accuracy', precision: 'Precision', recall: 'Recall', f1: 'F1', auc: 'ROC-AUC', pr_auc: 'PR-AUC', log_loss: 'Log Loss', top_k: 'Top-K' };
                        const cur = activeMetrics[key];
                        const prev = compareVersion.metrics[key];
                        return (
                          <tr key={key} className="border-t border-border/40">
                            <td className="px-4 py-2 font-medium">{labels[key]}</td>
                            <td className="px-4 py-2 text-center font-mono">{cur > 0 ? formatNumber(cur) : '-'}</td>
                            <td className="px-4 py-2 text-center font-mono">{prev > 0 ? formatNumber(prev) : '-'}</td>
                            <td className="px-4 py-2 text-center">
                              <MetricDiff current={cur} previous={prev} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Base Info */}
        <Card className="mb-4 border-border/60">
          <CardContent className="p-0">
            <div className="grid grid-cols-2 gap-0 sm:grid-cols-4">
              {baseInfoItems.map((item, i) => (
                <div key={item.label} className={`flex items-center gap-3 p-5 ${i > 0 ? 'border-l border-border/60' : ''}`}>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50">
                    <item.icon className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{item.label}</p>
                    <p className="text-sm font-semibold">{item.value}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Workflow */}
        <Card className="mb-4 border-border/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">工作流阶段</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {workflowPhases.map((phase) => {
                const PhaseIcon = phase.icon;
                if (phase.completed) {
                  return (
                    <Badge key={phase.name} className="gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-50 px-3 py-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {phase.name} 已完成
                    </Badge>
                  );
                }
                if ('error' in phase && phase.error) {
                  return (
                    <Badge key={phase.name} className="gap-1.5 bg-red-50 text-red-700 border border-red-200 hover:bg-red-50 px-3 py-1.5">
                      <AlertCircle className="h-3.5 w-3.5" />
                      {phase.name} 异常
                    </Badge>
                  );
                }
                return (
                  <Badge key={phase.name} className="gap-1.5 bg-gray-50 text-gray-500 border border-gray-200 hover:bg-gray-50 px-3 py-1.5">
                    <PhaseIcon className="h-3.5 w-3.5" />
                    {phase.name} 未执行
                  </Badge>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* 1. 版本指标对比 */}
        <Card className="mb-4 border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">版本指标对比</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">版本</th>
                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">AUC</th>
                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">KS</th>
                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">F1</th>
                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">PSI</th>
                    <th className="text-right py-2 px-3 font-medium text-muted-foreground">变化</th>
                  </tr>
                </thead>
                <tbody>
                  {[...model.versions].reverse().map((ver, idx) => {
                    const prev = idx < ([...model.versions].reverse().length - 1) ? [...model.versions].reverse()[idx + 1] : null;
                    const aucDiff = prev ? ver.metrics.auc - prev.metrics.auc : 0;
                    const ksDiff = prev ? ver.metrics.ks - prev.metrics.ks : 0;
                    const f1Diff = prev ? ((ver.metrics.f1 || 0) - (prev.metrics.f1 || 0)) : 0;
                    return (
                      <tr key={ver.version} className={`border-b border-border/50 ${ver.version === activeVersion.version ? 'bg-primary/5' : ''}`}>
                        <td className="py-2 px-3 font-medium">
                          <button
                            type="button"
                            onClick={() => setActiveVersionIdx(model.versions.findIndex(v => v.version === ver.version))}
                            className={`inline-flex items-center gap-1.5 ${ver.version === activeVersion.version ? 'text-primary' : 'text-foreground hover:text-primary'}`}
                          >
                            {ver.version}
                            {ver.version === activeVersion.version && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
                          </button>
                        </td>
                        <td className="text-right py-2 px-3 font-mono">{ver.metrics.auc.toFixed(3)}</td>
                        <td className="text-right py-2 px-3 font-mono">{ver.metrics.ks.toFixed(3)}</td>
                        <td className="text-right py-2 px-3 font-mono">{(ver.metrics.f1 || 0).toFixed(3)}</td>
                        <td className="text-right py-2 px-3 font-mono">{(ver.metrics.psi || 0).toFixed(3)}</td>
                        <td className="text-right py-2 px-3">
                          {prev ? (
                            <div className="flex items-center justify-end gap-2">
                              <span className={aucDiff >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                                AUC {aucDiff >= 0 ? '+' : ''}{aucDiff.toFixed(3)}
                              </span>
                              <span className={ksDiff >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                                KS {ksDiff >= 0 ? '+' : ''}{ksDiff.toFixed(3)}
                              </span>
                              <span className={f1Diff >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                                F1 {f1Diff >= 0 ? '+' : ''}{f1Diff.toFixed(3)}
                              </span>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* 2 & 3. ROC 曲线 + KS 曲线 (并排) */}
        <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">ROC 曲线</CardTitle>
            </CardHeader>
            <CardContent>
              <ROCCurveChart
                data={activeVizData?.roc_curve}
                aucValue={activeMetrics.auc}
                height={280}
              />
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">KS 曲线</CardTitle>
            </CardHeader>
            <CardContent>
              <KSCurveChart
                data={activeVizData?.ks_curve}
                ksValue={activeMetrics.ks}
                height={280}
              />
            </CardContent>
          </Card>
        </div>

        {/* 4. 混淆矩阵 + 风控策略对比（并排） */}
        <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">混淆矩阵</CardTitle>
                {activeVizData?.confusion_matrix && (
                  <span className="text-[11px] text-muted-foreground">阈值 = {activeVizData.confusion_matrix.threshold}</span>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <ConfusionMatrixChart data={activeVizData?.confusion_matrix} height={280} />
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">风控策略对比</CardTitle>
                <span className="text-[11px] text-muted-foreground">模型 vs 单特征规则</span>
              </div>
            </CardHeader>
            <CardContent>
              <StrategyCompareChart data={activeVizData?.strategy_data} height={280} />
            </CardContent>
          </Card>
        </div>

        {/* 5. 具体指标表 */}
        <Card className="mb-4 border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">具体指标表</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2.5 px-3 font-medium text-muted-foreground w-1/4">指标</th>
                    <th className="text-right py-2.5 px-3 font-medium text-muted-foreground">数值</th>
                    <th className="text-left py-2.5 px-3 font-medium text-muted-foreground">说明</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { name: 'AUC', value: activeMetrics.auc.toFixed(4), desc: 'ROC 曲线下面积，衡量模型整体区分能力，越接近 1 越好' },
                    { name: 'KS', value: activeMetrics.ks.toFixed(4), desc: 'Kolmogorov-Smirnov 统计量，衡量好坏样本分布最大间距，{" > "}0.2 可用' },
                    { name: 'F1 Score', value: (activeMetrics.f1 || 0).toFixed(4), desc: '精确率与召回率的调和平均数，综合衡量分类性能' },
                    { name: 'Accuracy', value: (activeMetrics.accuracy || 0).toFixed(4), desc: '预测正确的样本占总样本比例' },
                    { name: 'Precision', value: (activeMetrics.precision || 0).toFixed(4), desc: '预测为正的样本中实际为正的比例，影响误报率' },
                    { name: 'Recall', value: (activeMetrics.recall || 0).toFixed(4), desc: '实际为正的样本中被正确预测的比例，影响漏报率' },
                    { name: 'PSI', value: (activeMetrics.psi || 0).toFixed(4), desc: '群体稳定性指标，{" < "}0.1 稳定，0.1~0.25 需关注，{" > "}0.25 不稳定' },
                    { name: 'Log Loss', value: (activeMetrics.log_loss || 0).toFixed(4), desc: '对数损失，衡量预测概率与真实标签的偏差，越低越好' },
                  ].map((row) => (
                    <tr key={row.name} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2.5 px-3 font-medium">{row.name}</td>
                      <td className="text-right py-2.5 px-3 font-mono">{row.value}</td>
                      <td className="py-2.5 px-3 text-muted-foreground text-xs">{row.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* 6. 特征重要性 */}
        <Card className="mb-4 border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">特征重要性</CardTitle>
          </CardHeader>
          <CardContent>
            <FeatureImportanceChart
              features={activeVizData?.feature_importance || []}
              height={350}
            />
          </CardContent>
        </Card>


      </main>
    </div>
  );
}
