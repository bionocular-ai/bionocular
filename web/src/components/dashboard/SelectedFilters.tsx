'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface FilterTag {
  id: string;
  label: string;
  onRemove?: () => void;
}

export interface SelectedFiltersProps {
  tags: FilterTag[];
  className?: string;
}

export function SelectedFilters({ tags, className }: SelectedFiltersProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <span className="text-sm font-medium tracking-wider text-slate-500 shrink-0">
        Selected filters:
      </span>
      {tags.length === 0 ? (
        <span className="text-sm text-slate-400 italic">None</span>
      ) : (
        tags.map((tag) => (
          <span
            key={tag.id}
            className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200/80 pl-3 pr-1.5 py-1 text-xs font-medium text-teal-800"
          >
            {tag.label}
            {tag.onRemove && (
              <button
                type="button"
                onClick={tag.onRemove}
                className="rounded-full p-1 hover:bg-teal-200/60 text-teal-600 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-300 focus:ring-offset-1 transition-colors"
                aria-label={`Remove ${tag.label}`}
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        ))
      )}
    </div>
  );
}
