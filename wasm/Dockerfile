# Toolchain for the SuperTuxKart WebAssembly build.
# Same Emscripten release as the 0 A.D. port (see 0adwebassembly lock file).
FROM emscripten/emsdk:4.0.10

RUN apt-get update \
    && apt-get install -y --no-install-recommends cmake ninja-build git pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Emscripten ports used by STK, prebuilt (pthread variants where they exist)
# so the game build does not rebuild them every time.
RUN embuilder build sdl2-mt zlib libpng-mt libjpeg freetype harfbuzz-mt ogg vorbis

# MbedTLS replaces OpenSSL for STK's network crypto (AES-GCM, SHA256, base64).
ARG MBEDTLS_TAG=v3.6.2
RUN git clone --depth 1 --branch ${MBEDTLS_TAG} --recurse-submodules \
        https://github.com/Mbed-TLS/mbedtls.git /tmp/mbedtls \
    && emcmake cmake -S /tmp/mbedtls -B /tmp/mbedtls/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_FLAGS="-pthread" \
        -DCMAKE_INSTALL_PREFIX=/opt/stk-deps \
        -DENABLE_PROGRAMS=OFF -DENABLE_TESTING=OFF -DMBEDTLS_FATAL_WARNINGS=OFF \
        -DUSE_SHARED_MBEDTLS_LIBRARY=OFF \
    && cmake --build /tmp/mbedtls/build \
    && cmake --install /tmp/mbedtls/build \
    && rm -rf /tmp/mbedtls

WORKDIR /src
