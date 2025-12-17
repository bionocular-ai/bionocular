'use client';

import * as React from 'react';
import { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import Image from 'next/image';
import Link from 'next/link';
import {
  ChevronDown,
  Check,
  X,
  LayoutGrid,
  ArrowLeft,
  FileSpreadsheet,
  Presentation,
  FileText,
  TrendingUp,
  TrendingDown,
  Minus,
  Maximize2,
  Minimize2,
  Search,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { UserMenu } from '@/components/user-menu';
import HeadToHeadChart from '@/components/charts/HeadToHeadChart';
import { transformHeadToHeadData } from '@/lib/chart-transformers';
import { analyticsApi } from '@/lib/api';
import { HeadToHeadDataPoint, ChartMetric, TrialDataFile, ArmResult } from '@/types/analytics';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

// ============================================================================
// Category Mapping
// ============================================================================

const CATEGORY_SLUG_MAP: Record<string, string> = {
  'resected-cutaneous-melanoma': 'Resected Cutaneous Melanoma',
  'unresectable-cutaneous-melanoma': 'Unresectable Cutaneous Melanoma',
  'cutaneous-melanoma-with-brain-metastasis': 'Cutaneous melanoma with Brain metastasis',
  'cutaneous-melanoma-with-cns-metastasis': 'Cutaneous Melanoma with CNS metastasis',
  'uveal-melanoma': 'Uveal Melanoma',
  'mucosal-melanoma': 'Mucosal Melanoma',
  'acral-melanoma': 'Acral Melanoma',
  'basal-cell-carcinoma': 'Basal Cell Carcinoma',
  'merkel-cell-carcinoma': 'Merkel Cell Carcinoma',
  'cutaneous-squamous-cell-carcinoma': 'Cutaneous Squamous Cell Carcinoma',
};

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

// Known industry sponsors (pharmaceutical companies)
const INDUSTRY_SPONSORS = [
  'bristol-myers squibb', 'bms', 'bristol myers',
  'merck', 'msd',
  'novartis',
  'roche', 'genentech',
  'pfizer',
  'amgen',
  'gilead',
  'astrazeneca',
  'lilly', 'eli lilly',
  'sanofi',
  'glaxosmithkline', 'gsk',
  'abbvie',
  'biogen',
  'regeneron',
  'moderna',
  'johnson & johnson', 'janssen',
  'bayer',
  'boehringer',
  'takeda',
  'celgene',
  'iovance',
  'junshi',
  'pharmaceutical', 'pharma', 'biotech', 'biotechnology',
];

// Helper function to determine if funding is industry or non-industry
function isIndustryFunded(sponsorsValue: unknown): boolean | null {
  if (!sponsorsValue) return null;
  
  const sponsorsStr = typeof sponsorsValue === 'object' && 'value' in sponsorsValue
    ? String(sponsorsValue.value || '')
    : String(sponsorsValue || '');
  
  if (!sponsorsStr || sponsorsStr.toLowerCase() === 'not found' || sponsorsStr.toLowerCase() === 'none') {
    return null;
  }
  
  const sponsorsLower = sponsorsStr.toLowerCase();
  
  // Check for explicit non-industry indicators
  if (sponsorsLower.includes('non-industry') || 
      sponsorsLower.includes('non industry') ||
      sponsorsLower.includes('investigator sponsored') ||
      sponsorsLower.includes('academic') ||
      sponsorsLower.includes('university') ||
      sponsorsLower.includes('government') ||
      sponsorsLower.includes('nih') ||
      sponsorsLower.includes('national cancer institute')) {
    return false;
  }
  
  // Check for industry sponsors
  for (const industrySponsor of INDUSTRY_SPONSORS) {
    if (sponsorsLower.includes(industrySponsor)) {
      return true;
    }
  }
  
  // If we can't determine, return null (unknown)
  return null;
}

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
  { value: '1L', label: 'First Line' },
  { value: '2L', label: 'Second Line' },
  { value: '3L+', label: 'Third Line+' },
  { value: 'adjuvant', label: 'Adjuvant' },
  { value: 'neoadjuvant', label: 'Neoadjuvant' },
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
  { value: 'P_VALUE_PFS', label: 'p-value (PFS)' },
  { value: 'HR_PFS', label: 'HR (PFS)' },
  // Survival - OS
  { value: 'MEDIAN_OS', label: 'Median OS (months)' },
  { value: 'MEDIAN_FOLLOWUP_OS', label: 'Median OS Follow-up' },
  { value: 'P_VALUE_OS', label: 'p-value (OS)' },
  { value: 'HR_OS', label: 'HR (OS)' },
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
  { value: 'P_VALUE_EFS', label: 'p-value (EFS)' },
  { value: 'HR_EFS', label: 'HR (EFS)' },
  { value: 'RFS', label: 'Recurrence-Free Survival' },
  { value: 'P_VALUE_RFS', label: 'p-value (RFS)' },
  { value: 'LENGTH_RFS', label: 'RFS Follow-up Length' },
  { value: 'HR_RFS', label: 'HR (RFS)' },
  { value: 'MFS', label: 'Metastasis-Free Survival' },
  { value: 'LENGTH_MFS', label: 'MFS Follow-up Length' },
  { value: 'HR_MFS', label: 'HR (MFS)' },
  // Time Metrics
  { value: 'TTR', label: 'Time to Response' },
  { value: 'TTP', label: 'Time to Progression' },
  { value: 'TTNT', label: 'Time to Next Treatment' },
  { value: 'TTF', label: 'Time to Treatment Failure' },
];

const SAFETY_OPTIONS = [
  { value: 'none', label: 'None' },
  // General AE
  { value: 'AE', label: 'Any AE (%)' },
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
              className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm transition-colors ${
                selected.includes(option) 
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
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  // Fetch analytics data from backend
  const { data: analyticsData, isLoading, error } = useQuery({
    queryKey: ['analytics', 'data'],
    queryFn: analyticsApi.getData,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes (formerly cacheTime)
  });

  // Filter states
  const [company, setCompany] = useState('all');
  const [therapyType, setTherapyType] = useState('all');
  const [lineOfTreatment, setLineOfTreatment] = useState('all');
  const [resourceType, setResourceType] = useState('all');
  const [fundingType, setFundingType] = useState('all');
  const [biomarker, setBiomarker] = useState('all');
  const [biomarkerType, setBiomarkerType] = useState('all');
  const [selectedApproved, setSelectedApproved] = useState<string[]>([]);
  const [selectedNonApproved, setSelectedNonApproved] = useState<string[]>([]);
  const [efficacyParam, setEfficacyParam] = useState('OBJECTIVE_RESPONSE_RATE');
  const [safetyParam, setSafetyParam] = useState('none');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [windowHeight, setWindowHeight] = useState(700);

  // Handle window resize for fullscreen chart
  useEffect(() => {
    const updateHeight = () => setWindowHeight(window.innerHeight);
    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, []);

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
          
          if (cancerType && cancerType.toLowerCase() === categoryName.toLowerCase()) {
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

  // Track previous availableTherapies to detect changes
  const prevAvailableTherapiesRef = useRef(availableTherapies);
  
  // Clear selected therapies if they're not available in the current category
  // Only update when availableTherapies actually changes (not on every render)
  useEffect(() => {
    const prev = prevAvailableTherapiesRef.current;
    const current = availableTherapies;
    
    // Check if availableTherapies actually changed
    const approvedChanged = prev.approved.length !== current.approved.length ||
      prev.approved.some((t, i) => t !== current.approved[i]);
    const nonApprovedChanged = prev.nonApproved.length !== current.nonApproved.length ||
      prev.nonApproved.some((t, i) => t !== current.nonApproved[i]);
    
    if (approvedChanged || nonApprovedChanged) {
      // Use setTimeout to defer state updates outside of render cycle
      const timeoutId = setTimeout(() => {
        setSelectedApproved(prevSelected => prevSelected.filter(t => current.approved.includes(t)));
        setSelectedNonApproved(prevSelected => prevSelected.filter(t => current.nonApproved.includes(t)));
        prevAvailableTherapiesRef.current = current;
      }, 0);
      
      return () => clearTimeout(timeoutId);
    } else {
      prevAvailableTherapiesRef.current = current;
    }
  }, [availableTherapies]);

  // Transform and filter data
  const chartData = useMemo<HeadToHeadDataPoint[]>(() => {
    if (!analyticsData) return [];
    if (!displayMetric) return [];
    if (!analyticsData.abstracts) return [];

    // Transform backend data to TrialDataFile format for the transformer
    // Note: The API returns both abstracts and publications under the 'abstracts' key
    // We need to filter them based on whether they have abstract_id or publication_id
    let allTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];

    // Filter by cancer type (category)
    if (categoryName) {
      allTrials = allTrials.filter(trial => {
        // Check if any arm has the matching cancer type
        for (const arm of Object.values(trial.arm_results)) {
          // Check both key formats: abstracts use 'AttributeType.CANCER_TYPE', publications use 'cancer_type'
          const cancerTypeAttr = arm.attributes['AttributeType.CANCER_TYPE'] || arm.attributes['cancer_type'];
          if (cancerTypeAttr === null || cancerTypeAttr === undefined) continue;
          
          const cancerType = typeof cancerTypeAttr === 'object' && 'value' in cancerTypeAttr
            ? String(cancerTypeAttr.value || '')
            : String(cancerTypeAttr || '');
          
          if (cancerType && cancerType.toLowerCase() === categoryName.toLowerCase()) {
            return true;
          }
        }
        return false;
      });
    }

    // Filter by resource type (Conference or Publications)
    let filteredAbstracts: TrialDataFile['abstracts'];
    if (resourceType === 'conference') {
      // Filter to only show abstracts from ASCO or ESMO
      filteredAbstracts = allTrials.filter(trial => {
        // Must have abstract_id (not publication_id)
        if (!trial.abstract_id || trial.publication_id) return false;
        
        // Check if conference is ASCO or ESMO
        for (const arm of Object.values(trial.arm_results)) {
          const conferenceAttr = arm.attributes['AttributeType.CONFERENCE'];
          if (conferenceAttr === null || conferenceAttr === undefined) continue;
          
          const conference = typeof conferenceAttr === 'object' && 'value' in conferenceAttr
            ? String(conferenceAttr.value || '')
            : String(conferenceAttr || '');
          
          if (!conference) continue;
          
          const conferenceUpper = conference.toUpperCase();
          if (conferenceUpper === 'ASCO' || conferenceUpper === 'ESMO') {
            return true;
          }
        }
        return false;
      });
    } else if (resourceType === 'publication') {
      // Filter to only show publications (must have publication_id, not abstract_id)
      filteredAbstracts = allTrials.filter(trial => {
        return !!trial.publication_id && !trial.abstract_id;
      });
    } else {
      // If 'all' or unknown, show all
      filteredAbstracts = allTrials;
    }

    // Filter by therapy type if selected
    if (therapyType !== 'all') {
      filteredAbstracts = filteredAbstracts.map(trial => {
        const filteredArmResults: Record<string, ArmResult> = {};
        
        for (const [armId, arm] of Object.entries(trial.arm_results)) {
          const therapyTypeAttr = arm.attributes['AttributeType.TYPE_OF_THERAPY'];
          if (therapyTypeAttr === null || therapyTypeAttr === undefined) continue;
          
          const armTherapyType = typeof therapyTypeAttr === 'object' && 'value' in therapyTypeAttr
            ? String(therapyTypeAttr.value || '')
            : String(therapyTypeAttr || '');
          
          if (!armTherapyType) continue;
          
          // Normalize and compare (case-insensitive to handle "Targeted therapy" vs "Targeted Therapy")
          const armTypeNormalized = armTherapyType.trim().toLowerCase();
          const filterTypeNormalized = therapyType.trim().toLowerCase();
          
          // Check if therapy type matches (case-insensitive)
          if (armTypeNormalized === filterTypeNormalized) {
            filteredArmResults[armId] = arm;
          }
        }
        
        // Return trial with filtered arms, or null if no arms remain
        if (Object.keys(filteredArmResults).length === 0) {
          return null;
        }
        
        return {
          ...trial,
          arm_results: filteredArmResults,
        };
      }).filter((trial): trial is NonNullable<typeof trial> => trial !== null);
    }

    // Filter by funding type if selected
    if (fundingType !== 'all') {
      filteredAbstracts = filteredAbstracts.map(trial => {
        const filteredArmResults: Record<string, ArmResult> = {};
        
        for (const [armId, arm] of Object.entries(trial.arm_results)) {
          const sponsorsAttr = arm.attributes['AttributeType.SPONSORS'];
          const isIndustry = isIndustryFunded(sponsorsAttr);
          
          // Include arm if funding type matches
          if (fundingType === 'industry' && isIndustry === true) {
            filteredArmResults[armId] = arm;
          } else if (fundingType === 'non-industry' && isIndustry === false) {
            filteredArmResults[armId] = arm;
          }
        }
        
        // Return trial with filtered arms, or null if no arms remain
        if (Object.keys(filteredArmResults).length === 0) {
          return null;
        }
        
        return {
          ...trial,
          arm_results: filteredArmResults,
        };
      }).filter((trial): trial is NonNullable<typeof trial> => trial !== null);
    }

    // Filter by safety parameter if selected (and not being used as display metric)
    if (safetyParam !== 'none' && efficacyParam !== 'none') {
      const safetyMetricKey = `AttributeType.${safetyParam}`;
      filteredAbstracts = filteredAbstracts.map(trial => {
        const filteredArmResults: Record<string, ArmResult> = {};
        
        // Only include arms that have the selected safety parameter with a valid value
        for (const [armId, arm] of Object.entries(trial.arm_results)) {
          // Check if the attribute key exists in the attributes object
          if (!(safetyMetricKey in arm.attributes)) {
            continue;
          }
          
          const safetyAttr = arm.attributes[safetyMetricKey];
          
          // Use the same extraction logic as the transformer
          // Check if safety attribute exists and has a valid numeric value
          if (safetyAttr !== null && safetyAttr !== undefined) {
            let safetyValue: number | null = null;
            
            // Handle different attribute formats (same as extractNumericValue logic)
            if (typeof safetyAttr === 'number') {
              safetyValue = safetyAttr;
            } else if (typeof safetyAttr === 'string') {
              const parsed = parseFloat(safetyAttr);
              safetyValue = isNaN(parsed) ? null : parsed;
            } else if (typeof safetyAttr === 'object' && 'value' in safetyAttr) {
              const value = safetyAttr.value;
              if (value === null || value === 'Not found' || value === 'NR') {
                safetyValue = null;
              } else if (typeof value === 'number') {
                safetyValue = value;
              } else if (typeof value === 'string') {
                // Handle ranges like "12.5-15.3" by taking the first number
                const match = value.match(/[\d.]+/);
                if (match) {
                  const parsed = parseFloat(match[0]);
                  safetyValue = isNaN(parsed) ? null : parsed;
                }
              }
            }
            
            // Include arm if we have a valid numeric value (including 0, which is valid for percentages)
            if (safetyValue !== null && !isNaN(safetyValue)) {
              filteredArmResults[armId] = arm;
            }
          }
        }
        
        // Return trial with filtered arms, or null if no arms remain
        if (Object.keys(filteredArmResults).length === 0) {
          return null;
        }
        
        return {
          ...trial,
          arm_results: filteredArmResults,
        };
      }).filter((trial): trial is NonNullable<typeof trial> => trial !== null);
    }

    const trialData: TrialDataFile = {
      total_abstracts: filteredAbstracts.length,
      total_arms: analyticsData.total_arms,
      total_attributes_extracted: analyticsData.total_attributes_extracted,
      average_confidence: analyticsData.average_confidence,
      abstracts: filteredAbstracts,
    };

    let data = transformHeadToHeadData(trialData, {
      targetMetric: displayMetric as ChartMetric,
      minTrialCount: 1,
    });

    // Filter by selected therapies
    const allSelected = [...selectedApproved, ...selectedNonApproved];
    if (allSelected.length > 0) {
      data = data.filter(d => allSelected.includes(d.treatmentName));
    }

    // Sort by value descending
    data.sort((a, b) => b.averageValue - a.averageValue);

    return data;
  }, [analyticsData, displayMetric, efficacyParam, safetyParam, fundingType, resourceType, therapyType, categoryName, selectedApproved, selectedNonApproved]);

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

  // Calculate summary metrics
  const summaryMetric = useMemo(() => {
    if (chartData.length === 0) return { value: 0, change: 0 };
    const avg = chartData.reduce((sum, d) => sum + d.averageValue, 0) / chartData.length;
    // Simulated change percentage
    const change = 12.4;
    return { value: avg, change };
  }, [chartData]);

  return (
    <div className="flex flex-col min-h-screen w-full bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="w-full px-4 md:px-6">
          <div className="flex items-center justify-between h-14 gap-4">
            <div className="flex items-center gap-4">
              <Link href="/" className="brand flex-shrink-0">
                <div className="relative flex items-center" style={{ height: '32px' }}>
                  <Image
                    src="/logo.png"
                    alt="Bionocular Logo"
                    width={32}
                    height={32}
                    className="object-contain"
                    priority
                    unoptimized
                  />
                </div>
                <span className="brand-text text-lg">bi<span className="brand-o">o</span>nocular</span>
              </Link>
              <div className="h-6 w-px bg-slate-200" />
              <h1 className="text-lg font-semibold text-slate-800">Clinical Trials Analytics</h1>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push(`/dashboard/${categorySlug}`)}
                className="text-slate-600 hover:text-slate-900"
              >
                <ArrowLeft className="h-4 w-4 mr-1" />
                Trials
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push('/dashboard')}
                className="text-slate-600 hover:text-slate-900"
              >
                <LayoutGrid className="h-4 w-4 mr-1" />
                Categories
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
              onChange={setResourceType}
            />

            {/* Row 3 - Therapy Selection */}
            <TherapyMultiSelect
              label="Approved Therapies"
              maxLabel="Max 5"
              options={availableTherapies.approved}
              selected={selectedApproved}
              onChange={setSelectedApproved}
              maxSelect={5}
            />
            <TherapyMultiSelect
              label="Non-Approved"
              maxLabel="Max 5"
              options={availableTherapies.nonApproved}
              selected={selectedNonApproved}
              onChange={setSelectedNonApproved}
              maxSelect={5}
            />

            {/* Row 4 */}
            <FilterSelect
              label="Type of Funding"
              value={fundingType}
              options={FUNDING_TYPE_OPTIONS}
              onChange={setFundingType}
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

          {/* Parameter Selection */}
          <div className="space-y-3">
            <FilterSelect
              label="Efficacy Parameter"
              value={efficacyParam}
              options={EFFICACY_OPTIONS}
              onChange={setEfficacyParam}
              searchable
              searchPlaceholder="Search efficacy metrics..."
            />
            <FilterSelect
              label="Safety Parameter"
              value={safetyParam}
              options={SAFETY_OPTIONS}
              onChange={setSafetyParam}
              searchable
              searchPlaceholder="Search safety metrics..."
            />
          </div>

          {/* Action Buttons */}
          <div className="mt-4 flex gap-2">
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
                setSelectedApproved([]);
                setSelectedNonApproved([]);
                setEfficacyParam('OBJECTIVE_RESPONSE_RATE');
                setSafetyParam('none');
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
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between gap-4 flex-shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <h2 className="text-sm font-semibold text-slate-700">{metricLabel} by Drug/Intervention</h2>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-100 text-blue-700">
                  {metricLabel.split(' ')[0]}
                </span>
                <span className="text-xl font-bold text-slate-900">{summaryMetric.value.toFixed(1)}</span>
                <span className="flex items-center text-xs font-semibold text-emerald-600">
                  {summaryMetric.change > 0 ? (
                    <TrendingUp className="h-3.5 w-3.5 mr-0.5" />
                  ) : summaryMetric.change < 0 ? (
                    <TrendingDown className="h-3.5 w-3.5 mr-0.5" />
                  ) : (
                    <Minus className="h-3.5 w-3.5 mr-0.5" />
                  )}
                  {Math.abs(summaryMetric.change)}%
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Fullscreen Button */}
              <Button
                variant="outline"
                size="sm"
                className="h-8 px-2 text-slate-500 hover:text-indigo-600 hover:border-indigo-300"
                title="Full Screen"
                onClick={() => setIsFullscreen(true)}
              >
                <Maximize2 className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Chart Area - Fill remaining space */}
          <div className="flex-1 flex flex-col p-3 overflow-hidden">
            <div className="flex-1 relative">
              <div className="absolute inset-0">
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
                ) : chartData.length === 0 ? (
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
                ) : (
                  <HeadToHeadChart
                    data={chartData}
                    metric={displayMetric as ChartMetric}
                    title=""
                    description=""
                    height={450}
                    showReferenceLine={true}
                    showLegend={true}
                    compact={true}
                  />
                )}
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

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-slate-100 flex flex-col">
          {/* Fullscreen Header */}
          <div className="px-6 py-3 border-b border-slate-200 flex items-center justify-between bg-white shadow-sm flex-shrink-0">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <Link href="/" className="brand flex-shrink-0">
                  <div className="relative flex items-center" style={{ height: '28px' }}>
                    <Image
                      src="/logo.png"
                      alt="Bionocular Logo"
                      width={28}
                      height={28}
                      className="object-contain"
                      priority
                      unoptimized
                    />
                  </div>
                  <span className="brand-text text-base">bi<span className="brand-o">o</span>nocular</span>
                </Link>
                <div className="h-5 w-px bg-slate-200" />
              </div>
              <h2 className="text-base font-semibold text-slate-700">{metricLabel} by Drug/Intervention</h2>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center px-2.5 py-1 rounded-md text-sm font-semibold bg-blue-100 text-blue-700">
                  {metricLabel.split(' ')[0]}
                </span>
                <span className="text-2xl font-bold text-slate-900">{summaryMetric.value.toFixed(1)}</span>
                <span className="flex items-center text-sm font-semibold text-emerald-600">
                  {summaryMetric.change > 0 ? (
                    <TrendingUp className="h-4 w-4 mr-0.5" />
                  ) : summaryMetric.change < 0 ? (
                    <TrendingDown className="h-4 w-4 mr-0.5" />
                  ) : (
                    <Minus className="h-4 w-4 mr-0.5" />
                  )}
                  {Math.abs(summaryMetric.change)}%
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
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

          {/* Fullscreen Chart Area */}
          <div className="flex-1 p-4 flex flex-col min-h-0">
            <div className="flex-1 relative">
              <div className="absolute inset-0">
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3">
                    <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
                    <p className="text-base text-slate-500">Loading analytics data...</p>
                  </div>
                ) : chartData.length === 0 ? (
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
                ) : (
                  <HeadToHeadChart
                    data={chartData}
                    metric={displayMetric as ChartMetric}
                    title=""
                    description=""
                    height={windowHeight - 140}
                    showReferenceLine={true}
                    showLegend={true}
                    compact={true}
                  />
                )}
              </div>
            </div>
            
            {/* Export Buttons Below Chart */}
            <div className="flex items-center justify-center gap-4 pt-4 flex-shrink-0">
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
