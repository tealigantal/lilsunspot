#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
native_arch="$(uname -m)"
requested_arch="${1:-$native_arch}"

case "$requested_arch" in
  arm64)
    pyinstaller_arch="arm64"
    ;;
  x86_64)
    pyinstaller_arch="x86_64"
    ;;
  *)
    echo "Unsupported macOS sidecar architecture: $requested_arch" >&2
    exit 2
    ;;
esac

if [[ "$native_arch" != "$requested_arch" ]]; then
  echo "PyInstaller sidecars must be built natively: runner=$native_arch requested=$requested_arch" >&2
  exit 2
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is required to build the macOS sidecar." >&2
  exit 2
}

export MACOSX_DEPLOYMENT_TARGET=15.0

build_root="$root/ignored/pyinstaller-lilsunspotd-macos-$requested_arch"
work_dir="$build_root/build"
spec_dir="$build_root/spec"
dist_dir="$build_root/dist"
bundle_parent="$root/lilsunspot/desktop/src-tauri/binaries"
bundle_dir="$bundle_parent/lilsunspotd"
replacement_dir="$bundle_parent/.lilsunspotd-next-$$"
backup_dir="$bundle_parent/.lilsunspotd-old-$$"
resource_source="$root/lilsunspot/resources"
upstream_commit_source="$root/lilsunspot/UPSTREAM_COMMIT.txt"
plugin_source="$root/plugins"
skills_source="$root/skills"
optional_skills_source="$root/optional-skills"
optional_mcps_source="$root/optional-mcps"

cleanup() {
  rm -rf "$replacement_dir"
  if [[ -e "$backup_dir" ]]; then
    if [[ ! -e "$bundle_dir" ]]; then
      mv "$backup_dir" "$bundle_dir"
    else
      rm -rf "$backup_dir"
    fi
  fi
}
trap cleanup EXIT

rm -rf "$work_dir" "$spec_dir" "$dist_dir"
mkdir -p "$work_dir" "$spec_dir" "$dist_dir" "$bundle_parent"

cd "$root"
uv run --locked --extra web --extra lilsunspot --extra messaging --with pyinstaller==6.16.0 \
  pyinstaller \
  --onedir \
  --clean \
  --noconfirm \
  --target-arch "$pyinstaller_arch" \
  --name lilsunspotd \
  --distpath "$dist_dir" \
  --workpath "$work_dir" \
  --specpath "$spec_dir" \
  --hidden-import lilsunspot.daemon.app \
  --hidden-import uvicorn \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import gateway.platforms.weixin \
  --hidden-import aiohttp \
  --hidden-import qrcode \
  --hidden-import qrcode.image.svg \
  --hidden-import pypdf \
  --hidden-import docx \
  --hidden-import openpyxl \
  --hidden-import openpyxl.cell._writer \
  --hidden-import openpyxl.worksheet._reader \
  --hidden-import run_agent \
  --hidden-import hermes_state \
  --hidden-import gateway.session_context \
  --hidden-import tools.approval \
  --collect-submodules lilsunspot.daemon \
  --collect-submodules gateway \
  --collect-submodules plugins \
  --collect-submodules agent \
  --collect-submodules model_tools \
  --collect-submodules tools \
  --collect-submodules hermes_cli \
  --add-data "$resource_source:lilsunspot/resources" \
  --add-data "$upstream_commit_source:lilsunspot" \
  --add-data "$plugin_source:plugins" \
  --add-data "$skills_source:skills" \
  --add-data "$optional_skills_source:optional-skills" \
  --add-data "$optional_mcps_source:optional-mcps" \
  lilsunspot/daemon/sidecar_main.py

built_dir="$dist_dir/lilsunspotd"
built_executable="$built_dir/lilsunspotd"
if [[ ! -x "$built_executable" ]]; then
  echo "PyInstaller did not create executable $built_executable" >&2
  exit 1
fi
if ! lipo -archs "$built_executable" | tr ' ' '\n' | grep -Fxq "$requested_arch"; then
  echo "Built sidecar does not contain expected architecture $requested_arch" >&2
  exit 1
fi

ditto "$built_dir" "$replacement_dir"
[[ -x "$replacement_dir/lilsunspotd" ]]

if [[ -e "$bundle_dir" ]]; then
  mv "$bundle_dir" "$backup_dir"
fi
mv "$replacement_dir" "$bundle_dir"
rm -rf "$backup_dir"

echo "Built native macOS sidecar directory: $bundle_dir ($requested_arch)"
