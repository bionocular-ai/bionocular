'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { useParams, useRouter } from 'next/navigation';
import { TrialDataTable } from '@/components/dashboard/TrialDataTable';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { UserMenu } from '@/components/user-menu';
import { trialsApi, Trial } from '@/lib/api';
import { Loader2, ChevronDown, Check, LayoutGrid, BarChart3, ArrowRight } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

// Mapping of slugs to category names for accurate conversion
const CATEGORY_SLUG_MAP: Record<string, string> = {
  'cutaneous-melanoma': 'Cutaneous melanoma',
  'cutaneous-melanoma-with-brain-cns-metastasis': 'Cutaneous melanoma with Brain/CNS metastasis',
  'uveal-melanoma': 'Uveal Melanoma',
  'mucosal-melanoma': 'Mucosal Melanoma',
  'acral-melanoma': 'Acral Melanoma',
  'basal-cell-carcinoma': 'Basal Cell Carcinoma',
  'merkel-cell-carcinoma': 'Merkel Cell Carcinoma',
  'cutaneous-squamous-cell-carcinoma': 'Cutaneous Squamous Cell Carcinoma',
  // Legacy slugs for backward compatibility
  'resected-cutaneous-melanoma': 'Cutaneous melanoma',
  'unresectable-cutaneous-melanoma': 'Cutaneous melanoma',
  'cutaneous-melanoma-with-brain-metastasis': 'Cutaneous melanoma with Brain/CNS metastasis',
  'cutaneous-melanoma-with-cns-metastasis': 'Cutaneous melanoma with Brain/CNS metastasis',
};

// Normalize cancer type names to handle legacy data
function normalizeCancerType(cancerType: string | null | undefined): string | null {
  if (!cancerType) return null;
  const normalized = cancerType.trim();
  
  // Map old names to new names
  if (normalized === 'Resected Cutaneous Melanoma' || normalized === 'Unresectable Cutaneous Melanoma') {
    return 'Cutaneous melanoma';
  }
  if (normalized === 'Cutaneous melanoma with Brain metastasis' || 
      normalized === 'Cutaneous Melanoma with CNS metastasis' ||
      normalized === 'Cutaneous melanoma with Brain/CNS metastasis') {
    return 'Cutaneous melanoma with Brain/CNS metastasis';
  }
  
  return normalized;
}

// Helper function to convert slug back to category name
function slugToCategory(slug: string): string {
  return CATEGORY_SLUG_MAP[slug] || slug
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export default function CategoryDashboardPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);
  const [sponsorFilter, setSponsorFilter] = React.useState<string>('');
  const [nctFilter, setNctFilter] = React.useState<string>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['trials', categorySlug],
    queryFn: () => trialsApi.getAll(0, 1000), // Fetch up to 1000 trials
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Filter trials by category - only include trials where the selected category is the primary cancer_type
  // This ensures that when filtering for "Cutaneous Squamous Cell Carcinoma", we don't see trials
  // that are primarily "Basal Cell Carcinoma" even if they have both types in their cancer_types array
  // Also filter out trials without NCT numbers
  const trials = React.useMemo(() => {
    const allTrials = data?.trials || [];
    return allTrials.filter((trial: Trial) => {
      // Filter out trials without NCT numbers
      if (!trial.nct_id || !trial.nct_id.trim()) {
        return false;
      }
      
      // Normalize both the trial's cancer type and the selected category for comparison
      const normalizedTrialType = normalizeCancerType(trial.cancer_type);
      const normalizedCategory = normalizeCancerType(categoryName);
      
      // Strict filtering: only match if the primary cancer_type matches the selected category
      // This ensures we only see trials that are primarily for the selected cancer type
      return normalizedTrialType === normalizedCategory;
    });
  }, [data?.trials, categoryName]);

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

      {/* Category Title */}
      <div className="bg-gray-50 border-b border-gray-200 px-3 sm:px-4 md:px-6 py-4">
        <h1 className="text-xl sm:text-2xl font-semibold text-gray-900">
          {categoryName}
        </h1>
      </div>

      {/* Main Content - Sidebar + Table Layout */}
      <div className="flex flex-1 w-full overflow-hidden">
        {/* Left Sidebar - Filters */}
        <aside className="w-[280px] border-r border-gray-200 bg-gray-50/50 p-4 shrink-0 overflow-y-auto">
          <div className="mb-3">
            <h2 className="text-xs font-semibold text-gray-900 mb-0.5">Filters</h2>
            <p className="text-xs text-gray-500">Filter trials by criteria</p>
          </div>
          <Accordion type="multiple" className="w-full" defaultValue={[]}>
            <AccordionItem value="drug" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Drug/Intervention
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="arm" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Arm Name/Label
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="trial-id" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Trial ID (NCT)
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  value={nctFilter}
                  onChange={(e) => setNctFilter(e.target.value)}
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="trial-name" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Trial Name/Acronym
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="arm-type" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Arm Type
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="phase" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Phase
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="line-of-therapy" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Line of Therapy
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <Input
                  placeholder="Search..."
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="sponsor" className="border-b border-gray-200">
              <AccordionTrigger className="text-xs font-medium py-2.5 hover:no-underline">
                Sponsor
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2.5">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className={`flex h-8 w-full items-center justify-between rounded-md border bg-white px-3 py-1.5 text-xs text-gray-900 shadow-sm transition-all hover:border-gray-400 focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 ${
                        sponsorFilter 
                          ? 'border-primary/50' 
                          : 'border-gray-300'
                      }`}
                      style={{ outline: 'none' }}
                      onBlur={(e) => {
                        e.currentTarget.style.outline = 'none';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <span className="text-left">
                        {sponsorFilter === 'industry' 
                          ? 'Industry' 
                          : sponsorFilter === 'non-industry' 
                          ? 'Non-Industry' 
                          : 'All Sponsors'}
                      </span>
                      <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent 
                    align="start" 
                    className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[8rem] p-1"
                    sideOffset={4}
                  >
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        sponsorFilter === '' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setSponsorFilter('')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>All Sponsors</span>
                        {sponsorFilter === '' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        sponsorFilter === 'industry' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setSponsorFilter('industry')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>Industry</span>
                        {sponsorFilter === 'industry' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        sponsorFilter === 'non-industry' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setSponsorFilter('non-industry')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>Non-Industry</span>
                        {sponsorFilter === 'non-industry' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {/* Comparative Analytics Link */}
          <div className="mt-6 pt-4 border-t border-gray-200">
            <Link href={`/dashboard/${categorySlug}/analytics`}>
              <div className="group relative overflow-hidden rounded-lg bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 p-4 transition-all duration-200 hover:shadow-md hover:border-blue-300 hover:from-blue-100 hover:to-indigo-100 cursor-pointer">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg shadow-sm">
                    <BarChart3 className="h-4 w-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-gray-900 group-hover:text-blue-700 transition-colors">
                      Comparative Analytics
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Compare efficacy & safety metrics across treatments
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-gray-400 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all flex-shrink-0 mt-1" />
                </div>
              </div>
            </Link>
          </div>
        </aside>

        {/* Right Content - Table */}
        <main className="flex-1 overflow-auto bg-white">
          <div className="p-6">
            {/* Critical Error Banner (only for critical errors) */}
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

            {/* Trials Table - No Card wrapper */}
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="flex flex-col items-center gap-4">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <p className="text-sm text-gray-600">Loading trials...</p>
                  </div>
                </div>
              ) : (
            <TrialDataTable data={trials} nctFilter={nctFilter} sponsorFilter={sponsorFilter} />
              )}
          </div>
        </main>
      </div>
    </div>
  );
}

