import { OUTCOME_COL_TO_ATTR, type TrialOutcomeRow } from '@/lib/api';
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

  for (const [col, attrKey] of Object.entries(OUTCOME_COL_TO_ATTR)) {
    const metric = metricMap[attrKey];
    if (!metric) continue;
    const value = formatValue((row as Record<string, unknown>)[col], metric);
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

export function buildEfficacyRows(row: TrialOutcomeRow | null | undefined): OutcomeRow[] {
  if (!row) return [];
  return buildRows(row, EFFICACY_METRICS, EFFICACY_SUB_GROUP_ORDER);
}

export function buildSafetyRows(row: TrialOutcomeRow | null | undefined): OutcomeRow[] {
  if (!row) return [];
  return buildRows(row, SAFETY_METRICS, SAFETY_SUB_GROUP_ORDER);
}
