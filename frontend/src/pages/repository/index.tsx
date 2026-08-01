
import { useState, useMemo, useEffect } from 'react';
import {
  Card,
  CardContent,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Package,
  Search,
  Upload,
  Play,
  Rocket,
  Square,
  Eye,
  TrendingUp,
  Download,
  Tag,
  FileText,
  CheckCircle2,
  Archive,
  Clock,
  ArrowUpDown,
  LayoutGrid,
  List,
  Trash2,
  Loader2,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { formatNumber, type ModelItem, type ModelVersion, demoModels } from '@/lib/demo-data';
import { ColumnFilter } from '@/components/column-filter';
import { api } from '@/lib/api-client';
import { toast } from 'sonner';

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { className: string }> = {
    running: { className: 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100 border-emerald-200' },
    stopped: { className: 'bg-gray-100 text-gray-600 hover:bg-gray-100 border-gray-200' },
    error: { className: 'bg-red-100 text-red-700 hover:bg-red-100 border-red-200' },
    deploying: { className: 'bg-amber-100 text-amber-700 hover:bg-amber-100 border-amber-200' },
  };
  const labels: Record<string, string> = { running: '运行中', stopped: '已停止', error: '异常', deploying: '部署中' };
  const c = config[status] || config.stopped;

  return <Badge variant="outline" className={c.className}>{labels[status] || status}</Badge>;
}

function VersionBadge({ versionStatus }: { versionStatus: string }) {
  if (versionStatus === 'current') return <Badge className="bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-100 text-[10px] px-1.5 py-0">最新</Badge>;
  if (versionStatus === 'deprecated') return <Badge className="bg-red-50 text-red-500 border-red-200 hover:bg-red-50 text-[10px] px-1.5 py-0">已弃用</Badge>;
  return <Badge className="bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-100 text-[10px] px-1.5 py-0">归档</Badge>;
}

function DownloadDialog({ modelName, artifacts }: { modelName: string; artifacts: string[] }) {
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleDownload = (fileName: string) => {
    setDownloading(fileName);
    setTimeout(() => setDownloading(null), 1500);
  };

  const fileTypeMap: Record<string, { label: string; desc: string }> = {
    'model.pkl': { label: 'Pickle 模型', desc: 'sklearn 原生格式，可直接 load' },
    'model.onnx': { label: 'ONNX 模型', desc: '跨平台推理格式，高性能部署' },
    'schema.json': { label: '推理 Schema', desc: '输入/输出字段定义' },
    'features.json': { label: '特征定义', desc: '特征列表与预处理参数' },
    'features_ordered.json': { label: '有序特征定义', desc: '按重要性排序的特征列表' },
    'eval_report.pdf': { label: '评估报告', desc: '完整模型评估报告文档' },
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 shrink-0 border-blue-200 text-blue-600 hover:bg-blue-50 hover:text-blue-700 transition-all"
          onClick={(e) => e.stopPropagation()}
        >
          <Download className="h-3.5 w-3.5" />
          下载
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5 text-blue-600" />
            下载模型文件
          </DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <p className="text-sm text-muted-foreground mb-3">
            选择要下载的文件（模型: <span className="font-medium text-foreground">{modelName}</span>）
          </p>
          <div className="space-y-2">
            {artifacts.map((name) => {
              const info = fileTypeMap[name] || { label: name, desc: '' };
              return (
                <div
                  key={name}
                  className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2.5 hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="h-4 w-4 text-blue-400 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{name}</p>
                      <p className="text-xs text-muted-foreground">{info.desc}</p>
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
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    ) : (
                      <Download className="h-3.5 w-3.5" />
                    )}
                    {downloading === name ? '完成' : '下载'}
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

type SortKey = 'updatedAt' | 'downloadCount' | 'metrics.auc' | 'name';
type ViewMode = 'card' | 'table';

export default function RepositoryPage() {
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sceneFilter, setSceneFilter] = useState('all');
  const [versionFilter, setVersionFilter] = useState('all');
  const [sortKey, setSortKey] = useState<SortKey>('updatedAt');
  const [sortAsc, setSortAsc] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const navigate = useNavigate();
  const [models, setModels] = useState<ModelItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deployingId, setDeployingId] = useState<string | null>(null);
  const [usingDemoData, setUsingDemoData] = useState(false);

  const handleDeploy = async (modelId: string) => {
    setDeployingId(modelId);
    try {
      if (usingDemoData) {
        toast.info('当前展示的是演示仓库数据，已为您跳转到模型服务页查看示例部署');
        navigate('/service');
        return;
      }
      const versionData = await api.modelsDeploy.versions(Number(modelId));
      const versionItems = versionData?.items || [];
      if (versionItems.length === 0) {
        alert('该模型没有可用版本，无法部署');
        return;
      }
      const versionId = versionItems[0].model_version_id;
      await api.services.create(Number(versionId));
      navigate('/service');
    } catch (err) {
      alert('部署失败: ' + (err instanceof Error ? err.message : '网络错误'));
    } finally {
      setDeployingId(null);
    }
  };

  // 删除模型
  const handleDeleteModel = async (modelId: string, modelName: string) => {
    if (!confirm(`确定要删除模型「${modelName}」吗？\n\n删除后将同时清除该模型的所有版本、评估数据、服务实例和关联的物理文件，且不可恢复。`)) return;
    setDeletingId(modelId);
    try {
      await api.modelsDeploy.delete(Number(modelId));
      setModels((prev) => prev.filter((m) => m.id !== modelId));
      // 通知任务页面：该模型对应的任务不再入库
      window.dispatchEvent(new CustomEvent('repository:model-deleted', { detail: { modelId } }));
      toast.success('模型已删除', { description: `已删除模型「${modelName}」及关联数据` });
    } catch (err) {
      console.error('Failed to delete model:', err);
      toast.error('删除模型失败', { description: String(err) });
    } finally {
      setDeletingId(null);
    }
  };

  // Load real models from backend
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const backendModels = await api.modelsDeploy.list();
        if (cancelled) return;
        const modelsList = backendModels?.items || [];

        // Map models without version data first (fast render)
        setUsingDemoData(false);

        const mapped: ModelItem[] = modelsList.map((m: any) => ({
          id: String(m.model_id),
          name: String(m.name || '未命名模型'),
          modelType: String(m.model_type || 'sklearn'),
          framework: String(m.model_type || 'sklearn'),
          status: 'running' as ModelItem['status'],
          sceneName: String(m.scene_name || '通用'),
          version: '1.0v',
          createdAt: String(m.createdAt || m.created_at || ''),
          updatedAt: String(m.createdAt || m.created_at || ''),
          sampleCount: 0,
          featuresCount: 0,
          metrics: { accuracy: 0, precision: 0, recall: 0, f1: 0, auc: 0, pr_auc: 0, log_loss: 0, top_k: 0, ks: 0, psi: 0 },
          artifacts: [],
          tags: [String(m.scene_name || '通用'), String(m.model_type || 'sklearn')],
          versions: [{ version: '1.0v', createdAt: String(m.createdAt || m.created_at || ''), status: 'current' as ModelVersion['status'], metrics: { auc: 0, ks: 0, f1: 0, precision: 0, recall: 0, accuracy: 0 }, artifacts: [], changelog: '', downloadCount: 0, fileSize: '-' }],
          downloadCount: 0,
          description: String(m.description || ''),
        } as unknown as ModelItem));
        setModels(mapped);

        // Fetch version info for all models in batches of 5
        for (let batchStart = 0; batchStart < modelsList.length; batchStart += 5) {
          if (cancelled) return;
          const batch = modelsList.slice(batchStart, batchStart + 5);
          const versionPromises = batch.map(async (m: any) => {
            try {
              const versionData = await api.modelsDeploy.versions(Number(m.model_id));
              const versions = versionData?.items || [];
              if (versions.length > 0) {
                const latest = versions[0] as any;
                const vMetrics = (latest.metrics || {}) as Record<string, number>;
                // 补充从 evaluation 接口获取指标
                let evalMetrics: Record<string, number> = {};
                try {
                  const evalData = await api.modelsDeploy.versionEvaluation(Number(latest.model_version_id)) as any;
                  if (evalData?.metrics_data) evalMetrics = evalData.metrics_data as Record<string, number>;
                } catch { /* no evaluation yet */ }
                return {
                  modelId: String(m.model_id),
                  versionTag: String(latest.version_tag || '1.0v'),
                  parserStatus: String(latest.parser_status || 'completed'),
                  auc: evalMetrics.auc || vMetrics.auc || vMetrics.roc_auc || 0,
                  ks: evalMetrics.ks || vMetrics.ks || 0,
                  f1: evalMetrics.f1 || evalMetrics.f1_score || vMetrics.f1 || vMetrics.f1_score || 0,
                  precision: evalMetrics.precision || vMetrics.precision || 0,
                  recall: evalMetrics.recall || vMetrics.recall || 0,
                  accuracy: evalMetrics.accuracy || vMetrics.accuracy || 0,
                };
              }
            } catch { /* skip */ }
            return null;
          });
          const results = await Promise.all(versionPromises);
          if (cancelled) return;

          // Merge version data into models
          setModels(prev => {
            const updated = [...prev];
            for (const r of results) {
              if (!r) continue;
              const idx = updated.findIndex(m => m.id === r.modelId);
              if (idx >= 0) {
                updated[idx] = {
                  ...updated[idx],
                  status: (r.parserStatus === 'completed' || r.parserStatus === 'parsed') ? 'running' : 'stopped',
                  version: r.versionTag,
                  metrics: { ...updated[idx].metrics, auc: r.auc ?? 0, ks: r.ks ?? 0, f1: r.f1 ?? 0, precision: r.precision ?? 0, recall: r.recall ?? 0, accuracy: r.accuracy ?? 0, pr_auc: 0, log_loss: 0, top_k: 0, psi: 0 },
                  versions: [{
                    version: r.versionTag,
                    createdAt: updated[idx].createdAt,
                    status: 'current' as ModelVersion['status'],
                    metrics: { auc: r.auc ?? 0, ks: r.ks ?? 0, f1: r.f1 ?? 0, precision: r.precision ?? 0, recall: r.recall ?? 0, accuracy: r.accuracy ?? 0, pr_auc: 0, log_loss: 0, top_k: 0, psi: 0 },
                    artifacts: [],
                    changelog: '',
                    downloadCount: 0,
                    fileSize: '-',
                  }],
                };
              }
            }
            return updated;
          });
        }
      } catch (err) {
        console.error('Failed to load models from backend:', err);
        if (!cancelled) {
          setUsingDemoData(false);
          setModels([]); // 不使用 demoModels，而是显示空状态
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const scenes = useMemo(() => [...new Set(models.map((m) => m.sceneName))], [models]);
  const uniqueModels = useMemo(() => {
    const byName = new Map<string, ModelItem>();
    for (const model of models) {
      const key = model.name.trim().toLowerCase();
      const existing = byName.get(key);
      if (!existing) {
        byName.set(key, model);
        continue;
      }
      const existingScore = (existing.metrics.auc > 0 ? 4 : 0) + (existing.artifacts.length > 0 ? 2 : 0) + Number(existing.id);
      const nextScore = (model.metrics.auc > 0 ? 4 : 0) + (model.artifacts.length > 0 ? 2 : 0) + Number(model.id);
      if (nextScore > existingScore) byName.set(key, model);
    }
    return Array.from(byName.values());
  }, [models]);

  const filteredModels = useMemo(() => {
    const result = uniqueModels.filter((m) => {
      const matchKw = !keyword || m.name.toLowerCase().includes(keyword.toLowerCase()) || m.sceneName.toLowerCase().includes(keyword.toLowerCase()) || m.tags.some((t) => t.toLowerCase().includes(keyword.toLowerCase()));
      const matchStatus = statusFilter === 'all' || m.status === statusFilter;
      const matchScene = sceneFilter === 'all' || m.sceneName === sceneFilter;
      const matchVersion = versionFilter === 'all' ||
        (versionFilter === 'multi' && m.versions.length > 1) ||
        (versionFilter === 'single' && m.versions.length === 1);
      const matchColumnStatus = !columnFilters.status || m.status === columnFilters.status;
      const matchColumnScene = !columnFilters.scene || m.sceneName === columnFilters.scene;
      return matchKw && matchStatus && matchScene && matchVersion && matchColumnStatus && matchColumnScene;
    });

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'updatedAt': cmp = new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime(); break;
        case 'downloadCount': cmp = a.downloadCount - b.downloadCount; break;
        case 'metrics.auc': cmp = a.metrics.auc - b.metrics.auc; break;
        case 'name': cmp = a.name.localeCompare(b.name, 'zh'); break;
      }
      return sortAsc ? cmp : -cmp;
    });

    return result;
  }, [uniqueModels, keyword, statusFilter, sceneFilter, versionFilter, sortKey, sortAsc, columnFilters]);

  const total = uniqueModels.length;
  const running = uniqueModels.filter((m) => m.status === 'running').length;
  const stopped = uniqueModels.filter((m) => m.status === 'stopped').length;
  const errorCount = uniqueModels.filter((m) => m.status === 'error').length;
  const totalDownloads = uniqueModels.reduce((a, m) => a + m.downloadCount, 0);
  const avgAuc = uniqueModels.filter((m) => m.metrics.auc > 0).length > 0
    ? uniqueModels.filter((m) => m.metrics.auc > 0).reduce((a, m) => a + m.metrics.auc, 0) / uniqueModels.filter((m) => m.metrics.auc > 0).length
    : 0;

  const kpis = [
    { title: '仓库模型', value: total, subtitle: '真实模型总数', icon: Package, color: 'text-blue-600', bg: 'bg-blue-50' },
    { title: '运行中', value: running, subtitle: `占比 ${total ? Math.round((running / total) * 100) : 0}%`, icon: Play, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { title: '已下线', value: stopped, subtitle: `含异常 ${errorCount}`, icon: Square, color: 'text-gray-600', bg: 'bg-gray-50' },
    { title: '总下载量', value: formatNumber(totalDownloads), subtitle: '真实累计值', icon: Download, color: 'text-violet-600', bg: 'bg-violet-50' },
    { title: '平均 AUC', value: formatNumber(avgAuc), subtitle: '真实评估均值', icon: TrendingUp, color: 'text-amber-600', bg: 'bg-amber-50' },
  ];

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto max-w-[1440px] px-6 py-6">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">模型仓库</h1>
            <p className="mt-1 text-sm text-muted-foreground">集中管理训练和部署的所有模型，支持版本迭代与下载分发</p>
          </div>
          <Link to="/copilot">
            <Button className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700">
              <Upload className="h-4 w-4" /> 新建模型
            </Button>
          </Link>
        </div>

        {/* KPI Cards */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {kpis.map((kpi) => (
            <Card key={kpi.title} className="border-border/60 transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="p-4">
                <div className="flex items-center gap-2">
                  <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${kpi.bg}`}>
                    <kpi.icon className={`h-4 w-4 ${kpi.color}`} />
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">{kpi.title}</span>
                </div>
                <p className="mt-2 text-2xl font-bold tracking-tight">{kpi.value}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{kpi.subtitle}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filters */}
        <Card className="mb-4 border-border/60">
          <CardContent className="flex flex-wrap items-center gap-3 p-4">
            <div className="relative flex-1" style={{ minWidth: 220 }}>
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索模型名称、标签、场景"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="running">运行中</SelectItem>
                <SelectItem value="stopped">已停止</SelectItem>
                <SelectItem value="error">异常</SelectItem>
                <SelectItem value="deploying">部署中</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sceneFilter} onValueChange={setSceneFilter}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="全部场景" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部场景</SelectItem>
                {scenes.map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={versionFilter} onValueChange={setVersionFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="版本筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部版本</SelectItem>
                <SelectItem value="multi">多版本模型</SelectItem>
                <SelectItem value="single">单版本模型</SelectItem>
              </SelectContent>
            </Select>
            <div className="flex items-center gap-1 ml-auto">
              <Button
                variant={viewMode === 'card' ? 'default' : 'ghost'}
                size="sm"
                className="gap-1"
                onClick={() => setViewMode('card')}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant={viewMode === 'table' ? 'default' : 'ghost'}
                size="sm"
                className="gap-1"
                onClick={() => setViewMode('table')}
              >
                <List className="h-3.5 w-3.5" />
              </Button>
              <div className="w-px h-5 bg-border/60 mx-1" />
              <Button variant="outline" size="sm" onClick={() => { setKeyword(''); setStatusFilter('all'); setSceneFilter('all'); setVersionFilter('all'); }}>
                重置
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Sort bar */}
        <div className="mb-3 flex items-center gap-4 text-xs text-muted-foreground">
          <span>共 {filteredModels.length} 个模型</span>
          <button onClick={() => toggleSort('updatedAt')} className={`flex items-center gap-1 transition-colors ${sortKey === 'updatedAt' ? 'text-blue-600 font-medium' : 'hover:text-foreground'}`}>
            <Clock className="h-3 w-3" /> 更新时间
            {sortKey === 'updatedAt' && <ArrowUpDown className="h-3 w-3" />}
          </button>
          <button onClick={() => toggleSort('downloadCount')} className={`flex items-center gap-1 transition-colors ${sortKey === 'downloadCount' ? 'text-blue-600 font-medium' : 'hover:text-foreground'}`}>
            <Download className="h-3 w-3" /> 下载量
            {sortKey === 'downloadCount' && <ArrowUpDown className="h-3 w-3" />}
          </button>
          <button onClick={() => toggleSort('metrics.auc')} className={`flex items-center gap-1 transition-colors ${sortKey === 'metrics.auc' ? 'text-blue-600 font-medium' : 'hover:text-foreground'}`}>
            <TrendingUp className="h-3 w-3" /> AUC
            {sortKey === 'metrics.auc' && <ArrowUpDown className="h-3 w-3" />}
          </button>
        </div>

        {/* Card View */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Package className="h-8 w-8 animate-pulse mb-3" />
            <p className="text-sm">加载模型仓库...</p>
          </div>
        ) : viewMode === 'card' && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredModels.map((model) => {
              const archivedCount = model.versions.filter((v) => v.status === 'archived').length;
              return (
                <Card key={model.id} className="border-border/60 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 group">
                  <CardContent className="p-5">
                    {/* Header: Name + Status */}
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div className="min-w-0 flex-1">
                        <Link to={`/repository/${model.id}`} className="text-base font-semibold text-foreground hover:text-blue-600 transition-colors line-clamp-1">
                          {model.name}
                        </Link>
                        <div className="mt-1 flex items-center gap-2">
                          <StatusBadge status={model.status} />
                          <span className="text-xs text-muted-foreground">{model.modelType}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <DownloadDialog modelName={model.name} artifacts={model.artifacts} />
                        <Button
                          variant="outline" size="sm" className="gap-1"
                          disabled={deployingId === model.id}
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDeploy(model.id); }}
                        >
                          <Rocket className="h-3.5 w-3.5" /> {deployingId === model.id ? '部署中...' : '部署'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="gap-1 text-red-500 hover:text-red-700 hover:bg-red-50"
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDeleteModel(model.id, model.name); }}
                          disabled={deletingId === model.id}
                        >
                          {deletingId === model.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    </div>

                    {/* Version Tabs */}
                    <div className="mb-3 flex items-center gap-1.5 flex-wrap">
                      {model.versions.slice(0, 3).map((v) => (
                        <div key={v.version} className="flex items-center gap-1">
                          <Badge variant="outline" className={`text-[11px] font-mono ${
                            v.status === 'current' ? 'border-blue-300 text-blue-600 bg-blue-50' :
                            v.status === 'deprecated' ? 'border-red-200 text-red-400 bg-red-50' :
                            'border-gray-200 text-gray-500 bg-gray-50'
                          }`}>
                            {v.version}
                          </Badge>
                          <VersionBadge versionStatus={v.status} />
                        </div>
                      ))}
                      {model.versions.length > 3 && (
                        <Badge variant="outline" className="text-[11px] text-gray-400">+{model.versions.length - 3}</Badge>
                      )}
                    </div>

                    {/* Scene & Framework */}
                    <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1"><Tag className="h-3 w-3" />{model.sceneName}</span>
                      <span>·</span>
                      <span>{model.framework}</span>
                    </div>

                    {/* Tags */}
                    <div className="mb-3 flex flex-wrap gap-1">
                      {model.tags.map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0 bg-blue-50 text-blue-600 hover:bg-blue-100">
                          {tag}
                        </Badge>
                      ))}
                    </div>

                    {/* Metrics preview */}
                    <div className="grid grid-cols-3 gap-2 mb-3">
                      {[
                        { label: 'AUC', value: model.metrics.auc },
                        { label: 'Recall', value: model.metrics.recall },
                        { label: 'F1', value: model.metrics.f1 },
                      ].map((m) => (
                        <div key={m.label} className="rounded-md bg-gray-50 px-2 py-1.5 text-center">
                          <p className="text-[10px] text-muted-foreground">{m.label}</p>
                          <p className="text-sm font-semibold font-mono">{m.value > 0 ? formatNumber(m.value) : '-'}</p>
                        </div>
                      ))}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/40">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <Download className="h-3 w-3" /> {model.downloadCount.toLocaleString()}
                        </span>
                        <span className="flex items-center gap-1">
                          <Archive className="h-3 w-3" /> {archivedCount} 归档
                        </span>
                      </div>
                      <span>{new Date(model.updatedAt).toLocaleDateString('zh-CN')}</span>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
            {filteredModels.length === 0 && (
              <div className="col-span-full flex flex-col items-center justify-center py-16 text-muted-foreground">
                <Package className="h-10 w-10 mb-3" />
                <p className="text-sm">暂无匹配的模型</p>
              </div>
            )}
          </div>
        )}

        {/* Table View */}
        {viewMode === 'table' && (
          <Card className="border-border/60">
            <div className="overflow-x-auto">
              <table className="w-full caption-bottom text-sm">
                <thead className="[&_tr]:border-b">
                  <tr className="border-b transition-colors hover:bg-muted/50">
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">模型名称</th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">版本</th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                      <ColumnFilter options={[...new Set(models.map((m: ModelItem) => m.sceneName))].map(s => ({ label: String(s), value: String(s) }))} selectedValues={columnFilters.scene ? [columnFilters.scene] : []} onFilterChange={(v: string[]) => setColumnFilters(prev => ({ ...prev, scene: v[0] ?? '' }))} />
                    </th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                      <ColumnFilter options={[...new Set(models.map((m: ModelItem) => m.status))].map(s => ({ label: String(s), value: String(s) }))} selectedValues={columnFilters.status ? [columnFilters.status] : []} onFilterChange={(v: string[]) => setColumnFilters(prev => ({ ...prev, status: v[0] ?? '' }))} />
                    </th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">AUC</th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">Recall</th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">下载量</th>
                    <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">更新时间</th>
                    <th className="h-10 px-4 text-right align-middle font-medium text-muted-foreground">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredModels.map((model) => (
                    <tr key={model.id} className="group border-b transition-colors hover:bg-muted/50">
                      <td className="p-4 align-middle">
                        <Link to={`/repository/${model.id}`} className="flex items-center gap-2 font-medium text-blue-600 hover:text-blue-800 transition-colors">
                          <Package className="h-4 w-4 text-blue-400 shrink-0" />
                          <span className="truncate max-w-[200px]">{model.name}</span>
                        </Link>
                        <div className="mt-1 flex gap-1">
                          {model.tags.slice(0, 3).map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-[10px] px-1 py-0 bg-blue-50 text-blue-600">{tag}</Badge>
                          ))}
                        </div>
                      </td>
                      <td className="p-4 align-middle">
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-[11px] font-mono border-blue-300 text-blue-600 bg-blue-50">
                            {model.versions[0]?.version}
                          </Badge>
                          {model.versions.length > 1 && (
                            <span className="text-xs text-muted-foreground">({model.versions.length}版本)</span>
                          )}
                        </div>
                      </td>
                      <td className="p-4 align-middle text-muted-foreground text-sm">{model.sceneName}</td>
                      <td className="p-4 align-middle"><StatusBadge status={model.status} /></td>
                      <td className="p-4 align-middle font-mono text-sm">{model.metrics.auc > 0 ? formatNumber(model.metrics.auc) : '-'}</td>
                      <td className="p-4 align-middle font-mono text-sm">{model.metrics.recall > 0 ? formatNumber(model.metrics.recall) : '-'}</td>
                      <td className="p-4 align-middle text-sm">
                        <span className="flex items-center gap-1"><Download className="h-3 w-3 text-muted-foreground" />{model.downloadCount.toLocaleString()}</span>
                      </td>
                      <td className="p-4 align-middle text-muted-foreground text-xs">
                        {new Date(model.updatedAt).toLocaleDateString('zh-CN')}
                      </td>
                      <td className="p-4 align-middle text-right">
                        <div className="flex items-center justify-end gap-1">
                          <DownloadDialog modelName={model.name} artifacts={model.artifacts} />
                          <Button
                            variant="outline" size="sm" className="gap-1"
                            disabled={deployingId === model.id}
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDeploy(model.id); }}
                          >
                            <Rocket className="h-3.5 w-3.5" /> {deployingId === model.id ? '部署中...' : '部署'}
                          </Button>
                          <Link to={`/repository/${model.id}`}>
                            <Button variant="ghost" size="sm" className="gap-1">
                              <Eye className="h-3.5 w-3.5" /> 详情
                            </Button>
                          </Link>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="gap-1 text-red-500 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDeleteModel(model.id, model.name)}
                            disabled={deletingId === model.id}
                          >
                            {deletingId === model.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredModels.length === 0 && (
                    <tr>
                      <td colSpan={9} className="h-24 text-center text-muted-foreground">
                        暂无匹配的模型
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}
