"""ContextGraph Playground — interactive context compiler demo.

A zero-friction demo page at ``/playground`` that compiles governed context packs
from a pre-seeded corpus and shows three agents receiving different results from
the same query in a three-column compare view.

No login required. The corpus is seeded lazily on first visit.
"""

from __future__ import annotations

import json
import logging
from html import escape
from typing import Any

from ..models import ContextPack
from ..service import ContextGraphService
from ..utils import to_jsonable
from ._compat import HTMLResponse, Request

# ---------------------------------------------------------------------------
# Playground agent / corpus constants
# ---------------------------------------------------------------------------

_PLAYGROUND_ORG_ACME = "playground-acme"
_PLAYGROUND_ORG_GLOBEX = "playground-globex"
_PLAYGROUND_AGENTS = {
    "alice": {"name": "playground-alice", "org": _PLAYGROUND_ORG_ACME, "label": "owner", "color": "#3fb950"},
    "carol": {"name": "playground-carol", "org": _PLAYGROUND_ORG_ACME, "label": "teammate", "color": "#d29922"},
    "bob": {"name": "playground-bob", "org": _PLAYGROUND_ORG_GLOBEX, "label": "external", "color": "#f85149"},
}

_DEFAULT_QUERY = "payment service architecture incidents"
_DEFAULT_BUDGET = 2000
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed corpus
# ---------------------------------------------------------------------------


def _seed_playground_corpus(graph: ContextGraphService) -> dict[str, str]:
    """Create playground agents and memories. Returns agent name → agent_id map.

    Idempotent: skips if playground agents already exist.
    """
    existing_agents = {
        agent.name: agent for agent in graph.repository.list_agents() if agent.name.startswith("playground-")
    }

    def ensure_agent(name: str, org_id: str, tags: list[str]) -> str:
        existing = existing_agents.get(name)
        if existing is not None:
            return existing.agent_id
        agent = graph.register_agent(name, org_id, tags)
        existing_agents[name] = agent
        return agent.agent_id

    def ensure_memory(
        owner_agent_id: str,
        content: str,
        *,
        visibility: str,
        access_list: list[str] | None = None,
        price: float = 0.0,
    ) -> None:
        visible_memories = graph.list_memories(
            requester_agent_id=owner_agent_id,
            include_private_same_org=True,
            include_inactive=True,
            limit=1000,
        )
        for memory in visible_memories:
            if memory.agent_id != owner_agent_id:
                continue
            if memory.content == content:
                return
        graph.store_memory(
            agent_id=owner_agent_id,
            content=content,
            visibility=visibility,
            access_list=access_list,
            price=price,
        )

    alice_id = ensure_agent("playground-alice", _PLAYGROUND_ORG_ACME, ["engineering"])
    carol_id = ensure_agent("playground-carol", _PLAYGROUND_ORG_ACME, ["engineering"])
    bob_id = ensure_agent("playground-bob", _PLAYGROUND_ORG_GLOBEX, ["integration"])
    oncall_id = ensure_agent("playground-oncall", _PLAYGROUND_ORG_ACME, ["operations"])

    agents_by_name = {
        "playground-alice": alice_id,
        "playground-carol": carol_id,
        "playground-bob": bob_id,
        "playground-oncall": oncall_id,
    }

    # --- Memories ---

    # Alice: architecture decision (org-visible)
    ensure_memory(
        alice_id,
        content=(
            "Architecture decision: the payment service migrates from REST to gRPC "
            "for internal service-to-service communication. REST remains for external APIs. "
            "Target completion: end of Q2. All internal teams should plan migration."
        ),
        visibility="org",
    )

    # Alice: auth details (org-visible)
    ensure_memory(
        alice_id,
        content=(
            "The authentication service uses JWT tokens with RS256 signing. "
            "Token lifetime is 15 minutes with refresh tokens valid for 7 days. "
            "All tokens are validated by the API gateway before reaching backend services."
        ),
        visibility="org",
    )

    # Alice: private postmortem
    ensure_memory(
        alice_id,
        content=(
            "Internal postmortem: the gRPC migration was rushed without load testing. "
            "Connection pool defaults were insufficient for production traffic patterns. "
            "Recommendation: mandatory load testing gate for all protocol migrations."
        ),
        visibility="private",
    )

    # Alice: partner preview note (shared to Bob only)
    ensure_memory(
        alice_id,
        content=(
            "Partner preview: Bob at Globex can access the staged gRPC sandbox endpoint "
            "for payment service testing before the external rollout. This rollout note "
            "is shared only with the named integration partner."
        ),
        visibility="shared",
        access_list=[bob_id],
    )

    # Oncall: incident report (published)
    ensure_memory(
        oncall_id,
        content=(
            "Incident INC-2024-042: payment service latency spike to 2.3s p99 "
            "caused by connection pool exhaustion. Root cause: gRPC migration "
            "introduced incompatible keepalive settings. Mitigated by rolling back "
            "to REST endpoints. Permanent fix pending."
        ),
        visibility="published",
    )

    # Oncall: auth incident (published)
    ensure_memory(
        oncall_id,
        content=(
            "Incident INC-2024-043: authentication token validation failures "
            "affecting 3 percent of requests. Caused by clock skew between API gateway "
            "and auth service after NTP misconfiguration. Resolved within 45 minutes."
        ),
        visibility="published",
    )

    # Bob: integration report (published, priced)
    ensure_memory(
        bob_id,
        content=(
            "Globex integration status: REST webhook delivery from Acme payment service "
            "has been reliable at 99.97 percent over the past quarter. No gRPC endpoint "
            "is currently available for partner integrations."
        ),
        visibility="published",
        price=5.0,
    )

    return agents_by_name


def _get_playground_agents(graph: ContextGraphService) -> dict[str, str]:
    """Return playground agent name → agent_id map, seeding if needed."""
    return _seed_playground_corpus(graph)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_playground_routes(app: Any, graph: ContextGraphService) -> None:
    """Register the ``/playground`` route on the FastAPI app."""

    @app.get("/playground", response_class=HTMLResponse)
    async def playground(request: Request) -> Any:
        params = dict(request.query_params)
        query = params.get("q", "").strip()
        budget_str = params.get("budget", str(_DEFAULT_BUDGET))
        try:
            budget = max(50, min(int(budget_str), 8000))
        except (ValueError, TypeError):
            budget = _DEFAULT_BUDGET

        agents = _get_playground_agents(graph)
        alice_id = agents.get("playground-alice", "")
        carol_id = agents.get("playground-carol", "")
        bob_id = agents.get("playground-bob", "")

        packs: list[tuple[dict[str, Any], ContextPack | None]] = []

        agent_org_map = _build_agent_org_map(graph)

        if query and alice_id:
            for agent_key, agent_id in [("alice", alice_id), ("carol", carol_id), ("bob", bob_id)]:
                try:
                    pack = graph.compile_context(
                        agent_id=agent_id,
                        query=query,
                        token_budget=budget,
                        include_explanations=True,
                    )
                    packs.append((_PLAYGROUND_AGENTS[agent_key], pack))
                except Exception:
                    logger.exception(
                        "Playground failed to compile context",
                        extra={"agent_key": agent_key, "query": query, "token_budget": budget},
                    )
                    packs.append((_PLAYGROUND_AGENTS[agent_key], None))
        else:
            for agent_key in ("alice", "carol", "bob"):
                packs.append((_PLAYGROUND_AGENTS[agent_key], None))

        return HTMLResponse(_render_playground(query or _DEFAULT_QUERY, budget, packs, agent_org_map))


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

_CSS = """\
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #656d76;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-orange: #d29922;
    --accent-red: #f85149;
    --radius: 6px;
    --font-mono: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.5;
}
a { color: var(--accent-blue); text-decoration: none; }
a:hover { text-decoration: underline; }

.pg-topbar {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.pg-topbar h1 {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
}
.pg-topbar h1 span { color: var(--accent-blue); }
.pg-topbar-right {
    display: flex;
    gap: 16px;
    align-items: center;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
}

.pg-query-bar {
    padding: 16px 24px;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border);
}
.pg-query-form {
    display: flex;
    gap: 12px;
    align-items: flex-end;
}
.pg-query-form label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    display: block;
    margin-bottom: 4px;
}
.pg-query-form input[type="text"] {
    flex: 1;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 8px 12px;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 13px;
    outline: none;
}
.pg-query-form input[type="text"]:focus {
    border-color: var(--accent-blue);
}
.pg-budget-group {
    width: 180px;
}
.pg-budget-row {
    display: flex;
    align-items: center;
    gap: 8px;
}
.pg-budget-row input[type="range"] {
    flex: 1;
    accent-color: var(--accent-green);
    height: 6px;
}
.pg-budget-row span {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-primary);
    min-width: 40px;
    text-align: right;
}
.pg-compile-btn {
    background: #238636;
    color: #fff;
    border: none;
    border-radius: var(--radius);
    padding: 8px 24px;
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
}
.pg-compile-btn:hover { background: #2ea043; }

.pg-columns {
    display: flex;
    gap: 1px;
    background: var(--bg-tertiary);
    min-height: 400px;
}
.pg-col {
    flex: 1;
    background: var(--bg-primary);
    padding: 20px;
    overflow-y: auto;
}

.pg-agent-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}
.pg-agent-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}
.pg-agent-name {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 14px;
}
.pg-agent-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-secondary);
}

.pg-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 12px;
}
.pg-badge {
    font-family: var(--font-mono);
    font-size: 10px;
    padding: 1px 8px;
    border-radius: 4px;
    white-space: nowrap;
}
.pg-badge-green { background: #238636; color: #fff; }
.pg-badge-red { background: #da3633; color: #fff; }
.pg-badge-blue { background: #1f6feb; color: #fff; }
.pg-badge-gray { background: var(--bg-tertiary); color: var(--text-secondary); }
.pg-badge-orange { background: #9e6a03; color: #fff; }

.pg-summary {
    background: var(--bg-secondary);
    padding: 10px 12px;
    border-radius: var(--radius);
    margin-bottom: 12px;
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.6;
    color: var(--text-primary);
    border-left: 3px solid var(--accent-green);
}

.pg-claim-list {
    font-family: var(--font-mono);
    font-size: 11px;
}
.pg-claim {
    padding: 5px 0;
    border-bottom: 1px solid var(--bg-secondary);
    color: var(--text-primary);
    line-height: 1.5;
}
.pg-claim:last-child { border-bottom: none; }
.pg-claim-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}
.pg-claim-tag {
    font-size: 9px;
    padding: 0 4px;
    border-radius: 3px;
    margin-left: 4px;
    vertical-align: middle;
}
.pg-claim-tag-scope-private { background: #8957e5; color: #fff; }
.pg-claim-tag-scope-org { background: var(--accent-blue); color: #fff; }
.pg-claim-tag-scope-shared { background: #0aa2c0; color: #fff; }
.pg-claim-tag-scope-published { background: var(--accent-green); color: #fff; }
.pg-claim-tag-source-cross { background: var(--accent-blue); color: #fff; }
.pg-claim-tag-source-same { background: var(--bg-tertiary); color: var(--text-secondary); }
.pg-claim-tag-state-locked { background: var(--accent-red); color: #fff; }
.pg-claim-tag-state-stale { background: var(--accent-orange); color: #fff; }
.pg-claim-tag-state-conflict { background: var(--accent-red); color: #fff; }
.pg-more-toggle {
    padding: 4px 0;
    color: var(--text-secondary);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
}
.pg-more-toggle:hover { color: var(--accent-blue); }
.pg-hidden { display: none; }

.pg-warnings {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--bg-tertiary);
    font-family: var(--font-mono);
    font-size: 10px;
}
.pg-warn { padding: 2px 0; }
.pg-warn-red { color: var(--accent-red); }
.pg-warn-orange { color: var(--accent-orange); }
.pg-warn-gray { color: var(--text-muted); }

.pg-footer {
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    padding: 10px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.pg-footer-left {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
}
.pg-footer-right {
    display: flex;
    gap: 16px;
}
.pg-footer-right a, .pg-footer-right button {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--accent-blue);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
}
.pg-footer-right a:hover, .pg-footer-right button:hover { text-decoration: underline; }

.pg-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 300px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 13px;
    text-align: center;
}

.pg-json-block {
    margin-top: 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-secondary);
    max-height: 300px;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-all;
}
"""

_JS = """\
function updateBudgetLabel(val) {
    document.getElementById('budget-label').textContent = val;
}
function toggleMore(id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle('pg-hidden');
}
function toggleJson(id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle('pg-hidden');
}
function copyApiCall() {
    var q = document.getElementById('q-input').value;
    var b = document.getElementById('budget-slider').value;
    var cmd = 'curl -X POST http://localhost:8420/v1/context/compile -H "Content-Type: application/json"'
        + ' -H "X-Agent-Key: YOUR_API_KEY"'
        + ' -d \\'{\"query\": \"' + q + '\", \"token_budget\": ' + b + ', \"include_explanations\": true}\\'';
    navigator.clipboard.writeText(cmd).then(function() {
        var btn = document.getElementById('copy-btn');
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.textContent = 'Copy API call'; }, 2000);
    });
}
"""


_json_toggle_btn = "<button onclick=\"document.querySelectorAll('.pg-json-block').forEach(e=>e.classList.toggle('pg-hidden'))\">View raw JSON</button>"
_copy_btn = "<button id='copy-btn' onclick='copyApiCall()'>Copy API call</button>"


def _render_playground(
    query: str,
    budget: int,
    packs: list[tuple[dict[str, Any], ContextPack | None]],
    agent_org_map: dict[str, str] | None = None,
) -> str:
    has_results = any(p is not None for _, p in packs)
    columns_html = ""

    if has_results:
        for agent_info, pack in packs:
            columns_html += _render_column(agent_info, pack, agent_org_map)
    else:
        columns_html = (
            '<div class="pg-empty" style="flex:1;">'
            "<div>Type a query above and click <b>Compile</b> to see governed context packs.<br>"
            "<span style='color:var(--accent-blue);'>Three agents. Same corpus. Different results.</span></div>"
            "</div>"
        )

    tagline = "Same query. Same corpus. Three different governed packs." if has_results else ""

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>ContextGraph Playground</title>
    <style>{_CSS}</style>
</head>
<body>
<div class="pg-topbar">
    <h1><span>&#x25C6;</span> ContextGraph Playground</h1>
    <div class="pg-topbar-right">
        <span>Pre-seeded with 7 memories across 4 agents</span>
        <a href="/dashboard">Dashboard</a>
        <a href="https://github.com/AllenMaxi/ContextGraph" target="_blank">GitHub &#x2197;</a>
    </div>
</div>

<div class="pg-query-bar">
    <form class="pg-query-form" method="GET" action="/playground">
        <div style="flex:1;">
            <label for="q-input">Query</label>
            <input type="text" id="q-input" name="q" value="{escape(query)}" placeholder="e.g. payment service architecture" autocomplete="off">
        </div>
        <div class="pg-budget-group">
            <label>Token Budget</label>
            <div class="pg-budget-row">
                <input type="range" id="budget-slider" name="budget" min="100" max="8000" step="100" value="{budget}" oninput="updateBudgetLabel(this.value)">
                <span id="budget-label">{budget}</span>
            </div>
        </div>
        <div>
            <label>&nbsp;</label>
            <button type="submit" class="pg-compile-btn">Compile &#x25B6;</button>
        </div>
    </form>
</div>

<div class="pg-columns">
    {columns_html}
</div>

<div class="pg-footer">
    <div class="pg-footer-left">{tagline}</div>
    <div class="pg-footer-right">
        {_json_toggle_btn if has_results else ""}
        {_copy_btn if has_results else ""}
        <a href="https://github.com/AllenMaxi/ContextGraph" target="_blank">&#x2B50; Star on GitHub</a>
    </div>
</div>

<script>{_JS}</script>
</body>
</html>"""


def _build_agent_org_map(graph: ContextGraphService) -> dict[str, str]:
    """Return agent_id → org_id map for playground agents."""
    result: dict[str, str] = {}
    for agent in graph.repository.list_agents():
        if agent.name.startswith("playground-"):
            result[agent.agent_id] = agent.org_id
    return result


def _claim_tag(label: str, class_name: str) -> str:
    return f'<span class="pg-claim-tag {class_name}">{escape(label)}</span>'


def _claim_scope_tag(visibility: str) -> str:
    scope_classes = {
        "private": "pg-claim-tag-scope-private",
        "org": "pg-claim-tag-scope-org",
        "shared": "pg-claim-tag-scope-shared",
        "published": "pg-claim-tag-scope-published",
    }
    css_class = scope_classes.get(visibility, "pg-claim-tag-source-same")
    return _claim_tag(visibility or "unknown", css_class)


def _claim_tags(
    claim: Any,
    *,
    agent_info: dict[str, Any],
    agent_org_map: dict[str, str] | None,
    is_conflict: bool,
) -> str:
    tags = [_claim_scope_tag(str(getattr(claim, "visibility", "")))]
    viewer_org = agent_info["org"]
    if agent_org_map:
        source_org = agent_org_map.get(claim.source_agent_id, "")
        if source_org and source_org != viewer_org:
            org_label = source_org.replace("playground-", "")
            tags.append(_claim_tag(f"from {org_label}", "pg-claim-tag-source-cross"))
        elif source_org:
            org_label = source_org.replace("playground-", "")
            tags.append(_claim_tag(org_label, "pg-claim-tag-source-same"))
    if claim.locked:
        tags.append(_claim_tag("locked", "pg-claim-tag-state-locked"))
    if claim.staleness_warning:
        tags.append(_claim_tag("stale", "pg-claim-tag-state-stale"))
    elif is_conflict:
        tags.append(_claim_tag("conflict", "pg-claim-tag-state-conflict"))
    return "".join(tags)


def _render_column(
    agent_info: dict[str, Any], pack: ContextPack | None, agent_org_map: dict[str, str] | None = None
) -> str:
    name = agent_info["name"].replace("playground-", "").capitalize()
    color = agent_info["color"]
    label = agent_info["label"]
    org = agent_info["org"].replace("playground-", "")
    col_id = name.lower()

    if pack is None:
        return f"""\
<div class="pg-col">
    <div class="pg-agent-header">
        <div class="pg-agent-dot" style="background:{color}"></div>
        <span class="pg-agent-name" style="color:{color}">{name}</span>
        <span class="pg-agent-label">{label} &middot; {org}</span>
    </div>
    <div class="pg-empty" style="min-height:200px;">Waiting for query...</div>
</div>"""

    # Stats
    included_count = len(pack.included_claims)
    conflict_count = len(pack.conflicting_claims)
    total_count = included_count + conflict_count
    locked_count = sum(1 for c in pack.excluded_claims if c.locked)
    stale_count = pack.stale_claim_count

    badges = f'<span class="pg-badge pg-badge-green">{total_count} claims</span>'
    if conflict_count > 0:
        badges += (
            f'<span class="pg-badge pg-badge-red">{conflict_count} conflict{"s" if conflict_count > 1 else ""}</span>'
        )
    if locked_count > 0:
        badges += f'<span class="pg-badge pg-badge-gray">{locked_count} locked</span>'
    if pack.compression_ratio > 0:
        badges += f'<span class="pg-badge pg-badge-blue">{pack.compression_ratio}x</span>'
    badges += f'<span class="pg-badge pg-badge-gray">{pack.tokens_used} / {pack.token_budget} tok</span>'

    # Summary
    summary_html = ""
    if pack.summary:
        summary_text = escape(pack.summary[:200]) + ("..." if len(pack.summary) > 200 else "")
        summary_html = f'<div class="pg-summary" style="border-left-color:{color}">{summary_text}</div>'

    # Claims list
    conflicting_ids = {claim.claim_id for claim in pack.conflicting_claims}
    all_claims = pack.included_claims + pack.conflicting_claims
    claims_html = ""
    for i, claim in enumerate(all_claims):
        hidden_class = " pg-hidden" if i >= 3 else ""
        extra_id = f' id="more-{col_id}"' if i == 3 else ""
        is_conflict = claim.claim_id in conflicting_ids

        if claim.locked:
            dot_color = "var(--accent-red)"
            text = '<span style="color:var(--text-muted);font-style:italic;">Paid claim &mdash; locked</span>'
        else:
            dot_color = "var(--accent-red)" if is_conflict else "var(--accent-green)"
            text = escape(claim.statement[:120]) + ("..." if len(claim.statement) > 120 else "")

        tags_html = _claim_tags(
            claim,
            agent_info=agent_info,
            agent_org_map=agent_org_map,
            is_conflict=is_conflict,
        )

        wrap_start = f'<div{extra_id} class="{hidden_class.strip()}">' if i >= 3 else ""
        claims_html += f"""\
{wrap_start}<div class="pg-claim">
    <span class="pg-claim-dot" style="background:{dot_color}"></span>{text}{tags_html}
</div>"""

    # Close the hidden wrapper
    if len(all_claims) > 3:
        claims_html += "</div>"
        remaining = len(all_claims) - 3
        claims_html += f'<div class="pg-more-toggle" onclick="toggleMore(\'more-{col_id}\')">&#x25B8; {remaining} more claim{"s" if remaining > 1 else ""}</div>'

    # Also show locked claims from excluded
    for claim in pack.excluded_claims:
        if claim.locked:
            tags_html = _claim_tags(
                claim,
                agent_info=agent_info,
                agent_org_map=agent_org_map,
                is_conflict=False,
            )
            claims_html += (
                '<div class="pg-claim">'
                '<span class="pg-claim-dot" style="background:var(--accent-red)"></span>'
                '<span style="color:var(--text-muted);font-style:italic;">Paid claim &mdash; locked</span>'
                f"{tags_html}"
                "</div>"
            )

    # Warnings
    warnings_html = ""
    warning_items = []
    visible_claims = all_claims + [claim for claim in pack.excluded_claims if claim.locked]
    visible_scopes = {claim.visibility for claim in visible_claims if claim.visibility}
    if conflict_count > 0:
        warning_items.append(
            f'<div class="pg-warn pg-warn-red">&#x26A0; {conflict_count} conflict{"s" if conflict_count > 1 else ""} detected</div>'
        )
    if locked_count > 0:
        warning_items.append(
            f'<div class="pg-warn pg-warn-red">&#x1F512; {locked_count} paid claim{"s" if locked_count > 1 else ""} requires payment</div>'
        )
    if stale_count > 0:
        warning_items.append(
            f'<div class="pg-warn pg-warn-orange">&#x26A0; {stale_count} stale claim{"s" if stale_count > 1 else ""} &mdash; verify before acting</div>'
        )
    if total_count == 0 and locked_count == 0:
        warning_items.append('<div class="pg-warn pg-warn-gray">No accessible claims for this agent</div>')
    elif label == "external":
        if "shared" in visible_scopes and "published" in visible_scopes:
            warning_items.append(
                '<div class="pg-warn pg-warn-gray">Published and explicitly shared claims visible</div>'
            )
        elif "shared" in visible_scopes:
            warning_items.append('<div class="pg-warn pg-warn-gray">Only explicitly shared claims visible</div>')
        else:
            warning_items.append('<div class="pg-warn pg-warn-gray">Only published claims visible</div>')
    elif label == "teammate":
        warning_items.append('<div class="pg-warn pg-warn-gray">No private claims visible</div>')

    if warning_items:
        warnings_html = '<div class="pg-warnings">' + "".join(warning_items) + "</div>"

    # JSON block (hidden by default)
    pack_json = json.dumps(to_jsonable(pack), indent=2, default=str)
    json_html = f'<div class="pg-json-block pg-hidden">{escape(pack_json)}</div>'

    return f"""\
<div class="pg-col">
    <div class="pg-agent-header">
        <div class="pg-agent-dot" style="background:{color}"></div>
        <span class="pg-agent-name" style="color:{color}">{name}</span>
        <span class="pg-agent-label">{label} &middot; {org}</span>
    </div>
    <div class="pg-badges">{badges}</div>
    {summary_html}
    <div class="pg-claim-list">{claims_html}</div>
    {warnings_html}
    {json_html}
</div>"""
