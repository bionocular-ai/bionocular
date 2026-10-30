// The master film (docs/storyboard-master.md): brand card, the product intro (intro.js),
// sign-in, the dashboard tour (pages.js), Question 1 (simple, film.js), Question 2 (complex,
// q3.js), KM Curves Intelligence (km.js), end card. One app window runs from sign-in to the
// last chapter and every jump is a click inside it (joins.js): the login card grows into the
// app, the AI Agent rail opens Question 1's composer, Question 2 is typed as a follow-up under
// Question 1's answer, and the KM rail icon opens the KM page. Each chapter draws itself at
// its own local time, from where the join hands over to where the next one takes it.
// The cards use the landing page's lockup and tagline on the satin ground, and come into
// focus as the captions do. Pure function of T, like every chapter.

import { clamp, sp, easeInOutCubic } from './lib/motion.js';
import { font } from './lib/draw.js';
import { satin, focus, lockup, logo } from './lib/cards.js';
import * as product from './intro.js';
import * as pages from './pages.js';
import * as joins from './joins.js';
import * as q2 from './film.js';
import * as q3 from './q3.js';
import * as km from './km.js';

const C = q2.C;
// Where each chapter is picked up and left, in its own time.
const Q1_FROM = 0.85, Q1_TO = 8.4; // film.js: from its chip (the rivals rise at 0.9) to the settled tally card
const Q2_FROM = 0.95, Q2_TO = 19.5; // q3.js: from its chip to the cross-check seal, before its last hold
const KM_TO = 16.55; // km.js: through the upload caption, before its own clear
const INTRO_TO = 23.45; // intro.js: its diagram slide has lifted away; the login rises into the white
// [scene, length in s]
const SEQ = [
  ['brand', 1.56], ['intro', INTRO_TO], ['login', joins.LOGIN_DUR],
  ['tour', pages.T_DONE - joins.TOUR_FROM], ['toQ1', joins.TO_Q1_DUR], ['q1', Q1_TO - Q1_FROM],
  ['toQ2', joins.TO_Q2_DUR], ['q2', Q2_TO - Q2_FROM], ['toKM', joins.TO_KM_DUR], ['km', KM_TO],
  ['end', 3.4],
];
const START = {};
let total = 0;
for (const [name, d] of SEQ) { START[name] = total; total += d; }

export const FILM = { title: 'master', w: 1920, h: 1080, dur: +total.toFixed(3), bpm: 120 };
const { w: W, h: H } = FILM;

export const IMAGES = [...product.IMAGES, ...pages.IMAGES, ...joins.IMAGES, ...q2.IMAGES, ...q3.IMAGES, ...km.IMAGES, logo];

export const CUES = [];
const at = (name, t, type, gain = 1) => CUES.push({ t: +(START[name] + t).toFixed(3), type, gain });
// A chapter's own cues inside the span it plays, moved to where it plays.
const chapterCues = (name, ch, from, to) => ch.CUES.filter((x) => x.t >= from && x.t < to).forEach((x) => at(name, x.t - from, x.type, x.gain));
chapterCues('intro', product, 0, INTRO_TO);
chapterCues('tour', pages, joins.TOUR_FROM, pages.T_DONE);
chapterCues('q1', q2, Q1_FROM, Q1_TO);
chapterCues('q2', q3, Q2_FROM, Q2_TO);
chapterCues('km', km, 0, KM_TO);
joins.CUES.forEach((x) => at(x.beat, x.t, x.type, x.gain));

// ---------------------------------------------------------------- cards
const TAGLINE = 'Human-verified oncology intelligence';
const URL = 'bionocular.ai';

function centred(g, text, base, size, weight, color) {
  g.font = font(weight, size);
  g.fillStyle = color;
  g.textAlign = 'center';
  g.textBaseline = 'alphabetic';
  g.fillText(text, W / 2, base);
}

// The lockup and tagline come into focus on the satin and leave the same way; the ground
// eases to the intro's white as they go, so the cut to the first slide has no flash.
function brand(g, t) {
  satin(g, t, 1);
  const out = (d) => easeInOutCubic((t - 1.15 - d) / 0.35);
  focus(g, sp(t - 0.1, 'heavy'), out(0), () => lockup(g, 520, 120));
  focus(g, sp(t - 0.4, 'ui'), out(0.05), () => centred(g, TAGLINE, 616, 44, 500, C.ink));
  g.globalAlpha = easeInOutCubic((t - 1.2) / 0.36);
  g.fillStyle = '#FFFFFF';
  g.fillRect(0, 0, W, H);
  g.globalAlpha = 1;
}
at('brand', 0.08, 'whoosh', 0.35);
at('brand', 0.2, 'thump', 0.6);
at('brand', 0.62, 'tick', 0.5);
at('brand', 1.25, 'whoosh', 0.35);

// The KM sheet shrinks back toward the centre and blurs into the satin as the lockup
// comes into focus in its place: the app goes back into the logo it came from.
let buf;
function end(g, t) {
  const e = easeInOutCubic(t / 0.8);
  if (e < 1) {
    buf ??= Object.assign(document.createElement('canvas'), { width: W, height: H });
    const b = buf.getContext('2d');
    b.mac = true;
    km.draw(b, KM_TO, { rise: false });
    const s = 1 - 0.4 * sp(t, 'ui');
    g.save();
    g.globalAlpha = 1 - e;
    g.filter = `blur(${(14 * e).toFixed(2)}px)`;
    g.translate(W / 2, H / 2);
    g.scale(s, s);
    g.drawImage(buf, -W / 2, -H / 2);
    g.restore();
  }
  satin(g, START.end + t, easeInOutCubic((t - 0.1) / 0.6));
  focus(g, sp(t - 0.45, 'heavy'), 0, () => lockup(g, 490, 120));
  focus(g, sp(t - 0.8, 'ui'), 0, () => centred(g, TAGLINE, 592, 44, 500, C.ink));
  focus(g, sp(t - 1.1, 'ui'), 0, () => centred(g, URL, 700, 44, 600, C.primary));
  // Seafoam underline under the URL, drawn left to right.
  const u = clamp(sp(t - 1.3, 'ui'));
  if (u > 0) {
    g.font = font(600, 44);
    g.fillStyle = C.accent;
    const uw = g.measureText(URL).width;
    g.fillRect(W / 2 - uw / 2, 716, uw * u, 4);
  }
}
at('end', 0.05, 'whoosh', 0.4);
at('end', 0.5, 'thump', 0.6);
at('end', 0.8, 'tick', 0.5);
at('end', 1.2, 'chime', 0.7);
CUES.sort((a, b) => a.t - b.t);

// ---------------------------------------------------------------- scenes
const SCENES = {
  brand,
  intro: (g, t) => product.draw(g, t),
  login: (g, t) => joins.login(g, t),
  tour: (g, t) => pages.draw(g, joins.TOUR_FROM + t, { rise: false }),
  toQ1: (g, t) => joins.toQ1(g, t, q2.CHIP_TEXT),
  q1: (g, t) => q2.draw(g, Q1_FROM + t, { bar: false }),
  toQ2: (g, t) => joins.toQ2(g, t, q3.CHIP_TEXT, (x) => q2.draw(x, Q1_TO + Math.min(t, 0.2), { bar: false })),
  q2: (g, t) => q3.draw(g, Q2_FROM + t, { bar: false }),
  toKM: (g, t) => joins.toKM(g, t, (x) => q3.draw(x, Q2_TO, { bar: false })),
  km: (g, t) => { km.draw(g, t, { rise: false }); joins.kmWipe(g, t); },
  end,
};

export function draw(g, T) {
  g.mac = true; // the macOS pointer in every chapter
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  let i = SEQ.findIndex(([name, d]) => T >= START[name] && T < START[name] + d);
  if (i < 0) i = SEQ.length - 1;
  const [name] = SEQ[i];
  SCENES[name](g, T - START[name]);
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
}
