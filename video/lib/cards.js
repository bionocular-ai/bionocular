// Title-card pieces shared by the master films: the satin ground, type that comes into
// focus, and the landing page's lockup. Pure functions of their inputs.

import { clamp } from './motion.js';
import { font } from './draw.js';

const W = 1920, H = 1080;
const INK = '#102B36';
export const logo = Object.assign(new Image(), { src: 'assets/logo.svg' });
const LOGO_ASPECT = 127.35 / 148.3; // logo.svg viewBox width / height

// Soft diagonal folds of light over a pale seafoam base, drifting slowly.
export function satin(g, T, a) {
  if (a <= 0) return;
  g.save();
  g.globalAlpha = a;
  g.fillStyle = '#EDF5F2';
  g.fillRect(0, 0, W, H);
  g.translate(W / 2, H / 2);
  g.rotate(-0.38);
  for (let i = 0; i < 4; i++) {
    const d = (i - 1.5) * 560 + 160 * Math.sin(0.3 * T + i * 1.7);
    const w = 420 + 120 * Math.sin(i * 2.1 + 0.2 * T);
    const grad = g.createLinearGradient(d - w, 0, d + w, 0);
    grad.addColorStop(0, 'rgba(255, 255, 255, 0)');
    grad.addColorStop(0.35, 'rgba(255, 255, 255, 0.35)');
    grad.addColorStop(0.55, 'rgba(255, 255, 255, 0.8)');
    grad.addColorStop(0.75, 'rgba(255, 255, 255, 0.3)');
    grad.addColorStop(1, 'rgba(122, 193, 162, 0.07)');
    g.fillStyle = grad;
    g.fillRect(d - w, -1600, 2 * w, 3200);
  }
  g.restore();
}

// Something coming into focus: blurred, faint and a little low until p reaches 1;
// leaving (q 0 -> 1) it blurs, fades and drifts up.
export function focus(g, p, q, paint) {
  if (p <= 0 || q >= 1) return;
  const blur = Math.max(0, (1 - p) * 18) + q * 16;
  g.save();
  g.globalAlpha *= clamp(p * 1.5) * (1 - q);
  g.filter = blur > 0.2 ? `blur(${blur.toFixed(2)}px)` : 'none';
  g.translate(0, (1 - p) * 26 - q * 12);
  paint();
  g.restore();
}

// The landing page's lockup: logo + "bio" 800 / "nocular" 500, centred on x.
export function lockup(g, base, S) {
  const lh = S * 1.05;
  g.font = font(800, S, 'brand'); const wb = g.measureText('bio').width;
  g.font = font(500, S, 'brand'); const wn = g.measureText('nocular').width;
  const x0 = (W - (lh * LOGO_ASPECT + S * 0.4 + wb + wn)) / 2;
  g.drawImage(logo, x0, base + S * 0.12 - lh, lh * LOGO_ASPECT, lh);
  let x = x0 + lh * LOGO_ASPECT + S * 0.4;
  g.fillStyle = INK;
  g.textAlign = 'left';
  g.textBaseline = 'alphabetic';
  g.font = font(800, S, 'brand');
  g.fillText('bio', x, base);
  x += wb;
  g.font = font(500, S, 'brand');
  g.fillText('nocular', x, base);
}
