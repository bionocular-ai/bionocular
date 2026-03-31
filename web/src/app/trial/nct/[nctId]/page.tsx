'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from "@/lib/supabase/hooks";
import { useParams } from 'next/navigation';
import { TrialDataTable } from '@/components/dashboard/TrialDataTable';
import { TrialDetailView } from '@/components/trial/TrialDetailView';
import { AbstractsPublicationsPanel } from '@/components/trial/AbstractsPublicationsPanel';
import { Card, CardContent } from '@/components/ui/card';
import { UserMenu } from '@/components/user-menu';
import { trialsApi } from '@/lib/api';
import { Loader2, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { BackNav } from '@/components/nav/BackNav';

export default function NCTTrialsPage() {
  const { data: session } = useSession();
  const params = useParams();
  const nctId = params?.nctId as string;
  
  // Get category from URL search params to know where to go back to
  const [category, setCategory] = React.useState<string | null>(null);
  
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const searchParams = new URLSearchParams(window.location.search);
      setCategory(searchParams.get('category'));
    }
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ['trials', 'nct', nctId],
    queryFn: () => trialsApi.getByNctId(nctId, 0, 1000), // Fetch up to 1000 trials
    retry: false,
    refetchOnWindowFocus: false,
    enabled: !!nctId,
  });

  const { data: trialDetail, isLoading: detailLoading, error: detailError } = useQuery({
    queryKey: ['trial-detail', nctId],
    queryFn: () => trialsApi.getTrialDetail(nctId),
    retry: false,
    refetchOnWindowFocus: false,
    enabled: !!nctId,
  });

  const trials = data?.trials || [];
  const showDetailView = !!trialDetail && !detailError;

  return (
    <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50 shrink-0">
        <div className="w-full px-3 sm:px-4 md:px-6">
          <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
            <Link href="/" className="brand flex-shrink-0">
              <Logo height={32} />
              <span className="brand-text" style={{ lineHeight: '1.2' }}>
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
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

      {/* Page title strip: back + title (clearly distinct from nav and content) */}
      <div className="border-b border-gray-200 bg-gray-50 px-3 sm:px-4 md:px-6 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-4 min-w-0">
            <BackNav href="/dashboard" label="Back to dashboard" />
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <h1 className="text-xl sm:text-2xl font-semibold text-gray-900">
                  {nctId}
                </h1>
                <a
                  href={`https://clinicaltrials.gov/study/${nctId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline transition-colors"
                  aria-label="View trial on ClinicalTrials.gov"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
              <p className="text-sm text-gray-600 mt-1">
                {isLoading
                  ? 'Abstracts and publications'
                  : trials.length > 0
                    ? (() => {
                        const abstracts = trials.filter(t => !t.type || t.type === 'abstract').length;
                        const publications = trials.filter(t => t.type === 'publication').length;
                        if (abstracts > 0 && publications > 0) {
                          return `${trials.length} item${trials.length !== 1 ? 's' : ''} found (${abstracts} abstract${abstracts !== 1 ? 's' : ''}, ${publications} publication${publications !== 1 ? 's' : ''})`;
                        } else if (abstracts > 0) {
                          return `${abstracts} abstract${abstracts !== 1 ? 's' : ''} found`;
                        } else if (publications > 0) {
                          return `${publications} publication${publications !== 1 ? 's' : ''} found`;
                        } else {
                          return `${trials.length} item${trials.length !== 1 ? 's' : ''} found`;
                        }
                      })()
                    : 'No results available'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
        <div className="w-full min-w-0 max-w-[1600px] mx-auto px-4 py-5 sm:px-5 sm:py-6 md:px-6 md:py-6">
          {/* Critical Error Banner (abstracts/publications only) */}
          {error && !showDetailView && (
            <Card className="border-yellow-200 bg-yellow-50 mb-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-yellow-800 mb-1 text-sm">
                      Error Loading Trials
                    </h3>
                    <p className="text-xs text-yellow-700">
                      Unable to load abstracts and publications for this NCT number.
                    </p>
                    {error instanceof Error && (
                      <p className="text-xs text-yellow-600 mt-2">
                        Error: {error.message}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* AlphaSense-style trial detail (from clinical_trials_cache) */}
          {detailLoading && !trialDetail ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : null}
          {showDetailView && trialDetail ? (
            <div className="pb-8 sm:pb-10 flex min-w-0 flex-col xl:flex-row xl:gap-8 2xl:gap-10 gap-6">
              <div className="xl:order-1 flex-1 min-w-0 basis-0">
                <TrialDetailView data={trialDetail} nctId={nctId} />
              </div>
              {trials.length > 0 ? (
                <aside className="xl:order-2 w-full xl:w-[380px] xl:flex-shrink-0">
                  <div className="bg-white border border-gray-200 shadow-sm p-4 sm:p-5 md:p-6 h-fit min-w-0 rounded-[calc(0.5rem+1rem)] sm:rounded-[calc(0.5rem+1.25rem)] md:rounded-[calc(0.5rem+1.5rem)]">
                    <AbstractsPublicationsPanel
                      trials={trials}
                      category={category || undefined}
                    />
                  </div>
                </aside>
              ) : null}
            </div>
          ) : !detailLoading && !trialDetail ? (
            /* No cached API data: show abstracts/publications table only */
            <>
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : trials.length === 0 ? (
                <Card className="border-gray-200">
                  <CardContent className="pt-6">
                    <div className="text-center py-12">
                      <p className="text-sm text-gray-600">
                        No trial data found for {nctId}. This trial may not be in the dashboard cache for the selected cancer type.
                      </p>
                      <a
                        href={`https://clinicaltrials.gov/study/${nctId}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 mt-3 text-sm font-medium text-blue-600 hover:underline"
                      >
                        <ExternalLink className="h-4 w-4" />
                        View on ClinicalTrials.gov
                      </a>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <TrialDataTable data={trials} showAbstractId={true} hideNctId={true} category={category || undefined} />
              )}
            </>
          ) : null}
        </div>
      </main>
    </div>
  );
}

