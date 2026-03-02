'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, Check } from 'lucide-react';
import { DashboardStats } from '@/components/dashboard/DashboardStats';
import { trialsApi } from '@/lib/api';
import { DASHBOARD_CANCER_TYPES } from '@/lib/dashboard-constants';

export interface DashboardGlobalHeaderProps {
  cancerTypeSlug: string;
  onCancerTypeChange: (slug: string) => void;
  className?: string;
}

export function DashboardGlobalHeader({
  cancerTypeSlug,
  onCancerTypeChange,
  className,
}: DashboardGlobalHeaderProps) {
  const [oncologyDropdownOpen, setOncologyDropdownOpen] = React.useState(false);
  const [cancerTypeDropdownOpen, setCancerTypeDropdownOpen] = React.useState(false);

  const { data: statsData } = useQuery({
    queryKey: ['landscape-stats', cancerTypeSlug],
    queryFn: () => trialsApi.getLandscapeStats(cancerTypeSlug),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const selectedStats = statsData?.selected_type_stats ?? null;

  return (
    <section
      className={`rounded-lg bg-white border-b border-slate-200 shrink-0 min-w-0 ${className ?? ''}`}
      aria-label="Global context: cancer type and stats"
    >
      <div className="px-4 sm:px-6 lg:px-8 py-4 min-w-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <DashboardStats stats={selectedStats} />
          <div className="flex flex-wrap items-center justify-end gap-3 sm:gap-6 min-w-0">
            <div className="relative min-w-0">
              <button
                type="button"
                onClick={() => setOncologyDropdownOpen((o) => !o)}
                aria-label="Therapy area"
                aria-expanded={oncologyDropdownOpen}
                aria-haspopup="listbox"
                className="flex w-52 min-w-0 items-center justify-between border-0 border-b-2 border-sky-400 bg-transparent py-2 pl-0 pr-1 text-left text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-0"
              >
                <span className="truncate">Oncology</span>
                <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
              </button>
              {oncologyDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    aria-hidden
                    onClick={() => setOncologyDropdownOpen(false)}
                  />
                  <div
                    role="listbox"
                    aria-label="Therapy area"
                    className="absolute left-0 top-full z-20 mt-2 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                  >
                    <button
                      type="button"
                      role="option"
                      aria-selected
                      className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm text-slate-900 bg-sky-50"
                    >
                      <span>Oncology</span>
                      <Check className="h-4 w-4 shrink-0 text-sky-600" />
                    </button>
                  </div>
                </>
              )}
            </div>
            <div className="relative min-w-0 shrink-0">
              <button
                type="button"
                onClick={() => setCancerTypeDropdownOpen((o) => !o)}
                aria-label="Cancer type"
                aria-expanded={cancerTypeDropdownOpen}
                aria-haspopup="listbox"
                className="flex w-64 min-w-0 items-center justify-between border-0 border-b-2 border-sky-400 bg-transparent py-2 pl-0 pr-1 text-left text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-0"
              >
                <span className="truncate">
                  {DASHBOARD_CANCER_TYPES.find((o) => o.value === cancerTypeSlug)?.label ?? cancerTypeSlug}
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
              </button>
              {cancerTypeDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    aria-hidden
                    onClick={() => setCancerTypeDropdownOpen(false)}
                  />
                  <div
                    role="listbox"
                    aria-label="Cancer type"
                    className="absolute left-0 top-full z-20 mt-1.5 w-[24rem] max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                  >
                    {DASHBOARD_CANCER_TYPES.map((opt) => {
                      const selected = cancerTypeSlug === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          role="option"
                          aria-selected={selected}
                          onClick={() => {
                            onCancerTypeChange(opt.value);
                            setCancerTypeDropdownOpen(false);
                          }}
                          className={`flex w-full items-center justify-between gap-2.5 px-3 py-2.5 text-left text-sm transition-colors ${
                            selected ? 'bg-sky-50 text-slate-900' : 'text-slate-700 hover:bg-slate-50'
                          }`}
                        >
                          <span className="min-w-0 flex-1 break-words text-sm">{opt.label}</span>
                          {selected && <Check className="h-4 w-4 shrink-0 text-sky-600" />}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
