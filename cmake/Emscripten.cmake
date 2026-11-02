# Settings for building SuperTuxKart with Emscripten (WebAssembly + WebGL 2).
# Included from the root CMakeLists.txt when EMSCRIPTEN is set; see wasm/README.md.

# Emscripten ports provide the libraries a desktop build finds on the system.
# Passing the -sUSE_* flags at compile time makes the port headers available,
# passing them at link time links the (pthread) port libraries.
set(STK_EMSCRIPTEN_PORTS
    -sUSE_SDL=2 -sUSE_ZLIB=1 -sUSE_LIBPNG=1 -sUSE_LIBJPEG=1
    -sUSE_FREETYPE=1 -sUSE_HARFBUZZ=1 -sUSE_OGG=1 -sUSE_VORBIS=1)
string(REPLACE ";" " " STK_EMSCRIPTEN_PORTS_STR "${STK_EMSCRIPTEN_PORTS}")

set(CMAKE_C_FLAGS   "${CMAKE_C_FLAGS} -pthread -fexceptions ${STK_EMSCRIPTEN_PORTS_STR}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -fexceptions ${STK_EMSCRIPTEN_PORTS_STR}")

if(NOT EMSCRIPTEN_SYSROOT)
    execute_process(COMMAND em-config CACHE OUTPUT_VARIABLE EM_CACHE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE)
    set(EMSCRIPTEN_SYSROOT "${EM_CACHE_DIR}/sysroot")
endif()
set(EM_INCLUDE "${EMSCRIPTEN_SYSROOT}/include")

# Pre-seed the find_* results: the port libraries are linked through the
# -sUSE_* flags above, so the "library" is that flag.
set(SDL2_LIBRARY "-sUSE_SDL=2" CACHE STRING "" FORCE)
set(SDL2_INCLUDEDIR "${EM_INCLUDE}/SDL2" CACHE PATH "" FORCE)
set(ZLIB_LIBRARY "-sUSE_ZLIB=1" CACHE STRING "" FORCE)
set(ZLIB_INCLUDE_DIR "${EM_INCLUDE}" CACHE PATH "" FORCE)
set(PNG_LIBRARY "-sUSE_LIBPNG=1" CACHE STRING "" FORCE)
set(PNG_PNG_INCLUDE_DIR "${EM_INCLUDE}" CACHE PATH "" FORCE)
set(JPEG_LIBRARY "-sUSE_LIBJPEG=1" CACHE STRING "" FORCE)
set(JPEG_INCLUDE_DIR "${EM_INCLUDE}" CACHE PATH "" FORCE)
set(FREETYPE_LIBRARY "-sUSE_FREETYPE=1" CACHE STRING "" FORCE)
set(FREETYPE_LIBRARY_RELEASE "-sUSE_FREETYPE=1" CACHE STRING "" FORCE)
set(FREETYPE_INCLUDE_DIR_ft2build "${EM_INCLUDE}/freetype2" CACHE PATH "" FORCE)
set(FREETYPE_INCLUDE_DIR_freetype2 "${EM_INCLUDE}/freetype2" CACHE PATH "" FORCE)
set(HARFBUZZ_LIBRARY "-sUSE_HARFBUZZ=1" CACHE STRING "" FORCE)
set(HARFBUZZ_INCLUDEDIR "${EM_INCLUDE}/harfbuzz" CACHE PATH "" FORCE)
set(OGGVORBIS_OGG_INCLUDE_DIR "${EM_INCLUDE}" CACHE PATH "" FORCE)
set(OGGVORBIS_VORBIS_INCLUDE_DIR "${EM_INCLUDE}" CACHE PATH "" FORCE)
set(OGGVORBIS_OGG_LIBRARY "-sUSE_OGG=1" CACHE STRING "" FORCE)
set(OGGVORBIS_VORBIS_LIBRARY "-sUSE_VORBIS=1" CACHE STRING "" FORCE)
set(OGGVORBIS_VORBISFILE_LIBRARY "-sUSE_VORBIS=1" CACHE STRING "" FORCE)
set(OGGVORBIS_VORBISENC_LIBRARY "-sUSE_VORBIS=1" CACHE STRING "" FORCE)
# Emscripten ships its own OpenAL on top of Web Audio.
set(OPENAL_LIBRARY "-lopenal" CACHE STRING "" FORCE)
set(OPENAL_INCLUDE_DIR "${EM_INCLUDE}" CACHE PATH "" FORCE)

# Game data is mounted at /stk/data in the virtual file system.
set(STK_INSTALL_DATA_DIR_ABSOLUTE "/stk" CACHE PATH "" FORCE)

set(STK_EMSCRIPTEN_LINK_FLAGS
    ${STK_EMSCRIPTEN_PORTS}
    -pthread
    -fexceptions
    -lopenal
    -sFETCH=1
    -sMIN_WEBGL_VERSION=2
    -sMAX_WEBGL_VERSION=2
    -sFULL_ES3=1
    -sGL_ENABLE_GET_PROC_ADDRESS=1
    -sALLOW_MEMORY_GROWTH=1
    # Phones kill the tab early with a large reservation; the heap grows on demand
    -sINITIAL_MEMORY=256MB
    -sMAXIMUM_MEMORY=4GB
    -sSTACK_SIZE=8MB
    -sDEFAULT_PTHREAD_STACK_SIZE=2MB
    -sPTHREAD_POOL_SIZE=16
    -sFORCE_FILESYSTEM=1
    -lidbfs.js
    -sENVIRONMENT=web,worker
    # Keeps function names, so browser stack traces are readable (about 2 MB)
    --profiling-funcs
    --post-js ${CMAKE_CURRENT_LIST_DIR}/emscripten_audio_post.js
    # The player mounts IDBFS for the settings and loads the data package
    # (stk-data.js from wasm/package.sh) through these.
    -sEXPORTED_RUNTIME_METHODS=FS,ENV,addRunDependency,removeRunDependency,FS_createPath,FS_createDataFile,FS_createPreloadedFile)
