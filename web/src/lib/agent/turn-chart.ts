/**
 * A turn's outcomes table, as the values its charts plot.
 *
 * Read back from the cells the table is drawing rather than from the tool
 * rows: the charts follow every filter, pick and "show more" the reader sets on
 * the table, and the drawn cells are the one place all of those have already
 * been applied. `formatRowCell` writes exactly four shapes - a number, `<n`,
 * `NR` and `ABSENT` - so reading them back is exact; the test builds its rows
 * with `formatRowCell` so a new shape fails there first.
 *
 * One point is one readout. A treatment whose newest readout leaves an endpoint
 * empty is not topped up from an older one: a bubble would pair a 2024 x with
 * a 2022 y. It is marked 'earlier' so the chart can say where the value is.
 */

import { ABSENT, NOT_REACHED, type ResultTable } from './result-table';

/** 'earlier': empty on this row, reported by one of its earlier readouts. */
export type ChartValue = { n: number; censored?: true } | 'NR' | 'earlier' | null;

export interface ChartEndpoint {
  key: string;
  /** The table column's header, so the chart and the table read the same. */
  label: string;
  family: 'efficacy' | 'safety';
  lowerIsBetter: boolean;
}

export interface ChartSeries {
  label: string;
  values: Record<string, ChartValue>;
  /** The table's own cell text, so "11.0" and "<1" read as they do in the table. */
  text: Record<string, string>;
  patients: number | null;
  /** The row's setting - its line of therapy - which colours its bubble. */
  group: string | null;
}

export interface TurnChart {
  endpoints: ChartEndpoint[];
  series: ChartSeries[];
  /** `size` is a third endpoint drawn as bubble area; null draws N instead. */
  bubble: { x: string; y: string; size: string | null } | null;
}

const NUMBER = /^-?\d+(\.\d+)?$/;

export function parseCell(cell: string): { n: number; censored?: true } | 'NR' | null {
  if (cell === NOT_REACHED) return 'NR';
  if (cell.startsWith('<') && NUMBER.test(cell.slice(1))) return { n: Number(cell.slice(1)), censored: true };
  return NUMBER.test(cell) ? { n: Number(cell) } : null;
}

/**
 * Fewer adverse events, a smaller hazard ratio and a faster response are
 * better. p-values and CIs never reach here: `isQualifier` keeps them out of
 * the parameters.
 */
function lowerIsBetter(key: string, family: ChartEndpoint['family']): boolean {
  return family === 'safety' || key.startsWith('hr_') || key === 'ttr';
}

export function toTurnChart(
  table: ResultTable,
  rows: string[][],
  picked: string[],
  earlier: (row: string[]) => string[][],
): TurnChart | null {
  const parameters = table.parameters;
  if (!parameters) return null;
  const indexOf = (key: string) => table.columns.findIndex((column) => column.key === key);

  const endpoints = picked.flatMap((key): ChartEndpoint[] => {
    const parameter = parameters.find((p) => p.key === key);
    const index = indexOf(key);
    if (!parameter || index === -1) return [];
    return [{
      key,
      label: table.columns[index].label,
      family: parameter.family,
      lowerIsBetter: lowerIsBetter(key, parameter.family),
    }];
  });
  if (endpoints.length === 0) return null;

  const treatmentIndex = indexOf('treatment_name');
  const nctIndex = indexOf('nct_id');
  const patientsIndex = indexOf('num_patients');
  const settingIndex = indexOf('setting');
  const names = rows.map((row) => (treatmentIndex === -1 ? ABSENT : row[treatmentIndex]));

  const series = rows.map((row, rowIndex): ChartSeries => {
    const name = names[rowIndex];
    const shared = names.filter((other) => other === name).length > 1;
    const values: Record<string, ChartValue> = {};
    const text: Record<string, string> = {};
    for (const { key } of endpoints) {
      const index = indexOf(key);
      text[key] = row[index];
      values[key] =
        parseCell(row[index]) ??
        (earlier(row).some((readout) => readout[index] !== ABSENT) ? 'earlier' : null);
    }
    const patients = patientsIndex === -1 ? null : parseCell(row[patientsIndex]);
    const setting = settingIndex === -1 ? ABSENT : row[settingIndex];
    return {
      label: shared && nctIndex !== -1 ? `${name} · ${row[nctIndex]}` : name,
      values,
      text,
      patients: patients !== null && patients !== 'NR' && !patients.censored ? patients.n : null,
      group: setting === ABSENT ? null : setting,
    };
  });

  // The NCT does not separate two arms of one trial under one name (E1609's
  // ipilimumab 3 and 10 mg/kg); they are numbered in table order instead.
  const labels = series.map((s) => s.label);
  const seen = new Map<string, number>();
  for (const s of series) {
    if (labels.filter((label) => label === s.label).length < 2) continue;
    const ordinal = (seen.get(s.label) ?? 0) + 1;
    seen.set(s.label, ordinal);
    s.label = `${s.label} (${ordinal})`;
  }

  const efficacy = endpoints.find((e) => e.family === 'efficacy');
  const safety = endpoints.find((e) => e.family === 'safety');
  const axes =
    efficacy && safety
      ? { x: efficacy.key, y: safety.key }
      : endpoints.length >= 2
        ? { x: endpoints[0].key, y: endpoints[1].key }
        : null;
  const bubble = axes && {
    ...axes,
    size: endpoints.find((e) => e.key !== axes.x && e.key !== axes.y)?.key ?? null,
  };

  return { endpoints, series, bubble };
}

/**
 * Why treatments have no exact value for `key`, counted, so a chart can say
 * which: a not-reached median is the best result there is, and a value in an
 * earlier readout exists - neither is "not reported".
 */
export function gaps(series: ChartSeries[], key: string): { notReached: number; earlier: number; missing: number } {
  const count = (value: ChartValue) => series.filter((s) => s.values[key] === value).length;
  return { notReached: count('NR'), earlier: count('earlier'), missing: count(null) };
}

/**
 * Axis ticks a reader can count in: steps of 1, 2 or 5 x 10^k, from zero (or
 * below it when the data is), ending at the first tick at or past `max`.
 */
export function niceTicks(min: number, max: number, count = 6): number[] {
  const low = Math.min(0, min);
  if (max <= low) return [low, low + 1];
  const raw = (max - low) / (count - 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= raw)!;
  const start = Math.floor(low / step) * step;
  const ticks: number[] = [];
  for (let i = 0; ; i++) {
    const tick = Number((start + i * step).toFixed(12));
    ticks.push(tick);
    if (tick >= max) return ticks;
  }
}

export interface LabelBox {
  /** The bubble's centre and radius, in the plot's own units. */
  x: number;
  y: number;
  r: number;
  /** The label's estimated width in the same units. */
  width: number;
}

/** Cap height of a 10.5-unit label, plus the descender room under its baseline. */
const LABEL_HEIGHT = 12;

/**
 * Where each bubble's name goes: centred above it, kept inside the plot, and
 * moved below the bubble when the space above holds another bubble or a label
 * already placed, or when it would rise past `top` and be clipped. Beside-the-
 * bubble and above-only labels both collided in the mock. Returns each label's
 * centre x and baseline y.
 */
export function placeLabels(
  points: LabelBox[],
  left: number,
  right: number,
  top = -Infinity
): { x: number; y: number }[] {
  type Box = { x0: number; x1: number; y0: number; y1: number };
  const placed: Box[] = [];
  const overlaps = (a: Box, b: Box) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;
  const hits = (box: Box) =>
    box.y0 < top ||
    placed.some((other) => overlaps(box, other)) ||
    points.some((p) => overlaps(box, { x0: p.x - p.r, x1: p.x + p.r, y0: p.y - p.r, y1: p.y + p.r }));

  return points.map((p) => {
    const half = p.width / 2;
    const x = Math.min(right - half, Math.max(left + half, p.x));
    const box = (baseline: number): Box => ({
      x0: x - half,
      x1: x + half,
      y0: baseline - LABEL_HEIGHT + 2,
      y1: baseline + 2,
    });
    let y = p.y - p.r - 5;
    if (hits(box(y))) y = p.y + p.r + LABEL_HEIGHT + 1;
    placed.push(box(y));
    return { x, y };
  });
}

/**
 * A heatmap cell's colour for `t` in 0 (worst) to 1 (best).
 *
 * Mixing --brand-primary into --brand-accent-light, neither the dark text nor
 * white reaches 4.5:1 on the middle of the ramp (at 60% primary: white 3.6:1,
 * dark text 4.1:1). The ramp skips 50-72%: the worse half maps to 0-50% under
 * dark text (>= 5.0:1), the better half to 72-100% under white (>= 4.7:1).
 */
export function heatShade(t: number): { background: string; dark: boolean } {
  const clamped = Math.min(1, Math.max(0, t));
  const stop = clamped < 0.5 ? clamped : 0.72 + (clamped - 0.5) * 0.56;
  return {
    background: `color-mix(in oklab, var(--brand-primary) ${Math.round(stop * 100)}%, var(--brand-accent-light))`,
    dark: stop >= 0.72,
  };
}
