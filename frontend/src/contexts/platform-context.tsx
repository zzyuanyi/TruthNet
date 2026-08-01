
import React, { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import {
  type ModelItem,
  type ModelServiceRecord,
  type ModelingTask,
  type ChatSession,
} from '@/lib/demo-data';
import { api } from '@/lib/api-client';
import { useAuth } from '@/contexts/auth-context';

// ========== 类型定义 ==========

export interface ExperimentRecord {
  id: string;
  taskId: string;
  sessionId?: string;
  modelName: string;
  version: string;
  hyperparams: Record<string, string | number>;
  metrics: ModelItem['metrics'];
  trainTime: string;
  gpuUsage: string;
  dataset: string;
  createdAt: string;
  status: 'completed' | 'failed' | 'running';
}

export interface ApprovalRequest {
  id: string;
  serviceId: string;
  modelName: string;
  version: string;
  environment: string;
  requester: string;
  requestedAt: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewer?: string;
  reviewedAt?: string;
  comment?: string;
}

export interface PlatformState {
  models: ModelItem[];
  services: ModelServiceRecord[];
  tasks: ModelingTask[];
  sessions: ChatSession[];
  experiments: ExperimentRecord[];
  approvals: ApprovalRequest[];
}

interface PlatformContextValue extends PlatformState {
  // 模型操作
  addModel: (model: ModelItem) => void;
  // 服务操作
  addService: (service: ModelServiceRecord) => void;
  toggleService: (serviceId: string) => void;
  // 任务操作
  addTask: (task: ModelingTask) => void;
  updateTask: (taskId: string, updates: Partial<ModelingTask>) => void;
  pushToRepo: (taskId: string, backendData?: {
    modelId?: number;
    modelName?: string;
    modelType?: string;
    sceneName?: string;
    framework?: string;
    sampleCount?: number;
    featuresCount?: number;
    version?: string;
    metrics?: Record<string, number>;
  }) => void;
  // 实验追踪
  addExperiment: (exp: ExperimentRecord) => void;
  // 审批
  submitApproval: (serviceId: string) => void;
  approveService: (approvalId: string, reviewer: string, comment?: string) => void;
  rejectService: (approvalId: string, reviewer: string, comment?: string) => void;
}

const PlatformContext = createContext<PlatformContextValue | null>(null);

export function usePlatform(): PlatformContextValue {
  const ctx = useContext(PlatformContext);
  if (!ctx) throw new Error('usePlatform must be used within PlatformProvider');
  return ctx;
}

// ========== 默认状态 ==========

const defaultState: PlatformState = {
  models: [],
  services: [],
  tasks: [],
  sessions: [],
  experiments: [],
  approvals: [],
};

// localStorage key
const STORAGE_KEY = 'finforge-platform-state';

// ========== Provider ==========

export function PlatformProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? '';
  const [state, setState] = useState<PlatformState>(defaultState);
  const [hydrated, setHydrated] = useState(false);

  // 用于防抖保存的 ref
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestStateRef = useRef<PlatformState>(state);

  // 保持 latestStateRef 与 state 同步
  useEffect(() => {
    latestStateRef.current = state;
  }, [state]);

  // 防抖保存到 localStorage
  const saveToStorage = useCallback((data: PlatformState, uid: string) => {
    if (!uid) return;
    try {
      localStorage.setItem(`${STORAGE_KEY}-${uid}`, JSON.stringify(data));
    } catch {
      // 存储满或不可用，静默处理
    }
  }, []);

  // 状态变化时防抖保存
  useEffect(() => {
    if (!hydrated || !userId) return;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      saveToStorage(latestStateRef.current, userId);
    }, 2000);

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [state, hydrated, userId, saveToStorage]);

  // 用户切换时从后端加载数据，localStorage 作为缓存
  useEffect(() => {
    if (!userId) {
      setState(defaultState);
      setHydrated(false);
      return;
    }

    const loadData = async () => {
      try {
        // 先尝试从 localStorage 加载缓存
        const stored = localStorage.getItem(`${STORAGE_KEY}-${userId}`);
        if (stored) {
          const parsed = JSON.parse(stored) as PlatformState;
          if (Array.isArray(parsed.models) && Array.isArray(parsed.services)) {
            setState(parsed);
          }
        }

        // 从后端加载最新数据
        const [modelsData, servicesData, sessionsData] = await Promise.all([
          api.modelsDeploy.list(),
          api.services.list(),
          api.sessions.list(),
        ]);

        // 转换数据格式
        const rawModels = modelsData?.items || [];
        const models: ModelItem[] = rawModels.map((m: any) => ({
          id: String(m.model_id || m.id || ''),
          name: String(m.name || '未命名模型'),
          modelType: String(m.model_type || m.type || 'sklearn'),
          framework: String(m.framework || m.model_type || m.type || 'sklearn'),
          description: String(m.description || ''),
          status: 'stopped',
          sceneName: String(m.scene_name || m.scene || '通用'),
          version: String(m.latest_version || m.version || '1.0.0'),
          createdAt: String(m.created_at || m.createdAt || ''),
          updatedAt: String(m.updated_at || m.updatedAt || m.created_at || m.createdAt || ''),
          sampleCount: Number(m.sample_count || m.sampleCount || 0),
          featuresCount: Number(m.features_count || m.featuresCount || 0),
          metrics: {
            accuracy: Number(m.metrics?.accuracy || 0),
            precision: Number(m.metrics?.precision || 0),
            recall: Number(m.metrics?.recall || 0),
            f1: Number(m.metrics?.f1 || 0),
            auc: Number(m.metrics?.auc || 0),
            pr_auc: Number(m.metrics?.pr_auc || 0),
            log_loss: Number(m.metrics?.log_loss || 0),
            top_k: Number(m.metrics?.top_k || 0),
            ks: Number(m.metrics?.ks || 0),
            psi: Number(m.metrics?.psi || 0),
          },
          artifacts: Array.isArray(m.artifacts) ? m.artifacts : [],
          tags: Array.isArray(m.tags) ? m.tags : [],
          downloadCount: Number(m.download_count || m.downloadCount || 0),
          versions: [],
        }));
        const services: ModelServiceRecord[] = (servicesData?.items || []).map((svc: any) => ({
          id: String(svc.model_service_id || svc.modelServiceId || svc.id || ''),
          modelName: String(svc.model_name || svc.modelName || '未知模型'),
          modelId: String(svc.model_id || svc.modelId || ''),
          modelSlug: String(svc.model_slug || svc.modelSlug || svc.model_service_id || svc.id || 'service'),
          version: String(svc.version || '1.0.0'),
          scene: String(svc.scene || svc.scene_name || '通用'),
          framework: String(svc.framework || 'sklearn'),
          status: svc.status === 'running' ? 'running' : svc.status === 'deploying' ? 'deploying' : svc.status === 'error' ? 'error' : 'stopped',
          environment: 'production',
          instances: Number(svc.instances || 1),
          gpu: String(svc.gpu || '-'),
          qps: Number(svc.qps || 0),
          latency: Number(svc.latency || svc.latencyMs || 0),
          latencyMs: Number(svc.latency_ms || svc.latencyMs || svc.latency || 0),
          errorRate: Number(svc.error_rate || svc.errorRate || 0),
          apiEndpoint: String(svc.endpoint || svc.apiEndpoint || ''),
          serverInfo: String(svc.serverInfo || svc.server_info || ''),
          resourceQuota: String(svc.resourceQuota || svc.resource_quota || ''),
          hourlySuccessRate: String(svc.hourlySuccessRate || svc.hourly_success_rate || ''),
          apiInput: String(svc.apiInput || svc.api_input || '{}'),
          apiOutput: String(svc.apiOutput || svc.api_output || '{}'),
          deployTime: String(svc.created_at || svc.createdAt || ''),
          createdAt: String(svc.created_at || svc.createdAt || ''),
          updateTime: String(svc.updated_at || svc.updatedAt || svc.created_at || svc.createdAt || ''),
          updatedAt: String(svc.updated_at || svc.updatedAt || svc.created_at || svc.createdAt || ''),
          source: 'api',
          tags: Array.isArray(svc.tags) ? svc.tags : [],
        }));
        const sessions = sessionsData?.items || [];

        // 将会话转换为任务
        const tasks: ModelingTask[] = sessions.map((s: any) => ({
          id: String(s.session_id || s.id || ''),
          name: String(s.title || s.project_name || '未命名建模任务'),
          status: 'completed' as const,
          sessionId: String(s.session_id || s.id || ''),
          createdAt: String(s.created_at || ''),
          updatedAt: String(s.updated_at || s.created_at || ''),
          description: `建模任务 · ${s.message_count || 0}条消息`,
          dataFiles: [],
          modelFiles: [],
          codeFiles: [],
          inRepo: !!s.version_count || !!s.bound_model,
          repoModelId: undefined,
        }));

        setState(prev => ({
          ...prev,
          models,
          services,
          sessions,
          tasks,
        }));
      } catch (err) {
        console.error('Failed to load data from backend:', err);
        // 如果后端加载失败，保持 localStorage 的数据或使用默认状态
      } finally {
        setHydrated(true);
      }
    };

    loadData();
  }, [userId]);

  // ========== 操作方法 ==========

  const addModel = useCallback((model: ModelItem) => {
    setState(prev => ({ ...prev, models: [model, ...prev.models] }));
  }, []);

  const addService = useCallback((service: ModelServiceRecord) => {
    setState(prev => ({ ...prev, services: [service, ...prev.services] }));
  }, []);

  const toggleService = useCallback((serviceId: string) => {
    setState(prev => ({
      ...prev,
      services: prev.services.map(s =>
        s.id === serviceId
          ? { ...s, status: s.status === 'running' ? 'stopped' : 'running' }
          : s
      ),
    }));
  }, []);

  const addTask = useCallback((task: ModelingTask) => {
    setState(prev => ({ ...prev, tasks: [task, ...prev.tasks] }));
  }, []);

  const updateTask = useCallback((taskId: string, updates: Partial<ModelingTask>) => {
    setState(prev => ({
      ...prev,
      tasks: prev.tasks.map(t => (t.id === taskId ? { ...t, ...updates } : t)),
    }));
  }, []);

  const pushToRepo = useCallback((taskId: string, backendData?: {
    modelId?: number;
    modelName?: string;
    modelType?: string;
    sceneName?: string;
    framework?: string;
    sampleCount?: number;
    featuresCount?: number;
    version?: string;
    metrics?: Record<string, number>;
  }) => {
    setState(prev => {
      const task = prev.tasks.find(t => t.id === taskId);
      if (!task) return prev;

      const newModel: ModelItem = {
        id: backendData?.modelId?.toString() ?? `model-${Date.now()}`,
        name: backendData?.modelName ?? task.name,
        modelType: backendData?.modelType ?? 'classification',
        sceneName: backendData?.sceneName ?? '',
        framework: backendData?.framework ?? 'AutoML',
        version: backendData?.version ?? 'v1.0',
        status: 'running',
        sampleCount: backendData?.sampleCount ?? 0,
        featuresCount: backendData?.featuresCount ?? 0,
        metrics: {
          accuracy: backendData?.metrics?.accuracy ?? 0,
          precision: backendData?.metrics?.precision ?? 0,
          recall: backendData?.metrics?.recall ?? 0,
          f1: backendData?.metrics?.f1 ?? 0,
          auc: backendData?.metrics?.auc ?? 0,
          pr_auc: backendData?.metrics?.pr_auc ?? 0,
          log_loss: backendData?.metrics?.log_loss ?? 0,
          top_k: backendData?.metrics?.top_k ?? 0,
          ks: backendData?.metrics?.ks ?? 0,
          psi: backendData?.metrics?.psi ?? 0,
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        downloadCount: 0,
        artifacts: [],
        tags: [],
        versions: [],
        description: `${backendData?.sceneName ?? ''} 场景模型`,
      };

      return {
        ...prev,
        tasks: prev.tasks.map(t =>
          t.id === taskId ? { ...t, status: 'completed' as const, progress: 100 } : t
        ),
        models: [newModel, ...prev.models],
      };
    });
  }, []);

  const addExperiment = useCallback((exp: ExperimentRecord) => {
    setState(prev => ({ ...prev, experiments: [exp, ...prev.experiments] }));
  }, []);

  const submitApproval = useCallback((serviceId: string) => {
    const approval: ApprovalRequest = {
      id: `appr-${Date.now()}`,
      serviceId,
      modelName: '',
      version: '',
      environment: 'production',
      requester: 'current-user',
      requestedAt: new Date().toISOString(),
      status: 'pending',
    };
    setState(prev => ({ ...prev, approvals: [approval, ...prev.approvals] }));
  }, []);

  const approveService = useCallback((approvalId: string, reviewer: string, comment?: string) => {
    setState(prev => ({
      ...prev,
      approvals: prev.approvals.map(a =>
        a.id === approvalId
          ? { ...a, status: 'approved' as const, reviewer, reviewedAt: new Date().toISOString(), comment }
          : a
      ),
    }));
  }, []);

  const rejectService = useCallback((approvalId: string, reviewer: string, comment?: string) => {
    setState(prev => ({
      ...prev,
      approvals: prev.approvals.map(a =>
        a.id === approvalId
          ? { ...a, status: 'rejected' as const, reviewer, reviewedAt: new Date().toISOString(), comment }
          : a
      ),
    }));
  }, []);

  const value: PlatformContextValue = {
    ...state,
    addModel,
    addService,
    toggleService,
    addTask,
    updateTask,
    pushToRepo,
    addExperiment,
    submitApproval,
    approveService,
    rejectService,
  };

  return (
    <PlatformContext.Provider value={value}>
      {children}
    </PlatformContext.Provider>
  );
}
