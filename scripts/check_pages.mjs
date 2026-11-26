// Browser check for every page, at phone and desktop widths, including in-place navigation.
// Node built-ins plus a local Chrome; no npm packages.
//   python3 -m http.server 8000 &
//   node scripts/check_pages.mjs [base-url]      # default http://127.0.0.1:8000
// Exits non-zero on any 4xx/5xx asset, JS error, or horizontal overflow.
import {spawn} from 'node:child_process';
import {readdirSync, statSync, mkdtempSync, rmSync} from 'node:fs';
import {join, relative, sep} from 'node:path';
import {tmpdir} from 'node:os';

const BASE = (process.argv[2] || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ROOT = new URL('..', import.meta.url).pathname;
const CHROME = process.env.CHROME || 'google-chrome';
const VIEWPORTS = {desktop: {width: 1280, height: 900, mobile: false}, mobile: {width: 390, height: 844, mobile: true}};

function pages(dir = ROOT) {
  const out = [];
  for (const name of readdirSync(dir)) {
    if (name.startsWith('.') || ['tests', 'scripts', 'vendor', 'node_modules'].includes(name)) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...pages(p));
    else if (name === 'index.html') out.push('/' + relative(ROOT, dir).split(sep).filter(Boolean).map(s => s + '/').join(''));
  }
  return out.sort();
}
const PAGES = [...pages(), '/404.html'];
// Clicks a visitor makes: every header link from a few starting pages, plus the build cards.
const CLICKS = [
  ...['/', '/builds/', '/robots/pico/', '/robots/so-101/', '/writing/'].flatMap(p =>
    ['a.name', ...['builds', 'writing', 'talks', 'about', 'cv'].map(s => `nav a[href*="${s}"]`)].map(sel => [p, sel])),
  ['/builds/', 'h3 a[href*="so-101"]'], ['/builds/', 'h3 a[href*="pico"]'],
];

const sleep = ms => new Promise(r => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), 'check-pages-'));
const port = 9500 + Math.floor(Math.random() * 400);
const chrome = spawn(CHROME, ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], {stdio: 'ignore'});
let target;
for (let i = 0; i < 75 && !target; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page') } catch {}
  if (!target) await sleep(200);
}
if (!target) { console.error('could not start Chrome'); process.exit(2) }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let seq = 0, problems = [], loaded = null;
const pending = new Map();
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  if (m.method === 'Network.responseReceived') {
    const {status, url} = m.params.response, doc = m.params.type === 'Document';
    if (status >= 400 && !(doc && /\/404(\.html)?$/.test(url)) && !url.endsWith('/favicon.ico')) problems.push(`${status} ${url.replace(BASE, '')}`);
  }
  if (m.method === 'Runtime.exceptionThrown') problems.push('JS ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).split('\n')[0]);
  if (m.method === 'Page.loadEventFired' && loaded) loaded();
};
const send = (method, params = {}) => new Promise(r => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({id, method, params})) });
const evaluate = async x => (await send('Runtime.evaluate', {expression: x, awaitPromise: true, returnByValue: true})).result.result?.value;
const open = async path => { const l = new Promise(r => loaded = r); await send('Page.navigate', {url: BASE + path}); await Promise.race([l, sleep(8000)]); await sleep(700) };
const overflow = () => evaluate(`(() => {
  const w = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth <= w + 1) return '';
  const wide = [...document.querySelectorAll('main *, header *')].filter(e => e.getBoundingClientRect().right > w + 1).slice(0, 3)
    .map(e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''));
  return 'overflow ' + document.documentElement.scrollWidth + 'px > ' + w + 'px (' + wide.join(', ') + ')';
})()`);

await Promise.all(['Network.enable', 'Page.enable', 'Runtime.enable'].map(m => send(m)));
let failed = 0, total = 0;
const report = (label, extra) => {
  total++;
  const all = [...new Set(problems)].concat(extra || []);
  if (all.length) { failed++; console.log(`FAIL ${label}\n  ${all.join('\n  ')}`) }
  problems = [];
};
for (const [name, vp] of Object.entries(VIEWPORTS)) {
  await send('Emulation.setDeviceMetricsOverride', {width: vp.width, height: vp.height, deviceScaleFactor: vp.mobile ? 3 : 1, mobile: vp.mobile});
  await send('Emulation.setTouchEmulationEnabled', {enabled: vp.mobile});
  for (const path of PAGES) { problems = []; await open(path); report(`${name} load ${path}`, [await overflow()].filter(Boolean)) }
  for (const [start, sel] of CLICKS) {
    problems = []; await open(start);
    const href = await evaluate(`(() => { const a = document.querySelector(${JSON.stringify(sel)}); if (!a) return null; a.click(); return a.href })()`);
    if (!href) { problems = []; continue }
    await sleep(1800);
    const at = await evaluate('location.href');
    const extra = [await overflow()].filter(Boolean);
    if (at.replace(/#.*/, '') !== href.replace(/#.*/, '')) extra.push(`ended at ${at}, expected ${href}`);
    report(`${name} click ${start} -> ${href.replace(BASE, '')}`, extra);
  }
}
ws.close(); chrome.kill(); rmSync(profile, {recursive: true, force: true});
console.log(failed ? `${failed} of ${total} checks failed` : `all ${total} checks passed (${PAGES.length} pages, ${CLICKS.length} clicks, mobile + desktop)`);
process.exit(failed ? 1 : 0);
