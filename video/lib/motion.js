// Motion helpers. Every function here is a pure function of time, so any frame
// can be rendered on its own (seek(t) never depends on earlier frames).

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, p) => a + (b - a) * p;
export const mix = (a, b, p) => a + (b - a) * clamp(p);

// Closed-form damped spring, 0 -> 1, starting at t = 0.
// k = stiffness, d = damping. Lower damping ratio = more overshoot.
export function spring(t, k = 170, d = 26) {
  if (t <= 0) return 0;
  const w0 = Math.sqrt(k);
  const z = d / (2 * w0);
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + ((z * w0) / wd) * Math.sin(wd * t));
  }
  if (z === 1) return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
  // Overdamped
  const r1 = -w0 * (z - Math.sqrt(z * z - 1));
  const r2 = -w0 * (z + Math.sqrt(z * z - 1));
  const c2 = r1 / (r1 - r2);
  const c1 = 1 - c2;
  return 1 - (c1 * Math.exp(r1 * t) + c2 * Math.exp(r2 * t));
}

// Named spring presets. Use these instead of raw numbers so motion stays consistent.
export const SPRINGS = {
  snappy: [320, 30], // buttons, toggles, leading edges
  ui: [170, 26], // cards, containers, camera
  heavy: [90, 19], // big type, logo lockups
  soft: [60, 16], // slow drifts
};
export const sp = (t, name = 'ui') => spring(t, ...SPRINGS[name]);

// A value that changes target several times. One spring per change, summed,
// so motion stays continuous without simulating earlier frames.
// keys: [[time, value], ...] sorted by time.
export function track(t, keys, preset = 'ui') {
  let v = keys[0][1];
  for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * sp(t - keys[i][0], preset);
  return v;
}

// How far a lift is out: up with a little overshoot at t0, back without at t1.
export const lift = (T, [t0, t1]) => sp(T - t0, 'snappy') - sp(T - t1, 'ui');

// Same as track() for [x, y] points (cursor paths, camera targets).
export function track2(t, keys, preset = 'ui') {
  return [
    track(t, keys.map(([k, p]) => [k, p[0]]), preset),
    track(t, keys.map(([k, p]) => [k, p[1]]), preset),
  ];
}

// Opacity window: in over `fadeIn` after tIn, out over `fadeOut` before tOut.
export function window01(t, tIn, tOut, fadeIn = 0.15, fadeOut = 0.15) {
  return Math.min(clamp((t - tIn) / fadeIn), clamp((tOut - t) / fadeOut));
}

// Eases for things that must land exactly (counters, progress rings).
export const easeOutCubic = (p) => 1 - Math.pow(1 - clamp(p), 3);
export const easeInOutCubic = (p) => {
  p = clamp(p);
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
};

// Seeded random (mulberry32). Never use Math.random in a film.
export function rng(seed) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Beat helpers: a film with a tempo places events on beats, not on arbitrary seconds.
export const beats = (bpm) => {
  const b = 60 / bpm;
  return { beat: b, bar: b * 4, at: (n) => n * b };
};
