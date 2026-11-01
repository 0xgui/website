import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTENT_SIGNAL,
  estimateTokens,
  markdownAssetPath,
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
