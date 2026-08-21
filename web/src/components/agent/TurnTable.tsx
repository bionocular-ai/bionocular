'use client';

import type { ResultTable } from '@/lib/agent/result-table';
import { cn } from '@/lib/utils';

/**
 * The turn's rows, drawn by the app rather than transcribed by the model.
 *
 * Open by default and unclamped: `ToolStep` keeps a per-query disclosure for
 * checking one call's raw result, but this is the answer itself.
 */
export function TurnTable({ table }: { table: ResultTable }) {
  return (
    <div className="relative mb-1.5">
      <span
        aria-hidden
        className={cn(
          'absolute top-[9px] -left-[25px] h-[7px] w-[7px] rounded-full',
          'border border-(--brand-border) bg-(--brand-bg)'
        )}
      />
      <div className="overflow-x-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface)">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr>
              {table.columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    'border-b border-(--brand-border) bg-(--brand-accent-light)',
                    'px-2 py-1.5 text-left font-mono font-medium whitespace-nowrap',
                    'text-(--brand-primary)'
                  )}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={row[0] ?? rowIndex} className="border-b border-(--brand-border)/50 last:border-b-0">
                {row.map((cell, cellIndex) => (
                  <td
                    key={table.columns[cellIndex].key}
                    className="max-w-[34ch] px-2 py-1 align-top text-(--brand-text-muted)"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
