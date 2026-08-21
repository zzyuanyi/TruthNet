// 织网鉴真 TruthNet - 报告快照导出按钮
// 通过浏览器打印引擎将当前页面「另存为 PDF」，零依赖、中文/图表矢量清晰

import { Button } from '@/components/ui/button';
import { Printer } from 'lucide-react';

interface ExportSnapshotButtonProps {
  label?: string;
  className?: string;
}

export function ExportSnapshotButton({ label = '导出快照', className }: ExportSnapshotButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={className ?? 'gap-1.5'}
      data-no-print
      onClick={() => window.print()}
    >
      <Printer className="h-3.5 w-3.5" />
      {label}
    </Button>
  );
}