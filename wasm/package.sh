#!/bin/sh
# Packages the browser build with its game data. Runs inside the
# stk-wasm:toolchain image after wasm/build.sh:
#
#   python wasm/scripts/fetch_assets.py <work>
#   docker run --rm -v "$PWD:/src" -v <work>:/work stk-wasm:toolchain sh wasm/package.sh
#
# fetch_assets.py downloads the files of wasm/assets.json: <work>/stk-assets.zip,
# the stk-assets-mobile release matching this code, and <work>/extra-assets/
# (same layout), assets that the code needs but are newer than that release,
# taken from the stk-assets SVN and copied over it.
# Output in <work>/web/:
#   supertuxkart.js, supertuxkart.wasm   the engine (from build-wasm/)
#   stk-data.js, stk-data.data           data/ + assets mounted at /stk/data
#   index.html, application.mjs          a standalone player (wasm/browser/)
set -eu

WORK=${WORK:-/work}
ASSETS_ZIP=${ASSETS_ZIP:-$WORK/stk-assets.zip}
OUT=${OUT:-$WORK/web}
STAGE=/tmp/stk-stage

rm -rf "$STAGE"
mkdir -p "$STAGE" "$OUT"
cp -r /src/data "$STAGE/data"
python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' \
    "$ASSETS_ZIP" "$STAGE/data"
EXTRA_ASSETS=${EXTRA_ASSETS:-$WORK/extra-assets}
if [ -d "$EXTRA_ASSETS" ]; then
    cp -r "$EXTRA_ASSETS"/. "$STAGE/data/"
fi
# Desktop-only files the game never reads in the browser.
rm -rf "$STAGE/data/supertuxkart.icns" "$STAGE/data/supertuxkart_"*.png \
       "$STAGE/data/supertuxkart.desktop" "$STAGE/data/net.supertuxkart.SuperTuxKart.metainfo.xml" \
       "$STAGE/data/SuperTuxKart-Info"*.plist "$STAGE/data/optimize_data.sh"

# --use-preload-cache keeps the package in IndexedDB, so later starts skip
# the download.
python3 /emsdk/upstream/emscripten/tools/file_packager.py "$OUT/stk-data.data" \
    --preload "$STAGE/data@/stk/data" \
    --js-output="$OUT/stk-data.js" \
    --use-preload-cache --no-node

cp /src/build-wasm/supertuxkart.js /src/build-wasm/supertuxkart.wasm "$OUT/"
cp /src/wasm/browser/index.html /src/wasm/browser/application.mjs "$OUT/"
ls -la "$OUT"
