import assert from "node:assert/strict";
import { test } from "node:test";

import worker, {
  assertSnapshot,
  collectSnapshot,
  isChallenge,
  rssFromPosts,
  saveSnapshot,
} from "../worker.js";

const RSS = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel><item>
    <title>Hello world</title>
    <link>https://binarypaths.substack.com/p/hello-world</link>
    <pubDate>Mon, 05 Mar 2026 08:00:00 GMT</pubDate>
    <content:encoded><![CDATA[<p>The full essay.</p>]]></content:encoded>
  </item></channel>
</rss>`;

const CHALLENGE = "<html><title>Just a moment...</title><body>cf-browser-verification</body></html>";

function fetcher(map, calls) {
  return async (url) => {
    calls.push(url);
    const body = map(url);
    if (body instanceof Error) throw body;
    return { ok: true, status: 200, text: async () => body };
  };
}

test("a challenge page is not a snapshot", () => {
  assert.equal(isChallenge(CHALLENGE), true);
  assert.throws(() => assertSnapshot(CHALLENGE), /challenge html/);
  assert.throws(() => assertSnapshot("<rss></rss>"), /no items/);
  assert.throws(() => assertSnapshot(""), /empty snapshot/);
  assert.equal(assertSnapshot(RSS), RSS);
});

test("posts become a feed with content encoded", () => {
  const xml = rssFromPosts({
    posts: [{
      slug: "hello-world",
      title: "A & B",
      post_date: "2026-03-05T08:00:00.000Z",
      body_html: "<p>keep ]]> this</p>",
    }],
  }, "2026-11-01T18:27:00.000Z");
  assert.match(xml, /<!-- fetchedAt: 2026-11-01T18:27:00.000Z -->/);
  assert.match(xml, /<title>A &amp; B<\/title>/);
  assert.match(xml, /keep \]\]\]\]><!\[CDATA\[> this/);
  assertSnapshot(xml);
});

test("collectSnapshot retries the feed then uses the posts API", async () => {
  const calls = [];
  let rssTries = 0;
  const xml = await collectSnapshot(fetcher(url => {
    if (url.endsWith("/feed")) {
      rssTries += 1;
      return CHALLENGE;
    }
    return JSON.stringify({
      posts: [{ slug: "from-api", title: "From API", post_date: "2026-03-05T08:00:00.000Z", body_html: "<p>Full.</p>" }],
    });
  }, calls), () => new Date("2026-11-01T18:27:00.000Z"));
  assert.equal(rssTries, 3);
  assert.equal(calls.filter(url => url.includes("/api/v1/posts")).length, 1);
  assert.match(xml, /from-api/);
  assert.match(xml, /<p>Full\.<\/p>/);
});

test("a good feed is kept and a failed fetch does not write", async () => {
  const puts = [];
  const env = {
    SNAPSHOT: {
      async put(...args) { puts.push(args); },
      async getWithMetadata() { throw new Error("unread"); },
    },
  };
  const calls = [];
  const saved = await saveSnapshot(env, fetcher(() => RSS, calls), () => new Date("2026-11-01T18:27:00.000Z"));
  assert.equal(saved.fetchedAt, "2026-11-01T18:27:00.000Z");
  assert.equal(puts.length, 1);
  assert.equal(puts[0][0], "raw.xml");
  assert.match(puts[0][1], /<rss\b/);
  assert.equal(puts[0][2].metadata.fetchedAt, "2026-11-01T18:27:00.000Z");

  puts.length = 0;
  await assert.rejects(() => saveSnapshot(env, fetcher(() => CHALLENGE, calls)));
  assert.equal(puts.length, 0);
});

test("raw.xml serves the stored feed and the JSON route stays JSON", async () => {
  const stored = `<!-- fetchedAt: 2026-11-01T18:27:00.000Z -->${RSS}`;
  const env = {
    SNAPSHOT: {
      async getWithMetadata() {
        return { value: stored, metadata: { fetchedAt: "2026-11-01T18:27:00.000Z" } };
      },
    },
  };
  const raw = await worker.fetch(new Request("https://rss.silvags.com/raw.xml"), env, { waitUntil() {} });
  assert.equal(raw.status, 200);
  assert.match(raw.headers.get("content-type"), /application\/rss\+xml/);
  assert.equal(raw.headers.get("x-fetched-at"), "2026-11-01T18:27:00.000Z");
  assert.match(await raw.text(), /<item>/);

  const missing = await worker.fetch(new Request("https://rss.silvags.com/raw.xml"), {
    SNAPSHOT: { async getWithMetadata() { return { value: null, metadata: null }; } },
  }, { waitUntil() {} });
  assert.equal(missing.status, 503);

  const bad = await worker.fetch(new Request("https://rss.silvags.com/raw.xml"), {
    SNAPSHOT: { async getWithMetadata() { return { value: CHALLENGE, metadata: null }; } },
  }, { waitUntil() {} });
  assert.equal(bad.status, 503);

  const denied = await worker.fetch(new Request("https://rss.silvags.com/raw.xml", { method: "POST" }), env, { waitUntil() {} });
  assert.equal(denied.status, 405);

  globalThis.caches = { default: { async match() { return null; }, async put() {} } };
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(RSS, { status: 200 });
  try {
    const json = await worker.fetch(new Request("https://rss.silvags.com/"), {}, { waitUntil() {} });
    assert.equal(json.status, 200);
    assert.match(json.headers.get("content-type"), /application\/json/);
    const body = await json.json();
    assert.equal(body.stale, false);
    assert.equal(body.items[0].title, "Hello world");
    assert.equal(body.items[0].link, "https://binarypaths.substack.com/p/hello-world");
  } finally {
    globalThis.fetch = original;
  }
});

test("the cron stores one good snapshot and leaves KV alone when upstream fails", async () => {
  const puts = [];
  const env = { SNAPSHOT: { async put(...args) { puts.push(args); } } };
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(RSS, { status: 200 });
  try {
    let waited;
    await worker.scheduled({}, env, { waitUntil(promise) { waited = promise; } });
    await waited;
    assert.equal(puts.length, 1);
  } finally {
    globalThis.fetch = original;
  }

  puts.length = 0;
  globalThis.fetch = async () => new Response(CHALLENGE, { status: 200 });
  try {
    let waited;
    await worker.scheduled({}, env, { waitUntil(promise) { waited = promise; } });
    await assert.rejects(() => waited);
    assert.equal(puts.length, 0);
  } finally {
    globalThis.fetch = original;
  }
});
