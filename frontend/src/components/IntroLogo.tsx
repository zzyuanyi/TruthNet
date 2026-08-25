import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { TruthNetMark } from '@/components/truthnet/TruthNetMark';

/**
 * 开场动画：主题背景（light/dark 自动）中心播放「数据点织网 → 成眼 → 瞳孔扫视」，
 * 随后整体缩小并淡出，露出主界面（header 常驻小眼继续扫视）。
 */
export function IntroLogo() {
  const [phase, setPhase] = useState<'intro' | 'out' | 'done'>('intro');

  useEffect(() => {
    const t1 = window.setTimeout(() => setPhase('out'), 2400);
    const t2 = window.setTimeout(() => setPhase('done'), 3050);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  if (phase === 'done') return null;

  return (
    <div
      data-no-print
      aria-hidden="true"
      className={cn(
        'fixed inset-0 z-[100] flex items-center justify-center bg-background',
        'transition-opacity duration-500 ease-out',
        phase === 'out' && 'pointer-events-none opacity-0',
      )}
    >
      <div
        className={cn(
          'text-primary transition-transform duration-500 ease-in-out',
          phase === 'out' && 'scale-[0.14]',
        )}
        style={{ transformOrigin: 'center' }}
      >
        <TruthNetMark intro className="h-32 w-52 sm:h-44 sm:w-[17.6rem]" />
      </div>
    </div>
  );
}