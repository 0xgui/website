// RSS proxy for the homepage. Deploy separately using wrangler.toml.
const RSS_URL = 'https://binarypaths.substack.com/feed';
const FRESH_MS = 60 * 60 * 1000;
const RETAIN_SECONDS = 7 * 24 * 60 * 60;

function json(data, status = 200, maxAge = 300) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': status === 200 ? `public, max-age=${maxAge}` : 'no-store',
    },
  });
}

function decodeXML(value) {
  return value.replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos);/gi, (match, entity) => {
    const names = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
    if (entity[0] !== '#') return names[entity.toLowerCase()] || match;
    const n = entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : parseInt(entity.slice(1), 10);
    return n > 0 && n <= 0x10ffff && !(n >= 0xd800 && n <= 0xdfff) ? String.fromCodePoint(n) : match;
  });
}

function textTag(xml, name) {
  const raw = xml.match(new RegExp(`<${name}\\b[^>]*>([\\s\\S]*?)<\\/${name}>`, 'i'))?.[1]?.trim() || '';
  // Decode XML text without double-decoding text inside CDATA.
  return raw.split(/(<!\[CDATA\[[\s\S]*?\]\]>)/g)
    .map(part => part.startsWith('<![CDATA[') ? part.slice(9, -3) : decodeXML(part)).join('').trim();
}

function httpsURL(value) {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : ''; } catch { return ''; }
}

export function parseFeed(xml) {
  if (!/<rss\b/i.test(xml) || !/<\/rss\s*>/i.test(xml)) throw new Error('Invalid RSS document');
  const items = [];
  for (const match of xml.matchAll(/<item\b[^>]*>([\s\S]*?)<\/item>/gi)) {
    const source = match[1];
    const title = textTag(source, 'title');
    const link = httpsURL(textTag(source, 'link'));
    if (!title || !link) continue;
    let image = '';
    for (const tag of ['enclosure', 'media:content', 'media:thumbnail']) {
      const element = source.match(new RegExp(`<${tag}\\b[^>]*>`, 'i'))?.[0] || '';
      const value = element.match(/\burl\s*=\s*(["'])([\s\S]*?)\1/i)?.[2] || '';
      image = httpsURL(decodeXML(value));
      if (image) break;
    }
    items.push({ title, link, pubDate: textTag(source, 'pubDate'), description: textTag(source, 'description'), image });
    if (items.length === 5) break;
  }
  if (!items.length) throw new Error('RSS contains no usable articles');
  return items;
}

async function refresh(cache, key) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6000);
  try {
    const response = await fetch(RSS_URL, {
      signal: controller.signal,
      headers: { Accept: 'application/rss+xml, application/xml, text/xml' },
    });
    if (!response.ok) throw new Error(`RSS returned ${response.status}`);
    const items = parseFeed(await response.text());
    const data = { items, fetchedAt: new Date().toISOString() };
    // Keep a last-good copy beyond the freshness window for upstream outages.
    try { await cache.put(key, json(data, 200, RETAIN_SECONDS)); } catch { /* Cache is best-effort. */ }
    return data;
  } finally { clearTimeout(timeout); }
}

const API_URL = 'https://binarypaths.substack.com/api/v1/posts?limit=50';
const SNAPSHOT_KEY = 'raw.xml';
const SNAPSHOT_ATTEMPTS = 3;
const CONTENT_NS = 'http://purl.org/rss/1.0/modules/content/';
// Substack rejects short client names. This is the same browser string the mirror uses.
const SNAPSHOT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

export function isChallenge(text) {
  const sample = String(text || '').slice(0, 8000).toLowerCase();
  return [
    'just a moment',
    'cf-browser-verification',
    'challenge-platform',
    'attention required',
    'enable javascript and cookies',
    'cf-mitigated',
    'cf-chl',
  ].some(marker => sample.includes(marker));
}

export function assertSnapshot(xml) {
  if (typeof xml !== 'string' || !xml.trim()) throw new Error('empty snapshot');
  if (isChallenge(xml)) throw new Error('challenge html');
  if (!/<rss\b/i.test(xml) || !/<\/rss\s*>/i.test(xml)) throw new Error('not rss');
  if (!/<item\b/i.test(xml)) throw new Error('no items');
  return xml;
}

export function stampFetchedAt(xml, fetchedAt) {
  const comment = `<!-- fetchedAt: ${fetchedAt} -->`;
  if (/<!--\s*fetchedAt:[\s\S]*?-->/.test(xml)) {
    return xml.replace(/<!--\s*fetchedAt:[\s\S]*?-->/, comment);
  }
  if (xml.startsWith('<?xml')) return xml.replace(/^(<\?xml[^?]*\?>)/, `$1${comment}`);
  return comment + xml;
}

export function fetchedAtFromXml(xml) {
  return xml.match(/<!--\s*fetchedAt:\s*([^>]*?)\s*-->/)?.[1] || '';
}

function xmlEscape(value) {
  return String(value || '').replace(/[&<>"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
  }[char]));
}

function cdata(value) {
  return `<![CDATA[${String(value || '').replace(/]]>/g, ']]]]><![CDATA[>')}]]>`;
}

export function rssFromPosts(payload, fetchedAt) {
  const rows = Array.isArray(payload) ? payload : payload?.posts;
  if (!Array.isArray(rows) || !rows.length) throw new Error('api returned no posts');
  const items = rows.map(post => {
    const slug = String(post.slug || '').trim();
    const link = String(post.canonical_url || post.link || (slug ? `https://binarypaths.substack.com/p/${slug}` : ''));
    return [
      '<item>',
      `<title>${xmlEscape(post.title || '')}</title>`,
      `<link>${xmlEscape(link)}</link>`,
      `<pubDate>${xmlEscape(post.post_date || post.pubDate || '')}</pubDate>`,
      `<description>${xmlEscape(post.subtitle || post.description || '')}</description>`,
      `<content:encoded>${cdata(post.body_html || post.content_html || '')}</content:encoded>`,
      '</item>',
    ].join('');
  }).join('');
  return assertSnapshot(stampFetchedAt(
    `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:content="${CONTENT_NS}"><channel><title>Binary Paths</title>${items}</channel></rss>`,
    fetchedAt,
  ));
}

async function readUpstream(fetcher, url) {
  const response = await fetcher(url, {
    headers: { 'User-Agent': SNAPSHOT_UA, Accept: '*/*' },
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  if (isChallenge(text)) throw new Error(`${url} returned a challenge`);
  return text;
}

async function retry(fn) {
  let last;
  for (let attempt = 0; attempt < SNAPSHOT_ATTEMPTS; attempt++) {
    try {
      return await fn();
    } catch (err) {
      last = err;
    }
  }
  throw last;
}

async function postsFromApi(fetcher) {
  const posts = [];
  let cursor = '';
  for (let page = 0; page < 20; page++) {
    const url = API_URL + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : '');
    const raw = await retry(() => readUpstream(fetcher, url));
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      throw new Error('api json is not valid');
    }
    const rows = Array.isArray(payload) ? payload : payload?.posts;
    if (!Array.isArray(rows)) throw new Error('api posts is not a list');
    if (!rows.length) break;
    posts.push(...rows);
    cursor = !Array.isArray(payload) && payload?.nextCursor ? String(payload.nextCursor) : '';
    if (!cursor) break;
  }
  if (!posts.length) throw new Error('api returned no posts');
  return posts;
}

export async function collectSnapshot(fetcher = fetch, now = () => new Date()) {
  const fetchedAt = now().toISOString();
  let rssError;
  try {
    const xml = await retry(() => readUpstream(fetcher, RSS_URL));
    return stampFetchedAt(assertSnapshot(xml), fetchedAt);
  } catch (err) {
    rssError = err;
  }
  try {
    return rssFromPosts(await postsFromApi(fetcher), fetchedAt);
  } catch (err) {
    throw new Error(`snapshot fetch failed: ${rssError}; ${err}`);
  }
}

export async function saveSnapshot(env, fetcher = fetch, now = () => new Date()) {
  if (!env?.SNAPSHOT?.put) throw new Error('snapshot store is not configured');
  const xml = await collectSnapshot(fetcher, now);
  const fetchedAt = fetchedAtFromXml(xml);
  await env.SNAPSHOT.put(SNAPSHOT_KEY, xml, { metadata: { fetchedAt } });
  return { fetchedAt, bytes: xml.length };
}

function snapshotResponse(body, status, fetchedAt = '') {
  const headers = {
    'Cache-Control': status === 200 ? 'public, max-age=300' : 'no-store',
    'Access-Control-Allow-Origin': '*',
  };
  if (status === 200) {
    headers['Content-Type'] = 'application/rss+xml; charset=utf-8';
    headers['X-Fetched-At'] = fetchedAt;
  } else {
    headers['Content-Type'] = 'text/plain; charset=utf-8';
  }
  return new Response(body, { status, headers });
}

async function serveRaw(env) {
  if (!env?.SNAPSHOT?.getWithMetadata) return snapshotResponse('snapshot store is not configured', 503);
  let got;
  try {
    got = await env.SNAPSHOT.getWithMetadata(SNAPSHOT_KEY);
  } catch {
    return snapshotResponse('snapshot store failed', 503);
  }
  const value = got?.value;
  if (!value) return snapshotResponse('no snapshot yet', 503);
  try {
    assertSnapshot(value);
  } catch {
    // Leave the stored value in place. The next good cron run overwrites it.
    return snapshotResponse('stored snapshot is not a feed', 503);
  }
  const fetchedAt = got?.metadata?.fetchedAt || fetchedAtFromXml(value);
  return snapshotResponse(value, 200, fetchedAt);
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'GET') return new Response('Method not allowed', {
      status: 405, headers: { Allow: 'GET', 'Access-Control-Allow-Origin': '*' },
    });
    const url = new URL(request.url);
    if (url.pathname === '/raw.xml') return serveRaw(env);
    const cache = caches.default;
    // One key per feed, independent of visitor query strings and paths.
    const key = new Request(new URL('/__binary-paths-v2', request.url).href);
    let cached;
    try {
      const response = await cache.match(key);
      if (response) cached = await response.json();
    } catch { /* A cache failure should not prevent an upstream fetch. */ }
    const age = Date.now() - Date.parse(cached?.fetchedAt);
    if (Array.isArray(cached?.items) && cached.items.length && age >= 0 && age < RETAIN_SECONDS * 1000) {
      const stale = age >= FRESH_MS;
      if (stale) ctx.waitUntil(refresh(cache, key).catch(() => {
        console.warn('RSS refresh failed; retaining last-good articles');
      }));
      return json({ ...cached, stale }, 200, stale ? 60 : 300);
    }
    try {
      return json({ ...await refresh(cache, key), stale: false });
    } catch {
      return json({ error: 'Feed temporarily unavailable' }, 503);
    }
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(saveSnapshot(env));
  },
};
