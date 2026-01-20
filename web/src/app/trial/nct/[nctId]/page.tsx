'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { useParams, useRouter } from 'next/navigation';
import { TrialDataTable } from '@/components/dashboard/TrialDataTable';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { UserMenu } from '@/components/user-menu';
import { trialsApi } from '@/lib/api';
import { Loader2, ArrowLeft, LayoutGrid, ExternalLink } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

export default function NCTTrialsPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
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

  const trials = data?.trials || [];

  return (
    <div className="flex flex-col min-h-screen w-full bg-white">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shrink-0">
        <div className="w-full px-3 sm:px-4 md:px-6">
          <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
            <Link href="/" className="brand flex-shrink-0">
              <div className="relative flex items-center" style={{ height: '37px', flexShrink: 0, background: 'transparent' }}>
                <Image
                  src="/logo.png"
                  alt="Bionocular Logo"
                  width={37}
                  height={37}
                  className="object-contain"
                  priority
                  unoptimized
                  style={{ height: '37px', width: 'auto', background: 'transparent' }}
                />
              </div>
              <span className="brand-text" style={{ lineHeight: '1.2' }}>
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push('/dashboard')}
                className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
                aria-label="Navigate to main categories"
              >
                <LayoutGrid className="h-3.5 w-3.5 sm:mr-1.5 transition-colors group-hover:text-primary" />
                <span className="hidden sm:inline">Categories</span>
                <span className="sm:hidden">Main</span>
              </Button>
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

      {/* NCT Title */}
      <div className="bg-gray-50 border-b border-gray-200 px-3 sm:px-4 md:px-6 py-4">
        <div className="flex items-center gap-4">
          <Button
            onClick={() => {
              if (category) {
                router.push(`/dashboard/${category}/therapeutic-index`);
              } else {
                router.push('/dashboard');
              }
            }}
            variant="outline"
            size="sm"
            className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
            aria-label="Go back to therapeutic index"
          >
            <ArrowLeft className="mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4 transition-transform group-hover:-translate-x-0.5 group-hover:text-primary" />
            Back
          </Button>
          <div>
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
              {trials.length > 0 ? (() => {
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
              })() : 'Loading...'}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-white">
        <div className="p-6">
          {/* Critical Error Banner */}
          {error && (
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

          {/* Trials Table */}
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-gray-600">Loading abstracts and publications...</p>
              </div>
            </div>
          ) : trials.length === 0 ? (
            <Card className="border-gray-200">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <p className="text-sm text-gray-600">
                    No abstracts or publications found for {nctId}
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <TrialDataTable data={trials} showAbstractId={true} hideNctId={true} category={category || undefined} />
          )}
        </div>
      </main>
    </div>
  );
}

