# Bionocular product film - house rules

The Bionocular product film, rendered from code: an HTML canvas draws every frame, Playwright captures
them, ffmpeg encodes. Read this file before every task here. The film is a set of chapters (one per
question or feature). Chapters: `film.js` (Question 2, `docs/storyboard.md`), `km.js` (KM Curves
Intelligence, `docs/storyboard-km.md`), `q3.js` (Question 3, `docs/storyboard-q3.md`), `intro.js` (product
intro slides on white, `docs/storyboard-intro.md`) and `pages.js` (dashboard tour, `docs/storyboard-pages.md`,
captures from `scripts/capture-pages.sh`). Pass `--film km` to
`render.mjs` (or `?film=km` to the preview) for a chapter other than `film.js`. Each chapter renders into its own
folder, `out/<chapter>/` (`film.js` into `out/q2/`), with its `cues.json` next to the video.
`master.js` is the packaged demo (104.25 s, `docs/storyboard-master.md`): brand card, product intro, sign-in, dashboard tour (pages),
Question 1 (Simple, Q2), Question 2 (Complex, Q3), KM Curves Intelligence, end card (tagline, bionocular.ai). One app window
runs from sign-in to the last chapter: `joins.js` holds the joins (the login card growing into the app, the rail clicks, both
questions typed into the real composer, captured by `scripts/capture-agent.sh`). It draws each chapter at its own local time,
so chapter edits flow into it; `npm run master` renders it at `--sub 12` (fast camera moves strobe at 4) with the music bed
into `out/master/`. Chapters on their own stay effects-only. The KM captures come from `scripts/capture-km.sh`.

## How a film is made

- Each chapter module (`film.js`, `km.js`) is a film. It exports `FILM` (size, duration, bpm), `CUES` (sound cues) and `draw(g, T)`.
- `draw(g, T)` paints the exact frame for global time `T` in seconds. It must be a **pure function of T**:
  no timers, no `requestAnimationFrame` logic, no CSS transitions, no state carried between frames,
  no `Math.random` (use `rng(seed)` from `lib/motion.js`).
- Motion uses `lib/motion.js`: `sp(t, preset)` springs, `track()` / `track2()` for values with several targets,
  `window01()` for opacity windows, eases only for things that must land exactly (counters, progress).
  Never restart a spring when a value changes target; add one with `track()`.
- Drawing helpers are in `lib/draw.js` (`risingText`, `drawCursor`, `rrect`, `mixColor`, `font`).
- Fonts are the product's own, symlinked from `web/src/app/fonts` into `assets/fonts` and registered in
  `index.html`: `font(weight, size, 'display')` is Onest, `'sans'` (default) Poppins (400-700), `'mono'`
  IBM Plex Mono, the app's faces since PR #166. Never rely on system fonts. `assets/logo.svg` links to `web/public/logo.svg`.
- Format: 1920×1080, 16:9, 60 fps. A chapter starts and ends on the bare canvas so chapters join without a seam.

## Workflow — stop at each gate and wait for my OK

1. **Brief.** Read `docs/BRIEF.md`. If anything essential is missing, ask me before planning.
2. **Storyboard.** Write `docs/storyboard.md` (scene, time range, on screen, motion, transition, sound cue).
   Show it to me. **Stop.**
3. **Stills.** Build the scenes, then `node render.mjs --stills <one time per scene>`. Open
   `out/stills/sheet.png`, critique it (below), fix, then show me the sheet. **Stop.**
4. **Draft.** `npm run draft`, then `bash scripts/review.sh out/q2/draft.mp4 <time of fastest action>`.
   Critique loop until every score is 8+.
5. **Final.** `npm run final` → `out/q2/silent.mp4` (picture only) and `out/q2/final.mp4` (with sound).
   Always deliver both.

## Critique loop (run it yourself before showing me anything)

Open `out/review/contact.png`, `phone.png` and `strip.png` and look at them properly. Be a harsh motion
director, not a proud author. Score 1–10:
hook in the first 2 s · readability at phone size · motion quality · variety (something new every 2–4 s) ·
composition · brand accuracy · sound sync (only if sound is on).
List the 3 biggest problems with timestamps, fix them, re-render only the affected range with
`--from/--to`, and re-score. Hunt for: text overlapping during swaps, things sliding instead of springing,
blurry scaled text, dead beats where nothing happens, elements touching the frame edge, text below 24 px.

## Look

- Banned: centred title on a gradient, everything fading in, corner labels or frame borders, glows on UI,
  generic particle bursts, lens flares, stock "tech" grids.
- Bionocular tokens only (`C` in `film.js`, from `web/src/app/globals.css`): page #F7FAF9, ink #102B36,
  muted #4A6B77, border #C8E0D8, deep teal #1B4F65 as the one strong colour, seafoam #7AC1A2 / #DAF0E6 to
  mark what the viewer should look at. Light canvas; real UI sits on it as a white sheet with one soft shadow.
- Onest only for the few words of display type and headline stats (Onest 600, tight tracking), Poppins for UI text,
  Plex Mono for every other number (data, tallies, table values).
- Left-aligned editorial layout on a consistent grid (x = 160 margin) unless the brief says otherwise.
- Elements enter with springs or masks, not opacity fades. Opacity is for exits and secondary details only.
- Something new must happen on screen every 2–4 seconds. The last 1.5–2 s may hold on the end card.

## Product truth (non-negotiable)

- Use real product screenshots from `assets/screens/` (Bionocular captured at 2x with agent-browser from
  the logged-in app). Crop and animate them; never invent screens or features the product does not have.
- Competitor answers (Gemini, Opus) are their real screenshots, unedited apart from crops and highlights.
  Name them in text in our type as vendor + model ("Google Gemini 3.1 Pro", "Anthropic Claude Opus 5.5"), the
  vendor word and their bars in an identification colour only (Google Blue #4285F4, Claude orange #D97757;
  text shades #1A73E8, #C96442). No capture month, no competitor logos, no redrawn competitor UI. A comparison
  film's description (never the picture) carries "Not affiliated with or endorsed by Google or Anthropic." Our teal stays the hero colour.
  Every on-screen tally is counted from the screenshot it sits beside.
- Never show accuracy, sensitivity, outcome or performance claims unless `docs/BRIEF.md` provides them
  with a source. Any illustrative number must carry an on-screen "Example data" label.
- Never use real patient or user images. Use the stylised procedural illustration, or images the brief
  explicitly says we have the rights to use.

## Sound (optional layer — the picture never depends on it)

- Cues are declared in `film.js` with `cue(time, type, gain)`, next to the motion they belong to.
  Types: `click`, `tick`, `pop`, `whoosh`, `thump`, `chime`.
- `npm run sound` synthesises music + effects into `out/q2/audio.wav`; `npm run sound:sfx-only` for effects only;
  `node sound/score.mjs --track audio/<file>.wav` to put the effects over a supplied track.
- Place big moments (scene changes, logo) on beats: `beats(FILM.bpm).at(n)`.

## Commands

| Command | Output |
|---|---|
| `npm run preview` | live preview with scrubber at http://127.0.0.1:8080 |
| `node render.mjs --stills 1,3.5,6` | `out/stills/sheet.png` |
| `npm run draft` | `out/q2/draft.mp4` (30 fps, half size, fast) |
| `npm run render` | `out/q2/silent.mp4` (60 fps, motion blur) |
| `npm run final` | `out/q2/silent.mp4` + `out/q2/audio.wav` + `out/q2/final.mp4` |
| `npm run master` | `out/master/silent.mp4` + `out/master/final.mp4` (whole demo, music + effects) |
| `bash scripts/review.sh <video> [second]` | `out/review/*.png` |

Effort: use high effort for new films, medium for small fixes and re-renders.
