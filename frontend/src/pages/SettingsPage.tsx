import { useState, useEffect, useRef } from 'react';
import { Moon, Sun, Monitor, Zap, Type, Eye, Info, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Badge } from '@/components/ui/badge';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { RiskLevel } from '@/types/truthnet';

// ---------- 存储 key ----------
const STORAGE_KEY = 'truthnet-settings';

interface Settings {
  theme: 'light' | 'dark' | 'system';
  reduceMotion: boolean;
  fontSize: 'sm' | 'md' | 'lg';
  showRiskColors: boolean;
  showIndustryBenchmarks: boolean;
}

const DEFAULTS: Settings = {
  theme: 'dark',
  reduceMotion: false,
  fontSize: 'md',
  showRiskColors: true,
  showIndustryBenchmarks: true,
};

function loadSettings(): Settings | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return null;
  }
}

/** 无存储时，从当前实际 DOM 状态推导（而非默认值），保证设置页反映当前状态 */
function deriveCurrentSettings(): Settings {
  const root = document.documentElement;
  const px = parseFloat(getComputedStyle(root).fontSize);
  const fontSize: Settings['fontSize'] = px >= 17 ? 'lg' : px <= 15 ? 'sm' : 'md';
  return {
    ...DEFAULTS,
    theme: root.classList.contains('dark') ? 'dark' : 'light',
    fontSize,
  };
}

function saveSettings(s: Settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

// ---------- 风险色预览 ----------
const RISK_COLORS: Record<RiskLevel, string> = {
  red: 'bg-red-500',
  orange: 'bg-orange-500',
  yellow: 'bg-yellow-500',
  blue: 'bg-blue-500',
  green: 'bg-green-500',
  unknown: 'bg-muted-foreground/40',
};

const RISK_LABELS: Record<RiskLevel, string> = {
  red: '高风险',
  orange: '中高风险',
  yellow: '中等关注',
  blue: '低风险',
  green: '未见异常',
  unknown: '数据不足',
};

// ---------- 组件 ----------
export default function SettingsPage() {
  useDocumentTitle('设置');
  const navigate = useNavigate();
  const [settings, setSettings] = useState<Settings>(() => loadSettings() ?? deriveCurrentSettings());
  // 首次挂载跳过副作用：进入设置页展示的是"当前实际状态"，用户点选后才应用变更
  const skipApplyRef = useRef(true);

  useEffect(() => {
    if (skipApplyRef.current) {
      skipApplyRef.current = false;
      return;
    }
    saveSettings(settings);
    // 应用主题
    const root = document.documentElement;
    if (settings.theme === 'dark') {
      root.classList.add('dark');
    } else if (settings.theme === 'light') {
      root.classList.remove('dark');
    } else {
      // system
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      if (mq.matches) root.classList.add('dark');
      else root.classList.remove('dark');
    }
    // 应用动画
    root.style.setProperty(
      '--reduce-motion',
      settings.reduceMotion ? 'reduce' : 'no-preference',
    );
    // 应用字号
    const fontSizeMap: Record<string, string> = { sm: '14px', md: '16px', lg: '18px' };
    root.style.fontSize = fontSizeMap[settings.fontSize] || '16px';
  }, [settings]);

  const update = (patch: Partial<Settings>) =>
    setSettings((s) => ({ ...s, ...patch }));

  return (
    <div className="min-h-screen bg-background">
      {/* 顶部导航 */}
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex max-w-3xl items-center gap-4 px-6 py-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="size-5" />
          </Button>
          <h1 className="text-lg font-semibold">本地展示设置</h1>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {/* 外观 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Monitor className="size-4" />
              外观
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 主题 */}
            <div className="space-y-2">
              <Label>主题模式</Label>
              <RadioGroup
                value={settings.theme}
                onValueChange={(v) => update({ theme: v as Settings['theme'] })}
                className="flex gap-4"
              >
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="light" id="theme-light" />
                  <Label htmlFor="theme-light" className="flex items-center gap-1 cursor-pointer">
                    <Sun className="size-4" /> 浅色
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="dark" id="theme-dark" />
                  <Label htmlFor="theme-dark" className="flex items-center gap-1 cursor-pointer">
                    <Moon className="size-4" /> 深色
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="system" id="theme-system" />
                  <Label htmlFor="theme-system" className="flex items-center gap-1 cursor-pointer">
                    <Monitor className="size-4" /> 跟随系统
                  </Label>
                </div>
              </RadioGroup>
            </div>

            <Separator />

            {/* 字号 */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Type className="size-4" />
                字号
              </Label>
              <RadioGroup
                value={settings.fontSize}
                onValueChange={(v) => update({ fontSize: v as Settings['fontSize'] })}
                className="flex gap-4"
              >
                {([
                  ['sm', '小'],
                  ['md', '中'],
                  ['lg', '大'],
                ] as const).map(([v, label]) => (
                  <div key={v} className="flex items-center gap-2">
                    <RadioGroupItem value={v} id={`font-${v}`} />
                    <Label htmlFor={`font-${v}`} className="cursor-pointer">
                      {label}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          </CardContent>
        </Card>

        {/* 动画 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Zap className="size-4" />
              动画与动效
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <Label htmlFor="reduce-motion">减少动画效果</Label>
                <p className="text-sm text-muted-foreground">
                  关闭页面过渡、数字滚动、消息气泡等动画
                </p>
              </div>
              <Switch
                id="reduce-motion"
                checked={settings.reduceMotion}
                onCheckedChange={(v) => update({ reduceMotion: v })}
              />
            </div>
          </CardContent>
        </Card>

        {/* 风险展示 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Eye className="size-4" />
              风险展示
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <Label htmlFor="risk-colors">显示风险颜色标注</Label>
                <p className="text-sm text-muted-foreground">
                  在风险卡片、规则卡、时间线中显示颜色
                </p>
              </div>
              <Switch
                id="risk-colors"
                checked={settings.showRiskColors}
                onCheckedChange={(v) => update({ showRiskColors: v })}
              />
            </div>

            {/* 风险色预览 */}
            <div className="flex flex-wrap gap-2">
              {(Object.keys(RISK_COLORS) as RiskLevel[]).map((level) => (
                <Badge
                  key={level}
                  variant="outline"
                  className="flex items-center gap-1.5"
                >
                  <span
                    className={`inline-block size-2.5 rounded-full ${settings.showRiskColors ? RISK_COLORS[level] : 'bg-muted-foreground/40'}`}
                  />
                  {RISK_LABELS[level]}
                </Badge>
              ))}
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <Label htmlFor="benchmarks">显示行业对比基准</Label>
                <p className="text-sm text-muted-foreground">
                  在财务规则卡中显示行业分位参考线
                </p>
              </div>
              <Switch
                id="benchmarks"
                checked={settings.showIndustryBenchmarks}
                onCheckedChange={(v) => update({ showIndustryBenchmarks: v })}
              />
            </div>
          </CardContent>
        </Card>

        {/* 关于 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="size-4" />
              关于
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">TruthNet</span>
              {' '}织网鉴真 — 财报反欺诈智能问答系统
            </p>
            <p>版本 V12 · 2026</p>
            <p>第五届中国研究生金融科技创新大赛</p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}