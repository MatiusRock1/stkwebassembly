# Unified SuperTuxKart repository

Date: 2026-11-02. Working directory: `stkwebassembly/`.

## Current layout

The complete engine sources and browser adaptations live in this repository. `CMakeLists.txt`, `cmake/`, `lib/`, `src/`, `data/` and `wasm/` share the same root. Docker scripts still mount that root at `/src`; their commands no longer run from a sibling directory.

The source reference is the local `stk-wasm` tree, based on commit `356475121000f1fdf4c510598f87337bbf54896d`. Existing overlay-owned files matched their corresponding files in that tree. Changes to the game are incorporated directly in source files; historical patches are not reapplied before a build.

The upstream Git history, nested `.git` metadata, `build-wasm/` outputs and external asset downloads are not versioned. Existing local outputs are preserved during cleanup. The code's `data/` directory is required: it contains configuration, shaders, fonts and other build and runtime files. It is separate from the external kart, track and music package.

## Workflow

1. Edit and review changes directly in `stkwebassembly/`.
2. Run `python tools/assemble.py check` to verify the local source layout. This is a compatibility checker, not another assembly step.
3. Build, fetch external assets and package using the commands in the [README](../../README.md).
4. Run checks appropriate to the change. Record full builds and browser checks separately when they are actually performed.

An `export` step is no longer required to bring edits into the repository. `patches/` remains a historical reference; later source edits may make its contents outdated, and it is not a second source of truth.

## Preserved local changes

The official `stk-code/` clone remains intact, including its independent changes. Unique local files from `stk-wasm/` have been transferred here; conflicting versions and old metadata are retained under `.git/local-integration-backups/`. The old `stk-wasm/` path has been removed.

The audit found two modified files in `stk-code/` whose contents differ from the reference `stk-wasm/` tree:

- `src/graphics/sp/sp_base.cpp`
- `src/online/http_request_curl.cpp`

Those variants remain in `stk-code/` and are not merged automatically into the unified sources. Adopting them later requires a diff and checks; being in the official clone does not make them equivalent or newer.

## Assets and verification

`wasm/assets.json` still pins external downloads and SHA-256 hashes. `fetch_assets.py` and `package.sh` use an external work directory. Asset packages, external resources, downloaded dependencies and build outputs remain outside Git.

This note describes a source-tree migration. It does not claim a new full build, completed race or approved multiplayer session. Earlier results remain in [port.md](port.md), and new results must be recorded as new runs.

## Retiring the duplicate worktree

The old `stk-wasm` worktree is retired after its local files are transferred to this repository. The old path is removed; use `stkwebassembly` directly. Conflicting files and old metadata are backed up under `.git/local-integration-backups/`. The official `stk-code` clone and its independent changes remain untouched.
