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
  // The band only reports crossings, so remember which section is in it and re-apply on every scroll:
  // that clears Contact again when the reader scrolls back up from the bottom.
  const atBottom = () => innerHeight + scrollY >= document.documentElement.scrollHeight - 2;
  let inBand = 'hero';
  const setActive = id => links.forEach(a => a.getAttribute('href') === '#' + id ? a.setAttribute('aria-current', 'true') : a.removeAttribute('aria-current'));
  const sync = () => setActive(atBottom() ? 'contact' : inBand);
  addEventListener('scroll', sync, { passive: true });
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { inBand = e.target.id; sync(); } }), { rootMargin: '-45% 0px -50% 0px' });
  ['hero', 'product', 'survival', 'about', 'contact'].forEach(id => io.observe(document.getElementById(id)));
  const toggle = open => { hdr.toggleAttribute('data-open', open); btn.setAttribute('aria-expanded', open); };
  btn.addEventListener('click', () => toggle(!hdr.hasAttribute('data-open')));
  sheet.querySelectorAll('a').forEach(a => a.addEventListener('click', () => toggle(false)));
  addEventListener('keydown', e => {
    if (e.key !== 'Escape' || !hdr.hasAttribute('data-open')) return;
    const inSheet = sheet.contains(document.activeElement);
    toggle(false);
    if (inSheet) btn.focus(); // the sheet hides, so focus would otherwise fall to <body>
  });
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

// ── Product: shared data, drawn as an SVG diagram (≥768px) or a stacked list (<768px) ──
const SOURCES = ['Clinical Trials', 'Conference Abstracts', 'Publications', 'Press Releases', 'Live News', 'Standard of Care'];
const DIMS = ['Indication & Subtype', 'Clinical Setting', 'Disease Stage', 'Line of Therapy', 'Biomarker', 'Modality', 'Target', 'Efficacy Endpoints', 'Safety Endpoints'];
const MODS = [['CORE', 'Clinical Landscape and Trial Data'], ['OUTCOME INTELLIGENCE HUB', 'Efficacy, Safety and Efficacy vs Safety'], ['SURVIVAL INTELLIGENCE', 'KM-Curve Digitized Twin']];
(() => {
  const s = document.getElementById('flowSvg');
  const line = (d, color = 'rgba(122,193,162,.8)', delay = 0) => {
    el('path', { d, fill: 'none', stroke: 'rgba(255,255,255,.14)', 'stroke-width': 1.5 }, s);
    const f = el('path', { d, class: 'flow', stroke: color, 'stroke-width': 1.6, 'stroke-dasharray': '4 14' }, s); f.style.animationDelay = delay + 's';
  };
  const box = (x, y, w, h, fill, stroke, r = 12, sw = 1) => el('rect', { x, y, width: w, height: h, rx: r, fill, stroke, 'stroke-width': sw }, s);
  const CX = 400, CY = 294, R = 110;
  box(10, 20, 224, 546, 'rgba(201,162,39,.06)', 'rgba(201,162,39,.5)', 18, 1.3);
  el('circle', { cx: 32, cy: 45, r: 4.5, fill: '#C9A227' }, s);
  txt(s, 44, 51, 'Raw Scientific Data', { fill: '#fff', 'font-size': 17, 'font-weight': 600, 'font-family': 'Fraunces', 'letter-spacing': '-.01em' });
  SOURCES.forEach((n, i) => {
    const y = 70 + i * 84, cy = y + 27, ty = 254 + i * 16, ex = CX - Math.sqrt(R * R - (ty - CY) ** 2);
    line(`M220,${cy} C282,${cy} 262,${ty} ${ex},${ty}`, 'rgba(201,162,39,.8)', -i * .17);
    box(24, y, 196, 54, 'rgba(201,162,39,.12)', 'rgba(201,162,39,.48)');
    txt(s, 122, cy + 5, n, { 'text-anchor': 'middle', fill: '#F3EBD3', 'font-size': 14 });
  });
  [0, 2, 4, 5].forEach((i, k) => {
    const y = 70 + i * 84 + 27, ty = 254 + i * 16, ex = CX - Math.sqrt(R * R - (ty - CY) ** 2);
    const c = el('circle', { r: 3.2, fill: '#F1D77A' }, s);
    if (!still) el('animateMotion', { dur: '2.8s', repeatCount: 'indefinite', begin: (k * .7) + 's', path: `M220,${y} C282,${y} 262,${ty} ${ex},${ty}` }, c); else c.remove();
  });
  [['RAW', CX - R * .55, 'rgba(243,235,211,.7)'], ['STRUCTURED', CX + R * .55, 'rgba(218,240,230,.7)']].forEach(([t, x, f]) => txt(s, x, CY - R - 10, t, { 'text-anchor': 'middle', fill: f, 'font-size': 10.5, 'font-family': 'IBM Plex Mono', 'letter-spacing': '.14em' }));
  txt(s, CX, CY + 7, 'BIONOCULAR', { 'text-anchor': 'middle', 'font-size': 17, 'letter-spacing': '.16em', 'font-family': 'Plus Jakarta Sans', fill: '#fff', 'paint-order': 'stroke', stroke: 'rgba(6,26,36,.55)', 'stroke-width': 6, 'stroke-linejoin': 'round' });
  const pillY = i => 46 + i * 58, pillC = i => pillY(i) + 20;
  box(532, 24, 224, 542, 'rgba(122,193,162,.05)', 'rgba(122,193,162,.38)', 18, 1.3);
  line(`M${CX + R},${CY} H520`, 'rgba(122,193,162,.85)');
  el('path', { d: `M520,${pillC(0)} V${pillC(8)}`, stroke: 'rgba(255,255,255,.2)', 'stroke-width': 1.5, fill: 'none' }, s);
  el('path', { d: `M772,${pillC(0)} V${pillC(8)}`, stroke: 'rgba(255,255,255,.2)', 'stroke-width': 1.5, fill: 'none' }, s);
  DIMS.forEach((n, i) => {
    line(`M520,${pillC(i)} H544`, undefined, -i * .1); line(`M744,${pillC(i)} H772`, undefined, -i * .1);
    box(544, pillY(i), 200, 40, 'rgba(10,40,54,.5)', 'rgba(122,193,162,.42)', 10);
    txt(s, 644, pillC(i) + 5, n, { 'text-anchor': 'middle', fill: '#E4F3EC', 'font-size': 14 });
  });
  box(800, 20, 390, 400, 'rgba(122,193,162,.07)', 'rgba(122,193,162,.7)', 18, 1.3);
  txt(s, 822, 56, 'Visual Platform', { fill: '#7AC1A2', 'font-size': 21, 'font-weight': 600, 'font-family': 'Fraunces', 'letter-spacing': '-.01em' });
  txt(s, 990, 55, 'Cancer Specific', { fill: 'rgba(218,240,230,.7)', 'font-size': 12, 'font-family': 'IBM Plex Mono' });
  MODS.forEach(([h, d], i) => {
    const y = 76 + i * 110;
    line(`M772,${y + 46} H822`, 'rgba(122,193,162,.9)', -i * .2);
    box(822, y, 346, 92, 'rgba(10,40,54,.6)', 'rgba(122,193,162,.55)');
    txt(s, 844, y + 40, h, { fill: '#fff', 'font-size': 16, 'font-weight': 700, 'letter-spacing': '.04em' });
    txt(s, 844, y + 66, d, { fill: 'rgba(218,240,230,.8)', 'font-size': 14 });
  });
  line(`M772,${pillC(8)} V513 H822`, 'rgba(122,193,162,.9)');
  box(822, 470, 346, 86, 'rgba(201,162,39,.1)', '#C9A227', 12, 1.4);
  txt(s, 844, 506, 'bionocular AI Agent', { fill: '#fff', 'font-size': 17, 'font-weight': 700, 'font-family': 'Plus Jakarta Sans' });
  txt(s, 844, 532, 'Plain-Language Answers from the Same Data', { fill: 'rgba(243,235,211,.85)', 'font-size': 13.5 });
  el('path', { d: 'M1080,470 V420', class: 'dotted' }, s); el('path', { d: 'M1110,420 V470', class: 'dotted' }, s);
  txt(s, 1122, 450, 'Opens In', { fill: 'rgba(243,235,211,.75)', 'font-size': 11, 'font-family': 'IBM Plex Mono' });

  // Mobile stack from the same arrays
  const fill = (id, items, cls) => document.getElementById(id).innerHTML = items.map(n => `<div class="pillbox ${cls}">${n.replace('&', '&amp;')}</div>`).join('');
  fill('mSources', SOURCES, 'raw'); fill('mDims', DIMS, 'dim');
  document.getElementById('mMods').innerHTML = MODS.map(([h, d]) => `<div class="mod"><b>${h}</b><span>${d}</span></div>`).join('');
})();

// ── Core canvas: noise to structure. Runs only while visible; one still frame under reduced motion ──
function coreCanvas(cv) {
  const ctx = cv.getContext('2d');
  const SEA = [140, 222, 186], MINT = [226, 248, 238], RAW = [214, 180, 96];
  const mix = (a, b, t) => a.map((v, k) => v + (b[k] - v) * Math.max(0, Math.min(1, t)));
  const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
  const sstep = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  const hash = i => { const v = Math.sin(i * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
  const ROWS = 9, PER = 64, pts = [];
  for (let k = 0; k < ROWS; k++) for (let i = 0; i < PER; i++) pts.push({ k, ph: i / PER, ro: hash(k * PER + i) * 2 - 1, ro2: hash(k * PER + i + 999) });
  let size = 0;
  const resize = () => { const d = devicePixelRatio || 1; size = cv.clientWidth * d; cv.width = cv.height = size; };
  // Resizing resets the canvas; under reduced motion there is no loop to repaint it, so redraw the still frame.
  addEventListener('resize', () => { resize(); if (still) frame(4000); }); resize();
  const frame = t => {
    ctx.clearRect(0, 0, size, size); ctx.globalCompositeOperation = 'lighter';
    const c = size / 2, R = size * (110 / 340), d = devicePixelRatio || 1;
    for (let gy = -4; gy <= 4; gy++) { ctx.fillStyle = rgba(MINT, .25 + .2 * Math.sin(t * .003 + gy)); ctx.fillRect(c - d * .5, c + gy * R * .2 - d, d, d * 2); }
    for (const q of pts) {
      const u = (q.ph + t * .00004) % 1, x = -R + u * 2 * R, yr = (q.k - (ROWS - 1) / 2) / ((ROWS - 1) / 2) * R * .72;
      const sN = sstep(-.18 * R, .22 * R, x), yc = yr + q.ro * R * .85 + .14 * R * Math.sin(x / R * 6 + t * .0014 + q.ro * 5);
      const y = yc + (yr - yc) * sN, m = 1 - sstep(.82, 1, Math.hypot(x, y) / R);
      if (m <= 0) continue;
      const col = mix(RAW, mix(SEA, MINT, .3), sN), r = (1 + sN * .8) * d;
      ctx.fillStyle = rgba(col, m * (.4 + sN * .6) * (sN < .5 ? .5 + q.ro2 * .5 : 1)); ctx.fillRect(c + x - r / 2, c + y - r / 2, r, r);
    }
  };
  if (still) { frame(4000); return; }
  let on = false, raf = 0;
  const loop = t => { frame(t); raf = on ? requestAnimationFrame(loop) : 0; };
  new IntersectionObserver(([e]) => { on = e.isIntersecting && cv.clientWidth > 0; if (on && !raf) raf = requestAnimationFrame(loop); }).observe(cv);
}
coreCanvas(document.getElementById('core'));
coreCanvas(document.querySelector('#coreM canvas'));

// ── Survival: real digitized twins (km_curves, NCT01844505, NEJM 2019, ITT PFS) layered by step ──
(() => {
  document.getElementById('kmStored').textContent = `${KM.stored} twin points stored`;
  const s = document.getElementById('km'), chart = document.getElementById('chart');
  const wide = matchMedia('(min-width: 1024px)');
  const x0 = 52, x1 = 620, y0 = 14; let y1 = 322;
  const X = m => x0 + m / 60 * (x1 - x0), Y = p => y1 - p / 100 * (y1 - y0);
  const step = pts => pts.reduce((d, [t, p], i) => i ? d + ` H${X(t).toFixed(1)} V${Y(p).toFixed(1)}` : `M${X(t)},${Y(p)}`, '') + ` H${X(Math.min(60, pts.at(-1)[0] + 1.5))}`;
  const ARMS = [['nivolumab_plus_ipilimumab', '#1B4F65', 11.5], ['nivolumab', '#2F8A66', 6.9], ['ipilimumab', '#C9A227', 2.9]];
  // When pinned, the card fills the viewport below the header, so the plot is drawn to whatever height the svg
  // gets there (the viewBox matches its box). Elsewhere it keeps the default 640x380 proportions.
  const draw = () => {
    const r = s.getBoundingClientRect();
    const H = wide.matches && !still && r.width ? Math.max(380, Math.round(640 * r.height / r.width)) : 380;
    s.replaceChildren(); s.setAttribute('viewBox', `0 0 640 ${H}`); y1 = H - 58;
    const g = id => el('g', { id, class: 'layer' }, s);
    // Axes (step 2 snaps them into place)
    const ax = g('Lax');
    [0, 12, 24, 36, 48, 60].forEach(m => { el('line', { x1: X(m), x2: X(m), y1: y0, y2: y1, stroke: '#EEF4F1' }, ax); txt(ax, X(m), y1 + 20, m, { 'text-anchor': 'middle' }); });
    [0, 25, 50, 75, 100].forEach(p => { el('line', { x1: x0, x2: x1, y1: Y(p), y2: Y(p), stroke: '#EEF4F1' }, ax); txt(ax, x0 - 10, Y(p) + 4, p + '%', { 'text-anchor': 'end' }); });
    el('path', { d: `M${x0},${y0} V${y1} H${x1}`, fill: 'none', stroke: '#C8E0D8', 'stroke-width': 1.2 }, ax);
    txt(ax, (x0 + x1) / 2, y1 + 44, 'Months', { 'text-anchor': 'middle', style: 'font-family:Public Sans;font-size:12px' });
    // Other trials' twins (step 5)
    const bg = g('Lbg');
    KM.bg.forEach(b => el('path', { d: step(b.pts), fill: 'none', stroke: '#9DB8AD', 'stroke-width': 1.3, opacity: .55 }, bg));
    // The source figure as ingested: grey, slightly skewed and soft (steps 1-2)
    const src = g('Lsrc'); src.classList.add('on'); src.style.transformOrigin = `${x0}px ${y1}px`;
    el('rect', { x: x0 - 30, y: y0 - 34, width: x1 - x0 + 54, height: y1 - y0 + 66, rx: 6, fill: '#FBFCFB', stroke: '#D3DCD9', class: 'cap' }, src);
    txt(src, x0 - 18, y0 - 16, 'SOURCE FIGURE · PDF', { class: 'cap', style: 'font-size:13px;letter-spacing:.08em;fill:#7A8B86' });
    el('path', { d: `M${x0},${y0} V${y1} H${x1}`, fill: 'none', stroke: '#B9C4C0', 'stroke-width': 1 }, src);
    [25, 50, 75].forEach(p => el('line', { x1: x0 - 4, x2: x0, y1: Y(p), y2: Y(p), stroke: '#B9C4C0' }, src));
    [12, 24, 36, 48].forEach(m => el('line', { x1: X(m), x2: X(m), y1: y1, y2: y1 + 4, stroke: '#B9C4C0' }, src));
    ARMS.forEach(([k]) => el('path', { d: step(KM.main[k]), fill: 'none', stroke: '#8C9A96', 'stroke-width': 1.6 }, src));
    // Twins (step 3)
    const tw = g('Ltwin'); tw.classList.add('twin');
    ARMS.forEach(([k, c]) => { const p = el('path', { d: step(KM.main[k]), fill: 'none', stroke: c, 'stroke-width': 2.6, 'stroke-linejoin': 'round' }, tw); p.style.setProperty('--len', p.getTotalLength()); });
    // Medians (step 6): published values labelled, marker at the twin's 50% crossing
    const md = g('Lmed');
    el('line', { x1: x0, x2: x1, y1: Y(50), y2: Y(50), stroke: '#7A8F88', 'stroke-dasharray': '3 5' }, md);
    ARMS.forEach(([k, c, pub], i) => {
      const pts = KM.main[k], hit = pts.find(([, p]) => p <= 50), mx = X(hit[0]);
      el('line', { x1: mx, x2: mx, y1: Y(50), y2: y1, stroke: c, 'stroke-dasharray': '2 4', opacity: .7 }, md);
      el('circle', { cx: mx, cy: Y(50), r: 4.5, fill: '#fff', stroke: c, 'stroke-width': 2.2 }, md);
    });
    // Medians sit too close together to label at their markers, so they read as one line at the end of the 50% rule.
    const lab = txt(md, x1 - 2, Y(50) - 9, 'Median PFS  ', { 'text-anchor': 'end', style: 'fill:#4A6B77' });
    ARMS.forEach(([, c, pub], i) => { const t = el('tspan', { style: `fill:${c};font-weight:500` }, lab); t.textContent = pub + (i < 2 ? ' vs ' : ' mo'); });
    if (cur) show(cur);
  };
  const L = id => document.getElementById(id), meta = [...document.querySelectorAll('#meta span')];
  const show = n => {
    L('Lsrc').classList.toggle('norm', n >= 2); L('Lsrc').classList.toggle('dim', n >= 3);
    L('Lax').classList.toggle('on', n >= 2); L('Ltwin').classList.toggle('on', n >= 3); L('Lbg').classList.toggle('on', n >= 5); L('Lmed').classList.toggle('on', n >= 6);
    meta.forEach(m => m.classList.toggle('on', n >= +m.dataset.from));
  };
  const scroller = document.getElementById('svScroll'), stage = scroller.firstElementChild, bar = document.getElementById('svBar');
  const pills = [...document.querySelectorAll('#steps .pill')], N = pills.length, hdrEl = document.getElementById('hdr');
  let cur = 0, raf = 0, pinned = false;
  const setStep = n => { if (n === cur) return; cur = n; pills.forEach(p => +p.dataset.step === n ? p.setAttribute('aria-current', 'step') : p.removeAttribute('aria-current')); show(n); };
  // Scroll position inside the pinned run maps straight to a step, so no step can be skipped and the chart is always in view.
  const range = () => [scroller.getBoundingClientRect().top + scrollY - hdrEl.offsetHeight, Math.max(1, scroller.offsetHeight - stage.offsetHeight)];
  const pick = () => {
    raf = 0;
    const [top, len] = range(), p = Math.min(1, Math.max(0, (scrollY - top) / len));
    bar.style.transform = `scaleX(${p})`;
    setStep(Math.min(N, Math.floor(p * N) + 1));
  };
  const onScroll = () => { if (!raf) raf = requestAnimationFrame(pick); };
  pills.forEach((p, i) => p.addEventListener('click', () => {
    if (!pinned) return;
    const [top, len] = range();
    scrollTo({ top: top + (i + .5) / N * len, behavior: still ? 'auto' : 'smooth' });
  }));
  const mode = () => {
    removeEventListener('scroll', onScroll); cur = 0;
    pinned = wide.matches && !still;
    scroller.dataset.mode = pinned ? 'pinned' : 'static';
    draw();
    if (pinned) { addEventListener('scroll', onScroll, { passive: true }); pick(); }
    else { pills.forEach(p => p.removeAttribute('aria-current')); cur = N; show(N); }
  };
  wide.addEventListener('change', mode);
  addEventListener('resize', () => { draw(); if (pinned) pick(); });
  mode();
})();

// About: the comparison-row sparkline is the same three CheckMate 067 twins, at icon scale.
(() => {
  const sv = document.getElementById('cmpSpark'); if (!sv) return;
  const X = m => 2 + m / 60 * 146, Y = p => 2 + (100 - p) / 100 * 32;
  [['nivolumab_plus_ipilimumab', '#BFE6D4'], ['nivolumab', '#7AC1A2'], ['ipilimumab', '#D9BE5C']].forEach(([k, c]) => {
    const d = KM.main[k].reduce((d, [t, p], i) => i ? d + ` H${X(t).toFixed(1)} V${Y(p).toFixed(1)}` : `M${X(t)},${Y(p)}`, '') + ` H${X(60)}`;
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', d); p.setAttribute('fill', 'none'); p.setAttribute('stroke', c); p.setAttribute('stroke-width', '1.6'); sv.append(p);
  });
})();

// ── Footer year ──
document.getElementById('copyright').textContent = `© ${new Date().getFullYear()} Bionocular.ai. All rights reserved.`;
