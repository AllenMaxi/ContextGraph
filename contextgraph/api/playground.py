"""ContextGraph Playground — interactive context compiler demo.

A zero-friction demo page at ``/playground`` that compiles governed context packs
from a pre-seeded corpus and shows three agents receiving different results from
the same query in a three-column compare view.

No login required. The corpus is seeded lazily on first visit.
"""

from __future__ import annotations

import json
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

_seeded_services: set[int] = set()  # tracks which service instances have been seeded


# ---------------------------------------------------------------------------
# Seed corpus
# ---------------------------------------------------------------------------


def _seed_playground_corpus(graph: ContextGraphService) -> dict[str, str]:
    """Create playground agents and memories. Returns agent name → agent_id map.

    Idempotent: skips if playground agents already exist.
    """
    agents_by_name: dict[str, str] = {}

    # Check if already seeded
    existing = graph.repository.list_agents()
    for agent in existing:
        if agent.name.startswith("playground-"):
            agents_by_name[agent.name] = agent.agent_id

    if len(agents_by_name) >= 4:
        _seeded_services.add(id(graph))
        return agents_by_name

    # Register agents
    alice = graph.register_agent("playground-alice", _PLAYGROUND_ORG_ACME, ["engineering"])
    carol = graph.register_agent("playground-carol", _PLAYGROUND_ORG_ACME, ["engineering"])
    bob = graph.register_agent("playground-bob", _PLAYGROUND_ORG_GLOBEX, ["integration"])
    oncall = graph.register_agent("playground-oncall", _PLAYGROUND_ORG_ACME, ["operations"])

    agents_by_name = {
        "playground-alice": alice.agent_id,
        "playground-carol": carol.agent_id,
        "playground-bob": bob.agent_id,
        "playground-oncall": oncall.agent_id,
    }

    # --- Memories ---

    # Alice: architecture decision (org-visible)
    graph.store_memory(
        agent_id=alice.agent_id,
        content=(
            "Architecture decision: the payment service migrates from REST to gRPC "
            "for internal service-to-service communication. REST remains for external APIs. "
            "Target completion: end of Q2. All internal teams should plan migration."
        ),
        visibility="org",
    )

    # Alice: auth details (org-visible)
    graph.store_memory(
        agent_id=alice.agent_id,
        content=(
            "The authentication service uses JWT tokens with RS256 signing. "
            "Token lifetime is 15 minutes with refresh tokens valid for 7 days. "
            "All tokens are validated by the API gateway before reaching backend services."
        ),
        visibility="org",
    )

    # Alice: private postmortem
    graph.store_memory(
        agent_id=alice.agent_id,
        content=(
            "Internal postmortem: the gRPC migration was rushed without load testing. "
            "Connection pool defaults were insufficient for production traffic patterns. "
            "Recommendation: mandatory load testing gate for all protocol migrations."
        ),
        visibility="private",
    )

    # Oncall: incident report (published)
    graph.store_memory(
        agent_id=oncall.agent_id,
        content=(
            "Incident INC-2024-042: payment service latency spike to 2.3s p99 "
            "caused by connection pool exhaustion. Root cause: gRPC migration "
            "introduced incompatible keepalive settings. Mitigated by rolling back "
            "to REST endpoints. Permanent fix pending."
        ),
        visibility="published",
    )

    # Oncall: auth incident (published)
    graph.store_memory(
        agent_id=oncall.agent_id,
        content=(
            "Incident INC-2024-043: authentication token validation failures "
            "affecting 3 percent of requests. Caused by clock skew between API gateway "
            "and auth service after NTP misconfiguration. Resolved within 45 minutes."
        ),
        visibility="published",
    )

    # Bob: integration report (published, priced)
    graph.store_memory(
        agent_id=bob.agent_id,
        content=(
            "Globex integration status: REST webhook delivery from Acme payment service "
            "has been reliable at 99.97 percent over the past quarter. No gRPC endpoint "
            "is currently available for partner integrations."
        ),
        visibility="published",
        price=5.0,
    )

    _seeded_services.add(id(graph))
    return agents_by_name


def _get_playground_agents(graph: ContextGraphService) -> dict[str, str]:
    """Return playground agent name → agent_id map, seeding if needed."""
    if id(graph) not in _seeded_services:
        return _seed_playground_corpus(graph)
    agents: dict[str, str] = {}
    for agent in graph.repository.list_agents():
        if agent.name.startswith("playground-"):
            agents[agent.name] = agent.agent_id
    return agents


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
                    packs.append((_PLAYGROUND_AGENTS[agent_key], None))
        else:
            for agent_key in ("alice", "carol", "bob"):
                packs.append((_PLAYGROUND_AGENTS[agent_key], None))

        return HTMLResponse(_render_playground(query or _DEFAULT_QUERY, budget, packs))


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


def _render_playground(query: str, budget: int, packs: list[tuple[dict[str, Any], ContextPack | None]]) -> str:
    has_results = any(p is not None for _, p in packs)
    columns_html = ""

    if has_results:
        for agent_info, pack in packs:
            columns_html += _render_column(agent_info, pack)
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
        <span>Pre-seeded with 6 memories across 3 agents</span>
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


def _render_column(agent_info: dict[str, Any], pack: ContextPack | None) -> str:
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
    all_claims = pack.included_claims + pack.conflicting_claims
    claims_html = ""
    for i, claim in enumerate(all_claims):
        hidden_class = " pg-hidden" if i >= 3 else ""
        extra_id = f' id="more-{col_id}"' if i == 3 else ""

        if claim.locked:
            dot_color = color
            text = '<span style="color:var(--text-muted);font-style:italic;">Paid claim &mdash; locked</span>'
            tag = '<span class="pg-claim-tag" style="background:var(--accent-red);color:#fff;">&#x1F512;</span>'
        else:
            is_conflict = claim.claim_id in {c.claim_id for c in pack.conflicting_claims}
            dot_color = "var(--accent-red)" if is_conflict else "var(--accent-green)"
            text = escape(claim.statement[:120]) + ("..." if len(claim.statement) > 120 else "")
            tag = ""
            if claim.staleness_warning:
                tag = '<span class="pg-claim-tag" style="background:var(--accent-orange);color:#fff;">stale</span>'
            elif is_conflict:
                tag = '<span class="pg-claim-tag" style="background:var(--accent-red);color:#fff;">conflict</span>'

        wrap_start = f'<div{extra_id} class="{hidden_class.strip()}">' if i >= 3 else ""
        claims_html += f"""\
{wrap_start}<div class="pg-claim">
    <span class="pg-claim-dot" style="background:{dot_color}"></span>{text}{tag}
</div>"""

    # Close the hidden wrapper
    if len(all_claims) > 3:
        claims_html += "</div>"
        remaining = len(all_claims) - 3
        claims_html += f'<div class="pg-more-toggle" onclick="toggleMore(\'more-{col_id}\')">&#x25B8; {remaining} more claim{"s" if remaining > 1 else ""}</div>'

    # Also show locked claims from excluded
    for claim in pack.excluded_claims:
        if claim.locked:
            claims_html += (
                '<div class="pg-claim">'
                '<span class="pg-claim-dot" style="background:var(--accent-red)"></span>'
                '<span style="color:var(--text-muted);font-style:italic;">Paid claim &mdash; locked</span>'
                '<span class="pg-claim-tag" style="background:var(--accent-red);color:#fff;">&#x1F512;</span>'
                "</div>"
            )

    # Warnings
    warnings_html = ""
    warning_items = []
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
