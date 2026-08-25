import { cn } from '@/lib/utils';

interface TruthNetMarkProps {
  className?: string;
  /** 是否播放「织网 → 成眼 → 扫视」入场动画（开场 overlay 用）；默认 false 为常驻状态 */
  intro?: boolean;
}

/**
 * 织网鉴真 Logo：由数据点 / 网构成的「眼」，瞳孔持续扫视（寓意持续观测、鉴真）。
 * - 线条、节点跟随 currentColor，尺寸由 className 控制（viewBox 64×40 ≈ 1.6:1，如 h-5 w-8）。
 * - `intro` 时叠加 `.tn-intro` 入场动画（描边逐条画出 → 节点点亮 → 瞳孔浮现并扫视）。
 */
export function TruthNetMark({ className, intro = false }: TruthNetMarkProps) {
  return (
    <svg
      viewBox="0 0 64 40"
      fill="none"
      aria-hidden="true"
      className={cn('overflow-visible', intro && 'tn-intro', className)}
    >
      {/* 上 / 下眼睑 */}
      <path className="tn-line" d="M6 20 Q32 3 58 20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path className="tn-line" d="M6 20 Q32 37 58 20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />

      {/* 网：瞳孔 → 眼睑辐射连线 */}
      <line className="tn-line" x1="32" y1="20" x2="32" y2="11.5" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="32" y2="28.5" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="12" y2="20" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="52" y2="20" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="19" y2="14" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="45" y2="14" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="19" y2="26" stroke="currentColor" strokeWidth="1" />
      <line className="tn-line" x1="32" y1="20" x2="45" y2="26" stroke="currentColor" strokeWidth="1" />

      {/* 节点（数据点） */}
      <circle className="tn-node" cx="6" cy="20" r="1.8" fill="currentColor" />
      <circle className="tn-node" cx="58" cy="20" r="1.8" fill="currentColor" />
      <circle className="tn-node" cx="32" cy="11.5" r="1.6" fill="currentColor" />
      <circle className="tn-node" cx="32" cy="28.5" r="1.6" fill="currentColor" />
      <circle className="tn-node" cx="19" cy="14" r="1.5" fill="currentColor" />
      <circle className="tn-node" cx="45" cy="14" r="1.5" fill="currentColor" />
      <circle className="tn-node" cx="19" cy="26" r="1.5" fill="currentColor" />
      <circle className="tn-node" cx="45" cy="26" r="1.5" fill="currentColor" />

      {/* 瞳孔（持续扫视） */}
      <g className="tn-scan">
        <circle cx="32" cy="20" r="6" fill="currentColor" />
        <circle cx="32" cy="20" r="8" stroke="currentColor" strokeWidth="1" opacity="0.45" />
      </g>
    </svg>
  );
}