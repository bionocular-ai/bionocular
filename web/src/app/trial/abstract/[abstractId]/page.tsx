'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from "@/lib/supabase/hooks";
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { UserMenu } from '@/components/user-menu';
import { trialsApi } from '@/lib/api';
import { extractAbstractDetails } from '@/lib/utils/trial-utils';
import { buildArmTable } from '@/lib/utils/outcome-rows';
import { Loader2, ExternalLink, Eye, MoreVertical, Users, Activity, ShieldAlert } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { HomeNavLink } from '@/components/nav/HomeNavLink';
import { BackNav } from '@/components/nav/BackNav';
import { AbstractTimeline } from '@/components/timeline/AbstractTimeline';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

interface HeaderProps {
  session: { user?: { email?: string | null; name?: string | null } } | null;
}

function Header({ session }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50 shrink-0">
      <div className="w-full px-3 sm:px-4 md:px-6">
        <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
          <Link href={ROUTES.DASHBOARD} className="brand flex-shrink-0">
            <Logo className="text-[22px]" />
          </Link>
          <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
            <HomeNavLink />
            {session?.user && (
              <UserMenu
                email={session.user.email || null}
                name={session.user.name || null}
                image={undefined}
              />
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

function MetaCell({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-[15px] leading-snug text-gray-900 break-words">{value}</p>
    </div>
  );
}

function ArmValue({ value }: { value: string | null }) {
  if (value === null) {
    return (
      <span className="font-mono text-[15px] text-gray-500" title="Not reported for this arm">
        <span aria-hidden="true">-</span>
        <span className="sr-only">Not reported</span>
      </span>
    );
  }
  if (value === 'ref') {
    return <span className="font-mono text-[11px] font-medium text-gray-500" title="Reference arm for this hazard ratio">ref</span>;
  }
  return <span className="font-mono font-bold text-[15px] tabular-nums text-gray-900">{value}</span>;
}

function OutcomesTable({ table, label, emptyLabel }: { table: ReturnType<typeof buildArmTable>; label: string; emptyLabel: string }) {
  const scrollRef = React.useRef<HTMLDivElement>(null);
  // Which sides have more columns: drives the pinned-column shadow and the right-edge fade
  const [edges, setEdges] = React.useState({ left: false, right: false });

  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const update = () => setEdges({
      left: el.scrollLeft > 1,
      right: el.scrollLeft + el.clientWidth < el.scrollWidth - 1,
    });
    el.addEventListener('scroll', update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => {
      el.removeEventListener('scroll', update);
      observer.disconnect();
    };
  }, []);

  const { arms, rows } = table;
  // rows arrive sorted by sub-group, so consecutive runs are the groups
  const groups = rows.reduce<(typeof rows)[]>((acc, row) => {
    const last = acc[acc.length - 1];
    if (last && last[0].subGroup === row.subGroup) last.push(row);
    else acc.push([row]);
    return acc;
  }, []);
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 py-8 px-4 text-center">
        <p className="text-sm text-gray-500">{emptyLabel}</p>
      </div>
    );
  }

  const pinned = cn('sticky left-0 transition-shadow', edges.left && 'shadow-[8px_0_10px_-8px_rgba(17,24,39,0.22)]');
  // A table that scrolls sideways must be reachable by keyboard, so arrow keys can scroll it
  const scrolls = edges.left || edges.right;
  return (
    <div
      ref={scrollRef}
      tabIndex={scrolls ? 0 : undefined}
      role={scrolls ? 'region' : undefined}
      aria-label={scrolls ? `${label}, ${arms.length} arms` : undefined}
      className={cn(
        'overflow-x-auto overscroll-x-contain rounded-lg border border-gray-200 bg-white shadow-sm',
        'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 focus-visible:[mask-image:none]',
        edges.right && '[mask-image:linear-gradient(to_right,#000_calc(100%-32px),transparent)]',
      )}
    >
      <table className="w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th scope="col" className={cn(pinned, 'z-20 sm:w-2/5 bg-gray-50 border-b border-gray-200 py-3 px-2.5 sm:px-4 text-left align-bottom text-xs font-bold text-gray-700 uppercase tracking-wider')}>
              Metric
            </th>
            {arms.map((arm, i) => (
              <th
                key={i}
                scope="col"
                className={cn(
                  'w-px sm:w-auto min-w-[72px] sm:min-w-[96px] border-b border-gray-200 py-3 px-2.5 sm:px-4 text-right align-bottom',
                  arm.control ? 'bg-gray-100' : 'bg-gray-50',
                )}
              >
                <span className="block text-[11px] sm:text-xs font-semibold leading-snug text-gray-900">{arm.name}</span>
                <span className="mt-1 block font-mono text-[11px] font-medium text-gray-500">
                  {arm.patients !== null && `n ${arm.patients}`}
                  {arm.control && (
                    <span className="ml-1 inline-block rounded-sm border border-gray-200 bg-white px-1 font-sans text-[9px] font-bold uppercase tracking-wider">
                      Control
                    </span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        {groups.map((group, g) => (
          <tbody key={group[0].subGroup}>
            <tr>
              <th
                colSpan={arms.length + 1}
                scope="rowgroup"
                className={cn('bg-gray-50/60 px-2.5 sm:px-4 pt-2.5 pb-1.5 text-left', g > 0 && 'border-t border-gray-200')}
              >
                <span className="sticky left-2.5 sm:left-4 text-[11px] font-bold uppercase tracking-wider text-blue-700">{group[0].subGroup}</span>
              </th>
            </tr>
            {group.map((row, idx) => (
              <tr key={row.key} className="group">
                <th
                  scope="row"
                  className={cn(pinned, 'z-10 bg-white group-hover:bg-slate-100 py-2.5 px-2.5 sm:px-4 text-left font-normal', idx > 0 && 'border-t border-gray-100')}
                >
                  <div className="text-sm font-medium text-gray-900 whitespace-nowrap">{row.label}</div>
                  <div className="hidden sm:block text-xs text-gray-500 mt-0.5">{row.description}</div>
                </th>
                {row.values.map((value, i) => (
                  <td
                    key={i}
                    className={cn(
                      'py-2.5 px-2.5 sm:px-4 text-right whitespace-nowrap group-hover:bg-slate-100',
                      arms[i].control && 'bg-gray-50/70',
                      idx > 0 && 'border-t border-gray-100',
                    )}
                  >
                    <ArmValue value={value} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}

function metricCount(table: ReturnType<typeof buildArmTable>) {
  const n = table.rows.length;
  if (n === 0) return 'No reported metrics';
  const arms = table.arms.length > 1 ? ` · ${table.arms.length} arms` : '';
  return `${n} reported metric${n === 1 ? '' : 's'}${arms}`;
}

export default function AbstractDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const abstractId = params.abstractId as string;

  const [category, setCategory] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const searchParams = new URLSearchParams(window.location.search);
      setCategory(searchParams.get('category'));
    }
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ['abstract', abstractId, category],
    queryFn: () => trialsApi.getByAbstractId(abstractId, category),
  });

  if (isLoading) {
    return (
      <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
        <Header session={session} />
        <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
          <div className="w-full max-w-[1600px] mx-auto px-4 py-10 sm:px-6 md:px-6">
            <div className="flex items-center justify-center min-h-[400px]">
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground">Loading abstract details...</p>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
        <Header session={session} />
        <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
          <div className="w-full max-w-[1600px] mx-auto px-4 py-10 sm:px-6 md:px-6">
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <h2 className="text-xl font-semibold text-destructive mb-2">Abstract Not Found</h2>
                  <p className="text-muted-foreground mb-4">
                    The abstract you&apos;re looking for could not be found.
                  </p>
                  <BackNav href="/dashboard" label="Go to dashboard" className="inline-flex" />
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    );
  }

  const details = extractAbstractDetails(data);

  if (!details) {
    return (
      <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
        <Header session={session} />
        <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
          <div className="w-full max-w-[1600px] mx-auto px-4 py-10 sm:px-6 md:px-6">
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <h2 className="text-xl font-semibold text-destructive mb-2">Invalid Abstract Data</h2>
                  <p className="text-muted-foreground mb-4">
                    Unable to parse abstract data.
                  </p>
                  <BackNav href="/dashboard" label="Go to dashboard" className="inline-flex" />
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    );
  }

  const conferenceBadge = details.conference && details.year
    ? `${details.conference} ${details.year}`
    : details.conference || '';

  const outcomes = data.outcomes?.length ? data.outcomes : data.outcome ? [data.outcome] : [];
  const efficacy = buildArmTable(outcomes, 'efficacy');
  const safety = buildArmTable(outcomes, 'safety');
  const armNames = [...new Set(efficacy.arms.map((arm) => arm.name))];
  const treatment = armNames.length > 1 ? armNames.join(' vs ') : details.treatment;
  // Registered enrollment when the trial has one, else the abstract's arms added up
  const armTotal = efficacy.arms.reduce((sum, arm) => sum + (arm.patients ?? 0), 0);
  const enrollment = typeof data.trial?.enrollment_count === 'number' ? data.trial.enrollment_count : armTotal || null;

  return (
    <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
      <Header session={session} />

      <div className="border-b border-gray-200 bg-gray-50 px-3 sm:px-4 md:px-6 py-4">
        <BackNav
          onClick={() => {
            if (details.nctNumber) {
              const nctUrl = category
                ? `/trial/nct/${details.nctNumber}?category=${category}`
                : `/trial/nct/${details.nctNumber}`;
              router.push(nctUrl);
            } else {
              router.back();
            }
          }}
          label={details.nctNumber ? 'Back to trial' : 'Back'}
        />
      </div>

      <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
        <div className="w-full min-w-0 max-w-[1600px] mx-auto px-4 py-5 sm:px-5 sm:py-6 md:px-6 md:py-6">
          <div className="pb-8 sm:pb-10 flex min-w-0 flex-col xl:flex-row xl:items-start xl:gap-8 2xl:gap-10 gap-6">
            <div className="xl:order-1 flex-1 min-w-0 basis-0 space-y-4">
              {/* Trial Summary Card */}
              <Card className="bg-white border border-gray-200 shadow-sm rounded-md overflow-hidden">
                <CardHeader className="pb-5 pt-6 px-5 sm:px-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-col-reverse items-start gap-2 sm:flex-row sm:justify-between sm:gap-3">
                        <CardTitle className="text-xl sm:text-2xl font-bold text-gray-900 leading-snug break-words mb-2 flex-1 min-w-0">
                          {details.title || 'Untitled Abstract'}
                        </CardTitle>
                        {conferenceBadge && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-700 border border-purple-200 flex-shrink-0 mt-1 whitespace-nowrap">
                            {conferenceBadge}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mt-2 text-sm text-gray-600">
                        {details.nctNumber && (
                          <Link
                            href={category ? `/trial/nct/${details.nctNumber}?category=${category}` : `/trial/nct/${details.nctNumber}`}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors whitespace-nowrap"
                          >
                            {details.nctNumber}
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                        {details.phase && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 whitespace-nowrap">
                            Phase {details.phase}
                          </span>
                        )}
                        {details.status && details.status.toLowerCase() !== 'unknown' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200 whitespace-nowrap">
                            {details.status}
                          </span>
                        )}
                        {enrollment !== null && !Number.isNaN(enrollment) && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200 whitespace-nowrap">
                            <Users className="h-3 w-3" />
                            {enrollment.toLocaleString()}
                          </span>
                        )}
                        {details.abstractId && details.abstractId !== details.nctNumber && details.abstractId.startsWith('webscrape_') && details.sourceUrl && (
                          <a
                            href={details.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                            title="View source"
                          >
                            <span className="font-mono">#{details.abstractId}</span>
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Button variant="ghost" size="icon" className="h-9 w-9 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100" aria-label="View">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-9 w-9 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100" aria-label="More options">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-5 sm:px-6 pt-0 pb-6">
                  <div className={cn(
                    'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-5',
                    'pt-5 border-t border-gray-100',
                  )}>
                    <MetaCell label="Company" value={details.sponsor} />
                    <MetaCell label="Treatment" value={treatment} />
                    <MetaCell label="Indication" value={details.indication} />
                    <MetaCell label="Line of Therapy" value={details.lineOfTherapy} />
                    <MetaCell label="Target" value={details.target} />
                    <MetaCell label="Modality" value={details.modality} />
                    <MetaCell
                      label={details.isPublication ? 'Publication #' : 'Abstract #'}
                      value={details.abstractId || null}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* Efficacy Card */}
              <Card className="bg-white border border-gray-200 shadow-sm rounded-md overflow-hidden">
                <CardHeader className="pb-4 pt-6 px-5 sm:px-6">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center">
                      <Activity className="h-4 w-4 text-emerald-700" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-bold tracking-wide text-gray-900">Efficacy</CardTitle>
                      <CardDescription className="text-xs text-gray-500 mt-0.5">
                        {metricCount(efficacy)}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-5 sm:px-6 pt-0 pb-6">
                  <OutcomesTable table={efficacy} label="Efficacy" emptyLabel="No efficacy data available" />
                </CardContent>
              </Card>

              {/* Safety Card */}
              <Card className="bg-white border border-gray-200 shadow-sm rounded-md overflow-hidden">
                <CardHeader className="pb-4 pt-6 px-5 sm:px-6">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center">
                      <ShieldAlert className="h-4 w-4 text-amber-700" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-bold tracking-wide text-gray-900">Safety</CardTitle>
                      <CardDescription className="text-xs text-gray-500 mt-0.5">
                        {metricCount(safety)}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-5 sm:px-6 pt-0 pb-6">
                  <OutcomesTable table={safety} label="Safety" emptyLabel="No safety data available" />
                </CardContent>
              </Card>
            </div>

            {details.nctNumber && (
              <div className="xl:order-2 w-full xl:w-[380px] xl:flex-shrink-0">
                <AbstractTimeline
                  nctId={details.nctNumber}
                  currentAbstractId={details.abstractId}
                  className="bg-white border border-gray-200 rounded-[calc(0.5rem+1.5rem)]"
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
