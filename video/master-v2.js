// The master film, v2 (docs/storyboard-v2.md): the packaged demo in the style of a
// caption-led launch film. Captions come into focus word by word on a satin ground
// or the bare canvas; each question is typed into the real agent composer (2x captures,
// one per word typed) under a tight camera; the composer then shrinks into the
// chapter's question chip and the approved chapters play (Question 1 without its
// rivals, Question 2, Survival Intelligence). Captions are the boss's slide copy,
// verbatim (BRIEF Claims). Pure function of T, like every chapter.

import { clamp, lerp, sp, track, track2, window01, easeInOutCubic } from './lib/motion.js';
import { rrect, risingText, drawCursor, font } from './lib/draw.js';
import * as q2 from './film.js';
import * as q3 from './q3.js';
import * as km from './km.js';
import { satin, focus, lockup, logo } from './lib/cards.js';

const C = q2.C;
const image = (src) => Object.assign(new Image(), { src });

// ---------------------------------------------------------------- the composer captures
// Cropped from the AI Agent page at 1440x900 @2x: the pill and its focus ring, 1592x172.
// The pill is centred on (796, 86) whether it holds one line or two.
const COMPOSER = { w: 1592, h: 172, cx: 796, cy: 86, x0: 16, x1: 1576, r: 50 };
const pillRows = (two) => (two ? [16, 156] : [36, 136]);
const shot = (name) => image(`assets/screens/composer/${name}@2x.png`);
const QUESTIONS = {
  q1: {
    text: 'show me all published efficacy parameters (ORR, DCR and CR) in cutaneous melanoma for active treatments. strict rule: only treatments which are in phase 1 trial.',
    wrapAt: 16, // the word that wraps the question onto a second line
    chip: q2.CHIP_TEXT,
  },
  q3: {
    text: 'provide phase 3 active clinical treatments showing median PFS vs grade3+ Treatment emergent adverse events vs treatment discontinuation due to AEs in metastatic /cutaneous melanoma.',
    wrapAt: 14,
    chip: q3.CHIP_TEXT,
  },
};
for (const [key, q] of Object.entries(QUESTIONS)) {
  q.n = q.text.split(' ').length;
  q.words = Array.from({ length: q.n }, (_, i) => shot(`${key}-${String(i + 1).padStart(2, '0')}`));
  q.hover = shot(`${key}-hover`);
}
const EMPTY = shot('empty');
const EMPTY_FOCUS = shot('empty-focus');

export const IMAGES = [
  logo, EMPTY, EMPTY_FOCUS,
  ...Object.values(QUESTIONS).flatMap((q) => [...q.words, q.hover]),
  ...q2.IMAGES, ...q3.IMAGES, ...km.IMAGES,
];

// ---------------------------------------------------------------- the sequence
// [scene, length in s]. A chapter scene plays its chapter from local time `from`.
const Q1_FROM = 2.35, Q1_BLUR = 6.6; // Q1 starts as Bionocular rises; blurs out before its tally card
const Q3_FROM = 0.95; // just before the rivals rise
const SEQ = [
  ['open', 3.4], ['drown', 3.2], ['stop', 3.7],
  ['ask1', 4.15], ['q1', Q1_BLUR - Q1_FROM + 0.45],
  ['rigor', 3.0], ['numbers', 2.6],
  ['ask3', 4.15], ['q3', q3.FILM.dur - Q3_FROM],
  ['curve', 2.6], ['km', km.FILM.dur],
  ['built', 3.1], ['end', 4.2],
];
const START = {};
let total = 0;
for (const [name, d] of SEQ) { START[name] = total; total += d; }

export const FILM = { title: 'master-v2', w: 1920, h: 1080, dur: +total.toFixed(3), bpm: 120 };
const { w: W, h: H } = FILM;

export const CUES = [];
const cue = (t, type, gain = 1) => CUES.push({ t: +t.toFixed(3), type, gain });

const SIZE = 88;
// One caption line, centred on x, its words in focus one after the other.
function line(g, text, color, base, t, tIn, tOut, size = SIZE) {
  g.font = font(600, size, 'display');
  g.letterSpacing = `${-0.025 * size}px`;
  const words = text.split(' ');
  const space = g.measureText(' ').width;
  const widths = words.map((w) => g.measureText(w).width);
  let x = (W - widths.reduce((a, b) => a + b, 0) - space * (words.length - 1)) / 2;
  words.forEach((word, i) => {
    const p = sp(t - tIn - i * 0.08, 'ui');
    const q = easeInOutCubic((t - tOut - i * 0.03) / 0.4);
    const wx = x;
    focus(g, p, q, () => {
      g.fillStyle = color;
      g.textAlign = 'left';
      g.textBaseline = 'alphabetic';
      g.fillText(word, wx, base);
    });
    x += widths[i] + space;
  });
  g.letterSpacing = '0px';
}

// Baselines for n stacked lines centred on the frame (cap height ~0.72 em).
const stack = (n, i, size = SIZE) => H / 2 + size * 0.36 + (i - (n - 1) / 2) * size * 1.25;

// Two lines, the second replacing the first in place.
function swap(g, t, d, [a, ca], [b, cb]) {
  const mid = d / 2;
  line(g, a, ca, stack(1, 0), t, 0.15, mid - 0.3);
  line(g, b, cb, stack(1, 0), t, mid - 0.05, d - 0.5);
}
// Two lines stacked, the second a beat after the first.
function pair(g, t, d, [a, ca], [b, cb]) {
  line(g, a, ca, stack(2, 0), t, 0.15, d - 0.5);
  line(g, b, cb, stack(2, 1), t, 0.55, d - 0.45);
}

// ---------------------------------------------------------------- caption scenes
const SCENES = {};
const at = (name, t, type, gain) => cue(START[name] + t, type, gain);

SCENES.open = (g, t, d) => swap(g, t, d, ['The evidence is exploding.', C.ink], ["Your tools can't keep up.", C.primary]);
at('open', 0.12, 'whoosh', 0.35);
at('open', 0.2, 'thump', 0.55);
at('open', 1.62, 'whoosh', 0.3);

SCENES.drown = (g, t, d) => pair(g, t, d, ['Teams are drowning in data', C.ink], ["they can't compare", C.ink]);
at('drown', 0.12, 'whoosh', 0.3);
at('drown', 0.52, 'tick', 0.4);

// "Stop comparing headlines." gives way to "Start comparing evidence." with the
// lockup resolving under it; both blur away as the satin settles to the canvas.
SCENES.stop = (g, t, d) => {
  line(g, 'Stop comparing headlines.', C.ink, stack(1, 0), t, 0.15, 1.25);
  line(g, 'Start comparing evidence.', C.primary, stack(2, 0) - 10, t, 1.4, d - 0.75);
  focus(g, sp(t - 2.0, 'heavy'), easeInOutCubic((t - (d - 0.7)) / 0.4), () => lockup(g, stack(2, 1) + 30, 76));
};
at('stop', 0.12, 'whoosh', 0.3);
at('stop', 1.42, 'whoosh', 0.3);
at('stop', 2.05, 'chime', 0.55);

SCENES.rigor = (g, t, d) => pair(g, t, d, ['AI speed.', C.ink], ['Human rigor.', C.primary]);
at('rigor', 0.12, 'whoosh', 0.3);
at('rigor', 0.52, 'tick', 0.4);
SCENES.numbers = (g, t, d) => line(g, "Numbers that can't be compared", C.ink, stack(1, 0), t, 0.15, d - 0.5);
at('numbers', 0.12, 'whoosh', 0.3);
SCENES.curve = (g, t, d) => line(g, 'Headlines miss the curve shape', C.ink, stack(1, 0), t, 0.15, d - 0.5);
at('curve', 0.12, 'whoosh', 0.3);
SCENES.built = (g, t, d) => pair(g, t, d, ['Built for the people who shape', C.ink], ['treatment decisions', C.primary]);
at('built', 0.12, 'whoosh', 0.3);
at('built', 0.52, 'tick', 0.4);

const URL = 'bionocular.ai';
SCENES.end = (g, t) => {
  focus(g, sp(t - 0.15, 'heavy'), 0, () => lockup(g, 520, 120));
  focus(g, sp(t - 0.7, 'ui'), 0, () => {
    g.font = font(600, 48);
    g.fillStyle = C.primary;
    g.textAlign = 'center';
    g.textBaseline = 'alphabetic';
    g.fillText(URL, W / 2, 660);
  });
  // Seafoam underline under the URL, drawn left to right.
  const u = clamp(sp(t - 1.0, 'ui'));
  if (u > 0) {
    g.font = font(600, 48);
    const uw = g.measureText(URL).width;
    g.fillStyle = C.accent;
    g.fillRect(W / 2 - uw / 2, 678, uw * u, 4);
  }
};
at('end', 0.15, 'thump', 0.6);
at('end', 0.72, 'tick', 0.45);
at('end', 1.0, 'chime', 0.7);

// ---------------------------------------------------------------- composer scenes
// A light line sweeps across the frame and opens into the composer. The pointer
// clicks in, the question types in word by word (each frame a real capture),
// the pointer clicks Send, and the composer shrinks into the chapter's question chip.
const A = {
  sweep: [0, 0.5], open: [0.45, 0.9], cursorIn: 0.55, click: 1.1, type: 1.3, step: 0.055,
  toSend: 2.95, hover: 3.18, send: 3.4, morph: [3.55, 4.1],
};
// The camera pushes in on the text as it types, pans with the first line, and
// pulls back to the whole composer when the question wraps.
const wrapT = (q) => A.type + (q.wrapAt - 1) * A.step;
const camera = (t, q) => ({
  s: track(t, [[0, 1.1], [A.click, 1.33], [wrapT(q), 1.0]], 'soft'),
  x: track(t, [[0, COMPOSER.cx], [A.click, 640], [A.type, 768], [wrapT(q), COMPOSER.cx]], 'soft'),
});
const typed = (q, t) => (t < A.type ? 0 : Math.min(q.n, Math.floor((t - A.type) / A.step) + 1));
const toScreen = ({ s, x }, ix, iy) => [W / 2 + (ix - x) * s, H / 2 + (iy - COMPOSER.cy) * s];

for (const key of ['ask1', 'ask3']) {
  const q = QUESTIONS[key === 'ask1' ? 'q1' : 'q3'];
  at(key, A.sweep[0] + 0.02, 'whoosh', 0.35);
  at(key, A.click, 'click', 0.8);
  for (let i = 0; i < q.n; i += 3) at(key, A.type + i * A.step, 'tick', 0.22);
  at(key, A.hover, 'tick', 0.35);
  at(key, A.send, 'click', 0.9);
  at(key, A.morph[0] + 0.02, 'whoosh', 0.35);
}

// The chip each chapter shows its question in (film.js / q3.js question()).
function chipRect(g, text) {
  g.font = font(400, 18);
  return { x: 120, y: 48, w: g.measureText(text).width + 48, h: 52, r: 26 };
}

function composer(g, t, q) {
  const cam = camera(t, q);
  const { s } = cam;
  const k = typed(q, t);
  const two = t >= A.hover || k >= q.wrapAt;
  const img = t >= A.hover ? q.hover : k > 0 ? q.words[k - 1] : t >= A.click ? EMPTY_FOCUS : EMPTY;
  const [r0, r1] = pillRows(two);
  const [px0, py0] = toScreen(cam, COMPOSER.x0, r0);
  const [px1, py1] = toScreen(cam, COMPOSER.x1, r1);
  const pill = { x: px0, y: py0, w: px1 - px0, h: py1 - py0, r: COMPOSER.r * s };

  // The sweep: a teal line drawn left to right with a light at its head.
  const sw = easeInOutCubic((t - A.sweep[0]) / (A.sweep[1] - A.sweep[0]));
  const op = easeInOutCubic((t - A.open[0]) / (A.open[1] - A.open[0]));
  if (sw > 0 && op < 1) {
    const x = lerp(pill.x, pill.x + pill.w, sw);
    g.save();
    g.globalAlpha = 1 - op;
    g.fillStyle = C.primary;
    g.fillRect(pill.x, H / 2 - 1, x - pill.x, 2);
    const head = g.createRadialGradient(x, H / 2, 0, x, H / 2, 90);
    head.addColorStop(0, 'rgba(255, 255, 255, 1)');
    head.addColorStop(0.25, 'rgba(122, 193, 162, 0.55)');
    head.addColorStop(1, 'rgba(122, 193, 162, 0)');
    g.fillStyle = head;
    g.fillRect(x - 90, H / 2 - 90, 180, 180);
    g.restore();
  }
  if (op <= 0) return;

  // The line opens top and bottom into the pill; the capture shows through.
  const m = morphP(t);
  const chip = chipRect(g, q.chip);
  const oh = pill.h * op;
  const r = {
    x: lerp(pill.x, chip.x, m), y: lerp(H / 2 - oh / 2, chip.y, m),
    w: lerp(pill.w, chip.w, m), h: lerp(oh, chip.h, m), r: lerp(Math.min(pill.r, oh / 2), chip.r, m),
  };
  g.save();
  g.shadowColor = `rgba(16, 43, 54, ${0.06 * op})`;
  g.shadowBlur = 30;
  g.shadowOffsetY = 8;
  g.fillStyle = C.sheet;
  rrect(g, r.x, r.y, r.w, r.h, r.r);
  g.fill();
  g.restore();
  const content = op * (1 - clamp((t - A.morph[0]) / 0.15));
  if (content > 0) {
    g.save();
    // The capture is clipped to the pill and its focus ring, above the suggestion chips.
    rrect(g, r.x - 8 * s, r.y - 8 * s, r.w + 16 * s, r.h + 16 * s, r.r + 8 * s);
    g.clip();
    g.globalAlpha = content;
    const [ix, iy] = toScreen(cam, 0, 0);
    g.drawImage(img, ix, iy + (m * (chip.y - pill.y)), COMPOSER.w * s, COMPOSER.h * s);
    g.restore();
  }
  if (m > 0 || op < 1) {
    g.strokeStyle = C.line;
    g.lineWidth = 1.5;
    rrect(g, r.x, r.y, r.w, r.h, r.r);
    g.stroke();
  }
  if (m > 0.55) {
    g.font = font(400, 18);
    risingText(g, q.chip, r.x + 24, r.y + 32, sp(t - A.morph[0] - 0.32, 'snappy'), 0, 18, C.ink);
  }

  // The pointer: in from the lower right, clicks the field, then Send.
  const field = toScreen(cam, 560, COMPOSER.cy);
  const send = toScreen(cam, 1526, two ? 106 : COMPOSER.cy);
  const start = [W / 2 + 560, H / 2 + 380];
  const below = toScreen(cam, 700, COMPOSER.cy + 150);
  const [cx, cy] = track2(t, [[0, start], [A.cursorIn, field], [A.click + 0.2, below], [A.toSend, send]], 'ui');
  const press = Math.max(0, 1 - Math.abs(t - A.click) / 0.12, 1 - Math.abs(t - A.send) / 0.12);
  drawCursor(g, cx, cy, press, window01(t, A.cursorIn, A.morph[0] + 0.15, 0.15, 0.15));
}
// The content fades first (0.15 s), then the pill moves.
const morphP = (t) => easeInOutCubic((t - A.morph[0] - 0.1) / (A.morph[1] - A.morph[0] - 0.1));
SCENES.ask1 = (g, t) => composer(g, t, QUESTIONS.q1);
SCENES.ask3 = (g, t) => composer(g, t, QUESTIONS.q3);

// ---------------------------------------------------------------- chapter scenes
// The chapter frame, blurred and faded to the canvas by p.
let buf;
function blurOut(g, p) {
  if (p <= 0) return;
  buf ??= Object.assign(document.createElement('canvas'), { width: W, height: H });
  const b = buf.getContext('2d');
  b.clearRect(0, 0, W, H);
  b.drawImage(g.canvas, 0, 0);
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  g.filter = `blur(${(22 * p).toFixed(2)}px)`;
  g.globalAlpha = 1 - p;
  g.drawImage(buf, 0, 0);
  g.filter = 'none';
  g.globalAlpha = 1;
}

SCENES.q1 = (g, t) => {
  q2.draw(g, Math.min(Q1_FROM + t, 6.94), { bar: false, rivals: false });
  blurOut(g, easeInOutCubic((Q1_FROM + t - Q1_BLUR) / 0.45));
};
SCENES.q3 = (g, t) => q3.draw(g, Q3_FROM + t, { bar: false });
SCENES.km = (g, t) => km.draw(g, t);

// Each chapter's own cues, inside the span it plays.
const chapterCues = (name, ch, from, to) => ch.CUES
  .filter((x) => x.t >= from && x.t < to)
  .forEach((x) => at(name, x.t - from, x.type, x.gain));
chapterCues('q1', q2, Q1_FROM, Q1_BLUR + 0.2);
chapterCues('q3', q3, Q3_FROM, q3.FILM.dur);
chapterCues('km', km, 0, km.FILM.dur);
CUES.sort((a, b) => a.t - b.t);

// ---------------------------------------------------------------- frame
// The satin carries the opening three captions and the end card; it settles to the
// bare canvas as the opening's lockup blurs away.
const satinAlpha = (T) => {
  const outAt = START.stop + SEQ[2][1] - 0.7;
  if (T < START.end) return 1 - easeInOutCubic((T - outAt) / 0.6);
  return easeInOutCubic((T - START.end) / 0.5);
};

export function draw(g, T) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
  g.mac = true; // the macOS pointer in every chapter
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  let i = SEQ.findIndex(([name, d]) => T >= START[name] && T < START[name] + d);
  if (i < 0) i = SEQ.length - 1;
  const [name, d] = SEQ[i];
  if (!['q1', 'q3', 'km'].includes(name)) satin(g, T, satinAlpha(T));
  SCENES[name](g, T - START[name], d);
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
}
