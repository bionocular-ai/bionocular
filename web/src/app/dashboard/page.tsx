'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { UserMenu } from '@/components/user-menu';
import { CancerTypeBubbles } from '@/components/dashboard/CancerTypeBubbles';
import { trialsApi } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';


export default function DashboardPage() {
  const { data: session } = useSession();

  const { data, isLoading, error } = useQuery({
    queryKey: ['landscape-stats'],
    queryFn: () => trialsApi.getLandscapeStats(),
    retry: false,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="flex flex-col min-h-screen w-full bg-white overflow-hidden">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shrink-0 shadow-sm backdrop-blur-sm bg-white/95">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 sm:h-16 gap-3">
            <Link href="/" className="brand flex-shrink-0 hover:opacity-80 transition-opacity">
              <Logo height={32} />
              <span className="brand-text dashboard-brand-text">
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
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

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-gradient-to-br from-slate-50 via-white to-blue-50 overscroll-none">
        <div className="container mx-auto px-3 sm:px-4 md:px-6 lg:px-8 py-3 sm:py-4 md:py-6 lg:py-8 max-w-7xl h-full flex flex-col min-h-[calc(100vh-3.5rem)] sm:min-h-[calc(100vh-4rem)]">
          {/* Page Header */}
          <div className="mb-3 sm:mb-4 md:mb-6 text-center shrink-0 px-2">
            <h1 className="text-[1.375rem] min-[400px]:text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-2 sm:mb-3 tracking-tight leading-tight">
              Skin Cancer Ecosystem
            </h1>
            <p className="text-[0.8125rem] min-[400px]:text-sm sm:text-base md:text-lg text-gray-500 max-w-2xl mx-auto px-2 sm:px-4">
              Explore clinical trials by cancer type
            </p>
          </div>

          {/* Error Banner */}
          {error && (
            <Card className="border-yellow-200 bg-yellow-50 mb-3 sm:mb-4 md:mb-6 mx-2 sm:mx-0">
              <CardContent className="pt-4 sm:pt-6 pb-4 sm:pb-6">
                <div className="flex items-start gap-2 sm:gap-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-yellow-800 mb-1 text-xs sm:text-sm">
                      Backend Unavailable
                    </h3>
                    <p className="text-xs text-yellow-700">
                      Unable to connect to the backend API. Please ensure the backend is running.
                    </p>
                    {error instanceof Error && (
                      <p className="text-xs text-yellow-600 mt-1 sm:mt-2 break-words">
                        Error: {error.message}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Loading State */}
          <div className="flex-1 flex items-center justify-center min-h-0 overflow-hidden">
            {isLoading ? (
              <div className="flex flex-col items-center gap-3 sm:gap-4">
                <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-primary" />
                <p className="text-xs sm:text-sm text-gray-600">Loading landscape data...</p>
              </div>
            ) : error ? (
              <Card className="mx-4 max-w-md">
                <CardContent className="pt-6 pb-6">
                  <p className="text-xs sm:text-sm text-red-600 text-center break-words">
                    Error loading landscape data: {error instanceof Error ? error.message : 'Unknown error'}
                  </p>
                </CardContent>
              </Card>
            ) : data?.landscape ? (
              <CancerTypeBubbles stats={data.landscape} />
            ) : (
              <Card className="mx-4 max-w-md">
                <CardContent className="pt-6 pb-6">
                  <p className="text-xs sm:text-sm text-gray-600 text-center">
                    No landscape data available. Please run the sync script to populate data.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
