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


def _person() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": AUTHOR,
        "url": SITE + "/",
        "jobTitle": "Engineering Manager",
        "worksFor": {"@type": "Organization", "name": "xgeeks"},
        "email": "mailto:work@silvags.com",
        "sameAs": [
            "https://github.com/0xgui",
            "https://www.linkedin.com/in/silva-gs",
        ],
    }


def _ld_for(rel: Path, document: str) -> str | None:
    parts = rel.parts
    if parts == ("index.html",) or parts == ("about", "index.html"):
        data = _person()
    elif len(parts) >= 3 and parts[0] == "robots" and parts[-1] == "index.html":
        data = {
            "@context": "https://schema.org",
            "@type": "CreativeWork",
            "name": tag_text(document, "h1") or tag_text(document, "title"),
            "description": meta_content(document, "description"),
            "url": page_url(rel),
            "author": {"@type": "Person", "name": AUTHOR, "url": SITE + "/"},
        }
    else:
        return None
    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    return "\n".join([
        "<!-- agent:ld -->",
        '<script type="application/ld+json">',
        payload,
        "</script>",
        "<!-- /agent:ld -->",
    ])


def _upsert(document: str, pattern: re.Pattern, block: str | None) -> str:
    if block is None:
        return document
    if pattern.search(document):
        return pattern.sub(block, document, count=1)
    return document.replace("</head>", block + "\n</head>", 1)


def update_document(rel: Path, document: str) -> str:
    document = _upsert(document, LINKS_RE, links_block(rel))
    # Mirrored essays own their BlogPosting block. Don't replace it.
    if not (len(rel.parts) == 3 and rel.parts[0] == "writing" and rel.parts[-1] == "index.html"):
        document = _upsert(document, LD_RE, _ld_for(rel, document))
    return document


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
        "> Personal site of Guilherme Silva, engineering manager at xgeeks. Robotics build logs, and essays first published on Binary Paths.",
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
        ])),
        _section("Builds", rows([
            SITE + "/robots/so-101/",
            SITE + "/robots/pico/",
        ])),
        _section("Writing", [(name, href, note) for _, name, href, note in writing]) if writing else "",
        _section("Optional", [
            ("Full text", f"{SITE}/llms-full.txt", "Every page in one Markdown file"),
            ("Atom feed", f"{SITE}/feed.xml", "Essays mirrored from Binary Paths"),
            ("Sitemap", f"{SITE}/sitemap.xml", "HTML pages on this site"),
        ]),
    ]
    return "\n".join(parts).rstrip() + "\n"


def build_llms_full(pages: list[tuple[Path, str, str]]) -> str:
    chunks = [
        f"# {AUTHOR} — full text",
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


def build_sitemap(pages: list[Path]) -> str:
    urls = [page_url(rel) for rel in pages]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in sorted(urls):
        lines.append("  <url>")
        lines.append(f"    <loc>{_xml(url)}</loc>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def build_robots() -> str:
    return "\n".join([
        "# Content Signals: https://contentsignals.org/",
        "# Change the yes/no values in scripts/build_agent.py (CONTENT_SIGNAL),",
        "# set the same string in functions/_middleware.js, then re-run this script.",
        "# search    — build a search index and show links and short excerpts.",
        "# ai-input  — use the content as input to a model at read time.",
        "# ai-train  — train or fine-tune a model.",
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
        "  Content-Type: text/plain; charset=utf-8",
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
    ])


MEDIA_EXTS = ("glb", "webp", "webm", "png", "mp4", "svg")


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
        document = update_document(rel, original)
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
    files["sitemap.xml"] = build_sitemap([rel for rel, _doc in pages])
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
