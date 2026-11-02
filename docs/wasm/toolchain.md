# Validated toolchain

Code: BASE_COMMIT 356475121000f1fdf4c510598f87337bbf54896d (stk-code master after 1.5.1,
`git describe`: preview-1240). Builds run in Docker on a Windows host; the build directory lives
in the `stk-wasm-build` volume.

| Component | Tested value |
| --- | --- |
| SDK image | emscripten/emsdk:4.0.10; digest 90b757eb11fa9a0e3ce4d2d9f76d932a56018e4accc37b5a28b2783751e60eb7 (same as the 0 A.D. port) |
| Emscripten | 4.0.10 (b7dc6e5747465580df5984e723b9d1f10d8e804b); wasm32-unknown-emscripten |
| Image OS | Ubuntu 22.04.5 LTS |
| CMake, Ninja | 3.22.1, 1.10.1 (Ubuntu packages) |
| Node, Python in the image | 22.16.0, 3.10.12 |
| Emscripten ports | SDL2 2.32.0, zlib 1.3.1, libpng 1.6.39, libjpeg 9f, FreeType 2.13.3, HarfBuzz 3.2.0, libogg and libvorbis (port tag version_1); pthread variants prebuilt in the image |
| MbedTLS | 3.6.2, static libmbedcrypto built in the image with -pthread |
| Game assets | stk-assets-mobile 1.5 and stk-assets SVN r18627, with SHA-256 in wasm/assets.json |

Compile flags added for every target: `-pthread -fexceptions` (JavaScript-based C++ exceptions)
and the `-sUSE_*` port flags. CMAKE_BUILD_TYPE is Release. The link flags are in
cmake/Emscripten.cmake: WebGL 2 only (`MIN_WEBGL_VERSION=2`, `MAX_WEBGL_VERSION=2`, `FULL_ES3`),
`GL_ENABLE_GET_PROC_ADDRESS` (glad loads the GL functions through SDL), memory growth from
512 MB up to 4 GB, an 8 MB main stack and 2 MB thread stacks, a pool of 16 workers, `FETCH`,
Emscripten's OpenAL, IDBFS, `FORCE_FILESYSTEM` and `--profiling-funcs`, which keeps the function
names so that browser stack traces name the C++ functions. em++ warns that pthreads with memory
growth may run JavaScript slowly; that is accepted.

Output: supertuxkart.wasm 15.0 MB (13.0 MB of it without the function names), supertuxkart.js
0.37 MB, data package 333 MB.
