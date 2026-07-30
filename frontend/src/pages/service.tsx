
import { useState, useMemo, useEffect, Suspense, Fragment } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Server,
  Package,
  RefreshCw,
  Play,
  PowerOff,
  Copy,
  CheckCircle2,
  Loader2,
  AlertCircle,
  X,
  ChevronRight,
  Rocket,
  CircleDot,
  Layers,
  Cpu,
  Zap,
  ArrowUpFromLine,
  ArrowDownFromLine,
  AlertTriangle,
  Search,
  Filter,
  ArrowRight,
  Terminal,
  Info,
  Activity,
  Clock,
} from 'lucide-react';
import { type ModelServiceRecord, demoServiceRecords, formatDate } from '@/lib/demo-data';
import { AnimatedNumber } from '@/components/animated-ui';
import { api } from '@/lib/api-client';
import {
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';
import { toast } from 'sonner';

// Performance data — deterministic (no Math.random)

function StatusDot({ status }: { status: string }) {
  const config: Record<string, { color: string; pulse: boolean }> = {
    running: { color: 'bg-emerald-500', pulse: true },
    deploying: { color: 'bg-blue-500', pulse: true },
    stopped: { color: 'bg-gray-400', pulse: false },
    error: { color: 'bg-red-500', pulse: false },
  };
  const c = config[status] || config.stopped;
  return (
    <div className={`h-2.5 w-2.5 rounded-full ${c.color} ${c.pulse ? 'animate-pulse' : ''}`} />
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    running: { label: '运行中', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    deploying: { label: '部署中', className: 'bg-blue-50 text-blue-700 border-blue-200' },
    stopped: { label: '已停止', className: 'bg-gray-50 text-gray-600 border-gray-200' },
    error: { label: '异常', className: 'bg-red-50 text-red-700 border-red-200' },
  };
  const c = map[status] || map.stopped;
  return (
    <Badge variant="outline" className={`gap-1 text-xs ${c.className}`}>
      <StatusDot status={status} />
      {c.label}
    </Badge>
  );
}

export default function ServicePage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>}>
      <ServicePageContent />
    </Suspense>
  );
}

function ServicePageContent() {
  const [searchParams] = useSearchParams();
  const idFromUrl = searchParams.get('id');

  const [services, setServices] = useState<ModelServiceRecord[]>([]);
  const [loadingServices, setLoadingServices] = useState(true);
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(idFromUrl || null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [inferenceTestOpen, setInferenceTestOpen] = useState(false);
  const [testInput, setTestInput] = useState('');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  // Load real service instances from backend
  useEffect(() => {
    (async () => {
      try {
        const instancesData = await api.services.list();
        const instances = instancesData?.items || [];
        // Enrich with model name
        const enriched = await Promise.all(instances.map(async (svc: any) => {
          let modelName = '未知模型';
          let modelSlug = 'unknown';
          let modelId = '';
          let modelVersionId = String(svc.model_version_id || svc.modelVersionId || '');
          let version = '1.0.0';
          let scene = '通用';
          let framework = 'sklearn';
          try {
            const versionData = await api.modelsDeploy.getVersion(Number(svc.model_version_id || svc.modelVersionId)) as any;
            modelVersionId = String(versionData.model_version_id || versionData.modelVersionId || modelVersionId);
            version = String(versionData.version_tag || versionData.version || '1.0.0');
            if (versionData.model_id || versionData.modelId) {
              modelId = String(versionData.model_id || versionData.modelId || '');
              const modelData = await api.modelsDeploy.get(Number(versionData.model_id || versionData.modelId)) as any;
              modelName = String(modelData.name || '未知模型');
              scene = String(modelData.scene_name || modelData.scene || '通用');
              framework = String(modelData.model_type || modelData.type || 'sklearn');
              modelSlug = modelName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
            }
          } catch { /* ignore */ }

          return {
            id: String(svc.model_service_id || svc.id || ''),
            modelName,
            modelId,
            modelVersionId,
            modelSlug,
            version,
            scene,
            framework,
            status: (svc.status === 'running' ? 'running' : svc.status === 'deploying' ? 'deploying' : svc.status === 'error' ? 'error' : 'stopped') as ModelServiceRecord['status'],
            environment: 'production' as const,
            instances: 1,
            gpu: '-',
            qps: 0,
            latency: 0,
            latencyMs: Number(svc.avg_latency_ms || svc.avgLatencyMs || 0),
            errorRate: 0,
            apiEndpoint: String(svc.endpoint || ''),
            serverInfo: 'default',
            resourceQuota: '1 CPU / 2GB',
            hourlySuccessRate: '99.9%',
            apiInput: JSON.stringify({input_data: {features: {feature_1: 0.0, feature_2: 0.0}}, parameters: {threshold: 0.5}}, null, 2),
            apiOutput: JSON.stringify({prediction: {label: 0, probability: 0.12, risk_level: 'low'}, model_version: version || 'v1.0'}, null, 2),
            createdAt: String(svc.created_at || svc.createdAt || ''),
            updatedAt: String(svc.created_at || svc.createdAt || ''),
            requestCount: Number(svc.request_count || svc.requestCount || 0),
            lastRequestAt: String(svc.last_request_at || svc.lastRequestAt || ''),
          } as unknown as ModelServiceRecord;
        }));
        setServices(enriched);
      } catch (err) {
        console.error('Failed to load services from backend:', err);
        setServices([]); // 不使用 demoServiceRecords，而是显示空状态
      } finally {
        setLoadingServices(false);
      }
    })();
  }, []);
  const [deployingId, setDeployingId] = useState<string | null>(null);
  const [showApiGuide, setShowApiGuide] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [startingId, setStartingId] = useState<string | null>(null);
  const [dynamicApiInput, setDynamicApiInput] = useState<string | null>(null);

  // Computed stats
  const runningCount = services.filter((s) => s.status === 'running').length;
  const stoppedCount = services.filter((s) => s.status === 'stopped').length;
  const errorCount = services.filter((s) => s.status === 'error').length;
  const deployingCount = services.filter((s) => s.status === 'deploying').length;
  const totalRequests = services.reduce((sum, s) => sum + (s.requestCount || 0), 0);


  // Filtered services
  const filteredServices = useMemo(() => {
    let result = services;

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((s) =>
        s.modelName.toLowerCase().includes(q) ||
        s.scene.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        s.framework.toLowerCase().includes(q) ||
        s.tags.some((t) => t.toLowerCase().includes(q)) ||
        s.version.toLowerCase().includes(q) ||
        s.apiEndpoint.toLowerCase().includes(q) ||
        s.modelSlug.toLowerCase().includes(q)
      );
    }

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((s) => s.status === statusFilter);
    }

    return result;
  }, [services, searchQuery, statusFilter]);

  // Group services by modelId
  const groupedServices = useMemo(() => {
    const groups = new Map<string, ModelServiceRecord[]>();
    for (const svc of filteredServices) {
      const key = svc.modelId;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(svc);
    }
    return groups;
  }, [filteredServices]);

  const toggleGroup = (modelId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  };

  const selectedService = selectedServiceId ? services.find((s) => s.id === selectedServiceId) : null;

  // 选中服务时，根据 schema 动态生成输入 JSON 示例
  useEffect(() => {
    if (!selectedService) { setDynamicApiInput(null); return; }
    const mvId = Number((selectedService as any).modelVersionId);
    if (!mvId) { setDynamicApiInput(null); return; }
    (async () => {
      try {
        const vd = await api.modelsDeploy.getVersion(mvId) as any;
        const features: any[] = vd?.schema_json?.features || [];
        if (features.length === 0) { setDynamicApiInput(null); return; }
        const example: Record<string, unknown> = {};
        for (const f of features) {
          const name = String(f.name || f.feature_name || '');
          if (!name) continue;
          const dtype = String(f.dtype || f.type || 'float');
          if (dtype === 'int') example[name] = 0;
          else if (dtype === 'bool') example[name] = false;
          else if (dtype === 'string') example[name] = '';
          else if (dtype === 'datetime') example[name] = '2024-01-01T00:00:00';
          else example[name] = 0.0;
        }
        const generated = JSON.stringify({ features: example }, null, 2);
        setDynamicApiInput(generated);
        setTestInput(generated);
      } catch { setDynamicApiInput(null); }
    })();
  }, [selectedServiceId]);

  // Toggle online/offline
  const toggleService = async (serviceId: string) => {
    const svc = services.find((s) => s.id === serviceId);
    if (!svc) return;
    const wasRunning = svc.status === 'running';
    try {
      if (wasRunning) {
        // 运行中的服务 → 停止
        await api.services.stop(serviceId);
      } else {
        // 已停止的服务 → 启动已有实例（不新建）
        await api.services.start(serviceId);
      }
      // Refresh services list from backend
      const instancesData = await api.services.list();
      const instances = instancesData?.items || [];
      const enriched = await Promise.all(instances.map(async (s: any) => {
        let modelName = '未知模型';
        let modelSlug = 'unknown';
        let modelId = '';
        let modelVersionId = String(s.model_version_id || s.modelVersionId || '');
        let version = '1.0.0';
        let scene = '通用';
        let framework = 'sklearn';
        try {
          const versionData = await api.modelsDeploy.getVersion(Number(s.model_version_id || s.modelVersionId)) as any;
          modelVersionId = String(versionData.model_version_id || versionData.modelVersionId || modelVersionId);
          version = String(versionData.version_tag || versionData.version || '1.0.0');
          if (versionData.model_id || versionData.modelId) {
            modelId = String(versionData.model_id || versionData.modelId || '');
            const modelData = await api.modelsDeploy.get(Number(versionData.model_id || versionData.modelId)) as any;
            modelName = String(modelData.name || '未知模型');
            scene = String(modelData.scene_name || modelData.scene || '通用');
            framework = String(modelData.model_type || modelData.type || 'sklearn');
            modelSlug = modelName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
          }
        } catch { /* ignore */ }
        return {
          id: String(s.model_service_id || s.id || ''),
          modelName,
          modelId,
          modelVersionId,
          modelSlug,
          version,
          scene,
          framework,
          status: (s.status === 'running' ? 'running' : s.status === 'deploying' ? 'deploying' : s.status === 'error' ? 'error' : 'stopped') as ModelServiceRecord['status'],
          environment: 'production' as const,
          instances: 1,
          gpu: '-',
          qps: 0,
          latency: 0,
          latencyMs: 0,
          errorRate: 0,
          apiEndpoint: String(s.endpoint || ''),
          serverInfo: 'default',
          resourceQuota: '1 CPU / 2GB',
          hourlySuccessRate: '99.9%',
          apiInput: JSON.stringify({input_data: {features: {feature_1: 0.0, feature_2: 0.0}}, parameters: {threshold: 0.5}}, null, 2),
          apiOutput: JSON.stringify({prediction: {label: 0, probability: 0.12, risk_level: 'low'}}, null, 2),
          createdAt: String(s.created_at || s.createdAt || ''),
          updatedAt: String(s.created_at || s.createdAt || ''),
          requestCount: 0,
        } as unknown as ModelServiceRecord;
      }));
      setServices(enriched);
      toast.success(wasRunning ? `${svc.modelName} 已下线` : `${svc.modelName} 已上线`, {
        description: wasRunning ? '服务已停止接收流量' : '服务已开始接收流量',
      });
    } catch (err) {
      toast.error('操作失败，请重试');
    }
  };

  // Deploy a stopped/error service
  const deployService = async (serviceId: string) => {
    const svc = services.find((s) => s.id === serviceId);
    if (!svc) return;
    setDeployingId(serviceId);
    setServices((prev) =>
      prev.map((s) => s.id === serviceId ? { ...s, status: 'deploying' as const } : s)
    );
    try {
      // 已停止的服务 → 重新创建实例；运行中的 → 停止
      if (svc.status === 'stopped' || svc.status === 'error') {
        const mvId = (svc as any).modelVersionId || svc.modelId;
        await api.services.create(Number(mvId));
      } else {
        await api.services.stop(serviceId);
      }
      // Refresh services list from backend
      const instancesData = await api.services.list();
      const instances = instancesData?.items || [];
      const enriched = await Promise.all(instances.map(async (s: any) => {
        let modelName = '未知模型';
        let modelSlug = 'unknown';
        let modelId = '';
        let modelVersionId = String(s.model_version_id || s.modelVersionId || '');
        let version = '1.0.0';
        let scene = '通用';
        let framework = 'sklearn';
        try {
          const versionData = await api.modelsDeploy.getVersion(Number(s.model_version_id || s.modelVersionId)) as any;
          modelVersionId = String(versionData.model_version_id || versionData.modelVersionId || modelVersionId);
          version = String(versionData.version_tag || versionData.version || '1.0.0');
          if (versionData.model_id || versionData.modelId) {
            modelId = String(versionData.model_id || versionData.modelId || '');
            const modelData = await api.modelsDeploy.get(Number(versionData.model_id || versionData.modelId)) as any;
            modelName = String(modelData.name || '未知模型');
            scene = String(modelData.scene_name || modelData.scene || '通用');
            framework = String(modelData.model_type || modelData.type || 'sklearn');
            modelSlug = modelName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
          }
        } catch { /* ignore */ }
        return {
          id: String(s.model_service_id || s.id || ''),
          modelName,
          modelId,
          modelVersionId,
          modelSlug,
          version,
          scene,
          framework,
          status: (s.status === 'running' ? 'running' : s.status === 'deploying' ? 'deploying' : s.status === 'error' ? 'error' : 'stopped') as ModelServiceRecord['status'],
          environment: 'production' as const,
          instances: 1,
          gpu: '-',
          qps: 0,
          latency: 0,
          latencyMs: 0,
          errorRate: 0,
          apiEndpoint: String(s.endpoint || ''),
          serverInfo: 'default',
          resourceQuota: '1 CPU / 2GB',
          hourlySuccessRate: '99.9%',
          apiInput: '{"features": [...]}',
          createdAt: String(s.created_at || s.createdAt || ''),
          updatedAt: String(s.created_at || s.createdAt || ''),
          requestCount: 0,
        } as unknown as ModelServiceRecord;
      }));
      setServices(enriched);
      toast.success('部署成功', { description: '服务已上线运行' });
    } catch (err) {
      setServices((prev) =>
        prev.map((s) => s.id === serviceId ? { ...s, status: 'error' as const } : s)
      );
      toast.error('部署失败，请重试');
    }
    setDeployingId(null);
  };

  // 上线：启动已有的 stopped 服务实例
  const startService = async (serviceId: string) => {
    setStartingId(serviceId);
    setServices((prev) => prev.map((s) => s.id === serviceId ? { ...s, status: 'deploying' as const } : s));
    try {
      await api.services.start(serviceId);
      const instancesData = await api.services.list();
      const instances = instancesData?.items || [];
      const enriched = await Promise.all(instances.map(async (s: any) => {
        let modelName = '未知模型'; let modelSlug = 'unknown'; let modelId = ''; let modelVersionId = String(s.model_version_id || ''); let version = '1.0.0'; let scene = '通用'; let framework = 'sklearn';
        try {
          const vd = await api.modelsDeploy.getVersion(Number(s.model_version_id)) as any;
          modelVersionId = String(vd.model_version_id || modelVersionId);
          version = String(vd.version_tag || '1.0.0');
          if (vd.model_id) { modelId = String(vd.model_id); const md = await api.modelsDeploy.get(Number(vd.model_id)) as any; modelName = String(md.name || '未知模型'); scene = String(md.scene_name || '通用'); framework = String(md.model_type || 'sklearn'); modelSlug = modelName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''); }
        } catch { /* ignore */ }
        return { id: String(s.model_service_id || s.id || ''), modelName, modelId, modelVersionId, modelSlug, version, scene, framework, status: (s.status === 'running' ? 'running' : s.status === 'deploying' ? 'deploying' : s.status === 'error' ? 'error' : 'stopped') as ModelServiceRecord['status'], environment: 'production' as const, instances: 1, gpu: '-', qps: 0, latency: 0, latencyMs: Number(s.avg_latency_ms || s.avgLatencyMs || 0), errorRate: 0, apiEndpoint: String(s.endpoint || ''), serverInfo: 'default', resourceQuota: '1 CPU / 2GB', hourlySuccessRate: '99.9%', apiInput: JSON.stringify({input_data: {features: {}}, parameters: {threshold: 0.5}}, null, 2), apiOutput: JSON.stringify({prediction: {label: 0, probability: 0.12, risk_level: 'low'}}, null, 2), createdAt: String(s.created_at || ''), updatedAt: String(s.created_at || ''), requestCount: Number(s.request_count || s.requestCount || 0), lastRequestAt: String(s.last_request_at || s.lastRequestAt || '') } as unknown as ModelServiceRecord;
      }));
      setServices(enriched);
      toast.success('服务已上线', { description: '模型推理服务已启动' });
    } catch (err) {
      setServices((prev) => prev.map((s) => s.id === serviceId ? { ...s, status: 'error' as const } : s));
      toast.error('上线失败', { description: err instanceof Error ? err.message : '请重试' });
    }
    setStartingId(null);
  };

  // Copy API endpoint
  const copyApi = (endpoint: string) => {
    navigator.clipboard.writeText(endpoint);
    toast.success('已复制 API 地址');
  };

  // Inference test
  const runInferenceTest = async () => {
    if (!selectedServiceId || selectedService?.status !== 'running') return;
    setTestLoading(true);
    setTestResult(null);
    try {
      let parsedInput: Record<string, unknown>;
      try {
        parsedInput = JSON.parse(testInput);
      } catch {
        setTestResult(JSON.stringify({ error: '输入的 JSON 格式有误，请检查后重试' }, null, 2));
        setTestLoading(false);
        return;
      }
      const result = await api.services.predict(selectedServiceId, parsedInput);
      setTestResult(JSON.stringify(result, null, 2));
    } catch (err) {
      setTestResult(JSON.stringify({ error: '推理失败，请重试' }, null, 2));
    }
    setTestLoading(false);
  };

  // ===== Detail View =====
  if (selectedService) {
    const isRunning = selectedService.status === 'running';
    const isDeploying = selectedService.status === 'deploying';
    const isError = selectedService.status === 'error';

    return (
      <div className="min-h-screen bg-background">
        <main className="mx-auto max-w-[1440px] px-6 py-6">
          {/* Breadcrumb */}
          <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <button onClick={() => setSelectedServiceId(null)} className="hover:text-foreground transition-colors">
              模型服务
            </button>
            <ChevronRight className="h-4 w-4" />
            <span className="text-foreground font-medium">{selectedService.modelName}</span>
            <ChevronRight className="h-4 w-4" />
            <span className="text-foreground">{selectedService.version}</span>
          </div>

          {/* Header */}
          <div className="mb-6 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${isRunning ? 'bg-emerald-100' : isError ? 'bg-red-100' : 'bg-gray-100'}`}>
                <Server className={`h-5 w-5 ${isRunning ? 'text-emerald-600' : isError ? 'text-red-600' : 'text-gray-500'}`} />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">{selectedService.modelName}</h1>
                <div className="mt-0.5 flex items-center gap-2">
                  <StatusBadge status={selectedService.status} />
                  <span className="text-xs text-muted-foreground">{selectedService.version} · {selectedService.framework}</span>
                  <Link to={`/repository/${selectedService.modelId}`} className="text-xs text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-1">
                    <Package className="h-3 w-3" /> 查看模型
                  </Link>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" className="gap-2" onClick={() => setInferenceTestOpen(true)} disabled={!isRunning}>
                <Play className="h-4 w-4" /> 推理测试
              </Button>
              <Button variant="outline" className="gap-2" onClick={() => copyApi(selectedService.apiEndpoint)}>
                <Copy className="h-4 w-4" /> 复制 API
              </Button>
              {isRunning && (
                <Button variant="outline" className="gap-2" onClick={() => toggleService(selectedService.id)}>
                  <ArrowDownFromLine className="h-4 w-4" /> 下线
                </Button>
              )}
              {!isRunning && !isDeploying && (
                <Button
                  onClick={() => startService(selectedService.id)}
                  disabled={startingId === selectedService.id}
                  className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700"
                >
                  {startingId === selectedService.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                  {startingId === selectedService.id ? '启动中...' : '上线'}
                </Button>
              )}
              {isError && (
                <Button variant="outline" className="gap-2 text-amber-600 hover:bg-amber-50" onClick={() => deployService(selectedService.id)}>
                  <RefreshCw className="h-4 w-4" /> 重新部署
                </Button>
              )}
              {isError && (
                <Link to="/copilot?alert=drift">
                  <Button variant="outline" className="gap-2 text-red-600 hover:bg-red-50 border-red-200 hover:border-red-300">
                    <Activity className="h-4 w-4" /> 漂移重训练
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {/* Drift Alert Banner for error services */}
          {isError && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="relative shrink-0 mt-0.5">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
                    </span>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-red-500">Model Drift Detected</p>
                    <p className="mt-1 text-sm font-semibold text-red-900">
                      线上模型精准率漂移，错误率异常升高
                    </p>
                    <p className="mt-0.5 text-xs text-red-600">
                      建议跳转 Copilot 启动重训练流程，自动修复模型精度
                    </p>
                  </div>
                </div>
                <Link to="/copilot?alert=drift">
                  <Button size="sm" className="gap-1.5 bg-red-600 hover:bg-red-700 text-white shadow-sm">
                    <Activity className="h-3.5 w-3.5" /> 立即修复
                  </Button>
                </Link>
              </div>
            </div>
          )}

          {/* Service Info Cards */}
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Card className="border-border/60">
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">部署服务器</p>
                <p className="mt-2 text-sm font-medium">{selectedService.serverInfo || '\u2014'}</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">资源配额</p>
                <p className="mt-2 text-sm font-medium">{selectedService.resourceQuota || '\u2014'}</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">服务实例ID</p>
                <div className="mt-2 flex items-center gap-2">
                  <code className="rounded bg-gray-100 px-2 py-0.5 text-sm font-mono">{selectedService.id}</code>
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => copyApi(selectedService.id)}>
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">请求数</p>
                <p className="mt-2 text-lg font-bold">{selectedService.requestCount || 0}</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">小时请求成功率</p>
                <p className="mt-2 text-lg font-bold">{selectedService.hourlySuccessRate || '\u2014'}</p>
              </CardContent>
            </Card>
          </div>

          {/* API Service Interface */}
          <Card className="mb-6 border-border/60">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-blue-500" />
                  API 服务接口
                </CardTitle>
                <Badge variant="outline" className="gap-1 text-xs bg-green-50 text-green-700 border-green-200">
                  <CheckCircle2 className="h-3 w-3" /> 统一端口
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Unified port explanation */}
              <div className="rounded-lg bg-blue-50/50 border border-blue-100 p-4">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-blue-800">统一端口 + 服务实例 ID 路由</p>
                    <p className="text-xs text-blue-700">
                      所有模型服务共用同一端口，通过 URL 中的 <code className="bg-blue-100 px-1 rounded">model_service_id</code> 区分不同服务实例。
                      无需为每个模型分配独立端口，避免端口冲突和安全隐患。
                    </p>
                  </div>
                </div>
              </div>

              {/* Route Explanation */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-border/60 p-3">
                  <p className="text-xs font-medium text-muted-foreground mb-1">服务端口</p>
                  <p className="text-sm font-mono font-medium">统一 5000 端口</p>
                  <p className="text-xs text-muted-foreground mt-1">所有模型共用，无需额外端口</p>
                </div>
                <div className="rounded-lg border border-border/60 p-3">
                  <p className="text-xs font-medium text-muted-foreground mb-1">路由规则</p>
                  <p className="text-sm font-mono font-medium">/api/service-instances/{'{model_service_id}'}/predict</p>
                  <p className="text-xs text-muted-foreground mt-1">通过 model_service_id 区分服务实例</p>
                </div>
                <div className="rounded-lg border border-border/60 p-3">
                  <p className="text-xs font-medium text-muted-foreground mb-1">当前服务实例ID</p>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-mono font-medium">{selectedService.id}</p>
                    <Button variant="ghost" size="sm" className="h-5 w-5 p-0" onClick={() => copyApi(selectedService.id)}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">当前部署服务实例的唯一标识</p>
                </div>
              </div>

              {/* API Call Example */}
              <div className="space-y-2">
                <p className="text-sm font-medium">请求示例</p>
                <div className="rounded-lg bg-gray-900 p-4 text-sm font-mono text-gray-100 overflow-x-auto">
                  <div className="text-green-400">{'# 调用模型推理接口'}</div>
                  <div>curl -X POST {selectedService.apiEndpoint} \</div>
                  <div className="ml-4">-H &apos;Content-Type: application/json&apos; \</div>
                  <div className="ml-4">-d &apos;{`{"data": [...]`}&apos;</div>
                </div>
              </div>

              {/* Input JSON */}
              <div className="space-y-2">
                <p className="text-sm font-medium">输入 JSON (Input)</p>
                <pre className="rounded-lg bg-gray-50 p-4 text-xs font-mono overflow-auto max-h-[200px] border border-border/60 whitespace-pre-wrap break-all">
                  {dynamicApiInput || (selectedService.apiInput ? (() => { try { return JSON.stringify(JSON.parse(selectedService.apiInput), null, 2); } catch { return selectedService.apiInput; } })() : '{}')}
                </pre>
              </div>

              {/* Output JSON */}
              <div className="space-y-2">
                <p className="text-sm font-medium">输出 JSON (Output)</p>
                <pre className="rounded-lg bg-gray-50 p-4 text-xs font-mono overflow-auto max-h-[200px] border border-border/60 whitespace-pre-wrap break-all">
                  {selectedService.apiOutput ? (() => { try { return JSON.stringify(JSON.parse(selectedService.apiOutput), null, 2); } catch { return selectedService.apiOutput; } })() : '{}'}
                </pre>
              </div>
            </CardContent>
          </Card>

          {/* 真实运行统计 */}
          {isRunning && (
            <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {/* 累计请求数 */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50">
                      <Activity className="h-4 w-4 text-blue-500" />
                    </div>
                    <p className="text-xs font-medium text-muted-foreground">累计请求数</p>
                  </div>
                  <p className="text-2xl font-bold text-blue-600">
                    {(selectedService as any).requestCount > 0
                      ? ((selectedService as any).requestCount).toLocaleString()
                      : '—'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">次推理调用</p>
                </CardContent>
              </Card>

              {/* 平均延迟 */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50">
                      <Zap className="h-4 w-4 text-emerald-500" />
                    </div>
                    <p className="text-xs font-medium text-muted-foreground">平均延迟</p>
                  </div>
                  <p className="text-2xl font-bold text-emerald-600">
                    {(selectedService as any).latencyMs > 0
                      ? `${Math.round((selectedService as any).latencyMs)}`
                      : '—'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">ms / 次</p>
                </CardContent>
              </Card>

              {/* 最近请求 */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-50">
                      <Clock className="h-4 w-4 text-violet-500" />
                    </div>
                    <p className="text-xs font-medium text-muted-foreground">最近请求</p>
                  </div>
                  <p className="text-2xl font-bold text-violet-600">
                    {(() => {
                      const t = (selectedService as any).lastRequestAt;
                      if (!t) return '—';
                      const diff = Math.floor((Date.now() - new Date(t).getTime()) / 1000);
                      if (diff < 60) return `${diff}秒`;
                      if (diff < 3600) return `${Math.floor(diff / 60)}分钟`;
                      return `${Math.floor(diff / 3600)}小时`;
                    })()}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">前</p>
                </CardContent>
              </Card>

              {/* 服务健康 */}
              <Card className="border-border/60">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    </div>
                    <p className="text-xs font-medium text-muted-foreground">服务健康</p>
                  </div>
                  <p className="text-2xl font-bold text-emerald-600">正常</p>
                  <p className="text-xs text-muted-foreground mt-1">运行中</p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Back to list */}
          <Button variant="ghost" className="gap-2" onClick={() => setSelectedServiceId(null)}>
            <ChevronRight className="h-4 w-4 rotate-180" /> 返回服务列表
          </Button>

          {/* Inference Test Modal */}
          {inferenceTestOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
              <Card className="w-full max-w-[640px] shadow-2xl border-border/60 flex flex-col max-h-[90vh]">
                <CardHeader className="flex flex-row items-center justify-between pb-3 shrink-0">
                  <CardTitle className="text-lg">推理测试 - {selectedService.modelName}</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => { setInferenceTestOpen(false); setTestResult(null); }}>
                    <X className="h-4 w-4" />
                  </Button>
                </CardHeader>
                <CardContent className="space-y-4 overflow-y-auto flex-1 pb-5">
                  <div>
                    <p className="mb-2 text-sm font-medium">请求 JSON</p>
                    <Textarea
                      value={testInput}
                      onChange={(e) => setTestInput(e.target.value)}
                      className="font-mono text-sm min-h-[120px] max-h-[220px] resize-y"
                      placeholder="输入 JSON 格式的推理请求..."
                    />
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      onClick={runInferenceTest}
                      disabled={testLoading || !isRunning}
                      className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700"
                    >
                      {testLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      {testLoading ? '推理中...' : '执行推理'}
                    </Button>
                    {!isRunning && (
                      <span className="text-xs text-muted-foreground">请先上线模型后再测试</span>
                    )}
                  </div>
                  {testResult && (
                    <div>
                      <p className="mb-2 text-sm font-medium">推理结果</p>
                      <pre className="rounded-xl bg-gray-50 p-4 text-sm font-mono overflow-auto max-h-[260px] border border-border/60 whitespace-pre-wrap break-all">
                        {testResult}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </main>
      </div>
    );
  }

  // ===== Default: Service List View =====
  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto max-w-[1440px] px-6 py-6">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">模型服务</h1>
            <p className="mt-1 text-sm text-muted-foreground">管理模型部署、在线服务和推理任务</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" className="gap-2" onClick={() => setShowApiGuide(!showApiGuide)}>
              <Terminal className="h-4 w-4" /> API 使用说明
            </Button>
            <Button variant="outline" className="gap-2" onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4" /> 刷新
            </Button>
          </div>
        </div>

        {/* API Guide Panel */}
        {showApiGuide && (
          <Card className="mb-6 border-blue-200 bg-blue-50/30">
            <CardContent className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Terminal className="h-5 w-5 text-blue-600" />
                  <h3 className="font-semibold text-blue-900">统一端口 + 服务实例 ID 路由方案</h3>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setShowApiGuide(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="rounded-lg bg-white p-4 border border-blue-100">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">问题</p>
                    <p className="text-sm">每个模型分配独立端口，端口冲突、难管理、不安全</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">方案</p>
                    <p className="text-sm">统一端口 (5000)，通过 URL 路由 <code className="bg-blue-50 px-1 rounded text-blue-700">/api/service-instances/{'{model_service_id}'}/predict</code> 区分模型</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">优势</p>
                    <p className="text-sm">端口不冲突、易扩展、统一鉴权、便于监控</p>
                  </div>
                </div>
              </div>

              <div className="rounded-lg bg-gray-900 p-4 text-sm font-mono text-gray-100 overflow-x-auto">
                <div className="text-green-400">{'# 统一端口调用示例 — 通过 model_id 区分不同模型'}</div>
                <div className="mt-1">{'# 反欺诈模型'}</div>
                <div>curl -X POST /api/v1/inference/fraud-detect -d {`'{"data": [...]'`}</div>
                <div className="mt-2">{'# 信用评分模型'}</div>
                <div>curl -X POST /api/v1/inference/credit-score -d {`'{"data": [...]'`}</div>
                <div className="mt-2">{'# 客户流失模型'}</div>
                <div>curl -X POST /api/v1/inference/churn -d {`'{"data": [...]'`}</div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* KPI Cards */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Card className="border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-blue-500" />
                <p className="text-xs font-medium text-muted-foreground">部署总数</p>
              </div>
              <p className="mt-2 text-3xl font-bold"><AnimatedNumber value={services.length} /></p>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <CircleDot className="h-4 w-4 text-emerald-500" />
                <p className="text-xs font-medium text-muted-foreground">运行中</p>
              </div>
              <p className="mt-2 text-3xl font-bold text-emerald-600"><AnimatedNumber value={runningCount} /></p>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <PowerOff className="h-4 w-4 text-gray-400" />
                <p className="text-xs font-medium text-muted-foreground">已停止</p>
              </div>
              <p className="mt-2 text-3xl font-bold text-gray-500"><AnimatedNumber value={stoppedCount} /></p>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                <p className="text-xs font-medium text-muted-foreground">异常</p>
              </div>
              <p className="mt-2 text-3xl font-bold text-red-600"><AnimatedNumber value={errorCount} /></p>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-500" />
                <p className="text-xs font-medium text-muted-foreground">总请求数</p>
              </div>
              <p className="mt-2 text-3xl font-bold"><AnimatedNumber value={totalRequests} /></p>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-purple-500" />
                <p className="text-xs font-medium text-muted-foreground">部署中</p>
              </div>
              <p className="mt-2 text-3xl font-bold text-blue-600"><AnimatedNumber value={deployingCount} /></p>
            </CardContent>
          </Card>
        </div>

        {/* Service List Table */}
        <Card className="mb-6 border-border/60">
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">部署服务列表</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="gap-1 text-xs">
                    <CircleDot className="h-3 w-3 text-emerald-500" /> 运行 {runningCount}
                  </Badge>
                  <Badge variant="outline" className="gap-1 text-xs">
                    <PowerOff className="h-3 w-3 text-gray-400" /> 停止 {stoppedCount}
                  </Badge>
                  <Badge variant="outline" className="gap-1 text-xs">
                    <AlertTriangle className="h-3 w-3 text-red-500" /> 异常 {errorCount}
                  </Badge>
                </div>
              </div>
              {/* Search + Filters */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className="relative flex-1 min-w-[200px] max-w-[360px]">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="搜索模型名称、服务实例ID、场景、框架..."
                    className="pl-9 h-9"
                  />
                </div>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[120px] h-9">
                    <Filter className="h-3.5 w-3.5 mr-1" />
                    <SelectValue placeholder="状态" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="running">运行中</SelectItem>
                    <SelectItem value="stopped">已停止</SelectItem>
                    <SelectItem value="deploying">部署中</SelectItem>
                    <SelectItem value="error">异常</SelectItem>
                  </SelectContent>
                </Select>
                {(searchQuery || statusFilter !== 'all') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 text-xs"
                    onClick={() => { setSearchQuery(''); setStatusFilter('all'); }}
                  >
                    清除筛选
                  </Button>
                )}
                <span className="text-xs text-muted-foreground ml-auto">
                  共 {filteredServices.length} 条记录
                  {filteredServices.length !== services.length && ` (总计 ${services.length})`}
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loadingServices ? (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin mb-3" />
                <p className="text-sm">加载模型服务...</p>
              </div>
            ) : (
            <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>模型名称</TableHead>
                  <TableHead>服务实例ID</TableHead>
                  <TableHead>版本</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>请求数</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredServices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                      {searchQuery || statusFilter !== 'all'
                        ? '没有匹配的部署服务，请调整筛选条件'
                        : '暂无部署服务'}
                    </TableCell>
                  </TableRow>
                ) : (
                  Array.from(groupedServices.entries()).map(([modelId, groupSvcs]) => {
                    const isExpanded = expandedGroups.has(modelId);
                    const firstSvc = groupSvcs[0];
                    const modelName = firstSvc.modelName;
                    return (
                      <Fragment key={modelId}>
                        {/* Group header row */}
                        <TableRow
                          className="bg-muted/40 cursor-pointer hover:bg-muted/60"
                          onClick={() => toggleGroup(modelId)}
                        >
                          <TableCell colSpan={7}>
                            <div className="flex items-center gap-2">
                              <ChevronRight className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                              <Server className="h-4 w-4 text-muted-foreground" />
                              <span className="font-medium">{modelName}</span>
                              <Badge variant="secondary" className="text-xs h-5">{groupSvcs.length} 个部署</Badge>
                            </div>
                          </TableCell>
                        </TableRow>
                        {/* Expanded deployment rows */}
                        {isExpanded && groupSvcs.map((svc, idx) => {
                          const isRunning = svc.status === 'running';
                          const isDeploying = svc.status === 'deploying';
                          const isError = svc.status === 'error';
                          const isStopped = svc.status === 'stopped';
                          return (
                            <TableRow
                              key={svc.id}
                              className={`group ${isRunning ? 'border-l-2 border-l-emerald-500 bg-emerald-50/30' : isError ? 'border-l-2 border-l-red-500 bg-red-50/20' : isStopped ? 'opacity-60' : ''}`}
                            >
                              <TableCell>
                                <div className="flex items-center gap-2 pl-6">
                                  <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-muted text-xs font-medium text-muted-foreground">#{idx + 1}</span>
                                  <button
                                    onClick={() => setSelectedServiceId(svc.id)}
                                    className="font-medium text-left hover:text-blue-600 transition-colors truncate max-w-[160px]"
                                  >
                                    {svc.modelName}
                                  </button>
                                  <Link to={`/repository/${svc.modelId}`} className="opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                                    <Package className="h-3.5 w-3.5 text-blue-500 hover:text-blue-700" />
                                  </Link>
                                </div>
                              </TableCell>
                              <TableCell>
                                <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-mono">{svc.id}</code>
                              </TableCell>
                              <TableCell className="text-sm font-mono">{svc.version}</TableCell>
                              <TableCell><StatusBadge status={svc.status} /></TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {svc.requestCount || 0}
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground">{formatDate(svc.updatedAt)}</TableCell>
                              <TableCell className="text-right">
                                <div className="flex items-center justify-end gap-1">
                                  {(isRunning || isStopped) && (
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            className={`h-8 gap-1 ${isRunning ? 'text-amber-600 hover:bg-amber-50' : 'text-blue-600 hover:bg-blue-50'}`}
                                            onClick={() => toggleService(svc.id)}
                                          >
                                            {isRunning ? <ArrowDownFromLine className="h-3.5 w-3.5" /> : <ArrowUpFromLine className="h-3.5 w-3.5" />}
                                          </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>{isRunning ? '下线' : '上线'}</TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  )}
                                  {isError && (
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-8 gap-1 text-blue-600 hover:bg-blue-50"
                                            onClick={() => deployService(svc.id)}
                                            disabled={deployingId === svc.id}
                                          >
                                            {deployingId === svc.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Rocket className="h-3.5 w-3.5" />}
                                          </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>{deployingId === svc.id ? '部署中...' : '重新部署'}</TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  )}
                                  {isDeploying && (
                                    <span className="flex items-center gap-1 text-xs text-blue-600">
                                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> 部署中
                                    </span>
                                  )}
                                  <TooltipProvider>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <Button variant="ghost" size="sm" className="h-8" onClick={() => copyApi(svc.apiEndpoint)}>
                                          <Copy className="h-3.5 w-3.5" />
                                        </Button>
                                      </TooltipTrigger>
                                      <TooltipContent>复制 API 地址</TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                  <TooltipProvider>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <Button variant="ghost" size="sm" className="h-8" onClick={() => setSelectedServiceId(svc.id)}>
                                          <ChevronRight className="h-3.5 w-3.5" />
                                        </Button>
                                      </TooltipTrigger>
                                      <TooltipContent>查看详情</TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </Fragment>
                    );
                  })
                )}
              </TableBody>
            </Table>
            </div>
            )}
          </CardContent>
        </Card>

        {/* Copilot deployment note */}
        <Card className="border-border/60">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100">
                <Zap className="h-4 w-4 text-purple-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">通过 Copilot 自动部署</p>
                <p className="text-xs text-muted-foreground">
                  在智能建模 Copilot 中完成建模后，可一键部署为在线服务，部署记录将自动写入此列表
                </p>
              </div>
              <Link to="/copilot">
                <Button variant="outline" size="sm" className="gap-1">
                  前往 Copilot <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
