// The master film's joins (docs/storyboard-master.md): one app window from sign-in to the
// last chapter, every jump a click inside it. Sign-in on the real /login page, the card
// growing into the app sheet; the AI Agent rail click into Question 1, typed into the real
// composer; Question 2 typed as a follow-up under Question 1's answer; the KM rail click.
// Every screen is a 2x capture from scripts/capture-agent.sh, all coordinates its CSS px.
// Each beat is a pure function of its own local time t; the master places them.

import { clamp, lerp, sp, track, track2, window01, easeInOutCubic } from './lib/motion.js';
import { rrect, risingText, drawCursor, font } from './lib/draw.js';
import { focus } from './lib/cards.js';
import { C } from './film.js';
import * as pages from './pages.js';

const W = 1920, H = 1080;
const image = (name) => Object.assign(new Image(), { src: `assets/screens/agent/${name}@2x.png` });

const LOGIN = {
  empty: image('login-empty'),
  email: [3, 6, 9, 12, 15, 18].map((n) => image(`login-email-${n}`)), // demo@bionocular.ai, 3 letters a frame
  pass: [3, 6, 10].map((n) => image(`login-pass-${n}`)),
  hover: image('login-hover'),
  card: [496, 190, 448, 520], // radius 16
  email1: [528, 406, 384, 48],
  pass1: [528, 478, 384, 48],
  button: [528, 550, 384, 48],
};
const APP = {
  effHover: image('eff-agent-hover'), // the Efficacy hub at 1440x1500, AI Agent hovered on the rail
  empty: image('agent-empty'),
  q1Thread: image('q1-thread'), // Question 1's answer (2026-10-08) at its foot
  q2Thread: image('q2-thread'),
  kmHover: image('q2-thread-km-hover'),
};
// Typing changes only a band of the frame; q1c/ and q2c/ hold those bands, one per word.
const band = (dir, n) => Array.from({ length: n }, (_, i) => image(`${dir}c/${String(i + 1).padStart(2, '0')}`));
const ASK = {
  q1: {
    words: band('q1', 27), hover: image('q1c/hover'), base: APP.empty,
    band: [376, 340, 792, 192],
    pill: [[382, 419, 780, 50], [382, 409, 780, 70]], // one line, then two from word 15 (it grows both ways)
    wrap: 15, send: [[1119, 426, 36, 36], [1119, 436, 36, 36]],
  },
  q2: {
    words: band('q2', 25), hover: image('q2c/hover'), base: APP.q1Thread,
    band: [224, 770, 1096, 126],
    pill: [[232, 838, 1080, 50], [232, 818, 1080, 70]], // under the thread it grows upward, from word 19
    wrap: 19, send: [[1269, 845, 36, 36], [1269, 845, 36, 36]],
  },
};
export const IMAGES = [...Object.values(LOGIN).filter((v) => v instanceof Image), ...LOGIN.email, ...LOGIN.pass,
  ...Object.values(APP), ...Object.values(ASK).flatMap((q) => [...q.words, q.hover])];

export const CUES = []; // in each beat's local time, keyed by beat: { beat, t, type, gain }
const cue = (beat, t, type, gain = 1) => CUES.push({ beat, t: +t.toFixed(3), type, gain });

const center = ([x, y, w, h], dx = 0.5, dy = 0.5) => [x + w * dx, y + h * dy];

// ---------------------------------------------------------------- shared pieces
// Paints into an offscreen frame and lays it down blurred and faded (b 0 -> 1 is out of focus).
let buf;
function blurred(g, b, alpha, paint) {
  if (alpha <= 0) return;
  buf ??= Object.assign(document.createElement('canvas'), { width: W, height: H });
  const x = buf.getContext('2d');
  x.setTransform(1, 0, 0, 1, 0, 0);
  x.globalAlpha = 1;
  x.filter = 'none';
  x.clearRect(0, 0, W, H);
  x.mac = true;
  paint(x);
  g.save();
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.filter = b > 0.01 ? `blur(${(22 * b).toFixed(2)}px)` : 'none';
  g.globalAlpha = alpha;
  g.drawImage(buf, 0, 0);
  g.restore();
}

// "Question 1 (Simple)": the chapter's name comes into focus top left, as on a title card,
// over a wash of the canvas so it never sits on the page's own text.
function label(g, title, aside, p, q) {
  const a = clamp(p) * (1 - clamp(q));
  if (a > 0) {
    const wash = g.createLinearGradient(0, 0, 0, 300);
    wash.addColorStop(0, 'rgba(247, 250, 249, 0.97)');
    wash.addColorStop(0.55, 'rgba(247, 250, 249, 0.9)');
    wash.addColorStop(1, 'rgba(247, 250, 249, 0)');
    g.save();
    g.globalAlpha = a;
    g.fillStyle = wash;
    g.fillRect(0, 0, W, 300);
    g.restore();
  }
  focus(g, p, q, () => {
    g.textAlign = 'left';
    g.textBaseline = 'alphabetic';
    g.font = font(600, 48, 'display');
    g.letterSpacing = '-1.2px';
    g.fillStyle = C.primary;
    g.fillText(title, 160, 170);
    const x = 160 + g.measureText(title + ' ').width;
    g.font = font(400, 48, 'display');
    g.fillStyle = C.muted;
    g.fillText(aside, x, 170);
    g.letterSpacing = '0px';
  });
}

// The chapters' question chip (film.js / q3.js question()), in screen px.
function chipRect(g, text) {
  g.font = font(400, 18);
  return { x: 120, y: 48, w: g.measureText(text).width + 48, h: 52, r: 26 };
}

// The sent composer shrinks into the chapter's question chip: the content leaves first
// (0.12 s), then the pill moves, and the chip's text rises once it is nearly there.
function morph(g, t, from, chipText) {
  const m = easeInOutCubic((t - 0.1) / 0.45);
  const chip = chipRect(g, chipText);
  const r = {
    x: lerp(from.x, chip.x, m), y: lerp(from.y, chip.y, m),
    w: lerp(from.w, chip.w, m), h: lerp(from.h, chip.h, m), r: lerp(from.r, chip.r, m),
  };
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.06)';
  g.shadowBlur = 30;
  g.shadowOffsetY = 8;
  g.fillStyle = C.sheet;
  rrect(g, r.x, r.y, r.w, r.h, r.r);
  g.fill();
  g.restore();
  g.strokeStyle = C.line;
  g.lineWidth = 1.5;
  rrect(g, r.x, r.y, r.w, r.h, r.r);
  g.stroke();
  if (m > 0.55) {
    g.font = font(400, 18);
    risingText(g, chipText, r.x + 24, r.y + 32, sp(t - 0.42, 'snappy'), 0, 18, C.ink);
  }
  return m;
}

// ---------------------------------------------------------------- sign in
// The intro's last slide clears on white; the /login page rises from below as a panel,
// demo@bionocular.ai types in, the password fills, the pointer clicks Login, and the white
// card grows into the app sheet (Trial Updates, the tour's first frame) while the teal
// ground falls away to the canvas.
const L = { email: 0.55, step: 0.15, field2: 1.5, pass: 1.6, hover: 2.2, click: 2.45, grow: [2.6, 3.5] };
export const LOGIN_DUR = 3.6;
export const TOUR_FROM = 0.6; // the tour's local time the grown card lands on
cue('login', 0.02, 'whoosh', 0.4);
cue('login', 0.32, 'thump', 0.5);
[...LOGIN.email.keys()].forEach((i) => cue('login', L.email + i * L.step, 'tick', 0.22));
cue('login', L.field2 - 0.05, 'click', 0.6);
[0, 1, 2].forEach((i) => cue('login', L.pass + i * L.step, 'tick', 0.22));
cue('login', L.hover, 'tick', 0.35);
cue('login', L.click, 'click', 0.9);
cue('login', L.grow[0] + 0.02, 'whoosh', 0.45);

// The login page fills the frame; its camera leans in a little as the card is filled in.
const loginCam = (t) => ({ k: track(t, [[0, 1.42], [L.email - 0.2, 1.55]], 'heavy'), cx: 720, cy: track(t, [[0, 450], [L.email - 0.2, 462]], 'heavy') });
const loginScreen = (c, [x, y]) => [W / 2 + (x - c.cx) * c.k, H / 2 + (y - c.cy) * c.k];

function loginShot(t) {
  if (t >= L.hover) return LOGIN.hover;
  for (let i = LOGIN.pass.length - 1; i >= 0; i--) if (t >= L.pass + i * L.step) return LOGIN.pass[i];
  for (let i = LOGIN.email.length - 1; i >= 0; i--) if (t >= L.email + i * L.step) return LOGIN.email[i];
  return LOGIN.empty;
}

export function login(g, t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  const c = loginCam(t);
  const m = clamp(sp(t - L.grow[0], 'ui'));
  const rise = (1 - sp(t, 'ui')) * H;
  // The teal ground, card and all, rises as one panel and falls away as the card grows.
  g.save();
  g.globalAlpha = 1 - clamp(m * 1.4);
  g.translate(0, rise);
  const [x0, y0] = loginScreen(c, [0, 0]);
  g.drawImage(loginShot(t), x0, y0, 1440 * c.k, 900 * c.k);
  g.restore();

  if (t >= L.grow[0]) {
    // The card's white grows into the sheet the tour opens on; Trial Updates resolves inside it.
    const tc = pages.camAt(TOUR_FROM);
    const [cx0, cy0] = loginScreen(c, LOGIN.card);
    const card = { x: cx0, y: cy0, w: LOGIN.card[2] * c.k, h: LOGIN.card[3] * c.k, r: 16 * c.k };
    const [sx, sy] = pages.onScreen(tc, [0, 0]);
    const S = pages.B * tc.z;
    const target = { x: sx, y: sy, w: pages.VIEW.w * S, h: pages.VIEW.h * S, r: 14 * S };
    const r = Object.fromEntries(Object.keys(card).map((k) => [k, lerp(card[k], target[k], m)]));
    g.save();
    g.shadowColor = `rgba(16, 43, 54, ${0.1 * m})`;
    g.shadowBlur = 48;
    g.shadowOffsetY = 14;
    g.fillStyle = C.sheet;
    rrect(g, r.x, r.y, r.w, r.h, r.r);
    g.fill();
    g.restore();
    g.save();
    rrect(g, r.x, r.y, r.w, r.h, r.r);
    g.clip();
    blurred(g, 0, clamp((m - 0.25) / 0.5), (x) => pages.draw(x, TOUR_FROM, { rise: false }));
    g.restore();
  }

  // The pointer: in from below, clicks the email field, the password field, then Login.
  const [px, py] = track2(t, [
    [0, [1000, 760]], [0.3, center(LOGIN.email1, 0.7)], [L.field2 - 0.3, center(LOGIN.pass1, 0.7)],
    [L.hover - 0.25, center(LOGIN.button, 0.55)],
  ], 'snappy');
  const press = Math.max(0, ...[0.45, L.field2 - 0.05, L.click].map((t0) => 1 - Math.abs(t - t0) / 0.14));
  const [sx, sy] = loginScreen(c, [px, py]);
  drawCursor(g, sx, sy + rise, press, window01(t, 0.25, L.grow[0] + 0.1, 0.12, 0.15));
}

// ---------------------------------------------------------------- the agent composer
// One question typed into the real composer, a capture per word: the band for the words
// so far over the page at rest, then the Send hover.
const STEP = 0.07;
function typedBand(g, q, t, tType, tHover) {
  if (t >= tHover) return g.drawImage(q.hover, ...q.band);
  const k = t < tType ? 0 : Math.min(q.words.length, Math.floor((t - tType) / STEP) + 1);
  if (k > 0) g.drawImage(q.words[k - 1], ...q.band);
}
const twoLines = (q, t, tType, tHover) => t >= tHover || (t >= tType && Math.floor((t - tType) / STEP) + 1 >= q.wrap);
const typeEnd = (q, tType) => tType + (q.words.length - 1) * STEP;

// The pill in screen px, for camera c.
function pillOnScreen(c, [x, y, w, h]) {
  const [sx, sy] = pages.onScreen(c, [x, y]);
  const S = pages.B * c.z;
  return { x: sx, y: sy, w: w * S, h: h * S, r: (h / 2) * S };
}

// A sheet beat's camera, cursor and frame. keys: camera [t, [cx, cy, z]]; the sheet paints
// itself with paint(px, t); after `send` the pill morphs into the chip over the blurred sheet.
function askBeat(g, t, { q, keys, paint, tType, tHover, tSend, chip, title, aside, labelIn, path, presses, focusIn }) {
  const v = (i) => track(t, keys.map(([k, p]) => [k, p[i]]), 'heavy');
  const c = { cx: v(0), cy: v(1), z: v(2) };
  const tm = t - (tSend + 0.15);
  const out = clamp(easeInOutCubic(tm / 0.45));
  const into = focusIn ? focusIn(t) : 1;
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  if (focusIn) focusIn.under?.(g, t);
  const two = twoLines(q, t, tType, tHover);
  const pill = q.pill[two ? 1 : 0];
  blurred(g, Math.max(out, 1 - into), into * (1 - out), (x) => {
    x.fillStyle = C.bg;
    x.fillRect(0, 0, W, H);
    pages.sheet(x, c, (px) => {
      paint(x, t, px);
      if (t >= tType - 0.4) typedBand(x, q, t, tType, tHover);
      // Once sent, the composer leaves the page: it is the chip now.
      if (tm >= 0) {
        x.fillStyle = C.bg;
        rrect(x, pill[0] - 8, pill[1] - 8, pill[2] + 16, pill[3] + 16, pill[3] / 2 + 8);
        x.fill();
      }
    });
  });
  label(g, title, aside, sp(t - labelIn, 'ui') * into, easeInOutCubic((tm + 0.1) / 0.35));
  if (tm >= 0) morph(g, tm, pillOnScreen(c, pill), chip);

  const [px, py] = track2(t, path(two), 'snappy');
  const press = Math.max(0, ...presses.map((t0) => 1 - Math.abs(t - t0) / 0.14));
  const [sx, sy] = pages.onScreen(c, [px, py]);
  drawCursor(g, sx, sy, press, window01(t, 0.05, tSend + 0.25, 0.15, 0.15) * into);
}

// ---------------------------------------------------------------- Question 1
// The tour has just built the Efficacy bars. The pointer drops to the rail, AI Agent takes
// its hover (the rail opens), click: the agent page wipes in like every tour page. The
// camera pushes in on the composer, Question 1 types in, Send, and the composer shrinks
// into Question 1's chip as the app falls back out of focus.
const A1 = { hover: 0.55, click: 0.95, field: 1.75, type: 1.95 };
A1.hoverSend = typeEnd(ASK.q1, A1.type) + 0.3;
A1.send = A1.hoverSend + 0.22;
export const TO_Q1_DUR = A1.send + 0.15 + 0.6;
cue('toQ1', 0.05, 'whoosh', 0.25);
cue('toQ1', A1.hover, 'tick', 0.35);
cue('toQ1', A1.click, 'click', 0.85);
cue('toQ1', A1.click + 0.05, 'whoosh', 0.35);
cue('toQ1', A1.field, 'click', 0.6);
for (let i = 0; i < ASK.q1.words.length; i += 3) cue('toQ1', A1.type + i * STEP, 'tick', 0.2);
cue('toQ1', A1.hoverSend, 'tick', 0.35);
cue('toQ1', A1.send, 'click', 0.9);
cue('toQ1', A1.send + 0.17, 'whoosh', 0.35);

// The rail opens over the hub: the hover capture's rail, revealed from the left.
function effHover(g, p) {
  if (p <= 0.001) return;
  pages.clipped(g, [0, 56, 56 + 206 * clamp(p), 844], () => pages.blit(g, APP.effHover, [0, 56, 262, 844]));
}

export function toQ1(g, t, chipText) {
  const c0 = pages.camAt(pages.T_DONE);
  askBeat(g, t, {
    q: ASK.q1, chip: chipText, title: 'Question 1', aside: '(Simple)', labelIn: 1.35,
    tType: A1.type, tHover: A1.hoverSend, tSend: A1.send,
    keys: [[0, [c0.cx, c0.cy, c0.z]], [0.1, [560, 420, 1.15]], [A1.click + 0.25, [772, 440, 1.3]], [A1.field - 0.2, [772, 448, 1.8]]],
    paint: (x, tt) => {
      const open = sp(tt - A1.hover, 'snappy') - sp(tt - A1.click, 'snappy');
      const from = (y) => { pages.efficacyDone(y); effHover(y, open); };
      if (tt < A1.click) return from(x);
      pages.pageIn(x, from, APP.empty, A1.click, tt);
    },
    path: (two) => [
      [0, [1100, 700]], [0.1, [1100, 700]], [A1.hover - 0.3, pages.RAIL.agent], [A1.click + 0.3, [700, 600]],
      [A1.field - 0.3, [560, 444]], [A1.type + 0.15, [760, 560]], [A1.hoverSend - 0.25, center(ASK.q1.send[1])],
    ],
    presses: [A1.click, A1.field, A1.send],
  });
}

// ---------------------------------------------------------------- Question 2
// Question 1's tally card blurs away and Question 1's own answer comes back into focus in
// the app, at its foot. The camera pushes in on the follow-up composer, Question 2 types in,
// Send, and the composer shrinks into Question 2's chip.
const A2 = { field: 0.95, type: 1.15 };
A2.hoverSend = typeEnd(ASK.q2, A2.type) + 0.3;
A2.send = A2.hoverSend + 0.22;
export const TO_Q2_DUR = A2.send + 0.15 + 0.6;
cue('toQ2', 0.05, 'whoosh', 0.35);
cue('toQ2', A2.field, 'click', 0.6);
for (let i = 0; i < ASK.q2.words.length; i += 3) cue('toQ2', A2.type + i * STEP, 'tick', 0.2);
cue('toQ2', A2.hoverSend, 'tick', 0.35);
cue('toQ2', A2.send, 'click', 0.9);
cue('toQ2', A2.send + 0.17, 'whoosh', 0.35);

// prev(g): the chapter frame being left, which blurs out as the app comes into focus.
const pull = (prev) => Object.assign((t) => easeInOutCubic(t / 0.6), {
  under: (g, t) => blurred(g, easeInOutCubic(t / 0.6), 1 - easeInOutCubic((t - 0.1) / 0.5), prev),
});

export function toQ2(g, t, chipText, prev) {
  askBeat(g, t, {
    q: ASK.q2, chip: chipText, title: 'Question 2', aside: '(Complex)', labelIn: 0.55,
    tType: A2.type, tHover: A2.hoverSend, tSend: A2.send, focusIn: pull(prev),
    keys: [[0, [720, 520, 1.12]], [0.35, [772, 700, 1.5]]],
    paint: (x) => pages.view(x, APP.q1Thread),
    path: () => [
      [0, [980, 640]], [A2.field - 0.3, [520, 863]], [A2.type + 0.15, [880, 760]], [A2.hoverSend - 0.25, center(ASK.q2.send[1])],
    ],
    presses: [A2.field, A2.send],
  });
}

// ---------------------------------------------------------------- into KM
// Question 2's tally card blurs away to its answer in the app; the pointer clicks the KM
// Curves Intelligence rail icon and the KM page wipes in (km.js, its sheet in place, at the
// camera it opens on).
const K = { hover: 0.8, click: 1.15 };
export const TO_KM_DUR = K.click;
export const KM_CAM = { cx: 720, cy: 500, z: 1.15 }; // km.js cam(0)
cue('toKM', 0.05, 'whoosh', 0.35);
cue('toKM', K.hover, 'tick', 0.35);
cue('toKM', K.click, 'click', 0.85);
cue('toKM', K.click + 0.05, 'whoosh', 0.35);

export function toKM(g, t, prev) {
  const into = easeInOutCubic(t / 0.6);
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  blurred(g, into, 1 - easeInOutCubic((t - 0.1) / 0.5), prev);
  blurred(g, 1 - into, into, (x) => {
    x.fillStyle = C.bg;
    x.fillRect(0, 0, W, H);
    pages.sheet(x, KM_CAM, () => {
      pages.view(x, APP.q2Thread);
      pages.railHover(x, APP.kmHover, K.hover, t);
    });
  });
  const [px, py] = track2(t, [[0, [900, 640]], [K.hover - 0.3, pages.RAIL.km]], 'snappy');
  const [sx, sy] = pages.onScreen(KM_CAM, [px, py]);
  drawCursor(g, sx, sy, clamp(1 - Math.abs(t - K.click) / 0.14), window01(t, 0.1, 99, 0.15) * into);
}

// Drawn over km.js's first 0.8 s: Question 2's thread, still below the wipe's edge, and the
// pointer leaving the rail.
export function kmWipe(g, t) {
  const p = clamp(sp(t, 'ui'));
  if (p >= 0.995) return;
  pages.sheet(g, KM_CAM, () => {
    const [x, y, w, h] = pages.CONTENT;
    pages.clipped(g, [x, y + h * p, w, h * (1 - p)], () => pages.view(g, APP.q2Thread));
    g.globalAlpha = Math.min(1, (1 - p) * 8);
    g.fillStyle = C.line;
    g.fillRect(x, y + h * p - 1, w, 1);
    g.globalAlpha = 1;
  }, 0, true);
  const [sx, sy] = pages.onScreen(KM_CAM, pages.RAIL.km);
  drawCursor(g, sx, sy, clamp(1 - t / 0.14), 1 - clamp(t / 0.2));
}
