
import { useState } from 'react';
import { ChevronDown, Brain, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ThinkingStep {
  label: string;
  detail: string;
}

export interface ThinkingData {
  steps: ThinkingStep[];
  duration: string;
}

interface ThinkingBubbleProps {
  steps: ThinkingStep[];
  duration?: string;
  defaultOpen?: boolean;
}

export function ThinkingBubble({ steps, duration, defaultOpen = false }: ThinkingBubbleProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mb-1.5">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 text-[12px] rounded-lg px-2.5 py-1.5 transition-all duration-200',
          open
            ? 'bg-violet-50 text-violet-700'
            : 'bg-gray-50 text-gray-500 hover:bg-violet-50 hover:text-violet-600'
        )}
      >
        <Brain className="h-3.5 w-3.5" />
        <span className="font-medium">
          {open ? '思考过程' : `思考了 ${steps.length} 步`}
        </span>
        {duration && (
          <span className="text-[10px] opacity-70">{duration}</span>
        )}
        <ChevronDown
          className={cn(
            'h-3 w-3 transition-transform duration-200',
            open && 'rotate-180'
          )}
        />
      </button>

      {open && (
        <div className="mt-1.5 ml-1 border-l-2 border-violet-200 pl-3 space-y-2 animate-fade-in">
          {steps.map((step, i) => (
            <div key={i} className="flex gap-2 items-start">
              <div className="mt-0.5 shrink-0">
                <Sparkles className="h-3 w-3 text-violet-400" />
              </div>
              <div>
                <div className="text-[12px] font-medium text-violet-700">{step.label}</div>
                <div className="text-[11px] text-gray-500 leading-relaxed">{step.detail}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Generate thinking steps based on user message content keywords
 */
export function generateThinkingSteps(message: string): { steps: ThinkingStep[]; duration: string } {
  const lower = message.toLowerCase();
  const steps: ThinkingStep[] = [];

  if (lower.includes('欺诈') || lower.includes('风控') || lower.includes('反欺诈') || lower.includes('交易')) {
    steps.push(
      { label: '理解业务需求', detail: '识别为反欺诈检测场景，需要精准风控能力' },
      { label: '分析数据特征', detail: '检查交易金额、频率、时段、设备指纹等关键字段' },
      { label: '选择建模策略', detail: '二分类模型优先，考虑样本不均衡处理方案' },
      { label: '规划特征工程', detail: '时序统计特征 + 交叉特征 + 行为画像特征' },
    );
  } else if (lower.includes('信用') || lower.includes('评分') || lower.includes('评分卡') || lower.includes('违约')) {
    steps.push(
      { label: '理解业务需求', detail: '识别为信用评分卡建模场景，需要可解释性强的模型' },
      { label: '分析数据特征', detail: '检查收入、负债比、历史还款记录等核心字段' },
      { label: '选择建模策略', detail: '评分卡模型(Logistic Regression)优先，确保可解释性' },
      { label: '规划特征分箱', detail: '等频/等宽分箱 + WOE编码 + IV值筛选' },
    );
  } else if (lower.includes('数据') || lower.includes('接入') || lower.includes('上传') || lower.includes('csv')) {
    steps.push(
      { label: '解析数据源', detail: '识别文件格式、编码、分隔符' },
      { label: '数据质量检查', detail: '缺失值率、异常值分布、字段类型推断' },
      { label: '特征概览', detail: '数值型/类别型统计、相关性初步分析' },
    );
  } else if (lower.includes('特征') || lower.includes('工程') || lower.includes('筛选') || lower.includes('iv')) {
    steps.push(
      { label: '特征评估', detail: '计算IV值、相关性系数、共线性分析' },
      { label: '特征筛选', detail: '基于IV阈值和相关性矩阵剔除冗余特征' },
      { label: '特征衍生', detail: '交叉特征、多项式特征、时序统计特征' },
    );
  } else if (lower.includes('训练') || lower.includes('模型') || lower.includes('调参') || lower.includes('实验')) {
    steps.push(
      { label: '实验规划', detail: '确定基线算法、超参搜索空间、评估指标' },
      { label: '资源配置', detail: '计算资源评估、交叉验证策略选择' },
      { label: '训练监控', detail: 'Loss曲线、过拟合检测、早停策略' },
    );
  } else if (lower.includes('评估') || lower.includes('ks') || lower.includes('auc') || lower.includes('roc')) {
    steps.push(
      { label: '模型评估', detail: 'KS/AUC/ROC/Gini系数综合评估' },
      { label: '稳定性检查', detail: 'PSI群体稳定性指标、跨时间窗口验证' },
      { label: '业务效果预估', detail: '通过率与捕获率的业务平衡点分析' },
    );
  } else if (lower.includes('部署') || lower.includes('服务') || lower.includes('上线') || lower.includes('推理')) {
    steps.push(
      { label: '部署方案评估', detail: '推理延迟要求、QPS预估、资源需求' },
      { label: '模型格式转换', detail: 'PMML/ONNX格式导出、A/B测试分流配置' },
      { label: '监控配置', detail: '数据漂移告警、服务健康检查、自动回滚策略' },
    );
  } else {
    steps.push(
      { label: '理解意图', detail: '分析用户输入，识别建模需求类型' },
      { label: '检索知识', detail: '从金融建模知识库中检索相关最佳实践' },
      { label: '规划方案', detail: '制定端到端建模流程建议' },
    );
  }

  const durationSec = 2 + steps.length * 1.5;
  return { steps, duration: `${durationSec.toFixed(1)}s` };
}
