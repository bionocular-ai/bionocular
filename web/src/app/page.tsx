'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Logo } from '@/components/Logo';

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
  const [roleSelectValue, setRoleSelectValue] = useState('');
  const [roleDropdownOpen, setRoleDropdownOpen] = useState(false);
  const navLinksRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  const roleDropdownRef = useRef<HTMLDivElement>(null);

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

  // Close role dropdown when clicking outside
  useEffect(() => {
    if (!roleDropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (roleDropdownRef.current && !roleDropdownRef.current.contains(e.target as Node)) {
        setRoleDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [roleDropdownOpen]);

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

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    alert('Thank you for your message! We will get back to you soon.');
    e.currentTarget.reset();
    setRoleSelectValue('');
  };

  const ROLE_OPTIONS = [
    { value: 'researcher', label: 'Researcher' },
    { value: 'healthcare', label: 'Healthcare Professional' },
    { value: 'patient', label: 'Patient/Advocate' },
    { value: 'other', label: 'Other' },
  ];
  const rolePlaceholder = 'Select Your Role';

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
      >
        {/* Full-bleed atmospheric background: radial mesh gradient + noise */}
        <div className="hero-atmosphere absolute inset-0 pointer-events-none" aria-hidden="true" />
        <div className="hero-split-grid grid grid-cols-1 md:grid-cols-[2fr_3fr] min-h-[calc(92vh-62px)] relative z-0">
          {/* Left: text with soft-fade mask and glass divider */}
          <div className="hero-text-column flex flex-col justify-center py-12 md:py-16 text-left">
            <h1 id="heroHeadline" className="hero-split-title w-full max-w-xl">
              <HeroTextRotator />
            </h1>
            <div className="hero-glass-divider hidden md:block" aria-hidden="true" />
          </div>
          {/* Right: video with 10% dark overlay */}
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
        <section className="section section-problem" id="platform">
          <div className="container">
            <h2 className="section-title center">Comprehensive Research Intelligence</h2>
            <div className="card-grid">
              <article className="card feature-card">
                <i className="fas fa-microscope"></i>
                <h3>Research Aggregation</h3>
                <p>
                  Access consolidated oncology research findings from major medical congresses and
                  pharmaceutical companies.
                </p>
              </article>
              <article className="card feature-card">
                <i className="fas fa-chart-line"></i>
                <h3>Treatment Insights</h3>
                <p>
                  Track emerging approaches, drug developments, and clinical trial outcomes across
                  oncology treatment.
                </p>
              </article>
              <article className="card feature-card">
                <i className="fas fa-brain"></i>
                <h3>AI‑Powered Analysis</h3>
                <p>
                  Leverage analytics to identify trends and patterns—surfacing the signals that
                  matter and suppressing noise.
                </p>
              </article>
            </div>
          </div>
        </section>

        <section className="section section-about" id="about">
          <div className="container">
            <h2 className="section-title center">Why Choose Bionocular</h2>
            <div className="card-grid">
              <article className="card">
                <h3>Comprehensive Coverage</h3>
                <p>
                  Aggregate research from major oncology conferences, pharma pipelines, and advocacy
                  organizations.
                </p>
              </article>
              <article className="card">
                <h3>Specialized Focus</h3>
                <p>
                  Oncology‑tuned extraction and verification deliver clinically relevant, low‑noise
                  insights.
                </p>
              </article>
              <article className="card">
                <h3>Time‑Saving</h3>
                <p>
                  Eliminate manual sifting with organized, analyst‑verified briefs, alerts, and
                  datasets.
                </p>
              </article>
            </div>
          </div>
        </section>

        <section className="section section-contact" id="contact">
          <div className="container contact-wrap">
            <h2 className="section-title center">Get in Touch</h2>
            <div className="contact-form">
              <form onSubmit={handleSubmit}>
                <input
                  type="text"
                  name="name"
                  placeholder="Name"
                  required
                  aria-label="Name"
                />
                <input
                  type="email"
                  name="email"
                  placeholder="Email"
                  required
                  aria-label="Email"
                />
                <div className="contact-form-role-wrap" ref={roleDropdownRef}>
                  <input type="hidden" name="role" value={roleSelectValue} required />
                  <button
                    type="button"
                    onClick={() => setRoleDropdownOpen((o) => !o)}
                    aria-haspopup="listbox"
                    aria-expanded={roleDropdownOpen}
                    aria-label="Role"
                    className="contact-form-role-trigger"
                  >
                    <span>{roleSelectValue ? ROLE_OPTIONS.find((o) => o.value === roleSelectValue)?.label : rolePlaceholder}</span>
                    <svg className="contact-form-role-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="m6 9 6 6 6-6" /></svg>
                  </button>
                  {roleDropdownOpen && (
                    <ul
                      role="listbox"
                      className="contact-form-role-dropdown"
                      aria-label="Role"
                    >
                      {ROLE_OPTIONS.map((opt) => (
                        <li
                          key={opt.value}
                          role="option"
                          aria-selected={roleSelectValue === opt.value}
                          onClick={() => {
                            setRoleSelectValue(opt.value);
                            setRoleDropdownOpen(false);
                          }}
                          className="contact-form-role-option"
                        >
                          {opt.label}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <textarea
                  name="message"
                  placeholder="Message"
                  required
                  aria-label="Message"
                ></textarea>
                <button type="submit" className="btn btn-primary">
                  Request Access
                </button>
              </form>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="container footer-content">
          <div className="footer-section">
            <h4>Bionocular.ai</h4>
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
