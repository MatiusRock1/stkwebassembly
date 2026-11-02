"""Browser check of the packaged game: start it and look for working frames.

Opens the player in the installed Chrome (Playwright), presses Start and waits.
It passes when the page is cross-origin isolated, the engine did not abort,
WebGL reported no invalid operation and the last capture of the game surface
is not a flat colour (a flat 1280x720 PNG compresses to a few KiB). Captures,
the engine log, the browser console and summary.json go to --out.

  python wasm/scripts/smoke.py [--url http://localhost:8092/index.html]
      [--args "--race-now --track=lighthouse"] [--wait 90] [--headed] [--out DIR]

Needs Playwright for Python and Chrome. Headless Chrome draws WebGL in
software, which is much slower: use --headed to check a race.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

FLAT_FRAME_BYTES = 32 * 1024
WEBGL_ERROR = re.compile(r'GL_INVALID|WebGL: INVALID')


def with_args(url, engine_args):
    if not engine_args:
        return url
    parts = urlsplit(url)
    query = parse_qsl(parts.query) + [('args', engine_args)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', default='http://localhost:8092/index.html')
    parser.add_argument('--args', default='', help='engine options passed with ?args=')
    parser.add_argument('--wait', type=int, default=90, help='seconds to run after Start')
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('smoke-evidence'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    console = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=not args.headed,
                                             args=['--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})
        page.on('console', lambda message: console.append(f'[{message.type}] {message.text}'))
        page.on('pageerror', lambda error: console.append(f'[pageerror] {error.stack or error}'))
        page.goto(with_args(args.url, args.args))
        isolated = page.evaluate('crossOriginIsolated')
        page.click('#start')
        start, shots, state = time.time(), [], {}
        while time.time() - start < args.wait:
            time.sleep(10)
            state = page.evaluate('''() => ({status: document.querySelector('#status').textContent,
                loading: document.querySelector('#loading').hidden ? null
                    : document.querySelector('#loading-text').textContent,
                result: window.applicationResult})''')
            print(int(time.time() - start), json.dumps(state), flush=True)
            if state['loading'] is None:
                shot = args.out / f'shot-{len(shots) + 1:02d}.png'
                page.locator('#game-surface').screenshot(path=str(shot))
                shots.append(shot)
            if state['result']:
                break
        (args.out / 'engine.log').write_text('\n'.join(page.evaluate('window.stkLog || []')), encoding='utf-8')
        (args.out / 'console.log').write_text('\n'.join(console), encoding='utf-8')
        browser.close()

    webgl_errors = [line for line in console if WEBGL_ERROR.search(line)]
    last_frame = shots[-1].stat().st_size if shots else 0
    checks = {
        'cross_origin_isolated': isolated,
        'engine_running': not state.get('result'),
        'no_webgl_errors': not webgl_errors,
        'frame_not_flat': last_frame > FLAT_FRAME_BYTES,
    }
    summary = {'url': with_args(args.url, args.args), 'checks': checks, 'last_frame_bytes': last_frame,
               'webgl_errors': sorted(set(webgl_errors))[:10], 'status': state.get('status')}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
