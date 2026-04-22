/**
 * Compare Treatments Table Transformer
 * Builds a metric-by-treatment matrix (up to 5 columns) from raw trial data.
 */

import {
  ClinicalTrialRaw,
  EFFICACY_METRICS,
  SAFETY_METRICS,
  MetricConfig,
} from '@/types/analytics';
import {
  CompareCell,
  CompareGroup,
  CompareMode,
  CompareRow,
  CompareTableData,
  TreatmentMeta,
} from '@/types/compare';
import {
  AttributeInput,
  extractNumericValue,
  extractStringValue,
  getAttribute,
  normalizeTreatmentName,
} from './chart-transformers';

const NR_STRINGS = new Set(['nr', 'not reported', 'n/r', 'not available', 'na', 'n/a']);
const NE_STRINGS = new Set(['ne', 'not estimable', 'not evaluable', 'not reached', 'nr*']);

function classifySentinel(attr: AttributeInput): 'NR' | 'NE' | null {
  const raw = extractStringValue(attr).trim().toLowerCase();
  if (!raw) return null;
  if (NE_STRINGS.has(raw)) return 'NE';
  if (NR_STRINGS.has(raw)) return 'NR';
  return null;
}

function formatValue(value: number, unit: string, integer?: boolean): string {
  if (integer) return Math.round(value).toString();
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
  if (unit === '%') return rounded;
  return rounded;
}

interface ArmRecord {
  value: number | null;
  status: 'value' | 'NR' | 'NE';
  year: number;
  assessmentMethod?: string;
}

function pickBest(
  records: ArmRecord[],
  lowerIsBetter: boolean,
): ArmRecord | null {
  const withValues = records.filter(r => r.status === 'value' && r.value !== null);
  if (withValues.length > 0) {
    withValues.sort((a, b) => {
      if (b.year !== a.year) return b.year - a.year;
      const av = a.value as number;
      const bv = b.value as number;
      return lowerIsBetter ? av - bv : bv - av;
    });
    return withValues[0];
  }
  const ne = records.find(r => r.status === 'NE');
  if (ne) return ne;
  const nr = records.find(r => r.status === 'NR');
  if (nr) return nr;
  return null;
}

function buildRow(
  metric: MetricConfig,
  group: CompareGroup,
  treatments: string[],
  recordsByTreatment: Map<string, ArmRecord[]>,
): CompareRow {
  const cells: Record<string, CompareCell> = {};
  let coverage = 0;

  for (const treatment of treatments) {
    const records = recordsByTreatment.get(treatment) ?? [];
    const best = pickBest(records, metric.lowerIsBetter ?? false);

    let status: CompareCell['status'] = 'NR';
    let value: number | null = null;
    let displayValue = 'NR';
    let assessmentMethod: string | undefined;

    if (best) {
      status = best.status;
      assessmentMethod = best.assessmentMethod;
      if (best.status === 'value' && best.value !== null) {
        value = best.value;
        displayValue = formatValue(best.value, metric.unit, metric.integer);
        coverage += 1;
      } else if (best.status === 'NE') {
        displayValue = 'NE';
      }
    }

    cells[treatment] = {
      treatmentName: treatment,
      metricKey: metric.key,
      value,
      displayValue,
      status,
      assessmentMethod,
      unit: metric.unit,
    };
  }

  return {
    metricKey: metric.key,
    label: metric.label,
    description: metric.description,
    unit: metric.unit,
    group,
    subGroup: metric.subGroup,
    cells,
    coverage,
  };
}

function collectArmRecords(
  trials: ClinicalTrialRaw[],
  treatments: string[],
  metricKey: string,
): Map<string, ArmRecord[]> {
  const normalizedTargets = new Map(treatments.map(t => [normalizeTreatmentName(t), t]));
  const recordsByTreatment = new Map<string, ArmRecord[]>();
  for (const t of treatments) recordsByTreatment.set(t, []);

  for (const trial of trials) {
    for (const arm of Object.values(trial.arm_results)) {
      const normalized = normalizeTreatmentName(arm.arm_name);
      const original = normalizedTargets.get(normalized) ?? (treatments.includes(arm.arm_name) ? arm.arm_name : null);
      if (!original) continue;

      const attr = getAttribute(arm.attributes, metricKey);
      const yearStr =
        extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR')) ||
        extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_YEAR'));
      const year = parseInt(yearStr, 10) || 0;
      const assessmentMethod =
        extractStringValue(getAttribute(arm.attributes, 'ASSESSMENT_METHOD')) ||
        extractStringValue(getAttribute(arm.attributes, 'RESPONSE_ASSESSMENT_METHOD')) ||
        undefined;

      const numeric = extractNumericValue(attr);
      if (numeric !== null) {
        recordsByTreatment.get(original)!.push({
          value: numeric,
          status: 'value',
          year,
          assessmentMethod: assessmentMethod || undefined,
        });
        continue;
      }

      const sentinel = classifySentinel(attr);
      if (sentinel) {
        recordsByTreatment.get(original)!.push({
          value: null,
          status: sentinel,
          year,
        });
      }
    }
  }

  return recordsByTreatment;
}

export function buildCompareTable(
  trials: ClinicalTrialRaw[],
  selectedTreatments: string[],
  mode: CompareMode,
  rawMeta?: Array<{ treatmentName: string; modality: string | null; lineOfTreatment: string | null }>,
): CompareTableData {
  const treatments = selectedTreatments;

  const efficacyRows: CompareRow[] = [];
  const safetyRows: CompareRow[] = [];

  const treatmentMeta: Record<string, TreatmentMeta> = {};
  if (rawMeta) {
    const metaByNorm = new Map(rawMeta.map(m => [normalizeTreatmentName(m.treatmentName), m]));
    for (const t of treatments) {
      const found = metaByNorm.get(normalizeTreatmentName(t));
      treatmentMeta[t] = { modality: found?.modality ?? null, lineOfTreatment: found?.lineOfTreatment ?? null };
    }
  }

  if (treatments.length === 0) {
    return { treatments, efficacyRows, safetyRows, treatmentMeta };
  }

  if (mode === 'efficacy' || mode === 'all') {
    for (const metric of Object.values(EFFICACY_METRICS)) {
      const recs = collectArmRecords(trials, treatments, metric.key);
      efficacyRows.push(buildRow(metric, 'efficacy', treatments, recs));
    }
  }

  if (mode === 'safety' || mode === 'all') {
    for (const metric of Object.values(SAFETY_METRICS)) {
      const recs = collectArmRecords(trials, treatments, metric.key);
      safetyRows.push(buildRow(metric, 'safety', treatments, recs));
    }
  }

  return { treatments, efficacyRows, safetyRows, treatmentMeta };
}
