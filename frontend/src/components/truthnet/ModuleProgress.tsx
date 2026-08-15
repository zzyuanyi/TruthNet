// 织网鉴真 TruthNet - 模块执行进度条
// Phase D: 可视化展示 Agent 管线各模块的执行状态

import { cn } from '@/lib/utils';
import type { ModuleStatusV1, ModuleStatusState } from '@/types/truthnet';

// 模块中文名映射
const MODULE_LABELS: Record<string, string> = {
  memory: '指代消解',
  resolve_entity: '实体解析',
  plan_modules: '模块规划',
  load_context: '上下文加载',
  finance: '财务勾稽',
  events: '舆情挖掘',
  equity: '股权穿透',
  pattern_match: '模式匹配',
  cross_validate: '交叉验证',
  build_claims: '生成主张',
  risk: '风险评分',
  validate_evidence: '证据验证',
  generate_answer: '生成回答',
  persist_turn: '会话持久化',
};

const STATE_CONFIG: Record<ModuleStatusState, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'text-muted-foreground/50', bg: 'bg-muted-foreground/20' },
  running: { label: '运行中', color: 'text-blue-500', bg: 'bg-blue-500' },
  success: { label: '完成', color: 'text-green-500', bg: 'bg-green-500' },
  partial: { label: '部分完成', color: 'text-yellow-500', bg: 'bg-yellow-500' },
  failed: { label: '失败', color: 'text-red-500', bg: 'bg-red-500' },
  skipped: { label: '跳过', color: 'text-muted-foreground', bg: 'bg-muted-foreground/30' },
  cancelled: { label: '取消', color: 'text-muted-foreground', bg: 'bg-muted-foreground/30' },
};

interface ModuleProgressProps {
  moduleStatus: Record<string, ModuleStatusV1> | null | undefined;
  missingModules?: string[] | null;
}

export function ModuleProgress({ moduleStatus, missingModules }: ModuleProgressProps) {
  if (!moduleStatus || Object.keys(moduleStatus).length === 0) {
    if (!missingModules || missingModules.length === 0) return null;
    // 仅有缺失模块时显示
    return (
      <div className="space-y-2 p-3 rounded-lg bg-muted/30 border border-border/50">
        <p className="text-xs text-muted-foreground">以下模块不可用（数据不足）：</p>
        {missingModules.map((m) => (
          <div key={m} className="flex items-center gap-2 text-xs text-muted-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
            {MODULE_LABELS[m] || m}
          </div>
        ))}
      </div>
    );
  }

  const entries = Object.entries(moduleStatus);
  const total = entries.length;
  const completed = entries.filter(([, s]) => s.state === 'success' || s.state === 'partial').length;

  return (
    <div className="space-y-3 p-3 rounded-lg bg-muted/30 border border-border/50">
      {/* 总体进度条 */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">管线进度</span>
          <span className="text-muted-foreground font-mono">
            {completed}/{total}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* 各模块状态 */}
      <div className="space-y-1">
        {entries.map(([name, status]) => {
          const config = STATE_CONFIG[status.state];
          const label = MODULE_LABELS[name] || name;
          const isRunning = status.state === 'running';
          return (
            <div key={name} className="flex items-center gap-2 text-xs">
              <span
                className={cn(
                  'h-1.5 w-1.5 rounded-full shrink-0',
                  config.bg,
                  isRunning && 'animate-pulse',
                )}
              />
              <span className="flex-1 truncate text-muted-foreground">{label}</span>
              <span className={cn('shrink-0', config.color)}>
                {config.label}
                {status.duration_ms != null && status.state !== 'running' ? (
                  <span className="text-muted-foreground/50 ml-1">
                    {status.duration_ms < 1000
                      ? `${status.duration_ms}ms`
                      : `${(status.duration_ms / 1000).toFixed(1)}s`}
                  </span>
                ) : null}
              </span>
            </div>
          );
        })}
      </div>

      {/* 缺失模块 */}
      {missingModules && missingModules.length > 0 && (
        <div className="pt-1.5 border-t border-border/50">
          <p className="text-xs text-muted-foreground/60">
            跳过：{missingModules.map((m) => MODULE_LABELS[m] || m).join('、')}
          </p>
        </div>
      )}
    </div>
  );
}

export default ModuleProgress;