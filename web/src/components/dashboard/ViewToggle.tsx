'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export type ViewMode = 'landscape' | 'bullseye';

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export function ViewToggle({ value, onChange }: ViewToggleProps) {
  return (
    <div className="inline-flex items-center rounded-sm border border-slate-200 bg-slate-100 p-0.5 gap-0.5">
      <button
        type="button"
        onClick={() => onChange('landscape')}
        className={cn(
          'rounded-sm px-3 py-1.5 text-sm font-medium transition-colors',
          value === 'landscape'
            ? 'bg-teal-500 text-white shadow-sm'
            : 'text-slate-600 hover:text-slate-900 hover:bg-white/70'
        )}
      >
        Landscape
      </button>
      <button
        type="button"
        onClick={() => onChange('bullseye')}
        className={cn(
          'rounded-sm px-3 py-1.5 text-sm font-medium transition-colors',
          value === 'bullseye'
            ? 'bg-teal-500 text-white shadow-sm'
            : 'text-slate-600 hover:text-slate-900 hover:bg-white/70'
        )}
      >
        Bullseye
      </button>
    </div>
  );
}
