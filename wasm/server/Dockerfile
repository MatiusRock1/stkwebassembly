# Native SuperTuxKart server for browser multiplayer, with its WebSocket relay.
# Build from the assembled tree, with the work directory of fetch_assets.py:
#
#   docker buildx build -f wasm/server/Dockerfile --build-context work=<work> -t stk-server .
#
# Ports: 8081/tcp WebSocket for browsers, 2759/udp for desktop clients.
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build pkg-config python3 \
        libcurl4-openssl-dev libssl-dev zlib1g-dev libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*
# Only the game sources, so changes to the relay or the browser files do not
# recompile the server.
COPY CMakeLists.txt sources.cmake /src/
COPY cmake /src/cmake
COPY lib /src/lib
COPY src /src/src
COPY data /src/data
RUN cmake -S /src -B /build -G Ninja -DCMAKE_BUILD_TYPE=Release -DSERVER_ONLY=ON \
        -DCHECK_ASSETS=OFF -DUSE_WIIUSE=OFF -DUSE_SYSTEM_ENET=OFF -DUSE_SYSTEM_MCPP=OFF \
        -DUSE_SYSTEM_ANGELSCRIPT=OFF \
    && cmake --build /build
# Game data: the code's data/ plus the same assets as the browser package.
RUN --mount=type=bind,from=work,target=/work \
    mkdir -p /stk/data && cp -r /src/data/. /stk/data/ \
    && python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' \
        /work/stk-assets.zip /stk/data \
    && cp -r /work/extra-assets/. /stk/data/

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcurl4t64 libssl3t64 libsqlite3-0 zlib1g python3 python3-websockets ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /build/bin/supertuxkart /usr/local/bin/supertuxkart
COPY --from=build /stk /stk
COPY wasm/server/relay.py /opt/stk/relay.py
COPY --chmod=755 wasm/server/entrypoint.sh /opt/stk/entrypoint.sh
ENV SUPERTUXKART_DATADIR=/stk HOME=/config
RUN useradd --system --home-dir /config stk && mkdir -p /config/rooms && chown -R stk /config
USER stk
EXPOSE 8081/tcp 2759/udp
ENTRYPOINT ["/opt/stk/entrypoint.sh"]
