'use client';

import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { ChevronDown } from 'lucide-react';
import {
  heatShade,
  type ChartEndpoint,
  type ChartSeries,
  type ChartValue,
  type TurnChart,
} from '@/lib/agent/turn-chart';
import { cn } from '@/lib/utils';

/**
 * The table's values as Bar, Heatmap and Bubble views, under the table they
 * come from.
 *
 * Closed by default: an answer is read as a table first, and a chart nobody
 * opened should cost nothing, so the panel mounts only when opened. It adds no
 * controls of its own - filters, picks and "show more" are the table's, and
 * the charts follow them.
 */

type Measured = { n: number; censored?: true };

const isMeasured = (value: ChartValue): value is Measured => typeof value === 'object' && value !== null;

const TABS = [
  { id: 'bar', label: 'Bar' },
  { id: 'heatmap', label: 'Heatmap' },
  { id: 'bubble', label: 'Bubble' },
] as const;

type Tab = (typeof TABS)[number]['id'];

const TOGGLE_CLASSES = cn(
  'inline-flex h-7 items-center gap-1.5 rounded-full border border-(--brand-border) px-3',
  'bg-(--brand-surface) font-mono text-[10.5px] tracking-[0.05em] text-(--brand-primary)',
  'transition-colors hover:border-(--brand-primary)',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)'
);

const TAB_CLASSES = cn(
  '-mb-px border-b-2 border-transparent px-3 pt-1.5 pb-2 font-mono text-[10.5px] tracking-[0.06em]',
  'text-(--brand-text-muted) transition-colors hover:text-(--brand-primary)',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)'
);

const NOTE_CLASSES = 'mt-1.5 font-mono text-[10px] tracking-[0.04em] text-(--brand-text-muted)';

export function TurnCharts({ chart }: { chart: TurnChart }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('bar');
  const id = useId();
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const next =
      event.key === 'ArrowRight'
        ? index + 1
        : event.key === 'ArrowLeft'
          ? index - 1
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? TABS.length - 1
              : null;
    if (next === null) return;
    event.preventDefault();
    const target = (next + TABS.length) % TABS.length;
    setTab(TABS[target].id);
    tabs.current[target]?.focus();
  };

  return (
    <div className="pt-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-panel`}
        onClick={() => setOpen(!open)}
        className={TOGGLE_CLASSES}
      >
        Charts
        <ChevronDown aria-hidden className={cn('h-3 w-3 transition-transform', open && 'rotate-180')} />
      </button>
      {open ? (
        <div
          id={`${id}-panel`}
          className="mt-2 rounded-[3px] border border-(--brand-border) bg-(--brand-surface) px-4 pt-1 pb-4"
        >
          <div role="tablist" aria-label="Chart type" className="mb-3 flex gap-1 border-b border-(--brand-border)">
            {TABS.map((t, index) => (
              <button
                key={t.id}
                ref={(node) => {
                  tabs.current[index] = node;
                }}
                type="button"
                role="tab"
                id={`${id}-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`${id}-view`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => setTab(t.id)}
                onKeyDown={(event) => onKeyDown(event, index)}
                className={cn(TAB_CLASSES, tab === t.id && 'border-(--brand-primary) text-(--brand-primary)')}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`${id}-view`} aria-labelledby={`${id}-${tab}`}>
            {tab === 'bar' ? (
              <Bars chart={chart} />
            ) : tab === 'heatmap' ? (
              <Heatmap chart={chart} />
            ) : (
              <Bubble chart={chart} />
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** What a chart left out and why, so the numbers on screen still add up to the table's. */
function NotShown({ missing, earlier, label }: { missing: number; earlier: number; label: string }) {
  const parts = [
    missing > 0 ? `${missing} ${missing === 1 ? 'treatment' : 'treatments'} not shown: no ${label} reported` : null,
    earlier > 0
      ? `${earlier} ${earlier === 1 ? 'reports' : 'report'} ${label} only in an earlier readout, expand it in the table`
      : null,
  ].filter((part) => part !== null);
  return parts.length > 0 ? <p className={NOTE_CLASSES}>{parts.join(' · ')}</p> : null;
}

/** One small chart per endpoint: the units differ, so one shared axis would mean nothing. */
function Bars({ chart }: { chart: TurnChart }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,300px),1fr))] gap-x-6 gap-y-5">
      {chart.endpoints.map((endpoint) => (
        <EndpointBars key={endpoint.key} endpoint={endpoint} series={chart.series} />
      ))}
    </div>
  );
}

function EndpointBars({ endpoint, series }: { endpoint: ChartEndpoint; series: ChartSeries[] }) {
  const { key, label, lowerIsBetter } = endpoint;
  const valueOf = (s: ChartSeries) => (s.values[key] as Measured).n;
  const measured = series
    .filter((s) => isMeasured(s.values[key]))
    .sort((a, b) => (lowerIsBetter ? valueOf(a) - valueOf(b) : valueOf(b) - valueOf(a)));
  const reached = series.filter((s) => s.values[key] === 'NR');
  // Not reached outlasts every measured median, so it ranks first where higher is better.
  const ordered = lowerIsBetter ? [...measured, ...reached] : [...reached, ...measured];
  const max = Math.max(0, ...measured.map(valueOf));

  return (
    <figure className="m-0">
      <figcaption className="mb-1.5 flex justify-between gap-2 font-mono text-[10.5px] tracking-[0.04em]">
        <span className="text-(--brand-text)">{label}</span>
        <span className="text-(--brand-text-muted)">{lowerIsBetter ? 'lower is better' : 'higher is better'}</span>
      </figcaption>
      {ordered.length === 0 ? (
        <p className={NOTE_CLASSES}>No treatment reports {label}.</p>
      ) : (
        <ul className="m-0 list-none space-y-1 p-0">
          {ordered.map((s, index) => {
            const value = s.values[key];
            return (
              <li key={index} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-2">
                <span className="truncate text-right text-[11.5px] text-(--brand-text)" title={s.label}>
                  {s.label}
                </span>
                <span className="flex items-center gap-1.5 font-mono text-[11px] text-(--brand-text-muted)">
                  {isMeasured(value) ? (
                    // Square at the baseline, rounded at the data end.
                    <span
                      aria-hidden
                      className="h-3 shrink-0 rounded-r-[4px] bg-(--brand-primary)"
                      style={{ width: `${max > 0 ? Math.max(1, (value.n / max) * 85) : 1}%` }}
                    />
                  ) : null}
                  {s.text[key]}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      <NotShown
        missing={series.filter((s) => s.values[key] === null).length}
        earlier={series.filter((s) => s.values[key] === 'earlier').length}
        label={label}
      />
    </figure>
  );
}

/**
 * The table with colour: each column on its own scale, flipped where lower is
 * better, so darker always means better. The value is printed in every cell -
 * colour alone would say nothing to a reader who cannot see it.
 */
function Heatmap({ chart }: { chart: TurnChart }) {
  const ranges = new Map(
    chart.endpoints.map(({ key }) => {
      const values = chart.series.map((s) => s.values[key]).filter(isMeasured).map((v) => v.n);
      return [key, [Math.min(...values), Math.max(...values)] as const];
    })
  );
  const anyMeasured = chart.series.some((s) => chart.endpoints.some(({ key }) => isMeasured(s.values[key])));
  if (!anyMeasured) return <p className={NOTE_CLASSES}>No treatment reports the selected endpoints.</p>;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-[3px] text-[12px]">
          <thead>
            <tr>
              <td />
              {chart.endpoints.map((endpoint) => (
                <th
                  key={endpoint.key}
                  scope="col"
                  className={cn(
                    'px-1.5 py-1 text-center font-mono text-[10px] font-medium tracking-[0.04em]',
                    'whitespace-nowrap text-(--brand-text-muted)'
                  )}
                >
                  {endpoint.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {chart.series.map((s, index) => (
              <tr key={index}>
                <th scope="row" className="max-w-[16rem] pr-2 text-left text-[12px] font-medium text-(--brand-text)">
                  {s.label}
                </th>
                {chart.endpoints.map(({ key, lowerIsBetter }) => {
                  const value = s.values[key];
                  if (!isMeasured(value)) {
                    return (
                      <td
                        key={key}
                        title={value === 'earlier' ? 'Reported only in an earlier readout' : undefined}
                        className={cn(
                          'min-w-[76px] rounded-[3px] border border-dashed border-(--brand-border)',
                          'px-1.5 py-2 text-center font-mono text-(--brand-text-muted)'
                        )}
                      >
                        {s.text[key]}
                      </td>
                    );
                  }
                  const [low, high] = ranges.get(key)!;
                  const t = high === low ? 0.5 : (value.n - low) / (high - low);
                  const shade = heatShade(lowerIsBetter ? 1 - t : t);
                  return (
                    <td
                      key={key}
                      style={{ background: shade.background }}
                      className={cn(
                        'min-w-[76px] rounded-[3px] px-1.5 py-2 text-center font-mono',
                        shade.dark ? 'text-white' : 'text-(--brand-text)'
                      )}
                    >
                      {s.text[key]}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={cn(NOTE_CLASSES, 'flex flex-wrap items-center gap-2')}>
        <span>worse</span>
        <span
          aria-hidden
          className="h-2 w-28 rounded-[2px]"
          style={{
            background: `linear-gradient(90deg, ${heatShade(0).background}, ${heatShade(0.49).background} 50%, ${heatShade(0.5).background} 50%, ${heatShade(1).background})`,
          }}
        />
        <span>better · each column on its own scale, lower-is-better columns flipped · NR and empty cells uncoloured</span>
      </p>
    </>
  );
}

/** Replaced in the next task. */
function Bubble({ chart }: { chart: TurnChart }) {
  return chart.bubble ? null : (
    <p className={NOTE_CLASSES}>Pick a second endpoint in the table to plot a bubble chart.</p>
  );
}
