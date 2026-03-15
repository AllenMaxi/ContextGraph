#!/usr/bin/env python3
"""Check the public launch surface for a GitHub-first open-source release."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from typing import Any


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def status_line(label: str, state: str, detail: str) -> str:
    return f"[{state}] {label}: {detail}"


def find_registry_match(repo_url: str, full_name: str) -> dict[str, Any] | None:
    data = fetch_json("https://registry.modelcontextprotocol.io/v0.1/servers")
    servers = data.get("servers", [])
    for item in servers:
        payload = json.dumps(item).lower()
        if repo_url.lower() in payload or full_name.lower() in payload:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="AllenMaxi/ContextGraph")
    parser.add_argument("--release-tag", default="v0.2.1")
    args = parser.parse_args()

    owner_repo = args.repo
    repo_api = f"https://api.github.com/repos/{owner_repo}"
    release_api = f"{repo_api}/releases/tags/{args.release_tag}"
    repo_html = f"https://github.com/{owner_repo}"

    try:
        repo = fetch_json(repo_api)
    except urllib.error.URLError as exc:
        print(status_line("GitHub repo", "FAIL", f"could not fetch repo API: {exc}"))
        return 1

    print(status_line("GitHub repo", "PASS", repo.get("html_url", repo_html)))

    description = repo.get("description") or ""
    if "memory" in description.lower() and "mcp" in description.lower():
        print(status_line("Description", "PASS", description))
    else:
        print(status_line("Description", "WARN", description or "missing"))

    topics = repo.get("topics") or []
    if topics:
        print(status_line("Topics", "PASS", ", ".join(topics)))
    else:
        print(status_line("Topics", "WARN", "no topics configured"))

    if repo.get("has_discussions"):
        print(status_line("Discussions", "PASS", "enabled"))
    else:
        print(status_line("Discussions", "WARN", "disabled"))

    try:
        release = fetch_json(release_api)
        print(
            status_line(
                "Release",
                "PASS",
                f"{release.get('name', args.release_tag)} at {release.get('html_url', '')}",
            )
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(status_line("Release", "WARN", f"{args.release_tag} not found"))
        else:
            print(status_line("Release", "FAIL", f"could not fetch release: {exc}"))

    try:
        html = fetch_text(repo_html)
        match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if match:
            print(status_line("Social preview", "INFO", f"og:image exposed: {match.group(1)}"))
            print(
                status_line(
                    "Social preview",
                    "WARN",
                    "public HTML does not prove a custom uploaded social preview image",
                )
            )
        else:
            print(status_line("Social preview", "WARN", "no og:image found"))
    except urllib.error.URLError as exc:
        print(status_line("Social preview", "WARN", f"could not fetch repo HTML: {exc}"))

    repo_url = repo.get("html_url", repo_html)
    match = find_registry_match(repo_url, owner_repo)
    if match is None:
        print(status_line("MCP Registry", "WARN", "no official registry listing found"))
    else:
        name = match.get("server", {}).get("name", "unknown")
        print(status_line("MCP Registry", "PASS", f"listed as {name}"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
