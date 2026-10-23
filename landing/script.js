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

// ── Hero background: a heatmap band along the base, its cells drifting through the brand ramp ──
(() => {
  const hero = document.getElementById('hero'), cv = document.getElementById('heroBg'), ctx = cv.getContext('2d');
  const TEAL = '27,79,101', GOLD = '201,162,39';
  const RAMP = [[218,240,230], [122,193,162], [47,138,102], [27,79,101], [14,53,71]];
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = x => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const rng = s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const ramp = v => { v = clamp(v) * (RAMP.length - 1); const i = Math.min(RAMP.length - 2, v | 0), f = v - i; return RAMP[i].map((a, k) => a + (RAMP[i + 1][k] - a) * f); };
  // Cursor focus: the pointer is followed with an eased approach, never snapped to.
  const ptr = { x: 0, y: 0, tx: 0, ty: 0, on: 0, ton: 0 };
  const hh = document.getElementById('hdr').offsetHeight;
  let W = 0, H = 0, c = 32, u = 64, x0 = 0, L = 0, R = 0, rows = 7, cells = [], zones = [], slot = -1, pick = null;

  function size() {
    const dpr = Math.min(2, devicePixelRatio || 1), r = hero.getBoundingClientRect();
    W = r.width; H = r.height; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // One grid unit is two band cells: the band is drawn in cells, the field above it in units.
    c = W < 768 ? 24 : 32; u = 2 * c; x0 = (W % u) / 2 - u; rows = W < 768 ? 6 : 7;
    // The grid is framed: its outer edges sit on cell lines a margin in from each side, and nothing is drawn beyond them.
    const m = W < 768 ? 16 : 40; L = x0 + c * Math.ceil((m - x0) / c); R = x0 + c * Math.floor((W - m - x0) / c);
    // The frame's two edges carry on a little past the hero (main::before in styles.css).
    document.documentElement.style.setProperty('--grid-l', `${Math.round(L)}px`); document.documentElement.style.setProperty('--grid-r', `${W - Math.round(R) - 1}px`);
    // A few 2x2 merged cells on the unit grid, like a heatmap's aggregated bins.
    const rnd = rng(9), taken = new Set(), nx = Math.round((R - L) / c); cells = [];
    for (let r = 0; r < rows; r++) for (let i = 0; i < nx; i++) {
      if (taken.has(r * nx + i)) continue;
      const big = !(i % 2) && !(r % 2) && r + 1 < rows && i + 1 < nx && rnd() < .13;
      if (big) [r * nx + i + 1, (r + 1) * nx + i, (r + 1) * nx + i + 1].forEach(n => taken.add(n));
      cells.push({ x: L + i * c, y: H - (r + 1 + big) * c, r, n: big ? 2 : 1, p: rnd() * 6.3, q: rnd() * 6.3 });
    }
    // Each text column's own extent (its grid cell is wider than the text), so the band can fade behind it.
    zones = [...hero.querySelectorAll('.hero-copy')].map(e => {
      const kids = [...e.children].map(k => k.getBoundingClientRect());
      const L = Math.min(...kids.map(b => b.left)), Rt = Math.max(...kids.map(b => b.left + Math.min(b.width, 560))), T = Math.min(...kids.map(b => b.top)), B = Math.max(...kids.map(b => b.bottom));
      return { x: (L + Rt) / 2 - r.left, y: (T + B) / 2 - r.top, rx: (Rt - L) * .68, ry: (B - T) * .72 };
    });
    slot = -1;
  }

  function draw(t) {
    const top = H - rows * c;
    // Time-based easing (about .11 s), so the focus follows at the same speed on 60 and 120 Hz screens.
    const ease1 = 1 - Math.exp(-dt / .11);
    for (const k of ['x', 'y', 'on']) ptr[k] += (ptr['t' + k] - ptr[k]) * ease1;
    ctx.clearRect(0, 0, W, H); ctx.lineWidth = 1;
    // Above the band, tracks alternate one unit and two units wide in both directions (lines at 0, 1, 3, 4, 6, 7 ...),
    // with an open stretch of three units over the band where the copy ends.
    ctx.beginPath();
    for (let k = 0, x = x0; x <= W; k++, x += u) if (k % 3 !== 2 && x > L && x < R) { ctx.moveTo(Math.round(x) + .5, 0); ctx.lineTo(Math.round(x) + .5, top); }
    for (const x of [L, R]) { ctx.moveTo(Math.round(x) + .5, 0); ctx.lineTo(Math.round(x) + .5, top); }
    // The top of the hero is open: horizontal tracks stop two units below the header, so only the verticals run up to it.
    for (let k = 3, y = top - 3 * u; y >= hh + 2 * u; k++, y -= u) if (k % 3 !== 2) { ctx.moveTo(L, Math.round(y) - .5); ctx.lineTo(R + 1, Math.round(y) - .5); }
    ctx.strokeStyle = `rgba(${TEAL},.075)`; ctx.stroke();
    ctx.beginPath();
    for (let x = L; x <= R + 1; x += c) { ctx.moveTo(Math.round(x) + .5, top); ctx.lineTo(Math.round(x) + .5, H); }
    for (let y = H; y >= top - 1; y -= c) { ctx.moveTo(L, Math.round(y) - .5); ctx.lineTo(R + 1, Math.round(y) - .5); }
    ctx.strokeStyle = `rgba(${TEAL},.09)`; ctx.stroke();
    for (const k of cells) {
      const h = k.r / (rows - 1), cx = k.x + c * k.n / 2, cy = k.y + c * k.n / 2;
      const f = ptr.on * Math.exp(-((cx - ptr.x) ** 2 + (cy - ptr.y) ** 2) / (2 * 120 * 120));
      // Occupancy: a slow field, a little denser at the base, so cells come and go as it drifts.
      const o = .5 * Math.sin(k.x * .009 + t * .35 + k.p * .4) + .35 * Math.sin(k.x * .0031 - t * .22 + k.r * .7) + .2 * Math.sin(t * .5 + k.p) + .3 - h * .55 + f * .6;
      k.a = clamp(o / .35) * (.78 - h * .2 + f * .2);
      if (k.a < .02) continue;
      // Colour: a wave travelling along the band. Capped by opacity, so a faint cell is always a pale tint, never a greyed dark;
      // merged cells stay pale, and the band cools to grey toward the right edge.
      let v = Math.min(k.a + .08, .74, clamp(.36 + .32 * Math.sin(k.x * .006 - t * .6 + k.r * .5) + .2 * Math.sin(t * .4 + k.q) + (1 - h) * .1 + f * .05) ** 1.6);
      if (k.n > 1) v *= .45;
      const rgb = ramp(v), gr = .3 * rgb[0] + .59 * rgb[1] + .11 * rgb[2], d = .85 * clamp((cx / W - .62) / .3);
      // Square and flush on the grid: inset or rounded cells open gutters that pull the eye to the corners.
      ctx.fillStyle = `rgba(${rgb.map(x => Math.round(x + (gr - x) * d))},${k.a})`;
      ctx.fillRect(Math.round(k.x) + 1, Math.round(k.y), c * k.n - 1, c * k.n - 1);
    }
    // Fade the band behind each text column so the copy never competes with it.
    ctx.save(); ctx.globalCompositeOperation = 'destination-out';
    for (const z of zones) {
      ctx.save(); ctx.translate(z.x, z.y); ctx.scale(z.rx, z.ry);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
      g.addColorStop(0, 'rgba(0,0,0,.55)'); g.addColorStop(.55, 'rgba(0,0,0,.47)'); g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, 1, 0, 7); ctx.fill(); ctx.restore();
    }
    ctx.restore();
    // The one accent: every few seconds a settled cell clear of the copy turns gold, then fades.
    const s = Math.floor(t / 3), ph = (t / 3) % 1;
    if (s !== slot) {
      slot = s;
      const cand = cells.filter(k => k.n === 1 && k.r >= 2 && k.r <= rows - 2 && k.a > .35 && k.x > 40 && k.x < W - 140
        && !zones.some(z => ((k.x - z.x) / z.rx) ** 2 + ((k.y - z.y) / z.ry) ** 2 < 1));
      pick = cand.length ? cand[Math.floor(rng(s)() * cand.length)] : null;
    }
    if (!pick) return;
    const a = Math.min(ease(ph * 5), ease((1 - ph) * 5)), sz = (c - 1) * (.86 + .14 * a), o2 = (c - 1 - sz) / 2;
    ctx.beginPath(); ctx.rect(Math.round(pick.x) + 1 + o2, Math.round(pick.y) + o2, sz, sz);
    ctx.fillStyle = `rgba(247,250,249,${a})`; ctx.fill(); ctx.fillStyle = `rgba(${GOLD},${.8 * a})`; ctx.fill();
  }

  // Reduced motion gets one still frame, redrawn only when the hero resizes.
  let t = 6, last = performance.now(), visible = true, dt = 1 / 60;
  const redraw = () => { size(); draw(t); };
  new ResizeObserver(redraw).observe(hero);
  document.fonts.ready.then(redraw); // the text extents change once the webfonts swap in
  if (still) return;
  new IntersectionObserver(([e]) => visible = e.isIntersecting).observe(hero);
  const local = e => { const r = hero.getBoundingClientRect(); ptr.tx = e.clientX - r.left; ptr.ty = e.clientY - r.top; };
  hero.addEventListener('pointermove', e => { if (e.pointerType === 'touch') return; local(e); if (ptr.on < .05) { ptr.x = ptr.tx; ptr.y = ptr.ty; } ptr.ton = 1; });
  hero.addEventListener('pointerleave', () => ptr.ton = 0);
  const frame = now => {
    dt = Math.min(.05, (now - last) / 1000); t += dt * .5; last = now;
    if (visible) draw(t); // off-screen the clock still runs, so the band picks up where it would be
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();

// ── OS stack: scroll inside the pinned run drops one layer per step, then the last step fuses them ──
(() => {
  const sc = document.getElementById('osScroll'), stage = sc.firstElementChild, bar = document.getElementById('osBar'), stack = document.getElementById('osStack');
  const slabs = [...stack.querySelectorAll('.slab')], pills = [...sc.querySelectorAll('.osp')], box = document.getElementById('osCase'), note = document.getElementById('osNote');
  const floor = stack.querySelector('.os-floor'), tileBox = document.getElementById('osTiles');
  // Pinned only where the stage has room for the open pill card and the stack; shorter screens get the static layout.
  const hdr = document.getElementById('hdr'), wide = matchMedia('(min-width: 1024px) and (min-height: 560px)');
  const N = slabs.length + 1, HOLD = .5, GAP = 30, CASED = 26, DROP = 620, RISE = 8;
  const clamp = x => Math.min(1, Math.max(0, x)), out = t => 1 - (1 - t) ** 3, inOut = t => t < .5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
  // Modality keys, 3 x 2 on the plate: the most common novel modalities in the melanoma landscape, plus TIL and oncolytic virus.
  tileBox.innerHTML = ['Monoclonal Antibody', 'Small Molecule', 'Cytokine', 'Vaccine', 'TIL Therapy', 'Oncolytic Virus'].map((t, k) =>
    `<div class="tile" style="left:${(k % 3) * 34}%;top:${Math.floor(k / 3) * 51}%"><i></i><i></i><b>${t}</b></div>`).join('');
  const tiles = [...tileBox.children];
  // The case skin: thin rounded layers laid down one by one as the case drapes. Layers near the lid and the floor
  // are drawn slightly smaller, along a quarter circle, so both edges round off like moulded glass.
  const SKIN = 90, FILLET = 12, FOOT = 18;
  box.insertAdjacentHTML('afterbegin', Array.from({ length: SKIN }, (_, k) =>
    `<i class="skin${k < 2 ? ' lip' : ''}"></i>`).join(''));
  const skins = [...box.querySelectorAll('.skin')];
  // Ring depths and fillet scales depend only on the case height, so they are set when it changes, not every frame.
  let shapedFor = -1;
  const shape = h => {
    if (Math.abs(h - shapedFor) < .01) return;
    shapedFor = h;
    const step = h / SKIN, w = box.offsetWidth, curve = (d, r) => d < r ? r - Math.sqrt(r * r - (r - d) ** 2) : 0;
    skins.forEach((f, k) => {
      const d = (k + 1) * step, inset = Math.max(curve(d, FILLET), curve(h - d, FOOT));
      f.style.transform = `translateZ(${-d}px) scale(${1 - 2 * inset / w})`;
    });
  };

  // p runs 0..N: layer i falls during [i, i + .75] and settles. In the last unit the case lid drops onto the keys,
  // then its walls drape down as milky frost, each layer whitening as the walls pass it; last, the frost clears to glass.
  const paint = p => {
    const L = slabs.length, lidIn = out(clamp((p - L) / .25)), drape = inOut(clamp((p - L - .2) / .3));
    // The frost eases back to a translucent rest by .75 of the last step, and holds there before the pin releases.
    const frost = Math.min(1, drape * 1.6) * (1 - .6 * inOut(clamp((p - L - .5) / .25)));
    const gap = GAP - (GAP - CASED) * lidIn, rise = clamp((p - L + .32) / .3);
    // As the lid lands, the stack lifts off the floor and the lid sits higher, so the case has clear glass above and below the layers.
    const lift = 14 * lidIn, top = lift + (L - 1) * gap + 12.5 + RISE + 11 + 14 * lidIn, front = top - drape * (top + 2);
    slabs.forEach((s, i) => {
      s.style.setProperty('--z', `${lift + i * gap + (1 - out(clamp((p - i) / .75))) * DROP}px`);
      s.style.setProperty('--o', clamp((p - i) * 3.5));
      s.style.setProperty('--cov', i < L - 1 ? out(clamp((p - i - 1) / .75)) : rise);
      // --hid: covered by the case. Anything under the glass stays a shape, never readable text.
      const hid = drape && clamp((lift + i * gap + 12.5 - front) / 20);
      s.style.setProperty('--hid', hid);
      s.style.setProperty('--pk', (.12 + .68 * frost) * hid);
    });
    // The keys appear only once the Modality plate has landed, so its label reads while it falls.
    // Each key eases up in turn over the last third of the step, fading in as it lifts.
    tiles.forEach((t, k) => {
      const r = inOut(clamp((rise - k * .06) / .7));
      t.style.setProperty('--z', `${r * RISE}px`);
      t.style.setProperty('--to', r);
    });
    box.style.setProperty('--cz', `${top + (1 - lidIn) * DROP}px`);
    box.style.setProperty('--o', clamp((p - L) * 4));
    const h = top + 2, step = h / SKIN, reach = drape * h, body = .2 + .8 * frost;
    shape(h);
    skins.forEach((f, k) => {
      const shown = clamp((reach - k * step) / step), o = f.classList.length > 1 ? shown : shown * body;
      if (f._o !== o) f.style.opacity = f._o = o;
    });
    note.style.setProperty('--pk', drape);
    box.style.setProperty('--fr', frost);
    floor.style.opacity = clamp(p * 2);
  };
  // The drawn position follows the scroll position on a critically damped spring (response .45 s): it starts with
  // no jolt, carries its velocity when the scroll reverses, and settles without overshoot at any refresh rate.
  const W0 = 2 * Math.PI / .45;
  let cur = -1, raf = 0, pinned = false, target = 0, shown = 0, vel = 0, last = 0;
  const setStep = n => { if (n === cur) return; cur = n; pills.forEach(b => +b.dataset.step === n ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current')); };
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
  const mode = () => {
    removeEventListener('scroll', pick); cur = -1;
    pinned = wide.matches && !still;
    sc.dataset.mode = pinned ? 'pinned' : 'static';
    if (pinned) { addEventListener('scroll', pick, { passive: true }); pick(); shown = target; vel = 0; draw(); }
    else { pills.forEach(b => b.removeAttribute('aria-current')); paint(N); }
  };
  wide.addEventListener('change', mode);
  addEventListener('resize', () => { shapedFor = -1; if (pinned) pick(); else paint(N); });
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
  const setStep = n => { if (n === cur) return; cur = n; pills.forEach(p => +p.dataset.step === n ? p.setAttribute('aria-current', 'step') : p.removeAttribute('aria-current')); show(n); };
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
