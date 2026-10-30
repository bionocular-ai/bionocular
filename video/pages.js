// Product tour chapter: the dashboard pages a user lands on before asking the
// agent, one filter per page, in sidebar order. Trial Updates (New 33), Live
// News (Efficacy & Safety, then All 10 values), Trial Landscape (Group by Line of
// therapy), Outcome Intelligence Hub (Phase 3, two readouts ticked, the agent opens on them),
// Efficacy Intelligence Hub (Phase 3, the bars rebuild). Each page change is a
// click on the rail, which stays put on the left.
// Everything is a pure function of global time T (seconds). No timers, no state.
// Storyboard: docs/storyboard-pages.md. Every screen is a real 2x capture of the
// page at 1440x900 CSS px (the Efficacy hub at 1440x1500, to hold its chart),
// from scripts/capture-pages.sh; all coordinates below are those CSS px,
// measured from the live DOM.

import { clamp, sp, track, track2, window01, easeInOutCubic, easeOutCubic } from './lib/motion.js';
import { rrect, drawCursor } from './lib/draw.js';

export const FILM = { title: 'pages-chapter', w: 1920, h: 1080, dur: 21.7, bpm: 120 };
const { w: W, h: H } = FILM;

// Bionocular tokens (web/src/app/globals.css).
const C = {
  bg: '#F7FAF9',
  sheet: '#FFFFFF',
  accent: '#7AC1A2',
  line: '#C8E0D8',
};

const image = (name) => Object.assign(new Image(), { src: `assets/screens/pages/${name}@2x.png` });
const IMG = {
  tuAll: image('tu-all'),
  tuNew: image('tu-new'),
  tuHover: image('tu-new-hover'), // every *-hover: the page's last state, pointer on the next rail icon
  lnLatest: image('ln-latest'),
  lnEff: image('ln-efficacy'),
  lnOpen: image('ln-efficacy-open'),
  lnHover: image('ln-efficacy-open-hover'),
  lsMod: image('ls-modality'),
  lsMenu: image('ls-menu'),
  lsLine: image('ls-line'),
  lsHover: image('ls-line-hover'),
  hubRest: image('hub-rest'),
  hubP3: image('hub-p3'),
  hubSel: image('hub-2sel'),
  hubHover: image('hub-2sel-hover'),
  hubAgent: image('hub-agent'), // the agent drawer open on the two ticked readouts
  effAll: image('eff-all'),
  effP3: image('eff-p3'),
  effEmpty: image('eff-p3-empty'), // Phase 3 with the bars, dots and median hidden
};
export const IMAGES = Object.values(IMG);

export const CUES = [];
const cue = (t, type, gain = 1) => CUES.push({ t: +t.toFixed(3), type, gain });

// ---------------------------------------------------------------- layout (page CSS px)
const VIEW = { w: 1440, h: 900 };
const CONTENT = [56, 56, 1384, 844]; // right of the rail, below the top bar
const RAIL = { ln: [28, 116], ls: [28, 151], hub: [28, 204], eff: [29, 274], km: [28, 397], agent: [28, 450] }; // icon centres
const R = {
  tuNew: [263, 278, 74, 32],
  tuChips: [132, 270, 540, 48],
  tuFeed: 330, // the day groups start here
  lnEff: [1218, 119, 141, 32],
  lnFeed: 230,
  lnRoundup: [56, 230, 1384, 146], // Oct 28's ESMO roundup, which Efficacy & Safety drops
  lnRise: 132, // Oct 27 moves from 376 to 244
  lnAll10: [320, 405, 105, 28],
  lnButton: [310, 398, 260, 40],
  lnUnfold: 435, // the six more values open below the button...
  lnExtra: 149, // ...and push the rest of the feed down this far
  lsGroupBy: [222, 245, 176, 38],
  lsToolbar: [132, 228, 1232, 72],
  lsMenu: [222, 289, 208, 210],
  lsLine: [223, 414, 206, 40],
  lsCols: 310, // column heads at 324
  hubP3: [72, 265, 15, 15],
  hubP3Label: [72, 259, 231, 34],
  hubFilters: [56, 56, 288, 844],
  hubMain: [344, 56, 1096, 844],
  hubBoxes: [[363, 261, 15, 15], [363, 585, 15, 15]],
  hubCards: [[344, 238, 1072, 318], [344, 562, 1072, 338]],
  hubHead: [344, 198, 1072, 40], // "65 readouts ... 2 of 5 selected for the agent"
  fabSel: [1308, 810, 76, 46], // grows left from 46 px to show the 2 badge
  drawer: [1020, 56, 420, 844],
  agentList: [1053, 133, 355, 133], // "Answering about these 2 readouts", both listed
  agentClose: [1398, 69, 26, 26],
  effP3: [772, 310, 67, 24],
  effBars: { x: 176, w: 1168, top: 520, base: 963 },
};

// ---------------------------------------------------------------- timeline
const T_TU_LEAN = 0.75;
const T_TU_CLICK = 2.0; // SHOW New 33
const T_TU_WIPE = 2.05;
const T_TU_HOVER = 3.55;
const T_LN = 4.0; // rail click: Live News
const T_LN_LEAN = 4.45;
const T_LN_CLICK = 5.0; // VIEW Efficacy & Safety
const T_LN_RISE = 5.05;
const T_LN_SWAP = 5.6; // the risen Latest feed hands over to the Efficacy & Safety capture
const T_LN_OPEN_LEAN = 5.9;
const T_LN_OPEN = 6.35; // All 10 values
const T_LN_HOVER = 7.2;
const T_LS = 7.6; // rail click: Trial Landscape
const T_LS_LEAN = 8.05;
const T_LS_MENU = 8.45; // Group by opens
const T_LS_PICK = 9.1; // Line of therapy
const T_LS_COLS = 9.12; // straight after the pick, so the page never sits empty
const T_LS_HOVER = 10.8;
const T_HUB = 11.2; // rail click: Outcome Intelligence Hub
const T_HUB_LEAN = 11.65;
const T_HUB_P3 = 12.05; // Phase 3
const T_HUB_CARDS = 12.6;
const T_HUB_TICKS = [13.1, 13.45];
const T_HUB_SEL = 13.55; // "2 of 5 selected for the agent", the agent button grows its badge
const T_HUB_WIDE = 13.6;
const T_FAB = 14.2; // the agent opens on the two readouts
const T_AGENT_LEAN = 14.45;
const T_AGENT_LIST = 14.85;
const T_CLOSE = 16.0;
const T_HUB_HOVER = 16.8;
const T_EFF = 17.2; // rail click: Efficacy
const T_EFF_LEAN = 17.6;
const T_EFF_P3 = 18.1; // Phase 3
const T_EFF_SCROLL = 18.25;
const T_EFF_GROW = [18.6, 19.5];
const T_END = 21.2;

// ---------------------------------------------------------------- camera
// The page sits in a 1600 px wide sheet; the camera is the page point at the frame
// centre plus a zoom (1.8 is the 2x captures at native sharpness). A lean keeps the
// sheet's left edge 40+ px inside the frame (cx <= 920 / (B * z)), so the rail is never cut.
const B = 1600 / VIEW.w;
const RAIL_SHOT = [560, 420, 1.15]; // wide enough for the rail and the page beside it
const cam = (T) => {
  const keys = [
    [0, [560, 330, 1.25]],
    [T_TU_LEAN, [400, 300, 1.8]], // the count line and the SHOW chips
    [T_TU_WIPE + 0.1, [590, 450, 1.4]], // the new registrations, day by day
    [T_TU_HOVER - 0.4, RAIL_SHOT],
    [T_LN_LEAN, [700, 300, 1.25]], // logo and title through the VIEW chips, nothing cut mid-word
    [T_LN_RISE + 0.05, [590, 440, 1.4]], // the readouts rising into the roundup's place
    [T_LN_OPEN_LEAN, [610, 520, 1.35]], // the day and the metric grid, below the header
    [T_LN_HOVER - 0.4, RAIL_SHOT],
    [T_LS_LEAN, [420, 340, 1.8]], // Group by and its menu
    [T_LS_COLS - 0.05, [720, 520, 1.12]],
    [T_LS_HOVER - 0.4, RAIL_SHOT],
    [T_HUB_LEAN, [330, 300, 1.7]], // the Phase filter beside the readout count
    [T_HUB_CARDS, [700, 420, 1.35]], // below the top bar
    [T_HUB_WIDE, [760, 470, 1.05]], // out to the agent button and its badge
    [T_AGENT_LEAN, [912, 360, 1.5]], // the hub title and ticked cards beside the drawer that names them; the frame's left edge on the filter column's border
    [T_CLOSE + 0.1, [760, 470, 1.05]],
    [T_HUB_HOVER - 0.4, RAIL_SHOT],
    [T_EFF_LEAN, [500, 300, 1.65]], // logo to the last PHASE chip
    [T_EFF_SCROLL, [662, 480, 1.25]], // the chart, every bar in shot
  ];
  const v = (i) => track(T, keys.map(([t, p]) => [t, p[i]]), 'heavy');
  return { cx: v(0), cy: v(1), z: v(2) };
};
// Only the Efficacy hub scrolls: down to its chart once Phase 3 is picked.
export const EFF_SCROLL = 230;
const scrollY = (T) => track(T, [[0, 0], [T_EFF_SCROLL, EFF_SCROLL]], 'ui');
let rise = true; // set per frame from draw()'s opts, never carried between frames
const enter = (T) => (rise ? (1 - sp(T, 'ui')) * H : 0);
const toScreen = (T, [x, y]) => {
  const c = cam(T);
  return [W / 2 + (x - c.cx) * B * c.z, H / 2 + (y - c.cy) * B * c.z + enter(T)];
};

// ---------------------------------------------------------------- sound
cue(0.02, 'whoosh', 0.4);
cue(0.3, 'thump', 0.6);
[T_TU_LEAN, T_LN_LEAN, T_LS_LEAN, T_HUB_LEAN, T_EFF_LEAN].forEach((t) => cue(t, 'whoosh', 0.25));
[T_TU_CLICK, T_LN_CLICK, T_LN_OPEN, T_LS_MENU, T_LS_PICK, T_HUB_P3, ...T_HUB_TICKS, T_EFF_P3].forEach((t) => cue(t, 'click', 0.75));
[T_TU_HOVER, T_LN_HOVER, T_LS_HOVER, T_HUB_HOVER].forEach((t) => cue(t, 'tick', 0.3));
[T_LN, T_LS, T_HUB, T_EFF].forEach((t) => { cue(t, 'click', 0.8); cue(t + 0.05, 'whoosh', 0.35); });
for (let i = 0; i < 4; i++) cue(T_TU_WIPE + 0.1 + i * 0.09, 'tick', 0.25);
cue(T_LN_RISE + 0.05, 'whoosh', 0.3);
cue(T_LN_OPEN + 0.05, 'pop', 0.45);
for (let i = 0; i < 5; i++) cue(T_LS_COLS + i * 0.07, 'tick', 0.25);
cue(T_HUB_SEL + 0.1, 'pop', 0.6);
cue(T_FAB, 'click', 0.8);
cue(T_FAB + 0.05, 'whoosh', 0.35);
cue(T_AGENT_LIST, 'tick', 0.45);
cue(T_CLOSE, 'click', 0.7);
cue(T_CLOSE + 0.05, 'whoosh', 0.3);
for (let i = 0; i < 5; i++) cue(T_EFF_GROW[0] + i * 0.12, 'tick', 0.25);
cue(T_END, 'whoosh', 0.3);

// ---------------------------------------------------------------- pieces
// A region of a capture, drawn where it sits on the page. `s` is the capture's
// scroll (the Efficacy hub only); dy shifts the drawn copy.
export function blit(g, img, [x, y, w, h], dy = 0, s = 0) {
  g.drawImage(img, x * 2, (y + s) * 2, w * 2, h * 2, x, y + dy, w, h);
}

// A whole viewport. The top bar and rail are fixed; only the content scrolls.
export function view(g, img, s = 0) {
  if (!s) return g.drawImage(img, 0, 0, VIEW.w * 2, VIEW.h * 2, 0, 0, VIEW.w, VIEW.h);
  g.drawImage(img, 0, 0, VIEW.w * 2, 112, 0, 0, VIEW.w, 56);
  g.drawImage(img, 0, 112, 112, 1688, 0, 56, 56, 844);
  blit(g, img, CONTENT, 0, s);
}

export function clipped(g, [x, y, w, h], fn) {
  if (w <= 0 || h <= 0) return;
  g.save();
  g.beginPath();
  g.rect(x, y, w, h);
  g.clip();
  fn();
  g.restore();
}

// A rail click: the rail turns to the new page at once; the page area wipes in
// from the top over the old one, behind a hairline edge, the new page settling 6 px
// as it lands so the swap reads as a page change. `from` is a capture or a painter.
export function pageIn(g, from, to, t0, T, fromScroll = 0) {
  if (typeof from === 'function') from(g); else view(g, from, fromScroll);
  blit(g, to, [0, 56, 56, 844]);
  const p = clamp(sp(T - t0, 'ui'));
  const [x, y, w, h] = CONTENT;
  clipped(g, [x, y, w, h * p], () => {
    g.save();
    g.translate(0, (1 - p) * 6);
    view(g, to);
    g.restore();
  });
  if (p > 0 && p < 0.995) {
    g.save();
    g.globalAlpha = Math.min(1, (1 - p) * 8);
    g.fillStyle = C.line;
    g.fillRect(x, y + h * p - 1, w, 1);
    g.restore();
  }
}

// Hovering a rail icon opens the labelled flyout: it slides out from the rail.
export function railHover(g, img, t0, T) {
  if (T < t0) return;
  const p = clamp(sp(T - t0, 'snappy'));
  clipped(g, [0, 0, 56 + (VIEW.w - 56) * p, VIEW.h], () => view(g, img));
}

// A checkbox ticks: the ticked box springs in from its centre.
function tick(g, img, [x, y, w, h], t0, T) {
  const q = sp(T - t0, 'snappy');
  if (q <= 0) return;
  const pad = 2;
  g.save();
  g.fillStyle = C.sheet;
  g.fillRect(x - pad, y - pad, w + pad * 2, h + pad * 2);
  g.translate(x + w / 2, y + h / 2);
  g.scale(q, q);
  g.translate(-x - w / 2, -y - h / 2);
  blit(g, img, [x - pad, y - pad, w + pad * 2, h + pad * 2]);
  g.restore();
}

// Our seafoam ring marks what to look at, never a UI state. `px` keeps it a
// constant width on screen whatever the zoom.
function ring(g, [x, y, w, h], p, px, pad = 6, r = 10) {
  if (p <= 0) return;
  g.save();
  g.globalAlpha *= clamp(p * 2);
  const s = 0.9 + 0.1 * p;
  g.translate(x + w / 2, y + h / 2);
  g.scale(s, s);
  g.strokeStyle = C.accent;
  g.lineWidth = 3 * px;
  rrect(g, -w / 2 - pad, -h / 2 - pad, w + pad * 2, h + pad * 2, r);
  g.stroke();
  g.restore();
}

// A menu unfolds from its trigger: it grows downward and settles from 96%.
function menu(g, img, rect, tOpen, tClose, T) {
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
  g.restore();
}

// ---------------------------------------------------------------- pages
// Trial Updates: SHOW New 33; the day groups re-stack top-down to the new registrations.
function trialUpdates(g, T) {
  if (T < T_TU_CLICK) return view(g, IMG.tuAll);
  view(g, IMG.tuAll);
  blit(g, IMG.tuNew, R.tuChips);
  const p = clamp(sp(T - T_TU_WIPE, 'ui'));
  const top = R.tuFeed;
  const edge = top + (VIEW.h - top) * p;
  clipped(g, [56, top, 1384, edge - top], () => {
    g.fillStyle = C.bg;
    g.fillRect(56, top, 1384, edge - top);
    blit(g, IMG.tuNew, [56, top, 1384, VIEW.h - top], (1 - p) * 24);
  });
  railHover(g, IMG.tuHover, T_TU_HOVER, T);
}

// Live News: Efficacy & Safety drops the roundup and the readouts rise; then
// Chidamide + Nivolumab's grid unfolds from 4 values to 10.
function liveNews(g, T) {
  if (T < T_LN + 0.8) return pageIn(g, IMG.tuNew, IMG.lnLatest, T_LN, T);
  if (T < T_LN_CLICK) return view(g, IMG.lnLatest);
  if (T < T_LN_OPEN) {
    const p = sp(T - T_LN_RISE, 'ui');
    const swap = clamp((T - T_LN_SWAP) / 0.15);
    view(g, IMG.lnEff); // header: VIEW Efficacy & Safety, All months 40
    const top = R.lnFeed;
    clipped(g, [56, top, 1384, VIEW.h - top], () => {
      g.fillStyle = C.bg;
      g.fillRect(56, top, 1384, VIEW.h - top);
      g.globalAlpha = 1 - swap;
      const [rx, ry, rw, rh] = R.lnRoundup;
      g.save();
      g.globalAlpha *= 1 - clamp(p * 1.6); // the roundup leaves upward as the readouts take its place
      blit(g, IMG.lnLatest, [rx, ry, rw, rh], -R.lnRise * p);
      g.restore();
      blit(g, IMG.lnLatest, [56, ry + rh, 1384, VIEW.h - ry - rh], -R.lnRise * p);
      g.globalAlpha = swap;
      blit(g, IMG.lnEff, [56, top, 1384, VIEW.h - top]);
      g.globalAlpha = 1;
    });
    return;
  }
  // The six more values open below the button and push the feed down.
  const q = clamp(easeOutCubic((T - T_LN_OPEN - 0.05) / 0.45));
  const u = R.lnUnfold;
  view(g, IMG.lnEff);
  blit(g, IMG.lnOpen, R.lnButton); // All 10 values -> Show fewer values
  clipped(g, [56, u, 1384, VIEW.h - u], () => {
    g.fillStyle = C.bg;
    g.fillRect(56, u, 1384, VIEW.h - u);
    blit(g, IMG.lnEff, [56, u, 1384, VIEW.h - u], R.lnExtra * q);
    clipped(g, [56, u, 1384, R.lnExtra * q], () => blit(g, IMG.lnOpen, [56, u, 1384, R.lnExtra]));
  });
  railHover(g, IMG.lnHover, T_LN_HOVER, T);
}

// Trial Landscape: Group by opens, Line of therapy is picked, the columns unfold left to right.
function landscape(g, T) {
  if (T < T_LS + 0.8) return pageIn(g, IMG.lnOpen, IMG.lsMod, T_LS, T);
  if (T < T_LS_PICK) {
    view(g, IMG.lsMod);
    if (T >= T_LS_MENU) {
      blit(g, IMG.lsMenu, R.lsGroupBy);
      menu(g, IMG.lsMenu, R.lsMenu, T_LS_MENU, T_LS_PICK, T);
    }
    return;
  }
  view(g, IMG.lsMod);
  menu(g, IMG.lsMenu, R.lsMenu, T_LS_MENU, T_LS_PICK, T);
  blit(g, IMG.lsLine, R.lsToolbar);
  const top = R.lsCols;
  g.fillStyle = C.bg;
  g.save();
  g.globalAlpha = clamp((T - T_LS_PICK) / 0.08); // the modality columns clear
  g.fillRect(56, top, 1384, VIEW.h - top);
  g.restore();
  for (let i = 0; i < 5; i++) {
    const q = sp(T - T_LS_COLS - i * 0.07, 'ui');
    if (q <= 0) continue;
    const x = 132 + 256 * i - 6;
    // Masked, not faded: navy cards at part opacity read as grey.
    const dy = (1 - q) * 40;
    clipped(g, [x, top, 252, (VIEW.h - top) * clamp(q)], () => g.drawImage(IMG.lsLine, x * 2, top * 2, 252 * 2,
      (VIEW.h - top) * 2, x, top + dy, 252, VIEW.h - top));
  }
  railHover(g, IMG.lsHover, T_LS_HOVER, T);
}

// Outcome Intelligence Hub: Phase 3 narrows 200 readouts to 65; two are ticked
// for the agent, whose button grows a 2 badge.
function hub(g, T, px) {
  if (T < T_HUB + 0.8) return pageIn(g, IMG.lsLine, IMG.hubRest, T_HUB, T);
  if (T < T_HUB_P3) return view(g, IMG.hubRest);
  view(g, IMG.hubRest);
  if (T >= T_HUB_P3 + 0.06) blit(g, IMG.hubP3, R.hubFilters); // every count re-tallies
  tick(g, IMG.hubP3, R.hubP3, T_HUB_P3, T);
  const p = clamp(sp(T - T_HUB_P3 - 0.08, 'ui'));
  const [mx, my, mw, mh] = R.hubMain;
  clipped(g, [mx, my, mw, mh * p], () => blit(g, IMG.hubP3, R.hubMain, (1 - p) * 24));
  // Each ticked card takes its selected look, its box springing in.
  R.hubCards.forEach((card, i) => {
    const a = clamp((T - T_HUB_TICKS[i]) / 0.12);
    if (a <= 0) return;
    g.save();
    g.globalAlpha = a;
    blit(g, IMG.hubSel, card);
    g.restore();
    tick(g, IMG.hubSel, R.hubBoxes[i], T_HUB_TICKS[i], T);
  });
  if (T >= T_HUB_SEL) {
    const q = sp(T - T_HUB_SEL, 'snappy');
    const [hx, hy, hw, hh] = R.hubHead;
    clipped(g, R.hubHead, () => {
      g.fillStyle = C.bg;
      g.fillRect(hx, hy, hw, hh);
      blit(g, IMG.hubSel, R.hubHead, (1 - clamp(q)) * hh * 0.6);
    });
    // The agent button grows left to make room for its badge.
    const [fx, fy, fw, fh] = R.fabSel;
    const grow = clamp(q);
    clipped(g, [fx - 16 + 30 * (1 - grow), fy - 10, fw + 32 - 30 * (1 - grow), fh + 26], () => blit(g, IMG.hubSel, [fx - 16, fy - 10, fw + 32, fh + 26]));
    ring(g, R.fabSel, window01(T, T_HUB_SEL + 0.15, T_FAB, 0.01, 0.12) * sp(T - T_HUB_SEL - 0.15, 'snappy'), px, 6, 29);
  }
  drawer(g, T, px);
  railHover(g, IMG.hubHover, T_HUB_HOVER, T);
}

// The agent drawer slides in from the right, already answering about the two
// ticked readouts, and slides back out on its close button.
function drawer(g, T, px) {
  const p = sp(T - T_FAB - 0.05, 'ui') - sp(T - T_CLOSE - 0.05, 'ui');
  if (T < T_FAB + 0.05 || p <= 0.001) return;
  const [x, y, w, h] = R.drawer;
  g.save();
  g.translate((1 - p) * (w + 30), 0);
  g.save();
  g.shadowColor = 'rgba(16, 43, 54, 0.12)';
  g.shadowBlur = 30;
  g.fillStyle = C.sheet;
  g.fillRect(x, y, w, h);
  g.restore();
  blit(g, IMG.hubAgent, R.drawer);
  ring(g, R.agentList, window01(T, T_AGENT_LIST, T_CLOSE, 0.01, 0.12) * sp(T - T_AGENT_LIST, 'snappy'), px, 10, 12);
  g.restore();
}

// Efficacy Intelligence Hub: Phase 3; the page scrolls to the chart and the bars rebuild.
function efficacy(g, T) {
  if (T < T_EFF + 0.8) return pageIn(g, IMG.hubSel, IMG.effAll, T_EFF, T);
  if (T < T_EFF_P3) return view(g, IMG.effAll);
  const s = scrollY(T);
  view(g, IMG.effEmpty, s); // Phase 3 picked, 33 treatments / 58 trials, the chart cleared
  const { x, w, top, base } = R.effBars;
  const q = clamp(easeOutCubic((T - T_EFF_GROW[0]) / (T_EFF_GROW[1] - T_EFF_GROW[0])));
  const y = base - (base - top) * q;
  clipped(g, [x, Math.max(56, y - s), w, base - y], () => blit(g, IMG.effP3, [x, y, w, base - y], -s, 0));
}

function cursor(g, T) {
  const c = (r, dx = 0.5, dy = 0.5) => [r[0] + r[2] * dx, r[1] + r[3] * dy];
  const [x, y] = track2(T, [
    [0, [760, 520]],
    [T_TU_LEAN + 0.2, [620, 430]],
    [T_TU_CLICK - 0.35, c(R.tuNew, 0.45)],
    [T_TU_WIPE + 0.3, [560, 560]],
    [T_TU_HOVER - 0.3, RAIL.ln],
    [T_LN + 0.3, [700, 420]],
    [T_LN_CLICK - 0.4, c(R.lnEff, 0.45)],
    [T_LN_RISE + 0.3, [900, 440]],
    [T_LN_OPEN - 0.4, c(R.lnAll10, 0.4)],
    [T_LN_OPEN + 0.3, [620, 600]],
    [T_LN_HOVER - 0.3, RAIL.ls],
    [T_LS + 0.3, [600, 420]],
    [T_LS_MENU - 0.35, c(R.lsGroupBy, 0.4)],
    [T_LS_PICK - 0.35, c(R.lsLine, 0.35)],
    [T_LS_COLS + 0.3, [700, 620]],
    [T_LS_HOVER - 0.3, RAIL.hub],
    [T_HUB + 0.3, [300, 420]],
    [T_HUB_P3 - 0.35, c(R.hubP3Label, 0.2)],
    [T_HUB_TICKS[0] - 0.35, c(R.hubBoxes[0])],
    [T_HUB_TICKS[1] - 0.3, c(R.hubBoxes[1])],
    [T_HUB_SEL + 0.2, [1000, 640]],
    [T_FAB - 0.35, [1336, 833]],
    [T_FAB + 0.35, [980, 520]],
    [T_CLOSE - 0.4, c(R.agentClose)],
    [T_CLOSE + 0.3, [900, 520]],
    [T_HUB_HOVER - 0.3, RAIL.eff],
    [T_EFF + 0.3, [640, 420]],
    [T_EFF_P3 - 0.35, c(R.effP3, 0.45)],
    [T_EFF_SCROLL + 0.2, [1100, 720]],
  ], 'snappy');
  const presses = [T_TU_CLICK, T_LN, T_LN_CLICK, T_LN_OPEN, T_LS, T_LS_MENU, T_LS_PICK, T_HUB, T_HUB_P3,
    ...T_HUB_TICKS, T_FAB, T_CLOSE, T_EFF, T_EFF_P3];
  const press = Math.max(0, ...presses.map((t0) => (T > t0 - 0.05 && T < t0 + 0.3 ? clamp((T - t0 + 0.05) / 0.35) : 0)));
  const alpha = window01(T, T_TU_LEAN + 0.2, T_EFF_GROW[0] + 0.3, 0.12, 0.2);
  const [sx, sy] = toScreen(T, [x, y]);
  drawCursor(g, sx, sy, press, alpha);
}

// ---------------------------------------------------------------- frame
// The page as one white sheet with one soft shadow, seen by camera c ({ cx, cy, z });
// paint(px) draws in page px, px being one screen pixel. dy lifts the sheet (its rise);
// bare skips the sheet itself, to paint over a sheet already drawn at that camera.
export function sheet(g, c, paint, dy = 0, bare = false) {
  g.save();
  g.translate(W / 2, H / 2 + dy);
  g.scale(B * c.z, B * c.z);
  g.translate(-c.cx, -c.cy);
  if (!bare) {
    g.save();
    g.shadowColor = 'rgba(16, 43, 54, 0.10)';
    g.shadowBlur = 48; // canvas shadows are in screen px, untouched by the transform
    g.shadowOffsetY = 14;
    g.fillStyle = C.sheet;
    rrect(g, 0, 0, VIEW.w, VIEW.h, 14);
    g.fill();
    g.restore();
  }
  g.save();
  rrect(g, 0, 0, VIEW.w, VIEW.h, 14);
  g.clip();
  paint(1 / (B * c.z));
  g.restore();
  g.restore();
}
// Page px -> screen px for camera c.
export const onScreen = (c, [x, y]) => [W / 2 + (x - c.cx) * B * c.z, H / 2 + (y - c.cy) * B * c.z];

// Where the tour leaves off for the master: the Efficacy hub's bars built, the camera settled.
export const T_DONE = T_EFF_GROW[1] + 0.4;
export const camAt = (T) => cam(T);
export const efficacyDone = (g) => efficacy(g, T_DONE);
export { B, VIEW, CONTENT, RAIL, IMG };

function page(g, T, px) {
  if (T < T_LN) return trialUpdates(g, T);
  if (T < T_LS) return liveNews(g, T);
  if (T < T_HUB) return landscape(g, T);
  if (T < T_EFF) return hub(g, T, px);
  efficacy(g, T);
}

// opts.rise false: the sheet starts in place instead of rising in.
export function draw(g, T, opts = {}) {
  rise = opts.rise !== false;
  const mac = g.mac;
  g.mac = true; // the macOS pointer, here and inside any master film
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.imageSmoothingQuality = 'high';
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);

  sheet(g, cam(T), (px) => page(g, T, px), enter(T));

  cursor(g, T);

  const e = easeInOutCubic((T - T_END) / 0.35);
  if (e > 0) {
    g.globalAlpha = e;
    g.fillStyle = C.bg;
    g.fillRect(0, 0, W, H);
    g.globalAlpha = 1;
  }
  g.mac = mac;
}
