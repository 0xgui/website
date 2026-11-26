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
    r"(?:https?:)?//(?:www\.)?(?:x\.com|twitter\.com|mobile\.twitter\.com|t\.co|nitter\.net|vxtwitter\.com)(?:/[^\s\"'<>)]*|\b)",
    re.I,
)
_CTRL = re.compile(r"[\x00-\x1f\x7f]+")
_SCHEME = re.compile(r"^([a-z][a-z0-9+.-]*):", re.I)

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}


def escape_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def escape_attr(value: str) -> str:
    return escape_text(value).replace('"', "&quot;")


def scrub_banned(value: str) -> str:
    """Drop banned URLs and the one place name this site does not publish (Leiria), preserving whitespace."""
    value = _BANNED_URL.sub("", value)
    value = re.sub(r"\bLeiria\b", "", value, flags=re.I)
    return value


def clean_text(value: str) -> str:
    """Drop banned URLs and the one place name this site does not publish (Leiria)."""
    value = scrub_banned(value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r" +([,.;:!?])", r"\1", value)
    return value


def _clean_url(url: str) -> str:
    return _CTRL.sub("", url or "").strip()


def _url_scheme(url: str) -> str:
    match = _SCHEME.match(url)
    return match.group(1).lower() if match else ""


def _allowed_href(url: str) -> bool:
    if not url or url.startswith("//"):
        return False
    return _url_scheme(url) in {"", "http", "https", "mailto"}


def _allowed_img_src(url: str) -> bool:
    if not url or url.startswith("//"):
        return False
    return _url_scheme(url) in {"", "https"}


def host_of(url: str) -> str:
    try:
        return urlparse(_clean_url(url)).hostname or ""
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
        self.skip_stack: list[str] = []
        self.stack: list[str] = []
        self.in_pre = 0

    def handle_starttag(self, tag, attrs):
        self._start(tag, attr_map(attrs), False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attr_map(attrs), True)

    def _start(self, tag, attrs, empty):
        tag = tag.lower()
        if self.skip_stack:
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        blob = f"{attrs.get('class', '')} {attrs.get('data-component-name', '')}".lower()
        if any(token in blob for token in ("subscription", "subscribe-widget", "share-dialog")):
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        if tag in self.DROP_TAGS:
            if tag == "iframe":
                self._youtube(attrs.get("src", ""))
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        if tag in self.UNWRAP or (tag == "a" and "image" in attrs.get("class", "")):
            return
        if tag == "h1":
            tag = "h2"
        if tag not in self.ALLOW:
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        if tag == "a":
            raw_attr = attrs.get("href", "")
            raw = _clean_url(raw_attr)
            mapped = (
                self.link_map.get(raw_attr)
                or self.link_map.get(raw)
                or self.link_map.get(raw.split("?")[0])
                or raw
            )
            href = _clean_url(mapped)
            if not _allowed_href(href) or banned_url(raw) or banned_url(href):
                return
            external = href.lower().startswith(("http://", "https://"))
            rel = ' target="_blank" rel="noopener"' if external else ""
            self.parts.append(f'<a href="{escape_attr(href)}"{rel}>')
            self.stack.append("a")
            return
        if tag == "img":
            raw_src = attrs.get("src", "")
            cleaned_src = _clean_url(raw_src)
            mapped_src = self.image_map.get(raw_src) or self.image_map.get(cleaned_src) or cleaned_src
            src = _clean_url(mapped_src)
            if not _allowed_img_src(src) or banned_url(cleaned_src) or banned_url(src):
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
        cleaned = _clean_url(src)
        try:
            parsed = urlparse(cleaned)
        except ValueError:
            return
        host = (parsed.hostname or "").lower()
        if parsed.scheme.lower() not in {"http", "https"} or host not in YOUTUBE_HOSTS:
            return
        match = re.search(r"(?:embed/|watch\?v=|youtu\.be/)([\w-]{6,})", cleaned)
        if not match:
            return
        href = f"https://www.youtube.com/watch?v={match.group(1)}"
        self.parts.append(f'<p><a href="{href}" target="_blank" rel="noopener">Watch the video</a></p>\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip_stack:
            if tag in self.skip_stack:
                while self.skip_stack:
                    if self.skip_stack.pop() == tag:
                        break
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
        if self.skip_stack:
            return
        text = scrub_banned(data) if self.in_pre else clean_text(data)
        if text:
            self.parts.append(escape_text(text))


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
        self.buffers: list[list[str]] = [self.parts]
        self.inline_stack: list[tuple[str, str]] = []
        self.skip_stack: list[str] = []
        self.in_pre = 0
        self.in_heading = 0
        self.list_stack: list[tuple[str, int]] = []
        self.pending_dt = ""
        self.in_main = False
        self.seen_main = False
        self.table_rows: list[list[str]] | None = None
        self.table_row: list[str] | None = None
        self.in_cell = 0

    def _emit(self, token: str) -> None:
        self.buffers[-1].append(token)

    def _push_capture(self, tag: str, payload: str = "") -> None:
        self.buffers.append([])
        self.inline_stack.append((tag, payload))

    def _close_inline(self, entry_tag: str, payload: str, text: str) -> None:
        if entry_tag in {"strong", "b", "em", "i"}:
            core = text.strip()
            if not core:
                if text:
                    self._emit(text)
                return
            lead = text[:len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            self._emit(f"{lead}{payload}{core}{payload}{trail}")
        elif entry_tag == "a":
            label = text.strip()
            href = absolutize(payload, self.page_url)
            if label and href and not banned_url(href):
                self._emit(f"[{label}]({href})")
            elif label:
                self._emit(label)
        elif entry_tag == "dt":
            self.pending_dt = text.strip()
        elif entry_tag in {"th", "td"}:
            if self.in_cell:
                self.in_cell -= 1
            cell = re.sub(r"\s+", " ", text).strip().replace("|", "\\|")
            if self.table_row is not None:
                self.table_row.append(cell)

    def _unwind_inline(self, tag: str) -> bool:
        if not any(item[0] == tag for item in self.inline_stack):
            return False
        while self.inline_stack:
            open_tag, payload = self.inline_stack.pop()
            text = "".join(self.buffers.pop())
            self._close_inline(open_tag, payload, text)
            if open_tag == tag:
                break
        return True

    def close(self):
        super().close()
        while self.inline_stack:
            open_tag, payload = self.inline_stack.pop()
            text = "".join(self.buffers.pop())
            self._close_inline(open_tag, payload, text)

    def handle_starttag(self, tag, attrs):
        self._start(tag.lower(), attr_map(attrs), False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag.lower(), attr_map(attrs), True)

    def _start(self, tag, attrs, empty=False):
        if tag == "main":
            self.skip_stack.clear()
            self.in_main = True
            self.seen_main = True
            return
        if self.seen_main and not self.in_main:
            return
        if not self.seen_main and tag in {"head", "header", "nav", "footer", "script", "style"}:
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        if self.skip_stack:
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        if tag in {"script", "style", "svg", "button", "form", "canvas"} or attrs.get("aria-hidden") == "true":
            if not empty and tag not in VOID:
                self.skip_stack.append(tag)
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self.in_heading += 1
            self._emit("\n" + "#" * level + " ")
            return
        if tag == "span" and self.in_heading and "sub" in attrs.get("class", "").split():
            buf = self.buffers[-1]
            line = "".join(buf).rsplit("\n", 1)[-1]
            if line.lstrip("# "):
                while buf and buf[-1].endswith((" ", "\t")):
                    buf[-1] = buf[-1].rstrip(" \t")
                    if not buf[-1]:
                        buf.pop()
                    else:
                        break
                self._emit(" · ")
            return
        if tag == "p":
            self._emit("\n\n")
            return
        if tag == "br":
            self._emit(" " if self.in_cell else "\n")
            return
        if tag == "hr":
            self._emit("\n\n---\n\n")
            return
        if tag in {"strong", "b"} and not self.in_pre:
            if not empty:
                self._push_capture(tag, "**")
            return
        if tag in {"em", "i"} and not self.in_pre:
            if not empty:
                self._push_capture(tag, "*")
            return
        if tag == "a":
            if not empty:
                self._push_capture("a", attrs.get("href", ""))
            return
        if tag == "img":
            alt = clean_text(attrs.get("alt", "")).strip()
            src = absolutize(attrs.get("src", ""), self.page_url)
            if src and not banned_url(src):
                self._emit(f"\n\n![{alt}]({src})\n\n")
            return
        if tag == "ul":
            self.list_stack.append(("ul", 0))
            self._emit("\n")
            return
        if tag == "ol":
            self.list_stack.append(("ol", 0))
            self._emit("\n")
            return
        if tag == "li":
            if self.list_stack:
                kind, n = self.list_stack[-1]
                n += 1
                self.list_stack[-1] = (kind, n)
                indent = "  " * (len(self.list_stack) - 1)
                bullet = f"{n}. " if kind == "ol" else "- "
                self._emit(f"\n{indent}{bullet}")
            else:
                self._emit("\n- ")
            return
        if tag == "blockquote":
            self._emit("\n\n> ")
            return
        if tag == "pre":
            self.in_pre += 1
            self._emit("\n\n```\n")
            return
        if tag == "code" and not self.in_pre:
            self._emit("`")
            return
        if tag == "dt":
            self.pending_dt = ""
            if not empty:
                self._push_capture("dt")
            return
        if tag == "dd":
            self._emit(f"\n\n**{self.pending_dt}:** ")
            return
        if tag == "figcaption":
            self._emit("\n\n*")
            return
        if tag == "table":
            self.table_rows = []
            self.table_row = None
            return
        if tag == "tr" and self.table_rows is not None:
            self.table_row = []
            return
        if tag in {"th", "td"} and self.table_rows is not None:
            if self.table_row is None:
                self.table_row = []
            if empty:
                self.table_row.append("")
            else:
                self.in_cell += 1
                self._push_capture(tag)
            return
        if tag == "model-viewer" or (tag == "div" and "viewer" in attrs.get("class", "").split()):
            alt = clean_text(attrs.get("alt", "") or attrs.get("aria-label", "")).strip()
            if alt:
                self._emit(f"\n\n{alt}\n\n")
            return
        if tag == "video":
            label = clean_text(attrs.get("aria-label", "Video")).strip() or "Video"
            self._emit(f"\n\n{label}\n\n")
            return
        if tag == "source" and attrs.get("src"):
            src = absolutize(attrs["src"], self.page_url)
            self._emit(f"\n\n[Media]({src})\n\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "main":
            self.in_main = False
            return
        if self.skip_stack:
            if tag in self.skip_stack:
                while self.skip_stack:
                    if self.skip_stack.pop() == tag:
                        break
            return
        if self.seen_main and not self.in_main:
            return
        if tag in {"strong", "b", "em", "i", "a", "dt", "th", "td"}:
            self._unwind_inline(tag)
        elif tag == "tr" and self.table_rows is not None:
            if self.table_row:
                self.table_rows.append(self.table_row)
            self.table_row = None
        elif tag == "table" and self.table_rows is not None:
            if self.table_row:
                self.table_rows.append(self.table_row)
                self.table_row = None
            if self.table_rows:
                ncols = max(len(row) for row in self.table_rows)
                padded = [row + [""] * (ncols - len(row)) for row in self.table_rows]
                lines = [
                    "| " + " | ".join(padded[0]) + " |",
                    "| " + " | ".join("---" for _ in range(ncols)) + " |",
                ]
                for row in padded[1:]:
                    lines.append("| " + " | ".join(row) + " |")
                self._emit("\n\n" + "\n".join(lines) + "\n\n")
            self.table_rows = None
        elif tag in {"ul", "ol"} and self.list_stack:
            self.list_stack.pop()
            self._emit("\n")
        elif tag == "pre" and self.in_pre:
            self.in_pre -= 1
            self._emit("\n```\n\n")
        elif tag == "code" and not self.in_pre:
            self._emit("`")
        elif tag == "figcaption":
            self._emit("*\n\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            if self.in_heading:
                self.in_heading -= 1
            self._emit("\n")
        elif tag in {"p", "blockquote", "dd"}:
            self._emit("\n")

    def handle_data(self, data):
        if self.skip_stack or (self.seen_main and not self.in_main):
            return
        if self.table_rows is not None and not self.in_cell:
            return
        text = scrub_banned(data) if self.in_pre else clean_text(data)
        if text:
            self._emit(text)


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
