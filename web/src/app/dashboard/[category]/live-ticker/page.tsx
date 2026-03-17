'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { UserMenu } from '@/components/user-menu';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { trialsApi, LiveTickerArticle, LiveTickerResult } from '@/lib/api';
import { Loader2, ExternalLink, Newspaper, BarChart3, Calendar, ChevronDown, ChevronUp, Check } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { DashboardGlobalHeader } from '@/components/dashboard/DashboardGlobalHeader';

const CATEGORY_SLUG_MAP: Record<string, string> = {
  'cutaneous-melanoma': 'Cutaneous/Metastasis Melanoma',
  'cutaneous-melanoma-with-brain-cns-metastasis': 'Cutaneous Melanoma with Brain/CNS Metastasis',
  'uveal-melanoma': 'Uveal Melanoma',
  'mucosal-melanoma': 'Mucosal Melanoma',
  'acral-melanoma': 'Acral Melanoma',
  'basal-cell-carcinoma': 'Basal Cell Carcinoma',
  'merkel-cell-carcinoma': 'Merkel Cell Carcinoma',
  'cutaneous-squamous-cell-carcinoma': 'Cutaneous Squamous Cell Carcinoma',
};

function slugToCategory(slug: string): string {
  return CATEGORY_SLUG_MAP[slug] || slug
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function ArticleCard({ article }: { article: LiveTickerArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border border-slate-200 border-l-4 border-l-[var(--primary)] bg-white p-4 shadow-sm transition-all duration-200 hover:border-slate-300 hover:border-l-[var(--accent-dark)] hover:shadow-md focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 focus:ring-offset-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-gray-900 line-clamp-3 transition-colors group-hover:text-[var(--primary)]">
            {article.title}
          </h3>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-slate-500">{article.date}</span>
            {article.nct_id && (
              <span className="text-xs text-slate-500 font-medium tabular-nums">{article.nct_id}</span>
            )}
          </div>
        </div>
        <span className="flex shrink-0 items-center justify-center text-slate-500 transition-colors group-hover:text-[var(--primary)]">
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
    <Card className="overflow-hidden border border-slate-200 border-l-4 border-l-[var(--primary)] bg-white shadow-sm transition-all duration-200 hover:border-slate-300 hover:border-l-[var(--accent-dark)] hover:shadow-md focus-within:ring-2 focus-within:ring-[var(--primary)]/30 focus-within:ring-offset-2">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-base font-semibold leading-snug text-gray-900 min-w-0">
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-900 hover:text-[var(--primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 focus:ring-offset-2 rounded"
            >
              {result.title}
            </a>
          </CardTitle>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setSummaryOpen((v) => !v)}
              aria-expanded={summaryOpen}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            >
              Summary
              {summaryOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-2 text-slate-500 transition-colors hover:text-[var(--primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
              aria-label="Open article"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-slate-500">{result.date}</span>
          {result.nct_id && (
            <span className="text-xs text-slate-500 font-medium tabular-nums">{result.nct_id}</span>
          )}
        </div>
        {metricLabel && (
          <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            {metricLabel}
          </p>
        )}
      </CardHeader>
      {summaryOpen && valueParts.length > 0 && (
        <CardContent className="border-t border-slate-100 pt-4">
          <div className="flex flex-wrap gap-2">
            {valueParts.map((part, i) => (
              <span
                key={i}
                className="inline-flex rounded-lg bg-slate-50 px-3 py-2 text-sm leading-relaxed text-gray-800 border border-slate-100"
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
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const handleCancerTypeChange = React.useCallback(
    (slug: string) => {
      router.push(`/dashboard/${slug}/live-ticker`);
    },
    [router]
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['live-ticker', categorySlug],
    queryFn: () => trialsApi.getLiveTicker(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const hasArticles = (data?.articles?.length ?? 0) > 0;
  const hasResults = (data?.results?.length ?? 0) > 0;
  const isEmpty = !hasArticles && !hasResults;

  const [efficacyFirst, setEfficacyFirst] = React.useState(false);
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
    <div className="flex flex-col h-screen w-full bg-slate-100 overflow-hidden">
      <header className="bg-white border-b border-slate-200 shrink-0 z-50">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 gap-3">
            <Link href="/" className="brand flex-shrink-0 hover:opacity-80 transition-opacity">
              <Logo height={32} />
              <span className="brand-text dashboard-brand-text">
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              <DashboardNavLink />
              {session?.user && (
                <UserMenu
                  email={session.user.email || null}
                  name={session.user.name || null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-2 pt-2 pb-0 md:px-4 md:pt-4 md:pb-0 bg-slate-100 gap-4">
        <div className="w-full bg-white rounded-lg shadow shrink-0 overflow-visible">
          <DashboardGlobalHeader
            cancerTypeSlug={categorySlug}
            onCancerTypeChange={handleCancerTypeChange}
          />
        </div>
        <div className="flex-1 flex flex-col min-h-0 min-w-0 w-full bg-white rounded-lg shadow overflow-hidden">
          <section className="flex-1 flex flex-col min-h-0 bg-white overflow-hidden">
            <div className="px-4 sm:px-6 lg:px-8 pt-3 pb-2 flex-1 flex flex-col min-h-0 overflow-hidden">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 shrink-0 mb-2">
                <div>
                  <h2 className="text-2xl font-medium tracking-wide text-sky-700">Live Ticker</h2>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 py-2 shrink-0 border-y border-slate-100 bg-slate-50/50 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 mb-2">
                <div className="flex flex-wrap items-center gap-4 w-full">
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setMonthDropdownOpen((o) => !o)}
                      aria-label="Filter by month"
                      aria-expanded={monthDropdownOpen}
                      aria-haspopup="listbox"
                      className="flex w-52 items-center justify-between border-0 border-b-2 border-sky-400 bg-transparent py-2 pl-0 pr-1 text-left text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-0"
                    >
                      <span className="truncate flex items-center gap-2">
                        <Calendar className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                        {selectedMonthKey === ''
                          ? `All months (${latestItems.length})`
                          : (() => {
                              const m = availableMonths.find((ma) => ma.key === selectedMonthKey);
                              return m ? `${m.label} (${m.count})` : selectedMonthKey;
                            })()}
                      </span>
                      <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
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
                          className="absolute left-0 top-full z-20 mt-1.5 w-80 max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                        >
                          <button
                            type="button"
                            role="option"
                            aria-selected={selectedMonthKey === ''}
                            onClick={() => {
                              setSelectedMonthKey('');
                              setMonthDropdownOpen(false);
                            }}
                            className={`flex w-full items-center justify-between gap-2.5 px-3 py-2.5 text-left text-sm transition-colors ${selectedMonthKey === ''
                              ? 'bg-sky-50 text-slate-900'
                              : 'text-slate-700 hover:bg-slate-50'
                              }`}
                          >
                            <span className="min-w-0 flex-1 break-words text-sm">All months ({latestItems.length})</span>
                            {selectedMonthKey === '' && <Check className="h-4 w-4 shrink-0 text-sky-600" />}
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
                                className={`flex w-full items-center justify-between gap-2.5 px-3 py-2.5 text-left text-sm transition-colors ${selected
                                  ? 'bg-sky-50 text-slate-900'
                                  : 'text-slate-700 hover:bg-slate-50'
                                  }`}
                              >
                                <span className="min-w-0 flex-1 break-words text-sm">{month.label} ({month.count})</span>
                                {selected && <Check className="h-4 w-4 shrink-0 text-sky-600" />}
                              </button>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setEfficacyFirst((v) => !v)}
                    aria-pressed={efficacyFirst}
                    aria-label={efficacyFirst ? 'Show latest first' : 'Show efficacy & safety highlights first'}
                    className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 shrink-0 active:scale-[0.98] ${efficacyFirst
                      ? 'bg-teal-500 text-white shadow-md shadow-teal-500/30 hover:bg-teal-600 hover:shadow-lg hover:shadow-teal-500/25'
                      : 'bg-white text-slate-600 border-2 border-slate-200 hover:border-teal-300 hover:text-teal-700 hover:bg-teal-50/50'
                      }`}
                  >
                    <BarChart3 className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
                    Efficacy & Safety highlights
                  </button>
                </div>
              </div>

              <div className="flex-1 min-h-0 overflow-auto">
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center py-16">
                    <Loader2 className="h-10 w-10 animate-spin text-slate-400" aria-hidden />
                    <p className="mt-4 text-sm text-slate-500">Loading latest articles…</p>
                  </div>
                ) : error ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 py-12 text-center mx-4">
                    <p className="text-slate-600">Could not load live ticker. Please try again.</p>
                    <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                      Retry
                    </Button>
                  </div>
                ) : isEmpty ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 py-16 text-center mx-4">
                    <Newspaper className="mx-auto h-12 w-12 text-slate-300" aria-hidden />
                    <p className="mt-4 font-medium text-slate-600">No updates yet</p>
                    <p className="mt-1 text-sm text-slate-500">
                      Latest articles and efficacy & safety highlights will appear here for {categoryName}.
                    </p>
                  </div>
                ) : displayedItems.length === 0 ? (
                  <div className="rounded-lg bg-slate-50 py-10 text-center mx-4">
                    <p className="text-sm text-slate-600">No articles in this month.</p>
                    <button
                      type="button"
                      onClick={() => setSelectedMonthKey('')}
                      className="mt-3 text-sm font-medium text-sky-700 hover:underline focus:outline-none focus:ring-2 focus:ring-sky-400/30 focus:ring-offset-2 rounded"
                    >
                      Show all months
                    </button>
                  </div>
                ) : (
                  <div className="px-4 sm:px-6 lg:px-8 pb-6 space-y-6">
                    <p className="text-sm text-slate-500">
                      {displayedItems.length} {displayedItems.length === 1 ? 'item' : 'items'}
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
          </section>
        </div>
      </main>
    </div>
  );
}
