// Question 2 chapter: one question, two general models side by side, then the
// Bionocular answer: it scrolls, its expert-review filter lifts out, the
// heatmap builds beside it, and the three tallies close the chapter.
// Everything is a pure function of global time T (seconds). No timers, no state.
// Storyboard: docs/storyboard.md. The answer is the original screenshots
// (bio-part1 and 2, 1x) laid out as one page; the heatmap and the hovered
// filter chip are the 2x captures of the same answer. Every coordinate below
// is measured from their pixels.

import { clamp, lerp, sp, track, track2, window01, easeOutCubic, easeInOutCubic } from './lib/motion.js';
import { rrect, risingText, drawCursor, font } from './lib/draw.js';

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
  part1: image('assets/screens/bio-part1.png'),
  part2: image('assets/screens/bio-part2.png'),
  heat: image('assets/screens/charts-heatmap@2x.png'),
  reviewed: image('assets/screens/filters-hover-reviewed@2x.png'),
  // The Charts toggle (closed, then open) and the hub link, from the full 2x captures.
  answer: image('assets/screens/bio-answer@2x.png'),
  answerOpen: image('assets/screens/bio-answer-open-heatmap@2x.png'),
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
const T_POP = 3.9; // "Reviewed by an expert" lifts out of the answer
const T_BACK = 4.8; // and settles back
const T_SHIFT = 4.92; // the answer moves left to make room
const T_RIGHT = 5.3; // the Charts toggle and the hub link rise on the right
const T_ZOOM_IN = 5.34; // the camera leans into the Charts toggle
const T_HOVER = 5.52; // the cursor rests on Charts: its border darkens
const T_OPEN = 5.68; // click: the panel unfolds
const T_TAB = 5.88; // the cursor rests on Heatmap
const T_HEAT = 6.02; // click Heatmap
const T_ZOOM_OUT = 6.08;
const T_CELLS = 6.1;
const T_LEGEND = 6.5;
const T_LINK = 6.62; // the cursor ends on "Open in Efficacy Intelligence Hub"
const T_STATS = 6.95; // the scene greys out behind the tallies
const T_BARS = 7.15;
const T_END = 8.65; // everything clears to the bare canvas

// ---------------------------------------------------------------- layout
// Rivals: two equal sheets across the frame.
const RIVAL = { y: 240, w: 776, h: 760, x: [160, 984] };

// The answer as one page, in screenshot px: part 2 continues part 1's table.
const PAGE = { x0: 4, w: 1076, h: 978 + 455, part1Bottom: 978, part2: [15, 978] };
const CHIP = { page: [480, 247, 239, 33], src: [924, 0, 478, 64] }; // in-page slot, 2x capture
// The heatmap capture (2x): three columns of 19 cells, legend below.
// Cropped at the right, past the legend, where the capture is empty.
const HEAT = {
  y: 176, h: 760, src: [1700, 1760],
  cells: { x: [673, 903, 1133], w: 224, y: 160, pitch: 80.17, h: 74, rows: 19 },
  legend: [30, 1692, 1640, 40],
  underline: [132, 72, 145, 4], // under "Heatmap"; the tab row's rule is y 74-75
  body: 80, // everything below the tab row
};
const HK = HEAT.h / HEAT.src[1];
HEAT.w = HEAT.src[0] * HK;
// The answer and the panel share the frame, centred, 48 px apart.
const LEFT_W = PAGE.w * (HEAT.h / (PAGE.h + 24));
HEAT.x = (W - (LEFT_W + 48 + HEAT.w)) / 2 + LEFT_W + 48;
// The toggle sits 16 px (2x) above the panel; the link 16 px below the toggle
// while the panel is closed, below the panel once it is open.
const TOGGLE = [52, 3064, 170, 56];
const LINK = [50, 3136, 462, 28];
const toggleY = HEAT.y - (TOGGLE[3] + 16) * HK;
const linkY = (open) => HEAT.y + open * (HEAT.h + 16 * HK);

// Rivals ride one conveyor in and out; Bionocular comes up behind them.
const rivalsY = (T) => track(T, [[0, H], [T_RIVALS, 0], [T_BIO, -H]], 'ui');
const bioY = (T) => track(T, [[0, H], [T_BIO, 0]], 'ui');

// The Bionocular sheet's camera: `s` is the page row at the sheet's top
// (screenshot px), `scale` the zoom. Centred while it scrolls, then it moves
// left and shrinks until the whole page fits beside the heatmap.
const shift = (T) => sp(T - T_SHIFT, 'ui');
const bioView = (T) => {
  const k = shift(T);
  const scale = lerp(0.87, HEAT.h / (PAGE.h + 24), k);
  const end = PAGE.h - 700 / 0.87;
  return {
    s: lerp(52, end, easeInOutCubic((T - T_SCROLL[0]) / (T_SCROLL[1] - T_SCROLL[0])))
      + (150 - end) * sp(T - T_SCROLL_BACK, 'ui') - 150 * k,
    px: PAGE.x0,
    scale,
    w: PAGE.w * scale,
    x: lerp((W - PAGE.w * 0.87) / 2, HEAT.x - 48 - LEFT_W, k),
    h: lerp(700, HEAT.h, k),
    top: lerp(210, HEAT.y, k) + bioY(T),
  };
};
const toScreen = (v, x, y) => [v.x + (x - v.px) * v.scale, v.top + (y - v.s) * v.scale];

// The chip's lift: out with a little overshoot, back without.
const lift = (T) => sp(T - T_POP, 'snappy') - sp(T - T_BACK, 'ui');
// The camera leans into the Charts toggle and the tabs, pulls back out, then
// leans slowly toward the hub link the cursor ends on.
// The frame's left edge falls in the gap left of the panel, so no word of the answer is cut.
const FOCUS = [HEAT.x + 1000 * HK, HEAT.y - 10 * HK];
// The link lean scales about the link itself, so it stays where it is on screen.
const LINK_AT = [HEAT.x + 240 * HK, linkY(1) + 14 * HK];
const camera = (T) => {
  const k = sp(T - T_ZOOM_IN, 'heavy') - sp(T - T_ZOOM_OUT, 'heavy');
  const zl = 1 + 0.25 * sp(T - T_LINK + 0.1, 'soft');
  const lean = (a, mid) => a - (a - mid) / zl - mid;
  return {
    z: 1 + 1.1 * k + (zl - 1),
    cx: W / 2 + (FOCUS[0] - W / 2) * k + lean(LINK_AT[0], W / 2),
    cy: H / 2 + (FOCUS[1] - H / 2) * k + lean(LINK_AT[1], H / 2),
  };
};
const project = (T, [x, y]) => {
  const c = camera(T);
  return [W / 2 + (x - c.cx) * c.z, H / 2 + (y - c.cy) * c.z];
};
const unfold = (T) => sp(T - T_OPEN - 0.03, 'ui');
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
cue(T_SHIFT, 'whoosh', 0.35);
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
function modelName(g, r, x, y, pIn, size) {
  g.font = font(600, size);
  risingText(g, r.vendor, x, y, pIn, 0, size, r.text);
  const vw = g.measureText(`${r.vendor} `).width;
  risingText(g, r.name, x + vw, y, pIn, 0, size, C.ink);
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
  // The chip leaves upward when the answer makes room for the heatmap.
  const leave = sp(T - T_SHIFT, 'snappy');
  if (leave >= 0.999) return;
  const p = sp(tq - Q.shrink, 'ui');
  g.save();
  g.translate(0, -140 * leave);
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
    QUESTION.forEach((text, i) => risingText(g, text, tx, ty(i), sp(T - Q.lines[i], 'snappy'), 0, 44, C.ink));
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
  modelName(g, r, x, top - 64, sp(T - at - 0.1, 'ui'), 30);
  if (T >= r.counted) {
    const pIn = sp(T - r.counted, 'snappy');
    const n = count(r.treatments, r.counted, T);
    g.font = font(500, 26, 'mono');
    risingText(g, n, x, top - 20, pIn, 0, 26, C.ink);
    let tx = x + g.measureText(n).width + 10;
    g.font = font(500, 20);
    risingText(g, 'treatments extracted', tx, top - 22, pIn, 0, 20, C.ink);
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

// ---------------------------------------------------------------- scene 3: the Bionocular answer
function bioSheet(g, T) {
  const v = bioView(T);
  if (v.top > H + 40) return;
  const lp = sp(T - T_BIO - 0.05, 'heavy');
  if (lp > 0) {
    const lh = 44;
    const lw = lh * LOGO_ASPECT;
    g.save();
    g.beginPath();
    g.rect(v.x - 4, v.top - 78, lw + 8, (lh + 8) * clamp(lp));
    g.clip();
    g.drawImage(IMG.logo, v.x, v.top - 76, lw, lh);
    g.restore();
  }
  g.font = font(600, 30);
  risingText(g, 'Bionocular agent', v.x + 62, v.top - 42, sp(T - T_BIO - 0.1, 'ui'), 0, 30, C.ink);

  sheet(g, v.x, v.top, v.w, v.h);
  thinking(g, v.x + 44, v.top + 50, T, window01(T, T_BIO + 0.05, T_BIO_WIPE + 0.12, 0.08, 0.1));
  streamed(g, T, T_BIO_WIPE, v.x, v.top, v.w, v.h, () => {
    // An image placed at page position (px, py), drawn through the camera.
    const blit = (img, px, py) => {
      const [x, y] = toScreen(v, px, py);
      const sh = img === IMG.part1 ? PAGE.part1Bottom : img.naturalHeight;
      g.drawImage(img, 0, 0, img.naturalWidth, sh, x, y, img.naturalWidth * v.scale, sh * v.scale);
    };
    blit(IMG.part1, 0, 0);
    blit(IMG.part2, ...PAGE.part2);
  });
}

// "Reviewed by an expert (MD or PhD)" lifts out of the filter row, larger and
// hovered (the real 2x hover capture), over a veiled answer, then settles back.
function expert(g, T) {
  const p = lift(T);
  if (T < T_POP || p <= 0.001) return;
  const v = bioView(T);
  const [px, py, pw, ph] = CHIP.page;
  const [sx, sy] = toScreen(v, px, py);
  const [cx0, cy0] = [sx + (pw * v.scale) / 2, sy + (ph * v.scale) / 2];
  g.save();
  rrect(g, v.x, v.top, v.w, v.h, 18);
  g.clip();
  g.fillStyle = `rgba(247, 250, 249, ${0.82 * clamp(p)})`;
  g.fillRect(v.x, v.top, v.w, v.h);
  g.restore();

  const [ix, iy, iw, ih] = CHIP.src;
  const f = lerp((pw * v.scale) / iw, 1.25, p);
  const [w, h] = [iw * f, ih * f];
  const x = lerp(cx0, v.x + v.w / 2, p) - w / 2;
  const y = lerp(cy0, v.top + v.h / 2, p) - h / 2;
  g.save();
  g.shadowColor = `rgba(16, 43, 54, ${0.18 * clamp(p)})`;
  g.shadowBlur = 60 * clamp(p);
  g.shadowOffsetY = 22 * clamp(p);
  g.fillStyle = C.sheet;
  rrect(g, x, y, w, h, h / 2);
  g.fill();
  g.restore();
  g.save();
  rrect(g, x, y, w, h, h / 2);
  g.clip();
  g.drawImage(IMG.reviewed, ix, iy, iw, ih, x, y, w, h);
  g.restore();
  // Our seafoam ring marks it, never a UI state.
  g.save();
  g.globalAlpha = clamp(p);
  g.strokeStyle = C.accent;
  g.lineWidth = 3;
  rrect(g, x - 8, y - 8, w + 16, h + 16, h / 2 + 8);
  g.stroke();
  g.restore();
}

// ---------------------------------------------------------------- scene 4: Charts, Heatmap, the hub link
// The real Charts toggle and hub link rise beside the answer. The toggle shows
// its hover border (border-primary, as TurnCharts styles it), is clicked, and
// the panel unfolds with no chart drawn; Heatmap is clicked, its underline
// draws, and the real heatmap builds cell by cell, ORR then DCR then CR.
function rightColumn(g, T) {
  const p = sp(T - T_RIGHT, 'ui');
  if (p <= 0) return;
  const k = HK;
  const { x, w, h } = HEAT;
  const rise = (1 - p) * 80;
  const u = unfold(T);
  g.save();
  g.globalAlpha = clamp(p * 3);
  if (u > 0) {
    const top = HEAT.y + rise;
    const ph = h * u;
    const at = (cx, cy) => [x + cx * k, top + cy * k];
    sheet(g, x, top, w, ph);
    g.save();
    rrect(g, x, top, w, ph, 18);
    g.clip();
    g.drawImage(IMG.heat, 0, 0, ...HEAT.src, x, top, w, h);
    // No tab is underlined until Heatmap is clicked; then its line draws from the centre.
    const [ux, uy, uw, uh] = HEAT.underline;
    const [lx0, ly0] = at(ux, uy);
    g.fillStyle = C.sheet;
    g.fillRect(lx0, ly0 - 2 * k, uw * k, (uh + 2) * k);
    g.fillStyle = 'rgb(205, 223, 216)';
    g.fillRect(lx0, ly0 + 2 * k, uw * k, 2 * k);
    const up = easeOutCubic((T - T_HEAT) / 0.18);
    if (up > 0) g.drawImage(IMG.heat, ux + (uw * (1 - up)) / 2, uy, uw * up, uh, lx0 + (uw * (1 - up) * k) / 2, ly0, uw * up * k, uh * k);
    // The view stays empty until then; the heatmap's labels reveal top-down.
    const reveal = easeOutCubic((T - T_HEAT - 0.02) / 0.35);
    const [, by] = at(0, HEAT.body + (HEAT.src[1] - HEAT.body) * reveal);
    g.fillStyle = C.sheet;
    g.fillRect(x + 2, by, w - 4, top + h - by - 2);
    const { x: xs, w: cw, y: y0, pitch, h: ch, rows } = HEAT.cells;
    xs.forEach((cx, c) => {
      for (let r = 0; r < rows; r++) {
        const cy = y0 + r * pitch;
        const [dx, dy] = at(cx, cy);
        const [dw, dh] = [cw * k, ch * k];
        g.fillStyle = C.sheet;
        g.fillRect(dx - 2, dy - 2, dw + 4, dh + 4);
        const q = sp(T - (T_CELLS + c * 0.1 + r * 0.008), 'snappy');
        if (q <= 0) continue;
        const s = 0.86 + 0.14 * q;
        g.save();
        g.globalAlpha *= clamp(q * 2);
        g.drawImage(IMG.heat, cx, cy, cw, ch, dx + (dw * (1 - s)) / 2, dy + (dh * (1 - s)) / 2, dw * s, dh * s);
        g.restore();
      }
    });
    const [lx, ly, lw, lh] = HEAT.legend;
    const lp = easeOutCubic((T - T_LEGEND) / 0.3);
    const [gx, gy] = at(lx, ly);
    g.fillStyle = C.sheet;
    g.fillRect(gx, gy, lw * k, lh * k);
    if (lp > 0) g.drawImage(IMG.heat, lx, ly, lw * lp, lh, gx, gy, lw * lp * k, lh * k);
    g.restore();
  }

  // The toggle: closed until the click, open (chevron up) after.
  const ty = toggleY + rise;
  const [tx, tsy, tw, th] = TOGGLE;
  g.drawImage(T < T_OPEN ? IMG.answer : IMG.answerOpen, tx, tsy, tw, th, x, ty, tw * k, th * k);
  const hover = window01(T, T_HOVER - 0.04, T_TAB - 0.25, 0.08, 0.12);
  if (hover > 0) {
    g.save();
    g.globalAlpha *= hover;
    g.strokeStyle = C.primary;
    g.lineWidth = 2 * k;
    rrect(g, x + k, ty + k, (tw - 2) * k, (th - 2) * k, ((th - 2) * k) / 2);
    g.stroke();
    g.restore();
  }

  const [lx, lsy, lw, lh] = LINK;
  const ly = linkY(u) + rise;
  g.drawImage(IMG.answer, lx, lsy, lw, lh, x - 2 * k, ly, lw * k, lh * k);
  // Our seafoam outline marks the link the cursor ends on.
  const mark = window01(T, T_LINK, 99, 0.08, 0.1);
  if (mark > 0) {
    g.save();
    g.globalAlpha *= mark;
    g.strokeStyle = C.accent;
    g.lineWidth = 2.5;
    rrect(g, x - 2 * k - 8, ly - 6, lw * k + 16, lh * k + 12, 8);
    g.stroke();
    g.restore();
  }
  g.restore();
}

// Drawn outside the camera at the projected point, so it keeps its size.
function cursor(g, T) {
  if (T < T_ZOOM_IN) return;
  const k = HK;
  const toggle = [HEAT.x + 110 * k, toggleY + 32 * k];
  const tab = [HEAT.x + 214 * k, HEAT.y + 44 * k];
  const link = [HEAT.x + 440 * k, linkY(1) + 20 * k];
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
    risingText(g, label, cx, CARD.y + pad + 30, sp(T - T_STATS - 0.15 - c * 0.05, 'ui'), 0, 34, C.ink);
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
        risingText(g, r.name, cx + lh * 1.3 + 8, y, q, 0, 24, C.primary);
      } else {
        modelName(g, r, cx, y, q, 24);
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
  expert(g, T);
  rightColumn(g, T);
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
