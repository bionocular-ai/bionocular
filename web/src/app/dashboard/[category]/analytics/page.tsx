'use client';

import * as React from 'react';
import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import {
  ChevronDown,
  Check,
  X,
  FileSpreadsheet,
  Presentation,
  FileText,
  TrendingUp,
  Minus,
  Maximize2,
  Minimize2,
  Search,
  Loader2,
  AlertCircle,
  BarChart3,
  CircleDot,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { UserMenu } from '@/components/user-menu';
import BarChart from '@/components/charts/BarChart';
import DivergingBarChart from '@/components/charts/DivergingBarChart';
import BubbleChart from '@/components/charts/BubbleChart';
import DumbbellChart, { DumbbellDataPoint } from '@/components/charts/DumbbellChart';
import { transformHeadToHeadData, transformEfficacySafetyData, transformBubbleChartData } from '@/lib/chart-transformers';
import { analyticsApi } from '@/lib/api';
import { HeadToHeadDataPoint, ChartMetric, TrialDataFile, EfficacySafetyDataPoint, BubbleChartDataPoint } from '@/types/analytics';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { DashboardGlobalHeader } from '@/components/dashboard/DashboardGlobalHeader';

// ============================================================================
// Category Mapping
// ============================================================================

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

function slugToCategory(slug: string): string {
  return CATEGORY_SLUG_MAP[slug] || slug.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

// ============================================================================
// Filter Options
// ============================================================================

const COMPANY_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'bms', label: 'Bristol-Myers Squibb' },
  { value: 'merck', label: 'Merck' },
  { value: 'novartis', label: 'Novartis' },
  { value: 'roche', label: 'Roche' },
  { value: 'pfizer', label: 'Pfizer' },
];

// Note: Funding type filtering is now handled by the backend API

const THERAPY_TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'Immunotherapy', label: 'Immunotherapy' },
  { value: 'Cellular therapy', label: 'Cellular therapy' },
  { value: 'Targeted Therapy', label: 'Targeted Therapy' },
  { value: 'Oncolytic Virus', label: 'Oncolytic Virus' },
  { value: 'Chemotherapy', label: 'Chemotherapy' },
];

const LINE_OF_TREATMENT_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'neoadjuvant_resected', label: 'Neoadjuvant / Resected' },
  { value: 'adjuvant', label: 'Adjuvant' },
  { value: 'first_line', label: 'First Line' },
  { value: 'second_line', label: 'Second Line' },
  { value: 'third_line_plus', label: 'Third Line plus' },
];

const RESOURCE_TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'conference', label: 'Conference' },
  { value: 'publication', label: 'Publications' },
];

const FUNDING_TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'industry', label: 'Industry' },
  { value: 'non-industry', label: 'Non-Industry' },
];

const BIOMARKER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
];

const BIOMARKER_TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'BRAF', label: 'BRAF V600' },
  { value: 'PDL1', label: 'PD-L1' },
  { value: 'TMB', label: 'TMB' },
  { value: 'MSI', label: 'MSI-H' },
];

const EFFICACY_OPTIONS = [
  { value: 'none', label: 'None' },
  // Survival - PFS
  { value: 'MEDIAN_PFS', label: 'Median PFS (months)' },
  { value: 'MEDIAN_FOLLOWUP_PFS', label: 'Median PFS Follow-up' },
  // Survival - OS
  { value: 'MEDIAN_OS', label: 'Median OS (months)' },
  { value: 'MEDIAN_FOLLOWUP_OS', label: 'Median OS Follow-up' },
  // Hazard ratios (for bubble X/Y)
  { value: 'HR_PFS', label: 'HR (PFS)' },
  { value: 'HR_OS', label: 'HR (OS)' },
  { value: 'HR_EFS', label: 'HR (EFS)' },
  { value: 'HR_RFS', label: 'HR (RFS)' },
  { value: 'HR_MFS', label: 'HR (MFS)' },
  // Response Rates
  { value: 'OBJECTIVE_RESPONSE_RATE', label: 'ORR (%)' },
  { value: 'COMPLETE_RESPONSE', label: 'Complete Response (%)' },
  { value: 'PATHOLOGICAL_COMPLETE_RESPONSE', label: 'Pathological CR (%)' },
  { value: 'COMPLETE_METABOLIC_RESPONSE', label: 'Complete Metabolic Response (%)' },
  { value: 'DISEASE_CONTROL_RATE', label: 'Disease Control Rate (%)' },
  { value: 'CLINICAL_BENEFIT_RATE', label: 'Clinical Benefit Rate (%)' },
  { value: 'MEDIAN_DOR', label: 'Median DOR (months)' },
  { value: 'DOR_RATE', label: 'DOR Rate (%)' },
  // PFS Rates
  { value: 'PFS_RATE_6M', label: 'PFS Rate 6mo (%)' },
  { value: 'PFS_RATE_9M', label: 'PFS Rate 9mo (%)' },
  { value: 'PFS_RATE_12M', label: 'PFS Rate 12mo (%)' },
  { value: 'PFS_RATE_18M', label: 'PFS Rate 18mo (%)' },
  { value: 'PFS_RATE_24M', label: 'PFS Rate 24mo (%)' },
  { value: 'PFS_RATE_36M', label: 'PFS Rate 36mo (%)' },
  { value: 'PFS_RATE_48M', label: 'PFS Rate 48mo (%)' },
  // OS Rates
  { value: 'OS_RATE_6M', label: 'OS Rate 6mo (%)' },
  { value: 'OS_RATE_9M', label: 'OS Rate 9mo (%)' },
  { value: 'OS_RATE_12M', label: 'OS Rate 12mo (%)' },
  { value: 'OS_RATE_18M', label: 'OS Rate 18mo (%)' },
  { value: 'OS_RATE_24M', label: 'OS Rate 24mo (%)' },
  { value: 'OS_RATE_36M', label: 'OS Rate 36mo (%)' },
  { value: 'OS_RATE_48M', label: 'OS Rate 48mo (%)' },
  // Other Survival
  { value: 'EFS', label: 'Event-Free Survival' },
  { value: 'RFS', label: 'Recurrence-Free Survival' },
  { value: 'LENGTH_RFS', label: 'RFS Follow-up Length' },
  { value: 'MFS', label: 'Metastasis-Free Survival' },
  { value: 'LENGTH_MFS', label: 'MFS Follow-up Length' },
  // Time Metrics
  { value: 'TTR', label: 'Time to Response' },
  { value: 'TTP', label: 'Time to Progression' },
  { value: 'TTNT', label: 'Time to Next Treatment' },
  { value: 'TTF', label: 'Time to Treatment Failure' },
];

// Patient count options will be generated dynamically from data

const SAFETY_OPTIONS = [
  { value: 'none', label: 'None' },
  // General AE
  { value: 'AE', label: 'AE (%)' },
  { value: 'GRADE_3_PLUS_AE', label: 'Grade ≥3 AE (%)' },
  { value: 'AE_LEADING_TO_DISCONTINUATION', label: 'AE Discontinuation (%)' },
  { value: 'SERIOUS_AE', label: 'Serious AE (%)' },
  { value: 'IMMUNE_RELATED_AE', label: 'Immune-related AE (%)' },
  { value: 'SERIOUS_IMMUNE_RELATED_AE', label: 'Serious Immune-related AE (%)' },
  { value: 'AE_LEADING_TO_DEATH', label: 'AE Death (%)' },
  // TEAE
  { value: 'TEAE', label: 'TEAE (%)' },
  { value: 'GRADE_3_PLUS_TEAE', label: 'Grade ≥3 TEAE (%)' },
  { value: 'GRADE_3_TEAE', label: 'Grade 3 TEAE (%)' },
  { value: 'GRADE_4_TEAE', label: 'Grade 4 TEAE (%)' },
  { value: 'GRADE_5_TEAE', label: 'Grade 5 TEAE (%)' },
  { value: 'TEAE_LEADING_TO_DISCONTINUATION', label: 'TEAE Discontinuation (%)' },
  { value: 'TEAE_LEADING_TO_DEATH', label: 'TEAE Death (%)' },
  { value: 'SERIOUS_TEAE', label: 'Serious TEAE (%)' },
  { value: 'TEAE_IMMUNE_RELATED', label: 'TEAE Immune-related (%)' },
  // TRAE
  { value: 'TRAE', label: 'TRAE (%)' },
  { value: 'GRADE_3_PLUS_TRAE', label: 'Grade ≥3 TRAE (%)' },
  { value: 'GRADE_3_TRAE', label: 'Grade 3 TRAE (%)' },
  { value: 'GRADE_4_TRAE', label: 'Grade 4 TRAE (%)' },
  { value: 'GRADE_5_TRAE', label: 'Grade 5 TRAE (%)' },
  { value: 'TRAE_LEADING_TO_DISCONTINUATION', label: 'TRAE Discontinuation (%)' },
  { value: 'TRAE_LEADING_TO_DEATH', label: 'TRAE Death (%)' },
  { value: 'TRAE_IMMUNE_RELATED', label: 'TRAE Immune-related (%)' },
  { value: 'SERIOUS_TRAE', label: 'Serious TRAE (%)' },
  // Specific AE Types
  { value: 'CRS', label: 'CRS (%)' },
  { value: 'WBC_DECREASED', label: 'WBC Decreased (%)' },
  // Grade 3+ Specific AEs
  { value: 'GRADE_3_PLUS_AE_CRS', label: 'G3+ CRS (%)' },
  { value: 'GRADE_3_PLUS_AE_THROMBOCYTOPENIA', label: 'G3+ Thrombocytopenia (%)' },
  { value: 'GRADE_3_PLUS_AE_NEUTROPENIA', label: 'G3+ Neutropenia (%)' },
  { value: 'GRADE_3_PLUS_AE_LEUKOPENIA', label: 'G3+ Leukopenia (%)' },
  { value: 'GRADE_3_PLUS_AE_NAUSEA', label: 'G3+ Nausea (%)' },
  { value: 'GRADE_3_PLUS_AE_ANEMIA', label: 'G3+ Anemia (%)' },
  { value: 'GRADE_3_PLUS_AE_DIARRHEA', label: 'G3+ Diarrhea (%)' },
  { value: 'GRADE_3_PLUS_AE_COLITIS', label: 'G3+ Colitis (%)' },
  { value: 'GRADE_3_PLUS_AE_HYPERGLYCEMIA', label: 'G3+ Hyperglycemia (%)' },
  { value: 'GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED', label: 'G3+ Neutrophil Decreased (%)' },
  { value: 'GRADE_3_PLUS_AE_DYSPNEA', label: 'G3+ Dyspnea (%)' },
  { value: 'GRADE_3_PLUS_AE_PYREXIA', label: 'G3+ Pyrexia (%)' },
  { value: 'GRADE_3_PLUS_AE_BLEEDING', label: 'G3+ Bleeding (%)' },
  { value: 'GRADE_3_PLUS_AE_PRURITUS', label: 'G3+ Pruritus (%)' },
  { value: 'GRADE_3_PLUS_AE_RASH', label: 'G3+ Rash (%)' },
  { value: 'GRADE_3_PLUS_AE_PNEUMONIA', label: 'G3+ Pneumonia (%)' },
  { value: 'GRADE_3_PLUS_AE_THYROIDITIS', label: 'G3+ Thyroiditis (%)' },
  { value: 'GRADE_3_PLUS_AE_HYPOPHYSITIS', label: 'G3+ Hypophysitis (%)' },
  { value: 'GRADE_3_PLUS_AE_HEPATITIS', label: 'G3+ Hepatitis (%)' },
  { value: 'GRADE_3_PLUS_AE_PNEUMONITIS', label: 'G3+ Pneumonitis (%)' },
  { value: 'GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE', label: 'G3+ ALT Increased (%)' },
  { value: 'GRADE_3_PLUS_AE_WBC_DECREASED', label: 'G3+ WBC Decreased (%)' },
  { value: 'GRADE_3_PLUS_AE_IMMUNE_RELATED', label: 'G3+ Immune-related AE (%)' },
  // Grade 3+ TRAE Specific
  { value: 'GRADE_3_PLUS_TRAE_IMMUNE_RELATED', label: 'G3+ TRAE irAE (%)' },
  { value: 'GRADE_3_PLUS_TRAE_CRS', label: 'G3+ TRAE CRS (%)' },
  { value: 'GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA', label: 'G3+ TRAE Thrombocytopenia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_NEUTROPENIA', label: 'G3+ TRAE Neutropenia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_LEUKOPENIA', label: 'G3+ TRAE Leukopenia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_NAUSEA', label: 'G3+ TRAE Nausea (%)' },
  { value: 'GRADE_3_PLUS_TRAE_ANEMIA', label: 'G3+ TRAE Anemia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_DIARRHEA', label: 'G3+ TRAE Diarrhea (%)' },
  { value: 'GRADE_3_PLUS_TRAE_COLITIS', label: 'G3+ TRAE Colitis (%)' },
  { value: 'GRADE_3_PLUS_TRAE_HYPERGLYCEMIA', label: 'G3+ TRAE Hyperglycemia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED', label: 'G3+ TRAE Neutrophil↓ (%)' },
  { value: 'GRADE_3_PLUS_TRAE_DYSPNEA', label: 'G3+ TRAE Dyspnea (%)' },
  { value: 'GRADE_3_PLUS_TRAE_PYREXIA', label: 'G3+ TRAE Pyrexia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_BLEEDING', label: 'G3+ TRAE Bleeding (%)' },
  { value: 'GRADE_3_PLUS_TRAE_PRURITUS', label: 'G3+ TRAE Pruritus (%)' },
  { value: 'GRADE_3_PLUS_TRAE_RASH', label: 'G3+ TRAE Rash (%)' },
  { value: 'GRADE_3_PLUS_TRAE_PNEUMONIA', label: 'G3+ TRAE Pneumonia (%)' },
  { value: 'GRADE_3_PLUS_TRAE_THYROIDITIS', label: 'G3+ TRAE Thyroiditis (%)' },
  { value: 'GRADE_3_PLUS_TRAE_HYPOPHYSITIS', label: 'G3+ TRAE Hypophysitis (%)' },
  { value: 'GRADE_3_PLUS_TRAE_HEPATITIS', label: 'G3+ TRAE Hepatitis (%)' },
  { value: 'GRADE_3_PLUS_TRAE_PNEUMONITIS', label: 'G3+ TRAE Pneumonitis (%)' },
  { value: 'GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE', label: 'G3+ TRAE ALT (%)' },
  { value: 'GRADE_3_PLUS_TRAE_WBC_DECREASED', label: 'G3+ TRAE WBC↓ (%)' },
  // Grade 3+ TEAE Specific
  { value: 'GRADE_3_PLUS_TEAE_IMMUNE_RELATED', label: 'G3+ TEAE irAE (%)' },
  { value: 'GRADE_3_PLUS_TEAE_CRS', label: 'G3+ TEAE CRS (%)' },
  { value: 'GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA', label: 'G3+ TEAE Thrombocytopenia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_NEUTROPENIA', label: 'G3+ TEAE Neutropenia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_LEUKOPENIA', label: 'G3+ TEAE Leukopenia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_NAUSEA', label: 'G3+ TEAE Nausea (%)' },
  { value: 'GRADE_3_PLUS_TEAE_ANEMIA', label: 'G3+ TEAE Anemia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_DIARRHEA', label: 'G3+ TEAE Diarrhea (%)' },
  { value: 'GRADE_3_PLUS_TEAE_COLITIS', label: 'G3+ TEAE Colitis (%)' },
  { value: 'GRADE_3_PLUS_TEAE_HYPERGLYCEMIA', label: 'G3+ TEAE Hyperglycemia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED', label: 'G3+ TEAE Neutrophil↓ (%)' },
  { value: 'GRADE_3_PLUS_TEAE_DYSPNEA', label: 'G3+ TEAE Dyspnea (%)' },
  { value: 'GRADE_3_PLUS_TEAE_PYREXIA', label: 'G3+ TEAE Pyrexia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_BLEEDING', label: 'G3+ TEAE Bleeding (%)' },
  { value: 'GRADE_3_PLUS_TEAE_PRURITUS', label: 'G3+ TEAE Pruritus (%)' },
  { value: 'GRADE_3_PLUS_TEAE_RASH', label: 'G3+ TEAE Rash (%)' },
  { value: 'GRADE_3_PLUS_TEAE_PNEUMONIA', label: 'G3+ TEAE Pneumonia (%)' },
  { value: 'GRADE_3_PLUS_TEAE_THYROIDITIS', label: 'G3+ TEAE Thyroiditis (%)' },
  { value: 'GRADE_3_PLUS_TEAE_HYPOPHYSITIS', label: 'G3+ TEAE Hypophysitis (%)' },
  { value: 'GRADE_3_PLUS_TEAE_HEPATITIS', label: 'G3+ TEAE Hepatitis (%)' },
  { value: 'GRADE_3_PLUS_TEAE_PNEUMONITIS', label: 'G3+ TEAE Pneumonitis (%)' },
  { value: 'GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE', label: 'G3+ TEAE ALT (%)' },
  { value: 'GRADE_3_PLUS_TEAE_WBC_DECREASED', label: 'G3+ TEAE WBC↓ (%)' },
];

const Z_AXIS_OPTIONS = [
  { value: 'NUMBER_OF_PATIENTS', label: 'Number of Patients' },
  { value: 'P_VALUE_PFS', label: 'p-value (PFS)' },
  { value: 'P_VALUE_OS', label: 'p-value (OS)' },
  { value: 'P_VALUE_EFS', label: 'p-value (EFS)' },
  { value: 'P_VALUE_RFS', label: 'p-value (RFS)' },
];
/** Z-axis options for Safety bubble only (no p-values) */
const Z_AXIS_OPTIONS_SAFETY = Z_AXIS_OPTIONS.filter((o) => !o.value.startsWith('P_VALUE_'));
/** Efficacy options for Efficacy : Safety bubble only (no HR; HR is for Efficacy-only bubble) */
const EFFICACY_OPTIONS_NO_HR = EFFICACY_OPTIONS.filter((o) => !o.value.startsWith('HR_'));
/** Safety bubble X/Y: safety metrics (no None) + HR metrics */
const SAFETY_BUBBLE_XY_OPTIONS = [
  ...SAFETY_OPTIONS.filter((o) => o.value !== 'none'),
  ...EFFICACY_OPTIONS.filter((o) => o.value.startsWith('HR_')),
];

// Available therapies for selection
const APPROVED_THERAPIES = [
  'Nivolumab + Ipilimumab',
  'Pembrolizumab',
  'Dabrafenib + Trametinib',
  'Ipilimumab',
  'Encorafenib + Binimetinib',
  'Vemurafenib',
  'Talimogene Laherparepvec',
  'Cobimetinib + Vemurafenib',
  'Atezolizumab',
];

const NON_APPROVED_THERAPIES = [
  'Lifileucel',
  'Fianlimab + Cemiplimab',
  'Relatlimab + Nivolumab',
  'Tebentafusp',
  'RP1 + Nivolumab',
];

// ============================================================================
// Filter Select Component
// ============================================================================

interface FilterSelectProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  icon?: React.ReactNode;
  searchable?: boolean;
  searchPlaceholder?: string;
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  icon,
  searchable = false,
  searchPlaceholder = 'Search...',
}: FilterSelectProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const selectedOption = options.find(o => o.value === value);
  const filteredOptions = useMemo(
    () => options.filter(option => option.label.toLowerCase().includes(searchTerm.toLowerCase())),
    [options, searchTerm],
  );

  return (
    <div className="space-y-1.5">
      <label className="text-[13px] font-medium text-indigo-900">{label}</label>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex h-10 w-full items-center justify-between rounded-md border-2 border-indigo-100 bg-white px-3 text-sm text-gray-700 transition-all hover:border-indigo-300 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20">
            <span className="flex items-center gap-2 truncate">
              {icon && <span className="text-indigo-500">{icon}</span>}
              {selectedOption?.label || 'Select...'}
            </span>
            <ChevronDown className="h-4 w-4 text-indigo-400 flex-shrink-0" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
          {searchable && (
            <div className="px-3 py-2">
              <input
                type="text"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          )}
          {filteredOptions.length === 0 ? (
            <div className="px-3 py-2 text-sm text-slate-500">No results</div>
          ) : (
            filteredOptions.map(option => (
              <DropdownMenuItem
                key={option.value}
                className={`text-sm cursor-pointer ${value === option.value ? 'bg-indigo-50 text-indigo-700 font-medium' : ''}`}
                onClick={() => {
                  onChange(option.value);
                  setSearchTerm('');
                }}
              >
                <div className="flex items-center justify-between w-full">
                  <span>{option.label}</span>
                  {value === option.value && <Check className="h-4 w-4 text-indigo-600" />}
                </div>
              </DropdownMenuItem>
            ))
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

// ============================================================================
// Multi-Select Component for Therapies
// ============================================================================

interface TherapyMultiSelectProps {
  label: string;
  maxLabel: string;
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  maxSelect: number;
}

function TherapyMultiSelect({ label, maxLabel, options, selected, onChange, maxSelect }: TherapyMultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false);

  const toggleTherapy = (therapy: string) => {
    if (selected.includes(therapy)) {
      onChange(selected.filter(t => t !== therapy));
    } else if (selected.length < maxSelect) {
      onChange([...selected, therapy]);
    }
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-1">
        <label className="text-[13px] font-medium text-indigo-900">{label}</label>
        <span className="text-[10px] text-indigo-400 font-medium whitespace-nowrap">({maxLabel})</span>
      </div>
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <button className="flex h-10 w-full items-center justify-between rounded-md border-2 border-indigo-100 bg-white px-3 text-sm text-gray-700 transition-all hover:border-indigo-300 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20">
            <span className="truncate">
              {selected.length === 0 ? 'All' : `${selected.length} selected`}
            </span>
            <ChevronDown className="h-4 w-4 text-indigo-400 flex-shrink-0" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] p-2 max-h-64 overflow-y-auto">
          {selected.length > 0 && (
            <button
              onClick={() => onChange([])}
              className="w-full text-left text-xs text-indigo-600 hover:text-indigo-800 mb-2 flex items-center gap-1"
            >
              <X className="h-3 w-3" /> Clear selection
            </button>
          )}
          {options.map(option => (
            <label
              key={option}
              className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm transition-colors ${selected.includes(option)
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'hover:bg-gray-50 text-gray-700'
                } ${!selected.includes(option) && selected.length >= maxSelect ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <input
                type="checkbox"
                checked={selected.includes(option)}
                onChange={() => toggleTherapy(option)}
                disabled={!selected.includes(option) && selected.length >= maxSelect}
                className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="truncate">{option}</span>
            </label>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function CategoryAnalyticsPage() {
  const { data: session } = useSession();
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const handleCancerTypeChange = useCallback(
    (slug: string) => {
      const query = searchParams.toString();
      router.push(`/dashboard/${slug}/analytics${query ? `?${query}` : ''}`);
    },
    [router, searchParams]
  );

  // Check if we're in a specific mode (efficacy or safety only)
  // Read from URL params using Next.js useSearchParams to avoid hydration mismatch
  const modeParam = searchParams.get('mode');
  const mode: 'all' | 'efficacy' | 'safety' =
    modeParam === 'efficacy' || modeParam === 'safety' ? modeParam : 'all';

  // Filter states - initialized based on mode
  const [company, setCompany] = useState('all');
  const [therapyType, setTherapyType] = useState('all');
  const [lineOfTreatment, setLineOfTreatment] = useState('all');
  const [resourceType, setResourceType] = useState<'all' | 'conference' | 'publication'>('all');
  const [fundingType, setFundingType] = useState<'all' | 'industry' | 'non-industry'>('all');
  const [biomarker, setBiomarker] = useState('all');
  const [biomarkerType, setBiomarkerType] = useState('all');
  // Store raw user selections
  const [rawSelectedApproved, setRawSelectedApproved] = useState<string[]>([]);
  const [rawSelectedNonApproved, setRawSelectedNonApproved] = useState<string[]>([]);

  // Initialize params with safe defaults to avoid hydration mismatch
  // These will be updated by useEffect based on mode
  const [efficacyParam, setEfficacyParam] = useState('OBJECTIVE_RESPONSE_RATE');
  const [safetyParam, setSafetyParam] = useState('none');
  /** Second efficacy metric for Head to Head Efficacy (diverging/bubble): X vs Y axis */
  const [efficacyParamY, setEfficacyParamY] = useState('none');
  /** Second safety metric for Head to Head Safety (diverging/bubble): X vs Y axis */
  const [safetyParamY, setSafetyParamY] = useState('none');
  const [zAxisParam, setZAxisParam] = useState('NUMBER_OF_PATIENTS');

  // Direct axis assignments: track which metric is on which axis
  // Each metric can be assigned to 'x', 'y', or 'z'
  const [zParamAxis, setZParamAxis] = useState<'x' | 'y' | 'z'>('z');
  const [efficacyAxis, setEfficacyAxis] = useState<'x' | 'y' | 'z'>('y');
  const [safetyAxis, setSafetyAxis] = useState<'x' | 'y' | 'z'>('x');

  // Convert axis assignments to axisConfig (0-5) for backward compatibility with BubbleChart
  const axisConfig = useMemo(() => {
    // Build assignments object
    const assignments: { x: 'efficacy' | 'safety' | 'zParam'; y: 'efficacy' | 'safety' | 'zParam'; z: 'efficacy' | 'safety' | 'zParam' } = {
      x: safetyAxis === 'x' ? 'safety' : efficacyAxis === 'x' ? 'efficacy' : 'zParam',
      y: safetyAxis === 'y' ? 'safety' : efficacyAxis === 'y' ? 'efficacy' : 'zParam',
      z: safetyAxis === 'z' ? 'safety' : efficacyAxis === 'z' ? 'efficacy' : 'zParam',
    };

    // Map to axisConfig number
    const { x, y, z } = assignments;
    if (x === 'safety' && y === 'efficacy' && z === 'zParam') return 0;
    if (x === 'efficacy' && y === 'safety' && z === 'zParam') return 1;
    if (x === 'safety' && y === 'zParam' && z === 'efficacy') return 2;
    if (x === 'zParam' && y === 'safety' && z === 'efficacy') return 3;
    if (x === 'efficacy' && y === 'zParam' && z === 'safety') return 4;
    if (x === 'zParam' && y === 'efficacy' && z === 'safety') return 5;
    return 0; // Default fallback
  }, [efficacyAxis, safetyAxis]);

  // Helper to get current axis for a metric
  const getCurrentAxis = useCallback((metric: 'zParam' | 'efficacy' | 'safety'): 'x' | 'y' | 'z' => {
    if (metric === 'zParam') return zParamAxis;
    if (metric === 'efficacy') return efficacyAxis;
    return safetyAxis;
  }, [zParamAxis, efficacyAxis, safetyAxis]);

  // Handle axis selection - ensures no two metrics are on the same axis
  const handleAxisChange = useCallback((metric: 'zParam' | 'efficacy' | 'safety', newAxis: 'x' | 'y' | 'z') => {
    // Get current assignments
    const currentZ = zParamAxis;
    const currentEfficacy = efficacyAxis;
    const currentSafety = safetyAxis;

    // Check if the new axis is already taken
    const axisTaken =
      (metric !== 'zParam' && currentZ === newAxis) ||
      (metric !== 'efficacy' && currentEfficacy === newAxis) ||
      (metric !== 'safety' && currentSafety === newAxis);

    if (axisTaken) {
      // Swap: move the metric currently on newAxis to the metric's old axis
      if (metric !== 'zParam' && currentZ === newAxis) {
        setZParamAxis(getCurrentAxis(metric));
        if (metric === 'efficacy') setEfficacyAxis(newAxis);
        else setSafetyAxis(newAxis);
      } else if (metric !== 'efficacy' && currentEfficacy === newAxis) {
        setEfficacyAxis(getCurrentAxis(metric));
        if (metric === 'zParam') setZParamAxis(newAxis);
        else setSafetyAxis(newAxis);
      } else if (metric !== 'safety' && currentSafety === newAxis) {
        setSafetyAxis(getCurrentAxis(metric));
        if (metric === 'zParam') setZParamAxis(newAxis);
        else setEfficacyAxis(newAxis);
      }
    } else {
      // Simply assign the new axis
      if (metric === 'zParam') setZParamAxis(newAxis);
      else if (metric === 'efficacy') setEfficacyAxis(newAxis);
      else setSafetyAxis(newAxis);
    }
  }, [zParamAxis, efficacyAxis, safetyAxis, getCurrentAxis]);

  // Head to Head Efficacy/Safety: Z is always the z-axis (bubble size), no axis swap
  useEffect(() => {
    if (mode === 'efficacy' || mode === 'safety') {
      setZParamAxis('z');
    }
  }, [mode]);

  // Update params when mode changes (e.g., when navigating between pages)
  // This runs after hydration, so it's safe to use mode
  useEffect(() => {
    if (mode === 'safety') {
      setEfficacyParam('none');
      setSafetyParam('GRADE_3_PLUS_AE');
      setEfficacyParamY('none');
      setSafetyParamY('none');
    } else if (mode === 'efficacy') {
      setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
      setSafetyParam('none');
      setEfficacyParamY('none');
      setSafetyParamY('none');
    } else {
      setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
      setSafetyParam('none');
      setEfficacyParamY('none');
      setSafetyParamY('none');
    }
  }, [mode]);

  const [efficacySearch, setEfficacySearch] = useState('');
  const [safetySearch, setSafetySearch] = useState('');

  // Wrapper functions that enforce mode restrictions
  const setEfficacyParamWithMode = (value: string) => {
    // Only allow setting efficacy param if not in safety mode
    if (mode !== 'safety') {
      setEfficacyParam(value);
      // In bar chart mode, disable safety when efficacy is selected (and not 'none')
      if (mode === 'all' && chartType === 'bar' && value !== 'none') {
        setSafetyParam('none');
      }
    }
  };

  const setSafetyParamWithMode = (value: string) => {
    // Only allow setting safety param if not in efficacy mode
    if (mode !== 'efficacy') {
      setSafetyParam(value);
      // In bar chart mode, disable efficacy when safety is selected (and not 'none')
      if (mode === 'all' && chartType === 'bar' && value !== 'none') {
        setEfficacyParam('none');
      }
    }
  };

  // Build filter parameters for API call
  const apiFilters = useMemo(() => {
    const filters: Parameters<typeof analyticsApi.getData>[0] = {
      resource_type: resourceType as 'all' | 'conference' | 'publication',
      cancer_type: categoryName || undefined,
      therapy_type: therapyType,
      funding_type: fundingType as 'all' | 'industry' | 'non-industry',
      line_of_treatment: lineOfTreatment,
      limit: 2000, // Request all matching records
    };

    // Add has_metric filter if safety param is selected (and not being used as display metric)
    if (safetyParam !== 'none' && efficacyParam !== 'none') {
      filters.has_metric = safetyParam;
    }

    return filters;
  }, [resourceType, categoryName, therapyType, fundingType, lineOfTreatment, safetyParam, efficacyParam]);

  // Fetch analytics data from backend with filters
  const { data: analyticsData, isLoading, error } = useQuery({
    queryKey: ['analytics', 'data', apiFilters],
    queryFn: () => analyticsApi.getData(apiFilters),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes (formerly cacheTime)
  });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [windowHeight, setWindowHeight] = useState(700);
  const [chartType, setChartType] = useState<'bar' | 'diverging' | 'bubble' | 'dumbbell'>('bar');

  // Handle chart type changes - ensure proper filter states
  useEffect(() => {
    if (mode === 'all') {
      if (chartType === 'bar') {
        if (efficacyParam !== 'none' && safetyParam !== 'none') {
          setSafetyParam('none');
        } else if (efficacyParam === 'none' && safetyParam === 'none') {
          setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
        }
      } else if (chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell') {
        if (chartType === 'bubble' && efficacyParam.startsWith('HR_')) {
          setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
        }
        if (efficacyParam === 'none' && safetyParam === 'none') {
          setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
          setSafetyParam('GRADE_3_PLUS_AE');
        } else if (efficacyParam === 'none') {
          setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
        } else if (safetyParam === 'none') {
          setSafetyParam('GRADE_3_PLUS_AE');
        }
      }
    } else if (mode === 'efficacy' && (chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell')) {
      if (chartType === 'bubble') {
        setEfficacyParam('OBJECTIVE_RESPONSE_RATE'); // ORR
        setEfficacyParamY('MEDIAN_PFS');             // Median PFS
        setZAxisParam('NUMBER_OF_PATIENTS');         // Number of patients
      } else if (efficacyParamY === 'none') {
        setEfficacyParamY(efficacyParam === 'OBJECTIVE_RESPONSE_RATE' ? 'DISEASE_CONTROL_RATE' : 'OBJECTIVE_RESPONSE_RATE');
      }
    } else if (mode === 'safety' && (chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell')) {
      if (chartType === 'bubble') {
        if (zAxisParam.startsWith('P_VALUE_')) setZAxisParam('NUMBER_OF_PATIENTS');
        setSafetyParamY('AE'); // Y-axis default: AE (%)
      } else if (safetyParamY === 'none') {
        setSafetyParamY(safetyParam === 'GRADE_3_PLUS_AE' ? 'TEAE' : 'GRADE_3_PLUS_AE');
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartType, mode]); // Only depend on chartType and mode to avoid loops with param changes

  // Resolve X/Y collision in Head to Head Efficacy: same metric must not be on both axes
  useEffect(() => {
    if (mode !== 'efficacy' || (chartType !== 'diverging' && chartType !== 'bubble' && chartType !== 'dumbbell')) return;
    if (efficacyParam === 'none' || efficacyParamY === 'none') return;
    if (efficacyParam !== efficacyParamY) return;
    const fallback = efficacyParam === 'OBJECTIVE_RESPONSE_RATE' ? 'DISEASE_CONTROL_RATE' : 'OBJECTIVE_RESPONSE_RATE';
    setEfficacyParamY(EFFICACY_OPTIONS.some(o => o.value === fallback) ? fallback : (EFFICACY_OPTIONS.find(o => o.value !== 'none' && o.value !== efficacyParam)?.value ?? efficacyParamY));
  }, [mode, chartType, efficacyParam, efficacyParamY]);

  // Resolve X/Y collision in Head to Head Safety: same metric must not be on both axes
  useEffect(() => {
    if (mode !== 'safety' || (chartType !== 'diverging' && chartType !== 'bubble')) return;
    if (safetyParam === 'none' || safetyParamY === 'none') return;
    if (safetyParam !== safetyParamY) return;
    const fallback = safetyParam === 'GRADE_3_PLUS_AE' ? 'TEAE' : 'GRADE_3_PLUS_AE';
    setSafetyParamY(SAFETY_OPTIONS.some(o => o.value === fallback) ? fallback : (SAFETY_OPTIONS.find(o => o.value !== 'none' && o.value !== safetyParam)?.value ?? safetyParamY));
  }, [mode, chartType, safetyParam, safetyParamY]);

  // Handle window resize for fullscreen chart
  useEffect(() => {
    const updateHeight = () => {
      if (isFullscreen) {
        setWindowHeight(window.innerHeight);
      }
    };
    if (isFullscreen) {
      updateHeight();
    }
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, [isFullscreen]);

  // Update height when entering fullscreen
  useEffect(() => {
    if (isFullscreen) {
      setWindowHeight(window.innerHeight);
    }
  }, [isFullscreen]);

  // Handle Escape key to close fullscreen
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isFullscreen]);

  // Determine which metric to display (efficacy or safety)
  const displayMetric = useMemo(() => {
    if (efficacyParam !== 'none') return efficacyParam;
    if (safetyParam !== 'none') return safetyParam;
    return null;
  }, [efficacyParam, safetyParam]);

  // Get available therapies for the selected cancer category
  const availableTherapies = useMemo(() => {
    if (!analyticsData || !analyticsData.abstracts) {
      return { approved: APPROVED_THERAPIES, nonApproved: NON_APPROVED_THERAPIES };
    }

    // Filter by cancer type first
    let categoryTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];

    if (categoryName) {
      categoryTrials = categoryTrials.filter(trial => {
        for (const arm of Object.values(trial.arm_results)) {
          // Check both key formats: abstracts use 'AttributeType.CANCER_TYPE', publications use 'cancer_type'
          const cancerTypeAttr = arm.attributes['AttributeType.CANCER_TYPE'] || arm.attributes['cancer_type'];
          if (cancerTypeAttr === null || cancerTypeAttr === undefined) continue;

          const cancerType = typeof cancerTypeAttr === 'object' && 'value' in cancerTypeAttr
            ? String(cancerTypeAttr.value || '')
            : String(cancerTypeAttr || '');

          // Normalize both values for comparison
          const normalizedTrialType = normalizeCancerType(cancerType);
          const normalizedCategory = normalizeCancerType(categoryName);

          if (normalizedTrialType && normalizedCategory &&
            normalizedTrialType.toLowerCase() === normalizedCategory.toLowerCase()) {
            return true;
          }
        }
        return false;
      });
    }

    // Extract unique treatment names from filtered trials
    const treatmentSet = new Set<string>();
    for (const trial of categoryTrials) {
      for (const arm of Object.values(trial.arm_results)) {
        if (arm.arm_name) {
          treatmentSet.add(arm.arm_name);
        }
      }
    }

    const allTreatments = Array.from(treatmentSet).sort();

    // Classify treatments as approved or non-approved
    // Using the same logic as chart-transformers
    const APPROVED_TREATMENTS_SET = new Set([
      'pembrolizumab', 'nivolumab', 'ipilimumab', 'dabrafenib', 'trametinib',
      'vemurafenib', 'cobimetinib', 'encorafenib', 'binimetinib', 'atezolizumab',
      'talimogene laherparepvec', 't-vec', 'cemiplimab', 'avelumab',
    ]);

    const approved: string[] = [];
    const nonApproved: string[] = [];

    for (const treatment of allTreatments) {
      const normalized = treatment.toLowerCase();
      let isApproved = false;

      // Check if any approved treatment is in the name
      for (const approvedDrug of APPROVED_TREATMENTS_SET) {
        if (normalized.includes(approvedDrug)) {
          isApproved = true;
          break;
        }
      }

      // Check for combination therapies with approved drugs
      if (!isApproved && normalized.includes('+')) {
        const parts = normalized.split('+').map(p => p.trim());
        const hasApproved = parts.some(part =>
          Array.from(APPROVED_TREATMENTS_SET).some(approved => part.includes(approved))
        );
        if (hasApproved) {
          isApproved = true;
        }
      }

      if (isApproved) {
        approved.push(treatment);
      } else {
        nonApproved.push(treatment);
      }
    }

    return {
      approved: approved.length > 0 ? approved : APPROVED_THERAPIES,
      nonApproved: nonApproved.length > 0 ? nonApproved : NON_APPROVED_THERAPIES,
    };
  }, [analyticsData, categoryName]);

  // Derive valid selections by filtering raw selections against available therapies
  // This automatically handles cleanup when available therapies change (e.g., category switch)
  const selectedApproved = useMemo(
    () => rawSelectedApproved.filter(t => availableTherapies.approved.includes(t)),
    [rawSelectedApproved, availableTherapies.approved]
  );

  const selectedNonApproved = useMemo(
    () => rawSelectedNonApproved.filter(t => availableTherapies.nonApproved.includes(t)),
    [rawSelectedNonApproved, availableTherapies.nonApproved]
  );

  // Transform data for chart (backend already filtered the data)
  const chartData = useMemo<HeadToHeadDataPoint[]>(() => {
    if (!analyticsData) return [];
    if (!displayMetric) return [];
    if (!analyticsData.abstracts) return [];

    // Backend has already filtered the data, so we just need to transform it
    // Transform backend data to TrialDataFile format for the transformer
    const allTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];

    const trialData: TrialDataFile = {
      total_abstracts: analyticsData.total_abstracts,
      total_arms: analyticsData.total_arms,
      total_attributes_extracted: analyticsData.total_attributes_extracted,
      average_confidence: analyticsData.average_confidence,
      abstracts: allTrials,
    };

    let data = transformHeadToHeadData(trialData, {
      targetMetric: displayMetric as ChartMetric,
      minTrialCount: 1,
    });

    // Filter by selected therapies (this is still client-side as it's UI state)
    const allSelected = [...selectedApproved, ...selectedNonApproved];
    if (allSelected.length > 0) {
      data = data.filter((d) => allSelected.includes(d.treatmentName));
    }

    // Sort by value descending
    data.sort((a, b) => b.averageValue - a.averageValue);

    return data;
  }, [analyticsData, displayMetric, selectedApproved, selectedNonApproved]);

  // Transform data for diverging bar chart (efficacy vs safety, or efficacy vs efficacy, or safety vs safety)
  const divergingChartData = useMemo<EfficacySafetyDataPoint[]>(() => {
    if (!analyticsData || !analyticsData.abstracts) return [];
    let efficacyMetric: ChartMetric;
    let safetyMetric: ChartMetric;
    if (mode === 'efficacy') {
      if (efficacyParam === 'none' || efficacyParamY === 'none') return [];
      efficacyMetric = efficacyParam as ChartMetric;
      safetyMetric = efficacyParamY as ChartMetric;
    } else if (mode === 'safety') {
      if (safetyParam === 'none' || safetyParamY === 'none') return [];
      efficacyMetric = safetyParam as ChartMetric;
      safetyMetric = safetyParamY as ChartMetric;
    } else {
      if (efficacyParam === 'none' || safetyParam === 'none') return [];
      efficacyMetric = efficacyParam as ChartMetric;
      safetyMetric = safetyParam as ChartMetric;
    }

    const allTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];
    const trialData: TrialDataFile = {
      total_abstracts: analyticsData.total_abstracts,
      total_arms: analyticsData.total_arms,
      total_attributes_extracted: analyticsData.total_attributes_extracted,
      average_confidence: analyticsData.average_confidence,
      abstracts: allTrials,
    };

    let data = transformEfficacySafetyData(trialData, {
      efficacyMetric,
      safetyMetric,
      minTrialCount: 1,
    });

    const allSelected = [...selectedApproved, ...selectedNonApproved];
    if (allSelected.length > 0) {
      data = data.filter((d: EfficacySafetyDataPoint | BubbleChartDataPoint) => allSelected.includes(d.treatmentName));
    }

    return data;
  }, [analyticsData, mode, efficacyParam, efficacyParamY, safetyParam, safetyParamY, selectedApproved, selectedNonApproved]);

  // Transform data for bubble chart (efficacy vs safety, or efficacy vs efficacy, or safety vs safety)
  const bubbleChartData = useMemo<BubbleChartDataPoint[]>(() => {
    if (!analyticsData || !analyticsData.abstracts) return [];
    let efficacyMetric: ChartMetric;
    let safetyMetric: ChartMetric;
    if (mode === 'efficacy') {
      if (efficacyParam === 'none' || efficacyParamY === 'none') return [];
      efficacyMetric = efficacyParam as ChartMetric;
      safetyMetric = efficacyParamY as ChartMetric;
    } else if (mode === 'safety') {
      if (safetyParam === 'none' || safetyParamY === 'none') return [];
      efficacyMetric = safetyParam as ChartMetric;
      safetyMetric = safetyParamY as ChartMetric;
    } else {
      if (efficacyParam === 'none' || safetyParam === 'none') return [];
      efficacyMetric = efficacyParam as ChartMetric;
      safetyMetric = safetyParam as ChartMetric;
    }

    const allTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];
    const trialData: TrialDataFile = {
      total_abstracts: analyticsData.total_abstracts,
      total_arms: analyticsData.total_arms,
      total_attributes_extracted: analyticsData.total_attributes_extracted,
      average_confidence: analyticsData.average_confidence,
      abstracts: allTrials,
    };

    let data = transformBubbleChartData(trialData, {
      efficacyMetric,
      safetyMetric,
      zMetric: zAxisParam,
      minTrialCount: 1,
    });

    const allSelected = [...selectedApproved, ...selectedNonApproved];
    if (allSelected.length > 0) {
      data = data.filter((d: EfficacySafetyDataPoint | BubbleChartDataPoint) => allSelected.includes(d.treatmentName));
    }

    return data;
  }, [analyticsData, mode, efficacyParam, efficacyParamY, safetyParam, safetyParamY, zAxisParam, selectedApproved, selectedNonApproved]);

  // Dumbbell chart data: map bubble chart data (efficacy mode) to treatment + valueA (X) + valueB (Y) + hr (bubble size)
  const dumbbellChartData = useMemo<DumbbellDataPoint[]>(() => {
    if (mode !== 'efficacy' || bubbleChartData.length === 0) return [];
    return bubbleChartData.map((p) => ({
      treatmentName: p.treatmentName,
      valueA: p.efficacy,
      valueB: p.safety,
      hr: (p as BubbleChartDataPoint & { zValue?: number }).zValue ?? p.numberOfPatients,
    }));
  }, [mode, bubbleChartData]);

  // Determine the label for the displayed metric
  const metricLabel = useMemo(() => {
    if (efficacyParam !== 'none') {
      return EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label || efficacyParam;
    }
    if (safetyParam !== 'none') {
      return SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label || safetyParam;
    }
    return 'No Metric Selected';
  }, [efficacyParam, safetyParam]);

  return (
    <div className="flex flex-col min-h-screen w-full bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="w-full px-4 md:px-6">
          <div className="flex items-center justify-between h-14 gap-4">
            <div className="flex items-center gap-4">
              <Link href="/" className="brand flex-shrink-0">
                <Logo height={32} />
                <span className="brand-text text-lg">bi<span className="brand-o">o</span>nocular</span>
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <DashboardNavLink />
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

      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-2 pt-2 pb-4 md:px-4 md:pt-4 md:pb-6 bg-slate-100 gap-4">
        <div className="w-full bg-white rounded-lg shadow shrink-0 overflow-visible">
          <DashboardGlobalHeader
            cancerTypeSlug={categorySlug}
            onCancerTypeChange={handleCancerTypeChange}
          />
        </div>

      {/* Mode Banner with Parameter Selection - Compact, professional design */}
      {mode === 'all' && (
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 border-b border-blue-700/50">
          <div className="px-4 md:px-6 py-2.5">
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-7 h-7 bg-white/20 rounded-md">
                  <TrendingUp className="h-4 w-4 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <h2 className="text-white font-semibold text-sm">Head to Head Efficacy : Safety</h2>
                  <span className="hidden sm:inline-block w-px h-4 bg-white/30"></span>
                  <p className="text-blue-100 text-xs hidden sm:block">Comparative analysis</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto">
                {chartType === 'bubble' && (['x', 'y', 'z'] as const).map((axis) => (
                  <div key={axis} className="w-full sm:w-72 flex gap-2">
                    {efficacyAxis === axis && (
                      <>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 w-14 items-center justify-center rounded-md border border-white/40 bg-white/15 backdrop-blur-sm px-2 text-xs font-bold text-white transition-all hover:bg-white/25 hover:border-white/60 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/30" title={`Assign to ${axis.toUpperCase()}-axis`}>
                              <span className="font-mono">{axis.toUpperCase()}</span>
                              <ChevronDown className="h-3 w-3 text-white/80 flex-shrink-0 ml-1" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="w-28">
                            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 border-b">Assign to Axis</div>
                            {(['x', 'y', 'z'] as const).map((a) => (
                              <DropdownMenuItem key={a} className={`text-sm cursor-pointer ${efficacyAxis === a ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => handleAxisChange('efficacy', a)}>
                                <div className="flex items-center justify-between w-full"><span className="font-mono font-medium">{a.toUpperCase()}-axis</span>{efficacyAxis === a && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 flex-1 items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                              <span className="flex items-center gap-2 truncate font-medium">{EFFICACY_OPTIONS_NO_HR.find(o => o.value === efficacyParam)?.label || 'Select...'}</span>
                              <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                            <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                              <input type="text" value={efficacySearch} placeholder="Search efficacy metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" onChange={(e) => setEfficacySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                            </div>
                            {EFFICACY_OPTIONS_NO_HR.filter(option => option.value !== 'none' && option.label.toLowerCase().includes(efficacySearch.toLowerCase())).map(option => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${efficacyParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => { setEfficacyParamWithMode(option.value); setEfficacySearch(''); }}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{efficacyParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                    {safetyAxis === axis && (
                      <>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 w-14 items-center justify-center rounded-md border border-white/40 bg-white/15 backdrop-blur-sm px-2 text-xs font-bold text-white transition-all hover:bg-white/25 hover:border-white/60 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/30" title={`Assign to ${axis.toUpperCase()}-axis`}>
                              <span className="font-mono">{axis.toUpperCase()}</span>
                              <ChevronDown className="h-3 w-3 text-white/80 flex-shrink-0 ml-1" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="w-28">
                            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 border-b">Assign to Axis</div>
                            {(['x', 'y', 'z'] as const).map((a) => (
                              <DropdownMenuItem key={a} className={`text-sm cursor-pointer ${safetyAxis === a ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => handleAxisChange('safety', a)}>
                                <div className="flex items-center justify-between w-full"><span className="font-mono font-medium">{a.toUpperCase()}-axis</span>{safetyAxis === a && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 flex-1 items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                              <span className="flex items-center gap-2 truncate font-medium">{SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label || 'Select...'}</span>
                              <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                            <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                              <input type="text" value={safetySearch} placeholder="Search safety metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" onChange={(e) => setSafetySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                            </div>
                            {SAFETY_OPTIONS.filter(option => option.value !== 'none' && option.label.toLowerCase().includes(safetySearch.toLowerCase())).map(option => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${safetyParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => { setSafetyParamWithMode(option.value); setSafetySearch(''); }}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{safetyParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                    {zParamAxis === axis && (
                      <>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 w-14 items-center justify-center rounded-md border border-white/40 bg-white/15 backdrop-blur-sm px-2 text-xs font-bold text-white transition-all hover:bg-white/25 hover:border-white/60 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/30" title={`Assign to ${axis.toUpperCase()}-axis`}>
                              <span className="font-mono">{axis.toUpperCase()}</span>
                              <ChevronDown className="h-3 w-3 text-white/80 flex-shrink-0 ml-1" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="w-28">
                            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 border-b">Assign to Axis</div>
                            {(['x', 'y', 'z'] as const).map((a) => (
                              <DropdownMenuItem key={a} className={`text-sm cursor-pointer ${zParamAxis === a ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => handleAxisChange('zParam', a)}>
                                <div className="flex items-center justify-between w-full"><span className="font-mono font-medium">{a.toUpperCase()}-axis</span>{zParamAxis === a && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 flex-1 items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                              <span className="flex items-center gap-2 truncate font-medium">{Z_AXIS_OPTIONS.find((o) => o.value === zAxisParam)?.label || 'Select...'}</span>
                              <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                            {Z_AXIS_OPTIONS.map((option) => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${zAxisParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => setZAxisParam(option.value)}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{zAxisParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                  </div>
                ))}
                {chartType !== 'bubble' && (
                  <>
                    <div className="w-full sm:w-72">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button disabled={mode === 'all' && chartType === 'bar' && safetyParam !== 'none' && safetyParam !== ''} className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white/10">
                            <span className="flex items-center gap-2 truncate font-medium">{EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label || 'Select...'}</span>
                            <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                          <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                            <input type="text" value={efficacySearch} placeholder="Search efficacy metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" onChange={(e) => setEfficacySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                          </div>
                          {EFFICACY_OPTIONS.filter(option => (chartType === 'diverging' || chartType === 'bar' ? option.value !== 'none' : true) && option.label.toLowerCase().includes(efficacySearch.toLowerCase())).map(option => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${efficacyParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => { setEfficacyParamWithMode(option.value); setEfficacySearch(''); }}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{efficacyParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                              </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <div className="w-full sm:w-72">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button disabled={mode === 'all' && chartType === 'bar' && efficacyParam !== 'none' && efficacyParam !== ''} className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white/10">
                            <span className="flex items-center gap-2 truncate font-medium">{SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label || 'Select...'}</span>
                            <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                          <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                            <input type="text" value={safetySearch} placeholder="Search safety metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" onChange={(e) => setSafetySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                          </div>
                          {SAFETY_OPTIONS.filter(option => (chartType === 'diverging' || chartType === 'bar' ? option.value !== 'none' : true) && option.label.toLowerCase().includes(safetySearch.toLowerCase())).map(option => (
                            <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${safetyParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => { setSafetyParamWithMode(option.value); setSafetySearch(''); }}>
                              <div className="flex items-center justify-between w-full"><span>{option.label}</span>{safetyParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {mode === 'efficacy' && (
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 border-b border-blue-700/50">
          <div className="px-4 md:px-6 py-2.5">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-7 h-7 bg-white/20 rounded-md">
                  <TrendingUp className="h-4 w-4 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <h2 className="text-white font-semibold text-sm">Head to Head Efficacy</h2>
                  <span className="hidden sm:inline-block w-px h-4 bg-white/30"></span>
                  <p className="text-blue-100 text-xs hidden sm:block">
                    Clinical trial efficacy parameters
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                <div className={chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell' ? 'w-full sm:w-72' : 'w-full sm:w-80'}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                        <span className="flex items-center gap-2 truncate font-medium">
                          <span className="text-xs text-white/70">{chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell' ? 'X-axis:' : 'Parameter:'}</span>
                          {EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label || 'Select...'}
                        </span>
                        <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                      <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                        <input
                          type="text"
                          value={efficacySearch}
                          placeholder="Search efficacy metrics..."
                          className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          onChange={(e) => setEfficacySearch(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                      {EFFICACY_OPTIONS.filter(option => {
                        const base = (chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell' ? option.value !== 'none' : true) &&
                          option.label.toLowerCase().includes(efficacySearch.toLowerCase());
                        // In dual-axis mode, X-axis cannot show the metric selected for Y (avoid duplicate)
                        if (chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell') {
                          return base && (option.value !== efficacyParamY || option.value === efficacyParam);
                        }
                        return base;
                      }).map(option => (
                        <DropdownMenuItem
                          key={option.value}
                          className={`text-sm cursor-pointer ${efficacyParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`}
                          onClick={() => {
                            setEfficacyParamWithMode(option.value);
                            setEfficacySearch('');
                          }}
                        >
                          <div className="flex items-center justify-between w-full">
                            <span>{option.label}</span>
                            {efficacyParam === option.value && <Check className="h-4 w-4 text-blue-600" />}
                          </div>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {(chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell') && (
                  <div className="w-full sm:w-72">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-white/70">Y-axis:</span>
                            {EFFICACY_OPTIONS.find(o => o.value === efficacyParamY)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                        {EFFICACY_OPTIONS.filter(option =>
                          option.value !== 'none' &&
                          // Y-axis cannot show the metric selected for X (avoid duplicate)
                          (option.value !== efficacyParam || option.value === efficacyParamY)
                        ).map(option => (
                          <DropdownMenuItem
                            key={option.value}
                            className={`text-sm cursor-pointer ${efficacyParamY === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`}
                            onClick={() => setEfficacyParamY(option.value)}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span>{option.label}</span>
                              {efficacyParamY === option.value && <Check className="h-4 w-4 text-blue-600" />}
                            </div>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
                {chartType === 'bubble' && mode === 'efficacy' && (
                  <div className="w-full sm:w-72 flex gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-white/70">Z-axis:</span>
                            {Z_AXIS_OPTIONS.find((o) => o.value === zAxisParam)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                        {Z_AXIS_OPTIONS.map((option) => (
                          <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${zAxisParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => setZAxisParam(option.value)}>
                            <div className="flex items-center justify-between w-full"><span>{option.label}</span>{zAxisParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {mode === 'safety' && (
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 border-b border-blue-700/50">
          <div className="px-4 md:px-6 py-2.5">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-7 h-7 bg-white/20 rounded-md">
                  <AlertCircle className="h-4 w-4 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <h2 className="text-white font-semibold text-sm">Head to Head Safety</h2>
                  <span className="hidden sm:inline-block w-px h-4 bg-white/30"></span>
                  <p className="text-blue-100 text-xs hidden sm:block">
                    Clinical trial safety parameters
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                <div className={chartType === 'diverging' || chartType === 'bubble' ? 'w-full sm:w-72' : 'w-full sm:w-80'}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                        <span className="flex items-center gap-2 truncate font-medium">
                          <span className="text-xs text-white/70">{chartType === 'diverging' || chartType === 'bubble' ? 'X-axis:' : 'Parameter:'}</span>
                          {(chartType === 'bubble' ? SAFETY_BUBBLE_XY_OPTIONS : SAFETY_OPTIONS).find(o => o.value === safetyParam)?.label || 'Select...'}
                        </span>
                        <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                      <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                        <input
                          type="text"
                          value={safetySearch}
                          placeholder="Search safety metrics..."
                          className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          onChange={(e) => setSafetySearch(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                      {(chartType === 'bubble' ? SAFETY_BUBBLE_XY_OPTIONS : SAFETY_OPTIONS).filter(option => {
                        const base = (chartType === 'diverging' || chartType === 'bubble' ? option.value !== 'none' : true) &&
                          option.label.toLowerCase().includes(safetySearch.toLowerCase());
                        // In dual-axis mode, X-axis cannot show the metric selected for Y (avoid duplicate)
                        if (chartType === 'diverging' || chartType === 'bubble') {
                          return base && (option.value !== safetyParamY || option.value === safetyParam);
                        }
                        return base;
                      }).map(option => (
                        <DropdownMenuItem
                          key={option.value}
                          className={`text-sm cursor-pointer ${safetyParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`}
                          onClick={() => {
                            setSafetyParamWithMode(option.value);
                            setSafetySearch('');
                          }}
                        >
                          <div className="flex items-center justify-between w-full">
                            <span>{option.label}</span>
                            {safetyParam === option.value && <Check className="h-4 w-4 text-blue-600" />}
                          </div>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {(chartType === 'diverging' || chartType === 'bubble') && (
                  <div className="w-full sm:w-72">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-white/70">Y-axis:</span>
                            {(chartType === 'bubble' ? SAFETY_BUBBLE_XY_OPTIONS : SAFETY_OPTIONS).find(o => o.value === safetyParamY)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                        {(chartType === 'bubble' ? SAFETY_BUBBLE_XY_OPTIONS : SAFETY_OPTIONS).filter(option =>
                          option.value !== 'none' &&
                          // Y-axis cannot show the metric selected for X (avoid duplicate)
                          (option.value !== safetyParam || option.value === safetyParamY)
                        ).map(option => (
                          <DropdownMenuItem
                            key={option.value}
                            className={`text-sm cursor-pointer ${safetyParamY === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`}
                            onClick={() => setSafetyParamY(option.value)}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span>{option.label}</span>
                              {safetyParamY === option.value && <Check className="h-4 w-4 text-blue-600" />}
                            </div>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
                {chartType === 'bubble' && mode === 'safety' && (
                  <div className="w-full sm:w-72 flex gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-white/30 bg-white/10 backdrop-blur-sm px-3 text-sm text-white transition-all hover:bg-white/20 hover:border-white/50 focus:outline-none focus:border-white focus:ring-2 focus:ring-white/20">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-white/70">Z-axis:</span>
                            {Z_AXIS_OPTIONS_SAFETY.find((o) => o.value === zAxisParam)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-white/70 flex-shrink-0" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                        {Z_AXIS_OPTIONS_SAFETY.map((option) => (
                          <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${zAxisParam === option.value ? 'bg-blue-50 text-blue-700 font-medium' : ''}`} onClick={() => setZAxisParam(option.value)}>
                            <div className="flex items-center justify-between w-full"><span>{option.label}</span>{zAxisParam === option.value && <Check className="h-4 w-4 text-blue-600" />}</div>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel - Filters */}
        <aside className="w-[480px] border-r border-slate-200 bg-white p-4 overflow-y-auto flex-shrink-0">
          {/* Cancer Type Badge */}
          <div className="mb-4 p-2.5 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg border border-indigo-100">
            <div className="text-[11px] font-medium text-indigo-600 uppercase tracking-wider mb-0.5">Cancer Type</div>
            <div className="text-sm font-semibold text-indigo-900">{categoryName}</div>
          </div>

          {/* 2-Column Filter Grid */}
          <div className="grid grid-cols-2 gap-3">
            {/* Row 1 */}
            <FilterSelect
              label="Company"
              value={company}
              options={COMPANY_OPTIONS}
              onChange={setCompany}
            />
            <FilterSelect
              label="Type of Therapy"
              value={therapyType}
              options={THERAPY_TYPE_OPTIONS}
              onChange={setTherapyType}
            />

            {/* Row 2 */}
            <FilterSelect
              label="Line of Treatment"
              value={lineOfTreatment}
              options={LINE_OF_TREATMENT_OPTIONS}
              onChange={setLineOfTreatment}
            />
            <FilterSelect
              label="Type of Resource"
              value={resourceType}
              options={RESOURCE_TYPE_OPTIONS}
              onChange={(value) => setResourceType(value as 'all' | 'conference' | 'publication')}
            />

            {/* Row 3 - Therapy Selection */}
            <TherapyMultiSelect
              label="Approved Therapies"
              maxLabel="Max 5"
              options={availableTherapies.approved}
              selected={selectedApproved}
              onChange={setRawSelectedApproved}
              maxSelect={5}
            />
            <TherapyMultiSelect
              label="Non-Approved"
              maxLabel="Max 5"
              options={availableTherapies.nonApproved}
              selected={selectedNonApproved}
              onChange={setRawSelectedNonApproved}
              maxSelect={5}
            />

            {/* Row 4 */}
            <FilterSelect
              label="Type of Funding"
              value={fundingType}
              options={FUNDING_TYPE_OPTIONS}
              onChange={(value) => setFundingType(value as 'all' | 'industry' | 'non-industry')}
            />

            {/* Row 5 */}
            <FilterSelect
              label="Biomarker (YES or NO)"
              value={biomarker}
              options={BIOMARKER_OPTIONS}
              onChange={setBiomarker}
            />
            <FilterSelect
              label="Biomarker Selected"
              value={biomarkerType}
              options={BIOMARKER_TYPE_OPTIONS}
              onChange={setBiomarkerType}
            />
          </div>

          {/* Divider */}
          <div className="my-4 border-t border-slate-200" />

          {/* Action Buttons */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 border-indigo-200 text-indigo-700 hover:bg-indigo-50"
              onClick={() => {
                setCompany('all');
                setTherapyType('all');
                setLineOfTreatment('all');
                setResourceType('all');
                setFundingType('all');
                setBiomarker('all');
                setBiomarkerType('all');
                setRawSelectedApproved([]);
                setRawSelectedNonApproved([]);
                // Reset parameters based on mode
                setEfficacyParamY('none');
                setSafetyParamY('none');
                if (mode === 'safety') {
                  setEfficacyParam('none');
                  setSafetyParam('GRADE_3_PLUS_AE');
                } else if (mode === 'efficacy') {
                  setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
                  setSafetyParam('none');
                } else {
                  setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
                  setSafetyParam('GRADE_3_PLUS_AE');
                }
              }}
            >
              Reset Filters
            </Button>
            <Button className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white">
              Apply Filters
            </Button>
          </div>
        </aside>

        {/* Right Panel - Chart */}
        <main className="flex-1 flex flex-col overflow-hidden bg-white min-w-0">
          {/* Compact Chart Header */}
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-end gap-3 flex-shrink-0">
            {/* Chart type label + selector - Show in all Head to Head modes */}
            {(mode === 'all' || mode === 'efficacy' || mode === 'safety') && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Chart type</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="group h-10 pl-3 pr-3.5 gap-2.5 rounded-xl border border-slate-200/80 bg-white text-slate-700 font-medium shadow-sm transition-all duration-200 hover:bg-slate-50 hover:border-indigo-200 hover:text-indigo-700 hover:shadow-md focus-visible:ring-2 focus-visible:ring-indigo-500/20 focus-visible:border-indigo-300"
                    >
                      <span className="flex h-7 w-7 items-center justify-center text-indigo-600">
                        {chartType === 'bar' && <BarChart3 className="h-4 w-4" />}
                        {chartType === 'diverging' && <TrendingUp className="h-4 w-4" />}
                        {chartType === 'bubble' && <CircleDot className="h-4 w-4" />}
                        {chartType === 'dumbbell' && <Minus className="h-4 w-4" />}
                      </span>
                      <span className="text-sm tracking-tight">
                        {chartType === 'bar' ? 'Bar Chart' : chartType === 'diverging' ? 'Diverging Chart' : chartType === 'bubble' ? 'Bubble Chart' : 'Dumbbell Chart'}
                      </span>
                      <ChevronDown className="h-4 w-4 text-slate-400 transition-transform duration-200 group-data-[state=open]:rotate-180" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-52 rounded-xl border-slate-200/90 bg-white p-1.5 shadow-lg">
                    <DropdownMenuItem
                      onClick={() => setChartType('bar')}
                      className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                    >
                      <BarChart3 className="h-4 w-4 text-slate-500" />
                      <span>Bar Chart</span>
                      {chartType === 'bar' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setChartType('diverging')}
                      className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                    >
                      <TrendingUp className="h-4 w-4 text-slate-500" />
                      <span>Diverging Chart</span>
                      {chartType === 'diverging' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setChartType('bubble')}
                      className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                    >
                      <CircleDot className="h-4 w-4 text-slate-500" />
                      <span>Bubble Chart</span>
                      {chartType === 'bubble' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                    </DropdownMenuItem>
                    {mode === 'efficacy' && (
                      <DropdownMenuItem
                        onClick={() => setChartType('dumbbell')}
                        className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                      >
                        <Minus className="h-4 w-4 text-slate-500" />
                        <span>Dumbbell Chart</span>
                        {chartType === 'dumbbell' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}
            {/* Fullscreen Button */}
            <Button
              variant="outline"
              size="sm"
              className="h-10 w-10 rounded-xl border border-slate-200/80 bg-white text-slate-600 shadow-sm transition-all duration-200 hover:bg-slate-50 hover:border-indigo-200 hover:text-indigo-600 hover:shadow-md focus-visible:ring-2 focus-visible:ring-indigo-500/20"
              title="Full Screen"
              onClick={() => setIsFullscreen(true)}
            >
              <Maximize2 className="h-4 w-4" />
            </Button>
          </div>

          {/* Chart Area - Fill remaining space; consistent padding for all chart types (space between header block and chart) */}
          <div className="flex-1 flex flex-col overflow-hidden p-3">
            <div className="flex-1 relative min-h-0">
              <div className="absolute inset-0 w-full h-full">
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3">
                    <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
                    <p className="text-sm text-slate-500">Loading analytics data...</p>
                  </div>
                ) : error ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
                    <AlertCircle className="h-8 w-8 text-red-500" />
                    <div>
                      <p className="text-sm font-medium text-red-700">Failed to load data</p>
                      <p className="text-xs text-slate-500 mt-1">
                        {error instanceof Error ? error.message : 'Unknown error occurred'}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.location.reload()}
                      className="mt-2"
                    >
                      Retry
                    </Button>
                  </div>
                ) : (() => {
                  // Determine which data to check based on chart type (bar/diverging/bubble in any mode)
                  const hasData = chartType === 'bar'
                    ? chartData.length > 0
                    : chartType === 'diverging'
                      ? divergingChartData.length > 0
                      : chartType === 'dumbbell'
                        ? dumbbellChartData.length > 0
                        : bubbleChartData.length > 0;
                  const chartEfficacyParam = mode === 'efficacy' ? efficacyParam : mode === 'safety' ? safetyParam : efficacyParam;
                  const chartSafetyParam = mode === 'efficacy' ? efficacyParamY : mode === 'safety' ? safetyParamY : safetyParam;

                  if (!hasData) {
                    return (
                      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
                        <div className="h-12 w-12 rounded-full bg-slate-100 flex items-center justify-center">
                          <Search className="h-6 w-6 text-slate-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-700">No data available</p>
                          <p className="text-xs text-slate-500 mt-1">
                            No trials with {metricLabel} data found for the selected filters
                          </p>
                        </div>
                      </div>
                    );
                  }

                  // Render appropriate chart based on type (all/efficacy/safety modes)
                  if (chartType === 'diverging' && divergingChartData.length > 0) {
                    return (
                      <DivergingBarChart
                        efficacyParam={chartEfficacyParam !== 'none' ? chartEfficacyParam : undefined}
                        safetyParam={chartSafetyParam !== 'none' ? chartSafetyParam : undefined}
                        axisMode={mode === 'efficacy' ? 'efficacy-efficacy' : mode === 'safety' ? 'safety-safety' : undefined}
                        data={divergingChartData}
                        title=""
                        description=""
                        height={450}
                        compact={true}
                      />
                    );
                  }

                  if (chartType === 'bubble' && bubbleChartData.length > 0) {
                    return (
                      <div className="w-full h-full flex flex-col min-h-0 min-w-0">
                        <BubbleChart
                          efficacyParam={chartEfficacyParam !== 'none' ? chartEfficacyParam : undefined}
                          safetyParam={chartSafetyParam !== 'none' ? chartSafetyParam : undefined}
                          axisMode={mode === 'efficacy' ? 'efficacy-efficacy' : mode === 'safety' ? 'safety-safety' : undefined}
                          data={bubbleChartData}
                          title=""
                          description=""
                          height={450}
                          compact={false}
                          fillHeight
                          zAxisParam={zAxisParam}
                          axisConfig={axisConfig}
                        />
                      </div>
                    );
                  }

                  if (chartType === 'dumbbell' && mode === 'efficacy' && dumbbellChartData.length > 0) {
                    const labelA = EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label ?? 'X';
                    const labelB = EFFICACY_OPTIONS.find(o => o.value === efficacyParamY)?.label ?? 'Y';
                    return (
                      <DumbbellChart
                        data={dumbbellChartData}
                        labelA={labelA}
                        labelB={labelB}
                        xAxisLabel="Survival Duration (Months)"
                        yAxisLabel="Treatment"
                        height={450}
                        compact={true}
                        useHrForBubbleSize={true}
                      />
                    );
                  }

                  // Default to bar chart
                  return (
                    <BarChart
                      data={chartData}
                      metric={displayMetric as ChartMetric}
                      title=""
                      description=""
                      height={450}
                      showReferenceLine={true}
                      showLegend={true}
                      compact={true}
                    />
                  );
                })()}
              </div>
            </div>

            {/* Export Buttons Below Chart */}
            <div className="flex items-center justify-center gap-3 pt-3 flex-shrink-0">
              <Button variant="outline" size="sm" className="h-9 px-4 gap-2 text-slate-600 hover:text-emerald-600 hover:border-emerald-300 hover:bg-emerald-50" disabled={isLoading || chartData.length === 0}>
                <FileSpreadsheet className="h-4 w-4" />
                Excel
              </Button>
              <Button variant="outline" size="sm" className="h-9 px-4 gap-2 text-slate-600 hover:text-orange-600 hover:border-orange-300 hover:bg-orange-50" disabled={isLoading || chartData.length === 0}>
                <Presentation className="h-4 w-4" />
                PPT
              </Button>
              <Button variant="outline" size="sm" className="h-9 px-4 gap-2 text-slate-600 hover:text-red-600 hover:border-red-300 hover:bg-red-50" disabled={isLoading || chartData.length === 0}>
                <FileText className="h-4 w-4" />
                PDF
              </Button>
            </div>
          </div>
        </main>
      </div>
      </main>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-slate-100 flex flex-col">
          {/* Fullscreen Header */}
          <div className="border-b border-slate-200 bg-white shadow-sm flex-shrink-0">
            <div className="px-6 py-3 flex items-center justify-between">
              <Link href="/" className="brand flex-shrink-0">
                <Logo height={32} />
                <span className="brand-text text-base">bi<span className="brand-o">o</span>nocular</span>
              </Link>
              <div className="flex items-center gap-3">
                {/* Chart type label + selector - Show in Head to Head mode (efficacy vs safety) */}
                {(mode === 'all' || mode === 'efficacy' || mode === 'safety') && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Chart type</span>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          className="group h-10 pl-3.5 pr-4 gap-2.5 rounded-xl border border-slate-200/80 bg-white text-slate-700 font-medium shadow-sm transition-all duration-200 hover:bg-slate-50 hover:border-indigo-200 hover:text-indigo-700 hover:shadow-md focus-visible:ring-2 focus-visible:ring-indigo-500/20 focus-visible:border-indigo-300"
                        >
                          <span className="flex h-7 w-7 items-center justify-center text-indigo-600">
                            {chartType === 'bar' && <BarChart3 className="h-4 w-4" />}
                            {chartType === 'diverging' && <TrendingUp className="h-4 w-4" />}
                            {chartType === 'bubble' && <CircleDot className="h-4 w-4" />}
                            {chartType === 'dumbbell' && <Minus className="h-4 w-4" />}
                          </span>
                          <span className="text-sm tracking-tight">
                            {chartType === 'bar' ? 'Bar Chart' : chartType === 'diverging' ? 'Diverging Chart' : chartType === 'bubble' ? 'Bubble Chart' : 'Dumbbell Chart'}
                          </span>
                          <ChevronDown className="h-4 w-4 text-slate-400 transition-transform duration-200 group-data-[state=open]:rotate-180" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-52 rounded-xl border-slate-200/90 bg-white p-1.5 shadow-lg">
                        <DropdownMenuItem
                          onClick={() => setChartType('bar')}
                          className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                        >
                          <BarChart3 className="h-4 w-4 text-slate-500" />
                          <span>Bar Chart</span>
                          {chartType === 'bar' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setChartType('diverging')}
                          className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                        >
                          <TrendingUp className="h-4 w-4 text-slate-500" />
                          <span>Diverging Chart</span>
                          {chartType === 'diverging' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setChartType('bubble')}
                          className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                        >
                          <CircleDot className="h-4 w-4 text-slate-500" />
                          <span>Bubble Chart</span>
                          {chartType === 'bubble' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                        </DropdownMenuItem>
                        {mode === 'efficacy' && (
                          <DropdownMenuItem
                            onClick={() => setChartType('dumbbell')}
                            className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-indigo-50 focus:text-indigo-700"
                          >
                            <Minus className="h-4 w-4 text-slate-500" />
                            <span>Dumbbell Chart</span>
                            {chartType === 'dumbbell' && <Check className="h-4 w-4 ml-auto text-indigo-600" />}
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 text-slate-600 hover:text-slate-900"
                  onClick={() => setIsFullscreen(false)}
                >
                  <Minimize2 className="h-4 w-4" />
                  Exit
                </Button>
              </div>
            </div>
          </div>

          {/* Mode Banner in Fullscreen - Compact design */}
          {mode === 'all' && (
            <div className="bg-gradient-to-r from-blue-600 to-indigo-600 border-b border-blue-700/50 px-6 py-2">
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center w-6 h-6 bg-white/20 rounded">
                  <TrendingUp className="h-3.5 w-3.5 text-white" />
                </div>
                <span className="text-white text-xs font-medium">Head to Head Efficacy : Safety</span>
                <span className="w-px h-3 bg-white/30 mx-1"></span>
                <span className="text-blue-100 text-xs">
                  Efficacy: {EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label}
                </span>
                <span className="w-px h-3 bg-white/30 mx-1"></span>
                <span className="text-blue-100 text-xs">
                  Safety: {SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label}
                </span>
              </div>
            </div>
          )}
          {mode === 'efficacy' && (
            <div className="bg-gradient-to-r from-blue-600 to-indigo-600 border-b border-blue-700/50 px-6 py-2">
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center w-6 h-6 bg-white/20 rounded">
                  <TrendingUp className="h-3.5 w-3.5 text-white" />
                </div>
                <span className="text-white text-xs font-medium">Head to Head Efficacy</span>
                <span className="w-px h-3 bg-white/30 mx-1"></span>
                <span className="text-blue-100 text-xs">
                  {(chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell') && efficacyParamY !== 'none'
                    ? `${EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label} vs ${EFFICACY_OPTIONS.find(o => o.value === efficacyParamY)?.label}`
                    : EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label}
                </span>
              </div>
            </div>
          )}
          {mode === 'safety' && (
            <div className="bg-gradient-to-r from-blue-600 to-indigo-600 border-b border-blue-700/50 px-6 py-2">
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center w-6 h-6 bg-white/20 rounded">
                  <AlertCircle className="h-3.5 w-3.5 text-white" />
                </div>
                <span className="text-white text-xs font-medium">Head to Head Safety</span>
                <span className="w-px h-3 bg-white/30 mx-1"></span>
                <span className="text-blue-100 text-xs">
                  {(chartType === 'diverging' || chartType === 'bubble') && safetyParamY !== 'none'
                    ? `${SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label} vs ${SAFETY_OPTIONS.find(o => o.value === safetyParamY)?.label}`
                    : SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label}
                </span>
              </div>
            </div>
          )}

          {/* Fullscreen Chart Area */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden mt-2">
            <div className={`flex-1 flex flex-col min-h-0 w-full overflow-hidden ${chartType === 'diverging' ? 'p-2' : 'p-4'}`}>
              {isLoading ? (
                <div className="flex flex-col items-center justify-center h-full gap-3">
                  <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
                  <p className="text-base text-slate-500">Loading analytics data...</p>
                </div>
              ) : (() => {
                const hasData = chartType === 'bar'
                  ? chartData.length > 0
                  : chartType === 'diverging'
                    ? divergingChartData.length > 0
                    : chartType === 'dumbbell'
                      ? dumbbellChartData.length > 0
                      : bubbleChartData.length > 0;
                const chartEfficacyParam = mode === 'efficacy' ? efficacyParam : mode === 'safety' ? safetyParam : efficacyParam;
                const chartSafetyParam = mode === 'efficacy' ? efficacyParamY : mode === 'safety' ? safetyParamY : safetyParam;

                if (!hasData) {
                  return (
                    <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
                      <div className="h-16 w-16 rounded-full bg-slate-100 flex items-center justify-center">
                        <Search className="h-8 w-8 text-slate-400" />
                      </div>
                      <div>
                        <p className="text-base font-medium text-slate-700">No data available</p>
                        <p className="text-sm text-slate-500 mt-1">
                          No trials with {metricLabel} data found for the selected filters
                        </p>
                      </div>
                    </div>
                  );
                }

                const chartHeight = Math.max(400, windowHeight - 220);

                if (chartType === 'dumbbell' && mode === 'efficacy' && dumbbellChartData.length > 0) {
                  const labelA = EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label ?? 'X';
                  const labelB = EFFICACY_OPTIONS.find(o => o.value === efficacyParamY)?.label ?? 'Y';
                  return (
                    <div className="w-full p-4" style={{ height: chartHeight }}>
                      <DumbbellChart
                        data={dumbbellChartData}
                        labelA={labelA}
                        labelB={labelB}
                        xAxisLabel="Survival Duration (Months)"
                        yAxisLabel="Treatment"
                        height={chartHeight}
                        compact={false}
                        useHrForBubbleSize={true}
                      />
                    </div>
                  );
                }

                if (chartType === 'diverging' && divergingChartData.length > 0) {
                  return (
                    <div className="flex-1 flex flex-col min-h-0 min-w-0 w-full">
                      <DivergingBarChart
                        efficacyParam={chartEfficacyParam !== 'none' ? chartEfficacyParam : undefined}
                        safetyParam={chartSafetyParam !== 'none' ? chartSafetyParam : undefined}
                        axisMode={mode === 'efficacy' ? 'efficacy-efficacy' : mode === 'safety' ? 'safety-safety' : undefined}
                        data={divergingChartData}
                        title=""
                        description=""
                        height={chartHeight}
                        compact={false}
                        fillHeight
                      />
                    </div>
                  );
                }

                if (chartType === 'bubble' && bubbleChartData.length > 0) {
                  return (
                    <div className="flex-1 flex flex-col min-h-0 min-w-0 w-full">
                      <BubbleChart
                        efficacyParam={chartEfficacyParam !== 'none' ? chartEfficacyParam : undefined}
                        safetyParam={chartSafetyParam !== 'none' ? chartSafetyParam : undefined}
                        axisMode={mode === 'efficacy' ? 'efficacy-efficacy' : mode === 'safety' ? 'safety-safety' : undefined}
                        data={bubbleChartData}
                        title=""
                        description=""
                        height={chartHeight}
                        compact={false}
                        fillHeight
                        zAxisParam={zAxisParam}
                        axisConfig={axisConfig}
                      />
                    </div>
                  );
                }

                // Default to bar chart
                return (
                  <div className="w-full" style={{ height: chartHeight }}>
                    <BarChart
                      data={chartData}
                      metric={displayMetric as ChartMetric}
                      title=""
                      description=""
                      height={chartHeight}
                      showReferenceLine={true}
                      showLegend={true}
                      compact={true}
                    />
                  </div>
                );
              })()}
            </div>

            {/* Export Buttons Below Chart */}
            <div className="flex items-center justify-center gap-4 py-4 px-4 flex-shrink-0 border-t border-slate-200 bg-white">
              <Button variant="outline" size="lg" className="gap-2 text-slate-600 hover:text-emerald-600 hover:border-emerald-300 hover:bg-emerald-50" disabled={isLoading || chartData.length === 0}>
                <FileSpreadsheet className="h-5 w-5" />
                Export as Excel
              </Button>
              <Button variant="outline" size="lg" className="gap-2 text-slate-600 hover:text-orange-600 hover:border-orange-300 hover:bg-orange-50" disabled={isLoading || chartData.length === 0}>
                <Presentation className="h-5 w-5" />
                Export as PPT
              </Button>
              <Button variant="outline" size="lg" className="gap-2 text-slate-600 hover:text-red-600 hover:border-red-300 hover:bg-red-50" disabled={isLoading || chartData.length === 0}>
                <FileText className="h-5 w-5" />
                Export as PDF
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
