// @ts-nocheck — Recharts Tooltip formatter type mismatch is expected with v3
'use client';

import { useMemo, Fragment } from 'react';
import { cn } from '@/lib/utils';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, AreaChart, BarChart, Bar, Cell
} from 'recharts';

function ChartEmpty({ label, height = 280 }: { label: string; height?: number }) {
  return (
    <div className="flex items-center justify-center rounded-md border border-dashed border-border/70 bg-muted/20 text-sm text-muted-foreground" style={{ height }}>
      {label}
    </div>
  );
}

/**
 * KS 曲线图 - 金融风控核心指标
 * 展示正负样本累积分布差异，KS值 = max(|TPR - FPR|)
 */
interface KSCurveProps {
  data?: Array<{ threshold: number; tpr: number; fpr: number; ks: number }>;
  ksValue?: number;
  height?: number;
}

const DEFAULT_KS_DATA = [
  { threshold: 0.0, tpr: 1.000, fpr: 1.000, ks: 0.000 },
  { threshold: 0.1, tpr: 0.945, fpr: 0.782, ks: 0.163 },
  { threshold: 0.2, tpr: 0.872, fpr: 0.568, ks: 0.304 },
  { threshold: 0.3, tpr: 0.764, fpr: 0.374, ks: 0.390 },
  { threshold: 0.4, tpr: 0.623, fpr: 0.218, ks: 0.405 },
  { threshold: 0.5, tpr: 0.478, fpr: 0.112, ks: 0.366 },
  { threshold: 0.6, tpr: 0.334, fpr: 0.052, ks: 0.282 },
  { threshold: 0.7, tpr: 0.201, fpr: 0.019, ks: 0.182 },
  { threshold: 0.8, tpr: 0.098, fpr: 0.006, ks: 0.092 },
  { threshold: 0.9, tpr: 0.032, fpr: 0.001, ks: 0.031 },
  { threshold: 1.0, tpr: 0.000, fpr: 0.000, ks: 0.000 },
];

export function KSCurveChart({ data, ksValue = 0, height = 300 }: KSCurveProps) {
  const safeData = Array.isArray(data) ? data : [];
  const maxKSPoint = useMemo(() => {
    let max = 0;
    let threshold = 0;
    for (const d of safeData) {
      if (d.ks > max) { max = d.ks; threshold = d.threshold; }
    }
    return { max, threshold };
  }, [safeData]);

  if (safeData.length === 0) return <ChartEmpty label="暂无真实 KS 曲线数据" height={height} />;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">KS 曲线</span>
        <span className="text-sm font-semibold text-blue-600">KS = {ksValue.toFixed(3)}</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={safeData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="threshold" type="number" domain={[0, 1]} tickFormatter={(v: number) => v.toFixed(1)} label={{ value: '阈值', position: 'insideBottomRight', offset: -5, fontSize: 12 }} />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip
            formatter={(value: number, name: string) => {
              const labels: Record<string, string> = { tpr: '正样本累计率(TPR)', fpr: '负样本累计率(FPR)', ks: 'KS值' };
              return [`${(value * 100).toFixed(1)}%`, labels[name] || name];
            }}
            labelFormatter={(label: number) => `阈值: ${label.toFixed(2)}`}
          />
          <Legend formatter={(value: string) => {
            const labels: Record<string, string> = { tpr: '正样本累计率(TPR)', fpr: '负样本累计率(FPR)', ks: 'KS差异' };
            return labels[value] || value;
          }} />
          <Area type="monotone" dataKey="tpr" stroke="#3b82f6" fill="#3b82f620" strokeWidth={2} />
          <Area type="monotone" dataKey="fpr" stroke="#ef4444" fill="#ef444420" strokeWidth={2} />
          <Line type="monotone" dataKey="ks" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          <ReferenceLine x={maxKSPoint.threshold} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: `KS=${maxKSPoint.max.toFixed(3)}`, position: 'top', fill: '#f59e0b', fontSize: 11 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * ROC 曲线图
 * 展示不同阈值下TPR vs FPR的关系，AUC为曲线下面积
 */
interface ROCCurveProps {
  data?: Array<{ fpr: number; tpr: number }>;
  aucValue?: number;
  height?: number;
}

const DEFAULT_ROC_DATA = [
  { fpr: 0.000, tpr: 0.000 },
  { fpr: 0.001, tpr: 0.032 },
  { fpr: 0.006, tpr: 0.098 },
  { fpr: 0.019, tpr: 0.201 },
  { fpr: 0.052, tpr: 0.334 },
  { fpr: 0.112, tpr: 0.478 },
  { fpr: 0.218, tpr: 0.623 },
  { fpr: 0.374, tpr: 0.764 },
  { fpr: 0.568, tpr: 0.872 },
  { fpr: 0.782, tpr: 0.945 },
  { fpr: 1.000, tpr: 1.000 },
];

export function ROCCurveChart({ data, aucValue = 0, height = 300 }: ROCCurveProps) {
  if (!Array.isArray(data) || data.length === 0) return <ChartEmpty label="暂无真实 ROC 曲线数据" height={height} />;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">ROC 曲线</span>
        <span className="text-sm font-semibold text-green-600">AUC = {aucValue.toFixed(3)}</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="fpr" type="number" domain={[0, 1]} tickFormatter={(v: number) => v.toFixed(1)} label={{ value: 'FPR (假正率)', position: 'insideBottomRight', offset: -5, fontSize: 12 }} />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip
            formatter={(value: number, name: string) => {
              const labels: Record<string, string> = { tpr: '真正率(TPR)', roc: 'ROC曲线', random: '随机基线' };
              return [`${(value * 100).toFixed(1)}%`, labels[name] || name];
            }}
            labelFormatter={(label: number) => `FPR: ${label.toFixed(3)}`}
          />
          <ReferenceLine slope={1} stroke="#94a3b8" strokeDasharray="5 5" label={{ value: '随机基线', position: 'insideTopLeft', fill: '#94a3b8', fontSize: 11 }} />
          <Area type="monotone" dataKey="tpr" stroke="#10b981" fill="#10b98118" strokeWidth={2.5} name="roc" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * 混淆矩阵热力图
 */
interface ConfusionMatrixProps {
  tp?: number; fn?: number; fp?: number; tn?: number;
  labels?: { positive: string; negative: string };
}

function ConfusionMatrixCell({ value, label, colorBase, total }: { value: number; label: string; colorBase: string; total: number }) {
  const getIntensity = (val: number) => {
    const ratio = val / total;
    return Math.min(ratio * 4, 1);
  };
  const intensity = getIntensity(value);
  const pct = ((value / total) * 100).toFixed(1);
  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-lg border" style={{
      backgroundColor: `${colorBase}${Math.round(intensity * 40 + 10).toString(16).padStart(2, '0')}`,
      borderColor: `${colorBase}30`
    }}>
      <span className="text-2xl font-bold" style={{ color: colorBase }}>{value}</span>
      <span className="text-xs text-gray-500 mt-1">{pct}%</span>
      <span className="text-xs text-gray-400 mt-0.5">{label}</span>
    </div>
  );
}

export function ConfusionMatrix({
  tp = 842, fn = 158, fp = 112, tn = 888,
  labels = { positive: '欺诈(正)', negative: '正常(负)' }
}: ConfusionMatrixProps) {
  const total = tp + fn + fp + tn;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-700">混淆矩阵</span>
        <span className="text-xs text-gray-400">总样本: {total.toLocaleString()}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {/* Header row */}
        <div className="text-center text-xs text-gray-500 py-1">预测: {labels.positive}</div>
        <div className="text-center text-xs text-gray-500 py-1">预测: {labels.negative}</div>
        {/* Data rows */}
        <ConfusionMatrixCell value={tp} total={total} label="TP (真正例)" colorBase="#10b981" />
        <ConfusionMatrixCell value={fn} total={total} label="FN (假负例)" colorBase="#f59e0b" />
        <ConfusionMatrixCell value={fp} total={total} label="FP (假正例)" colorBase="#ef4444" />
        <ConfusionMatrixCell value={tn} total={total} label="TN (真负例)" colorBase="#3b82f6" />
      </div>
      {/* Row labels */}
      <div className="flex justify-between mt-1">
        <span className="text-xs text-gray-500">实际: {labels.positive}</span>
        <span className="text-xs text-gray-500">实际: {labels.negative}</span>
      </div>
      {/* Derived metrics */}
      <div className="mt-3 pt-3 border-t grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-xs text-gray-400">精确率</div>
          <div className="text-sm font-semibold text-blue-600">{(tp / (tp + fp) * 100).toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">召回率</div>
          <div className="text-sm font-semibold text-green-600">{(tp / (tp + fn) * 100).toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">F1-Score</div>
          <div className="text-sm font-semibold text-purple-600">{(2 * tp / (2 * tp + fp + fn) * 100).toFixed(1)}%</div>
        </div>
      </div>
    </div>
  );
}

/**
 * 特征重要性排序图
 */
interface FeatureImportanceProps {
  features?: Array<{ name: string; importance: number; category?: string }>;
  height?: number;
}

const DEFAULT_FEATURES = [
  { name: '交易金额异常度', importance: 0.182, category: '金额' },
  { name: 'IP地理位置偏移', importance: 0.154, category: '位置' },
  { name: '交易时间异常', importance: 0.128, category: '时间' },
  { name: '设备指纹变更', importance: 0.112, category: '设备' },
  { name: '历史欺诈关联', importance: 0.098, category: '历史' },
  { name: '交易频次突增', importance: 0.087, category: '频次' },
  { name: '跨行转账比例', importance: 0.065, category: '金额' },
  { name: '账户注册时长', importance: 0.054, category: '账户' },
  { name: '夜间交易占比', importance: 0.043, category: '时间' },
  { name: '银行卡绑定数', importance: 0.032, category: '账户' },
];

export function FeatureImportanceChart({ features, height = 300 }: FeatureImportanceProps) {
  if (!Array.isArray(features) || features.length === 0) return <ChartEmpty label="暂无真实特征重要性数据" height={height} />;
  
  // 过滤掉 importance 为 0 的特征，只显示 Top 10
  const filtered = features.filter(f => (f.importance || 0) > 0);
  const sorted = [...(filtered.length > 0 ? filtered : features)]
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 10);
  
  const categoryColors: Record<string, string> = {
    '金额': '#3b82f6', '位置': '#ef4444', '时间': '#f59e0b',
    '设备': '#8b5cf6', '历史': '#10b981', '频次': '#ec4899',
    '账户': '#6366f1',
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">特征重要性 Top {sorted.length}</span>
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={sorted} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 120 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
            <XAxis type="number" tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
            <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, '重要性']} />
            <Bar
              dataKey="importance"
              radius={[0, 4, 4, 0]}
            >
              {sorted.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={categoryColors[entry.category] || '#3b82f6'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* Category legend */}
      <div className="flex flex-wrap gap-2 mt-2">
        {Object.entries(categoryColors).filter(([cat]) => sorted.some(f => f.category === cat)).map(([cat, color]) => (
          <span key={cat} className="flex items-center gap-1 text-xs text-gray-500">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
            {cat}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * PSI 群体稳定性指标图
 * PSI > 0.25 需要重新训练模型
 */
interface PSIChartProps {
  data?: Array<{ bin: string; expected: number; actual: number; psi: number }>;
  totalPSI?: number;
  height?: number;
}

const DEFAULT_PSI_DATA = [
  { bin: '0-0.1', expected: 0.12, actual: 0.10, psi: 0.0036 },
  { bin: '0.1-0.2', expected: 0.15, actual: 0.14, psi: 0.0007 },
  { bin: '0.2-0.3', expected: 0.18, actual: 0.19, psi: 0.0005 },
  { bin: '0.3-0.4', expected: 0.20, actual: 0.22, psi: 0.0019 },
  { bin: '0.4-0.5', expected: 0.15, actual: 0.16, psi: 0.0006 },
  { bin: '0.5-0.6', expected: 0.08, actual: 0.07, psi: 0.0014 },
  { bin: '0.6-0.7', expected: 0.06, actual: 0.05, psi: 0.0019 },
  { bin: '0.7-0.8', expected: 0.04, actual: 0.04, psi: 0.0000 },
  { bin: '0.8-0.9', expected: 0.015, actual: 0.02, psi: 0.0014 },
  { bin: '0.9-1.0', expected: 0.005, actual: 0.01, psi: 0.0068 },
];

export function PSIChart({ data = DEFAULT_PSI_DATA, totalPSI = 0.0188, height = 250 }: PSIChartProps) {
  const status = totalPSI < 0.1 ? 'stable' : totalPSI < 0.25 ? 'attention' : 'alert';
  const statusConfig = {
    stable: { label: '稳定', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' },
    attention: { label: '需关注', color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
    alert: { label: '需重训', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
  };
  const cfg = statusConfig[status];

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">PSI 群体稳定性指标</span>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.border} ${cfg.color} font-medium`}>
          PSI = {totalPSI.toFixed(4)} ({cfg.label})
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
          <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip formatter={(value: number, name: string) => [`${(value * 100).toFixed(1)}%`, name === 'expected' ? '训练期分布' : '当前期分布']} />
          <Legend formatter={(value: string) => value === 'expected' ? '训练期分布' : '当前期分布'} />
          <Area type="monotone" dataKey="expected" stroke="#3b82f6" fill="#3b82f615" strokeWidth={2} />
          <Area type="monotone" dataKey="actual" stroke="#f59e0b" fill="#f59e0b15" strokeWidth={2} strokeDasharray="5 5" />
        </AreaChart>
      </ResponsiveContainer>
      {/* PSI threshold legend */}
      <div className="flex gap-4 mt-2 text-xs text-gray-400">
        <span>&lt; 0.10 稳定</span>
        <span>0.10 ~ 0.25 需关注</span>
        <span>&gt; 0.25 需重训</span>
      </div>
    </div>
  );
}

/**
 * 学习曲线 / 训练过程可视化
 */
interface TrainingCurveProps {
  data?: Array<{ epoch: number; trainLoss: number; valLoss: number; metric: number }>;
  height?: number;
}

const DEFAULT_TRAINING_DATA = [
  { epoch: 1, trainLoss: 0.693, valLoss: 0.695, metric: 0.512 },
  { epoch: 2, trainLoss: 0.542, valLoss: 0.558, metric: 0.648 },
  { epoch: 3, trainLoss: 0.423, valLoss: 0.451, metric: 0.734 },
  { epoch: 5, trainLoss: 0.312, valLoss: 0.367, metric: 0.798 },
  { epoch: 8, trainLoss: 0.245, valLoss: 0.312, metric: 0.836 },
  { epoch: 10, trainLoss: 0.198, valLoss: 0.289, metric: 0.858 },
  { epoch: 15, trainLoss: 0.152, valLoss: 0.278, metric: 0.876 },
  { epoch: 20, trainLoss: 0.128, valLoss: 0.282, metric: 0.892 },
  { epoch: 25, trainLoss: 0.108, valLoss: 0.291, metric: 0.895 },
  { epoch: 30, trainLoss: 0.095, valLoss: 0.301, metric: 0.893 },
];

export function TrainingCurveChart({ data = DEFAULT_TRAINING_DATA, height = 250 }: TrainingCurveProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">训练过程</span>
        <span className="text-xs text-gray-400">Early Stopping @ Epoch 20</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="epoch" label={{ value: 'Epoch', position: 'insideBottomRight', offset: -5, fontSize: 12 }} />
          <YAxis yAxisId="loss" orientation="left" tickFormatter={(v: number) => v.toFixed(2)} label={{ value: 'Loss', angle: -90, position: 'insideLeft', fontSize: 12 }} />
          <YAxis yAxisId="metric" orientation="right" domain={[0.5, 1]} tickFormatter={(v: number) => v.toFixed(2)} label={{ value: 'AUC', angle: 90, position: 'insideRight', fontSize: 12 }} />
          <Tooltip />
          <Legend />
          <Line yAxisId="loss" type="monotone" dataKey="trainLoss" stroke="#3b82f6" strokeWidth={2} dot={false} name="训练损失" />
          <Line yAxisId="loss" type="monotone" dataKey="valLoss" stroke="#ef4444" strokeWidth={2} dot={false} name="验证损失" />
          <Line yAxisId="metric" type="monotone" dataKey="metric" stroke="#10b981" strokeWidth={2} dot={false} name="AUC" />
          <ReferenceLine yAxisId="loss" x={20} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'Best', position: 'top', fill: '#f59e0b', fontSize: 11 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── SHAP Waterfall Chart ─── */
interface SHAPWaterfallProps {
  features?: Array<{ name: string; value: number }>;
  baseValue?: number;
  height?: number;
}

const DEFAULT_SHAP_FEATURES = [
  { name: 'ip_risk_score', value: 0.182 },
  { name: 'amount', value: 0.134 },
  { name: 'merchant_category', value: 0.098 },
  { name: 'hour_of_day', value: 0.056 },
  { name: 'device_type', value: -0.042 },
  { name: 'user_credit_score', value: -0.067 },
  { name: 'user_age', value: -0.031 },
  { name: 'transaction_count_7d', value: 0.023 },
];

export function SHAPWaterfallChart({ features = DEFAULT_SHAP_FEATURES, baseValue = 0.35, height = 300 }: SHAPWaterfallProps) {
  const sorted = useMemo(() => [...features].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)), [features]);

  // Build waterfall: each bar starts from cumulative position
  const waterfallData = useMemo(() => {
    const result: Array<{ name: string; start: number; end: number; value: number; positive: boolean }> = [];
    let cumulative = baseValue;
    for (const f of sorted) {
      const start = cumulative;
      cumulative += f.value;
      result.push({
        name: f.name,
        start: Math.min(start, cumulative),
        end: Math.max(start, cumulative),
        value: f.value,
        positive: f.value >= 0,
      });
    }
    return result;
  }, [sorted, baseValue]);

  const finalValue = baseValue + sorted.reduce((s, f) => s + f.value, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">SHAP 特征贡献 (Waterfall)</span>
        <span className="text-xs text-gray-400">Base={baseValue.toFixed(3)} &rarr; Pred={finalValue.toFixed(3)}</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={waterfallData} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 100 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" tickFormatter={(v: number) => v.toFixed(2)} />
          <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => v.toFixed(4)} />
          <Bar dataKey="start" fill="transparent" stackId="stack" />
          <Bar dataKey="end" stackId="stack" radius={[0, 4, 4, 0]}>
            {waterfallData.map((entry, idx) => (
              <Cell key={idx} fill={entry.positive ? '#3b82f6' : '#ef4444'} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-center gap-4 mt-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-blue-500" /> 正向贡献</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-red-500" /> 负向贡献</span>
      </div>
    </div>
  );
}

/* ─── Lift/Gain Chart ─── */
interface LiftGainProps {
  data?: Array<{ percentile: number; gain: number; lift: number; random: number }>;
  height?: number;
}

const DEFAULT_LIFT_GAIN_DATA = [
  { percentile: 10, gain: 0.42, lift: 4.2, random: 0.10 },
  { percentile: 20, gain: 0.61, lift: 3.1, random: 0.20 },
  { percentile: 30, gain: 0.74, lift: 2.5, random: 0.30 },
  { percentile: 40, gain: 0.83, lift: 2.1, random: 0.40 },
  { percentile: 50, gain: 0.89, lift: 1.8, random: 0.50 },
  { percentile: 60, gain: 0.93, lift: 1.5, random: 0.60 },
  { percentile: 70, gain: 0.96, lift: 1.4, random: 0.70 },
  { percentile: 80, gain: 0.98, lift: 1.2, random: 0.80 },
  { percentile: 90, gain: 0.99, lift: 1.1, random: 0.90 },
  { percentile: 100, gain: 1.00, lift: 1.0, random: 1.00 },
];

export function LiftGainChart({ data, height = 280 }: LiftGainProps) {
  if (!Array.isArray(data) || data.length === 0) return <ChartEmpty label="暂无真实 Lift / Gain 数据" height={height} />;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">Lift / Gain 曲线</span>
        <span className="text-xs text-gray-400">前10%客户覆盖42%正样本</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="percentile" tickFormatter={(v: number) => `${v}%`} label={{ value: '样本比例', position: 'insideBottomRight', offset: -5, fontSize: 12 }} />
          <YAxis yAxisId="gain" orientation="left" domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} label={{ value: 'Gain', angle: -90, position: 'insideLeft', fontSize: 12 }} />
          <YAxis yAxisId="lift" orientation="right" domain={[0, 5]} tickFormatter={(v: number) => v.toFixed(1)} label={{ value: 'Lift', angle: 90, position: 'insideRight', fontSize: 12 }} />
          <Tooltip formatter={(v: number, name: string) => name === 'Lift' ? v.toFixed(2) : `${(v * 100).toFixed(1)}%`} />
          <Legend />
          <Area yAxisId="gain" type="monotone" dataKey="gain" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={2} name="Gain" />
          <Line yAxisId="gain" type="monotone" dataKey="random" stroke="#9ca3af" strokeDasharray="4 4" strokeWidth={1} dot={false} name="随机基线" />
          <Line yAxisId="lift" type="monotone" dataKey="lift" stroke="#f59e0b" strokeWidth={2} dot={false} name="Lift" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Confusion Matrix Chart ─── */
interface ConfusionMatrixProps {
  data?: { tp: number; tn: number; fp: number; fn: number; precision: number; recall: number; f1: number; accuracy: number; threshold: number } | null;
  height?: number;
}

export function ConfusionMatrixChart({ data, height = 280 }: ConfusionMatrixProps) {
  if (!data) return <ChartEmpty label="暂无混淆矩阵数据" height={height} />;
  const total = data.tp + data.tn + data.fp + data.fn || 1;
  const cells = [
    { label: 'TP', sub: '真正例', value: data.tp, pct: ((data.tp / total) * 100).toFixed(1), bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700', badge: 'bg-emerald-100 text-emerald-600', row: '真实：欺诈', col: '预测：欺诈' },
    { label: 'FN', sub: '假负例', value: data.fn, pct: ((data.fn / total) * 100).toFixed(1), bg: 'bg-rose-50', border: 'border-rose-300', text: 'text-rose-700', badge: 'bg-rose-100 text-rose-600', row: '真实：欺诈', col: '预测：正常' },
    { label: 'FP', sub: '假正例', value: data.fp, pct: ((data.fp / total) * 100).toFixed(1), bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-600', row: '真实：正常', col: '预测：欺诈' },
    { label: 'TN', sub: '真负例', value: data.tn, pct: ((data.tn / total) * 100).toFixed(1), bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700', badge: 'bg-emerald-100 text-emerald-600', row: '真实：正常', col: '预测：正常' },
  ];
  return (
    <div className="flex flex-col gap-3" style={{ minHeight: height }}>
      <div className="grid grid-cols-3 gap-1.5 text-xs">
        <div />
        <div className="flex items-center justify-center font-semibold text-gray-500 py-1">预测：欺诈</div>
        <div className="flex items-center justify-center font-semibold text-gray-500 py-1">预测：正常</div>
        {[0, 2].map((i) => (
          <Fragment key={i}>
            <div className="flex items-center justify-center font-semibold text-gray-500 text-[11px]">{cells[i].row}</div>
            {[i, i + 1].map((j) => (
              <div key={j} className={`rounded-xl border-2 ${cells[j].bg} ${cells[j].border} p-3 flex flex-col items-center justify-center gap-1`}>
                <span className={`text-[10px] font-bold uppercase tracking-wider ${cells[j].badge.split(' ')[1]} px-1.5 py-0.5 rounded-full ${cells[j].badge.split(' ')[0]}`}>{cells[j].label}</span>
                <span className={`text-2xl font-bold ${cells[j].text}`}>{cells[j].value}</span>
                <span className="text-[10px] text-gray-400">{cells[j].pct}%</span>
                <span className={`text-[10px] ${cells[j].text} opacity-70`}>{cells[j].sub}</span>
              </div>
            ))}
          </Fragment>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-2 mt-1">
        {[
          { label: '精确率', value: (data.precision * 100).toFixed(1) + '%', color: 'text-blue-600' },
          { label: '召回率', value: (data.recall * 100).toFixed(1) + '%', color: 'text-indigo-600' },
          { label: 'F1', value: data.f1.toFixed(3), color: 'text-violet-600' },
          { label: '准确率', value: (data.accuracy * 100).toFixed(1) + '%', color: 'text-emerald-600' },
        ].map((m) => (
          <div key={m.label} className="rounded-lg bg-gray-50 border border-border/50 p-2 text-center">
            <div className={`text-sm font-bold ${m.color}`}>{m.value}</div>
            <div className="text-[10px] text-gray-400 mt-0.5">{m.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Strategy Compare Chart ─── */
interface StrategyCompareProps {
  data?: Array<{ label: string; type: string; precision: number; recall: number; predicted: number }> | null;
  height?: number;
}

export function StrategyCompareChart({ data, height = 280 }: StrategyCompareProps) {
  if (!Array.isArray(data) || data.length === 0) return <ChartEmpty label="暂无风控策略数据" height={height} />;
  const maxVal = 100;
  return (
    <div className="flex flex-col gap-2" style={{ minHeight: height }}>
      <div className="flex items-center gap-3 mb-1">
        <span className="flex items-center gap-1 text-xs text-gray-500"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-500" />模型策略</span>
        <span className="flex items-center gap-1 text-xs text-gray-500"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-violet-400" />特征规则</span>
      </div>
      <div className="flex flex-col gap-2.5 flex-1">
        {data.map((item, i) => {
          const isModel = item.type === 'model_threshold';
          const color = isModel ? '#3b82f6' : '#a78bfa';
          const lightBg = isModel ? 'bg-blue-50' : 'bg-violet-50';
          const textColor = isModel ? 'text-blue-700' : 'text-violet-700';
          return (
            <div key={i} className="flex items-center gap-2">
              <div className={`text-[10px] font-medium truncate w-36 shrink-0 ${textColor}`} title={item.label}>{item.label}</div>
              <div className="flex-1 flex flex-col gap-0.5">
                <div className="flex items-center gap-1">
                  <div className="w-8 text-[10px] text-gray-400 text-right">精确</div>
                  <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${item.precision}%`, backgroundColor: color, opacity: 0.85 }} />
                  </div>
                  <div className="w-8 text-[10px] font-semibold text-right" style={{ color }}>{item.precision}%</div>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-8 text-[10px] text-gray-400 text-right">召回</div>
                  <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${item.recall}%`, backgroundColor: color, opacity: 0.5 }} />
                  </div>
                  <div className="w-8 text-[10px] font-semibold text-right" style={{ color }}>{item.recall}%</div>
                </div>
              </div>
              <div className={`text-[10px] px-1.5 py-0.5 rounded-full ${lightBg} ${textColor} shrink-0`}>覆盖{item.predicted}条</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Score Distribution Chart ─── */
interface ScoreDistProps {
  data?: Array<{ bin: string; good: number; bad: number }>;
  height?: number;
}

const DEFAULT_SCORE_DIST = [
  { bin: '0-0.1', good: 45200, bad: 120 },
  { bin: '0.1-0.2', good: 98500, bad: 340 },
  { bin: '0.2-0.3', good: 156000, bad: 890 },
  { bin: '0.3-0.4', good: 198000, bad: 1560 },
  { bin: '0.4-0.5', good: 245000, bad: 3200 },
  { bin: '0.5-0.6', good: 187000, bad: 5800 },
  { bin: '0.6-0.7', good: 134000, bad: 9200 },
  { bin: '0.7-0.8', good: 67000, bad: 12400 },
  { bin: '0.8-0.9', good: 22000, bad: 18200 },
  { bin: '0.9-1.0', good: 4500, bad: 15800 },
];

export function ScoreDistributionChart({ data = DEFAULT_SCORE_DIST, height = 250 }: ScoreDistProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">评分分布 (好/坏客户)</span>
        <span className="text-xs text-gray-400">按模型预测分分组</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
          <YAxis tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v)} />
          <Tooltip formatter={(v: number) => v.toLocaleString()} />
          <Legend />
          <Bar dataKey="good" fill="#3b82f6" name="好客户" radius={[2, 2, 0, 0]} />
          <Bar dataKey="bad" fill="#ef4444" name="坏客户" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Parallel Coordinates (Experiment Tracking) ─── */
interface ParallelCoordsProps {
  experiments?: Array<{
    name: string;
    params: Record<string, number>;
    metric: number;
  }>;
  paramKeys?: string[];
  height?: number;
}

const DEFAULT_PARALLEL_EXPERIMENTS = [
  { name: 'LR-C1.0', params: { C: 1.0, maxDepth: 0, learningRate: 0, nEstimators: 100 }, metric: 0.892 },
  { name: 'LR-C0.5', params: { C: 0.5, maxDepth: 0, learningRate: 0, nEstimators: 200 }, metric: 0.915 },
  { name: 'XGB-d6', params: { C: 0, maxDepth: 6, learningRate: 0.1, nEstimators: 200 }, metric: 0.941 },
  { name: 'GBM-d5', params: { C: 0, maxDepth: 5, learningRate: 0.05, nEstimators: 300 }, metric: 0.948 },
  { name: 'XGB-d8', params: { C: 0, maxDepth: 8, learningRate: 0.08, nEstimators: 250 }, metric: 0.935 },
];

export function ParallelCoordinatesChart({ experiments = DEFAULT_PARALLEL_EXPERIMENTS, paramKeys, height = 280 }: ParallelCoordsProps) {
  const keys = useMemo(() => paramKeys || (experiments.length > 0 ? Object.keys(experiments[0].params) : []), [paramKeys, experiments]);
  // Normalize each param to [0,1]
  const normalized = useMemo(() => {
    const ranges: Record<string, { min: number; max: number }> = {};
    for (const key of keys) {
      const vals = experiments.map((e) => e.params[key]).filter((v) => v > 0);
      ranges[key] = { min: Math.min(...vals), max: Math.max(...vals) };
    }
    ranges['metric'] = {
      min: Math.min(...experiments.map((e) => e.metric)),
      max: Math.max(...experiments.map((e) => e.metric)),
    };
    return experiments.map((exp) => {
      const point: Record<string, number> = {};
      for (const key of keys) {
        const v = exp.params[key];
        const r = ranges[key];
        point[key] = r.max === r.min ? 0.5 : (v - r.min) / (r.max - r.min);
      }
      const mr = ranges['metric'];
      point['metric'] = mr.max === mr.min ? 0.5 : (exp.metric - mr.min) / (mr.max - mr.min);
      return { ...point, _name: exp.name, _metric: exp.metric };
    });
  }, [experiments, keys]);

  const allAxes = [...keys, 'metric'];
  const axisLabels: Record<string, string> = { C: 'C (正则化)', maxDepth: 'Max Depth', learningRate: 'Learning Rate', nEstimators: 'N Estimators', metric: 'AUC' };

  // Draw SVG lines
  const w = 600;
  const h = height - 40;
  const padX = 60;
  const padY = 30;
  const axisSpacing = (w - 2 * padX) / Math.max(allAxes.length - 1, 1);

  const colorScale = (metric: number) => {
    const minM = Math.min(...experiments.map((e) => e.metric));
    const maxM = Math.max(...experiments.map((e) => e.metric));
    const t = maxM === minM ? 0.5 : (metric - minM) / (maxM - minM);
    const r = Math.round(239 * (1 - t) + 59 * t);
    const g = Math.round(68 * (1 - t) + 130 * t);
    const b = Math.round(68 * (1 - t) + 246 * t);
    return `rgb(${r},${g},${b})`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">参数平行坐标图</span>
        <span className="text-xs text-gray-400">颜色=模型AUC (红=低, 蓝=高)</span>
      </div>
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }}>
        {/* Axis lines */}
        {allAxes.map((key, i) => {
          const x = padX + i * axisSpacing;
          return (
            <g key={key}>
              <line x1={x} y1={padY} x2={x} y2={h - padY} stroke="#e5e7eb" strokeWidth={1} />
              <text x={x} y={h - padY + 16} textAnchor="middle" className="text-[10px] fill-gray-500">{axisLabels[key] || key}</text>
              <text x={x} y={padY - 8} textAnchor="middle" className="text-[9px] fill-gray-400">1.0</text>
              <text x={x} y={h - padY + 4} textAnchor="middle" className="text-[9px] fill-gray-400">0.0</text>
            </g>
          );
        })}
        {/* Lines */}
        {normalized.map((point, idx) => {
          const p = point as unknown as Record<string, number>;
          const pathParts = allAxes.map((key, i) => {
            const x = padX + i * axisSpacing;
            const val = p[key] ?? 0;
            const y = h - padY - val * (h - 2 * padY);
            return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
          });
          return (
            <path
              key={idx}
              d={pathParts.join(' ')}
              fill="none"
              stroke={colorScale(p._metric)}
              strokeWidth={2}
              opacity={0.7}
            />
          );
        })}
        {/* Dots */}
        {normalized.map((point, idx) => {
          const p = point as unknown as Record<string, number>;
          return allAxes.map((key, i) => {
            const x = padX + i * axisSpacing;
            const val = p[key] ?? 0;
            const y = h - padY - val * (h - 2 * padY);
            return (
              <circle
                key={`${idx}-${key}`}
                cx={x}
                cy={y}
                r={3}
                fill={colorScale(p._metric)}
                stroke="white"
                strokeWidth={1}
              />
            );
          });
        })}
      </svg>
    </div>
  );
}

/* ─── Model Lineage Visualization ─── */
interface LineageNode {
  id: string;
  label: string;
  type: 'data' | 'feature' | 'model' | 'service';
  status?: string;
}

interface LineageEdge {
  from: string;
  to: string;
}

interface ModelLineageProps {
  nodes?: LineageNode[];
  edges?: LineageEdge[];
  height?: number;
}

const DEFAULT_LINEAGE_NODES: LineageNode[] = [
  { id: 'data-1', label: '交易流水数据', type: 'data', status: '1.2M行' },
  { id: 'data-2', label: '信用记录数据', type: 'data', status: '856K行' },
  { id: 'feat-1', label: '特征工程管道', type: 'feature', status: '32特征' },
  { id: 'model-1', label: '反欺诈风控模型', type: 'model', status: 'AUC 0.989' },
  { id: 'svc-1', label: '生产推理服务', type: 'service', status: 'QPS 128' },
];

export function ModelLineageChart({ nodes = DEFAULT_LINEAGE_NODES, height = 220 }: ModelLineageProps) {
  const typeStyles: Record<string, { bg: string; border: string; text: string }> = {
    data: { bg: 'bg-blue-50', border: 'border-blue-300', text: 'text-blue-700' },
    feature: { bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-700' },
    model: { bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700' },
    service: { bg: 'bg-purple-50', border: 'border-purple-300', text: 'text-purple-700' },
  };

  const typeLabels: Record<string, string> = { data: '数据', feature: '特征', model: '模型', service: '服务' };

  const layers = ['data', 'feature', 'model', 'service'];
  const layeredNodes = layers.map((type) => nodes.filter((n) => n.type === type));

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-gray-700">模型血缘链路</span>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {layers.map((l) => (
            <span key={l} className="flex items-center gap-1">
              <span className={cn('inline-block w-2.5 h-2.5 rounded-sm', typeStyles[l].bg, 'border', typeStyles[l].border)} />
              {typeLabels[l]}
            </span>
          ))}
        </div>
      </div>
      {/* Row-based layout: each row = [layer_column] [arrow] [layer_column] [arrow] ... */}
      <div className="flex items-stretch" style={{ height }}>
        {layers.map((type, li) => {
          const style = typeStyles[type];
          return (
            <Fragment key={type}>
              {/* Layer column */}
              <div className="flex flex-1 flex-col items-center justify-center gap-2.5">
                {/* Layer header */}
                <div className={cn('text-[10px] font-bold uppercase tracking-wider mb-1', style.text)}>
                  {typeLabels[type]}
                </div>
                {/* Nodes */}
                {layeredNodes[li].map((node) => (
                  <div
                    key={node.id}
                    className={cn(
                      'w-full max-w-[150px] rounded-lg border-2 px-3 py-2 text-center transition-all hover:shadow-md hover:scale-[1.02]',
                      style.bg,
                      style.border
                    )}
                  >
                    <div className="text-xs font-semibold truncate">{node.label}</div>
                    {node.status && <div className="text-[10px] text-muted-foreground mt-0.5">{node.status}</div>}
                  </div>
                ))}
                {layeredNodes[li].length === 0 && (
                  <div className="w-full max-w-[150px] rounded-lg border-2 border-dashed border-gray-200 px-3 py-2 text-center text-xs text-gray-400">
                    无{typeLabels[type]}节点
                  </div>
                )}
              </div>
              {/* Arrow between this layer and the next */}
              {li < layers.length - 1 && (
                <div className="flex items-center justify-center" style={{ width: 32, minWidth: 32 }}>
                  <svg width="28" height="28" viewBox="0 0 28 28" className="text-gray-400 shrink-0">
                    <path d="M4 14 L20 14" stroke="currentColor" strokeWidth="2" fill="none" />
                    <path d="M16 8 L22 14 L16 20" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              )}
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}
