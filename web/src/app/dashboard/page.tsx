'use client';

import * as React from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { Logo } from '@/components/Logo';
import { UserMenu } from '@/components/user-menu';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { Search, Activity, ArrowRight } from 'lucide-react';

const CANCER_TYPES = [
  { name: 'Cutaneous/Metastatic Melanoma', slug: 'cutaneous-melanoma' },
  { name: 'Cutaneous Squamous Cell Carcinoma', slug: 'cutaneous-squamous-cell-carcinoma' },
  { name: 'Cutaneous Melanoma with Brain/CNS Metastasis', slug: 'cutaneous-melanoma-with-brain-cns-metastasis' },
  { name: 'Uveal Melanoma', slug: 'uveal-melanoma' },
  { name: 'Acral Melanoma', slug: 'acral-melanoma' },
  { name: 'Mucosal Melanoma', slug: 'mucosal-melanoma' },
  { name: 'Basal Cell Carcinoma', slug: 'basal-cell-carcinoma' },
  { name: 'Merkel Cell Carcinoma', slug: 'merkel-cell-carcinoma' },
];

export default function MainDashboardPage() {
  const { data: session } = useSession();
  const [searchQuery, setSearchQuery] = React.useState('');

  const filteredTypes = CANCER_TYPES.filter((type) =>
    type.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-screen w-full bg-[var(--brand-bg)] overflow-hidden relative selection:bg-[var(--brand-accent-light)] selection:text-[var(--brand-primary)]">
      <header className="bg-white border-b border-slate-200 shrink-0 z-50 sticky top-0 shadow-sm">
        <div className="w-full px-10 sm:px-12 lg:px-16 xl:px-20 2xl:px-24">
          <div className="flex items-center justify-between h-14 sm:h-16 gap-3">
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

      <main className="flex-1 flex flex-col items-center pt-8 sm:pt-10 lg:pt-12 pb-16 sm:pb-20 px-10 sm:px-12 lg:px-16 xl:px-20 2xl:px-24 overflow-y-auto z-10 custom-scrollbar relative">
        <div className="w-full max-w-7xl 2xl:max-w-[1600px]">
          {/* Hero Section */}
          <div className="text-center mb-8 sm:mb-10 lg:mb-12">
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[var(--brand-text)] tracking-tight flex flex-wrap items-center justify-center gap-2 sm:gap-3 mb-4">
              Disease Portfolios <span style={{ color: 'var(--brand-primary)' }}>bi<span className="brand-o">o</span>nocular</span>
            </h1>
            <p className="text-sm sm:text-base lg:text-lg text-[var(--brand-text-muted)] max-w-2xl mx-auto font-medium px-1">
              Access human-verified oncology signals and clinical trial intelligence across multiple therapeutic areas.
            </p>
          </div>

          {/* Search Bar */}
          <div className="w-full max-w-2xl mx-auto mb-10 sm:mb-12 lg:mb-16 relative group">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-[var(--brand-text-muted)] group-focus-within:text-[var(--brand-primary)] transition-colors" />
            </div>
            <input
              type="text"
              placeholder="Search indications... (e.g. Melanoma)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="block w-full pl-11 pr-4 py-3 sm:py-4 bg-white border border-[var(--brand-border)] rounded-2xl text-[var(--brand-text)] placeholder-[var(--brand-text-muted)] opacity-80 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-[var(--brand-accent-light)] focus:border-[var(--brand-primary)] shadow-sm transition-all text-base font-medium"
            />
          </div>

          {/* Grid: 1 col below 640px, 2 cols 640–1023px, 3 cols 1024px+, 4 cols 1536px+ */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4 sm:gap-5 lg:gap-6">
            {filteredTypes.map((type) => (
              <Link key={type.slug} href={`/dashboard/${type.slug}`}>
                <div className="group relative bg-white border border-[var(--brand-border)] rounded-2xl p-5 sm:p-6 shadow-md hover:shadow-xl hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden flex flex-col min-h-[140px] sm:min-h-[160px]">
                  {/* Subtle hover tint */}
                  <div className="absolute inset-0 bg-[var(--brand-accent-light)] opacity-0 group-hover:opacity-30 transition-opacity duration-300 rounded-2xl" />
                  
                  {/* Card Content */}
                  <div className="relative z-10 flex flex-col h-full">
                    <div className="flex items-start justify-between mb-4">
                      <div className="w-10 h-10 rounded-xl bg-[var(--brand-accent-light)] flex items-center justify-center group-hover:scale-110 transition-all duration-300">
                         <Activity className="h-5 w-5 text-[var(--brand-primary)]" />
                      </div>
                    </div>
                    
                    <h2 className="text-lg font-bold text-[var(--brand-text)] mb-2 group-hover:text-[var(--brand-primary)] transition-colors line-clamp-2 leading-tight flex-1">
                      {type.name}
                    </h2>
                    
                    <div className="mt-auto flex items-center justify-end pt-4 border-t border-slate-100">
                      <div className="w-8 h-8 rounded-full bg-[var(--brand-bg)] flex items-center justify-center group-hover:bg-[var(--brand-primary)] transition-colors">
                        <ArrowRight className="h-4 w-4 text-[var(--brand-primary)] group-hover:text-white transition-colors" />
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
          
          {filteredTypes.length === 0 && (
            <div className="text-center py-20">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[var(--brand-bg)] mb-4">
                <Search className="h-6 w-6 text-[var(--brand-primary)]" />
              </div>
              <h3 className="text-lg font-semibold text-[var(--brand-text)] mb-1">No indications found</h3>
              <p className="text-[var(--brand-text-muted)]">Try adjusting your search query.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
