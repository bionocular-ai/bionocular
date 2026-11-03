// Question 2 chapter: one question, two general models side by side, then the
// Bionocular answer: it scrolls, its expert-review filter lifts out, Charts
// opens in place under its table and the heatmap builds there (as in q3.js),
// and the three tallies close the chapter.
// Everything is a pure function of global time T (seconds). No timers, no state.
// Storyboard: docs/storyboard.md. The answer is its 2x capture (Charts closed),
// then the same answer with the heatmap open; the heatmap panel and the hovered
// filter chip are 2x captures of the same answer. Every coordinate below is
// measured from their pixels.

import { clamp, lerp, sp, track, track2, window01, easeOutCubic, easeInOutCubic, lift } from './lib/motion.js';
import { rrect, risingText, riseWords, drawCursor, font, liftOut } from './lib/draw.js';

export const FILM = { title: 'q2-chapter', w: 1920, h: 1080, dur: 9, bpm: 120 };
const { w: W, h: H } = FILM;

// Bionocular tokens (web/src/app/globals.css).
export const C = {
  bg: '#F7FAF9',
  sheet: '#FFFFFF',
  ink: '#102B36',
  muted: '#4A6B77',
  line: '#C8E0D8',
  primary: '#1B4F65',
  accent: '#7AC1A2',
  tint: '#DAF0E6',
};

const image = (src) => Object.assign(new Image(), { src });
const IMG = {
  gemini: image('assets/screens/gemini-3.1-pro.png'),
  opus1: image('assets/screens/opus-5.5-part1.png'),
  opus2: image('assets/screens/opus-5.5-part2.png'),
  heat: image('assets/screens/q1-charts-heatmap@2x.png'),
  reviewed: image('assets/screens/q1-reviewed-hover@2x.png'),
  // The Charts toggle (closed, then open) and the hub link, from the full 2x captures.
  answer: image('assets/screens/q1-bio-answer@2x.png'),
  answerOpen: image('assets/screens/q1-bio-answer-heatmap@2x.png'),
  logo: image('assets/logo.svg'),
};
const LOGO_ASPECT = 127.35 / 148.3; // logo.svg viewBox width / height
export const IMAGES = Object.values(IMG);

export const CUES = [];
const cue = (t, type, gain = 1) => CUES.push({ t: +t.toFixed(3), type, gain });

// ---------------------------------------------------------------- timeline
const Q = { lines: [0.08, 0.16, 0.24], marks: [0.42, 0.48, 0.54, 0.6], shrink: 0.85 };

// Counted from each screenshot: treatments, and the readouts (table rows) they
// come from. Gemini: 5 rows, 5 treatments. Opus: 14 rows (Table A 5, Table B 9),
// "nine agents". Bionocular: 19 rows, 16 treatments (one regimen in one trial).
// Vendor colours identify each model in text and bars only, never as a logo:
// Google Blue and Claude's orange, with darker shades for text so labels keep
// 3:1+ on white after compression.
const RIVALS = [
  { key: 'gemini', vendor: 'Google', name: 'Gemini 3.1 Pro', color: '#4285F4', text: '#1A73E8', wipe: 1.2, counted: 1.55, treatments: 5, readouts: 5 },
  { key: 'opus', vendor: 'Anthropic', name: 'Claude Opus 5.5', color: '#D97757', text: '#C96442', wipe: 1.28, counted: 1.62, treatments: 9, readouts: 14 },
];
const BIO_TALLY = { treatments: 16, readouts: 19 };
const T_RIVALS = 0.9; // both sheets rise in
const T_RIVAL_SCROLL = [1.6, 2.25];
const T_BIO = 2.4; // the rivals leave, Bionocular arrives
const T_BIO_WIPE = 2.65;
const T_SCROLL = [2.95, 3.55]; // down the whole answer
const T_SCROLL_BACK = 3.58; // back up to the filter row
const T_POP = 3.9; // "Reviewed by a biopharma expert" lifts out of the answer
const T_BACK = 4.8; // and settles back
const T_CH = 4.92; // down to the Charts toggle under the table
const T_ZOOM_IN = 5.34; // the camera leans into the Charts toggle
const T_HOVER = 5.52; // the cursor rests on Charts: its border darkens
const T_OPEN = 5.68; // click: the panel unfolds
const T_TAB = 5.88; // the cursor rests on Heatmap
const T_HEAT = 6.02; // click Heatmap
const T_ZOOM_OUT = 6.08; // the camera pulls out until the whole panel fits
const T_CELLS = 6.1;
const T_LEGEND = 6.5;
const T_LINK = 6.62; // the cursor ends on "Open in Efficacy Intelligence Hub"
const T_STATS = 6.95; // the scene greys out behind the tallies
const T_BARS = 7.15;
const T_END = 8.65; // everything clears to the bare canvas

// ---------------------------------------------------------------- layout
// Rivals: two equal sheets across the frame.
const RIVAL = { y: 240, w: 776, h: 760, x: [160, 984] };

// The Bionocular answer, as in q3.js: the 2x capture at its scale, across the
// full grid. The run of 2026-10-08 reopened from history (scripts/capture-answers.sh),
// its column widened from 1080 to 1460 px as in q3.js. q1-bio-answer has Charts
// closed; q1-bio-answer-heatmap is the same answer with the heatmap open, identical
// above the panel. Capture px, measured from the DOM.
const BS = { y: 210, h: 800, w: 1600, src: [2920, 3260] };
BS.x = (W - BS.w) / 2;
BS.s = BS.w / BS.src[0];
const CHIP = [995, 830, 638, 64]; // "Reviewed by a biopharma expert (MD or PhD)" in the answer
const CHIP_SRC = [0, 0, 638, 64]; // the hover capture is that chip alone
const TOGGLE = [52, 3064, 170, 56];
const LINK = [52, 3132, 461, 32]; // under the closed toggle
const LINK_OPEN = 4913; // its row once the panel is open
// The heatmap panel capture is the open answer's panel, at PANEL. In its own
// px: three columns of 19 cells (rows vary where a label wraps), the legend, the tab row.
const PANEL = [52, 3136];
const HEAT = {
  src: [2868, 1765],
  cells: {
    x: [686, 916, 1146], w: 224,
    rows: [
      [159, 74], [240, 74], [320, 74], [400, 74], [481, 74], [561, 74], [642, 74],
      [722, 74], [802, 77], [885, 74], [965, 74], [1046, 74], [1126, 74], [1207, 70],
      [1283, 74], [1363, 74], [1444, 74], [1524, 74], [1604, 77],
    ],
  },
  legend: [30, 1693, 1690, 44],
  underline: [132, 72, 145, 4], // under "Heatmap"; the tab row's rule is y 74-75
  body: 80, // everything below the tab row
};
// The page row at the sheet's top while the toggle sits low in the sheet, and
// the scale and row at which the open panel, toggle to link, fits the sheet.
const ROW_TOGGLE = TOGGLE[1] - (BS.h * 0.62) / BS.s;
// 50 px spare, so the link's outline and the pointer stay inside the sheet.
const FIT = (BS.h - 50) / (LINK_OPEN + LINK[3] - TOGGLE[1]);
const ROW_FIT = TOGGLE[1] - 6 / FIT;
const fitPoint = (x, y) => [(W - BS.src[0] * FIT) / 2 + x * FIT, BS.y + 12 + (y - ROW_FIT) * FIT];
const togglePoint = (x, y) => [BS.x + x * BS.s, BS.y + 12 + (y - ROW_TOGGLE) * BS.s];

// Rivals ride one conveyor in and out; Bionocular comes up behind them.
const rivalsY = (T) => track(T, [[0, H], [T_RIVALS, 0], [T_BIO, -H]], 'ui');
const bioY = (T) => track(T, [[0, H], [T_BIO, 0]], 'ui');

// The camera leans into the toggle and the tabs, then pulls back out.
const FOCUS = togglePoint(TOGGLE[0] + 218, TOGGLE[1] + 72);
const camera = (T) => {
  const k = sp(T - T_ZOOM_IN, 'heavy') - sp(T - T_ZOOM_OUT, 'heavy');
  return { z: 1 + 1.1 * k, cx: W / 2 + (FOCUS[0] - W / 2) * k, cy: H / 2 + (FOCUS[1] - H / 2) * k };
};
const project = (T, [x, y]) => {
  const c = camera(T);
  return [W / 2 + (x - c.cx) * c.z, H / 2 + (y - c.cy) * c.z];
};
// The grey-out behind the tallies, and the final clear.
const dim = (T) => easeInOutCubic((T - T_STATS) / 0.4);
const clear = (T) => easeInOutCubic((T - T_END) / 0.35);

// ---------------------------------------------------------------- sound
cue(0.08, 'tick', 0.35);
Q.marks.forEach((t) => cue(t, 'tick', 0.45));
cue(Q.shrink, 'whoosh', 0.35);
cue(T_RIVALS + 0.02, 'whoosh', 0.45);
RIVALS.forEach((r) => [0, 0.08].forEach((d) => cue(r.counted + d, 'tick', 0.5)));
cue(T_RIVAL_SCROLL[0], 'whoosh', 0.25);
cue(T_BIO + 0.02, 'whoosh', 0.45);
cue(T_BIO + 0.05, 'thump', 0.7);
cue(T_SCROLL[0], 'whoosh', 0.25);
cue(T_SCROLL_BACK, 'whoosh', 0.2);
cue(T_POP, 'pop', 0.7);
cue(T_BACK, 'tick', 0.4);
cue(T_CH, 'whoosh', 0.3);
cue(T_ZOOM_IN, 'whoosh', 0.3);
cue(T_HOVER, 'tick', 0.4);
cue(T_OPEN, 'click', 0.9);
cue(T_TAB, 'tick', 0.35);
cue(T_HEAT, 'click', 0.9);
cue(T_ZOOM_OUT, 'whoosh', 0.25);
[0, 1, 2].forEach((c) => cue(T_CELLS + c * 0.1, 'pop', 0.4));
cue(T_LINK, 'tick', 0.5);
cue(T_STATS, 'whoosh', 0.4);
[0, 1, 2].forEach((i) => cue(T_BARS + i * 0.12, 'tick', 0.5));
cue(T_BARS + 0.36, 'chime', 0.7);

// ---------------------------------------------------------------- pieces
function sheet(g, x, y, w, h) {
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.10)';
  g.shadowBlur = 48;
  g.shadowOffsetY = 14;
  g.fillStyle = C.sheet;
  rrect(g, x, y, w, h, 18);
  g.fill();
  g.restore();
  g.strokeStyle = C.line;
  g.lineWidth = 1;
  rrect(g, x + 0.5, y + 0.5, w - 1, h - 1, 18);
  g.stroke();
}

// Three dots, the same for every model: our indicator, not anyone's UI.
function thinking(g, x, y, T, alpha) {
  if (alpha <= 0) return;
  g.save();
  g.fillStyle = C.accent;
  for (let i = 0; i < 3; i++) {
    g.globalAlpha = alpha * (0.3 + 0.7 * Math.max(0, Math.sin(2 * Math.PI * (T * 2.4 - i * 0.18))));
    g.beginPath();
    g.arc(x + i * 22, y, 6, 0, Math.PI * 2);
    g.fill();
  }
  g.restore();
}

// The answer streams in top to bottom, clipped to its sheet.
function streamed(g, T, wipe, x, y, w, h, paint) {
  const reveal = h * easeInOutCubic((T - wipe) / 0.35);
  if (reveal <= 0) return;
  g.save();
  rrect(g, x, y, w, h, 18);
  g.clip();
  g.beginPath();
  g.rect(x, y, w, reveal);
  g.clip();
  paint();
  g.restore();
}

const count = (n, t0, T, d = 0.35) => `${Math.round(n * easeOutCubic((T - t0) / d))}`;

// "Google Gemini 3.1 Pro": vendor in the model's colour, model in ink.
function modelName(g, r, x, y, T, tIn, size) {
  g.font = font(600, size);
  riseWords(g, r.vendor, x, y, T, tIn, 0, r.text);
  const vw = g.measureText(`${r.vendor} `).width;
  riseWords(g, r.name, x + vw, y, T, tIn + 0.06, 0, C.ink);
}

// ---------------------------------------------------------------- scene 1: the question
const QUESTION = [
  'Show me all published efficacy parameters (ORR, DCR and CR)',
  'in metastatic /cutaneous melanoma for active treatments.',
  'strict rule: only treatments which are in phase 1 trial.',
];
const MARKS = [[0, 'ORR'], [0, 'DCR'], [0, 'CR)'], [2, 'phase 1']];
export const CHIP_TEXT = 'Show me all published efficacy parameters (ORR, DCR and CR)…';
const BAR = { x: 160, y: 372, w: 1600, h: 268, r: 30 };

// `settled`: the bar is already a chip (the master film types the question in its own composer).
function question(g, T, settled = false) {
  const tq = settled ? 99 : T;
  const enter = sp(tq, 'ui');
  if (enter <= 0) return;
  const p = sp(tq - Q.shrink, 'ui');
  g.save();
  g.font = font(400, 18);
  const chip = { x: 120, y: 48, w: g.measureText(CHIP_TEXT).width + 48, h: 52, r: 26 };
  const r = {
    x: lerp(BAR.x, chip.x, p), y: lerp(BAR.y + (1 - enter) * 60, chip.y, p),
    w: lerp(BAR.w, chip.w, p), h: lerp(BAR.h, chip.h, p), r: lerp(BAR.r, chip.r, p),
  };
  g.save();
  g.globalAlpha = clamp(tq / 0.12);
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

  // The full question rises in line by line and leaves as the bar shrinks.
  const out = clamp((tq - Q.shrink) / 0.1);
  if (out < 1) {
    g.save();
    g.globalAlpha = 1 - out;
    g.font = font(400, 44);
    const tx = BAR.x + 56;
    const ty = (i) => BAR.y + 92 + i * 64;
    MARKS.forEach(([line, word], i) => {
      const m = sp(T - Q.marks[i], 'snappy');
      if (m <= 0) return;
      const text = QUESTION[line];
      const x = tx + g.measureText(text.slice(0, text.indexOf(word))).width - 6;
      const w = (g.measureText(word.replace(')', '')).width + 12) * clamp(m);
      g.fillStyle = C.tint;
      rrect(g, x, ty(line) - 39, w, 53, 9);
      g.fill();
    });
    QUESTION.forEach((text, i) => riseWords(g, text, tx, ty(i), T, Q.lines[i], 0, C.ink, { stagger: 0.02, fade: 0.3 }));
    g.restore();
  }
  g.font = font(400, 18);
  risingText(g, CHIP_TEXT, chip.x + 24, chip.y + 32, sp(tq - Q.shrink - 0.12, 'snappy'), 0, 18, C.ink);
  g.restore();
}

// ---------------------------------------------------------------- scene 2: Gemini and Opus side by side
function rival(g, T, r, i) {
  const x = RIVAL.x[i];
  const top = RIVAL.y + rivalsY(T) + (1 - sp(T - T_RIVALS - i * 0.08, 'ui')) * 40;
  if (top > H + 40 || top < -RIVAL.h - 200) return;
  const { w, h } = RIVAL;
  const at = T_RIVALS + i * 0.08;

  // Name, and the tally on the line below.
  modelName(g, r, x, top - 64, T, at + 0.1, 30);
  if (T >= r.counted) {
    const pIn = sp(T - r.counted, 'snappy');
    const n = count(r.treatments, r.counted, T);
    g.font = font(500, 26, 'mono');
    risingText(g, n, x, top - 20, pIn, 0, 26, C.ink);
    let tx = x + g.measureText(n).width + 10;
    g.font = font(500, 20);
    riseWords(g, 'treatments extracted', tx, top - 22, T, r.counted + 0.04, 0, C.ink);
    tx += g.measureText('treatments extracted').width + 12;
    g.font = font(400, 18, 'mono');
    risingText(g, `· ${count(r.readouts, r.counted + 0.08, T)} readouts`, tx, top - 23, sp(T - r.counted - 0.08, 'snappy'), 0, 18, C.muted);
  }

  sheet(g, x, top, w, h);
  // The model's colour runs along the top edge of its sheet, clipped to the corners.
  g.save();
  rrect(g, x, top, w, h, 18);
  g.clip();
  g.fillStyle = r.color;
  g.fillRect(x, top, w * easeOutCubic((T - at - 0.1) / 0.4), 4);
  g.restore();
  thinking(g, x + 44, top + 50, T, window01(T, at + 0.05, r.wipe + 0.12, 0.08, 0.1));
  // A quick scroll to the end of the full response.
  const scroll = easeInOutCubic((T - T_RIVAL_SCROLL[0]) / (T_RIVAL_SCROLL[1] - T_RIVAL_SCROLL[0]));
  streamed(g, T, r.wipe, x, top + 4, w, h - 4, () => {
    const parts = r.key === 'gemini' ? [IMG.gemini] : [IMG.opus1, IMG.opus2];
    const heights = parts.map((img) => (img.naturalHeight * w) / img.naturalWidth);
    const total = heights.reduce((a, b) => a + b, 0);
    let y = top + 4 - Math.max(0, total - h) * scroll;
    parts.forEach((img, k) => {
      g.drawImage(img, x, y, w, heights[k]);
      y += heights[k];
    });
  });
}

// ---------------------------------------------------------------- scenes 3-4: the Bionocular answer
// One sheet, as in q3.js: it scrolls the whole answer, comes back to the filter
// row and "Reviewed by a biopharma expert (MD or PhD)" lifts out (the 2x hover capture).
// Then down to the Charts toggle: hover, click, the panel unfolds in place with
// no chart drawn, Heatmap is clicked and the real heatmap builds cell by cell,
// ORR then DCR then CR; the view pulls back until the whole panel fits and the
// cursor ends on the hub link.
function bioSheet(g, T) {
  const top = BS.y + bioY(T);
  if (top > H + 40) return;
  const lp = sp(T - T_BIO - 0.05, 'heavy');
  if (lp > 0) {
    const lh = 44;
    g.save();
    g.beginPath();
    g.rect(BS.x - 4, top - 78, lh * LOGO_ASPECT + 8, (lh + 8) * clamp(lp));
    g.clip();
    g.drawImage(IMG.logo, BS.x, top - 76, lh * LOGO_ASPECT, lh);
    g.restore();
  }
  g.font = font(600, 30);
  riseWords(g, 'Bionocular agent', BS.x + 62, top - 42, T, T_BIO + 0.1, 0, C.ink);
  sheet(g, BS.x, top, BS.w, BS.h);
  thinking(g, BS.x + 44, top + 50, T, window01(T, T_BIO + 0.05, T_BIO_WIPE + 0.12, 0.08, 0.1));
  const end = BS.src[1] * BS.s - BS.h + 24;
  const chipAt = CHIP[1] * BS.s - 200;
  const scroll = end * easeInOutCubic((T - T_SCROLL[0]) / (T_SCROLL[1] - T_SCROLL[0]))
    + (chipAt - end) * sp(T - T_SCROLL_BACK, 'ui')
    + (ROW_TOGGLE * BS.s - chipAt) * sp(T - T_CH, 'ui');
  // Page rows (capture px) map to the sheet at scale `s`, centred.
  const f = sp(T - T_ZOOM_OUT, 'ui');
  const s = lerp(BS.s, FIT, f);
  const row = lerp(scroll / BS.s, ROW_FIT, f);
  const x0 = (W - BS.src[0] * s) / 2;
  const y0 = top + 12 - row * s;
  const blit = (img, [sx, sy, sw, sh], px, py) => g.drawImage(img, sx, sy, sw, sh, x0 + px * s, y0 + py * s, sw * s, sh * s);
  const u = sp(T - T_OPEN - 0.03, 'ui');
  streamed(g, T, T_BIO_WIPE, BS.x, top, BS.w, BS.h, () => {
    g.fillStyle = C.bg;
    g.fillRect(BS.x, top, BS.w, BS.h);
    if (T < T_OPEN) {
      g.drawImage(IMG.answer, x0, y0, BS.src[0] * s, BS.src[1] * s);
      return;
    }
    blit(IMG.answerOpen, [0, 0, BS.src[0], PANEL[1]], 0, 0);
    g.save();
    g.beginPath();
    g.rect(BS.x, y0 + PANEL[1] * s, BS.w, HEAT.src[1] * u * s);
    g.clip();
    heatPanel(g, T, { x: x0 + PANEL[0] * s, y: y0 + PANEL[1] * s, s });
    g.restore();
    blit(IMG.answer, LINK, LINK[0], lerp(LINK[1], LINK_OPEN, u));
  });
  // The toggle's hover border (border-primary, as TurnCharts styles it).
  const hover = window01(T, T_HOVER - 0.04, T_TAB - 0.25, 0.08, 0.12);
  if (hover > 0) {
    const [tx, ty, tw, th] = TOGGLE;
    g.save();
    g.globalAlpha *= hover;
    g.strokeStyle = C.primary;
    g.lineWidth = 2 * s;
    rrect(g, x0 + (tx + 1) * s, y0 + (ty + 1) * s, (tw - 2) * s, (th - 2) * s, ((th - 2) * s) / 2);
    g.stroke();
    g.restore();
  }
  // Our seafoam outline marks the link the cursor ends on.
  const mark = window01(T, T_LINK, 99, 0.08, 0.1);
  if (mark > 0) {
    const [lx, , lw, lh] = LINK;
    g.save();
    g.globalAlpha *= mark;
    g.strokeStyle = C.accent;
    g.lineWidth = 2.5;
    rrect(g, x0 + lx * s - 8, y0 + LINK_OPEN * s - 6, lw * s + 16, lh * s + 12, 8);
    g.stroke();
    g.restore();
  }
  const [cx, cy, cw, ch] = CHIP;
  liftOut(g, IMG.reviewed, CHIP_SRC, { f: s, cx: x0 + (cx + cw / 2) * s, cy: y0 + (cy + ch / 2) * s },
    { f: 1.25, cx: W / 2, cy: top + BS.h / 2 }, lift(T, [T_POP, T_BACK]), C.accent, [BS.x, top, BS.w, BS.h], 'pill');
}

// The open panel at v (its top-left on screen, scale s): no tab underlined and
// no chart until Heatmap is clicked; then its underline draws from the centre,
// the labels reveal top-down and the cells pop in, ORR then DCR then CR.
function heatPanel(g, T, v) {
  const X = (x) => v.x + x * v.s;
  const Y = (y) => v.y + y * v.s;
  const [pw, ph] = HEAT.src;
  g.drawImage(IMG.heat, 0, 0, pw, ph, v.x, v.y, pw * v.s, ph * v.s);
  const [ux, uy, uw, uh] = HEAT.underline;
  g.fillStyle = C.sheet;
  g.fillRect(X(ux), Y(uy - 2), uw * v.s, (uh + 2) * v.s);
  g.fillStyle = 'rgb(205, 223, 216)';
  g.fillRect(X(ux), Y(uy + 2), uw * v.s, 2 * v.s);
  const up = easeOutCubic((T - T_HEAT) / 0.18);
  if (up > 0) g.drawImage(IMG.heat, ux + (uw * (1 - up)) / 2, uy, uw * up, uh, X(ux + (uw * (1 - up)) / 2), Y(uy), uw * up * v.s, uh * v.s);
  const reveal = easeOutCubic((T - T_HEAT - 0.02) / 0.35);
  const by = Y(HEAT.body + (ph - HEAT.body) * reveal);
  g.fillStyle = C.sheet;
  g.fillRect(X(2), by, (pw - 4) * v.s, Y(ph - 2) - by);
  const { x: xs, w: cw, rows } = HEAT.cells;
  xs.forEach((cx, c) => {
    rows.forEach(([cy, ch], r) => {
      const [dx, dy, dw, dh] = [X(cx), Y(cy), cw * v.s, ch * v.s];
      g.fillStyle = C.sheet;
      g.fillRect(dx - 2, dy - 2, dw + 4, dh + 4);
      const q = sp(T - (T_CELLS + c * 0.1 + r * 0.008), 'snappy');
      if (q <= 0) return;
      const k = 0.86 + 0.14 * q;
      g.save();
      g.globalAlpha *= clamp(q * 2);
      g.drawImage(IMG.heat, cx, cy, cw, ch, dx + (dw * (1 - k)) / 2, dy + (dh * (1 - k)) / 2, dw * k, dh * k);
      g.restore();
    });
  });
  const [lx, ly, lw, lh] = HEAT.legend;
  const lp = easeOutCubic((T - T_LEGEND) / 0.3);
  g.fillStyle = C.sheet;
  g.fillRect(X(lx), Y(ly), lw * v.s, lh * v.s);
  if (lp > 0) g.drawImage(IMG.heat, lx, ly, lw * lp, lh, X(lx), Y(ly), lw * lp * v.s, lh * v.s);
}

// Drawn outside the camera at the projected point, so it keeps its size.
function cursor(g, T) {
  if (T < T_ZOOM_IN) return;
  const toggle = togglePoint(TOGGLE[0] + 58, TOGGLE[1] + 32);
  const tab = togglePoint(PANEL[0] + 214, PANEL[1] + 44);
  const link = fitPoint(LINK[0] + 440, LINK_OPEN + 20);
  const start = [FOCUS[0] + 340, FOCUS[1] + 300];
  const [x, y] = track2(T, [[0, start], [T_ZOOM_IN, start], [T_HOVER - 0.2, toggle], [T_TAB - 0.18, tab], [T_LINK - 0.2, link]], 'snappy');
  const press = (t0) => (T > t0 - 0.05 && T < t0 + 0.4 ? clamp((T - t0 + 0.05) / 0.45) : 0);
  const [sx, sy] = project(T, [x, y]);
  drawCursor(g, sx, sy, Math.max(press(T_OPEN), press(T_HEAT)), window01(T, T_ZOOM_IN + 0.05, T_STATS + 0.1, 0.12, 0.15));
}

// ---------------------------------------------------------------- scene 5: the tallies
// The scene greys out and blurs; one card holds the three tallies as bars, on
// one shared scale. Bionocular is the only row in the brand colour.
let blurBuf;
function greyOut(g, p) {
  blurBuf ??= Object.assign(document.createElement('canvas'), { width: W, height: H });
  const b = blurBuf.getContext('2d');
  b.clearRect(0, 0, W, H);
  b.drawImage(g.canvas, 0, 0);
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  g.filter = `blur(${18 * p}px)`;
  g.drawImage(blurBuf, 0, 0);
  g.filter = 'none';
  g.fillStyle = `rgba(16, 43, 54, ${0.45 * p})`;
  g.fillRect(0, 0, W, H);
}

const CARD = { w: 1400, h: 620 };
CARD.x = (W - CARD.w) / 2;
CARD.y = (H - CARD.h) / 2;
const MAX = BIO_TALLY.readouts;
function tallies(g, T) {
  const p = sp(T - T_STATS - 0.05, 'ui');
  if (p <= 0) return;
  const { w, h } = CARD;
  const s = 0.94 + 0.06 * p;
  g.save();
  g.globalAlpha = clamp(p * 4);
  g.translate(W / 2, H / 2 + (1 - p) * 50);
  g.scale(s, s);
  g.translate(-W / 2, -H / 2);
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.25)';
  g.shadowBlur = 80;
  g.shadowOffsetY = 24;
  g.fillStyle = C.sheet;
  rrect(g, CARD.x, CARD.y, w, h, 28);
  g.fill();
  g.restore();

  const pad = 84;
  const gap = 104;
  const colW = (w - pad * 2 - gap) / 2;
  const barMax = colW - 140;
  const rows = [
    ...RIVALS.map((r) => ({ r, values: [r.treatments, r.readouts] })),
    { r: { vendor: '', name: 'Bionocular agent' }, values: [BIO_TALLY.treatments, BIO_TALLY.readouts], ours: true },
  ];
  ['Treatments extracted', 'Readouts'].forEach((label, c) => {
    const cx = CARD.x + pad + c * (colW + gap);
    g.font = font(600, 34);
    riseWords(g, label, cx, CARD.y + pad + 30, T, T_STATS + 0.15 + c * 0.05, 0, C.ink, { stagger: 0.05 });
    rows.forEach(({ r, values, ours }, i) => {
      const y = CARD.y + pad + 112 + i * 132;
      const t0 = T_BARS + i * 0.12 + c * 0.06;
      const q = sp(T - t0, 'ui');
      if (q <= 0) return;
      if (ours) {
        g.fillStyle = C.tint;
        rrect(g, cx - 24, y - 40, (colW + 48) * clamp(q * 1.4), 120, 16);
        g.fill();
      }
      if (ours) {
        const lh = 28;
        g.save();
        g.beginPath();
        g.rect(cx, y - lh - 2, lh * 1.3, (lh + 8) * clamp(q));
        g.clip();
        g.drawImage(IMG.logo, cx, y - lh + 2, lh * LOGO_ASPECT, lh);
        g.restore();
        g.font = font(600, 24);
        riseWords(g, r.name, cx + lh * 1.3 + 8, y, T, t0, 0, C.primary);
      } else {
        modelName(g, r, cx, y, T, t0, 24);
      }
      const n = values[c];
      const bw = Math.max(0, (n / MAX) * barMax * q);
      g.fillStyle = ours ? C.primary : r.color;
      rrect(g, cx, y + 18, bw, 44, 10);
      g.fill();
      const size = ours ? 72 : 56;
      g.font = font(600, size, 'mono');
      risingText(g, count(n, t0, T, 0.5), cx + bw + 20, y + 40 + size * 0.36, sp(T - t0 - 0.04, 'snappy'), 0, size, ours ? C.primary : C.ink);
    });
  });
  g.restore();
}

// ---------------------------------------------------------------- frame
// opts.bar false: the question starts as its chip; opts.rivals false: no Gemini / Opus sheets.
export function draw(g, T, opts = {}) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  const c = camera(T);
  g.save();
  g.translate(W / 2, H / 2);
  g.scale(c.z, c.z);
  g.translate(-c.cx, -c.cy);
  if (opts.rivals !== false) RIVALS.forEach((r, i) => rival(g, T, r, i));
  bioSheet(g, T);
  question(g, T, opts.bar === false);
  g.restore();
  cursor(g, T);
  const d = dim(T);
  if (d > 0) greyOut(g, d);
  tallies(g, T);
  const e = clear(T);
  if (e > 0) {
    g.globalAlpha = e;
    g.fillStyle = C.bg;
    g.fillRect(0, 0, W, H);
    g.globalAlpha = 1;
  }
}
