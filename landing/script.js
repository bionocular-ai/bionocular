'use strict';
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const txt = (parent, x, y, s, attrs = {}) => { const t = el('text', { x, y, ...attrs }, parent); t.textContent = s; return t; };
const still = matchMedia('(prefers-reduced-motion: reduce)').matches;

// Step pills (OS and Survival) open into a card, and the last one closes, on an underdamped spring (about 1% overshoot)
// rather than a snap. Each card's size is its own spring: a change mid-flight retargets it from where it is drawn,
// keeping its velocity, so fast scrolling through the steps never jolts. A card that starts opening while another closes
// waits a beat, so the hand-off reads as one motion. morph(apply) runs apply (the aria-current change) and springs every
// card from its old size to its new one; without animate it just applies.
const pillSprings = pills => {
  const Z = .82, W = 2 * Math.PI / .42, springs = pills.map(() => null);
  let raf = 0;
  const unsize = b => { b.style.width = b.style.height = ''; };
  const settle = () => { cancelAnimationFrame(raf); raf = 0; springs.fill(null); pills.forEach(unsize); };
  const tick = now => {
    let busy = false;
    springs.forEach((s, i) => {
      if (!s) return;
      const dt = Math.min(.05, s.last ? (now - s.last) / 1000 : 1 / 60); s.last = now; busy = true;
      if (now < s.start) return;
      for (const k of ['w', 'h']) { s['v' + k] += (W * W * (s['t' + k] - s[k]) - 2 * Z * W * s['v' + k]) * dt; s[k] += s['v' + k] * dt; }
      if (Math.abs(s.tw - s.w) + Math.abs(s.th - s.h) < .4 && Math.abs(s.vw) + Math.abs(s.vh) < 4) { springs[i] = null; unsize(pills[i]); }
      else { pills[i].style.width = `${s.w}px`; pills[i].style.height = `${s.h}px`; }
    });
    raf = busy ? requestAnimationFrame(tick) : 0;
  };
  const morph = (apply, animate) => {
    const from = pills.map(b => b.getBoundingClientRect());
    apply();
    if (!animate) return settle();
    pills.forEach(unsize);
    const to = pills.map(b => b.getBoundingClientRect()), now = performance.now();
    const closing = from.some((f, j) => f.height - to[j].height > 1);
    pills.forEach((b, i) => {
      const f = from[i], t = to[i], s = springs[i];
      if (!s && Math.abs(f.width - t.width) < .5 && Math.abs(f.height - t.height) < .5) return;
      springs[i] = { w: f.width, h: f.height, vw: s ? s.vw : 0, vh: s ? s.vh : 0, tw: t.width, th: t.height, last: 0,
        start: !s && closing && t.height > f.height ? now + 140 : 0 };
      b.style.width = `${f.width}px`; b.style.height = `${f.height}px`;
    });
    if (!raf) raf = requestAnimationFrame(tick);
  };
  return { morph, settle };
};

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
  const sync = () => { setActive(atBottom() ? 'contact' : inBand); hdr.toggleAttribute('data-scrolled', scrollY > 0); };
  addEventListener('scroll', sync, { passive: true });
  // The OS stack and the diagram after the comparison are part of Product too, so they keep the Product link lit.
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { inBand = ['platform', 'how-it-works'].includes(e.target.id) ? 'product' : e.target.id; sync(); } }), { rootMargin: '-45% 0px -50% 0px' });
  ['hero', 'platform', 'product', 'how-it-works', 'survival', 'about', 'contact'].forEach(id => io.observe(document.getElementById(id)));
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
  const R = document.querySelector('.rotator'), P = [...R.children];
  let i = 0;
  setInterval(() => {
    R.setAttribute('data-live', ''); // set on the first swap, so the page loads with the headline already in place
    P[i].removeAttribute('data-on'); P[i].setAttribute('data-out', '');
    i = (i + 1) % P.length;
    P[i].removeAttribute('data-out'); P[i].setAttribute('data-on', '');
  }, 6000);
})();

// ── Hero background: four oncology charts take turns behind the copy (heatmap, efficacy vs safety, KM curves, forest plot) ──
(() => {
  const hero = document.getElementById('hero'), cv = document.getElementById('heroBg'), ctx = cv.getContext('2d'), hdr = document.getElementById('hdr');
  const TEAL = '27,79,101', SEA = '47,138,102', GOLD = '201,162,39';
  const RAMP = [[218,240,230], [122,193,162], [47,138,102], [27,79,101], [14,53,71]];
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = x => 1 - Math.pow(1 - clamp(x), 3);
  const rng = s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const ramp = v => { v = clamp(v) * (RAMP.length - 1); const i = Math.min(RAMP.length - 2, v | 0), f = v - i; return RAMP[i].map((a, k) => a + (RAMP[i + 1][k] - a) * f); };
  // HEAT scales every mark's opacity: a quarter of full strength keeps the charts behind the copy, never competing with it.
  // The heatmap band fills FILL of the hero below the header. Each chart holds for DUR seconds of the clock (which runs at
  // .75x real time), the next crossfades in over FADE and draws itself in over BUILD.
  const HEAT = .25, FILL = .6, DUR = 9, FADE = 1.6, BUILD = 3;
  let W = 0, H = 0, L = 0, R = 0, S = {};
  const hh = () => hdr.offsetHeight;

  // Each copy block as an ellipse (lines capped at 560px, for the gold cell to keep clear of) and as its true box.
  const zones = () => [...hero.querySelectorAll('.hero-copy')].map(e => {
    const r = hero.getBoundingClientRect(), b = [...e.children].map(k => k.getBoundingClientRect());
    const x0 = Math.min(...b.map(q => q.left)), x1 = Math.max(...b.map(q => q.left + Math.min(q.width, 560))), y0 = Math.min(...b.map(q => q.top)), y1 = Math.max(...b.map(q => q.bottom));
    const X1 = Math.max(...b.map(q => q.right));
    return { x: (x0 + x1) / 2 - r.left, y: (y0 + y1) / 2 - r.top, rx: (x1 - x0) * .7, ry: (y1 - y0) * .75, box: [(x0 + X1) / 2 - r.left, (y0 + y1) / 2 - r.top, (X1 - x0) / 2, (y1 - y0) / 2] };
  });
  const inCopy = (x, y, pad) => S.zs.some(({ box: [cx, cy, w2, h2] }) => Math.abs(x - cx) < w2 + pad && Math.abs(y - cy) < h2 + pad);

  function size() {
    const dpr = Math.min(2, devicePixelRatio || 1), r = hero.getBoundingClientRect();
    W = r.width; H = r.height; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // The frame sits on the page's column edges (.wrap in styles.css): 16px in on phones, 40px on tablets, 96px from 1200px,
    // and at most 1680px wide. Its two edges carry on a little past the hero (main::before in styles.css).
    const m = Math.round(W < 768 ? 16 : W < 1200 ? 40 : Math.max(96, (W - 1680) / 2));
    L = m; R = W - m;
    document.documentElement.style.setProperty('--grid-l', `${L}px`); document.documentElement.style.setProperty('--grid-r', `${W - R - 1}px`);
    // Heatmap cells are 48px (32px on phones), stretched by a fraction of a pixel so a whole number spans the frame; the other
    // charts space their margins on a finer 32px (24px) unit.
    const u = W < 768 ? 24 : 32, base = W < 768 ? 32 : 48, c = (R - L) / Math.round((R - L) / base), rows = Math.max(4, Math.round((H - hh()) * FILL / c));
    const rnd = rng(9), nx = Math.round((R - L) / c), cells = [], bandTop = Math.round(hh() + (H - hh() - rows * c) / 2);
    for (let r = 0; r < rows; r++) for (let i = 0; i < nx; i++) cells.push({ x: L + i * c, y: bandTop + (rows - 1 - r) * c, r, p: rnd() * 6.3, q: rnd() * 6.3 });
    // Illustrative, unlabelled points: bubbles as a share of each axis, forest rows as hazard ratios with 95% CIs.
    const bubbles = Array.from({ length: 16 }, () => ({ sx: rnd(), sy: clamp(.15 + rnd() * .75), r: u * (.3 + rnd() ** 1.6 * 1.05), v: rnd(), p: rnd() * 6.3, q: rnd() * 6.3 }));
    const forest = Array.from({ length: W < 768 ? 6 : 8 }, () => { const hr = Math.exp(-.35 + (rnd() - .5) * .7), w = .45 + rnd() * .55; return { hr, lo: hr * Math.exp(-(.12 + (1 - w) * .45)), hi: hr * Math.exp(.12 + (1 - w) * .45), w }; });
    const lhr = forest.reduce((s, r) => s + Math.log(r.hr), 0) / forest.length, pooled = { hr: Math.exp(lhr), lo: Math.exp(lhr - .1), hi: Math.exp(lhr + .1) };
    S = { c, u, rows, cells, bandTop, bubbles, forest, pooled, zs: zones(), slot: -1, pick: null };
  }

  // Build-in wipes from the left: each mark grows once the build passes its x.
  const grow = (b, x) => ease(b * 1.5 - (x - L) / (R - L) * .5);
  // Marks thin out within three units of their chart's top and bottom.
  const edge = (y, top, bot) => .25 + .75 * clamp(Math.min(y - top, bot - y) / (3 * S.u));
  // Lines and labels need more ink than fills to read at the same strength.
  const ink = k => k * Math.min(1, HEAT * 2);
  // Labels are skipped where they would land on the copy (on phones the copy covers most of the hero): text over text is noise.
  const label = (text, x, y, align = 'left', a = .55) => {
    ctx.font = '500 10.5px "IBM Plex Mono", monospace'; ctx.letterSpacing = '.04em';
    const w = ctx.measureText(text).width, x0 = align === 'right' ? x - w : align === 'center' ? x - w / 2 : x;
    if (inCopy(x0, y, 4) || inCopy(x0 + w, y, 4)) return;
    ctx.textAlign = align; ctx.textBaseline = 'middle'; ctx.fillStyle = `rgba(${TEAL},${ink(a)})`; ctx.fillText(text, x, y);
  };
  const hline = (x0, x1, y, a) => { ctx.fillStyle = `rgba(${TEAL},${ink(a)})`; ctx.fillRect(Math.round(x0), Math.round(y), Math.round(x1 - x0), 1); };
  const vline = (x, y0, y1, a) => { ctx.fillStyle = `rgba(${TEAL},${ink(a)})`; ctx.fillRect(Math.round(x), Math.round(y0), 1, Math.round(y1 - y0)); };
  // The plot area sits one unit in from the frame and a unit and a half from its chart's top and bottom. With `onText`, its
  // left edge (the y-axis) moves onto the hero text's left edge, so the axis and the headline share one line.
  const plot = (top, bot, onText) => ({ x0: onText ? Math.round(Math.min(...S.zs.map(z => z.box[0] - z.box[2]))) : L + S.u, x1: R - S.u, y0: top + S.u * 1.5, y1: bot - S.u * 1.5 });

  // Each chart takes the height that suits it (h, a share of the hero below the header, centred); the heatmap keeps the band.
  const CHARTS = [
    { draw(t, b) {
      const { c, rows, cells } = S;
      for (const k of cells) {
        // Edge weight: the top and bottom two rows thin out, so the band has no hard edge at either end.
        const h = 1 - clamp((rows - 1 - k.r + .5) / 2) * clamp((k.r + .5) / 2);
        // Every cell keeps a 30% floor and the slow wave only shades the field, so the band never opens empty patches.
        const o = .45 * Math.sin(k.x * .009 + t * .35 + k.p * .4) + .2 * Math.sin(k.x * .0031 - t * .22 + k.r * .7) + .2 * Math.sin(t * .5 + k.p) + .45 - h * .5;
        k.a = (.3 + .7 * clamp(o / .6)) * (.85 - h * .3);
        // Colour never drops to the palest mint, which vanishes into the page tint and reads as a hole.
        const v = Math.min(k.a + .08, .54, .14 + .86 * clamp(.36 + .32 * Math.sin(k.x * .006 - t * .6 + k.r * .5) + .2 * Math.sin(t * .4 + k.q) + (1 - h) * .1) ** 1.6);
        ctx.fillStyle = `rgba(${ramp(v).map(Math.round)},${clamp(k.a * .42 * clamp((1 - h) * 1.6 + .15) * HEAT * grow(b, k.x))})`;
        const x1 = Math.round(k.x), y1 = Math.round(k.y);
        ctx.fillRect(x1 + 1, y1, Math.round(k.x + c) - x1 - 1, Math.round(k.y + c) - y1 - 1);
      }
      // The one accent: every few seconds a random settled cell turns gold, then fades. Any cell outside the thinned outer two
      // rows qualifies, under the copy too (the text sits over it, as over the charts), and never the last one, so the accent
      // wanders across the whole band rather than cycling through the few cells clear of the copy.
      const s = Math.floor(t / 3), ph = (t / 3) % 1;
      if (s !== S.slot) {
        S.slot = s;
        const cand = cells.filter(k => k !== S.pick && k.r >= 1 && k.r <= rows - 2 && k.a > .3);
        S.pick = cand.length ? cand[Math.floor(Math.random() * cand.length)] : null;
      }
      const p = S.pick; if (!p) return;
      const a = Math.min(ease(ph * 5), ease((1 - ph) * 5)) * b;
      ctx.fillStyle = `rgba(247,250,249,${a})`; ctx.fillRect(Math.round(p.x) + 1, Math.round(p.y), c - 1, c - 1);
      ctx.fillStyle = `rgba(${GOLD},${.26 * a})`; ctx.fillRect(Math.round(p.x) + 1, Math.round(p.y), c - 1, c - 1);
    } },

    // Efficacy against safety: x is the grade 3+ adverse event rate, y the median PFS, size the trial's enrolment.
    { h: .8, draw(t, b, top, bot) {
      const P = plot(top, bot, true), X = v => P.x0 + (.06 + v * .88) * (P.x1 - P.x0), Y = v => P.y1 - (.08 + v * .84) * (P.y1 - P.y0);
      // Axes, and a dashed median crosshair that splits the field into quadrants.
      hline(P.x0, P.x0 + (P.x1 - P.x0) * ease(b * 2), P.y1, .2); vline(P.x0, P.y1 - (P.y1 - P.y0) * ease(b * 2), P.y1, .2);
      ctx.setLineDash([2, 5]); ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${TEAL},${ink(.15 * b)})`; ctx.beginPath();
      ctx.moveTo(Math.round(X(.5)) + .5, P.y0); ctx.lineTo(Math.round(X(.5)) + .5, P.y1); ctx.moveTo(P.x0, Math.round(Y(.5)) + .5); ctx.lineTo(P.x1, Math.round(Y(.5)) + .5); ctx.stroke(); ctx.setLineDash([]);
      label('Grade 3+ AEs →', P.x1, P.y1 + 14, 'right', .5 * b); label('↑ Median PFS', P.x0 + 8, P.y0 + 4, 'left', .5 * b);
      // The gold bubble is the best balance (high PFS, low toxicity) among those clear of the copy, so it is always seen.
      const best = S.bubbles.filter(k => !inCopy(X(k.sx), Y(k.sy), k.r + 40)).reduce((m, k) => !m || k.sy - k.sx > m.sy - m.sx ? k : m, null);
      for (const k of S.bubbles) {
        const g = grow(b, X(k.sx)); if (g <= 0) continue;
        // A spring-like overshoot as each bubble arrives, then a slow drift.
        const pop = g < 1 ? g * (1 + .12 * Math.sin(g * Math.PI)) : 1;
        const x = X(k.sx) + 6 * Math.sin(t * .2 + k.p), y = Y(k.sy) + 4 * Math.cos(t * .17 + k.q), r = k.r * pop, e = edge(y, top, bot);
        const col = ramp(.2 + k.v * .55).map(Math.round), lit = ramp(.05 + k.v * .3).map(Math.round);
        // A soft sheen from the top left gives each bubble a little volume.
        const f = ctx.createRadialGradient(x - r * .35, y - r * .35, 0, x, y, r);
        f.addColorStop(0, `rgba(${lit},${.15 * HEAT * e})`); f.addColorStop(1, `rgba(${col},${.26 * HEAT * e})`);
        ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = f; ctx.fill();
        ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${col},${ink(.35 * e)})`; ctx.stroke();
        if (k !== best) continue;
        // The one accent: ringed in gold with a slow pulse.
        const ph = (t * .4) % 1;
        ctx.lineWidth = 1.25; ctx.strokeStyle = `rgba(${GOLD},${ink(.9 * g)})`; ctx.beginPath(); ctx.arc(x, y, r + 3, 0, 7); ctx.stroke();
        ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${GOLD},${ink(.5 * (1 - ph) * g)})`; ctx.beginPath(); ctx.arc(x, y, r + 3 + ph * 14, 0, 7); ctx.stroke();
      }
    } },

    // The three real CheckMate 067 PFS arms (data/km-checkmate067-pfs.js); a cursor reads across them.
    { h: .84, draw(t, b, top, bot) {
      const P = plot(top, bot, true), X = m => P.x0 + m / 60 * (P.x1 - P.x0), Y = p => P.y1 - p / 100 * (P.y1 - P.y0);
      const curves = [KM.main.ipilimumab, KM.main.nivolumab, KM.main.nivolumab_plus_ipilimumab];
      hline(P.x0, P.x1, P.y1, .2);
      for (const m of [0, 12, 24, 36, 48, 60]) { vline(X(m), P.y1, P.y1 + 4, .2); label(m === 60 ? '60 mo' : String(m), X(m), P.y1 + 14, m === 0 ? 'left' : m === 60 ? 'right' : 'center', .5); }
      // The curves draw themselves from month 0 as the chart builds.
      ctx.save(); ctx.beginPath(); ctx.rect(P.x0 - 2, top, (P.x1 - P.x0) * ease(b) + 4, bot - top); ctx.clip();
      curves.forEach((pts, i) => {
        const front = i === curves.length - 1, end = Math.min(60, pts.at(-1)[0] + 1.5);
        const path = new Path2D(); let py = Y(pts[0][1]); path.moveTo(X(0), py);
        for (const [tm, p] of pts.slice(1)) { path.lineTo(X(tm), py); py = Y(p); path.lineTo(X(tm), py); }
        path.lineTo(X(end), py);
        if (front) {
          // The front arm carries a soft fill down to the axis.
          const area = new Path2D(path); area.lineTo(X(end), P.y1); area.lineTo(X(0), P.y1); area.closePath();
          const g = ctx.createLinearGradient(0, P.y0, 0, P.y1); g.addColorStop(0, `rgba(${SEA},${.1 * HEAT})`); g.addColorStop(1, `rgba(${SEA},0)`);
          ctx.fillStyle = g; ctx.fill(area);
        }
        ctx.lineWidth = front ? 1.6 : 1; ctx.strokeStyle = front ? `rgba(${TEAL},${ink(.55)})` : `rgba(${SEA},${ink(.32)})`; ctx.stroke(path);
        // A censored tail ends in a small tick rather than an invented line to 60 months.
        ctx.beginPath(); ctx.moveTo(X(end), py - 3); ctx.lineTo(X(end), py + 3); ctx.stroke();
      });
      ctx.restore();
      // The one accent: the front arm's median, where it crosses 50%.
      const front = curves[2], tm = front[front.findIndex(([, p]) => p < 50)][0], mx = X(tm), a = clamp((ease(b) - (mx - P.x0) / (P.x1 - P.x0)) * 5);
      ctx.setLineDash([2, 4]); ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${GOLD},${ink(.6 * a)})`; ctx.beginPath(); ctx.moveTo(Math.round(mx) + .5, Y(50)); ctx.lineTo(Math.round(mx) + .5, P.y1); ctx.stroke(); ctx.setLineDash([]);
      ctx.beginPath(); ctx.arc(mx, Y(50), 3.5, 0, 7); ctx.fillStyle = `rgba(247,250,249,${a})`; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = `rgba(${GOLD},${ink(a)})`; ctx.stroke();
      label(`mPFS ${tm.toFixed(1)} mo`, mx + 9, Y(50) - 10, 'left', .6 * a);
      // Once the curves are drawn, a reading cursor sweeps across, marking where each arm sits.
      if (b < 1) return;
      const at = (pts, m) => { let p = pts[0][1]; for (const [tm, v] of pts) { if (tm > m) break; p = v; } return p; };
      const ph = (t * .05) % 1, m = 3 + ph * 52, ca = Math.sin(Math.PI * ph) ** .6, cx = X(m);
      vline(cx, P.y0, P.y1, .3 * ca);
      curves.forEach((pts, i) => { ctx.beginPath(); ctx.arc(cx, Y(at(pts, m)), i === 2 ? 3 : 2.5, 0, 7); ctx.fillStyle = `rgba(${i === 2 ? TEAL : SEA},${ink(.55 * ca)})`; ctx.fill(); });
    } },

    // Hazard ratios across subgroups around the no-difference line, with the pooled estimate as a gold diamond.
    { h: .8, draw(t, b, top, bot) {
      const P = plot(top, bot), mid = Math.round(L + (R - L) / 2), sc = (R - L) * .26, X = hr => mid + Math.log(hr) * sc;
      const rows = S.forest, n = rows.length, rowH = (P.y1 - P.y0 - S.u * 1.2) / n, yd = P.y1 - S.u * .35;
      vline(mid, P.y0 - S.u * .6, P.y1 + 4, .25 * ease(b * 2));
      label('HR 1.0', mid + 6, P.y0 - S.u * .6 + 6, 'left', .5 * b);
      label('← favours treatment', mid - 10, P.y1 + 14, 'right', .45 * b); label('favours control →', mid + 10, P.y1 + 14, 'left', .45 * b);
      // One row at a time lifts, as if read by a pointer.
      const hot = Math.floor(t * .5) % n, hp = (t * .5) % 1, hotA = Math.min(ease(hp * 4), ease((1 - hp) * 4));
      rows.forEach((r, i) => {
        const y = Math.round(P.y0 + (i + .5) * rowH) + .5, g = ease(b * 1.6 - i / n * .6); if (g <= 0) return;
        const lift = i === hot ? hotA : 0, e = edge(y, top, bot);
        if (lift) { ctx.fillStyle = `rgba(${SEA},${.12 * HEAT * lift})`; ctx.fillRect(P.x0, y - rowH / 2, P.x1 - P.x0, rowH); }
        // Whiskers grow outward from the estimate, then the box lands.
        const x = X(r.hr), lo = x + (X(r.lo) - x) * g, hi = x + (X(r.hi) - x) * g;
        ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${TEAL},${ink((.25 + .3 * lift) * e)})`; ctx.beginPath(); ctx.moveTo(lo, y); ctx.lineTo(hi, y);
        ctx.moveTo(Math.round(lo) + .5, y - 3); ctx.lineTo(Math.round(lo) + .5, y + 3); ctx.moveTo(Math.round(hi) + .5, y - 3); ctx.lineTo(Math.round(hi) + .5, y + 3); ctx.stroke();
        const s = r.w * Math.min(rowH * .55, 11) * ease(g * 1.4 - .4);
        ctx.fillStyle = `rgba(${ramp(.55 + .3 * lift).map(Math.round)},${ink((.35 + .3 * lift) * e)})`; ctx.fillRect(Math.round(x - s / 2), Math.round(y - s / 2), Math.round(s), Math.round(s));
      });
      // The one accent: the pooled estimate.
      const { hr, lo, hi } = S.pooled, a = ease(b * 2 - 1), h = Math.min(rowH * .4, 7);
      ctx.setLineDash([2, 4]); ctx.strokeStyle = `rgba(${GOLD},${ink(.35 * a)})`; ctx.beginPath(); ctx.moveTo(Math.round(X(hr)) + .5, P.y0); ctx.lineTo(Math.round(X(hr)) + .5, yd); ctx.stroke(); ctx.setLineDash([]);
      ctx.beginPath(); ctx.moveTo(X(lo), yd); ctx.lineTo(X(hr), yd - h); ctx.lineTo(X(hi), yd); ctx.lineTo(X(hr), yd + h); ctx.closePath();
      ctx.fillStyle = `rgba(${GOLD},${ink(.3 * a)})`; ctx.fill(); ctx.lineWidth = 1.25; ctx.strokeStyle = `rgba(${GOLD},${ink(.9 * a)})`; ctx.stroke();
    } },
  ];

  function draw(t) {
    const { c, rows } = S, u = 2 * c, top = S.bandTop, bot = top + rows * c, x0 = L - u * Math.ceil(L / u);
    const n = Math.floor(t / DUR), f = t - n * DUR, len = CHARTS.length;
    // The grid belongs to the heatmap alone; the other charts sit on clean light. hm is how much heatmap is on screen.
    const hm = (n % len === 0 ? clamp(f / FADE) : 0) + (n > 0 && f < FADE && (n - 1) % len === 0 ? 1 - f / FADE : 0);
    ctx.clearRect(0, 0, W, H); ctx.lineWidth = 1;
    // The column edges, as every section has.
    ctx.beginPath(); for (const x of [L, R]) { ctx.moveTo(Math.round(x) + .5, 0); ctx.lineTo(Math.round(x) + .5, H); }
    ctx.strokeStyle = `rgba(${TEAL},.07)`; ctx.stroke();
    // Hairline tracks above and below the band alternate one unit and two units wide (lines at 0, 1, 3, 4, 6, 7 ...),
    // then fade out toward the header and the foot.
    ctx.beginPath();
    for (let k = 0, x = x0; x <= W; k++, x += u) if (k % 3 !== 2 && x > L && x < R) { ctx.moveTo(Math.round(x) + .5, hh()); ctx.lineTo(Math.round(x) + .5, H); }
    for (let k = 3, y = top - 3 * u; y >= hh() + u; k++, y -= u) if (k % 3 !== 2) { ctx.moveTo(L, Math.round(y) - .5); ctx.lineTo(R + 1, Math.round(y) - .5); }
    for (let k = 3, y = bot + 3 * u; y <= H - u; k++, y += u) if (k % 3 !== 2) { ctx.moveTo(L, Math.round(y) - .5); ctx.lineTo(R + 1, Math.round(y) - .5); }
    ctx.globalAlpha = hm; ctx.strokeStyle = `rgba(${TEAL},.07)`; ctx.stroke(); ctx.globalAlpha = 1;
    ctx.save(); ctx.globalCompositeOperation = 'destination-out';
    const fade = ctx.createLinearGradient(0, hh(), 0, H), mid = ((top + bot) / 2 - hh()) / (H - hh());
    fade.addColorStop(0, 'rgba(0,0,0,.9)'); fade.addColorStop(mid, 'rgba(0,0,0,0)'); fade.addColorStop(1, 'rgba(0,0,0,.9)');
    ctx.fillStyle = fade; ctx.fillRect(0, hh(), W, H - hh()); ctx.restore();
    // The band's hairline cells, fading toward its top and bottom so it has no drawn outline.
    ctx.beginPath();
    for (let x = L; x <= R + 1; x += c) { ctx.moveTo(Math.round(x) + .5, top); ctx.lineTo(Math.round(x) + .5, bot); }
    for (let y = top; y <= bot + 1; y += c) { ctx.moveTo(L, Math.round(y) + .5); ctx.lineTo(R + 1, Math.round(y) + .5); }
    const hair = ctx.createLinearGradient(0, top, 0, bot);
    hair.addColorStop(0, `rgba(${TEAL},0)`); hair.addColorStop(.25, `rgba(${TEAL},.07)`); hair.addColorStop(.75, `rgba(${TEAL},.07)`); hair.addColorStop(1, `rgba(${TEAL},0)`);
    ctx.globalAlpha = hm; ctx.strokeStyle = hair; ctx.stroke(); ctx.globalAlpha = 1;
    // The charts run straight under the copy; the text sits over them rather than the art stepping back around it.
    const run = (k, a, b) => {
      const h = k.h ? (H - hh()) * k.h : bot - top, y0 = k.h ? Math.round(hh() + (H - hh() - h) / 2) : top, y1 = Math.round(y0 + h);
      ctx.save(); ctx.globalAlpha = a; ctx.beginPath(); ctx.rect(L, y0, R - L, y1 - y0); ctx.clip(); k.draw(t, b, y0, y1); ctx.restore();
    };
    // The outgoing chart only fades; the incoming one fades in and builds itself.
    if (n > 0 && f < FADE) run(CHARTS[(n - 1) % len], 1 - f / FADE, 1);
    run(CHARTS[n % len], clamp(f / FADE), clamp(f / BUILD));
  }

  // Reduced motion gets one still frame of the settled heatmap, redrawn only when the hero resizes.
  let t = still ? 6 : 0, last = 0, visible = true;
  const redraw = () => { size(); draw(t); };
  new ResizeObserver(redraw).observe(hero);
  document.fonts.ready.then(redraw); // the text extents change once the webfonts swap in
  if (still) return;
  new IntersectionObserver(([e]) => visible = e.isIntersecting).observe(hero);
  const frame = now => {
    t += Math.min(.05, last ? (now - last) / 1000 : 0) * .75; last = now;
    if (visible && S.cells) draw(t); // off-screen the clock still runs, so the loop picks up where it would be
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();

// ── OS stack: scroll inside the pinned run drops one layer per step, then the last step fuses them ──
(() => {
  const sc = document.getElementById('osScroll'), stage = sc.firstElementChild, bar = document.getElementById('osBar'), stack = document.getElementById('osStack');
  const slabs = [...stack.querySelectorAll('.slab')], pills = [...sc.querySelectorAll('.osp')], box = document.getElementById('osCase'), note = document.getElementById('osNote');
  const floor = stack.querySelector('.os-floor');
  // Pinned only where the stage has room for the open pill card and the stack; shorter screens get the static layout.
  const hdr = document.getElementById('hdr'), wide = matchMedia('(min-width: 1024px) and (min-height: 560px)');
  // HEAD: clear glass between the top layer's face and the lid.
  const N = slabs.length + 1, HOLD = .5, GAP = 30, CASED = 26, DROP = 620, HEAD = 19;
  const clamp = x => Math.min(1, Math.max(0, x)), out = t => 1 - (1 - t) ** 3, inOut = t => t < .5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
  // The case skin: thin rounded rings laid down one by one as the case drapes. Rings near the lid and the floor
  // are drawn slightly smaller, along a quarter circle, so both edges round off like moulded glass.
  // A ring is not a layer of its own. Rings are flat shadows on a few wall planes, each cast along the plane diagonal by
  // as far as its depth moves it on screen (PLANE px per px of depth). Planes keep the draw order of the rings they
  // stand for: one per gap between slabs, and one per slab between its edge and its face for the rings beside its rim,
  // which frost over that rim, plus one for the bright lip under the lid. So the case costs two layers per slab, not one
  // per ring. Shadow colours are fixed at full frost and each plane fades by opacity, so the frost costs no repaint.
  const SKIN = 90, FILLET = 12, FOOT = 18, PLANE = Math.tan(66.3 * Math.PI / 180) / Math.SQRT2;
  // Ring colours at full frost: the lip, the wall band, and the frost a gap's rings lay over the slab inside.
  const LIP = '255,255,255', RING = '229,242,237', FROST = '222,239,232', BAND = .3, FILL = .14;
  box.insertAdjacentHTML('afterbegin', '<i class="wall" hidden></i>'.repeat(2 * slabs.length + 2));
  const walls = [...box.querySelectorAll('.wall')];
  // Ring depths and fillet insets depend only on the case height, so they are set when it changes, not every frame.
  let shapedFor = -1, w = 0, depth = [], inset = [];
  const shape = h => {
    if (Math.abs(h - shapedFor) < .01) return;
    shapedFor = h; w = box.offsetWidth;
    const step = h / SKIN, curve = (d, r) => d < r ? r - Math.sqrt(r * r - (r - d) ** 2) : 0;
    depth = Array.from({ length: SKIN }, (_, k) => (k + 1) * step);
    inset = depth.map(d => Math.max(curve(d, FILLET), curve(h - d, FOOT)));
  };

  // p runs 0..N: layer i falls during [i, i + .75] and settles. In the last unit the case lid drops onto the stack,
  // then its walls drape down as milky frost, each layer whitening as the walls pass it; last, the frost clears to glass.
  const paint = p => {
    const L = slabs.length, lidIn = out(clamp((p - L) / .25)), drape = inOut(clamp((p - L - .2) / .3));
    // The frost eases back to a translucent rest by .75 of the last step, and holds there before the pin releases.
    const frost = Math.min(1, drape * 1.6) * (1 - .6 * inOut(clamp((p - L - .5) / .25)));
    const gap = GAP - (GAP - CASED) * lidIn, capped = clamp((p - L + .32) / .3);
    // As the lid lands, the stack lifts off the floor and the lid sits higher, so the case has clear glass above and below the layers.
    const lift = 14 * lidIn, top = lift + (L - 1) * gap + 12.5 + HEAD + 14 * lidIn, front = top - drape * (top + 2);
    slabs.forEach((s, i) => {
      s.style.setProperty('--z', `${lift + i * gap + (1 - out(clamp((p - i) / .75))) * DROP}px`);
      s.style.setProperty('--o', clamp((p - i) * 3.5));
      s.style.setProperty('--cov', i < L - 1 ? out(clamp((p - i - 1) / .75)) : capped);
      // --hid: covered by the case. Anything under the glass stays a shape, never readable text.
      const hid = drape && clamp((lift + i * gap + 12.5 - front) / 20);
      s.style.setProperty('--hid', hid);
      s.style.setProperty('--pk', (.12 + .68 * frost) * hid);
    });
    const cz = top + (1 - lidIn) * DROP;
    box.style.setProperty('--cz', `${cz}px`);
    box.style.setProperty('--o', clamp((p - L) * 4));
    const h = top + 2, step = h / SKIN, reach = drape * h, body = .2 + .8 * frost;
    shape(h);
    // Rings are revealed top down. Wall 0 is under the stack; wall 2i + 1 is beside slab i's rim, 2i + 2 the gap above
    // it; the last wall is the lip.
    const groups = walls.map(() => []);
    for (let k = 0; k < SKIN && reach > k * step; k++) {
      const z = cz - depth[k];
      let i = -1;
      while (i + 1 < L && lift + (i + 1) * gap <= z) i++;
      groups[k < 2 ? walls.length - 1 : i < 0 ? 0 : z <= lift + i * gap + 12.25 ? 2 * i + 1 : 2 * i + 2].push(k);
    }
    // A rim wall sits just above its slab's edge plane, a gap wall at its highest ring; each takes the size of its
    // smallest ring, so every ring's shadow clears it.
    walls.forEach((el, g) => {
      const ks = groups[g];
      el.hidden = !ks.length;
      if (!ks.length) return;
      const lip = g === walls.length - 1, d0 = g % 2 && !lip ? cz - (lift + (g - 1) / 2 * gap + 12.3) : depth[ks[0]], s = 1 - 2 * Math.max(...ks.map(k => inset[k])) / w;
      let clear = 1;
      const shadow = ks.map(k => {
        const o = clamp((reach - k * step) / step);
        clear *= 1 - FILL * o;
        const off = (PLANE * (depth[k] - d0) / s).toFixed(2), spread = (((w - 2 * inset[k]) / s - w) / 2).toFixed(2);
        return `${off}px ${off}px 0 ${spread}px rgba(${lip ? LIP : RING},${((lip ? .95 : BAND) * o).toFixed(3)})`;
      }).join();
      const css = `transform:translateZ(${(-d0).toFixed(2)}px) scale(${s.toFixed(4)});background:rgba(${FROST},${lip ? 0 : (1 - clear).toFixed(3)});box-shadow:${shadow};opacity:${lip ? 1 : body.toFixed(3)}`;
      if (el._css !== css) el.style.cssText = el._css = css;
    });
    note.style.setProperty('--pk', drape);
    box.style.setProperty('--fr', frost);
    floor.style.opacity = clamp(p * 2);
  };
  // The drawn position follows the scroll position on a critically damped spring (response .45 s): it starts with
  // no jolt, carries its velocity when the scroll reverses, and settles without overshoot at any refresh rate.
  const W0 = 2 * Math.PI / .45;
  let cur = -1, raf = 0, pinned = false, target = 0, shown = 0, vel = 0, last = 0;
  const cards = pillSprings(pills), settle = cards.settle;
  const setStep = n => {
    if (n === cur) return;
    const was = cur; cur = n;
    cards.morph(() => pills.forEach(b => +b.dataset.step === n ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current')), pinned && was >= 0);
  };
  const range = () => [sc.getBoundingClientRect().top + scrollY - hdr.offsetHeight, Math.max(1, sc.offsetHeight - stage.offsetHeight)];
  // The pills and the progress bar read the drawn position, so they change on the same frame as the stack.
  const draw = () => {
    const q = Math.min(N, shown * (N + HOLD));
    paint(q); bar.style.transform = `scaleX(${shown})`; setStep(Math.min(N, Math.floor(q) + 1));
  };
  const frame = now => {
    const dt = Math.min(.05, last ? (now - last) / 1000 : 1 / 60); last = now;
    vel += (W0 * W0 * (target - shown) - 2 * W0 * vel) * dt; shown += vel * dt;
    if (Math.abs(target - shown) < .0003 && Math.abs(vel) < .002) { shown = target; vel = 0; }
    draw();
    raf = shown === target ? 0 : requestAnimationFrame(frame);
    if (!raf) last = 0;
  };
  const pick = () => {
    const [top, len] = range();
    target = clamp((scrollY - top) / len);
    if (!raf) raf = requestAnimationFrame(frame);
  };
  pills.forEach((b, i) => b.addEventListener('click', () => {
    if (!pinned) return;
    const [top, len] = range();
    scrollTo({ top: top + (i + .8) / (N + HOLD) * len, behavior: 'smooth' });
  }));
  // The scene is drawn for a 1248 x 836 stage (a 1440 x 900 window). Larger stages scale all of it, depths included,
  // by height, as far as the width leaves the stack clear of the pills.
  const fit = () => stack.style.setProperty('--k', pinned ? Math.max(1, Math.min(stage.clientHeight / 836, stage.clientWidth / 840)) : 1);
  const mode = () => {
    removeEventListener('scroll', pick); cur = -1; settle();
    pinned = wide.matches && !still;
    sc.dataset.mode = pinned ? 'pinned' : 'static';
    fit();
    if (pinned) { addEventListener('scroll', pick, { passive: true }); pick(); shown = target; vel = 0; draw(); }
    else { pills.forEach(b => b.removeAttribute('aria-current')); paint(N); }
  };
  wide.addEventListener('change', mode);
  addEventListener('resize', () => { shapedFor = -1; settle(); fit(); if (pinned) pick(); else paint(N); });
  mode();
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
  // The title sits above its box, not inside it, so the box holds only the sources.
  box(10, 48, 224, 518, 'rgba(201,162,39,.06)', 'rgba(201,162,39,.5)', 18, 1.3);
  el('circle', { cx: 16, cy: 24, r: 4.5, fill: '#C9A227' }, s);
  txt(s, 28, 30, 'Raw Scientific Data', { fill: '#fff', 'font-size': 17, 'font-weight': 600, 'font-family': 'Onest', 'letter-spacing': '-.03em' });
  SOURCES.forEach((n, i) => {
    const y = 70 + i * 84, cy = y + 27, ty = 254 + i * 16, ex = CX - Math.sqrt(R * R - (ty - CY) ** 2);
    line(`M220,${cy} C282,${cy} 262,${ty} ${ex},${ty}`, 'rgba(201,162,39,.8)', -i * .17);
    box(24, y, 196, 54, 'rgba(201,162,39,.12)', 'rgba(201,162,39,.48)');
    txt(s, 122, cy + 5, n, { 'text-anchor': 'middle', fill: '#F3EBD3', 'font-size': 14 });
  });
  [0, 2, 4, 5].forEach((i, k) => {
    const y = 70 + i * 84 + 27, ty = 254 + i * 16, ex = CX - Math.sqrt(R * R - (ty - CY) ** 2);
    const c = el('circle', { r: 3.2, fill: '#F1D77A' }, s);
    if (!still) el('animateMotion', { dur: '2.8s', repeatCount: 'indefinite', begin: (-k * .7) + 's', path: `M220,${y} C282,${y} 262,${ty} ${ex},${ty}` }, c); else c.remove();
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
  txt(s, 822, 56, 'Visual Platform', { fill: '#7AC1A2', 'font-size': 21, 'font-weight': 600, 'font-family': 'Onest', 'letter-spacing': '-.03em' });
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
  // Pinned only where the stage has room for the open step card and the chart; shorter screens get the static layout.
  const wide = matchMedia('(min-width: 1024px) and (min-height: 560px)');
  const x0 = 52, y0 = 14; let x1 = 620, y1 = 322;
  const X = m => x0 + m / 60 * (x1 - x0), Y = p => y1 - p / 100 * (y1 - y0);
  const step = pts => pts.reduce((d, [t, p], i) => i ? d + ` H${X(t).toFixed(1)} V${Y(p).toFixed(1)}` : `M${X(t)},${Y(p)}`, '') + ` H${X(Math.min(60, pts.at(-1)[0] + 1.5))}`;
  const ARMS = [['nivolumab_plus_ipilimumab', '#1B4F65', 11.5], ['nivolumab', '#2F8A66', 6.9], ['ipilimumab', '#C9A227', 2.9]];
  // When pinned, the card scales with the viewport, so the plot is drawn to the svg's own box. One unit stays 1.3px
  // once the box outgrows 640 units: the plot grows on big screens while the axis text keeps its laptop size.
  // Elsewhere it keeps the default 640x380 proportions.
  const draw = () => {
    const r = s.getBoundingClientRect(), fit = wide.matches && !still && r.width;
    const W = fit ? Math.max(640, Math.round(r.width / 1.3)) : 640;
    const H = fit ? Math.max(380, Math.round(W * r.height / r.width)) : 380;
    s.replaceChildren(); s.setAttribute('viewBox', `0 0 ${W} ${H}`); x1 = W - 20; y1 = H - 58;
    const g = id => el('g', { id, class: 'layer' }, s);
    // Axes (step 2 snaps them into place)
    const ax = g('Lax');
    [0, 12, 24, 36, 48, 60].forEach(m => { el('line', { x1: X(m), x2: X(m), y1: y0, y2: y1, stroke: '#EEF4F1' }, ax); txt(ax, X(m), y1 + 20, m, { 'text-anchor': 'middle' }); });
    [0, 25, 50, 75, 100].forEach(p => { el('line', { x1: x0, x2: x1, y1: Y(p), y2: Y(p), stroke: '#EEF4F1' }, ax); txt(ax, x0 - 10, Y(p) + 4, p + '%', { 'text-anchor': 'end' }); });
    el('path', { d: `M${x0},${y0} V${y1} H${x1}`, fill: 'none', stroke: '#C8E0D8', 'stroke-width': 1.2 }, ax);
    txt(ax, (x0 + x1) / 2, y1 + 44, 'Months', { 'text-anchor': 'middle', style: 'font-family:Poppins;font-size:12px' });
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
  const cards = pillSprings(pills);
  const setStep = n => {
    if (n === cur) return;
    const was = cur; cur = n;
    cards.morph(() => pills.forEach(p => +p.dataset.step === n ? p.setAttribute('aria-current', 'step') : p.removeAttribute('aria-current')), pinned && was > 0);
    show(n);
  };
  // Scroll position inside the pinned run maps straight to a step, so no step can be skipped and the chart is always in view.
  const range = () => [scroller.getBoundingClientRect().top + scrollY - hdrEl.offsetHeight, Math.max(1, scroller.offsetHeight - stage.offsetHeight)];
  const pick = () => {
    raf = 0;
    const [top, len] = range(), p = Math.min(1, Math.max(0, (scrollY - top) / len));
    bar.style.transform = `scaleX(${p})`;
    // Hysteresis: the step changes only once the scroll is a little past a boundary, so resting on one never flickers.
    const at = p * N, n = Math.min(N, Math.floor(at) + 1);
    if (n !== cur && (!cur || Math.abs(at - (n > cur ? n - 1 : n)) > .06)) setStep(n);
  };
  const onScroll = () => { if (!raf) raf = requestAnimationFrame(pick); };
  pills.forEach((p, i) => p.addEventListener('click', () => {
    if (!pinned) return;
    const [top, len] = range();
    scrollTo({ top: top + (i + .5) / N * len, behavior: still ? 'auto' : 'smooth' });
  }));
  const mode = () => {
    removeEventListener('scroll', onScroll); cur = 0; cards.settle();
    pinned = wide.matches && !still;
    scroller.dataset.mode = pinned ? 'pinned' : 'static';
    draw();
    if (pinned) { addEventListener('scroll', onScroll, { passive: true }); pick(); }
    else { pills.forEach(p => p.removeAttribute('aria-current')); cur = N; show(N); }
  };
  wide.addEventListener('change', mode);
  addEventListener('resize', () => { cards.settle(); draw(); if (pinned) pick(); });
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
