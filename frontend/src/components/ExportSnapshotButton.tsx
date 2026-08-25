// 织网鉴真 TruthNet - 报告快照导出按钮
// 通过浏览器打印引擎将当前页面「另存为 PDF」，零依赖、中文/图表矢量清晰。
// 8/25 增强：打印前把页面中的 <canvas>（如 G6 股权穿透图）实时转成高清位图
// 图片，避免 Canvas 因内部 transform/DPR 缩放导致打印空白或裁切——确保导出
// 的报告里包含股权图等图表图片。

import { Button } from '@/components/ui/button';
import { Printer } from 'lucide-react';

interface ExportSnapshotButtonProps {
  label?: string;
  className?: string;
}

interface CanvasReplacement {
  canvas: HTMLCanvasElement;
  img: HTMLImageElement;
}

export function ExportSnapshotButton({ label = '导出快照', className }: ExportSnapshotButtonProps) {
  const handleExport = () => {
    // 收集页面可见、非空的 canvas（G6 股权图等）
    const canvases = Array.from(document.querySelectorAll<HTMLCanvasElement>('canvas'));
    const replacements: CanvasReplacement[] = [];

    for (const canvas of canvases) {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      try {
        const dataUrl = canvas.toDataURL('image/png');
        if (!dataUrl || dataUrl === 'data:,') continue;
        const img = document.createElement('img');
        img.src = dataUrl;
        img.alt = '股权穿透图';
        img.style.width = `${rect.width}px`;
        img.style.height = `${rect.height}px`;
        img.style.display = 'block';
        img.style.maxWidth = '100%';
        // 隐藏原 canvas、在其原位置后插入等尺寸 img（打印引擎渲染 img 稳定）
        canvas.style.display = 'none';
        canvas.parentElement?.insertBefore(img, canvas.nextSibling);
        replacements.push({ canvas, img });
      } catch {
        // 跨域（被污染）canvas 无法 toDataURL：跳过，保留原 canvas 打印
      }
    }

    const cleanup = () => {
      for (const { canvas, img } of replacements) {
        img.remove();
        canvas.style.display = '';
      }
      window.removeEventListener('afterprint', cleanup);
    };

    window.addEventListener('afterprint', cleanup);
    window.print();
    // 兜底：部分环境/取消打印对话框时不触发 afterprint
    window.setTimeout(cleanup, 1000);
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={className ?? 'gap-1.5'}
      data-no-print
      onClick={handleExport}
    >
      <Printer className="h-3.5 w-3.5" />
      {label}
    </Button>
  );
}