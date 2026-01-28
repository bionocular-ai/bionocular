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


export default function TherapeuticIndexPage() {
  const { data: session } = useSession();

  const { data, isLoading, error } = useQuery({
    queryKey: ['landscape-stats'],
    queryFn: () => trialsApi.getLandscapeStats(),
    retry: false,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="flex flex-col min-h-screen w-full bg-white">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shrink-0">
        <div className="w-full px-3 sm:px-4 md:px-6">
          <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
            <Link href="/" className="brand flex-shrink-0">
              <Logo height={36} />
              <span className="brand-text" style={{ lineHeight: '1.2' }}>
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
      <main className="flex-1 overflow-hidden bg-gradient-to-br from-slate-50 via-white to-blue-50">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 max-w-6xl h-full flex flex-col">
          {/* Page Header */}
          <div className="mb-4 sm:mb-6 text-center shrink-0">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-gray-900 mb-3 tracking-tight">
              Skin Cancer Ecosystem
            </h1>
            <p className="text-base sm:text-lg text-gray-500 max-w-2xl mx-auto">
              Explore clinical trials by cancer type
            </p>
          </div>

          {/* Error Banner */}
          {error && (
            <Card className="border-yellow-200 bg-yellow-50 mb-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-yellow-800 mb-1 text-sm">
                      Backend Unavailable
                    </h3>
                    <p className="text-xs text-yellow-700">
                      Unable to connect to the backend API. Please ensure the backend is running.
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

          {/* Loading State */}
          <div className="flex-1 flex items-center justify-center min-h-0 overflow-hidden">
            {isLoading ? (
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-gray-600">Loading landscape data...</p>
              </div>
            ) : data?.landscape ? (
              <CancerTypeBubbles stats={data.landscape} />
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <p className="text-sm text-gray-600 text-center">
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

