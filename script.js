// Headlines rotation
const headlines = [
  'Next-gen AI and Machine learning providing analytics and insights (with Human verification) in the Oncology landscape',
  'Cutting the noise and only focusing on the key elements'
];

let headlineIndex = 0;
let activeNav = '';

// Initialize headline rotation
function initHeadlineRotation() {
  const headlineEl = document.getElementById('heroHeadline');
  if (!headlineEl) return;

  headlineEl.textContent = headlines[headlineIndex];
  headlineEl.style.opacity = '1';

  setInterval(() => {
    headlineEl.style.opacity = '0';
    setTimeout(() => {
      headlineIndex = (headlineIndex + 1) % headlines.length;
      headlineEl.textContent = headlines[headlineIndex];
      headlineEl.style.opacity = '1';
    }, 500);
  }, 9000);
}

// Canvas particles animation
function initParticles() {
  const canvas = document.getElementById('dataCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let particles = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function spawnParticles(count) {
    particles = Array.from({ length: count }, () => ({
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
  spawnParticles(Math.min(250, Math.floor((canvas.width * canvas.height) / 3000)));

  function tick() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const p of particles) {
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

  window.addEventListener('resize', () => {
    resize();
    spawnParticles(Math.min(250, Math.floor((canvas.width * canvas.height) / 3000)));
  });
}

// Smooth scrolling and active nav
function initSmoothScroll() {
  const EXTRA_GAP_PX = 10;

  function findAnchorTarget(hash) {
    const el = document.querySelector(hash);
    if (!el) return null;
    return el.querySelector('h2, h1') || el;
  }

  function scrollToHash(hash) {
    const targetEl = findAnchorTarget(hash);
    if (!targetEl) return;
    const header = document.querySelector('.site-header');
    const headerHeight = header ? header.offsetHeight : 0;
    const top = targetEl.getBoundingClientRect().top + window.pageYOffset - headerHeight - EXTRA_GAP_PX;
    window.scrollTo({ top, behavior: 'smooth' });
  }

  function setActiveNav(hash) {
    activeNav = hash;
    document.querySelectorAll('.nav-link').forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('data-section') === hash.slice(1)) {
        link.classList.add('active');
      }
    });
  }

  function handleAnchorClick(e) {
    const anchor = e.currentTarget;
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
    const headerHeight = header ? header.offsetHeight : 0;
    const top = targetEl.getBoundingClientRect().top + window.pageYOffset - headerHeight - EXTRA_GAP_PX;
    window.scrollTo({ top, behavior: 'smooth' });
    setActiveNav(href);
  }

  const anchors = document.querySelectorAll('a[href^="#"]');
  anchors.forEach((anchor) => {
    anchor.addEventListener('click', handleAnchorClick);
  });

  // IntersectionObserver for active nav
  const sections = document.querySelectorAll('main section[id]');
  const sectionObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = '#' + entry.target.id;
          setActiveNav(id);
        }
      });
    },
    { rootMargin: '-40% 0px -50% 0px', threshold: 0.01 }
  );
  sections.forEach((sec) => sectionObserver.observe(sec));

  // Handle initial hash
  const initialHash = window.location.hash;
  if (initialHash) {
    requestAnimationFrame(() => {
      scrollToHash(initialHash);
      setActiveNav(initialHash);
    });
  }

  window.addEventListener('hashchange', () => {
    if (window.location.hash) {
      scrollToHash(window.location.hash);
      setActiveNav(window.location.hash);
    }
  });
}

// Contact form handler
function initContactForm() {
  const form = document.getElementById('contactForm');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    alert('Thank you for your message! We will get back to you soon.');
    form.reset();
  });
}

// Set copyright year
function setCopyright() {
  const copyrightEl = document.getElementById('copyright');
  if (copyrightEl) {
    const currentYear = new Date().getFullYear();
    copyrightEl.textContent = `© ${currentYear} Bionocular.ai. All rights reserved.`;
  }
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  initHeadlineRotation();
  initParticles();
  initSmoothScroll();
  initContactForm();
  setCopyright();
});

