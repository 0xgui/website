#!/usr/bin/env python3
"""Prove the worker bundle and the deploy token. Does not deploy.

Uses CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID. Prints the KV namespace
id and the workers.dev snapshot URL. Exits non-zero when the token cannot
list or create that namespace, when deploy --dry-run fails, or when the
committed namespace id is still a placeholder.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLE = "binary-paths-snapshot"
BINDING = re.compile(r'(binding = "SNAPSHOT"\nid = ")([^"]+)"')


def namespace_id(listing: str, title: str) -> str | None:
    start = listing.find("[")
    if start < 0:
        raise ValueError("kv namespace list was not JSON")
    items = json.loads(listing[start:])
    for item in items:
        if item.get("title") == title or item.get("name") == title:
            return str(item["id"]).lower()
    return None


def created_id(text: str) -> str:
    match = re.search(r'id\s*=\s*"([0-9a-fA-F]{32})"', text)
    if not match:
        raise ValueError("namespace create did not print an id")
    return match.group(1).lower()


def with_namespace_id(toml: str, namespace: str) -> str:
    match = BINDING.search(toml)
    if not match:
        raise ValueError("wrangler.toml has no SNAPSHOT binding")
    start, end = match.span(2)
    return toml[:start] + namespace + toml[end:]


def committed_namespace_id(toml: str) -> str:
    match = BINDING.search(toml)
    if not match:
        raise ValueError("wrangler.toml has no SNAPSHOT binding")
    return match.group(2)


def _run(wrangler: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    print("+", "wrangler", *args, flush=True)
    return subprocess.run([wrangler, *args], cwd=ROOT, text=True, capture_output=True)


def _api(token: str, url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return exc.code, body


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    wrangler = os.environ.get("WRANGLER", "wrangler")
    if not token or not account:
        print("CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are required", file=sys.stderr)
        return 1
    who = _run(wrangler, ["whoami"])
    sys.stdout.write(who.stdout)
    sys.stderr.write(who.stderr)
    if who.returncode != 0:
        print("wrangler whoami failed. The token cannot identify this account.", file=sys.stderr)
        return who.returncode

    listed = _run(wrangler, ["kv", "namespace", "list"])
    sys.stdout.write(listed.stdout)
    sys.stderr.write(listed.stderr)
    if listed.returncode != 0:
        print(
            "wrangler kv namespace list failed. The token needs Workers KV Storage Read.",
            file=sys.stderr,
        )
        return listed.returncode
    found = namespace_id(listed.stdout + listed.stderr, TITLE)
    if found:
        namespace = found
        print(f"SNAPSHOT_ID={namespace}")
    else:
        created = _run(wrangler, ["kv", "namespace", "create", TITLE])
        sys.stdout.write(created.stdout)
        sys.stderr.write(created.stderr)
        if created.returncode != 0:
            print(
                "wrangler kv namespace create failed. The token needs Workers KV Storage Edit "
                "to create binary-paths-snapshot. No worker was deployed.",
                file=sys.stderr,
            )
            return created.returncode
        namespace = created_id(created.stdout + created.stderr)
        print(f"SNAPSHOT_ID={namespace}")

    path = ROOT / "wrangler.toml"
    original = path.read_text(encoding="utf-8")
    path.write_text(with_namespace_id(original, namespace), encoding="utf-8")
    try:
        dry = _run(wrangler, ["deploy", "--dry-run"])
    finally:
        path.write_text(original, encoding="utf-8")
    sys.stdout.write(dry.stdout)
    sys.stderr.write(dry.stderr)
    if dry.returncode != 0:
        print("wrangler deploy --dry-run failed. Nothing was deployed.", file=sys.stderr)
        return dry.returncode
    print("DRY_RUN=ok")

    committed = committed_namespace_id(original)
    if committed != namespace:
        print(
            f"wrangler.toml SNAPSHOT id is {committed!r}; the namespace id is {namespace}. "
            "Commit that id. Nothing was deployed.",
            file=sys.stderr,
        )
        return 1

    status, body = _api(token, f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/subdomain")
    print(f"SUBDOMAIN_HTTP={status}")
    if status != 200:
        print(body[:500], file=sys.stderr)
        print("Could not read the workers.dev subdomain.", file=sys.stderr)
        return 1
    subdomain = json.loads(body)["result"]["subdomain"]
    snapshot = f"https://rss-worker.{subdomain}.workers.dev/raw.xml"
    print(f"WORKERS_DEV_SNAPSHOT={snapshot}")

    enabled_status, enabled_body = _api(
        token,
        f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/rss-worker/subdomain",
    )
    print(f"SCRIPT_SUBDOMAIN_HTTP={enabled_status}")
    enabled = False
    if enabled_status == 200:
        enabled = bool(json.loads(enabled_body).get("result", {}).get("enabled"))
    print(f"WORKERS_DEV_ENABLED={str(enabled).lower()}")
    if not enabled:
        print("workers.dev is not enabled on the current worker. The next deploy turns it on.")
        return 0

    fetch_status, fetch_body, fetch_type = _fetch(snapshot)
    print(f"WORKERS_DEV_FETCH={fetch_status} {fetch_type}")
    sample = " ".join(fetch_body[:180].split())
    print(f"WORKERS_DEV_BODY={sample}")
    lowered = fetch_body[:8000].lower()
    if "just a moment" in lowered or "cf-browser-verification" in lowered or "challenge-platform" in lowered:
        print("workers.dev returned a challenge page.", file=sys.stderr)
        return 1
    return 0


def _fetch(url: str) -> tuple[int, str, str]:
    request = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace"), response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        ctype = exc.headers.get("content-type", "") if exc.headers else ""
        return exc.code, body, ctype


if __name__ == "__main__":
    sys.exit(main())
