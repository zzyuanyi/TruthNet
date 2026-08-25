import { Reveal } from '@/components/reveal';
import { ArrowDown } from 'lucide-react';
import '@phosphor-icons/web/duotone';
import { MarketPulseGlobe } from '@/components/truthnet/MarketPulseGlobe';

interface QuickAction {
  /** Phosphor duotone 图标类名（如 ph-file-magnifying-glass） */
  icon: string;
  label: string;
  /** 卡片展示的功能描述（10~15 字） */
  desc: string;
  /** 点击后实际发送的示例问题 */
  sample: string;
  href?: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    icon: 'ph-file-magnifying-glass',
    label: '财务核查',
    desc: '勾稽交叉核验，识别科目粉饰',
    sample: '分析金牌家居财务风险',
  },
  {
    icon: 'ph-coins',
    label: '现金流核验',
    desc: '三表现金流配比与造血体检',
    sample: '查看比亚迪经营现金流',
  },
  {
    icon: 'ph-tree-structure',
    label: '股权穿透',
    desc: '逐层穿透股东与关联网络',
    sample: '查看金牌家居股权穿透',
  },
  {
    icon: 'ph-chart-bar-horizontal',
    label: '横向对比',
    desc: '同业对标，定位风险水位差',
    sample: '华峰化学 · 中泰化学 · 利尔化学',
    href: '/compare?codes=002064.SZ,002092.SZ,002258.SZ',
  },
];

interface WelcomeHeroProps {
  /** 发送示例问题（财务核查 / 现金流核验 / 股权穿透） */
  onSendSample: (text: string) => void;
  /** 打开横向对比页 */
  onOpenCompare: () => void;
}

/**
 * 织网鉴真首页欢迎 Hero。
 * 颜色全部走主题语义色（light/dark 自动适配），背景沿用 ink 光晕 + 极淡网格，
 * 采用 mono 品牌词标 + 多行交错大标题 + 交错入场，克制不做蓝紫渐变。
 */
export function WelcomeHero({ onSendSample, onOpenCompare }: WelcomeHeroProps) {
  return (
    <div
      className="relative flex min-h-full flex-col justify-center px-6 py-14 text-foreground sm:px-10 lg:px-16"
      style={{
        background: [
          'radial-gradient(60% 45% at 50% 0%, color-mix(in srgb, var(--color-primary) 16%, transparent), transparent 72%)',
          'radial-gradient(42% 36% at 84% 100%, color-mix(in srgb, var(--color-primary) 9%, transparent), transparent 72%)',
          'linear-gradient(color-mix(in srgb, var(--color-foreground) 5%, transparent) 1px, transparent 1px)',
          'linear-gradient(90deg, color-mix(in srgb, var(--color-foreground) 5%, transparent) 1px, transparent 1px)',
        ].join(', '),
        backgroundSize: '100% 100%, 100% 100%, 44px 44px, 44px 44px',
      }}
    >
      <div className="relative mx-auto w-full max-w-xl">
        {/* 品牌词标 */}
        <Reveal delay={0}>
          <div className="flex items-center justify-between font-mono text-[11px] tracking-widest text-muted-foreground">
            <span>( TRUTHNET )</span>
            <span>[ v0.2 ]</span>
          </div>
        </Reveal>

        {/* 主标题：多行交错 */}
        <div className="mt-10">
          <h2 className="sr-only">织网鉴真 · 财报反欺诈 · 智能问答</h2>
          <Reveal delay={100}>
            <p className="pl-6 text-4xl font-medium leading-[1.08] tracking-tight text-foreground sm:pl-10 sm:text-5xl">
              织网鉴真
            </p>
          </Reveal>
          <Reveal delay={220}>
            <p className="text-4xl font-medium leading-[1.08] tracking-tight text-foreground sm:text-5xl">
              财报反欺诈
            </p>
          </Reveal>
          <Reveal delay={340}>
            <p className="pl-12 text-3xl font-light leading-[1.2] tracking-normal text-muted-foreground sm:pl-16 sm:text-4xl">
              · 智能问答
            </p>
          </Reveal>
        </div>

        {/* 副标题 */}
        <Reveal delay={440}>
          <p className="mt-8 max-w-md text-sm leading-relaxed text-muted-foreground">
            输入上市公司名称或股票代码，穿透股权 · 交叉验证 · 对齐舆情
          </p>
        </Reveal>

        {/* 快捷入口：1×4 玻璃拟态 + 波浪滚动 */}
        <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-4">
          {QUICK_ACTIONS.map((action, i) => (
            <Reveal key={action.label} delay={520 + i * 90} className="h-full">
              <button
                onClick={() => (action.href ? onOpenCompare() : onSendSample(action.sample))}
                className="tn-glass-card group flex h-full w-full flex-col items-start rounded-md p-4 text-left animate-tn-wave"
                style={{ animationDelay: `${i * 260}ms` }}
              >
                <i
                  aria-hidden
                  className={`ph-duotone ${action.icon} mb-3 shrink-0 text-[26px] leading-none text-primary transition-transform duration-300 group-hover:scale-110`}
                />
                <span className="text-sm font-medium text-foreground">{action.label}</span>
                <span className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {action.desc}
                </span>
              </button>
            </Reveal>
          ))}
        </div>

        {/* 全球舆情监控：旋转地球 + 鉴真之眼 */}
        <Reveal delay={860}>
          <div className="mt-8">
            <MarketPulseGlobe />
          </div>
        </Reveal>

        {/* 底部提示 */}
        <Reveal delay={900}>
          <div className="mt-10 flex items-center justify-center gap-2 font-mono text-[10px] tracking-widest text-muted-foreground">
            <ArrowDown className="h-3.5 w-3.5 animate-bounce" />
            在下方输入框开始提问
          </div>
        </Reveal>
      </div>
    </div>
  );
}