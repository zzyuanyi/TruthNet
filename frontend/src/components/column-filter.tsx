'use client';

import { useState, useCallback } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Filter, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface FilterOption {
  label: string;
  value: string;
}

interface ColumnFilterProps {
  options?: FilterOption[];
  selectedValues: string[];
  onFilterChange: (values: string[]) => void;
  type?: 'select' | 'search';
  searchPlaceholder?: string;
}

export function ColumnFilter({ options, selectedValues, onFilterChange, type = 'select', searchPlaceholder = '搜索...' }: ColumnFilterProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const hasFilter = selectedValues.length > 0;

  const filteredOptions = options?.filter((opt) =>
    opt.label.toLowerCase().includes(search.toLowerCase())
  );

  const toggleValue = useCallback((value: string) => {
    if (selectedValues.includes(value)) {
      onFilterChange(selectedValues.filter((v) => v !== value));
    } else {
      onFilterChange([...selectedValues, value]);
    }
  }, [selectedValues, onFilterChange]);

  const clearFilter = useCallback(() => {
    onFilterChange([]);
    setOpen(false);
  }, [onFilterChange]);

  const selectAll = useCallback(() => {
    onFilterChange(options?.map((o) => o.value) ?? []);
  }, [options, onFilterChange]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            'inline-flex items-center gap-0.5 rounded p-0.5 transition-colors',
            hasFilter
              ? 'text-blue-600 hover:text-blue-700'
              : 'text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-foreground'
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <Filter className="h-3 w-3" />
          {hasFilter && (
            <span className="text-[10px] font-medium">{selectedValues.length}</span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-52 p-0" align="start">
        <div className="border-b px-3 py-2">
          <Input
            placeholder={searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-7 text-xs"
          />
        </div>
        {type === 'select' && filteredOptions && (
          <div className="max-h-48 overflow-y-auto py-1">
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-2 text-xs text-muted-foreground">无匹配项</div>
            ) : (
              filteredOptions.map((opt) => (
                <button
                  key={opt.value}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent transition-colors"
                  onClick={() => toggleValue(opt.value)}
                >
                  <span className={cn(
                    'flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border',
                    selectedValues.includes(opt.value)
                      ? 'border-blue-600 bg-blue-600 text-white'
                      : 'border-border'
                  )}>
                    {selectedValues.includes(opt.value) && <Check className="h-2.5 w-2.5" />}
                  </span>
                  <span className="truncate">{opt.label}</span>
                </button>
              ))
            )}
          </div>
        )}
        <div className="flex items-center justify-between border-t px-3 py-1.5">
          <button
            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            onClick={clearFilter}
          >
            清除
          </button>
          {type === 'select' && (
            <button
              className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              onClick={selectAll}
            >
              全选
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
