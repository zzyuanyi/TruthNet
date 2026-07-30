// Demo data service for FinForge AI platform
// Provides mock data that mirrors the Python backend's API responses

export interface ModelVersion {
  version: string;
  status: 'current' | 'archived' | 'deprecated';
  createdAt: string;
  metrics: ModelItem['metrics'];
  artifacts: string[];
  changelog: string;
  downloadCount: number;
  fileSize: string;
}

export interface ModelItem {
  id: string;
  name: string;
  modelType: string;
  framework: string;
  description?: string;
  status: 'running' | 'stopped' | 'error' | 'deploying';
  sceneName: string;
  version: string;
  createdAt: string;
  updatedAt: string;
  sampleCount: number;
  featuresCount: number;
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
    auc: number;
    pr_auc: number;
    log_loss: number;
    top_k: number;
    ks: number;
    psi: number;
  };
  artifacts: string[];
  tags: string[];
  downloadCount: number;
  versions: ModelVersion[];
}

export interface ProjectItem {
  id: string;
  name: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  versions: {
    id: string;
    version: string;
    status: string;
    artifacts: string[];
    createdAt: string;
  }[];
}

export interface ChatSession {
  id: string;
  title: string;
  status: string;
  progress: string;
  time: string;
  messages: { role: 'user' | 'ai'; text: string; timestamp?: string; thinking?: { steps: { label: string; detail: string }[]; duration: string }; files?: { name: string; size: string; type: string; id?: number | string; time?: string; sizeBytes?: number; rows?: number; columnsCount?: number; columns?: string[] }[] }[];
  pinned?: boolean;
  createdAt?: string;
  files?: { name: string; type: 'input' | 'output'; size: string | number; time: string; id?: number | string; sizeBytes?: number; rows?: number; columnsCount?: number; columns?: string[] }[];
  models?: { name: string; version: string; status: 'running' | 'stopped' | 'training' | 'deployed'; time: string }[];
  _streamingText?: string;
  _thinking?: { steps: { label: string; detail: string }[]; duration: string };
}

export const demoModels: ModelItem[] = [
  {
    id: '1',
    name: '反欺诈实时风控模型',
    modelType: '二分类模型',
    framework: 'sklearn / LogisticRegression',
    status: 'running',
    sceneName: '反欺诈检测',
    version: '3.0',
    createdAt: '2025-05-10T09:32:00Z',
    updatedAt: '2025-05-15T16:42:00Z',
    sampleCount: 1256842,
    featuresCount: 32,
    metrics: {
      accuracy: 0.968,
      precision: 0.962,
      recall: 0.955,
      f1: 0.958,
      auc: 0.989,
      pr_auc: 0.976,
      log_loss: 0.089,
      top_k: 0.942, ks: 0.568, psi: 0.052},
    artifacts: ['model.pkl', 'schema.json', 'eval_report.pdf', 'features.json'],
    tags: ['反欺诈', '实时推理', '风控'],
    downloadCount: 1286,
    versions: [
      {
        version: '3.0v', status: 'current', createdAt: '2025-05-15T16:42:00Z',
        metrics: { accuracy: 0.968, precision: 0.962, recall: 0.955, f1: 0.958, auc: 0.989, pr_auc: 0.976, log_loss: 0.089, top_k: 0.942, ks: 0.568, psi: 0.052},
        artifacts: ['model.pkl', 'schema.json', 'eval_report.pdf', 'features.json'],
        changelog: '新增时序衍生特征8个，Recall提升3.2%，PR-AUC提升1.5%',
        downloadCount: 486, fileSize: '45.7 MB',
      },
      {
        version: '2.0v', status: 'archived', createdAt: '2025-05-12T14:20:00Z',
        metrics: { accuracy: 0.952, precision: 0.948, recall: 0.923, f1: 0.935, auc: 0.981, pr_auc: 0.961, log_loss: 0.118, top_k: 0.928, ks: 0.56, psi: 0.057},
        artifacts: ['model.pkl', 'schema.json'],
        changelog: '优化特征交叉策略，Precision提升2.1%',
        downloadCount: 580, fileSize: '42.3 MB',
      },
      {
        version: '1.0v', status: 'deprecated', createdAt: '2025-05-10T09:30:00Z',
        metrics: { accuracy: 0.921, precision: 0.915, recall: 0.898, f1: 0.906, auc: 0.962, pr_auc: 0.938, log_loss: 0.178, top_k: 0.891, ks: 0.54, psi: 0.068},
        artifacts: ['model.pkl'],
        changelog: '初始版本，基线模型',
        downloadCount: 220, fileSize: '38.1 MB',
      },
    ],
  },
  {
    id: '2',
    name: '信用评分卡模型',
    modelType: '二分类模型',
    framework: 'sklearn / GradientBoosting',
    status: 'stopped',
    sceneName: '信用风险评估',
    version: '3.0',
    createdAt: '2025-05-08T14:20:00Z',
    updatedAt: '2025-05-12T11:30:00Z',
    sampleCount: 856000,
    featuresCount: 28,
    metrics: {
      accuracy: 0.945,
      precision: 0.938,
      recall: 0.921,
      f1: 0.929,
      auc: 0.978,
      pr_auc: 0.965,
      log_loss: 0.134,
      top_k: 0.912, ks: 0.552, psi: 0.061},
    artifacts: ['model.pkl', 'schema.json', 'eval_report.pdf'],
    tags: ['信用评分', 'WOE编码', '可解释'],
    downloadCount: 864,
    versions: [
      {
        version: '3.0v', status: 'current', createdAt: '2025-05-12T11:30:00Z',
        metrics: { accuracy: 0.945, precision: 0.938, recall: 0.921, f1: 0.929, auc: 0.978, pr_auc: 0.965, log_loss: 0.134, top_k: 0.912, ks: 0.552, psi: 0.061},
        artifacts: ['model.pkl', 'schema.json', 'eval_report.pdf'],
        changelog: '优化WOE分箱策略，新增稳定性指标PSI监控',
        downloadCount: 312, fileSize: '39.2 MB',
      },
      {
        version: '2.0v', status: 'archived', createdAt: '2025-05-10T08:00:00Z',
        metrics: { accuracy: 0.931, precision: 0.925, recall: 0.908, f1: 0.916, auc: 0.971, pr_auc: 0.952, log_loss: 0.162, top_k: 0.896, ks: 0.543, psi: 0.066},
        artifacts: ['model.pkl', 'schema.json'],
        changelog: '修复评分卡刻度偏移问题',
        downloadCount: 348, fileSize: '37.8 MB',
      },
      {
        version: '1.0v', status: 'deprecated', createdAt: '2025-05-08T14:15:00Z',
        metrics: { accuracy: 0.918, precision: 0.912, recall: 0.895, f1: 0.903, auc: 0.958, pr_auc: 0.936, log_loss: 0.195, top_k: 0.872, ks: 0.53, psi: 0.073},
        artifacts: ['model.pkl'],
        changelog: '初始版本，标准评分卡流程',
        downloadCount: 204, fileSize: '35.4 MB',
      },
    ],
  },
  {
    id: '3',
    name: '反电诈特征增强模型',
    modelType: '二分类模型',
    framework: 'onnx / XGBoost',
    status: 'running',
    sceneName: '实时反电诈',
    version: '3.0',
    createdAt: '2025-05-12T08:15:00Z',
    updatedAt: '2025-05-15T10:20:00Z',
    sampleCount: 2100000,
    featuresCount: 45,
    metrics: {
      accuracy: 0.972,
      precision: 0.965,
      recall: 0.958,
      f1: 0.961,
      auc: 0.992,
      pr_auc: 0.981,
      log_loss: 0.072,
      top_k: 0.955, ks: 0.575, psi: 0.049},
    artifacts: ['model.onnx', 'schema.json', 'features.json', 'eval_report.pdf'],
    tags: ['反电诈', '特征增强', 'ONNX'],
    downloadCount: 2150,
    versions: [
      {
        version: '3.0v', status: 'current', createdAt: '2025-05-15T10:20:00Z',
        metrics: { accuracy: 0.972, precision: 0.965, recall: 0.958, f1: 0.961, auc: 0.992, pr_auc: 0.981, log_loss: 0.072, top_k: 0.955, ks: 0.575, psi: 0.049},
        artifacts: ['model.onnx', 'schema.json', 'features.json', 'eval_report.pdf'],
        changelog: '新增图结构特征，F1提升4.2%，迁移至ONNX推理引擎',
        downloadCount: 892, fileSize: '38.2 MB',
      },
      {
        version: '2.0v', status: 'archived', createdAt: '2025-05-13T16:00:00Z',
        metrics: { accuracy: 0.948, precision: 0.941, recall: 0.919, f1: 0.930, auc: 0.979, pr_auc: 0.958, log_loss: 0.125, top_k: 0.916, ks: 0.554, psi: 0.06},
        artifacts: ['model.onnx', 'schema.json'],
        changelog: '引入交叉特征编码，AUC提升1.8%',
        downloadCount: 758, fileSize: '35.6 MB',
      },
      {
        version: '1.0v', status: 'deprecated', createdAt: '2025-05-12T08:10:00Z',
        metrics: { accuracy: 0.925, precision: 0.918, recall: 0.901, f1: 0.909, auc: 0.961, pr_auc: 0.942, log_loss: 0.172, top_k: 0.885, ks: 0.537, psi: 0.069},
        artifacts: ['model.onnx'],
        changelog: '初始版本，基线XGBoost模型',
        downloadCount: 500, fileSize: '32.1 MB',
      },
    ],
  },
  {
    id: '4',
    name: '客户流失预测模型',
    modelType: '二分类模型',
    framework: 'sklearn / RandomForest',
    status: 'stopped',
    sceneName: '客户留存分析',
    version: '1.0',
    createdAt: '2025-05-05T16:45:00Z',
    updatedAt: '2025-05-09T09:10:00Z',
    sampleCount: 520000,
    featuresCount: 22,
    metrics: {
      accuracy: 0.891,
      precision: 0.875,
      recall: 0.862,
      f1: 0.868,
      auc: 0.945,
      pr_auc: 0.928,
      log_loss: 0.245,
      top_k: 0.885, ks: 0.537, psi: 0.069},
    artifacts: ['model.pkl', 'schema.json'],
    tags: ['客户流失', '预测分析', 'RandomForest'],
    downloadCount: 432,
    versions: [
      {
        version: '1.0v', status: 'current', createdAt: '2025-05-09T09:10:00Z',
        metrics: { accuracy: 0.891, precision: 0.875, recall: 0.862, f1: 0.868, auc: 0.945, pr_auc: 0.928, log_loss: 0.245, top_k: 0.885, ks: 0.537, psi: 0.069},
        artifacts: ['model.pkl', 'schema.json'],
        changelog: '初始版本，RandomForest基线',
        downloadCount: 432, fileSize: '28.6 MB',
      },
    ],
  },
  {
    id: '5',
    name: '高维特征回归模型',
    modelType: '回归模型',
    framework: 'onnx / LightGBM',
    status: 'error',
    sceneName: '额度预测',
    version: '2.0',
    createdAt: '2025-05-13T10:00:00Z',
    updatedAt: '2025-05-14T08:30:00Z',
    sampleCount: 980000,
    featuresCount: 1000,
    metrics: {
      accuracy: 0.0,
      precision: 0.0,
      recall: 0.0,
      f1: 0.0,
      auc: 0.0,
      pr_auc: 0.0,
      log_loss: 0.0,
      top_k: 0.0, ks: 0.0, psi: 0.0},
    artifacts: ['model.onnx', 'features_ordered.json'],
    tags: ['额度预测', '高维特征', 'LightGBM'],
    downloadCount: 156,
    versions: [
      {
        version: '2.0v', status: 'current', createdAt: '2025-05-14T08:30:00Z',
        metrics: { accuracy: 0.0, precision: 0.0, recall: 0.0, f1: 0.0, auc: 0.0, pr_auc: 0.0, log_loss: 0.0, top_k: 0.0, ks: 0.0, psi: 0.0},
        artifacts: ['model.onnx', 'features_ordered.json'],
        changelog: '1000维特征版本，训练异常中断',
        downloadCount: 42, fileSize: '86.3 MB',
      },
      {
        version: '1.0v', status: 'archived', createdAt: '2025-05-13T10:00:00Z',
        metrics: { accuracy: 0.872, precision: 0.858, recall: 0.841, f1: 0.849, auc: 0.931, pr_auc: 0.912, log_loss: 0.281, top_k: 0.856, ks: 0.521, psi: 0.078},
        artifacts: ['model.onnx'],
        changelog: '初始版本，100维特征基线',
        downloadCount: 114, fileSize: '31.2 MB',
      },
    ],
  },
];

export const demoProjects: ProjectItem[] = [
  {
    id: 'p1',
    name: '反欺诈检测建模',
    status: '已完成',
    createdAt: '2025-05-10T09:30:00Z',
    updatedAt: '2025-05-15T16:42:00Z',
    versions: [
      { id: 'v1', version: '3.0v', status: '已入仓', artifacts: ['model.pkl', 'schema.json', 'eval_report.pdf'], createdAt: '2025-05-15T16:42:00Z' },
      { id: 'v2', version: '2.0v', status: '已入仓', artifacts: ['model.pkl', 'schema.json'], createdAt: '2025-05-12T14:20:00Z' },
      { id: 'v3', version: '1.0v', status: '已归档', artifacts: ['model.pkl'], createdAt: '2025-05-10T09:30:00Z' },
    ],
  },
  {
    id: 'p2',
    name: '信用评分卡模型',
    status: '已完成',
    createdAt: '2025-05-08T14:15:00Z',
    updatedAt: '2025-05-12T11:30:00Z',
    versions: [
      { id: 'v4', version: '3.0v', status: '已入仓', artifacts: ['model.pkl', 'schema.json', 'eval_report.pdf'], createdAt: '2025-05-12T11:30:00Z' },
      { id: 'v5', version: '2.0v', status: '已入仓', artifacts: ['model.pkl', 'schema.json'], createdAt: '2025-05-10T08:00:00Z' },
    ],
  },
  {
    id: 'p3',
    name: '反电诈特征增强模型',
    status: '进行中',
    createdAt: '2025-05-12T08:10:00Z',
    updatedAt: '2025-05-15T10:20:00Z',
    versions: [
      { id: 'v6', version: '3.0v', status: '可部署', artifacts: ['model.onnx', 'schema.json', 'features.json'], createdAt: '2025-05-15T10:20:00Z' },
      { id: 'v7', version: '2.0v', status: '已入仓', artifacts: ['model.onnx', 'schema.json'], createdAt: '2025-05-13T16:00:00Z' },
    ],
  },
  {
    id: 'p4',
    name: '客户流失预测',
    status: '已完成',
    createdAt: '2025-05-05T16:40:00Z',
    updatedAt: '2025-05-09T09:10:00Z',
    versions: [
      { id: 'v8', version: '1.0v', status: '已入仓', artifacts: ['model.pkl', 'schema.json'], createdAt: '2025-05-09T09:10:00Z' },
    ],
  },
  {
    id: 'p5',
    name: '高维特征回归建模',
    status: '进行中',
    createdAt: '2025-05-13T09:55:00Z',
    updatedAt: '2025-05-14T08:30:00Z',
    versions: [
      { id: 'v9', version: '2.0v', status: '可部署', artifacts: ['model.onnx', 'features_ordered.json'], createdAt: '2025-05-14T08:30:00Z' },
    ],
  },
];

export const demoSessions: ChatSession[] = [
  {
    id: 's1',
    title: '反欺诈检测建模',
    status: '模型训练完成',
    progress: '准备评估与部署',
    time: '16:42',
    createdAt: '2025-05-15T15:30:00',
    files: [
      { name: 'transaction_data_2025.csv', type: 'input', size: '256 MB', time: '2025-05-15 15:35' },
      { name: 'data_analysis_report.pdf', type: 'output', size: '2.1 MB', time: '2025-05-15 15:38' },
      { name: 'feature_engineering_result.json', type: 'output', size: '890 KB', time: '2025-05-15 16:10' },
      { name: 'eval_report_3.0v.pdf', type: 'output', size: '1.8 MB', time: '2025-05-15 16:42' },
      { name: 'features_ordered.json', type: 'output', size: '45 KB', time: '2025-05-15 16:42' },
    ],
    models: [
      { name: '反欺诈实时风控模型', version: '3.0v', status: 'running', time: '2025-05-15 16:42' },
      { name: '反欺诈实时风控模型', version: '2.0v', status: 'stopped', time: '2025-05-12 14:20' },
      { name: '反欺诈实时风控模型', version: '1.0v', status: 'stopped', time: '2025-05-10 09:30' },
    ],
    messages: [
      { role: 'ai', text: '你好，我是 FinForge AI 智能建模 Copilot。我可以帮你完成从数据分析到模型部署的全流程建模任务。请告诉我你的建模目标，或直接上传数据开始。', timestamp: '2025-05-15T15:30:00' },
      { role: 'user', text: '我需要构建一个反欺诈检测模型，数据已经准备好了，是脱敏后的业务数据。', timestamp: '2025-05-15T15:31:00' },
      { role: 'ai', text: '收到！针对反欺诈检测场景，我建议以下建模路线：\n\n1. **数据质量检查**：缺失值、异常值、类别分布\n2. **特征工程**：基于行为特征（频率、金额分布、时间模式等）构建衍生特征\n3. **模型选择**：推荐使用 XGBoost/LightGBM，适合类别不平衡的反欺诈场景\n4. **评估策略**：采用 PR-AUC + 精准率为主指标，Recall 作为辅助\n\n请上传你的数据文件，我将开始自动分析。', timestamp: '2025-05-15T15:31:30' },
      { role: 'user', text: '数据已上传，请开始分析', timestamp: '2025-05-15T15:35:00' },
      { role: 'ai', text: '数据分析完成，以下是关键发现：\n\n📊 **数据概览**\n- 样本总量：1,256,842 条\n- 特征字段：32 个\n- 正样本比例：3.2%（高度不平衡）\n- 缺失率：最高 8.3%（transaction_desc 字段）\n\n🔍 **关键特征分布**\n- 交易金额呈现右偏分布，异常交易金额中位数偏高\n- 夜间交易（22:00-06:00）欺诈比例显著高于白天\n- 新账户首笔大额转账是高风险信号\n\n我将进入特征工程阶段，自动构建时序特征和交叉特征。', timestamp: '2025-05-15T15:38:00' },
      { role: 'ai', text: '特征工程完成！共构建 45 个特征，其中：\n\n- 原始特征：32 个\n- 时序衍生特征：8 个（近1h/24h交易频率、金额变化率等）\n- 交叉特征：5 个（金额×时段、频率×账户年龄等）\n\n平均 IV 值：0.38，其中 12 个特征 IV > 0.3（强预测力）\n\n已自动选择 XGBoost 进行模型训练，正在调参中...', timestamp: '2025-05-15T16:10:00' },
      { role: 'ai', text: '模型训练完成！核心指标如下：\n\n| 指标 | 值 |\n|------|------|\n| Precision | 0.965 |\n| Recall | 0.958 |\n| F1 Score | 0.961 |\n| PR-AUC | 0.981 |\n| ROC-AUC | 0.992 |\n\n精准率达到 0.965，已超过 0.95 的目标阈值。模型已自动入仓，你可以前往模型仓库查看详情，或直接部署为在线推理服务。', timestamp: '2025-05-15T16:42:00' },
    ],
  },
  {
    id: 's2',
    title: '信用评分卡建模',
    status: '特征工程进行中',
    progress: '自动特征筛选',
    time: '14:20',
    createdAt: '2025-05-15T13:50:00',
    files: [
      { name: 'credit_data_2025.csv', type: 'input', size: '180 MB', time: '2025-05-15 13:55' },
      { name: 'data_analysis_report.pdf', type: 'output', size: '1.5 MB', time: '2025-05-15 14:00' },
    ],
    models: [
      { name: '信用评分卡模型', version: '3.0v', status: 'stopped', time: '2025-05-12 11:30' },
    ],
    messages: [
      { role: 'ai', text: '你好，我是 FinForge AI 智能建模 Copilot。请告诉我你的目标。', timestamp: '2025-05-15T13:50:00' },
      { role: 'user', text: '构建信用评分卡模型，用于贷款审批', timestamp: '2025-05-15T13:51:00' },
      { role: 'ai', text: '好的，信用评分卡模型需要特别注意特征的可解释性和稳定性。我将按照标准评分卡流程进行建模：\n\n1. 数据探索与质量检查\n2. WOE 分箱与 IV 值筛选\n3. 逻辑回归建模（保证可解释性）\n4. 评分卡刻度转换\n\n请上传数据开始。', timestamp: '2025-05-15T13:52:00' },
    ],
  },
  {
    id: 's3',
    title: '反电诈特征增强',
    status: '数据分析中',
    progress: '生成特征工程建议',
    time: '10:15',
    createdAt: '2025-05-15T10:00:00',
    files: [
      { name: 'fraud_call_data.csv', type: 'input', size: '92 MB', time: '2025-05-15 10:05' },
    ],
    models: [],
    messages: [
      { role: 'ai', text: '你好，我是 FinForge AI 智能建模 Copilot。请告诉我你的目标。', timestamp: '2025-05-15T10:00:00' },
      { role: 'user', text: '需要设计实时反电诈特征，要求业务可解释性好', timestamp: '2025-05-15T10:01:00' },
      { role: 'ai', text: '反电诈场景对实时性和可解释性要求很高。我将重点设计以下几类特征：\n\n1. **交易行为特征**：转账频率、金额突变、夜间交易占比\n2. **账户画像特征**：账户年龄、历史交易模式、异常登录\n3. **关系网络特征**：资金流向集中度、关联账户风险传播\n\n这些特征都具有良好的业务可解释性。请上传数据，我将进行自动化特征设计。', timestamp: '2025-05-15T10:02:00' },
    ],
  },
];

export const workflowSteps = [
  { name: '数据接入', status: 'completed' as const },
  { name: '特征工程', status: 'completed' as const },
  { name: '模型训练', status: 'completed' as const },
  { name: '模型评估', status: 'in_progress' as const },
];

// ===== 模型服务（部署记录） =====
export interface ModelServiceRecord {
  id: string;
  modelName: string;        // 部署的模型名称
  modelId: string;          // 关联仓库模型ID
  modelSlug: string;        // 模型路由标识 (用于API路由，如 fraud-detect)
  version: string;          // 部署版本号
  scene: string;            // 场景
  framework: string;        // 框架
  status: 'running' | 'stopped' | 'deploying' | 'error';
  environment: 'production' | 'staging' | 'testing';
  instances: number;        // 实例数
  gpu: string;              // GPU配置
  qps: number;              // 当前QPS
  latency: number;          // 平均延迟(ms)
  latencyMs: number;        // 别名: 平均延迟(ms)
  errorRate: number;        // 错误率(0-1)
  requestCount?: number;    // 后端真实请求次数
  lastRequestAt?: string;   // 后端最近请求时间
  apiEndpoint: string;      // 统一API地址 (统一端口 + model_id 路由)
  serverInfo: string;             // 部署服务器信息
  resourceQuota: string;          // 允许使用的资源配额
  hourlySuccessRate: string;      // 每小时请求成功率
  apiInput: string;               // API 输入 JSON 示例
  apiOutput: string;              // API 输出 JSON 示例
  deployTime: string;        // 部署时间
  createdAt: string;         // 创建时间
  updateTime: string;        // 更新时间
  updatedAt: string;         // 别名: 更新时间
  source: 'copilot' | 'manual' | 'api';  // 部署来源
  sourceTaskId?: string;    // 如果来自copilot，关联的任务ID
  sourceSessionId?: string; // 关联的copilot会话ID
  tags: string[];           // 标签
  approvalStatus?: 'none' | 'pending' | 'approved' | 'rejected'; // 审批状态
  approvalRequestedAt?: string; // 申请审批时间
  approvedBy?: string;     // 审批人
  approvedAt?: string;     // 审批时间
}

export const demoServiceRecords: ModelServiceRecord[] = [
  {
    id: 'svc-001',
    modelName: '反欺诈实时风控模型',
    modelId: '1',
    modelSlug: 'fraud-detect',
    version: '3.0v',
    scene: '反欺诈检测',
    framework: 'sklearn / LogisticRegression',
    status: 'running',
    environment: 'production',
    instances: 4,
    gpu: 'A100 x2',
    qps: 128,
    latency: 45,
    latencyMs: 45,
    errorRate: 0.001,
    apiEndpoint: '/api/v1/predict/fraud-detect',
    serverInfo: 'NVIDIA DGX A100 集群, 节点 node-01',
    resourceQuota: 'CPU 16核 / 内存 64GB / GPU A100 x2',
    hourlySuccessRate: '99.97%',
    apiInput: JSON.stringify({transaction_id: 'txn_20250516_001', amount: 5280.50, merchant_category: 'electronics', card_type: 'credit', hour_of_day: 14, is_weekend: false, distance_from_home: 3.2, distance_from_last_txn: 0.8, ratio_to_median_amount: 4.5, is_online: true}, null, 2),
    apiOutput: JSON.stringify({fraud_probability: 0.87, risk_level: 'high', decision: 'reject', model_version: '3.0v', explain_features: [{feature: 'ratio_to_median_amount', contribution: 0.35}, {feature: 'is_online', contribution: 0.22}]}, null, 2),
    deployTime: '2025-05-10T10:30:00Z',
    createdAt: '2025-05-10T10:30:00Z',
    updateTime: '2025-05-15T16:42:00Z',
    updatedAt: '2025-05-15T16:42:00Z',
    source: 'copilot',
    tags: ['生产', '高可用'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-002',
    modelName: '信用评分卡模型',
    modelId: '2',
    modelSlug: 'credit-score',
    version: '2.0v',
    scene: '信用评分',
    framework: 'XGBoost',
    status: 'running',
    environment: 'production',
    instances: 3,
    gpu: 'A100 x1',
    qps: 85,
    latency: 38,
    latencyMs: 38,
    errorRate: 0.0005,
    apiEndpoint: '/api/v1/predict/credit-score',
    serverInfo: 'NVIDIA DGX A100 集群, 节点 node-02',
    resourceQuota: 'CPU 12核 / 内存 48GB / GPU A100 x1',
    hourlySuccessRate: '99.95%',
    apiInput: JSON.stringify({customer_id: 'cust_88234', age: 35, income: 280000, debt_ratio: 0.32, credit_history_months: 120, num_open_accounts: 4, num_delinquencies: 0, employment_years: 8}, null, 2),
    apiOutput: JSON.stringify({credit_score: 720, score_range: 'good', pd: 0.018, model_version: '2.0v', key_factors: [{factor: 'credit_history_months', impact: 'positive'}, {factor: 'num_delinquencies', impact: 'positive'}]}, null, 2),
    deployTime: '2025-05-08T14:20:00Z',
    createdAt: '2025-05-08T14:20:00Z',
    updateTime: '2025-05-14T11:30:00Z',
    updatedAt: '2025-05-14T11:30:00Z',
    source: 'copilot',
    tags: ['生产'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-003',
    modelName: '反电诈特征增强模型',
    modelId: '4',
    modelSlug: 'anti-telecom-fraud',
    version: '1.0v',
    scene: '反电诈识别',
    framework: 'LightGBM',
    status: 'stopped',
    environment: 'staging',
    instances: 1,
    gpu: 'V100 x1',
    qps: 0,
    latency: 0,
    latencyMs: 0,
    errorRate: 0,
    apiEndpoint: '/api/v1/predict/anti-telecom-fraud-v2',
    serverInfo: '预发服务器 staging-node-01',
    resourceQuota: 'CPU 4核 / 内存 16GB / GPU V100 x1',
    hourlySuccessRate: '—',
    apiInput: JSON.stringify({call_id: 'call_20250516_001', duration_seconds: 45, call_type: 'incoming', caller_region: 'high_risk', is_international: false, freq_last_24h: 8, is_new_contact: true, user_age_group: 'senior'}, null, 2),
    apiOutput: JSON.stringify({fraud_probability: 0.92, risk_level: 'high', fraud_type: 'telecom', model_version: '1.0v', alert_actions: ['block_call', 'send_sms_warning']}, null, 2),
    deployTime: '2025-04-28T09:15:00Z',
    createdAt: '2025-04-28T09:15:00Z',
    updateTime: '2025-05-01T08:00:00Z',
    updatedAt: '2025-05-01T08:00:00Z',
    source: 'manual',
    tags: ['预发', '待验证'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-004',
    modelName: '客户流失预测模型',
    modelId: '3',
    modelSlug: 'churn',
    version: '2.0v',
    scene: '客户流失预测',
    framework: 'RandomForest',
    status: 'running',
    environment: 'production',
    instances: 2,
    gpu: 'A100 x1',
    qps: 56,
    latency: 62,
    latencyMs: 62,
    errorRate: 0.002,
    apiEndpoint: '/api/v1/predict/churn',
    serverInfo: 'NVIDIA DGX A100 集群, 节点 node-03',
    resourceQuota: 'CPU 8核 / 内存 32GB / GPU A100 x1',
    hourlySuccessRate: '99.92%',
    apiInput: JSON.stringify({customer_id: 'cust_55123', tenure_months: 6, monthly_charges: 89.5, total_charges: 537, contract_type: 'month_to_month', internet_service: 'fiber', has_phone_service: true, num_tickets: 3}, null, 2),
    apiOutput: JSON.stringify({churn_probability: 0.73, risk_level: 'high', retention_action: 'offer_discount', model_version: '2.0v', key_drivers: [{driver: 'contract_type', impact: 0.38}, {driver: 'num_tickets', impact: 0.25}]}, null, 2),
    deployTime: '2025-05-05T11:00:00Z',
    createdAt: '2025-05-05T11:00:00Z',
    updateTime: '2025-05-13T15:20:00Z',
    updatedAt: '2025-05-13T15:20:00Z',
    source: 'copilot',
    tags: ['生产'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-005',
    modelName: '高维特征回归模型',
    modelId: '5',
    modelSlug: 'default-prob',
    version: '1.0v',
    scene: '违约概率预测',
    framework: 'Neural Network',
    status: 'error',
    environment: 'testing',
    instances: 1,
    gpu: 'T4 x1',
    qps: 0,
    latency: 0,
    latencyMs: 0,
    errorRate: 0.125,
    apiEndpoint: '/api/v1/predict/default-prob',
    serverInfo: '测试服务器 test-node-05',
    resourceQuota: 'CPU 4核 / 内存 16GB / GPU T4 x1',
    hourlySuccessRate: '87.50%',
    apiInput: JSON.stringify({loan_id: 'loan_20250516_001', loan_amount: 500000, annual_income: 180000, credit_score: 650, debt_to_income: 0.45, employment_status: 'employed', loan_purpose: 'business', collateral_value: 300000}, null, 2),
    apiOutput: JSON.stringify({default_probability: 0.15, risk_grade: 'B', suggested_rate: 0.068, model_version: '1.0v', risk_factors: [{factor: 'debt_to_income', impact: 0.30}, {factor: 'credit_score', impact: 0.28}]}, null, 2),
    deployTime: '2025-05-12T16:45:00Z',
    createdAt: '2025-05-12T16:45:00Z',
    updateTime: '2025-05-16T09:30:00Z',
    updatedAt: '2025-05-16T09:30:00Z',
    source: 'api',
    tags: ['测试', '异常'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-006',
    modelName: '反欺诈实时风控模型',
    modelId: '1',
    modelSlug: 'fraud-detect',
    version: '3.0v',
    scene: '反欺诈检测',
    framework: 'sklearn / LogisticRegression',
    status: 'running',
    environment: 'production',
    instances: 4,
    gpu: 'A100 x2',
    qps: 210,
    latency: 28,
    latencyMs: 28,
    errorRate: 0.0003,
    apiEndpoint: '/api/v1/predict/anti-telecom-fraud-v2',
    serverInfo: 'NVIDIA DGX A100 集群, 节点 node-04',
    resourceQuota: 'CPU 8核 / 内存 32GB / GPU A100 x2',
    hourlySuccessRate: '99.99%',
    apiInput: JSON.stringify({transaction_id: 'txn_20250516_002', amount: 1200.00, merchant_category: 'food', card_type: 'debit', hour_of_day: 22, is_weekend: true, distance_from_home: 15.6, distance_from_last_txn: 12.3, ratio_to_median_amount: 0.8, is_online: false}, null, 2),
    apiOutput: JSON.stringify({fraud_probability: 0.12, risk_level: 'low', decision: 'approve', model_version: '3.0v', explain_features: [{feature: 'ratio_to_median_amount', contribution: 0.08}, {feature: 'is_online', contribution: 0.03}]}, null, 2),
    deployTime: '2025-05-11T08:00:00Z',
    createdAt: '2025-05-11T08:00:00Z',
    updateTime: '2025-05-15T20:10:00Z',
    updatedAt: '2025-05-15T20:10:00Z',
    source: 'copilot',
    tags: ['生产', '高可用'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-007',
    modelName: '信用评分卡模型',
    modelId: '2',
    modelSlug: 'credit-score',
    version: '2.0v',
    scene: '信用评分',
    framework: 'XGBoost',
    status: 'stopped',
    environment: 'testing',
    instances: 1,
    gpu: 'T4 x1',
    qps: 0,
    latency: 0,
    latencyMs: 0,
    errorRate: 0,
    apiEndpoint: '/api/v1/predict/credit-score-v2',
    serverInfo: '测试服务器 test-node-07',
    resourceQuota: 'CPU 2核 / 内存 8GB / GPU T4 x1',
    hourlySuccessRate: '—',
    apiInput: JSON.stringify({customer_id: 'cust_11234', age: 28, income: 150000, debt_ratio: 0.45, credit_history_months: 36, num_open_accounts: 6, num_delinquencies: 2, employment_years: 3}, null, 2),
    apiOutput: JSON.stringify({credit_score: 580, score_range: 'fair', pd: 0.085, model_version: '2.0v', key_factors: [{factor: 'num_delinquencies', impact: 'negative'}, {factor: 'debt_ratio', impact: 'negative'}]}, null, 2),
    deployTime: '2025-04-20T13:30:00Z',
    createdAt: '2025-04-20T13:30:00Z',
    updateTime: '2025-04-25T10:00:00Z',
    updatedAt: '2025-04-25T10:00:00Z',
    source: 'manual',
    tags: ['测试', '已停用'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-008',
    modelName: '反欺诈实时风控模型',
    modelId: '1',
    modelSlug: 'fraud-detect',
    version: '3.0v',
    scene: '反欺诈检测',
    framework: 'sklearn / LogisticRegression',
    status: 'stopped',
    environment: 'staging',
    instances: 1,
    gpu: 'V100 x1',
    qps: 0,
    latency: 0,
    latencyMs: 0,
    errorRate: 0,
    apiEndpoint: '/api/v1/predict/fraud-detect-staging',
    serverInfo: '预发服务器 staging-node-02',
    resourceQuota: 'CPU 2核 / 内存 8GB / GPU T4 x1',
    hourlySuccessRate: '—',
    apiInput: JSON.stringify({transaction_id: 'txn_stg_001', amount: 999.99, merchant_category: 'travel', card_type: 'credit', hour_of_day: 10, is_weekend: false, distance_from_home: 50.0, distance_from_last_txn: 45.2, ratio_to_median_amount: 1.2, is_online: true}, null, 2),
    apiOutput: JSON.stringify({fraud_probability: 0.35, risk_level: 'medium', decision: 'review', model_version: '3.0v', explain_features: [{feature: 'distance_from_home', contribution: 0.18}, {feature: 'distance_from_last_txn', contribution: 0.15}]}, null, 2),
    deployTime: '2025-04-15T07:00:00Z',
    createdAt: '2025-04-15T07:00:00Z',
    updateTime: '2025-04-18T12:00:00Z',
    updatedAt: '2025-04-18T12:00:00Z',
    source: 'manual',
    tags: ['预发', '灰度'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-009',
    modelName: '反电诈特征增强模型',
    modelId: '4',
    modelSlug: 'anti-telecom-fraud',
    version: '2.0v',
    scene: '反电诈识别',
    framework: 'LightGBM',
    status: 'running',
    environment: 'production',
    instances: 3,
    gpu: 'A100 x2',
    qps: 95,
    latency: 52,
    latencyMs: 52,
    errorRate: 0.001,
    apiEndpoint: '/api/v1/predict/anti-telecom-fraud',
    serverInfo: 'NVIDIA DGX A100 集群, 节点 node-05',
    resourceQuota: 'CPU 12核 / 内存 48GB / GPU A100 x2',
    hourlySuccessRate: '99.96%',
    apiInput: JSON.stringify({call_id: 'call_20250516_002', duration_seconds: 120, call_type: 'outgoing', caller_region: 'normal', is_international: true, freq_last_24h: 1, is_new_contact: false, user_age_group: 'adult'}, null, 2),
    apiOutput: JSON.stringify({fraud_probability: 0.05, risk_level: 'low', fraud_type: 'none', model_version: '2.0v', alert_actions: []}, null, 2),
    deployTime: '2025-05-03T15:00:00Z',
    createdAt: '2025-05-03T15:00:00Z',
    updateTime: '2025-05-14T18:30:00Z',
    updatedAt: '2025-05-14T18:30:00Z',
    source: 'copilot',
    tags: ['生产'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-010',
    modelName: '信用评分卡模型',
    modelId: '2',
    modelSlug: 'credit-score',
    version: '2.0v',
    scene: '信用评分',
    framework: 'XGBoost',
    status: 'stopped',
    environment: 'staging',
    instances: 1,
    gpu: 'T4 x1',
    qps: 0,
    latency: 0,
    latencyMs: 0,
    errorRate: 0,
    apiEndpoint: '/api/v1/predict/credit-score-staging',
    serverInfo: '预发服务器 staging-node-02',
    resourceQuota: 'CPU 2核 / 内存 8GB / GPU T4 x1',
    hourlySuccessRate: '—',
    apiInput: JSON.stringify({customer_id: 'cust_stg_001', age: 45, income: 350000, debt_ratio: 0.18, credit_history_months: 240, num_open_accounts: 2, num_delinquencies: 0, employment_years: 15}, null, 2),
    apiOutput: JSON.stringify({credit_score: 810, score_range: 'excellent', pd: 0.003, model_version: '2.0v', key_factors: [{factor: 'credit_history_months', impact: 'positive'}, {factor: 'debt_ratio', impact: 'positive'}]}, null, 2),
    deployTime: '2025-04-10T09:00:00Z',
    createdAt: '2025-04-10T09:00:00Z',
    updateTime: '2025-04-12T14:00:00Z',
    updatedAt: '2025-04-12T14:00:00Z',
    source: 'manual',
    tags: ['预发'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-011',
    modelName: '客户流失预测模型',
    modelId: '3',
    modelSlug: 'churn',
    version: '2.0v',
    scene: '客户流失预测',
    framework: 'RandomForest',
    status: 'running',
    environment: 'production',
    instances: 2,
    gpu: 'A100 x1',
    qps: 72,
    latency: 45,
    latencyMs: 45,
    errorRate: 0.001,
    apiEndpoint: '/api/v1/predict/churn-v2',
    serverInfo: 'NVIDIA DGX A100 集群, 节点 node-06',
    resourceQuota: 'CPU 8核 / 内存 32GB / GPU A100 x1',
    hourlySuccessRate: '99.96%',
    apiInput: JSON.stringify({customer_id: 'cust_77890', tenure_months: 24, monthly_charges: 45.0, total_charges: 1080, contract_type: 'one_year', internet_service: 'dsl', has_phone_service: false, num_tickets: 1}, null, 2),
    apiOutput: JSON.stringify({churn_probability: 0.18, risk_level: 'low', retention_action: 'none', model_version: '2.0v', key_drivers: [{driver: 'contract_type', impact: 0.12}, {driver: 'tenure_months', impact: 0.09}]}, null, 2),
    deployTime: '2025-05-07T12:00:00Z',
    createdAt: '2025-05-07T12:00:00Z',
    updateTime: '2025-05-15T10:00:00Z',
    updatedAt: '2025-05-15T10:00:00Z',
    source: 'copilot',
    tags: ['生产'],
    approvalStatus: 'none',
  },
  {
    id: 'svc-012',
    modelName: '高维特征回归模型',
    modelId: '5',
    modelSlug: 'default-prob',
    version: '1.0v',
    scene: '违约概率预测',
    framework: 'Neural Network',
    status: 'stopped',
    environment: 'testing',
    instances: 1,
    gpu: 'T4 x1',
    qps: 0,
    latency: 0,
    latencyMs: 0,
    errorRate: 0,
    apiEndpoint: '/api/v1/predict/default-prob-test',
    serverInfo: '测试服务器 test-node-12',
    resourceQuota: 'CPU 2核 / 内存 8GB / GPU T4 x1',
    hourlySuccessRate: '—',
    apiInput: JSON.stringify({loan_id: 'loan_test_001', loan_amount: 100000, annual_income: 120000, credit_score: 720, debt_to_income: 0.25, employment_status: 'employed', loan_purpose: 'housing', collateral_value: 200000}, null, 2),
    apiOutput: JSON.stringify({default_probability: 0.03, risk_grade: 'A', suggested_rate: 0.045, model_version: '1.0v', risk_factors: [{factor: 'credit_score', impact: 0.35}, {factor: 'debt_to_income', impact: 0.20}]}, null, 2),
    deployTime: '2025-04-22T10:00:00Z',
    createdAt: '2025-04-22T10:00:00Z',
    updateTime: '2025-04-25T16:00:00Z',
    updatedAt: '2025-04-25T16:00:00Z',
    source: 'api',
    tags: ['测试', '已停用'],
    approvalStatus: 'none',
  },
];

export const inferenceTasks = [
  {
    name: '日交易实时评分任务_20250515',
    type: '实时推理',
    source: 'API 请求',
    status: '运行中',
    createdAt: '2025-05-15 08:00:00',
    completedAt: '-',
  },
  {
    name: '历史交易批量评分_20250514',
    type: '批量推理',
    source: '上传文件',
    status: '已完成',
    createdAt: '2025-05-14 18:22:10',
    completedAt: '2025-05-14 18:45:32',
  },
  {
    name: '新账户风险初筛_20250513',
    type: '实时推理',
    source: 'API 请求',
    status: '已完成',
    createdAt: '2025-05-13 09:15:00',
    completedAt: '2025-05-13 09:15:45',
  },
];

export function formatNumber(num: number, digits = 3): string {
  return Number.isFinite(num) ? num.toFixed(digits) : '-';
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return String(dateStr);
  return d.toLocaleString('zh-CN', { hour12: false });
}

export function formatCompact(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return String(num);
}

/* ─── Modeling Task Types & Data ─── */
export interface TaskArtifact {
  id?: string;
  name: string;
  type: 'data' | 'model' | 'code' | 'report';
  size: string;
  time: string;
  sizeBytes?: number;
  url?: string;
  createdAt?: string;
  rows?: number;
  columnsCount?: number;
  columns?: string[];
  preview?: Record<string, unknown>[];
}

export interface ModelingTask {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'archived' | 'failed';
  sessionId?: string;
  createdAt: string;
  updatedAt: string;
  description: string;
  dataFiles: TaskArtifact[];
  modelFiles: TaskArtifact[];
  codeFiles: TaskArtifact[];
  inRepo: boolean;
  repoModelId?: string;
}

export const demoTasks: ModelingTask[] = [
  {
    id: 't1',
    name: '反欺诈检测建模',
    status: 'completed',
    sessionId: 's1',
    createdAt: '2025-05-15T15:30:00',
    updatedAt: '2025-05-15T16:42:00',
    description: '基于脱敏交易流水数据，构建实时反欺诈风控模型，覆盖特征工程、XGBoost训练、模型评估全流程',
    dataFiles: [
      { name: 'transaction_data_2025.csv', type: 'data', size: '256 MB', time: '2025-05-15 15:35' },
      { name: 'data_analysis_report.pdf', type: 'report', size: '2.1 MB', time: '2025-05-15 15:38' },
    ],
    modelFiles: [
      { name: 'anti_fraud_model_3.0v.pkl', type: 'model', size: '45.7 MB', time: '2025-05-15 16:42' },
      { name: 'anti_fraud_model_3.0v.onnx', type: 'model', size: '38.2 MB', time: '2025-05-15 16:42' },
      { name: 'schema.json', type: 'model', size: '12.4 KB', time: '2025-05-15 16:42' },
      { name: 'features_ordered.json', type: 'model', size: '9.1 KB', time: '2025-05-15 16:42' },
      { name: 'eval_report_3.0v.pdf', type: 'report', size: '1.8 MB', time: '2025-05-15 16:42' },
    ],
    codeFiles: [
      { name: 'feature_engineering.py', type: 'code', size: '12.8 KB', time: '2025-05-15 16:10' },
      { name: 'train_xgboost.py', type: 'code', size: '8.5 KB', time: '2025-05-15 16:40' },
      { name: 'evaluate_model.py', type: 'code', size: '6.2 KB', time: '2025-05-15 16:42' },
    ],
    inRepo: true,
    repoModelId: '1',
  },
  {
    id: 't2',
    name: '信用评分卡建模',
    status: 'running',
    sessionId: 's2',
    createdAt: '2025-05-15T13:50:00',
    updatedAt: '2025-05-15T14:20:00',
    description: '构建标准信用评分卡模型，使用WOE分箱+逻辑回归，保证可解释性',
    dataFiles: [
      { name: 'credit_data_2025.csv', type: 'data', size: '180 MB', time: '2025-05-15 13:55' },
      { name: 'data_analysis_report.pdf', type: 'report', size: '1.5 MB', time: '2025-05-15 14:00' },
    ],
    modelFiles: [],
    codeFiles: [
      { name: 'woe_binning.py', type: 'code', size: '9.4 KB', time: '2025-05-15 14:05' },
    ],
    inRepo: false,
  },
  {
    id: 't3',
    name: '反电诈特征增强',
    status: 'running',
    sessionId: 's3',
    createdAt: '2025-05-15T10:00:00',
    updatedAt: '2025-05-15T10:20:00',
    description: '基于通信行为数据构建反电诈特征增强模型，引入图结构特征',
    dataFiles: [
      { name: 'fraud_call_data.csv', type: 'data', size: '92 MB', time: '2025-05-15 10:05' },
    ],
    modelFiles: [],
    codeFiles: [],
    inRepo: false,
  },
  {
    id: 't4',
    name: '客户流失预测尝试',
    status: 'archived',
    createdAt: '2025-05-14T09:00:00',
    updatedAt: '2025-05-14T11:30:00',
    description: '尝试用RandomForest做客户流失预测，效果不理想已归档，未存入仓库',
    dataFiles: [
      { name: 'customer_churn_data.csv', type: 'data', size: '45 MB', time: '2025-05-14 09:05' },
    ],
    modelFiles: [
      { name: 'churn_model_1.0v.pkl', type: 'model', size: '28.6 MB', time: '2025-05-14 11:30' },
    ],
    codeFiles: [
      { name: 'exploratory_analysis.py', type: 'code', size: '5.2 KB', time: '2025-05-14 09:30' },
    ],
    inRepo: false,
  },
  {
    id: 't5',
    name: '高维特征回归尝试',
    status: 'failed',
    createdAt: '2025-05-13T10:00:00',
    updatedAt: '2025-05-14T08:30:00',
    description: '1000维特征额度预测模型，训练过程中断，LightGBM内存溢出',
    dataFiles: [
      { name: 'credit_limit_data.csv', type: 'data', size: '380 MB', time: '2025-05-13 10:10' },
    ],
    modelFiles: [],
    codeFiles: [
      { name: 'high_dim_feature_eng.py', type: 'code', size: '15.3 KB', time: '2025-05-13 11:00' },
      { name: 'train_lightgbm.py', type: 'code', size: '7.1 KB', time: '2025-05-13 14:00' },
    ],
    inRepo: false,
  },
  {
    id: 't6',
    name: '违约概率预测尝试',
    status: 'archived',
    createdAt: '2025-05-12T08:00:00',
    updatedAt: '2025-05-12T15:00:00',
    description: '尝试性建模，数据特征覆盖不足，AUC仅0.82，未达标已归档',
    dataFiles: [
      { name: 'default_data_v1.csv', type: 'data', size: '120 MB', time: '2025-05-12 08:10' },
    ],
    modelFiles: [
      { name: 'default_model_1.0v.pkl', type: 'model', size: '22.1 MB', time: '2025-05-12 15:00' },
    ],
    codeFiles: [
      { name: 'train_default_model.py', type: 'code', size: '6.8 KB', time: '2025-05-12 14:30' },
    ],
    inRepo: false,
  },
];
