'use client';

import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { ChevronDown } from 'lucide-react';
import { SETTING_ORDER } from '@/lib/agent/result-table';
import {
  barRows,
  gaps,
  heatShade,
  niceTicks,
  placeLabels,
  unitOf,
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
          {/* All three views share one grid cell and the inactive ones are only
              invisible, so the card keeps the tallest view's height instead of
              jumping on every tab change. `invisible` also takes them out of the
              tab order and the accessibility tree. */}
          <div role="tabpanel" id={`${id}-view`} aria-labelledby={`${id}-${tab}`} className="grid">
            {TABS.map((t) => (
              <div key={t.id} className={cn('col-start-1 row-start-1 min-w-0', tab !== t.id && 'invisible')}>
                {t.id === 'bar' ? (
                  <Bars chart={chart} />
                ) : t.id === 'heatmap' ? (
                  <Heatmap chart={chart} />
                ) : (
                  <Bubble chart={chart} />
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

const SEGMENT_CLASSES = cn(
  'h-7 rounded-full px-3 font-mono text-[10.5px] tracking-[0.04em] whitespace-nowrap transition-colors',
  'text-(--brand-text-muted) hover:text-(--brand-primary)',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)'
);

/**
 * A ranking on one endpoint at a time, full width - precise comparison is the
 * job the heatmap and the bubble do not do. The endpoints to choose from are
 * the ones picked in the table, so the switch adds no filter of its own. Every
 * treatment the table draws appears: ranked when it has a value, listed under
 * the ranking when it does not.
 */
function Bars({ chart }: { chart: TurnChart }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const endpoint = chart.endpoints.find((e) => e.key === chosen) ?? chart.endpoints[0];
  if (chart.series.length === 0) return <p className={NOTE_CLASSES}>No treatments match the table&apos;s filters.</p>;

  const { ranked, absent } = barRows(chart.series, endpoint);
  const unit = unitOf(endpoint.key, endpoint.family);
  const measured = ranked.flatMap((s) => {
    const value = s.values[endpoint.key];
    return isMeasured(value) ? [value.n] : [];
  });
  const ticks = niceTicks(Math.min(0, ...measured), Math.max(0, ...measured));
  const low = ticks[0];
  const span = ticks[ticks.length - 1] - low;
  const at = (n: number) => ((n - low) / span) * 100;

  return (
    <figure className="m-0">
      {chart.endpoints.length > 1 ? (
        <div
          role="group"
          aria-label="Endpoint"
          className="mb-3 inline-flex flex-wrap gap-0.5 rounded-full border border-(--brand-border) p-0.5"
        >
          {chart.endpoints.map((e) => (
            <button
              key={e.key}
              type="button"
              aria-pressed={e.key === endpoint.key}
              onClick={() => setChosen(e.key)}
              className={cn(
                SEGMENT_CLASSES,
                e.key === endpoint.key && 'bg-(--brand-accent-light) text-(--brand-primary)'
              )}
            >
              {e.label}
            </button>
          ))}
        </div>
      ) : null}
      <figcaption className="mb-2 flex justify-between gap-3 font-mono text-[10.5px] tracking-[0.04em]">
        <span className="text-(--brand-text)">
          {endpoint.label}
          {unit === 'months' ? ' (months)' : ''}
        </span>
        <span className="text-(--brand-text-muted)">
          {endpoint.lowerIsBetter ? 'lower is better, best first' : 'higher is better, best first'}
        </span>
      </figcaption>
      {/* Names size the first column - up to 22rem, then they wrap rather
          than truncate; the bars keep at least 9rem on a phone. The right
          padding is room for the value at a bar's tip. */}
      <div className="grid grid-cols-[minmax(0,auto)_minmax(9rem,1fr)] pr-14">
        {ranked.length > 0 ? (
          <div
            aria-hidden
            className="pointer-events-none relative col-start-2"
            style={{ gridRow: `1 / span ${ranked.length}` }}
          >
            {ticks.map((tick) => (
              <span
                key={tick}
                className="absolute inset-y-0 w-px bg-(--brand-border) opacity-60"
                style={{ left: `${at(tick)}%` }}
              />
            ))}
          </div>
        ) : null}
        {ranked.map((s, index) => {
          const value = s.values[endpoint.key];
          return (
            <div key={index} className="group contents">
              <span
                className={cn(
                  'col-start-1 max-w-[22rem] py-1.5 pr-3 text-right text-[12px] leading-snug text-(--brand-text)',
                  'group-hover:bg-(--brand-bg)'
                )}
                style={{ gridRow: index + 1 }}
              >
                {s.label}
              </span>
              <span
                className="relative col-start-2 flex items-center group-hover:bg-(--brand-bg)/60"
                style={{ gridRow: index + 1 }}
              >
                {isMeasured(value) ? (
                  // Square at the baseline, rounded at the data end.
                  <span
                    className="h-3.5 rounded-r-[4px] bg-(--brand-primary)"
                    style={{ width: `${Math.max(0.5, at(value.n) - at(Math.max(low, 0)))}%`, marginLeft: `${at(Math.max(low, 0))}%` }}
                  />
                ) : (
                  // Not reached has no length: an open, dashed track to the
                  // end of the scale says "beyond what was followed".
                  <span
                    title="Median not reached"
                    className="h-3.5 w-full rounded-r-[4px] border border-dashed border-(--brand-primary)/50"
                  />
                )}
                <span className="absolute left-full ml-1 bg-(--brand-surface) px-1 font-mono text-[11px] whitespace-nowrap text-(--brand-text-muted)"
                  style={isMeasured(value) ? { left: `${at(value.n)}%` } : undefined}
                >
                  {value === 'NR' ? 'NR' : s.text[endpoint.key]}
                </span>
              </span>
            </div>
          );
        })}
        {ranked.length > 0 ? (
          <div
            aria-hidden
            className="relative col-start-2 mt-1 h-4 border-t border-(--brand-border)"
            style={{ gridRow: ranked.length + 1 }}
          >
            {ticks.map((tick) => (
              <span
                key={tick}
                className="absolute top-1 -translate-x-1/2 font-mono text-[10px] text-(--brand-text-muted)"
                style={{ left: `${at(tick)}%` }}
              >
                {tick}
                {unit === '%' ? '%' : ''}
              </span>
            ))}
          </div>
        ) : (
          <p className={cn(NOTE_CLASSES, 'col-span-2')}>No treatment reports {endpoint.label}.</p>
        )}
        {absent.length > 0 ? (
          <>
            <p
              className="col-span-2 mt-5 mb-1 border-t border-(--brand-border) pt-2 font-mono text-[10px] tracking-[0.04em] text-(--brand-text-muted)"
            >
              No {endpoint.label} ({absent.length})
            </p>
            {absent.map(({ series: s, earlier }, index) => (
              <div key={index} className="contents">
                <span className="col-start-1 max-w-[22rem] py-1 pr-3 text-right text-[12px] leading-snug text-(--brand-text-muted)">
                  {s.label}
                </span>
                <span className="col-start-2 self-center font-mono text-[10.5px] text-(--brand-text-muted)">
                  {earlier ? 'only in an earlier readout, expand it in the table' : 'not reported'}
                </span>
              </div>
            ))}
          </>
        ) : null}
      </div>
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
                    'w-28 px-1.5 py-1 text-center align-bottom font-mono text-[10px] font-medium tracking-[0.04em]',
                    'text-balance text-(--brand-text-muted)'
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
                          'w-28 rounded-[3px] border border-dashed border-(--brand-border)',
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
                        'w-28 rounded-[3px] px-1.5 py-2 text-center font-mono',
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
// The top margin holds a label above the top-most bubble, which `niceTicks` can put on the top tick.
const MARGIN = { left: 56, right: 24, top: 44, bottom: 52 };
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
  const hollow = sizeAxis ? gaps(points.map((p) => p.s), sizeAxis.key) : null;

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
          W - MARGIN.right,
          0
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
  /** Roughly the tooltip's height in plot units; nearer the top than this, it opens downward. */
  const tooltipBelow = shown !== null && shown.cy - shown.r < 90;

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
                'pointer-events-none absolute z-10 max-w-[18rem] -translate-x-1/2',
              // Above the bubble, or below it near the top, where the scroll box would clip it.
              !tooltipBelow && '-translate-y-full',
                'rounded-[3px] border border-(--brand-border) bg-(--brand-surface) px-2.5 py-1.5',
                'text-[11.5px] leading-snug text-(--brand-text) shadow-sm'
              )}
              style={{
                left: `${Math.min(85, Math.max(15, (shown.cx / W) * 100))}%`,
                top: tooltipBelow
                ? `calc(${((shown.cy + shown.r) / H) * 100}% + 6px)`
                : `calc(${((shown.cy - shown.r) / H) * 100}% - 6px)`,
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
          hollow && hollow.notReached + hollow.earlier + hollow.missing > 0
            ? `hollow = no exact ${sizeAxis!.label}: ${[
                hollow.missing > 0 ? `${hollow.missing} not reported` : null,
                hollow.earlier > 0 ? `${hollow.earlier} only in an earlier readout` : null,
                hollow.notReached > 0 ? `${hollow.notReached} not reached` : null,
              ]
                .filter((part) => part !== null)
                .join(', ')}`
            : null,
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
