'use client';

import * as React from 'react';
import { ListChecks, Scale, ShieldCheck, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { describeSelection, type Readout } from '@/lib/readouts';
import { PeekIcon } from '@/components/icons/PeekIcon';
import { ChatPanel, type Suggestion } from './ChatPanel';

function suggestionsFor(n: number): Suggestion[] {
  const these = n === 1 ? 'this readout' : 'these readouts';
  return [
    ...(n > 1 ? [{ label: 'Compare them', icon: Scale, question: `Compare the efficacy and safety of ${these}.` }] : []),
    { label: 'Key results', icon: ListChecks, question: `Summarise the key results of ${these}.` },
    { label: 'Safety', icon: ShieldCheck, question: n === 1 ? 'What safety findings does this readout report?' : 'What safety findings do these readouts report?' },
  ];
}

/**
 * The agent, opened from a floating button over a page. The readouts selected
 * on the page travel with the next question as context; the conversation
 * survives closing the drawer and changing the selection.
 */
export function AgentDrawer({
  cancerType,
  selected,
  onRemove,
  onClear,
}: {
  cancerType: string;
  selected: Readout[];
  onRemove: (key: string) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [sessionId] = React.useState(() => crypto.randomUUID());
  const panelRef = React.useRef<HTMLElement>(null);
  const n = selected.length;

  React.useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const selection = (
    <div className="flex flex-col gap-2">
      <h3 className="text-[13px] font-semibold text-(--brand-text)">
        {n ? `Answering about ${n === 1 ? 'this readout' : `these ${n} readouts`}` : 'No readouts selected'}
      </h3>
      {n ? (
        <>
          <ul className="flex flex-col border-t border-[#E3EEEA]">
            {selected.map((r) => (
              <li key={r.key} className="flex items-center gap-2.5 border-b border-[#E3EEEA] py-2 text-[13px]">
                <b className="shrink-0 font-semibold text-(--brand-primary)">{r.acronym ?? r.drug ?? r.nctId}</b>
                <span className="min-w-0 flex-1 truncate text-(--brand-text-muted)">{r.source.label}</span>
                <button
                  type="button"
                  onClick={() => onRemove(r.key)}
                  className="shrink-0 px-1 text-[12.5px] text-(--brand-text-muted) hover:text-(--brand-primary) hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={onClear}
            className="self-start text-[12.5px] font-medium text-(--brand-primary) hover:underline"
          >
            Clear selection
          </button>
        </>
      ) : (
        <p className="text-[13px] text-(--brand-text-muted)">
          Tick readout cards to ask about them, or ask anything about this indication.
        </p>
      )}
    </div>
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={n ? `Open agent, ${n} ${n === 1 ? 'readout' : 'readouts'} selected` : 'Open agent'}
        className={cn(
          'group fixed right-5 bottom-6 z-30 flex h-[46px] min-w-[46px] items-center rounded-full border border-(--brand-border) bg-(--brand-surface) px-[5px] md:right-14 md:bottom-11',
          'shadow-[0_1px_2px_rgba(16,43,54,.12),0_12px_28px_-14px_rgba(16,43,54,.6)] transition-[transform,box-shadow] hover:-translate-y-px',
          'hover:shadow-[0_1px_2px_rgba(16,43,54,.12),0_16px_32px_-14px_rgba(16,43,54,.7)]',
        )}
      >
        <PeekIcon className="h-[34px] w-[34px] shrink-0" />
        {/* The label slides in on hover. Its line box is taller than the text
            because it clips to slide: a 1:1 line height cuts off the "g". */}
        <span
          className={cn(
            'max-w-0 overflow-hidden whitespace-nowrap text-[13px] leading-[18px] font-semibold opacity-0 transition-[max-width,opacity,margin] duration-200',
            'group-hover:ml-1 group-hover:max-w-[60px] group-hover:opacity-100 group-focus-visible:ml-1 group-focus-visible:max-w-[60px] group-focus-visible:opacity-100',
            !n && 'group-hover:mr-2.5 group-focus-visible:mr-2.5',
          )}
        >
          Agent
        </span>
        {n > 0 && (
          <span
            className="mr-1.5 ml-0.5 h-[22px] min-w-[22px] rounded-full bg-(--brand-accent) px-1.5 text-center text-xs leading-[22px] font-semibold tabular-nums"
            aria-hidden="true"
          >
            {n}
          </span>
        )}
      </button>

      <aside
        ref={panelRef}
        tabIndex={-1}
        aria-label="Agent"
        inert={!open}
        className={cn(
          'fixed top-14 right-0 bottom-0 z-50 flex w-full flex-col border-l border-(--brand-border) bg-(--brand-bg) outline-none md:w-[420px]',
          'transition-transform duration-250 ease-[cubic-bezier(.22,.8,.3,1)]',
          open ? 'translate-x-0 shadow-[-24px_0_48px_-32px_rgba(16,43,54,.7)]' : 'translate-x-[102%]',
        )}
      >
        <div className="flex items-center gap-2.5 border-b border-(--brand-border) bg-(--brand-surface) px-4 py-3">
          <PeekIcon className="h-7 w-7" />
          <h2 className="flex-1 text-base font-semibold">Ask the agent</h2>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close agent"
            className="rounded p-1 text-(--brand-text-muted) hover:text-(--brand-text)"
          >
            <X className="h-[18px] w-[18px]" />
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <ChatPanel
            key={sessionId}
            cancerType={cancerType}
            sessionId={sessionId}
            header={selection}
            contextPrefix={n ? describeSelection(selected) : undefined}
            suggestions={n ? suggestionsFor(n) : undefined}
          />
        </div>
      </aside>
    </>
  );
}
