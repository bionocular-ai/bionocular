// The master film, v2 (docs/storyboard-v2.md): the packaged demo in the style of a
// caption-led launch film. Captions come into focus word by word on a satin ground
// or the bare canvas; each question is typed into the real agent composer (2x captures,
// one per word typed) under a tight camera; the composer then shrinks into the
// chapter's question chip and the approved chapters play (Question 1 without its
// rivals, Question 2, Survival Intelligence). Captions are the boss's slide copy,
// verbatim (BRIEF Claims). Pure function of T, like every chapter.

import { clamp, sp, easeInOutCubic } from './lib/motion.js';
import { font } from './lib/draw.js';
import * as q2 from './film.js';
import * as q3 from './q3.js';
import * as km from './km.js';
import { satin, focus, lockup, logo } from './lib/cards.js';
import { canvasAsk as composer, CANVAS_ASK as QUESTIONS, CANVAS_A as A, CANVAS_IMAGES } from './joins.js';

const C = q2.C;
const image = (src) => Object.assign(new Image(), { src });


export const IMAGES = [
  logo, ...CANVAS_IMAGES,
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
// The composer on the bare canvas (joins.js): a light line sweeps open into it, the
// question types in, Send, and it shrinks into the chapter's question chip.
for (const key of ['ask1', 'ask3']) {
  const q = QUESTIONS[key === 'ask1' ? 'q1' : 'q3'];
  at(key, A.sweep[0] + 0.02, 'whoosh', 0.35);
  at(key, A.click, 'click', 0.8);
  for (let i = 0; i < q.n; i += 3) at(key, A.type + i * A.step, 'tick', 0.22);
  at(key, A.hover, 'tick', 0.35);
  at(key, A.send, 'click', 0.9);
  at(key, A.morph[0] + 0.02, 'whoosh', 0.35);
}

SCENES.ask1 = (g, t) => composer(g, t, QUESTIONS.q1, q2.CHIP_TEXT);
SCENES.ask3 = (g, t) => composer(g, t, QUESTIONS.q3, q3.CHIP_TEXT);

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
