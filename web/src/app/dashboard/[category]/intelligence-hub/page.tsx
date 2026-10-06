'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { readoutsApi } from '@/lib/api';
import { EMPTY_FILTERS, filterReadouts, groupReadouts, sortReadouts, type ReadoutFilters as Filters } from '@/lib/readouts';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { ReadoutCard } from '@/components/dashboard/ReadoutCard';
import { ReadoutFilters } from '@/components/dashboard/ReadoutFilters';
import { slugToCategory } from '@/lib/dashboard-constants';

const PAGE_SIZE = 20;

const PAGE_BUTTON =
  'inline-flex h-9 w-9 items-center justify-center rounded-lg border border-(--brand-border) bg-(--brand-surface) text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-text) disabled:pointer-events-none disabled:opacity-40';

/** Every readout for the indication from a trial in Trial Landscape, one card each. */
export default function IntelligenceHubPage() {
  const categorySlug = useParams().category as string;
  const [filters, setFilters] = React.useState<Filters>({ ...EMPTY_FILTERS, onlyResults: true });
  const [page, setPage] = React.useState(1);
  const listRef = React.useRef<HTMLElement>(null);

  const { data: rows, isLoading, error } = useQuery({
    queryKey: ['intelligence-hub-readouts', categorySlug],
    queryFn: () => readoutsApi.getCategoryRows(categorySlug),
    enabled: Boolean(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const readouts = React.useMemo(() => sortReadouts(groupReadouts(rows ?? [])), [rows]);
  const visible = React.useMemo(() => filterReadouts(readouts, filters), [readouts, filters]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const pageItems = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const trials = new Set(visible.map((r) => r.nctId)).size;
  const withoutResults = visible.filter((r) => !r.hasResults).length;

  const changeFilters = (next: Filters) => {
    setFilters(next);
    setPage(1);
  };
  const goTo = (p: number) => {
    setPage(p);
    listRef.current?.scrollIntoView({ block: 'start' });
  };

  const results = (
    <section ref={listRef} aria-label="Readouts" className="min-w-0 scroll-mt-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 pb-3">
        <h2 className="text-[22px] font-semibold leading-none tabular-nums">
          {visible.length.toLocaleString()} {visible.length === 1 ? 'readout' : 'readouts'}
        </h2>
        <span className="text-[13px] text-(--brand-text-muted)">
          {filters.onlyResults
            ? `with results, from ${trials.toLocaleString()} ${trials === 1 ? 'trial' : 'trials'}`
            : `including ${withoutResults.toLocaleString()} without results yet`}
        </span>
        <span className="ml-auto text-[13px] text-(--brand-text-muted)">
          Sorted by <span className="font-medium text-(--brand-text)">primary completion, newest</span>
        </span>
      </div>

      {visible.length === 0 ? (
        <div className="rounded-[10px] border border-(--brand-border) bg-(--brand-surface) py-12 text-center text-sm text-(--brand-text-muted)">
          No readouts match these filters.{' '}
          <button
            type="button"
            onClick={() => changeFilters({ ...EMPTY_FILTERS, onlyResults: filters.onlyResults })}
            className="font-medium text-(--brand-primary) hover:underline"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {pageItems.map((r) => (
              <ReadoutCard key={r.key} readout={r} category={categorySlug} />
            ))}
          </div>

          <nav
            className="mt-6 flex items-center justify-between gap-4 border-t border-(--brand-border) pt-4"
            aria-label="Readouts pagination"
          >
            <p className="text-sm text-(--brand-text-muted)">
              Showing{' '}
              <span className="font-semibold text-(--brand-text) tabular-nums">{(page - 1) * PAGE_SIZE + 1}</span>–
              <span className="font-semibold text-(--brand-text) tabular-nums">
                {Math.min(page * PAGE_SIZE, visible.length)}
              </span>{' '}
              of <span className="font-semibold text-(--brand-text) tabular-nums">{visible.length.toLocaleString()}</span>
            </p>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => goTo(page - 1)} disabled={page <= 1} aria-label="Previous page" className={PAGE_BUTTON}>
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 text-sm text-(--brand-text-muted) tabular-nums">
                {page} / {totalPages}
              </span>
              <button type="button" onClick={() => goTo(page + 1)} disabled={page >= totalPages} aria-label="Next page" className={PAGE_BUTTON}>
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </nav>
        </>
      )}
    </section>
  );

  // Desktop: the filters dock against the global sidebar as a full-height
  // column, with the header and cards to their right. Phone: one column,
  // filters between the header and the cards.
  return (
    <div className="grid min-h-screen grid-cols-1 bg-(--brand-bg) lg:grid-cols-[264px_minmax(0,1fr)] lg:grid-rows-[auto_1fr]">
      <div className="mx-auto w-full max-w-7xl px-4 pt-8 md:px-6 lg:col-start-2 lg:row-start-1">
        <PageHeader
          category={slugToCategory(categorySlug)}
          title="Intelligence Hub"
          description="Every reported result for this indication, one readout per card."
        />
      </div>

      {readouts.length > 0 && (
        <div className="px-4 pt-6 md:px-6 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:p-0">
          <ReadoutFilters readouts={readouts} filters={filters} onChange={changeFilters} />
        </div>
      )}

      <div className="mx-auto w-full max-w-7xl px-4 pt-6 pb-8 md:px-6 lg:col-start-2 lg:row-start-2">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-(--brand-text-muted)" aria-label="Loading readouts" />
          </div>
        ) : error ? (
          <p className="py-16 text-center text-sm text-(--brand-text-muted)">Could not load readouts.</p>
        ) : readouts.length === 0 ? (
          <p className="py-16 text-center text-sm text-(--brand-text-muted)">No readouts for this indication yet.</p>
        ) : (
          results
        )}
      </div>
    </div>
  );
}
