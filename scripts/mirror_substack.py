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
import re
import tempfile
import time
import urllib.error
import urllib.request

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
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]  # noqa: F811 — Path imported above
UA = "silvags-mirror/1.0 (+https://silvags.com)"
HOME_LIMIT = 4
SITE = "https://silvags.com"
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
FORBIDDEN = re.compile(
    r"leiria|portugal|https?://(?:www\.)?(?:x\.com|twitter\.com)|https?://t\.co/",
    re.I,
)
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


def format_date(post: Post) -> str:
    when = post.published
    return f"{MONTHS[when.month - 1]} {when.day}, {when.year}"


def http_get(url: str, accept: str, timeout: int = 25, attempts: int = 3, sleep=time.sleep):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.headers.get("content-type", ""), response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp else b""
            ctype = exc.headers.get("content-type", "") if exc.headers else ""
            text = raw.decode("utf-8", "replace")
            if looks_like_challenge(exc.code, text, ctype):
                last = ChallengeError(f"{url} returned {exc.code}")
            else:
                last = FeedError(f"{url} returned {exc.code}")
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


def fetch_posts(get=http_get) -> list[Post]:
    """Substack API, then archive, then RSS.

    rss.silvags.com is not a source. Cloudflare puts a JavaScript challenge
    in front of that host (cf-mitigated: challenge) for datacenter clients,
    including a browser User-Agent. The mirror cannot pass that challenge.
    """
    errors = []
    for name, fn in (
        ("api", lambda: _posts_api(get)),
        ("archive", lambda: _posts_archive(get)),
        ("rss", lambda: posts_from_rss(_decode(*get(
            "https://binarypaths.substack.com/feed",
            "application/rss+xml, application/xml, text/xml",
        ), "https://binarypaths.substack.com/feed"))),
    ):
        try:
            posts = fn()
            if not posts:
                raise EmptyFeed(f"{name} returned no posts")
            return posts
        except FeedError as exc:
            errors.append(f"{name}: {exc}")
    raise FeedError("all feed sources failed:\n" + "\n".join(errors))


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


def to_webp(data: bytes) -> bytes:
    if _is_webp(data) and len(data) <= IMAGE_MAX:
        return data
    ffmpeg = _which("ffmpeg")
    if not ffmpeg:
        raise FeedError("image is over 1MB or not WebP and ffmpeg is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        src = folder / "in"
        dest = folder / "out.webp"
        src.write_bytes(data)
        quality = 78
        last = b""
        while quality >= 40:
            import subprocess
            result = subprocess.run(
                [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                 "-vf", "scale='min(1600,iw)':-2", "-c:v", "libwebp", "-quality", str(quality), str(dest)],
                check=False, capture_output=True,
            )
            if result.returncode == 0 and dest.exists():
                last = dest.read_bytes()
                if len(last) <= IMAGE_TARGET:
                    return last
            quality -= 15
        if last and len(last) <= IMAGE_MAX:
            return last
    raise FeedError("could not compress an image under 1MB")


def _which(name: str) -> str | None:
    from shutil import which
    return which(name)


def prepare_images(post: Post, fetch_bytes, previous: dict) -> tuple[dict[str, str], dict[str, bytes], str]:
    """Return image_map (remote src -> local path), files to write, and body html with cover."""
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
    old_by_hash = {item.get("source_sha256"): item.get("file") for item in old if isinstance(item, dict)}
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
        prior_name = old_by_hash.get(digest)
        prior_path = None
        if prior_name:
            prior_path = post_dir_file(previous, prior_name)
        if prior_path and prior_name == name and len(prior_path) <= IMAGE_MAX:
            media = prior_path
        else:
            try:
                media = gif_to_webm(data) if ext == "webm" else to_webp(data)
            except FeedError as exc:
                raise FeedError(f"{post.slug} {origin} ({len(data)} bytes, {data[:16]!r}): {exc}") from exc
        if len(media) > IMAGE_MAX:
            raise FeedError(f"{post.slug} image {name} is {len(media)} bytes")
        files[local] = media
        manifest["images"].append({"file": name, "source_sha256": digest})
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
            image = path.parent / "images" / item.get("file", "")
            if image.exists():
                file_bytes[item["file"]] = image.read_bytes()
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
        return re.sub(pattern, repl, html, count=1)
    return html.replace("</head>", repl + "\n</head>", 1)


def render_article(template: str, post: Post, body: str) -> str:
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
    html = re.sub(r"<main>.*?</main>", "<main>\n" + article + "</main>", html, count=1, flags=re.S)
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": description,
        "datePublished": post.atom_time(),
        "author": {"@type": "Person", "name": "Guilherme Silva", "url": SITE + "/"},
        "mainEntityOfPage": local,
        "url": local,
        "isBasedOn": post.canonical,
    }
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
        else:
            files, manifest = {}, '{ "images": [] }\n'
            body = ""
        html = render_article(template, post, body)
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


def main(argv: list[str]) -> int:
    if "--reindex" in argv:
        try:
            changed = refresh_indexes(ROOT)
        except FeedError as exc:
            print(f"reindex failed: {exc}", file=sys.stderr)
            return 1
        print(f"reindexed {len(changed)} file(s)" if changed else "indexes are up to date")
        return 0
    try:
        posts = fetch_posts()
        changed = apply_mirror(ROOT, posts)
    except FeedError as exc:
        print(f"mirror failed: {exc}", file=sys.stderr)
        return 1
    if changed:
        print(f"updated {len(changed)} file(s)")
    else:
        print("mirror is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
