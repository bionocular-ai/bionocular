'use client';

import * as React from 'react';
import Link from 'next/link';
import { useSession } from "@/lib/supabase/hooks";
import { Logo } from '@/components/Logo';
import { UserMenu } from '@/components/user-menu';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { AgentNavLink } from '@/components/nav/AgentNavLink';
import { Search, ArrowUpRight } from 'lucide-react';

const CANCER_TYPES = [
  { name: 'Cutaneous Melanoma',                        slug: 'cutaneous-melanoma',                           accent: '#1B4F65', category: 'Cutaneous' },
  { name: 'Cutaneous Squamous Cell Carcinoma (cSCC)',  slug: 'cutaneous-squamous-cell-carcinoma',            accent: '#2D7D5A', category: 'Squamous' },
  { name: 'Cutaneous Melanoma (Brain/CNS Metastases)', slug: 'cutaneous-melanoma-with-brain-cns-metastasis', accent: '#5B3E8F', category: 'Brain/CNS' },
  { name: 'Uveal Melanoma',                            slug: 'uveal-melanoma',                               accent: '#1A4A8A', category: 'Uveal' },
  { name: 'Acral Melanoma',                            slug: 'acral-melanoma',                               accent: '#7B3FA0', category: 'Acral' },
  { name: 'Mucosal Melanoma',                          slug: 'mucosal-melanoma',                             accent: '#A63820', category: 'Mucosal' },
  { name: 'Basal Cell Carcinoma (BCC)',                slug: 'basal-cell-carcinoma',                         accent: '#8A5C1E', category: 'Basal' },
  { name: 'Merkel Cell Carcinoma (MCC)',               slug: 'merkel-cell-carcinoma',                        accent: '#1E7070', category: 'Merkel' },
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
              <Link href="/" className="brand flex-shrink-0">
                <Logo height={32} />
                <span className="brand-text text-lg">bi<span className="brand-o">o</span>nocular</span>
              </Link>
              <div className="flex items-center gap-2">
                <AgentNavLink />
                <DashboardNavLink />
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
                <p className="text-[9px] font-bold tracking-[0.22em] uppercase text-[var(--brand-text-muted)] mb-2 opacity-60">
                  Oncology Intelligence · {CANCER_TYPES.length} Indications
                </p>
                <h1 className="text-3xl sm:text-4xl font-extrabold text-[var(--brand-text)] tracking-tight leading-none">
                  Disease Portfolios{' '}
                  <span style={{ color: 'var(--brand-primary)' }}>
                    bi<span className="brand-o">o</span>nocular
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
              {filteredTypes.map((type, i) => (
                <Link
                  key={type.slug}
                  href={`/dashboard/${type.slug}`}
                  className="cancer-card block"
                >
                  <div
                    className="group relative bg-white overflow-hidden cursor-pointer flex flex-col min-h-[168px] transition-all duration-200 hover:shadow-lg hover:-translate-y-px"
                    style={{ borderRadius: '7px', border: '1px solid #dce9e4' }}
                  >
                    {/* Large faint ordinal — decorative depth */}
                    <div
                      className="absolute right-2 bottom-1 leading-none select-none pointer-events-none font-black"
                      style={{
                        color: type.accent,
                        opacity: 0.07,
                        fontSize: '72px',
                        fontVariantNumeric: 'tabular-nums',
                        fontFamily: 'Georgia, serif',
                      }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </div>

                    <div className="flex flex-col flex-1 p-4 relative z-10">
                      {/* Category label with color swatch */}
                      <div className="flex items-center gap-1.5 mb-3">
                        <span
                          className="shrink-0 rounded-[2px]"
                          style={{ width: '7px', height: '7px', backgroundColor: type.accent }}
                        />
                        <p
                          className="text-[9px] font-bold tracking-[0.18em] uppercase leading-none"
                          style={{ color: type.accent }}
                        >
                          {type.category}
                        </p>
                      </div>

                      {/* Cancer name in Lora serif */}
                      <h2
                        className="leading-snug flex-1 text-[var(--brand-text)] line-clamp-3"
                        style={{
                          fontFamily: "var(--font-lora), Georgia, serif",
                          fontWeight: 600,
                          fontSize: '15px',
                          letterSpacing: '-0.01em',
                        }}
                      >
                        {type.name}
                      </h2>

                      {/* Footer */}
                      <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-slate-100">
                        <span
                          className="text-[9px] font-mono font-semibold tracking-wider"
                          style={{ color: type.accent, opacity: 0.45 }}
                        >
                          #{String(i + 1).padStart(2, '0')}
                        </span>
                        <div
                          className="flex items-center gap-0.5 text-[11px] font-semibold opacity-0 group-hover:opacity-100 transition-all duration-200 translate-x-2 group-hover:translate-x-0"
                          style={{ color: type.accent }}
                        >
                          View
                          <ArrowUpRight className="h-3 w-3" />
                        </div>
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
