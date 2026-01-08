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
import { Loader2, ChevronDown, Check, LayoutGrid } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
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

export default function TherapeuticIndexPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);
  const [sponsorFilter, setSponsorFilter] = React.useState<string>('');
  const [nctFilter, setNctFilter] = React.useState<string>('');
  const [drugFilter, setDrugFilter] = React.useState<string>('');
  const [armNameFilter, setArmNameFilter] = React.useState<string>('');
  const [trialNameFilter, setTrialNameFilter] = React.useState<string>('');
  const [phaseFilter, setPhaseFilter] = React.useState<string>('');
  const [armTypeFilter, setArmTypeFilter] = React.useState<string>('');
  const [lineOfTherapyFilter, setLineOfTherapyFilter] = React.useState<string>('all');

  const { data, isLoading, error } = useQuery({
    queryKey: ['trials', categorySlug],
    queryFn: () => trialsApi.getAll(0, 1000), // Fetch up to 1000 trials
    retry: false,
    refetchOnWindowFocus: false,
  });

  // State to store line of treatment data for each abstract
  const [lineOfTreatmentMap, setLineOfTreatmentMap] = React.useState<Map<string, string>>(new Map());
  const [loadingLineOfTreatment, setLoadingLineOfTreatment] = React.useState(false);

  // Fetch line of treatment data when filter is active
  React.useEffect(() => {
    if (lineOfTherapyFilter && lineOfTherapyFilter !== 'all' && data?.trials) {
      setLoadingLineOfTreatment(true);
      const fetchLineOfTreatment = async () => {
        const lotMap = new Map<string, string>();
        
        // First, filter trials by category
        const categoryFilteredTrials = data.trials.filter((trial: Trial) => {
          if (!trial.nct_id || !trial.nct_id.trim()) return false;
          const normalizedTrialType = normalizeCancerType(trial.cancer_type);
          const normalizedCategory = normalizeCancerType(categoryName);
          return normalizedTrialType === normalizedCategory;
        });

        // Fetch abstract details for trials that don't have cached data
        const fetchPromises = categoryFilteredTrials
          .filter(trial => trial.abstract_id && !lineOfTreatmentMap.has(trial.abstract_id))
          .slice(0, 100) // Limit to avoid overwhelming the API
          .map(async (trial) => {
            try {
              const abstractData = await trialsApi.getByAbstractId(trial.abstract_id!);
              // Extract line of treatment from arm_results
              const armResults = abstractData.arm_results || {};
              const firstArm = Object.values(armResults)[0] as { attributes?: Record<string, { value?: string }> } | undefined;
              const attributes = firstArm?.attributes || {};
              const lineOfTreatment = attributes['LINE_OF_TREATMENT']?.value || 
                                     attributes['line_of_treatment']?.value || 
                                     attributes['AttributeType.LINE_OF_TREATMENT']?.value || '';
              if (trial.abstract_id) {
                lotMap.set(trial.abstract_id, lineOfTreatment);
              }
            } catch (error) {
              console.error(`Error fetching abstract ${trial.abstract_id}:`, error);
            }
          });

        await Promise.all(fetchPromises);
        setLineOfTreatmentMap(prev => new Map([...prev, ...lotMap]));
        setLoadingLineOfTreatment(false);
      };

      fetchLineOfTreatment();
    } else {
      setLoadingLineOfTreatment(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lineOfTherapyFilter, data?.trials, categoryName]);

  // Filter trials by category - only include trials where the selected category is the primary cancer_type
  // This ensures that when filtering for "Cutaneous Squamous Cell Carcinoma", we don't see trials
  // that are primarily "Basal Cell Carcinoma" even if they have both types in their cancer_types array
  // Also filter out trials without NCT numbers
  const trials = React.useMemo(() => {
    const allTrials = data?.trials || [];
    let filtered = allTrials.filter((trial: Trial) => {
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

    // Apply phase filter if active
    if (phaseFilter && phaseFilter.trim() !== '') {
      filtered = filtered.filter((trial: Trial) => {
        // Handle phase as string, number, or undefined/null
        const trialPhase = trial.phase != null ? String(trial.phase) : '';
        const normalizedPhase = trialPhase.toLowerCase().trim();
        
        if (!normalizedPhase) {
          return false;
        }
        
        // Map UI filter values to database phase values
        // Database values are cleaned (PHASE1 -> "1", PHASE1, PHASE2 -> "1, 2", etc.)
        switch (phaseFilter) {
          case 'Early Phase 1':
            // Match "EARLY_1" or "EARLY_PHASE1" (before cleaning) or "early_phase1"
            return normalizedPhase.includes('early') && normalizedPhase.includes('1');
          
          case 'Phase 1':
            // Match "1" or combinations like "1, 2" or "2, 1"
            // Split by comma and check if "1" is in the list of phases
            const phases1 = normalizedPhase.split(',').map(p => p.trim()).filter(p => p);
            return phases1.includes('1');
          
          case 'Phase 2':
            // Match "2" or combinations like "1, 2" or "2, 3"
            const phases2 = normalizedPhase.split(',').map(p => p.trim()).filter(p => p);
            return phases2.includes('2');
          
          case 'Phase 3':
            // Match "3" or combinations like "2, 3"
            const phases3 = normalizedPhase.split(',').map(p => p.trim()).filter(p => p);
            return phases3.includes('3');
          
          case 'Phase 4':
            // Match "4" or combinations
            const phases4 = normalizedPhase.split(',').map(p => p.trim()).filter(p => p);
            return phases4.includes('4');
          
          case 'Not applicable':
            // Match "NA" or "na" or "not applicable"
            return normalizedPhase === 'na' || 
                   normalizedPhase.includes('not applicable') ||
                   normalizedPhase.includes('n/a');
          
          default:
            return false;
        }
      });
    }

    // Apply line of treatment filter if active
    if (lineOfTherapyFilter && lineOfTherapyFilter !== 'all') {
      filtered = filtered.filter((trial: Trial) => {
        if (!trial.abstract_id) return false;
        const lineOfTreatment = lineOfTreatmentMap.get(trial.abstract_id) || '';
        const normalizedLot = lineOfTreatment.toLowerCase().trim();
        
        // More precise matching to avoid substring issues (e.g., "adjuvant" matching "neoadjuvant")
        switch (lineOfTherapyFilter) {
          case 'neoadjuvant_resected':
            // Match neoadjuvant (but not adjuvant), resected, or combinations
            return normalizedLot.includes('neoadjuvant') || 
                   normalizedLot === 'resected' ||
                   normalizedLot.includes('neoadjuvant/resected') ||
                   normalizedLot.includes('neoadjuvant / resected');
          
          case 'adjuvant':
            // Match adjuvant but NOT neoadjuvant (use word boundary check)
            // Check for exact match or word boundary to avoid matching "neoadjuvant"
            if (normalizedLot.includes('neoadjuvant')) {
              return false; // Explicitly exclude neoadjuvant
            }
            return normalizedLot === 'adjuvant' || 
                   normalizedLot === 'adjuvant*' ||
                   normalizedLot.startsWith('adjuvant ') ||
                   normalizedLot.startsWith('adjuvant* ') ||
                   normalizedLot.includes(' adjuvant') ||
                   normalizedLot.includes(' adjuvant*') ||
                   normalizedLot.includes('/adjuvant') ||
                   normalizedLot.includes('/adjuvant*') ||
                   normalizedLot.includes(' / adjuvant') ||
                   normalizedLot.includes(' / adjuvant*');
          
          case 'first_line':
            return normalizedLot.includes('first line') || 
                   normalizedLot.includes('first-line') ||
                   normalizedLot === '1l' ||
                   normalizedLot.startsWith('1l+') ||
                   normalizedLot === 'first' ||
                   normalizedLot.includes('1st line') ||
                   normalizedLot.includes('1st-line');
          
          case 'second_line':
            return normalizedLot.includes('second line') || 
                   normalizedLot.includes('second-line') ||
                   normalizedLot === '2l' ||
                   normalizedLot.startsWith('2l+') ||
                   normalizedLot === 'second' ||
                   normalizedLot.includes('2nd line') ||
                   normalizedLot.includes('2nd-line');
          
          case 'third_line_plus':
            return normalizedLot.includes('third line') || 
                   normalizedLot.includes('third-line') ||
                   normalizedLot === '3l' ||
                   normalizedLot.startsWith('3l+') ||
                   normalizedLot === 'third' ||
                   normalizedLot.includes('fourth') ||
                   normalizedLot.includes('fifth') ||
                   normalizedLot.includes('later') ||
                   normalizedLot.includes('3rd line') ||
                   normalizedLot.includes('3rd-line') ||
                   normalizedLot.includes('4th') ||
                   normalizedLot.includes('5th');
          
          default:
            return false;
        }
      });
    }

    return filtered;
  }, [data?.trials, categoryName, phaseFilter, lineOfTherapyFilter, lineOfTreatmentMap]);

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
        {/* Left Sidebar - Navigation Only */}
        <aside className="w-[280px] border-r border-gray-200 bg-gray-50/50 p-4 shrink-0 overflow-y-auto">
          <nav className="space-y-1">
            <Link
              href={`/dashboard/${categorySlug}/disease-landscape`}
              className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Disease Landscape
            </Link>
            <Link
              href={`/dashboard/${categorySlug}/therapeutic-index`}
              className="block px-3 py-2 text-sm font-medium text-orange-600 bg-orange-50 rounded-md"
            >
              Therapeutic Index
            </Link>
            <Link
              href={`/dashboard/${categorySlug}/analytics`}
              className="block px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md ml-6 border-l-2 border-gray-300 hover:border-orange-400 transition-colors"
            >
              Comparative Analytics
            </Link>
            <div className="block px-3 py-2 text-sm font-medium text-gray-500">
              &quot;Live&quot; Ticker
              <span className="ml-2 text-xs text-gray-400">Upcoming</span>
            </div>
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

        {/* Right Panel - Filters + Table */}
        <main className="flex-1 flex flex-col overflow-hidden bg-white">
          {/* Filters Bar - Top */}
          <div className="border-b border-gray-200 bg-gray-50/50 px-4 py-3">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-4 gap-3">
              {/* Drug/Intervention */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Drug/Intervention</label>
                <Input
                  placeholder="Search..."
                  value={drugFilter}
                  onChange={(e) => setDrugFilter(e.target.value)}
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </div>

              {/* Arm Name/Label */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Arm Name/Label</label>
                <Input
                  placeholder="Search..."
                  value={armNameFilter}
                  onChange={(e) => setArmNameFilter(e.target.value)}
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </div>

              {/* Trial ID (NCT) */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Trial ID (NCT)</label>
                <Input
                  placeholder="Search..."
                  value={nctFilter}
                  onChange={(e) => setNctFilter(e.target.value)}
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </div>

              {/* Trial Name/Acronym */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Trial Name/Acronym</label>
                <Input
                  placeholder="Search..."
                  value={trialNameFilter}
                  onChange={(e) => setTrialNameFilter(e.target.value)}
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </div>

              {/* Arm Type */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Arm Type</label>
                <Input
                  placeholder="Search..."
                  value={armTypeFilter}
                  onChange={(e) => setArmTypeFilter(e.target.value)}
                  className="text-xs h-8 border-gray-300 focus:border-primary focus:ring-primary/20"
                />
              </div>

              {/* Phase */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Phase</label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className={`flex h-8 items-center justify-between rounded-md border bg-white px-3 py-1.5 text-xs text-gray-900 shadow-sm transition-all hover:border-gray-400 focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 ${
                        phaseFilter 
                          ? 'border-primary/50' 
                          : 'border-gray-300'
                      }`}
                    >
                      <span className="text-left">
                        {phaseFilter || 'All'}
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
                        phaseFilter === '' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setPhaseFilter('')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>All</span>
                        {phaseFilter === '' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    {['Early Phase 1', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4', 'Not applicable'].map((phase) => (
                      <DropdownMenuItem
                        key={phase}
                        className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                          phaseFilter === phase 
                            ? 'bg-blue-50 text-primary font-medium' 
                            : 'text-gray-700 hover:bg-gray-100'
                        }`}
                        onClick={() => setPhaseFilter(phase)}
                      >
                        <div className="flex items-center justify-between w-full">
                          <span>{phase}</span>
                          {phaseFilter === phase && (
                            <Check className="h-3.5 w-3.5 text-primary ml-2" />
                          )}
                        </div>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Line of Treatment */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Line of Treatment</label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className={`flex h-8 items-center justify-between rounded-md border bg-white px-3 py-1.5 text-xs text-gray-900 shadow-sm transition-all hover:border-gray-400 focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 ${
                        lineOfTherapyFilter !== 'all' 
                          ? 'border-primary/50' 
                          : 'border-gray-300'
                      }`}
                    >
                      <span className="text-left">
                        {lineOfTherapyFilter === 'all' 
                          ? 'All' 
                          : lineOfTherapyFilter === 'neoadjuvant_resected'
                          ? 'Neoadjuvant / Resected'
                          : lineOfTherapyFilter === 'adjuvant'
                          ? 'Adjuvant'
                          : lineOfTherapyFilter === 'first_line'
                          ? 'First Line'
                          : lineOfTherapyFilter === 'second_line'
                          ? 'Second Line'
                          : lineOfTherapyFilter === 'third_line_plus'
                          ? 'Third Line plus'
                          : lineOfTherapyFilter}
                      </span>
                      <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent 
                    align="start" 
                    className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[10rem] p-1"
                    sideOffset={4}
                  >
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        lineOfTherapyFilter === 'all' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setLineOfTherapyFilter('all')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>All</span>
                        {lineOfTherapyFilter === 'all' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        lineOfTherapyFilter === 'neoadjuvant_resected' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setLineOfTherapyFilter('neoadjuvant_resected')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>Neoadjuvant / Resected</span>
                        {lineOfTherapyFilter === 'neoadjuvant_resected' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        lineOfTherapyFilter === 'adjuvant' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setLineOfTherapyFilter('adjuvant')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>Adjuvant</span>
                        {lineOfTherapyFilter === 'adjuvant' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        lineOfTherapyFilter === 'first_line' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setLineOfTherapyFilter('first_line')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>First Line</span>
                        {lineOfTherapyFilter === 'first_line' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        lineOfTherapyFilter === 'second_line' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setLineOfTherapyFilter('second_line')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>Second Line</span>
                        {lineOfTherapyFilter === 'second_line' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className={`text-xs cursor-pointer rounded-md px-2 py-1.5 ${
                        lineOfTherapyFilter === 'third_line_plus' 
                          ? 'bg-blue-50 text-primary font-medium' 
                          : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      onClick={() => setLineOfTherapyFilter('third_line_plus')}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>Third Line plus</span>
                        {lineOfTherapyFilter === 'third_line_plus' && (
                          <Check className="h-3.5 w-3.5 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Sponsor */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700">Sponsor</label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className={`flex h-8 items-center justify-between rounded-md border bg-white px-3 py-1.5 text-xs text-gray-900 shadow-sm transition-all hover:border-gray-400 focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 ${
                        sponsorFilter 
                          ? 'border-primary/50' 
                          : 'border-gray-300'
                      }`}
                    >
                      <span className="text-left">
                        {sponsorFilter === 'industry' 
                          ? 'Industry' 
                          : sponsorFilter === 'non-industry' 
                          ? 'Non-Industry' 
                          : 'All'}
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
                        <span>All</span>
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
              </div>
            </div>
          </div>

          {/* Table Content */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 sm:p-6">
            {isLoading || loadingLineOfTreatment ? (
              <div className="flex items-center justify-center py-12">
                <div className="flex flex-col items-center gap-4">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <p className="text-sm text-gray-600">
                    {loadingLineOfTreatment ? 'Loading line of treatment data...' : 'Loading trials...'}
                  </p>
                </div>
              </div>
            ) : error ? (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="pt-6">
                  <p className="text-sm text-red-800 text-center">
                    Error loading trials. Please try again later.
                  </p>
                </CardContent>
              </Card>
            ) : trials.length === 0 ? (
              <Card>
                <CardContent className="pt-6">
                  <p className="text-sm text-gray-600 text-center">
                    No trials found for {categoryName}.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <TrialDataTable
                data={trials}
                nctFilter={nctFilter}
                sponsorFilter={sponsorFilter}
                drugFilter={drugFilter}
                armNameFilter={armNameFilter}
                trialNameFilter={trialNameFilter}
                armTypeFilter={armTypeFilter}
                lineOfTherapyFilter={lineOfTherapyFilter}
              />
            )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

