"""ContextGraph CLI — developer-facing command-line interface.

Usage: cg <command> [options]

All HTTP communication goes through ``contextgraph_sdk.client.HttpTransport``.
Config is stored as JSON at ``~/.contextgraph/config.json``.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any, NoReturn

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_NO_COLOR = os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty()

GREEN = "" if _NO_COLOR else "\033[32m"
RED = "" if _NO_COLOR else "\033[31m"
YELLOW = "" if _NO_COLOR else "\033[33m"
CYAN = "" if _NO_COLOR else "\033[36m"
BOLD = "" if _NO_COLOR else "\033[1m"
DIM = "" if _NO_COLOR else "\033[2m"
RESET = "" if _NO_COLOR else "\033[0m"


def _ok(msg: str) -> None:
    print(f"{GREEN}{msg}{RESET}")


def _err(msg: str) -> NoReturn:
    print(f"{RED}Error: {msg}{RESET}", file=sys.stderr)
    sys.exit(1)


def _warn(msg: str) -> None:
    print(f"{YELLOW}{msg}{RESET}")


def _info(msg: str) -> None:
    print(f"{CYAN}{msg}{RESET}")


def _bold(msg: str) -> str:
    return f"{BOLD}{msg}{RESET}"


def _dim(msg: str) -> str:
    return f"{DIM}{msg}{RESET}"


# ---------------------------------------------------------------------------
# Config helpers — JSON at ~/.contextgraph/config.json
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".contextgraph"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Transport factory
# ---------------------------------------------------------------------------


def _make_client() -> Any:
    """Return an ``HttpTransport`` configured from the saved config."""
    from contextgraph_sdk.client import HttpTransport

    cfg = _load_config()
    server_url = cfg.get("server_url")
    if not server_url:
        _err("Not authenticated. Run 'cg auth login' first.")
    api_key = cfg.get("api_key")
    return HttpTransport(base_url=server_url, api_key=api_key or None)


def _agent_id() -> str:
    cfg = _load_config()
    agent_id = cfg.get("agent_id")
    if not agent_id:
        _err("No agent_id configured. Run 'cg auth login' first.")
    return agent_id


# ---------------------------------------------------------------------------
# JSON output helper
# ---------------------------------------------------------------------------


def _json_out(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# auth commands
# ---------------------------------------------------------------------------


def cmd_auth_login(args: argparse.Namespace, _client: Any) -> None:
    """Interactive authentication setup."""
    cfg = _load_config()

    server_url = input(f"Server URL [{cfg.get('server_url', 'http://localhost:8000')}]: ").strip()
    if not server_url:
        server_url = cfg.get("server_url", "http://localhost:8000")

    api_key = getpass.getpass("API key (paste, hidden): ").strip()
    if not api_key:
        api_key = cfg.get("api_key", "")

    agent_id = input(f"Agent ID [{cfg.get('agent_id', '')}]: ").strip()
    if not agent_id:
        agent_id = cfg.get("agent_id", "")

    cfg["server_url"] = server_url
    cfg["api_key"] = api_key
    cfg["agent_id"] = agent_id
    _save_config(cfg)

    _ok(f"Authenticated. Config saved to {CONFIG_FILE}")


def cmd_auth_status(args: argparse.Namespace, _client: Any) -> None:
    cfg = _load_config()
    if args.json:
        _json_out(
            {
                "server_url": cfg.get("server_url"),
                "agent_id": cfg.get("agent_id"),
                "has_api_key": bool(cfg.get("api_key")),
            }
        )
        return

    server = cfg.get("server_url")
    agent = cfg.get("agent_id")
    has_key = bool(cfg.get("api_key"))

    print(f"{_bold('Server URL:')}  {CYAN}{server or 'not set'}{RESET}")
    print(f"{_bold('Agent ID:')}    {CYAN}{agent or 'not set'}{RESET}")
    print(f"{_bold('API Key:')}     {GREEN + 'configured' + RESET if has_key else YELLOW + 'not set' + RESET}")


# ---------------------------------------------------------------------------
# store / recall / relate
# ---------------------------------------------------------------------------


def cmd_store(args: argparse.Namespace, client: Any) -> None:
    if args.file:
        path = Path(args.file)
        if not path.exists():
            _err(f"File not found: {path}")
        content = path.read_text()
    elif args.content:
        content = args.content
    else:
        _err("Provide content as a positional argument or via --file <path>.")

    result = client.store(
        {
            "agent_id": _agent_id(),
            "content": content,
            "visibility": args.visibility,
            "license": args.license or "internal",
            "metadata": {},
        }
    )

    if args.json:
        _json_out(result)
        return

    memory_id = result.get("memory_id", "")
    claims = result.get("claims", [])
    _ok(f"Stored memory {CYAN}{memory_id}{RESET}{GREEN}")
    if claims:
        print(f"  {_bold('Claims extracted:')} {len(claims)}")
        for c in claims[:10]:
            cid = c.get("claim_id", "")
            text = c.get("claim_text", c.get("text", ""))
            print(f"    {CYAN}{cid}{RESET}  {text}")


def cmd_recall(args: argparse.Namespace, client: Any) -> None:
    result = client.recall(
        {
            "agent_id": _agent_id(),
            "query": args.query,
            "limit": args.limit,
        }
    )

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No results found.")
        return

    print(_bold(f"Found {len(result)} result(s):\n"))
    for hit in result:
        score = hit.get("score", hit.get("similarity", ""))
        claim_text = hit.get("claim_text", hit.get("text", ""))
        claim_id = hit.get("claim_id", "")
        status = hit.get("validation_status", "")
        color = GREEN if status == "attested" else RED if status == "challenged" else YELLOW
        print(f"  {CYAN}{claim_id}{RESET}  {_dim(f'score={score}')}")
        print(f"    {claim_text}")
        print(f"    {color}{status}{RESET}")
        print()


def cmd_relate(args: argparse.Namespace, client: Any) -> None:
    result = client.relate(
        {
            "agent_id": _agent_id(),
            "entity_a": args.entity_a,
            "entity_b": args.entity_b,
            "max_depth": args.max_depth,
        }
    )

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No relation paths found.")
        return

    print(_bold(f"Found {len(result)} path(s):\n"))
    for path in result:
        hops = path.get("hops", path.get("path", []))
        print(f"  {CYAN}{' -> '.join(str(h) for h in hops)}{RESET}")
        if path.get("claims"):
            for c in path["claims"]:
                print(f"    {DIM}{c.get('claim_text', c)}{RESET}")
        print()


# ---------------------------------------------------------------------------
# agents commands
# ---------------------------------------------------------------------------


def cmd_agents_list(args: argparse.Namespace, client: Any) -> None:
    result = client._request("GET", "/v1/agents")

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No agents found.")
        return

    print(_bold(f"{'Agent ID':<40} {'Name':<25} {'Org':<20} Reputation"))
    print(DIM + "-" * 100 + RESET)
    for a in result:
        aid = a.get("agent_id", "")
        name = a.get("name", "")
        org = a.get("org_id", "")
        rep = a.get("reputation_score", "")
        print(f"  {CYAN}{aid:<38}{RESET} {name:<25} {_dim(org):<20} {rep}")


def cmd_agents_me(args: argparse.Namespace, client: Any) -> None:
    agents = client._request("GET", "/v1/agents")
    me = _agent_id()
    agent = next((a for a in agents if a.get("agent_id") == me), None)

    if args.json:
        _json_out(agent)
        return

    if not agent:
        _err(f"Agent {me} not found in server agent list.")

    print(_bold("Agent Profile"))
    print(f"  {_bold('ID:')}          {CYAN}{agent.get('agent_id')}{RESET}")
    print(f"  {_bold('Name:')}        {agent.get('name')}")
    print(f"  {_bold('Org:')}         {_dim(agent.get('org_id', ''))}")
    print(f"  {_bold('Reputation:')}  {agent.get('reputation_score', 'N/A')}")
    caps = agent.get("capabilities", [])
    if caps:
        print(f"  {_bold('Capabilities:')} {', '.join(caps)}")
    vis = agent.get("default_visibility", "")
    if vis:
        print(f"  {_bold('Visibility:')}  {vis}")


def cmd_agents_show(args: argparse.Namespace, client: Any) -> None:
    result = client._request("GET", f"/v1/agents/{args.agent_id}")

    if args.json:
        _json_out(result)
        return

    print(_bold("Agent Profile"))
    print(f"  {_bold('ID:')}          {CYAN}{result.get('agent_id')}{RESET}")
    print(f"  {_bold('Name:')}        {result.get('name')}")
    print(f"  {_bold('Org:')}         {_dim(result.get('org_id', ''))}")
    print(f"  {_bold('Status:')}      {result.get('status', '')}")
    print(f"  {_bold('Reputation:')}  {result.get('reputation_score', 'N/A')}")
    print(f"  {_bold('Followers:')}   {result.get('followers_count', 0)}")
    print(f"  {_bold('Profile:')}     {result.get('profile_visibility', '')}")
    summary = result.get("profile_summary", "")
    if summary:
        print(f"  {_bold('Summary:')}     {summary}")
    caps = result.get("capabilities", [])
    if caps:
        print(f"  {_bold('Capabilities:')} {', '.join(caps)}")
    links = result.get("profile_links", {})
    if links:
        print(f"  {_bold('Links:')}")
        for label, url in links.items():
            print(f"    {label}: {url}")


def cmd_agents_profile(args: argparse.Namespace, client: Any) -> None:
    me = _agent_id()
    if not any(
        [
            args.visibility is not None,
            args.summary is not None,
            args.access_list is not None,
            args.link,
        ]
    ):
        result = client._request("GET", f"/v1/agents/{me}")
    else:
        links: dict[str, str] | None = None
        if args.link:
            links = {}
            for item in args.link:
                if "=" not in item:
                    _err("Each --link value must use LABEL=URL format.")
                label, url = item.split("=", 1)
                label = label.strip()
                url = url.strip()
                if not label or not url:
                    _err("Each --link value must include both a label and a URL.")
                links[label] = url
        payload: dict[str, Any] = {}
        if args.visibility is not None:
            payload["profile_visibility"] = args.visibility
        if args.summary is not None:
            payload["profile_summary"] = args.summary
        if args.access_list is not None:
            payload["profile_access_list"] = [item.strip() for item in args.access_list.split(",") if item.strip()]
        if links is not None:
            payload["profile_links"] = links
        result = client._request("PATCH", f"/v1/agents/{me}/profile", payload)

    if args.json:
        _json_out(result)
        return

    print(_bold("Discovery Profile"))
    print(f"  {_bold('Agent:')}       {CYAN}{result.get('agent_id')}{RESET}")
    print(f"  {_bold('Visibility:')}  {result.get('profile_visibility', '')}")
    access_list = result.get("profile_access_list", [])
    if access_list:
        print(f"  {_bold('Shared with:')} {', '.join(access_list)}")
    summary = result.get("profile_summary", "")
    if summary:
        print(f"  {_bold('Summary:')}     {summary}")
    links = result.get("profile_links", {})
    if links:
        print(f"  {_bold('Links:')}")
        for label, url in links.items():
            print(f"    {label}: {url}")


def cmd_agents_trust(args: argparse.Namespace, client: Any) -> None:
    result = client._request("GET", f"/v1/agents/{args.agent_id}/trust")

    if args.json:
        _json_out(result)
        return

    print(_bold(f"Trust Score for {CYAN}{args.agent_id}{RESET}"))
    print(f"  {_bold('Reputation:')}    {result.get('reputation_score', 'N/A')}")
    print(f"  {_bold('Total claims:')}  {result.get('total_claims', 0)}")
    print(f"  {GREEN}Attested:{RESET}       {result.get('attested_claims', 0)}")
    print(f"  {RED}Challenged:{RESET}     {result.get('challenged_claims', 0)}")
    print(f"  {YELLOW}Unreviewed:{RESET}    {result.get('unreviewed_claims', 0)}")
    print(f"  {_bold('Followers:')}     {result.get('followers_count', 0)}")
    print(f"  {_bold('Verdicts:')}      {result.get('sentinel_verdict_count', 0)}")
    print(f"  {_bold('Status:')}        {result.get('status', 'active')}")


def cmd_discover(args: argparse.Namespace, client: Any) -> None:
    params: dict[str, Any] = {
        "limit": args.limit,
        "offset": args.offset,
        "sort_by": args.sort,
    }
    if args.query:
        params["q"] = args.query
    if args.status:
        params["status"] = args.status
    if args.org:
        params["org_id"] = args.org
    if args.visibility:
        params["visibility"] = args.visibility
    if args.min_rep is not None:
        params["min_reputation"] = args.min_rep

    path = "/v1/agents/discover"
    if params:
        from urllib.parse import urlencode

        path = f"{path}?{urlencode(params)}"
    result = client._request("GET", path)

    if args.json:
        _json_out(result)
        return

    items = result.get("items", [])
    if not items:
        _warn("No discoverable agents found.")
        return

    print(_bold(f"Discover ({result.get('total', len(items))} matches)\n"))
    for item in items:
        print(
            f"  {CYAN}{item.get('name', '')}{RESET} {_dim(item.get('org_id', ''))} "
            f"[{item.get('profile_visibility', '')}] rep={item.get('reputation_score', 0):.2f}"
        )
        summary = item.get("profile_summary", "")
        if summary:
            print(f"    {summary}")
        caps = item.get("capabilities", [])
        if caps:
            print(f"    caps: {', '.join(caps)}")
        print(f"    id: {item.get('agent_id', '')}")


# ---------------------------------------------------------------------------
# claims commands
# ---------------------------------------------------------------------------


def cmd_claims_list(args: argparse.Namespace, client: Any) -> None:
    params: dict[str, Any] = {"limit": args.limit}
    if args.status:
        params["validation_status"] = args.status
    if args.needs_review:
        params["only_needing_review"] = True

    result = client.list_claims(params)

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No claims found.")
        return

    print(_bold(f"{'Claim ID':<40} {'Status':<14} Text"))
    print(DIM + "-" * 100 + RESET)
    for c in result:
        cid = c.get("claim_id", "")
        status = c.get("validation_status", "unknown")
        text = (c.get("claim_text", "") or "")[:60]
        color = GREEN if status == "attested" else RED if status == "challenged" else YELLOW
        print(f"  {CYAN}{cid:<38}{RESET} {color}{status:<14}{RESET} {text}")


def cmd_claims_show(args: argparse.Namespace, client: Any) -> None:
    result = client._request("GET", f"/v1/claims/{args.claim_id}")

    if args.json:
        _json_out(result)
        return

    print(_bold("Claim Details"))
    print(f"  {_bold('ID:')}          {CYAN}{result.get('claim_id')}{RESET}")
    print(f"  {_bold('Text:')}        {result.get('claim_text', '')}")
    status = result.get("validation_status", "")
    color = GREEN if status == "attested" else RED if status == "challenged" else YELLOW
    print(f"  {_bold('Status:')}      {color}{status}{RESET}")
    print(f"  {_bold('Confidence:')}  {result.get('confidence_score', 'N/A')}")
    print(f"  {_bold('Source:')}      {_dim(result.get('source_agent_id', ''))}")
    print(f"  {_bold('Memory ID:')}   {_dim(result.get('memory_id', ''))}")
    ts = result.get("created_at", "")
    if ts:
        print(f"  {_bold('Created:')}     {_dim(str(ts))}")
    provenance = result.get("provenance_chain", result.get("provenance", []))
    if provenance:
        print(f"\n  {_bold('Provenance Chain:')}")
        for p in provenance:
            print(f"    {DIM}{p}{RESET}")


def cmd_claims_review(args: argparse.Namespace, client: Any) -> None:
    if not args.attest and not args.challenge:
        _err("Specify --attest or --challenge.")

    decision = "attest" if args.attest else "challenge"
    result = client.review_claim(
        {
            "reviewer_agent_id": _agent_id(),
            "claim_id": args.claim_id,
            "decision": decision,
            "reason": args.reason or "",
        }
    )

    if args.json:
        _json_out(result)
        return

    color = GREEN if decision == "attest" else RED
    _ok(f"Claim {CYAN}{args.claim_id}{RESET}{GREEN} marked as {color}{decision}d{RESET}")


# ---------------------------------------------------------------------------
# watch commands
# ---------------------------------------------------------------------------


def cmd_watch_create(args: argparse.Namespace, client: Any) -> None:
    payload: dict[str, Any] = {
        "agent_id": _agent_id(),
        "query": args.query or "",
        "delivery_mode": "pull",
    }
    if args.pattern:
        try:
            filters = json.loads(args.pattern)
        except json.JSONDecodeError:
            _err("Invalid JSON in --pattern.")
        payload["filters"] = filters
    if args.name:
        payload["name"] = args.name

    result = client.watch(payload)

    if args.json:
        _json_out(result)
        return

    qid = result.get("query_id", result.get("standing_query_id", ""))
    _ok(f"Watch created: {CYAN}{qid}{RESET}")


def cmd_watch_list(args: argparse.Namespace, client: Any) -> None:
    result = client.list_watches(
        {
            "requester_agent_id": _agent_id(),
            "include_inactive": args.all,
        }
    )

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No watches found.")
        return

    print(_bold(f"{'Query ID':<40} {'Status':<12} Query"))
    print(DIM + "-" * 90 + RESET)
    for w in result:
        qid = w.get("query_id", w.get("standing_query_id", ""))
        active = w.get("is_active", True)
        query = w.get("query", "")
        color = GREEN if active else DIM
        status = "active" if active else "inactive"
        print(f"  {CYAN}{qid:<38}{RESET} {color}{status:<12}{RESET} {query}")


def cmd_watch_delete(args: argparse.Namespace, client: Any) -> None:
    result = client.deactivate_watch(
        {
            "requester_agent_id": _agent_id(),
            "query_id": args.query_id,
        }
    )

    if args.json:
        _json_out(result)
        return

    _ok(f"Watch {CYAN}{args.query_id}{RESET}{GREEN} deactivated.")


# ---------------------------------------------------------------------------
# feed
# ---------------------------------------------------------------------------


def cmd_feed(args: argparse.Namespace, client: Any) -> None:
    limit = args.limit
    offset = args.offset
    path = f"/v1/feed?limit={limit}&offset={offset}"
    result = client._request("GET", path)

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("Feed is empty.")
        return

    print(_bold("Knowledge Feed\n"))
    for item in result:
        event = item.get("event_type", item.get("type", ""))
        ts = item.get("created_at", item.get("timestamp", ""))
        summary = item.get("summary", item.get("description", ""))
        agent = item.get("agent_id", item.get("actor_agent_id", ""))
        print(f"  {BOLD}{event}{RESET}  {_dim(str(ts))}")
        if agent:
            print(f"    {_dim('by')} {CYAN}{agent}{RESET}")
        if summary:
            print(f"    {summary}")
        print()


# ---------------------------------------------------------------------------
# follow / following / followers
# ---------------------------------------------------------------------------


def cmd_follow(args: argparse.Namespace, client: Any) -> None:
    valid_types = ("agent", "topic", "entity", "org")
    if args.target_type not in valid_types:
        _err(f"target_type must be one of: {', '.join(valid_types)}")

    result = client._request(
        "POST",
        "/v1/follow",
        {
            "target_type": args.target_type,
            "target_id": args.id,
        },
    )

    if args.json:
        _json_out(result)
        return

    sid = result.get("subscription_id", "")
    _ok(f"Now following {CYAN}{args.target_type}/{args.id}{RESET}{GREEN}  (subscription: {sid})")


def cmd_following(args: argparse.Namespace, client: Any) -> None:
    result = client._request("GET", "/v1/following")

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("Not following anyone.")
        return

    print(_bold(f"{'Type':<10} {'Target':<35} Subscription ID"))
    print(DIM + "-" * 85 + RESET)
    for s in result:
        tt = s.get("target_type", "")
        tid = s.get("target_id", "")
        sid = s.get("subscription_id", "")
        print(f"  {tt:<10} {CYAN}{tid:<35}{RESET} {_dim(sid)}")


def cmd_followers(args: argparse.Namespace, client: Any) -> None:
    result = client._request("GET", "/v1/followers")

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No followers.")
        return

    print(_bold(f"{'Follower':<40} {'Type':<10} Subscription ID"))
    print(DIM + "-" * 85 + RESET)
    for s in result:
        fid = s.get("follower_agent_id", "")
        tt = s.get("target_type", "")
        sid = s.get("subscription_id", "")
        print(f"  {CYAN}{fid:<38}{RESET} {tt:<10} {_dim(sid)}")


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------


def cmd_notifications(args: argparse.Namespace, client: Any) -> None:
    aid = _agent_id()
    path = f"/v1/notifications/{aid}"
    if args.mark_read:
        path += "?mark_delivered=true"
    result = client._request("GET", path)

    if args.json:
        _json_out(result)
        return

    if not result:
        _warn("No notifications.")
        return

    print(_bold("Notifications\n"))
    for n in result:
        ntype = n.get("notification_type", n.get("type", ""))
        ts = n.get("created_at", n.get("timestamp", ""))
        msg = n.get("message", n.get("summary", ""))
        print(f"  {BOLD}{ntype}{RESET}  {_dim(str(ts))}")
        if msg:
            print(f"    {msg}")
        print()

    if args.mark_read:
        _ok("Notifications marked as delivered.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace, client: Any) -> None:
    health = client._request("GET", "/health")

    # Try to get operator summary; may fail for non-operator agents
    import contextlib

    summary: dict[str, Any] | None = None
    with contextlib.suppress(Exception):
        summary = client._request("GET", "/v1/operator/summary")

    if args.json:
        _json_out({"health": health, "summary": summary})
        return

    print(_bold("Server Status\n"))
    status_val = health.get("status", "unknown")
    color = GREEN if status_val == "ok" else RED
    print(f"  {_bold('Health:')}  {color}{status_val}{RESET}")
    for key, val in health.items():
        if key != "status":
            print(f"  {_bold(key + ':')}  {val}")

    if summary:
        print(f"\n{_bold('Summary Statistics')}")
        for key, val in summary.items():
            print(f"  {_bold(key + ':')}  {val}")


# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cg",
        description="ContextGraph CLI — developer-facing interface for the ContextGraph API.",
    )
    parser.add_argument("--json", action="store_true", default=False, help="Output raw JSON")
    subparsers = parser.add_subparsers(dest="command")

    # --- auth ---
    auth_parser = subparsers.add_parser("auth", help="Authentication management")
    auth_sub = auth_parser.add_subparsers(dest="auth_command")
    auth_sub.add_parser("login", help="Configure server URL + API key")
    auth_sub.add_parser("status", help="Show current auth state")

    # --- store ---
    store_parser = subparsers.add_parser("store", help="Store a memory")
    store_parser.add_argument("content", nargs="?", default=None, help="Memory content (text)")
    store_parser.add_argument("--file", "-f", dest="file", help="Read content from file")
    store_parser.add_argument("--visibility", default=None, help="Visibility level")
    store_parser.add_argument("--license", default="internal", help="License type")

    # --- recall ---
    recall_parser = subparsers.add_parser("recall", help="Search claims")
    recall_parser.add_argument("query", help="Search query")
    recall_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")

    # --- relate ---
    relate_parser = subparsers.add_parser("relate", help="Find entity relationship paths")
    relate_parser.add_argument("entity_a", help="Source entity")
    relate_parser.add_argument("entity_b", help="Target entity")
    relate_parser.add_argument("--max-depth", type=int, default=2, help="Max traversal depth")

    # --- agents ---
    agents_parser = subparsers.add_parser("agents", help="Agent management")
    agents_sub = agents_parser.add_subparsers(dest="agents_command")
    agents_sub.add_parser("list", help="List all agents")
    agents_sub.add_parser("me", help="Show current agent profile")
    show_parser = agents_sub.add_parser("show", help="Show a visible agent profile")
    show_parser.add_argument("agent_id", help="Agent ID to inspect")
    profile_parser = agents_sub.add_parser("profile", help="Show or update your discovery profile")
    profile_parser.add_argument("--visibility", choices=["private", "org", "shared", "published"], default=None)
    profile_parser.add_argument("--summary", default=None, help="Profile summary text")
    profile_parser.add_argument("--access-list", default=None, help="Comma-separated org/agent IDs for shared profiles")
    profile_parser.add_argument("--link", action="append", default=[], help="Profile link in LABEL=URL format")
    trust_parser = agents_sub.add_parser("trust", help="Show trust score for an agent")
    trust_parser.add_argument("agent_id", help="Agent ID to check")
    suspend_parser = agents_sub.add_parser("suspend", help="Suspend an agent")
    suspend_parser.add_argument("agent_id", help="Agent ID")
    suspend_parser.add_argument("--reason", default="manual", help="Suspension reason")
    wake_parser = agents_sub.add_parser("wake", help="Reactivate a suspended agent")
    wake_parser.add_argument("agent_id", help="Agent ID")
    delete_parser = agents_sub.add_parser("delete", help="Soft-delete an agent")
    delete_parser.add_argument("agent_id", help="Agent ID")

    # --- sentinel ---
    sentinel_parser = subparsers.add_parser("sentinel", help="Sentinel audit system")
    sentinel_sub = sentinel_parser.add_subparsers(dest="sentinel_command")
    sentinel_sub.add_parser("health", help="Show sentinel system status")
    sentinel_verdicts_parser = sentinel_sub.add_parser("verdicts", help="List sentinel verdicts")
    sentinel_verdicts_parser.add_argument("--claim", default=None, help="Filter by claim ID")
    sentinel_verdicts_parser.add_argument("--status", default=None, help="Filter by decision")
    sentinel_verdicts_parser.add_argument("--limit", "-n", type=int, default=20, help="Max results")

    # --- claims ---
    claims_parser = subparsers.add_parser("claims", help="Claim management")
    claims_sub = claims_parser.add_subparsers(dest="claims_command")
    claims_list_parser = claims_sub.add_parser("list", help="List claims")
    claims_list_parser.add_argument("--status", default=None, help="Filter by validation status")
    claims_list_parser.add_argument(
        "--needs-review", action="store_true", default=False, help="Only claims needing review"
    )
    claims_list_parser.add_argument("--limit", "-n", type=int, default=100, help="Max results")
    claims_show_parser = claims_sub.add_parser("show", help="Show claim details")
    claims_show_parser.add_argument("claim_id", help="Claim ID")
    claims_review_parser = claims_sub.add_parser("review", help="Review a claim")
    claims_review_parser.add_argument("claim_id", help="Claim ID")
    claims_review_parser.add_argument("--attest", action="store_true", default=False, help="Attest the claim")
    claims_review_parser.add_argument("--challenge", action="store_true", default=False, help="Challenge the claim")
    claims_review_parser.add_argument("--reason", default="", help="Reason for the review decision")

    # --- watch ---
    watch_parser = subparsers.add_parser("watch", help="Standing query management")
    watch_sub = watch_parser.add_subparsers(dest="watch_command")
    watch_create_parser = watch_sub.add_parser("create", help="Create a standing query")
    watch_create_parser.add_argument("query", nargs="?", default=None, help="Watch query string")
    watch_create_parser.add_argument("--pattern", default=None, help="JSON filter pattern")
    watch_create_parser.add_argument("--name", default=None, help="Watch name")
    watch_list_parser = watch_sub.add_parser("list", help="List watches")
    watch_list_parser.add_argument("--all", action="store_true", default=False, help="Include inactive watches")
    watch_delete_parser = watch_sub.add_parser("delete", help="Deactivate a watch")
    watch_delete_parser.add_argument("query_id", help="Query ID to deactivate")

    # --- feed ---
    feed_parser = subparsers.add_parser("feed", help="Show knowledge feed")
    feed_parser.add_argument("--limit", "-n", type=int, default=20, help="Max items")
    feed_parser.add_argument("--offset", type=int, default=0, help="Skip items")

    # --- discover ---
    discover_parser = subparsers.add_parser("discover", help="Discover visible agents")
    discover_parser.add_argument("--query", "-q", default="", help="Search name, org, capabilities, or summary")
    discover_parser.add_argument("--status", default=None, help="Filter by agent status")
    discover_parser.add_argument("--org", default=None, help="Filter by org")
    discover_parser.add_argument("--visibility", choices=["private", "org", "shared", "published"], default=None)
    discover_parser.add_argument("--min-rep", type=float, default=0.0, help="Minimum reputation score")
    discover_parser.add_argument(
        "--sort", choices=["reputation", "followers", "created_at", "name"], default="reputation"
    )
    discover_parser.add_argument("--limit", "-n", type=int, default=20, help="Max items")
    discover_parser.add_argument("--offset", type=int, default=0, help="Skip items")

    # --- follow ---
    follow_parser = subparsers.add_parser("follow", help="Follow an agent/topic/entity/org")
    follow_parser.add_argument("target_type", choices=["agent", "topic", "entity", "org"], help="Target type")
    follow_parser.add_argument("id", help="Target ID")

    # --- following ---
    subparsers.add_parser("following", help="List who you follow")

    # --- followers ---
    subparsers.add_parser("followers", help="List your followers")

    # --- notifications ---
    notif_parser = subparsers.add_parser("notifications", help="Show notifications")
    notif_parser.add_argument("--mark-read", action="store_true", default=False, help="Mark as delivered")

    # --- status ---
    subparsers.add_parser("status", help="Server health + summary stats")

    return parser


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "store": cmd_store,
    "recall": cmd_recall,
    "relate": cmd_relate,
    "feed": cmd_feed,
    "discover": cmd_discover,
    "follow": cmd_follow,
    "following": cmd_following,
    "followers": cmd_followers,
    "notifications": cmd_notifications,
    "status": cmd_status,
}


def _dispatch(args: argparse.Namespace, client: Any) -> None:
    cmd = args.command

    if cmd == "auth":
        sub = getattr(args, "auth_command", None)
        if sub == "login":
            cmd_auth_login(args, client)
        elif sub == "status":
            cmd_auth_status(args, client)
        else:
            _err("Usage: cg auth {login|status}")
        return

    if cmd == "agents":
        sub = getattr(args, "agents_command", None)
        if sub == "list":
            cmd_agents_list(args, client)
        elif sub == "me":
            cmd_agents_me(args, client)
        elif sub == "show":
            cmd_agents_show(args, client)
        elif sub == "profile":
            cmd_agents_profile(args, client)
        elif sub == "trust":
            cmd_agents_trust(args, client)
        elif sub == "suspend":
            result = client.suspend_agent(args.agent_id, reason=args.reason)
            print(json.dumps(result, indent=2, default=str))
        elif sub == "wake":
            result = client.reactivate_agent(args.agent_id)
            print(json.dumps(result, indent=2, default=str))
        elif sub == "delete":
            result = client.delete_agent(args.agent_id)
            print(json.dumps(result, indent=2, default=str))
        else:
            _err("Usage: cg agents {list|me|show|profile|trust|suspend|wake|delete}")
        return

    if cmd == "sentinel":
        sub = getattr(args, "sentinel_command", None)
        if sub == "health":
            result = client.sentinel_health()
            print(json.dumps(result, indent=2, default=str))
        elif sub == "verdicts":
            result = client.sentinel_verdicts(claim_id=args.claim, decision=args.status)
            print(json.dumps(result, indent=2, default=str))
        else:
            _err("Usage: cg sentinel {health|verdicts}")
        return

    if cmd == "claims":
        sub = getattr(args, "claims_command", None)
        if sub == "list":
            cmd_claims_list(args, client)
        elif sub == "show":
            cmd_claims_show(args, client)
        elif sub == "review":
            cmd_claims_review(args, client)
        else:
            _err("Usage: cg claims {list|show <claim_id>|review <claim_id>}")
        return

    if cmd == "watch":
        sub = getattr(args, "watch_command", None)
        if sub == "create":
            cmd_watch_create(args, client)
        elif sub == "list":
            cmd_watch_list(args, client)
        elif sub == "delete":
            cmd_watch_delete(args, client)
        else:
            _err("Usage: cg watch {create|list|delete <query_id>}")
        return

    handler = _DISPATCH.get(cmd)
    if handler:
        handler(args, client)
    else:
        _err(f"Unknown command: {cmd}. Run 'cg --help' for usage.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # auth commands don't need a client
    client = None
    if args.command != "auth":
        try:
            client = _make_client()
        except SystemExit:
            raise
        except Exception as exc:
            _err(f"Failed to initialize client: {exc}")

    try:
        _dispatch(args, client)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except Exception as exc:
        _err(str(exc))


if __name__ == "__main__":
    main()
