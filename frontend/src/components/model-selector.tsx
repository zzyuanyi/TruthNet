// @ts-nocheck
/* ─── Model Selector (Simplified) ───
 * 对话功能由后端 Agent API 提供，前端不再直接管理 LLM 配置。
 * 此组件仅保留模型参数调节功能（可传给后端 session）。
 */
import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Settings2 } from 'lucide-react';

/* ─── Types ─── */
export interface ModelConfig {
  modelId: string;
  temperature: number;
  frequencyPenalty: number;
  topP: number;
  maxTokens: number;
  maxTotalTokens: number;
  thinking: boolean;
  thinkingLevel: 'low' | 'medium' | 'high';
  outputFormat: 'text' | 'markdown' | 'json';
}

export const DEFAULT_MODEL_CONFIG: ModelConfig = {
  modelId: 'agent-default',
  temperature: 0.7,
  frequencyPenalty: 0,
  topP: 0.9,
  maxTokens: 4096,
  maxTotalTokens: 8192,
  thinking: true,
  thinkingLevel: 'medium',
  outputFormat: 'markdown',
};

/* ─── Helpers ─── */
function ParamLabel({ label }: { label: string }) {
  return <div className="text-xs font-medium">{label}</div>;
}

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  onChange,
  leftLabel,
  rightLabel,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  leftLabel: string;
  rightLabel: string;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <ParamLabel label={label} />
        <span className="text-xs font-mono text-muted-foreground tabular-nums">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${pct}%, hsl(var(--muted)) ${pct}%, hsl(var(--muted)) 100%)`,
        }}
      />
      <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}

/* ─── Main Component ─── */
interface ModelSelectorProps {
  config: ModelConfig;
  onConfigChange: (config: ModelConfig) => void;
}

export function ModelSelector({ config, onConfigChange }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);

  // Temp state for editing
  const [tempModelId, setTempModelId] = useState(config.modelId);
  const [tempTemp, setTempTemp] = useState(config.temperature);
  const [tempFreqPenalty, setTempFreqPenalty] = useState(config.frequencyPenalty);
  const [tempTopP, setTempTopP] = useState(config.topP);
  const [tempMaxTokens, setTempMaxTokens] = useState(config.maxTokens);
  const [tempMaxTotalTokens, setTempMaxTotalTokens] = useState(config.maxTotalTokens);
  const [tempThinking, setTempThinking] = useState(config.thinking);
  const [tempThinkingLevel, setTempThinkingLevel] = useState(config.thinkingLevel);
  const [tempOutputFormat, setTempOutputFormat] = useState(config.outputFormat);

  const handleOpen = (val: boolean) => {
    setOpen(val);
    if (val) {
      setTempModelId(config.modelId);
      setTempTemp(config.temperature);
      setTempFreqPenalty(config.frequencyPenalty);
      setTempTopP(config.topP);
      setTempMaxTokens(config.maxTokens);
      setTempMaxTotalTokens(config.maxTotalTokens);
      setTempThinking(config.thinking);
      setTempThinkingLevel(config.thinkingLevel);
      setTempOutputFormat(config.outputFormat);
    }
  };

  const handleApply = () => {
    onConfigChange({
      modelId: tempModelId,
      temperature: tempTemp,
      frequencyPenalty: tempFreqPenalty,
      topP: tempTopP,
      maxTokens: tempMaxTokens,
      maxTotalTokens: tempMaxTotalTokens,
      thinking: tempThinking,
      thinkingLevel: tempThinkingLevel,
      outputFormat: tempOutputFormat,
    });
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 rounded-lg border border-border/60 bg-background hover:bg-accent/50 transition-colors text-sm"
        >
          <Settings2 className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="font-medium">Agent 对话</span>
          <span className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-200">
            后端驱动
          </span>
        </button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[580px] p-0 gap-0 overflow-hidden">
        {/* Header */}
        <DialogHeader className="px-5 pt-5 pb-3 border-b">
          <DialogTitle className="text-base">对话参数设置</DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            对话由后端 Agent API 驱动，此处仅调节请求参数
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col max-h-[75vh]">
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {/* ── Agent Info ── */}
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-700">
              对话功能由后端 Agent API (端口 8000) 提供，前端不直接调用 LLM。
              发送消息至 POST /api/sessions/&#123;sessionId&#125;/message
            </div>

            {/* ── Divider ── */}
            <div className="border-t" />

            {/* ── Parameter Settings ── */}
            <div>
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                参数配置
              </div>
              <div className="space-y-5">
                {/* Temperature */}
                <SliderRow
                  label="生成随机性"
                  value={tempTemp}
                  min={0}
                  max={2}
                  step={0.1}
                  onChange={setTempTemp}
                  leftLabel="精确"
                  rightLabel="创意"
                />

                {/* Frequency Penalty */}
                <SliderRow
                  label="重复语句惩罚"
                  value={tempFreqPenalty}
                  min={0}
                  max={2}
                  step={0.1}
                  onChange={setTempFreqPenalty}
                  leftLabel="无惩罚"
                  rightLabel="强惩罚"
                />

                {/* Top P */}
                <SliderRow
                  label="Top P"
                  value={tempTopP}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={setTempTopP}
                  leftLabel="窄采样"
                  rightLabel="全采样"
                />

                {/* Max Tokens */}
                <SliderRow
                  label="最大回复长度"
                  value={tempMaxTokens}
                  min={256}
                  max={8192}
                  step={256}
                  onChange={setTempMaxTokens}
                  leftLabel="短"
                  rightLabel="长"
                />

                {/* Max Total Tokens */}
                <SliderRow
                  label="最大推理&回答长度"
                  value={tempMaxTotalTokens}
                  min={1024}
                  max={32768}
                  step={1024}
                  onChange={setTempMaxTotalTokens}
                  leftLabel="短"
                  rightLabel="长"
                />

                {/* Deep Thinking Toggle */}
                <div className="flex items-center justify-between py-1">
                  <div>
                    <ParamLabel label="深度思考开关" />
                    <div className="text-xs text-muted-foreground mt-0.5">
                      复杂推理任务时启用，响应时间更长
                    </div>
                  </div>
                  <Switch
                    checked={tempThinking}
                    onCheckedChange={setTempThinking}
                  />
                </div>

                {/* Thinking Level (conditional) */}
                {tempThinking && (
                  <div className="space-y-2 ml-5 pl-4 border-l-2 border-violet-200">
                    <ParamLabel label="深度思考程度" />
                    <div className="flex gap-2">
                      {[
                        { value: "low" as const, label: "低" },
                        { value: "medium" as const, label: "中" },
                        { value: "high" as const, label: "高" },
                      ].map((opt) => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setTempThinkingLevel(opt.value)}
                          className={`px-4 py-1.5 rounded-md text-sm font-medium border transition-all ${
                            tempThinkingLevel === opt.value
                              ? "border-violet-400 bg-violet-50 text-violet-700"
                              : "border-border hover:bg-accent/50 text-muted-foreground"
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Output Format */}
                <div className="space-y-2">
                  <ParamLabel label="输出格式" />
                  <div className="flex gap-2">
                    {[
                      { value: "text" as const, label: "纯文本" },
                      { value: "markdown" as const, label: "Markdown" },
                      { value: "json" as const, label: "JSON" },
                    ].map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setTempOutputFormat(opt.value)}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium border transition-all ${
                          tempOutputFormat === opt.value
                            ? "border-primary/40 bg-primary/5 text-primary"
                            : "border-border hover:bg-accent/50 text-muted-foreground"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-5 py-4 border-t bg-muted/10">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="px-4 py-2 rounded-md border border-border text-sm text-muted-foreground hover:bg-accent/50 transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleApply}
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              应用
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
