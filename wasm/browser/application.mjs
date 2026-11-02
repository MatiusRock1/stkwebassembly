// SuperTuxKart in the player: loads the Emscripten build (supertuxkart.js,
// .wasm) and its data package (stk-data.js, .data) from the engine directory
// into the shared player surface.
const canvas = document.querySelector('#canvas');
const status = document.querySelector('#status');
const loading = document.querySelector('#loading');
const loadingText = document.querySelector('#loading-text');
const surface = document.querySelector('#game-surface');
const startButton = document.querySelector('#start');
const fullscreenButton = document.querySelector('#fullscreen');
const closeButton = document.querySelector('#close');

const query = new URL(location.href).searchParams;
// ?engine= overrides the engine directory a deployment writes into the page.
const engineBase = new URL(query.get('engine') ||
  document.querySelector('meta[name="engine-base"]')?.content || './', location.href).href;
// The data package (stk-data.data) may live elsewhere, for example on a CDN
// that allows this site with CORS: <meta name="stk-data"> or ?data= names it.
const dataSetting = query.get('data') || document.querySelector('meta[name="stk-data"]')?.content;
const dataURL = dataSetting ? new URL(dataSetting, location.href).href : null;
// Network play: the game's sockets reach its server through a WebSocket relay
// (wasm/server/relay.py) named by <meta name="stk-net"> or ?net=. Emscripten
// opens ws://<address>:<port>/ for each destination; those connections go to
// <relay>/<address>/<port>, so the game's own LAN menu finds the server.
// ?online=1 joins it directly.
const netSetting = query.get('net') || document.querySelector('meta[name="stk-net"]')?.content;
const netURL = netSetting ? new URL(netSetting, location.href).href.replace(/^http/, 'ws') : null;
const online = netURL && query.get('online') === '1';
if (netURL) {
  const NativeWebSocket = window.WebSocket;
  const relay = netURL.replace(/\/?$/, '/');
  window.WebSocket = function (url, protocols) {
    const target = /^ws:\/\/([^/:]+):(\d+)\//.exec(url);
    return new NativeWebSocket(target ? `${relay}${target[1]}/${target[2]}` : url, protocols);
  };
  window.WebSocket.prototype = NativeWebSocket.prototype;
  for (const state of ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'])
    window.WebSocket[state] = NativeWebSocket[state];
}
// Player profiles, options and progress live here; kept in IndexedDB.
const CONFIG_DIR = '/home/web_user/.config';

// Recent engine output, for diagnosing a failed start from the console. It
// also goes to the console as it happens, which keeps the context of a freeze
// visible: fatal errors as errors, the engine's errors and warnings (mostly
// harmless, as on the desktop) as warnings, the rest at the Verbose level.
const log = [];
window.stkLog = log;
function record(line) {
  log.push(line);
  if (log.length > 2000) log.shift();
  if (/^\[fatal/.test(line)) console.error(line);
  else if (/^\[(error|warn)/.test(line)) console.warn(line);
  else console.debug(line);
}

function showLoading(message) { loading.hidden = false; loadingText.textContent = message; }

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${src}.`));
    document.body.append(script);
  });
}

function fail(message) {
  loading.hidden = true;
  status.textContent = `Game error: ${message}. Reload the page to try again.`;
  window.applicationResult = { error: message };
  fullscreenButton.disabled = true;
}

// Writes the config directory back to IndexedDB, one sync at a time.
let syncing = false;
function saveConfig(module) {
  if (syncing || !module.FS) return;
  syncing = true;
  module.FS.syncfs(false, error => {
    syncing = false;
    if (error) record(`Could not save settings: ${error}`);
  });
}

canvas.addEventListener('contextmenu', event => event.preventDefault());
// Touches go to the game (steering wheel and buttons), not to page scroll or zoom.
canvas.style.touchAction = 'none';
const touchScreen = navigator.maxTouchPoints > 0 && matchMedia('(pointer: coarse)').matches;
// Phones report 2.5-4 device pixels per CSS pixel and the engine sizes its
// canvas from devicePixelRatio; each pixel costs frame time, so cap it at 2.
if (touchScreen && devicePixelRatio > 2) {
  Object.defineProperty(window, 'devicePixelRatio', { value: 2, configurable: true });
}
// Safari's engine, WebKit, cannot run the game yet. It is Safari on a Mac and
// every browser on iPhone and iPad (Apple requires it there), so the player
// asks for Chrome or Firefox instead, before anything is downloaded.
if (/Apple/.test(navigator.vendor)) {
  const appleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent));
  const [title, text] = appleMobile
    ? ['Not available on iPhone or iPad yet.',
       'On iPhone and iPad every browser, Chrome and Firefox included, uses the Safari engine, which cannot run SuperTuxKart yet. Open this page on a computer or an Android phone with Chrome or Firefox.']
    : ['Open it in Chrome or Firefox.',
       'SuperTuxKart does not run in Safari yet. Open this page in Chrome or Firefox.'];
  const idle = surface.querySelector('.game-idle');
  const badge = idle?.querySelector('.badge');
  const heading = idle?.querySelector('h2');
  const paragraph = idle?.querySelector('p');
  if (badge) badge.textContent = 'Chrome or Firefox';
  if (heading) heading.textContent = title;
  if (paragraph) paragraph.textContent = text;
  startButton.disabled = true;
}
canvas.addEventListener('pointerdown', () => canvas.focus());
window.applicationResult = null;

startButton.addEventListener('click', async () => {
  startButton.disabled = true;
  // Phones race in landscape fullscreen; needs this click, so it goes first.
  if (touchScreen) {
    surface.requestFullscreen?.().then(() => screen.orientation?.lock?.('landscape')).catch(() => {});
  }
  surface.querySelector('.game-idle').hidden = true;
  showLoading('Preparing SuperTuxKart…');
  if (!window.crossOriginIsolated) {
    fail('this page is not cross-origin isolated (COOP/COEP headers), which WebAssembly threads need');
    return;
  }
  const module = window.Module = {
    canvas,
    // ?args= appends engine options, e.g. ?args=--race-now --track=lighthouse
    arguments: ['--screensize=1280x720', '--windowed', '--log=nocolor',
      ...(online ? ['--connect-now=10.0.0.1:2759'] : []),
      ...(query.get('args') || '').split(' ').filter(Boolean)],
    websocket: netURL ? { url: 'ws://', subprotocol: 'binary' } : {},
    locateFile: path => path === 'stk-data.data' && dataURL ? dataURL : new URL(path, engineBase).href,
    print: record,
    printErr: record,
    // The data package reports 'Downloading data... (loaded/total)'.
    setStatus: text => {
      const progress = /\((\d+)\/(\d+)\)/.exec(text);
      if (progress) {
        const [loaded, total] = [Number(progress[1]), Number(progress[2])].map(bytes => (bytes / 1048576).toFixed(0));
        showLoading(`Downloading game data: ${loaded} / ${total} MiB. Only the first start downloads it.`);
      } else if (text) {
        record(text);
      }
    },
    preRun: [() => {
      // Path on this site that forwards the official online services
      // (accounts, news, add-ons), which do not allow browsers themselves.
      const onlineProxy = document.querySelector('meta[name="stk-online"]')?.content;
      if (onlineProxy) module.ENV.STK_ONLINE_PROXY = onlineProxy;
      // The relay also starts the rooms that players create (GET rooms/create).
      if (netURL) module.ENV.STK_ROOMS_URL = netURL.replace(/^ws/, 'http').replace(/\/?$/, '/');
      const { FS } = module;
      FS.mkdirTree(CONFIG_DIR);
      FS.mount(FS.filesystems.IDBFS, {}, CONFIG_DIR);
      module.addRunDependency('stk-config');
      FS.syncfs(true, error => {
        if (error) record(`Could not restore settings: ${error}`);
        module.removeRunDependency('stk-config');
      });
    }],
    onRuntimeInitialized: () => {
      loading.hidden = true;
      status.textContent = 'SuperTuxKart running.';
      fullscreenButton.disabled = false;
      closeButton.disabled = false;
      canvas.focus();
      setInterval(() => saveConfig(module), 5000);
    },
    onAbort: reason => fail(String(reason)),
  };
  window.addEventListener('pagehide', () => saveConfig(module));
  try {
    // The data package registers its download in Module.preRun, so it loads
    // before the engine script.
    await loadScript(new URL('stk-data.js', engineBase).href);
    await loadScript(new URL('supertuxkart.js', engineBase).href);
  } catch (error) {
    fail(error.message);
  }
});

fullscreenButton.addEventListener('click', async () => {
  try {
    await surface.requestFullscreen();
    if (touchScreen) await screen.orientation?.lock?.('landscape').catch(() => {});
    canvas.focus();
  }
  catch (error) { status.textContent = `Could not enter fullscreen: ${error.message}`; }
});
// The engine cannot be restarted in place; save the settings and reload.
closeButton.addEventListener('click', () => {
  closeButton.disabled = true;
  status.textContent = 'Closing…';
  const module = window.Module;
  if (!module?.FS) { location.reload(); return; }
  module.FS.syncfs(false, () => location.reload());
});
