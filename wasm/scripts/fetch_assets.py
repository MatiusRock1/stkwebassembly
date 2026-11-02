"""Download the game assets that wasm/package.sh needs into a work directory.

Each file of wasm/assets.json is downloaded only when it is missing or its
SHA-256 differs, and is checked before it replaces anything.

  python wasm/scripts/fetch_assets.py <work>
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / 'assets.json'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def download(url, target, expected):
    partial = target.with_name(target.name + '.part')
    digest = hashlib.sha256()
    with urllib.request.urlopen(url) as response, partial.open('wb') as stream:
        for block in iter(lambda: response.read(1 << 20), b''):
            digest.update(block)
            stream.write(block)
    if digest.hexdigest() != expected:
        partial.unlink()
        sys.exit(f'{url}: SHA-256 {digest.hexdigest()}, expected {expected}.')
    partial.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('work', type=Path, help='work directory mounted at /work by wasm/package.sh')
    args = parser.parse_args()
    for name, entry in json.loads(LOCK.read_text(encoding='utf-8')).items():
        target = args.work / name
        if target.is_file() and sha256(target) == entry['sha256']:
            print(f'ok          {name}')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f'downloading {name}', flush=True)
        download(entry['url'], target, entry['sha256'])
        print(f'ok          {name}')


if __name__ == '__main__':
    main()
