#!/bin/sh
# Configures and builds SuperTuxKart for the browser. Runs inside the
# stk-wasm:toolchain image with the stk-code checkout mounted at /src:
#
#   docker build -t stk-wasm:toolchain wasm
#   docker run --rm -v "$PWD:/src" -v stk-wasm-build:/build stk-wasm:toolchain sh wasm/build.sh
#
# Object files stay in the stk-wasm-build volume (out of the synced folder);
# the output is copied to build-wasm/supertuxkart.{html,js,wasm}.
set -eu

BUILD_DIR=${BUILD_DIR:-/build}
OUT_DIR=${OUT_DIR:-/src/build-wasm}
BUILD_TYPE=${BUILD_TYPE:-Release}
JOBS=${JOBS:-$(nproc)}

emcmake cmake -S /src -B "$BUILD_DIR" -G Ninja \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    -DCHECK_ASSETS=OFF \
    -DUSE_GLES2=ON \
    -DNO_SHADERC=ON \
    -DBUILD_RECORDER=OFF \
    -DUSE_WIIUSE=OFF \
    -DUSE_SQLITE3=OFF \
    -DUSE_MOJOAL=OFF \
    -DUSE_DNS_C=OFF \
    -DUSE_SYSTEM_ENET=OFF \
    -DUSE_SYSTEM_MCPP=OFF \
    -DUSE_SYSTEM_SQUISH=OFF \
    -DUSE_SYSTEM_ANGELSCRIPT=OFF \
    -DUSE_CRYPTO_OPENSSL=OFF \
    -DMBEDTLS_INCLUDE_DIRS=/opt/stk-deps/include \
    -DMBEDCRYPTO_LIBRARY=/opt/stk-deps/lib/libmbedcrypto.a

cmake --build "$BUILD_DIR" -j "$JOBS"
mkdir -p "$OUT_DIR"
cp "$BUILD_DIR"/bin/supertuxkart.* "$OUT_DIR"/
ls -la "$OUT_DIR"
