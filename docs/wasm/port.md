# SuperTuxKart in the browser

How the WebAssembly layer changes SuperTuxKart (stk-code) and what the browser runtime expects.
Versions are in toolchain.md; build and test commands in the README of the layer.

## Status

2026-10-30, Chrome on Windows:

- The layer builds from BASE_COMMIT: a full build of the assembled tree in Docker, with no errors.
- The game downloads its data and shows the first-start user screen, the login screen and the
  main menu.
- Entering a race with the deferred renderer failed: WebGL refused the draws with "Feedback loop
  formed between Framebuffer and active Texture". With the forward renderer (data.patch) the
  engine then trapped with "function signature mismatch" in the fence wait of DrawCalls, fixed in
  src-graphics.patch. With both fixes a race loads and runs (tested by hand). Not verified yet: a
  full race against AI karts, the font fix (lib-graphics_engine.patch), audio, gamepads, Firefox
  and Safari.
- The first frame on a track whose textures were still loading froze the page for good, with no
  console error (a deadlock, see src-graphics.patch). After the fix, a `--race-now` race on
  lighthouse with 6 karts runs in a fresh browser profile (headless Chrome on the GPU).
- Online play is not expected to work (see below).

## Changes to stk-code (patches/)

| Patch | Files | Change |
| --- | --- | --- |
| root.patch | CMakeLists.txt | Includes cmake/Emscripten.cmake; skips pkg-config, libresolv, Gamerzilla and curl for Emscripten; link flags and `.html` output for the game target. |
| cmake.patch | cmake/FindFreetype.cmake, cmake/FindOggVorbis.cmake | Use the Emscripten ports instead of pkg-config. |
| src.patch | src/main_loop.cpp, .hpp | The body of the main loop becomes `MainLoop::runFrame()`. The browser cannot block in a loop, so `emscripten_set_main_loop_arg` calls it once per animation frame; desktop builds keep the loop. The body keeps its indentation so the patch stays small. |
| src-online.patch | src/online/http_request.hpp, http_request_curl.cpp | Leaves out the curl backend; src/online/http_request_emscripten.cpp replaces it. |
| src-network.patch | src/network/network_config.cpp, protocols/connect_to_server.cpp | No DNS SRV/TXT lookups: browsers cannot make them. |
| lib-irrlicht.patch | lib/irrlicht/source/Irrlicht/CIrrDeviceSDL.cpp | Wraps `glMapBufferRange` to drop `GL_MAP_UNSYNCHRONIZED_BIT`. Emscripten emulates mapping with a copy at unmap and rejected the flag, so mesh, particle and skinning uploads failed. |
| src-graphics.patch | src/graphics/sp/sp_base.cpp, sp_texture_manager.cpp, graphics_restrictions.cpp, draw_calls.hpp | Sleeps 1 ms when a GL command still waits for its textures before a scene: in the browser the texture loading threads read files through the main thread, and the retry loop never let it serve them, so the first frame on a new track deadlocked. Binds the Matrices and LightingData uniform buffers at start: every shader includes header.txt, and WebGL refuses draws with a used uniform block that has no buffer (the GUI was a flat colour). Adds the `web` OS to graphical_restrictions.xml rules. Creates no fence for the instance data: WebGL copies buffer data on upload and signals syncs only between frames, and Emscripten's proc address for `glClientWaitSync` takes the 64-bit timeout as two 32-bit halves, so the call through glad trapped with "function signature mismatch". |
| data.patch | data/graphical_restrictions.xml | `os="web"` disables AdvancedPipeline. The deferred renderer samples the depth texture while it is attached to the bound framebuffer; WebGL refuses those draws as a feedback loop. The forward renderer has none. |
| lib-graphics_engine.patch | lib/graphics_engine/src/ge_gl_texture.cpp | No texture swizzle for single-channel font textures: WebGL 2 lacks it (`texParameter: INVALID_ENUM`, and titles were red glyphs on black boxes). They use RGBA textures instead. |

Own files of the layer:

- cmake/Emscripten.cmake: port flags, pre-seeded results for the `find_*` calls, link flags, data
  directory `/stk`.
- src/online/http_request_emscripten.cpp: HTTP with a synchronous `emscripten_fetch`, run from the
  request manager thread and the other worker threads that already make requests. The browser
  handles TLS, redirects and the user agent. A transfer reports no progress and cannot be
  cancelled while it runs, and CORS applies.
- wasm/: Dockerfile, build.sh, package.sh, assets.json, browser/ (standalone player) and scripts/
  (fetch_assets.py, serve.py, smoke.py).

## Runtime

- Data: wasm/package.sh packs data/ plus the assets with Emscripten's file packager; the package is
  preloaded into memory at `/stk/data` (`SUPERTUXKART_DATADIR=/stk`) and kept in IndexedDB by the
  packager, so later starts skip the download.
- Settings, player profiles and progress: `/home/web_user/.config`, an IDBFS mount made by the
  player, saved every 5 seconds, on page hide and on Close.
- Threads: the build uses pthreads, so the page needs SharedArrayBuffer: every response must carry
  `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`.
- Player: wasm/browser/application.mjs loads stk-data.js, then supertuxkart.js (a plain script with a
  global `Module`). Engine options: `--screensize=1280x720 --windowed --log=nocolor`, plus the
  ones in `?args=` (for example `?args=--race-now --track=lighthouse`). The engine directory comes
  from `<meta name="engine-base">` or `?engine=`, next to the page by default. The engine output
  goes to `window.stkLog` and to the browser console (info lines at the Verbose level), which keeps
  the context of a freeze visible. The Demo-Games player (Demo-Game/website/dist/playstk/) uses a
  copy of application.mjs, with the engine files served from the same `/playstk/` directory, as
  the 0 A.D. engine is in `/play/`.
- Graphics: WebGL 2 with the forward renderer; Options shows dynamic lighting as unavailable.

## Multiplayer

Browsers cannot open UDP sockets, so network races go through a relay. Emscripten
emulates each game socket with WebSockets: with `Module.websocket.url = 'ws://'` it opens
`ws://<address>:<port>/` per destination and sends one binary message per datagram, after a
10-byte port announcement. The player rewrites those URLs to `<relay>/<address>/<port>`, and
wasm/server/relay.py sends them by UDP to its own server, only to the game port (2759) or
the LAN discovery port (2757). The game's own Online > LAN menu therefore lists the server
(its broadcast reaches the relay) and joins it, with the player's profile name.

- wasm/server/Dockerfile builds the server (`SERVER_ONLY`) from the game sources and data,
  plus the relay: 8081/tcp WebSocket for browsers, 2759/udp for desktop clients
  (variables STK_SERVER_NAME, STK_SERVER_PORT, STK_RELAY_PORT).
- The player takes the relay URL from `<meta name="stk-net">` or `?net=`; `?online=1`
  joins directly with `--connect-now`.
- 2026-10-31: the discovery answer (name, players, port) and a browser joining the lobby
  through the relay were verified. A race between several browsers is not verified yet.
- Rooms: a browser cannot host a server, so the create server screen (src/states_screens/
  online/create_server_screen.cpp) asks the relay, GET `<relay>/rooms/create`, which starts a LAN
  server process on a free port (STK_MAX_ROOMS, default 5) and stops it after STK_ROOM_IDLE
  seconds empty (default 300). The relay answers LAN discovery for every room. 2026-10-31: a room
  was created, listed by discovery next to the main server, and joined by a browser.
- Official online services (accounts, news, add-ons) work through the site path in
  `<meta name="stk-online">` (STK_ONLINE_PROXY), which the Demo-Games image forwards; joining
  the official public servers does not, as it needs an open relay.
- Not available: the official online services (accounts, global server list), which do not
  allow browsers (CORS), and hosting a server from the browser.

## Assets

BASE_COMMIT is newer than the latest asset release, so wasm/assets.json takes the stk-assets-mobile
1.5 package and adds the files that the code loads but that release lacks, from the stk-assets SVN
(today only textures/stk_noise_simplex.png, used by the speed streaks). After moving BASE_COMMIT,
a missing asset shows in the engine log as `[fatal ] ... Failed to load`; add it to assets.json
with its SVN revision and SHA-256.

## Known limitations and pending work

- Verify a full race, audio and gamepads with the forward renderer.
- The kartDirt shader fails to load ("kartDirt shader is missing, fallback to solid"); check its
  compile log in WebGL.
- Startup and track loading run inside one browser frame: the page does not respond for several
  seconds and the loading screen does not animate.
- Online play: STK servers use ENet over UDP, which browsers cannot open; HTTP to the STK online
  services (news, add-ons, accounts) also needs CORS from those servers.
- The first start downloads 333 MB in one package; the low-quality assets (106 MB) or a package
  per track would shorten it.
- The Vulkan code is compiled but never used; leaving it out would shrink the binary.
- The Demo-Games image for CasaOS (arm64) does not include the `/playstk` engine files yet.

## Phones and tablets

Tested in Chrome on an Android Studio emulator (AVD `Medium_Phone_API_37.0`, `adb reverse tcp:8091 tcp:8091`, then http://localhost:8091/playstk/, so the page stays a secure context for threads) and on the user's phone through the Demo-Games image.

- Touch controls, `src/main.cpp` after `loadConfig`: on a coarse touch pointer, STK's own multitouch race GUI is enabled (`m_multitouch_active = 2`, `m_multitouch_draw_gui`, steering wheel). `RaceGUIMultitouch` is created with the race GUI, so the steering wheel and buttons appear only while racing. They reach the player through kart selection; `--race-now` never assigns them, so test touch through the menus. Desktop browsers set `m_multitouch_active = 0`.
- Text boxes: browsers open no system keyboard for the canvas, so touch screens set `m_screen_keyboard = 1` (STK's own on-screen keyboard).
- Memory: touch screens cap textures like Android (256, no HD textures, no light scatter); `cmake/Emscripten.cmake` starts the heap at 256MB (was 512MB) and grows it on demand. The first emulator runs had Chrome killed for memory.
- `shared_gpu_objects.cpp`, `sp/sp_base.cpp`: the matrices UBO is allocated as 16*9+4 floats. std140 rounds the block to 592 bytes; mobile GLES rejects 584 ("buffer range at index 0 not large enough") and nothing is drawn.
- Sound: Emscripten's OpenAL lives on the main thread and every AL call from another thread waits for it, so STK's sfx thread fell behind (music source stopped, sfx throttled, choppy sound on phones). `audio/sfx_manager.cpp`: no sfx thread under Emscripten; `update()` runs the queued commands on the main thread once per frame (like the Switch path, without its 1 ms sleep and update re-queue). `audio/music_ogg.*`: 4 music buffers of 0.25 s under Emscripten (was 2), one second queued without decoding long blocks in one frame. `cmake/emscripten_audio_post.js` (`--post-js`): `AL.QUEUE_LOOKAHEAD = 0.5` (was 0.1), since Web Audio is fed from a main-thread timer that slow frames delay. The 5 "Throttling sfx" warnings while a race loads are harmless: only position/speed updates are dropped, and loop flags are applied when a source is created.
- Lag, the main cause: `graphics/2dutils.cpp` called `glGetError()` after every 2D draw (HUD images, energy meter, kart icons, touch buttons) and discarded the result. WebGL's getError waits for the GPU process: a race profile in desktop Chrome spent 24% of the main thread in it (60% of its busy time), and phones pay far more per call. `clearGLError()` skips it under Emscripten; the same profile then went from 60% to 83% idle at 60 fps. Profile with `--race-now` and the Profiler domain of the DevTools protocol; function names are kept (`--profiling-funcs`).
- Lag, canvas size: `main.cpp` does not set the 480x480 minimum window size under Emscripten. Window units are CSS pixels there and a landscape phone is about 400 high, so the canvas was forced taller than the page and the picture squashed. `m_scale_rtts_factor` (render scale) does nothing here: it only applies to the deferred renderer, which the web build disables; resolution is set by the canvas, so the player caps `devicePixelRatio` at 2 on touch screens.
- Safari: WebKit (Safari on a Mac, and every browser on iPhone and iPad, where Apple requires it) cannot run the game yet. The player detects it with `navigator.vendor` and replaces Start with a notice asking for Chrome or Firefox (on iPhone/iPad: a computer or an Android phone); its Spanish strings are in Demo-Games `translations.tsv`.
- Player, `wasm/browser/application.mjs` (copied to Demo-Games `dist/playstk/`): `touch-action: none` on the canvas; on touch screens `devicePixelRatio` is capped at 2 before the engine sizes its canvas, and Start enters fullscreen and locks landscape; the WebKit notice above.
- Gamepads: `input/gamepad_config.cpp` binds accelerate/brake to the right/left triggers when the pad's SDL mapping has them (were Y/X; fire B, nitro LB, skid RB, look back A, rescue Back, pause Start unchanged). `input/sdl_controller.cpp`: a saved config still on the old Y/X defaults switches once to the trigger layout; customised layouts are kept. The player's help text lists the layout.
