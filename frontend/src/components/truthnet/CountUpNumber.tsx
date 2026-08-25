import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface CountUpNumberProps {
  /** 目标数值 */
  value: number
  /** 小数位数（默认 0） */
  decimals?: number
  /** 动画时长 ms（默认 900） */
  duration?: number
  /** 是否已挂载后才启动（用于等数据到位） */
  active?: boolean
  className?: string
}

/**
 * 金融级数字滚动组件：easeOutCubic 缓动 + tabular-nums 等宽数字，
 * 避免 Roboto/Inter 等比例字体在滚动时数字跳动。
 * 遵守 prefers-reduced-motion：直接显示终值。
 */
export function CountUpNumber({
  value,
  decimals = 0,
  duration = 900,
  active = true,
  className,
}: CountUpNumberProps) {
  const [display, setDisplay] = useState(0)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (!active) return
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced || duration <= 0) {
      setDisplay(value)
      return
    }
    const start = performance.now()
    const from = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(from + (value - from) * eased)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    }
  }, [value, duration, active])

  return (
    <span className={cn('tabular-nums', className)}>
      {display.toFixed(decimals)}
    </span>
  )
}
