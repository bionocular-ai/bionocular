#!/usr/bin/env bash
# Captures every screen the pages chapter needs (docs/storyboard-pages.md) into assets/screens/pages/.
# Needs the web dev server on :3000 and the logged-in profile. Headless, 2x, pointer parked, focus blurred.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=assets/screens/pages
mkdir -p "$OUT"
export AGENT_BROWSER_SESSION=pages-capture
BASE=http://localhost:3000/dashboard/cutaneous-melanoma
ab() { agent-browser "$@" >/dev/null; }

# Fresh load, then hide the Next.js and React Query dev badges and wait for the page's own ready text.
load() {
  ab open "$BASE/$1"
  ab wait --text "$2"
  ab wait --fn "!document.body.innerText.includes('Loading')"
  ab eval "document.head.insertAdjacentHTML('beforeend','<style>nextjs-portal,.tsqd-parent-container{display:none!important}</style>')"
  ab wait 1500
}
# Pointer on the page title, nothing focused, then shoot.
shot() {
  ab mouse move 600 120
  ab eval "document.activeElement && document.activeElement.blur()"
  ab wait 400
  ab screenshot "$OUT/$1@2x.png"
  echo "$OUT/$1@2x.png"
}
# The same frame with the pointer over the next page's rail icon.
rail_hover() {
  ab find role link hover --name "$2" --exact
  ab wait 400
  ab screenshot "$OUT/$1-hover@2x.png"
  echo "$OUT/$1-hover@2x.png"
}
# Chart with its marks hidden, for the build-up from empty axes.
empty_chart() {
  ab eval "document.head.insertAdjacentHTML('beforeend','<style>.recharts-bar,.recharts-scatter,.recharts-label-list,.recharts-reference-line{visibility:hidden!important}</style>')"
  ab wait 300
  shot "$1"
}

ab --profile ~/.claude/chrome-profile-bionocular open about:blank
ab set viewport 1440 900 2

load trial-updates "trials changed"; shot tu-all
load "trial-updates?show=new" "trials changed"; shot tu-new; rail_hover tu-new "Live News"

load live-ticker "Live News"; shot ln-latest
load "live-ticker?view=efficacy" "Live News"; shot ln-efficacy
ab find role button click --name "All 10 values"; ab wait 800; shot ln-efficacy-open; rail_hover ln-efficacy-open "Trial Landscape"

load landscape "Small Molecule"; shot ls-modality
ab find role button click --name "Group by"; ab wait 600; ab screenshot "$OUT/ls-menu@2x.png"; echo "$OUT/ls-menu@2x.png"
ab find role option click --name "Line of therapy"; ab wait 2000; shot ls-line
rail_hover ls-line "Outcome Intelligence Hub"

load intelligence-hub "with results, from"; shot hub-rest
ab find role checkbox check --name "Phase 3"; ab wait --text "from 38 trials"; ab wait 1000; shot hub-p3
ab find role checkbox check --name "Select NEO-MIMAJOR"; ab find role checkbox check --name "Select Encorafenib + Binimetinib + Pembrolizumab"
ab wait --text "2 of 5 selected"; ab wait 800; shot hub-2sel
ab find role button click --name "Open agent"; ab wait --text "Answering about these 2 readouts"; ab wait 1000; shot hub-agent
ab find role button click --name "Close agent"; ab wait 800; rail_hover hub-2sel "Efficacy"

# The charts run below the fold at 900 px; take them at a taller viewport and crop in the film.
ab set viewport 1440 1500 2
load "analytics?mode=efficacy" "treatments"; shot eff-all
ab find role button click --name "Phase 3" --exact
ab wait --fn "!document.body.innerText.includes('Loading analytics')"; ab wait 2500; shot eff-p3; empty_chart eff-p3-empty

agent-browser close
