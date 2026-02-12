'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { useParams, useRouter, usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { UserMenu } from '@/components/user-menu';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { trialsApi, LiveTickerArticle, LiveTickerResult } from '@/lib/api';
import { Loader2, LayoutGrid, ExternalLink, Newspaper, BarChart3, Calendar, ChevronDown, ChevronUp } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';

const CATEGORY_SLUG_MAP: Record<string, string> = {
  'cutaneous-melanoma': 'Cutaneous melanoma',
  'cutaneous-melanoma-with-brain-cns-metastasis': 'Cutaneous melanoma with Brain/CNS metastasis',
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
  const pathname = usePathname();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);
  const isLiveTickerPage = pathname?.includes('/live-ticker');

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
    <div className="flex min-h-screen w-full flex-col bg-white">
      <header className="sticky top-0 z-50 shrink-0 border-b border-gray-200 bg-white">
        <div className="w-full px-3 sm:px-4 md:px-6">
          <div className="flex h-16 items-center justify-between gap-2 sm:gap-4">
            <Link href="/" className="brand flex-shrink-0">
              <Logo height={32} />
              <span className="brand-text" style={{ lineHeight: '1.2' }}>
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex flex-shrink-0 items-center gap-2 sm:gap-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push('/dashboard')}
                className="group border-gray-300 text-xs font-medium text-gray-700 transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20 sm:text-sm"
                aria-label="Navigate to main categories"
              >
                <LayoutGrid className="mr-1.5 h-3.5 w-3.5 transition-colors group-hover:text-primary sm:mr-1.5" />
                <span className="hidden sm:inline">Categories</span>
                <span className="sm:hidden">Main</span>
              </Button>
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

      <div className="border-b border-gray-200 bg-gray-50 px-3 py-4 sm:px-4 md:px-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">
          {categoryName}
        </h1>
      </div>

      <div className="flex flex-1 w-full overflow-hidden">
        <aside className="w-[280px] shrink-0 overflow-y-auto border-r border-gray-200 bg-gray-50/50 p-4">
          <nav className="space-y-1">
            <Link
              href={`/dashboard/${categorySlug}/disease-landscape`}
              className="block rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Disease Landscape
            </Link>
            <Link
              href={`/dashboard/${categorySlug}/analytics?mode=efficacy`}
              className="block rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Head to Head Efficacy
            </Link>
            <Link
              href={`/dashboard/${categorySlug}/analytics?mode=safety`}
              className="block rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Head to Head Safety
            </Link>
            <div>
              <Link
                href={`/dashboard/${categorySlug}/therapeutic-index`}
                className="block rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
              >
                Head to Head Efficacy : Safety
              </Link>
            </div>
            <Link
              href={`/dashboard/${categorySlug}/live-ticker`}
              className={`block rounded-md px-3 py-2 text-sm font-medium ${
                isLiveTickerPage
                  ? 'bg-[var(--accent-light)] text-[var(--primary)]'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              Live Ticker
            </Link>
            <div className="block px-3 py-2 text-sm font-medium text-gray-500">
              AI Chatbot
              <span className="ml-2 text-xs text-gray-400">Upcoming</span>
            </div>
            <div className="block px-3 py-2 text-sm font-medium text-gray-500">
              Regulatory Milestone
              <span className="ml-2 text-xs text-gray-400">Upcoming</span>
            </div>
          </nav>
        </aside>

        <main className="flex-1 overflow-y-auto bg-slate-50/50">
          <div className="p-6 md:p-8">
            <div className="mb-8">
              <h2 className="text-2xl font-semibold tracking-tight text-gray-900 md:text-3xl">
                Live updates
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Recent news and efficacy & safety data for {categoryName}.
              </p>
            </div>

            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader2 className="h-10 w-10 animate-spin text-slate-400" aria-hidden />
                <p className="mt-4 text-sm text-slate-500">Loading latest articles…</p>
              </div>
            ) : error ? (
              <div className="rounded-xl border border-slate-200 bg-white py-12 text-center shadow-sm">
                <p className="text-slate-600">Could not load live ticker. Please try again.</p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => refetch()}
                >
                  Retry
                </Button>
              </div>
            ) : isEmpty ? (
              <div className="rounded-xl border border-slate-200 bg-white py-16 text-center shadow-sm">
                <Newspaper className="mx-auto h-12 w-12 text-slate-300" aria-hidden />
                <p className="mt-4 font-medium text-slate-600">No updates yet</p>
                <p className="mt-1 text-sm text-slate-500">
                  Latest articles and efficacy & safety highlights will appear here for this category.
                </p>
              </div>
            ) : (
              <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      Latest articles
                    </h3>
                    <p className="mt-0.5 text-sm text-slate-500">
                      {displayedItems.length} {displayedItems.length === 1 ? 'item' : 'items'}
                      {selectedMonthKey
                        ? ` in ${availableMonths.find((m) => m.key === selectedMonthKey)?.label ?? ''}`
                        : ''}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50/80 pl-2.5 pr-1 py-1.5 focus-within:border-slate-300 focus-within:bg-white focus-within:ring-2 focus-within:ring-[var(--primary)]/20 focus-within:ring-offset-1 transition-colors">
                      <Calendar className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                      <select
                        value={selectedMonthKey}
                        onChange={(e) => setSelectedMonthKey(e.target.value)}
                        aria-label="Filter by month"
                        className="min-w-[10rem] border-0 bg-transparent py-2 pr-8 pl-2 text-sm font-medium text-slate-800 focus:ring-0 focus:outline-none"
                      >
                        <option value="">All months ({latestItems.length})</option>
                        {availableMonths.map((month) => (
                          <option key={month.key} value={month.key}>
                            {month.label} ({month.count})
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      onClick={() => setEfficacyFirst((v) => !v)}
                      aria-pressed={efficacyFirst}
                      aria-label={efficacyFirst ? 'Show latest first' : 'Show efficacy & safety highlights first'}
                      className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 focus:ring-offset-2 shrink-0 ${
                        efficacyFirst
                          ? 'border-[var(--primary)] bg-[var(--primary)] text-white shadow-sm hover:bg-[var(--accent-dark)] hover:border-[var(--accent-dark)]'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      <BarChart3 className="h-4 w-4 shrink-0" aria-hidden />
                      Efficacy & Safety highlights
                    </button>
                  </div>
                </div>

                {displayedItems.length === 0 ? (
                  <div className="rounded-lg bg-slate-50 py-10 text-center">
                    <p className="text-sm text-slate-600">No articles in this month.</p>
                    <button
                      type="button"
                      onClick={() => setSelectedMonthKey('')}
                      className="mt-3 text-sm font-medium text-[var(--primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 focus:ring-offset-2 rounded"
                    >
                      Show all months
                    </button>
                  </div>
                ) : (
                  <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2">
                    {displayedItems.map((item, i) =>
                      item.type === 'result' ? (
                        <ResultCard key={`result-${item.value.url}-${i}`} result={item.value} />
                      ) : (
                        <ArticleCard key={`article-${item.value.url}-${i}`} article={item.value} />
                      )
                    )}
                  </div>
                )}
              </section>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
