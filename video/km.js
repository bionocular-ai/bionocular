// KM Curves Intelligence chapter: every feature of the page in 16 s. The curves
// draw in, the endpoint and arm filters are used, the chart and the
// published-vs-twin table are read, the floating agent opens and three
// prompts are typed (never sent), and the upload button closes it.
// Everything is a pure function of global time T (seconds). No timers, no state.
// Storyboard: docs/storyboard-km.md. Every screen is a real 2x capture of the
// page at 1440x900 CSS px; all coordinates below are those CSS px, measured
// from the live DOM.

import { clamp, sp, track, track2, window01, easeInOutCubic, easeOutCubic } from './lib/motion.js';
import { rrect, risingText, drawCursor, font } from './lib/draw.js';

export const FILM = { title: 'km-chapter', w: 1920, h: 1080, dur: 16, bpm: 120 };
const { w: W, h: H } = FILM;

// Bionocular tokens (web/src/app/globals.css).
const C = {
  bg: '#F7FAF9',
  sheet: '#FFFFFF',
  ink: '#102B36',
  muted: '#4A6B77',
  line: '#C8E0D8',
  primary: '#1B4F65',
  accent: '#7AC1A2',
  tint: '#DAF0E6',
};

const image = (name) => Object.assign(new Image(), { src: `assets/screens/${name}@2x.png` });
const PROMPT_LINES = [
  ['Calculate the delta between the PFS', 'and OS digital twins to identify which', 'parameters most strongly drive', 'Post-Progression Survival ?'],
  ['Compare the PFS and OS digital twins to', 'model Post-Progression Survival and', 'highlight top hazard drivers?'],
  ['Show how Grade 3+ AEs impact both', 'curves. How significantly does high', 'toxicity pull down the PFS curve versus', 'the OS twin compared to the baseline', 'cohort?'],
];
const IMG = {
  full: image('km-page-full'), // agent button hidden: it is fixed, drawn on its own
  rest: image('km-rest'),
  endpointHover: image('km-endpoint-hover'),
  endpointOpen: image('km-endpoint-open'),
  arms1Hover: image('km-arms1-hover'),
  arms1Open: image('km-arms1-open2'),
  arms2Open: image('km-arms2-open2'),
  fabHover: image('km-fab-hover'),
  // The drawer captures are cropped to the drawer itself (R.drawer): 21 full
  // frames at 2x are more than headless Chromium will decode at once.
  drawer: image('km-drawer-panel'),
  // km-prompt<i>-<k>: prompt i typed through the end of its line k.
  prompts: PROMPT_LINES.map((lines, i) => lines.map((_, k) => image(`km-prompt${i + 1}-${k + 1}-panel`))),
};
export const IMAGES = [IMG.full, IMG.rest, IMG.endpointHover, IMG.endpointOpen, IMG.arms1Hover, IMG.arms1Open,
  IMG.arms2Open, IMG.fabHover, IMG.drawer, ...IMG.prompts.flat()];

export const CUES = [];
const cue = (t, type, gain = 1) => CUES.push({ t: +t.toFixed(3), type, gain });

// ---------------------------------------------------------------- layout (page CSS px)
const VIEW = { w: 1440, h: 900 };
const R = {
  endpoint1: [933, 114, 224, 36],
  arms1: [1165, 114, 199, 36],
  arms2: [1165, 158, 199, 36],
  badge1: [1308, 123, 21, 18],
  badge2: [1308, 167, 21, 18],
  endpointMenu: [869, 154, 288, 206],
  pfsInUse: [876, 193, 274, 32],
  osItem: [876, 161, 274, 32],
  arms1Menu: [1064, 154, 300, 399],
  arms1Items: [[1065, 228, 298, 52], [1065, 280, 298, 32]],
  arms2Menu: [1064, 198, 300, 399],
  arms2Items: [[1065, 272, 298, 52], [1065, 324, 298, 32]],
  grid: [225, 291, 1090, 394],
  legend: [440, 740, 760, 88],
  legendRows: [747, 767, 787, 807], // OS/PFS heading, two arms, HR
  hr: [[489, 807, 26, 16], [797, 807, 24, 16]],
  medians: [443, 899, 228, 268], // Median (published) + Median (twin), header to last row
  twinStatus: [981, 899, 138, 268],
  fab: [1308, 810, 76, 46],
  fabHover: [1264, 810, 120, 46],
  drawer: [1020, 56, 420, 844],
  upload: [1128, 247, 211, 36],
};
// The composer grows by one 20 px line at a time, centred: its top rises 10 px per line.
const COMPOSER = { x: 1074, top1: 484, pad: 8, lh: 20, w: 283 };

// ---------------------------------------------------------------- timeline
const T_WIPE = [0.18, 0.95]; // curves draw along the time axis
const T_LEGEND = 0.85;
const T_FILTERS = 1.2; // camera leans into the filter cluster
const T_EP_HOVER = 1.55;
const T_EP_OPEN = 1.8;
const T_IN_USE = 2.05;
const T_EP_PICK = 2.5;
const T_A1_HOVER = 2.95;
const T_A1_OPEN = 3.1;
const T_A1_TICKS = [3.45, 3.75];
const T_A1_BADGE = 3.95;
const T_A1_CLOSE = 4.25;
const T_A2_OPEN = 4.55;
const T_A2_TICKS = [4.8, 4.98];
const T_A2_CLOSE = 5.22;
const T_CHART = 5.4; // camera pulls out to the chart, then leans to the legend
const T_LEGEND_LEAN = 5.75;
const T_HR = [6.0, 6.12];
const T_TABLE = 6.8; // the page scrolls to the table
const T_COLS = [7.3, 7.7];
const T_BACK = 8.4; // scroll back up
const T_FAB_HOVER = 8.68;
const T_FAB_CLICK = 8.85;
const T_COMPOSER = 9.3;
const SLOTS = [[9.45, 1.35], [10.85, 1.35], [12.25, 1.95]]; // [start, length] per prompt
const T_DRAWER_OUT = 14.2;
const T_UPLOAD = 14.6;
const T_CAPTION = 14.72;
const T_END = 15.6;

// ---------------------------------------------------------------- camera
// The page sits in a 1600 px wide sheet at x = 160. The camera is the page point
// at the frame centre plus a zoom; 1.8 is the 2x captures at native sharpness.
const B = 1600 / VIEW.w;
const cam = (T) => {
  const keys = [
    [0, [720, 500, 1.15]], // open on the chart, so the curves read at phone size
    // 1.9 with the right edge on the sheet's: the description's last word stays out of shot.
    [T_FILTERS, [1061, 300, 1.9]],
    [T_A2_OPEN - 0.2, [1061, 330, 1.9]],
    [T_CHART, [720, 450, 1]],
    [T_LEGEND_LEAN, [700, 615, 1.6]], // the lowest centre that keeps the sheet's edge out of frame
    [T_TABLE, [720, 450, 1.08]],
    [T_COLS[0] - 0.2, [780, 470, 1.6]],
    [T_BACK, [720, 450, 1]],
    [T_COMPOSER, [1061, 470, 1.9]],
    [T_DRAWER_OUT, [1061, 300, 1.9]],
  ];
  const v = (i) => track(T, keys.map(([t, p]) => [t, p[i]]), 'heavy');
  return { cx: v(0), cy: v(1), z: v(2) };
};
const scrollY = (T) => track(T, [[0, 0], [T_TABLE, 560], [T_BACK, 0]], 'ui');
// The sheet rises in from below at the start.
const enter = (T) => (1 - sp(T, 'ui')) * H;
const toScreen = (T, [x, y]) => {
  const c = cam(T);
  return [W / 2 + (x - c.cx) * B * c.z, H / 2 + (y - c.cy) * B * c.z + enter(T)];
};

// ---------------------------------------------------------------- sound
cue(0.02, 'whoosh', 0.4);
cue(T_WIPE[0], 'thump', 0.6);
cue(T_FILTERS, 'whoosh', 0.3);
cue(T_EP_HOVER, 'tick', 0.35);
cue(T_EP_OPEN, 'click', 0.8);
cue(T_IN_USE, 'pop', 0.4);
cue(T_EP_PICK, 'click', 0.7);
cue(T_A1_HOVER, 'tick', 0.35);
cue(T_A1_OPEN, 'click', 0.8);
T_A1_TICKS.forEach((t) => cue(t, 'click', 0.6));
cue(T_A1_BADGE, 'pop', 0.4);
cue(T_A2_OPEN, 'click', 0.8);
T_A2_TICKS.forEach((t) => cue(t, 'click', 0.6));
cue(T_CHART, 'whoosh', 0.35);
T_HR.forEach((t) => cue(t, 'pop', 0.45));
cue(T_TABLE, 'whoosh', 0.35);
T_COLS.forEach((t) => cue(t, 'tick', 0.45));
cue(T_BACK, 'whoosh', 0.3);
cue(T_FAB_HOVER, 'tick', 0.35);
cue(T_FAB_CLICK, 'click', 0.8);
cue(T_FAB_CLICK + 0.05, 'whoosh', 0.35);
SLOTS.forEach(([t0, d]) => { for (let t = t0 + 0.04; t < t0 + d * 0.72; t += 0.075) cue(t, 'tick', 0.12); });
cue(T_DRAWER_OUT, 'whoosh', 0.35);
cue(T_UPLOAD, 'pop', 0.5);
cue(T_END, 'whoosh', 0.3);

// ---------------------------------------------------------------- pieces
// A region of a capture, drawn where it sits on the page (dy shifts it, e.g. by scroll).
function blit(g, img, [x, y, w, h], dy = 0) {
  g.drawImage(img, x * 2, y * 2, w * 2, h * 2, x, y + dy, w, h);
}

// Our seafoam ring marks what to look at, never a UI state. `px` keeps it a
// constant width on screen whatever the zoom.
function ring(g, [x, y, w, h], p, px, pad = 6, r = 10) {
  if (p <= 0) return;
  g.save();
  g.globalAlpha *= clamp(p * 2);
  const s = 0.9 + 0.1 * p;
  const [cx, cy] = [x + w / 2, y + h / 2];
  g.translate(cx, cy);
  g.scale(s, s);
  g.strokeStyle = C.accent;
  g.lineWidth = 3 * px;
  rrect(g, -w / 2 - pad, -h / 2 - pad, w + pad * 2, h + pad * 2, r);
  g.stroke();
  g.restore();
}

// A menu unfolds from its trigger: it grows downward and settles from 96%.
function menu(g, img, rect, tOpen, tClose, T, inside = () => {}) {
  if (T < tOpen || T > tClose + 0.12) return;
  const p = sp(T - tOpen, 'snappy');
  const out = clamp((T - tClose) / 0.12);
  const [x, y, w, h] = rect;
  const pad = 14; // the menu's shadow
  g.save();
  g.globalAlpha *= clamp(p * 3) * (1 - out);
  g.beginPath();
  g.rect(x - pad, y - 4, w + pad * 2, (h + pad + 4) * clamp(p));
  g.clip();
  const s = 0.96 + 0.04 * p;
  g.translate(x + w / 2, y);
  g.scale(s, s);
  g.translate(-x - w / 2, -y);
  blit(g, img, [x - pad, y - 4, w + pad * 2, h + pad + 4]);
  inside();
  g.restore();
}

// Check marks pop in at their tick times; before that the row shows unticked.
function ticks(g, img, items, times, T) {
  items.forEach(([x, y, , h], i) => {
    const box = [x + 2, y + 2, 26, h - 4];
    g.fillStyle = C.sheet;
    g.fillRect(...box);
    const q = sp(T - times[i], 'snappy');
    if (q <= 0) return;
    const [bx, by, bw, bh] = box;
    g.save();
    g.translate(bx + bw / 2, by + bh / 2);
    g.scale(q, q);
    g.translate(-bx - bw / 2, -by - bh / 2);
    blit(g, img, box);
    g.restore();
  });
}

// The plot without its curves, keyed out of the real capture once (a cache, not
// frame state): saturated pixels are the curves, grey ones the grid.
let bare;
function bareGrid() {
  if (bare) return bare;
  const [x, y, w, h] = [R.grid[0] - 6, R.grid[1] - 6, R.grid[2] + 12, R.grid[3] + 12];
  bare = Object.assign(document.createElement('canvas'), { width: w * 2, height: h * 2 });
  const b = bare.getContext('2d');
  b.drawImage(IMG.full, x * 2, y * 2, w * 2, h * 2, 0, 0, w * 2, h * 2);
  const d = b.getImageData(0, 0, w * 2, h * 2);
  for (let i = 0; i < d.data.length; i += 4) {
    const [r, gg, bb] = [d.data[i], d.data[i + 1], d.data[i + 2]];
    if (Math.max(r, gg, bb) - Math.min(r, gg, bb) > 24) d.data[i] = d.data[i + 1] = d.data[i + 2] = 255;
  }
  b.putImageData(d, 0, 0);
  bare.rect = [x, y, w, h];
  return bare;
}

function curvesDraw(g, T) {
  const p = easeInOutCubic((T - T_WIPE[0]) / (T_WIPE[1] - T_WIPE[0]));
  if (p >= 1) return;
  const c = bareGrid();
  const [x, y, w, h] = c.rect;
  const edge = R.grid[0] + R.grid[2] * p;
  g.save();
  g.beginPath();
  g.rect(edge, y, x + w - edge, h);
  g.clip();
  g.drawImage(c, x, y, w, h);
  g.restore();
}

// The legend rows rise into place once the curves are drawn.
function legend(g, T) {
  const [x, y, w, h] = R.legend;
  g.fillStyle = C.sheet;
  g.fillRect(x, y, w, h);
  R.legendRows.forEach((ry, i) => {
    const p = sp(T - T_LEGEND - i * 0.05, 'snappy');
    if (p <= 0) return;
    g.save();
    g.beginPath();
    g.rect(x, ry - 2, w, 20);
    g.clip();
    g.drawImage(IMG.full, x * 2, (ry - 2) * 2, w * 2, 40, x, ry - 2 + (1 - p) * 18, w, 20);
    g.restore();
  });
}

// The floating agent button is fixed to the viewport, so it is drawn on its own.
function fab(g, T) {
  if (T >= T_FAB_CLICK + 0.05) return;
  const hover = T >= T_FAB_HOVER;
  const [x, y, w, h] = hover ? R.fabHover : R.fab;
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.14)';
  g.shadowBlur = 18;
  g.shadowOffsetY = 4;
  g.fillStyle = C.sheet;
  rrect(g, x, y, w, h, h / 2);
  g.fill();
  g.restore();
  g.save();
  rrect(g, x, y, w, h, h / 2);
  g.clip();
  blit(g, hover ? IMG.fabHover : IMG.rest, [x, y, w, h]);
  g.restore();
}

// Prompt i is typed at a steady rate over most of its slot, then held. The
// capture for the current line count shows the composer at its real height;
// the rest of the current line is masked, with a caret at the typing point.
function typing(T) {
  for (let i = SLOTS.length - 1; i >= 0; i--) {
    const [t0, d] = SLOTS[i];
    if (T < t0 || T >= t0 + d) continue;
    const lines = PROMPT_LINES[i];
    const total = lines.join(' ').length;
    const typed = Math.floor(total * clamp((T - t0) / (d * 0.72)));
    if (typed === 0) return null;
    let k = 0, before = 0;
    while (k < lines.length - 1 && typed > before + lines[k].length) { before += lines[k].length + 1; k++; }
    return { img: IMG.prompts[i][k], k, text: lines[k].slice(0, typed - before), done: typed >= total };
  }
  return null;
}

function drawer(g, T, px) {
  if (T < T_FAB_CLICK + 0.05) return;
  const p = sp(T - T_FAB_CLICK - 0.05, 'ui') - sp(T - T_DRAWER_OUT, 'ui');
  if (p <= 0.001) return;
  const [x, y, w, h] = R.drawer;
  const typed = typing(T);
  g.save();
  g.translate((1 - p) * (w + 30), 0);
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.12)';
  g.shadowBlur = 30;
  g.fillStyle = C.sheet;
  g.fillRect(x, y, w, h);
  g.restore();
  g.drawImage(typed ? typed.img : IMG.drawer, x, y, w, h);
  if (typed) {
    const top = COMPOSER.top1 - 10 * typed.k + COMPOSER.pad + typed.k * COMPOSER.lh;
    g.font = font(400, 14);
    const tw = g.measureText(typed.text).width;
    g.fillStyle = C.sheet;
    g.fillRect(COMPOSER.x + tw, top, COMPOSER.w - tw + 2, COMPOSER.lh);
    if (!typed.done) {
      g.fillStyle = C.ink;
      g.fillRect(COMPOSER.x + tw + 1, top + 2, 1.2, 16);
    }
  }
  g.restore();
}

// "Upload your own curves - coming soon", the button's own tooltip copy, in our type.
function caption(g, T) {
  const p = sp(T - T_CAPTION, 'snappy');
  if (p <= 0) return;
  const [x, y, w, h] = R.upload;
  const [rx, by] = toScreen(T, [x + w, y + h]);
  g.font = font(600, 40, 'display');
  risingText(g, 'Upload your own curves - coming soon', rx, by + 78, p, 0, 40, C.ink, 'right');
}

function cursor(g, T) {
  const c = (r, dx = 0.5, dy = 0.5) => [r[0] + r[2] * dx, r[1] + r[3] * dy];
  const [x, y] = track2(T, [
    [0, [1250, 420]],
    [T_FILTERS, [1250, 420]],
    [T_EP_HOVER - 0.2, c(R.endpoint1, 0.45)],
    [T_EP_PICK - 0.2, c(R.osItem, 0.35)],
    [T_A1_HOVER - 0.2, c(R.arms1, 0.4)],
    [T_A1_TICKS[0] - 0.18, c(R.arms1Items[0], 0.4)],
    [T_A1_TICKS[1] - 0.18, c(R.arms1Items[1], 0.4)],
    [T_A2_OPEN - 0.22, c(R.arms2, 0.4)],
    [T_A2_TICKS[0] - 0.15, c(R.arms2Items[0], 0.4)],
    [T_A2_TICKS[1] - 0.15, c(R.arms2Items[1], 0.4)],
    [T_CHART, [1180, 560]],
    [T_BACK, [1180, 620]],
    [T_FAB_HOVER - 0.2, c(R.fab)],
    [T_DRAWER_OUT, [1250, 420]],
    [T_UPLOAD - 0.2, c(R.upload, 0.55)],
  ], 'snappy');
  const presses = [T_EP_OPEN, T_EP_PICK, T_A1_OPEN, ...T_A1_TICKS, T_A2_OPEN, ...T_A2_TICKS, T_FAB_CLICK];
  const press = Math.max(0, ...presses.map((t0) => (T > t0 - 0.05 && T < t0 + 0.3 ? clamp((T - t0 + 0.05) / 0.35) : 0)));
  const alpha = Math.max(window01(T, T_FILTERS + 0.05, T_CHART + 0.15, 0.12, 0.15),
    window01(T, T_BACK + 0.05, T_FAB_CLICK + 0.25, 0.12, 0.15),
    window01(T, T_DRAWER_OUT + 0.05, T_END + 0.1, 0.12, 0.15));
  const [sx, sy] = toScreen(T, [x, y]);
  drawCursor(g, sx, sy, press, alpha);
}

// ---------------------------------------------------------------- the page
function page(g, T, px) {
  const s = scrollY(T);
  g.drawImage(IMG.full, 0, s * 2, VIEW.w * 2, VIEW.h * 2, 0, 0, VIEW.w, VIEW.h);
  if (T < T_WIPE[1]) curvesDraw(g, T);
  if (T < T_LEGEND + 0.6) legend(g, T);

  // Endpoint filter: hover border, then the menu with Progression-free survival "In use".
  if (T >= T_EP_HOVER && T < T_EP_OPEN) blit(g, IMG.endpointHover, R.endpoint1);
  if (T >= T_EP_OPEN && T < T_EP_PICK + 0.12) {
    blit(g, IMG.endpointOpen, R.endpoint1);
    menu(g, IMG.endpointOpen, R.endpointMenu, T_EP_OPEN, T_EP_PICK, T);
    if (T < T_EP_PICK) ring(g, R.pfsInUse, sp(T - T_IN_USE, 'snappy'), px, 2, 8);
  }

  // Treatment arms, OS then PFS: each menu opens on its coBRIM group and both arms tick.
  if (T >= T_A1_HOVER && T < T_A1_OPEN) blit(g, IMG.arms1Hover, R.arms1);
  if (T >= T_A1_OPEN && T < T_A1_CLOSE + 0.12) {
    blit(g, IMG.arms1Open, R.arms1);
    menu(g, IMG.arms1Open, R.arms1Menu, T_A1_OPEN, T_A1_CLOSE, T, () => ticks(g, IMG.arms1Open, R.arms1Items, T_A1_TICKS, T));
  }
  ring(g, R.badge1, window01(T, T_A1_BADGE, T_A2_OPEN - 0.1, 0.01, 0.15) * sp(T - T_A1_BADGE, 'snappy'), px, 4, 8);
  if (T >= T_A2_OPEN && T < T_A2_CLOSE + 0.12) {
    blit(g, IMG.arms2Open, R.arms2);
    menu(g, IMG.arms2Open, R.arms2Menu, T_A2_OPEN, T_A2_CLOSE, T, () => ticks(g, IMG.arms2Open, R.arms2Items, T_A2_TICKS, T));
  }

  // The legend's twin hazard ratios, then the published-vs-twin columns.
  R.hr.forEach((r, i) => ring(g, r, window01(T, T_HR[i], T_TABLE, 0.01, 0.15) * sp(T - T_HR[i], 'snappy'), px, 5, 6));
  [R.medians, R.twinStatus].forEach(([x, y, w, h], i) =>
    ring(g, [x, y - s, w, h], window01(T, T_COLS[i], T_BACK, 0.01, 0.15) * sp(T - T_COLS[i], 'snappy'), px, 2, 10));

  fab(g, T);
  drawer(g, T, px);
  ring(g, R.upload, sp(T - T_UPLOAD, 'snappy'), px, 5, 22);
}

// ---------------------------------------------------------------- frame
export function draw(g, T) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.imageSmoothingQuality = 'high';
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);

  const c = cam(T);
  const px = 1 / (B * c.z); // one screen pixel in page units
  g.save();
  g.translate(W / 2, H / 2 + enter(T));
  g.scale(B * c.z, B * c.z);
  g.translate(-c.cx, -c.cy);
  // The page is one white sheet with one soft shadow.
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.10)';
  g.shadowBlur = 48; // canvas shadows are in screen px, untouched by the transform
  g.shadowOffsetY = 14;
  g.fillStyle = C.sheet;
  rrect(g, 0, 0, VIEW.w, VIEW.h, 14);
  g.fill();
  g.restore();
  g.save();
  rrect(g, 0, 0, VIEW.w, VIEW.h, 14);
  g.clip();
  page(g, T, px);
  g.restore();
  g.restore();

  caption(g, T);
  cursor(g, T);

  const e = easeInOutCubic((T - T_END) / 0.35);
  if (e > 0) {
    g.globalAlpha = e;
    g.fillStyle = C.bg;
    g.fillRect(0, 0, W, H);
    g.globalAlpha = 1;
  }
}
