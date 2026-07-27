
import { useState, useMemo, useEffect, Fragment } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Card,
  CardContent,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Search,
  Download,
  Archive,
  Package,
  Clock,
  CheckCircle2,
  Layers,
  FileText,
  Database,
  Code2,
  Box,
  ArrowRight,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Bot,
  Sparkles,
  Inbox,
  Rocket,
  Trash2,
  RotateCcw,
  ArrowUpDown,
  BarChart3,
  ChevronLeft,
  Loader2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDate, type ModelingTask, type TaskArtifact } from '@/lib/demo-data';
import { DataProfilingPanel, type ColumnProfile, type ProfilingDataFile } from '@/components/data-profiling-panel';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';

/* ─── Helpers ─── */
async function downloadArtifact(file: TaskArtifact) {
  if (!file.url) {
    toast.error('暂无真实下载地址', { description: file.name });
    return;
  }
  const link = document.createElement('a');
  link.href = file.url;
  link.download = file.name;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function canPushTaskToRepo(task: ModelingTask & Record<string, unknown>) {
  const sessionModels = Array.isArray(task._sessionModels) ? task._sessionModels : [];
  return task.modelFiles.length > 0 || Boolean(task.repoModelId) || sessionModels.some((model: any) => Boolean(model?.modelId));
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string; dot: string }> = {
    running: { label: '进行中', className: 'bg-blue-50 text-blue-700 border-blue-200', dot: 'bg-blue-500' },
    completed: { label: '已完成', className: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500' },
    archived: { label: '已归档', className: 'bg-gray-50 text-gray-500 border-gray-200', dot: 'bg-gray-400' },
    failed: { label: '失败', className: 'bg-red-50 text-red-600 border-red-200', dot: 'bg-red-500' },
  };
  const c = config[status] || config.archived;
  return (
    <Badge variant="outline" className={`${c.className} gap-1.5`}>
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </Badge>
  );
}

function ArtifactTypeIcon({ type }: { type: string }) {
  if (type === 'data') return <Database className="h-4 w-4 text-blue-400" />;
  if (type === 'model') return <Box className="h-4 w-4 text-violet-400" />;
  if (type === 'code') return <Code2 className="h-4 w-4 text-emerald-500" />;
  return <FileText className="h-4 w-4 text-amber-400" />;
}

function DownloadFileDialog({ artifacts, taskName }: { artifacts: TaskArtifact[]; taskName: string }) {
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleDownload = async (file: TaskArtifact) => {
    setDownloading(file.name);
    try {
      await downloadArtifact(file);
      toast.success('下载已开始', { description: file.name });
    } catch (err) {
      toast.error('下载失败', { description: err instanceof Error ? err.message : String(err) });
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Download className="h-3.5 w-3.5" /> 下载产物
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5 text-blue-600" />
            下载任务产物
          </DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <p className="text-sm text-muted-foreground mb-3">
            任务: <span className="font-medium text-foreground">{taskName}</span>
          </p>
          <div className="space-y-2 max-h-[360px] overflow-y-auto">
            {artifacts.map((file) => (
              <div
                key={file.name}
                className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2.5 hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <ArtifactTypeIcon type={file.type} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{file.size} · {file.time}</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="gap-1 shrink-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                  onClick={() => handleDownload(file)}
                  disabled={downloading === file.name}
                >
                  {downloading === file.name ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  {downloading === file.name ? '完成' : '下载'}
                </Button>
              </div>
            ))}
            {artifacts.length === 0 && (
              <div className="text-center py-6 text-muted-foreground text-sm">暂无产物文件</div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ─── Expanded Row Detail ─── */
function ExpandedTaskDetail({ task, onPushToRepo }: { task: ModelingTask; onPushToRepo: (id: string) => void }) {
  const [activeTab, setActiveTab] = useState<'data' | 'profiling' | 'model' | 'code'>('data');
  const allArtifacts = [...task.dataFiles, ...task.modelFiles, ...task.codeFiles];
  const profilingFiles: ProfilingDataFile[] = task.dataFiles.map((file) => {
    const rows = Number(file.rows || 0);
    const columns = file.columns || [];
    const preview = file.preview || [];
    return {
      id: String(file.id || file.name),
      name: file.name,
      rows,
      columns: Number(file.columnsCount || columns.length || 0),
      previewCols: columns.map((name) => ({ key: name, label: name, type: 'text' as const })),
      previewRows: preview.map((row, index) => ({ id: String(index), ...row })),
      columnProfiles: columns.map((name) => {
        const values = preview.map((row) => row?.[name]).filter((value) => value !== null && value !== undefined && value !== '');
        const unique = new Set(values.map((value) => String(value))).size;
        const numericCount = values.filter((value) => typeof value === 'number' || (!Number.isNaN(Number(value)) && String(value).trim() !== '')).length;
        const lower = name.toLowerCase();
        const type: ColumnProfile['type'] = lower.includes('dt') || lower.includes('time') || lower.includes('date')
          ? 'datetime'
          : values.length > 0 && numericCount / values.length > 0.8
          ? 'numeric'
          : unique > 20
          ? 'text'
          : 'categorical';
        const nonNull = rows || values.length;
        return {
          name,
          type,
          nonNull,
          total: rows || values.length,
          nullRate: '0.00%',
          unique,
        };
      }),
    };
  });

  const tabs = [
    { key: 'data' as const, label: '数据文件', icon: Database, items: task.dataFiles, color: 'text-blue-500' },
    { key: 'profiling' as const, label: '数据探查', icon: BarChart3, color: 'text-amber-500' },
    { key: 'model' as const, label: '模型产物', icon: Box, items: task.modelFiles, color: 'text-violet-500' },
    // 隐藏源代码显示
    // { key: 'code' as const, label: '源代码', icon: Code2, items: task.codeFiles, color: 'text-emerald-500' },
  ];

  const activeItems = tabs.find((t) => t.key === activeTab)?.items || [];
  const isProfilingTab = activeTab === 'profiling';

  return (
    <div className="bg-muted/20 px-8 py-5">
      {/* Description */}
      <p className="text-sm text-muted-foreground mb-4">{task.description}</p>

      {/* Artifact Tabs */}
      <div className="flex items-center gap-1 mb-3 border-b border-border/60">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
                activeTab === tab.key
                  ? `border-blue-600 text-blue-700`
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <TabIcon className={`h-3.5 w-3.5 ${activeTab === tab.key ? tab.color : ''}`} />
              {tab.label}
              {'items' in tab && tab.items && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 ml-0.5">{tab.items.length}</Badge>
              )}
            </button>
          );
        })}
      </div>

      {/* File List */}
      {isProfilingTab ? (
        <DataProfilingPanel files={profilingFiles} />
      ) : activeItems.length > 0 ? (
        <div className="space-y-1.5">
          {activeItems.map((file) => (
            <div key={file.name} className="flex items-center justify-between rounded-md border border-border/30 px-3 py-2 hover:bg-accent/30 transition-colors">
              <div className="flex items-center gap-2.5 min-w-0">
                <ArtifactTypeIcon type={file.type} />
                <div className="min-w-0">
                  <p className="text-xs font-medium truncate">{file.name}</p>
                  <p className="text-[10px] text-muted-foreground">{file.size} · {file.time}</p>
                </div>
              </div>
              <Button variant="ghost" size="sm" className="gap-1 shrink-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50 h-7 text-xs" onClick={() => downloadArtifact(file).catch((err) => toast.error('下载失败', { description: err instanceof Error ? err.message : String(err) }))}>
                <Download className="h-3 w-3" /> 下载
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center py-6 text-muted-foreground text-xs">
          <Inbox className="h-6 w-6 mr-2" /> 暂无{tabs.find((t) => t.key === activeTab)?.label}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 pt-3 border-t border-border/40 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>共 {allArtifacts.length} 个文件</span>
          {task.sessionId && (
            <>
              <span>·</span>
              <Link to={`/copilot?session=${task.sessionId}`} className="flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors">
                <Bot className="h-3 w-3" /> 关联对话
              </Link>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {allArtifacts.length > 0 && (
            <DownloadFileDialog artifacts={allArtifacts} taskName={task.name} />
          )}
          {canPushTaskToRepo(task as ModelingTask & Record<string, unknown>) && (
            <Button
              size="sm"
              disabled={task.inRepo}
              className={`gap-1.5 ${task.inRepo ? 'bg-gray-300 text-gray-500 cursor-not-allowed opacity-60' : 'bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700'}`}
              onClick={() => !task.inRepo && onPushToRepo(task.id)}
            >
              <Package className="h-3.5 w-3.5" /> {task.inRepo ? '已入仓库' : '存入仓库'}
            </Button>
          )}
          {task.inRepo && (
            <Link to="/service">
              <Button
                size="sm"
                className="gap-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 shadow-md shadow-emerald-500/20 hover:from-emerald-700 hover:to-teal-700"
              >
                <Rocket className="h-3.5 w-3.5" /> 部署到服务
              </Button>
            </Link>
          )}
          {task.inRepo && task.repoModelId && (
            <Link to={`/repository/${task.repoModelId}`}>
              <Button variant="outline" size="sm" className="gap-1.5">
                查看仓库模型 <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Main Page ─── */
export default function ModelingTasksPage() {
  const [searchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState('all');
  const [keyword, setKeyword] = useState('');
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<ModelingTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortField, setSortField] = useState<'updatedAt' | 'name' | 'status'>('updatedAt');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Load real session data from backend (each session = one modeling task)
  useEffect(() => {
    let cancelled = false;

    const formatFileSize = (bytes: number): string => {
      if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
      return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
    };

    const toArtifact = (file: any, type: TaskArtifact['type']): TaskArtifact => {
      const name = String(file.fileName || file.name || 'unknown');
      const sizeBytes = Number(file.fileSize ?? file.size ?? 0);
      const createdAt = String(file.uploadTime || file.createdAt || file.modifiedAt || new Date().toISOString());
      return {
        id: String(file.fileId || file.artifactId || file.id || name),
        name,
        size: formatFileSize(sizeBytes),
        sizeBytes,
        type,
        url: String(file.downloadUrl || file.url || ''),
        createdAt,
        time: formatDate(createdAt),
        rows: Number(file.rows || 0),
        columnsCount: Number(file.columnsCount || 0),
        columns: Array.isArray(file.columns) ? file.columns : [],
        preview: Array.isArray(file.preview) ? file.preview : [],
      };
    };

    (async () => {
      try {
        setLoading(true);
        const sessionsData = await api.sessions.list();
        const sessions = sessionsData?.items || [];
        const mapped: ModelingTask[] = await Promise.all(sessions.map(async (s: any) => {
          const sessionId = String(s.session_id || s.sessionId || s.id || '');
          const title = String(s.title || s.project_name || '未命名建模任务');
          const createdAt = String(s.createdAt || s.created_at || '');
          const updatedAt = String(s.updatedAt || s.updated_at || s.created_at || '');

          const [filesRes, outputsRes, modelsRes, workflowRes] = await Promise.allSettled([
            api.sessions.files(sessionId),
            api.sessions.modelOutputs(sessionId),
            api.sessions.models(sessionId),
            api.sessions.workflow(sessionId),
          ]);

          const files = filesRes.status === 'fulfilled' ? (filesRes.value?.items || []) : [];
          const outputs = outputsRes.status === 'fulfilled' ? outputsRes.value : { items: [], modelItems: [], codeItems: [] };
          const sessionModels = modelsRes.status === 'fulfilled' ? (modelsRes.value?.items || []) : [];
          const workflow = workflowRes.status === 'fulfilled' ? workflowRes.value : null;

          const dataFiles = files.map((file: any) => toArtifact(file, 'data'));
          const modelFiles = ((outputs.modelItems || outputs.items || []) as any[]).map((file) => toArtifact(file, 'model'));
          const codeFiles = ((outputs.codeItems || []) as any[]).map((file) => toArtifact(file, 'code'));

          const workflowState = String(workflow?.workflow_state || 'not_started');
          let taskStatus: ModelingTask['status'] = 'pending';
          if (workflowState === 'completed' || modelFiles.length > 0 || sessionModels.length > 0) taskStatus = 'completed';
          else if (workflowState !== 'not_started' || Number(s.message_count || 0) > 0) taskStatus = 'running';

          const repoModels = sessionModels.filter((m: any) => Boolean(m?.modelId || m?.inRepo || m?.repositoryName || m?.repository_name));
          const firstModel = repoModels.find((m: any) => m.modelId) || null;

          return {
            id: sessionId,
            name: title,
            status: taskStatus,
            sessionId,
            createdAt,
            updatedAt,
            description: `建模任务 · ${Number(s.message_count || 0)}条消息`,
            dataFiles,
            modelFiles,
            codeFiles,
            inRepo: repoModels.length > 0,
            repoModelId: firstModel?.modelId ? String(firstModel.modelId) : undefined,
            _rawSession: s,
            _sessionModels: sessionModels,
          } as ModelingTask & Record<string, unknown>;
        }));
        if (!cancelled) setTasks(mapped);
      } catch (err) {
        console.error('Failed to load sessions from backend:', err);
        if (!cancelled) setTasks([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, []);

  // Auto-expand and highlight task when navigating from Copilot with ?session=s1 or ?highlight=t1
  const [highlightId, setHighlightId] = useState<string | null>(null);
  useEffect(() => {
    const sessionFilter = searchParams.get('session');
    const highlightFilter = searchParams.get('highlight');
    const targetId = highlightFilter || (sessionFilter ? tasks.find((t) => t.sessionId === sessionFilter)?.id ?? null : null);
    if (targetId) {
      setExpandedTaskId(targetId);
      setHighlightId(targetId);
      // Auto-scroll to the task after a brief delay
      setTimeout(() => {
        const el = document.getElementById(`task-${targetId}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 300);
      // Clear highlight after 3 seconds
      setTimeout(() => setHighlightId(null), 3000);
    }
  }, [searchParams, tasks]);

  const filteredTasks = useMemo(() => {
    const filtered = tasks.filter((t) => {
      const matchKw = !keyword || t.name.toLowerCase().includes(keyword.toLowerCase()) || t.description.toLowerCase().includes(keyword.toLowerCase());
      if (statusFilter === 'inrepo') return matchKw && t.inRepo;
      const matchStatus = statusFilter === 'all' || t.status === statusFilter;
      return matchKw && matchStatus;
    });
    // Sort
    filtered.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'updatedAt') cmp = new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
      else if (sortField === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortField === 'status') cmp = a.status.localeCompare(b.status);
      return sortDir === 'desc' ? -cmp : cmp;
    });
    return filtered;
  }, [keyword, statusFilter, tasks, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filteredTasks.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pagedTasks = filteredTasks.slice((safeCurrentPage - 1) * pageSize, safeCurrentPage * pageSize);

  const toggleSort = (field: 'updatedAt' | 'name' | 'status') => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortField(field); setSortDir('desc'); }
  };

  const totalTasks = tasks.length;
  const runningCount = tasks.filter((t) => t.status === 'running').length;
  const completedCount = tasks.filter((t) => t.status === 'completed').length;
  const inRepoCount = tasks.filter((t) => t.inRepo).length;

  const handlePushToRepo = async (taskId: string) => {
    const task = tasks.find((t) => t.id === taskId) as (ModelingTask & Record<string, any>) | undefined;
    if (!task) {
      toast.error('任务不存在', { description: '未找到指定的建模任务' });
      return;
    }

    try {
      toast.loading('正在检查任务模型产物...', { id: 'push-repo' });

      const boundModel = (task._sessionModels || []).find((m: any) => m.modelId);
      if (task.repoModelId || boundModel?.modelId) {
        const modelId = Number(task.repoModelId || boundModel.modelId);
        await api.modelsDeploy.pushToRepo(modelId);
        setTasks((prev) => prev.map((t) => t.id === taskId ? { ...t, inRepo: true, repoModelId: String(modelId) } : t));
        toast.success('模型已在仓库中', { id: 'push-repo', description: '已刷新仓库状态' });
        return;
      }

      const modelArtifact = task.modelFiles.find((file) => file.url) || task.modelFiles[0];
      if (!modelArtifact?.url) {
        throw new Error('未找到该任务生成的真实模型文件，请先完成模型训练后再入库');
      }

      toast.loading('正在读取真实模型文件...', { id: 'push-repo' });
      const fileResponse = await fetch(modelArtifact.url);
      if (!fileResponse.ok) throw new Error(`模型文件读取失败：${fileResponse.status}`);
      const blob = await fileResponse.blob();
      const modelFile = new File([blob], modelArtifact.name, { type: blob.type || 'application/octet-stream' });

      toast.loading('正在创建业务模型...', { id: 'push-repo' });
      const modelData = await api.modelsDeploy.create({
        name: task.name,
        description: task.description || '通过建模任务创建的模型',
        repository_name: task.name,
        session_id: task.sessionId,
      });
      const modelId = Number(modelData.model_id || (modelData as any).id);
      if (!modelId) throw new Error('创建模型失败：未返回模型 ID');

      toast.loading('正在上传模型版本...', { id: 'push-repo' });
      const versionData = await api.modelsDeploy.uploadVersion(modelId, {
        version: '1.0.0',
        description: `建模任务 ${task.name} 的初始版本`,
        file: modelFile,
        model_type: 'sklearn',
        scene_name: '金融风控',
        session_id: task.sessionId,
      });

      toast.loading('正在存入仓库并绑定会话...', { id: 'push-repo' });
      await api.modelsDeploy.pushToRepo(modelId);
      if (task.sessionId) await api.sessions.bindModel(task.sessionId, modelId);

      setTasks((prev) => prev.map((t) =>
        t.id === taskId
          ? { ...t, inRepo: true, repoModelId: String(modelId), _sessionModels: [{ modelId, modelName: task.name, modelVersionId: versionData.model_version_id, version: versionData.version_tag }] } as ModelingTask & Record<string, unknown>
          : t
      ));

      toast.success('模型已成功存入仓库', {
        id: 'push-repo',
        description: '已使用该任务生成的真实模型产物创建模型版本',
      });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      toast.error('存入仓库失败', { id: 'push-repo', description: errorMsg });
    }
  };

  const handleArchiveTask = (taskId: string) => {
    setTasks((prev) => prev.map((t) =>
      t.id === taskId ? { ...t, status: 'archived' as const } : t
    ));
    toast.success('任务已归档', { description: '归档后仍可在"已归档"分类中查看' });
  };

  const handleDeleteTask = async (taskId: string) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;

    // 已入库的任务不可删除
    if (task.inRepo) {
      toast.error('已入库的任务不可删除', { description: '该模型已入库到仓库，数据需要保留' });
      return;
    }

    // 确认删除
    if (!confirm(`确定要删除任务"${task.name}"吗？\n删除后将同时清除该任务的 Copilot 对话和相关数据，且不可恢复。`)) return;

    try {
      // 1. 调用后端API删除session数据（pipeline + 上传文件）
      if (task.sessionId) {
        try {
          await api.sessions.delete(task.sessionId);
        } catch {
          // session数据已不存在（可忽略）
        }
      }

      // 2. 删除关联的 Copilot 会话（通过 CustomEvent 通知 copilot 页面）
      if (task.sessionId) {
        window.dispatchEvent(new CustomEvent('copilot:delete-session', { detail: { sessionId: task.sessionId } }));
      }

      // 3. 从前端 state 中移除任务
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      if (expandedTaskId === taskId) setExpandedTaskId(null);
      toast.success('任务已删除', { description: '关联的对话和数据已一并清除' });
    } catch (err) {
      console.error('Failed to delete task:', err);
      toast.error('删除任务失败', { description: String(err) });
    }
  };

  // 监听来自 copilot 页面的级联删除事件
  useEffect(() => {
    const handleDeleteTaskEvent = (e: Event) => {
      const { taskId } = (e as CustomEvent).detail;
      if (taskId) setTasks((prev) => prev.filter((t) => t.id !== taskId));
    };
    // 监听来自模型仓库的模型删除事件，更新关联任务的入库状态
    const handleModelDeletedEvent = (e: Event) => {
      const { modelId } = (e as CustomEvent).detail;
      if (modelId) {
        setTasks((prev) =>
          prev.map((t) =>
            t.repoModelId === modelId ? { ...t, inRepo: false, repoModelId: undefined } : t
          )
        );
      }
    };
    window.addEventListener('tasks:delete-task', handleDeleteTaskEvent);
    window.addEventListener('repository:model-deleted', handleModelDeletedEvent);
    return () => {
      window.removeEventListener('tasks:delete-task', handleDeleteTaskEvent);
      window.removeEventListener('repository:model-deleted', handleModelDeletedEvent);
    };
  }, []);

  const filterTabs = [
    { key: 'all', label: '全部', count: totalTasks },
    { key: 'running', label: '进行中', count: runningCount },
    { key: 'completed', label: '已完成', count: completedCount },
    { key: 'archived', label: '已归档', count: tasks.filter((t) => t.status === 'archived').length },
    { key: 'failed', label: '失败', count: tasks.filter((t) => t.status === 'failed').length },
    { key: 'inrepo', label: '已入仓库', count: inRepoCount },
  ];

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto max-w-[1440px] px-6 py-6">
        {/* Title */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">建模任务</h1>
            <p className="mt-1 text-sm text-muted-foreground">每次 Copilot 对话对应一个建模任务，管理数据、模型产物与源代码</p>
          </div>
          <Link to="/copilot">
            <Button className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 shadow-md shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700">
              <Sparkles className="h-4 w-4" /> 新建任务
            </Button>
          </Link>
        </div>

        {/* KPI Row */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { title: '总任务', value: totalTasks, icon: Layers, color: 'text-blue-600', bg: 'bg-blue-50' },
            { title: '进行中', value: runningCount, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50' },
            { title: '已完成', value: completedCount, icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50' },
            { title: '已入仓库', value: inRepoCount, icon: Package, color: 'text-violet-600', bg: 'bg-violet-50' },
          ].map((kpi) => (
            <Card key={kpi.title} className="border-border/60 transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="p-4 flex items-center gap-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${kpi.bg}`}>
                  <kpi.icon className={`h-5 w-5 ${kpi.color}`} />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{kpi.title}</p>
                  <p className="text-2xl font-bold">{kpi.value}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filter Tabs + Search */}
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-1 rounded-lg bg-muted/50 p-1">
            {filterTabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setStatusFilter(tab.key)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                  statusFilter === tab.key
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab.label}
                <span className={`text-[10px] ${statusFilter === tab.key ? 'text-blue-500' : 'text-muted-foreground'}`}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>
          <div className="relative w-72">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索任务名称、描述..."
              value={keyword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeyword(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </div>

        {/* Task Table */}
        <Card className="border-border/60 overflow-hidden">
          <div className="overflow-x-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mb-3" />
              <p className="text-sm">加载建模任务...</p>
            </div>
          ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-8"></TableHead>
                <TableHead>
                  <button className="flex items-center gap-1 hover:text-foreground transition-colors" onClick={() => toggleSort('name')}>
                    任务名称
                    <ArrowUpDown className={`h-3 w-3 ${sortField === 'name' ? 'text-blue-600' : 'text-muted-foreground/50'}`} />
                  </button>
                </TableHead>
                <TableHead className="w-24 text-center">
                  <button className="inline-flex items-center gap-1 hover:text-foreground transition-colors" onClick={() => toggleSort('status')}>
                    状态
                    <ArrowUpDown className={`h-3 w-3 ${sortField === 'status' ? 'text-blue-600' : 'text-muted-foreground/50'}`} />
                  </button>
                </TableHead>
                <TableHead className="w-20 text-center">数据</TableHead>
                <TableHead className="w-20 text-center">模型</TableHead>
                {/* 隐藏源代码列 */}
                {/* <TableHead className="w-20 text-center">代码</TableHead> */}
                <TableHead className="w-28 text-center">入库</TableHead>
                <TableHead className="w-40 text-right">
                  <button className="inline-flex items-center gap-1 hover:text-foreground transition-colors" onClick={() => toggleSort('updatedAt')}>
                    更新时间
                    <ArrowUpDown className={`h-3 w-3 ${sortField === 'updatedAt' ? 'text-blue-600' : 'text-muted-foreground/50'}`} />
                  </button>
                </TableHead>
                <TableHead className="w-32 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagedTasks.map((task) => {
                const isExpanded = expandedTaskId === task.id;
                return (
                  <Fragment key={task.id}>
                    <TableRow
                      key={task.id}
                      className={`cursor-pointer transition-colors ${highlightId === task.id ? 'ring-2 ring-blue-400 bg-blue-50/70 animate-pulse' : isExpanded ? 'bg-blue-50/50' : 'hover:bg-accent/50'}`}
                      id={`task-${task.id}`}
                      onClick={() => setExpandedTaskId(isExpanded ? null : task.id)}
                    >
                      <TableCell className="pr-0">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-blue-600" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{task.name}</p>
                          {task.sessionId && (
                            <Link
                              to={`/copilot?session=${task.sessionId}`}
                              onClick={(e: React.MouseEvent) => e.stopPropagation()}
                              className="text-[10px] text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-0.5 mt-0.5"
                            >
                              <Bot className="h-2.5 w-2.5" /> Copilot 对话
                            </Link>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <StatusBadge status={task.status} />
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="flex items-center justify-center gap-1 text-xs">
                          <Database className="h-3 w-3 text-blue-400" /> {task.dataFiles.length}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="flex items-center justify-center gap-1 text-xs">
                          <Box className="h-3 w-3 text-violet-400" /> {task.modelFiles.length}
                        </span>
                      </TableCell>
                      {/* 隐藏源代码列 */}
                      {/* <TableCell className="text-center">
                        <span className="flex items-center justify-center gap-1 text-xs">
                          <Code2 className="h-3 w-3 text-emerald-500" /> {task.codeFiles.length}
                        </span>
                      </TableCell> */}
                      <TableCell className="text-center">
                        {task.inRepo ? (
                          <Badge className="bg-emerald-50 text-emerald-600 border-emerald-200 text-[10px]">
                            <Package className="h-2.5 w-2.5 mr-0.5" /> 已入库
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="text-xs text-muted-foreground">{formatDate(task.updatedAt)}</span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                          {canPushTaskToRepo(task as ModelingTask & Record<string, unknown>) && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={task.inRepo}
                              className={`gap-1 text-[11px] h-7 ${task.inRepo ? 'border-gray-200 text-gray-400 cursor-not-allowed opacity-60' : 'border-blue-200 text-blue-600 hover:bg-blue-50 hover:text-blue-700'}`}
                              onClick={() => !task.inRepo && handlePushToRepo(task.id)}
                            >
                              <Package className="h-3 w-3" /> {task.inRepo ? '已入仓库' : '存入仓库'}
                            </Button>
                          )}
                          {task.status === 'running' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="gap-1 text-[11px] h-7 text-gray-500 hover:text-gray-700"
                              onClick={() => handleArchiveTask(task.id)}
                            >
                              <Archive className="h-3 w-3" /> 归档
                            </Button>
                          )}
                          {task.status === 'failed' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="gap-1 text-[11px] h-7 text-amber-600 hover:text-amber-700"
                              onClick={() => handleArchiveTask(task.id)}
                            >
                              <RotateCcw className="h-3 w-3" /> 重试
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="gap-1 text-[11px] h-7 text-red-500 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDeleteTask(task.id)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {/* Expanded Row */}
                    {isExpanded && (
                      <TableRow key={`${task.id}-detail`} className="hover:bg-transparent">
                        <TableCell colSpan={9} className="p-0 border-b border-border/60">
                          <ExpandedTaskDetail task={task} onPushToRepo={handlePushToRepo} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
              {filteredTasks.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="h-40 text-center">
                    <div className="flex flex-col items-center justify-center text-muted-foreground">
                      <FolderOpen className="h-10 w-10 mb-3" />
                      <p className="text-sm">暂无匹配的建模任务</p>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          )}
          </div>
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-border/60">
              <p className="text-xs text-muted-foreground">
                共 {filteredTasks.length} 条，第 {safeCurrentPage}/{totalPages} 页
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safeCurrentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <Button
                    key={page}
                    variant={page === safeCurrentPage ? 'default' : 'outline'}
                    size="sm"
                    className="h-7 w-7 p-0 text-xs"
                    onClick={() => setCurrentPage(page)}
                  >
                    {page}
                  </Button>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safeCurrentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
