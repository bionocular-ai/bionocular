// Synthesises the soundtrack in code from out/cues.json (written by render.mjs).
// Deterministic: same cues in, same audio out.
//
//   node sound/score.mjs                         music bed + sound effects -> out/audio.wav
//   node sound/score.mjs --no-music              sound effects only
//   node sound/score.mjs --no-sfx                music bed only
//   node sound/score.mjs --track audio/song.wav  skip the bed, mix SFX over your own track (via ffmpeg)
//
// Don't like the sound? Use out/silent.mp4. The picture never depends on the audio.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const argv = process.argv.slice(2);
const has = (k) => argv.includes('--' + k);
const arg = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };

const { dur, bpm, cues } = JSON.parse(readFileSync(arg('cues', 'out/cues.json'), 'utf8'));
const OUT = arg('out', 'out/audio.wav');
const TRACK = arg('track', null);
const MUSIC = !has('no-music') && !TRACK;
const SFX = !has('no-sfx');
const MUSIC_GAIN = Number(arg('music-gain', 1));
const SFX_GAIN = Number(arg('sfx-gain', 1));

const SR = 48000;
const N = Math.ceil(dur * SR);
const L = new Float32Array(N), R = new Float32Array(N);
const TAU = Math.PI * 2;

// Deterministic noise
let seed = 1234567;
const noise = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 2147483648 - 1);

const add = (i, l, r = l) => { if (i >= 0 && i < N) { L[i] += l; R[i] += r; } };
const note = (midi) => 440 * Math.pow(2, (midi - 69) / 12);

// ------------------------------------------------------------------ music bed
if (MUSIC) {
  const beat = 60 / bpm, bar = beat * 4;
  // Am9 -> Fmaj7 -> Cmaj7 -> G6 (calm, slightly hopeful). MIDI note numbers.
  const CHORDS = [
    [45, 57, 60, 64, 67, 71],
    [41, 57, 60, 64, 65, 69],
    [48, 55, 59, 64, 67, 72],
    [43, 55, 59, 62, 64, 71],
  ];
  const fadeIn = 0.3, fadeOut = Math.min(1.2, dur * 0.15);
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    const master = MUSIC_GAIN * Math.min(1, t / fadeIn) * Math.min(1, (dur - t) / fadeOut);
    const b = t / beat, tb = (b - Math.floor(b)) * beat; // time since last beat
    const barIdx = Math.floor(t / bar), tbar = t - barIdx * bar;
    const chord = CHORDS[barIdx % CHORDS.length];
    const duck = 1 - 0.45 * Math.exp(-tb * 7); // pad breathes with the kick

    // Pad: soft sines, slight stereo detune, gentle swell per bar
    const swell = Math.min(1, tbar / 0.5) * (0.85 + 0.15 * Math.cos((TAU * tbar) / bar));
    let pl = 0, pr = 0;
    for (let v = 1; v < chord.length; v++) {
      const f = note(chord[v]);
      pl += Math.sin(TAU * f * 0.9985 * t) + 0.25 * Math.sin(TAU * f * 2 * t);
      pr += Math.sin(TAU * f * 1.0015 * t) + 0.25 * Math.sin(TAU * f * 2 * t);
    }
    const padG = 0.018 * swell * duck;

    // Bass: root note, short pluck on every beat
    const bassF = note(chord[0]);
    const bass = Math.sin(TAU * bassF * t) * Math.exp(-tb * 5) * 0.11;

    // Kick: pitch drop 120 -> 48 Hz (closed-form phase)
    const kick = Math.sin(TAU * (48 * tb + (72 / 28) * (1 - Math.exp(-28 * tb)))) * Math.exp(-tb * 9) * 0.32;

    // Hi-hat on the off-beat
    const off = ((b + 0.5) - Math.floor(b + 0.5)) * beat;
    const hat = (noise() - noise()) * Math.exp(-off * 70) * 0.035;

    const m = master;
    add(i, m * (pl * padG + bass + kick + hat * 0.8), m * (pr * padG + bass + kick + hat * 1.2));
  }
}

// ------------------------------------------------------------------ sound effects
// Each voice: [length in seconds, (t, len) => [left, right]]
const VOICES = {
  click: [0.06, (t) => { const v = (Math.sin(TAU * 2100 * t) * 0.6 + noise() * 0.4) * Math.exp(-t * 110) * 0.5; return [v, v]; }],
  tick: [0.05, (t) => { const v = Math.sin(TAU * 3300 * t) * Math.exp(-t * 130) * 0.28; return [v, v]; }],
  pop: [0.16, (t) => { const v = Math.sin(TAU * (520 * t + 1600 * t * t)) * Math.exp(-t * 32) * 0.36; return [v, v]; }],
  thump: [0.7, (t) => {
    const v = Math.sin(TAU * (40 * t + (80 / 14) * (1 - Math.exp(-14 * t)))) * Math.exp(-t * 6.5) * 0.75
      + noise() * Math.exp(-t * 90) * 0.12;
    return [v, v];
  }],
  chime: [1.4, (t) => {
    const e = Math.exp(-t * 3.2);
    const v = (Math.sin(TAU * 1318.5 * t) + 0.6 * Math.sin(TAU * 1975.5 * t) + 0.2 * Math.sin(TAU * 1318.5 * 2.76 * t)) * e * 0.09;
    return [v * 0.85, v * 1.15];
  }],
};
// Whoosh is stateful (filtered noise), so it is rendered per cue below.
function whoosh(start, gain) {
  const len = 0.55, n = Math.floor(len * SR);
  let lp = 0;
  for (let k = 0; k < n; k++) {
    const p = k / n;
    const env = Math.sin(Math.PI * Math.min(1, p * 1.25)) ** 2;
    const cutoff = 0.02 + 0.25 * Math.sin(Math.PI * p); // one-pole lowpass coefficient
    lp += cutoff * (noise() - lp);
    const v = lp * env * 0.55 * gain;
    add(start + k, v * (1 - p * 0.8), v * (0.2 + p * 0.8)); // pans left -> right
  }
}

if (SFX) {
  for (const c of cues) {
    const start = Math.round(c.t * SR), g = (c.gain ?? 1) * SFX_GAIN;
    if (c.type === 'whoosh') { whoosh(start, g); continue; }
    const voice = VOICES[c.type];
    if (!voice) { console.warn(`unknown cue type "${c.type}" at ${c.t}s, skipped`); continue; }
    const [len, fn] = voice;
    for (let k = 0; k < len * SR; k++) { const [l, r] = fn(k / SR); add(start + k, l * g, r * g); }
  }
}

// ------------------------------------------------------------------ write WAV
function writeWav(path, left, right) {
  const n = left.length, b = Buffer.alloc(44 + n * 4);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 4, 4); b.write('WAVEfmt ', 8);
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(2, 22);
  b.writeUInt32LE(SR, 24); b.writeUInt32LE(SR * 4, 28); b.writeUInt16LE(4, 32); b.writeUInt16LE(16, 34);
  b.write('data', 36); b.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) {
    // soft clip so stacked hits never crack
    b.writeInt16LE(Math.round(Math.tanh(left[i] * 1.1) * 32000), 44 + i * 4);
    b.writeInt16LE(Math.round(Math.tanh(right[i] * 1.1) * 32000), 46 + i * 4);
  }
  writeFileSync(path, b);
}

mkdirSync('out', { recursive: true });
if (TRACK) {
  // Mix synthesized SFX over a supplied track, trimmed to the film length
  writeWav('out/sfx.wav', L, R);
  const r = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', TRACK, '-i', 'out/sfx.wav',
    '-filter_complex', `[0:a]atrim=0:${dur},afade=t=out:st=${Math.max(0, dur - 1)}:d=1[m];[m][1:a]amix=inputs=2:normalize=0[a]`,
    '-map', '[a]', '-ar', String(SR), '-ac', '2', OUT], { stdio: 'inherit' });
  if (r.status !== 0) process.exit(r.status ?? 1);
} else {
  writeWav(OUT, L, R);
}
console.log(`-> ${OUT}  (${dur.toFixed(2)} s, music ${MUSIC ? 'on' : TRACK ? 'from track' : 'off'}, sfx ${SFX ? cues.length + ' cues' : 'off'})`);
