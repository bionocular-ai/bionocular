// The master film: the product intro (intro.js), brand card, the three chapters
// back to back, end card. Order: Question 1 (simple, film.js), Question 2 (complex, q3.js), then
// Survival Intelligence (km.js). A label names each one above where it starts.
// The cards are centred. Each chapter draws itself at its own local time and
// starts and ends on the bare canvas, so the joins need no transition.
// The cards reuse the landing page's lockup (logo + "bio" 800 / "nocular" 500
// in Plus Jakarta Sans) and its tagline. Pure function of T, like every chapter.

import { clamp, sp } from './lib/motion.js';
import { font } from './lib/draw.js';
import * as product from './intro.js';
import * as q2 from './film.js';
import * as q3 from './q3.js';
import * as km from './km.js';

const C = q2.C;
// The intro runs first, on its own white canvas; everything below is timed from its end.
const PRE = product.FILM.dur;
const INTRO = 1.8, OUTRO = 2.1;
const CHAPTERS = [q2, q3, km];
// Bare canvas before a chapter. KM opens on a full-frame sheet, so its label
// needs a beat of its own; the questions' labels ride on their question bar.
const GAPS = [0, 0, 0.7];
// Spans skipped inside a chapter, [local start, length] in seconds, so the demo
// runs 50 s. A skip must sit in a truly static hold (identical frames at both
// ends), or it shows as a jump: only Q3's final pill hold qualifies.
const CUTS = [[], [[19.5, 0.55]], []];
const cutTotal = (i) => CUTS[i].reduce((s, [, len]) => s + len, 0);
const DURS = CHAPTERS.map((c, i) => c.FILM.dur - cutTotal(i));
const STARTS = DURS.map((_, i) => INTRO + GAPS[i] + DURS.slice(0, i).reduce((s, d, k) => s + d + GAPS[k], 0));
const T_OUTRO = STARTS.at(-1) + DURS.at(-1);
// Demo time since the chapter's start -> the chapter's own time.
const local = (i, u) => CUTS[i].reduce((t, [at, len]) => (t >= at ? t + len : t), u);

export const FILM = { title: 'master', w: 1920, h: 1080, dur: +(PRE + T_OUTRO + OUTRO).toFixed(3), bpm: 120 };
const { w: W, h: H } = FILM;

const logo = Object.assign(new Image(), { src: 'assets/logo.svg' });
const LOGO_ASPECT = 127.35 / 148.3; // logo.svg viewBox width / height
export const IMAGES = [...product.IMAGES, ...q2.IMAGES, ...q3.IMAGES, ...km.IMAGES, logo];

export const CUES = [...product.CUES];
const cue = (t, type, gain = 1) => CUES.push({ t: +(PRE + t).toFixed(3), type, gain });
// A chapter's cues move back by the cuts before them; none fall inside a cut.
CHAPTERS.forEach((c, i) => c.CUES.forEach((x) => {
  const before = CUTS[i].filter(([at]) => x.t >= at).reduce((s, [, len]) => s + len, 0);
  cue(x.t - before + STARTS[i], x.type, x.gain);
}));

// ---------------------------------------------------------------- cards
const S = 120; // wordmark size; the logo is 1.05em tall, as on the landing page
const TAGLINE = ['Human-verified oncology intelligence', 'for research and medical teams.'];
const URL = 'bionocular.ai';

cue(0.08, 'whoosh', 0.35);
cue(0.2, 'thump', 0.6);
cue(0.62, 'tick', 0.5);
cue(1.25, 'whoosh', 0.35);
cue(T_OUTRO + 0.2, 'thump', 0.6);
cue(T_OUTRO + 0.52, 'tick', 0.5);
cue(T_OUTRO + 0.85, 'chime', 0.7);

// Draws inside a mask band around baseline `base`, offset by the rise/exit progress.
function masked(g, base, size, pIn, pOut, paint) {
  if (pIn <= 0 || pOut >= 0.99) return;
  const off = (1 - pIn) * size * 1.4 - pOut * size * 1.4;
  g.save();
  g.beginPath();
  g.rect(0, base - size * 1.25, W, size * 1.6);
  g.clip();
  g.translate(0, off);
  paint();
  g.restore();
}

function lockup(g, base, pIn, pOut) {
  masked(g, base, S, pIn, pOut, () => {
    const lh = S * 1.05;
    g.font = font(800, S, 'brand'); const wb = g.measureText('bio').width;
    g.font = font(500, S, 'brand'); const wn = g.measureText('nocular').width;
    const X0 = (W - (lh * LOGO_ASPECT + S * 0.4 + wb + wn)) / 2;
    g.drawImage(logo, X0, base + S * 0.12 - lh, lh * LOGO_ASPECT, lh);
    let x = X0 + lh * LOGO_ASPECT + S * 0.4;
    g.fillStyle = C.ink;
    g.textBaseline = 'alphabetic';
    g.textAlign = 'left';
    g.font = font(800, S, 'brand');
    g.fillText('bio', x, base);
    x += g.measureText('bio').width;
    g.font = font(500, S, 'brand');
    g.fillText('nocular', x, base);
  });
}

function line(g, text, base, size, weight, color, pIn, pOut) {
  masked(g, base, size, pIn, pOut, () => {
    g.font = font(weight, size);
    g.fillStyle = color;
    g.textAlign = 'center';
    g.textBaseline = 'alphabetic';
    g.fillText(text, W / 2, base);
  });
}

function intro(g, t) {
  const out = (d) => sp(t - 1.25 - d, 'snappy');
  lockup(g, 520, sp(t - 0.1, 'heavy'), out(0));
  line(g, TAGLINE[0], 616, 44, 500, C.ink, sp(t - 0.4, 'ui'), out(0.05));
}

function outro(g, t) {
  lockup(g, 430, sp(t - 0.1, 'heavy'), 0);
  line(g, TAGLINE[0], 532, 44, 500, C.ink, sp(t - 0.45, 'ui'), 0);
  line(g, TAGLINE[1], 592, 44, 500, C.muted, sp(t - 0.52, 'ui'), 0);
  line(g, URL, 700, 44, 600, C.primary, sp(t - 0.8, 'ui'), 0);
  // Seafoam underline under the URL, drawn left to right.
  const u = clamp(sp(t - 0.95, 'ui'));
  if (u > 0) {
    g.font = font(600, 44);
    g.fillStyle = C.accent;
    const uw = g.measureText(URL).width; g.fillRect(W / 2 - uw / 2, 716, uw * u, 4);
  }
}

// ---------------------------------------------------------------- chapter labels
// [title, aside, in, out, baseline] in demo time. The question labels sit
// above the question bar (x 160, top 372) and leave as it shrinks to a chip
// (Q.shrink in film.js 0.85, q3.js 0.95). KM's stands alone, centred on the
// bare canvas: it rises as Q3's card finishes clearing and leaves just before
// KM's sheet rises through the frame.
const LABELS = [
  ['Question 1', '(Simple)', STARTS[0] + 0.05, STARTS[0] + 0.85, 336],
  ['Question 2', '(Complex)', STARTS[1] + 0.05, STARTS[1] + 0.95, 336],
  ['Survival Intelligence', '', STARTS[2] - GAPS[2] - 0.08, STARTS[2] - 0.05, 554],
];
cue(LABELS[2][2], 'tick', 0.5);

function labels(g, T) {
  for (const [title, aside, tIn, tOut, y] of LABELS) {
    masked(g, y, 40, sp(T - tIn, 'ui'), sp(T - tOut, 'snappy'), () => {
      g.textAlign = 'left';
      g.textBaseline = 'alphabetic';
      g.font = font(600, 40, 'display');
      g.fillStyle = C.primary;
      const x0 = aside ? 160 : (W - g.measureText(title).width) / 2;
      g.fillText(title, x0, y);
      const x = x0 + g.measureText(title + ' ').width;
      g.font = font(400, 40, 'display');
      g.fillStyle = C.muted;
      g.fillText(aside, x, y);
    });
  }
}

export function draw(g, T) {
  if (T < PRE) return product.draw(g, T);
  T -= PRE;
  const i = STARTS.findIndex((s, k) => T >= s && T < s + DURS[k]);
  if (i >= 0) CHAPTERS[i].draw(g, local(i, T - STARTS[i]));
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
  if (i < 0) {
    g.fillStyle = C.bg;
    g.fillRect(0, 0, W, H);
    if (T < INTRO) intro(g, T);
    else if (T >= T_OUTRO) outro(g, T - T_OUTRO);
  }
  labels(g, T);
}
