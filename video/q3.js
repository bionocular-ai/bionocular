// Question 3 chapter: one question, Gemini and Opus side by side (Gemini's
// grade 3+ TEAE columns crossed out, Opus's table swapped for its cross-checked
// copy with red cells lifted out one by one), the Bionocular answer, and a tally card whose bars
// drop from the treatment arms each answer gave to the arms that survived the
// cross-check. Everything is a pure function of global time T (seconds).
// Storyboard: docs/storyboard-q3.md. Competitor answers are the user's
// screenshots (1x); the Bionocular answer is a 2x capture of a Q3 run on
// 2026-10-20. Every coordinate below is measured from their pixels.

import { clamp, lerp, sp, track, track2, window01, easeOutCubic, easeInOutCubic, lift } from './lib/motion.js';
import { rrect, risingText, font, drawCursor, liftOut } from './lib/draw.js';

export const FILM = { title: 'q3-chapter', w: 1920, h: 1080, dur: 20.95, bpm: 120 };
const { w: W, h: H } = FILM;

// Bionocular tokens (web/src/app/globals.css); red is its --destructive.
const C = {
  bg: '#F7FAF9',
  sheet: '#FFFFFF',
  ink: '#102B36',
  muted: '#4A6B77',
  line: '#C8E0D8',
  primary: '#1B4F65',
  accent: '#7AC1A2',
  tint: '#DAF0E6',
  red: '#EF4444',
  redText: '#DC2626',
};

const image = (name) => Object.assign(new Image(), { src: `assets/screens/${name}.png` });
const IMG = {
  gem1: image('q3-gemini-part1'),
  gem2: image('q3-gemini-part2'),
  opus1: image('q3-opus-part1'),
  opus2: image('q3-opus-part2'),
  opus3: image('q3-opus-part3'),
  checked: image('q3-opus-corrected'),
  bio: image('q3-bio-answer@2x'),
  reviewed: image('q3-reviewed-hover@2x'), // the expert-review filter, hovered
  // The same answer with Charts open on Bubble, from the toggle down to the hub link,
  // and the same again with the bubbles and their labels hidden.
  charts: image('q3-charts-bubble@2x'),
  chartsEmpty: image('q3-charts-empty@2x'),
  logo: Object.assign(new Image(), { src: 'assets/logo.svg' }),
};
const LOGO_ASPECT = 127.35 / 148.3; // logo.svg viewBox width / height
export const IMAGES = Object.values(IMG);

export const CUES = [];
const cue = (t, type, gain = 1) => CUES.push({ t: +t.toFixed(3), type, gain });

// ---------------------------------------------------------------- timeline
const Q = { lines: [0.08, 0.16, 0.24], marks: [0.42, 0.5, 0.58, 0.66], shrink: 0.95 };

// Treatment arms counted from each screenshot (table rows), then the arms the
// user's cross-check kept. Gemini: 5 checkpoint + 3 BRAF/MEK rows = 8.
// Opus: 13 table rows. Bionocular: "1L (12)".
const GEMINI = { vendor: 'Google', name: 'Gemini 3.1 Pro', color: '#4285F4', text: '#1A73E8', arms: 8, kept: 2, wipe: 1.3, counted: 1.7 };
const OPUS = { vendor: 'Anthropic', name: 'Claude Opus 5.5', color: '#D97757', text: '#C96442', arms: 13, kept: 8, wipe: 1.38, counted: 1.78 };
const BIO = { arms: 12, kept: 12 };

const T_RIVALS = 1.0; // both sheets rise in
const T_RIVAL_SCROLL = [1.95, 3.55]; // Gemini scrolls to the end, Opus to its table
const T_GEM_BACK = 3.6; // Gemini comes back up to its two TEAE columns
const T_BAND = 3.95; // the TEAE columns are marked
const T_X = 4.3; // and crossed out
const T_CAPTION = 4.65;
const T_SWAP = 4.9; // Opus's table wipes to its cross-checked copy
const LIFTS = [[5.45, 6.2], [6.35, 7.1], [7.45, 8.2]]; // [out, back] per red row
const T_CHECK_SCROLL = 7.12; // the copy scrolls down to its last red row
const T_BIO = 8.45; // the rivals leave, Bionocular rises
const T_BIO_WIPE = 8.75;
const T_BIO_COUNT = 9.15;
const T_BIO_SCROLL = [9.7, 11.3]; // after a beat on the opening text
const T_BIO_BACK = 11.35; // back up to the class note and the filter row
const T_NOTE = [11.75, 12.55]; // the note's first sentence lifts out, settles back
const T_POP = [12.7, 13.6]; // "Reviewed by an expert" lifts out, settles back
const T_CH = 13.65; // down to the Charts toggle under the table
const T_ZOOM_IN = 13.85; // the camera leans into the toggle
const T_HOVER = 14.05; // the cursor rests on Charts: its border darkens
const T_OPEN = 14.25; // click: the panel unfolds
const T_TAB = 14.5; // the cursor rests on Bubble
const T_BUBBLE = 14.65; // click Bubble
const T_ZOOM_OUT = 14.72; // the camera pulls out until the whole panel fits
const T_AXES = 14.75;
const T_DOTS = 15.05; // the bubbles pop in, lowest median PFS first
const T_LINK = 15.75; // the cursor ends on "Open in Efficacy vs Safety Index Hub"
const T_STATS = 16.45; // the scene greys out behind the tallies
const T_BARS = 16.65;
const T_DROP = 17.95; // the bars drop to the cross-checked counts
const T_SEAL = 18.65; // Bionocular's row is marked: cross-checked and expert reviewed
const T_END = 20.55;

// Each answer rides one conveyor: up from below, out the top.
const conveyor = (T, tIn, tOut) => track(T, [[0, H], [tIn, 0], [tOut, -H - 200]], 'ui');

// ---------------------------------------------------------------- sound
cue(0.08, 'tick', 0.35);
Q.marks.forEach((t) => cue(t, 'tick', 0.45));
cue(Q.shrink, 'whoosh', 0.35);
cue(T_RIVALS + 0.02, 'whoosh', 0.45);
[GEMINI, OPUS].forEach((r) => cue(r.counted, 'tick', 0.5));
cue(T_RIVAL_SCROLL[0], 'whoosh', 0.25);
cue(T_GEM_BACK, 'whoosh', 0.2);
cue(T_BAND, 'pop', 0.5);
cue(T_X, 'thump', 0.7);
cue(T_X + 0.15, 'thump', 0.5);
cue(T_CAPTION, 'tick', 0.5);
cue(T_SWAP, 'whoosh', 0.35);
cue(T_CHECK_SCROLL, 'whoosh', 0.2);
LIFTS.forEach(([t0, t1]) => { cue(t0, 'pop', 0.7); cue(t1, 'tick', 0.35); });
cue(T_BIO + 0.02, 'whoosh', 0.45);
cue(T_BIO + 0.05, 'thump', 0.7);
cue(T_BIO_COUNT, 'tick', 0.5);
cue(T_BIO_SCROLL[0], 'whoosh', 0.25);
cue(T_BIO_BACK, 'whoosh', 0.2);
[T_NOTE, T_POP].forEach(([t0, t1]) => { cue(t0, 'pop', 0.7); cue(t1, 'tick', 0.35); });
cue(T_CH, 'whoosh', 0.25);
cue(T_ZOOM_IN, 'whoosh', 0.3);
cue(T_HOVER, 'tick', 0.4);
cue(T_OPEN, 'click', 0.9);
cue(T_TAB, 'tick', 0.35);
cue(T_BUBBLE, 'click', 0.9);
cue(T_ZOOM_OUT, 'whoosh', 0.25);
[0, 2, 4].forEach((i) => cue(T_DOTS + i * 0.09, 'pop', 0.4));
cue(T_LINK, 'tick', 0.5);
cue(T_STATS, 'whoosh', 0.4);
[0, 1, 2].forEach((i) => cue(T_BARS + i * 0.12, 'tick', 0.5));
cue(T_DROP, 'whoosh', 0.4);
[0, 1].forEach((i) => cue(T_DROP + 0.1 + i * 0.12, 'tick', 0.5));
cue(T_DROP + 0.5, 'chime', 0.7);
cue(T_SEAL, 'pop', 0.6);

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

// The model's colour along the top edge of its sheet, clipped to the corners.
function topStroke(g, x, y, w, h, color, p) {
  g.save();
  rrect(g, x, y, w, h, 18);
  g.clip();
  g.fillStyle = color;
  g.fillRect(x, y, w * clamp(p), 4);
  g.restore();
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
  return x + vw + g.measureText(r.name).width;
}

// "12 treatment arms" on the line under a sheet's name.
function armsTally(g, n, x, y, t0, T) {
  if (T < t0) return;
  const pIn = sp(T - t0, 'snappy');
  const s = count(n, t0, T);
  g.font = font(500, 26, 'mono');
  risingText(g, s, x, y, pIn, 0, 26, C.ink);
  const tx = x + g.measureText(s).width + 10;
  g.font = font(500, 20);
  risingText(g, 'treatment arms', tx, y - 2, pIn, 0, 20, C.ink);
}

// ---------------------------------------------------------------- scene 1: the question
const QUESTION = [
  'Provide phase 3 active clinical treatments showing median PFS',
  'vs grade3+ Treatment emergent adverse events vs treatment',
  'discontinuation due to AEs in metastatic /cutaneous melanoma.',
];
const MARKS = [[0, 'phase 3 active'], [0, 'median PFS'], [1, 'grade3+ Treatment emergent'], [2, 'discontinuation due to AEs']];
export const CHIP_TEXT = 'Provide phase 3 active clinical treatments showing median PFS vs grade3+…';
const BAR = { x: 160, y: 372, w: 1600, h: 268, r: 30 }; // Q2's bar

function question(g, T) {
  const enter = sp(T, 'ui');
  if (enter <= 0) return;
  const p = sp(T - Q.shrink, 'ui');
  g.font = font(400, 18);
  const chip = { x: 120, y: 48, w: g.measureText(CHIP_TEXT).width + 48, h: 52, r: 26 };
  const r = {
    x: lerp(BAR.x, chip.x, p), y: lerp(BAR.y + (1 - enter) * 60, chip.y, p),
    w: lerp(BAR.w, chip.w, p), h: lerp(BAR.h, chip.h, p), r: lerp(BAR.r, chip.r, p),
  };
  g.save();
  g.globalAlpha = clamp(T / 0.12);
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
  const out = clamp((T - Q.shrink) / 0.1);
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
      const w = (g.measureText(word).width + 12) * clamp(m);
      g.fillStyle = C.tint;
      rrect(g, x, ty(line) - 39, w, 53, 9);
      g.fill();
    });
    QUESTION.forEach((text, i) => risingText(g, text, tx, ty(i), sp(T - Q.lines[i], 'snappy'), 0, 44, C.ink));
    g.restore();
  }
  g.font = font(400, 18);
  risingText(g, CHIP_TEXT, chip.x + 24, chip.y + 32, sp(T - Q.shrink - 0.12, 'snappy'), 0, 18, C.ink);
}

// ---------------------------------------------------------------- scene 2: Gemini and Opus side by side
// Two equal sheets, as in Q2. Each answer is its parts stacked as one page.
// Gemini's parts each fill the sheet width; Opus's share one scale so the type
// stays one size (its part 2 repeats part 1's last paragraph, so it starts at
// its table, y 128). Gemini's grade 3+ TEAE column of each table (screenshot
// px) is marked and crossed out once it scrolls back to show both, while Opus
// holds on its table.
const RIVAL = { y: 230, w: 776, h: 730, x: [160, 984] };
const page = (parts, fit) => {
  let y = 0;
  return parts.map(([img, cut, band]) => {
    const s = RIVAL.w / (fit ? img.naturalWidth : parts[0][0].naturalWidth);
    const part = { img, cut, s, y, band };
    y += (img.naturalHeight - cut) * s;
    return part;
  });
};
// Built per frame: image sizes are only known once they have loaded.
const gemPage = () => page([[IMG.gem1, 0, [1005, 470, 315, 695]], [IMG.gem2, 0, [1035, 320, 315, 495]]], true);
const opusPage = () => page([[IMG.opus1, 0], [IMG.opus2, 128], [IMG.opus3, 0]], false);
const pageH = (parts) => parts.reduce((a, { img, cut, s }) => a + (img.naturalHeight - cut) * s, 0);
// Gemini's view at the X: 6 px above the first band, which shows both bands.
const gemHold = ([first]) => first.band[1] * first.s - 6;
const rivalsY = (T) => track(T, [[0, H], [T_RIVALS, 0], [T_BIO, -H - 200]], 'ui');

function rival(g, T, r, i, parts, bg) {
  const x = RIVAL.x[i];
  const { w, h } = RIVAL;
  const at = T_RIVALS + i * 0.08;
  const top = RIVAL.y + rivalsY(T) + (1 - sp(T - at, 'ui')) * 40;
  if (top > H + 40 || top < -h - 300) return;
  modelName(g, r, x, top - 64, sp(T - at - 0.1, 'ui'), 30);
  armsTally(g, r.arms, x, top - 20, r.counted, T);
  sheet(g, x, top, w, h);
  topStroke(g, x, top, w, h, r.color, easeOutCubic((T - at - 0.1) / 0.4));
  thinking(g, x + 44, top + 50, T, window01(T, at + 0.05, r.wipe + 0.12, 0.08, 0.1));
  // Opus stops on its table (part 2's top), where its 13 arms are counted;
  // Gemini scrolls to the end.
  const end = r === OPUS ? parts[1].y : pageH(parts) - h + 4;
  let scroll = end * easeInOutCubic((T - T_RIVAL_SCROLL[0]) / (T_RIVAL_SCROLL[1] - T_RIVAL_SCROLL[0]));
  if (r === GEMINI) scroll += (gemHold(parts) - end) * sp(T - T_GEM_BACK, 'ui');
  const y0 = top + 4 - scroll;
  streamed(g, T, r.wipe, x, top + 4, w, h - 4, () => {
    g.fillStyle = bg; // the screenshots' own page colour, so their edges vanish
    g.fillRect(x, top, w, h);
    parts.forEach(({ img, cut, s, y }) => {
      const ph = img.naturalHeight - cut;
      g.drawImage(img, 0, cut, img.naturalWidth, ph, x, y0 + y, img.naturalWidth * s, ph * s);
    });
  });
  if (r === GEMINI) crossOut(g, T, x, y0, parts);
  if (r === OPUS) crossChecked(g, T, x, top);
}

// A red band down each TEAE column, then an X drawn across it.
function crossOut(g, T, x, y0, parts) {
  parts.forEach(({ s, y, band }, i) => {
    const [bx, by, bw, bh] = band;
    const r = [x + bx * s, y0 + y + by * s, bw * s, bh * s];
    const p = sp(T - T_BAND - i * 0.06, 'snappy');
    if (p <= 0) return;
    g.save();
    g.beginPath();
    g.rect(r[0] - 10, r[1] - 10, r[2] + 20, (r[3] + 20) * clamp(p));
    g.clip();
    g.fillStyle = 'rgba(239, 68, 68, 0.10)';
    rrect(g, ...r, 10);
    g.fill();
    g.strokeStyle = C.red;
    g.lineWidth = 3;
    rrect(g, ...r, 10);
    g.stroke();
    g.restore();
    const inset = 14;
    const strokes = [
      [[r[0] + inset, r[1] + inset], [r[0] + r[2] - inset, r[1] + r[3] - inset]],
      [[r[0] + r[2] - inset, r[1] + inset], [r[0] + inset, r[1] + r[3] - inset]],
    ];
    strokes.forEach(([a, b], k) => {
      const q = easeOutCubic((T - T_X - k * 0.15 - i * 0.05) / 0.22);
      if (q <= 0) return;
      g.save();
      g.strokeStyle = C.red;
      g.lineWidth = 8;
      g.lineCap = 'round';
      g.beginPath();
      g.moveTo(...a);
      g.lineTo(lerp(a[0], b[0], q), lerp(a[1], b[1], q));
      g.stroke();
      g.restore();
    });
  });
}

// The user's cross-check of Opus's table (red = factually wrong value, amber =
// inconsistent) wipes over the table in the Opus sheet at the sheet's width,
// and the subtitle grows to say so. It scrolls to its end before the last lift.
const RED_ROWS = [[25, 513, 920, 124], [25, 761, 920, 102], [25, 1226, 920, 63]]; // dab+tram, enco+bini, missing trials
const LIFT_F = 1.4;
const checkView = (T, top) => {
  const s = RIVAL.w / IMG.checked.naturalWidth;
  const end = IMG.checked.naturalHeight * s - RIVAL.h + 8;
  return { s, y0: top + 4 - end * sp(T - T_CHECK_SCROLL, 'ui') };
};

function crossChecked(g, T, x, top) {
  const u = easeInOutCubic((T - T_SWAP) / 0.4);
  if (u <= 0) return;
  const { w, h } = RIVAL;
  const { s, y0 } = checkView(T, top);
  g.save();
  rrect(g, x, top + 4, w, h - 4, 18);
  g.clip();
  g.beginPath();
  g.rect(x, top + 4, w, (h - 4) * u);
  g.clip();
  g.fillStyle = '#FCFCFB';
  g.fillRect(x, top, w, h);
  g.drawImage(IMG.checked, x, y0, w, IMG.checked.naturalHeight * s);
  g.restore();
  // "13 treatment arms" gains its qualifier.
  g.font = font(500, 26, 'mono');
  let tx = x + g.measureText(`${OPUS.arms}`).width + 10;
  g.font = font(500, 20);
  tx += g.measureText('treatment arms').width + 12;
  risingText(g, '· cross-checked against the sources', tx, top - 22, sp(T - T_SWAP - 0.1, 'snappy'), 0, 20, C.muted);
}

// Each red row lifts from the Opus sheet to the centre, over both sheets.
function redLifts(g, T) {
  const top = RIVAL.y + rivalsY(T);
  const x = RIVAL.x[1];
  const { s, y0 } = checkView(T, top);
  LIFTS.forEach((times, i) => {
    const [sx, sy, sw, sh] = RED_ROWS[i];
    liftOut(g, IMG.checked, RED_ROWS[i],
      { f: s, cx: x + (sx + sw / 2) * s, cy: y0 + (sy + sh / 2) * s },
      { f: LIFT_F, cx: W / 2, cy: top + RIVAL.h / 2 },
      lift(T, times), C.red, [RIVAL.x[0], top, RIVAL.x[1] + RIVAL.w - RIVAL.x[0], RIVAL.h]);
  });
}

function rivals(g, T) {
  rival(g, T, GEMINI, 0, gemPage(), '#FAF9F9');
  rival(g, T, OPUS, 1, opusPage(), '#FCFCFB');
  // The caption sits under both sheets and leaves with them.
  const top = RIVAL.y + rivalsY(T);
  g.font = font(600, 40, 'display');
  risingText(g, 'These numbers are non-existent and this is GenAI', RIVAL.x[0], top + RIVAL.h + 66, sp(T - T_CAPTION, 'snappy'), 0, 40, C.redText);
  redLifts(g, T);
}

// ---------------------------------------------------------------- scene 4: the Bionocular answer
// The 2x capture at one scale, across the full grid; a beat on the opening
// text, it scrolls the whole answer, comes back to the class note and the
// filter row, the note's first sentence lifts out, then "Reviewed by an expert
// (MD or PhD)" does (the 2x hover capture), as in Q2. Then, as in Q2, down to
// the Charts toggle: hover, click, the panel unfolds with no chart drawn,
// Bubble is clicked and its chart builds, the view pulls back until the whole
// panel fits, and the cursor ends on the hub link.
const BS = { w: 1600, y: 210, h: 800 };
BS.x = (W - BS.w) / 2;
BS.s = BS.w / 2920;
const NOTE = [52, 807, 972, 58]; // "No treatment reports Grade 3+ TEAE; showing Grade 3+ TRAE (6 treatments)"
const CHIP = [1321, 929, 511, 64]; // the filter in the capture, measured from the DOM
// The charts captures, in their own px; their row 0 is the toggle's row in the
// answer capture (`at`). Measured from the DOM and the pixels.
const CHARTS = {
  at: 2590,
  head: 72, // the open toggle and the gap under it
  box: [52, 72, 2868, 1610],
  body: [54, 148, 2862, 1532], // inside the border, under the tab row
  toggle: [52, 0, 170, 56],
  tab: [337, 83, 131, 66], // "Bubble"
  underline: [336, 144, 132, 4], // the tab row's rule is rows 146-147
  link: [52, 1694, 500, 32],
  linkClosed: 68, // the link's row under the toggle while the panel is closed
  fit: 0.445, // the scale at which the open panel, toggle to link, fits the sheet
  // [circle, label] per treatment, lowest median PFS first
  bubbles: [
    [[824, 834, 88, 88], [764, 791, 209, 50]], // Nivolumab
    [[1270, 766, 124, 124], [1123, 708, 418, 50]], // prolgo monotherapy
    [[1526, 374, 88, 88], [1315, 330, 511, 50]], // Relatlimab + Nivolumab
    [[1626, 684, 88, 88], [1357, 640, 627, 50]], // Pembrolizumab · NCT05155254
    [[2140, 555, 162, 162], [2071, 496, 302, 50]], // nuru + prolgo
    [[2678, 730, 88, 88], [2171, 811, 627, 50]], // IO102-IO103 + Pembrolizumab
  ],
};
// The page row at the sheet's top while the toggle sits low in the sheet, and
// once the open panel fits.
const ROW_TOGGLE = CHARTS.at - (BS.h * 0.62) / BS.s;
const ROW_FIT = CHARTS.at - 6 / CHARTS.fit;
const FIT_X = BS.x + (BS.w - 2920 * CHARTS.fit) / 2;
const fitPoint = (x, y) => [FIT_X + x * CHARTS.fit, BS.y + 12 + (CHARTS.at + y - ROW_FIT) * CHARTS.fit];
const togglePoint = (x, y) => [BS.x + x * BS.s, BS.y + 12 + (CHARTS.at + y - ROW_TOGGLE) * BS.s];
// The camera leans into the toggle and the tabs, then pulls back out. (No
// lean toward the hub link as in Q2: this sheet spans the grid, so any lean
// pushes it off the frame.)
const FOCUS = togglePoint(270, 72);
const camera = (T) => {
  const k = sp(T - T_ZOOM_IN, 'heavy') - sp(T - T_ZOOM_OUT, 'heavy');
  return { z: 1 + 1.1 * k, cx: W / 2 + (FOCUS[0] - W / 2) * k, cy: H / 2 + (FOCUS[1] - H / 2) * k };
};
const project = (T, [x, y]) => {
  const c = camera(T);
  return [W / 2 + (x - c.cx) * c.z, H / 2 + (y - c.cy) * c.z];
};

function bio(g, T) {
  const top = BS.y + conveyor(T, T_BIO, 99) + (1 - sp(T - T_BIO, 'ui')) * 40;
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
  risingText(g, 'Bionocular agent', BS.x + 62, top - 42, sp(T - T_BIO - 0.1, 'ui'), 0, 30, C.ink);
  armsTally(g, BIO.arms, BS.x + 62 + 270, top - 42, T_BIO_COUNT, T);
  sheet(g, BS.x, top, BS.w, BS.h);
  thinking(g, BS.x + 44, top + 50, T, window01(T, T_BIO + 0.05, T_BIO_WIPE + 0.12, 0.08, 0.1));
  const end = IMG.bio.naturalHeight * BS.s - BS.h + 24;
  const noteAt = NOTE[1] * BS.s - 200;
  const scroll = end * easeInOutCubic((T - T_BIO_SCROLL[0]) / (T_BIO_SCROLL[1] - T_BIO_SCROLL[0]))
    + (noteAt - end) * sp(T - T_BIO_BACK, 'ui')
    + (ROW_TOGGLE * BS.s - noteAt) * sp(T - T_CH, 'ui');
  // Page rows (answer capture px) map to the sheet at scale `s`, centred.
  const f = sp(T - T_ZOOM_OUT, 'ui');
  const s = lerp(BS.s, CHARTS.fit, f);
  const row = lerp(scroll / BS.s, ROW_FIT, f);
  const x0 = BS.x + (BS.w - 2920 * s) / 2;
  const y0 = top + 12 - row * s;
  const blit = (img, [sx, sy, sw, sh], px, py) => g.drawImage(img, sx, sy, sw, sh, x0 + px * s, y0 + py * s, sw * s, sh * s);
  const u = sp(T - T_OPEN - 0.03, 'ui');
  streamed(g, T, T_BIO_WIPE, BS.x, top, BS.w, BS.h, () => {
    g.fillStyle = C.bg;
    g.fillRect(BS.x, top, BS.w, BS.h);
    if (T < T_OPEN) {
      g.drawImage(IMG.bio, x0, y0, 2920 * s, IMG.bio.naturalHeight * s);
      return;
    }
    const at = CHARTS.at;
    blit(IMG.bio, [0, 0, 2920, at], 0, 0);
    blit(IMG.charts, [0, 0, 2920, CHARTS.head], 0, at);
    g.save();
    g.beginPath();
    g.rect(BS.x, y0 + (at + CHARTS.head) * s, BS.w, CHARTS.box[3] * u * s);
    g.clip();
    chartsPanel(g, T, { x0, y0, s });
    g.restore();
    blit(IMG.charts, CHARTS.link, CHARTS.link[0], at + lerp(CHARTS.linkClosed, CHARTS.link[1], u));
  });
  // The toggle's hover border (border-primary, as TurnCharts styles it).
  const hover = window01(T, T_HOVER - 0.04, T_TAB - 0.25, 0.08, 0.12);
  if (hover > 0) {
    const [tx, ty, tw, th] = CHARTS.toggle;
    g.save();
    g.globalAlpha *= hover;
    g.strokeStyle = C.primary;
    g.lineWidth = 2 * s;
    rrect(g, x0 + (tx + 1) * s, y0 + (CHARTS.at + ty + 1) * s, (tw - 2) * s, (th - 2) * s, ((th - 2) * s) / 2);
    g.stroke();
    g.restore();
  }
  // Our seafoam outline marks the link the cursor ends on.
  const mark = window01(T, T_LINK, 99, 0.08, 0.1);
  if (mark > 0) {
    const [lx, ly, lw, lh] = CHARTS.link;
    g.save();
    g.globalAlpha *= mark;
    g.strokeStyle = C.accent;
    g.lineWidth = 2.5;
    rrect(g, x0 + lx * s - 8, y0 + (CHARTS.at + ly) * s - 6, lw * s + 16, lh * s + 12, 8);
    g.stroke();
    g.restore();
  }
  const veil = [BS.x, top, BS.w, BS.h];
  const slot = ([x, y, w, h]) => ({ f: s, cx: x0 + (x + w / 2) * s, cy: y0 + (y + h / 2) * s });
  liftOut(g, IMG.bio, NOTE, slot(NOTE), { f: 1.5, cx: W / 2, cy: top + BS.h / 2 }, lift(T, T_NOTE), C.accent, veil);
  liftOut(g, IMG.reviewed, [0, 0, CHIP[2], CHIP[3]], slot(CHIP), { f: 1.3, cx: W / 2, cy: top + BS.h / 2 },
    lift(T, T_POP), C.accent, veil, 'pill');
}

// The open panel: no tab underlined and no chart until Bubble is clicked; then
// its underline draws from the centre, the axes reveal top-down and the
// bubbles pop in one by one, each label wiping in beside its bubble. `v` maps
// charts-capture px to the screen.
function chartsPanel(g, T, v) {
  const X = (x) => v.x0 + x * v.s;
  const Y = (y) => v.y0 + (CHARTS.at + y) * v.s;
  const put = (img, [sx, sy, sw, sh], x = sx, y = sy, k = 1) => {
    if (sw > 0 && sh > 0) g.drawImage(img, sx, sy, sw, sh, X(x), Y(y), sw * v.s * k, sh * v.s * k);
  };
  const fill = (color, [x, y, w, h]) => {
    g.fillStyle = color;
    g.fillRect(X(x), Y(y), w * v.s, h * v.s);
  };
  put(IMG.charts, CHARTS.box);
  const [ux, uy, uw, uh] = CHARTS.underline;
  fill(C.sheet, CHARTS.underline);
  fill('rgb(200, 224, 216)', [ux, uy + 2, uw, 2]);
  const up = easeOutCubic((T - T_BUBBLE) / 0.18);
  if (up > 0) put(IMG.charts, [ux + (uw * (1 - up)) / 2, uy, uw * up, uh]);
  const [bx, by, bw, bh] = CHARTS.body;
  fill(C.sheet, CHARTS.body);
  const reveal = easeOutCubic((T - T_AXES) / 0.35);
  if (reveal > 0) put(IMG.chartsEmpty, [bx, by, bw, bh * reveal]);
  CHARTS.bubbles.forEach(([[cx, cy, cw, ch], [lx, ly, lw, lh]], i) => {
    const t0 = T_DOTS + i * 0.09;
    const q = sp(T - t0, 'snappy');
    if (q > 0) {
      const r = cw / 2 + 3;
      const [mx, my] = [cx + cw / 2, cy + ch / 2];
      g.save();
      g.beginPath();
      g.arc(X(mx), Y(my), r * q * v.s, 0, Math.PI * 2);
      g.clip();
      put(IMG.charts, [mx - r, my - r, 2 * r, 2 * r], mx - r * q, my - r * q, q);
      g.restore();
    }
    const w = easeOutCubic((T - t0 - 0.05) / 0.25);
    if (w > 0) put(IMG.charts, [lx, ly, lw * w, lh]);
  });
}

// Drawn outside the camera at the projected point, so it keeps its size.
function cursor(g, T) {
  if (T < T_ZOOM_IN) return;
  const toggle = togglePoint(110, 32);
  const tab = togglePoint(392, 122);
  const link = fitPoint(CHARTS.link[0] + 440, CHARTS.link[1] + 22);
  const start = [FOCUS[0] + 340, FOCUS[1] + 300];
  const [x, y] = track2(T, [[0, start], [T_ZOOM_IN, start], [T_HOVER - 0.2, toggle], [T_TAB - 0.18, tab], [T_LINK - 0.2, link]], 'snappy');
  const press = (t0) => (T > t0 - 0.05 && T < t0 + 0.4 ? clamp((T - t0 + 0.05) / 0.45) : 0);
  const [sx, sy] = project(T, [x, y]);
  drawCursor(g, sx, sy, Math.max(press(T_OPEN), press(T_BUBBLE)), window01(T, T_ZOOM_IN + 0.05, T_STATS + 0.1, 0.12, 0.15));
}

// ---------------------------------------------------------------- scene 5: the tallies
// The scene greys out; one card holds the arms each answer gave, on one shared
// scale. Then the bars drop to the arms that held up under the cross-check,
// leaving a faint ghost of what was claimed.
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

const CARD = { w: 1300, h: 640 };
const SEAL_H = 54; // our row (and the card) grow by this to fit the pill
CARD.x = (W - CARD.w) / 2;
CARD.y = (H - CARD.h - SEAL_H) / 2;
const MAX = OPUS.arms;
const dim = (T) => easeInOutCubic((T - T_STATS) / 0.4);
const clear = (T) => easeInOutCubic((T - T_END) / 0.35);

// After the drop, our row grows a line and gets a seafoam ring and a pill:
// the 12 arms held up under the cross-check, and the answer carries the
// "Reviewed by an expert (MD or PhD)" badge shown in scene 4.
const SEAL = 'Cross-checked  ·  Reviewed by an expert (MD or PhD)';
function seal(g, T, x, y, w, h) {
  const p = sp(T - T_SEAL, 'ui');
  if (p <= 0) return;
  const per = 2 * (w + h);
  g.save();
  g.strokeStyle = C.accent;
  g.lineWidth = 3;
  g.setLineDash([per * clamp(p), per]);
  rrect(g, x - 8, y - 8, w + 16, h + 16, 22);
  g.stroke();
  g.restore();

  g.font = font(600, 22);
  const tw = g.measureText(SEAL).width;
  const [ph, ck] = [40, 24];
  const pw = tw + ck + 52;
  const px = x + 24;
  const py = y + 120 + SEAL_H - ph - 18;
  const q = sp(T - T_SEAL - 0.25, 'snappy');
  g.save();
  g.beginPath();
  g.rect(px - 4, py - 4, (pw + 8) * clamp(q), ph + 8);
  g.clip();
  g.fillStyle = C.primary;
  rrect(g, px, py, pw, ph, ph / 2);
  g.fill();
  g.strokeStyle = C.sheet;
  g.lineWidth = 3;
  g.lineCap = 'round';
  g.lineJoin = 'round';
  const [kx, ky] = [px + 20, py + ph / 2];
  g.beginPath();
  g.moveTo(kx, ky);
  g.lineTo(kx + ck * 0.35, ky + ck * 0.3);
  g.lineTo(kx + ck * 0.85, ky - ck * 0.32);
  g.stroke();
  g.restore();
  risingText(g, SEAL, px + 20 + ck + 12, py + ph / 2 + 8, sp(T - T_SEAL - 0.35, 'snappy'), 0, 22, C.sheet);
}

function tallies(g, T) {
  const p = sp(T - T_STATS - 0.05, 'ui');
  if (p <= 0) return;
  const grow = SEAL_H * sp(T - T_SEAL, 'ui');
  const { w } = CARD;
  const h = CARD.h + grow;
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
  const cx = CARD.x + pad;
  const barMax = w - pad * 2 - 160;
  const drop = sp(T - T_DROP, 'ui');
  // The heading swaps as the bars drop.
  g.font = font(600, 34);
  const swap = sp(T - T_DROP, 'snappy');
  risingText(g, 'Treatment arms in the answer', cx, CARD.y + pad + 30, sp(T - T_STATS - 0.15, 'ui'), swap, 34, C.ink);
  risingText(g, 'Treatment arms that hold up after cross-check', cx, CARD.y + pad + 30, sp(T - T_DROP - 0.15, 'snappy'), 0, 34, C.ink);

  const rows = [
    { r: GEMINI, n: GEMINI.arms, kept: GEMINI.kept },
    { r: OPUS, n: OPUS.arms, kept: OPUS.kept },
    { r: { name: 'Bionocular agent' }, n: BIO.arms, kept: BIO.kept, ours: true },
  ];
  rows.forEach(({ r, n, kept, ours }, i) => {
    const y = CARD.y + pad + 120 + i * 140;
    const t0 = T_BARS + i * 0.12;
    const q = sp(T - t0, 'ui');
    if (q <= 0) return;
    if (ours) {
      g.fillStyle = C.tint;
      rrect(g, cx - 24, y - 40, (w - pad * 2 + 48) * clamp(q * 1.4), 120 + grow, 16);
      g.fill();
      const lh = 28;
      g.save();
      g.beginPath();
      g.rect(cx, y - lh - 2, lh * 1.3, (lh + 8) * clamp(q));
      g.clip();
      g.drawImage(IMG.logo, cx, y - lh + 2, lh * LOGO_ASPECT, lh);
      g.restore();
      g.font = font(600, 24);
      risingText(g, r.name, cx + lh * 1.3 + 8, y, q, 0, 24, C.primary);
      seal(g, T, cx - 24, y - 40, w - pad * 2 + 48, 120 + grow);
    } else {
      modelName(g, r, cx, y, q, 24);
    }
    const full = (n / MAX) * barMax * q;
    const dropAt = t0 - T_BARS + T_DROP;
    const d = sp(T - dropAt, 'ui');
    const value = lerp(n, kept, d);
    const bw = Math.max(0, (value / MAX) * barMax * q);
    // Ghost of the claimed length once the bar has dropped.
    if (kept < n && d > 0) {
      g.save();
      g.globalAlpha *= 0.5 * clamp(d * 2);
      g.strokeStyle = r.color;
      g.lineWidth = 2;
      g.setLineDash([8, 6]);
      rrect(g, cx + 1, y + 19, full - 2, 42, 10);
      g.stroke();
      g.restore();
    }
    g.fillStyle = ours ? C.primary : r.color;
    rrect(g, cx, y + 18, bw, 44, 10);
    g.fill();
    const size = ours ? 72 : 56;
    g.font = font(600, size, 'mono');
    const label = T < dropAt ? count(n, t0, T, 0.5) : `${Math.round(value)}`;
    // The number rides the bar end, then sits past the ghost so it never covers it.
    const lx = cx + Math.max(bw, kept < n ? full * drop : 0) + 20;
    risingText(g, label, lx, y + 40 + size * 0.36, sp(T - t0 - 0.04, 'snappy'), 0, size, ours ? C.primary : C.ink);
    if (kept < n && d > 0.02) {
      const lw = g.measureText(label).width;
      g.font = font(500, 26, 'mono');
      risingText(g, `of ${n}`, lx + lw + 14, y + 40 + size * 0.36, sp(T - dropAt - 0.1, 'snappy'), 0, 26, C.muted);
    }
  });
  g.restore();
}

// ---------------------------------------------------------------- frame
// opts.bar false: the question starts as its chip (the master film types it in its own composer).
export function draw(g, T, opts = {}) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  // The camera moves the whole scene, the question chip with it.
  const c = camera(T);
  g.save();
  g.translate(W / 2, H / 2);
  g.scale(c.z, c.z);
  g.translate(-c.cx, -c.cy);
  rivals(g, T);
  bio(g, T);
  question(g, opts.bar === false ? 99 : T);
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
