#!/usr/bin/env bash
# Turns the screen recordings from web/e2e/record.spec.ts into the README's GIFs
# (docs/media/*.gif) and the release's MP4 walkthrough (dist/walkthrough.mp4).
# Needs ffmpeg. Run through `make gif`, which records first.
set -euo pipefail

IN=web/recordings
WIDTH=${WIDTH:-960}
mkdir -p docs/media dist

trim() { python3 -c "import json, sys; print(json.load(open(sys.argv[1]))['trim'])" "$IN/$1.json"; }

# name:frames per second:size budget in MB (the README loads them all, so keep them lean)
for clip in hero:12:10 search-profile:10:5 assistant:10:7 analyst:10:5; do
  IFS=: read -r name fps budget <<<"$clip"
  # Two passes in one: a palette from the frames' changes, then redraw only what changes.
  # No dithering: the map and UI are flat colours, and dither noise bloats the file
  ffmpeg -y -loglevel error -ss "$(trim "$name")" -i "$IN/$name.webm" \
    -vf "fps=$fps,scale=$WIDTH:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
    "docs/media/$name.gif"
  size=$(python3 -c "import os, sys; print(round(os.path.getsize(sys.argv[1]) / 1e6, 1))" "docs/media/$name.gif")
  echo "docs/media/$name.gif: $size MB (budget $budget MB)"
  python3 -c "import sys; sys.exit(float(sys.argv[1]) > float(sys.argv[2]))" "$size" "$budget" \
    || { echo "  over budget: shorten the clip, or try WIDTH=880" >&2; exit 1; }
done

ffmpeg -y -loglevel error -ss "$(trim walkthrough)" -i "$IN/walkthrough.webm" \
  -c:v libx264 -pix_fmt yuv420p -crf 22 -preset slow -movflags +faststart dist/walkthrough.mp4
echo "dist/walkthrough.mp4: $(du -h dist/walkthrough.mp4 | cut -f1)"
