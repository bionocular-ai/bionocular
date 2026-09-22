'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import { ABSENT, toSections } from '@/lib/agent/result-table';
import type { ResultSummary, ResultTable } from '@/lib/agent/result-table';
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
 * The counts above the table: scope first, then the sponsor split.
 *
 * Each part is dropped when it has nothing to say - no baskets set aside, no
 * sponsor class in the projection - so the strip never pads itself with
 * zeroes. `uncurated` is `trials - curated` because every row either carried a
 * curated regimen or did not; the sponsor split is counted on both sides
 * instead, since a row can belong to neither.
 */
function SummaryStrip({ summary }: { summary: ResultSummary }) {
  const uncurated = summary.trials - summary.curated;
  const scope = [
    `${summary.trials} ${summary.trials === 1 ? 'trial' : 'trials'}`,
    `${summary.curated} curated`,
    ...(uncurated > 0 ? [`${uncurated} not yet curated`] : []),
    ...(summary.setAside > 0 ? [`${summary.setAside} set aside`] : []),
  ];
  const sponsors =
    summary.industry + summary.nonIndustry > 0
      ? [`Industry ${summary.industry}`, `Non-industry ${summary.nonIndustry}`]
      : [];

  return (
    <div
      className={cn(
        'flex flex-wrap items-baseline gap-x-3 gap-y-1 pb-1.5',
        'font-mono text-[10px] tracking-[0.05em] text-(--brand-text-muted)'
      )}
    >
      <span className="text-(--brand-primary)">{scope.join(' · ')}</span>
      {sponsors.length > 0 ? <span>{sponsors.join(' · ')}</span> : null}
    </div>
  );
}

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
 * A landscape turn is read by group, not row by row, so rows carrying a
 * `setting` are drawn in sections under it and the column itself goes: the
 * section heading already says what it said, on one line instead of every
 * line. `modality` moves under the regimen for the same reason - it qualifies
 * the treatment rather than standing beside it. Any other table renders flat,
 * exactly as before.
 *
 * Dropping the trial-name column (see `turn-table.ts`) leans on `nct_id`
 * being the row's one navigable identifier, so that cell is linked here
 * rather than left as the plain text every other cell renders as. It sits
 * second, behind the treatment: the question is about a drug, and the NCT is
 * how a reader follows one up afterwards. Any cell
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

  const indexOf = (key: string) => table.columns.findIndex((column) => column.key === key);
  const settingIndex = indexOf('setting');
  const basketIndex = indexOf('is_basket');
  const treatmentIndex = indexOf('treatment_name');
  // Only folded when there is a regimen to fold it under. On a table with a
  // modality and no treatment name it is the treatment column there is.
  const modalityIndex = treatmentIndex === -1 ? -1 : indexOf('modality');
  // `sponsor_type` is `lead_sponsor_class` collapsed to the only distinction a
  // landscape draws, so the two rendered side by side say INDUSTRY twice.
  const sponsorClassIndex = indexOf('sponsor_type') === -1 ? -1 : indexOf('lead_sponsor_class');

  const hidden = useMemo(
    () =>
      new Set(
        [settingIndex, modalityIndex, sponsorClassIndex, basketIndex].filter(
          (index) => index !== -1
        )
      ),
    [settingIndex, modalityIndex, sponsorClassIndex, basketIndex]
  );
  const columns = table.columns.filter((_, index) => !hidden.has(index));
  const sections = useMemo(
    () => toSections(table.rows, settingIndex, basketIndex),
    [table.rows, settingIndex, basketIndex]
  );

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
      {table.summary ? <SummaryStrip summary={table.summary} /> : null}
      <div
        ref={scroller}
        onScroll={measure}
        className="overflow-x-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface)"
      >
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr>
              {columns.map((column) => (
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
          {sections.map((section) => (
            // One tbody per section so the heading row belongs to the rows it
            // introduces rather than floating among them.
            <tbody key={section.label ?? 'all'}>
              {section.label ? (
                <tr>
                  <th
                    scope="colgroup"
                    colSpan={columns.length}
                    className={cn(
                      'border-b border-(--brand-border) bg-(--brand-accent-light)/40',
                      'px-2 py-1 text-left font-mono text-[10px] font-medium',
                      'tracking-[0.05em] whitespace-nowrap text-(--brand-primary)'
                    )}
                  >
                    {section.label}{' '}
                    <span className="text-(--brand-text-muted)">({section.rows.length})</span>
                  </th>
                </tr>
              ) : null}
              {section.rows.map((row, rowIndex) => (
                // Keyed by position, not by the first cell. That cell used to be
                // a unique `id`; `orderColumns` now leads with the treatment
                // and puts `nct_id` second, and
                // `trial_outcomes` is one row per treatment arm - two arms of one
                // trial share an nct_id by design, which React reads as duplicate
                // keys and is free to drop rows over. Rows are positional and the
                // whole table re-renders per turn, so the index is the identity.
                <tr key={rowIndex} className="border-b border-(--brand-border)/50 last:border-b-0">
                  {row.map((cell, cellIndex) =>
                    hidden.has(cellIndex) ? null : (
                      <td
                        key={table.columns[cellIndex].key}
                        // A floor as well as a ceiling. The table lays out
                        // automatically and is already wider than its box, so
                        // a column of short repeated values ("Stage II; Stage
                        // III; Stage IV") could be squeezed to 47px and wrap
                        // to seven lines, making the whole row that tall.
                        className={cn(
                          'min-w-[11ch] max-w-[34ch] px-2 py-1 align-top',
                          'text-(--brand-text-muted)',
                          // The lead column carries the longest values and is
                          // the one the question was about, so it gets the
                          // wider floor rather than wrapping a three-drug
                          // regimen over three lines.
                          cellIndex === treatmentIndex && 'min-w-[24ch]'
                        )}
                      >
                        {table.columns[cellIndex].key === 'nct_id' && NCT_ID_PATTERN.test(cell) ? (
                          <Link href={trialRoute(cell, cancerType)} className={NCT_LINK_CLASSES}>
                            {cell}
                          </Link>
                        ) : (
                          cell
                        )}
                        {/* An uncurated row has no modality, and the cell above
                            already ends in `· registry` to say why. A line
                            holding only an em dash adds height and no fact. */}
                        {cellIndex === treatmentIndex &&
                        modalityIndex !== -1 &&
                        row[modalityIndex] !== ABSENT ? (
                          // Set apart by size, not by fading the colour: at
                          // 70% opacity this measured 3.06:1 on the surface,
                          // under the 4.5:1 floor for text this size.
                          <span className="block text-[10px] text-(--brand-text-muted)">
                            {row[modalityIndex]}
                          </span>
                        ) : null}
                      </td>
                    )
                  )}
                </tr>
              ))}
            </tbody>
          ))}
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
            <span className="font-mono text-[10px] text-(--brand-text-muted)">
              shows the full set
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
