// The master film's joins (docs/storyboard-master.md): one app window from sign-in to the
// last chapter, every jump a click inside it. Sign-in on the real /login page, the card
// growing into the app sheet; the eight disease portfolios, Cutaneous Melanoma clicked into
// the tour; the AI Agent rail click into Question 1, typed into the real
// composer; Question 2 typed into the composer on the bare canvas (master v2's, captures in
// assets/screens/composer/); the KM rail click. The app screens are 2x captures from
// scripts/capture-agent.sh, all coordinates their CSS px.
// Each beat is a pure function of its own local time t; the master places them.

import { clamp, lerp, sp, track, track2, window01, easeInOutCubic } from './lib/motion.js';
import { rrect, risingText, riseWords, drawCursor, font } from './lib/draw.js';
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
  q2Thread: image('q2-thread'),
  kmHover: image('q2-thread-km-hover'),
};
// Typing changes only a band of the frame; q1c/ holds those bands, one per word.
const band = (dir, n) => Array.from({ length: n }, (_, i) => image(`${dir}c/${String(i + 1).padStart(2, '0')}`));
const ASK = {
  q1: {
    words: band('q1', 27), hover: image('q1c/hover'), base: APP.empty,
    band: [376, 340, 792, 192],
    pill: [[382, 419, 780, 50], [382, 409, 780, 70]], // one line, then two from word 15 (it grows both ways)
    wrap: 15, send: [[1119, 426, 36, 36], [1119, 436, 36, 36]],
  },
};
// /dashboard's eight disease portfolios (scripts/capture-portfolio.sh): each hover is a crop of its
// card and shadow, this far outside the card on every side.
const PORT = {
  rest: image('port-rest'),
  empty: image('port-empty'), // the same page, its cards not yet in
  hover: Array.from({ length: 8 }, (_, i) => image(`portc/0${i + 1}`)),
  cards: [80, 404, 728, 1052].map((x) => [x, 247, 308, 168]).concat([80, 404, 728, 1052].map((x) => [x, 431, 308, 168])),
  pad: 20,
};
export const IMAGES = [...Object.values(LOGIN).filter((v) => v instanceof Image), ...LOGIN.email, ...LOGIN.pass,
  ...Object.values(APP), ...Object.values(ASK).flatMap((q) => [...q.words, q.hover]), PORT.rest, PORT.empty, ...PORT.hover];

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

// "Question 1 (Simple)": the chapter's name rises in word by word top left, as on a title card,
// over a wash of the canvas so it never sits on the page's own text.
function label(g, title, aside, t, tIn, q) {
  const a = clamp(sp(t - tIn, 'ui')) * (1 - clamp(q));
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
  g.save();
  g.letterSpacing = '-1.2px';
  g.font = font(600, 48, 'display');
  riseWords(g, title, 160, 170, t, tIn, q, C.primary);
  const x = 160 + g.measureText(title + ' ').width;
  g.font = font(400, 48, 'display');
  riseWords(g, aside, x, 170, t, tIn + 0.06 * title.split(' ').length, q, C.muted);
  g.letterSpacing = '0px';
  g.restore();
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
// card grows into the app sheet (the disease portfolios, where sign-in lands) while the teal
// ground falls away to the canvas.
const L = { email: 0.55, step: 0.15, field2: 1.5, pass: 1.6, hover: 2.2, click: 2.45, grow: [2.6, 3.5] };
export const LOGIN_DUR = 3.6;
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
    // The card's white grows into the portfolios' sheet, and the page resolves inside it.
    const [cx0, cy0] = loginScreen(c, LOGIN.card);
    const card = { x: cx0, y: cy0, w: LOGIN.card[2] * c.k, h: LOGIN.card[3] * c.k, r: 16 * c.k };
    const [sx, sy] = pages.onScreen(PICK_WIDE, [0, 0]);
    const S = pages.B * PICK_WIDE.z;
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
    blurred(g, 0, clamp((m - 0.25) / 0.5), (x) => pickFrame(x, t - LOGIN_DUR));
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

// ---------------------------------------------------------------- the disease portfolios
// Sign-in lands on /dashboard. The eight cards stagger in as they do on the real page, the
// pointer walks the bottom row left to right and the top row back, each card taking its hover,
// and clicks Cutaneous Melanoma as the camera leans in. Its Trial Updates wipes in, rail and
// all, the camera and pointer flowing straight into the tour's first lean. The cards start while
// the login card is still growing, so t runs from before 0 there.
const PICK = { walk: 0.6, step: 0.24, up: 0.12, click: 2.8 };
PICK.order = [4, 5, 6, 7, 3, 2, 1, 0]; // card indices, in the order the pointer reaches them
PICK.at = PICK.order.map((_, i) => PICK.walk + i * PICK.step + (i >= 4 ? PICK.up : 0));
PICK.lean = PICK.at[4] - 0.2;
export const PICK_DUR = PICK.click + 0.7;
export const TOUR_FROM = 1; // the tour's local time this hands over to, inside its first lean
const PICK_WIDE = { cx: 720, cy: 350, z: 1.15 }; // every card, and the sheet's edges inside the frame
const PICK_LEAN = { cx: 500, cy: 300, z: 1.55 }; // the header to the bottom row, cards 1-3 whole
PICK.order.forEach((_, i) => cue('pick', PICK.at[i], 'tick', 0.2));
cue('pick', PICK.lean, 'whoosh', 0.25);
cue('pick', PICK.click, 'click', 0.85);
cue('pick', PICK.click + 0.05, 'whoosh', 0.35);

const pickCam = (t) => {
  const e = easeInOutCubic((t - PICK.click) / (PICK_DUR - PICK.click));
  // The tour's camera as it runs up to the handover, so the speed carries across the cut.
  const tour = pages.camAt(TOUR_FROM - (PICK_DUR - t));
  const v = (k) => lerp(track(t, [[0, PICK_WIDE[k]], [PICK.lean, PICK_LEAN[k]]], 'heavy'), tour[k], e);
  return { cx: v('cx'), cy: v('cy'), z: v('z') };
};

function pickPage(g, t) {
  pages.view(g, PORT.empty);
  PORT.cards.forEach(([x, y, w, h], i) => {
    // Masked, not faded, as the landscape's columns land.
    const q = sp(t + 0.3 - i * 0.06, 'ui');
    pages.clipped(g, [x - 2, y - 2, w + 4, (h + 4) * clamp(q)], () => pages.blit(g, PORT.rest, [x - 2, y - 2, w + 4, h + 4], (1 - q) * 24));
  });
  PICK.order.forEach((card, i) => {
    const a = i < 7 ? window01(t, PICK.at[i], PICK.at[i + 1] + 0.1, 0.12, 0.2) : clamp((t - PICK.at[i]) / 0.12);
    if (a <= 0) return;
    const [x, y, w, h] = PORT.cards[card];
    const m = PORT.pad;
    g.save();
    g.globalAlpha = a;
    g.drawImage(PORT.hover[card], x - m, y - m, w + m * 2, h + m * 2);
    g.restore();
  });
  // No rail on this page, so the whole frame below the top bar wipes in, and the bar's links change.
  const p = clamp(sp(t - PICK.click, 'ui'));
  if (p <= 0) return;
  const [W0, H0] = [pages.VIEW.w, pages.VIEW.h];
  g.save();
  g.globalAlpha = clamp(p * 3);
  pages.blit(g, pages.IMG.tuAll, [0, 0, W0, 56]);
  g.restore();
  pages.clipped(g, [0, 56, W0, (H0 - 56) * p], () => {
    g.save();
    g.translate(0, (1 - p) * 6);
    pages.view(g, pages.IMG.tuAll);
    g.restore();
  });
  if (p < 0.995) {
    g.save();
    g.globalAlpha = Math.min(1, (1 - p) * 8);
    g.fillStyle = C.line;
    g.fillRect(0, 56 + (H0 - 56) * p - 1, W0, 1);
    g.restore();
  }
}

function pickFrame(g, t, c = PICK_WIDE) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  pages.sheet(g, c, () => pickPage(g, t));
}

export function pick(g, t) {
  const c = pickCam(t);
  pickFrame(g, t, c);
  const [px, py] = track2(t, [
    [0, [720, 660]],
    ...PICK.order.map((card, i) => [PICK.at[i] - 0.14, center(PORT.cards[card], 0.5, 0.45)]),
    [PICK.click + 0.2, pages.pointerAt(TOUR_FROM)],
  ], 'ui');
  const [sx, sy] = pages.onScreen(c, [px, py]);
  drawCursor(g, sx, sy, clamp(1 - Math.abs(t - PICK.click) / 0.14), clamp((t - 0.15) / 0.12));
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
function askBeat(g, t, { q, keys, paint, tType, tHover, tSend, chip, title, aside, labelIn, path, presses }) {
  const v = (i) => track(t, keys.map(([k, p]) => [k, p[i]]), 'heavy');
  const c = { cx: v(0), cy: v(1), z: v(2) };
  const tm = t - (tSend + 0.15);
  const out = clamp(easeInOutCubic(tm / 0.45));
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  const two = twoLines(q, t, tType, tHover);
  const pill = q.pill[two ? 1 : 0];
  blurred(g, out, 1 - out, (x) => {
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
  label(g, title, aside, t, labelIn, easeInOutCubic((tm + 0.1) / 0.35));
  if (tm >= 0) morph(g, tm, pillOnScreen(c, pill), chip);

  const [px, py] = track2(t, path(two), 'snappy');
  const press = Math.max(0, ...presses.map((t0) => 1 - Math.abs(t - t0) / 0.14));
  const [sx, sy] = pages.onScreen(c, [px, py]);
  drawCursor(g, sx, sy, press, window01(t, 0.05, tSend + 0.25, 0.15, 0.15));
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

// ---------------------------------------------------------------- the composer on the bare canvas
// Question 2 in this film, and both questions in master v2. The composer captures:
// Cropped from the AI Agent page at 1440x900 @2x: the pill and its focus ring, 1592x172.
// The pill is centred on (796, 86) whether it holds one line or two.
const COMPOSER = { w: 1592, h: 172, cx: 796, cy: 86, x0: 16, x1: 1576, r: 50 };
const pillRows = (two) => (two ? [16, 156] : [36, 136]);
const shot = (name) => Object.assign(new Image(), { src: `assets/screens/composer/${name}@2x.png` });
export const CANVAS_ASK = {
  q1: {
    text: 'show me all published efficacy parameters (ORR, DCR and CR) in cutaneous melanoma for active treatments. strict rule: only treatments which are in phase 1 trial.',
    wrapAt: 16, // the word that wraps the question onto a second line
  },
  q3: {
    text: 'provide phase 3 active clinical treatments showing median PFS vs grade3+ Treatment emergent adverse events vs treatment discontinuation due to AEs in metastatic /cutaneous melanoma.',
    wrapAt: 14,
  },
};
for (const [key, q] of Object.entries(CANVAS_ASK)) {
  q.n = q.text.split(' ').length;
  q.words = Array.from({ length: q.n }, (_, i) => shot(`${key}-${String(i + 1).padStart(2, '0')}`));
  q.hover = shot(`${key}-hover`);
}
const EMPTY = shot('empty');
const EMPTY_FOCUS = shot('empty-focus');

// A light line sweeps across the frame and opens into the composer. The pointer
// clicks in, the question types in word by word (each frame a real capture),
// the pointer clicks Send, and the composer shrinks into the chapter's question chip.
export const CANVAS_A = {
  sweep: [0, 0.5], open: [0.45, 0.9], cursorIn: 0.55, click: 1.1, type: 1.3, step: 0.055,
  toSend: 2.95, hover: 3.18, send: 3.4, morph: [3.55, 4.1],
};
// The camera pushes in on the text as it types, pans with the first line, and
// pulls back to the whole composer when the question wraps.
const wrapT = (q) => CANVAS_A.type + (q.wrapAt - 1) * CANVAS_A.step;
const camera = (t, q) => ({
  s: track(t, [[0, 1.1], [CANVAS_A.click, 1.33], [wrapT(q), 1.0]], 'soft'),
  x: track(t, [[0, COMPOSER.cx], [CANVAS_A.click, 640], [CANVAS_A.type, 768], [wrapT(q), COMPOSER.cx]], 'soft'),
});
const typed = (q, t) => (t < CANVAS_A.type ? 0 : Math.min(q.n, Math.floor((t - CANVAS_A.type) / CANVAS_A.step) + 1));
const toScreen = ({ s, x }, ix, iy) => [W / 2 + (ix - x) * s, H / 2 + (iy - COMPOSER.cy) * s];

export function canvasAsk(g, t, q, chipText) {
  const cam = camera(t, q);
  const { s } = cam;
  const k = typed(q, t);
  const two = t >= CANVAS_A.hover || k >= q.wrapAt;
  const img = t >= CANVAS_A.hover ? q.hover : k > 0 ? q.words[k - 1] : t >= CANVAS_A.click ? EMPTY_FOCUS : EMPTY;
  const [r0, r1] = pillRows(two);
  const [px0, py0] = toScreen(cam, COMPOSER.x0, r0);
  const [px1, py1] = toScreen(cam, COMPOSER.x1, r1);
  const pill = { x: px0, y: py0, w: px1 - px0, h: py1 - py0, r: COMPOSER.r * s };

  // The sweep: a teal line drawn left to right with a light at its head.
  const sw = easeInOutCubic((t - CANVAS_A.sweep[0]) / (CANVAS_A.sweep[1] - CANVAS_A.sweep[0]));
  const op = easeInOutCubic((t - CANVAS_A.open[0]) / (CANVAS_A.open[1] - CANVAS_A.open[0]));
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
  const chip = chipRect(g, chipText);
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
  const content = op * (1 - clamp((t - CANVAS_A.morph[0]) / 0.15));
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
    risingText(g, chipText, r.x + 24, r.y + 32, sp(t - CANVAS_A.morph[0] - 0.32, 'snappy'), 0, 18, C.ink);
  }

  // The pointer: in from the lower right, clicks the field, then Send.
  const field = toScreen(cam, 560, COMPOSER.cy);
  const send = toScreen(cam, 1526, two ? 106 : COMPOSER.cy);
  const start = [W / 2 + 560, H / 2 + 380];
  const below = toScreen(cam, 700, COMPOSER.cy + 150);
  const [cx, cy] = track2(t, [[0, start], [CANVAS_A.cursorIn, field], [CANVAS_A.click + 0.2, below], [CANVAS_A.toSend, send]], 'ui');
  const press = Math.max(0, 1 - Math.abs(t - CANVAS_A.click) / 0.12, 1 - Math.abs(t - CANVAS_A.send) / 0.12);
  drawCursor(g, cx, cy, press, window01(t, CANVAS_A.cursorIn, CANVAS_A.morph[0] + 0.15, 0.15, 0.15));
}
// The content fades first (0.15 s), then the pill moves.
export const CANVAS_IMAGES = [EMPTY, EMPTY_FOCUS, ...Object.values(CANVAS_ASK).flatMap((q) => [...q.words, q.hover])];
const morphP = (t) => easeInOutCubic((t - CANVAS_A.morph[0] - 0.1) / (CANVAS_A.morph[1] - CANVAS_A.morph[0] - 0.1));

// ---------------------------------------------------------------- Question 2
// Question 1's tally card blurs away to the bare canvas and Question 2 starts fresh, as in
// master v2: a light line sweeps open into the composer, the question types in, Send, and
// the composer shrinks into Question 2's chip. "Question 2 (Complex)" rises in top left.
const Q2_BLUR = 0.5;
export const TO_Q2_DUR = Q2_BLUR + CANVAS_A.morph[1];
{
  const at = (t, type, gain) => cue('toQ2', Q2_BLUR + t, type, gain);
  const q = CANVAS_ASK.q3;
  cue('toQ2', 0.05, 'whoosh', 0.3);
  at(CANVAS_A.sweep[0] + 0.02, 'whoosh', 0.35);
  at(CANVAS_A.click, 'click', 0.8);
  for (let i = 0; i < q.n; i += 3) at(CANVAS_A.type + i * CANVAS_A.step, 'tick', 0.22);
  at(CANVAS_A.hover, 'tick', 0.35);
  at(CANVAS_A.send, 'click', 0.9);
  at(CANVAS_A.morph[0] + 0.02, 'whoosh', 0.35);
}

// prev(g): Question 1's last frame, which blurs out to the canvas.
export function toQ2(g, t, chipText, prev) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  const b = easeInOutCubic(t / Q2_BLUR);
  blurred(g, b, 1 - b, prev);
  const tc = t - Q2_BLUR;
  if (tc > 0) canvasAsk(g, tc, CANVAS_ASK.q3, chipText);
  label(g, 'Question 2', '(Complex)', t, Q2_BLUR + 0.35, easeInOutCubic((tc - CANVAS_A.morph[0]) / 0.35));
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
