'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import type { ResultTable } from '@/lib/agent/result-table';
import type { EfficacyLink } from '@/lib/agent/efficacy-link';
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
export function TurnTable({
  table,
  cancerType,
  efficacyLink,
}: {
  table: ResultTable;
  cancerType: string;
  /** Present only when this turn's filters are ones the hub can reproduce. */
  efficacyLink?: EfficacyLink | null;
}) {
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
              // Keyed by position, not by the first cell. That cell used to be
              // a unique `id`; `orderColumns` now leads with `nct_id`, and
              // `trial_outcomes` is one row per treatment arm - two arms of one
              // trial share an nct_id by design, which React reads as duplicate
              // keys and is free to drop rows over. Rows are positional and the
              // whole table re-renders per turn, so the index is the identity.
              <tr key={rowIndex} className="border-b border-(--brand-border)/50 last:border-b-0">
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
      {efficacyLink ? (
        <div className="flex items-baseline gap-2 pt-1.5">
          <Link
            href={efficacyLink.href}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              'inline-flex items-center gap-1 font-mono text-[10px] tracking-[0.05em]',
              'text-(--brand-text-muted) no-underline transition hover:text-(--brand-primary)'
            )}
          >
            Open in {efficacyLink.title}
            <ArrowUpRight className="h-3 w-3" />
          </Link>
          {/* The hub applies no size budget, so it legitimately shows rows this
              result was capped before reaching. Said out loud rather than left
              for the reader to discover as a discrepancy. */}
          {efficacyLink.showsMore ? (
            <span className="font-mono text-[10px] text-(--brand-text-muted)/70">
              shows the full set
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
