'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useSession } from "@/lib/supabase/hooks";
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { UserMenu } from '@/components/user-menu';
import { DashboardGlobalHeader } from '@/components/dashboard/DashboardGlobalHeader';
import { SelectedFilters, type FilterTag } from '@/components/dashboard/SelectedFilters';
import { TrialCard } from '@/components/dashboard/TrialCard';
import { trialsApi } from '@/lib/api';
import type { DashboardTrialCard } from '@/lib/api';
import { Loader2, Filter, FileDown, FileSpreadsheet, ChevronDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Check } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { DEFAULT_CANCER_TYPE_SLUG, PHASE_OPTIONS, STATUS_OPTIONS } from '@/lib/dashboard-constants';

/** Modality column headers in display order (reference). */
const MODALITY_HEADERS = [
  'Monoclonal Antibody',
  'Vaccine',
  'Immunostimulant/Cytokine',
  'Bispecific',
  'CAR-T',
  'NK or Myeloid Cell Therapy',
  'TIL Therapy',
  'Small Molecule',
  'Antibody-Drug Conjugate',
  'Oncolytic Virus',
  'Chemotherapy',
] as const;

const MODALITY_OTHER = 'Other';

const UNSPECIFIED_LABEL = 'Unspecified';
const OPEN_STUDY_STATUSES = new Set([
  'open',
  'not yet recruiting',
  'recruiting',
  'active, not recruiting',
]);

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

function isOpenStudyStatus(status: string | null | undefined): boolean {
  return OPEN_STUDY_STATUSES.has((status ?? '').trim().toLowerCase());
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
    'small molecule': 'Small Molecule',
    'antibody-drug conjugate': 'Antibody-Drug Conjugate',
    'adc': 'Antibody-Drug Conjugate',
    'oncolytic virus': 'Oncolytic Virus',
    'chemotherapy': 'Chemotherapy',
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

type GroupByOption = 'modality' | 'stage' | 'biomarker' | 'line_of_therapy' | 'previous_treatment';

const GROUP_BY_OPTIONS: { value: GroupByOption; label: string }[] = [
  { value: 'modality', label: 'Modality' },
  { value: 'stage', label: 'Stage' },
  { value: 'biomarker', label: 'Biomarker' },
  { value: 'line_of_therapy', label: 'Line of therapy' },
  { value: 'previous_treatment', label: 'Previous treatment' },
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
  const { data: session } = useSession();
  const searchParams = useSearchParams();
  const params = useParams();
  const router = useRouter();

  const cancerTypeSlug = (params?.category as string) || searchParams.get('cancer_type') || DEFAULT_CANCER_TYPE_SLUG;
  const [phaseFilter, setPhaseFilter] = React.useState<string[]>([]);
  const [hasAbstractsOnly, setHasAbstractsOnly] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<string[]>([]);
  const [sponsorTypeFilter, setSponsorTypeFilter] = React.useState<string[]>([]);
  const [groupBy, setGroupBy] = React.useState<GroupByOption>('modality');
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(DEFAULT_PAGE_SIZE);
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

  const setCancerType = React.useCallback(
    (slug: string) => {
      // Navigate to the new cancer type's landscape page
      router.push(`/dashboard/${slug}/landscape`);
    },
    [router]
  );

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
    <>
    <div className="flex flex-col h-screen w-full bg-slate-100 overflow-hidden">
      <header className="bg-white border-b border-slate-200 shrink-0 z-50">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 gap-3">
            <Link href="/" className="brand flex-shrink-0 hover:opacity-80 transition-opacity">
              <Logo height={32} />
              <span className="brand-text dashboard-brand-text">
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              <DashboardNavLink />
              {session?.user && (
                <UserMenu
                  email={session.user.email || null}
                  name={(session.user.user_metadata?.full_name || session.user.user_metadata?.name || null) as string | null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 overflow-y-auto overflow-x-hidden px-2 pt-2 pb-4 md:px-4 md:pt-4 md:pb-6 bg-slate-100 gap-4">
        <div className="w-full bg-white rounded-lg shadow shrink-0 overflow-visible">
          {error && (
            <div className="mx-4 sm:mx-6 lg:mx-8 mt-4 first:mt-0">
              <Card className="border-yellow-200 bg-yellow-50">
                <CardContent className="pt-4 pb-4">
                  <p className="text-sm text-yellow-800">
                    Unable to connect to the backend API. {error instanceof Error ? error.message : 'Please ensure the backend is running.'}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Top section: stats + global cancer selection only (Level 1) */}
          <DashboardGlobalHeader
            cancerTypeSlug={cancerTypeSlug}
            onCancerTypeChange={setCancerType}
          />
        </div>

        {/* Clinical Trials — landscape section (scrolls with main) */}
        <div className="w-full bg-white rounded-lg shadow min-h-0 min-w-0">
          <section className="bg-white min-h-0">
            <div className="px-4 sm:px-6 lg:px-8 pt-3 pb-2 flex flex-col min-h-0">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 shrink-0 mb-2">
                <div>
                  <h2 className="text-2xl font-medium tracking-wide text-sky-700">Landscape</h2>
                </div>
                <div className="relative shrink-0">
                  <button
                    type="button"
                    onClick={() => setPhaseDropdownOpen((o) => !o)}
                    className="inline-flex items-center gap-2 rounded-sm bg-teal-500 px-3 py-2 sm:px-4 text-white hover:bg-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2"
                  >
                    <Filter className="h-4 w-4 shrink-0 fill-white text-white" strokeWidth={2} />
                    <span className="text-sm font-medium whitespace-nowrap">FILTERS</span>
                    <ChevronDown className="h-4 w-4 shrink-0" />
                  </button>
                  {phaseDropdownOpen && (
                    <>
                      <div className="fixed inset-0 z-10" aria-hidden onClick={() => setPhaseDropdownOpen(false)} />
                      <div className="absolute right-0 top-full z-20 mt-2 flex flex-col min-w-[30rem] max-w-[90vw] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl ring-1 ring-slate-900/5">
                        <div className="flex overflow-hidden">
                          {/* Phase */}
                          <div className="w-[9.5rem] shrink-0 flex flex-col border-r border-slate-200">
                            <div className="bg-slate-100 px-3 py-2.5 border-b border-slate-200">
                              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-600">Phase</span>
                            </div>
                            <div className="bg-slate-50/60 py-1">
                              {PHASE_OPTIONS.map((phase) => {
                                const checked = phaseDraft.includes(phase);
                                return (
                                  <label
                                    key={phase}
                                    className={`flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors ${checked ? 'bg-teal-50 text-slate-900 font-medium' : 'text-slate-700 hover:bg-white/80'}`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() =>
                                        setPhaseDraft((prev) =>
                                          prev.includes(phase) ? prev.filter((p) => p !== phase) : [...prev, phase]
                                        )
                                      }
                                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-teal-600 focus:ring-2 focus:ring-teal-500/40"
                                    />
                                    <span className="min-w-0 break-words">{phase}</span>
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                          {/* Status */}
                          <div className="min-w-[13rem] flex-1 flex flex-col border-r border-slate-200">
                            <div className="bg-slate-100 px-3 py-2.5 border-b border-slate-200">
                              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-600">Status</span>
                            </div>
                            <div className="bg-slate-50/60 py-1 max-h-52 overflow-y-auto">
                              {STATUS_OPTIONS.map((status) => {
                                const checked = statusDraft.includes(status);
                                return (
                                  <label
                                    key={status}
                                    className={`flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors ${checked ? 'bg-teal-50 text-slate-900 font-medium' : 'text-slate-700 hover:bg-white/80'}`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() =>
                                        setStatusDraft((prev) =>
                                          prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
                                        )
                                      }
                                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-teal-600 focus:ring-2 focus:ring-teal-500/40"
                                    />
                                    <span className="min-w-0 break-words">{status}</span>
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                          {/* Sponsor Type + Data */}
                          <div className="min-w-[10rem] w-[11rem] shrink-0 flex flex-col">
                            <div className="bg-slate-100 px-3 py-2.5 border-b border-slate-200">
                              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-600">Sponsor Type</span>
                            </div>
                            <div className="bg-slate-50/60 py-1">
                              {['Industry', 'Non-Industry'].map((option) => {
                                const checked = sponsorTypeDraft.includes(option);
                                return (
                                  <label
                                    key={option}
                                    className={`flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors ${checked ? 'bg-teal-50 text-slate-900 font-medium' : 'text-slate-700 hover:bg-white/80'}`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() =>
                                        setSponsorTypeDraft((prev) =>
                                          prev.includes(option) ? prev.filter((s) => s !== option) : [...prev, option]
                                        )
                                      }
                                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-teal-600 focus:ring-2 focus:ring-teal-500/40"
                                    />
                                    <span className="min-w-0 break-words">{option}</span>
                                  </label>
                                );
                              })}
                            </div>
                            <div className="border-t-2 border-slate-200 mt-0.5">
                              <div className="bg-slate-100 px-3 py-2 border-b border-slate-200">
                                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-600">Data</span>
                              </div>
                              <div className="bg-slate-50/60 py-1">
                                <label
                                  className={`flex cursor-pointer items-start gap-2.5 px-3 py-2 text-[13px] leading-snug transition-colors ${hasAbstractsDraft ? 'bg-teal-50 text-slate-900 font-medium' : 'text-slate-700 hover:bg-white/80'}`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={hasAbstractsDraft}
                                    onChange={(e) => setHasAbstractsDraft(e.target.checked)}
                                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-teal-600 focus:ring-2 focus:ring-teal-500/40"
                                  />
                                  <span className="min-w-0 break-words">Efficacy & Safety</span>
                                </label>
                              </div>
                            </div>
                          </div>
                        </div>
                        {/* Footer: Reset + Apply */}
                        <div className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3 rounded-b-xl">
                          <button
                            type="button"
                            onClick={resetFilterDraft}
                            className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-md hover:bg-slate-200/80"
                          >
                            Reset
                          </button>
                          <button
                            type="button"
                            onClick={applyFilterDraft}
                            className="inline-flex items-center gap-2 rounded-sm bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2"
                          >
                            Apply filters
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 py-2 shrink-0 border-y border-slate-100 bg-slate-50/50 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 mb-2">
                <div className="flex flex-wrap items-center gap-6 w-full">
                  {/* Level 2: Group by, selected filters (left); Export PPT (right) */}
                  <div className="flex flex-wrap items-center gap-4 flex-1 min-w-0">
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-sm font-medium tracking-wider text-slate-500">Group By:</span>
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setGroupByDropdownOpen((o) => !o)}
                          aria-label="Group by"
                          aria-expanded={groupByDropdownOpen}
                          aria-haspopup="listbox"
                          className="flex w-44 items-center justify-between border-0 border-b-2 border-sky-400 bg-transparent py-2 pl-0 pr-1 text-left text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-0"
                        >
                          <span>
                            {GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label ?? 'Modality'}
                          </span>
                          <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
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
                              className="absolute left-0 top-full z-20 mt-2 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
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
                                    className={`flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm transition-colors ${selected ? 'bg-sky-50 text-slate-900' : 'text-slate-700 hover:bg-slate-50'
                                      }`}
                                  >
                                    <span>{opt.label}</span>
                                    {selected && <Check className="h-4 w-4 shrink-0 text-sky-600" />}
                                  </button>
                                );
                              })}
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                    {hasGroupBySubfilter && (
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-sm font-medium tracking-wider text-slate-500">Filter:</span>
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setGroupBySubfilterOpen((o) => !o)}
                            aria-label={`Filter ${GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label ?? groupBy} values`}
                            aria-expanded={groupBySubfilterOpen}
                            aria-haspopup="listbox"
                            className="flex min-w-[10rem] max-w-[16rem] items-center justify-between border-0 border-b-2 border-sky-400 bg-transparent py-2 pl-0 pr-1 text-left text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-0"
                          >
                            <span className="truncate">
                              {groupByValueFilter.length === 0
                                ? 'All'
                                : groupByValueFilter.length <= 2
                                  ? groupByValueFilter.join(', ')
                                  : `${groupByValueFilter.length} selected`}
                            </span>
                            <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
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
                                className="absolute left-0 top-full z-20 mt-2 max-h-72 min-w-[14rem] overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
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
                                      className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm transition-colors ${selected ? 'bg-sky-50 text-slate-900' : 'text-slate-700 hover:bg-slate-50'}`}
                                    >
                                      <span className="min-w-0 truncate">{value}</span>
                                      {selected && <Check className="h-4 w-4 shrink-0 text-sky-600" />}
                                    </button>
                                  );
                                })}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                    <SelectedFilters tags={filterTags} className="flex-1 min-w-0" />
                  </div>
                  <div className="flex items-center gap-2 ml-auto shrink-0">
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-2xl bg-transparent px-4 py-2.5 text-sm font-semibold text-sky-700 transition-colors duration-150 hover:bg-slate-100 hover:text-sky-800"
                      title="Export Excel (placeholder)"
                    >
                      <FileSpreadsheet className="h-4 w-4 text-emerald-700 shrink-0" />
                      <span>Export Excel</span>
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-2xl bg-transparent px-4 py-2.5 text-sm font-semibold text-sky-700 transition-colors duration-150 hover:bg-slate-100 hover:text-sky-800"
                      title="Export PPT (placeholder)"
                    >
                      <FileDown className="h-4 w-4 text-emerald-700 shrink-0" />
                      <span>Export PPT</span>
                    </button>
                  </div>
                </div>
              </div>

              <div>
                {trialsLoading ? (
                  <div className="flex items-center justify-center h-full min-h-[200px]">
                    <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                  </div>
                ) : groupBy === 'modality' ? (
                  /* Group by Modality — column layout: top 15 per column, then Load more */
                  <div className="pb-4 min-h-0">
                    <div className="overflow-x-auto pr-4 w-full min-h-0 pb-6">
                      <div className="flex gap-4 min-w-max">
                        {(groupByValueFilter.length > 0
                          ? trialsByModality.order.filter((c) => groupByValueFilter.includes(c))
                          : trialsByModality.order
                        ).map((groupLabel) => {
                          const groupTrials = trialsByModality.map[groupLabel] ?? [];
                          const visibleCount = visibleCountByGroup[groupLabel] ?? CARDS_PER_GROUP_INITIAL;
                          const visibleTrials = groupTrials.slice(0, visibleCount);
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
                              className="flex flex-col shrink-0 w-[320px] min-h-[124px]"
                            >
                              <h3 className="text-sm font-semibold text-slate-600 mb-3 pb-1.5 border-b border-slate-200 shrink-0">
                                {groupLabel}
                              </h3>
                              <div className="flex flex-col gap-2">
                                {visibleTrials.map((trial) => (
                                  <TrialCard
                                    key={trial.nct_id}
                                    trial={trial}
                                    category={cancerTypeSlug}
                                  />
                                ))}
                              </div>
                              {hasMore && (
                                <div className="mt-5 pt-1 pb-0.5 w-full">
                                  <button
                                    type="button"
                                    disabled={isLoadingMore || loadingMoreAll}
                                    onClick={handleLoadMore}
                                    aria-busy={isLoadingMore}
                                    aria-disabled={isLoadingMore || loadingMoreAll}
                                    title={showCountPill ? `${categoryTotal.toLocaleString()} in this category` : undefined}
                                    className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-slate-200 bg-transparent text-slate-700 text-sm font-medium transition-colors hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:ring-offset-1 disabled:opacity-60 disabled:pointer-events-none"
                                  >
                                    {isLoadingMore ? (
                                      <>
                                        <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                                        <span>Loading…</span>
                                      </>
                                    ) : (
                                      <>
                                        <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                                        <span>{loadMoreMainLabel}</span>
                                        {showCountPill && (
                                          <span
                                            className="shrink-0 text-xs text-slate-400 bg-slate-100 rounded-full px-2 py-0.5 tabular-nums"
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
                                <p className="text-sm text-slate-400 py-2">No trials</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Group by Stage / Biomarker / Line of therapy / Previous treatment — same as Modality: top per category, Load more fetches from server */
                  <div className="pb-4 min-h-0">
                    <div className="overflow-x-auto pr-4 w-full min-h-0 pb-6">
                      <div className="flex gap-4 min-w-max">
                        {(groupByValueFilter.length > 0
                          ? trialsByCustomGroup.order.filter((c) => groupByValueFilter.includes(c))
                          : trialsByCustomGroup.order
                        ).map((groupLabel) => {
                          const groupTrials = trialsByCustomGroup.map[groupLabel] ?? [];
                          const visibleCount = visibleCountByGroup[groupLabel] ?? CARDS_PER_GROUP_INITIAL;
                          const visibleTrials = groupTrials.slice(0, visibleCount);
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
                              className="flex flex-col shrink-0 w-[320px] min-h-[124px]"
                            >
                              <h3 className="text-sm font-semibold text-slate-600 mb-3 pb-1.5 border-b border-slate-200 shrink-0">
                                {groupLabel}
                              </h3>
                              <div className="flex flex-col gap-2">
                                {visibleTrials.map((trial) => (
                                  <TrialCard
                                    key={trial.nct_id}
                                    trial={trial}
                                    category={cancerTypeSlug}
                                  />
                                ))}
                              </div>
                              {hasMore && (
                                <div className="mt-5 pt-1 pb-0.5 w-full">
                                  <button
                                    type="button"
                                    disabled={isLoadingMore}
                                    onClick={handleLoadMore}
                                    aria-busy={isLoadingMore}
                                    className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg border border-slate-200 bg-transparent text-slate-700 text-sm font-medium transition-colors hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:ring-offset-1 disabled:opacity-60 disabled:pointer-events-none"
                                  >
                                    {isLoadingMore ? (
                                      <>
                                        <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                                        <span>Loading…</span>
                                      </>
                                    ) : (
                                      <>
                                        <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                                        <span>{nextBatch > 0 ? `Show next ${nextBatch}` : 'Load more'}</span>
                                        {showCountPill && (
                                          <span
                                            className="shrink-0 text-xs text-slate-400 bg-slate-100 rounded-full px-2 py-0.5 tabular-nums"
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
                                <p className="text-sm text-slate-400 py-2">No trials</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* When grouped by modality/target: show note instead of pagination */}
              {!trialsLoading && trialsTotal > 0 && groupBy === 'modality' && (
                <div className="pt-1 mt-0 border-t border-slate-100 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8">
                  <div className="flex flex-col items-center gap-2 py-2">
                    {modalitiesWithMore.length > 0 && (
                      <button
                        type="button"
                        disabled={loadingMoreAll}
                        onClick={handleLoadMoreAll}
                        aria-busy={loadingMoreAll}
                        className="inline-flex items-center gap-2 py-2 px-4 rounded-lg border border-slate-200 bg-slate-100 text-slate-700 text-sm font-medium transition-colors hover:bg-slate-200 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:ring-offset-1 disabled:opacity-60 disabled:pointer-events-none"
                      >
                        {loadingMoreAll ? (
                          <>
                            <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                            <span>Loading all…</span>
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                            <span>Load more in all columns</span>
                          </>
                        )}
                      </button>
                    )}
                    <p className="text-xs text-slate-500">
                      Showing {CARDS_PER_GROUP_LOAD_MORE} trials per category at a time.
                    </p>
                  </div>
                </div>
              )}

              {/* Pagination at bottom — industry standard: First / Prev / numbered pages / Next / Last (hidden when grouped by modality/target) */}
              {!trialsLoading && trialsTotal > 0 && false && (
                <nav
                  className="flex flex-wrap items-center justify-between gap-4 py-4 mt-auto border-t border-slate-200 bg-slate-50/50 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8"
                  aria-label="Trials pagination"
                >
                  <div className="flex items-center gap-4 flex-wrap">
                    <p className="text-sm text-slate-600">
                      Showing <span className="font-semibold text-slate-800">{startRow}</span>
                      –<span className="font-semibold text-slate-800">{endRow}</span> of{' '}
                      <span className="font-semibold text-slate-800">{trialsTotal.toLocaleString()}</span> trials
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-slate-500">per page</span>
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setPageSizeDropdownOpen((o) => !o)}
                          aria-expanded={pageSizeDropdownOpen}
                          aria-haspopup="listbox"
                          aria-label="Items per page"
                          className="flex w-14 items-center justify-between rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50"
                        >
                          {pageSize}
                          <ChevronDown className="h-4 w-4 text-slate-500 shrink-0" />
                        </button>
                        {pageSizeDropdownOpen && (
                          <>
                            <div className="fixed inset-0 z-10" aria-hidden onClick={() => setPageSizeDropdownOpen(false)} />
                            <div
                              role="listbox"
                              aria-label="Per page options"
                              className="absolute left-0 bottom-full z-20 mb-1 w-20 rounded-lg border border-slate-200 bg-white py-1 shadow-lg ring-1 ring-slate-900/5"
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
                                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm ${pageSize === size ? 'bg-sky-50 font-medium text-sky-800' : 'text-slate-700 hover:bg-slate-50'}`}
                                >
                                  {size}
                                  {pageSize === size && <Check className="h-4 w-4 text-sky-600 shrink-0" />}
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
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 shadow-sm hover:bg-slate-50 hover:text-slate-900 disabled:opacity-40 disabled:pointer-events-none disabled:cursor-not-allowed"
                    >
                      <ChevronsLeft className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      aria-label="Previous page"
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 shadow-sm hover:bg-slate-50 hover:text-slate-900 disabled:opacity-40 disabled:pointer-events-none disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>

                    <span className="mx-1 flex items-center gap-0.5">
                      {getPaginationPages(page, totalPages).map((p, i) =>
                        p === null ? (
                          <span key={`ellipsis-${i}`} className="flex h-9 w-9 items-center justify-center text-slate-400" aria-hidden>
                            …
                          </span>
                        ) : (
                          <button
                            key={p}
                            type="button"
                            onClick={() => setPage(p)}
                            aria-label={`Page ${p}`}
                            aria-current={page === p ? 'page' : undefined}
                            className={`inline-flex h-9 min-w-[2.25rem] items-center justify-center rounded-md border px-2 text-sm font-medium transition-colors ${
                              page === p
                                ? 'border-sky-500 bg-sky-600 text-white shadow-sm'
                                : 'border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 hover:text-slate-900'
                            }`}
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
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 shadow-sm hover:bg-slate-50 hover:text-slate-900 disabled:opacity-40 disabled:pointer-events-none disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPage(totalPages)}
                      disabled={page >= totalPages}
                      aria-label="Last page"
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 shadow-sm hover:bg-slate-50 hover:text-slate-900 disabled:opacity-40 disabled:pointer-events-none disabled:cursor-not-allowed"
                    >
                      <ChevronsRight className="h-4 w-4" />
                    </button>
                  </div>
                </nav>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
    </>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col min-h-screen w-full bg-white">
          <header className="bg-white border-b border-gray-200 h-14 sm:h-16" />
          <main className="flex-1 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </main>
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
