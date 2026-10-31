import { CONTROL_ARM_RE, OUTCOME_COL_TO_ATTR, type TrialOutcomeRow } from '@/lib/api';
import { EFFICACY_METRICS, SAFETY_METRICS, type MetricConfig } from '@/types/analytics';

export interface OutcomeRow {
  key: string;
  label: string;
  description: string;
  value: string;
  subGroup: string;
}

const EFFICACY_SUB_GROUP_ORDER = ['Study', 'Response', 'PFS', 'OS', 'EFS', 'RFS', 'MFS', 'Time-to'];
const SAFETY_SUB_GROUP_ORDER = ['Study', 'AE', 'TEAE', 'TRAE', 'Specific AE', 'Grade 3+ AE', 'Grade 3+ TEAE', 'Grade 3+ TRAE'];

function formatValue(raw: unknown, metric: MetricConfig): string | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed || trimmed.toLowerCase() === 'not found') return null;
    const num = Number(trimmed);
    if (!Number.isNaN(num)) return formatNumber(num, metric);
    return trimmed;
  }
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) return null;
    return formatNumber(raw, metric);
  }
  return String(raw);
}

function formatNumber(value: number, metric: MetricConfig): string {
  if (metric.pValue) return value < 0.001 ? '<0.001' : value.toFixed(3);
  if (metric.integer) return Math.round(value).toString();
  // HRs live near 1, so one decimal turns 0.55 into 0.6
  if (metric.key.startsWith('HR_')) return value.toFixed(2);
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
  if (metric.unit === '%') return `${rounded}%`;
  if (metric.unit === 'months') return `${rounded} mo`;
  return rounded;
}

function buildRows(
  row: TrialOutcomeRow,
  metricMap: Record<string, MetricConfig>,
  subGroupOrder: string[],
): OutcomeRow[] {
  const rows: OutcomeRow[] = [];
  const orderedKeys = Object.keys(metricMap);

  // is_nr / is_lt name columns: a not-reached median is stored as null, a "<1%" as the bound 1
  const flagged = (name: 'is_nr' | 'is_lt') => (Array.isArray(row[name]) ? (row[name] as string[]) : []);
  const notReached = flagged('is_nr');
  const lessThan = flagged('is_lt');

  for (const [col, attrKey] of Object.entries(OUTCOME_COL_TO_ATTR)) {
    const metric = metricMap[attrKey];
    if (!metric) continue;
    const formatted = formatValue((row as Record<string, unknown>)[col], metric);
    const value = notReached.includes(col) ? 'NR' : formatted !== null && lessThan.includes(col) ? `<${formatted}` : formatted;
    if (value === null) continue;
    rows.push({
      key: attrKey,
      label: metric.label,
      description: metric.description,
      value,
      subGroup: metric.subGroup ?? 'Other',
    });
  }

  rows.sort((a, b) => {
    const ia = subGroupOrder.indexOf(a.subGroup);
    const ib = subGroupOrder.indexOf(b.subGroup);
    const groupDiff = (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    if (groupDiff !== 0) return groupDiff;
    return orderedKeys.indexOf(a.key) - orderedKeys.indexOf(b.key);
  });

  return rows;
}

export interface Arm {
  name: string;
  patients: number | null;
  control: boolean;
}

export interface ArmTableRow extends Omit<OutcomeRow, 'value'> {
  /** One entry per arm: the formatted value, 'ref' for the control arm of a hazard ratio, or null. */
  values: (string | null)[];
}

const isControl = (row: TrialOutcomeRow) => typeof row.arm_name === 'string' && CONTROL_ARM_RE.test(row.arm_name);

/**
 * One column per arm: experimental arms first in arm_id order, control arms last.
 * N lives in the arm header, so it is not a row.
 */
export function buildArmTable(outcomes: TrialOutcomeRow[], kind: 'efficacy' | 'safety'): { arms: Arm[]; rows: ArmTableRow[] } {
  const sorted = [...outcomes].sort((a, b) =>
    Number(isControl(a)) - Number(isControl(b)) ||
    String(a.arm_id ?? '').localeCompare(String(b.arm_id ?? ''), undefined, { numeric: true }));
  const arms = sorted.map((row) => ({
    name: typeof row.arm_name === 'string' && row.arm_name ? row.arm_name : 'Arm',
    patients: typeof row.num_patients === 'number' ? row.num_patients : null,
    control: isControl(row),
  }));

  const [metricMap, order] = kind === 'efficacy'
    ? [EFFICACY_METRICS, EFFICACY_SUB_GROUP_ORDER]
    : [SAFETY_METRICS, SAFETY_SUB_GROUP_ORDER];
  const byKey = new Map<string, ArmTableRow>();
  sorted.forEach((outcome, i) => {
    for (const { value, ...meta } of buildRows(outcome, metricMap, order)) {
      if (meta.key === 'NUMBER_OF_PATIENTS') continue;
      if (!byKey.has(meta.key)) byKey.set(meta.key, { ...meta, values: sorted.map(() => null) });
      byKey.get(meta.key)!.values[i] = value;
    }
  });

  // A hazard ratio compares against the control arm, which never stores one itself
  for (const row of byKey.values()) {
    if (!row.key.startsWith('HR_')) continue;
    arms.forEach((a, i) => { if (a.control && row.values[i] === null) row.values[i] = 'ref'; });
  }

  const keys = Object.keys(metricMap);
  const rank = (r: ArmTableRow) => {
    const g = order.indexOf(r.subGroup);
    return (g === -1 ? 999 : g) * 1000 + keys.indexOf(r.key);
  };
  return { arms, rows: [...byKey.values()].sort((a, b) => rank(a) - rank(b)) };
}
