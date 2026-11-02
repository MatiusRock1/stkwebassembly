"""Serve the packaged game on localhost, cross-origin isolated.

The engine uses threads, so the page needs SharedArrayBuffer: COOP/COEP on
every response, and localhost (or HTTPS). Adapted from Demo-Game's
RPG-Demo/web/serve.py.

  python wasm/scripts/serve.py <work>/web [--port 8092]
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class IsolatedHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      '.wasm': 'application/wasm', '.mjs': 'text/javascript', '.js': 'text/javascript',
                      '.data': 'application/octet-stream'}

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', type=Path, help='output directory of wasm/package.sh')
    parser.add_argument('--port', type=int, default=8092)
    args = parser.parse_args()
    directory = args.directory.resolve()
    handler = partial(IsolatedHandler, directory=str(directory))
    print(f'Serving {directory} on http://localhost:{args.port}/index.html', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), handler).serve_forever()


if __name__ == '__main__':
    main()
