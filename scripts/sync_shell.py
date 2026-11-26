#!/usr/bin/env python3
"""Check or sync the shared inline <style> and 4 inline <script> blocks from index.html.

Usage:
    python3 scripts/sync_shell.py --check
    python3 scripts/sync_shell.py --apply

Stdlib only. Excludes talks/bottleneck-moved/slides.html.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".github", ".cursor", "scripts", "tests", "functions", "node_modules"}
EXCLUDE_PAGES = {"talks/bottleneck-moved/slides.html"}
EXPECTED_SCRIPTS = 4

STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
SCRIPT_RE = re.compile(r"<script\b([^>]*)>.*?</script>", re.I | re.S)
SRC_ATTR_RE = re.compile(r"\bsrc\s*=", re.I)


def _is_shared_script(attrs: str) -> bool:
    low = attrs.lower()
    if "application/ld+json" in low:
        return False
    if SRC_ATTR_RE.search(low):
        return False
    return True


def site_pages(root: Path = ROOT) -> list[Path]:
    """Return relative paths to all site pages sharing the shell (all index.html + 404.html)."""
    found: list[Path] = []
    for path in root.rglob("index.html"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.as_posix() in EXCLUDE_PAGES:
            continue
        found.append(rel)
    not_found = root / "404.html"
    if not_found.is_file():
        found.append(Path("404.html"))
    return sorted(found, key=lambda item: (len(item.parts), item.as_posix()))


def extract_shell(html: str) -> tuple[str, list[str]]:
    """Extract the single <style> block and the 4 shared inline <script> blocks."""
    styles = STYLE_RE.findall(html)
    if len(styles) != 1:
        raise ValueError(f"expected 1 <style> block, found {len(styles)}")
    scripts = [
        match.group(0)
        for match in SCRIPT_RE.finditer(html)
        if _is_shared_script(match.group(1))
    ]
    if len(scripts) != EXPECTED_SCRIPTS:
        raise ValueError(f"expected {EXPECTED_SCRIPTS} shared inline <script> blocks, found {len(scripts)}")
    return styles[0], scripts


def sync_html(html: str, ref_style: str, ref_scripts: list[str]) -> str:
    """Replace the page's <style> and 4 shared inline <script> blocks, preserving everything else."""
    # Validate target structure before modifying.
    extract_shell(html)
    updated = STYLE_RE.sub(lambda _match: ref_style, html, count=1)
    idx = 0

    def _replace_script(match: re.Match) -> str:
        nonlocal idx
        if not _is_shared_script(match.group(1)):
            return match.group(0)
        replacement = ref_scripts[idx]
        idx += 1
        return replacement

    return SCRIPT_RE.sub(_replace_script, updated)


def check_pages(root: Path = ROOT) -> list[tuple[Path, list[str]]]:
    """Return a list of (rel_path, reasons) for every site page whose shell differs from index.html."""
    ref_path = root / "index.html"
    ref_style, ref_scripts = extract_shell(ref_path.read_text(encoding="utf-8"))
    diffs: list[tuple[Path, list[str]]] = []
    for rel in site_pages(root):
        if rel.as_posix() == "index.html":
            continue
        html = (root / rel).read_text(encoding="utf-8")
        try:
            style, scripts = extract_shell(html)
        except ValueError as exc:
            diffs.append((rel, [str(exc)]))
            continue
        reasons = []
        if style != ref_style:
            reasons.append("style")
        for i, (actual, expected) in enumerate(zip(scripts, ref_scripts)):
            if actual != expected:
                reasons.append(f"script[{i}]")
        if reasons:
            diffs.append((rel, reasons))
    return diffs


def apply_pages(root: Path = ROOT) -> list[Path]:
    """Sync the shell from index.html into all other site pages. Returns modified relative paths."""
    ref_path = root / "index.html"
    ref_style, ref_scripts = extract_shell(ref_path.read_text(encoding="utf-8"))
    changed: list[Path] = []
    for rel in site_pages(root):
        if rel.as_posix() == "index.html":
            continue
        path = root / rel
        current = path.read_text(encoding="utf-8")
        updated = sync_html(current, ref_style, ref_scripts)
        if updated != current:
            path.write_text(updated, encoding="utf-8")
            changed.append(rel)
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check or sync shared <style> and inline <script> blocks.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Exit 1 if any site page differs from index.html")
    mode.add_argument("--apply", action="store_true", help="Copy <style> and 4 inline <script> blocks from index.html")
    parser.add_argument("--root", type=Path, default=ROOT, help="Site root directory")
    args = parser.parse_args(argv)

    if args.apply:
        changed = apply_pages(args.root)
        if changed:
            print(f"synced {len(changed)} page(s)")
            for rel in changed:
                print(f"  {rel.as_posix()}")
        else:
            print("shell blocks are already in sync")
        return 0

    diffs = check_pages(args.root)
    if diffs:
        print(f"shell drift in {len(diffs)} page(s)")
        for rel, reasons in diffs:
            print(f"  {rel.as_posix()}: {', '.join(reasons)}")
        return 1
    print(f"shell blocks are in sync across {len(site_pages(args.root))} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
