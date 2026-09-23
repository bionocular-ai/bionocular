'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { ArrowUpRight, Check, ChevronDown } from 'lucide-react';
import { ABSENT, filterRows, toFacets, toSections } from '@/lib/agent/result-table';
import type { Facet, ResultSummary, ResultTable } from '@/lib/agent/result-table';
import type { EfficacyLink } from '@/lib/agent/efficacy-link';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { NCT_ID_PATTERN, trialRoute } from '@/lib/constants';
import { cn } from '@/lib/utils';

/** Anchor treatment matched to the one `createMarkdownComponents` gives an in-app link. */
const NCT_LINK_CLASSES = cn(
  'font-mono text-[12px] font-medium text-(--brand-primary)',
  'border-b border-(--brand-border) pb-px no-underline',
  'hover:border-(--brand-primary)'
);

/**
 * The two columns a reader scans rather than reads: is it open, and who is
 * paying for it. Both are closed sets of a handful of values, which is what
 * makes them worth shaping - a pill on a free-text column would only be a box
 * around a sentence.
 *
 * Tone is an emphasis, never the message: every pill states its value in
 * words, so the colour is redundant to a reader who cannot see it.
 */
const PILL_TONES: Record<string, string> = {
  recruiting: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  'not yet recruiting': 'bg-emerald-50 text-emerald-800 border-emerald-200',
  'enrolling by invitation': 'bg-emerald-50 text-emerald-800 border-emerald-200',
  'active, not recruiting': 'bg-amber-50 text-amber-800 border-amber-200',
  industry: 'bg-violet-50 text-violet-800 border-violet-200',
};

const PILL_COLUMNS = ['overall_status', 'sponsor_type'];

function Pill({ value }: { value: string }) {
  return (
    <span
      className={cn(
        'inline-block rounded-[4px] border px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap',
        PILL_TONES[value.toLowerCase()] ??
          'border-(--brand-border) bg-(--brand-bg) text-(--brand-text-muted)'
      )}
    >
      {value}
    </span>
  );
}

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
 * Narrowing the rows already on screen - no second query, no new turn.
 *
 * A landscape answer is a set the reader works through, not a number: having
 * asked for every active Phase 3 trial, the next thing they do is look at the
 * industry ones, or the adjuvant ones, or the one drug they came for. Asking
 * the agent again costs a round trip and re-derives a set it has already sent.
 *
 * One menu per column rather than a row of chips: three chip rows and the
 * search wrapped to two lines in the chat column, while a menu button stays
 * one line and reads as a sentence ("Sponsor Type: Industry"). One value per
 * column keeps the count beside each option unambiguous - it is how many rows
 * that choice would leave, given every other filter already set.
 */
function FilterBar({
  facets,
  rows,
  selected,
  onSelect,
  onClear,
  query,
  onQuery,
  shown,
}: {
  facets: Facet[];
  rows: string[][];
  selected: Record<number, string>;
  onSelect: (index: number, value: string) => void;
  onClear: () => void;
  query: string;
  onQuery: (query: string) => void;
  shown: number;
}) {
  const optionCount = (facet: Facet, value: string) => {
    const others = { ...selected };
    delete others[facet.index];
    return filterRows(rows, others, query).filter(
      (row) => value === '' || row[facet.index] === value
    ).length;
  };

  return (
    <div className="flex flex-wrap items-center gap-2 pb-2.5">
      {facets.map((facet) => {
        const value = selected[facet.index] ?? '';
        // An absent value is a group like any other - the trials with no
        // curated regimen - but "—" in a menu reads as a broken label.
        const label = (option: string) =>
          option === '' ? 'All' : option === ABSENT ? 'None' : option;
        return (
          <DropdownMenu key={facet.index}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className={cn(
                  'inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12px]',
                  'whitespace-nowrap transition-colors focus-visible:outline-none',
                  'focus-visible:ring-2 focus-visible:ring-(--brand-primary)',
                  'text-(--brand-text-muted)',
                  value
                    ? 'border-(--brand-primary)/60 bg-(--brand-accent-light)/60'
                    : 'border-(--brand-border) bg-(--brand-surface) hover:border-(--brand-primary)'
                )}
              >
                {facet.label}:
                <span className="font-semibold text-(--brand-text)">{label(value)}</span>
                <ChevronDown className="h-3 w-3" aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              className="min-w-[14rem] rounded-xl border-(--brand-border) p-1.5"
            >
              <DropdownMenuRadioGroup
                value={value}
                onValueChange={(next) => onSelect(facet.index, next)}
              >
                {/* "All" closes the list: the groups are what a reader came
                    to pick from, and the total is the way back out. */}
                {[...facet.values, ''].map((option) => (
                  // The primitive rather than the shared `DropdownMenuRadioItem`,
                  // which draws a dot only on the checked row. Here every row
                  // shows its state - a check or an empty ring - so the choice
                  // reads as a choice before anything is picked.
                  <DropdownMenuPrimitive.RadioItem
                    key={option}
                    value={option}
                    className={cn(
                      'group flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2',
                      'text-[13px] text-(--brand-text) outline-none select-none',
                      'focus:bg-(--brand-bg) data-[state=checked]:bg-(--brand-accent-light)/70',
                      'data-[state=checked]:font-semibold'
                    )}
                  >
                    <Check
                      aria-hidden
                      className="hidden h-4 w-4 shrink-0 text-emerald-600 group-data-[state=checked]:block"
                    />
                    <span
                      aria-hidden
                      className={cn(
                        'h-3.5 w-3.5 shrink-0 rounded-full border-[1.5px] border-(--brand-text-muted)/60',
                        'm-px group-data-[state=checked]:hidden'
                      )}
                    />
                    <span className="flex-1">{label(option)}</span>
                    <span
                      className={cn(
                        'min-w-[2.25rem] rounded-full px-2 py-0.5 text-center text-[11px] font-medium',
                        'text-(--brand-text)',
                        option === '' || option === value
                          ? 'bg-(--brand-accent)/30'
                          : 'bg-(--brand-text-muted)/15'
                      )}
                    >
                      {optionCount(facet, option)}
                    </span>
                  </DropdownMenuPrimitive.RadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
      <input
        type="search"
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        placeholder="drug, sponsor, NCT id…"
        aria-label="Search rows"
        className={cn(
          'h-8 min-w-[18ch] flex-1 rounded-full border border-(--brand-border)',
          'bg-(--brand-surface) px-3.5 text-[12px] text-(--brand-text)',
          'placeholder:text-(--brand-text-muted) focus-visible:border-(--brand-primary)',
          'focus-visible:outline-none'
        )}
      />
      {Object.keys(selected).length > 0 ? (
        <button
          type="button"
          onClick={onClear}
          className={cn(
            'font-mono text-[11px] font-medium text-(--brand-primary) underline',
            'underline-offset-[3px] focus-visible:outline-none focus-visible:ring-2',
            'focus-visible:ring-(--brand-primary)'
          )}
        >
          Clear
        </button>
      ) : null}
      <span
        className={cn(
          'shrink-0 font-mono text-[10px] tracking-[0.05em] whitespace-nowrap',
          'text-(--brand-text-muted)'
        )}
      >
        {shown} of {rows.length}
      </span>
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
  const [selected, setSelected] = useState<Record<number, string>>({});
  const [query, setQuery] = useState('');

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
  // `follow_up_only` qualifies the status rather than standing beside it: it
  // says an "active, not recruiting" trial is past its primary completion and
  // has stopped being an option. Alone in a column it read "yes" or an em
  // dash, a whole column of width for one word about five rows.
  const statusIndex = indexOf('overall_status');
  const followUpIndex = statusIndex === -1 ? -1 : indexOf('follow_up_only');

  const hidden = useMemo(
    () =>
      new Set(
        [settingIndex, modalityIndex, sponsorClassIndex, basketIndex, followUpIndex].filter(
          (index) => index !== -1
        )
      ),
    [settingIndex, modalityIndex, sponsorClassIndex, basketIndex, followUpIndex]
  );
  const columns = table.columns.filter((_, index) => !hidden.has(index));
  const facets = useMemo(() => toFacets(table), [table]);
  const rows = useMemo(
    () => filterRows(table.rows, selected, query),
    [table.rows, selected, query]
  );
  const sections = useMemo(
    () => toSections(rows, settingIndex, basketIndex),
    [rows, settingIndex, basketIndex]
  );

  const select = useCallback((index: number, value: string) => {
    setSelected((previous) => {
      const next = { ...previous };
      // No entry rather than an empty one, so "All" leaves nothing to match on.
      if (value) next[index] = value;
      else delete next[index];
      return next;
    });
  }, []);

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
  }, [measure, rows]);

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
      {facets.length > 0 ? (
        <FilterBar
          facets={facets}
          rows={table.rows}
          selected={selected}
          onSelect={select}
          onClear={() => setSelected({})}
          query={query}
          onQuery={setQuery}
          shown={rows.length}
        />
      ) : null}
      <div
        ref={scroller}
        onScroll={measure}
        className="overflow-x-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface)"
      >
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    'border-b border-(--brand-border) bg-(--brand-accent-light)',
                    'px-3 py-2 text-left font-mono font-medium whitespace-nowrap',
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
                      'px-3 py-1.5 text-left font-mono text-[10px] font-medium',
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
                          'min-w-[11ch] max-w-[34ch] px-3 py-2.5 align-top',
                          'text-(--brand-text-muted)',
                          // The lead column carries the longest values and is
                          // the one the question was about, so it gets the
                          // wider floor rather than wrapping a three-drug
                          // regimen over three lines.
                          cellIndex === treatmentIndex &&
                            'min-w-[30ch] max-w-[40ch] font-medium text-(--brand-text)'
                        )}
                      >
                        {table.columns[cellIndex].key === 'nct_id' && NCT_ID_PATTERN.test(cell) ? (
                          <Link href={trialRoute(cell, cancerType)} className={NCT_LINK_CLASSES}>
                            {cell}
                          </Link>
                        ) : PILL_COLUMNS.includes(table.columns[cellIndex].key) &&
                          cell !== ABSENT ? (
                          <Pill value={cell} />
                        ) : (
                          cell
                        )}
                        {/* Under the status it qualifies, on the rows that
                            have it, rather than as a column of em dashes. */}
                        {cellIndex === statusIndex &&
                        followUpIndex !== -1 &&
                        row[followUpIndex] !== ABSENT ? (
                          <span className="mt-1 block font-mono text-[10px] text-(--brand-text-muted)">
                            follow-up only
                          </span>
                        ) : null}
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
          {/* A header row over nothing reads as a failed query rather than as
              a filter the reader set a moment ago. */}
          {rows.length === 0 ? (
            <tbody>
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-4 text-center text-(--brand-text-muted)"
                >
                  No rows match these filters.
                </td>
              </tr>
            </tbody>
          ) : null}
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
