'use client';

import { useState, useMemo, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  ChevronLeft,
  ChevronRight,
  Rows3,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ─── Types ─── */
export interface PreviewColumn {
  key: string;
  label: string;
  type: 'numeric' | 'categorical' | 'datetime' | 'text';
}

export interface PreviewRow {
  [key: string]: string | number | null;
}

interface DataPreviewTableProps {
  columns: PreviewColumn[];
  rows: PreviewRow[];
  maxRows?: number;
}

type SortDir = 'asc' | 'desc' | null;

const PAGE_SIZE = 20;

/* ─── Component ─── */
export function DataPreviewTable({ columns, rows, maxRows = 100 }: DataPreviewTableProps) {
  const displayRows = useMemo(() => rows.slice(0, maxRows), [rows, maxRows]);

  const [searchQuery, setSearchQuery] = useState('');
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [page, setPage] = useState(0);

  // Filter
  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return displayRows;
    const q = searchQuery.toLowerCase();
    return displayRows.filter((row) =>
      columns.some((col) => String(row[col.key] ?? '').toLowerCase().includes(q))
    );
  }, [displayRows, searchQuery, columns]);

  // Sort
  const sorted = useMemo(() => {
    if (!sortCol || !sortDir) return filtered;
    return [...filtered].sort((a, b) => {
      const va = a[sortCol];
      const vb = b[sortCol];
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const colDef = columns.find((c) => c.key === sortCol);
      if (colDef?.type === 'numeric') {
        const na = typeof va === 'number' ? va : parseFloat(String(va));
        const nb = typeof vb === 'number' ? vb : parseFloat(String(vb));
        return sortDir === 'asc' ? na - nb : nb - na;
      }
      const sa = String(va);
      const sb = String(vb);
      return sortDir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
  }, [filtered, sortCol, sortDir, columns]);

  // Pagination
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = useMemo(() => {
    const start = page * PAGE_SIZE;
    return sorted.slice(start, start + PAGE_SIZE);
  }, [sorted, page]);

  const handleSort = useCallback((key: string) => {
    setSortCol((prev) => {
      if (prev !== key) {
        setSortDir('asc');
        setPage(0);
        return key;
      }
      setSortDir((d) => {
        if (d === 'asc') { setPage(0); return 'desc'; }
        if (d === 'desc') { setPage(0); return null; }
        setPage(0);
        return 'asc';
      });
      return key;
    });
  }, []);

  const typeBadgeStyle: Record<string, string> = {
    numeric: 'bg-blue-50 text-blue-700',
    categorical: 'bg-amber-50 text-amber-700',
    datetime: 'bg-purple-50 text-purple-700',
    text: 'bg-emerald-50 text-emerald-700',
  };

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Rows3 className="h-4 w-4 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            预览前 {displayRows.length} 行
            {searchQuery.trim() && ` · 匹配 ${filtered.length} 行`}
          </span>
        </div>
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="搜索数据..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border/60 overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/30 hover:bg-muted/30">
                <TableHead className="w-10 text-center text-[11px] font-medium">#</TableHead>
                {columns.map((col) => (
                  <TableHead
                    key={col.key}
                    className="text-[11px] font-medium cursor-pointer select-none hover:bg-muted/50 transition-colors"
                    onClick={() => handleSort(col.key)}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono">{col.label}</span>
                      <Badge
                        variant="outline"
                        className={cn('text-[9px] px-1 py-0 border-0', typeBadgeStyle[col.type])}
                      >
                        {col.type === 'numeric' ? '数值' : col.type === 'categorical' ? '分类' : col.type === 'datetime' ? '时间' : '文本'}
                      </Badge>
                      {sortCol === col.key ? (
                        sortDir === 'asc' ? <ArrowUp className="h-3 w-3 text-blue-600" /> : <ArrowDown className="h-3 w-3 text-blue-600" />
                      ) : (
                        <ArrowUpDown className="h-3 w-3 text-muted-foreground/40" />
                      )}
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {paged.map((row, ri) => (
                <TableRow key={ri} className="hover:bg-accent/20 transition-colors">
                  <TableCell className="text-center text-[11px] text-muted-foreground">
                    {page * PAGE_SIZE + ri + 1}
                  </TableCell>
                  {columns.map((col) => {
                    const val = row[col.key];
                    const isNull = val === null || val === undefined || val === '';
                    return (
                      <TableCell key={col.key} className="text-xs font-mono max-w-[200px] truncate">
                        {isNull ? (
                          <span className="text-red-400 italic text-[11px]">NULL</span>
                        ) : (
                          <span className={cn(col.type === 'numeric' && 'text-right tabular-nums')}>
                            {String(val)}
                          </span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
              {paged.length === 0 && (
                <TableRow>
                  <TableCell colSpan={columns.length + 1} className="text-center py-8 text-sm text-muted-foreground">
                    无匹配数据
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            第 {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sorted.length)} 行，共 {sorted.length} 行
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            {Array.from({ length: totalPages }, (_, i) => i).map((p) => (
              <Button
                key={p}
                variant={p === page ? 'default' : 'outline'}
                size="sm"
                className="h-7 w-7 p-0 text-xs"
                onClick={() => setPage(p)}
              >
                {p + 1}
              </Button>
            ))}
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
