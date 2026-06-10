'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Activity, Check, ChevronDown, ListFilter, Loader2 } from 'lucide-react';
import { useSession } from '@/lib/supabase/hooks';
import { UserMenu } from '@/components/user-menu';
import { Logo } from '@/components/Logo';
import { HomeNavLink } from '@/components/nav/HomeNavLink';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
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
import { kmCurvesApi, type KmCurveRow, type KmPoint } from '@/lib/api';
import KaplanMeierChart from '@/components/charts/KaplanMeierChart';

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
};
const endpointLabel = (e: string) => ENDPOINT_LABELS[e] ?? e;

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
  const { data: session } = useSession();
  const params = useParams();
  const categorySlug = params?.category as string;

  const { data, isLoading } = useQuery({
    queryKey: ['km-curves', categorySlug],
    queryFn: () => kmCurvesApi.getByCancerType(categorySlug),
    staleTime: 5 * 60 * 1000,
  });
  const allCurves = data ?? EMPTY_CURVES;

  // Distinct endpoints across all publications (PFS, OS, …).
  const endpoints = React.useMemo(
    () => [...new Set(allCurves.map((c) => c.endpoint))].sort(),
    [allCurves]
  );

  const [endpoint, setEndpoint] = React.useState<string>('');
  React.useEffect(() => {
    if (endpoints.length && !endpoints.includes(endpoint)) setEndpoint(endpoints[0]);
  }, [endpoints, endpoint]);

  // All arms for the selected endpoint, across every publication/cohort.
  const armsForEndpoint = React.useMemo(
    () => allCurves.filter((c) => c.endpoint === endpoint),
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
    return { hr, cmpName: cmp.arm_name, refName: ref.arm_name };
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
    <div className="flex flex-col h-screen w-full bg-slate-100 overflow-hidden">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="w-full px-8">
          <div className="flex items-center justify-between h-14 gap-4">
            <div className="flex items-center gap-4">
              <Link href="/" className="brand shrink-0">
                <Logo height={32} />
                <span className="brand-text text-lg">bi<span className="brand-o">o</span>nocular</span>
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <HomeNavLink />
              <DashboardNavLink />
              {session?.user && (
                <UserMenu
                  email={session.user.email || null}
                  name={(session.user.user_metadata?.full_name as string) || null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center overflow-y-auto px-4 py-6 bg-slate-100">
        <div className="w-full max-w-7xl">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
            <div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900">
                Head-to-Head Survival
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                Reconstructed digitized-twin survival curves by treatment arm.
              </p>
            </div>

            {/* Selectors */}
            <div className="flex items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!endpoints.length}
                    className="h-9 gap-2 bg-white pl-3 pr-2.5 shadow-sm hover:bg-slate-50"
                  >
                    <Activity className="h-4 w-4 text-slate-400" />
                    <span className="text-xs font-medium text-slate-400">Endpoint</span>
                    <span className="font-semibold text-slate-900">{endpoint || '—'}</span>
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-[200px]">
                  <DropdownMenuLabel className="text-xs font-normal text-slate-500">
                    Endpoint
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {endpoints.map((e) => (
                    <DropdownMenuItem
                      key={e}
                      onClick={() => setEndpoint(e)}
                      className="justify-between gap-4"
                    >
                      <span>{endpointLabel(e)}</span>
                      {e === endpoint && <Check className="h-4 w-4 text-slate-900" />}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!armsForEndpoint.length}
                    className="h-9 gap-2 bg-white pl-3 pr-2.5 shadow-sm hover:bg-slate-50"
                  >
                    <ListFilter className="h-4 w-4 text-slate-400" />
                    <span className="font-medium text-slate-700">Treatment arms</span>
                    <Badge variant="secondary" className="px-1.5 py-0 tabular-nums">
                      {selectedIds.size}
                    </Badge>
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-[300px] p-0">
                  <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2">
                    <span className="text-xs text-slate-500 tabular-nums">
                      {selectedIds.size} of {Math.min(armsForEndpoint.length, MAX_ARMS)} selected (max {MAX_ARMS})
                    </span>
                    <div className="flex items-center gap-0.5">
                      <button
                        type="button"
                        onClick={selectAllArms}
                        disabled={selectedIds.size === armsForEndpoint.length}
                        className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent"
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={clearArms}
                        disabled={selectedIds.size === 0}
                        className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="max-h-[360px] overflow-y-auto py-1">
                    {armGroups.map((g, gi) => (
                      <React.Fragment key={g.key}>
                        {gi > 0 && <DropdownMenuSeparator />}
                        <DropdownMenuLabel className="truncate text-xs font-normal text-slate-400">
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
                            {c.arm_name}
                          </DropdownMenuCheckboxItem>
                        ))}
                      </React.Fragment>
                    ))}
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Chart */}
          <Card className="bg-white">
            <CardHeader className="pb-0">
              <CardTitle className="text-base font-semibold text-slate-700 text-center">
                {endpoint ? `${endpointLabel(endpoint)} — Digitized twin` : 'Survival curves'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center h-[400px] text-slate-400">
                  <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading curves…
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
          <Card className="mt-4 bg-white">
            <CardContent className="pt-6 overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-b-2 bg-slate-50 hover:bg-slate-50">
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">Treatment Arm</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">Median (published)</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">Median (twin)</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">{rateLabel} (published)</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">{rateLabel} (twin)</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">Med. Follow-up</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">Digitized Twin Status</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-slate-600">Reference</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleCurves.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">{c.arm_name}</TableCell>
                      <TableCell>{fmt(c.published_median, 'm')}</TableCell>
                      <TableCell>{fmt(c.twin_median, 'm')}</TableCell>
                      <TableCell>{fmtRate(c.published_rate, c.rate_timepoint)}</TableCell>
                      <TableCell>{fmtRate(c.twin_rate, c.rate_timepoint)}</TableCell>
                      <TableCell>{fmt(c.median_follow_up, 'm')}</TableCell>
                      <TableCell>
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
                                className="text-sky-600 hover:underline"
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
      </main>
    </div>
  );
}
