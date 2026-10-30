#!/usr/bin/env bash
# Captures every screen the KM chapter needs (docs/storyboard-km.md) into assets/screens/: the page with
# coBRIM's raised-LDH arms chosen in both panels (the one publication whose four rows all carry a
# published median, twin median and match %), each filter hovered and open (the arms menus scrolled to
# that group), the agent button hovered, the plot hovered at 12 months, the whole page, and the agent
# drawer with both prompts typed in one line at a time (cropped to the drawer).
# Needs the web dev server on :3000 and the logged-in profile. Headless, 2x, focus blurred.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=assets/screens
export AGENT_BROWSER_SESSION=km-capture
ab() { agent-browser "$@" >/dev/null; }

shot() { ab wait 400; ab screenshot "$OUT/$1@2x.png"; echo "$OUT/$1@2x.png"; }
# The drawer only, at 2x: R.drawer in km.js is [1020, 56, 420, 844].
panel() {
  ab wait 400
  ab screenshot "$OUT/.panel@2x.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/.panel@2x.png" -vf "crop=840:1688:2040:112" "$OUT/$1@2x.png"
  rm "$OUT/.panel@2x.png"
  echo "$OUT/$1@2x.png"
}
park() { ab mouse move 600 120; ab eval "document.activeElement && document.activeElement.blur()"; }
click_at() { ab mouse move "$1" "$2"; ab mouse down; ab mouse up; ab wait 700; }

ab --profile ~/.claude/chrome-profile-bionocular open about:blank
ab set viewport 1440 900 2
ab open http://localhost:3000/dashboard/cutaneous-melanoma/head-to-head-survival
ab wait --text "Survival Curves"
ab wait --fn "!document.body.innerText.includes('Loading')"
ab eval "document.head.insertAdjacentHTML('beforeend','<style>nextjs-portal,.tsqd-parent-container{display:none!important}textarea{caret-color:transparent!important}</style>')"
ab wait 2500
# The arms menu at (x, y): cleared, then both raised-LDH arms ticked, through the menu itself.
ARMS=("Cobimetinib + Vemurafenib Raised LDH" "Placebo + Vemurafenib Raised LDH")
choose_arms() {
  click_at "$1" "$2"
  ab find role button click --name "Clear" --exact; ab wait 300
  for arm in "${ARMS[@]}"; do ab find role menuitemcheckbox click --name "$arm" --exact; ab wait 300; done
  ab press Escape; ab wait 500
}
# Scrolls the open arms menu until the chosen arms' group heads the list, as a user would.
scroll_to_arms() {
  ab eval "(() => { const it = [...document.querySelectorAll('[role=menu] [role=menuitemcheckbox]')].find((i) => i.innerText.includes('${ARMS[0]}')); const list = it.parentElement; list.scrollTop += it.previousElementSibling.getBoundingClientRect().top - list.firstElementChild.getBoundingClientRect().top; })()"
  ab wait 400
}
choose_arms 1260 132
choose_arms 1260 176
ab wait 2000
park; shot km-rest

# Endpoint filter (OS panel): hovered, then open.
ab mouse move 1040 132; shot km-endpoint-hover
click_at 1040 132; shot km-endpoint-open
ab press Escape; ab wait 400
# Treatment arms, OS then PFS: hovered, then open on their default pair.
ab mouse move 1260 132; shot km-arms1-hover
click_at 1260 132; scroll_to_arms; shot km-arms1-open2
ab press Escape; ab wait 400
click_at 1260 176; scroll_to_arms; shot km-arms2-open2
ab press Escape; ab wait 400

# The plot hovered at 12 months: guide line, active dots, tooltip.
ab mouse move 656 520; shot km-hover
# The floating agent button hovered.
ab mouse move 1346 833; shot km-fab-hover

# The whole page, agent button hidden (km.js draws it on its own).
park
ab eval "document.head.insertAdjacentHTML('beforeend','<style id=nofab>[aria-label^=\"Open agent\"]{visibility:hidden!important}</style>')"
ab wait 400
ab screenshot --full "$OUT/km-page-full@2x.png"; echo "$OUT/km-page-full@2x.png"
ab eval "document.getElementById('nofab').remove()"

# The agent drawer, then each prompt typed through the end of each wrapped line (km.js PROMPT_LINES).
ab find role button click --name "Open agent"
ab wait --text "What do you want to know?"
park; panel km-drawer-panel
type_lines() {
  local i=$1; shift
  local sofar="" k=0
  for line in "$@"; do
    k=$((k + 1))
    # A line that breaks at a hyphen ("Post-") joins the next without a space.
    if [[ "$sofar" == *- ]]; then sofar="$sofar$line"; else sofar="${sofar:+$sofar }$line"; fi
    ab fill textarea "$sofar"; park
    echo "  prompt $i line $k: textarea $(agent-browser eval "document.querySelector('textarea').scrollHeight") px"
    panel "km-prompt$i-$k-panel"
  done
}
type_lines 1 "Calculate the delta between the PFS" "and OS digital twins to identify which" "parameters most strongly drive Post-" "Progression Survival?"
type_lines 2 "Compare the PFS and OS digital twins to" "model Post-Progression Survival and" "highlight top hazard drivers?"

agent-browser close
