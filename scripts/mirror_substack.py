#!/usr/bin/env python3
"""Mirror public Binary Paths essays onto /writing/<slug>/.

Zero third-party packages. Idempotent: a second run with the same source
writes nothing. A missing, empty, malformed, or challenge response never
deletes or blanks an essay that is already on disk.

    python3 scripts/mirror_substack.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hashlib
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import replace
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser

from scripts.build_agent import apply as apply_agent
from scripts.build_agent import links_block
from scripts.feeds import (
    ChallengeError,
    EmptyFeed,
    FeedError,
    MalformedFeed,
    Post,
    looks_like_challenge,
    post_from_mapping,
    posts_from_rss,
)
from scripts.htmltext import (
    BLOCKS,
    attr_map,
    banned_url,
    clean_text,
    escape_attr,
    escape_text,
    inner,
    meta_content,
    plain_text,
    sanitize,
    tag_text,
)

ROOT = Path(__file__).resolve().parents[1]  # noqa: F811 — Path imported above
# Substack answers 403 to the default Python client and to short bot names from
# GitHub-hosted runners. A normal browser User-Agent is the request it accepts.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HOME_LIMIT = 4
SITE = "https://silvags.com"
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
FORBIDDEN = re.compile(
    r"leiria|https?://(?:www\.)?(?:x\.com|twitter\.com)|https?://t\.co/",
    re.I,
)
# Sign-off tails and leftover Twitter sentences, applied to essay bodies.
_SPACE = r"(?:\s|&nbsp;|&#160;)+"
_SIGNOFF_X_RE = re.compile(
    rf"(?i){_SPACE}or{_SPACE}(?:(?P<playground>the{_SPACE}digital{_SPACE}playground{_SPACE}\()|on{_SPACE})?"
    rf"(?:(?:X|Twitter)\b|<(?P<tag>em|strong|b|i|span)>(?:X|Twitter)</(?P=tag)>)(?(playground)\))"
)
_TWITTER_WORD_RE = re.compile(r"(?i)\bTwitter\b")
_SENTENCE_RE = re.compile(r".+?(?:[.!?]+(?=\s|$)|$)", re.S)
LIST_RE = re.compile(
    r"<!-- mirror:posts -->.*?<!-- /mirror:posts -->|<ul class=\"posts\" id=\"articles\">.*?</ul>",
    re.S,
)
FEED_SCRIPT_RE = re.compile(
    r"\n<script>\s*// Binary Paths via rss\.silvags\.com.*?</script>",
    re.S,
)
IMAGE_MAX = 1_000_000
IMAGE_TARGET = 500_000
# Rewritten after a successful fetch when the file is missing or older than this.
STAMP_EVERY = 24 * 60 * 60
# A failed fetch stays quiet while the newest good data is younger than this.
QUIET_AFTER = 48 * 60 * 60
LAST_GOOD = "writing/last-good.txt"
# workers.dev is outside the silvags.com zone. The account subdomain is zer0hex.
DEFAULT_WORKERS_DEV = "https://rss-worker.zer0hex.workers.dev/raw.xml"
RSS_HOST_SNAPSHOT = "https://rss.silvags.com/raw.xml"


def format_date(post: Post) -> str:
    when = post.published
    return f"{MONTHS[when.month - 1]} {when.day}, {when.year}"


class _TextSpans(HTMLParser):
    """Collect text node offsets, grouped into blocks of visible text."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self.html = html
        self.lines = [0, *(match.end() for match in re.finditer("\n", html))]
        self.blocks: list[list[tuple[int, int]]] = [[]]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if (tag in BLOCKS or tag == "br") and self.blocks[-1]:
            self.blocks.append([])

    def handle_data(self, data):
        line, column = self.getpos()
        start = self.lines[line - 1] + column
        self.blocks[-1].append((start, start + len(data)))

    def handle_entityref(self, name):
        self._entity("&" + name)

    def handle_charref(self, name):
        self._entity("&#" + name)

    def _entity(self, raw):
        line, column = self.getpos()
        end = self.lines[line - 1] + column + len(raw)
        self.handle_data(raw + ";" if self.html[end:end + 1] == ";" else raw)


def _without_spans(html: str, spans: list[tuple[int, int]]) -> str:
    parts = []
    pos = 0
    for start, end in spans:
        parts.append(html[pos:start])
        pos = end
    parts.append(html[pos:])
    return "".join(parts)


def _drop_twitter_sentences(html: str) -> str:
    """Drop Twitter sentences across inline markup by editing only their text."""
    removed = []
    for block in _TextSpans(html).blocks:
        text = "".join(html[start:end] for start, end in block)
        sentences = [
            match.span() for match in _SENTENCE_RE.finditer(text)
            if _TWITTER_WORD_RE.search(unescape(match.group()))
        ]
        offset = 0
        for start, end in block:
            for left, right in sentences:
                lo = max(offset, left)
                hi = min(offset + end - start, right)
                if lo < hi:
                    removed.append((start + lo - offset, start + hi - offset))
            offset += end - start
    return _without_spans(html, removed)


def strip_x_mentions(html: str) -> str:
    """Remove X/Twitter sign-off alternatives and any leftover Twitter sentence.

    'You can find me on LinkedIn or X.' becomes 'You can find me on LinkedIn.'
    Also covers 'or on X', 'or the digital playground (X|Twitter)', and a
    body sentence that names Twitter. Idempotent. Does not touch a lone 'X'
    outside those patterns (OS X, 10x, catch(x)).
    """
    spans = [span for block in _TextSpans(html).blocks for span in block]
    alternatives = [
        match.span() for match in _SIGNOFF_X_RE.finditer(html)
        if any(start <= match.start() < end for start, end in spans)
    ]
    text = _without_spans(html, alternatives)
    return _drop_twitter_sentences(text)


def http_get(url: str, accept: str, timeout: int = 25, attempts: int = 3, sleep=time.sleep):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": accept,
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.headers.get("content-type", ""), response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp else b""
            ctype = exc.headers.get("content-type", "") if exc.headers else ""
            text = raw.decode("utf-8", "replace")
            detail = " ".join(text[:180].split())
            if looks_like_challenge(exc.code, text, ctype):
                last = ChallengeError(f"{url} returned {exc.code} ({ctype}) {detail}")
            else:
                last = FeedError(f"{url} returned {exc.code} ({ctype}) {detail}")
        except Exception as exc:  # noqa: BLE001 — network failures become FeedError
            last = FeedError(f"{url} failed: {exc}")
        if attempt + 1 < attempts:
            sleep(2 ** attempt)
    assert last is not None
    raise last


def _decode(status: int, ctype: str, body: bytes, url: str) -> str:
    text = body.decode("utf-8", "replace")
    if status >= 400 or looks_like_challenge(status, text, ctype):
        if looks_like_challenge(status, text, ctype) or status in {401, 403, 429, 503}:
            raise ChallengeError(f"{url} returned {status}")
        raise FeedError(f"{url} returned {status}")
    return text


def default_snapshot_urls() -> list[tuple[str, str]]:
    """workers.dev first. The silvags.com zone's bot settings do not apply there."""
    found = []
    dev = os.environ.get("WORKERS_DEV_SNAPSHOT", DEFAULT_WORKERS_DEV).strip()
    if dev:
        if not dev.endswith("/raw.xml"):
            dev = dev.rstrip("/") + "/raw.xml"
        found.append(("workers-dev", dev))
    found.append(("rss-host", RSS_HOST_SNAPSHOT))
    return found


def _posts_from_snapshot(get, url: str) -> list[Post]:
    text = _decode(*get(
        url,
        "application/rss+xml, application/xml, text/xml",
    ), url)
    return posts_from_rss(text)


def fetch_posts(get=http_get, snapshots=None) -> list[Post]:
    """Posts API, archive, RSS, then the worker's stored snapshot.

    A challenge, empty body, or malformed snapshot is one failed source.
    The next source is tried. Nothing is deleted.
    """
    errors = []
    sources: list[tuple[str, object]] = [
        ("api", lambda: _posts_api(get)),
        ("archive", lambda: _posts_archive(get)),
        ("rss", lambda: posts_from_rss(_decode(*get(
            "https://binarypaths.substack.com/feed",
            "application/rss+xml, application/xml, text/xml",
        ), "https://binarypaths.substack.com/feed"))),
    ]
    chosen = default_snapshot_urls() if snapshots is None else list(snapshots)
    for name, url in chosen:
        sources.append((name, lambda url=url: _posts_from_snapshot(get, url)))
    for name, fn in sources:
        try:
            posts = fn()
            if not posts:
                raise EmptyFeed(f"{name} returned no posts")
            return posts
        except FeedError as exc:
            errors.append(f"{name}: {exc}")
    raise FeedError("all feed sources failed:\n" + "\n".join(errors))


def _parse_stamp(text: str) -> datetime:
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    found = datetime.fromisoformat(text)
    if found.tzinfo is None:
        found = found.replace(tzinfo=timezone.utc)
    return found.astimezone(timezone.utc)


def last_good_at(root: Path) -> datetime | None:
    path = root / LAST_GOOD
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        return _parse_stamp(text)
    except ValueError:
        return None


def outage_is_loud(root: Path, now: datetime | None = None) -> bool:
    """True when no path worked and the newest good data is missing or >= 48h old."""
    stamp = last_good_at(root)
    if stamp is None:
        return True
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc) - stamp).total_seconds() >= QUIET_AFTER


def note_success(root: Path, now: datetime | None = None) -> bool:
    """Record a successful fetch, at most once per 24h, so a no-op run stays quiet."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    stamp = last_good_at(root)
    if stamp is not None and (now - stamp).total_seconds() < STAMP_EVERY:
        return False
    path = root / LAST_GOOD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(now.strftime("%Y-%m-%dT%H:%M:%SZ") + "\n", encoding="utf-8")
    return True


def run_mirror(root: Path, get=http_get, now: datetime | None = None, snapshots=None) -> int:
    try:
        posts = fetch_posts(get, snapshots=snapshots)
        changed = apply_mirror(root, posts)
        if note_success(root, now):
            changed.append(LAST_GOOD)
    except FeedError as exc:
        if outage_is_loud(root, now):
            print(f"mirror failed: {exc}", file=sys.stderr)
            return 1
        print(
            "mirror sources failed; newest good data is under 48h, so this run stays quiet:\n"
            + str(exc)
        )
        return 0
    if changed:
        print(f"updated {len(changed)} file(s)")
    else:
        print("mirror is up to date")
    return 0


def _collect(rows: list[dict], seen: dict[str, Post]) -> None:
    for row in rows:
        post = post_from_mapping(row, source="api")
        seen.setdefault(post.slug, post)


def _posts_api(get) -> list[Post]:
    seen: dict[str, Post] = {}
    cursor = None
    for page in range(20):
        url = "https://binarypaths.substack.com/api/v1/posts?limit=20"
        if cursor:
            url += "&cursor=" + urllib.request.quote(str(cursor))
        text = _decode(*get(url, "application/json"), url)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedFeed("api json is not valid") from exc
        rows = payload.get("posts") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise MalformedFeed("api posts is not a list")
        if not rows and page == 0:
            raise EmptyFeed("api returned no posts")
        if not rows:
            break
        _collect(rows, seen)
        cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
        if not cursor:
            break
    else:
        raise FeedError("api still had pages after 20 requests; refusing to truncate")
    return list(seen.values())


def _posts_archive(get) -> list[Post]:
    seen: dict[str, Post] = {}
    offset = 0
    for _page in range(20):
        url = f"https://binarypaths.substack.com/api/v1/archive?sort=new&limit=20&offset={offset}"
        text = _decode(*get(url, "application/json"), url)
        try:
            rows = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedFeed("archive json is not valid") from exc
        if isinstance(rows, dict):
            rows = rows.get("posts") or rows.get("items")
        if not isinstance(rows, list):
            raise MalformedFeed("archive is not a list")
        if not rows and offset == 0:
            raise EmptyFeed("archive returned no posts")
        if not rows:
            break
        _collect(rows, seen)
        offset += len(rows)
        if len(rows) < 20:
            break
    else:
        raise FeedError("archive still had pages after 20 requests; refusing to truncate")
    return list(seen.values())


class _Images(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            src = attr_map(attrs).get("src", "")
            if src:
                self.found.append(src)


def image_identity(url: str) -> str:
    if "/image/fetch/" in url:
        return urllib.request.unquote(url.split("/image/fetch/", 1)[1].split("/", 1)[-1])
    return url


def origin_url(url: str) -> str:
    if "/image/fetch/" not in url:
        return url
    rest = url.split("/image/fetch/", 1)[1]
    origin = rest.split("/", 1)[-1]
    return urllib.request.unquote(origin)


def tune_image_url(url: str) -> str:
    if "substackcdn.com/image/fetch/" not in url:
        return url
    pre, _, rest = url.partition("/image/fetch/")
    params, _, origin = rest.partition("/")
    parts = []
    saw_w = saw_f = False
    for part in params.split(","):
        if part.startswith("w_"):
            parts.append("w_1600")
            saw_w = True
        elif part.startswith("f_"):
            parts.append("f_webp")
            saw_f = True
        elif part.startswith("q_"):
            parts.append("q_80")
        else:
            parts.append(part)
    if not saw_w:
        parts.append("w_1600")
    if not saw_f:
        parts.append("f_webp")
    return f"{pre}/image/fetch/{','.join(parts)}/{origin}"


def _is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _webp_chunks(data: bytes):
    offset = 12
    while offset + 8 <= len(data):
        tag = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        end = offset + 8 + size
        if end > len(data):
            break
        yield tag, data[offset + 8:end]
        offset = end + (size % 2)


def _exif_orientation(data: bytes) -> int:
    data = data.removeprefix(b"Exif\0\0")
    if data.startswith(b"II*\0"):
        order = "little"
    elif data.startswith(b"MM\0*"):
        order = "big"
    else:
        return 1
    start = int.from_bytes(data[4:8], order)
    count = int.from_bytes(data[start:start + 2], order)
    for offset in range(start + 2, min(len(data) - 11, start + 2 + count * 12), 12):
        tag = int.from_bytes(data[offset:offset + 2], order)
        field_type = int.from_bytes(data[offset + 2:offset + 4], order)
        values = int.from_bytes(data[offset + 4:offset + 8], order)
        if (tag, field_type, values) == (0x112, 3, 1):
            orientation = int.from_bytes(data[offset + 8:offset + 10], order)
            return orientation if 1 <= orientation <= 8 else 1
    return 1


def _image_metadata(data: bytes) -> tuple[bytes, int]:
    if _is_webp(data):
        chunks = dict(_webp_chunks(data))
        return chunks.get(b"ICCP", b""), _exif_orientation(chunks.get(b"EXIF", b""))
    icc = b""
    orientation = 1
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        while offset + 12 <= len(data):
            size = int.from_bytes(data[offset:offset + 4], "big")
            tag = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + size]
            if tag == b"iCCP" and b"\0\0" in payload:
                try:
                    decoder = zlib.decompressobj()
                    profile = decoder.decompress(payload.split(b"\0\0", 1)[1], IMAGE_MAX)
                    if decoder.eof:
                        icc = profile
                except zlib.error:
                    pass
            elif tag == b"eXIf":
                orientation = _exif_orientation(payload)
            offset += 12 + size
    elif data.startswith(b"\xff\xd8"):
        offset = 2
        profile_parts = {}
        total = 0
        while data[offset:offset + 1] == b"\xff":
            marker = data[offset + 1:offset + 2]
            if marker == b"\xff":
                offset += 1
                continue
            if marker in (b"\xda", b"\xd9"):
                break
            size = int.from_bytes(data[offset + 2:offset + 4], "big")
            if size < 2 or offset + 2 + size > len(data):
                break
            payload = data[offset + 4:offset + 2 + size]
            if marker == b"\xe1" and payload.startswith(b"Exif\0\0"):
                orientation = _exif_orientation(payload)
            elif marker == b"\xe2" and payload.startswith(b"ICC_PROFILE\0") and len(payload) >= 14:
                index, total = payload[12:14]
                profile_parts[index] = payload[14:]
            offset += 2 + size
        if total and len(profile_parts) == total and all(i in profile_parts for i in range(1, total + 1)):
            icc = b"".join(profile_parts[i] for i in range(1, total + 1))
    return icc, orientation


def _webp_with_metadata(data: bytes, icc: bytes, orientation: int) -> bytes:
    chunks = list(_webp_chunks(data))
    extended = next((body for tag, body in chunks if tag == b"VP8X"), b"")
    original_flags = int.from_bytes(extended[:1], "little")
    if orientation == 1 and not icc and not original_flags & 0x08 and not any(tag == b"EXIF" for tag, _ in chunks):
        return data
    size = webp_size(data)
    if size is None:
        raise FeedError("could not read WebP dimensions")
    width, height = size
    # VP8X flags announce ICC, alpha and EXIF chunks to the decoder.
    flags = original_flags & ~0x28
    if any(tag == b"VP8L" and len(body) >= 5 and body[4] & 0x10 for tag, body in chunks):
        flags |= 0x10
    if icc:
        flags |= 0x20
    if orientation != 1:
        flags |= 0x08
    canvas = bytes([flags]) + b"\0" * 3 + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    output = [(b"VP8X", canvas)]
    if icc:
        output.append((b"ICCP", icc))
    output.extend((tag, body) for tag, body in chunks if tag not in (b"VP8X", b"ICCP", b"EXIF", b"XMP "))
    if orientation != 1:
        # Minimal little-endian TIFF with just the orientation entry.
        exif = bytes.fromhex("49492a000800000001001201030001000000") + bytes([orientation]) + b"\0" * 7
        output.append((b"EXIF", exif))
    output.extend((tag, body) for tag, body in chunks if tag == b"XMP ")
    riff = b"WEBP" + b"".join(
        tag + len(body).to_bytes(4, "little") + body + b"\0" * (len(body) % 2)
        for tag, body in output
    )
    return b"RIFF" + len(riff).to_bytes(4, "little") + riff


def _ffmpeg(args: list[str]) -> None:
    ffmpeg = _which("ffmpeg")
    if not ffmpeg:
        raise FeedError("ffmpeg is not installed, so an image could not be optimized")
    import subprocess
    result = subprocess.run([ffmpeg, *args], check=False, capture_output=True)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace")[-400:]
        raise FeedError(f"ffmpeg failed: {detail}")


def gif_to_webm(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        src = folder / "in.gif"
        dest = folder / "out.webm"
        src.write_bytes(data)
        bitrate = 200
        last = b""
        while bitrate >= 80:
            _ffmpeg([
                "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                "-vf", "scale='min(800,iw)':-2", "-c:v", "libvpx-vp9",
                "-b:v", f"{bitrate}k", "-an", str(dest),
            ])
            if dest.exists():
                last = dest.read_bytes()
                if len(last) <= IMAGE_TARGET:
                    return last
            bitrate -= 40
        if last and len(last) <= IMAGE_MAX:
            return last
    raise FeedError("could not compress a gif under 1MB")


def _encode_webps(data: bytes, scales: dict[int, str], quality: int) -> dict[int, bytes]:
    icc, orientation = _image_metadata(data)
    # WebP stores its display orientation separately from the encoded pixels.
    autorotate = ["-noautorotate"] if orientation != 1 else []
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        src = folder / "in"
        dest = folder / "out.webp"
        src.write_bytes(data)
        for width, scale in scales.items():
            _ffmpeg([
                "-y", "-hide_banner", "-loglevel", "error", *autorotate, "-i", str(src),
                "-vf", scale, "-frames:v", "1", "-map_metadata", "-1",
                "-c:v", "libwebp", "-quality", str(quality), str(dest),
            ])
            results[width] = _webp_with_metadata(dest.read_bytes(), icc, orientation)
    return results


def to_webp(data: bytes) -> bytes:
    if _is_webp(data) and len(data) <= IMAGE_MAX:
        return _webp_with_metadata(data, *_image_metadata(data))
    scale = "scale=-1:'min(1600,ih)'" if _image_metadata(data)[1] >= 5 else "scale='min(1600,iw)':-1"
    for quality in (78, 63, 48):
        result = _encode_webps(data, {1600: scale}, quality)[1600]
        if len(result) <= IMAGE_TARGET:
            return result
    if len(result) <= IMAGE_MAX:
        return result
    raise FeedError("could not compress an image under 1MB")


def _responsive_webps(data: bytes) -> dict[int, bytes]:
    size = _display_size(data)
    animated = any(tag == b"ANIM" for tag, _ in _webp_chunks(data))
    if not size or animated:
        return {}
    rotated = _image_metadata(data)[1] >= 5
    scales = {
        width: f"scale=-1:{width}" if rotated else f"scale={width}:-1"
        for width in (800, 1200) if width < size[0]
    }
    if not scales:
        return {}
    return {
        width: variant for width, variant in _encode_webps(data, scales, 78).items()
        if len(variant) < len(data) and (_display_size(variant) or (0, 0))[0] == width
    }


def _which(name: str) -> str | None:
    from shutil import which
    return which(name)


def prepare_images(post: Post, fetch_bytes, previous: dict) -> tuple[dict[str, str], dict[str, bytes], str, str]:
    """Return remote-to-local paths, media bytes, body HTML with cover, and manifest JSON."""
    parser = _Images()
    parser.feed(post.body_html or "")
    ordered = []
    seen = set()
    for src in parser.found:
        if not src.startswith("https://") or banned_url(src):
            continue
        ident = image_identity(src)
        if ident in seen:
            continue
        seen.add(ident)
        ordered.append(src)
    if (
        post.cover_url.startswith("https://")
        and not banned_url(post.cover_url)
        and image_identity(post.cover_url) not in seen
    ):
        ordered.insert(0, post.cover_url)
    image_map: dict[str, str] = {}
    ident_local: dict[str, str] = {}
    files: dict[str, bytes] = {}
    manifest = {"images": []}
    old = previous.get("images") or []
    old_by_hash = {item.get("source_sha256"): item for item in old if isinstance(item, dict)}
    for index, src in enumerate(ordered, start=1):
        tuned = tune_image_url(src)
        origin = origin_url(src)
        animated = origin.lower().endswith(".gif")
        data = fetch_bytes(origin if animated else tuned)
        digest = hashlib.sha256(data).hexdigest()
        ext = "webm" if animated or data[:3] == b"GIF" else "webp"
        name = f"{index:02d}.{ext}"
        local = f"images/{name}"
        image_map[src] = local
        ident_local[image_identity(src)] = local
        if src != tuned:
            image_map[tuned] = local
        prior = old_by_hash.get(digest, {})
        prior_bytes = post_dir_file(previous, name) if prior.get("file") == name else None
        reusable = prior_bytes is not None and 0 < len(prior_bytes) <= IMAGE_MAX
        try:
            if ext == "webm":
                media = prior_bytes if reusable else gif_to_webm(data)
            else:
                # Older manifests predate metadata preservation and responsive WebPs.
                media = to_webp(prior_bytes if reusable and "variants" in prior else data)
        except FeedError as exc:
            raise FeedError(f"{post.slug} {origin} ({len(data)} bytes, {data[:16]!r}): {exc}") from exc
        if len(media) > IMAGE_MAX:
            raise FeedError(f"{post.slug} image {name} is {len(media)} bytes")
        files[local] = media
        item = {"file": name, "source_sha256": digest}
        if ext == "webp":
            cached = prior.get("variants") if media == prior_bytes else None
            if isinstance(cached, list) and all(post_dir_file(previous, variant) for variant in cached):
                variants = {variant: post_dir_file(previous, variant) for variant in cached}
            else:
                variants = {f"{index:02d}-{width}w.webp": variant for width, variant in _responsive_webps(media).items()}
            files.update({f"images/{variant}": content for variant, content in variants.items()})
            item["variants"] = list(variants)
        manifest["images"].append(item)
    for src in parser.found:
        ident = image_identity(src)
        if ident in ident_local:
            image_map[src] = ident_local[ident]
    body = post.body_html or ""
    if post.cover_url and post.cover_url in image_map and post.cover_url not in parser.found:
        local = image_map[post.cover_url]
        body = f'<figure><img src="{escape_attr(local)}" alt=""></figure>\n' + body
        # already mapped; sanitizer will see the original cover only if we injected local src
    return image_map, files, body, json.dumps(manifest, indent=2) + "\n"


def webp_size(data: bytes) -> tuple[int, int] | None:
    """Width and height from a WebP header (VP8, VP8L or VP8X), or None."""
    if not _is_webp(data) or len(data) < 30:
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if chunk == b"VP8L" and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    return None


def _display_size(data: bytes) -> tuple[int, int] | None:
    size = webp_size(data)
    if size and _image_metadata(data)[1] >= 5:
        return size[1], size[0]
    return size


IMG_TAG_RE = re.compile(r'<img src="([^"]+)" alt="([^"]*)">')


def size_images(body: str, files: dict[str, bytes]) -> str:
    """Give each local <img> its intrinsic size (no layout shift) and lazy-load all but the first."""
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        count += 1
        src, alt = match.group(1), match.group(2)
        size = _display_size(files.get(src, b""))
        dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
        responsive = ""
        if size:
            candidates = []
            for width in (800, 1200):
                variant = f"{src[:-len('.webp')]}-{width}w.webp"
                if variant in files:
                    candidates.append(f"{variant} {width}w")
            if candidates:
                candidates.append(f"{src} {size[0]}w")
                responsive = f' srcset="{", ".join(candidates)}" sizes="(max-width: 600px) 100vw, 544px"'
        lazy = ' loading="lazy"' if count > 1 else ""
        return f'<img src="{src}" alt="{alt}"{dims}{responsive}{lazy} decoding="async">'

    return IMG_TAG_RE.sub(repl, body)


def post_dir_file(previous: dict, name: str) -> bytes | None:
    raw = previous.get("_bytes", {}).get(name)
    return raw


def load_saved(path: Path) -> tuple[Post, int, dict]:
    html = path.read_text(encoding="utf-8")
    slug = path.parent.name
    title = tag_text(html, "h1")
    canonical = ""
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
    if match:
        canonical = match.group(1)
    if not title or not canonical:
        raise FeedError(f"refusing to continue: {path} is missing a title or canonical")
    kind = meta_content(html, "mirror-kind") or "full"
    description = meta_content(html, "description")
    stamp = "1970-01-01T00:00:00Z"
    time_match = re.search(r'<time\b[^>]*datetime="([^"]+)"', html)
    if time_match:
        stamp = time_match.group(1)
        if "T" not in stamp:
            stamp += "T00:00:00Z"
    body = inner(html, "article", "post")
    post = post_from_mapping({
        "slug": slug,
        "title": title,
        "canonical_url": canonical,
        "post_date": stamp,
        "description": description,
        "body_html": body,
        "kind": kind,
        "id": meta_content(html, "mirror-id"),
    }, source="api")
    manifest = {}
    media = path.parent / "media.json"
    file_bytes = {}
    if media.exists():
        try:
            manifest = json.loads(media.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FeedError(f"{media} is not valid json") from exc
        for item in manifest.get("images") or []:
            for name in [item.get("file", ""), *item.get("variants", [])]:
                image = path.parent / "images" / name
                if image.is_file():
                    file_bytes[name] = image.read_bytes()
    manifest["_bytes"] = file_bytes
    return post, len(plain_text(body)), manifest


def discover(root: Path) -> dict[str, tuple[Post, int, dict]]:
    writing = root / "writing"
    saved = {}
    if not writing.exists():
        return saved
    for path in sorted(writing.glob("*/index.html")):
        saved[path.parent.name] = load_saved(path)
    return saved


def merge(saved: dict, fetched: list[Post]) -> tuple[list[Post], set[str]]:
    """Return posts to show, and slugs that must be re-rendered.

    Slugs already on disk are never dropped. A full essay is never replaced
    by a stub or by a much shorter body.
    """
    chosen: dict[str, Post] = {}
    render: set[str] = set()
    for post in fetched:
        old = saved.get(post.slug)
        if old:
            previous, old_len, _manifest = old
            new_len = len(plain_text(post.body_html if post.kind == "full" else post.description))
            if previous.kind == "full" and (post.kind != "full" or (old_len and new_len < int(old_len * 0.6))):
                chosen[post.slug] = previous
                continue
            if not post.post_id and previous.post_id:
                # RSS has no post id; keep the one the API gave earlier.
                post = replace(post, post_id=previous.post_id)
        chosen[post.slug] = post
        render.add(post.slug)
    for slug, (previous, _length, _manifest) in saved.items():
        if slug not in chosen:
            chosen[slug] = previous
    posts = sorted(chosen.values(), key=lambda post: (post.published, post.slug), reverse=True)
    return posts, render


def sibling_links(posts: list[Post], here: str) -> dict[str, str]:
    mapping = {}
    for post in posts:
        if post.slug == here:
            continue
        mapping[post.canonical] = f"../{post.slug}/"
        mapping[post.canonical + "/"] = f"../{post.slug}/"
    return mapping


def article_template(writing_html: str) -> str:
    html = FEED_SCRIPT_RE.sub("", writing_html)
    html = re.sub(r"<!-- agent:links -->.*?<!-- /agent:links -->\n?", "", html, flags=re.S)
    html = re.sub(r"<!-- agent:ld -->.*?<!-- /agent:ld -->\n?", "", html, flags=re.S)
    if "../../" in html:
        raise FeedError("writing/index.html already contains ../../ so it cannot be the article template")
    return html.replace("../", "../../")


def _set_attr_meta(html: str, attr: str, key: str, content: str) -> str:
    pattern = rf'<meta\s+{attr}="{re.escape(key)}"\s+content="[^"]*"\s*/?>'
    repl = f'<meta {attr}="{key}" content="{escape_attr(content)}">'
    if re.search(pattern, html):
        return re.sub(pattern, lambda _: repl, html, count=1)
    return html.replace("</head>", repl + "\n</head>", 1)


def essay_cover(body: str, page_url: str) -> str | None:
    """Absolute URL of the essay's first local image (the Substack cover when there is one), for link previews."""
    match = re.search(r'<img src="(images/[^"]+)"', body or "")
    return page_url + match.group(1) if match else None


def render_article(template: str, post: Post, body: str, *, root: Path, files: dict[str, bytes]) -> str:
    local = f"{SITE}/writing/{post.slug}/"
    title = clean_text(post.title).strip()
    description = clean_text(post.description).strip()
    if len(description) > 180:
        description = description[:177].rsplit(" ", 1)[0] + "…"
    html = template
    html = re.sub(r"<title>.*?</title>", f"<title>{escape_text(title)} · {escape_text('Guilherme Silva')}</title>", html, count=1, flags=re.S)
    html = _set_attr_meta(html, "name", "description", description)
    html = _set_attr_meta(html, "property", "og:title", title)
    html = _set_attr_meta(html, "property", "og:description", description)
    html = _set_attr_meta(html, "property", "og:url", post.canonical)
    html = _set_attr_meta(html, "property", "og:type", "article")
    html = _set_attr_meta(html, "property", "og:site_name", "Guilherme Silva")
    html = _set_attr_meta(html, "property", "og:locale", "en_GB")
    html = _set_attr_meta(html, "name", "twitter:card", "summary_large_image")
    html = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*">',
        f'<link rel="canonical" href="{escape_attr(post.canonical)}">',
        html,
        count=1,
    )
    display = format_date(post)
    canonical = escape_attr(post.canonical)
    if post.kind == "stub":
        excerpt = escape_text(clean_text(post.body_html or post.description).strip())
        article = (
            f"<h1>{escape_text(title)}</h1>\n"
            f'<p class="meta"><time datetime="{post.date_key()}">{display}</time> · '
            f'Originally published on <a href="{canonical}" target="_blank" rel="noopener">Binary Paths</a></p>\n'
            "<p>This is a preview. The full post is on Binary Paths.</p>\n"
            f"<blockquote><p>{excerpt}</p></blockquote>\n"
            f'<p class="more"><a href="{canonical}" target="_blank" rel="noopener">Continue reading on Binary Paths</a></p>\n'
        )
    else:
        article = (
            f"<h1>{escape_text(title)}</h1>\n"
            f'<p class="meta"><time datetime="{post.date_key()}">{display}</time> · '
            f'Originally published on <a href="{canonical}" target="_blank" rel="noopener">Binary Paths</a></p>\n'
            f'<article class="post">\n{body.strip()}\n</article>\n'
        )
    html = re.sub(r"<main>.*?</main>", lambda _: "<main>\n" + article + "</main>", html, count=1, flags=re.S)
    cover = essay_cover(body, local)
    dimensions = None
    cover_alt = title
    og = root / "og"
    preferred = og / f"essay-{post.slug}-v1.webp"
    custom = preferred if preferred.is_file() else next(
        (path for path in sorted(og.glob(f"essay-{post.slug}-*.webp")) if path.is_file()), None
    )
    if custom:
        cover = SITE + "/" + custom.relative_to(root).as_posix()
        dimensions = (1200, 630)
    elif cover:
        dimensions = _display_size(files.get(cover.removeprefix(local), b""))
        match = re.search(r'<img src="images/[^"]+" alt="([^"]*)"', body)
        if match and match[1].strip():
            cover_alt = unescape(match[1])
    else:
        cover = unescape(meta_content(template, "og:image", prop=True))
        cover_alt = unescape(meta_content(template, "og:image:alt", prop=True)) or title
        if cover.startswith(SITE + "/"):
            fallback = root / cover.removeprefix(SITE + "/")
            if fallback.is_file():
                dimensions = _display_size(fallback.read_bytes())
    if cover:
        html = _set_attr_meta(html, "property", "og:image", cover)
        if dimensions:
            html = _set_attr_meta(html, "property", "og:image:width", str(dimensions[0]))
            html = _set_attr_meta(html, "property", "og:image:height", str(dimensions[1]))
        if cover.endswith(".webp"):
            html = _set_attr_meta(html, "property", "og:image:type", "image/webp")
        html = _set_attr_meta(html, "property", "og:image:alt", cover_alt)
        html = _set_attr_meta(html, "name", "twitter:image:alt", cover_alt)
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": description,
        "datePublished": post.atom_time(),
        "author": {"@type": "Person", "name": "Guilherme Silva", "url": SITE + "/"},
        "mainEntityOfPage": post.canonical,
        "url": local,
        "isBasedOn": post.canonical,
    }
    if cover:
        ld["image"] = cover
    payload = json.dumps(ld, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    block = "\n".join([
        links_block(Path("writing") / post.slug / "index.html"),
        "<!-- agent:ld -->",
        '<script type="application/ld+json">',
        payload,
        "</script>",
        "<!-- /agent:ld -->",
        f'<meta name="author" content="Guilherme Silva">',
        f'<meta name="mirror-kind" content="{post.kind}">',
        f'<meta name="mirror-id" content="{escape_attr(post.post_id)}">',
    ])
    html = html.replace("</head>", block + "\n</head>", 1)
    return html


def list_markup(posts: list[Post], href_for, limit: int | None) -> str:
    rows = posts[:limit] if limit else posts
    items = []
    for post in rows:
        desc = clean_text(post.description).strip()
        if len(desc) > 180:
            desc = desc[:177].rsplit(" ", 1)[0] + "…"
        desc_html = f'<span class="desc">{escape_text(desc)}</span>' if desc else ""
        items.append(
            f'  <li><time datetime="{post.date_key()}">{format_date(post)}</time>'
            f'<a href="{escape_attr(href_for(post))}">{escape_text(clean_text(post.title).strip())}</a>'
            f"{desc_html}</li>"
        )
    inner_html = "\n".join(items)
    return f'<ul class="posts" id="articles">\n{inner_html}\n</ul>'


def replace_list(html: str, markup: str) -> str:
    block = f"<!-- mirror:posts -->\n{markup}\n<!-- /mirror:posts -->"
    updated, count = LIST_RE.subn(block, html, count=1)
    if count != 1:
        raise FeedError("could not find the writing list to update")
    return FEED_SCRIPT_RE.sub("", updated)


def _scan(text: str, label: str) -> None:
    if FORBIDDEN.search(text):
        raise FeedError(f"refusing to write {label}: it contains a banned link or place name")


def render_posts(root: Path, posts: list[Post], render_slugs: set[str], saved: dict, fetch_bytes) -> dict[str, bytes | str]:
    writing_path = root / "writing" / "index.html"
    if not writing_path.exists():
        raise FeedError("writing/index.html is missing; it is the article template")
    template = article_template(writing_path.read_text(encoding="utf-8"))
    staged: dict[str, bytes | str] = {}
    for post in posts:
        if post.slug not in render_slugs:
            continue
        print(f"render {post.slug}", flush=True)
        previous = saved.get(post.slug, (None, 0, {}))[2]
        if post.kind == "full":
            image_map, files, body, manifest = prepare_images(post, fetch_bytes, previous)
            body = sanitize(body, link_map=sibling_links(posts, post.slug), image_map=image_map)
            body = strip_x_mentions(body)
            body = size_images(body, files)
        else:
            files, manifest = {}, '{ "images": [] }\n'
            body = ""
        html = render_article(template, post, body, root=root, files=files)
        _scan(html, post.slug)
        folder = f"writing/{post.slug}"
        staged[f"{folder}/index.html"] = html
        staged[f"{folder}/media.json"] = manifest
        for name, data in files.items():
            staged[f"{folder}/{name}"] = data
    return staged


def default_fetch_bytes(url: str) -> bytes:
    status, ctype, body = http_get(url, "image/webp,image/*;q=0.8,*/*;q=0.5", timeout=40)
    if status >= 400 or looks_like_challenge(status, body[:200].decode("utf-8", "replace"), ctype):
        raise FeedError(f"image {url} returned {status}")
    if not body:
        raise FeedError(f"image {url} was empty")
    return body


def apply_mirror(root: Path, posts: list[Post], *, fetch_bytes=default_fetch_bytes) -> list[str]:
    saved = discover(root)
    merged, render_slugs = merge(saved, posts)
    for slug in saved:
        if slug not in {post.slug for post in merged}:
            raise FeedError(f"internal error: {slug} would be dropped")
    staged = render_posts(root, merged, render_slugs, saved, fetch_bytes)
    home = root / "index.html"
    writing = root / "writing" / "index.html"
    if not home.exists():
        raise FeedError("index.html is missing")
    home_html = replace_list(home.read_text(encoding="utf-8"), list_markup(
        merged, lambda post: f"writing/{post.slug}/", HOME_LIMIT,
    ))
    writing_html = replace_list(writing.read_text(encoding="utf-8"), list_markup(
        merged, lambda post: f"{post.slug}/", None,
    ))
    _scan(home_html, "index.html")
    _scan(writing_html, "writing/index.html")
    staged["index.html"] = home_html
    staged["writing/index.html"] = writing_html
    changed = []
    for rel, content in staged.items():
        path = root / rel
        data = content if isinstance(content, bytes) else content.encode("utf-8")
        if path.exists() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        changed.append(rel)
    # Drop images that this render no longer references. Never drop a whole essay.
    for post in merged:
        if post.slug not in render_slugs:
            continue
        folder = root / "writing" / post.slug / "images"
        if not folder.exists():
            continue
        keep = {Path(rel).name for rel in staged if rel.startswith(f"writing/{post.slug}/images/")}
        for image in folder.iterdir():
            if image.is_file() and image.name not in keep:
                image.unlink()
                changed.append(f"writing/{post.slug}/images/{image.name} (removed)")
    changed.extend(apply_agent(root))
    return changed


def refresh_indexes(root: Path) -> list[str]:
    """Rebuild the homepage list, the writing list, and agent files from disk."""
    saved = discover(root)
    posts = sorted((row[0] for row in saved.values()), key=lambda post: (post.published, post.slug), reverse=True)
    home = root / "index.html"
    writing = root / "writing" / "index.html"
    changed = []
    for path, markup in (
        (home, list_markup(posts, lambda post: f"writing/{post.slug}/", HOME_LIMIT)),
        (writing, list_markup(posts, lambda post: f"{post.slug}/", None)),
    ):
        updated = replace_list(path.read_text(encoding="utf-8"), markup)
        if path.read_text(encoding="utf-8") != updated:
            path.write_text(updated, encoding="utf-8")
            changed.append(str(path.relative_to(root)))
    changed.extend(apply_agent(root))
    return changed


def rewrite_mirrored_essays(root: Path) -> list[str]:
    """Apply strip_x_mentions to each saved essay body. Leaves the shell alone."""
    changed = []
    writing = root / "writing"
    if not writing.is_dir():
        return changed
    article = re.compile(
        r'(<article\b[^>]*class="post"[^>]*>)(.*?)(</article>)',
        re.I | re.S,
    )
    for path in sorted(writing.glob("*/index.html")):
        html = path.read_text(encoding="utf-8")
        match = article.search(html)
        if not match:
            continue
        body = match.group(2)
        updated = strip_x_mentions(body)
        if updated == body:
            continue
        path.write_text(html[:match.start(2)] + updated + html[match.end(2):], encoding="utf-8")
        changed.append(str(path.relative_to(root)))
    return changed


def main(argv: list[str]) -> int:
    if "--reindex" in argv:
        try:
            changed = refresh_indexes(ROOT)
        except FeedError as exc:
            print(f"reindex failed: {exc}", file=sys.stderr)
            return 1
        print(f"reindexed {len(changed)} file(s)" if changed else "indexes are up to date")
        return 0
    return run_mirror(ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
