// 织网鉴真 TruthNet - 应用头部

import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { MessageSquare, Shield, TrendingUp } from 'lucide-react';

const navItems = [
  { href: '/', label: '智能问答', icon: MessageSquare },
  { href: '/company/000002', label: '企业画像', icon: Shield },
  { href: '/compare', label: '跨公司对比', icon: TrendingUp },
];

export function AppHeader() {
  const location = useLocation();
  const pathname = location.pathname;

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-border/60 bg-background/95 px-4 md:px-5 backdrop-blur-sm">
      <div className="flex items-center gap-4 md:gap-6">
        <Link to="/" className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <span className="text-lg font-bold tracking-tight text-foreground">
            织网鉴真
          </span>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            财报反欺诈智能问答
          </span>
        </Link>

        {/* 导航 */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map(item => (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
                pathname === item.href
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>
      </div>

      {/* 右侧 */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">
          TruthNet 织网鉴真
        </span>
      </div>
    </header>
  );
}
