#!/usr/bin/env python3
"""Build Markdown twins, llms.txt, sitemap, robots.txt, the Atom feed, and _headers.

The HTML pages are the source. Re-run this after editing a page:

    python3 scripts/build_agent.py

`--check` exits 1 when a generated file would change.

Content Signals default to search=yes, ai-input=yes, ai-train=no.
Change CONTENT_SIGNAL below, keep functions/_middleware.js in sync, and re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import html
import json
import re

from scripts.htmltext import html_to_markdown, inner, meta_content, tag_text

ROOT = Path(__file__).resolve().parents[1]  # repo root
SITE = "https://silvags.com"
AUTHOR = "Guilherme Silva"
# Edit this one line to change the site's Content Signals, then re-run this script.
# functions/_middleware.js must carry the same string (tests/test_agent.py checks).
CONTENT_SIGNAL = "search=yes, ai-input=yes, ai-train=no"

SKIP_DIRS = {".git", ".github", ".cursor", "scripts", "tests", "functions", "node_modules"}

LINKS_RE = re.compile(r"<!-- agent:links -->.*?<!-- /agent:links -->", re.S)
LD_RE = re.compile(r"<!-- agent:ld -->.*?<!-- /agent:ld -->", re.S)
CRUMBS_RE = re.compile(r"<!-- agent:crumbs -->.*?<!-- /agent:crumbs -->", re.S)
SOCIAL_RE = re.compile(r"<!-- agent:social -->.*?<!-- /agent:social -->", re.S)
# Tags the social block owns. Any copy outside the block (hand-written or from the mirror) is dropped.
SOCIAL_TAG_RE = re.compile(
    r'[ \t]*<meta\s+(?:property="(?:og:site_name|og:locale|og:image(?::[a-z_]+)?)"|name="twitter:(?:card|image:alt)")'
    r'\s+content="[^"]*"\s*/?>\n?'
)
PERSON_ID = SITE + "/#person"

# Link-preview cards (1200x630 WebP) made by scripts/og_cards.mjs. Page -> (file in og/, alt text).
# Essays not listed keep their own cover image. Bump the -vN in both places when a card changes.
CARDS = {
    "index.html": ("home-v1.webp", "Guilherme Silva: building small robots from scratch and writing about engineering and physical AI, beside an ink study of the SO-101 robotic arm"),
    "about/index.html": ("about-v1.webp", "About Guilherme Silva: platform engineer turned robot tinkerer"),
    "work/index.html": ("work-v1.webp", "Where I’ve worked: Hitachi Digital, Deichmann, Mercedes-Benz and more"),
    "builds/index.html": ("builds-v1.webp", "Robots I’m building, beside an ink study of Pico"),
    "writing/index.html": ("writing-v1.webp", "Binary Paths: essays on engineering, teams and physical AI"),
    "talks/index.html": ("talks-v1.webp", "Talks and slides by Guilherme Silva"),
    "talks/bottleneck-moved/index.html": ("talk-bottleneck-moved-v1.webp", "The Bottleneck Moved, a talk at KCD Porto × DevOpsDays 2026"),
    "robots/so-101/index.html": ("robot-so101-v1.webp", "SO-101 robotic arm build log, beside an ink study of the arm"),
    "robots/pico/index.html": ("robot-pico-v1.webp", "Pico, a self-righting robot, beside an ink study of Pico tipping on its base"),
    "writing/aiconomy/index.html": ("essay-aiconomy-v1.webp", "AIconomy, an essay on Binary Paths"),
    "writing/5-tech-trends-that-will-define-2025/index.html": ("essay-5-tech-trends-that-will-define-2025-v1.webp", "5 Tech Trends That Will Define 2025, an essay on Binary Paths"),
    "writing/i-built-a-tiny-robot-that-refuses/index.html": ("essay-i-built-a-tiny-robot-that-refuses-v1.webp", "I built a tiny robot that refuses to stay down, beside an ink study of Pico"),
    "writing/i-just-wanted-to-clean-my-house/index.html": ("essay-i-just-wanted-to-clean-my-house-v1.webp", "I just wanted to clean my house, an essay on Binary Paths"),
    "writing/physical-ai-is-here-and-im-building/index.html": ("essay-physical-ai-is-here-and-im-building-v1.webp", "Physical AI is here and I’m building for it, beside an ink study of the SO-101 arm"),
    "writing/engineering-estimates/index.html": ("essay-engineering-estimates-v1.webp", "Engineering Estimates: 1 week means 4, an essay on Binary Paths"),
    "writing/you-cant-know-everything-in-tech/index.html": ("essay-you-cant-know-everything-in-tech-v1.webp", "You Can’t Know Everything in Tech, an essay on Binary Paths"),
}


def page_url(rel: Path) -> str:
    parts = rel.parts
    if parts == ("index.html",):
        return SITE + "/"
    if parts[-1] == "index.html":
        return SITE + "/" + "/".join(parts[:-1]) + "/"
    return SITE + "/" + "/".join(parts)


def md_href(rel: Path) -> str:
    url = page_url(rel)
    path = url[len(SITE):]
    if path.endswith("/"):
        return path + "index.md"
    return path + ".md"


def links_block(rel: Path) -> str:
    href = md_href(rel)
    return "\n".join([
        "<!-- agent:links -->",
        f'<link rel="alternate" type="text/markdown" href="{href}">',
        '<link rel="describedby" href="/llms.txt" type="text/plain">',
        '<link rel="alternate" type="application/atom+xml" title="Guilherme Silva" href="/feed.xml">',
        "<!-- /agent:links -->",
    ])


def _is_essay(rel: Path) -> bool:
    return len(rel.parts) == 3 and rel.parts[0] == "writing" and rel.parts[-1] == "index.html"


def webp_size(data: bytes) -> tuple[int, int] | None:
    """Width and height from a WebP header (VP8, VP8L or VP8X)."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if chunk == b"VP8 ":
        return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def _essay_card(root: Path, slug: str) -> Path | None:
    """An on-disk card og/essay-<slug>-*.webp: -v1 first, then the highest -vN, then any other name (sorted)."""
    prefix = f"essay-{slug}-"
    # Skip cards of a longer slug that starts with this one (the-art vs the-art-of-juggling-life).
    longer = [f"essay-{other.name}-" for other in (root / "writing").glob(f"{slug}-*") if other.is_dir()]
    found = [
        path for path in (root / "og").glob(f"{prefix}*.webp")
        if path.is_file() and not any(path.name.startswith(other) for other in longer)
    ]
    if not found:
        return None
    versioned = {}
    for path in found:
        match = re.fullmatch(r"v(\d+)", path.name[len(prefix):-len(".webp")])
        if match:
            versioned[int(match.group(1))] = path
    if 1 in versioned:
        return versioned[1]
    if versioned:
        return versioned[max(versioned)]
    return sorted(found)[0]


def _existing_alt(document: str) -> str | None:
    """og:image:alt (or twitter:image:alt) already on the page, e.g. written by the mirror.

    The Writing card's alt is ignored: essays copy writing/index.html's head, so it is not theirs.
    """
    for pattern in (
        r'<meta\s+property="og:image:alt"\s+content="([^"]*)"',
        r'<meta\s+name="twitter:image:alt"\s+content="([^"]*)"',
    ):
        match = re.search(pattern, document)
        if match:
            alt = html.unescape(match.group(1)).strip()
            if alt and alt != CARDS["writing/index.html"][1]:
                return alt
    return None


def _image_for(root: Path, rel: Path, document: str) -> tuple[str, str, Path] | None:
    """(absolute URL, alt text, local file) of the page's link-preview image."""
    card = CARDS.get(rel.as_posix())
    if card:
        return f"{SITE}/og/{card[0]}", card[1], root / "og" / card[0]
    if _is_essay(rel):
        title = tag_text(document, "h1") or rel.parts[1]
        alt = _existing_alt(document)
        # A card dropped into og/ (by hand or by the mirror) wins over the Substack cover.
        own = _essay_card(root, rel.parts[1])
        if own:
            return f"{SITE}/og/{own.name}", alt or f"{title}, an essay on Binary Paths", own
        # Same rule as mirror_substack.essay_cover: the first local image, usually the Substack cover.
        match = re.search(r'<img src="(images/[^"]+)"', document)
        if match:
            return page_url(rel) + match.group(1), alt or f"Cover image for {title}", root / rel.parent / match.group(1)
        # No image of its own: the Writing card.
        return _image_for(root, Path("writing/index.html"), "")
    return None


def social_block(root: Path, rel: Path, document: str) -> str | None:
    image = _image_for(root, rel, document)
    if image is None:
        return None
    url, alt, path = image
    size = webp_size(path.read_bytes()) if path.exists() else None
    lines = [
        "<!-- agent:social -->",
        f'<meta property="og:site_name" content="{AUTHOR}">',
        '<meta property="og:locale" content="en_GB">',
        f'<meta property="og:image" content="{_xml(url)}">',
    ]
    if size:
        lines += [
            f'<meta property="og:image:width" content="{size[0]}">',
            f'<meta property="og:image:height" content="{size[1]}">',
        ]
    lines += [
        '<meta property="og:image:type" content="image/webp">',
        f'<meta property="og:image:alt" content="{_xml(alt)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:image:alt" content="{_xml(alt)}">',
        "<!-- /agent:social -->",
    ]
    return "\n".join(lines)


def _person() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": PERSON_ID,
        "name": AUTHOR,
        "url": SITE + "/",
        "jobTitle": "Engineering Manager",
        "worksFor": {"@type": "Organization", "name": "Hitachi Digital"},
        "email": "mailto:guilherme@silvags.com",
        "sameAs": [
            "https://github.com/0xgui",
            "https://www.linkedin.com/in/silva-gs",
        ],
    }


def _ld_script(data: dict) -> list[str]:
    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    return ['<script type="application/ld+json">', payload, "</script>"]


def _ld_block(marker: str, items: list[dict]) -> str:
    # One script per item, so the first block on a page stays its main entity.
    lines = [f"<!-- agent:{marker} -->"]
    for item in items:
        lines += _ld_script(item)
    lines.append(f"<!-- /agent:{marker} -->")
    return "\n".join(lines)


def _ld_for(rel: Path, document: str) -> str | None:
    parts = rel.parts
    if parts == ("index.html",):
        items = [_person(), {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "@id": SITE + "/#website",
            "name": AUTHOR,
            "url": SITE + "/",
            "author": {"@id": PERSON_ID},
            "publisher": {"@id": PERSON_ID},
        }]
    elif parts == ("about", "index.html"):
        items = [_person()]
    elif parts == ("work", "index.html"):
        person = _person()
        del person["@context"]
        items = [{
            "@context": "https://schema.org",
            "@type": "ProfilePage",
            "name": tag_text(document, "title"),
            "url": page_url(rel),
            "mainEntity": person,
        }]
    elif len(parts) >= 3 and parts[0] == "robots" and parts[-1] == "index.html":
        data = {
            "@context": "https://schema.org",
            "@type": "CreativeWork",
            "name": tag_text(document, "h1") or tag_text(document, "title"),
            "description": meta_content(document, "description"),
            "url": page_url(rel),
            "author": {"@type": "Person", "@id": PERSON_ID, "name": AUTHOR, "url": SITE + "/"},
        }
        card = CARDS.get(rel.as_posix())
        if card:
            data["image"] = f"{SITE}/og/{card[0]}"
        items = [data]
    else:
        return None
    return _ld_block("ld", items)


def crumbs_block(rel: Path, document: str) -> str | None:
    """BreadcrumbList for pages one level below a section: robots, the talk, and essays."""
    parts = rel.parts
    if len(parts) != 3 or parts[-1] != "index.html":
        return None
    sections = {"robots": ("Builds", SITE + "/builds/"), "talks": ("Talks", SITE + "/talks/"), "writing": ("Writing", SITE + "/writing/")}
    if parts[0] not in sections:
        return None
    name, url = sections[parts[0]]
    trail = [("Home", SITE + "/"), (name, url), (tag_text(document, "h1") or tag_text(document, "title"), page_url(rel))]
    return _ld_block("crumbs", [{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": label, "item": link}
            for i, (label, link) in enumerate(trail, 1)
        ],
    }])


def _upsert(document: str, pattern: re.Pattern, block: str | None) -> str:
    if block is None:
        return document
    if pattern.search(document):
        return pattern.sub(block, document, count=1)
    return document.replace("</head>", block + "\n</head>", 1)


def update_document(rel: Path, document: str, root: Path = ROOT) -> str:
    document = _upsert(document, LINKS_RE, links_block(rel))
    # Mirrored essays own their BlogPosting block. Don't replace it.
    if not _is_essay(rel):
        document = _upsert(document, LD_RE, _ld_for(rel, document))
    # Breadcrumbs and social tags always go last in <head>. Essays copy writing/index.html's head,
    # so a fixed position keeps the mirror's output the same on every run.
    crumbs = crumbs_block(rel, document)
    social = social_block(root, rel, document)
    document = _drop(_drop(document, CRUMBS_RE), SOCIAL_RE)
    if social:
        # The social block owns these tags; drop hand-written or mirror-written copies.
        document = SOCIAL_TAG_RE.sub("", document)
    for block in (crumbs, social):
        if block:
            document = document.replace("</head>", block + "\n</head>", 1)
    return document


def _drop(document: str, pattern: re.Pattern) -> str:
    return re.compile(pattern.pattern + r"\n?", pattern.flags).sub("", document)


def html_pages(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("index.html"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        found.append(path.relative_to(root))
    return sorted(found, key=lambda item: (len(item.parts), str(item)))


def markdown_for(root: Path, rel: Path, document: str) -> str:
    url = page_url(rel)
    body = html_to_markdown(document, url)
    title = tag_text(document, "h1") or tag_text(document, "title") or AUTHOR
    if not body.lstrip().startswith("#"):
        description = meta_content(document, "description")
        extra = f"\n\n> {description}\n" if description else "\n"
        body = f"# {title}{extra}\n{body.lstrip()}"
    return body if body.endswith("\n") else body + "\n"


def _section(title: str, rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return ""
    lines = [f"## {title}", ""]
    for name, href, note in rows:
        safe = name.replace("[", "(").replace("]", ")")
        lines.append(f"- [{safe}]({href}): {note}" if note else f"- [{safe}]({href})")
    lines.append("")
    return "\n".join(lines)


def build_llms(root: Path, pages: list[tuple[Path, str]]) -> str:
    by_url = {page_url(rel): (rel, doc) for rel, doc in pages}

    def row(url: str) -> tuple[str, str, str] | None:
        found = by_url.get(url)
        if not found:
            return None
        rel, doc = found
        name = tag_text(doc, "h1") or tag_text(doc, "title")
        note = meta_content(doc, "description")
        return name, SITE + md_href(rel), note

    def rows(urls: list[str]) -> list[tuple[str, str, str]]:
        return [item for item in (row(url) for url in urls) if item]

    writing = []
    for rel, doc in pages:
        if len(rel.parts) == 3 and rel.parts[0] == "writing":
            published = ""
            match = re.search(r'<time\b[^>]*datetime="([^"]+)"', doc)
            if match:
                published = match.group(1)[:10]
            note = meta_content(doc, "description")
            if published:
                note = f"{published}. {note}".strip()
            writing.append((match.group(1) if match else "", tag_text(doc, "h1"), SITE + md_href(rel), note))
    writing.sort(key=lambda item: item[0], reverse=True)

    parts = [
        f"# {AUTHOR}",
        "",
        "> Personal site of Guilherme Silva, engineering manager at Hitachi Digital. Robotics build logs, and essays first published on Binary Paths.",
        "",
        f"Canonical site: {SITE}. Essays keep a canonical link to https://binarypaths.substack.com. "
        f"Content-Signal: {CONTENT_SIGNAL}.",
        "",
        _section("Site", rows([
            SITE + "/",
            SITE + "/about/",
            SITE + "/builds/",
            SITE + "/writing/",
            SITE + "/talks/",
            SITE + "/talks/bottleneck-moved/",
            SITE + "/work/",
        ])),
        _section("Builds", rows([
            SITE + "/robots/so-101/",
            SITE + "/robots/pico/",
        ])),
        _section("Writing", [(name, href, note) for _, name, href, note in writing]) if writing else "",
        _section("Optional", [
            ("Full text", f"{SITE}/llms-full.txt", "Every page in one Markdown file"),
            ("Atom feed", f"{SITE}/feed.xml", "Essays mirrored from Binary Paths"),
            ("Sitemap", f"{SITE}/sitemap.xml", "HTML pages canonical on this site"),
        ]),
    ]
    return "\n".join(parts).rstrip() + "\n"


def build_llms_full(pages: list[tuple[Path, str, str]]) -> str:
    chunks = [
        f"# {AUTHOR}: full text",
        "",
        "> Generated from the HTML pages. Prefer llms.txt when you only need the map.",
        "",
    ]
    for rel, _doc, md in pages:
        chunks.append("---")
        chunks.append("")
        chunks.append(f"Source: {page_url(rel)}")
        chunks.append("")
        chunks.append(md.rstrip())
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def build_sitemap(pages: list[tuple[Path, str]]) -> str:
    # lastmod only where the HTML carries a trustworthy date: an essay's publish date, and the newest
    # essay for the homepage and Writing list (they change when one is added). Other pages get none.
    dates = {rel: published[:10] for published, rel, _doc in _articles(pages) if published}
    newest = max(dates.values(), default="")
    if newest:
        dates[Path("index.html")] = newest
        dates[Path("writing/index.html")] = newest
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    # Mirrored essays are canonical on Binary Paths, so only pages canonical here are listed.
    for url, rel in sorted((page_url(rel), rel) for rel, _doc in pages if not _is_essay(rel)):
        lines.append("  <url>")
        lines.append(f"    <loc>{_xml(url)}</loc>")
        if rel in dates:
            lines.append(f"    <lastmod>{dates[rel]}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def build_robots() -> str:
    return "\n".join([
        "# Content Signals: https://contentsignals.org/",
        "# Change the yes/no values in scripts/build_agent.py (CONTENT_SIGNAL),",
        "# set the same string in functions/_middleware.js, then re-run this script.",
        "# search:   build a search index and show links and short excerpts.",
        "# ai-input: use the content as input to a model at read time.",
        "# ai-train: train or fine-tune a model.",
        "# Omitting a signal would mean no preference. This file sets all three.",
        "",
        "User-agent: *",
        f"Content-Signal: {CONTENT_SIGNAL}",
        "Allow: /",
        "",
        f"Sitemap: {SITE}/sitemap.xml",
        "",
    ])


def build_headers() -> str:
    return "\n".join([
        "# Generated by scripts/build_agent.py. Content-Signal is CONTENT_SIGNAL.",
        "/*",
        f"  Content-Signal: {CONTENT_SIGNAL}",
        "  X-Content-Type-Options: nosniff",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  Vary: Accept",
        '  Link: </llms.txt>; rel="describedby", </feed.xml>; rel="alternate"; type="application/atom+xml"',
        "",
        "/*.md",
        "  Content-Type: text/markdown; charset=utf-8",
        "",
        "/llms.txt",
        "  Content-Type: text/plain; charset=utf-8",
        "",
        "/llms-full.txt",
        "  Content-Type: text/markdown; charset=utf-8",
        "",
        "/robots.txt",
        "  Content-Type: text/plain; charset=utf-8",
        "",
        "/sitemap.xml",
        "  Content-Type: application/xml; charset=utf-8",
        "",
        "/feed.xml",
        "  Content-Type: application/atom+xml; charset=utf-8",
        "",
        # Media file names are not fingerprinted: a day fresh, then served stale while it revalidates.
        *[line for ext in MEDIA_EXTS for line in (
            f"/*.{ext}",
            "  Cache-Control: public, max-age=86400, stale-while-revalidate=604800",
            "",
        )],
        # Self-hosted fonts never change in place; a new version gets a new file name.
        "/fonts/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
        "/vendor/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
    ])


MEDIA_EXTS = ("glb", "webp", "webm", "png", "mp4", "svg", "pdf")


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _articles(pages: list[tuple[Path, str]]) -> list[tuple[str, Path, str]]:
    rows = []
    for rel, doc in pages:
        if not (len(rel.parts) == 3 and rel.parts[0] == "writing"):
            continue
        match = re.search(r'<time\b[^>]*datetime="([^"]+)"', doc)
        published = match.group(1) if match else ""
        rows.append((published, rel, doc))
    rows.sort(key=lambda item: item[0], reverse=True)
    return rows


def build_feed(pages: list[tuple[Path, str]]) -> str:
    articles = _articles(pages)
    updated = articles[0][0] if articles else "2026-01-01T00:00:00Z"
    if updated and "T" not in updated:
        updated = updated + "T00:00:00Z"
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"  <title>{AUTHOR}</title>",
        "  <subtitle>Essays mirrored from Binary Paths</subtitle>",
        f'  <link href="{SITE}/feed.xml" rel="self" type="application/atom+xml"/>',
        f'  <link href="{SITE}/writing/"/>',
        f"  <updated>{_xml(updated)}</updated>",
        "  <author><name>Guilherme Silva</name></author>",
        f"  <id>{SITE}/feed.xml</id>",
    ]
    for published, rel, doc in articles:
        url = page_url(rel)
        title = tag_text(doc, "h1") or rel.parts[1]
        summary = meta_content(doc, "description")
        canonical = ""
        match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', doc)
        if match:
            canonical = match.group(1)
        stamp = published if "T" in published else (published + "T00:00:00Z" if published else updated)
        content = inner(doc, "article", "post") or summary
        lines.extend([
            "  <entry>",
            f"    <title>{_xml(title)}</title>",
            f'    <link href="{_xml(url)}" rel="alternate" type="text/html"/>',
        ])
        if canonical:
            lines.append(f'    <link href="{_xml(canonical)}" rel="related" type="text/html"/>')
        lines.extend([
            f"    <id>{_xml(url)}</id>",
            f"    <published>{_xml(stamp)}</published>",
            f"    <updated>{_xml(stamp)}</updated>",
            "    <author><name>Guilherme Silva</name></author>",
            f"    <summary>{_xml(summary)}</summary>",
            f'    <content type="html">{_xml(content)}</content>',
            "  </entry>",
        ])
    lines.append("</feed>")
    lines.append("")
    return "\n".join(lines)


def outputs(root: Path) -> dict[str, str]:
    pages = []
    updated_html = {}
    markdowns = []
    for rel in html_pages(root):
        original = (root / rel).read_text(encoding="utf-8")
        document = update_document(rel, original, root)
        updated_html[str(rel)] = document
        md = markdown_for(root, rel, document)
        md_rel = rel.with_suffix(".md") if rel.name == "index.html" else rel
        # index.html -> index.md beside it
        md_rel = rel.parent / "index.md"
        updated_html[str(md_rel)] = md
        pages.append((rel, document))
        markdowns.append((rel, document, md))
    files = dict(updated_html)
    files["llms.txt"] = build_llms(root, pages)
    files["llms-full.txt"] = build_llms_full(markdowns)
    files["sitemap.xml"] = build_sitemap(pages)
    files["robots.txt"] = build_robots()
    files["feed.xml"] = build_feed(pages)
    files["_headers"] = build_headers()
    return files


def diff(root: Path) -> list[str]:
    changed = []
    for rel, content in outputs(root).items():
        path = root / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            changed.append(rel)
    return changed


def apply(root: Path) -> list[str]:
    changed = []
    for rel, content in outputs(root).items():
        path = root / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        changed.append(rel)
    return changed


def main(argv: list[str]) -> int:
    root = ROOT
    check = "--check" in argv
    changed = diff(root) if check else apply(root)
    if changed:
        verb = "would change" if check else "wrote"
        print(f"{verb} {len(changed)} file(s)")
        for name in changed:
            print(f"  {name}")
        return 1 if check else 0
    print("agent files are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
