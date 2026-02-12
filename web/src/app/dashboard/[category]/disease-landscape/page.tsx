'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { useParams, useRouter, usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { UserMenu } from '@/components/user-menu';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, LayoutGrid } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { trialsApi, DiseaseLandscapeStats } from '@/lib/api';

// Mapping of slugs to category names
const CATEGORY_SLUG_MAP: Record<string, string> = {
  'cutaneous-melanoma': 'Cutaneous melanoma',
  'cutaneous-melanoma-with-brain-cns-metastasis': 'Cutaneous melanoma with Brain/CNS metastasis',
  'uveal-melanoma': 'Uveal Melanoma',
  'mucosal-melanoma': 'Mucosal Melanoma',
  'acral-melanoma': 'Acral Melanoma',
  'basal-cell-carcinoma': 'Basal Cell Carcinoma',
  'merkel-cell-carcinoma': 'Merkel Cell Carcinoma',
  'cutaneous-squamous-cell-carcinoma': 'Cutaneous Squamous Cell Carcinoma',
};

function slugToCategory(slug: string): string {
  return CATEGORY_SLUG_MAP[slug] || slug
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export default function DiseaseLandscapePage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const pathname = usePathname();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);
  const isTherapeuticIndexPage = pathname?.includes('/therapeutic-index');
  const [showNavigationBars, setShowNavigationBars] = React.useState(false);

  const { data: stats, isLoading, error } = useQuery<DiseaseLandscapeStats>({
    queryKey: ['disease-landscape-stats', categorySlug],
    queryFn: () => trialsApi.getDiseaseLandscapeStats(categorySlug),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  return (
    <div className="flex flex-col min-h-screen w-full bg-white">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shrink-0">
        <div className="w-full px-3 sm:px-4 md:px-6">
          <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
            <Link href="/" className="brand flex-shrink-0">
              <Logo height={32} />
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

      {/* Category Title */}
      <div className="bg-gray-50 border-b border-gray-200 px-3 sm:px-4 md:px-6 py-4">
        <h1 className="text-xl sm:text-2xl font-semibold text-gray-900">
          {categoryName}
        </h1>
      </div>

      {/* Main Content - Sidebar + Statistics */}
      <div className="flex flex-1 w-full overflow-hidden">
        {/* Left Sidebar - Navigation */}
        <aside className="w-[280px] border-r border-gray-200 bg-gray-50/50 p-4 shrink-0 overflow-y-auto">
          <nav className="space-y-1">
            <Link
              href={`/dashboard/${categorySlug}/disease-landscape`}
              className="block px-3 py-2 text-sm font-medium text-orange-600 bg-orange-50 rounded-md"
            >
              Disease Landscape
            </Link>
            <Link
              href={`/dashboard/${categorySlug}/analytics?mode=efficacy`}
              className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Head to Head Efficacy
            </Link>
            <Link
              href={`/dashboard/${categorySlug}/analytics?mode=safety`}
              className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Head to Head Safety
            </Link>
            <div>
              <Link
                href={`/dashboard/${categorySlug}/therapeutic-index`}
                className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
              >
                Head to Head Efficacy : Safety
              </Link>
              {isTherapeuticIndexPage && (
                <Link
                  href={`/dashboard/${categorySlug}/analytics`}
                  className="block px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md ml-6 border-l-2 border-gray-300 hover:border-orange-400 transition-colors"
                >
                  Efficacy : Safety Therapeutic Index
                </Link>
              )}
            </div>
            <Link
              href={`/dashboard/${categorySlug}/live-ticker`}
              className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Live Ticker
            </Link>
            <div className="block px-3 py-2 text-sm font-medium text-gray-500">
              AI Chatbot
              <span className="ml-2 text-xs text-gray-400">Upcoming</span>
            </div>
            <div className="block px-3 py-2 text-sm font-medium text-gray-500">
              Regulatory Milestone
              <span className="ml-2 text-xs text-gray-400">Upcoming</span>
            </div>
          </nav>
        </aside>

        {/* Right Panel - Statistics */}
        <main className="flex-1 overflow-y-auto bg-white">
          <div className="p-6">
            <h2 className="text-3xl font-light text-gray-400 mb-6" style={{ letterSpacing: '0.05em' }}>
              Clinical trials
            </h2>
            
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : error ? (
              <div className="text-center py-12">
                <p className="text-red-600">Error loading statistics. Please try again later.</p>
              </div>
            ) : stats ? (
              <div className="space-y-6">
                {/* Calculate consistent max value across all sections */}
                {(() => {
                  const overallStatusCount = stats.status['Overall Status'] || 0;
                  const maxPhaseValue = Math.max(...Object.values(stats.phase));
                  const maxFunderValue = Math.max(...Object.values(stats.funder_type));
                  const globalMax = Math.max(overallStatusCount, maxPhaseValue, maxFunderValue);
                  
                  return (
                    <>
                      {/* Status */}
                      <Card className="border-blue-200">
                        <CardContent className="pt-6">
                          <h3 className="text-sm font-semibold text-gray-900 mb-4">Status</h3>
                          <div className="space-y-2">
                            {Object.entries(stats.status).map(([key, value]) => {
                              const percentage = globalMax > 0 ? (value / globalMax) * 100 : 0;
                              const isOverallStatus = key === 'Overall Status';
                              const extractedCount = stats.extracted_count || 0;
                              const extractedPercentage = globalMax > 0 ? (extractedCount / globalMax) * 100 : 0;
                        
                        return (
                          <div key={key} className="flex items-center gap-3">
                            <span className="text-sm text-gray-700 whitespace-nowrap">
                              {key} <span className="font-medium text-gray-900">({value})</span>
                            </span>
                            {isOverallStatus && extractedCount > 0 ? (
                              <div className="flex-1 relative">
                                {/* Navigation bars - shown above when clicked, positioned absolutely */}
                                {showNavigationBars && (
                                  <div className="absolute bottom-full left-0 mb-2 flex gap-2 z-10" style={{ width: `${extractedPercentage}%` }}>
                                    <button
                                      onClick={() => router.push(`/dashboard/${categorySlug}/analytics?mode=efficacy`)}
                                      className="h-6 bg-blue-500 rounded-md transition-all duration-300 hover:bg-blue-600 cursor-pointer flex items-center justify-center text-xs text-white font-medium px-3 whitespace-nowrap"
                                    >
                                      Head to Head Efficacy
                                    </button>
                                    <button
                                      onClick={() => router.push(`/dashboard/${categorySlug}/analytics?mode=safety`)}
                                      className="h-6 bg-blue-500 rounded-md transition-all duration-300 hover:bg-blue-600 cursor-pointer flex items-center justify-center text-xs text-white font-medium px-3 whitespace-nowrap"
                                    >
                                      Head to Head Safety
                                    </button>
                                    <button
                                      onClick={() => router.push(`/dashboard/${categorySlug}/therapeutic-index`)}
                                      className="h-6 bg-blue-500 rounded-md transition-all duration-300 hover:bg-blue-600 cursor-pointer flex items-center justify-center text-xs text-white font-medium px-3 whitespace-nowrap"
                                    >
                                      Head to Head Efficacy : Safety
                                    </button>
                                  </div>
                                )}
                                <div className="relative h-6">
                                  {/* Outer bar (Overall Status) */}
                                  <div
                                    className="absolute h-6 bg-gray-400 rounded-md transition-all duration-300"
                                    style={{ width: `${percentage}%` }}
                                  />
                                  {/* Inner bar (Extracted count) - Clickable */}
                                  <button
                                    onClick={() => setShowNavigationBars(!showNavigationBars)}
                                    className="absolute h-6 bg-blue-500 rounded-md transition-all duration-300 hover:bg-blue-600 cursor-pointer"
                                    style={{ width: `${extractedPercentage}%` }}
                                    title={`View ${extractedCount} therapeutic index trials`}
                                  />
                                </div>
                              </div>
                            ) : (
                              <div
                                className="h-6 bg-gray-400 rounded-md transition-all duration-300"
                                style={{ width: `${percentage}%` }}
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Phase */}
                <Card className="border-blue-200">
                  <CardContent className="pt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-4">Phase</h3>
                    <div className="space-y-2">
                      {Object.entries(stats.phase).map(([key, value]) => {
                        const percentage = globalMax > 0 ? (value / globalMax) * 100 : 0;
                        return (
                          <div key={key} className="flex items-center gap-3">
                            <span className="text-sm text-gray-700 whitespace-nowrap">
                              {key} <span className="font-medium text-gray-900">({value})</span>
                            </span>
                            <div
                              className="h-6 bg-gray-400 rounded-md transition-all duration-300"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Funder Type */}
                <Card className="border-blue-200 rounded-tl-lg rounded-tr-lg">
                  <CardContent className="pt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-4">Funder Type</h3>
                    <div className="space-y-2">
                      {Object.entries(stats.funder_type).map(([key, value]) => {
                        const percentage = globalMax > 0 ? (value / globalMax) * 100 : 0;
                        return (
                          <div key={key} className="flex items-center gap-3">
                            <span className="text-sm text-gray-700 whitespace-nowrap">
                              {key} <span className="font-medium text-gray-900">({value})</span>
                            </span>
                            <div
                              className="h-6 bg-gray-400 rounded-md transition-all duration-300"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
                    </>
                  );
                })()}
              </div>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  );
}

