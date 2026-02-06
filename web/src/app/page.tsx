'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';

const headlines = [
  'Next-gen AI and Machine learning providing analytics and insights (with Human verification) in the Oncology landscape',
  'Cutting the noise and only focusing on the key elements'
];

export default function Home() {
  const { data: session } = useSession();
  const [headlineIndex, setHeadlineIndex] = useState(0);
  const [activeNav, setActiveNav] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const headlineRef = useRef<HTMLHeadingElement>(null);

  interface Particle {
    x: number;
    y: number;
    z: number;
    vx: number;
    vy: number;
    r: number;
    a: number;
  }
  const particlesRef = useRef<Particle[]>([]);

  // Rotating headlines
  useEffect(() => {
    const interval = setInterval(() => {
      setHeadlineIndex((prev) => (prev + 1) % headlines.length);
    }, 9000);
    return () => clearInterval(interval);
  }, []);

  // Canvas particles
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    function resize() {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }

    function spawnParticles(count: number) {
      if (!canvas) return;
      particlesRef.current = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        z: Math.random() * 1 + 0.2,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 1.6 + 0.3,
        a: Math.random() * 0.4 + 0.2,
      }));
    }

    resize();
    if (canvas) {
      spawnParticles(Math.min(250, Math.floor((canvas.width * canvas.height) / 3000)));
    }

    function tick() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const p of particlesRef.current) {
        p.x += p.vx * p.z;
        p.y += p.vy * p.z;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#0ea5e9';
        const r = parseInt(accent.slice(1, 3), 16);
        const g = parseInt(accent.slice(3, 5), 16);
        const b = parseInt(accent.slice(5, 7), 16);
        ctx.fillStyle = `rgba(${r},${g},${b},${p.a})`;
        ctx.fill();
      }
      requestAnimationFrame(tick);
    }

    tick();

    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

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

    // Scroll listener to detect when at the top
    const handleScroll = () => {
      if (window.scrollY < 200) {
        setActiveNav('#hero');
      }
    };

    // IntersectionObserver for active nav
    const sections = document.querySelectorAll('main section[id], section.hero[id]');
    const sectionObserver = new IntersectionObserver(
      (entries) => {
        // Only update if we're not near the top of the page
        if (window.scrollY < 200) {
          setActiveNav('#hero');
          return;
        }

        // Find the entry with the highest intersectionRatio
        let mostVisible = entries[0];
        entries.forEach((entry) => {
          if (entry.intersectionRatio > mostVisible.intersectionRatio) {
            mostVisible = entry;
          }
        });

        if (mostVisible && mostVisible.isIntersecting && mostVisible.intersectionRatio > 0.1) {
          const id = '#' + mostVisible.target.id;
          setActiveNav(id);
        }
      },
      { 
        rootMargin: '-80px 0px -50% 0px',
        threshold: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
      }
    );
    sections.forEach((sec) => sectionObserver.observe(sec));

    // Handle initial hash - use requestAnimationFrame to avoid setState in effect
    const initialHash = window.location.hash;
    if (initialHash) {
      requestAnimationFrame(() => {
        scrollToHash(initialHash);
        setActiveNav(initialHash);
      });
    } else if (window.scrollY < 200) {
      requestAnimationFrame(() => {
        setActiveNav('#hero');
      });
    }

    const handleHashChange = () => {
      if (window.location.hash) {
        scrollToHash(window.location.hash);
        setActiveNav(window.location.hash);
      }
    };

    window.addEventListener('scroll', handleScroll);
    window.addEventListener('hashchange', handleHashChange);

    return () => {
      anchors.forEach((anchor) => {
        anchor.removeEventListener('click', handleAnchorClick);
      });
      sectionObserver.disconnect();
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    alert('Thank you for your message! We will get back to you soon.');
    e.currentTarget.reset();
  };

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
              Solutions
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

      <section className="hero" id="hero">
        <video
          className="hero-media"
          src="/Bionocular.mp4"
          autoPlay
          loop
          muted
          playsInline
          aria-hidden="true"
        />
        <canvas ref={canvasRef} id="dataCanvas" className="hero-canvas" aria-hidden="true" />
        <div className="hero-overlay">
          <h1
            ref={headlineRef}
            id="heroHeadline"
            className="hero-title"
            style={{ opacity: 1 }}
          >
            {headlines[headlineIndex]}
          </h1>
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
                <select name="role" required aria-label="Role">
                  <option value="">Select Your Role</option>
                  <option value="researcher">Researcher</option>
                  <option value="healthcare">Healthcare Professional</option>
                  <option value="patient">Patient/Advocate</option>
                  <option value="other">Other</option>
                </select>
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
