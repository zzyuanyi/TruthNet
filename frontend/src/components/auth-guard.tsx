
import { useAuth } from '@/contexts/auth-context';
import { useLocation, useNavigate } from 'react-router-dom';
import { useEffect, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

// 登录页和注册页等不需要鉴权的路由
const PUBLIC_PATHS = ['/login'];

export function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const pathname = location.pathname;
  const navigate = useNavigate();

  const isPublicPath = PUBLIC_PATHS.some(p => pathname.startsWith(p));

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !isPublicPath) {
      navigate('/login');
    }
  }, [isLoading, isAuthenticated, isPublicPath, navigate]);

  // 正在加载中 — 显示全屏 spinner
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">正在验证身份...</p>
        </div>
      </div>
    );
  }

  // 未登录且不在公开页面 — 显示加载中（等待跳转）
  if (!isAuthenticated && !isPublicPath) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // 已登录但访问登录页 — 跳转到首页
  if (isAuthenticated && isPublicPath) {
    // login 页面自己处理跳转，这里不需要额外处理
  }

  return <>{children}</>;
}
