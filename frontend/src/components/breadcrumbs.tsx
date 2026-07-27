
import { useLocation, Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

const ROUTE_MAP: Record<string, string> = {
  copilot: '智能建模',
  tasks: '建模任务',
  repository: '模型仓库',
  service: '模型服务',
};

export function Breadcrumbs() {
  const location = useLocation();
  const pathname = location.pathname;

  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 0) return null;

  const crumbs: { label: string; href: string; isLast: boolean }[] = [];

  let currentPath = '';
  for (let i = 0; i < segments.length; i++) {
    currentPath += `/${segments[i]}`;
    const isLast = i === segments.length - 1;
    const seg = segments[i];

    const label = ROUTE_MAP[seg] || (seg.match(/^\d+$/) ? `模型 #${seg}` : seg);
    crumbs.push({ label, href: currentPath, isLast });
  }

  return (
    <nav aria-label="面包屑导航" className="flex items-center gap-1 text-sm text-muted-foreground py-2 px-4 md:px-6">
      {crumbs.map((crumb, i) => (
        <span key={`${crumb.href}-${i}`} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />}
          {crumb.isLast ? (
            <span className="font-medium text-foreground">{crumb.label}</span>
          ) : (
            <Link
              to={crumb.href}
              className="transition-colors hover:text-foreground"
            >
              {crumb.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
