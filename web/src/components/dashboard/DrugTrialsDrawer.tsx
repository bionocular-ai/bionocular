'use client';

import * as React from 'react';
import type { DrugDot } from '@/hooks/useBullseyeData';
import { TrialCard } from '@/components/dashboard/TrialCard';
import { X } from 'lucide-react';

interface DrugTrialsDrawerProps {
  drug: DrugDot | null;
  cancerTypeSlug: string;
  onClose: () => void;
}

export function DrugTrialsDrawer({ drug, cancerTypeSlug, onClose }: DrugTrialsDrawerProps) {
  React.useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  if (!drug) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20" aria-hidden onClick={onClose} />
      <div className="fixed right-0 top-0 z-50 h-full w-full max-w-sm bg-white shadow-2xl flex flex-col">
        <div className="flex items-start justify-between gap-2 px-4 py-4 border-b border-slate-200">
          <div className="min-w-0">
            <h3 className="font-semibold text-slate-900 truncate">{drug.drug_name}</h3>
            <p className="text-sm text-slate-500 mt-0.5 truncate">{drug.sponsor}</p>
            <span className="mt-1 inline-block text-xs font-medium text-sky-700 bg-sky-50 px-2 py-0.5 rounded">
              {drug.phase}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-2">
          <p className="text-xs text-slate-400 mb-1">{drug.trial_count} trial{drug.trial_count !== 1 ? 's' : ''}</p>
          {drug.trials.map((trial) => (
            <TrialCard key={trial.nct_id} trial={trial} category={cancerTypeSlug} />
          ))}
        </div>
      </div>
    </>
  );
}
