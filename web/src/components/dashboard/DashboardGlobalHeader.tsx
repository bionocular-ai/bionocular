'use client';

/**
 * Global banner (stats + Oncology / Category dropdowns) is disabled; callers still pass props for API stability.
 */
export interface DashboardGlobalHeaderProps {
  cancerTypeSlug: string;
  onCancerTypeChange: (slug: string) => void;
  className?: string;
}

export function DashboardGlobalHeader(props: DashboardGlobalHeaderProps) {
  void props;
  return null;

  // Global banner (stats + Oncology / Category dropdowns) — restore when re-enabling UI:
  // import * as React from 'react';
  // import { useQuery } from '@tanstack/react-query';
  // import { ChevronDown, Check } from 'lucide-react';
  // import { DashboardStats } from '@/components/dashboard/DashboardStats';
  // import { trialsApi } from '@/lib/api';
  // import { DASHBOARD_CANCER_TYPES } from '@/lib/dashboard-constants';
  // const [oncologyDropdownOpen, setOncologyDropdownOpen] = React.useState(false);
  // const [cancerTypeDropdownOpen, setCancerTypeDropdownOpen] = React.useState(false);
  // const { data: statsData } = useQuery({ queryKey: ['landscape-stats', cancerTypeSlug], ... });
  // const selectedStats = statsData?.selected_type_stats ?? null;
  // return (
  //   <section className={...} aria-label="Global context: cancer type and stats">
  //     ... DashboardStats, dropdowns using DASHBOARD_CANCER_TYPES, onCancerTypeChange ...
  //   </section>
  // );
}
