// Mirrors the full_name column of melanoma/resources/ash/indications.csv (the db cancer_type values).
const LABELS = [
  'Multiple Myeloma',
  'AL Amyloidosis',
  'Smoldering Myeloma',
  'Waldenström Macroglobulinemia',
  'Acute Myeloid Leukemia',
  'Acute Promyelocytic Leukemia',
  'Acute Lymphoblastic Leukemia',
  'Chronic Lymphocytic Leukemia',
  'Diffuse Large B-Cell Lymphoma',
  'Follicular Lymphoma',
  'Mantle Cell Lymphoma',
  'Marginal Zone Lymphoma',
  'Hodgkin Lymphoma',
  'T-Cell Lymphoma',
  'Chronic Myeloid Leukemia',
  'Myelodysplastic Syndromes',
  'Chronic Myelomonocytic Leukemia',
  'Myelofibrosis',
  'Polycythemia Vera / Essential Thrombocythemia',
  'Allogeneic Transplant / GVHD',
];

const toSlug = (label: string) =>
  label.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export const HEME_CANCERS: readonly { slug: string; label: string }[] = LABELS.map((label) => ({
  slug: toSlug(label),
  label,
}));

const HEME_LABELS = new Set(LABELS);

export const HEME_SLUG_TO_DB: Record<string, string> = Object.fromEntries(HEME_CANCERS.map((c) => [c.slug, c.label]));

export function isHemeCancerType(dbCancerType: string): boolean {
  return HEME_LABELS.has(dbCancerType);
}
