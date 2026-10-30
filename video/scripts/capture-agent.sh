#!/usr/bin/env bash
# Captures the screens the master film's joins need (docs/storyboard-master.md) into assets/screens/agent/:
# the login card typed in, the Efficacy hub and the agent threads with a rail icon hovered, the empty
# agent page and the Question 1 thread, and both questions typed into their composers one word per frame.
# Needs the web dev server on :3000 and the logged-in profile. Headless, 2x, pointer parked, caret hidden.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=assets/screens/agent
mkdir -p "$OUT/q1" "$OUT/q2"
BASE=http://localhost:3000
ab() { agent-browser "$@" >/dev/null; }

# The Next.js and React Query dev badges and the text caret never show.
clean() {
  ab eval "document.head.insertAdjacentHTML('beforeend','<style>nextjs-portal,.tsqd-parent-container{display:none!important}textarea,input{caret-color:transparent!important}</style>')"
}
park() { ab mouse move 700 140; }
shot() { ab wait 400; ab screenshot "$OUT/$1@2x.png"; echo "$OUT/$1@2x.png"; }
# A rail link hovered, once the rail has expanded (300 ms hover intent, then a 200 ms widen).
rail_hover() { ab find role link hover --name "$1" --exact; ab wait 600; }

# ---------------------------------------------------------------- login: a fresh session, never submitted
export AGENT_BROWSER_SESSION=login-capture
ab open about:blank
ab set viewport 1440 900 2
ab open "$BASE/login"
ab wait --text "Welcome Back"
clean
ab wait 1200
park; shot login-empty
EMAIL=demo@bionocular.ai
ab click "#email"
for n in 3 6 9 12 15 18; do ab fill "#email" "${EMAIL:0:$n}"; park; shot "login-email-$n"; done
ab click "#password"
for n in 3 6 10; do ab fill "#password" "$(printf 'x%.0s' $(seq 1 $n))"; park; shot "login-pass-$n"; done
ab find role button hover --name "Login"; shot login-hover
agent-browser close

# ---------------------------------------------------------------- the app, logged in
export AGENT_BROWSER_SESSION=agent-capture
ab --profile ~/.claude/chrome-profile-bionocular open about:blank

# The Efficacy hub at Phase 3, the AI Agent rail icon hovered (the pages chapter's viewport).
ab set viewport 1440 1500 2
ab open "$BASE/dashboard/cutaneous-melanoma/analytics?mode=efficacy"
ab wait --text "treatments"
clean
ab find role button click --name "Phase 3" --exact
ab wait --fn "!document.body.innerText.includes('Loading analytics')"; ab wait 2500
rail_hover "AI Agent"; shot eff-agent-hover

ab set viewport 1440 900 2
# A thread's composer: one frame per word typed, then the Send hover.
type_words() {
  local dir=$1 text=$2 i=0 sofar=""
  ab click textarea
  for w in $text; do
    i=$((i + 1)); sofar="${sofar:+$sofar }$w"
    ab fill textarea "$sofar"; park
    ab wait 150; ab screenshot "$OUT/$dir/$(printf '%02d' $i)@2x.png"
  done
  ab find role button hover --name "Send"; shot "$dir/hover"
  echo "$OUT/$dir: $i words"
}
# The history drawer: shown or hidden by its own toggle; a past chat opened by its title and date.
history() { ab eval "[...document.querySelectorAll('button')].find(b => b.getAttribute('aria-label') === '$1 chat history')?.click()"; ab wait 600; }
open_chat() { ab wait --text "$2"; ab eval "[...document.querySelectorAll('button')].find(b => b.innerText.startsWith('$1') && b.innerText.includes('$2')).click()"; }
composer_rect() { agent-browser eval "JSON.stringify(document.querySelector('textarea').closest('div.flex').getBoundingClientRect())"; }

# The empty agent page, history hidden: at rest, then Question 1 typed in.
ab open "$BASE/dashboard/cutaneous-melanoma/agent"
ab wait --text "What do you want to know?"
clean
history Hide
park; shot agent-empty
echo "empty composer: $(composer_rect)"
type_words q1 "show me all published efficacy parameters (ORR, DCR and CR) in metastatic /cutaneous melanoma for active treatments. strict rule: only treatments which are in phase 1 trial."

# The Question 1 thread (2026-10-08) at its foot: at rest, then Question 2 typed as a follow-up.
ab open "$BASE/dashboard/cutaneous-melanoma/agent"
ab wait --text "What do you want to know?"
clean
history Show
open_chat "show me all published efficacy parameters (ORR, DCR and CR) in metastatic" "08/10/2026"
ab wait --text "Open in Efficacy Intelligence Hub"
history Hide
ab wait 1500
park; shot q1-thread
echo "thread composer: $(composer_rect)"
type_words q2 "provide phase 3 active clinical treatments showing median PFS vs grade3+ Treatment emergent adverse events vs treatment discontinuation due to AEs in metastatic /cutaneous melanoma."

# The Question 2 thread (2026-10-20) at its foot, then the KM Curves Intelligence rail icon hovered.
ab open "$BASE/dashboard/cutaneous-melanoma/agent"
ab wait --text "What do you want to know?"
clean
history Show
open_chat "provide phase 3 active clinical treatments" "20/10/2026"
ab wait --text "Open in"
history Hide
ab wait 1500
park; shot q2-thread
rail_hover "KM Curves Intelligence"; shot q2-thread-km-hover

agent-browser close

# Typing only changes a band around each composer (measured as the pixel diff from the frame at rest),
# so the film loads those bands, not 53 full frames: q1c/ and q2c/, 2x crops of CSS [x, y, w, h].
crop_dir() {
  mkdir -p "$OUT/$1c"
  for f in "$OUT/$1"/*@2x.png; do ffmpeg -hide_banner -loglevel error -y -i "$f" -vf "crop=$2" "$OUT/$1c/$(basename "$f")"; done
  echo "$OUT/$1c: $(ls "$OUT/$1c" | wc -l | tr -d ' ') crops"
}
crop_dir q1 1584:384:752:680   # CSS [376, 340, 792, 192]: the title through the suggestion chips
crop_dir q2 2192:252:448:1540  # CSS [224, 770, 1096, 126]: the thread composer, one or two lines
