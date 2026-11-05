'use client';

import * as React from 'react';
import Link from 'next/link';
import { useSession } from "@/lib/supabase/hooks";
import { Logo } from '@/components/Logo';
import { UserMenu } from '@/components/user-menu';
import { HomeNavLink } from '@/components/nav/HomeNavLink';
import { Search, ArrowUpRight } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const CANCER_TYPES = [
  { name: 'Cutaneous Melanoma',                        slug: 'cutaneous-melanoma',                           accent: '#1B4F65' },
  { name: 'Cutaneous Squamous Cell Carcinoma (cSCC)',  slug: 'cutaneous-squamous-cell-carcinoma',            accent: '#2D7D5A' },
  { name: 'Cutaneous Melanoma (Brain/CNS Metastases)', slug: 'cutaneous-melanoma-with-brain-cns-metastasis', accent: '#5B3E8F' },
  { name: 'Uveal Melanoma',                            slug: 'uveal-melanoma',                               accent: '#1A4A8A' },
  { name: 'Acral Melanoma',                            slug: 'acral-melanoma',                               accent: '#7B3FA0' },
  { name: 'Mucosal Melanoma',                          slug: 'mucosal-melanoma',                             accent: '#A63820' },
  { name: 'Basal Cell Carcinoma (BCC)',                slug: 'basal-cell-carcinoma',                         accent: '#8A5C1E' },
  { name: 'Merkel Cell Carcinoma (MCC)',               slug: 'merkel-cell-carcinoma',                        accent: '#1E7070' },
];

export default function MainDashboardPage() {
  const { data: session } = useSession();
  const [searchQuery, setSearchQuery] = React.useState('');

  const filteredTypes = CANCER_TYPES.filter((type) =>
    type.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <style>{`
        @keyframes cardIn {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .cancer-card { animation: cardIn 0.35s ease both; }
        .cancer-card:nth-child(1) { animation-delay: 0ms; }
        .cancer-card:nth-child(2) { animation-delay: 45ms; }
        .cancer-card:nth-child(3) { animation-delay: 90ms; }
        .cancer-card:nth-child(4) { animation-delay: 135ms; }
        .cancer-card:nth-child(5) { animation-delay: 180ms; }
        .cancer-card:nth-child(6) { animation-delay: 225ms; }
        .cancer-card:nth-child(7) { animation-delay: 270ms; }
        .cancer-card:nth-child(8) { animation-delay: 315ms; }
      `}</style>

      <div
        className="flex flex-col h-screen w-full overflow-hidden relative selection:bg-[var(--brand-accent-light)] selection:text-[var(--brand-primary)]"
        style={{ backgroundColor: '#F4F8F6' }}
      >
        <header className="bg-white border-b border-slate-200 shrink-0 z-50 sticky top-0 shadow-sm">
          <div className="w-full px-8">
            <div className="flex items-center justify-between h-14 gap-4">
              <Link href={ROUTES.DASHBOARD} className="brand flex-shrink-0">
                <Logo className="text-[22px]" />
              </Link>
              <div className="flex items-center gap-2">
                <HomeNavLink />
                {session?.user && (
                  <UserMenu
                    email={session.user.email || null}
                    name={session.user.user_metadata?.full_name || null}
                    image={undefined}
                  />
                )}
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 flex flex-col items-center pt-8 sm:pt-10 lg:pt-12 pb-16 sm:pb-20 px-10 sm:px-12 lg:px-16 xl:px-20 2xl:px-24 overflow-y-auto z-10 custom-scrollbar relative">
          <div className="w-full max-w-7xl 2xl:max-w-[1600px]">

            {/* Hero row: title left, search right */}
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-5 mb-5">
              <div>
                <p
                  className="text-[11px] font-medium uppercase tracking-[0.14em] text-(--brand-text-muted) mb-2"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  Oncology Intelligence · {CANCER_TYPES.length} Indications
                </p>
                {/* The same title type as PageHeader on every other page. */}
                <h1
                  className="font-semibold leading-[1.1] tracking-[-0.01em] text-(--brand-text)"
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(24px, 3.4vw, 34px)',
                  }}
                >
                  Disease Portfolios{' '}
                  <span style={{ color: 'var(--brand-primary)' }}>
                    <span className="brand-text"><span className="brand-bio">bio</span>nocular</span>
                  </span>
                </h1>
                <p className="mt-2 text-sm text-[var(--brand-text-muted)] max-w-md">
                  Human-verified oncology signals and clinical trial intelligence.
                </p>
              </div>

              <div className="relative group w-full sm:w-64 shrink-0">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Search className="h-3.5 w-3.5 text-[var(--brand-text-muted)] group-focus-within:text-[var(--brand-primary)] transition-colors" />
                </div>
                <input
                  type="text"
                  aria-label="Filter indications"
                  placeholder="Filter indications…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="block w-full pl-9 pr-3 py-2.5 bg-white border border-[var(--brand-border)] rounded-lg text-[var(--brand-text)] placeholder-[var(--brand-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-accent-light)] focus:border-[var(--brand-primary)] shadow-sm transition-all text-sm"
                />
              </div>
            </div>

            {/* Hairline divider */}
            <div className="h-px bg-[var(--brand-border)] mb-7" />

            {/* Card grid — 4×2 on desktop */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
              {filteredTypes.map((type) => (
                <Link
                  key={type.slug}
                  href={`/dashboard/${type.slug}`}
                  className="cancer-card group block rounded-[7px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-[#F4F8F6]"
                >
                  <div
                    className="relative bg-white overflow-hidden cursor-pointer flex flex-col min-h-[112px] sm:min-h-[168px] transition-all duration-200 hover:shadow-lg hover:-translate-y-px active:scale-[0.98] active:duration-100"
                    style={{ borderRadius: '7px', border: '1px solid #dce9e4' }}
                  >
                    {/* Large faint ordinal, decorative. Its place in the full list, whatever the filter shows. */}
                    <div
                      aria-hidden
                      className="absolute right-2 bottom-1 text-[48px] sm:text-[72px] leading-none select-none pointer-events-none font-black"
                      style={{
                        color: type.accent,
                        opacity: 0.07,
                        fontVariantNumeric: 'tabular-nums',
                        fontFamily: 'var(--font-display)',
                      }}
                    >
                      {String(CANCER_TYPES.indexOf(type) + 1).padStart(2, '0')}
                    </div>

                    <div className="flex flex-col flex-1 p-4 relative z-10">
                      {/* Cancer name in the display face */}
                      <h2
                        className="leading-snug flex-1 text-[var(--brand-text)] line-clamp-3"
                        style={{
                          fontFamily: "var(--font-display)",
                          fontWeight: 600,
                          fontSize: '15px',
                          letterSpacing: '-0.01em',
                        }}
                      >
                        {type.name}
                      </h2>

                      {/* Shown on hover or keyboard focus, and always where there is no hover. */}
                      <div
                        aria-hidden
                        className="flex items-center gap-0.5 mt-3 text-xs font-semibold opacity-0 -translate-x-2 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0 group-focus-visible:opacity-100 group-focus-visible:translate-x-0 [@media(hover:none)]:opacity-100 [@media(hover:none)]:translate-x-0"
                        style={{ color: type.accent }}
                      >
                        View
                        <ArrowUpRight className="h-3 w-3" />
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>

            {filteredTypes.length === 0 && (
              <div className="text-center py-20">
                <p className="text-sm text-[var(--brand-text-muted)]">
                  No indications match <em>&ldquo;{searchQuery}&rdquo;</em>
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </>
  );
}
