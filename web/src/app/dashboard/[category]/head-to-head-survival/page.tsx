'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ListFilter, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { slugToCategory } from '@/lib/dashboard-constants';
import { kmCurvesApi, type KmCurveRow, type KmPoint } from '@/lib/api';
import { formatArmName } from '@/lib/utils/arm-name';
import KaplanMeierChart from '@/components/charts/KaplanMeierChart';
import { SurvivalCurveIcon } from '@/components/icons/SurvivalCurveIcon';

function fmt(n: number | null | undefined, suffix = ''): string {
  return n == null ? '—' : `${n}${suffix}`;
}

// A "comparison" = one publication + cohort (comparison_label). Arm names are
// unique within a comparison but can collide across them, so arms are selected
// by curve id (not name) to allow head-to-head across publications/cohorts.
const comparisonKey = (c: KmCurveRow) => `${c.publication_id ?? ''}||${c.comparison_label ?? ''}`;
const comparisonLabel = (c: KmCurveRow) =>
  c.comparison_label ? `${c.comparison_label} · ${c.publication_id ?? ''}` : c.publication_id ?? comparisonKey(c);

const ENDPOINT_LABELS: Record<string, string> = {
  PFS: 'Progression-free survival',
  OS: 'Overall survival',
  DFS: 'Disease-free survival',
  RFS: 'Recurrence-free survival',
  EFS: 'Event-free survival',
  DOR: 'Duration of response',
  MSS: 'Melanoma-specific survival',
};

// Source publications label the same endpoint inconsistently (e.g. "PFS",
// "PROGRESSION-FREE SURVIVAL", "PROGRESSION-FREE SURVIVAL PER BICR ASSESSMENT").
// Collapse known variants to one canonical code so the filter doesn't fragment
// a single endpoint into several duplicate-looking options.
const ENDPOINT_CANONICAL_RULES: Array<{ code: string; test: RegExp }> = [
  { code: 'OS', test: /overall survival|^os$/i },
  { code: 'PFS', test: /progression.?free|overall pfs|^pfs$/i },
  { code: 'RFS', test: /recurrence.?free|relapse.?free|^rfs$/i },
  { code: 'DFS', test: /disease.?free|^dfs$/i },
  { code: 'EFS', test: /event.?free|^efs$/i },
  { code: 'DOR', test: /duration of response|^dor$/i },
  { code: 'MSS', test: /melanoma.?specific survival|^mss$/i },
];
const ENDPOINT_ORDER = ['OS', 'PFS', 'RFS', 'DFS', 'EFS', 'DOR', 'MSS'];

function canonicalEndpoint(raw: string): string {
  const trimmed = raw.trim();
  const rule = ENDPOINT_CANONICAL_RULES.find(({ test }) => test.test(trimmed));
  return rule ? rule.code : trimmed.toUpperCase();
}

function toTitleCase(s: string): string {
  return s.toLowerCase().replace(/(^|[\s-])[a-z]/g, (c) => c.toUpperCase());
}

const endpointLabel = (e: string) => ENDPOINT_LABELS[e] ?? toTitleCase(e);

// Stable empty reference so query-loading state doesn't churn memo/effect deps.
const EMPTY_CURVES: KmCurveRow[] = [];

// Sort Relatlimab-Nivolumab first (experimental arm, approved winner in RELATIVITY-047).
const FIRST_ARM_RE = /relatlimab/i;

// Approximate HR via log-rank O/E (Mantel-Haenszel).
// cmpArm = numerator, refArm = denominator (higher median = cmp, lower = reference).
// HR < 1 → cmpArm has lower hazard than refArm (favorable, matches published convention).
function computeApproxHR(cmpArm: KmCurveRow, refArm: KmCurveRow): number | null {
  if (!cmpArm.n_points || !refArm.n_points) return null;

  const getSteps = (row: KmCurveRow): Array<{ t: number; d: number }> => {
    const steps: Array<{ t: number; d: number }> = [];
    const pts = row.twin_coords;
    for (let i = 1; i < pts.length; i++) {
      const drop = pts[i - 1].surv - pts[i].surv;
      if (drop > 0.1) {
        steps.push({ t: pts[i].time, d: Math.max(1, Math.round((drop / 100) * row.n_points!)) });
      }
    }
    return steps;
  };

  const survBefore = (coords: KmPoint[], t: number): number => {
    let s = 100;
    for (const pt of coords) {
      if (pt.time < t) s = pt.surv;
      else break;
    }
    return s;
  };

  const byTime = new Map<number, { dCmp: number; dRef: number }>();
  for (const { t, d } of getSteps(cmpArm)) {
    const e = byTime.get(t) ?? { dCmp: 0, dRef: 0 };
    e.dCmp += d;
    byTime.set(t, e);
  }
  for (const { t, d } of getSteps(refArm)) {
    const e = byTime.get(t) ?? { dCmp: 0, dRef: 0 };
    e.dRef += d;
    byTime.set(t, e);
  }

  let OCmp = 0, ECmp = 0;
  for (const [t, { dCmp, dRef }] of byTime) {
    const nCmp = Math.round((survBefore(cmpArm.twin_coords, t) / 100) * cmpArm.n_points!);
    const nRef = Math.round((survBefore(refArm.twin_coords, t) / 100) * refArm.n_points!);
    const n = nCmp + nRef;
    if (n === 0) continue;
    OCmp += dCmp;
    ECmp += (dCmp + dRef) * (nCmp / n);
  }

  if (ECmp === 0) return null;
  return OCmp / ECmp;
}

export default function HeadToHeadEfficacyPage() {
  const params = useParams();
  const categorySlug = params?.category as string;

  const { data, isLoading } = useQuery({
    queryKey: ['km-curves', categorySlug],
    queryFn: () => kmCurvesApi.getByCancerType(categorySlug),
    staleTime: 5 * 60 * 1000,
  });
  const allCurves = data ?? EMPTY_CURVES;

  // Distinct canonical endpoints across all publications (PFS, OS, …), in a fixed
  // clinical order with any unrecognized ones trailing alphabetically.
  const endpoints = React.useMemo(() => {
    const set = new Set(allCurves.map((c) => canonicalEndpoint(c.endpoint)));
    return [...set].sort((a, b) => {
      const ai = ENDPOINT_ORDER.indexOf(a);
      const bi = ENDPOINT_ORDER.indexOf(b);
      if (ai !== -1 || bi !== -1) return (ai === -1 ? ENDPOINT_ORDER.length : ai) - (bi === -1 ? ENDPOINT_ORDER.length : bi);
      return a.localeCompare(b);
    });
  }, [allCurves]);

  const [endpoint, setEndpoint] = React.useState<string>('');
  React.useEffect(() => {
    if (endpoints.length && !endpoints.includes(endpoint)) setEndpoint(endpoints[0]);
  }, [endpoints, endpoint]);

  // All arms for the selected endpoint, across every publication/cohort.
  const armsForEndpoint = React.useMemo(
    () => allCurves.filter((c) => canonicalEndpoint(c.endpoint) === endpoint),
    [allCurves, endpoint]
  );

  // Arms grouped by comparison for the dropdown.
  const armGroups = React.useMemo(() => {
    const map = new Map<string, { key: string; label: string; arms: KmCurveRow[] }>();
    for (const c of armsForEndpoint) {
      const key = comparisonKey(c);
      if (!map.has(key)) map.set(key, { key, label: comparisonLabel(c), arms: [] });
      map.get(key)!.arms.push(c);
    }
    return [...map.values()].map((g) => ({
      ...g,
      arms: [...g.arms].sort((a, b) => {
        const aFirst = FIRST_ARM_RE.test(a.arm_name) ? 0 : 1;
        const bFirst = FIRST_ARM_RE.test(b.arm_name) ? 0 : 1;
        return aFirst - bFirst;
      }),
    }));
  }, [armsForEndpoint]);

  // Selected curve ids (default: arms of the first comparison only).
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  React.useEffect(() => {
    const first = armGroups[0];
    setSelectedIds(new Set(first ? first.arms.map((c) => c.id) : []));
  }, [armGroups]);

  const visibleCurves: KmCurveRow[] = React.useMemo(
    () =>
      armsForEndpoint
        .filter((c) => selectedIds.has(c.id))
        .sort((a, b) => {
          const aCtrl = FIRST_ARM_RE.test(a.arm_name) ? 0 : 1;
          const bCtrl = FIRST_ARM_RE.test(b.arm_name) ? 0 : 1;
          return aCtrl - bCtrl;
        }),
    [armsForEndpoint, selectedIds]
  );

  // When exactly 2 arms selected, compute approximate HR.
  // Higher-median arm = cmp (numerator); HR < 1 means cmp has lower hazard (matches published convention).
  const hrInfo = React.useMemo(() => {
    if (visibleCurves.length !== 2) return null;
    const [a, b] = visibleCurves;
    const medA = a.twin_median ?? a.published_median ?? 0;
    const medB = b.twin_median ?? b.published_median ?? 0;
    const [cmp, ref] = medA >= medB ? [a, b] : [b, a];
    const hr = computeApproxHR(cmp, ref);
    if (hr == null) return null;
    return { hr, cmpName: formatArmName(cmp.arm_name), refName: formatArmName(ref.arm_name) };
  }, [visibleCurves]);

  // Rate timepoint can differ per arm. When selected arms agree, name it in the
  // column header; when they mix, keep the header generic and annotate each cell.
  const { rateLabel, rateMixed } = React.useMemo(() => {
    const tps = [...new Set(visibleCurves.map((c) => c.rate_timepoint).filter((t) => t != null))];
    return tps.length === 1
      ? { rateLabel: `Rate @ ${tps[0]}m`, rateMixed: false }
      : { rateLabel: 'Rate', rateMixed: tps.length > 1 };
  }, [visibleCurves]);

  // Rate value with a per-arm timepoint suffix when the selection mixes timepoints.
  const fmtRate = (value: number | null | undefined, tp: number | null | undefined) =>
    value == null ? '—' : `${value}%${rateMixed && tp != null ? ` @ ${tp}m` : ''}`;

  const MAX_ARMS = 4;

  const toggleId = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < MAX_ARMS) next.add(id);
      return next;
    });
  };
  const selectAllArms = () =>
    setSelectedIds(new Set(armsForEndpoint.slice(0, MAX_ARMS).map((c) => c.id)));
  const clearArms = () => setSelectedIds(new Set());

  return (
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          category={slugToCategory(categorySlug)}
          title="Survival Intelligence Hub"
          description="Reconstructed digitized-twin Kaplan–Meier survival curves by treatment arm, head-to-head across publications and cohorts."
          right={
            <div className="flex flex-wrap items-center justify-end gap-2">
              {endpoints.length > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-9 gap-2 rounded-full border-(--brand-border) bg-(--brand-surface) pl-3 pr-2.5 text-(--brand-text) shadow-sm hover:border-(--brand-primary) hover:bg-(--brand-accent-light)"
                    >
                      <SurvivalCurveIcon className="h-4 w-4 shrink-0 text-(--brand-text-muted)" />
                      <span className="max-w-[180px] truncate font-medium">
                        {endpoint ? endpointLabel(endpoint) : 'Endpoint'}
                      </span>
                      <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-64">
                    <DropdownMenuRadioGroup value={endpoint} onValueChange={setEndpoint}>
                      {endpoints.map((e) => (
                        <DropdownMenuRadioItem key={e} value={e}>
                          {endpointLabel(e)}
                        </DropdownMenuRadioItem>
                      ))}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!armsForEndpoint.length}
                    className="h-9 gap-2 rounded-full border-(--brand-border) bg-(--brand-surface) pl-3 pr-2.5 text-(--brand-text) shadow-sm hover:border-(--brand-primary) hover:bg-(--brand-accent-light)"
                  >
                    <ListFilter className="h-4 w-4 text-(--brand-text-muted)" />
                    <span className="font-medium">Treatment arms</span>
                    <Badge
                      variant="secondary"
                      className="bg-(--brand-accent-light) px-1.5 py-0 text-(--brand-primary)"
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {selectedIds.size}
                    </Badge>
                    <ChevronDown className="h-4 w-4 text-(--brand-text-muted)" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-[300px] p-0">
                  <div className="flex items-center justify-between gap-2 border-b border-(--brand-border) px-3 py-2">
                    <span
                      className="text-xs text-(--brand-text-muted)"
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {selectedIds.size} of {Math.min(armsForEndpoint.length, MAX_ARMS)} selected (max {MAX_ARMS})
                    </span>
                    <div className="flex items-center gap-0.5">
                      <button
                        type="button"
                        onClick={selectAllArms}
                        disabled={selectedIds.size === armsForEndpoint.length}
                        className="rounded px-1.5 py-0.5 text-xs font-medium text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) disabled:opacity-40 disabled:hover:bg-transparent"
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={clearArms}
                        disabled={selectedIds.size === 0}
                        className="rounded px-1.5 py-0.5 text-xs font-medium text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) disabled:opacity-40 disabled:hover:bg-transparent"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="max-h-[360px] overflow-y-auto py-1">
                    {armGroups.map((g, gi) => (
                      <React.Fragment key={g.key}>
                        {gi > 0 && <DropdownMenuSeparator />}
                        <DropdownMenuLabel className="truncate text-xs font-normal text-(--brand-text-muted)">
                          {g.label}
                        </DropdownMenuLabel>
                        {g.arms.map((c) => (
                          <DropdownMenuCheckboxItem
                            key={c.id}
                            checked={selectedIds.has(c.id)}
                            disabled={!selectedIds.has(c.id) && selectedIds.size >= MAX_ARMS}
                            onCheckedChange={() => toggleId(c.id)}
                            onSelect={(e) => e.preventDefault()}
                          >
                            {formatArmName(c.arm_name)}
                          </DropdownMenuCheckboxItem>
                        ))}
                      </React.Fragment>
                    ))}
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          }
        />

        {/* Chart */}
        <Card className="mt-6 border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          <CardHeader className="pb-0">
            <CardTitle className="text-center text-base font-semibold text-(--brand-text)">
              {endpoint ? `${endpointLabel(endpoint)} — Digitized twin` : 'Survival curves'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex h-[400px] items-center justify-center text-(--brand-text-muted)">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading curves…
              </div>
            ) : (
              <KaplanMeierChart
                curves={visibleCurves}
                endpoint={endpoint}
                hr={hrInfo ? { value: hrInfo.hr, cmpName: hrInfo.cmpName, refName: hrInfo.refName } : null}
              />
            )}
          </CardContent>
        </Card>

        {/* Table: published vs digitized-twin */}
        <Card className="mt-6 border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          <CardContent className="overflow-x-auto pt-6">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-(--brand-border) bg-(--brand-bg) hover:bg-(--brand-bg)">
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">Treatment Arm</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">Median (published)</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">Median (twin)</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">{rateLabel} (published)</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">{rateLabel} (twin)</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">Med. Follow-up</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">Digitized Twin Status</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-[0.08em] text-(--brand-text-muted)">Reference</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleCurves.map((c) => (
                  <TableRow key={c.id} className="border-(--brand-border)">
                    <TableCell className="font-medium text-(--brand-text)">
                      {formatArmName(c.arm_name)}
                    </TableCell>
                    <TableCell style={{ fontFamily: 'var(--font-mono)' }}>{fmt(c.published_median, 'm')}</TableCell>
                    <TableCell style={{ fontFamily: 'var(--font-mono)' }}>{fmt(c.twin_median, 'm')}</TableCell>
                    <TableCell style={{ fontFamily: 'var(--font-mono)' }}>{fmtRate(c.published_rate, c.rate_timepoint)}</TableCell>
                    <TableCell style={{ fontFamily: 'var(--font-mono)' }}>{fmtRate(c.twin_rate, c.rate_timepoint)}</TableCell>
                    <TableCell style={{ fontFamily: 'var(--font-mono)' }}>{fmt(c.median_follow_up, 'm')}</TableCell>
                    <TableCell style={{ fontFamily: 'var(--font-mono)' }}>
                      {c.match_pct == null
                        ? '—'
                        : `${c.match_pct}% Match${c.n_points != null ? ` (${c.n_points} pts)` : ''}`}
                    </TableCell>
                    <TableCell className="max-w-[220px] truncate">
                      {c.reference
                        ? /^https?:\/\//.test(c.reference)
                          ? (
                            <a
                              href={c.reference}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-(--brand-primary) hover:underline"
                            >
                              {c.reference}
                            </a>
                          )
                          : c.reference
                        : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
