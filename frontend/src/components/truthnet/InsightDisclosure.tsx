import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type DisclosureSeverity =
  "critical" | "high" | "medium" | "low" | "info";

const SEVERITY_SKIN: Record<
  DisclosureSeverity,
  { dot: string; ring: string; text: string; glow: string }
> = {
  critical: {
    dot: "bg-red-500",
    ring: "border-red-500/25 dark:border-red-400/20",
    text: "text-red-600 dark:text-red-400",
    glow: "shadow-[0_0_0_1px_rgba(239,68,68,0.08),0_10px_36px_-14px_rgba(239,68,68,0.28)]",
  },
  high: {
    dot: "bg-orange-500",
    ring: "border-orange-500/25 dark:border-orange-400/20",
    text: "text-orange-600 dark:text-orange-400",
    glow: "shadow-[0_0_0_1px_rgba(249,115,22,0.08),0_10px_36px_-14px_rgba(249,115,22,0.26)]",
  },
  medium: {
    dot: "bg-amber-500",
    ring: "border-amber-500/25 dark:border-amber-400/20",
    text: "text-amber-600 dark:text-amber-400",
    glow: "shadow-[0_0_0_1px_rgba(245,158,11,0.08),0_10px_36px_-14px_rgba(245,158,11,0.24)]",
  },
  low: {
    dot: "bg-sky-500",
    ring: "border-sky-500/25 dark:border-sky-400/20",
    text: "text-sky-600 dark:text-sky-400",
    glow: "shadow-[0_0_0_1px_rgba(14,165,233,0.08),0_10px_36px_-14px_rgba(14,165,233,0.22)]",
  },
  info: {
    dot: "bg-primary",
    ring: "border-primary/20",
    text: "text-primary",
    glow: "shadow-[0_10px_36px_-16px_rgba(0,0,0,0.25)] dark:shadow-[0_10px_36px_-14px_rgba(0,0,0,0.5)]",
  },
};

export interface InsightDisclosureProps {
  severity?: DisclosureSeverity;
  /** 收起态显示的一行结论（必填，详略得当的关键） */
  title: React.ReactNode;
  /** 标题右侧的元信息（如规则数、日期） */
  meta?: React.ReactNode;
  /** 徽章 */
  badge?: React.ReactNode;
  /** 展开后的详细内容 */
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

/**
 * 拆信封式就地展开卡：默认只露一行结论 + 等级灯，
 * 点击后原地展开详细分析（不跳页），grid-rows 0fr→1fr 平滑撑开。
 */
export function InsightDisclosure({
  severity = "info",
  title,
  meta,
  badge,
  children,
  defaultOpen = false,
  className,
}: InsightDisclosureProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [mounted, setMounted] = useState(false);
  const panelId = useId();
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const skin = SEVERITY_SKIN[severity];

  useEffect(() => setMounted(true), []);

  const toggle = useCallback(() => setOpen((v) => !v), []);

  return (
    <div
      className={cn(
        "tn-disclose group relative overflow-hidden rounded-xl border bg-card/80 backdrop-blur-sm transition-[box-shadow,border-color,transform] duration-300",
        "hover:-translate-y-px",
        skin.ring,
        open ? cn(skin.glow, "border-transparent") : "hover:border-primary/25",
        className,
      )}
    >
      {/* 展开时的顶部光效线 */}
      <span
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-current to-transparent opacity-0 transition-opacity duration-500",
          skin.text,
          open && "opacity-60",
        )}
      />
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left sm:px-5"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-60",
              skin.dot,
              open && "animate-ping",
            )}
          />
          <span
            className={cn(
              "relative inline-flex h-2 w-2 rounded-full",
              skin.dot,
            )}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold leading-6 text-foreground">
              {title}
            </span>
            {badge}
          </span>
          {meta ? (
            <span className="mt-0.5 block truncate text-xs text-muted-foreground">
              {meta}
            </span>
          ) : null}
        </span>
        <span className="flex shrink-0 items-center gap-2 text-xs font-medium text-muted-foreground">
          <span className="hidden sm:inline">{open ? "收起" : "展开分析"}</span>
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
              open && "rotate-180",
            )}
          />
        </span>
      </button>

      {/* 拆信封展开区：grid 0fr→1fr 原生高度动画 */}
      <div
        id={panelId}
        role="region"
        className={cn(
          "tn-disclose-panel grid transition-[grid-template-rows] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
          open ? "[grid-template-rows:1fr]" : "[grid-template-rows:0fr]",
        )}
      >
        <div className="overflow-hidden">
          <div
            ref={bodyRef}
            className={cn(
              "tn-disclose-body px-4 pb-5 pt-1 sm:px-5",
              mounted && open && "tn-envelope-open",
            )}
          >
            <div className="mb-3 h-px bg-gradient-to-r from-border via-border/40 to-transparent" />
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
