import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTENT_SIGNAL,
  estimateTokens,
  markdownAssetPath,
  onRequest,
  prefersMarkdown,
} from "../functions/_middleware.js";

test("browsers stay on HTML", () => {
  assert.equal(
    prefersMarkdown("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    false,
  );
  assert.equal(prefersMarkdown(""), false);
  assert.equal(prefersMarkdown("text/html, text/markdown;q=0.1"), false);
});

test("markdown clients get markdown", () => {
  assert.equal(prefersMarkdown("text/markdown"), true);
  assert.equal(prefersMarkdown("text/markdown, text/html;q=0.9"), true);
  assert.equal(prefersMarkdown("text/markdown, text/html"), true);
  assert.equal(prefersMarkdown("text/html, text/markdown"), false);
});

test("paths map onto index.md twins", () => {
  assert.equal(markdownAssetPath("/"), "/index.md");
  assert.equal(markdownAssetPath("/index.html"), "/index.md");
  assert.equal(markdownAssetPath("/about/"), "/about/index.md");
  assert.equal(markdownAssetPath("/about"), "/about/index.md");
  assert.equal(markdownAssetPath("/writing/hello-world/"), "/writing/hello-world/index.md");
  assert.equal(markdownAssetPath("/writing/hello-world/index.md"), null);
  assert.equal(markdownAssetPath("/favicon.svg"), null);
  assert.equal(markdownAssetPath("/robots/so-101/arms-wide.webp"), null);
  assert.equal(markdownAssetPath("/../secret"), null);
});

test("signal and token estimate stay stable", () => {
  assert.equal(CONTENT_SIGNAL, "search=yes, ai-input=yes, ai-train=no");
  assert.equal(estimateTokens("abcd"), 1);
  assert.equal(estimateTokens("abcde"), 2);
});

function context(path, accept, pages) {
  const respond = (p) => (p in pages ? new Response(pages[p], { status: 200 }) : new Response("missing", { status: 404 }));
  return {
    request: new Request("https://silvags.com" + path, { headers: { Accept: accept } }),
    env: { ASSETS: { fetch: async (req) => respond(new URL(req.url).pathname) } },
    next: async () => respond(path),
  };
}

test("markdown-only client: twin, missing page, page without twin", async () => {
  const pages = { "/about/": "<html>", "/about/index.md": "# About", "/demo/": "<html>" };
  const twin = await onRequest(context("/about/", "text/markdown", pages));
  assert.equal(twin.status, 200);
  assert.equal(await twin.text(), "# About");
  assert.equal((await onRequest(context("/nope/", "text/markdown", pages))).status, 404);
  assert.equal((await onRequest(context("/demo/", "text/markdown", pages))).status, 406);
});
