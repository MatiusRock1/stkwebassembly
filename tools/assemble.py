#!/usr/bin/env python3
"""Verify the unified source tree; never create a second worktree or apply old patches."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = 'SuperTuxKart'
REQUIRED = ['BASE_COMMIT.txt', 'CMakeLists.txt', 'sources.cmake', 'src/main.cpp', 'src/online/http_request_emscripten.cpp', 'lib/irrlicht/CMakeLists.txt', 'data/stk_config.xml', 'wasm/build.sh']


def check_tree(root=ROOT):
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise SystemExit('Incomplete unified source tree: ' + ', '.join(missing))
    if not (root / 'BASE_COMMIT.txt').read_text(encoding='utf-8-sig').strip():
        raise SystemExit('BASE_COMMIT.txt must identify the original source revision.')
    print(f'{GAME}: engine sources and web layer are together in {root}')
    print('Source-tree check only; no compilation or runtime acceptance performed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='check', choices=['check', 'build', 'export'])
    args = parser.parse_args()
    check_tree()
    if args.command == 'build':
        print('The full source tree is already assembled. Run the build commands in README.md here.')
    elif args.command == 'export':
        print('Edit and review the engine and web files directly in this repository.')
        print('No export is needed. Historical patches are not regenerated or reapplied.')


if __name__ == '__main__':
    main()
