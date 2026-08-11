'use client';

import { CheckCircle2, Loader2, AlertCircle, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';

type ToolState = 'input-streaming' | 'input-available' | 'output-available' | 'output-error';

export interface ToolCardProps {
  toolName: string;
  state: ToolState;
  input?: unknown;
  output?: unknown;
  errorText?: string;
}

const PRETTY_NAMES: Record<string, string> = {
  query_proprietary_data:  'Proprietary data query',
  lookup_trial:            'Trial lookup',
  store_finding:           'Save finding',
};

export function ToolCard({ toolName, state, input, output, errorText }: ToolCardProps) {
  const display = PRETTY_NAMES[toolName] ?? toolName;
  const isError = state === 'output-error';
  const isDone  = state === 'output-available';

  return (
    <div
      className={cn(
        'rounded-xl border bg-slate-50/80 px-3 py-2 text-xs',
        isError
          ? 'border-red-200 bg-red-50'
          : isDone
            ? 'border-emerald-200'
            : 'border-slate-200'
      )}
    >
      <div className="flex items-center gap-2 font-medium">
        {isError ? (
          <AlertCircle className="h-4 w-4 text-red-500" />
        ) : isDone ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
        )}
        <Wrench className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-slate-700">{display}</span>
      </div>

      {input != null && state !== 'input-streaming' ? (
        <details className="mt-1.5">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-700">
            Input
          </summary>
          <pre className="mt-1 overflow-x-auto rounded bg-white p-2 text-[11px] text-slate-700">
            {JSON.stringify(input, null, 2)}
          </pre>
        </details>
      ) : null}

      {output != null && isDone ? (
        <details className="mt-1.5">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-700">
            Result
          </summary>
          <pre className="mt-1 max-h-60 overflow-auto rounded bg-white p-2 text-[11px] text-slate-700">
            {JSON.stringify(output, null, 2)}
          </pre>
        </details>
      ) : null}

      {isError && errorText ? (
        <div className="mt-1.5 text-red-600">{errorText}</div>
      ) : null}
    </div>
  );
}
