import { describe, expect, it } from 'vitest';
import { ABSENT, formatRowCell, type ResultParameter, type ResultTable } from './result-table';
import { heatShade, niceTicks, parseCell, placeLabels, toTurnChart } from './turn-chart';

const KEYS = [
  'treatment_name', 'nct_id', 'setting', 'num_patients', 'median_pfs', 'grade_3_plus_teae_pct',
  'ae_leading_to_discontinuation_pct', 'orr', 'hr_pfs', 'ttr',
];

const LABELS: Record<string, string> = {
  median_pfs: 'Median PFS',
  grade_3_plus_teae_pct: 'Grade 3+ TEAE %',
  ae_leading_to_discontinuation_pct: 'AE discontinuation %',
};

const parameters: ResultParameter[] = [
  { key: 'median_pfs', label: 'Median PFS', family: 'efficacy', arms: 4 },
  { key: 'grade_3_plus_teae_pct', label: 'Grade 3+ TEAE %', family: 'safety', arms: 4 },
  { key: 'ae_leading_to_discontinuation_pct', label: 'AE discontinuation %', family: 'safety', arms: 2 },
  { key: 'orr', label: 'ORR', family: 'efficacy', arms: 4 },
  { key: 'hr_pfs', label: 'HR PFS', family: 'efficacy', arms: 1 },
  { key: 'ttr', label: 'TTR', family: 'efficacy', arms: 1 },
];

const raw: Record<string, unknown>[] = [
  {
    treatment_name: 'Nivolumab + relatlimab', nct_id: 'NCT03470922', setting: 'Advanced / metastatic',
    num_patients: 355, median_pfs: 10.2, grade_3_plus_teae_pct: 21, ae_leading_to_discontinuation_pct: null,
    orr: 43, hr_pfs: 0.78, ttr: 2.8,
  },
  {
    treatment_name: 'Fianlimab + cemiplimab', nct_id: 'NCT05352672', setting: null,
    num_patients: 98, median_pfs: null, grade_3_plus_teae_pct: 28, ae_leading_to_discontinuation_pct: 1,
    orr: 57, hr_pfs: null, ttr: null,
    is_nr: ['median_pfs'], is_lt: ['ae_leading_to_discontinuation_pct'],
  },
  {
    treatment_name: 'Nivolumab', nct_id: 'NCT03470922', setting: 'Advanced / metastatic',
    num_patients: 359, median_pfs: 11, grade_3_plus_teae_pct: 11, ae_leading_to_discontinuation_pct: null,
    orr: 33, hr_pfs: null, ttr: null,
  },
  {
    treatment_name: 'Nivolumab', nct_id: 'NCT01844505', setting: 'Peri-operative',
    num_patients: null, median_pfs: 6.9, grade_3_plus_teae_pct: 17, ae_leading_to_discontinuation_pct: 8,
    orr: 44, hr_pfs: null, ttr: null,
  },
];

// Built with the real formatter, so a new cell shape fails here first.
const rows = raw.map((row) => KEYS.map((key) => formatRowCell(row, key)));
const table: ResultTable = {
  columns: KEYS.map((key) => ({ key, label: LABELS[key] ?? key })),
  rows,
  parameters,
};

// Row 0 has an earlier readout reporting the discontinuation rate its newest one leaves empty.
const discIndex = KEYS.indexOf('ae_leading_to_discontinuation_pct');
const earlierReadout = rows[0].map((cell, i) => (i === discIndex ? '15' : cell));
const earlier = (row: string[]) => (row === rows[0] ? [earlierReadout] : []);

const PICKED = ['median_pfs', 'grade_3_plus_teae_pct', 'ae_leading_to_discontinuation_pct'];

describe('parseCell', () => {
  it('reads back every shape formatRowCell writes', () => {
    expect(parseCell('10.2')).toEqual({ n: 10.2 });
    expect(parseCell('11.0')).toEqual({ n: 11 });
    expect(parseCell('-0.3')).toEqual({ n: -0.3 });
    expect(parseCell('<1')).toEqual({ n: 1, censored: true });
    expect(parseCell('NR')).toBe('NR');
    expect(parseCell(ABSENT)).toBeNull();
    expect(parseCell('Stage III')).toBeNull();
  });
});

describe('toTurnChart', () => {
  it('draws nothing for a landscape table or an empty pick', () => {
    expect(toTurnChart({ ...table, parameters: undefined }, rows, PICKED, earlier)).toBeNull();
    expect(toTurnChart(table, rows, [], earlier)).toBeNull();
  });

  it('reads values and keeps the table text, through formatRowCell', () => {
    const chart = toTurnChart(table, rows, PICKED, earlier)!;
    expect(chart.series[0].values.median_pfs).toEqual({ n: 10.2 });
    expect(chart.series[2].values.median_pfs).toEqual({ n: 11 });
    expect(chart.series[2].text.median_pfs).toBe('11.0');
    expect(chart.series[1].values.median_pfs).toBe('NR');
    expect(chart.series[1].values.ae_leading_to_discontinuation_pct).toEqual({ n: 1, censored: true });
    expect(chart.series[1].text.ae_leading_to_discontinuation_pct).toBe('<1');
  });

  it('marks a value only an earlier readout reports, and never plots it', () => {
    const chart = toTurnChart(table, rows, PICKED, earlier)!;
    expect(chart.series[0].values.ae_leading_to_discontinuation_pct).toBe('earlier');
    expect(chart.series[0].text.ae_leading_to_discontinuation_pct).toBe(ABSENT);
    expect(chart.series[2].values.ae_leading_to_discontinuation_pct).toBeNull();
  });

  it('reads N and the setting when the table carries them', () => {
    const chart = toTurnChart(table, rows, PICKED, earlier)!;
    expect(chart.series.map((s) => s.patients)).toEqual([355, 98, 359, null]);
    expect(chart.series.map((s) => s.group)).toEqual([
      'Advanced / metastatic',
      null,
      'Advanced / metastatic',
      'Peri-operative',
    ]);
  });

  it('tells apart treatments that share a name by their trial', () => {
    const chart = toTurnChart(table, rows, PICKED, earlier)!;
    expect(chart.series.map((s) => s.label)).toEqual([
      'Nivolumab + relatlimab',
      'Fianlimab + cemiplimab',
      'Nivolumab · NCT03470922',
      'Nivolumab · NCT01844505',
    ]);
  });

  it('labels endpoints as the table header does and knows which way is better', () => {
    const chart = toTurnChart(table, rows, ['median_pfs', 'grade_3_plus_teae_pct', 'orr', 'hr_pfs', 'ttr'], earlier)!;
    expect(chart.endpoints.map(({ key, label, family, lowerIsBetter }) => [key, label, family, lowerIsBetter])).toEqual([
      ['median_pfs', 'Median PFS', 'efficacy', false],
      ['grade_3_plus_teae_pct', 'Grade 3+ TEAE %', 'safety', true],
      ['orr', 'orr', 'efficacy', false],
      ['hr_pfs', 'hr_pfs', 'efficacy', true],
      ['ttr', 'ttr', 'efficacy', true],
    ]);
  });

  it('puts efficacy on x and safety on y, else the first two picks, else no bubble', () => {
    expect(toTurnChart(table, rows, ['median_pfs', 'grade_3_plus_teae_pct'], earlier)!.bubble).toEqual({
      x: 'median_pfs', y: 'grade_3_plus_teae_pct', size: null,
    });
    expect(toTurnChart(table, rows, ['grade_3_plus_teae_pct', 'orr'], earlier)!.bubble).toEqual({
      x: 'orr', y: 'grade_3_plus_teae_pct', size: null,
    });
    expect(toTurnChart(table, rows, ['orr', 'median_pfs'], earlier)!.bubble).toEqual({
      x: 'orr', y: 'median_pfs', size: null,
    });
    expect(toTurnChart(table, rows, ['orr'], earlier)!.bubble).toBeNull();
  });

  it('sizes the bubbles by the first pick that is on neither axis', () => {
    expect(toTurnChart(table, rows, PICKED, earlier)!.bubble).toEqual({
      x: 'median_pfs', y: 'grade_3_plus_teae_pct', size: 'ae_leading_to_discontinuation_pct',
    });
    expect(toTurnChart(table, rows, ['grade_3_plus_teae_pct', 'orr', 'median_pfs'], earlier)!.bubble).toEqual({
      x: 'orr', y: 'grade_3_plus_teae_pct', size: 'median_pfs',
    });
  });

  it('ignores a pick the table does not offer', () => {
    expect(toTurnChart(table, rows, ['median_pfs', 'not_a_column'], earlier)!.endpoints.map((e) => e.key)).toEqual(['median_pfs']);
    expect(toTurnChart(table, rows, ['not_a_column'], earlier)).toBeNull();
  });
});

describe('niceTicks', () => {
  it('steps by 1, 2 or 5 x 10^k from zero, ending at or past the max', () => {
    expect(niceTicks(4.6, 11.5)).toEqual([0, 5, 10, 15]);
    expect(niceTicks(11, 59)).toEqual([0, 20, 40, 60]);
    expect(niceTicks(0.4, 0.9)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
  });

  it('starts below zero only when the data does', () => {
    expect(niceTicks(-3, 4)).toEqual([-4, -2, 0, 2, 4]);
  });

  it('still spans a range when every value is zero', () => {
    expect(niceTicks(0, 0)).toEqual([0, 1]);
  });
});

describe('placeLabels', () => {
  it('puts a label above its bubble when nothing is in the way', () => {
    const placed = placeLabels(
      [{ x: 100, y: 100, r: 20, width: 60 }, { x: 300, y: 100, r: 10, width: 60 }],
      0,
      760,
    );
    expect(placed).toEqual([{ x: 100, y: 75 }, { x: 300, y: 85 }]);
  });

  it('moves a label below its bubble when the space above holds another bubble', () => {
    const placed = placeLabels(
      [{ x: 100, y: 140, r: 30, width: 40 }, { x: 110, y: 160, r: 10, width: 40 }],
      0,
      760,
    );
    expect(placed[1]).toEqual({ x: 110, y: 183 });
  });

  it('keeps a label inside the plot', () => {
    expect(placeLabels([{ x: 740, y: 200, r: 10, width: 100 }], 56, 736)[0].x).toBe(686);
  });
});

describe('heatShade', () => {
  it('skips the middle of the ramp, where no text colour reaches 4.5:1', () => {
    const stops = [0, 0.25, 0.49, 0.5, 0.75, 1].map((t) => heatShade(t));
    expect(stops.map((s) => s.background)).toEqual([
      'color-mix(in oklab, var(--brand-primary) 0%, var(--brand-accent-light))',
      'color-mix(in oklab, var(--brand-primary) 25%, var(--brand-accent-light))',
      'color-mix(in oklab, var(--brand-primary) 49%, var(--brand-accent-light))',
      'color-mix(in oklab, var(--brand-primary) 72%, var(--brand-accent-light))',
      'color-mix(in oklab, var(--brand-primary) 86%, var(--brand-accent-light))',
      'color-mix(in oklab, var(--brand-primary) 100%, var(--brand-accent-light))',
    ]);
    expect(stops.map((s) => s.dark)).toEqual([false, false, false, true, true, true]);
  });

  it('clamps out-of-range input', () => {
    expect(heatShade(-1)).toEqual(heatShade(0));
    expect(heatShade(2)).toEqual(heatShade(1));
  });
});
