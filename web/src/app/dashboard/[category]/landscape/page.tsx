'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { FilterChips } from '@/components/dashboard/FilterChips';
import { SelectedFilters, type FilterTag } from '@/components/dashboard/SelectedFilters';
import { TrialCard } from '@/components/dashboard/TrialCard';
import { trialsApi } from '@/lib/api';
import type { DashboardTrialCard } from '@/lib/api';
import { Loader2, Filter, FileDown, FileSpreadsheet, ChevronDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Check } from 'lucide-react';
import { DEFAULT_CANCER_TYPE_SLUG, MODALITY_OTHER, MODALITY_VALUES, PHASE_OPTIONS, STATUS_OPTIONS, slugToCategory } from '@/lib/dashboard-constants';
import { isOpenStudyStatus, selectTrialsWithOpenBias } from '@/lib/utils/trial-utils';
import { cn } from '@/lib/utils';
import type { GroupByOption } from '@/types/bullseye';
import { type ViewMode } from '@/components/dashboard/ViewToggle';
import { BullseyeView } from '@/components/dashboard/BullseyeView';

/** Modality column headers in display order. `Other` is rendered last, separately. */
const MODALITY_HEADERS = MODALITY_VALUES.filter((v) => v !== MODALITY_OTHER);

const UNSPECIFIED_LABEL = 'Unspecified';
/** Canonical group-by category values (match trials_extraction_prompts.py). Column order follows these lists. */
const BIOMARKER_VALUES = [
  'BRAF (V600)',
  'PD-L1',
  'HLA-A*02:01',
  'LAG-3',
  'TMB',
  'c-KIT',
  'NRAS',
  'NF1',
  'PRAME',
  'CDKN2A / CDK4',
  'MSI-H / dMMR',
  'GNAQ / GNA11',
  'SF3B1 / EIF1AX',
  'BAP1',
  'MCPyV',
  'PTCH1 / SMO',
  'PIK3CA',
  'EGFR',
  'ctDNA (MRD)',
  'MART-1',
  'gp100',
  'Other',
];

const STAGE_VALUES = [
  'Stage I',
  'Stage I/II',
  'Stage II',
  'Stage II/III',
  'Stage III',
  'Stage III/IV',
  'Stage IV',
];

const LINE_OF_THERAPY_VALUES = ['1L', '2L', '3L', 'R/R', 'Adjuvant', 'Neoadjuvant'];

const PREVIOUS_TREATMENT_VALUES = ['Failed IO', 'No prior BRAFi', 'IO Naive'];

/** Parse a semicolon- or comma-separated string into trimmed non-empty labels; fallback to Unspecified. */
function parseGroupValues(raw: string | null | undefined): string[] {
  const s = (raw ?? '').trim();
  if (!s) return [UNSPECIFIED_LABEL];
  const parts = s.split(/[;,]/).map((p) => p.trim()).filter(Boolean);
  return parts.length > 0 ? parts : [UNSPECIFIED_LABEL];
}

/** Parse modality string (semicolon-separated from extraction/CSV); return normalized modality labels. Matches trials_extraction_prompts multi-value modality. */
function parseModalityValues(raw: string | null | undefined): string[] {
  const s = (raw ?? '').trim();
  if (!s) return [MODALITY_OTHER];
  const parts = s.split(/[;,]/).map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) return [MODALITY_OTHER];
  const normalized = parts.map((p) => normalizeModality(p));
  const unique = Array.from(new Set(normalized));
  return unique.length > 0 ? unique : [MODALITY_OTHER];
}

function sortTrialsOpenStatusFirst(trials: DashboardTrialCard[]): DashboardTrialCard[] {
  return [...trials].sort((a, b) => {
    const aIsOpen = isOpenStudyStatus(a.study_status);
    const bIsOpen = isOpenStudyStatus(b.study_status);
    if (aIsOpen === bIsOpen) return 0;
    return aIsOpen ? -1 : 1;
  });
}


/** Stable empty list for useMemo when no trials data yet. */
const EMPTY_TRIALS: DashboardTrialCard[] = [];

/** Map API modality values to display header (case-insensitive match + common aliases). */
function normalizeModality(apiModality: string | null | undefined): (typeof MODALITY_HEADERS)[number] | typeof MODALITY_OTHER {
  const raw = (apiModality ?? '').trim();
  if (!raw) return MODALITY_OTHER;
  const lower = raw.toLowerCase();
  const aliases: Record<string, (typeof MODALITY_HEADERS)[number]> = {
    'monoclonal antibody': 'Monoclonal Antibody',
    'mab': 'Monoclonal Antibody',
    'vaccine': 'Vaccine',
    'immunostimulant/cytokine': 'Immunostimulant/Cytokine',
    'immunostimulant': 'Immunostimulant/Cytokine',
    'cytokine': 'Immunostimulant/Cytokine',
    'bispecific': 'Bispecific',
    'bi-specific': 'Bispecific',
    'bi-specifics': 'Bispecific',
    'car-t': 'CAR-T',
    'car t': 'CAR-T',
    'nk or myeloid cell therapy': 'NK or Myeloid Cell Therapy',
    'nk cell': 'NK or Myeloid Cell Therapy',
    'til therapy': 'TIL Therapy',
    'til': 'TIL Therapy',
    'cell therapy': 'Cell Therapy',
    'adoptive cell therapy': 'Cell Therapy',
    'gene therapy': 'Gene Therapy',
    'small molecule': 'Small Molecule',
    'antibody-drug conjugate': 'Antibody-Drug Conjugate',
    'adc': 'Antibody-Drug Conjugate',
    'oncolytic virus': 'Oncolytic Virus',
    'chemotherapy': 'Chemotherapy',
    'radiotherapy': 'Radiotherapy',
    'radiation': 'Radiotherapy',
    'radiation therapy': 'Radiotherapy',
    'radiopharmaceutical': 'Radiopharmaceutical',
    'imaging/diagnostic agent': 'Imaging/Diagnostic Agent',
    'imaging agent': 'Imaging/Diagnostic Agent',
    'diagnostic agent': 'Imaging/Diagnostic Agent',
    'pet tracer': 'Imaging/Diagnostic Agent',
    'photodynamic therapy': 'Photodynamic Therapy',
    'pdt': 'Photodynamic Therapy',
    'surgery/procedure': 'Surgery/Procedure',
    'surgery': 'Surgery/Procedure',
    'procedure': 'Surgery/Procedure',
    'graft': 'Surgery/Procedure',
    'tissue engineered': 'Surgery/Procedure',
    'device': 'Device',
    'protein/peptide therapeutic': 'Protein/Peptide Therapeutic',
    'protein': 'Protein/Peptide Therapeutic',
    'peptide': 'Protein/Peptide Therapeutic',
    'fusion protein': 'Protein/Peptide Therapeutic',
    'enzyme': 'Protein/Peptide Therapeutic',
    'dietary/microbiome': 'Dietary/Microbiome',
    'dietary': 'Dietary/Microbiome',
    'diet': 'Dietary/Microbiome',
    'microbiome': 'Dietary/Microbiome',
    'fmt': 'Dietary/Microbiome',
    'behavioral/digital health': 'Behavioral/Digital Health',
    'behavioral': 'Behavioral/Digital Health',
    'behavioural': 'Behavioral/Digital Health',
    'digital health': 'Behavioral/Digital Health',
  };
  if (aliases[lower]) return aliases[lower];
  const exact = MODALITY_HEADERS.find((h) => h.toLowerCase() === lower);
  return exact ?? MODALITY_OTHER;
}

const PAGE_SIZE_OPTIONS = [50, 100, 200, 500] as const;
const DEFAULT_PAGE_SIZE = 100;
const PAGINATION_WINDOW = 2; // pages to show on each side of current (like GitHub/Linear)

/** Build page numbers to show: [1, null, 4, 5, 6, null, 10]. null = ellipsis. */
function getPaginationPages(current: number, totalPages: number): (number | null)[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const set = new Set<number>([1, totalPages]);
  const lo = Math.max(1, current - PAGINATION_WINDOW);
  const hi = Math.min(totalPages, current + PAGINATION_WINDOW);
  for (let i = lo; i <= hi; i++) set.add(i);
  const sorted = Array.from(set).sort((a, b) => a - b);
  const out: (number | null)[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i]! - sorted[i - 1]! > 1) out.push(null);
    out.push(sorted[i]!);
  }
  return out;
}

/** When grouping by modality/target, show this many cards per column initially and per "Load more". */
const CARDS_PER_GROUP_INITIAL = 15;
const CARDS_PER_GROUP_LOAD_MORE = 15;

/** When grouping by modality, fetch this many per category so "Load more" has more to reveal. */
const CARDS_PER_GROUP_FETCH_MODALITY = 45;

// GroupByOption imported from @/types/bullseye

const GROUP_BY_OPTIONS: { value: GroupByOption; label: string }[] = [
  { value: 'modality', label: 'Modality' },
  { value: 'stage', label: 'Stage' },
  { value: 'biomarker', label: 'Biomarker' },
  { value: 'line_of_therapy', label: 'Line of therapy' },
  { value: 'previous_treatment', label: 'Previous treatment' },
];

const VIEW_OPTIONS: { value: ViewMode; label: string }[] = [
  { value: 'landscape', label: 'Landscape' },
  { value: 'bullseye', label: 'Bullseye' },
];

/** Column order for group-by dimensions; matches trials_extraction_prompts.py vocabulary. */
function getCanonicalOrderForGroupBy(groupBy: GroupByOption): string[] {
  switch (groupBy) {
    case 'stage':
      return [...STAGE_VALUES];
    case 'biomarker':
      return [...BIOMARKER_VALUES];
    case 'line_of_therapy':
      return [...LINE_OF_THERAPY_VALUES];
    case 'previous_treatment':
      return [...PREVIOUS_TREATMENT_VALUES];
    default:
      return [];
  }
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const params = useParams();
  const router = useRouter();

  const cancerTypeSlug = (params?.category as string) || searchParams.get('cancer_type') || DEFAULT_CANCER_TYPE_SLUG;
  const categoryName = slugToCategory(cancerTypeSlug);
  const [phaseFilter, setPhaseFilter] = React.useState<string[]>([]);
  const [hasAbstractsOnly, setHasAbstractsOnly] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<string[]>([]);
  const [sponsorTypeFilter, setSponsorTypeFilter] = React.useState<string[]>([]);
  const [groupBy, setGroupBy] = React.useState<GroupByOption>('modality');
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(DEFAULT_PAGE_SIZE);
  const [viewMode, setViewMode] = React.useState<ViewMode>(() =>
    searchParams.get('view') === 'bullseye' ? 'bullseye' : 'landscape'
  );
  const handleViewMode = React.useCallback((m: ViewMode) => {
    setViewMode(m);
    const params = new URLSearchParams(window.location.search);
    if (m === 'bullseye') params.set('view', 'bullseye');
    else params.delete('view');
    router.replace(`${window.location.pathname}?${params.toString()}`, { scroll: false });
  }, [router]);
  const [phaseDropdownOpen, setPhaseDropdownOpen] = React.useState(false);
  const [groupByDropdownOpen, setGroupByDropdownOpen] = React.useState(false);
  /** Subfilter: when Group by is Modality, Stage, or Biomarker, restrict columns to selected values. Empty = show all. */
  const [groupByValueFilter, setGroupByValueFilter] = React.useState<string[]>([]);
  const [groupBySubfilterOpen, setGroupBySubfilterOpen] = React.useState(false);
  const [pageSizeDropdownOpen, setPageSizeDropdownOpen] = React.useState(false);

  const groupBySubfilterOptions = React.useMemo(() => {
    if (groupBy === 'modality') return [...MODALITY_HEADERS, MODALITY_OTHER];
    if (groupBy === 'stage') return [...STAGE_VALUES];
    if (groupBy === 'biomarker') return [...BIOMARKER_VALUES];
    return [];
  }, [groupBy]);

  const hasGroupBySubfilter = groupBySubfilterOptions.length > 0;

  React.useEffect(() => {
    setGroupByValueFilter([]);
  }, [groupBy]);

  /** When grouping by modality/target, how many cards to show per column (key = modality or target label). */
  const [visibleCountByGroup, setVisibleCountByGroup] = React.useState<Record<string, number>>({});
  /** Extra trials loaded via "Load more" per modality (server-side pagination for that column). */
  const [extraTrialsByModality, setExtraTrialsByModality] = React.useState<Record<string, DashboardTrialCard[]>>({});
  /** Total trial count per modality from server (set when we fetch a modality page). */
  const [totalByModality, setTotalByModality] = React.useState<Record<string, number>>({});
  const [loadingMoreModality, setLoadingMoreModality] = React.useState<string | null>(null);
  const [loadingMoreAll, setLoadingMoreAll] = React.useState(false);

  // Draft filter state (used in panel; applied only on "Apply")
  const [phaseDraft, setPhaseDraft] = React.useState<string[]>([]);
  const [statusDraft, setStatusDraft] = React.useState<string[]>([]);
  const [sponsorTypeDraft, setSponsorTypeDraft] = React.useState<string[]>([]);
  const [hasAbstractsDraft, setHasAbstractsDraft] = React.useState(false);

  // When opening the filter panel, sync draft from applied state
  React.useEffect(() => {
    if (phaseDropdownOpen) {
      setPhaseDraft(phaseFilter);
      setStatusDraft(statusFilter);
      setSponsorTypeDraft(sponsorTypeFilter);
      setHasAbstractsDraft(hasAbstractsOnly);
    }
    // Intentionally only when panel opens; adding filter deps would overwrite draft while user edits
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phaseDropdownOpen]);

  const applyFilterDraft = React.useCallback(() => {
    setPhaseFilter(phaseDraft);
    setStatusFilter(statusDraft);
    setSponsorTypeFilter(sponsorTypeDraft);
    setHasAbstractsOnly(hasAbstractsDraft);
    setPage(1);
    setPhaseDropdownOpen(false);
  }, [phaseDraft, statusDraft, sponsorTypeDraft, hasAbstractsDraft]);

  const resetFilterDraft = React.useCallback(() => {
    setPhaseDraft([]);
    setStatusDraft([]);
    setSponsorTypeDraft([]);
    setHasAbstractsDraft(false);
  }, []);

  // Apply phase and sponsor_type from URL when landing from Pipeline Health
  React.useEffect(() => {
    const phaseParam = searchParams.get('phase');
    if (phaseParam) {
      const decoded = decodeURIComponent(phaseParam).trim();
      const phases = decoded.split(',').map((p) => p.trim()).filter(Boolean);
      const valid = phases.filter((p) => (PHASE_OPTIONS as readonly string[]).includes(p));
      if (valid.length > 0) setPhaseFilter(valid);
    }
    const sponsorParam = searchParams.get('sponsor_type');
    if (sponsorParam) {
      const decoded = decodeURIComponent(sponsorParam).trim();
      const types = decoded.split(',').map((s) => s.trim()).filter(Boolean);
      const valid = types.filter((s) => s === 'Industry' || s === 'Non-Industry');
      if (valid.length > 0) setSponsorTypeFilter(valid);
    }
  }, [searchParams]);

  // Reset to page 1 when filters or cancer type change
  const prevFiltersRef = React.useRef<string>('');
  React.useEffect(() => {
    const key = `${cancerTypeSlug}-${phaseFilter.join(',')}-${hasAbstractsOnly}-${statusFilter.join(',')}-${sponsorTypeFilter.join(',')}`;
    if (prevFiltersRef.current && prevFiltersRef.current !== key) setPage(1);
    prevFiltersRef.current = key;
  }, [cancerTypeSlug, phaseFilter, hasAbstractsOnly, statusFilter, sponsorTypeFilter]);

  /** Per-category totals and extra trials for non-modality group-by (Stage/Biomarker/Line/Previous), same pattern as modality. */
  const [totalByGroup, setTotalByGroup] = React.useState<Record<string, number>>({});
  const [extraTrialsByGroup, setExtraTrialsByGroup] = React.useState<Record<string, DashboardTrialCard[]>>({});
  const [loadingMoreGroup, setLoadingMoreGroup] = React.useState<string | null>(null);

  // When switching group-by mode or filters, reset per-column visible counts so we show 15 again
  React.useEffect(() => {
    setVisibleCountByGroup({});
    setExtraTrialsByModality({});
    setTotalByModality({});
    setExtraTrialsByGroup({});
    setTotalByGroup({});
  }, [groupBy, cancerTypeSlug, phaseFilter, hasAbstractsOnly, statusFilter, sponsorTypeFilter]);

  const { error: statsError } = useQuery({
    queryKey: ['landscape-stats', cancerTypeSlug],
    queryFn: () => trialsApi.getLandscapeStats(cancerTypeSlug),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const skip = (page - 1) * pageSize;
  const isCustomGroupBy = groupBy !== 'modality';

  const { data: trialsData, isLoading: trialsLoading, error: trialsError } = useQuery({
    queryKey: ['dashboard-trials', cancerTypeSlug, phaseFilter, hasAbstractsOnly, statusFilter, sponsorTypeFilter, skip, pageSize, groupBy],
    queryFn: () => {
      const baseFilters = {
        phase: phaseFilter.length > 0 ? phaseFilter : undefined,
        has_abstracts: hasAbstractsOnly || undefined,
        status: statusFilter.length > 0 ? statusFilter : undefined,
        sponsor_type: sponsorTypeFilter.length > 0 ? sponsorTypeFilter : undefined,
      };
      if (groupBy === 'modality') {
        // Server controls cardinality via per_group — do NOT add a top-level limit
        return trialsApi.getDashboardTrials(cancerTypeSlug, {
          ...baseFilters,
          balance_by_modality: true,
          per_group: CARDS_PER_GROUP_FETCH_MODALITY,
        });
      }
      if (isCustomGroupBy) {
        return trialsApi.getDashboardTrials(cancerTypeSlug, {
          ...baseFilters,
          balance_by_group: groupBy,
          per_group: CARDS_PER_GROUP_FETCH_MODALITY,
        });
      }
      // Flat paginated view fallback
      return trialsApi.getDashboardTrials(cancerTypeSlug, {
        ...baseFilters,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      });
    },
    retry: false,
    refetchOnWindowFocus: false,
    enabled: !!cancerTypeSlug,
  });

  const trials = React.useMemo(
    () => trialsData?.trials ?? EMPTY_TRIALS,
    [trialsData?.trials]
  );
  const trialsTotal = trialsData?.total ?? 0;

  // Populate per-modality or per-group totals from initial balanced response
  React.useEffect(() => {
    if (groupBy === 'modality' && trialsData?.totals_by_modality) {
      setTotalByModality((prev) => ({ ...prev, ...trialsData.totals_by_modality }));
    }
    if (isCustomGroupBy && trialsData?.totals_by_group) {
      setTotalByGroup((prev) => ({ ...prev, ...trialsData.totals_by_group }));
    }
  }, [groupBy, isCustomGroupBy, trialsData?.totals_by_modality, trialsData?.totals_by_group]);

  /** Base trials + extra loaded per modality (for "Load more" server fetch). */
  const allTrialsForModality = React.useMemo(() => {
    const extra = Object.values(extraTrialsByModality).flat();
    return trials.concat(extra);
  }, [trials, extraTrialsByModality]);

  const totalPages = Math.max(1, Math.ceil(trialsTotal / pageSize));
  const startRow = trialsTotal === 0 ? 0 : skip + 1;
  const endRow = Math.min(skip + pageSize, trialsTotal);

  const filterTags: FilterTag[] = React.useMemo(() => {
    const tags: FilterTag[] = [];
    if (phaseFilter.length > 0) {
      tags.push({
        id: 'phase',
        label: `Phase: ${phaseFilter.join(', ')}`,
        onRemove: () => setPhaseFilter([]),
      });
    }
    if (hasAbstractsOnly) {
      tags.push({
        id: 'abstracts',
        label: 'Efficacy & Safety',
        onRemove: () => setHasAbstractsOnly(false),
      });
    }
    if (statusFilter.length > 0) {
      tags.push({
        id: 'status',
        label: `Status: ${statusFilter.join(', ')}`,
        onRemove: () => setStatusFilter([]),
      });
    }
    if (sponsorTypeFilter.length > 0) {
      tags.push({
        id: 'sponsor_type',
        label: `Sponsor Type: ${sponsorTypeFilter.join(', ')}`,
        onRemove: () => setSponsorTypeFilter([]),
      });
    }
    return tags;
  }, [phaseFilter, hasAbstractsOnly, statusFilter, sponsorTypeFilter]);

  /** Trials grouped by modality for column layout. Multi-value modality places trial in each bucket. Dedupe by nct_id per column so the same trial (e.g. from initial + Load more) is not rendered twice. */
  const trialsByModality = React.useMemo(() => {
    const allHeaders: string[] = [...MODALITY_HEADERS, MODALITY_OTHER];
    const map: Record<string, DashboardTrialCard[]> = {};
    const seenByModality: Record<string, Set<string>> = {};
    allHeaders.forEach((h) => {
      map[h] = [];
      seenByModality[h] = new Set();
    });
    allTrialsForModality.forEach((t) => {
      const headers = parseModalityValues(t.modality ?? undefined);
      headers.forEach((header) => {
        const h = map[header] ? header : MODALITY_OTHER;
        if (seenByModality[h]!.has(t.nct_id)) return;
        seenByModality[h]!.add(t.nct_id);
        if (map[h]) map[h].push(t);
        else map[MODALITY_OTHER].push(t);
      });
    });
    Object.keys(map).forEach((key) => {
      map[key] = sortTrialsOpenStatusFirst(map[key] ?? []);
    });
    const order = [...allHeaders].sort((a, b) => {
      if (a === MODALITY_OTHER) return 1;
      if (b === MODALITY_OTHER) return -1;
      return (map[b]?.length ?? 0) - (map[a]?.length ?? 0);
    });
    return { order, map };
  }, [allTrialsForModality]);

  /** Get group key(s) for a trial for the given groupBy dimension (one trial can appear in multiple groups). */
  const getGroupKeysForTrial = React.useCallback(
    (t: DashboardTrialCard): string[] => {
      switch (groupBy) {
        case 'modality':
          return parseModalityValues(t.modality ?? undefined);
        case 'stage':
          return parseGroupValues(t.stage);
        case 'biomarker':
          return parseGroupValues(t.biomarker);
        case 'line_of_therapy':
          return parseGroupValues(t.line_of_therapy);
        case 'previous_treatment':
          return parseGroupValues(t.previous_treatment_criteria);
        default:
          return [UNSPECIFIED_LABEL];
      }
    },
    [groupBy]
  );

  /** Base trials + extra loaded per category for custom group-by (same pattern as modality). */
  const allTrialsForCustomGroup = React.useMemo(() => {
    if (!isCustomGroupBy) return trials;
    const extra = Object.values(extraTrialsByGroup).flat();
    return trials.concat(extra);
  }, [isCustomGroupBy, trials, extraTrialsByGroup]);

  /** Grouped trials for non-modality dimensions. Always show all canonical categories in prompt order (even with 0 trials), then Unspecified last. Dedupe by nct_id per column so the same trial (e.g. from initial + Load more) is not rendered twice. */
  const trialsByCustomGroup = React.useMemo(() => {
    if (groupBy === 'modality') return { order: [] as string[], map: {} as Record<string, DashboardTrialCard[]> };
    const map: Record<string, DashboardTrialCard[]> = {};
    const seenByKey: Record<string, Set<string>> = {};
    allTrialsForCustomGroup.forEach((t) => {
      const keys = getGroupKeysForTrial(t);
      keys.forEach((key) => {
        if (!map[key]) map[key] = [];
        if (!seenByKey[key]) seenByKey[key] = new Set();
        if (seenByKey[key]!.has(t.nct_id)) return;
        seenByKey[key]!.add(t.nct_id);
        map[key].push(t);
      });
    });
    Object.keys(map).forEach((key) => {
      map[key] = sortTrialsOpenStatusFirst(map[key] ?? []);
    });
    const canonical = getCanonicalOrderForGroupBy(groupBy);
    const order = [
      ...canonical,
      ...Object.keys(map).filter((k) => !canonical.includes(k) && k !== UNSPECIFIED_LABEL),
      UNSPECIFIED_LABEL,
    ];
    return { order, map };
  }, [groupBy, allTrialsForCustomGroup, getGroupKeysForTrial]);

  /** Modality columns that have more trials to load (for "Load more in all" button). Respects group-by value subfilter. */
  const modalitiesWithMore = React.useMemo(() => {
    if (groupBy !== 'modality') return [];
    const order =
      groupByValueFilter.length > 0
        ? trialsByModality.order.filter((c) => groupByValueFilter.includes(c))
        : trialsByModality.order;
    return order.filter((mod) => {
      const groupTrials = trialsByModality.map[mod] ?? [];
      const visibleCount = visibleCountByGroup[mod] ?? CARDS_PER_GROUP_INITIAL;
      const totalForModality = totalByModality[mod];
      const hasMoreClient = groupTrials.length > visibleCount;
      const hasMoreServer =
        totalForModality != null
          ? visibleCount < totalForModality
          : groupTrials.length >= CARDS_PER_GROUP_FETCH_MODALITY;
      return hasMoreClient || hasMoreServer;
    });
  }, [groupBy, groupByValueFilter, trialsByModality, visibleCountByGroup, totalByModality]);

  const handleLoadMoreAll = React.useCallback(() => {
    if (modalitiesWithMore.length === 0) return;
    setLoadingMoreAll(true);
    const baseFilters = {
      phase: phaseFilter.length > 0 ? phaseFilter : undefined,
      has_abstracts: hasAbstractsOnly || undefined,
      status: statusFilter.length > 0 ? statusFilter : undefined,
      sponsor_type: sponsorTypeFilter.length > 0 ? sponsorTypeFilter : undefined,
    };
    const promises = modalitiesWithMore.map((mod) => {
      const groupTrials = trialsByModality.map[mod] ?? [];
      return trialsApi
        .getDashboardTrials(cancerTypeSlug, {
          ...baseFilters,
          modality: mod,
          modality_skip: groupTrials.length,
          modality_limit: CARDS_PER_GROUP_LOAD_MORE,
        })
        .then((res) => ({ mod, res }));
    });
    Promise.all(promises)
      .then((pairs) => {
        setExtraTrialsByModality((prev) => {
          const next = { ...prev };
          pairs.forEach(({ mod, res }) => {
            next[mod] = [...(next[mod] ?? []), ...res.trials];
          });
          return next;
        });
        setTotalByModality((prev) => {
          const next = { ...prev };
          pairs.forEach(({ mod, res }) => {
            next[mod] = res.total;
          });
          return next;
        });
        setVisibleCountByGroup((prev) => {
          const next = { ...prev };
          pairs.forEach(({ mod, res }) => {
            const cur = prev[mod] ?? CARDS_PER_GROUP_INITIAL;
            next[mod] = cur + res.trials.length;
          });
          return next;
        });
      })
      .finally(() => setLoadingMoreAll(false));
  }, [
    cancerTypeSlug,
    phaseFilter,
    hasAbstractsOnly,
    statusFilter,
    sponsorTypeFilter,
    trialsByModality,
    modalitiesWithMore,
  ]);

  const error = statsError ?? trialsError;

  return (
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          category={categoryName}
          title="Trial Landscape"
          description="Active and historical trials across the treatment landscape, grouped by modality, biomarker, stage, and line of therapy."
          right={
            <FilterChips
              label="VIEW"
              options={VIEW_OPTIONS}
              value={viewMode}
              onChange={handleViewMode}
            />
          }
        />

        {error && (
          <div className="mt-6">
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-4 pb-4">
                <p className="text-sm text-amber-800">
                  Unable to connect to the backend API. {error instanceof Error ? error.message : 'Please ensure the backend is running.'}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Toolbar: filters + group-by + selected filters + export */}
        <div className="mt-6 flex flex-col gap-4 rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-4 shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              {/* Group by */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">
                  Group by
                </span>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setGroupByDropdownOpen((o) => !o)}
                    aria-label="Group by"
                    aria-expanded={groupByDropdownOpen}
                    aria-haspopup="listbox"
                    className="flex w-44 items-center justify-between rounded-full border border-(--brand-border) bg-(--brand-surface) py-2 pl-3 pr-2.5 text-left text-sm text-(--brand-text) transition-colors hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
                  >
                    <span>
                      {GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label ?? 'Modality'}
                    </span>
                    <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" />
                  </button>
                  {groupByDropdownOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        aria-hidden
                        onClick={() => setGroupByDropdownOpen(false)}
                      />
                      <div
                        role="listbox"
                        aria-label="Group by"
                        className="absolute left-0 top-full z-20 mt-1.5 w-52 rounded-xl border border-(--brand-border) bg-(--brand-surface) py-1 shadow-lg"
                      >
                        {GROUP_BY_OPTIONS.map((opt) => {
                          const selected = groupBy === opt.value;
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              role="option"
                              aria-selected={selected}
                              onClick={() => {
                                setGroupBy(opt.value);
                                setGroupByDropdownOpen(false);
                              }}
                              className={cn(
                                'flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm transition-colors',
                                selected
                                  ? 'bg-(--brand-accent-light) text-(--brand-text)'
                                  : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                              )}
                            >
                              <span>{opt.label}</span>
                              {selected && <Check className="h-4 w-4 shrink-0 text-(--brand-primary)" />}
                            </button>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {hasGroupBySubfilter && (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">
                    Filter
                  </span>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setGroupBySubfilterOpen((o) => !o)}
                      aria-label={`Filter ${GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label ?? groupBy} values`}
                      aria-expanded={groupBySubfilterOpen}
                      aria-haspopup="listbox"
                      className="flex min-w-[10rem] max-w-[16rem] items-center justify-between rounded-full border border-(--brand-border) bg-(--brand-surface) py-2 pl-3 pr-2.5 text-left text-sm text-(--brand-text) transition-colors hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
                    >
                      <span className="truncate">
                        {groupByValueFilter.length === 0
                          ? 'All'
                          : groupByValueFilter.length <= 2
                            ? groupByValueFilter.join(', ')
                            : `${groupByValueFilter.length} selected`}
                      </span>
                      <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" />
                    </button>
                    {groupBySubfilterOpen && (
                      <>
                        <div
                          className="fixed inset-0 z-10"
                          aria-hidden
                          onClick={() => setGroupBySubfilterOpen(false)}
                        />
                        <div
                          role="listbox"
                          aria-label={`Filter ${groupBy} values`}
                          className="absolute left-0 top-full z-20 mt-1.5 max-h-72 min-w-[14rem] overflow-y-auto rounded-xl border border-(--brand-border) bg-(--brand-surface) py-1 shadow-lg"
                        >
                          {groupBySubfilterOptions.map((value) => {
                            const selected = groupByValueFilter.includes(value);
                            return (
                              <button
                                key={value}
                                type="button"
                                role="option"
                                aria-selected={selected}
                                onClick={() => {
                                  setGroupByValueFilter((prev) =>
                                    prev.includes(value)
                                      ? prev.filter((v) => v !== value)
                                      : [...prev, value]
                                  );
                                }}
                                className={cn(
                                  'flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm transition-colors',
                                  selected
                                    ? 'bg-(--brand-accent-light) text-(--brand-text)'
                                    : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                                )}
                              >
                                <span className="min-w-0 truncate">{value}</span>
                                {selected && <Check className="h-4 w-4 shrink-0 text-(--brand-primary)" />}
                              </button>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* Filters panel */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setPhaseDropdownOpen((o) => !o)}
                  className="inline-flex items-center gap-2 rounded-full bg-(--brand-primary) px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-(--brand-primary-hover) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1"
                >
                  <Filter className="h-4 w-4 shrink-0" strokeWidth={2} />
                  <span className="whitespace-nowrap">Filters</span>
                  <ChevronDown className="h-4 w-4 shrink-0" />
                </button>
                {phaseDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" aria-hidden onClick={() => setPhaseDropdownOpen(false)} />
                    <div className="absolute right-0 top-full z-20 mt-2 flex min-w-[30rem] max-w-[90vw] flex-col overflow-hidden rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-xl">
                      <div className="flex overflow-hidden">
                        {/* Phase */}
                        <div className="flex w-[9.5rem] shrink-0 flex-col border-r border-(--brand-border)">
                          <div className="border-b border-(--brand-border) bg-(--brand-bg) px-3 py-2.5">
                            <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Phase</span>
                          </div>
                          <div className="py-1">
                            {PHASE_OPTIONS.map((phase) => {
                              const checked = phaseDraft.includes(phase);
                              return (
                                <label
                                  key={phase}
                                  className={cn(
                                    'flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors',
                                    checked ? 'bg-(--brand-accent-light) font-medium text-(--brand-text)' : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() =>
                                      setPhaseDraft((prev) =>
                                        prev.includes(phase) ? prev.filter((p) => p !== phase) : [...prev, phase]
                                      )
                                    }
                                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-(--brand-border) text-(--brand-primary) focus:ring-2 focus:ring-(--brand-primary)/40"
                                  />
                                  <span className="min-w-0 break-words">{phase}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                        {/* Status */}
                        <div className="flex min-w-[13rem] flex-1 flex-col border-r border-(--brand-border)">
                          <div className="border-b border-(--brand-border) bg-(--brand-bg) px-3 py-2.5">
                            <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Status</span>
                          </div>
                          <div className="max-h-52 overflow-y-auto py-1">
                            {STATUS_OPTIONS.map((status) => {
                              const checked = statusDraft.includes(status);
                              return (
                                <label
                                  key={status}
                                  className={cn(
                                    'flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors',
                                    checked ? 'bg-(--brand-accent-light) font-medium text-(--brand-text)' : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() =>
                                      setStatusDraft((prev) =>
                                        prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
                                      )
                                    }
                                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-(--brand-border) text-(--brand-primary) focus:ring-2 focus:ring-(--brand-primary)/40"
                                  />
                                  <span className="min-w-0 break-words">{status}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                        {/* Sponsor Type + Data */}
                        <div className="flex w-[11rem] min-w-[10rem] shrink-0 flex-col">
                          <div className="border-b border-(--brand-border) bg-(--brand-bg) px-3 py-2.5">
                            <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Sponsor Type</span>
                          </div>
                          <div className="py-1">
                            {['Industry', 'Non-Industry'].map((option) => {
                              const checked = sponsorTypeDraft.includes(option);
                              return (
                                <label
                                  key={option}
                                  className={cn(
                                    'flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors',
                                    checked ? 'bg-(--brand-accent-light) font-medium text-(--brand-text)' : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() =>
                                      setSponsorTypeDraft((prev) =>
                                        prev.includes(option) ? prev.filter((s) => s !== option) : [...prev, option]
                                      )
                                    }
                                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-(--brand-border) text-(--brand-primary) focus:ring-2 focus:ring-(--brand-primary)/40"
                                  />
                                  <span className="min-w-0 break-words">{option}</span>
                                </label>
                              );
                            })}
                          </div>
                          <div className="mt-0.5 border-t border-(--brand-border)">
                            <div className="border-b border-(--brand-border) bg-(--brand-bg) px-3 py-2">
                              <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Data</span>
                            </div>
                            <div className="py-1">
                              <label
                                className={cn(
                                  'flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors',
                                  hasAbstractsDraft ? 'bg-(--brand-accent-light) font-medium text-(--brand-text)' : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                                )}
                              >
                                <input
                                  type="checkbox"
                                  checked={hasAbstractsDraft}
                                  onChange={(e) => setHasAbstractsDraft(e.target.checked)}
                                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-(--brand-border) text-(--brand-primary) focus:ring-2 focus:ring-(--brand-primary)/40"
                                />
                                <span className="min-w-0 break-words">Efficacy &amp; Safety</span>
                              </label>
                            </div>
                          </div>
                        </div>
                      </div>
                      {/* Footer: Reset + Apply */}
                      <div className="flex items-center justify-end gap-2 border-t border-(--brand-border) bg-(--brand-bg) px-4 py-3">
                        <button
                          type="button"
                          onClick={resetFilterDraft}
                          className="rounded-lg px-3 py-1.5 text-sm font-medium text-(--brand-text-muted) transition-colors hover:bg-(--brand-accent-light) hover:text-(--brand-text)"
                        >
                          Reset
                        </button>
                        <button
                          type="button"
                          onClick={applyFilterDraft}
                          className="inline-flex items-center gap-2 rounded-full bg-(--brand-primary) px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-(--brand-primary-hover) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1"
                        >
                          Apply filters
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Export */}
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-(--brand-text-muted) transition-colors hover:bg-(--brand-accent-light) hover:text-(--brand-primary)"
                title="Export Excel (placeholder)"
              >
                <FileSpreadsheet className="h-4 w-4 shrink-0" />
                <span>Excel</span>
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-(--brand-text-muted) transition-colors hover:bg-(--brand-accent-light) hover:text-(--brand-primary)"
                title="Export PPT (placeholder)"
              >
                <FileDown className="h-4 w-4 shrink-0" />
                <span>PPT</span>
              </button>
            </div>
          </div>

          {filterTags.length > 0 && (
            <div className="border-t border-(--brand-border) pt-3">
              <SelectedFilters tags={filterTags} />
            </div>
          )}
        </div>

        {/* Trials */}
        <div className="mt-6">
          {trialsLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-10 w-10 animate-spin text-(--brand-text-muted)" aria-hidden />
            </div>
          ) : viewMode === 'bullseye' ? (
            <BullseyeView
              trials={trials}
              groupBy={groupBy}
              cancerTypeSlug={cancerTypeSlug}
            />
          ) : groupBy === 'modality' ? (
            /* Group by Modality — column layout: top 15 per column, then Load more */
            <div className="overflow-x-auto pb-6">
              <div className="flex min-w-max gap-4">
                {(groupByValueFilter.length > 0
                  ? trialsByModality.order.filter((c) => groupByValueFilter.includes(c))
                  : trialsByModality.order
                ).map((groupLabel) => {
                  const groupTrials = trialsByModality.map[groupLabel] ?? [];
                  const visibleCount = visibleCountByGroup[groupLabel] ?? CARDS_PER_GROUP_INITIAL;
                  const visibleTrials = selectTrialsWithOpenBias(groupTrials, visibleCount);
                  const hasMoreClient = groupTrials.length > visibleCount;
                  const totalForModality = totalByModality[groupLabel];
                  const hasMoreServer = totalForModality != null
                    ? visibleCount < totalForModality
                    : groupTrials.length >= CARDS_PER_GROUP_FETCH_MODALITY;
                  const hasMore = hasMoreClient || hasMoreServer;
                  const isLoadingMore = loadingMoreModality === groupLabel;
                  const handleLoadMore = () => {
                    if (hasMoreClient) {
                      setVisibleCountByGroup((prev) => {
                        const current = prev[groupLabel] ?? CARDS_PER_GROUP_INITIAL;
                        const next = current + CARDS_PER_GROUP_LOAD_MORE;
                        const capped = Math.min(next, groupTrials.length);
                        return { ...prev, [groupLabel]: capped };
                      });
                      return;
                    }
                    if (hasMoreServer && !isLoadingMore) {
                      setLoadingMoreModality(groupLabel);
                      const filters = {
                        phase: phaseFilter.length > 0 ? phaseFilter : undefined,
                        has_abstracts: hasAbstractsOnly || undefined,
                        status: statusFilter.length > 0 ? statusFilter : undefined,
                        sponsor_type: sponsorTypeFilter.length > 0 ? sponsorTypeFilter : undefined,
                        modality: groupLabel,
                        modality_skip: groupTrials.length,
                        modality_limit: CARDS_PER_GROUP_LOAD_MORE,
                      };
                      trialsApi.getDashboardTrials(cancerTypeSlug, filters).then((res) => {
                        setExtraTrialsByModality((prev) => ({
                          ...prev,
                          [groupLabel]: [...(prev[groupLabel] ?? []), ...res.trials],
                        }));
                        setTotalByModality((prev) => ({ ...prev, [groupLabel]: res.total }));
                        setVisibleCountByGroup((prev) => ({
                          ...prev,
                          [groupLabel]: (prev[groupLabel] ?? visibleCount) + res.trials.length,
                        }));
                      }).finally(() => setLoadingMoreModality(null));
                    }
                  };
                  const remaining = Math.max(0, totalForModality != null
                    ? totalForModality - visibleCount
                    : groupTrials.length - visibleCount);
                  const nextBatch = hasMoreClient
                    ? Math.min(CARDS_PER_GROUP_LOAD_MORE, groupTrials.length - visibleCount)
                    : CARDS_PER_GROUP_LOAD_MORE;
                  const showCountPill = remaining > 0 || totalForModality != null;
                  const categoryTotal = totalForModality ?? groupTrials.length;
                  const loadMoreMainLabel = showCountPill ? `Show next ${nextBatch}` : 'Load more';
                  return (
                    <div
                      key={groupLabel}
                      className="flex w-60 shrink-0 flex-col"
                    >
                      <h3 className="mb-3 shrink-0 border-b border-(--brand-border) pb-1.5 text-sm font-semibold text-(--brand-text)">
                        {groupLabel}
                      </h3>
                      <div className="flex flex-col gap-2">
                        {visibleTrials.map((trial) => (
                          <TrialCard
                            key={trial.nct_id}
                            trial={trial}
                            category={cancerTypeSlug}
                            density="compact"
                          />
                        ))}
                      </div>
                      {hasMore && (
                        <div className="mt-5 w-full pt-1 pb-0.5">
                          <button
                            type="button"
                            disabled={isLoadingMore || loadingMoreAll}
                            onClick={handleLoadMore}
                            aria-busy={isLoadingMore}
                            aria-disabled={isLoadingMore || loadingMoreAll}
                            title={showCountPill ? `${categoryTotal.toLocaleString()} in this category` : undefined}
                            className="flex w-full items-center justify-center gap-2 rounded-xl border border-(--brand-border) bg-transparent px-3 py-2.5 text-sm font-medium text-(--brand-text-muted) transition-colors hover:border-(--brand-primary) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-60"
                          >
                            {isLoadingMore ? (
                              <>
                                <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                                <span>Loading…</span>
                              </>
                            ) : (
                              <>
                                <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" aria-hidden />
                                <span>{loadMoreMainLabel}</span>
                                {showCountPill && (
                                  <span
                                    className="shrink-0 rounded-full bg-(--brand-bg) px-2 py-0.5 text-xs text-(--brand-text-muted)"
                                    style={{ fontFamily: 'var(--font-mono)' }}
                                    aria-hidden
                                  >
                                    {categoryTotal.toLocaleString()}
                                  </span>
                                )}
                              </>
                            )}
                          </button>
                        </div>
                      )}
                      {groupTrials.length === 0 && (
                        <p className="py-2 text-sm text-(--brand-text-muted)">No trials</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Group by Stage / Biomarker / Line of therapy / Previous treatment — same as Modality: top per category, Load more fetches from server */
            <div className="overflow-x-auto pb-6">
              <div className="flex min-w-max gap-4">
                {(groupByValueFilter.length > 0
                  ? trialsByCustomGroup.order.filter((c) => groupByValueFilter.includes(c))
                  : trialsByCustomGroup.order
                ).map((groupLabel) => {
                  const groupTrials = trialsByCustomGroup.map[groupLabel] ?? [];
                  const visibleCount = visibleCountByGroup[groupLabel] ?? CARDS_PER_GROUP_INITIAL;
                  const visibleTrials = selectTrialsWithOpenBias(groupTrials, visibleCount);
                  const hasMoreClient = groupTrials.length > visibleCount;
                  const totalForCategory = totalByGroup[groupLabel];
                  const hasMoreServer =
                    totalForCategory != null
                      ? visibleCount < totalForCategory
                      : groupTrials.length >= CARDS_PER_GROUP_FETCH_MODALITY;
                  const hasMore = hasMoreClient || hasMoreServer;
                  const isLoadingMore = loadingMoreGroup === groupLabel;
                  const nextBatch = hasMoreClient
                    ? Math.min(CARDS_PER_GROUP_LOAD_MORE, groupTrials.length - visibleCount)
                    : CARDS_PER_GROUP_LOAD_MORE;
                  const categoryTotal = totalForCategory ?? groupTrials.length;
                  const showCountPill = (totalForCategory != null) || groupTrials.length > 0;
                  const handleLoadMore = () => {
                    if (hasMoreClient) {
                      setVisibleCountByGroup((prev) => {
                        const current = prev[groupLabel] ?? CARDS_PER_GROUP_INITIAL;
                        const next = current + CARDS_PER_GROUP_LOAD_MORE;
                        const capped = Math.min(next, groupTrials.length);
                        return { ...prev, [groupLabel]: capped };
                      });
                      return;
                    }
                    if (hasMoreServer && !isLoadingMore) {
                      setLoadingMoreGroup(groupLabel);
                      const baseFilters = {
                        phase: phaseFilter.length > 0 ? phaseFilter : undefined,
                        has_abstracts: hasAbstractsOnly || undefined,
                        status: statusFilter.length > 0 ? statusFilter : undefined,
                        sponsor_type: sponsorTypeFilter.length > 0 ? sponsorTypeFilter : undefined,
                        balance_by_group: groupBy,
                        category_filter: groupLabel,
                        category_skip: groupTrials.length,
                        category_limit: CARDS_PER_GROUP_LOAD_MORE,
                      };
                      trialsApi
                        .getDashboardTrials(cancerTypeSlug, baseFilters)
                        .then((res) => {
                          setExtraTrialsByGroup((prev) => ({
                            ...prev,
                            [groupLabel]: [...(prev[groupLabel] ?? []), ...res.trials],
                          }));
                          setTotalByGroup((prev) => ({ ...prev, [groupLabel]: res.total }));
                          setVisibleCountByGroup((prev) => ({
                            ...prev,
                            [groupLabel]: (prev[groupLabel] ?? visibleCount) + res.trials.length,
                          }));
                        })
                        .finally(() => setLoadingMoreGroup(null));
                    }
                  };
                  return (
                    <div
                      key={groupLabel}
                      className="flex w-60 shrink-0 flex-col"
                    >
                      <h3 className="mb-3 shrink-0 border-b border-(--brand-border) pb-1.5 text-sm font-semibold text-(--brand-text)">
                        {groupLabel}
                      </h3>
                      <div className="flex flex-col gap-2">
                        {visibleTrials.map((trial) => (
                          <TrialCard
                            key={trial.nct_id}
                            trial={trial}
                            category={cancerTypeSlug}
                            density="compact"
                          />
                        ))}
                      </div>
                      {hasMore && (
                        <div className="mt-5 w-full pt-1 pb-0.5">
                          <button
                            type="button"
                            disabled={isLoadingMore}
                            onClick={handleLoadMore}
                            aria-busy={isLoadingMore}
                            className="flex w-full items-center justify-center gap-2 rounded-xl border border-(--brand-border) bg-transparent px-3 py-2.5 text-sm font-medium text-(--brand-text-muted) transition-colors hover:border-(--brand-primary) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-60"
                          >
                            {isLoadingMore ? (
                              <>
                                <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                                <span>Loading…</span>
                              </>
                            ) : (
                              <>
                                <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" aria-hidden />
                                <span>{nextBatch > 0 ? `Show next ${nextBatch}` : 'Load more'}</span>
                                {showCountPill && (
                                  <span
                                    className="shrink-0 rounded-full bg-(--brand-bg) px-2 py-0.5 text-xs text-(--brand-text-muted)"
                                    style={{ fontFamily: 'var(--font-mono)' }}
                                    aria-hidden
                                  >
                                    {categoryTotal.toLocaleString()}
                                  </span>
                                )}
                              </>
                            )}
                          </button>
                        </div>
                      )}
                      {groupTrials.length === 0 && (
                        <p className="py-2 text-sm text-(--brand-text-muted)">No trials</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* When grouped by modality: show note instead of pagination */}
        {!trialsLoading && trialsTotal > 0 && groupBy === 'modality' && (
          <div className="mt-2 border-t border-(--brand-border) pt-2">
            <div className="flex flex-col items-center gap-2 py-2">
              {modalitiesWithMore.length > 0 && (
                <button
                  type="button"
                  disabled={loadingMoreAll}
                  onClick={handleLoadMoreAll}
                  aria-busy={loadingMoreAll}
                  className="inline-flex items-center gap-2 rounded-full border border-(--brand-border) bg-(--brand-surface) px-4 py-2 text-sm font-medium text-(--brand-text) transition-colors hover:border-(--brand-primary) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-60"
                >
                  {loadingMoreAll ? (
                    <>
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                      <span>Loading all…</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" aria-hidden />
                      <span>Load more in all columns</span>
                    </>
                  )}
                </button>
              )}
              <p className="text-xs text-(--brand-text-muted)">
                Showing {CARDS_PER_GROUP_LOAD_MORE} trials per category at a time.
              </p>
            </div>
          </div>
        )}

        {/* Pagination at bottom — industry standard: First / Prev / numbered pages / Next / Last (hidden when grouped by modality/target) */}
        {!trialsLoading && trialsTotal > 0 && false && (
          <nav
            className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-(--brand-border) pt-4"
            aria-label="Trials pagination"
          >
            <div className="flex flex-wrap items-center gap-4">
              <p className="text-sm text-(--brand-text-muted)">
                Showing <span className="font-semibold text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>{startRow}</span>
                –<span className="font-semibold text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>{endRow}</span> of{' '}
                <span className="font-semibold text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>{trialsTotal.toLocaleString()}</span> trials
              </p>
              <div className="flex items-center gap-2">
                <span className="text-sm text-(--brand-text-muted)">per page</span>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setPageSizeDropdownOpen((o) => !o)}
                    aria-expanded={pageSizeDropdownOpen}
                    aria-haspopup="listbox"
                    aria-label="Items per page"
                    className="flex w-14 items-center justify-between rounded-lg border border-(--brand-border) bg-(--brand-surface) px-2.5 py-1.5 text-sm font-medium text-(--brand-text) hover:bg-(--brand-accent-light)"
                  >
                    {pageSize}
                    <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" />
                  </button>
                  {pageSizeDropdownOpen && (
                    <>
                      <div className="fixed inset-0 z-10" aria-hidden onClick={() => setPageSizeDropdownOpen(false)} />
                      <div
                        role="listbox"
                        aria-label="Per page options"
                        className="absolute left-0 bottom-full z-20 mb-1 w-20 rounded-xl border border-(--brand-border) bg-(--brand-surface) py-1 shadow-lg"
                      >
                        {PAGE_SIZE_OPTIONS.map((size) => (
                          <button
                            key={size}
                            type="button"
                            role="option"
                            aria-selected={pageSize === size}
                            onClick={() => {
                              setPageSize(size);
                              setPage(1);
                              setPageSizeDropdownOpen(false);
                            }}
                            className={cn(
                              'flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm',
                              pageSize === size ? 'bg-(--brand-accent-light) font-medium text-(--brand-text)' : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)'
                            )}
                          >
                            {size}
                            {pageSize === size && <Check className="h-4 w-4 shrink-0 text-(--brand-primary)" />}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => setPage(1)}
                disabled={page <= 1}
                aria-label="First page"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-(--brand-border) bg-(--brand-surface) text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-text) disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronsLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                aria-label="Previous page"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-(--brand-border) bg-(--brand-surface) text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-text) disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <span className="mx-1 flex items-center gap-0.5">
                {getPaginationPages(page, totalPages).map((p, i) =>
                  p === null ? (
                    <span key={`ellipsis-${i}`} className="flex h-9 w-9 items-center justify-center text-(--brand-text-muted)" aria-hidden>
                      …
                    </span>
                  ) : (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPage(p)}
                      aria-label={`Page ${p}`}
                      aria-current={page === p ? 'page' : undefined}
                      style={{ fontFamily: 'var(--font-mono)' }}
                      className={cn(
                        'inline-flex h-9 min-w-[2.25rem] items-center justify-center rounded-lg border px-2 text-sm font-medium transition-colors',
                        page === p
                          ? 'border-(--brand-primary) bg-(--brand-primary) text-white'
                          : 'border-(--brand-border) bg-(--brand-surface) text-(--brand-text) hover:bg-(--brand-accent-light)'
                      )}
                    >
                      {p}
                    </button>
                  )
                )}
              </span>

              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                aria-label="Next page"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-(--brand-border) bg-(--brand-surface) text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-text) disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setPage(totalPages)}
                disabled={page >= totalPages}
                aria-label="Last page"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-(--brand-border) bg-(--brand-surface) text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-text) disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronsRight className="h-4 w-4" />
              </button>
            </div>
          </nav>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen w-full items-center justify-center bg-(--brand-bg)">
          <Loader2 className="h-8 w-8 animate-spin text-(--brand-text-muted)" />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
