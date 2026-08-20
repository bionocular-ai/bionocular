'use client';

import { useMemo, useState } from 'react';
import { toResultTable } from '@/lib/agent/result-table';
import { cn } from '@/lib/utils';

/**
 * One query the agent ran, as a line of prose rather than a JSON dump.
 *
 * Everything shown here already ships inside the tool result - `coverage`
 * carries how many rows matched, whether the set is complete, and any caveat
 * the table comes with. The previous card hid all of it behind a disclosure.
 *
 * The rows themselves are drawn from `output.rows` rather than left to the
 * answer's prose. Asked for 53 trials the model received all 53 and wrote up 45,
 * having pivoted to one row per treatment and merged the ones sharing a drug.
 * The model keeps the analysis; the app owns the row set.
 */

export type ToolState = 'input-streaming' | 'input-available' | 'output-available' | 'output-error';

export interface ToolStepProps {
  toolName: string;
  state: ToolState;
  input?: unknown;
  output?: unknown;
  errorText?: string;
}

interface Coverage {
  returned?: number;
  matched?: number;
  complete?: boolean;
  truncatedBy?: 'size' | 'limit';
  caveat?: string;
}

type Tone = 'pending' | 'ok' | 'partial' | 'error';

interface Summary {
  /** The thing that was queried: a table name, or an NCT number. */
  subject: string;
  detail: string;
  caveat?: string;
  tone: Tone;
}

const FALLBACK_SUBJECTS: Record<string, string> = {
  query_proprietary_data: 'proprietary data',
  lookup_trial: 'trial lookup',
  store_finding: 'saved finding',
};

const MISS_REASONS: Record<string, string> = {
  other_cancer_type: 'exists, but is tagged to another cancer type',
  not_in_bionocular: 'not in Bionocular',
};

const FAILURE_REASONS: Record<string, string> = {
  no_rows: 'no rows matched',
  unknown_column: 'unknown column',
  unsupported_filter: 'filter not supported on this table',
  query_failed: 'query failed',
};

function count(value: number | undefined): string {
  return (value ?? 0).toLocaleString('en-US');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function coverageDetail(coverage: Coverage | undefined): string {
  if (!coverage) return 'complete';
  const rows = `${count(coverage.returned)} of ${count(coverage.matched)} rows`;
  if (coverage.complete) return `${rows} · complete`;
  return `${rows} · truncated by ${coverage.truncatedBy ?? 'limit'}`;
}

function summarise({ toolName, state, output, errorText }: ToolStepProps): Summary {
  const fallback = FALLBACK_SUBJECTS[toolName] ?? toolName;

  if (state === 'input-streaming') return { subject: fallback, detail: 'preparing…', tone: 'pending' };
  if (state === 'input-available') return { subject: fallback, detail: 'querying…', tone: 'pending' };
  if (state === 'output-error') {
    return { subject: fallback, detail: errorText || 'failed', tone: 'error' };
  }

  if (!isRecord(output)) return { subject: fallback, detail: 'done', tone: 'ok' };

  // lookup_trial
  if ('found' in output) {
    const nctId = typeof output.nctId === 'string' ? output.nctId : fallback;
    if (output.found !== true) {
      const reason = typeof output.reason === 'string' ? output.reason : '';
      return { subject: nctId, detail: MISS_REASONS[reason] ?? 'not found', tone: 'partial' };
    }
    const coverage = isRecord(output.coverage) ? output.coverage : {};
    const presentIn = Array.isArray(coverage.presentIn) ? (coverage.presentIn as string[]) : [];
    const absentFrom = Array.isArray(coverage.absentFrom) ? (coverage.absentFrom as string[]) : [];
    const caveats = Array.isArray(coverage.caveats) ? (coverage.caveats as string[]) : [];
    return {
      subject: nctId,
      detail: [
        presentIn.length ? `found in ${presentIn.join(', ')}` : 'no rows',
        absentFrom.length ? `absent from ${absentFrom.join(', ')}` : '',
      ]
        .filter(Boolean)
        .join(' · '),
      caveat: caveats[0],
      tone: presentIn.length ? 'ok' : 'partial',
    };
  }

  // store_finding
  if (toolName === 'store_finding') {
    return { subject: fallback, detail: output.ok === true ? 'saved' : 'not saved', tone: 'ok' };
  }

  // query_proprietary_data
  const table = typeof output.table === 'string' ? output.table : fallback;
  const coverage = isRecord(output.coverage) ? (output.coverage as Coverage) : undefined;

  if (output.ok !== true) {
    const reason = typeof output.reason === 'string' ? output.reason : '';
    return {
      subject: table,
      detail: FAILURE_REASONS[reason] ?? 'query failed',
      caveat: coverage?.caveat,
      tone: reason === 'no_rows' ? 'partial' : 'error',
    };
  }

  return {
    subject: table,
    detail: coverageDetail(coverage),
    caveat: coverage?.caveat,
    tone: coverage?.complete === false ? 'partial' : 'ok',
  };
}

const NODE_TONE: Record<Tone, string> = {
  pending: 'bg-(--brand-primary) motion-safe:animate-pulse',
  ok: 'bg-(--brand-accent)',
  partial: 'bg-(--brand-accent)',
  error: 'bg-red-700',
};

const CHIP_TONE: Record<Tone, string> = {
  pending: 'border border-(--brand-border) text-(--brand-text-muted)',
  ok: 'bg-(--brand-accent-light) text-(--brand-primary)',
  partial: 'border border-(--brand-border) text-(--brand-text-muted)',
  error: 'border border-red-200 bg-red-50 text-red-700',
};

export function ToolStep(props: ToolStepProps) {
  const { input, output, state } = props;
  const { subject, detail, caveat, tone } = summarise(props);
  const [showRaw, setShowRaw] = useState(false);
  const [showRows, setShowRows] = useState(false);
  const hasRaw = state === 'output-available' || state === 'output-error';
  const table = useMemo(() => toResultTable(output), [output]);

  return (
    <div className="relative mb-1.5">
      <span
        aria-hidden
        className={cn(
          'absolute top-[7px] -left-[26px] h-[9px] w-[9px] rounded-full',
          'shadow-[0_0_0_3px_var(--brand-bg)]',
          NODE_TONE[tone]
        )}
      />
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 py-0.5">
        <span className="font-mono text-[12.5px] font-medium text-(--brand-primary)">{subject}</span>
        <span
          className={cn(
            'rounded-[3px] px-1.5 py-0.5 font-mono text-[10px] whitespace-nowrap',
            CHIP_TONE[tone]
          )}
        >
          {detail}
        </span>
        {table ? (
          <button
            type="button"
            onClick={() => setShowRows((open) => !open)}
            className={cn(
              'cursor-pointer font-mono text-[10px] tracking-[0.04em]',
              'text-(--brand-text-muted) underline underline-offset-[3px] hover:text-(--brand-primary)'
            )}
          >
            {showRows ? 'hide rows' : `${table.rows.length} rows`}
          </button>
        ) : null}
        {hasRaw ? (
          <button
            type="button"
            onClick={() => setShowRaw((open) => !open)}
            className={cn(
              'cursor-pointer font-mono text-[10px] tracking-[0.04em]',
              'text-(--brand-text-muted) underline underline-offset-[3px] hover:text-(--brand-primary)'
            )}
          >
            {showRaw ? 'hide' : 'raw'}
          </button>
        ) : null}
        {caveat ? (
          <p className="max-w-[62ch] basis-full text-[12px] text-(--brand-text-muted)">{caveat}</p>
        ) : null}
        {showRows && table ? (
          <div className="max-h-96 basis-full overflow-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface)">
            <table className="w-full border-collapse text-[11px]">
              <thead>
                <tr>
                  {table.columns.map((column) => (
                    <th
                      key={column}
                      className={cn(
                        'sticky top-0 z-1 border-b border-(--brand-border) bg-(--brand-accent-light)',
                        'px-2 py-1.5 text-left font-mono font-medium whitespace-nowrap',
                        'text-(--brand-primary)'
                      )}
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className="border-b border-(--brand-border)/50 last:border-b-0">
                    {row.map((cell, cellIndex) => (
                      <td
                        key={table.columns[cellIndex]}
                        className="max-w-[30ch] px-2 py-1 align-top text-(--brand-text-muted)"
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {showRaw ? (
          <pre className="max-h-60 basis-full overflow-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface) p-2 text-[11px] text-(--brand-text-muted)">
            {JSON.stringify({ input, output }, null, 2)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
