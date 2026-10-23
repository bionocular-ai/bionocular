#!/usr/bin/env bash
# Review images for the critique loop. Claude opens these and scores the film.
#   bash scripts/review.sh [video] [fast-action-second]
set -euo pipefail
VIDEO="${1:-out/q2/silent.mp4}"
AT="${2:-}"
mkdir -p out/review
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
ROWS=$(python3 -c "import math;print(math.ceil(float('$DUR')*2/6))")

# Contact sheet: 2 frames per second, 6 across
ffmpeg -hide_banner -loglevel error -y -i "$VIDEO" \
  -vf "fps=2,scale=320:-1,tile=6x${ROWS}:padding=4:color=0x07090C" -frames:v 1 out/review/contact.png

# Phone test: 1 frame per second at 360 px wide (how it reads on a phone feed)
ffmpeg -hide_banner -loglevel error -y -i "$VIDEO" \
  -vf "fps=1,scale=360:-1,tile=4x$(python3 -c "import math;print(math.ceil(float('$DUR')/4))"):padding=4" -frames:v 1 out/review/phone.png

# Strip: 12 consecutive frames around a fast action (catches pops, overlaps, flicker)
if [ -n "$AT" ]; then
  START=$(python3 -c "print(max(0, $AT - 0.1))")
  ffmpeg -hide_banner -loglevel error -y -ss "$START" -i "$VIDEO" \
    -vf "scale=320:-1,tile=6x2:padding=4" -frames:v 1 out/review/strip.png
fi

# Loop check: two plays back to back (only matters for looping films)
ffmpeg -hide_banner -loglevel error -y -stream_loop 1 -i "$VIDEO" -c copy out/review/loop_check.mp4

echo "-> out/review/contact.png, phone.png${AT:+, strip.png}, loop_check.mp4"
