#!/usr/bin/env bash
# Captures the page the master film lands on after sign-in (docs/storyboard-master.md): /dashboard's
# eight disease portfolios at rest, with the cards hidden (they stagger in on the real page), and each
# card hovered, cropped to the card and its shadow. Into assets/screens/agent/.
# Needs the web dev server on :3000 and the logged-in profile. Headless, 2x, pointer parked.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=assets/screens/agent
mkdir -p "$OUT/portc"
export AGENT_BROWSER_SESSION=portfolio-capture
ab() { agent-browser "$@" >/dev/null; }

ab --profile ~/.claude/chrome-profile-bionocular open about:blank
ab set viewport 1440 900 2
ab open http://localhost:3000/dashboard
ab wait --text "Disease Portfolios"
ab eval "document.head.insertAdjacentHTML('beforeend','<style>nextjs-portal,.tsqd-parent-container{display:none!important}</style>')"
ab wait 1500
ab mouse move 700 760
ab wait 400
ab screenshot "$OUT/port-rest@2x.png"

# CSS [x, y] of each card, 308x168; the film draws each crop with the same 20 px margin (joins.js PORT).
i=0
for xy in "80 247" "404 247" "728 247" "1052 247" "80 431" "404 431" "728 431" "1052 431"; do
  i=$((i + 1))
  read -r x y <<< "$xy"
  ab mouse move $((x + 154)) $((y + 84))
  ab wait 500
  ab screenshot "$OUT/port-hover.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/port-hover.png" -vf "crop=696:416:$(((x - 20) * 2)):$(((y - 20) * 2))" "$OUT/portc/0$i@2x.png"
done
rm "$OUT/port-hover.png"

ab mouse move 700 760
ab eval "document.head.insertAdjacentHTML('beforeend','<style>.cancer-card{visibility:hidden!important}</style>')"
ab wait 400
ab screenshot "$OUT/port-empty@2x.png"

agent-browser close
ls "$OUT"/port-*@2x.png "$OUT"/portc/
