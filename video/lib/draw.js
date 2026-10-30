// Small canvas drawing helpers shared by every film.
import { clamp, lerp } from './motion.js';

// Registered in index.html from assets/fonts (the product's own faces).
// 'brand' is Plus Jakarta Sans, for the bionocular wordmark only.
const FAMILY = { display: 'FilmDisplay', sans: 'FilmSans', mono: 'FilmMono', brand: 'FilmBrand' };
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

// The macOS pointer: black arrow, white edge, soft shadow, no click ripple.
function macCursor(g, x, y, press, alpha) {
  const s = 2.3 * (1 - 0.12 * clamp(press));
  g.save();
  g.globalAlpha = alpha;
  g.translate(x, y);
  g.scale(s, s);
  g.beginPath();
  g.moveTo(0, 0);
  g.lineTo(0, 16.6);
  g.lineTo(3.9, 12.9);
  g.lineTo(6.5, 18.9);
  g.lineTo(9.1, 17.8);
  g.lineTo(6.6, 12);
  g.lineTo(11.8, 12);
  g.closePath();
  g.lineJoin = 'round';
  g.shadowColor = 'rgba(0, 0, 0, 0.32)';
  g.shadowBlur = 8;
  g.shadowOffsetY = 3;
  g.strokeStyle = '#FFFFFF';
  g.lineWidth = 2.2;
  g.stroke();
  g.shadowColor = 'transparent';
  g.fillStyle = '#000000';
  g.fill();
  g.restore();
}

// Arrow pointer. press: 0..1 (1 = fully pressed). A film that sets `g.mac = true`
// for the frame gets the macOS pointer instead, in every chapter it draws.
export function drawCursor(g, x, y, press = 0, alpha = 1) {
  if (alpha <= 0) return;
  if (g.mac) return macCursor(g, x, y, press, alpha);
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

// A region of a capture lifted out of its sheet over a veil, larger, with a ring.
// src is in image px; from/to are { f: screen px per image px, cx, cy }; veil is
// the sheet's screen rect; p comes from lift().
export function liftOut(g, img, src, from, to, p, ring, veil, radius = 10) {
  if (p <= 0.001) return;
  const [vx, vy, vw, vh] = veil;
  g.save();
  rrect(g, vx, vy, vw, vh, 18);
  g.clip();
  g.fillStyle = `rgba(247, 250, 249, ${0.85 * clamp(p)})`;
  g.fillRect(vx, vy, vw, vh);
  g.restore();
  const [sx, sy, sw, sh] = src;
  const f = lerp(from.f, to.f, p);
  const [w, h] = [sw * f, sh * f];
  const x = lerp(from.cx, to.cx, p) - w / 2;
  const y = lerp(from.cy, to.cy, p) - h / 2;
  g.save();
  g.shadowColor = `rgba(16, 43, 54, ${0.2 * clamp(p)})`;
  g.shadowBlur = 60 * clamp(p);
  g.shadowOffsetY = 22 * clamp(p);
  g.fillStyle = '#FFFFFF';
  const r = radius === 'pill' ? h / 2 : radius;
  rrect(g, x, y, w, h, r);
  g.fill();
  g.restore();
  g.save();
  rrect(g, x, y, w, h, r);
  g.clip();
  g.drawImage(img, sx, sy, sw, sh, x, y, w, h);
  g.restore();
  g.save();
  g.globalAlpha = clamp(p);
  g.strokeStyle = ring;
  g.lineWidth = 3;
  rrect(g, x - 10, y - 10, w + 20, h + 20, r + 6);
  g.stroke();
  g.restore();
}
