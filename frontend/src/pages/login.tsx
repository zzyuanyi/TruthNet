import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/auth-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Bot,
  Eye,
  EyeOff,
  Loader2,
  Shield,
  Zap,
  BarChart3,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

const features = [
  { icon: Shield, title: '智能风控', desc: '大模型驱动的金融反欺诈检测' },
  { icon: Zap, title: '端到端建模', desc: '从数据到部署的全流程自动化' },
  { icon: BarChart3, title: '模型评估', desc: 'KS/ROC/SHAP 多维度可解释分析' },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register, isAuthenticated, isLoading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirm, setRegisterConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // 已登录则跳转
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      navigate('/copilot');
    }
  }, [authLoading, isAuthenticated, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码');
      return;
    }
    setLoading(true);
    const result = await login(username.trim(), password);
    setLoading(false);
    if (result.success) {
      navigate('/copilot');
    } else {
      setError(result.error || '登录失败');
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!registerUsername.trim() || !registerPassword.trim()) {
      setError('请输入用户名和密码');
      return;
    }
    if (registerPassword !== registerConfirm) {
      setError('两次密码输入不一致');
      return;
    }
    if (registerPassword.length < 6) {
      setError('密码至少6位');
      return;
    }
    setLoading(true);
    const result = await register(registerUsername.trim(), registerPassword);
    setLoading(false);
    if (result.success) {
      navigate('/copilot');
    } else {
      setError(result.error || '注册失败');
    }
  };

  // 加载中 / 已登录时显示骨架
  if (authLoading || isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* ====== 左侧品牌区 ====== */}
      <div className="hidden lg:flex lg:w-[52%] relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        {/* 装饰光效 */}
        <div className="absolute inset-0">
          <div className="absolute -top-1/4 -left-1/4 w-[600px] h-[600px] rounded-full bg-blue-500/10 blur-[120px]" />
          <div className="absolute -bottom-1/4 -right-1/4 w-[500px] h-[500px] rounded-full bg-indigo-500/10 blur-[100px]" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] rounded-full bg-cyan-500/5 blur-[80px]" />
        </div>

        {/* 网格背景 */}
        <div className="absolute inset-0 opacity-[0.04]" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }} />

        {/* 内容 */}
        <div className="relative z-10 flex flex-col justify-center px-16 xl:px-24">
          <div className="mb-10 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/25">
              <Bot className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">FinForge AI</h1>
              <p className="text-sm text-slate-400">金融智能风控建模平台</p>
            </div>
          </div>

          <h2 className="mb-4 text-3xl font-bold text-white leading-tight xl:text-4xl">
            大模型驱动<br />端到端模型自动生成
          </h2>
          <p className="mb-12 max-w-md text-base text-slate-400 leading-relaxed">
            从业务需求出发，AI Copilot 引导自动完成数据接入、特征工程、模型训练、评估入库、服务部署的全流程。
          </p>

          <div className="space-y-5">
            {features.map((f) => (
              <div key={f.title} className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                  <f.icon className="h-5 w-5 text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white text-sm">{f.title}</h3>
                  <p className="text-sm text-slate-400 mt-0.5">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 底部版权 */}
        <div className="absolute bottom-6 left-16 xl:left-24 text-xs text-slate-500">
          &copy; {new Date().getFullYear()} FinForge AI &middot; 大模型驱动的端到端模型自动生成场景
        </div>
      </div>

      {/* ====== 右侧表单区 ====== */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 bg-background">
        <div className="w-full max-w-[400px]">
          {/* 移动端 Logo */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600">
              <Bot className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-foreground tracking-tight">FinForge AI</h1>
              <p className="text-xs text-muted-foreground">金融智能风控建模平台</p>
            </div>
          </div>

          {/* 登录/注册切换 */}
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'login' | 'register')} className="mb-6">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">登录</TabsTrigger>
              <TabsTrigger value="register">注册</TabsTrigger>
            </TabsList>
          </Tabs>

          {/* ====== 登录表单 ====== */}
          {activeTab === 'login' && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="login-username">用户名</Label>
              <Input
                id="login-username"
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="login-password">密码</Label>
              </div>
              <div className="relative">
                <Input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="请输入密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  登录中...
                </>
              ) : (
                <>
                  登录
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </form>
          )}

          {/* ====== 注册表单 ====== */}
          {activeTab === 'register' && (
          <form onSubmit={handleRegister} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="reg-username">用户名</Label>
              <Input
                id="reg-username"
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-password">密码</Label>
              <div className="relative">
                <Input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="请输入密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  注册中...
                </>
              ) : (
                <>
                  注册
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </form>
          )}

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <Separator />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">提示</span>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <div
                className="rounded-lg border bg-muted/30 p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => { setUsername('demo'); setPassword('demo123456'); }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { setUsername('demo'); setPassword('demo123456'); } }}
              >
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                  <span className="text-muted-foreground">体验账号：点击自动填入</span>
                </div>
                <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground pl-6">
                  <span>用户名 <code className="rounded bg-muted px-1.5 py-0.5 font-mono">demo</code></span>
                  <span>密码 <code className="rounded bg-muted px-1.5 py-0.5 font-mono">demo123456</code></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
