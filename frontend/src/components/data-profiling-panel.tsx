'use client';

import { useMemo, useState } from 'react';
import { BarChart2, ChevronDown, ChevronRight, Database } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataPreviewTable, type PreviewColumn, type PreviewRow } from '@/components/data-preview-table';
import { cn } from '@/lib/utils';

export interface ColumnProfile {
  name: string;
  type: 'numeric' | 'categorical' | 'datetime' | 'text';
  nonNull: number;
  total: number;
  nullRate: string;
  unique: number;
  mean?: string;
  std?: string;
  min?: string;
  max?: string;
  topValues?: { value: string; count: number }[];
  iv?: number;
  skewness?: number;
}

export interface ProfilingDataFile {
  id: string;
  name: string;
  rows: number;
  columns: number;
  columnProfiles: ColumnProfile[];
  previewCols?: PreviewColumn[];
  previewRows?: PreviewRow[];
}

interface DataProfilingPanelProps {
  files?: ProfilingDataFile[];
  previewMap?: Record<string, { cols: PreviewColumn[]; rows: PreviewRow[] }>;
}

function ColumnTypeBadge({ type }: { type: ColumnProfile['type'] }) {
  const labels: Record<ColumnProfile['type'], string> = {
    numeric: '数值',
    categorical: '分类',
    datetime: '时间',
    text: '文本',
  };
  const classes: Record<ColumnProfile['type'], string> = {
    numeric: 'border-blue-200 bg-blue-50 text-blue-700',
    categorical: 'border-purple-200 bg-purple-50 text-purple-700',
    datetime: 'border-amber-200 bg-amber-50 text-amber-700',
    text: 'border-slate-200 bg-slate-50 text-slate-700',
  };
  return <Badge variant="outline" className={cn('px-1.5 py-0 text-[10px]', classes[type])}>{labels[type]}</Badge>;
}

function buildFallbackPreview(file: ProfilingDataFile): { cols: PreviewColumn[]; rows: PreviewRow[] } {
  const cols: PreviewColumn[] = file.previewCols?.length
    ? file.previewCols
    : file.columnProfiles.map((col) => ({ key: col.name, label: col.name, type: col.type }));
  return { cols, rows: file.previewRows ?? [] };
}

export function DataProfilingPanel({ files, previewMap }: DataProfilingPanelProps) {
  const dataFiles = files ?? [];
  const [expandedFileId, setExpandedFileId] = useState<string | null>(dataFiles[0]?.id ?? null);
  const [tab, setTab] = useState<'profile' | 'preview'>('profile');

  const totals = useMemo(() => ({
    files: dataFiles.length,
    rows: dataFiles.reduce((sum, file) => sum + (Number(file.rows) || 0), 0),
    columns: dataFiles.reduce((sum, file) => sum + (Number(file.columns) || 0), 0),
  }), [dataFiles]);

  if (dataFiles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
        <BarChart2 className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-sm">暂无真实数据文件</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 text-sm sm:grid-cols-3">
        <div className="rounded-lg border bg-background p-3">
          <div className="text-muted-foreground">真实文件</div>
          <div className="mt-1 text-lg font-semibold">{totals.files.toLocaleString()} 个</div>
        </div>
        <div className="rounded-lg border bg-background p-3">
          <div className="text-muted-foreground">真实行数</div>
          <div className="mt-1 text-lg font-semibold">{totals.rows.toLocaleString()} 行</div>
        </div>
        <div className="rounded-lg border bg-background p-3">
          <div className="text-muted-foreground">真实列数</div>
          <div className="mt-1 text-lg font-semibold">{totals.columns.toLocaleString()} 列</div>
        </div>
      </div>

      {dataFiles.map((file) => {
        const expanded = expandedFileId === file.id;
        const preview = previewMap?.[file.id] ?? buildFallbackPreview(file);
        return (
          <div key={file.id} className="rounded-lg border bg-background">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
              onClick={() => setExpandedFileId(expanded ? null : file.id)}
            >
              <span className="flex min-w-0 items-center gap-3">
                {expanded ? <ChevronDown className="h-4 w-4 text-primary" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                <Database className="h-4 w-4 text-blue-500" />
                <span className="truncate font-medium">{file.name}</span>
              </span>
              <span className="shrink-0 text-sm text-muted-foreground">
                {file.rows.toLocaleString()} 行 · {file.columns.toLocaleString()} 列
              </span>
            </button>

            {expanded && (
              <div className="border-t px-4 py-3">
                <div className="mb-3 flex gap-2">
                  <Button size="sm" variant={tab === 'profile' ? 'default' : 'outline'} onClick={() => setTab('profile')}>字段画像</Button>
                  <Button size="sm" variant={tab === 'preview' ? 'default' : 'outline'} onClick={() => setTab('preview')}>数据预览</Button>
                </div>

                {tab === 'profile' ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] text-sm">
                      <thead className="border-b text-muted-foreground">
                        <tr>
                          <th className="py-2 text-left font-medium">字段</th>
                          <th className="py-2 text-left font-medium">类型</th>
                          <th className="py-2 text-right font-medium">非空</th>
                          <th className="py-2 text-right font-medium">缺失率</th>
                          <th className="py-2 text-right font-medium">唯一值</th>
                          <th className="py-2 text-left font-medium">真实统计</th>
                        </tr>
                      </thead>
                      <tbody>
                        {file.columnProfiles.map((col) => (
                          <tr key={col.name} className="border-b last:border-0">
                            <td className="py-2 font-medium">{col.name}</td>
                            <td className="py-2"><ColumnTypeBadge type={col.type} /></td>
                            <td className="py-2 text-right">{col.nonNull.toLocaleString()}</td>
                            <td className="py-2 text-right">{col.nullRate}</td>
                            <td className="py-2 text-right">{col.unique.toLocaleString()}</td>
                            <td className="py-2 text-muted-foreground">
                              {col.type === 'numeric'
                                ? `min ${col.min ?? '-'} / max ${col.max ?? '-'} / mean ${col.mean ?? '-'}`
                                : col.topValues?.slice(0, 2).map((item) => `${item.value}: ${item.count}`).join('，') || '来自上传文件元数据'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : preview.rows.length > 0 ? (
                  <DataPreviewTable columns={preview.cols} rows={preview.rows} />
                ) : (
                  <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                    当前后端未返回可预览行，但文件统计来自真实上传文件。
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
