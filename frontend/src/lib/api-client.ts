/**
 * FinForge AI — 前端 API 客户端
 *
 * 严格对接三个后端微服务（最终版接口清单）：
 *   Agent API (8000):  会话管理、SSE对话、仪表盘、认证、搜索、系统配置
 *   File Upload API (8001): 文件上传、解析、列表、状态
 *   Model Deploy Manager (5000): 模型项目、版本、服务实例、推理、Schema
 *
 * 开发模式通过 Vite proxy 转发，生产模式由 Nginx 反代。
 * 所有响应遵循统一格式：{ code, msg, data, timestamp }
 */

const API_BASE = '';

// ---------------------------------------------------------------------------
// 标准响应格式（后端统一规范）
// ---------------------------------------------------------------------------

interface ApiResponse<T = unknown> {
  code: number;       // HTTP 状态码语义: 2xx 成功, 4xx 客户端错误, 5xx 服务端错误
  msg: string;        // 简要信息
  data: T;            // 业务数据，空数据为 {}
  timestamp: number;  // Unix 时间戳（秒）
}

async function request<T>(
  method: string,
  path: string,
  options?: RequestInit & { params?: Record<string, string | number | undefined> }
): Promise<T> {
  const { params, ...fetchOptions } = options || {};

  let url = `${API_BASE}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.set(key, String(value));
    });
    const query = searchParams.toString();
    if (query) url += `?${query}`;
  }

  const res = await fetch(url, {
    ...fetchOptions,
    method,
    headers: {
      // 当body是FormData时，不设置Content-Type（让浏览器自动设置boundary）
      ...(fetchOptions.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...fetchOptions.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }

  const json: ApiResponse<T> = await res.json();
  if (json.code < 200 || json.code >= 300) {
    throw new Error(json.msg || `API Error: code ${json.code}`);
  }

  return json.data as T;
}

// ---------------------------------------------------------------------------
// 公共类型
// ---------------------------------------------------------------------------

export interface PaginatedData<T> {
  items: T[];
  total: number;
}

// ---------------------------------------------------------------------------
// 1.1 会话管理 (Agent API:8000)
// ---------------------------------------------------------------------------

export interface Session {
  sessionId: string;
  title: string;
  createdAt: string;
  updatedAt?: string;
  created_at?: string;
  updated_at?: string;
  files?: DataFile[];
  models?: SessionModel[];
  workflow_state?: string;
  workflow_steps?: WorkflowStep[];
  [key: string]: unknown;
}

export interface Message {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  files?: Array<{ name: string; type: string; size: string; time: string }>;
}

/** GET /api/sessions */
export async function getSessions(params?: { page?: number; pageSize?: number; keyword?: string }) {
  const response = await request<any>('GET', '/api/sessions', { params });
  // Backend returns { sessions: [...] }, convert to { items: [...] } for compatibility
  if (response && response.sessions) {
    return {
      items: response.sessions,
      total: response.sessions.length,
    };
  }
  return response;
}

/** POST /api/sessions */
export async function createSession(title: string) {
  return request<Session>('POST', '/api/sessions', { body: JSON.stringify({ title }) });
}

/** GET /api/sessions/{session_id} */
export async function getSession(sessionId: string) {
  const response = await request<any>('GET', `/api/sessions/${sessionId}`);
  if (response?.session) {
    const session = response.session;
    return {
      ...session,
      sessionId: String(session.sessionId || session.session_id || session.id || sessionId),
      createdAt: String(session.createdAt || session.created_at || ''),
      updatedAt: String(session.updatedAt || session.updated_at || session.created_at || ''),
      latest_files: response.latest_files || [],
      model_files: response.model_files || [],
      models: response.models || [],
      versions: response.versions || [],
      workflow_state: response.workflow_state,
      workflow_steps: response.steps || [],
      file_count: response.file_count || 0,
      model_count: response.model_count || 0,
    } as Session;
  }
  return response as Session;
}

/** PUT /api/sessions/{session_id} */
export async function updateSession(sessionId: string, title: string) {
  return request<Session>('PUT', `/api/sessions/${sessionId}`, { body: JSON.stringify({ title }) });
}

/** DELETE /api/sessions/{session_id} */
export async function deleteSession(sessionId: string) {
  return request<Record<string, never>>('DELETE', `/api/sessions/${sessionId}`);
}

/** GET /api/sessions/{session_id}/history */
export async function getSessionHistory(sessionId: string) {
  const response = await request<any>('GET', `/api/sessions/${sessionId}/history`);
  // 后端返回 {"history": [...]}，转换为 {items: [...]} 兼容格式
  if (response && response.history) {
    return {
      items: response.history,
      total: response.history.length,
    };
  }
  return response;
}

/** POST /api/sessions/{session_id}/clear */
export async function clearSessionHistory(sessionId: string) {
  return request<Record<string, never>>('POST', `/api/sessions/${sessionId}/clear`);
}

/** GET /api/sessions/{session_id}/memory */
export async function getSessionMemory(sessionId: string) {
  return request<Record<string, unknown>>('GET', `/api/sessions/${sessionId}/memory`);
}

/** POST /api/sessions/{session_id}/memory/clear */
export async function clearSessionMemory(sessionId: string) {
  return request<Record<string, never>>('POST', `/api/sessions/${sessionId}/memory/clear`);
}

// ---------------------------------------------------------------------------
// 1.2 对话交互 (Agent API:8000)
// ---------------------------------------------------------------------------

/**
 * POST /api/sessions/{session_id}/message
 * SSE 流式对话，返回原始 Response 供调用方解析事件流
 */
export async function sendSSEMessage(sessionId: string, message: string, stream = true) {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, stream }),
  });
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
  return res;
}

// ---------------------------------------------------------------------------
// 1.3 会话绑定与建模 (Agent API:8000)
// ---------------------------------------------------------------------------

export interface BoundModel {
  modelId: number;
  modelName: string;
}

/** GET /api/sessions/{session_id}/boundModel */
export async function getBoundModel(sessionId: string) {
  return request<BoundModel | null>('GET', `/api/sessions/${sessionId}/boundModel`);
}

/** POST /api/sessions/{session_id}/bindModel */
export async function bindModel(sessionId: string, modelId: number) {
  return request<BoundModel>('POST', `/api/sessions/${sessionId}/bindModel`, {
    body: JSON.stringify({ modelId }),
  });
}

/** DELETE /api/sessions/{session_id}/bindModel */
export async function unbindModel(sessionId: string) {
  return request<Record<string, never>>('DELETE', `/api/sessions/${sessionId}/bindModel`);
}


export interface SessionFile {
  fileId: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  uploadTime: string;
  status?: string;
  path?: string;
  downloadUrl?: string;
  rows?: number;
  columnsCount?: number;
  columns?: string[];
  preview?: Record<string, unknown>[];
}

export interface SessionModelOutput {
  id: string;
  artifactId?: string;
  name: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  createdAt: string;
  modifiedAt?: string;
  downloadUrl: string;
  type?: string;
}

export interface SessionModel {
  modelId?: number | string | null;
  modelName: string;
  modelVersionId?: number | string | null;
  version?: string;
  status?: string;
  time?: string;
}

export interface WorkflowStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  output?: string;
  detail?: string;
}

/** GET /api/sessions/{session_id}/files */
export async function getSessionFiles(sessionId: string) {
  return request<PaginatedData<SessionFile>>('GET', `/api/sessions/${sessionId}/files`);
}

/** GET /api/sessions/{session_id}/model-outputs */
export async function getSessionModelOutputs(sessionId: string) {
  return request<{ items: SessionModelOutput[]; modelItems?: SessionModelOutput[]; codeItems?: SessionModelOutput[]; allItems?: SessionModelOutput[]; total: number }>('GET', `/api/sessions/${sessionId}/model-outputs`);
}

/** GET /api/sessions/{session_id}/models */
export async function getSessionModels(sessionId: string) {
  return request<PaginatedData<SessionModel>>('GET', `/api/sessions/${sessionId}/models`);
}

/** GET /api/sessions/{session_id}/workflow */
export async function getSessionWorkflow(sessionId: string) {
  return request<{ workflow_state: string; steps: WorkflowStep[] }>('GET', `/api/sessions/${sessionId}/workflow`);
}

// ---------------------------------------------------------------------------
// 1.4 非核心功能支持 (Agent API:8000)
// ---------------------------------------------------------------------------

// --- 认证 ---

export interface AuthUser {
  id: string;
  username: string;
  role: string;
  email?: string;
  lastLoginAt?: string;
}

/** POST /api/auth/login */
export async function authLogin(username: string, password: string) {
  return request<{ user: AuthUser; token: string }>('POST', '/api/auth/login', {
    body: JSON.stringify({ username, password }),
  });
}

/** POST /api/auth/register */
export async function authRegister(username: string, password: string, email?: string) {
  return request<{ user: AuthUser; token: string }>('POST', '/api/auth/register', {
    body: JSON.stringify({ username, password, email }),
  });
}

/** POST /api/auth/logout */
export async function authLogout() {
  return request<Record<string, never>>('POST', '/api/auth/logout');
}

/** GET /api/auth/me */
export async function authMe() {
  return request<{ user: AuthUser | null }>('GET', '/api/auth/me');
}

// --- 系统状态 ---

export interface ServiceHealth {
  agent: string;
  file: string;
  deploy: string;
}

/** GET /api/system/health */
export async function getSystemHealth() {
  return request<{ services: ServiceHealth }>('GET', '/api/system/health');
}

/** GET /api/system/capabilities */
export async function getSystemCapabilities() {
  return request<Record<string, unknown>>('GET', '/api/system/capabilities');
}

// --- UI 配置 ---

export interface UIConfig {
  maxUploadSize: number;
  supportedFileTypes: string[];
}

/** GET /api/config/ui */
export async function getUIConfig() {
  return request<UIConfig>('GET', '/api/config/ui');
}

// --- 枚举 ---

/** GET /api/enums/modelTypes */
export async function getModelTypes() {
  return request<{ items: string[] }>('GET', '/api/enums/modelTypes');
}

/** GET /api/enums/scenes */
export async function getScenes() {
  return request<{ items: string[] }>('GET', '/api/enums/scenes');
}

// --- 仪表盘 ---

export interface DashboardData {
  sessionCount: number;
  modelCount: number;
  activeServiceCount: number;
  totalModels?: number;
  totalVersions?: number;
  totalServices?: number;
  runningServices?: number;
  totalRequests?: number;
}

/** GET /api/dashboard/overview */
export async function getDashboard() {
  return request<DashboardData>('GET', '/api/dashboard/overview');
}

/** GET /api/dashboard/sessions */
export async function getDashboardSessions(params?: { limit?: number; status?: string }) {
  return request<PaginatedData<Session>>('GET', '/api/dashboard/sessions', { params });
}

// --- 快捷输入 ---

export interface QuickPrompt {
  id: string;
  title: string;
  prompt: string;
  category?: string;
}

/** GET /api/quick-prompts */
export async function getQuickPrompts() {
  return request<{ items: QuickPrompt[] }>('GET', '/api/quick-prompts');
}

// --- 最近活动 ---

export interface RecentActivity {
  id: string;
  type: string;
  description: string;
  timestamp: string;
}

/** GET /api/recent-activities */
export async function getRecentActivities(params?: { limit?: number }) {
  return request<{ items: RecentActivity[] }>('GET', '/api/recent-activities', { params });
}

// --- 搜索 ---

/** GET /api/sessions/search?keyword=xxx */
export async function searchSessions(keyword: string) {
  return request<PaginatedData<Session>>('GET', '/api/sessions/search', { params: { keyword } });
}

/** GET /api/sessions/{session_id}/messages/search?keyword=xxx */
export async function searchMessages(sessionId: string, keyword: string) {
  return request<PaginatedData<Message>>('GET', `/api/sessions/${sessionId}/messages/search`, {
    params: { keyword },
  });
}

/** GET /api/models/search?keyword=xxx */
export async function searchModels(keyword: string) {
  return request<PaginatedData<Model>>('GET', '/api/models/search', { params: { keyword } });
}

// --- 会话概览 ---

export interface SessionOverview {
  sessionId: string;
  title: string;
  fileCount: number;
  modelCount: number;
  serviceCount: number;
  lastActivity: string;
}

/** GET /api/sessions/{session_id}/overview */
export async function getSessionOverview(sessionId: string) {
  return request<SessionOverview>('GET', `/api/sessions/${sessionId}/overview`);
}

// --- 文件总览 ---

export interface FileOverview {
  totalFiles: number;
  totalSize: string;
  fileTypes: Record<string, number>;
}

/** GET /api/sessions/{session_id}/files/overview */
export async function getSessionFilesOverview(sessionId: string) {
  return request<FileOverview>('GET', `/api/sessions/${sessionId}/files/overview`);
}

/** GET /api/sessions/{session_id}/files/summary */
export async function getSessionFilesSummary(sessionId: string) {
  return request<Record<string, unknown>>('GET', `/api/sessions/${sessionId}/files/summary`);
}

// --- 建模产物 ---

export interface Artifact {
  id: string;
  name: string;
  type: string;
  createdAt: string;
  downloadUrl?: string;
}

/** GET /api/sessions/{session_id}/artifacts */
export async function getSessionArtifacts(sessionId: string) {
  return request<PaginatedData<Artifact>>('GET', `/api/sessions/${sessionId}/artifacts`);
}

/** GET /api/sessions/{session_id}/artifacts/{artifact_id}/download */
export function getArtifactDownloadUrl(sessionId: string, artifactId: string) {
  return `${API_BASE}/api/sessions/${sessionId}/artifacts/${artifactId}/download`;
}

// --- 会话导出 ---

/** GET /api/sessions/{session_id}/export */
export function getSessionExportUrl(sessionId: string) {
  return `${API_BASE}/api/sessions/${sessionId}/export`;
}

/** GET /api/sessions/{session_id}/export/preview */
export async function getSessionExportPreview(sessionId: string) {
  return request<Record<string, unknown>>('GET', `/api/sessions/${sessionId}/export/preview`);
}

// --- 用户偏好 ---

/** GET /api/user/preferences */
export async function getUserPreferences() {
  return request<Record<string, unknown>>('GET', '/api/user/preferences');
}

/** PUT /api/user/preferences */
export async function updateUserPreferences(preferences: Record<string, unknown>) {
  return request<Record<string, unknown>>('PUT', '/api/user/preferences', {
    body: JSON.stringify(preferences),
  });
}

// ---------------------------------------------------------------------------
// 2. File Upload API (端口: 8001)
// ---------------------------------------------------------------------------

export interface DataFile {
  fileId: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  uploadTime: string;
  status?: string;
  rowCount?: number;
  columnCount?: number;
  description?: string;
}

/** POST /api/upload */
export async function uploadDataFile(sessionId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('sessionId', sessionId);
  const payload = await request<Record<string, unknown>>('POST', '/api/upload', {
    body: formData,
  } as RequestInit);

  const fileRecord = ((payload as { file?: Record<string, unknown> } | null)?.file ?? payload ?? {}) as Record<string, unknown>;

  return {
    fileId: String(fileRecord.fileId ?? fileRecord.file_id ?? ''),
    fileName: String(fileRecord.fileName ?? fileRecord.original_name ?? file.name),
    fileSize: Number(fileRecord.fileSize ?? fileRecord.size_bytes ?? file.size ?? 0),
    fileType: String(fileRecord.fileType ?? fileRecord.file_type ?? file.name.split('.').pop()?.toLowerCase() ?? 'file'),
    uploadTime: String(fileRecord.uploadTime ?? fileRecord.created_at ?? new Date().toISOString()),
    status: fileRecord.status ? String(fileRecord.status) : (fileRecord.parse_status ? String(fileRecord.parse_status) : undefined),
  } satisfies DataFile;
}

/** GET /api/files/{session_id} */
export async function getDataFiles(sessionId: string) {
  return request<PaginatedData<DataFile>>('GET', `/api/files/${sessionId}`);
}

/** GET /api/files/{session_id}/{file_id} */
export async function getDataFile(sessionId: string, fileId: string) {
  return request<DataFile>('GET', `/api/files/${sessionId}/${fileId}`);
}

/** DELETE /api/files/{session_id}/{file_id} */
export async function deleteDataFile(sessionId: string, fileId: string) {
  return request<Record<string, never>>('DELETE', `/api/files/${sessionId}/${fileId}`);
}

/** POST /api/files/{file_id}/parse */
export async function parseDataFile(fileId: string) {
  return request<Record<string, unknown>>('POST', `/api/files/${fileId}/parse`);
}

/** GET /api/files/{file_id}/status */
export async function getDataFileStatus(fileId: string) {
  return request<{ status: string; progress?: number }>('GET', `/api/files/${fileId}/status`);
}

/** GET /api/files/{file_id}/parsedData */
export async function getParsedData(fileId: string) {
  return request<Record<string, unknown>>('GET', `/api/files/${fileId}/parsedData`);
}

/** GET /api/files/{session_id}/outputs */
export async function listSessionOutputs(sessionId: string) {
  return request<DataFile[]>('GET', `/api/files/${sessionId}/outputs`);
}

// ---------------------------------------------------------------------------
// 3. Model Deploy Manager (端口: 5000)
// ---------------------------------------------------------------------------

export interface Model {
  model_id: number;
  id?: string | number;
  name: string;
  description?: string;
  model_type?: string;
  type?: string;
  scene_name?: string;
  scene?: string;
  archived?: boolean;
  created_at?: string;
  createdAt?: string;
  version_count?: number;
  latest_version?: string;
}

/** GET /api/models */
export async function getModels(params?: { page?: number; pageSize?: number; keyword?: string }) {
  return request<PaginatedData<Model>>('GET', '/api/models', { params });
}

/** POST /api/models */
export async function createModel(data: { name: string; description?: string; type?: string; scene?: string; model_type?: string; scene_name?: string; session_id?: string; repository_name?: string }) {
  const formData = new FormData();
  formData.append('name', data.name);
  formData.append('description', data.description || '');
  formData.append('repository_name', data.repository_name || '');
  if (data.session_id) formData.append('session_id', data.session_id);
  return request<Model>('POST', '/api/models', { body: formData } as RequestInit);
}

/** GET /api/models/{model_id} */
export async function getModel(modelId: number) {
  return request<Model>('GET', `/api/models/${modelId}`);
}

/** PUT /api/models/{model_id} */
export async function updateModel(modelId: number, data: { name?: string; description?: string }) {
  return request<Model>('PUT', `/api/models/${modelId}`, { body: JSON.stringify(data) });
}

/** DELETE /api/models/{model_id} */
export async function deleteModel(modelId: number) {
  return request<Record<string, never>>('DELETE', `/api/models/${modelId}`);
}

/** POST /api/models/{model_id}/pushToRepo */
export async function pushToRepo(modelId: number) {
  return request<Record<string, unknown>>('POST', `/api/models/${modelId}/pushToRepo`);
}

/** GET /api/models/{model_id}/lineage */
export async function getModelLineage(modelId: number) {
  return request<Record<string, unknown>>('GET', `/api/models/${modelId}/lineage`);
}

/** POST /api/models/preparse */
export async function preparseModel(data: Record<string, unknown>) {
  return request<Record<string, unknown>>('POST', '/api/models/preparse', { body: JSON.stringify(data) });
}

// --- 模型版本 ---

export interface ModelVersion {
  model_version_id: number;
  model_id: number;
  version_tag: string;
  description?: string;
  parser_status?: string;
  created_at?: string;
  createdAt?: string;
  file_path?: string;
  filePath?: string;
  metrics?: Record<string, number>;
}

/** GET /api/models/{model_id}/versions */
export async function getModelVersions(modelId: number) {
  return request<PaginatedData<ModelVersion>>('GET', `/api/models/${modelId}/versions`);
}

/** POST /api/models/{model_id}/versions/upload */
export async function uploadModelVersion(modelId: number, data: { version: string; description?: string; file: File; model_type?: string; scene_name?: string; session_id?: string; metrics_json?: string }) {
  if (!data.file) throw new Error('上传模型版本需要真实模型文件');
  const formData = new FormData();
  formData.append('version_tag', data.version);
  formData.append('model_type', data.model_type || 'sklearn');
  if (data.description) formData.append('description', data.description);
  if (data.scene_name) formData.append('scene_name', data.scene_name);
  if (data.session_id) formData.append('session_id', data.session_id);
  if (data.metrics_json) formData.append('metrics_json', data.metrics_json);
  formData.append('file', data.file);
  return request<ModelVersion>('POST', `/api/models/${modelId}/versions/upload`, {
    body: formData,
  } as RequestInit);
}

/** GET /api/model-versions/{model_version_id} */
export async function getModelVersion(versionId: number) {
  return request<ModelVersion>('GET', `/api/model-versions/${versionId}`);
}

/** DELETE /api/model-versions/{model_version_id} */
export async function deleteModelVersion(versionId: number) {
  return request<Record<string, never>>('DELETE', `/api/model-versions/${versionId}`);
}

/** GET /api/model-versions/{model_version_id}/status */
export async function getModelVersionStatus(versionId: number) {
  return request<{ status: string }>('GET', `/api/model-versions/${versionId}/status`);
}

/** GET /api/model-versions/{model_version_id}/evaluation */
export async function getModelVersionEvaluation(versionId: number) {
  return request<Record<string, unknown>>('GET', `/api/model-versions/${versionId}/evaluation`);
}

// --- 服务实例 ---

export interface ServiceInstance {
  model_service_id: string;
  modelServiceId?: string;
  id?: string;
  model_version_id: number;
  modelVersionId?: number;
  model_name?: string;
  modelName?: string;
  version?: string;
  status: string;
  created_at?: string;
  createdAt?: string;
  endpoint?: string;
  config?: Record<string, unknown>;
}

/** GET /api/service-instances */
export async function getServiceInstances(params?: { page?: number; pageSize?: number }) {
  return request<PaginatedData<ServiceInstance>>('GET', '/api/service-instances', { params });
}

/** POST /api/model-versions/{model_version_id}/service-instances */
export async function createServiceInstance(versionId: number, config?: Record<string, unknown>) {
  return request<ServiceInstance>('POST', `/api/model-versions/${versionId}/service-instances`, {
    body: JSON.stringify(config || {}),
  });
}

/** POST /api/service-instances/{model_service_id}/start */
export async function startServiceInstance(serviceId: string) {
  return request<ServiceInstance>('POST', `/api/service-instances/${serviceId}/start`);
}

/** GET /api/service-instances/{model_service_id} */
export async function getServiceInstance(serviceId: string) {
  return request<ServiceInstance>('GET', `/api/service-instances/${serviceId}`);
}

/** POST /api/service-instances/{model_service_id}/stop */
export async function stopServiceInstance(serviceId: string) {
  return request<Record<string, never>>('POST', `/api/service-instances/${serviceId}/stop`);
}

/** DELETE /api/service-instances/{model_service_id} */
export async function deleteServiceInstance(serviceId: string) {
  return request<Record<string, never>>('DELETE', `/api/service-instances/${serviceId}`);
}

/** POST /api/service-instances/{model_service_id}/predict */
export async function predict(serviceId: string | number, data: { features?: Record<string, unknown>; [key: string]: unknown }) {
    return request<{
        code: number;
        data: {
            prediction: Record<string, unknown> | unknown;
            latency_ms?: number;
        }
    }>('POST', `/api/service-instances/${serviceId}/predict`, {
        body: JSON.stringify(data),
    });
}

// --- 流水线 ---

export interface Pipeline {
  id: number | string;
  name: string;
  description?: string;
  status?: string;
  steps?: PipelineStep[];
  currentStep?: number | string;
  result_message?: string;
  model_id?: number | string;
  createdAt?: string;
  updatedAt?: string;
}

export interface PipelineStep {
  name: string;
  type: string;
  status?: string;
  config?: Record<string, unknown>;
}

/** GET /api/pipelines */
export async function getPipelines(params?: { page?: number; pageSize?: number }) {
  return request<PaginatedData<Pipeline>>('GET', '/api/pipelines', { params });
}

/** POST /api/pipelines */
export async function createPipeline(data: { name: string; description?: string; steps?: PipelineStep[] }) {
  return request<Pipeline>('POST', '/api/pipelines', { body: JSON.stringify(data) });
}

/** GET /api/pipelines/{pipeline_id} */
export async function getPipeline(pipelineId: number | string) {
  return request<Pipeline>('GET', `/api/pipelines/${pipelineId}`);
}

/** DELETE /api/pipelines/{pipeline_id} */
export async function deletePipeline(pipelineId: number) {
  return request<Record<string, never>>('DELETE', `/api/pipelines/${pipelineId}`);
}

/** POST /api/pipelines/{pipeline_id}/execute */
export async function executePipeline(pipelineId: number) {
  return request<Pipeline>('POST', `/api/pipelines/${pipelineId}/execute`);
}

/** POST /api/pipelines/{pipeline_id}/execute-step */
export async function executePipelineStep(pipelineId: number, stepIndex: number) {
  return request<Pipeline>('POST', `/api/pipelines/${pipelineId}/execute-step`, {
    body: JSON.stringify({ stepIndex }),
  });
}

// --- 监控 ---

export interface MonitorPoint {
  timestamp: string;
  qps: number;
  latencyP50: number;
  latencyP99: number;
  errorRate: number;
}

/** GET /api/service-monitor */
export async function getServiceMonitor() {
  return request<{ data: MonitorPoint[] }>('GET', '/api/service-monitor');
}

// --- Schema 管理 ---

/** POST /api/schema/template */
export async function getSchemaTemplate(data: Record<string, unknown>) {
  return request<Record<string, unknown>>('POST', '/api/schema/template', { body: JSON.stringify(data) });
}

/** POST /api/schema/confirm */
export async function confirmSchema(data: Record<string, unknown>) {
  return request<Record<string, unknown>>('POST', '/api/schema/confirm', { body: JSON.stringify(data) });
}

/** POST /api/schema/validate */
export async function validateSchema(data: Record<string, unknown>) {
  return request<{ valid: boolean; errors?: string[] }>('POST', '/api/schema/validate', {
    body: JSON.stringify(data),
  });
}

// --- 建模进度 ---

export interface ModelingRun {
  runId: string;
  sessionId: string;
  status: string;
  progress: number;
  currentStep?: string;
  createdAt: string;
}

/** GET /api/modeling-runs/{run_id}/progress */
export async function getModelingRunProgress(runId: string) {
  return request<ModelingRun>('GET', `/api/modeling-runs/${runId}/progress`);
}

/** GET /api/sessions/{session_id}/modeling-runs/latest */
export async function getLatestModelingRun(sessionId: string) {
  return request<ModelingRun>('GET', `/api/sessions/${sessionId}/modeling-runs/latest`);
}

// --- 模型仓库详情 ---

/** GET /api/repository/{repo_id}/detail */
export async function getRepositoryDetail(repoId: string) {
  return request<Record<string, unknown>>('GET', `/api/repository/${repoId}/detail`);
}

// ---------------------------------------------------------------------------
// 统一导出 api 对象（方便组件中使用 api.xxx.yyy() 风格调用）
// ---------------------------------------------------------------------------

export const api = {
  // 1.1 会话管理
  sessions: {
    list: getSessions,
    create: createSession,
    get: getSession,
    update: updateSession,
    delete: deleteSession,
    history: getSessionHistory,
    clear: clearSessionHistory,
    memory: getSessionMemory,
    clearMemory: clearSessionMemory,
    overview: getSessionOverview,
    search: searchSessions,
    searchMessages,
    filesOverview: getSessionFilesOverview,
    filesSummary: getSessionFilesSummary,
    files: getSessionFiles,
    modelOutputs: getSessionModelOutputs,
    models: getSessionModels,
    workflow: getSessionWorkflow,
    artifacts: getSessionArtifacts,
    artifactDownloadUrl: getArtifactDownloadUrl,
    exportUrl: getSessionExportUrl,
    exportPreview: getSessionExportPreview,
    boundModel: getBoundModel,
    bindModel,
    unbindModel,
  },

  // 1.2 对话交互
  chat: {
    send: sendSSEMessage,
  },

  // 1.4 非核心功能
  auth: {
    login: authLogin,
    register: authRegister,
    logout: authLogout,
    me: authMe,
  },
  system: {
    health: getSystemHealth,
    capabilities: getSystemCapabilities,
  },
  config: {
    ui: getUIConfig,
  },
  enums: {
    modelTypes: getModelTypes,
    scenes: getScenes,
  },
  dashboard: {
    overview: getDashboard,
    sessions: getDashboardSessions,
  },
  quickPrompts: {
    list: getQuickPrompts,
  },
  recentActivities: {
    list: getRecentActivities,
  },
  models: {
    search: searchModels,
    list: getModels,
  },
  user: {
    preferences: getUserPreferences,
    updatePreferences: updateUserPreferences,
  },

  // 2. 文件上传
  files: {
    upload: uploadDataFile,
    list: getDataFiles,
    get: getDataFile,
    delete: deleteDataFile,
    parse: parseDataFile,
    status: getDataFileStatus,
    parsedData: getParsedData,
  },

  // 3. 模型部署管理
  modelsDeploy: {
    list: getModels,
    create: createModel,
    get: getModel,
    update: updateModel,
    delete: deleteModel,
    pushToRepo,
    lineage: getModelLineage,
    preparse: preparseModel,
    versions: getModelVersions,
    uploadVersion: uploadModelVersion,
    getVersion: getModelVersion,
    deleteVersion: deleteModelVersion,
    versionStatus: getModelVersionStatus,
    versionEvaluation: getModelVersionEvaluation,
    repositoryDetail: getRepositoryDetail,
  },
  services: {
    list: getServiceInstances,
    create: createServiceInstance,
    start: startServiceInstance,
    get: getServiceInstance,
    stop: stopServiceInstance,
    delete: deleteServiceInstance,
    predict,
  },
  pipelines: {
    list: getPipelines,
    create: createPipeline,
    get: getPipeline,
    delete: deletePipeline,
    execute: executePipeline,
    executeStep: executePipelineStep,
  },
  monitor: {
    getData: getServiceMonitor,
  },
  schema: {
    template: getSchemaTemplate,
    confirm: confirmSchema,
    validate: validateSchema,
  },
  modelingRuns: {
    progress: getModelingRunProgress,
    latest: getLatestModelingRun,
  },
};
