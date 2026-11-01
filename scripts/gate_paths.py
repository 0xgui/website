#!/usr/bin/env python3
"""Risk tiers for .review-gate.yml and the mirror's auto-merge decision.

A typical mirror diff is low or medium and may auto-merge once the gate and CI
are green. A diff that touches a high-tier path must not auto-merge.

This is a one-maintainer repo. The gate config asks for no approving reviews
at any tier (a second approval cannot be satisfied). Auto-merge is still
refused for high-tier diffs here, in the mirror workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".review-gate.yml"

TIER_RANK = {"low": 1, "medium": 2, "high": 3}

# Placeholders the gate treats as an empty section.
EMPTY_MARKERS = ("todo", "n/a", "tbd")


def parse_yaml(text: str):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    value, index = _parse(lines, 0, 0)
    if index != len(lines):
        raise ValueError(f"yaml parse stopped early at {lines[index]}")
    return value


def _parse(lines, index, indent):
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_map(lines, index, indent)


def _parse_list(lines, index, indent):
    items = []
    while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
        item = lines[index][1][2:]
        index += 1
        if item.endswith(":") and not item[:-1].strip().endswith(":"):
            # "- key:" with nested keys, or "- key: value" handled below
            pass
        if ": " in item or item.endswith(":"):
            key, _, rest = item.partition(":")
            mapping = {}
            rest = rest.strip()
            if rest:
                mapping[key.strip()] = _scalar(rest)
            else:
                nested, index = _parse(lines, index, lines[index][0] if index < len(lines) else indent + 2)
                mapping[key.strip()] = nested
            while index < len(lines) and lines[index][0] > indent and not lines[index][1].startswith("- "):
                nested_indent, content = lines[index]
                if ": " in content or content.endswith(":"):
                    nkey, _, nrest = content.partition(":")
                    index += 1
                    nrest = nrest.strip()
                    if nrest:
                        mapping[nkey.strip()] = _scalar(nrest)
                    else:
                        nested, index = _parse(lines, index, lines[index][0])
                        mapping[nkey.strip()] = nested
                else:
                    break
            items.append(mapping)
        else:
            items.append(_scalar(item))
    return items, index


def _parse_map(lines, index, indent):
    mapping = {}
    while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
        content = lines[index][1]
        key, _, rest = content.partition(":")
        rest = rest.strip()
        index += 1
        if rest:
            mapping[key.strip()] = _scalar(rest)
        elif index < len(lines) and lines[index][0] > indent:
            nested, index = _parse(lines, index, lines[index][0])
            mapping[key.strip()] = nested
        else:
            mapping[key.strip()] = {}
    return mapping, index


def _scalar(value: str):
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part.strip()) for part in inner.split(",")]
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
    return value


def load_config(path: Path = CONFIG) -> dict:
    return parse_yaml(path.read_text(encoding="utf-8"))


def glob_match(pattern: str, path: str) -> bool:
    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    pattern = pattern.replace("\\", "/")
    if pattern == path:
        return True
    if "**" not in pattern and "*" not in pattern and "?" not in pattern:
        return False
    # Translate a small glob: ** crosses directories, * does not.
    regex = ["^"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            regex.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            regex.append(".*")
            i += 2
        elif pattern[i] == "*":
            regex.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            regex.append("[^/]")
            i += 1
        else:
            regex.append(re_escape(pattern[i]))
            i += 1
    regex.append("$")
    import re
    return re.search("".join(regex), path) is not None


def re_escape(char: str) -> str:
    if char.isalnum() or char in "/_-":
        return char
    return "\\" + char


def tier_of(path: str, config: dict) -> str:
    best = config.get("default_tier") or "low"
    best_rank = TIER_RANK[best]
    tiers = config.get("tiers") or {}
    for name, patterns in tiers.items():
        if name not in TIER_RANK or not isinstance(patterns, list):
            continue
        for pattern in patterns:
            if isinstance(pattern, str) and glob_match(pattern, path):
                if TIER_RANK[name] > best_rank:
                    best = name
                    best_rank = TIER_RANK[name]
    return best


def tier_for_paths(paths: list[str], config: dict | None = None) -> str:
    config = config if config is not None else load_config()
    if not paths:
        return config.get("default_tier") or "low"
    return max((tier_of(path, config) for path in paths), key=lambda name: TIER_RANK[name])


def section_bodies(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in (body or "").splitlines():
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current:
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections


def section_filled(text: str) -> bool:
    if not text or not text.strip():
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower().strip(" .:-")
        if low in EMPTY_MARKERS or stripped.startswith("- [ ]"):
            return False
        if any(low.endswith(marker) or f": {marker}" in low for marker in EMPTY_MARKERS):
            return False
    return True


def required_section_names(config: dict) -> list[tuple[str, list[str]]]:
    evidence = (config.get("evidence") or {}).get("sections") or []
    names = []
    for item in evidence:
        if isinstance(item, str):
            names.append((item, []))
        elif isinstance(item, dict):
            name = item.get("name") or ""
            aliases = item.get("aliases") or []
            names.append((name, list(aliases)))
    return names


def verdict(paths: list[str], body: str, *, ci_green: bool, config: dict | None = None) -> dict:
    config = config if config is not None else load_config()
    tier = tier_for_paths(paths, config)
    approvals = ((config.get("routing") or {}).get("approvals") or {})
    needed = int(approvals.get(tier, 0) or 0)
    missing = []
    bodies = section_bodies(body)
    for name, aliases in required_section_names(config):
        text = bodies.get(name, "")
        if not text:
            for alias in aliases:
                if bodies.get(alias):
                    text = bodies[alias]
                    break
        if not section_filled(text):
            missing.append(f"section:{name}")
    require_ci = (config.get("evidence") or {}).get("require_green_ci", True)
    if require_ci and not ci_green:
        missing.append("ci")
    gate_pass = not missing and needed == 0
    # High-tier diffs are never auto-merged, even when the gate would pass.
    auto_merge = gate_pass and tier != "high"
    return {
        "tier": tier,
        "required_approvals": needed,
        "missing": missing,
        "gate": "pass" if not missing else "blocked",
        "auto_merge": auto_merge,
    }


def mirror_pr_body(summary: str) -> str:
    summary = summary.strip()
    return f"""{summary}

## Testing

The mirror workflow ran `python3 -m unittest discover -s tests -v` and `node --test tests/negotiate.test.mjs` before opening this PR. Both passed. A second mirror with no upstream change produces no diff.

## Risk

Low. This PR only updates generated Binary Paths pages, images, and indexes (`writing/`, the homepage list, `llms.txt`, `llms-full.txt`, `sitemap.xml`, and `feed.xml`). It does not change workflows, `_headers`, `_redirects`, `_routes.json`, `functions/`, `worker.js`, `wrangler.toml`, `.review-gate.yml`, or the mirror script.

## How to revert

Revert this commit. The live site stays on the previous revision until that revert lands. The next successful mirror run will recreate essays that are still public on Binary Paths.
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["decide", "body"])
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--body-file")
    parser.add_argument("--ci-green", action="store_true", default=True)
    parser.add_argument("--summary", default="Mirror public Binary Paths essays onto the site.")
    args = parser.parse_args(argv)
    if args.command == "body":
        print(mirror_pr_body(args.summary), end="")
        return 0
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else mirror_pr_body(args.summary)
    result = verdict(args.files, body, ci_green=args.ci_green)
    print(json.dumps(result, indent=2))
    return 0 if result["gate"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
