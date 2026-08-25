import { Reveal } from '@/components/reveal';
import { ArrowDown, FileText, Shield, TrendingUp, Zap } from 'lucide-react';

interface QuickAction {
  icon: typeof TrendingUp;
  label: string;
  text: string;
  href?: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { icon: TrendingUp, label: '财务核查', text: '分析金牌家居财务风险' },
  { icon: FileText, label: '现金流核验', text: '查看比亚迪经营现金流' },
  { icon: Zap, label: '股权穿透', text: '查看金牌家居股权穿透' },
  {
    icon: Shield,
    label: '横向对比',
    text: '华峰化学 · 中泰化学 · 利尔化学',
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
 * 织网鉴真首页欢迎 Hero —— 暗黑电影感升级。
 * 融合 NOVA_AI 的排版语言（mono 品牌词标 + 多行交错大标题 + 交错入场），
 * 背景沿用 TruthNet 的 ink 深海军蓝光晕 + 极淡网格，克制不做蓝紫渐变。
 */
export function WelcomeHero({ onSendSample, onOpenCompare }: WelcomeHeroProps) {
  return (
    <div
      className="relative flex min-h-full flex-col justify-center px-6 py-14 text-white sm:px-10 lg:px-16"
      style={{
        background: [
          'radial-gradient(60% 45% at 50% 0%, rgba(15, 58, 93, 0.42), transparent 70%)',
          'radial-gradient(42% 36% at 84% 100%, rgba(47, 106, 153, 0.16), transparent 72%)',
          'linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px)',
          'linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px)',
          '#0a0a0a',
        ].join(', '),
        backgroundSize: '100% 100%, 100% 100%, 44px 44px, 44px 44px, 100% 100%',
      }}
    >
      <div className="relative mx-auto w-full max-w-xl">
        {/* 品牌词标 */}
        <Reveal delay={0}>
          <div className="flex items-center justify-between font-mono text-[11px] tracking-widest text-white/50">
            <span>( TRUTHNET )</span>
            <span>[ v0.2 ]</span>
          </div>
        </Reveal>

        {/* 主标题：多行交错 */}
        <div className="mt-10">
          <h2 className="sr-only">织网鉴真 · 财报反欺诈 · 智能问答</h2>
          <Reveal delay={100}>
            <p className="pl-6 text-4xl font-medium leading-[1.08] tracking-tight text-white drop-shadow-lg sm:pl-10 sm:text-5xl">
              织网鉴真
            </p>
          </Reveal>
          <Reveal delay={220}>
            <p className="text-4xl font-medium leading-[1.08] tracking-tight text-white drop-shadow-lg sm:text-5xl">
              财报反欺诈
            </p>
          </Reveal>
          <Reveal delay={340}>
            <p className="pl-12 text-3xl font-light leading-[1.2] tracking-normal text-white/75 drop-shadow-md sm:pl-16 sm:text-4xl">
              · 智能问答
            </p>
          </Reveal>
        </div>

        {/* 副标题 */}
        <Reveal delay={440}>
          <p className="mt-8 max-w-md text-sm leading-relaxed text-white/55">
            输入上市公司名称或股票代码，穿透股权 · 交叉验证 · 对齐舆情
          </p>
        </Reveal>

        {/* 快捷入口 */}
        <div className="mt-10 grid grid-cols-2 gap-3">
          {QUICK_ACTIONS.map((action, i) => (
            <Reveal key={action.label} delay={520 + i * 90} className="h-full">
              <button
                onClick={() => (action.href ? onOpenCompare() : onSendSample(action.text))}
                className="group flex h-full w-full flex-col items-start rounded-md border border-white/10 bg-white/[0.03] p-4 text-left transition-all duration-300 hover:border-white/60 hover:bg-white hover:text-black"
              >
                <action.icon className="mb-3 h-5 w-5 shrink-0 text-white/70 transition-colors duration-300 group-hover:text-black" />
                <span className="text-sm font-medium transition-colors duration-300">{action.label}</span>
                <span className="mt-1 text-xs leading-relaxed text-white/45 transition-colors duration-300 group-hover:text-black/65">
                  {action.text}
                </span>
              </button>
            </Reveal>
          ))}
        </div>

        {/* 底部提示 */}
        <Reveal delay={900}>
          <div className="mt-10 flex items-center justify-center gap-2 font-mono text-[10px] tracking-widest text-white/35">
            <ArrowDown className="h-3.5 w-3.5 animate-bounce" />
            在下方输入框开始提问
          </div>
        </Reveal>
      </div>
    </div>
  );
}