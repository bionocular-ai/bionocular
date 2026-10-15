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

// ── Headline rotator ──
(() => {
  if (still) return;
  const P = [...document.querySelectorAll('.rotator > .h1')];
  let i = 0;
  setInterval(() => { P[i].removeAttribute('data-on'); i = (i + 1) % P.length; P[i].setAttribute('data-on', ''); }, 6000);
})();

// ── Hero story: beats advance when the active segment finishes filling, so pause and jump are exact ──
(() => {
  const story = document.getElementById('story'), segs = [...story.querySelectorAll('.seg')], pause = document.getElementById('pause');
  const HOLD = [2000, 2000, 3600, 3600];
  let beat = 0, userPaused = false;
  const go = n => {
    beat = n; story.dataset.beat = n;
    segs.forEach((s, i) => { s.toggleAttribute('data-done', i < n); s.removeAttribute('data-active'); });
    void segs[n].offsetWidth; // restart the fill animation
    segs[n].style.setProperty('--hold', HOLD[n] + 'ms'); segs[n].setAttribute('data-active', '');
  };
  if (still) { story.dataset.beat = 3; segs.forEach(s => s.setAttribute('data-done', '')); return; }
  segs.forEach((s, i) => { s.firstElementChild.addEventListener('animationend', () => i === beat && go((beat + 1) % 4)); s.addEventListener('click', () => go(i)); });
  const setPaused = () => story.toggleAttribute('data-paused', userPaused || !visible);
  let visible = true;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; setPaused(); }, { threshold: .25 }).observe(story);
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; setPaused(); });
  pause.addEventListener('click', () => { userPaused = !userPaused; pause.setAttribute('aria-pressed', userPaused); pause.querySelector('span').textContent = userPaused ? 'Play' : 'Pause';
    pause.querySelector('svg').innerHTML = userPaused ? '<path d="M3 1.5v9l7.5-4.5z"/>' : '<rect x="2" y="1.5" width="2.6" height="9" rx="1"/><rect x="7.4" y="1.5" width="2.6" height="9" rx="1"/>'; setPaused(); });
  go(0);
})();

// ── Footer year ──
document.getElementById('copyright').textContent = `© ${new Date().getFullYear()} Bionocular.ai. All rights reserved.`;
