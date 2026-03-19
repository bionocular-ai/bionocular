'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Logo } from '@/components/Logo';
import {
  Clock, LineChart, BrainCircuit, Filter, Database,
  HelpCircle, ClipboardList, Unplug, ArrowRight,
  FileX, Table, FileText, Network, LayoutDashboard, Brain, RefreshCw
} from 'lucide-react';

const HERO_PHRASES: { strong: string; rest: string }[] = [
  {
    strong: 'Next-gen AI and Machine learning',
    rest: ' providing analytics and insights (with Human verification) in the Oncology landscape.',
  },
  {
    strong: 'Cutting the noise',
    rest: ' and only focusing on the key elements.',
  },
];

const ROTATOR_DISPLAY_MS = 5000;
const ROTATOR_FADE_MS = 600;

const slideFade = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -14 },
  transition: {
    duration: ROTATOR_FADE_MS / 1000,
    ease: [0.25, 0.46, 0.45, 0.94] as const,
  },
};

function HeroTextRotator() {
  const [index, setIndex] = useState(0);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const runCycle = () => {
      const t = setTimeout(() => {
        setIndex((i) => (i + 1) % HERO_PHRASES.length);
      }, ROTATOR_DISPLAY_MS);
      timeoutsRef.current.push(t);
    };

    const firstRun = setTimeout(runCycle, ROTATOR_DISPLAY_MS);
    const interval = setInterval(runCycle, ROTATOR_DISPLAY_MS);
    return () => {
      clearTimeout(firstRun);
      clearInterval(interval);
      timeoutsRef.current.forEach(clearTimeout);
      timeoutsRef.current = [];
    };
  }, []);

  const phrase = HERO_PHRASES[index];

  return (
    <div
      className="hero-rotator-wrapper relative min-h-[7rem] sm:min-h-[8.5rem] md:min-h-[10rem] lg:min-h-[12rem] w-full max-w-xl flex flex-col justify-center"
      aria-live="polite"
      aria-atomic="true"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.p
          key={index}
          className="hero-rotator-phrase w-full text-[#E9ECEF] text-xl leading-[1.2] tracking-[-0.02em] sm:text-2xl md:text-3xl lg:text-4xl text-left pr-4"
          {...slideFade}
          aria-hidden={false}
        >
          <span className="font-bold" style={{ fontWeight: 700 }}>
            {phrase.strong}
          </span>
          <span className="font-light" style={{ fontWeight: 300, opacity: 0.85 }}>
            {phrase.rest}
          </span>
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

export default function Home() {
  const { data: session } = useSession();
  const [activeNav, setActiveNav] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navLinksRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);

  // Position sliding indicator on active nav link (smooth when skipping sections)
  useEffect(() => {
    const container = navLinksRef.current;
    const indicator = indicatorRef.current;
    if (!container || !indicator) return;

    const activeLink = container.querySelector(`a[href="${activeNav}"]`) as HTMLAnchorElement | null;
    if (!activeLink) {
      indicator.style.opacity = '0';
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const linkRect = activeLink.getBoundingClientRect();
    indicator.style.left = `${linkRect.left - containerRect.left}px`;
    indicator.style.width = `${linkRect.width}px`;
    indicator.style.opacity = '1';
  }, [activeNav, mobileMenuOpen]);

  // Re-run on resize
  useEffect(() => {
    const container = navLinksRef.current;
    const indicator = indicatorRef.current;
    if (!container || !indicator) return;

    const update = () => {
      const activeLink = container.querySelector(`a[href="${activeNav}"]`) as HTMLAnchorElement | null;
      if (!activeLink) return;
      const containerRect = container.getBoundingClientRect();
      const linkRect = activeLink.getBoundingClientRect();
      indicator.style.left = `${linkRect.left - containerRect.left}px`;
      indicator.style.width = `${linkRect.width}px`;
    };

    const ro = new ResizeObserver(update);
    ro.observe(container);
    update();
    return () => ro.disconnect();
  }, [activeNav]);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  // Close mobile menu on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [mobileMenuOpen]);

  // Smooth scrolling and active nav
  useEffect(() => {
    const EXTRA_GAP_PX = 10;

    function findAnchorTarget(hash: string) {
      const el = document.querySelector(hash);
      if (!el) return null;
      return el.querySelector('h2, h1') || el;
    }

    function scrollToHash(hash: string) {
      const targetEl = findAnchorTarget(hash);
      if (!targetEl) return;
      const header = document.querySelector('.site-header');
      const headerHeight = header ? (header as HTMLElement).offsetHeight : 0;
      const top = targetEl.getBoundingClientRect().top + window.pageYOffset - headerHeight - EXTRA_GAP_PX;
      window.scrollTo({ top, behavior: 'smooth' });
    }

    function handleAnchorClick(e: Event) {
      const anchor = e.currentTarget as HTMLAnchorElement;
      const href = anchor.getAttribute('href');
      if (!href || href === '#') return;
      if (href === '#hero') {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
        setActiveNav('#hero');
        return;
      }
      const targetEl = findAnchorTarget(href);
      if (!targetEl) return;
      e.preventDefault();
      const header = document.querySelector('.site-header');
      const headerHeight = header ? (header as HTMLElement).offsetHeight : 0;
      const top = targetEl.getBoundingClientRect().top + window.pageYOffset - headerHeight - EXTRA_GAP_PX;
      window.scrollTo({ top, behavior: 'smooth' });
      setActiveNav(href);
    }

    const anchors = document.querySelectorAll('a[href^="#"]');
    anchors.forEach((anchor) => {
      anchor.addEventListener('click', handleAnchorClick);
    });

    // Single scroll-based active section: use a fixed "activation line" so one section wins (no bouncing)
    const ACTIVATION_OFFSET_PX = 120; // distance from top of viewport to decide active section
    const sectionIds = ['hero', 'platform', 'about', 'contact'];

    function getActiveSectionId(): string {
      const header = document.querySelector('.site-header');
      const headerHeight = header ? (header as HTMLElement).offsetHeight : 0;
      const line = headerHeight + ACTIVATION_OFFSET_PX;

      // Active section = last one whose top is still at or above the activation line (stable, no bounce)
      let activeId = '#hero';
      for (const id of sectionIds) {
        const el = document.getElementById(id);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top <= line) activeId = '#' + id;
        else break;
      }
      return activeId;
    }

    let rafId: number | null = null;
    const handleScroll = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        setActiveNav(getActiveSectionId());
      });
    };

    // Handle initial hash - use requestAnimationFrame to avoid setState in effect
    const initialHash = window.location.hash;
    if (initialHash) {
      requestAnimationFrame(() => {
        scrollToHash(initialHash);
        setActiveNav(initialHash);
      });
    } else {
      requestAnimationFrame(() => setActiveNav(getActiveSectionId()));
    }

    const handleHashChange = () => {
      if (window.location.hash) {
        scrollToHash(window.location.hash);
        setActiveNav(window.location.hash);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('hashchange', handleHashChange);

    return () => {
      anchors.forEach((anchor) => {
        anchor.removeEventListener('click', handleAnchorClick);
      });
      if (rafId !== null) cancelAnimationFrame(rafId);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  const currentYear = new Date().getFullYear();

  return (
    <>
      {mobileMenuOpen && (
        <div 
          className="mobile-menu-backdrop" 
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}
      <header className="site-header">
        <div className="container header-inner">
          <a className="brand" href="#" aria-label="Bionocular Home">
            <Logo height={32} />
            <span className="brand-text" style={{ lineHeight: '1.2' }}>
              bi<span className="brand-o">o</span>nocular
            </span>
          </a>
          <button 
            className="mobile-menu-toggle" 
            aria-label="Toggle menu"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            <span className={`hamburger ${mobileMenuOpen ? 'open' : ''}`}>
              <span></span>
              <span></span>
              <span></span>
            </span>
          </button>
          <nav className={`nav ${mobileMenuOpen ? 'mobile-open' : ''}`}>
            <div className="nav-links-wrap" ref={navLinksRef}>
              <span ref={indicatorRef} className="nav-indicator" aria-hidden="true" />
              <a 
                href="#hero" 
                className={activeNav === '#hero' ? 'active' : ''}
                onClick={() => setMobileMenuOpen(false)}
              >
                Home
              </a>
              <a 
                href="#platform" 
                className={activeNav === '#platform' ? 'active' : ''}
                onClick={() => setMobileMenuOpen(false)}
              >
                Product
              </a>
              <a 
                href="#about" 
                className={activeNav === '#about' ? 'active' : ''}
                onClick={() => setMobileMenuOpen(false)}
              >
                About
              </a>
              <a 
                href="#contact" 
                className={activeNav === '#contact' ? 'active' : ''}
                onClick={() => setMobileMenuOpen(false)}
              >
                Contact
              </a>
            </div>
            {session ? (
              <Link href="/dashboard" className="btn btn-primary btn-small">
                Dashboard
              </Link>
            ) : (
              <Link href="/login" className="btn btn-primary btn-small">
                Login
              </Link>
            )}
          </nav>
        </div>
      </header>

      <section
        className="hero hero-split min-h-[92vh] pt-[62px] md:min-h-[92vh] relative"
        id="hero"
        aria-labelledby="heroHeadline"
      >
        {/* Full-bleed brand teal atmospheric background */}
        <div className="hero-atmosphere absolute inset-0 pointer-events-none" aria-hidden="true" />

        <div className="hero-split-grid grid grid-cols-1 md:grid-cols-[2fr_3fr] min-h-[calc(92vh-62px)] relative z-0">

          {/* Left: text column */}
          <div className="hero-text-column flex flex-col justify-center gap-8 py-12 md:py-16 text-left">

            {/* Eyebrow badge */}
            <div className="inline-flex items-center gap-2 self-start">
              <span
                className="text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full"
                style={{
                  background: 'rgba(122,193,162,0.18)',
                  color: '#7AC1A2',
                  border: '1px solid rgba(122,193,162,0.35)',
                }}
              >
                Oncology Intelligence Platform
              </span>
            </div>

            {/* H1 rotator */}
            <h1 id="heroHeadline" className="hero-split-title w-full max-w-xl m-0">
              <HeroTextRotator />
            </h1>

            {/* Sub-headline */}
            <p
              className="text-base md:text-lg max-w-md leading-relaxed m-0"
              style={{ color: 'rgba(218,240,230,0.8)' }}
            >
              Human‑verified oncology intelligence for research and medical teams — from raw data noise to clinical clarity, instantly.
            </p>

            {/* CTA buttons */}
            <div className="hero-split-ctas flex mt-6">
              <a
                href="#platform"
                className="btn flex items-center justify-center"
                style={{
                  background: 'var(--brand-accent)',
                  color: '#0E3547',
                  border: 'none',
                  borderRadius: '9999px',
                  padding: '16px 36px',
                  fontWeight: 700,
                  fontSize: '1.05rem',
                  letterSpacing: '0.01em',
                  transition: 'background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = '#5EADA8';
                  (e.currentTarget as HTMLElement).style.boxShadow = '0 8px 24px rgba(122,193,162,0.45)';
                  (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--brand-accent)';
                  (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                  (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
                }}
              >
                See How It Works
                <ArrowRight className="w-5 h-5 ml-2" strokeWidth={2.5} />
              </a>
            </div>

            <div className="hero-glass-divider hidden md:block" aria-hidden="true" />
          </div>

          {/* Right: video with brand teal overlay */}
          <div className="hero-video-column relative min-h-[50vh] md:min-h-[calc(92vh-62px)] w-full overflow-hidden">
            <video
              className="absolute inset-0 w-full h-full object-cover object-center"
              src="/Bionocular.mp4"
              autoPlay
              loop
              muted
              playsInline
              aria-hidden="true"
            />
            <div className="hero-video-overlay absolute inset-0 pointer-events-none" aria-hidden="true" />
          </div>

        </div>
      </section>

      <main>
        {/* SECTION 1: COMPARISON */}
        <section className="section py-20" id="platform" style={{ background: 'var(--brand-bg)' }}>
          <div className="container max-w-6xl mx-auto px-4">
            <div className="text-center mb-16">
              <span
                className="inline-block text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full mb-4"
                style={{ background: 'var(--brand-accent-light)', color: 'var(--brand-primary)' }}
              >
                Why Bionocular
              </span>
              <h2 className="text-3xl md:text-4xl font-bold mb-4" style={{ color: 'var(--brand-text)' }}>
                The New Standard in{' '}
                <span style={{ color: 'var(--brand-primary)' }}>Oncology Intelligence</span>
              </h2>
              <p className="text-lg max-w-2xl mx-auto" style={{ color: 'var(--brand-text-muted)' }}>
                Discover why leading research and medical teams are leaving static databases behind for dynamic, AI-driven insights.
              </p>
            </div>

            <div className="relative grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
              {/* VS Badge */}
              <div
                className="hidden lg:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-12 h-12 rounded-full items-center justify-center font-bold shadow-lg z-10 border-4"
                style={{ background: 'var(--brand-primary)', color: '#fff', borderColor: 'var(--brand-bg)' }}
              >
                VS
              </div>

              {/* Left: bionocularAI */}
              <div
                className="rounded-2xl shadow-xl p-8 relative overflow-hidden"
                style={{ background: '#fff', border: '1.5px solid var(--brand-border)' }}
              >
                {/* Top accent stripe */}
                <div className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl" style={{ background: 'linear-gradient(90deg, var(--brand-primary), var(--brand-accent))' }} />
                <h3 className="text-2xl font-bold mb-1" style={{ color: 'var(--brand-primary)' }}>
                  With bi<span style={{ textDecoration: 'underline', textDecorationColor: 'var(--brand-accent)', textDecorationThickness: '2px', textUnderlineOffset: '4px' }}>o</span>nocularAI
                </h3>
                <p className="font-medium mb-8" style={{ color: 'var(--brand-accent)' }}>Dynamic, AI-Driven Intelligence</p>

                <div className="space-y-6">
                  {[
                    { Icon: Clock, text: 'Offers real-time trial and treatment landscape changes in specific cancers' },
                    { Icon: LineChart, text: 'Instantly plots 100+ endpoints on dynamic 2D & 3D analytical models' },
                    { Icon: BrainCircuit, text: 'Disease-Specific AI Agent, Active Reasoning Partner' },
                    { Icon: Filter, text: 'The full ecosystem is connected with innovative filters to streamline data and is very user-friendly' },
                  ].map(({ Icon, text }) => (
                    <div key={text} className="flex gap-4">
                      <div
                        className="shrink-0 w-12 h-12 rounded-lg flex items-center justify-center"
                        style={{ background: 'var(--brand-accent-light)', color: 'var(--brand-primary)' }}
                      >
                        <Icon className="w-6 h-6" />
                      </div>
                      <div className="flex items-center">
                        <p className="font-medium" style={{ color: 'var(--brand-text)' }}>{text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: Others */}
              <div
                className="rounded-2xl p-8"
                style={{ background: 'var(--brand-bg)', border: '1.5px solid var(--brand-border)' }}
              >
                <h3 className="text-2xl font-bold mb-1" style={{ color: 'var(--brand-text)' }}>Others</h3>
                <p className="font-medium mb-8" style={{ color: 'var(--brand-text-muted)' }}>Static, Passive Data</p>

                <div className="space-y-6">
                  {[
                    { Icon: Database, text: 'Siloed Oncology Vendors & Flat Clinical Scrapers', sub: '"Give you a login to a database"' },
                    { Icon: HelpCircle, text: 'Generic LLMs lacking disease-specific context or specialized oncology training.', sub: '' },
                    { Icon: ClipboardList, text: 'Static Data Aggregators', sub: '"Just dump lists of trial updates"' },
                    { Icon: Unplug, text: 'Data is highly fragmented and segregated', sub: '' },
                  ].map(({ Icon, text, sub }) => (
                    <div key={text} className="flex gap-4 opacity-75">
                      <div
                        className="shrink-0 w-12 h-12 rounded-lg flex items-center justify-center"
                        style={{ background: '#E8EFF2', color: '#8AAAB5' }}
                      >
                        <Icon className="w-6 h-6" />
                      </div>
                      <div className="flex items-center">
                        <p style={{ color: 'var(--brand-text-muted)' }}>
                          {text}{sub && <><br /><span className="italic text-sm">{sub}</span></>}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 2: PIPELINE FLOW */}
        <section className="section py-20" id="about" style={{ background: '#fff' }}>
          <div className="container max-w-6xl mx-auto px-4">
            <div className="text-center mb-16">
              <span
                className="inline-block text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full mb-4"
                style={{ background: 'var(--brand-accent-light)', color: 'var(--brand-primary)' }}
              >
                How It Works
              </span>
              <h2 className="text-3xl md:text-4xl font-bold mb-4" style={{ color: 'var(--brand-text)' }}>
                The Clinical Clarity Pipeline
              </h2>
              <p className="text-lg max-w-2xl mx-auto" style={{ color: 'var(--brand-text-muted)' }}>
                From data noise to clinical clarity: The bi
                <span style={{ textDecoration: 'underline', textDecorationColor: 'var(--brand-accent)', textDecorationThickness: '2px', textUnderlineOffset: '4px' }}>o</span>
                nocular AI Advantage
              </p>
            </div>

            {/* 3-Step Flow */}
            <div className="flex flex-col md:flex-row items-stretch gap-4 md:gap-2 lg:gap-4 relative w-full">

              {/* Step 1: Challenge */}
              <div
                className="flex-1 flex flex-col items-center text-center p-6 rounded-xl"
                style={{ background: 'var(--brand-bg)', border: '1.5px solid var(--brand-border)' }}
              >
                <h4 className="font-bold mb-1" style={{ color: 'var(--brand-text)' }}>The Challenge:</h4>
                <p className="text-sm mb-6" style={{ color: 'var(--brand-text-muted)' }}>Fragmented Data &amp; Noise</p>

                <div className="relative w-32 h-32 mb-6 flex items-center justify-center opacity-60">
                  <div className="absolute grid grid-cols-2 gap-2">
                    <FileX className="w-8 h-8" style={{ color: '#E57373' }} strokeWidth={1.5} />
                    <Table className="w-8 h-8" style={{ color: 'var(--brand-text-muted)' }} strokeWidth={1.5} />
                    <FileText className="w-8 h-8" style={{ color: 'var(--brand-accent)' }} strokeWidth={1.5} />
                    <FileX className="w-8 h-8" style={{ color: 'var(--brand-text-muted)' }} strokeWidth={1.5} />
                  </div>
                </div>

                <p className="text-sm leading-relaxed" style={{ color: 'var(--brand-text-muted)' }}>
                  Voluminous, unstructured data across disparate sources makes manual analysis slow and incomplete.
                </p>
              </div>

              {/* Arrow 1 */}
              <div className="hidden md:flex items-center justify-center px-1 lg:px-2 shrink-0" style={{ color: 'var(--brand-border)' }}>
                <ArrowRight className="w-8 h-8 lg:w-10 lg:h-10" strokeWidth={1.5} />
              </div>

              {/* Step 2: Solution */}
              <div
                className="flex-1 flex flex-col items-center text-center p-6 rounded-xl"
                style={{ background: 'var(--brand-accent-light)', border: '1.5px solid var(--brand-accent)' }}
              >
                <h4 className="font-bold mb-1" style={{ color: 'var(--brand-primary)' }}>The Solution:</h4>
                <p className="text-sm mb-6" style={{ color: 'var(--brand-primary)' }}>Intelligent Synthesis &amp; Structure</p>

                <div className="relative w-32 h-32 mb-6 flex flex-col items-center justify-center">
                  <Filter className="w-16 h-16 mb-2" style={{ color: 'var(--brand-primary)' }} strokeWidth={1.5} />
                  <div
                    className="text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded"
                    style={{ background: 'var(--brand-primary)', color: '#fff' }}
                  >
                    AI + Human Engine
                  </div>
                  <Network className="w-8 h-8 mt-2" style={{ color: 'var(--brand-accent)' }} strokeWidth={1.5} />
                </div>

                <p className="text-sm leading-relaxed" style={{ color: 'var(--brand-text)' }}>
                  Real-time aggregation and structuring of trials, publications, and news using advanced NLP and machine learning.
                </p>
              </div>

              {/* Arrow 2 */}
              <div className="hidden md:flex items-center justify-center px-1 lg:px-2 shrink-0" style={{ color: 'var(--brand-accent)' }}>
                <ArrowRight className="w-8 h-8 lg:w-10 lg:h-10" strokeWidth={1.5} />
              </div>

              {/* Step 3: Edge */}
              <div
                className="flex-1 flex flex-col items-center text-left p-6 rounded-xl"
                style={{ background: 'var(--brand-primary)', border: '1.5px solid var(--brand-primary)' }}
              >
                <h4 className="font-bold mb-1 text-center w-full" style={{ color: '#fff' }}>The Unique Edge:</h4>
                <p className="text-sm mb-6 text-center w-full" style={{ color: 'var(--brand-accent)' }}>Expert-Curated Visualization</p>

                <div className="flex gap-4 mb-6 w-full justify-center" style={{ color: 'var(--brand-accent)' }}>
                  <LayoutDashboard className="w-8 h-8" strokeWidth={1.5} />
                  <Brain className="w-8 h-8" strokeWidth={1.5} />
                  <RefreshCw className="w-8 h-8" strokeWidth={1.5} />
                </div>

                <ul className="text-sm space-y-2 list-disc pl-4" style={{ color: 'rgba(218,240,230,0.9)' }}>
                  <li>Real-time trial updates and live news</li>
                  <li>Trial landscape with treatment cards and critical filters</li>
                  <li>All trial outcome data with user friendly analytics</li>
                  <li>Cancer specific AI agent</li>
                  <li>Regulatory timeline analytics</li>
                </ul>
              </div>

            </div>
          </div>
        </section>

      </main>

      <footer className="site-footer" id="contact">
        <div className="container footer-content">
          <div className="footer-section">
            {/* Brand lockup */}
            <div className="flex items-center gap-2 mb-2">
              <Logo height={28} />
              <span style={{ fontWeight: 700, fontSize: '1.25rem', color: '#fff', fontFamily: "'IBM Plex Sans', Inter, system-ui, sans-serif", letterSpacing: '0.2px' }}>
                bi<span className="brand-o">o</span>nocular
              </span>
            </div>
            <p>Human‑verified oncology intelligence for research and medical teams.</p>
          </div>
          <div className="footer-section">
            <h4>Contact</h4>
            <p>
              <a href="mailto:info@bionocular.ai">info@bionocular.ai</a>
            </p>
          </div>
          <div className="footer-section">
            <h4>Connect</h4>
            <div className="social-links">
              <a href="#" aria-label="LinkedIn">
                <i className="fab fa-linkedin"></i>
              </a>
              <a href="#" aria-label="Twitter/X">
                <i className="fab fa-x-twitter"></i>
              </a>
              <a href="mailto:info@bionocular.ai" aria-label="Email">
                <i className="fas fa-envelope"></i>
              </a>
            </div>
          </div>
        </div>
        <div className="container footer-bottom">
          <p>© {currentYear} Bionocular.ai. All rights reserved.</p>
        </div>
      </footer>
    </>
  );
}
