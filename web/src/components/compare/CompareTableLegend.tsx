'use client';

import * as React from 'react';

export function CompareTableLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-600 px-4 py-3 border-t border-slate-200">
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block h-4 w-6 rounded-sm border border-slate-300"
          style={{
            backgroundImage:
              'repeating-linear-gradient(45deg, #f1f5f9 0 4px, #ffffff 4px 8px)',
          }}
        />
        <span>
          <strong className="text-slate-700">NR</strong> — not reported
        </span>
      </span>
      <span>
        <strong className="text-slate-700">NE</strong> — not estimable / not reached
      </span>
      <span>
        <strong className="text-slate-700">Cov</strong> — drugs with data / total
      </span>
    </div>
  );
}
