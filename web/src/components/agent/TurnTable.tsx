'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import type { ResultTable } from '@/lib/agent/result-table';
import { NCT_ID_PATTERN, trialRoute } from '@/lib/constants';
import { cn } from '@/lib/utils';

/** Anchor treatment matched to the one `createMarkdownComponents` gives an in-app link. */
const NCT_LINK_CLASSES = cn(
  'font-mono text-[12px] font-medium text-(--brand-primary)',
  'border-b border-(--brand-border) pb-px no-underline',
  'hover:border-(--brand-primary)'
);

/**
 * The turn's rows, drawn by the app rather than transcribed by the model.
 *
 * Open by default and unclamped: `ToolStep` keeps a per-query disclosure for
 * checking one call's raw result, but this is the answer itself.
 *
 * Nine columns are wider than the chat column, so the table scrolls sideways
 * inside its own box. Nothing in the default rendering says so - the clipped
 * edge looks like the end of the row - hence the fade, shown only while there
 * is something past the right edge to reach.
 *
 * Dropping the trial-name column (see `turn-table.ts`) leans on `nct_id`
 * being the row's one navigable identifier, so that cell is linked here
 * rather than left as the plain text every other cell renders as. Any cell
 * that does not look like a real NCT number - `ABSENT` included - fails the
 * pattern check and falls through to plain text instead of a link to a
 * nonsense route.
 */
export function TurnTable({ table, cancerType }: { table: ResultTable; cancerType: string }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [clipped, setClipped] = useState(false);

  const measure = useCallback(() => {
    const node = scroller.current;
    if (node) setClipped(node.scrollLeft + node.clientWidth < node.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [measure, table]);

  return (
    <div className="relative mb-1.5">
      <span
        aria-hidden
        className={cn(
          'absolute top-[9px] -left-[25px] h-[7px] w-[7px] rounded-full',
          'border border-(--brand-border) bg-(--brand-bg)'
        )}
      />
      <div
        ref={scroller}
        onScroll={measure}
        className="overflow-x-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface)"
      >
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
                  scope="col"
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
                    {table.columns[cellIndex].key === 'nct_id' && NCT_ID_PATTERN.test(cell) ? (
                      <Link href={trialRoute(cell, cancerType)} className={NCT_LINK_CLASSES}>
                        {cell}
                      </Link>
                    ) : (
                      cell
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {clipped ? (
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-y-px right-px w-10 rounded-r-[3px]',
            'bg-gradient-to-l from-(--brand-surface) to-transparent'
          )}
        />
      ) : null}
    </div>
  );
}
