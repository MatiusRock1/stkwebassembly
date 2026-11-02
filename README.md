# SuperTuxKart WebAssembly

The [SuperTuxKart](https://supertuxkart.net) engine sources and browser port live in **one repository**, using Emscripten and WebGL 2. Build and edit directly in `stkwebassembly/`; a separate `stk-wasm` tree and an export step are no longer required.

The original base is recorded in `BASE_COMMIT.txt`: `356475121000f1fdf4c510598f87337bbf54896d`. Browser adaptations are already incorporated into the source files.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/`, `lib/` | Game sources, bundled libraries and browser adaptations |
| `CMakeLists.txt`, `cmake/` | Native and Emscripten build configuration |
| `data/` | Data shipped with the code: configuration, shaders, fonts and other required files |
| `wasm/` | Docker toolchain, build scripts, packaging, browser player and checks |
| `wasm/assets.json` | External asset sources and SHA-256 hashes |
| `docs/wasm/` | Port documentation, results and the [unified repository migration](docs/wasm/unified-repository.md) |
| `patches/` | Historical record of the former overlay; not applied before building |
| `tools/assemble.py` | Compatibility check of the local source tree; no separate worktree is created |

Large external assets such as karts, tracks, music and textures are downloaded into a work directory outside the repository. Build outputs, downloaded dependencies and packaged data also stay out of Git.

## Build, package and check

Requirements: Docker and Python 3. Run these commands from **this repository's root**. `<work>` is an external work directory, for example `C:/stk-web-work`. In PowerShell, use `${PWD}` instead of `$PWD`.

```text
python tools/assemble.py check

docker build -t stk-wasm:toolchain wasm

docker run --rm -v "$PWD:/src" -v stk-wasm-build:/build stk-wasm:toolchain sh wasm/build.sh
python wasm/scripts/fetch_assets.py <work>
docker run --rm -v "$PWD:/src" -v <work>:/work stk-wasm:toolchain sh wasm/package.sh
python wasm/scripts/serve.py <work>/web
```

1. Build the toolchain image: Emscripten 4.0.10, its ports and MbedTLS.
2. Compile in the `stk-wasm-build` volume, outside the source folder. Local ignored outputs are placed in `build-wasm/supertuxkart.{html,js,wasm}`.
3. Download and verify the assets listed in `wasm/assets.json` into `<work>` (about 230 MB).
4. Assemble `<work>/web/`: the engine, packaged data (about 330 MB) and browser player.
5. Serve it at <http://localhost:8092/index.html> with the headers required by WebAssembly threads.

Automated browser check, with Playwright for Python and Chrome:

```text
python wasm/scripts/smoke.py --headed
python wasm/scripts/smoke.py --headed --args "--race-now --track=lighthouse"
```

This source-tree migration does not establish that a new build or race has passed. Recorded functional results and limitations remain in [docs/wasm/port.md](docs/wasm/port.md).

## Editing the game and port

Edit `src/`, `lib/`, `cmake/`, `data/` or `wasm/` directly and review changes with `git diff` here. Running `assemble.py build` or `assemble.py export` to move edits between directories is no longer necessary.

`patches/` records the former overlay. Do not reapply those patches to the current tree: their changes are already present. Updating upstream requires reviewing and testing changes to the game, port and assets pinned in `wasm/assets.json`; changing only `BASE_COMMIT.txt` does not update the sources.

The official `stk-code` clone remains intact. The old `stk-wasm` path is now a compatibility junction to this repository, without a duplicate source tree. The [migration note](docs/wasm/unified-repository.md) identifies two divergent changes in `stk-code` that were not merged automatically.

## Deployment and multiplayer

To deploy the web package, copy `<work>/web/` to your web server; Demos-Games serves it under `/playstk/`. Every response must include `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`.

`wasm/server/Dockerfile` builds the native server and its WebSocket-to-UDP relay. Run it from this repository's root with the external downloaded assets:

```text
docker buildx build -f wasm/server/Dockerfile --build-context work=<work> -t stk-server .
docker run -p 8081:8081 -p 2759:2759/udp stk-server
```

The player accepts the `net` query parameter for the relay URL and `online=1`, or the online-play button when the page includes `<meta name="stk-net">`. A relay implementation does not prove that an online match has been validated; see [port.md](docs/wasm/port.md) for results and limitations.

## License and attribution

SuperTuxKart is free software developed by the [SuperTuxKart team](https://supertuxkart.net) and its contributors. This repository preserves their sources and attribution and does not claim ownership of the original project.

The code is licensed under GNU GPL version 3 or later (see [COPYING](COPYING)); modifications retain that license. Game assets use several licenses, including GPL, CC BY, CC BY-SA and public domain: consult each resource's `licenses.txt`. Data shipped with the code retains its original licenses; `wasm/scripts/fetch_assets.py` downloads external assets from the documented sources.

This port is independent and is not affiliated with or endorsed by the SuperTuxKart team. Credit for the original game belongs to its team and contributors.
