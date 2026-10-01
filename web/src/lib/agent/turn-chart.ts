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
