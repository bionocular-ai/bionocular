# Motion studio

Product demo videos rendered from code: an HTML canvas draws every frame, Playwright captures
them, ffmpeg encodes. Sound is synthesised from cues as a separate layer, so you always get a
silent version too. No After Effects, no Remotion licence, nothing to pay for.

## Setup (once)

Requirements: Node 22+, ffmpeg (`brew install ffmpeg` / `sudo apt install ffmpeg`).

```bash
npm install
npx playwright install chromium
npm run preview          # open http://127.0.0.1:8080 to see the demo film
npm run final            # out/silent.mp4 + out/final.mp4 (with sound)
```

## Making your video with Claude Code

1. Fill in `docs/BRIEF.md`. Put real screenshots in `assets/screens/`, your logo in `assets/`,
   and an optional style reference in `refs/`.
2. Start Claude Code in this folder on Opus 5.5 at high effort and say:

   > Read CLAUDE.md and docs/BRIEF.md. Plan the film and write docs/storyboard.md. Stop for my approval.

3. Approve or change the storyboard. Claude then builds the scenes, renders stills and stops again.
4. After the stills, Claude drafts, runs its own critique loop, and renders the final.

`CLAUDE.md` holds the house rules (render contract, banned clichés, product-truth rules, critique loop),
so you don't have to repeat them in prompts.

## Sound: keep it or drop it

| You want | Use |
|---|---|
| Music + effects | `out/final.mp4` |
| No sound at all | `out/silent.mp4` |
| Effects only | `npm run sound:sfx-only && npm run mux` |
| Your own track + effects | `node sound/score.mjs --track audio/song.wav && npm run mux` |
| Quieter music | `node sound/score.mjs --music-gain 0.5 && npm run mux` |

## Files

| Path | What it is |
|---|---|
| `film.js` | The film: timeline, scenes, sound cues. The file Claude edits. |
| `lib/motion.js` | Springs, `track()`, seeded random, beat helpers |
| `lib/draw.js` | Masked text, cursor, rounded rects, colour mixing |
| `index.html` | Loads fonts and the film; preview player with scrubber |
| `render.mjs` | Renderer: stills, draft, final (motion blur), preview server |
| `sound/score.mjs` | Synthesised music bed and effects from `out/cues.json` |
| `scripts/review.sh` | Contact sheet, phone test, frame strip for the critique loop |
| `docs/BRIEF.md` | What you fill in |
| `docs/storyboard.md` | What Claude writes and you approve |

## Timing

On a typical laptop: stills in about 2 s, a 25 s draft in about 30 s, a 25 s final with motion blur in
about 3 minutes. Use `--from 4 --to 7` to re-render one section while iterating.

The demo content (product window, illustration, numbers) is a placeholder. The illustration is
procedural, and the numbers are labelled "Example data". Inter font is included under the SIL Open
Font License (`assets/fonts/OFL.txt`).
