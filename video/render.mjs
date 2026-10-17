// Renders film.js to video, frame by frame, with optional motion blur.
//
//   node render.mjs                      final: 60 fps, 4 subframes (motion blur) -> out/silent.mp4
//   node render.mjs --draft              fast: 30 fps, no blur, half size        -> out/draft.mp4
//   node render.mjs --stills 1,3.5,6     key frames only                         -> out/stills/
//   node render.mjs --from 4 --to 6      render only part of the film
//   node render.mjs --serve              live preview in your browser (http://127.0.0.1:8080)
//   node render.mjs --film km ...        render another chapter (km.js) instead of film.js
//
// Always writes out/cues.json (sound cues in the rendered range) for sound/score.mjs.

import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile, rm } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const argv = process.argv.slice(2);
const has = (k) => argv.includes('--' + k);
const arg = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };

const DRAFT = has('draft');
const FPS = Number(arg('fps', DRAFT ? 30 : 60));
const SUB = Number(arg('sub', DRAFT ? 1 : 4));
const SCALE = Number(arg('scale', DRAFT ? 0.5 : 1));
const OUT = arg('out', DRAFT ? 'out/draft.mp4' : 'out/silent.mp4');
const STILLS = arg('stills', null);

// --- tiny static server (ES modules and fonts don't load from file://)
const ROOT = process.cwd();
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  try {
    const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^([/\\])+/, '');
    const file = join(ROOT, path || 'index.html');
    if (!file.startsWith(ROOT)) throw new Error('outside root');
    res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream' });
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end(); }
});
if (has('serve')) {
  // Live preview with scrubber: npm run preview
  const port = Number(arg('port', 8080));
  await new Promise((r) => server.listen(port, '127.0.0.1', r));
  console.log(`Preview: http://127.0.0.1:${port}/index.html  (Ctrl+C to stop; reload after edits)`);
  await new Promise(() => {});
}
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const FILM_ARG = arg('film', null);
const url = `http://127.0.0.1:${server.address().port}/index.html?render${FILM_ARG ? `&film=${FILM_ARG}` : ''}`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('console', (m) => { if (m.type() === 'warning' || m.type() === 'error') console.log('[page]', m.text()); });
page.on('pageerror', (e) => { console.error('[page error]', e.message); process.exitCode = 1; });
await page.goto(url);
await page.waitForFunction(() => window.ready);
const { fontsMissing } = await page.evaluate(() => window.ready);
if (fontsMissing.length) console.warn('WARNING: fonts missing for weights', fontsMissing);
const FILM = await page.evaluate(() => window.FILM);

const FROM = Number(arg('from', 0));
const TO = Number(arg('to', FILM.dur));
await mkdir('out', { recursive: true });

// Cues for the rendered range, shifted so the clip starts at 0
const cues = (await page.evaluate(() => window.CUES))
  .filter((c) => c.t >= FROM && c.t < TO)
  .map((c) => ({ ...c, t: +(c.t - FROM).toFixed(3) }));
await writeFile('out/cues.json', JSON.stringify({ dur: TO - FROM, bpm: FILM.bpm, cues }, null, 1));

const grab = async (t) => {
  await page.evaluate((t) => window.seek(t), t);
  const dataUrl = await page.evaluate(() => window.frame());
  return Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
};

const ffmpeg = (args) => new Promise((resolve, reject) => {
  const p = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args], { stdio: ['pipe', 'inherit', 'inherit'] });
  p.on('close', (code) => (code === 0 ? resolve() : reject(new Error('ffmpeg exited ' + code))));
  return p;
});

if (STILLS) {
  // Key frames for review before a full render
  const times = STILLS.split(',').map(Number);
  await rm('out/stills', { recursive: true, force: true });
  await mkdir('out/stills', { recursive: true });
  for (const [i, t] of times.entries()) {
    await writeFile(`out/stills/s_${String(i).padStart(3, '0')}.png`, await grab(t));
    console.log(`still ${i + 1}/${times.length} at ${t}s`);
  }
  const cols = Math.min(times.length, 3);
  const rows = Math.ceil(times.length / cols);
  await ffmpeg(['-framerate', '1', '-i', 'out/stills/s_%03d.png',
    '-vf', `scale=640:-1,tile=${cols}x${rows}:padding=8:color=0x07090C`, '-frames:v', '1', 'out/stills/sheet.png']);
  console.log('-> out/stills/sheet.png');
} else {
  const vf = [];
  if (SUB > 1) vf.push(`tmix=frames=${SUB}`, `select='eq(mod(n\\,${SUB})\\,${SUB - 1})'`, `setpts=N/${FPS}/TB`);
  if (SCALE !== 1) vf.push(`scale=${Math.round(FILM.w * SCALE / 2) * 2}:-2:flags=lanczos`);
  vf.push('format=yuv420p');

  const enc = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-i', '-',
    '-vf', vf.join(','), '-r', String(FPS),
    '-c:v', 'libx264', '-preset', DRAFT ? 'veryfast' : 'slow', '-crf', DRAFT ? '22' : '16',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-movflags', '+faststart', OUT],
  { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((r, j) => enc.on('close', (c) => (c === 0 ? r() : j(new Error('ffmpeg exited ' + c)))));

  const total = Math.round((TO - FROM) * FPS * SUB);
  const started = Date.now();
  for (let i = 0; i < total; i++) {
    const png = await grab(FROM + i / (FPS * SUB));
    if (!enc.stdin.write(png)) await new Promise((r) => enc.stdin.once('drain', r));
    if (i % (FPS * SUB) === 0) {
      const s = i / (FPS * SUB);
      const rate = i / ((Date.now() - started) / 1000 || 1);
      console.log(`rendered ${s.toFixed(0)}s / ${(TO - FROM).toFixed(1)}s  (${rate.toFixed(1)} frames/s)`);
    }
  }
  enc.stdin.end();
  await done;
  console.log(`-> ${OUT}  (${total} captures, ${((Date.now() - started) / 1000).toFixed(0)} s)`);
}

await browser.close();
server.close();
