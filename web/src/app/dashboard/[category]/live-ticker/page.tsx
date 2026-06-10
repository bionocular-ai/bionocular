'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { trialsApi, LiveTickerArticle, LiveTickerResult } from '@/lib/api';
import { Loader2, ExternalLink, Newspaper, Calendar, ChevronDown, ChevronUp, Check } from 'lucide-react';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { FilterChips } from '@/components/dashboard/FilterChips';
import { slugToCategory } from '@/lib/dashboard-constants';
import { cn } from '@/lib/utils';

type FeedFilter = 'latest' | 'efficacy';

const FEED_FILTER_OPTIONS: { value: FeedFilter; label: string }[] = [
  { value: 'latest', label: 'Latest' },
  { value: 'efficacy', label: 'Efficacy & Safety' },
];

function ArticleCard({ article }: { article: LiveTickerArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-4 shadow-[0_1px_2px_rgba(16,43,54,0.04)] transition-all duration-200 hover:border-(--brand-primary) hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-3 font-semibold text-(--brand-text) transition-colors group-hover:text-(--brand-primary)">
            {article.title}
          </h3>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-(--brand-text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
              {article.date}
            </span>
            {article.nct_ids?.[0] && (
              <span
                className="text-xs font-medium text-(--brand-text-muted)"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {article.nct_ids[0]}
              </span>
            )}
          </div>
        </div>
        <span className="flex shrink-0 items-center justify-center text-(--brand-text-muted) transition-colors group-hover:text-(--brand-primary)">
          <ExternalLink className="h-4 w-4" aria-hidden />
        </span>
      </div>
    </a>
  );
}

function ResultCard({ result }: { result: LiveTickerResult }) {
  const [summaryOpen, setSummaryOpen] = React.useState(false);
  const { efficacy_or_safety_data } = result;
  const ed = efficacy_or_safety_data as {
    metric?: string;
    value?: string;
    efficacy_metrics?: Array<{ metric: string; value: string }>;
    safety_metrics?: Array<{ metric: string; value: string }>;
  };
  const valueParts = ed.value
    ? ed.value.split(';').map((s) => s.trim()).filter(Boolean)
    : [
      ...(ed.efficacy_metrics ?? []).map((m) => `${m.metric}: ${m.value}`),
      ...(ed.safety_metrics ?? []).map((m) => `${m.metric}: ${m.value}`),
    ];
  const metricLabel = ed.metric ?? (ed.efficacy_metrics || ed.safety_metrics ? 'Efficacy & Safety' : '');
  return (
    <Card className="overflow-hidden rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)] transition-all duration-200 hover:border-(--brand-primary) hover:shadow-md focus-within:ring-2 focus-within:ring-(--brand-primary) focus-within:ring-offset-1">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="min-w-0 text-base font-semibold leading-snug text-(--brand-text)">
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded text-(--brand-text) hover:text-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1"
            >
              {result.title}
            </a>
          </CardTitle>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setSummaryOpen((v) => !v)}
              aria-expanded={summaryOpen}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-(--brand-text-muted) transition-colors hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
            >
              Summary
              {summaryOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-2 text-(--brand-text-muted) transition-colors hover:text-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
              aria-label="Open article"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-(--brand-text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
            {result.date}
          </span>
          {result.nct_ids?.[0] && (
            <span
              className="text-xs font-medium text-(--brand-text-muted)"
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {result.nct_ids[0]}
            </span>
          )}
        </div>
        {metricLabel && (
          <p className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-(--brand-primary)">
            {metricLabel}
          </p>
        )}
      </CardHeader>
      {summaryOpen && valueParts.length > 0 && (
        <CardContent className="border-t border-(--brand-border) pt-4">
          <div className="flex flex-wrap gap-2">
            {valueParts.map((part, i) => (
              <span
                key={i}
                className="inline-flex rounded-lg border border-(--brand-border) bg-(--brand-bg) px-3 py-2 text-sm leading-relaxed text-(--brand-text)"
              >
                {part}
              </span>
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export default function LiveTickerPage() {
  const params = useParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['live-ticker', categorySlug],
    queryFn: () => trialsApi.getLiveTicker(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const hasArticles = (data?.articles?.length ?? 0) > 0;
  const hasResults = (data?.results?.length ?? 0) > 0;
  const isEmpty = !hasArticles && !hasResults;

  const [feedFilter, setFeedFilter] = React.useState<FeedFilter>('latest');
  const efficacyFirst = feedFilter === 'efficacy';
  const [selectedMonthKey, setSelectedMonthKey] = React.useState<string>('');
  const [monthDropdownOpen, setMonthDropdownOpen] = React.useState(false);

  const latestItems = React.useMemo(() => {
    if (!data) return [];
    const resultUrls = new Set(data.results.map((r) => r.url));
    const articlesOnly = data.articles.filter((a) => !resultUrls.has(a.url));
    type Item = { type: 'result'; value: LiveTickerResult } | { type: 'article'; value: LiveTickerArticle };
    const parseDate = (d: string) => new Date(d).getTime();
    const byDateDesc = (a: Item, b: Item) => parseDate(b.value.date) - parseDate(a.value.date);

    const results: Item[] = data.results.map((value) => ({ type: 'result' as const, value }));
    const articles: Item[] = articlesOnly.map((value) => ({ type: 'article' as const, value }));

    results.sort(byDateDesc);
    articles.sort(byDateDesc);

    if (efficacyFirst) return [...results, ...articles];
    const combined = [...results, ...articles];
    combined.sort(byDateDesc);
    return combined;
  }, [data, efficacyFirst]);

  const getMonthKey = (d: string) => {
    const date = new Date(d);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  };
  const formatMonthLabel = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  const availableMonths = React.useMemo(() => {
    if (latestItems.length === 0) return [];
    const map = new Map<string, { label: string; count: number }>();
    for (const item of latestItems) {
      const key = getMonthKey(item.value.date);
      const label = formatMonthLabel(item.value.date);
      if (!map.has(key)) map.set(key, { label, count: 0 });
      map.get(key)!.count += 1;
    }
    return [...map.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([key, { label, count }]) => ({ key, label, count }));
  }, [latestItems]);

  const displayedItems = React.useMemo(() => {
    let items = latestItems;
    if (selectedMonthKey) items = items.filter((item) => getMonthKey(item.value.date) === selectedMonthKey);
    if (efficacyFirst) items = items.filter((item) => item.type === 'result');
    return items;
  }, [latestItems, selectedMonthKey, efficacyFirst]);

  return (
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          category={categoryName}
          title="Live News"
          description="Latest news, press releases, and efficacy & safety readouts across the treatment landscape."
          right={
            <FilterChips
              options={FEED_FILTER_OPTIONS}
              value={feedFilter}
              onChange={setFeedFilter}
            />
          }
        />

        {/* Month filter */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <div className="relative">
            <button
              type="button"
              onClick={() => setMonthDropdownOpen((o) => !o)}
              aria-label="Filter by month"
              aria-expanded={monthDropdownOpen}
              aria-haspopup="listbox"
              className="flex w-56 items-center justify-between rounded-full border border-(--brand-border) bg-(--brand-surface) py-2 pl-3 pr-2.5 text-left text-sm text-(--brand-text) transition-colors hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
            >
              <span className="flex items-center gap-2 truncate">
                <Calendar className="h-4 w-4 shrink-0 text-(--brand-text-muted)" aria-hidden />
                {selectedMonthKey === ''
                  ? `All months (${latestItems.length})`
                  : (() => {
                      const m = availableMonths.find((ma) => ma.key === selectedMonthKey);
                      return m ? `${m.label} (${m.count})` : selectedMonthKey;
                    })()}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" />
            </button>
            {monthDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  aria-hidden
                  onClick={() => setMonthDropdownOpen(false)}
                />
                <div
                  role="listbox"
                  aria-label="Filter by month"
                  className="absolute left-0 top-full z-20 mt-1.5 max-h-60 w-80 overflow-y-auto rounded-xl border border-(--brand-border) bg-(--brand-surface) py-1 shadow-lg"
                >
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedMonthKey === ''}
                    onClick={() => {
                      setSelectedMonthKey('');
                      setMonthDropdownOpen(false);
                    }}
                    className={cn(
                      'flex w-full items-center justify-between gap-2.5 px-3 py-2.5 text-left text-sm transition-colors',
                      selectedMonthKey === ''
                        ? 'bg-(--brand-accent-light) text-(--brand-text)'
                        : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)',
                    )}
                  >
                    <span className="min-w-0 flex-1 break-words text-sm">All months ({latestItems.length})</span>
                    {selectedMonthKey === '' && <Check className="h-4 w-4 shrink-0 text-(--brand-primary)" />}
                  </button>
                  {availableMonths.map((month) => {
                    const selected = selectedMonthKey === month.key;
                    return (
                      <button
                        key={month.key}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        onClick={() => {
                          setSelectedMonthKey(month.key);
                          setMonthDropdownOpen(false);
                        }}
                        className={cn(
                          'flex w-full items-center justify-between gap-2.5 px-3 py-2.5 text-left text-sm transition-colors',
                          selected
                            ? 'bg-(--brand-accent-light) text-(--brand-text)'
                            : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)',
                        )}
                      >
                        <span className="min-w-0 flex-1 break-words text-sm">{month.label} ({month.count})</span>
                        {selected && <Check className="h-4 w-4 shrink-0 text-(--brand-primary)" />}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Feed */}
        <div className="mt-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-10 w-10 animate-spin text-(--brand-text-muted)" aria-hidden />
              <p className="mt-4 text-sm text-(--brand-text-muted)">Loading latest articles…</p>
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) py-12 text-center">
              <p className="text-(--brand-text-muted)">Could not load live ticker. Please try again.</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : isEmpty ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) py-16 text-center">
              <Newspaper className="mx-auto h-12 w-12 text-(--brand-border)" aria-hidden />
              <p className="mt-4 font-medium text-(--brand-text)">No updates yet</p>
              <p className="mt-1 text-sm text-(--brand-text-muted)">
                Latest articles and efficacy & safety highlights will appear here for {categoryName}.
              </p>
            </div>
          ) : displayedItems.length === 0 ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) py-10 text-center">
              <p className="text-sm text-(--brand-text-muted)">No articles in this month.</p>
              <button
                type="button"
                onClick={() => setSelectedMonthKey('')}
                className="mt-3 rounded text-sm font-medium text-(--brand-primary) hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1"
              >
                Show all months
              </button>
            </div>
          ) : (
            <div className="space-y-5">
              <p className="text-sm text-(--brand-text-muted)">
                <span style={{ fontFamily: 'var(--font-mono)' }}>{displayedItems.length}</span>{' '}
                {displayedItems.length === 1 ? 'item' : 'items'}
                {selectedMonthKey
                  ? ` in ${availableMonths.find((m) => m.key === selectedMonthKey)?.label ?? ''}`
                  : ''}
              </p>
              <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2">
                {displayedItems.map((item, i) =>
                  item.type === 'result' ? (
                    <ResultCard key={`result-${item.value.url}-${i}`} result={item.value} />
                  ) : (
                    <ArticleCard key={`article-${item.value.url}-${i}`} article={item.value} />
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
