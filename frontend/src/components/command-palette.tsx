import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useHotkeys } from "react-hotkeys-hook";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import {
  MessageSquare,
  Building2,
  GitCompare,
  Settings,
  FileText,
  Shield,
  Home,
} from "lucide-react";

const pages = [
  { label: "智能问答", path: "/", icon: MessageSquare, keywords: ["chat", "对话", "问答", "ai", "分析"] },
  { label: "企业画像", path: "/company", icon: Building2, keywords: ["公司", "企业", "profile", "财报"] },
  { label: "跨公司对比", path: "/compare", icon: GitCompare, keywords: ["对比", "比较", "compare", "竞品"] },
  { label: "规则配置", path: "/rules", icon: Shield, keywords: ["规则", "rule", "配置", "阈值"] },
  { label: "设置", path: "/settings", icon: Settings, keywords: ["设置", "setting", "偏好", "主题"] },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useHotkeys("mod+k", (e) => {
    e.preventDefault();
    setOpen((prev) => !prev);
  });

  useHotkeys("escape", () => {
    setOpen(false);
  }, { enabled: open });

  const handleSelect = useCallback(
    (path: string) => {
      setOpen(false);
      navigate(path);
    },
    [navigate]
  );

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="搜索页面或功能..." />
      <CommandList>
        <CommandEmpty>未找到匹配结果</CommandEmpty>
        <CommandGroup heading="页面导航">
          {pages.map((page) => (
            <CommandItem
              key={page.path}
              value={`${page.label} ${page.keywords.join(" ")}`}
              onSelect={() => handleSelect(page.path)}
            >
              <page.icon className="mr-2 h-4 w-4" />
              <span>{page.label}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {page.path === "/" ? "首页" : page.path}
              </span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
      <div className="border-t px-3 py-2 text-xs text-muted-foreground flex gap-4">
        <span><kbd className="inline-flex items-center rounded border px-1 font-mono text-[10px]">↑↓</kbd> 导航</span>
        <span><kbd className="inline-flex items-center rounded border px-1 font-mono text-[10px]">↵</kbd> 选择</span>
        <span><kbd className="inline-flex items-center rounded border px-1 font-mono text-[10px]">Esc</kbd> 关闭</span>
      </div>
    </CommandDialog>
  );
}