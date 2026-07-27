
import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Model, type ServiceInstance } from '@/lib/api-client';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import {
  ChevronRight,
  MessageSquare,
  Database,
  Package,
  Server,
  Search,
  ArrowRight,
  Command,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SearchItem {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  keywords: string[];
  category: string;
}

// 静态页面搜索项 — 始终可用
const PAGE_ITEMS: SearchItem[] = [
  { id: 'copilot', title: '智能建模', description: 'AI对话驱动建模、Agent工作流', icon: MessageSquare, href: '/copilot', keywords: ['copilot', '智能建模', '对话', 'AI', '助手'], category: '页面' },
  { id: 'tasks', title: '建模任务', description: '任务管理、产物查看、存入仓库', icon: Database, href: '/tasks', keywords: ['tasks', '建模任务', '任务', '产物'], category: '页面' },
  { id: 'repository', title: '模型仓库', description: '模型列表、筛选、版本管理', icon: Package, href: '/repository', keywords: ['repository', '模型仓库', '仓库', '模型'], category: '页面' },
  { id: 'service', title: '模型服务', description: '服务部署、运行状态、推理测试', icon: Server, href: '/service', keywords: ['service', '模型服务', '部署', '推理', '服务'], category: '页面' },
];

// 从后端获取动态搜索项
async function fetchDynamicItems(): Promise<SearchItem[]> {
  const items: SearchItem[] = [];

  try {
    // 并行获取模型和服务
    const [modelsData, servicesData] = await Promise.allSettled([
      api.models.list(),
      api.services.list(),
    ]);

    // 模型条目
    if (modelsData.status === 'fulfilled' && modelsData.value) {
      const models: Model[] = modelsData.value.items || [];
      for (const m of models) {
        items.push({
          id: `model-${m.id}`,
          title: m.name,
          description: m.type || '模型',
          icon: Package,
          href: `/repository/${m.id}`,
          keywords: [m.name, `模型${m.id}`, m.type || ''],
          category: '模型',
        });
      }
    }

    // 服务条目
    if (servicesData.status === 'fulfilled' && servicesData.value) {
      const services: ServiceInstance[] = servicesData.value.items || [];
      const statusLabel: Record<string, string> = {
        running: '运行中',
        stopped: '已停止',
        error: '异常',
        deploying: '部署中',
      };
      for (const s of services) {
        items.push({
          id: `svc-${s.modelServiceId}`,
          title: `服务 ${s.modelServiceId}`,
          description: `${statusLabel[s.status] || s.status} | 版本 ${s.modelVersionId}`,
          icon: Server,
          href: '/service',
          keywords: [`服务${s.modelServiceId}`, s.status, `版本${s.modelVersionId}`],
          category: '服务',
        });
      }
    }
  } catch {
    // 静默失败 — 搜索仍可用页面条目
  }

  return items;
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [dynamicItems, setDynamicItems] = useState<SearchItem[]>([]);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  // 合并：页面条目 + 动态条目
  const SEARCH_ITEMS = [...PAGE_ITEMS, ...dynamicItems];

  // 打开时刷新动态数据
  useEffect(() => {
    if (open) {
      fetchDynamicItems().then(setDynamicItems);
    }
  }, [open]);

  // Cmd+K / Ctrl+K to open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    const handleCustomOpen = () => setOpen(true);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('open-global-search', handleCustomOpen);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('open-global-search', handleCustomOpen);
    };
  }, []);

  // Reset on open/close
  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const filtered = query.trim()
    ? SEARCH_ITEMS.filter((item) => {
        const q = query.toLowerCase();
        return (
          item.title.toLowerCase().includes(q) ||
          item.description.toLowerCase().includes(q) ||
          item.keywords.some((k) => k.toLowerCase().includes(q))
        );
      })
    : SEARCH_ITEMS;

  const handleSelect = useCallback((item: SearchItem) => {
    setOpen(false);
    navigate(item.href);
  }, [navigate]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      handleSelect(filtered[selectedIndex]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }, [filtered, selectedIndex, handleSelect]);

  // Group by category
  const grouped = filtered.reduce<Record<string, SearchItem[]>>((acc, item) => {
    if (!acc[item.category]) acc[item.category] = [];
    acc[item.category].push(item);
    return acc;
  }, {});

  const categoryOrder = ['页面', '模型', '任务', '服务'];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="gap-0 overflow-hidden p-0 shadow-2xl sm:max-w-[560px] [&>button]:hidden">
        {/* Search Input */}
        <div className="flex items-center border-b px-3">
          <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="搜索页面、模型、任务、服务..."
            className="flex h-12 w-full bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground/60"
          />
          <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[360px] overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              没有找到匹配结果
            </div>
          ) : (
            categoryOrder.map((cat) => {
              const items = grouped[cat];
              if (!items) return null;
              return (
                <div key={cat}>
                  <div className="px-2 py-1.5 text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">
                    {cat}
                  </div>
                  {items.map((item) => {
                    const globalIndex = filtered.indexOf(item);
                    const isSelected = globalIndex === selectedIndex;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleSelect(item)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                        className={cn(
                          'flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm transition-colors',
                          isSelected ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50'
                        )}
                      >
                        <item.icon className={cn('h-4 w-4 shrink-0', isSelected ? 'text-primary' : 'text-muted-foreground')} />
                        <div className="flex-1 overflow-hidden">
                          <div className="font-medium truncate">{item.title}</div>
                          <div className="text-xs text-muted-foreground truncate">{item.description}</div>
                        </div>
                        <ArrowRight className={cn('h-3.5 w-3.5 shrink-0 transition-opacity', isSelected ? 'opacity-100' : 'opacity-0')} />
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="border-t px-3 py-2 flex items-center gap-4 text-[11px] text-muted-foreground/60">
          <span className="flex items-center gap-1">
            <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">&uarr;&darr;</kbd> 导航
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">&crarr;</kbd> 打开
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">esc</kbd> 关闭
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Trigger button for the header */
export function SearchTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 rounded-lg border border-border/60 bg-background/80 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:border-border"
    >
      <Search className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">搜索...</span>
      <kbd className="pointer-events-none hidden h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:inline-flex">
        <Command className="h-2.5 w-2.5" />K
      </kbd>
    </button>
  );
}
