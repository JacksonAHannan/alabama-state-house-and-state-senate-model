#!/usr/bin/env node
/**
 * Browser checks for the public Southern WAR explorer (internal checklist southern-12).
 *
 * What it does
 *   1. Serves `docs/` over a local HTTP server (Node `http`, no dependencies) because the
 *      page fetches `data/southern_war_map_payload.json`.
 *   2. Opens `southern-war.html` in headless Chromium at 1258x900 and 390x844.
 *   3. Fails on console errors, uncaught page errors, and failed or HTTP >= 400 requests.
 *   4. Injects and evaluates `scripts/tests/southern_war_browser_checks.js` (all 116 slices).
 *   5. Verifies keyboard reachability (Tab order) of the state/cycle/chamber selects and the
 *      district picker, the empty-slice explanation for VA-2017-lower, and the absence of
 *      horizontal page overflow (required at 390px; also asserted at 1258px).
 *   6. Saves screenshots when `--screenshot-dir <dir>` is given, prints one JSON result object
 *      and exits 1 on any failure.
 *
 * Browser driver resolution (no dependency is added to the repository)
 *   a. `playwright` or `playwright-core` importable from the global npm root (`npm root -g`),
 *      including agent-browser's nested node_modules.
 *   b. `playwright` or `playwright-core` in npm's npx cache (`npm config get cache`/_npx/...),
 *      preferring stable over pre-release versions. On the authoring machine (2026-09-08) the
 *      global root holds only `agent-browser` with no nested Playwright, so this rung was the
 *      one used: `npx playwright` 1.63.0 lives in the npx cache. Its pinned Chromium revision
 *      (1243) is not installed, so when the default launch reports a missing executable the
 *      harness retries with `executablePath` set to the newest Chromium already present in the
 *      ms-playwright browser cache (`chromium-1234`, installed by agent-browser); the JSON
 *      result records the executable actually used.
 *   c. The globally installed `agent-browser` CLI driven through child processes
 *      (`open`, `set viewport`, `eval -b`, `press`, `screenshot`, `console --json`,
 *      `errors --json`, `close`). This rung follows the CLI's documented surface; it could not
 *      be exercised on the authoring machine because the CLI hung (even `doctor`) when invoked
 *      from the non-interactive shell, so its output parsing is deliberately lenient and each
 *      CLI call is capped at two minutes.
 *   Force a rung with `--driver playwright|agent-browser`.
 *
 * Usage
 *   node scripts/run_southern_war_browser_checks.mjs [--docs <dir>] [--screenshot-dir <dir>]
 *                                                    [--driver playwright|agent-browser] [--headed]
 */
import { spawnSync } from 'node:child_process';
import { createReadStream, existsSync, promises as fs, readdirSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const CHECKS_FILE = path.join(HERE, 'tests', 'southern_war_browser_checks.js');
const PAGE = 'southern-war.html';
const VIEWPORTS = [{ width: 1258, height: 900 }, { width: 390, height: 844 }];
const WANTED_TAB_ORDER = ['state', 'cycle', 'chamber', 'district'];
const MIME = {
  '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.csv': 'text/csv; charset=utf-8',
  '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
};

function parseArgs(argv) {
  const options = { docs: path.join(ROOT, 'docs'), screenshotDir: null, driver: null, headed: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--docs') options.docs = path.resolve(argv[++i]);
    else if (arg === '--screenshot-dir') options.screenshotDir = path.resolve(argv[++i]);
    else if (arg === '--driver') options.driver = argv[++i];
    else if (arg === '--headed') options.headed = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (options.driver && !['playwright', 'agent-browser'].includes(options.driver)) {
    throw new Error(`--driver must be playwright or agent-browser, got ${options.driver}`);
  }
  return options;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------------------
// Static server for docs/
// ---------------------------------------------------------------------------
async function serveDocs(root) {
  const base = path.resolve(root);
  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://127.0.0.1');
      let pathname = decodeURIComponent(url.pathname);
      if (pathname === '/favicon.ico') { response.writeHead(204); response.end(); return; }
      if (pathname.endsWith('/')) pathname += 'index.html';
      const file = path.resolve(base, `.${pathname}`);
      if (file !== base && !file.startsWith(base + path.sep)) { response.writeHead(403); response.end('forbidden'); return; }
      const stat = await fs.stat(file).catch(() => null);
      if (!stat || !stat.isFile()) { response.writeHead(404, { 'content-type': 'text/plain' }); response.end('not found'); return; }
      response.writeHead(200, {
        'content-type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
        'content-length': stat.size,
        'cache-control': 'no-store',
      });
      createReadStream(file).pipe(response);
    } catch (error) {
      response.writeHead(500, { 'content-type': 'text/plain' });
      response.end(String(error));
    }
  });
  await new Promise((resolve, reject) => server.listen(0, '127.0.0.1', resolve).on('error', reject));
  return { server, origin: `http://127.0.0.1:${server.address().port}` };
}

// ---------------------------------------------------------------------------
// Driver resolution
// ---------------------------------------------------------------------------
// Shell out with one command string: `.cmd` shims on Windows need a shell, and Node 24 warns
// when an args array is combined with `shell: true`.
const shellQuote = (value) => (/[\s"&|<>^()]/.test(value) ? `"${String(value).replace(/"/g, '\\"')}"` : String(value));
function shell(command, args, timeout) {
  return spawnSync([command, ...args.map(String).map(shellQuote)].join(' '), { encoding: 'utf8', shell: true, timeout });
}

function npmOutput(args) {
  const result = shell('npm', args, 60000);
  return result.status === 0 ? result.stdout.trim() : '';
}

function browsersCacheDirs() {
  const dirs = [];
  const configured = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (configured && configured !== '0') dirs.push(configured);
  if (process.platform === 'win32') dirs.push(path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'ms-playwright'));
  else if (process.platform === 'darwin') dirs.push(path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright'));
  else dirs.push(path.join(process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache'), 'ms-playwright'));
  return dirs.filter((dir) => existsSync(dir));
}

function installedChromiumExecutables() {
  const layouts = process.platform === 'win32'
    ? { 'chromium-': ['chrome-win64/chrome.exe', 'chrome-win/chrome.exe'], 'chromium_headless_shell-': ['chrome-headless-shell-win64/chrome-headless-shell.exe'] }
    : process.platform === 'darwin'
      ? { 'chromium-': ['chrome-mac/Chromium.app/Contents/MacOS/Chromium', 'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium'], 'chromium_headless_shell-': ['chrome-headless-shell-mac/chrome-headless-shell', 'chrome-headless-shell-mac-arm64/chrome-headless-shell'] }
      : { 'chromium-': ['chrome-linux/chrome', 'chrome-linux64/chrome'], 'chromium_headless_shell-': ['chrome-headless-shell-linux64/chrome-headless-shell', 'chrome-headless-shell-linux/chrome-headless-shell'] };
  const found = [];
  for (const dir of browsersCacheDirs()) {
    for (const entry of readdirSync(dir)) {
      for (const [prefix, relatives] of Object.entries(layouts)) {
        if (!entry.startsWith(prefix) || !/^\d+$/.test(entry.slice(prefix.length))) continue;
        for (const relative of relatives) {
          const executablePath = path.join(dir, entry, ...relative.split('/'));
          if (existsSync(executablePath)) found.push({ executablePath, revision: Number(entry.slice(prefix.length)), headlessShell: prefix.includes('headless') });
        }
      }
    }
  }
  // Newest revision first; a full Chromium build before the headless shell of the same revision.
  return found.sort((a, b) => b.revision - a.revision || Number(a.headlessShell) - Number(b.headlessShell));
}

function candidateModuleDirs() {
  const candidates = [];
  const globalRoot = npmOutput(['root', '-g']);
  if (globalRoot) {
    candidates.push({ dir: globalRoot, source: 'global npm root', rank: 0 });
    candidates.push({ dir: path.join(globalRoot, 'agent-browser'), source: 'agent-browser nested node_modules', rank: 0 });
  }
  const cache = npmOutput(['config', 'get', 'cache']);
  const npx = cache ? path.join(cache, '_npx') : '';
  if (npx && existsSync(npx)) {
    for (const entry of readdirSync(npx)) {
      const modules = path.join(npx, entry, 'node_modules');
      if (existsSync(path.join(modules, 'playwright')) || existsSync(path.join(modules, 'playwright-core'))) {
        candidates.push({ dir: path.join(npx, entry), source: 'npx cache', rank: 1 });
      }
    }
  }
  return candidates;
}

function resolvePlaywrightModules() {
  const found = [];
  for (const candidate of candidateModuleDirs()) {
    const require = createRequire(path.join(candidate.dir, 'package.json'));
    for (const name of ['playwright', 'playwright-core']) {
      try {
        const packageJson = require.resolve(`${name}/package.json`);
        const version = JSON.parse(readFileSync(packageJson, 'utf8')).version;
        found.push({ name, version, main: require.resolve(name), source: candidate.source, rank: candidate.rank, prerelease: version.includes('-') });
      } catch {
        // Not present at this candidate; keep looking.
      }
    }
  }
  const compare = (a, b) => a.rank - b.rank || Number(a.prerelease) - Number(b.prerelease) || b.version.localeCompare(a.version, 'en', { numeric: true });
  const unique = new Map();
  for (const item of found.sort(compare)) if (!unique.has(item.main)) unique.set(item.main, item);
  return [...unique.values()];
}

// ---------------------------------------------------------------------------
// Session adapters: the checks only use open/evaluate/press/screenshot/errors/close.
// ---------------------------------------------------------------------------
class PlaywrightSession {
  constructor(browser, viewport) {
    this.browser = browser;
    this.viewport = viewport;
    this.consoleErrors = [];
    this.pageErrors = [];
    this.failedRequests = [];
  }

  async open(url) {
    this.context = await this.browser.newContext({ viewport: this.viewport });
    this.page = await this.context.newPage();
    this.page.on('console', (message) => { if (message.type() === 'error') this.consoleErrors.push(message.text()); });
    this.page.on('pageerror', (error) => this.pageErrors.push(String(error && error.message ? error.message : error)));
    this.page.on('requestfailed', (request) => this.failedRequests.push(`${request.url()} ${request.failure() ? request.failure().errorText : 'failed'}`));
    this.page.on('response', (response) => { if (response.status() >= 400) this.failedRequests.push(`${response.url()} HTTP ${response.status()}`); });
    await this.page.goto(url, { waitUntil: 'load' });
  }

  evaluate(expression) { return this.page.evaluate(expression); }
  press(key) { return this.page.keyboard.press(key); }
  async screenshot(file, fullPage) { await this.page.screenshot({ path: file, fullPage }); }
  async errors() { return { consoleErrors: this.consoleErrors, pageErrors: this.pageErrors, failedRequests: this.failedRequests }; }
  async close() { if (this.context) await this.context.close(); }
}

class AgentBrowserSession {
  constructor(viewport) {
    this.viewport = viewport;
    this.session = `southern-war-${viewport.width}x${viewport.height}-${process.pid}`;
  }

  run(args, { json = false } = {}) {
    const result = shell('agent-browser', ['--session', this.session, ...(json ? ['--json'] : []), ...args], 120000);
    if (result.error) throw result.error;
    if (result.status !== 0) {
      throw new Error(`agent-browser ${args[0]} failed (${result.status}): ${(result.stderr || result.stdout || '').trim()}`);
    }
    return (result.stdout || '').trim();
  }

  static parseJson(text) {
    try { return JSON.parse(text); } catch { return text; }
  }

  static unwrap(parsed) {
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      for (const key of ['result', 'value', 'data']) if (key in parsed) return parsed[key];
    }
    return parsed;
  }

  static messages(parsed) {
    let list;
    if (Array.isArray(parsed)) list = parsed;
    else if (parsed && typeof parsed === 'object') list = [parsed.logs, parsed.messages, parsed.errors, parsed.data, parsed.result].find(Array.isArray) || [];
    else list = String(parsed || '').split(/\r?\n/).filter(Boolean);
    return list.map((item) => (item && typeof item === 'object' ? item : { text: String(item) }));
  }

  async open(url) {
    this.run(['open', url]);
    this.run(['set', 'viewport', this.viewport.width, this.viewport.height]);
  }

  async evaluate(expression) {
    const output = this.run(['eval', '-b', Buffer.from(expression, 'utf8').toString('base64')], { json: true });
    const parsed = AgentBrowserSession.parseJson(output);
    if (parsed && typeof parsed === 'object' && parsed.error) throw new Error(String(parsed.error));
    return AgentBrowserSession.unwrap(parsed);
  }

  async press(key) { this.run(['press', key]); }
  async screenshot(file, fullPage) { this.run(['screenshot', ...(fullPage ? ['--full'] : []), file]); }

  async errors() {
    const consoleErrors = AgentBrowserSession.messages(AgentBrowserSession.parseJson(this.run(['console'], { json: true })))
      .filter((item) => !item.type || /error/i.test(String(item.type)))
      .map((item) => item.text || JSON.stringify(item));
    const pageErrors = AgentBrowserSession.messages(AgentBrowserSession.parseJson(this.run(['errors'], { json: true })))
      .map((item) => item.text || item.message || JSON.stringify(item));
    return { consoleErrors, pageErrors, failedRequests: [] };
  }

  async close() { try { this.run(['close']); } catch { /* session already gone */ } }
}

async function selectDriver(options) {
  const attempts = [];
  if (options.driver !== 'agent-browser') {
    const installed = installedChromiumExecutables();
    for (const candidate of resolvePlaywrightModules()) {
      let playwright;
      try {
        const module = await import(pathToFileURL(candidate.main).href);
        playwright = module.chromium ? module : module.default;
        if (!playwright || !playwright.chromium) throw new Error('module exposes no chromium launcher');
      } catch (error) {
        attempts.push(`${candidate.source} ${candidate.name}@${candidate.version}: ${error.message.split('\n')[0]}`);
        continue;
      }
      // The module's pinned browser first, then any Chromium already installed in the cache.
      const launches = [{ executablePath: undefined }, ...installed];
      for (const launch of launches) {
        try {
          const browser = await playwright.chromium.launch({ headless: !options.headed, executablePath: launch.executablePath });
          return {
            info: {
              kind: 'playwright', module: candidate.name, version: candidate.version, source: candidate.source, path: candidate.main,
              browserVersion: browser.version(), executablePath: launch.executablePath || 'module default',
              note: launch.executablePath ? 'launched an installed Chromium revision that differs from the module default' : undefined,
              attempts,
            },
            create: (viewport) => new PlaywrightSession(browser, viewport),
            dispose: () => browser.close(),
          };
        } catch (error) {
          attempts.push(`${candidate.source} ${candidate.name}@${candidate.version} (${launch.executablePath || 'module default'}): ${error.message.split('\n')[0]}`);
        }
      }
    }
    if (options.driver === 'playwright') throw new Error(`No usable Playwright module: ${attempts.join('; ') || 'none found'}`);
  }
  const probe = shell('agent-browser', ['--version'], 60000);
  if (probe.status !== 0) {
    throw new Error(`No browser driver available. Playwright attempts: ${attempts.join('; ') || 'none found'}. agent-browser: ${(probe.stderr || probe.error || 'not found').toString().trim()}`);
  }
  return {
    info: { kind: 'agent-browser', version: (probe.stdout || '').trim(), attempts },
    create: (viewport) => new AgentBrowserSession(viewport),
    dispose: async () => {},
  };
}

// ---------------------------------------------------------------------------
// In-page expressions (evaluated as strings so both drivers behave identically)
// ---------------------------------------------------------------------------
const READY_EXPRESSION = `(() => {
  const title = document.querySelector('#mapTitle');
  if (title && title.textContent === 'Map failed to load') {
    return { failed: (document.querySelector('#detail') || {}).textContent || 'unknown' };
  }
  return { ready: typeof DATA !== 'undefined' && !!DATA && !!active && document.querySelectorAll('#map .district').length > 0 };
})()`;

const RESET_FOCUS_EXPRESSION = `(() => { window.scrollTo(0, 0); if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); return true; })()`;

const ACTIVE_ELEMENT_EXPRESSION = `(() => {
  const el = document.activeElement;
  if (!el || el === document.body) return 'body';
  return el.id || (el.getAttribute('class') || el.tagName.toLowerCase());
})()`;

const OVERFLOW_EXPRESSION = `(() => {
  const scrolls = (el) => { for (let node = el.parentElement; node && node !== document.body; node = node.parentElement) { const overflow = getComputedStyle(node).overflowX; if (overflow === 'auto' || overflow === 'scroll' || overflow === 'hidden') return true; } return false; };
  const wide = [...document.querySelectorAll('body *')]
    .filter((el) => el.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(el).position !== 'fixed' && !scrolls(el))
    .slice(0, 6)
    .map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : ''));
  const ok = document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth;
  return { ok, innerWidth, scrollWidth: document.documentElement.scrollWidth, bodyScrollWidth: document.body.scrollWidth, elementsPastRightEdge: wide };
})()`;

const EMPTY_SLICE_EXPRESSION = `(() => {
  const change = (selector, value) => { const el = document.querySelector(selector); el.value = String(value); el.dispatchEvent(new Event('change', { bubbles: true })); };
  change('#state', 'VA'); change('#cycle', 2017); change('#chamber', 'lower');
  const slice = DATA.slices['VA-2017-lower'];
  const text = (selector) => ((document.querySelector(selector) || {}).textContent || '').replace(/\\s+/g, ' ').trim();
  const result = {
    sliceKey: active ? active.state + '-' + active.cycle + '-' + active.chamber : null,
    mapTitle: text('#mapTitle'),
    districts: document.querySelectorAll('#map .district').length,
    expectedDistricts: slice ? slice.districts : null,
    races: slice ? Object.keys(slice.races).length : null,
    rowsText: text('#rows').slice(0, 160),
    summaryText: text('#summary').slice(0, 160),
    strictRacesTile: (() => { const tile = [...document.querySelectorAll('#summary div')].find((div) => /Strict D\\/R races/.test(div.textContent)); return tile && tile.querySelector('b') ? tile.querySelector('b').textContent.trim() : null; })(),
    pickerAllUnscored: [...document.querySelectorAll('#district option')].slice(1).every((option) => /unscored/.test(option.textContent)),
    grayDistricts: [...document.querySelectorAll('#map .district')].every((p) => p.getAttribute('fill') === color(null)),
  };
  change('#district', '1');
  result.detailText = text('#detail').slice(0, 260);
  result.raceboxAbsent = !document.querySelector('.racebox');
  result.detailVisible = getComputedStyle(document.querySelector('#detail')).display !== 'none';
  result.ok = result.sliceKey === 'VA-2017-lower' && result.races === 0 && result.districts === result.expectedDistricts && result.districts === 100
    && /No strict WAR-eligible races/.test(result.rowsText) && result.strictRacesTile === '0' && result.pickerAllUnscored && result.grayDistricts
    && /No eligible WAR score/.test(result.detailText) && /Missing WAR is not zero/.test(result.detailText) && result.raceboxAbsent && result.detailVisible;
  return result;
})()`;

const SCROLL_DASHBOARD_EXPRESSION = `(() => { const el = document.querySelector('.dashboard'); if (el) el.scrollIntoView({ block: 'start' }); return !!el; })()`;

async function waitForPayload(session) {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    const state = await session.evaluate(READY_EXPRESSION);
    if (state && state.failed) throw new Error(`Map failed to load: ${state.failed}`);
    if (state && state.ready) return;
    await sleep(250);
  }
  throw new Error('Timed out waiting for the map payload to render');
}

async function keyboardReachability(session) {
  await session.evaluate(RESET_FOCUS_EXPRESSION);
  const sequence = [];
  const reached = [];
  for (let i = 0; i < 40 && reached.length < WANTED_TAB_ORDER.length; i++) {
    await session.press('Tab');
    const focused = String(await session.evaluate(ACTIVE_ELEMENT_EXPRESSION));
    sequence.push(focused);
    if (WANTED_TAB_ORDER.includes(focused) && !reached.includes(focused)) reached.push(focused);
  }
  const ok = JSON.stringify(reached) === JSON.stringify(WANTED_TAB_ORDER);
  return { ok, reached, tabPresses: sequence.length, sequence };
}

async function runViewport(driver, origin, viewport, options) {
  const label = `${viewport.width}x${viewport.height}`;
  const report = { status: 'passed', failures: [], screenshots: [] };
  const fail = (message) => { report.failures.push(message); };
  const session = driver.create(viewport);
  try {
    await session.open(`${origin}/${PAGE}`);
    await waitForPayload(session);
    report.initialOverflow = await session.evaluate(OVERFLOW_EXPRESSION);
    if (!report.initialOverflow.ok) fail(`horizontal page overflow after load (scrollWidth ${report.initialOverflow.scrollWidth} > ${report.initialOverflow.innerWidth})`);

    report.keyboard = await keyboardReachability(session);
    if (!report.keyboard.ok) fail(`Tab order did not reach ${WANTED_TAB_ORDER.join(', ')} in order; reached ${report.keyboard.reached.join(', ') || 'nothing'}`);

    try {
      report.inPageChecks = await session.evaluate(readFileSync(CHECKS_FILE, 'utf8'));
      if (!report.inPageChecks || report.inPageChecks.status !== 'passed') fail('in-page checks did not report status passed');
    } catch (error) {
      report.inPageChecks = { status: 'failed', error: error.message.split('\n')[0] };
      fail(`in-page checks: ${report.inPageChecks.error}`);
    }
    report.selectedRaceOverflow = await session.evaluate(OVERFLOW_EXPRESSION);
    if (!report.selectedRaceOverflow.ok) fail(`horizontal page overflow with a race selected (scrollWidth ${report.selectedRaceOverflow.scrollWidth} > ${report.selectedRaceOverflow.innerWidth})`);
    report.focusAfterChecks = String(await session.evaluate(ACTIVE_ELEMENT_EXPRESSION));
    if (options.screenshotDir) {
      const file = path.join(options.screenshotDir, `southern-war-${label}-full.png`);
      await session.screenshot(file, true);
      report.screenshots.push(file);
    }

    report.emptySlice = await session.evaluate(EMPTY_SLICE_EXPRESSION);
    if (!report.emptySlice.ok) fail('VA-2017-lower empty-slice explanation is incomplete');
    report.emptySliceOverflow = await session.evaluate(OVERFLOW_EXPRESSION);
    if (!report.emptySliceOverflow.ok) fail(`horizontal page overflow on the empty slice (scrollWidth ${report.emptySliceOverflow.scrollWidth} > ${report.emptySliceOverflow.innerWidth})`);
    report.focusAfterEmptySlice = String(await session.evaluate(ACTIVE_ELEMENT_EXPRESSION));
    if (options.screenshotDir) {
      await session.evaluate(SCROLL_DASHBOARD_EXPRESSION);
      const file = path.join(options.screenshotDir, `southern-war-${label}-va-2017-lower.png`);
      await session.screenshot(file, false);
      report.screenshots.push(file);
    }
  } catch (error) {
    fail(`harness: ${error.message.split('\n')[0]}`);
  } finally {
    try {
      const errors = await session.errors();
      Object.assign(report, errors);
      if (errors.consoleErrors.length) fail(`${errors.consoleErrors.length} console error(s)`);
      if (errors.pageErrors.length) fail(`${errors.pageErrors.length} page error(s)`);
      if (errors.failedRequests.length) fail(`${errors.failedRequests.length} failed request(s)`);
    } catch (error) {
      fail(`could not collect browser errors: ${error.message.split('\n')[0]}`);
    }
    await session.close();
  }
  report.status = report.failures.length ? 'failed' : 'passed';
  return report;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const result = { status: 'failed', page: null, docsDir: options.docs, checksFile: CHECKS_FILE, driver: null, viewports: {}, failures: [] };
  if (!existsSync(path.join(options.docs, PAGE))) throw new Error(`Missing ${path.join(options.docs, PAGE)}`);
  if (options.screenshotDir) await fs.mkdir(options.screenshotDir, { recursive: true });
  const { server, origin } = await serveDocs(options.docs);
  result.page = `${origin}/${PAGE}`;
  let driver = null;
  try {
    driver = await selectDriver(options);
    result.driver = driver.info;
    for (const viewport of VIEWPORTS) {
      const label = `${viewport.width}x${viewport.height}`;
      const report = await runViewport(driver, origin, viewport, options);
      result.viewports[label] = report;
      for (const failure of report.failures) result.failures.push(`${label}: ${failure}`);
    }
  } finally {
    if (driver) await driver.dispose();
    server.close();
  }
  result.status = result.failures.length ? 'failed' : 'passed';
  return result;
}

main().then((result) => {
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.status === 'passed' ? 0 : 1);
}).catch((error) => {
  console.log(JSON.stringify({ status: 'error', error: error.message, stack: error.stack }, null, 2));
  process.exit(1);
});
