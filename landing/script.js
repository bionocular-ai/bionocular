'use strict';
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const txt = (parent, x, y, s, attrs = {}) => { const t = el('text', { x, y, ...attrs }, parent); t.textContent = s; return t; };
const still = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── Header: the link for the section in view takes the accent colour ──
(() => {
  const hdr = document.getElementById('hdr'), nav = document.getElementById('nav');
  const links = [...nav.querySelectorAll('a')], btn = document.getElementById('menuBtn'), sheet = document.getElementById('sheet');
  // The footer is too short to reach the middle of the viewport, so the page bottom counts as Contact.
  const atBottom = () => innerHeight + scrollY >= document.documentElement.scrollHeight - 2;
  addEventListener('scroll', () => atBottom() && setActive('contact'), { passive: true });
  const setActive = id => links.forEach(a => a.getAttribute('href') === '#' + id ? a.setAttribute('aria-current', 'true') : a.removeAttribute('aria-current'));
  const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && setActive(atBottom() ? 'contact' : e.target.id)), { rootMargin: '-45% 0px -50% 0px' });
  ['hero', 'product', 'survival', 'about', 'contact'].forEach(id => io.observe(document.getElementById(id)));
  const toggle = open => { hdr.toggleAttribute('data-open', open); btn.setAttribute('aria-expanded', open); };
  btn.addEventListener('click', () => toggle(!hdr.hasAttribute('data-open')));
  sheet.querySelectorAll('a').forEach(a => a.addEventListener('click', () => toggle(false)));
  addEventListener('keydown', e => e.key === 'Escape' && toggle(false));
})();

// ── Footer year ──
document.getElementById('copyright').textContent = `© ${new Date().getFullYear()} Bionocular.ai. All rights reserved.`;
