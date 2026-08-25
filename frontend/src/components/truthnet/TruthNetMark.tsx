import { cn } from '@/lib/utils';

interface TruthNetMarkProps {
  className?: string;
  /** 是否播放「织网 → 成眼 → 扫视」入场动画（开场 overlay 用）；默认 false 为常驻状态 */
  intro?: boolean;
}

/**
 * 织网鉴真 Logo：数据点 / 网构成的「眼」，瞳孔是字母 T 与 N 的镜面融合，持续扫视（寓意持续观测、鉴真）。
 * 科技风：线条化、轻量、不神秘学——眼只是「取景框」，核心是 TN 融合瞳孔。
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
      {/* 上 / 下眼睑（取景框） */}
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

      {/* 瞳孔：T / N 镜面融合（T 的横线在上，N 的斜杠居中，左右对称）+ 瞳环，持续扫视 */}
      <g className="tn-scan">
        <circle cx="32" cy="20" r="9" stroke="currentColor" strokeWidth="1" opacity="0.4" />
        <path
          className="tn-line"
          d="M27 15.5 H37 M32 15.5 V24.5 M27 24.5 H37"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* N 的斜杠（穿过 T 竖线，形成 TN 融合视觉） */}
        <path
          className="tn-line"
          d="M28.5 15.8 L35.5 24.2"
          stroke="currentColor"
          strokeWidth="1.1"
          strokeLinecap="round"
          opacity="0.85"
        />
      </g>
    </svg>
  );
}
