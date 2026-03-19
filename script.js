// Headlines rotation
const HERO_PHRASES = [
  {
    strong: 'Next-gen AI and Machine learning',
    rest: ' providing analytics and insights (with Human verification) in the Oncology landscape.',
  },
  {
    strong: 'Cutting the noise',
    rest: ' and only focusing on the key elements.',
  },
];

let headlineIndex = 0;
let activeNav = '';

// Initialize headline rotation
function initHeadlineRotation() {
  const phraseEl = document.getElementById('heroRotatorPhrase');
  if (!phraseEl) return;

  function updatePhrase() {
    const phrase = HERO_PHRASES[headlineIndex];
    phraseEl.style.opacity = '0';
    phraseEl.style.transform = 'translateY(-14px)';
    
    setTimeout(() => {
      phraseEl.innerHTML = `
        <span class="font-bold" style="font-weight: 700">${phrase.strong}</span>
        <span class="font-light" style="font-weight: 300; opacity: 0.85">${phrase.rest}</span>
      `;
      // Start from below before animating in
      phraseEl.style.transform = 'translateY(14px)';
      
      requestAnimationFrame(() => {
        // Must delay slightly for browser to register the translateY(14px)
        setTimeout(() => {
          phraseEl.style.opacity = '1';
          phraseEl.style.transform = 'translateY(0)';
        }, 50);
      });
    }, 400); // Wait for fade out
  }

  updatePhrase();
  setInterval(() => {
    headlineIndex = (headlineIndex + 1) % HERO_PHRASES.length;
    updatePhrase();
  }, 5000); // 5 sec per phrase
}

// Smooth scrolling and active nav
function initSmoothScroll() {
  const EXTRA_GAP_PX = 10;
  const navIndicator = document.getElementById('navIndicator');
  const navLinksWrap = document.getElementById('navLinksWrap');

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

  function updateIndicator(activeLink) {
    if (!navIndicator || !navLinksWrap || !activeLink) {
      if (navIndicator) navIndicator.style.opacity = '0';
      return;
    }
    const wrapRect = navLinksWrap.getBoundingClientRect();
    const linkRect = activeLink.getBoundingClientRect();
    navIndicator.style.left = `${linkRect.left - wrapRect.left}px`;
    navIndicator.style.width = `${linkRect.width}px`;
    navIndicator.style.opacity = '1';
  }

  function setActiveNav(hash) {
    activeNav = hash;
    let foundLink = null;
    document.querySelectorAll('.nav-links-wrap a').forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href') === hash) {
        link.classList.add('active');
        foundLink = link;
      }
    });
    updateIndicator(foundLink);
  }

  function handleAnchorClick(e) {
    const anchor = e.currentTarget;
    const href = anchor.getAttribute('href');
    if (!href || href === '#') return;
    
    // Close mobile menu if open
    const nav = document.getElementById('siteNav');
    const backdrop = document.getElementById('mobileMenuBackdrop');
    const hamburger = document.querySelector('.hamburger');
    
    if (nav.classList.contains('mobile-open')) {
      nav.classList.remove('mobile-open');
      backdrop.style.display = 'none';
      hamburger.classList.remove('open');
      document.body.style.overflow = '';
    }
    
    if (href === '#hero') {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      setActiveNav('#hero');
      return;
    }
    const targetEl = findAnchorTarget(href);
    if (!targetEl) return;
    e.preventDefault();
    scrollToHash(href);
    setActiveNav(href);
  }

  const anchors = document.querySelectorAll('.nav-links-wrap a[href^="#"]');
  anchors.forEach((anchor) => {
    anchor.addEventListener('click', handleAnchorClick);
  });

  // IntersectionObserver for active nav
  const sections = document.querySelectorAll('main section[id], #hero, #contact');
  const sectionObserver = new IntersectionObserver(
    (entries) => {
      let intersecting = [];
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          intersecting.push(entry);
        }
      });
      // Sort by topmost if multiple intersecting, or pick the single one
      if (intersecting.length > 0) {
        const id = '#' + intersecting[0].target.id;
        setActiveNav(id);
      }
    },
    { rootMargin: '-40% 0px -50% 0px', threshold: 0.05 }
  );
  sections.forEach((sec) => sectionObserver.observe(sec));

  // Handle initial hash
  const initialHash = window.location.hash;
  if (initialHash) {
    requestAnimationFrame(() => {
      scrollToHash(initialHash);
      setActiveNav(initialHash);
    });
  } else {
      setActiveNav('#hero');
  }

  window.addEventListener('hashchange', () => {
    if (window.location.hash) {
      scrollToHash(window.location.hash);
      setActiveNav(window.location.hash);
    }
  });
  
  window.addEventListener('resize', () => {
    const active = document.querySelector('.nav-links-wrap a.active');
    updateIndicator(active);
  });
}

// Mobile Menu
function initMobileMenu() {
  const toggle = document.getElementById('mobileMenuToggle');
  const nav = document.getElementById('siteNav');
  const backdrop = document.getElementById('mobileMenuBackdrop');
  const hamburger = document.querySelector('.hamburger');

  function openMenu() {
    nav.classList.add('mobile-open');
    backdrop.style.display = 'block';
    hamburger.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeMenu() {
    nav.classList.remove('mobile-open');
    backdrop.style.display = 'none';
    hamburger.classList.remove('open');
    document.body.style.overflow = '';
  }

  toggle.addEventListener('click', () => {
    if (nav.classList.contains('mobile-open')) closeMenu();
    else openMenu();
  });

  backdrop.addEventListener('click', closeMenu);
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
  initMobileMenu();
  initSmoothScroll();
  setCopyright();
});
