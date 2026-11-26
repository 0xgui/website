// Social preview cards (Open Graph / link previews): 1200x630 WebP files in og/.
// Node built-ins plus a local Chromium browser; no npm packages.
//   node scripts/og_cards.mjs            # writes og/*.webp
//   CHROME=/path/to/chrome node scripts/og_cards.mjs
// File names carry a version (-v1). Bump it when a card changes, so link-preview caches
// and the year-long media cache pick up the new file. Update CARDS in scripts/build_agent.py too.
import {spawn, execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync, existsSync} from 'node:fs';
import {join, normalize, extname} from 'node:path';
import {tmpdir} from 'node:os';

const ROOT = new URL('..', import.meta.url).pathname;
const W = 1200, H = 630;

const ART = {
  so101: {src: '/robots/so-101/so101-notebook.svg', box: [40, 110, 1500, 980]},
  pico: {src: '/robots/pico/pico-notebook.svg', box: [500, 70, 640, 1040], clear: '64px', fade: '150px'},
};

// slug: output name; kicker: small caps line; title; sub: one line under the title; art: right-third study.
export const CARDS = [
  {slug: 'home', kicker: 'Builds · Writing · Talks', title: 'Guilherme Silva', sub: 'Building small robots from scratch and writing about engineering and physical AI', art: 'so101'},
  {slug: 'about', kicker: 'About', title: 'Platform engineer turned robot tinkerer', sub: 'Guilherme Silva'},
  {slug: 'work', kicker: 'Work', title: 'Where I’ve worked', sub: 'Hitachi Digital, Deichmann, Mercedes-Benz and more'},
  {slug: 'builds', kicker: 'Builds', title: 'Robots I’m building', sub: 'An SO-101 arm and Pico, a self-righting robot', art: 'pico'},
  {slug: 'writing', kicker: 'Writing', title: 'Binary Paths', sub: 'Essays on engineering, teams and physical AI'},
  {slug: 'talks', kicker: 'Talks', title: 'Talks and slides', sub: 'Kubernetes, WebAssembly, platform engineering and AI'},
  {slug: 'talk-bottleneck-moved', kicker: 'Talk', title: 'The Bottleneck Moved', sub: 'KCD Porto × DevOpsDays 2026'},
  {slug: 'robot-so101', kicker: 'Build log', title: 'SO-101 robotic arm', sub: 'Teleop, imitation learning, sim-to-real', art: 'so101'},
  {slug: 'robot-pico', kicker: 'Build notes', title: 'Pico, a self-righting robot', sub: 'Two servos and a policy trained in MuJoCo', art: 'pico'},
  {slug: 'essay-aiconomy', kicker: 'Binary Paths · Essay', title: 'AIconomy', sub: 'AI agents will define the future of global ecommerce'},
  {slug: 'essay-5-tech-trends-that-will-define-2025', kicker: 'Binary Paths · Essay', title: '5 Tech Trends That Will Define 2025', sub: 'We are in the best timeline'},
  {slug: 'essay-i-built-a-tiny-robot-that-refuses', kicker: 'Binary Paths · Essay', title: 'I built a tiny robot that refuses to stay down', sub: 'Its name is Pico', art: 'pico'},
  {slug: 'essay-i-just-wanted-to-clean-my-house', kicker: 'Binary Paths · Essay', title: 'I just wanted to clean my house', sub: 'Cleaning one room turned into open-heart surgery on a robot vacuum'},
  {slug: 'essay-physical-ai-is-here-and-im-building', kicker: 'Binary Paths · Essay', title: 'Physical AI is here and I’m building for it', sub: 'A robotic arm moving for the first time', art: 'so101'},
  {slug: 'essay-engineering-estimates', kicker: 'Binary Paths · Essay', title: 'Engineering Estimates: 1 week means 4', sub: 'Why your estimate is a lie you keep telling yourself'},
  {slug: 'essay-you-cant-know-everything-in-tech', kicker: 'Binary Paths · Essay', title: 'You Can’t Know Everything in Tech', sub: 'Tech moves fast, but you can move faster'},
];

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// Keep hyphenated words whole when a title wraps ("self-righting", "sim-to-real").
const title = s => esc(s).replace(/\S+-\S+/g, w => `<span class="nw">${w}</span>`);

function page(card) {
  const art = card.art && ART[card.art];
  const textWidth = art ? 640 : 1040;
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:"Newsreader";font-style:normal;font-weight:400 500;src:url(/fonts/newsreader-normal-latin-v27.woff2) format("woff2")}
@font-face{font-family:"Newsreader";font-style:italic;font-weight:400 500;src:url(/fonts/newsreader-italic-latin-v26.woff2) format("woff2")}
html,body{margin:0;width:${W}px;height:${H}px;overflow:hidden;background:#f4efe4}
body{position:relative;font-family:"Newsreader",Georgia,serif;color:#2a231b;-webkit-font-smoothing:antialiased}
.frame{position:absolute;inset:28px;border:1px solid #d8cdbb}
.text{position:absolute;left:80px;top:80px;bottom:80px;width:${textWidth}px;display:flex;flex-direction:column}
.kicker{font-size:24px;letter-spacing:.14em;font-variant:small-caps;text-transform:lowercase;color:#6c6152;font-weight:500}
.mark{width:72px;height:3px;background:#8a3d1c;margin:22px 0 28px}
h1{margin:0;font-weight:500;font-size:${art ? 72 : 80}px;line-height:1.08;letter-spacing:-.01em;text-wrap:balance}
.sub{margin-top:22px;font-style:italic;font-size:32px;line-height:1.25;color:#6c6152;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.nw{white-space:nowrap}
.foot{margin-top:auto;font-size:24px;color:#2a231b}
.foot span{color:#8a3d1c}
.art{position:absolute;right:48px;top:44px;bottom:44px;width:460px;display:flex;align-items:center;justify-content:center}
.art svg{width:100%;height:100%;color:#2a231b}
.art{-webkit-mask-image:linear-gradient(to right,transparent var(--clear,0px),#000 var(--fade,48px))}
</style></head><body><div class="frame"></div>
<div class="text">
  <div class="kicker">${esc(card.kicker)}</div>
  <div class="mark"></div>
  <h1>${title(card.title)}</h1>
  ${card.sub ? `<div class="sub">${esc(card.sub)}</div>` : ''}
  <div class="foot">Guilherme Silva <span>·</span> silvags.com</div>
</div>
${art ? `<div class="art" style="--clear:${art.clear || '0px'};--fade:${art.fade || '48px'}">${artSvg(card)}</div>` : ''}
<script>
// Shrink the title until it fits on two lines (never below 52px).
const h1 = document.querySelector('h1');
document.fonts.ready.then(() => {
  let size = parseFloat(getComputedStyle(h1).fontSize);
  while (h1.getBoundingClientRect().height > size * 1.08 * 2 + 2 && size > 52) h1.style.fontSize = (size -= 2) + 'px';
  document.body.dataset.ready = '1';
});
</script></body></html>`;
}

// The notebook SVG is inlined so its strokes take the ink colour through currentColor.
function artSvg(card) {
  const art = ART[card.art];
  const inner = readFileSync(join(ROOT, art.src), 'utf8')
    .replace(/^[\s\S]*?<svg\b[^>]*>/, '').replace(/<\/svg>\s*$/, '').replace(/<title\b[^>]*>[\s\S]*?<\/title>/, '');
  return `<svg viewBox="${art.box.join(' ')}" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
}

const TYPES = {'.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.html': 'text/html'};

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  const names = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'brave', 'brave-browser'];
  const paths = ['/opt/brave-origin-bin/brave', '/opt/brave-bin/brave', '/opt/google/chrome/chrome',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'];
  for (const name of names) {
    try { return execFileSync('which', [name], {encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore']}).trim() } catch {}
  }
  const found = paths.find(p => existsSync(p));
  if (found) return found;
  console.error('no Chrome found; set CHROME=/path/to/chrome');
  process.exit(2);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const only = process.argv.slice(2);
  const cards = only.length ? CARDS.filter(c => only.includes(c.slug)) : CARDS;
  const server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    const card = url.pathname.startsWith('/__card/') && CARDS.find(c => c.slug === url.pathname.slice(8));
    if (card) { res.writeHead(200, {'content-type': 'text/html'}); return res.end(page(card)) }
    const file = join(ROOT, normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, ''));
    if (!file.startsWith(ROOT) || !existsSync(file)) { res.writeHead(404); return res.end() }
    res.writeHead(200, {'content-type': TYPES[extname(file)] || 'application/octet-stream'});
    res.end(readFileSync(file));
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;

  const profile = mkdtempSync(join(tmpdir(), 'og-cards-'));
  const port = 9100 + Math.floor(Math.random() * 400);
  const chrome = spawn(findChrome(), ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
    '--force-color-profile=srgb', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], {stdio: 'ignore'});
  let target;
  for (let i = 0; i < 75 && !target; i++) {
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page') } catch {}
    if (!target) await sleep(200);
  }
  if (!target) { console.error('could not start Chrome'); process.exit(2) }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let seq = 0, loaded = null;
  const pending = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
    if (m.method === 'Page.loadEventFired' && loaded) loaded();
  };
  const send = (method, params = {}) => new Promise(r => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({id, method, params})) });
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {width: W, height: H, deviceScaleFactor: 1, mobile: false});

  mkdirSync(join(ROOT, 'og'), {recursive: true});
  for (const card of cards) {
    const l = new Promise(r => loaded = r);
    await send('Page.navigate', {url: `${base}/__card/${card.slug}`});
    await Promise.race([l, sleep(8000)]);
    await send('Runtime.evaluate', {expression: `new Promise(r => (function wait() { document.body.dataset.ready ? r(1) : setTimeout(wait, 20) })())`, awaitPromise: true});
    await sleep(150);
    if (process.env.OG_DEBUG) console.log(JSON.stringify((await send('Runtime.evaluate', {expression: 'JSON.stringify([...document.querySelectorAll(".art svg > g")].map(g => { const b = g.getBBox(); return [b.x, b.y, b.width, b.height].map(Math.round) }))', returnByValue: true})).result.result.value));
    const shot = await send('Page.captureScreenshot', {format: 'webp', quality: 96, clip: {x: 0, y: 0, width: W, height: H, scale: 1}});
    const bytes = Buffer.from(shot.result.data, 'base64');
    const out = join(ROOT, 'og', `${card.slug}-v1.webp`);
    writeFileSync(out, bytes);
    console.log(`og/${card.slug}-v1.webp ${Math.round(bytes.length / 1024)} KB`);
  }
  ws.close(); server.close();
  const exited = new Promise(r => chrome.once('exit', r));
  chrome.kill();
  await Promise.race([exited, sleep(3000)]);
  try { rmSync(profile, {recursive: true, force: true, maxRetries: 5}) } catch {}  // Chrome may still be flushing its profile
}

main();
