'use client';

import * as React from 'react';
import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
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
import { PageHeader } from '@/components/dashboard/PageHeader';
import { FilterChips } from '@/components/dashboard/FilterChips';
import { MODALITY_VALUES, slugToCategory } from '@/lib/dashboard-constants';
import { PHASE_MAP, STATUS_MAP } from '@/lib/clinical-trials-enums';
import BarChart from '@/components/charts/BarChart';
import DivergingBarChart from '@/components/charts/DivergingBarChart';
import BubbleChart from '@/components/charts/BubbleChart';
import DumbbellChart, { DumbbellDataPoint } from '@/components/charts/DumbbellChart';
import { transformHeadToHeadData, transformEfficacySafetyData, transformBubbleChartData, normalizeTreatmentName } from '@/lib/chart-transformers';
import { analyticsApi } from '@/lib/api';
import { HeadToHeadDataPoint, ChartMetric, TrialDataFile, EfficacySafetyDataPoint, BubbleChartDataPoint, EFFICACY_METRICS, SAFETY_METRICS } from '@/types/analytics';
import { CompareTable } from '@/components/compare/CompareTable';
import { buildCompareTable } from '@/lib/compare-transformers';
import { CompareSelection, CompareSortMode, MAX_COMPARE_TREATMENTS } from '@/types/compare';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

// ============================================================================
// Filter Options
// ============================================================================

// Note: Funding type filtering is now handled by the backend API

/** Derived from the shared vocabulary so the filter can never fall behind it. */
const MODALITY_OPTIONS = [
  { value: 'all', label: 'All' },
  ...MODALITY_VALUES.map((value) => ({ value, label: value })),
];

const RESOURCE_TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'conference', label: 'Conference' },
  { value: 'publication', label: 'Publications' },
  { value: 'live_feed_upcoming', label: 'Live Feed Upcoming', italic: true },
];

/**
 * Derived from the CT.gov enum map rather than the display-name list in
 * dashboard-constants, so the value in the URL is the value the query uses and
 * the chip label is the same string the rest of the app shows for that phase.
 */
const PHASE_FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  ...Object.entries(PHASE_MAP).map(([value, label]) => ({ value, label })),
];

const FUNDING_TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'industry', label: 'Industry' },
  { value: 'non-industry', label: 'Non-Industry' },
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

// Advanced filters: options from Landscape page (separate filters, not "Group by")

const ADVANCED_STAGE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'Stage I', label: 'Stage I' },
  { value: 'Stage I/II', label: 'Stage I/II' },
  { value: 'Stage II', label: 'Stage II' },
  { value: 'Stage II/III', label: 'Stage II/III' },
  { value: 'Stage III', label: 'Stage III' },
  { value: 'Stage III/IV', label: 'Stage III/IV' },
  { value: 'Stage IV', label: 'Stage IV' },
];
const ADVANCED_BIOMARKER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'BRAF (V600)', label: 'BRAF (V600)' },
  { value: 'PD-L1', label: 'PD-L1' },
  { value: 'HLA-A*02:01', label: 'HLA-A*02:01' },
  { value: 'LAG-3', label: 'LAG-3' },
  { value: 'TMB', label: 'TMB' },
  { value: 'c-KIT', label: 'c-KIT' },
  { value: 'NRAS', label: 'NRAS' },
  { value: 'NF1', label: 'NF1' },
  { value: 'PRAME', label: 'PRAME' },
  { value: 'CDKN2A / CDK4', label: 'CDKN2A / CDK4' },
  { value: 'MSI-H / dMMR', label: 'MSI-H / dMMR' },
  { value: 'GNAQ / GNA11', label: 'GNAQ / GNA11' },
  { value: 'SF3B1 / EIF1AX', label: 'SF3B1 / EIF1AX' },
  { value: 'BAP1', label: 'BAP1' },
  { value: 'MCPyV', label: 'MCPyV' },
  { value: 'PTCH1 / SMO', label: 'PTCH1 / SMO' },
  { value: 'PIK3CA', label: 'PIK3CA' },
  { value: 'EGFR', label: 'EGFR' },
  { value: 'ctDNA (MRD)', label: 'ctDNA (MRD)' },
  { value: 'MART-1', label: 'MART-1' },
  { value: 'gp100', label: 'gp100' },
  { value: 'Other', label: 'Other' },
];
const ADVANCED_LINE_OF_THERAPY_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'Neoadjuvant', label: 'Neoadjuvant' },
  { value: 'Adjuvant', label: 'Adjuvant' },
  { value: '1L (First Line)', label: '1L (First Line)' },
  { value: '2L (Second Line)', label: '2L (Second Line)' },
  { value: '2L+ (Refractory)', label: '2L+ (Refractory)' },
  { value: '3L+ (Third Line+)', label: '3L+ (Third Line+)' },
];
// ============================================================================
// Main Page Component
// ============================================================================

export default function CategoryAnalyticsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  // Check if we're in a specific mode (efficacy or safety only)
  // Read from URL params using Next.js useSearchParams to avoid hydration mismatch
  const modeParam = searchParams.get('mode');
  const mode: 'all' | 'efficacy' | 'safety' =
    modeParam === 'all' ? 'all' : modeParam === 'safety' ? 'safety' : 'efficacy';

  // Per-mode page header (sidebar owns mode selection; this page reads ?mode).
  const { hubTitle, hubDescription } = useMemo(() => {
    if (mode === 'safety') {
      return {
        hubTitle: 'Safety Intelligence Hub',
        hubDescription:
          'Compare adverse-event, TEAE, and TRAE rates across treatments to weigh tolerability head to head.',
      };
    }
    if (mode === 'all') {
      return {
        hubTitle: 'Efficacy vs Safety Index Hub',
        hubDescription:
          'Plot efficacy against safety to surface the benefit–risk trade-offs between treatments.',
      };
    }
    return {
      hubTitle: 'Efficacy Intelligence Hub',
      hubDescription:
        'Compare response, survival, and hazard-ratio outcomes across treatments head to head.',
    };
  }, [mode]);

  // Filter states - initialized based on mode
  // Phase, status and funding may arrive from the agent's hand-off link. Read
  // through useSearchParams like `mode` above, not from window.location, so the
  // first client render matches the prerendered HTML.
  const [phase, setPhase] = useState(() => searchParams.get('phase') ?? 'all');
  const [status, setStatus] = useState<string[]>(() => {
    const raw = searchParams.get('status');
    return raw ? raw.split(',').filter(Boolean) : [];
  });
  const [modality, setModality] = useState('all');
  const [resourceType, setResourceType] = useState<'all' | 'conference' | 'publication'>('all');
  // Defaults to industry, as it always has. A hand-off link pins it explicitly,
  // because that default alone hides 96 of the 189 Phase 1 rows the agent shows.
  const [fundingType, setFundingType] = useState<'all' | 'industry' | 'non-industry'>(
    () => {
      const fromUrl = searchParams.get('funding');
      return fromUrl === 'all' || fromUrl === 'industry' || fromUrl === 'non-industry'
        ? fromUrl
        : 'industry';
    }
  );
  const [advancedLineOfTherapy, setAdvancedLineOfTherapy] = useState('all');
  // Store raw treatment selections (merged approved + non-approved)
  const [rawSelectedTreatments, setRawSelectedTreatments] = useState<string[]>([]);
  // Advanced filters
  const [advancedStage, setAdvancedStage] = useState('all');
  const [advancedBiomarker, setAdvancedBiomarker] = useState('all');

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
      // Pass the URL slug, not the display name — getDbCancerType() maps slugs to DB values.
      // e.g. 'cutaneous-melanoma' → 'Cutaneous Melanoma' (not 'Cutaneous/Metastatic Melanoma')
      cancer_type: categorySlug || undefined,
      modality: modality !== 'all' ? modality : undefined,
      funding_type: fundingType as 'all' | 'industry' | 'non-industry',
      phase: phase !== 'all' ? phase : undefined,
      status: status.length > 0 ? status : undefined,
      limit: 2000, // Request all matching records
    };

    // Add has_metric filter if safety param is selected (and not being used as display metric)
    if (safetyParam !== 'none' && efficacyParam !== 'none') {
      filters.has_metric = safetyParam;
    }

    return filters;
  }, [resourceType, categorySlug, modality, fundingType, phase, status, safetyParam, efficacyParam]);

  // Fetch analytics data from backend with filters
  const { data: analyticsData, isLoading, error } = useQuery({
    queryKey: ['analytics', 'data', apiFilters],
    queryFn: () => analyticsApi.getData(apiFilters),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes (formerly cacheTime)
  });

  const { data: treatmentMetaRaw } = useQuery({
    queryKey: ['analytics', 'treatmentMeta', apiFilters.cancer_type],
    queryFn: () => analyticsApi.getTreatmentMeta(apiFilters.cancer_type ?? 'All'),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [windowHeight, setWindowHeight] = useState(700);
  const [chartType, setChartType] = useState<'bar' | 'diverging' | 'bubble' | 'dumbbell'>(
    modeParam === 'all' ? 'bubble' : 'bar'
  );

  // Compare treatments table state
  const [compareSort, setCompareSort] = useState<CompareSortMode>('most-complete');
  const [compareHideEmpty, setCompareHideEmpty] = useState(false);
  const [compareSelections, setCompareSelections] = useState<CompareSelection[]>([]);
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);

  // Clear selections when mode switches — metric namespace changes
  useEffect(() => {
    setCompareSelections([]);
  }, [mode]);

  const toggleCompareSelection = useCallback((sel: CompareSelection) => {
    setCompareSelections(prev => {
      const idx = prev.findIndex(s => s.treatmentName === sel.treatmentName && s.metricKey === sel.metricKey);
      if (idx >= 0) return prev.filter((_, i) => i !== idx);
      return [...prev, sel];
    });
  }, []);

  // Handle chart type changes - ensure proper filter states
  useEffect(() => {
    if (mode === 'all') {
      if (chartType === 'bar' || chartType === 'dumbbell') {
        const nextChartType = chartType === 'dumbbell' ? 'diverging' : 'bubble';
        setChartType(nextChartType);
      } else if (chartType === 'diverging' || chartType === 'bubble') {
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
        setChartType('diverging');
        if (efficacyParamY === 'none') {
          setEfficacyParamY(efficacyParam === 'OBJECTIVE_RESPONSE_RATE' ? 'DISEASE_CONTROL_RATE' : 'OBJECTIVE_RESPONSE_RATE');
        }
      } else if (efficacyParamY === 'none') {
        setEfficacyParamY(efficacyParam === 'OBJECTIVE_RESPONSE_RATE' ? 'DISEASE_CONTROL_RATE' : 'OBJECTIVE_RESPONSE_RATE');
      }
    } else if (mode === 'safety' && (chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell')) {
      if (chartType === 'bubble') {
        setChartType('diverging');
        if (safetyParamY === 'none') {
          setSafetyParamY(safetyParam === 'GRADE_3_PLUS_AE' ? 'TEAE' : 'GRADE_3_PLUS_AE');
        }
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
      return { approved: [] as string[], nonApproved: [] as string[] };
    }

    // The API already pre-filters by cancer type, so no need to re-filter client-side.
    const categoryTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];

    // Extract unique treatment names from all returned trials
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

      for (const approvedDrug of APPROVED_TREATMENTS_SET) {
        if (normalized.includes(approvedDrug)) {
          isApproved = true;
          break;
        }
      }

      if (!isApproved && normalized.includes('+')) {
        const parts = normalized.split('+').map(p => p.trim());
        const hasApproved = parts.some(part =>
          Array.from(APPROVED_TREATMENTS_SET).some(approved => part.includes(approved))
        );
        if (hasApproved) isApproved = true;
      }

      if (isApproved) {
        approved.push(treatment);
      } else {
        nonApproved.push(treatment);
      }
    }

    return { approved, nonApproved };
  }, [analyticsData]);

  // All available treatments (approved + non-approved merged)
  const allAvailableTreatments = useMemo(
    () => [...availableTherapies.approved, ...availableTherapies.nonApproved].sort(),
    [availableTherapies]
  );

  // Validate raw selections against currently available treatments
  const selectedTreatments = useMemo(
    () => rawSelectedTreatments.filter(t => allAvailableTreatments.includes(t)).slice(0, MAX_COMPARE_TREATMENTS),
    [rawSelectedTreatments, allAvailableTreatments]
  );

  const compareTableData = useMemo(() => {
    const trials = [
      ...((analyticsData?.abstracts as unknown as TrialDataFile['abstracts']) ?? []),
      ...((analyticsData?.publications as unknown as TrialDataFile['publications']) ?? []),
    ];
    let treatmentsForTable = selectedTreatments.length > 0 ? selectedTreatments : allAvailableTreatments;
    if (advancedLineOfTherapy !== 'all' && treatmentMetaRaw) {
      const lineByName = new Map(treatmentMetaRaw.map(m => [m.treatmentName, m.lineOfTreatment]));
      treatmentsForTable = treatmentsForTable.filter(t => lineByName.get(t) === advancedLineOfTherapy);
    }
    if (advancedStage !== 'all' && treatmentMetaRaw) {
      const stageByName = new Map(treatmentMetaRaw.map(m => [m.treatmentName, m.stage]));
      treatmentsForTable = treatmentsForTable.filter(t => stageByName.get(t) === advancedStage);
    }
    if (advancedBiomarker !== 'all' && treatmentMetaRaw) {
      const biomarkerByName = new Map(treatmentMetaRaw.map(m => [m.treatmentName, m.biomarker]));
      treatmentsForTable = treatmentsForTable.filter(t => biomarkerByName.get(t) === advancedBiomarker);
    }
    return buildCompareTable(trials ?? [], treatmentsForTable, mode, treatmentMetaRaw ?? []);
  }, [analyticsData, selectedTreatments, allAvailableTreatments, mode, treatmentMetaRaw, advancedLineOfTherapy, advancedStage, advancedBiomarker]);

  const activeMetricKeys = useMemo(() => {
    const keys: string[] = [];
    if (mode === 'all') {
      if (efficacyParam !== 'none') keys.push(efficacyParam);
      if (safetyParam !== 'none') keys.push(safetyParam);
    } else if (mode === 'efficacy') {
      if (efficacyParam !== 'none') keys.push(efficacyParam);
      if ((chartType === 'diverging' || chartType === 'dumbbell') && efficacyParamY !== 'none') keys.push(efficacyParamY);
    } else if (mode === 'safety') {
      if (safetyParam !== 'none') keys.push(safetyParam);
      if ((chartType === 'diverging' || chartType === 'dumbbell') && safetyParamY !== 'none') keys.push(safetyParamY);
    }
    return keys;
  }, [mode, chartType, efficacyParam, safetyParam, efficacyParamY, safetyParamY]);

  // Derive chart overrides from cell selections. When any cells are selected, they
  // take precedence over the dropdown-bound metric state for driving the chart.
  const compareOverride = useMemo(() => {
    if (compareSelections.length === 0) return null;
    const treatments = Array.from(new Set(compareSelections.map(s => s.treatmentName)));
    const efficacyMetrics: string[] = [];
    const safetyMetrics: string[] = [];
    for (const s of compareSelections) {
      if (EFFICACY_METRICS[s.metricKey] && !efficacyMetrics.includes(s.metricKey)) efficacyMetrics.push(s.metricKey);
      if (SAFETY_METRICS[s.metricKey] && !safetyMetrics.includes(s.metricKey)) safetyMetrics.push(s.metricKey);
    }
    return { treatments, efficacyMetrics, safetyMetrics };
  }, [compareSelections]);

  // Transform data for chart (backend already filtered the data)
  const chartData = useMemo<HeadToHeadDataPoint[]>(() => {
    if (!analyticsData) return [];
    if (!analyticsData.abstracts) return [];

    const targetMetric =
      compareOverride?.efficacyMetrics[0] ||
      compareOverride?.safetyMetrics[0] ||
      displayMetric;
    if (!targetMetric) return [];

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
      targetMetric: targetMetric as ChartMetric,
      minTrialCount: 1,
    });

    // Cell-clicked treatments override picker; if neither, show all
    const filterTreatments = compareOverride?.treatments ?? selectedTreatments;
    if (filterTreatments.length > 0) {
      const normalized = filterTreatments.map(normalizeTreatmentName);
      data = data.filter((d) => normalized.includes(d.treatmentName));
    }

    // Sort by value descending
    data.sort((a, b) => b.averageValue - a.averageValue);

    return data;
  }, [analyticsData, displayMetric, selectedTreatments, compareOverride]);

  // Transform data for diverging bar chart (efficacy vs safety, or efficacy vs efficacy, or safety vs safety)
  const divergingChartData = useMemo<EfficacySafetyDataPoint[]>(() => {
    if (!analyticsData || !analyticsData.abstracts) return [];
    let efficacyMetric: ChartMetric;
    let safetyMetric: ChartMetric;
    if (mode === 'efficacy') {
      const x = compareOverride?.efficacyMetrics[0] ?? efficacyParam;
      const y = compareOverride?.efficacyMetrics[1] ?? efficacyParamY;
      if (x === 'none' || y === 'none') return [];
      efficacyMetric = x as ChartMetric;
      safetyMetric = y as ChartMetric;
    } else if (mode === 'safety') {
      const x = compareOverride?.safetyMetrics[0] ?? safetyParam;
      const y = compareOverride?.safetyMetrics[1] ?? safetyParamY;
      if (x === 'none' || y === 'none') return [];
      efficacyMetric = x as ChartMetric;
      safetyMetric = y as ChartMetric;
    } else {
      const ex = compareOverride?.efficacyMetrics[0] ?? efficacyParam;
      const sy = compareOverride?.safetyMetrics[0] ?? safetyParam;
      if (ex === 'none' || sy === 'none') return [];
      efficacyMetric = ex as ChartMetric;
      safetyMetric = sy as ChartMetric;
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

    const filterTreatments = compareOverride?.treatments ?? selectedTreatments;
    if (filterTreatments.length > 0) {
      const normalized = filterTreatments.map(normalizeTreatmentName);
      data = data.filter((d: EfficacySafetyDataPoint | BubbleChartDataPoint) => normalized.includes(d.treatmentName));
    }

    return data;
  }, [analyticsData, mode, efficacyParam, efficacyParamY, safetyParam, safetyParamY, selectedTreatments, compareOverride]);

  // Transform data for bubble chart (efficacy vs safety, or efficacy vs efficacy, or safety vs safety)
  const bubbleChartData = useMemo<BubbleChartDataPoint[]>(() => {
    if (!analyticsData || !analyticsData.abstracts) return [];
    let efficacyMetric: ChartMetric;
    let safetyMetric: ChartMetric;
    if (mode === 'efficacy') {
      const x = compareOverride?.efficacyMetrics[0] ?? efficacyParam;
      const y = compareOverride?.efficacyMetrics[1] ?? efficacyParamY;
      if (x === 'none' || y === 'none') return [];
      efficacyMetric = x as ChartMetric;
      safetyMetric = y as ChartMetric;
    } else if (mode === 'safety') {
      const x = compareOverride?.safetyMetrics[0] ?? safetyParam;
      const y = compareOverride?.safetyMetrics[1] ?? safetyParamY;
      if (x === 'none' || y === 'none') return [];
      efficacyMetric = x as ChartMetric;
      safetyMetric = y as ChartMetric;
    } else {
      const ex = compareOverride?.efficacyMetrics[0] ?? efficacyParam;
      const sy = compareOverride?.safetyMetrics[0] ?? safetyParam;
      if (ex === 'none' || sy === 'none') return [];
      efficacyMetric = ex as ChartMetric;
      safetyMetric = sy as ChartMetric;
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

    const filterTreatments = compareOverride?.treatments ?? selectedTreatments;
    if (filterTreatments.length > 0) {
      const normalized = filterTreatments.map(normalizeTreatmentName);
      data = data.filter((d: EfficacySafetyDataPoint | BubbleChartDataPoint) => normalized.includes(d.treatmentName));
    }

    return data;
  }, [analyticsData, mode, efficacyParam, efficacyParamY, safetyParam, safetyParamY, zAxisParam, selectedTreatments, compareOverride]);

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
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto flex max-w-7xl flex-col px-6 py-8">
        <PageHeader
          category={categoryName}
          title={hubTitle}
          description={hubDescription}
        />

      {/* Mode Banner with Parameter Selection - Compact, professional design */}
      {mode === 'all' && (
        <div className="mt-6 rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          <div className="px-4 md:px-6 py-3">
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-7 h-7 bg-(--brand-accent-light) rounded-md">
                  <TrendingUp className="h-4 w-4 text-(--brand-primary)" />
                </div>
                <p className="text-xs font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
                  Axes &amp; metrics
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto">
                {chartType === 'bubble' && (['x', 'y', 'z'] as const).map((axis) => (
                  <div key={axis} className="w-full sm:w-72 flex gap-2">
                    {efficacyAxis === axis && (
                      <>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 w-14 items-center justify-center rounded-md border border-(--brand-border) bg-(--brand-accent-light) px-2 text-xs font-bold text-(--brand-primary) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)" title={`Assign to ${axis.toUpperCase()}-axis`}>
                              <span className="font-mono">{axis.toUpperCase()}</span>
                              <ChevronDown className="h-3 w-3 text-[var(--brand-primary)]/60 flex-shrink-0 ml-1" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="w-28">
                            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 border-b">Assign to Axis</div>
                            {(['x', 'y', 'z'] as const).map((a) => (
                              <DropdownMenuItem key={a} className={`text-sm cursor-pointer ${efficacyAxis === a ? 'bg-[var(--brand-accent-light)] text-[var(--brand-primary)] font-medium' : ''}`} onClick={() => handleAxisChange('efficacy', a)}>
                                <div className="flex items-center justify-between w-full"><span className="font-mono font-medium">{a.toUpperCase()}-axis</span>{efficacyAxis === a && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 flex-1 items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                              <span className="flex items-center gap-2 truncate font-medium">{EFFICACY_OPTIONS_NO_HR.find(o => o.value === efficacyParam)?.label || 'Select...'}</span>
                              <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                            <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                              <input type="text" value={efficacySearch} placeholder="Search efficacy metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)]" onChange={(e) => setEfficacySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                            </div>
                            {EFFICACY_OPTIONS_NO_HR.filter(option => option.value !== 'none' && option.label.toLowerCase().includes(efficacySearch.toLowerCase())).map(option => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${efficacyParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => { setEfficacyParamWithMode(option.value); setEfficacySearch(''); }}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{efficacyParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
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
                            <button className="flex h-9 w-14 items-center justify-center rounded-md border border-(--brand-border) bg-(--brand-accent-light) px-2 text-xs font-bold text-(--brand-primary) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)" title={`Assign to ${axis.toUpperCase()}-axis`}>
                              <span className="font-mono">{axis.toUpperCase()}</span>
                              <ChevronDown className="h-3 w-3 text-[var(--brand-primary)]/60 flex-shrink-0 ml-1" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="w-28">
                            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 border-b">Assign to Axis</div>
                            {(['x', 'y', 'z'] as const).map((a) => (
                              <DropdownMenuItem key={a} className={`text-sm cursor-pointer ${safetyAxis === a ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => handleAxisChange('safety', a)}>
                                <div className="flex items-center justify-between w-full"><span className="font-mono font-medium">{a.toUpperCase()}-axis</span>{safetyAxis === a && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 flex-1 items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                              <span className="flex items-center gap-2 truncate font-medium">{SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label || 'Select...'}</span>
                              <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                            <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                              <input type="text" value={safetySearch} placeholder="Search safety metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)]" onChange={(e) => setSafetySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                            </div>
                            {SAFETY_OPTIONS.filter(option => option.value !== 'none' && option.label.toLowerCase().includes(safetySearch.toLowerCase())).map(option => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${safetyParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => { setSafetyParamWithMode(option.value); setSafetySearch(''); }}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{safetyParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
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
                            <button className="flex h-9 w-14 items-center justify-center rounded-md border border-(--brand-border) bg-(--brand-accent-light) px-2 text-xs font-bold text-(--brand-primary) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)" title={`Assign to ${axis.toUpperCase()}-axis`}>
                              <span className="font-mono">{axis.toUpperCase()}</span>
                              <ChevronDown className="h-3 w-3 text-[var(--brand-primary)]/60 flex-shrink-0 ml-1" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="w-28">
                            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 border-b">Assign to Axis</div>
                            {(['x', 'y', 'z'] as const).map((a) => (
                              <DropdownMenuItem key={a} className={`text-sm cursor-pointer ${zParamAxis === a ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => handleAxisChange('zParam', a)}>
                                <div className="flex items-center justify-between w-full"><span className="font-mono font-medium">{a.toUpperCase()}-axis</span>{zParamAxis === a && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="flex h-9 flex-1 items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                              <span className="flex items-center gap-2 truncate font-medium">{Z_AXIS_OPTIONS.find((o) => o.value === zAxisParam)?.label || 'Select...'}</span>
                              <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                            {Z_AXIS_OPTIONS.map((option) => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${zAxisParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => setZAxisParam(option.value)}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{zAxisParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
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
                          <button disabled={mode === 'all' && chartType === 'bar' && safetyParam !== 'none' && safetyParam !== ''} className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) disabled:opacity-50 disabled:cursor-not-allowed">
                            <span className="flex items-center gap-2 truncate font-medium">{EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label || 'Select...'}</span>
                            <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                          <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                            <input type="text" value={efficacySearch} placeholder="Search efficacy metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)]" onChange={(e) => setEfficacySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                          </div>
                          {EFFICACY_OPTIONS.filter(option => (chartType === 'diverging' || chartType === 'bar' ? option.value !== 'none' : true) && option.label.toLowerCase().includes(efficacySearch.toLowerCase())).map(option => (
                              <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${efficacyParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => { setEfficacyParamWithMode(option.value); setEfficacySearch(''); }}>
                                <div className="flex items-center justify-between w-full"><span>{option.label}</span>{efficacyParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
                              </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <div className="w-full sm:w-72">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button disabled={mode === 'all' && chartType === 'bar' && efficacyParam !== 'none' && efficacyParam !== ''} className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) disabled:opacity-50 disabled:cursor-not-allowed">
                            <span className="flex items-center gap-2 truncate font-medium">{SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label || 'Select...'}</span>
                            <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                          <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                            <input type="text" value={safetySearch} placeholder="Search safety metrics..." className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)]" onChange={(e) => setSafetySearch(e.target.value)} onClick={(e) => e.stopPropagation()} />
                          </div>
                          {SAFETY_OPTIONS.filter(option => (chartType === 'diverging' || chartType === 'bar' ? option.value !== 'none' : true) && option.label.toLowerCase().includes(safetySearch.toLowerCase())).map(option => (
                            <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${safetyParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => { setSafetyParamWithMode(option.value); setSafetySearch(''); }}>
                              <div className="flex items-center justify-between w-full"><span>{option.label}</span>{safetyParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
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
        <div className="mt-6 rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          <div className="px-4 md:px-6 py-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-7 h-7 bg-(--brand-accent-light) rounded-md">
                  <TrendingUp className="h-4 w-4 text-(--brand-primary)" />
                </div>
                <p className="text-xs font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
                  Efficacy parameters
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                <div className={chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell' ? 'w-full sm:w-72' : 'w-full sm:w-80'}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                        <span className="flex items-center gap-2 truncate font-medium">
                          <span className="text-xs text-(--brand-text-muted)">{chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell' ? 'X-axis:' : 'Parameter:'}</span>
                          {EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label || 'Select...'}
                        </span>
                        <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                      <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                        <input
                          type="text"
                          value={efficacySearch}
                          placeholder="Search efficacy metrics..."
                          className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)]"
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
                          className={`text-sm cursor-pointer ${efficacyParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`}
                          onClick={() => {
                            setEfficacyParamWithMode(option.value);
                            setEfficacySearch('');
                          }}
                        >
                          <div className="flex items-center justify-between w-full">
                            <span>{option.label}</span>
                            {efficacyParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}
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
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-(--brand-text-muted)">Y-axis:</span>
                            {EFFICACY_OPTIONS.find(o => o.value === efficacyParamY)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
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
                            className={`text-sm cursor-pointer ${efficacyParamY === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`}
                            onClick={() => setEfficacyParamY(option.value)}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span>{option.label}</span>
                              {efficacyParamY === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}
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
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-(--brand-text-muted)">Z-axis:</span>
                            {Z_AXIS_OPTIONS.find((o) => o.value === zAxisParam)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                        {Z_AXIS_OPTIONS.map((option) => (
                          <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${zAxisParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => setZAxisParam(option.value)}>
                            <div className="flex items-center justify-between w-full"><span>{option.label}</span>{zAxisParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
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
        <div className="mt-6 rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          <div className="px-4 md:px-6 py-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-7 h-7 bg-(--brand-accent-light) rounded-md">
                  <AlertCircle className="h-4 w-4 text-(--brand-primary)" />
                </div>
                <p className="text-xs font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
                  Safety parameters
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                <div className={chartType === 'diverging' || chartType === 'bubble' ? 'w-full sm:w-72' : 'w-full sm:w-80'}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                        <span className="flex items-center gap-2 truncate font-medium">
                          <span className="text-xs text-(--brand-text-muted)">{chartType === 'diverging' || chartType === 'bubble' ? 'X-axis:' : 'Parameter:'}</span>
                          {(chartType === 'bubble' ? SAFETY_BUBBLE_XY_OPTIONS : SAFETY_OPTIONS).find(o => o.value === safetyParam)?.label || 'Select...'}
                        </span>
                        <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                      <div className="px-3 py-2 sticky top-0 bg-white border-b z-10">
                        <input
                          type="text"
                          value={safetySearch}
                          placeholder="Search safety metrics..."
                          className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)]"
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
                          className={`text-sm cursor-pointer ${safetyParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`}
                          onClick={() => {
                            setSafetyParamWithMode(option.value);
                            setSafetySearch('');
                          }}
                        >
                          <div className="flex items-center justify-between w-full">
                            <span>{option.label}</span>
                            {safetyParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}
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
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-(--brand-text-muted)">Y-axis:</span>
                            {(chartType === 'bubble' ? SAFETY_BUBBLE_XY_OPTIONS : SAFETY_OPTIONS).find(o => o.value === safetyParamY)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
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
                            className={`text-sm cursor-pointer ${safetyParamY === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`}
                            onClick={() => setSafetyParamY(option.value)}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span>{option.label}</span>
                              {safetyParamY === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}
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
                        <button className="flex h-9 w-full items-center justify-between rounded-md border border-(--brand-border) bg-(--brand-surface) px-3 text-sm text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)">
                          <span className="flex items-center gap-2 truncate font-medium">
                            <span className="text-xs text-(--brand-text-muted)">Z-axis:</span>
                            {Z_AXIS_OPTIONS_SAFETY.find((o) => o.value === zAxisParam)?.label || 'Select...'}
                          </span>
                          <ChevronDown className="h-3.5 w-3.5 text-[var(--brand-primary)]/60 flex-shrink-0" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-72 overflow-y-auto">
                        {Z_AXIS_OPTIONS_SAFETY.map((option) => (
                          <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${zAxisParam === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => setZAxisParam(option.value)}>
                            <div className="flex items-center justify-between w-full"><span>{option.label}</span>{zAxisParam === option.value && <Check className="h-4 w-4 text-[var(--brand-primary)]" />}</div>
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

      {/* Main Content — Filter Bar + Chart */}
      <div className="mt-2 flex flex-col rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)] overflow-hidden">
        {/* Compact Filter Bar */}
        <div className="border-b border-(--brand-border) px-4 py-2 flex-shrink-0">
          <div className="flex items-center gap-2 flex-wrap">
            <FilterChips
              label="FUNDING"
              size="sm"
              options={FUNDING_TYPE_OPTIONS}
              value={fundingType}
              onChange={(value) => setFundingType(value as 'all' | 'industry' | 'non-industry')}
            />
            <div className="w-px h-4 bg-(--brand-border)" />
            <FilterChips
              label="PHASE"
              size="sm"
              options={PHASE_FILTER_OPTIONS}
              value={phase}
              onChange={setPhase}
            />
            {/* Status arrives from a hand-off link and is applied to the query,
                but it is not a chip: STATUS_OPTIONS here (Open/Closed/…) is a
                different vocabulary from the nine CT.gov values the agent emits,
                and the agent can send several at once. Reconciling the two
                vocabularies is its own job; carrying the filter honestly is not.
                ponytail: read-only pill, promote to a real control when someone
                needs to set status from the hub itself. */}
            {status.length > 0 ? (
              <>
                <div className="w-px h-4 bg-(--brand-border)" />
                <button
                  type="button"
                  onClick={() => setStatus([])}
                  title="Clear status filter"
                  className={cn(
                    'inline-flex items-center gap-1.5 h-7 rounded-full border border-(--brand-border)',
                    'bg-(--brand-accent-light) pl-2.5 pr-2 text-xs text-(--brand-primary) transition',
                    'hover:border-(--brand-primary)'
                  )}
                >
                  <span
                    className="font-medium uppercase tracking-[0.1em] text-[10px] opacity-70"
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    STATUS
                  </span>
                  <span className="font-medium">
                    {status.map((value) => STATUS_MAP[value] ?? value).join(', ')}
                  </span>
                  <X className="h-3 w-3 flex-shrink-0 opacity-70" />
                </button>
              </>
            ) : null}
            <div className="w-px h-4 bg-(--brand-border)" />
            <FilterChips
              label="LINE"
              size="sm"
              options={ADVANCED_LINE_OF_THERAPY_OPTIONS}
              value={advancedLineOfTherapy}
              onChange={setAdvancedLineOfTherapy}
            />
            <div className="w-px h-4 bg-(--brand-border)" />
            <FilterChips
              label="RESOURCE"
              size="sm"
              options={RESOURCE_TYPE_OPTIONS.map(({ value, label }) => ({ value, label }))}
              value={resourceType}
              onChange={(value) => setResourceType(value as 'all' | 'conference' | 'publication')}
            />
            <div className="w-px h-4 bg-(--brand-border)" />
            {/* Modality inline select */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="inline-flex items-center gap-1 h-7 rounded-md border border-(--brand-border) bg-(--brand-surface) pl-2.5 pr-2 text-xs text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-1 focus-visible:ring-(--brand-primary)">
                  <span className="font-medium text-(--brand-text-muted) uppercase tracking-[0.1em] text-[10px]" style={{ fontFamily: 'var(--font-mono)' }}>MODALITY</span>
                  <span className="font-medium truncate max-w-[80px]">{MODALITY_OPTIONS.find(o => o.value === modality)?.label ?? 'All'}</span>
                  <ChevronDown className="h-3 w-3 text-(--brand-text-muted) flex-shrink-0" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-52 max-h-72 overflow-y-auto">
                {MODALITY_OPTIONS.map(option => (
                  <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${modality === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => setModality(option.value)}>
                    <div className="flex items-center justify-between w-full"><span>{option.label}</span>{modality === option.value && <Check className="h-3.5 w-3.5 text-[var(--brand-primary)]" />}</div>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            {/* Treatments inline select */}
            <DropdownMenu open={undefined}>
              <DropdownMenuTrigger asChild>
                <button
                  className="inline-flex items-center gap-1 h-7 rounded-md border border-(--brand-border) bg-(--brand-surface) pl-2.5 pr-2 text-xs text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-1 focus-visible:ring-(--brand-primary)"
                  onClick={() => {}}
                >
                  <span className="font-medium text-(--brand-text-muted) uppercase tracking-[0.1em] text-[10px]" style={{ fontFamily: 'var(--font-mono)' }}>TREATMENTS</span>
                  <span className="font-medium">{selectedTreatments.length === 0 ? 'All' : `${selectedTreatments.length} selected`}</span>
                  <ChevronDown className="h-3 w-3 text-(--brand-text-muted) flex-shrink-0" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56 p-2 max-h-64 overflow-y-auto">
                {selectedTreatments.length > 0 && (
                  <button onClick={() => setRawSelectedTreatments([])} className="w-full text-left text-xs text-(--brand-primary) hover:text-(--brand-primary) mb-2 flex items-center gap-1">
                    <X className="h-3 w-3" /> Clear
                  </button>
                )}
                {allAvailableTreatments.map(option => (
                  <label key={option} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm transition-colors ${selectedTreatments.includes(option) ? 'bg-(--brand-accent-light) text-(--brand-primary)' : 'hover:bg-gray-50 text-gray-700'} ${!selectedTreatments.includes(option) && selectedTreatments.length >= 5 ? 'opacity-40 cursor-not-allowed' : ''}`}>
                    <input type="checkbox" checked={selectedTreatments.includes(option)} onChange={() => {
                      if (selectedTreatments.includes(option)) setRawSelectedTreatments(selectedTreatments.filter(t => t !== option));
                      else if (selectedTreatments.length < 5) setRawSelectedTreatments([...selectedTreatments, option]);
                    }} disabled={!selectedTreatments.includes(option) && selectedTreatments.length >= 5} className="rounded border-(--brand-border) text-(--brand-primary) focus:ring-(--brand-primary)" />
                    <span className="truncate">{option}</span>
                  </label>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <div className="w-px h-4 bg-(--brand-border)" />
            {/* Advanced filters popover */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setAdvancedFiltersOpen(o => !o)}
                className={cn(
                  'inline-flex items-center gap-1 h-7 rounded-md border px-2.5 text-xs font-medium transition-all',
                  advancedFiltersOpen
                    ? 'border-(--brand-primary) bg-(--brand-accent-light) text-(--brand-primary)'
                    : 'border-(--brand-border) bg-(--brand-surface) text-(--brand-text-muted) hover:border-(--brand-primary) hover:text-(--brand-primary)',
                )}
              >
                Advanced
                <ChevronDown className={cn('h-3 w-3 transition-transform', advancedFiltersOpen && 'rotate-180')} />
              </button>
              {advancedFiltersOpen && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setAdvancedFiltersOpen(false)} />
                  <div className="absolute left-0 top-full mt-1.5 z-40 w-max rounded-xl border border-(--brand-border) bg-(--brand-surface) shadow-xl p-4">
                    <div className="text-[10px] font-semibold text-(--brand-text-muted) uppercase tracking-[0.14em] mb-3" style={{ fontFamily: 'var(--font-mono)' }}>Advanced filters</div>
                    <div className="flex items-center gap-2">
                      {/* Stage inline select */}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className="inline-flex items-center gap-1 h-7 rounded-md border border-(--brand-border) bg-(--brand-surface) pl-2.5 pr-2 text-xs text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-1 focus-visible:ring-(--brand-primary)">
                            <span className="font-medium text-(--brand-text-muted) uppercase tracking-[0.1em] text-[10px]" style={{ fontFamily: 'var(--font-mono)' }}>STAGE</span>
                            <span className="font-medium truncate max-w-[80px]">{ADVANCED_STAGE_OPTIONS.find(o => o.value === advancedStage)?.label ?? 'All'}</span>
                            <ChevronDown className="h-3 w-3 text-(--brand-text-muted) flex-shrink-0" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start" className="w-52 max-h-72 overflow-y-auto">
                          {ADVANCED_STAGE_OPTIONS.map(option => (
                            <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${advancedStage === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => setAdvancedStage(option.value)}>
                              <div className="flex items-center justify-between w-full"><span>{option.label}</span>{advancedStage === option.value && <Check className="h-3.5 w-3.5 text-[var(--brand-primary)]" />}</div>
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                      {/* Biomarker inline select */}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className="inline-flex items-center gap-1 h-7 rounded-md border border-(--brand-border) bg-(--brand-surface) pl-2.5 pr-2 text-xs text-(--brand-text) transition-all hover:border-(--brand-primary) focus:outline-none focus-visible:ring-1 focus-visible:ring-(--brand-primary)">
                            <span className="font-medium text-(--brand-text-muted) uppercase tracking-[0.1em] text-[10px]" style={{ fontFamily: 'var(--font-mono)' }}>BIOMARKER</span>
                            <span className="font-medium truncate max-w-[80px]">{ADVANCED_BIOMARKER_OPTIONS.find(o => o.value === advancedBiomarker)?.label ?? 'All'}</span>
                            <ChevronDown className="h-3 w-3 text-(--brand-text-muted) flex-shrink-0" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start" className="w-52 max-h-72 overflow-y-auto">
                          {ADVANCED_BIOMARKER_OPTIONS.map(option => (
                            <DropdownMenuItem key={option.value} className={`text-sm cursor-pointer ${advancedBiomarker === option.value ? 'bg-(--brand-accent-light) text-(--brand-primary) font-medium' : ''}`} onClick={() => setAdvancedBiomarker(option.value)}>
                              <div className="flex items-center justify-between w-full"><span>{option.label}</span>{advancedBiomarker === option.value && <Check className="h-3.5 w-3.5 text-[var(--brand-primary)]" />}</div>
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="flex-1" />
            {/* Reset */}
            <button
              type="button"
              className="inline-flex items-center h-7 rounded-md border border-(--brand-border) px-2.5 text-xs font-medium text-(--brand-text-muted) hover:border-(--brand-primary) hover:text-(--brand-primary) transition-colors"
              onClick={() => {
                setModality('all'); setResourceType('all'); setFundingType('industry');
                setAdvancedLineOfTherapy('all'); setRawSelectedTreatments([]);
                setAdvancedStage('all'); setAdvancedBiomarker('all');
                setEfficacyParamY('none'); setSafetyParamY('none');
                if (mode === 'safety') { setEfficacyParam('none'); setSafetyParam('GRADE_3_PLUS_AE'); }
                else if (mode === 'efficacy') { setEfficacyParam('OBJECTIVE_RESPONSE_RATE'); setSafetyParam('none'); }
                else { setEfficacyParam('OBJECTIVE_RESPONSE_RATE'); setSafetyParam('GRADE_3_PLUS_AE'); }
              }}
            >
              Reset
            </button>
          </div>
        </div>

        {/* Chart */}
        <main className="flex flex-col bg-(--brand-surface)" style={{ minHeight: '640px' }}>
          {/* Compact Chart Header */}
          <div className="px-4 py-3 bg-(--brand-bg) border-b border-(--brand-border) flex items-center justify-between gap-3 flex-shrink-0">
            {/* Export Buttons */}
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="h-8 px-3 gap-1.5 text-slate-600 hover:text-emerald-600 hover:border-emerald-300 hover:bg-emerald-50" disabled={isLoading || chartData.length === 0}>
                <FileSpreadsheet className="h-3.5 w-3.5" />
                Excel
              </Button>
              <Button variant="outline" size="sm" className="h-8 px-3 gap-1.5 text-slate-600 hover:text-orange-600 hover:border-orange-300 hover:bg-orange-50" disabled={isLoading || chartData.length === 0}>
                <Presentation className="h-3.5 w-3.5" />
                PPT
              </Button>
              <Button variant="outline" size="sm" className="h-8 px-3 gap-1.5 text-slate-600 hover:text-red-600 hover:border-red-300 hover:bg-red-50" disabled={isLoading || chartData.length === 0}>
                <FileText className="h-3.5 w-3.5" />
                PDF
              </Button>
            </div>
            <div className="flex items-center gap-3">
            {/* Chart type label + selector - Show in all Head to Head modes */}
            {(mode === 'all' || mode === 'efficacy' || mode === 'safety') && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-(--brand-text-muted) uppercase tracking-[0.12em]" style={{ fontFamily: 'var(--font-mono)' }}>Chart type</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="group h-10 pl-3 pr-3.5 gap-2.5 rounded-xl border border-slate-200/80 bg-white text-slate-700 font-medium shadow-sm transition-all duration-200 hover:bg-slate-50 hover:border-[var(--brand-border)] hover:text-[var(--brand-primary)] hover:shadow-md focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)]/20 focus-visible:border-[var(--brand-border)]"
                    >
                      <span className="flex h-7 w-7 items-center justify-center text-[var(--brand-primary)]">
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
                    {mode !== 'all' && (
                      <DropdownMenuItem
                        onClick={() => setChartType('bar')}
                        className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                      >
                        <BarChart3 className="h-4 w-4 text-slate-500" />
                        <span>Bar Chart</span>
                        {chartType === 'bar' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem
                      onClick={() => setChartType('diverging')}
                      className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                    >
                      <TrendingUp className="h-4 w-4 text-slate-500" />
                      <span>Diverging Chart</span>
                      {chartType === 'diverging' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
                    </DropdownMenuItem>
                    {mode === 'all' && (
                      <DropdownMenuItem
                        onClick={() => setChartType('bubble')}
                        className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                      >
                        <CircleDot className="h-4 w-4 text-slate-500" />
                        <span>Bubble Chart</span>
                        {chartType === 'bubble' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
                      </DropdownMenuItem>
                    )}
                    {mode === 'efficacy' && (
                      <DropdownMenuItem
                        onClick={() => setChartType('dumbbell')}
                        className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                      >
                        <Minus className="h-4 w-4 text-slate-500" />
                        <span>Dumbbell Chart</span>
                        {chartType === 'dumbbell' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
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
              className="h-10 w-10 rounded-xl border border-slate-200/80 bg-white text-slate-600 shadow-sm transition-all duration-200 hover:bg-slate-50 hover:border-[var(--brand-border)] hover:text-[var(--brand-primary)] hover:shadow-md focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)]/20"
              title="Full Screen"
              onClick={() => setIsFullscreen(true)}
            >
              <Maximize2 className="h-4 w-4" />
            </Button>
            </div>
          </div>

          {/* Chart Area */}
          <div className="flex-1 flex flex-col" style={{ minHeight: '540px' }}>
            <div className="flex-1 relative" style={{ minHeight: '500px' }}>
              <div className="absolute inset-0 w-full h-full">
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3">
                    <Loader2 className="h-8 w-8 animate-spin text-[var(--brand-primary)]" />
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

          </div>
        </main>
      </div>

      {/* Compare Table — separate card */}
      <div className="mt-2 flex flex-col rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)] overflow-hidden" style={{ minHeight: '600px', maxHeight: '80vh' }}>
        <CompareTable
          data={compareTableData}
          mode={mode}
          title={`Compare treatments — ${categoryName}`}
          sort={compareSort}
          onSortChange={setCompareSort}
          hideEmpty={compareHideEmpty}
          onHideEmptyChange={setCompareHideEmpty}
          selections={compareSelections}
          onToggleSelection={toggleCompareSelection}
          activeMetricKeys={activeMetricKeys}
        />
      </div>
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-(--brand-bg) flex flex-col">
          {/* Fullscreen Header */}
          <div className="border-b border-(--brand-border) bg-(--brand-surface) shadow-sm flex-shrink-0">
            <div className="px-6 py-3 flex items-center justify-between">
              <span
                className="text-sm font-semibold text-(--brand-text)"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {hubTitle}
              </span>
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
                          className="group h-10 pl-3.5 pr-4 gap-2.5 rounded-xl border border-slate-200/80 bg-white text-slate-700 font-medium shadow-sm transition-all duration-200 hover:bg-slate-50 hover:border-[var(--brand-border)] hover:text-[var(--brand-primary)] hover:shadow-md focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)]/20 focus-visible:border-[var(--brand-border)]"
                        >
                          <span className="flex h-7 w-7 items-center justify-center text-[var(--brand-primary)]">
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
                        {mode !== 'all' && (
                          <DropdownMenuItem
                            onClick={() => setChartType('bar')}
                            className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                          >
                            <BarChart3 className="h-4 w-4 text-slate-500" />
                            <span>Bar Chart</span>
                            {chartType === 'bar' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          onClick={() => setChartType('diverging')}
                          className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                        >
                          <TrendingUp className="h-4 w-4 text-slate-500" />
                          <span>Diverging Chart</span>
                          {chartType === 'diverging' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
                        </DropdownMenuItem>
                        {mode === 'all' && (
                          <DropdownMenuItem
                            onClick={() => setChartType('bubble')}
                            className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                          >
                            <CircleDot className="h-4 w-4 text-slate-500" />
                            <span>Bubble Chart</span>
                            {chartType === 'bubble' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
                          </DropdownMenuItem>
                        )}
                        {mode === 'efficacy' && (
                          <DropdownMenuItem
                            onClick={() => setChartType('dumbbell')}
                            className="flex items-center gap-3 rounded-lg py-2.5 cursor-pointer focus:bg-[var(--brand-accent-light)] focus:text-[var(--brand-primary)]"
                          >
                            <Minus className="h-4 w-4 text-slate-500" />
                            <span>Dumbbell Chart</span>
                            {chartType === 'dumbbell' && <Check className="h-4 w-4 ml-auto text-[var(--brand-primary)]" />}
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

          {/* Mode summary strip in Fullscreen */}
          {mode === 'all' && (
            <div className="border-b border-(--brand-border) bg-(--brand-bg) px-6 py-2">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center justify-center w-6 h-6 bg-(--brand-accent-light) rounded">
                  <TrendingUp className="h-3.5 w-3.5 text-(--brand-primary)" />
                </div>
                <span className="text-xs text-(--brand-text-muted)">Efficacy: <span className="text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>{EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label}</span></span>
                <span className="w-px h-3 bg-(--brand-border) mx-1" />
                <span className="text-xs text-(--brand-text-muted)">Safety: <span className="text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>{SAFETY_OPTIONS.find(o => o.value === safetyParam)?.label}</span></span>
              </div>
            </div>
          )}
          {mode === 'efficacy' && (
            <div className="border-b border-(--brand-border) bg-(--brand-bg) px-6 py-2">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center justify-center w-6 h-6 bg-(--brand-accent-light) rounded">
                  <TrendingUp className="h-3.5 w-3.5 text-(--brand-primary)" />
                </div>
                <span className="text-xs text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>
                  {(chartType === 'diverging' || chartType === 'bubble' || chartType === 'dumbbell') && efficacyParamY !== 'none'
                    ? `${EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label} vs ${EFFICACY_OPTIONS.find(o => o.value === efficacyParamY)?.label}`
                    : EFFICACY_OPTIONS.find(o => o.value === efficacyParam)?.label}
                </span>
              </div>
            </div>
          )}
          {mode === 'safety' && (
            <div className="border-b border-(--brand-border) bg-(--brand-bg) px-6 py-2">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center justify-center w-6 h-6 bg-(--brand-accent-light) rounded">
                  <AlertCircle className="h-3.5 w-3.5 text-(--brand-primary)" />
                </div>
                <span className="text-xs text-(--brand-text)" style={{ fontFamily: 'var(--font-mono)' }}>
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
                  <Loader2 className="h-10 w-10 animate-spin text-[var(--brand-primary)]" />
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
                      bottomMargin={140}
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
