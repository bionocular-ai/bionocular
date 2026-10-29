// Product intro chapter: the boss's five product-intro slides (2026-10-23), copy
// verbatim apart from em dashes, in the user's order: the evidence is exploding,
// teams are drowning in data, who it is built for, AI speed / human rigor, and the
// product diagram. White canvas (the user's call) in the film's tokens.
// Everything is a pure function of global time T (seconds). No timers, no state.
// Storyboard: docs/storyboard-intro.md. Claims: docs/BRIEF.md.

import { clamp, sp, easeOutCubic } from './lib/motion.js';
import { rrect, risingText, font } from './lib/draw.js';

export const FILM = { title: 'intro-chapter', w: 1920, h: 1080, dur: 23.8, bpm: 120 };
const { w: W, h: H } = FILM;

// Bionocular tokens (web/src/app/globals.css), on white.
const C = {
  bg: '#FFFFFF',
  ink: '#102B36',
  muted: '#4A6B77',
  line: '#C8E0D8',
  hair: '#E3EEEA',
  primary: '#1B4F65',
  accent: '#7AC1A2',
  accentText: '#287758',
  tint: '#DAF0E6',
  gold: '#C9A227',
  goldTint: '#F6EED3',
};

export const IMAGES = [];
export const CUES = [];
const cue = (t, type, gain = 1) => CUES.push({ t: +t.toFixed(3), type, gain });

const X = 160; // left margin of the grid
const CW = W - 2 * X; // content width
// Scene spans in seconds.
// Each scene's pieces land in reading order, and it leaves about 1.5 s after the last one.
const S = { stats: [0, 5.0], drown: [5.0, 10.2], built: [10.2, 13.6], rigor: [13.6, 19.2], diagram: [19.2, 23.4] };
// Every scene leaves together, just before its end.
const leave = (T, end) => sp(T - (end - 0.38), 'snappy');

// ---------------------------------------------------------------- type helpers
function type(g, weight, size, family = 'sans', track = 0) {
  g.font = font(weight, size, family);
  g.letterSpacing = `${track * size}px`;
  g.textAlign = 'left';
  g.textBaseline = 'alphabetic';
}

function head(g, text, y, size, color, pIn, pOut) {
  type(g, 600, size, 'display', -0.04);
  risingText(g, text, X, y, pIn, pOut, size, color);
  g.letterSpacing = '0px';
}

function wrap(g, text, maxW) {
  const lines = [];
  let cur = '';
  for (const word of text.split(' ')) {
    const next = cur ? `${cur} ${word}` : word;
    if (cur && g.measureText(next).width > maxW) { lines.push(cur); cur = word; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}

// Words with their own font and colour, wrapped into lines of positioned runs.
function wrapRich(g, segs, maxW) {
  const lines = [];
  let line = [], x = 0;
  for (const s of segs) for (const word of s.t.split(' ').filter(Boolean)) {
    g.font = s.f;
    const ww = g.measureText(word).width, gap = line.length ? g.measureText(' ').width : 0;
    if (line.length && x + gap + ww > maxW) { lines.push(line); line = []; x = 0; }
    const at = line.length ? x + g.measureText(' ').width : 0;
    line.push({ word, f: s.f, c: s.c, x: at });
    x = at + ww;
  }
  if (line.length) lines.push(line);
  return lines;
}

// Paints inside a mask band around baseline y, risen in by pIn and out by pOut.
function masked(g, y, size, pIn, pOut, paint) {
  if (pIn <= 0 || pOut >= 0.99) return;
  const off = (1 - pIn) * size * 1.4 - pOut * size * 1.4;
  g.save();
  g.beginPath();
  g.rect(0, y - size * 1.05, W, size * 1.4);
  g.clip();
  g.translate(0, off);
  paint();
  g.restore();
}

// A white sheet with a hairline border and one soft shadow. It springs up into
// place and lifts away on exit; its contents are painted in its frame.
function card(g, x, y, w, h, pIn, pOut, paint, { fill = '#FFFFFF', stroke = C.hair, lw = 1.5, r = 22, dx = 0, shadow = true } = {}) {
  if (pIn <= 0.001 || pOut >= 0.99) return;
  g.save();
  g.globalAlpha = clamp(pIn * 3) * (1 - clamp(pOut));
  g.translate(dx * (1 - pIn), (1 - pIn) * 80 - pOut * 50);
  if (shadow) {
    g.shadowColor = 'rgba(16,43,54,0.07)';
    g.shadowBlur = 36;
    g.shadowOffsetY = 14;
  }
  rrect(g, x, y, w, h, r);
  g.fillStyle = fill;
  g.fill();
  g.shadowColor = 'transparent';
  if (stroke) { g.lineWidth = lw; g.strokeStyle = stroke; g.stroke(); }
  if (paint) paint(x, y);
  g.restore();
}

function textLines(g, lines, x, y, lh) {
  lines.forEach((l, k) => g.fillText(l, x, y + k * lh));
}

// ---------------------------------------------------------------- 1. the evidence is exploding
const STATS = [
  [9000, (v) => `~${Math.round(v).toLocaleString('en-US')}`, 'Oncology programs in development, about 39% of the pharma pipeline'],
  [2100, (v) => `${Math.round(v).toLocaleString('en-US')}+`, 'New oncology trials started in 2024, up 58% in a decade'],
  [117, (v) => `${Math.round(v)}+`, 'AI-enabled drug assets already in clinical trials'],
  [68, (v) => `${Math.round(v)}%`, 'Of top-10 pharma targets pursued by more than five assets'],
];
const STAT_IN = (i) => 1.2 + i * 0.45;
cue(0.1, 'whoosh', 0.35);
cue(0.22, 'thump', 0.6);
STATS.forEach((_, i) => cue(STAT_IN(i) + 0.05, 'tick', 0.45));
cue(3.15, 'whoosh', 0.3);

function stats(g, T) {
  const t = T - S.stats[0], out = leave(T, S.stats[1]);
  head(g, 'The evidence is exploding.', 300, 112, C.ink, sp(t - 0.1, 'heavy'), out);
  head(g, "Your tools can't keep up.", 424, 112, C.primary, sp(t - 0.55, 'heavy'), out);
  const w = (CW - 3 * 32) / 4, top = 500, h = 330;
  STATS.forEach(([n, fmt, label], i) => {
    const d = STAT_IN(i);
    card(g, X + i * (w + 32), top, w, h, sp(t - d), out, (x, y) => {
      type(g, 600, 84, 'display', -0.04);
      g.fillStyle = C.primary;
      g.fillText(fmt(n * easeOutCubic((t - d - 0.1) / 1.2)), x + 36, y + 118);
      type(g, 400, 26);
      g.fillStyle = C.muted;
      textLines(g, wrap(g, label, w - 72), x + 36, y + 180, 37);
    });
  });
  // A hairline, then the line that hands over to the next slide.
  const rule = clamp(sp(t - 3.0, 'ui'));
  if (rule > 0 && out < 0.99) {
    g.save();
    g.globalAlpha = 1 - out;
    g.fillStyle = C.hair;
    g.fillRect(X, 868, CW * rule, 2);
    g.restore();
  }
  masked(g, 950, 50, sp(t - 3.15, 'ui'), out, () => {
    type(g, 600, 50, 'sans', -0.02);
    const a = 'Stop comparing headlines.';
    g.fillStyle = C.ink;
    g.fillText(a, X, 950);
    g.fillStyle = C.primary;
    g.fillText(' Start comparing evidence.', X + g.measureText(a).width, 950);
    g.letterSpacing = '0px';
  });
}

// ---------------------------------------------------------------- 2. teams are drowning in data
const LEAD2 = [
  { t: 'In 2025, ADC trials grew 30% and bispecific antibody trials grew 66%. Every ASCO and ESMO brings dozens of new readouts. Yet the core question remains unanswered:', f: font(400, 30), c: C.muted },
  { t: 'are these numbers actually comparable?', f: font(600, 30), c: C.ink },
];
const PROBLEMS = [
  ['Weeks to benchmark', 'Analysts manually extract ORR, PFS, OS from abstracts, posters, and publications. One conference can generate 40+ relevant readouts across 8 tumor types.', 'watch'],
  ["Numbers that can't be compared", 'Median PFS of 11.2 vs. 8.4 months means nothing without matching line of therapy, biomarker, prior treatment, assessment method, and data maturity.', 'scales'],
  ['Headlines miss the curve shape', 'A median PFS hides crossing curves, late separations, and tail plateaus - exactly the patterns that matter for IO and ADC combinations.', 'curves'],
];
const PROB_IN = (i) => 1.4 + i * 0.55;
cue(S.drown[0] + 0.05, 'whoosh', 0.35);
PROBLEMS.forEach((_, i) => cue(S.drown[0] + PROB_IN(i) + 0.05, 'tick', 0.45));
cue(S.drown[0] + PROB_IN(2) + 1.35, 'pop', 0.5);

function icon(g, kind, x, y, t) {
  const s = 68;
  rrect(g, x, y, s, s, 16);
  g.fillStyle = kind === 'scales' ? C.goldTint : C.tint;
  g.fill();
  g.save();
  g.lineWidth = 3;
  g.lineCap = 'round';
  g.lineJoin = 'round';
  const cx = x + s / 2, cy = y + s / 2;
  if (kind === 'watch') {
    g.strokeStyle = C.primary;
    g.beginPath(); g.arc(cx, cy + 3, 17, 0, Math.PI * 2); g.stroke();
    g.beginPath(); g.moveTo(cx, cy - 14); g.lineTo(cx, cy - 19); g.moveTo(cx - 5, cy - 20); g.lineTo(cx + 5, cy - 20); g.stroke();
    const a = -Math.PI / 2 + Math.max(0, t) * 2.4;
    g.beginPath(); g.moveTo(cx, cy + 3); g.lineTo(cx + Math.cos(a) * 12, cy + 3 + Math.sin(a) * 12); g.stroke();
  } else if (kind === 'scales') {
    g.strokeStyle = '#9A7A14';
    const tilt = Math.sin(Math.max(0, t) * 2.6) * 0.16 * Math.exp(-Math.max(0, t) * 0.5);
    g.beginPath(); g.moveTo(cx, cy - 16); g.lineTo(cx, cy + 18); g.moveTo(cx - 10, cy + 18); g.lineTo(cx + 10, cy + 18); g.stroke();
    const ex = Math.cos(tilt) * 19, ey = Math.sin(tilt) * 19;
    g.beginPath(); g.moveTo(cx - ex, cy - 12 - ey); g.lineTo(cx + ex, cy - 12 + ey); g.stroke();
    for (const [px, py] of [[cx - ex, cy - 12 - ey], [cx + ex, cy - 12 + ey]]) {
      g.beginPath(); g.moveTo(px, py); g.lineTo(px - 6, py + 12); g.lineTo(px + 6, py + 12); g.closePath(); g.stroke();
    }
  } else {
    // Two survival curves drawn left to right; they cross.
    const p = clamp(t / 1.1);
    g.beginPath(); g.rect(x + 12, y + 10, (s - 24) * p, s - 20); g.clip();
    g.lineWidth = 2.5;
    g.strokeStyle = C.primary;
    g.beginPath(); g.moveTo(x + 14, y + 18); g.lineTo(x + 26, y + 18); g.lineTo(x + 26, y + 30); g.lineTo(x + 40, y + 30); g.lineTo(x + 40, y + 46); g.lineTo(x + 54, y + 46); g.stroke();
    g.strokeStyle = C.accent;
    g.beginPath(); g.moveTo(x + 14, y + 18); g.lineTo(x + 20, y + 18); g.lineTo(x + 20, y + 36); g.lineTo(x + 34, y + 36); g.lineTo(x + 34, y + 40); g.lineTo(x + 54, y + 40); g.stroke();
  }
  g.restore();
}

function drown(g, T) {
  const t = T - S.drown[0], out = leave(T, S.drown[1]);
  head(g, 'Teams are drowning in data', 230, 100, C.ink, sp(t - 0.1, 'heavy'), out);
  head(g, "they can't compare", 334, 100, C.ink, sp(t - 0.24, 'heavy'), out);
  wrapRich(g, LEAD2, 1400).forEach((line, k) => {
    const y = 422 + k * 46;
    masked(g, y, 30, sp(t - 0.55 - k * 0.07, 'ui'), out, () => {
      for (const w of line) { g.font = w.f; g.fillStyle = w.c; g.letterSpacing = '0px'; g.fillText(w.word, X + w.x, y); }
    });
  });
  const w = (CW - 2 * 24) / 3, top = 565, h = 420;
  PROBLEMS.forEach(([title, body, kind], i) => {
    const d = PROB_IN(i);
    card(g, X + i * (w + 24), top, w, h, sp(t - d), out, (x, y) => {
      icon(g, kind, x + 40, y + 40, t - d - 0.3);
      type(g, 600, 28, 'sans', -0.01);
      g.fillStyle = C.ink;
      const tl = wrap(g, title, w - 80);
      textLines(g, tl, x + 40, y + 160, 38);
      type(g, 400, 25);
      g.fillStyle = C.muted;
      textLines(g, wrap(g, body, w - 80), x + 40, y + 160 + (tl.length - 1) * 38 + 48, 37);
    });
  });
}

// ---------------------------------------------------------------- 3. built for
const AUDIENCES = [
  ['Strategic Intelligence', 'Daily power users tracking landscape shifts'],
  ['BD&L', 'Asset diligence and deal evaluation'],
  ['Clinical Development', 'Trial design and control-arm assumptions'],
  ['Consultants', 'Client deliverables and strategic advisory'],
  ['Investment Banks', 'Valuations and fairness opinions'],
  ['Oncologists & Cancer Centers', 'Tumor boards, formulary, and investigator-initiated trials'],
];
const AUD_IN = (i) => 0.6 + i * 0.12;
cue(S.built[0] + 0.05, 'whoosh', 0.35);
AUDIENCES.forEach((_, i) => cue(S.built[0] + AUD_IN(i) + 0.05, 'tick', 0.32));

function built(g, T) {
  const t = T - S.built[0], out = leave(T, S.built[1]);
  head(g, 'Built for the people who shape', 220, 100, C.ink, sp(t - 0.1, 'heavy'), out);
  head(g, 'treatment decisions', 324, 100, C.ink, sp(t - 0.24, 'heavy'), out);
  const w = (CW - 2 * 24) / 3, h = 250;
  AUDIENCES.forEach(([title, body], i) => {
    const x0 = X + (i % 3) * (w + 24), y0 = 400 + Math.floor(i / 3) * (h + 24);
    card(g, x0, y0, w, h, sp(t - AUD_IN(i)), out, (x, y) => {
      type(g, 600, 34, 'sans', -0.02);
      const tl = wrap(g, title, w - 88);
      type(g, 400, 26);
      const bl = wrap(g, body, w - 88);
      const block = tl.length * 44 + 12 + bl.length * 38;
      const y1 = y + (h - block) / 2 + 32;
      type(g, 600, 34, 'sans', -0.02);
      g.fillStyle = C.ink;
      textLines(g, tl, x + 44, y1, 44);
      type(g, 400, 26);
      g.fillStyle = C.muted;
      textLines(g, bl, x + 44, y1 + tl.length * 44 + 12, 38);
    });
  });
}

// ---------------------------------------------------------------- 4. AI speed, human rigor
const PILLARS = [
  ['01', 'Evidence Network: Efficacy, Safety & KM Digitized Twins', "Every arm's efficacy, safety, and digitized PFS/OS curves sit in one connected network across trials. Recompute HRs, RMST, and landmark rates, overlay competitors, and weigh benefit against toxicity side by side."],
  ['02', 'Comparability Engine', 'Every arm tagged with line, biomarker, prior treatment, region, assessment method, and data maturity. The system warns when a comparison is fragile - before you put it in a slide.'],
  ['03', 'Human + Expert Validation', 'AI extracts 30+ parameters per arm. Pharma-trained oncology analysts validate every extraction. Published accuracy benchmarks you can show your biostatisticians.'],
  ['04', 'Data-Cut Lineage', "Track how a trial's results evolve from abstract to presentation to publication to label update. See when a benefit grows or shrinks across data cuts."],
];
// Two pairs share one row: 01-02, then 03-04 take their place.
const PAIR_IN = [0.9, 2.95], PAIR_OUT = 2.7;
cue(S.rigor[0] + 0.05, 'whoosh', 0.35);
cue(S.rigor[0] + 0.18, 'thump', 0.55);
PAIR_IN.forEach((d) => { cue(S.rigor[0] + d + 0.05, 'tick', 0.45); cue(S.rigor[0] + d + 0.2, 'tick', 0.4); });
cue(S.rigor[0] + PAIR_OUT + 0.02, 'whoosh', 0.28);

function rigor(g, T) {
  const t = T - S.rigor[0], out = leave(T, S.rigor[1]);
  head(g, 'AI speed.', 225, 108, C.ink, sp(t - 0.1, 'heavy'), out);
  head(g, 'Human rigor.', 340, 108, C.primary, sp(t - 0.26, 'heavy'), out);
  type(g, 400, 30);
  wrap(g, 'Every datapoint in the platform passes through a three-stage pipeline that no pure-AI tool or manual team can match alone.', 1150)
    .forEach((l, k) => risingText(g, l, X, 424 + k * 46, sp(t - 0.5 - k * 0.07, 'ui'), out, 30, C.muted));
  const w = (CW - 24) / 2, top = 530, h = 430;
  PILLARS.forEach(([num, title, body], i) => {
    const pair = i < 2 ? 0 : 1, d = PAIR_IN[pair] + (i % 2) * 0.15;
    const pOut = pair === 0 ? sp(t - PAIR_OUT, 'snappy') : out;
    card(g, X + (i % 2) * (w + 24), top, w, h, sp(t - d), pOut, (x, y) => {
      type(g, 500, 26, 'mono');
      g.fillStyle = C.accentText;
      g.fillText(num, x + 44, y + 66);
      type(g, 600, 34, 'sans', -0.02);
      g.fillStyle = C.ink;
      const tl = wrap(g, title, w - 88);
      textLines(g, tl, x + 44, y + 124, 44);
      type(g, 400, 26);
      g.fillStyle = C.muted;
      textLines(g, wrap(g, body, w - 88), x + 44, y + 124 + (tl.length - 1) * 44 + 52, 39);
    });
  });
}

// ---------------------------------------------------------------- 5. product diagram
const SOURCES = ['Clinical Trials', 'Conference Abstracts', 'Publications', 'Press Releases', 'Live News', 'Standard of Care'];
const DIMS = ['Indication & Subtype', 'Clinical Setting', 'Disease Stage', 'Line of Therapy', 'Biomarker', 'Modality', 'Target', 'Efficacy Endpoints', 'Safety Endpoints'];
const MODULES = [
  ['LANDSCAPE INTELLIGENCE', 'Clinical Landscape and Trial Data'],
  ['OUTCOME INTELLIGENCE HUB', 'Efficacy, Safety and Efficacy vs Safety'],
  ['SURVIVAL INTELLIGENCE', 'KM-Curve Digitized Twin'],
];
const D = {
  raw: [160, 180, 330, 800], src: (k) => [180, 212 + k * 128, 290, 92],
  core: [700, 590], coreHalf: 140,
  dims: [910, 120, 340, 860], dim: (j) => [930, 140 + j * 92, 300, 70],
  plat: [1290, 120, 470, 600], mod: (k) => [1312, 212 + k * 165, 426, 145],
  agent: [1290, 800, 470, 160],
};
cue(S.diagram[0] + 0.05, 'whoosh', 0.35);
SOURCES.forEach((_, k) => k % 2 === 0 && cue(S.diagram[0] + 0.2 + k * 0.07, 'tick', 0.3));
cue(S.diagram[0] + 1.25, 'whoosh', 0.28);
MODULES.forEach((_, k) => cue(S.diagram[0] + 2.1 + k * 0.12, 'tick', 0.38));
cue(S.diagram[0] + 2.62, 'chime', 0.6);

function centred(g, text, x, y, w) {
  g.textAlign = 'center';
  g.fillText(text, x + w / 2, y);
  g.textAlign = 'left';
}

// A dashed path revealed left to right between x0 and x0 + span.
function reveal(g, x0, span, p, paint) {
  if (p <= 0) return;
  g.save();
  g.beginPath();
  g.rect(x0 - 4, 0, span * clamp(p) + 8, H);
  g.clip();
  paint();
  g.restore();
}

function diagram(g, T) {
  const t = T - S.diagram[0], out = leave(T, S.diagram[1]);
  const fade = 1 - clamp(out);
  // Raw scientific data
  masked(g, 152, 32, sp(t - 0.05, 'ui'), out, () => {
    g.fillStyle = C.gold;
    g.beginPath(); g.arc(X + 9, 141, 9, 0, Math.PI * 2); g.fill();
    type(g, 600, 32, 'display', -0.02);
    g.fillStyle = C.ink;
    g.fillText('Raw Scientific Data', X + 30, 152);
    g.letterSpacing = '0px';
  });
  card(g, ...D.raw, sp(t - 0.05), out, null, { fill: '#FCF8EC', stroke: 'rgba(201,162,39,0.45)', r: 26, shadow: false });
  SOURCES.forEach((s, k) => {
    const [x0, y0, w, h] = D.src(k);
    card(g, x0, y0, w, h, sp(t - 0.15 - k * 0.07), out, (x, y) => {
      type(g, 500, 24);
      g.fillStyle = C.ink;
      centred(g, s, x, y + 55, w);
    }, { stroke: 'rgba(201,162,39,0.6)', r: 16, dx: -50, shadow: false });
  });
  // Gold dashed links from every source into the core.
  const [cx, cy] = D.core;
  g.save();
  g.globalAlpha = fade;
  reveal(g, 470, cx - D.coreHalf - 470, easeOutCubic((t - 0.65) / 0.7), () => {
    g.strokeStyle = C.gold;
    g.lineWidth = 2;
    g.setLineDash([7, 9]);
    g.lineDashOffset = -Math.max(0, t) * 30;
    SOURCES.forEach((_, k) => {
      const [x0, y0, w, h] = D.src(k), sy = y0 + h / 2;
      g.beginPath(); g.moveTo(x0 + w, sy); g.bezierCurveTo(x0 + w + 60, sy, cx - D.coreHalf - 50, cy - 12, cx - D.coreHalf, cy - 12); g.stroke();
    });
  });
  // A teal bracket out of the core: stem, bus, one tick per dimension.
  reveal(g, cx + D.coreHalf, D.dims[0] + 20 - cx - D.coreHalf, easeOutCubic((t - 1.2) / 0.5), () => {
    const bx = D.dims[0] - 30, mid = (j) => D.dim(j)[1] + D.dim(j)[3] / 2;
    g.strokeStyle = C.primary;
    g.lineWidth = 2;
    g.setLineDash([2, 6]);
    g.beginPath(); g.moveTo(cx + D.coreHalf + 4, cy - 12); g.lineTo(bx, cy - 12);
    g.moveTo(bx, mid(0)); g.lineTo(bx, mid(DIMS.length - 1));
    DIMS.forEach((_, j) => { g.moveTo(bx, mid(j)); g.lineTo(D.dim(j)[0], mid(j)); });
    g.stroke();
  });
  g.restore();
  masked(g, cy - 74, 24, sp(t - 0.9, 'ui'), out, () => {
    type(g, 500, 24, 'sans', 0.14);
    g.textAlign = 'center';
    g.fillStyle = C.muted;
    g.fillText('RAW  \u2192  STRUCTURED', cx, cy - 74);
  });
  masked(g, cy, 32, sp(t - 0.85, 'heavy'), out, () => {
    type(g, 600, 32, 'display', 0.12);
    g.textAlign = 'center';
    g.fillStyle = C.ink;
    g.fillText('BIONOCULAR', cx, cy);
  });
  g.letterSpacing = '0px';
  g.textAlign = 'left';
  // Nine clinical dimensions
  card(g, ...D.dims, sp(t - 1.15), out, null, { fill: '#F7FAF9', stroke: C.line, r: 26, shadow: false });
  DIMS.forEach((s, j) => {
    const [x0, y0, w, h] = D.dim(j);
    card(g, x0, y0, w, h, sp(t - 1.25 - j * 0.05), out, (x, y) => {
      type(g, 500, 24);
      g.fillStyle = C.ink;
      centred(g, s, x, y + 44, w);
    }, { stroke: 'rgba(27,79,101,0.3)', r: 14, shadow: false });
  });
  // Dimensions feed the platform modules.
  g.save();
  g.globalAlpha = fade;
  reveal(g, D.dims[0] + D.dims[2], 40, easeOutCubic((t - 1.9) / 0.3), () => {
    g.strokeStyle = C.primary;
    g.lineWidth = 2;
    g.setLineDash([6, 6]);
    MODULES.forEach((_, k) => {
      const [, y0, , h] = D.mod(k);
      g.beginPath(); g.moveTo(D.dims[0] + D.dims[2], y0 + h / 2); g.lineTo(D.plat[0], y0 + h / 2); g.stroke();
    });
    const [, ay, , ah] = D.agent;
    g.beginPath(); g.moveTo(D.dims[0] + D.dims[2], ay + ah / 2); g.lineTo(D.agent[0], ay + ah / 2); g.stroke();
  });
  g.restore();
  // Visual platform
  card(g, ...D.plat, sp(t - 1.95), out, (x, y) => {
    type(g, 600, 32, 'display', -0.02);
    g.fillStyle = C.accentText;
    g.fillText('Visual Platform', x + 25, y + 62);
    const tw = g.measureText('Visual Platform ').width;
    type(g, 400, 24);
    g.fillStyle = C.muted;
    g.fillText('Cancer Specific', x + 25 + tw + 8, y + 62);
  }, { fill: '#F3FAF6', stroke: C.accent, r: 26, shadow: false });
  MODULES.forEach(([title, sub], k) => {
    const [x0, y0, w, h] = D.mod(k);
    card(g, x0, y0, w, h, sp(t - 2.05 - k * 0.12), out, (x, y) => {
      type(g, 400, 24);
      const sl = wrap(g, sub, w - 52);
      const y1 = y + (h - (34 + sl.length * 32)) / 2 + 24;
      type(g, 600, 24, 'sans', 0.03);
      g.fillStyle = C.primary;
      g.fillText(title, x + 26, y1);
      g.letterSpacing = '0px';
      type(g, 400, 24);
      g.fillStyle = C.muted;
      textLines(g, sl, x + 26, y1 + 42, 32);
    }, { stroke: 'rgba(27,79,101,0.25)', r: 18 });
  });
  // "Opens In": the agent opens from the platform.
  const oi = clamp(sp(t - 2.75, 'ui'));
  if (oi > 0 && out < 0.99) {
    g.save();
    g.globalAlpha = fade;
    g.strokeStyle = C.gold;
    g.lineWidth = 2.5;
    g.setLineDash([2, 7]);
    const y0 = D.plat[1] + D.plat[3], y1 = D.agent[1];
    for (const lx of [1515, 1555]) { g.beginPath(); g.moveTo(lx, y0); g.lineTo(lx, y0 + (y1 - y0) * oi); g.stroke(); }
    g.restore();
  }
  type(g, 400, 24);
  risingText(g, 'Opens In', 1582, 768, sp(t - 2.8, 'ui'), out, 24, C.muted);
  // bionocular AI Agent
  card(g, ...D.agent, sp(t - 2.55), out, (x, y) => {
    g.font = font(800, 32, 'brand');
    g.fillStyle = C.ink;
    g.letterSpacing = '0px';
    g.fillText('bio', x + 28, y + 62);
    const bw = g.measureText('bio').width;
    g.font = font(500, 32, 'brand');
    g.fillText('nocular AI Agent', x + 28 + bw, y + 62);
    type(g, 400, 24);
    g.fillStyle = C.muted;
    textLines(g, wrap(g, 'Plain-Language Answers from the Same Data', D.agent[2] - 56), x + 28, y + 104, 34);
  }, { fill: '#FCF8EC', stroke: C.gold, lw: 2.5, r: 20 });
}

// ---------------------------------------------------------------- frame
export function draw(g, T) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.fillStyle = C.bg;
  g.fillRect(0, 0, W, H);
  if (T < S.stats[1]) stats(g, T);
  else if (T < S.drown[1]) drown(g, T);
  else if (T < S.built[1]) built(g, T);
  else if (T < S.rigor[1]) rigor(g, T);
  else if (T < S.diagram[1]) diagram(g, T);
  g.letterSpacing = '0px';
}
