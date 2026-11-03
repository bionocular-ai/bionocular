#!/usr/bin/env bash
# Captures both questions' Bionocular answers into assets/screens/, each run reopened from the chat
# history (never re-asked), its column widened from 1080 to 1460 px: at rest, its expert-review chip
# hovered (the chip alone), and for Question 1 with Charts open on Heatmap (film.js) - Question 3's
# Charts captures (q3-charts-*) start at its toggle and never show the chip. Prints the rects the
# films use (2x capture px). Needs the web dev server on :3000 and the logged-in profile. Headless,
# 2x, pointer parked. The viewport is taller than the answer: a headless element shot of a tall turn
# paints blank above the fold, so the full page is shot and the turn cropped from it.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=assets/screens
TMP=$(mktemp -d)
export AGENT_BROWSER_SESSION=answers-capture
ab() { agent-browser "$@" >/dev/null; }
js() { agent-browser eval "$1" | tr -d '"'; }
CHIP_TEXT="Reviewed by a biopharma expert (MD or PhD)"
# A rect relative to the answer turn, 2x: x:y:w:h.
rel() { js "(() => { const R = document.getElementById('film-turn').getBoundingClientRect(); const r = ($1).getBoundingClientRect(); return [r.x - R.x, r.y - R.y, r.width, r.height].map(v => Math.round(v * 2)).join(':'); })()"; }
chip_el="[...document.querySelectorAll('#film-turn button')].find(b => b.innerText.includes('$CHIP_TEXT'))"
turn() { js "(() => { const r = document.getElementById('film-turn').getBoundingClientRect(); return [r.width, r.height, r.x, r.y].map(v => Math.round(v * 2)).join(':'); })()"; }
# The page shot, cropped to the turn.
shoot() {
  ab mouse move 1900 40; ab wait 600
  ab screenshot "$TMP/page.png"
  ffmpeg -hide_banner -loglevel error -y -i "$TMP/page.png" -vf "crop=$(turn)" "$1"
  echo "$1 ($(turn | cut -d: -f1-2 | tr : x))"
}
# A past run by its title and date; the turn holding its table gets id film-turn.
open_run() {
  ab set viewport 1920 1080 2
  ab open http://localhost:3000/dashboard/cutaneous-melanoma/agent
  ab wait --text "What do you want to know?"
  ab eval "document.head.insertAdjacentHTML('beforeend','<style>.max-w-\\\\[1080px\\\\]{max-width:1460px!important}nextjs-portal,.tsqd-parent-container{display:none!important}</style>')"
  ab eval "[...document.querySelectorAll('button')].find(b => b.getAttribute('aria-label') === 'Show chat history')?.click()"
  ab wait --text "$2"
  ab eval "[...document.querySelectorAll('button')].filter(b => b.innerText.startsWith('$1') && b.innerText.includes('$2'))[0].click()"
  ab wait --text "$3"
  ab eval "[...document.querySelectorAll('button')].find(b => b.getAttribute('aria-label') === 'Hide chat history')?.click()"
  ab eval "(() => { const box = document.querySelector('.max-w-\\\\[1080px\\\\]'); let e = document.querySelector('table'); while (e.parentElement !== box) e = e.parentElement; e.id = 'film-turn'; })()"
  ab set viewport 1920 "$4" 2; ab wait 1500
}
# The answer at rest, then its chip hovered and cropped alone.
answer() {
  shoot "$OUT/$1-bio-answer@2x.png"
  local c; c=$(rel "$chip_el"); echo "  chip $c"
  ab find role button hover --name "$CHIP_TEXT"; ab wait 500
  ab screenshot "$TMP/page.png"
  IFS=: read -r _ _ tx ty <<< "$(turn)"; IFS=: read -r x y w h <<< "$c"
  ffmpeg -hide_banner -loglevel error -y -i "$TMP/page.png" -vf "crop=$w:$h:$((tx + x)):$((ty + y))" "$OUT/$1-reviewed-hover@2x.png"
  echo "$OUT/$1-reviewed-hover@2x.png"
}

ab --profile ~/.claude/chrome-profile-bionocular open about:blank

# Question 1: the first 08/10 run, "The search identified 19 treatments from 12 trials".
open_run "show me all published efficacy parameters (ORR, DCR and CR) in metastatic" "08/10/2026" "Open in Efficacy Intelligence Hub" 2600
answer q1
echo "  toggle $(rel "[...document.querySelectorAll('#film-turn button')].find(b => b.innerText.trim().startsWith('Charts'))")"
echo "  link $(rel "[...document.querySelectorAll('#film-turn a, #film-turn button')].find(b => b.innerText.trim().startsWith('Open in'))")"
ab set viewport 1920 3100 2; ab wait 800
ab find role button click --name "Charts"; ab wait 800
ab find text "Heatmap" click; ab wait 2500
shoot "$OUT/q1-bio-answer-heatmap@2x.png"
echo "  link open $(rel "[...document.querySelectorAll('#film-turn a, #film-turn button')].find(b => b.innerText.trim().startsWith('Open in'))")"
# The panel alone (film.js PANEL, HEAT.src).
ffmpeg -hide_banner -loglevel error -y -i "$OUT/q1-bio-answer-heatmap@2x.png" -vf "crop=2868:1765:52:3136" "$OUT/q1-charts-heatmap@2x.png"
echo "$OUT/q1-charts-heatmap@2x.png"

# Question 3 (the film's Question 2): the run of 2026-10-20.
open_run "provide phase 3 active clinical treatments" "20/10/2026" "Open in" 2400
answer q3
echo "  toggle $(rel "[...document.querySelectorAll('#film-turn button')].find(b => b.innerText.trim().startsWith('Charts'))")"
agent-browser close >/dev/null
