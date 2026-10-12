// Small canvas drawing helpers shared by every film.
import { clamp } from './motion.js';

// Registered in index.html from assets/fonts (the product's own faces).
const FAMILY = { display: 'FilmDisplay', sans: 'FilmSans', mono: 'FilmMono' };
export const font = (weight, size, family = 'sans') => `${weight} ${size}px ${FAMILY[family]}`;

export function rrect(g, x, y, w, h, r) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  g.beginPath();
  g.roundRect(x, y, w, h, r);
}

// Text that rises into view from behind an invisible mask, and leaves upward.
// pIn / pOut are 0..1 progress values (usually springs). size = font size in px.
export function risingText(g, text, x, y, pIn, pOut, size, color, align = 'left') {
  // 0.99 cut-off: springs overshoot past 1 and settle back, which would
  // otherwise let descenders peek back into the mask for a few frames.
  if (pIn <= 0 || pOut >= 0.99) return;
  const off = (1 - pIn) * size * 1.4 - pOut * size * 1.4;
  g.save();
  g.beginPath();
  g.rect(x - size * 2 - (align === 'right' ? 4000 : 0), y - size * 1.0, 8000, size * 1.35);
  g.clip();
  g.fillStyle = color;
  g.textAlign = align;
  g.textBaseline = 'alphabetic';
  g.fillText(text, x, y + off);
  g.restore();
}

// macOS-style arrow pointer. press: 0..1 (1 = fully pressed).
export function drawCursor(g, x, y, press = 0, alpha = 1) {
  if (alpha <= 0) return;
  const s = 1.6 * (1 - 0.14 * clamp(press));
  g.save();
  g.globalAlpha = alpha;
  g.translate(x, y);
  g.scale(s, s);
  g.beginPath();
  g.moveTo(0, 0);
  g.lineTo(0, 22);
  g.lineTo(5.5, 17);
  g.lineTo(9.5, 26);
  g.lineTo(13, 24.5);
  g.lineTo(9, 16);
  g.lineTo(16, 16);
  g.closePath();
  g.fillStyle = '#FFFFFF';
  g.strokeStyle = '#0B0E12';
  g.lineWidth = 1.6;
  g.lineJoin = 'round';
  g.fill();
  g.stroke();
  g.restore();
  // Click ripple
  if (press > 0.02) {
    g.save();
    g.globalAlpha = alpha * (1 - press) * 0.6;
    g.strokeStyle = '#FFFFFF';
    g.lineWidth = 3;
    g.beginPath();
    g.arc(x, y, 12 + 40 * press, 0, Math.PI * 2);
    g.stroke();
    g.restore();
  }
}

// Interpolate two #RRGGBB colors.
export function mixColor(a, b, p) {
  p = clamp(p);
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
  const ch = (v, s) => (v >> s) & 255;
  const c = (s) => Math.round(ch(pa, s) + (ch(pb, s) - ch(pa, s)) * p);
  return `rgb(${c(16)},${c(8)},${c(0)})`;
}
