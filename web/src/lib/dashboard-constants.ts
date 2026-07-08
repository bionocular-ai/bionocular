import type { ComponentType, SVGProps } from 'react';
import {
  ClipboardList,
  Newspaper,
  Target,
  TrendingUp,
  ShieldCheck,
  Scale,
  Workflow,
  Landmark,
  Sparkles,
} from 'lucide-react';
import { SurvivalCurveIcon } from '@/components/icons/SurvivalCurveIcon';

type NavIcon = ComponentType<SVGProps<SVGSVGElement>>;

/** Cancer type options for dashboard dropdown (slug + display label). */
export const DASHBOARD_CANCER_TYPES = [
  { value: 'cutaneous-melanoma', label: 'Cutaneous/Metastatic Melanoma' },
  { value: 'acral-melanoma', label: 'Acral Melanoma' },
  { value: 'mucosal-melanoma', label: 'Mucosal Melanoma' },
  { value: 'uveal-melanoma', label: 'Uveal Melanoma' },
  { value: 'cutaneous-melanoma-with-brain-cns-metastasis', label: 'Cutaneous Melanoma with Brain/CNS Metastasis' },
  { value: 'cutaneous-squamous-cell-carcinoma', label: 'Cutaneous Squamous Cell Carcinoma' },
  { value: 'merkel-cell-carcinoma', label: 'Merkel Cell Carcinoma' },
  { value: 'basal-cell-carcinoma', label: 'Basal Cell Carcinoma' },
] as const;

/** Slug → display-name map, derived from DASHBOARD_CANCER_TYPES (single source of truth). */
export const CATEGORY_SLUG_MAP: Record<string, string> = Object.fromEntries(
  DASHBOARD_CANCER_TYPES.map((t) => [t.value, t.label]),
);

export function slugToCategory(slug: string): string {
  return CATEGORY_SLUG_MAP[slug] || slug
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export type DashboardNavStatus = 'live' | 'upcoming';

export interface DashboardNavItem {
  key: string;
  label: string;
  icon: NavIcon;
  section?: string;
  query?: Record<string, string>;
  status: DashboardNavStatus;
  /** Optional submenu items, rendered nested below this item. */
  children?: DashboardNavItem[];
}

export const DASHBOARD_NAV_ITEMS: DashboardNavItem[] = [
  { key: 'trial-updates',       label: 'Trial Updates',              icon: ClipboardList, section: 'trial-updates',       status: 'live' },
  { key: 'live-news',           label: 'Live News',                  icon: Newspaper,     section: 'live-ticker',         status: 'live' },
  { key: 'landscape',           label: 'Trial Landscape',            icon: Target,        section: 'landscape',           status: 'live' },
  {
    key: 'efficacy', label: 'Efficacy Intelligence Hub', icon: TrendingUp, section: 'analytics', query: { mode: 'efficacy' }, status: 'live',
    children: [
      { key: 'survival', label: 'Survival Intelligence Hub', icon: SurvivalCurveIcon, section: 'head-to-head-survival', status: 'live' },
    ],
  },
  { key: 'safety',              label: 'Safety Intelligence Hub',    icon: ShieldCheck,   section: 'analytics', query: { mode: 'safety' },   status: 'live' },
  { key: 'index',               label: 'Efficacy vs Safety Index Hub', icon: Scale,       section: 'analytics', query: { mode: 'all' },      status: 'live' },
  { key: 'treatment-algorithm', label: 'Treatment Algorithm',        icon: Workflow,                                                         status: 'upcoming' },
  { key: 'regulatory',          label: 'Regulatory Timeline',        icon: Landmark,      section: 'regulatory-timeline',                    status: 'upcoming' },
  { key: 'ai-agent',            label: 'AI Agent',                   icon: Sparkles,                                                         status: 'upcoming' },
];

export const DEFAULT_CANCER_TYPE_SLUG = 'cutaneous-melanoma';

/** Phase options for filter (display names). */
export const PHASE_OPTIONS = [
  'Early Phase 1',
  'Phase 1',
  'Phase 2',
  'Phase 3',
  'Phase 4',
  'Not applicable',
] as const;

/** Status options for filter (match study_status on trial cards). */
export const STATUS_OPTIONS = [
  'Open',
  'Closed',
  'Suspended',
  'Enrolling by invitation',
  'Unknown',
] as const;
