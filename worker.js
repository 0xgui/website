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

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'GET') return new Response('Method not allowed', {
      status: 405, headers: { Allow: 'GET', 'Access-Control-Allow-Origin': '*' },
    });
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
};
