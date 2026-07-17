#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_icon="$root/lilsunspot/desktop/src/assets/lilsunspot-icon.png"
output_icon="$root/lilsunspot/desktop/src-tauri/icons/icon.icns"
output_png="$root/lilsunspot/desktop/src-tauri/icons/icon.png"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/lilsunspot-icon.XXXXXX")"
iconset="$work_dir/Lilsunspot.iconset"

cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT

mkdir -p "$iconset" "$(dirname "$output_icon")"

render_icon() {
  local points="$1"
  local scale="$2"
  local output_name="$3"
  local pixels=$((points * scale))
  local resized="$work_dir/resized-${pixels}.png"

  sips --resampleHeightWidthMax "$pixels" "$source_icon" --out "$resized" >/dev/null
  sips --padToHeightWidth "$pixels" "$pixels" --padColor 000000 "$resized" \
    --out "$iconset/$output_name" >/dev/null
}

render_icon 16 1 icon_16x16.png
render_icon 16 2 icon_16x16@2x.png
render_icon 32 1 icon_32x32.png
render_icon 32 2 icon_32x32@2x.png
render_icon 128 1 icon_128x128.png
render_icon 128 2 icon_128x128@2x.png
render_icon 256 1 icon_256x256.png
render_icon 256 2 icon_256x256@2x.png
render_icon 512 1 icon_512x512.png
render_icon 512 2 icon_512x512@2x.png

iconutil --convert icns --output "$output_icon" "$iconset"
cp "$iconset/icon_512x512.png" "$output_png"
test -s "$output_icon"
test -s "$output_png"
echo "Prepared macOS icons: $output_icon and $output_png"
