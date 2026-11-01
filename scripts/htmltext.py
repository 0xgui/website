"""HTML helpers shared by the mirror and the agent-file builder. Stdlib only."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
}
BLOCKS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote",
    "pre", "figure", "figcaption", "table", "thead", "tbody", "tr", "div",
    "article", "section", "dl", "dt", "dd", "hr",
}

# Hosts that must never be linked from this site.
BANNED_HOSTS = {
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "mobile.twitter.com", "t.co", "nitter.net", "vxtwitter.com",
}

_BANNED_URL = re.compile(
    r"https?://(?:www\.)?(?:x\.com|twitter\.com|mobile\.twitter\.com|t\.co|nitter\.net|vxtwitter\.com)/\S*",
    re.I,
)


def escape_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def escape_attr(value: str) -> str:
    return escape_text(value).replace('"', "&quot;")


def clean_text(value: str) -> str:
    """Drop banned URLs and place names this site does not publish."""
    value = _BANNED_URL.sub("", value)
    value = re.sub(r"\bLeiria\b", "", value, flags=re.I)
    value = re.sub(r"\s+in Portugal\b", " there", value, flags=re.I)
    value = re.sub(r"\s+of Portugal\b", " of the trip", value, flags=re.I)
    value = re.sub(r"\bPortugal(?:['’]s)?\b", "", value, flags=re.I)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r" +([,.;:!?])", r"\1", value)
    return value


def host_of(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def banned_url(url: str) -> bool:
    host = host_of(url).lower()
    return host in BANNED_HOSTS or host.endswith(".x.com") or host.endswith(".twitter.com")


def attr_map(attrs) -> dict:
    out = {}
    for key, value in attrs:
        if key and value is not None:
            out[key.lower()] = value
    return out


class Sanitizer(HTMLParser):
    """Allowlist sanitizer. Unwraps layout divs. Drops scripts, widgets, and banned links."""

    ALLOW = {
        "p", "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "ul", "ol", "li",
        "blockquote", "pre", "code", "em", "strong", "a", "img", "figure",
        "figcaption", "sub", "sup", "table", "thead", "tbody", "tr", "th", "td",
    }
    UNWRAP = {"div", "span", "picture", "section", "article", "header", "footer", "main", "body", "html"}
    DROP_TAGS = {
        "script", "style", "svg", "button", "form", "input", "textarea", "nav",
        "aside", "noscript", "object", "embed", "video", "audio", "canvas",
        "source", "iframe", "link", "meta",
    }

    def __init__(self, link_map=None, image_map=None):
        super().__init__(convert_charrefs=True)
        self.link_map = link_map or {}
        self.image_map = image_map or {}
        self.parts: list[str] = []
        self.skip = 0
        self.stack: list[str] = []
        self.in_pre = 0

    def handle_starttag(self, tag, attrs):
        self._start(tag, attr_map(attrs), False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attr_map(attrs), True)

    def _start(self, tag, attrs, empty):
        tag = tag.lower()
        if self.skip:
            if not empty and tag not in VOID:
                self.skip += 1
            return
        blob = f"{attrs.get('class', '')} {attrs.get('data-component-name', '')}".lower()
        if any(token in blob for token in ("subscription", "subscribe-widget", "share-dialog")):
            if not empty and tag not in VOID:
                self.skip = 1
            return
        if tag in self.DROP_TAGS:
            if tag == "iframe":
                self._youtube(attrs.get("src", ""))
            if not empty and tag not in VOID:
                self.skip = 1
            return
        if tag in self.UNWRAP or (tag == "a" and "image" in attrs.get("class", "")):
            return
        if tag == "h1":
            tag = "h2"
        if tag not in self.ALLOW:
            if not empty and tag not in VOID:
                self.skip = 1
            return
        if tag == "a":
            raw = attrs.get("href", "")
            href = self.link_map.get(raw) or self.link_map.get(raw.split("?")[0]) or raw
            if not href or banned_url(raw) or banned_url(href) or href.lower().startswith(("javascript:", "data:")):
                return
            external = href.startswith(("http://", "https://"))
            rel = ' target="_blank" rel="noopener"' if external else ""
            self.parts.append(f'<a href="{escape_attr(href)}"{rel}>')
            self.stack.append("a")
            return
        if tag == "img":
            src = self.image_map.get(attrs.get("src", ""), attrs.get("src", ""))
            if not src or banned_url(src) or src.lower().startswith("javascript:"):
                return
            alt = clean_text(attrs.get("alt", "")).strip()
            if src.endswith(".webm"):
                label = f' aria-label="{escape_attr(alt)}"' if alt else ""
                self.parts.append(
                    f'<video autoplay muted loop playsinline preload="none"{label}>'
                    f'<source src="{escape_attr(src)}" type="video/webm"></video>'
                )
                return
            self.parts.append(f'<img src="{escape_attr(src)}" alt="{escape_attr(alt)}">')
            return
        if tag in VOID:
            self.parts.append(f"<{tag}>")
            return
        self.parts.append(f"<{tag}>")
        self.stack.append(tag)
        if tag == "pre":
            self.in_pre += 1
        if empty:
            self._end(tag)

    def _youtube(self, src: str) -> None:
        match = re.search(r"(?:embed/|watch\?v=|youtu\.be/)([\w-]{6,})", src or "")
        if not match:
            return
        href = f"https://www.youtube.com/watch?v={match.group(1)}"
        self.parts.append(f'<p><a href="{href}" target="_blank" rel="noopener">Watch the video</a></p>\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            self.skip -= 1
            return
        if tag == "h1":
            tag = "h2"
        if tag in self.stack:
            while self.stack:
                open_tag = self.stack.pop()
                self._end(open_tag)
                if open_tag == tag:
                    break

    def _end(self, tag):
        if tag == "pre" and self.in_pre:
            self.in_pre -= 1
        self.parts.append(f"</{tag}>")
        if tag in BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        text = data if self.in_pre else clean_text(data)
        if text:
            self.parts.append(escape_text(text))

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


def sanitize(html: str, link_map=None, image_map=None) -> str:
    parser = Sanitizer(link_map=link_map, image_map=image_map)
    parser.feed(html or "")
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"(?:<p>\s*</p>\s*)+", "", text)
    text = re.sub(r"(?:<figure>\s*</figure>\s*)+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + ("\n" if text.strip() else "")


def plain_text(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def absolutize(href: str, page_url: str) -> str:
    if not href or href.startswith(("#", "mailto:", "javascript:")):
        return href
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(page_url, href)


class Markdown(HTMLParser):
    """Convert a page's <main> into Markdown. Skips scripts and styles."""

    def __init__(self, page_url: str):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.parts: list[str] = []
        self.skip = 0
        self.in_pre = 0
        self.capture = None
        self.href = ""
        self.list_stack: list[tuple[str, int]] = []
        self.pending_dt = ""
        self.in_main = False
        self.seen_main = False

    def handle_starttag(self, tag, attrs):
        self._start(tag.lower(), attr_map(attrs))

    def handle_startendtag(self, tag, attrs):
        self._start(tag.lower(), attr_map(attrs))
        if tag.lower() not in VOID and self.skip:
            self.skip -= 1

    def _start(self, tag, attrs):
        if tag == "main":
            self.in_main = True
            self.seen_main = True
            return
        if self.seen_main and not self.in_main:
            return
        if not self.seen_main and tag in {"head", "header", "nav", "footer", "script", "style"}:
            if tag not in VOID:
                self.skip += 1
            return
        if self.skip:
            if tag not in VOID:
                self.skip += 1
            return
        if tag in {"script", "style", "svg", "button", "form", "canvas"}:
            if tag not in VOID:
                self.skip += 1
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self.parts.append("\n" + "#" * level + " ")
            return
        if tag == "p":
            self.parts.append("\n\n")
            return
        if tag == "br":
            self.parts.append("\n")
            return
        if tag == "hr":
            self.parts.append("\n\n---\n\n")
            return
        if tag in {"strong", "b"}:
            self.parts.append("**")
            return
        if tag in {"em", "i"}:
            self.parts.append("*")
            return
        if tag == "a":
            self.capture = []
            self.href = attrs.get("href", "")
            return
        if tag == "img":
            alt = clean_text(attrs.get("alt", "")).strip()
            src = absolutize(attrs.get("src", ""), self.page_url)
            if src and not banned_url(src):
                self.parts.append(f"\n\n![{alt}]({src})\n\n")
            return
        if tag == "ul":
            self.list_stack.append(("ul", 0))
            self.parts.append("\n")
            return
        if tag == "ol":
            self.list_stack.append(("ol", 0))
            self.parts.append("\n")
            return
        if tag == "li":
            if self.list_stack:
                kind, n = self.list_stack[-1]
                n += 1
                self.list_stack[-1] = (kind, n)
                indent = "  " * (len(self.list_stack) - 1)
                bullet = f"{n}. " if kind == "ol" else "- "
                self.parts.append(f"\n{indent}{bullet}")
            else:
                self.parts.append("\n- ")
            return
        if tag == "blockquote":
            self.parts.append("\n\n> ")
            return
        if tag == "pre":
            self.in_pre += 1
            self.parts.append("\n\n```\n")
            return
        if tag == "code" and not self.in_pre:
            self.parts.append("`")
            return
        if tag == "dt":
            self.pending_dt = ""
            self.capture = []
            return
        if tag == "dd":
            self.parts.append(f"\n\n**{self.pending_dt}:** ")
            return
        if tag == "figcaption":
            self.parts.append("\n\n*")
            return
        if tag == "model-viewer":
            alt = clean_text(attrs.get("alt", "")).strip()
            if alt:
                self.parts.append(f"\n\n{alt}\n\n")
            return
        if tag == "video":
            label = clean_text(attrs.get("aria-label", "Video")).strip() or "Video"
            self.parts.append(f"\n\n{label}\n\n")
            return
        if tag == "source" and attrs.get("src"):
            src = absolutize(attrs["src"], self.page_url)
            self.parts.append(f"\n\n[Media]({src})\n\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "main":
            self.in_main = False
            return
        if self.skip:
            self.skip -= 1
            return
        if self.seen_main and not self.in_main:
            return
        if tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "a" and self.capture is not None:
            text = "".join(self.capture).strip()
            href = absolutize(self.href, self.page_url)
            self.capture = None
            if text and href and not banned_url(href):
                self.parts.append(f"[{text}]({href})")
            elif text:
                self.parts.append(text)
        elif tag in {"ul", "ol"} and self.list_stack:
            self.list_stack.pop()
            self.parts.append("\n")
        elif tag == "pre" and self.in_pre:
            self.in_pre -= 1
            self.parts.append("\n```\n\n")
        elif tag == "code" and not self.in_pre:
            self.parts.append("`")
        elif tag == "dt" and self.capture is not None:
            self.pending_dt = "".join(self.capture).strip()
            self.capture = None
        elif tag == "figcaption":
            self.parts.append("*\n\n")
        elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "dd", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip or (self.seen_main and not self.in_main):
            return
        text = data if self.in_pre else clean_text(data)
        if self.capture is not None:
            self.capture.append(text)
            return
        self.parts.append(text)


def html_to_markdown(document: str, page_url: str) -> str:
    parser = Markdown(page_url if page_url.endswith("/") else page_url + "/")
    parser.feed(document)
    parser.close()
    text = "".join(parser.parts)
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def meta_content(document: str, name: str, prop: bool = False) -> str:
    attr = "property" if prop else "name"
    match = re.search(
        rf'<meta\s+{attr}="{re.escape(name)}"\s+content="([^"]*)"',
        document,
        re.I,
    )
    if not match:
        match = re.search(
            rf'<meta\s+content="([^"]*)"\s+{attr}="{re.escape(name)}"',
            document,
            re.I,
        )
    return match.group(1).strip() if match else ""


def tag_text(document: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", document, re.I | re.S)
    return plain_text(match.group(1)) if match else ""


def inner(document: str, tag: str, class_name: str = "") -> str:
    if class_name:
        match = re.search(
            rf'<{tag}\b[^>]*class="{re.escape(class_name)}"[^>]*>(.*?)</{tag}>',
            document,
            re.I | re.S,
        )
    else:
        match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", document, re.I | re.S)
    return match.group(1).strip() if match else ""
