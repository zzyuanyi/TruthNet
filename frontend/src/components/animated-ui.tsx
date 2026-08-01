'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * AnimatedNumber - 数字跳动动画组件
 * 当 value 变化时，从旧值动画过渡到新值
 */
export function AnimatedNumber({ value, duration = 600, className = '' }: {
  value: number;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const from = prevRef.current;
    const to = value;
    prevRef.current = value;

    if (from === to) return;

    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplay(Math.round(from + (to - from) * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value, duration]);

  return <span className={className}>{display.toLocaleString()}</span>;
}

/**
 * FadeInOnMount - 挂载时淡入动画
 */
export function FadeInOnMount({ children, delay = 0, className = '' }: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  return (
    <div
      className={`transition-all duration-300 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1'} ${className}`}
    >
      {children}
    </div>
  );
}

/**
 * PulseBadge - 数值变化时脉冲动画的 Badge
 */
export function PulseBadge({ children, pulse, className = '' }: {
  children: React.ReactNode;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span className={`relative inline-flex ${className}`}>
      {pulse && (
        <span className="absolute inset-0 rounded-md animate-ping bg-blue-400/20" />
      )}
      <span className="relative">{children}</span>
    </span>
  );
}
