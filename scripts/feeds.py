"""Parse Binary Paths feeds. Stdlib only. No network here."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CANONICAL_RE = re.compile(r"^https://(?:www\.)?binarypaths\.substack\.com/p/([a-z0-9-]+)/?$")
PAID = {"only_paid", "paid", "founding", "only_founding"}


class FeedError(Exception):
    """A source could not be used. Callers try the next source."""


class ChallengeError(FeedError):
    pass


class MalformedFeed(FeedError):
    pass


class EmptyFeed(FeedError):
    pass


@dataclass(frozen=True)
class Post:
    slug: str
    title: str
    canonical: str
    published: datetime
    description: str
    body_html: str
    kind: str
    cover_url: str = ""
    post_id: str = ""

    def date_key(self) -> str:
        return self.published.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def atom_time(self) -> str:
        return self.published.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def looks_like_challenge(status: int, body: str, content_type: str = "") -> bool:
    if status in {401, 403, 429, 503, 520, 521, 522, 523, 524}:
        return True
    sample = (body or "")[:8000].lower()
    markers = (
        "just a moment",
        "cf-browser-verification",
        "challenge-platform",
        "attention required",
        "enable javascript and cookies",
        "cf-mitigated",
        "cf-chl",
    )
    if any(marker in sample for marker in markers):
        return True
    ctype = (content_type or "").lower()
    stripped = sample.lstrip()
    if "text/html" in ctype and not stripped.startswith(("<?xml", "<rss", "{", "[")):
        if "<html" in stripped[:500]:
            return True
    return False


def _kind(audience: str, body: str) -> str:
    if (audience or "everyone").lower() in PAID:
        return "stub"
    low = (body or "").lower()
    if 'class="paywall"' in low or "this post is for paid subscribers" in low:
        return "stub"
    if not (body or "").strip():
        return "stub"
    return "full"


def _published(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        raise MalformedFeed("post has no date")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        found = datetime.fromisoformat(value)
    except ValueError:
        try:
            found = parsedate_to_datetime(value)
        except (TypeError, ValueError) as exc:
            raise MalformedFeed(f"bad date {value!r}") from exc
    if found.tzinfo is None:
        found = found.replace(tzinfo=timezone.utc)
    return found.astimezone(timezone.utc)


def _check(slug: str, canonical: str, title: str) -> None:
    if not SLUG_RE.match(slug or ""):
        raise MalformedFeed(f"bad slug {slug!r}")
    if not CANONICAL_RE.match(canonical or ""):
        raise MalformedFeed(f"canonical is not a Binary Paths post: {canonical!r}")
    if not (title or "").strip():
        raise MalformedFeed(f"{slug} has no title")


def post_from_mapping(item: dict, *, source: str) -> Post:
    canonical = (item.get("canonical_url") or item.get("link") or item.get("canonical") or "").strip()
    match = CANONICAL_RE.match(canonical)
    slug = (item.get("slug") or (match.group(1) if match else "") or "").strip()
    if not canonical and slug:
        canonical = f"https://binarypaths.substack.com/p/{slug}"
    title = (item.get("title") or "").strip()
    _check(slug, canonical, title)
    body = item.get("body_html") or item.get("content_html") or ""
    if source == "rss":
        body = item.get("content_html") or ""
    description = (item.get("description") or item.get("subtitle") or item.get("truncated_body_text") or "").strip()
    kind = item.get("kind") or _kind(str(item.get("audience") or "everyone"), body)
    if kind == "stub":
        body = item.get("truncated_body_text") or description or ""
    published = _published(str(item.get("post_date") or item.get("pubDate") or item.get("published") or ""))
    cover = (item.get("cover_image") or item.get("image") or "") or ""
    if isinstance(cover, str):
        cover = cover.strip()
    else:
        cover = ""
    return Post(
        slug=slug,
        title=title,
        canonical=canonical.split("?")[0],
        published=published,
        description=_plain_description(description),
        body_html=body if kind == "full" else _plain_description(body or description),
        kind=kind,
        cover_url=cover if cover.startswith("https://") else "",
        post_id=str(item.get("id") or ""),
    )


def _plain_description(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def posts_from_api(payload) -> list[Post]:
    if isinstance(payload, str):
        if looks_like_challenge(200, payload, "application/json"):
            raise ChallengeError("api returned a challenge page")
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MalformedFeed("api json is not valid") from exc
    if isinstance(payload, dict) and "posts" in payload:
        rows = payload["posts"]
    elif isinstance(payload, list):
        rows = payload
    else:
        raise MalformedFeed("api payload has no posts")
    if not isinstance(rows, list):
        raise MalformedFeed("api posts is not a list")
    if not rows:
        raise EmptyFeed("api returned no posts")
    posts = []
    for row in rows:
        if not isinstance(row, dict):
            raise MalformedFeed("api post is not an object")
        posts.append(post_from_mapping(row, source="api"))
    return posts


def posts_from_worker(payload) -> list[Post]:
    """rss.silvags.com returns titles and excerpts, not full HTML. Those are stubs."""
    if isinstance(payload, str):
        if looks_like_challenge(200, payload, "application/json"):
            raise ChallengeError("worker returned a challenge page")
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MalformedFeed("worker json is not valid") from exc
    rows = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise EmptyFeed("worker returned no items")
    posts = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        link = (row.get("link") or "").strip()
        match = CANONICAL_RE.match(link)
        if not match:
            continue
        posts.append(post_from_mapping({
            "slug": match.group(1),
            "title": row.get("title") or "",
            "canonical_url": link,
            "pubDate": row.get("pubDate") or "",
            "description": row.get("description") or "",
            "truncated_body_text": row.get("description") or "",
            "audience": "everyone",
            "kind": "stub",
            "image": row.get("image") or "",
        }, source="worker"))
    if not posts:
        raise EmptyFeed("worker items had no Binary Paths links")
    return posts


def _text(node) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def posts_from_rss(xml: str) -> list[Post]:
    if xml is None:
        raise MalformedFeed("rss is empty")
    if looks_like_challenge(200, xml, "text/html"):
        raise ChallengeError("rss body is a challenge page")
    stripped = xml.lstrip()
    if stripped.startswith("<!") or stripped.lower().startswith("<html"):
        raise ChallengeError("rss body is HTML, not a feed")
    if "<rss" not in xml.lower():
        raise MalformedFeed("not an rss document")
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise MalformedFeed("rss xml is not well formed") from exc
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")
    posts = []
    for item in items:
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        description = _text(item.find("description"))
        encoded = item.find(f"{{{CONTENT_NS}}}encoded")
        content = _text(encoded)
        enclosure = ""
        enc = item.find("enclosure")
        if enc is not None:
            enclosure = (enc.attrib.get("url") or "").strip()
        kind = _kind("everyone", content or "")
        # A description-only item is an excerpt, not a full essay.
        if not content.strip():
            kind = "stub"
        posts.append(post_from_mapping({
            "title": title,
            "canonical_url": link,
            "pubDate": _text(item.find("pubDate")),
            "description": description,
            "content_html": content,
            "truncated_body_text": description,
            "kind": kind,
            "cover_image": enclosure,
        }, source="rss"))
    if not posts:
        raise EmptyFeed("rss contains no usable items")
    return posts
