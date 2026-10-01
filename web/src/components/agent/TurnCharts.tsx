'use client';

import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { ChevronDown } from 'lucide-react';
import { SETTING_ORDER } from '@/lib/agent/result-table';
import {
  heatShade,
  niceTicks,
  placeLabels,
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
        <table className="border-separate border-spacing-[3px] text-[12px]">
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
                <th scope="row" className="max-w-[20rem] pr-3 text-left text-[12px] font-medium text-(--brand-text)">
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
                          'min-w-[104px] rounded-[3px] border border-dashed border-(--brand-border)',
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
                        'min-w-[104px] rounded-[3px] px-1.5 py-2 text-center font-mono',
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

/** The plot's own units; the SVG scales to its box, text with it. */
const W = 760;
const H = 380;
const MARGIN = { left: 56, right: 24, top: 20, bottom: 52 };
/** Past this, names over every bubble crowd the plot; the tooltip still names each one. */
const LABEL_LIMIT = 8;
/** Width of one character of a 10.5-unit monospace label. */
const CHAR_WIDTH = 6.3;
/** A bubble with no size value, and the floor of every hover target (24px across). */
const FIXED_RADIUS = 8;
const HIT_RADIUS = 12;

/**
 * Setting colours, validated all-pairs (a scatter puts every pair side by side)
 * with the dataviz checker on white: worst CVD dE 9.2, normal-vision 20.2. The
 * aqua sits under 3:1, so the legend, the direct labels and the heatmap carry
 * identity too. Three is the most that validates all-pairs; a fourth setting
 * and beyond fold into Other.
 */
const GROUP_COLOURS = ['#2577a8', '#eb6834', '#1baf7a'];
const OTHER_COLOUR = '#898781';
const OTHER = 'Other';

/** The corner where both axes are better, as the arrow that points into it. */
function betterArrow(x: ChartEndpoint, y: ChartEndpoint): string {
  if (x.lowerIsBetter) return y.lowerIsBetter ? '↙' : '↖';
  return y.lowerIsBetter ? '↘' : '↗';
}

/**
 * Two endpoints against each other, a third as bubble area. Axes run the way
 * readers expect - zero at the origin, up is more - and a corner hint says
 * which way is better, rather than reversing an axis to make it so. Only exact
 * values have a position: a not-reached median or a censored "<1" is left out
 * and counted.
 */
function Bubble({ chart }: { chart: TurnChart }) {
  const [active, setActive] = useState<number | null>(null);
  if (!chart.bubble) {
    return <p className={NOTE_CLASSES}>Pick a second endpoint in the table to plot a bubble chart.</p>;
  }
  const { bubble } = chart;
  const xAxis = chart.endpoints.find((e) => e.key === bubble.x)!;
  const yAxis = chart.endpoints.find((e) => e.key === bubble.y)!;
  const sizeAxis = bubble.size ? chart.endpoints.find((e) => e.key === bubble.size)! : null;
  const exact = (value: ChartValue): value is Measured => isMeasured(value) && !value.censored;

  const points = chart.series.flatMap((s) => {
    const x = s.values[xAxis.key];
    const y = s.values[yAxis.key];
    return exact(x) && exact(y) ? [{ s, x: x.n, y: y.n }] : [];
  });
  const earlier = chart.series.filter(
    (s) => !points.some((p) => p.s === s) && (s.values[xAxis.key] === 'earlier' || s.values[yAxis.key] === 'earlier')
  ).length;
  const left = chart.series.length - points.length - earlier;

  if (points.length === 0) {
    return (
      <p className={NOTE_CLASSES}>
        No treatment reports both {xAxis.label} and {yAxis.label}.
      </p>
    );
  }

  // Area by the third endpoint when there is one, else by N.
  const sizeOf = (s: ChartSeries): number | null => {
    if (!sizeAxis) return s.patients;
    const value = s.values[sizeAxis.key];
    return isMeasured(value) ? value.n : null;
  };
  const maxSize = Math.max(0, ...points.map((p) => sizeOf(p.s) ?? 0));
  const radius = (value: number | null) =>
    value !== null && maxSize > 0 ? 6 + 16 * Math.sqrt(value / maxSize) : FIXED_RADIUS;
  const unsized = sizeAxis ? points.filter((p) => sizeOf(p.s) === null).length : 0;

  // Settings in their reading order, then any the order does not list.
  const groupNames = [...new Set(points.map((p) => p.s.group ?? 'Unclassified'))].sort((a, b) => {
    const rank = (g: string) => {
      const i = (SETTING_ORDER as readonly string[]).indexOf(g);
      return i === -1 ? SETTING_ORDER.length : i;
    };
    return rank(a) - rank(b);
  });
  const legendName = (group: string) => (groupNames.indexOf(group) < GROUP_COLOURS.length ? group : OTHER);
  const colourOf = (group: string) => GROUP_COLOURS[groupNames.indexOf(group)] ?? OTHER_COLOUR;
  const legend = [...new Set(groupNames.map(legendName))].map((name) => ({
    name,
    colour: name === OTHER ? OTHER_COLOUR : colourOf(name),
  }));

  const xTicks = niceTicks(Math.min(...points.map((p) => p.x)), Math.max(...points.map((p) => p.x)));
  const yTicks = niceTicks(Math.min(...points.map((p) => p.y)), Math.max(...points.map((p) => p.y)));
  const fraction = (value: number, ticks: number[]) => (value - ticks[0]) / (ticks[ticks.length - 1] - ticks[0]);
  const plotW = W - MARGIN.left - MARGIN.right;
  const plotH = H - MARGIN.top - MARGIN.bottom;
  const sx = (v: number) => MARGIN.left + fraction(v, xTicks) * plotW;
  const sy = (v: number) => MARGIN.top + plotH - fraction(v, yTicks) * plotH;

  // Largest first, so a small bubble is never hidden under a big one.
  const bubbles = points
    .map((p) => ({
      ...p,
      cx: sx(p.x),
      cy: sy(p.y),
      r: radius(sizeOf(p.s)),
      // A small filled bubble would read as a small value; hollow reads as none.
      hollow: sizeAxis !== null && sizeOf(p.s) === null,
      group: p.s.group ?? 'Unclassified',
    }))
    .sort((a, b) => b.r - a.r);
  const labels =
    bubbles.length <= LABEL_LIMIT
      ? placeLabels(
          bubbles.map((b) => ({
            x: b.cx,
            y: b.cy,
            r: b.r,
            width: b.s.label.length * CHAR_WIDTH,
          })),
          MARGIN.left,
          W - MARGIN.right
        )
      : null;

  const describe = (b: (typeof bubbles)[number]) =>
    [
      b.s.label,
      `${xAxis.label} ${b.s.text[xAxis.key]}`,
      `${yAxis.label} ${b.s.text[yAxis.key]}`,
      sizeAxis ? `${sizeAxis.label} ${b.s.text[sizeAxis.key]}` : null,
      b.s.patients !== null ? `N ${b.s.patients}` : null,
      b.s.group,
    ]
      .filter((part) => part !== null)
      .join(' · ');

  const arrow = betterArrow(xAxis, yAxis);
  const hint = {
    x: xAxis.lowerIsBetter ? MARGIN.left + 6 : W - MARGIN.right - 6,
    y: yAxis.lowerIsBetter ? H - MARGIN.bottom - 8 : MARGIN.top + 14,
    anchor: xAxis.lowerIsBetter ? 'start' : 'end',
  } as const;
  const shown = active === null ? null : bubbles[active];

  return (
    <figure className="m-0">
      {legend.length > 1 ? (
        <ul className="m-0 mb-2 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-[11.5px] text-(--brand-text)">
          {legend.map(({ name, colour }) => (
            <li key={name} className="inline-flex items-center gap-1.5">
              <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: colour }} />
              {name}
            </li>
          ))}
        </ul>
      ) : null}
      {/* Scrolls inside its own box below 560px, like the table, rather than
          scaling its labels down past reading size. */}
      <div className="overflow-x-auto">
        <div className="relative min-w-[560px]">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full font-mono"
            // A group, not an img: an img's children are presentational, which
            // would hide the focusable, named bubbles from a screen reader.
            role="group"
            aria-label={`${xAxis.label} against ${yAxis.label}, bubble area by ${sizeAxis ? sizeAxis.label : 'number of patients'}`}
          >
            {xTicks.map((tick) => (
              <g key={`x${tick}`}>
                <line
                  x1={sx(tick)}
                  x2={sx(tick)}
                  y1={MARGIN.top}
                  y2={H - MARGIN.bottom}
                  className="stroke-(--brand-border)"
                  strokeOpacity={0.6}
                />
                <text
                  x={sx(tick)}
                  y={H - MARGIN.bottom + 16}
                  textAnchor="middle"
                  fontSize={10}
                  className="fill-(--brand-text-muted)"
                >
                  {tick}
                </text>
              </g>
            ))}
            {yTicks.map((tick) => (
              <g key={`y${tick}`}>
                <line
                  x1={MARGIN.left}
                  x2={W - MARGIN.right}
                  y1={sy(tick)}
                  y2={sy(tick)}
                  className="stroke-(--brand-border)"
                  strokeOpacity={0.6}
                />
                <text
                  x={MARGIN.left - 8}
                  y={sy(tick) + 3}
                  textAnchor="end"
                  fontSize={10}
                  className="fill-(--brand-text-muted)"
                >
                  {tick}
                </text>
              </g>
            ))}
            <text x={hint.x} y={hint.y} textAnchor={hint.anchor} fontSize={10} className="fill-(--brand-text-muted)">
              {hint.anchor === 'end' ? `better ${arrow}` : `${arrow} better`}
            </text>
            {bubbles.map((b, index) => (
              <g
                key={index}
                tabIndex={0}
                role="img"
                aria-label={describe(b)}
                onMouseEnter={() => setActive(index)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
                className="cursor-default outline-none [&:focus-visible>circle.mark]:stroke-(--brand-primary)"
              >
                <circle cx={b.cx} cy={b.cy} r={Math.max(b.r, HIT_RADIUS)} fill="transparent" />
                <circle
                  cx={b.cx}
                  cy={b.cy}
                  r={b.r}
                  // A surface ring, not a border: it parts overlapping bubbles without adding ink.
                  className={cn('mark', !b.hollow && 'stroke-(--brand-surface)')}
                  strokeWidth={2}
                  stroke={b.hollow ? colourOf(b.group) : undefined}
                  fill={b.hollow ? 'var(--brand-surface)' : colourOf(b.group)}
                  fillOpacity={b.hollow ? 1 : 0.85}
                />
                {labels ? (
                  <text
                    x={labels[index].x}
                    y={labels[index].y}
                    textAnchor="middle"
                    fontSize={10.5}
                    className="pointer-events-none fill-(--brand-text)"
                  >
                    {b.s.label}
                  </text>
                ) : null}
              </g>
            ))}
            <text
              x={MARGIN.left + plotW / 2}
              y={H - 12}
              textAnchor="middle"
              fontSize={10.5}
              className="fill-(--brand-text)"
            >
              {xAxis.label}
            </text>
            <text
              transform={`translate(16 ${MARGIN.top + plotH / 2}) rotate(-90)`}
              textAnchor="middle"
              fontSize={10.5}
              className="fill-(--brand-text)"
            >
              {yAxis.label}
            </text>
          </svg>
          {shown ? (
            <div
              aria-hidden
              className={cn(
                'pointer-events-none absolute z-10 max-w-[18rem] -translate-x-1/2 -translate-y-full',
                'rounded-[3px] border border-(--brand-border) bg-(--brand-surface) px-2.5 py-1.5',
                'text-[11.5px] leading-snug text-(--brand-text) shadow-sm'
              )}
              style={{
                left: `${Math.min(85, Math.max(15, (shown.cx / W) * 100))}%`,
                top: `calc(${((shown.cy - shown.r) / H) * 100}% - 6px)`,
              }}
            >
              <p className="m-0 font-medium">{shown.s.label}</p>
              <p className="m-0 font-mono text-[10.5px] text-(--brand-text-muted)">
                {describe(shown).split(' · ').slice(1).join(' · ')}
              </p>
            </div>
          ) : null}
        </div>
      </div>
      <p className={NOTE_CLASSES}>
        {[
          `Bubble area = ${sizeAxis ? sizeAxis.label : 'N'}`,
          unsized > 0 ? `hollow = no ${sizeAxis!.label} reported (${unsized})` : null,
          left > 0
            ? `${left} ${left === 1 ? 'treatment' : 'treatments'} not shown: no exact ${xAxis.label} and ${yAxis.label} (missing, not reached or censored)`
            : null,
          earlier > 0
            ? `${earlier} ${earlier === 1 ? 'reports' : 'report'} a value only in an earlier readout, expand it in the table`
            : null,
        ]
          .filter((part) => part !== null)
          .join(' · ')}
      </p>
    </figure>
  );
}
