// Accept: text/markdown negotiation for the static Markdown twins.
// Cloudflare's Markdown for Agents is not on the free plan, so this one
// function serves the sibling index.md when the client prefers Markdown.
// Static files, _headers, and _routes.json do the rest.

export const CONTENT_SIGNAL = "search=yes, ai-input=yes, ai-train=no";

export function estimateTokens(text) {
  const length = typeof text === "string" ? text.length : 0;
  return Math.max(1, Math.ceil(length / 4));
}

function rangeQ(accept, wanted) {
  const [wantType, wantSub] = wanted.split("/");
  let found = null;
  for (const part of String(accept || "").split(",")) {
    const bits = part.split(";").map((bit) => bit.trim()).filter(Boolean);
    if (!bits.length) continue;
    const media = bits[0].toLowerCase();
    let q = 1;
    let index = String(accept).indexOf(part);
    for (const bit of bits.slice(1)) {
      const match = /^q\s*=\s*([0-9.]+)$/i.exec(bit);
      if (match) q = Number(match[1]);
    }
    if (!Number.isFinite(q) || q <= 0) continue;
    const [type, sub] = media.split("/");
    let spec = 0;
    if (media === wanted) spec = 3;
    else if (type === wantType && sub === "*") spec = 2;
    else if (media === "*/*") spec = 1;
    else continue;
    if (!found || spec > found.spec || (spec === found.spec && q > found.q)) {
      found = { spec, q, index };
    }
  }
  return found || { spec: 0, q: 0, index: 1e9 };
}

// Markdown wins only when its quality is higher, or when the qualities tie
// and text/markdown is listed first. Browsers send text/html first and stay
// on HTML. A client that sends only text/markdown gets Markdown.
export function prefersMarkdown(accept) {
  const markdown = rangeQ(accept, "text/markdown");
  const html = rangeQ(accept, "text/html");
  if (markdown.q <= 0) return false;
  if (html.q <= 0) return true;
  if (markdown.q !== html.q) return markdown.q > html.q;
  return markdown.index < html.index;
}

export function markdownAssetPath(pathname) {
  let path = pathname || "/";
  try {
    path = decodeURIComponent(path);
  } catch (_error) {
    return null;
  }
  if (path.includes("\0") || path.split("/").includes("..")) return null;
  if (path.endsWith(".md")) return null;
  if (path === "/" || path === "/index.html") return "/index.md";
  if (path.endsWith("/index.html")) return path.slice(0, -"index.html".length) + "index.md";
  if (path.endsWith("/")) return path + "index.md";
  const slash = path.lastIndexOf("/");
  const base = slash >= 0 ? path.slice(slash + 1) : path;
  if (base.includes(".")) return null;
  return path + "/index.md";
}

function vary(headers) {
  const current = headers.get("Vary");
  if (!current) headers.set("Vary", "Accept");
  else if (!/\baccept\b/i.test(current)) headers.set("Vary", current + ", Accept");
}

function stamp(response) {
  const headers = new Headers(response.headers);
  headers.set("Content-Signal", CONTENT_SIGNAL);
  vary(headers);
  if (!headers.has("Link")) {
    headers.set(
      "Link",
      '</llms.txt>; rel="describedby", </feed.xml>; rel="alternate"; type="application/atom+xml"',
    );
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

export async function onRequest(context) {
  const request = context.request;
  if (request.method !== "GET" && request.method !== "HEAD") {
    return stamp(await context.next());
  }
  const accept = request.headers.get("Accept") || "";
  const url = new URL(request.url);
  if (prefersMarkdown(accept)) {
    const assetPath = markdownAssetPath(url.pathname);
    if (assetPath) {
      const assetUrl = new URL(assetPath, url.origin);
      const asset = await context.env.ASSETS.fetch(new Request(assetUrl, { method: request.method }));
      if (asset.ok) {
        const headers = new Headers(asset.headers);
        headers.set("Content-Type", "text/markdown; charset=utf-8");
        headers.set("Content-Signal", CONTENT_SIGNAL);
        vary(headers);
        headers.set(
          "Link",
          `</llms.txt>; rel="describedby", <${url.pathname}>; rel="alternate"; type="text/html"`,
        );
        if (request.method === "GET") {
          const bytes = await asset.arrayBuffer();
          headers.set("x-markdown-tokens", String(estimateTokens(new TextDecoder().decode(bytes))));
          return new Response(bytes, { status: 200, headers });
        }
        return new Response(null, { status: 200, headers });
      }
      const html = rangeQ(accept, "text/html");
      if (html.q <= 0) {
        return new Response("No markdown representation\n", {
          status: 406,
          headers: {
            "Content-Type": "text/plain; charset=utf-8",
            Vary: "Accept",
            "Content-Signal": CONTENT_SIGNAL,
          },
        });
      }
    }
  }
  const response = await context.next();
  const headers = new Headers(response.headers);
  const assetPath = markdownAssetPath(url.pathname);
  if (assetPath) {
    headers.set(
      "Link",
      `</llms.txt>; rel="describedby", </feed.xml>; rel="alternate"; type="application/atom+xml", <${assetPath}>; rel="alternate"; type="text/markdown"`,
    );
  }
  if (url.pathname.endsWith(".md") || url.pathname.endsWith("/llms-full.txt")) {
    headers.set("Content-Type", "text/markdown; charset=utf-8");
  }
  const stamped = new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  return stamp(stamped);
}
