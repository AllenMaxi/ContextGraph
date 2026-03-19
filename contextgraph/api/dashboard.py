"""GitHub-like dashboard for ContextGraph.

A clean, dark-themed operator console with agent profiles, knowledge browser,
activity feeds, review system, and graph explorer. Ships as pure HTML/CSS/JS
with zero build step — included in pip install.
"""

from __future__ import annotations

from html import escape
from typing import Any

from ..errors import AuthenticationError
from ..models import ValidationStatus, Visibility
from ..service import ContextGraphService
from ..utils import to_jsonable
from ._compat import HTMLResponse, RedirectResponse, Request

_COOKIE_NAME = "cg_session"


def register_dashboard_routes(app: Any, graph: ContextGraphService) -> None:
    """Register all dashboard routes on the FastAPI app."""

    def _get_agent(request: Request) -> Any:
        api_key = request.cookies.get(_COOKIE_NAME, "")
        if not api_key:
            return None
        try:
            return graph.authenticate_agent(api_key)
        except AuthenticationError:
            return None

    # ------------------------------------------------------------------
    # Auth routes
    # ------------------------------------------------------------------

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_index(request: Request) -> Any:
        agent = _get_agent(request)
        if agent is None:
            return HTMLResponse(_render_login())
        return HTMLResponse(_render_app(graph, agent, page="overview"))

    @app.get("/dashboard/{page}", response_class=HTMLResponse)
    async def dashboard_page(page: str, request: Request) -> Any:
        agent = _get_agent(request)
        if agent is None:
            return HTMLResponse(_render_login())
        return HTMLResponse(_render_app(graph, agent, page=page))

    @app.get("/dashboard/agents/{agent_id}", response_class=HTMLResponse)
    async def dashboard_agent_detail(agent_id: str, request: Request) -> Any:
        agent = _get_agent(request)
        if agent is None:
            return HTMLResponse(_render_login())
        return HTMLResponse(_render_app(graph, agent, page="agent-detail", detail_id=agent_id))

    @app.get("/dashboard/claims/{claim_id}", response_class=HTMLResponse)
    async def dashboard_claim_detail(claim_id: str, request: Request) -> Any:
        agent = _get_agent(request)
        if agent is None:
            return HTMLResponse(_render_login())
        return HTMLResponse(_render_app(graph, agent, page="claim-detail", detail_id=claim_id))

    @app.post("/dashboard/login")
    async def dashboard_login(request: Request) -> Any:
        form = await request.form()
        api_key = str(form.get("api_key", "")).strip()
        if not api_key:
            return HTMLResponse(_render_login(error="API key is required."), status_code=400)
        try:
            graph.authenticate_agent(api_key)
        except AuthenticationError as exc:
            return HTMLResponse(_render_login(error=str(exc)), status_code=401)
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key=_COOKIE_NAME, value=api_key, httponly=True, samesite="lax", max_age=86400)
        return response

    @app.get("/dashboard-logout")
    async def dashboard_logout() -> Any:
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.delete_cookie(_COOKIE_NAME)
        return response

    @app.post("/dashboard/review")
    async def dashboard_review(request: Request) -> Any:
        api_key = request.cookies.get(_COOKIE_NAME, "")
        form = await request.form()
        claim_id = str(form.get("claim_id", ""))
        decision = str(form.get("decision", ""))
        reason = str(form.get("reason", ""))
        agent = graph.authenticate_agent(api_key)
        graph.review_claim(reviewer_agent_id=agent.agent_id, claim_id=claim_id, decision=decision, reason=reason)
        return RedirectResponse(url="/dashboard/knowledge", status_code=303)

    # ------------------------------------------------------------------
    # API endpoints for dashboard JS
    # ------------------------------------------------------------------

    @app.get("/dashboard/api/graph-data")
    async def dashboard_graph_data(request: Request) -> Any:
        agent = _get_agent(request)
        if agent is None:
            return {"error": "Not authenticated"}
        entities = {}
        claims = graph.list_claims(requester_agent_id=agent.agent_id, limit=500)
        nodes = []
        edges = []
        for claim in claims:
            for eid in claim.entity_ids:
                if eid not in entities:
                    entity = graph.repository.get_entity(eid)
                    if entity:
                        entities[eid] = entity
                        nodes.append(
                            {
                                "id": eid,
                                "name": entity.name,
                                "type": entity.entity_type,
                                "alias": entity.alias_key,
                            }
                        )
            if len(claim.entity_ids) >= 2:
                for i in range(len(claim.entity_ids) - 1):
                    edges.append(
                        {
                            "source": claim.entity_ids[i],
                            "target": claim.entity_ids[i + 1],
                            "claim_id": claim.claim_id,
                            "statement": claim.statement,
                            "relation": claim.relation_type or "related_to",
                        }
                    )
        return {"nodes": nodes, "edges": edges}

    @app.get("/dashboard/api/activity")
    async def dashboard_activity(request: Request) -> Any:
        agent = _get_agent(request)
        if agent is None:
            return {"error": "Not authenticated"}
        entries = graph.list_audit_entries(requester_agent_id=agent.agent_id)
        recent = sorted(entries, key=lambda e: e.timestamp, reverse=True)[:20]
        return {"entries": to_jsonable(recent)}


# ======================================================================
# CSS
# ======================================================================

_CSS = """\
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --bg-card: #1c2128;
    --border: #30363d;
    --border-hover: #484f58;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #656d76;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-orange: #d29922;
    --accent-red: #f85149;
    --accent-purple: #bc8cff;
    --accent-cyan: #39d2c0;
    --radius: 6px;
    --radius-lg: 10px;
    --transition: 0.15s ease;
    --sidebar-width: 240px;
    --font-mono: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.5;
    overflow-x: hidden;
}

a { color: var(--accent-blue); text-decoration: none; }
a:hover { text-decoration: underline; }

.app-layout { display: flex; min-height: 100vh; }

.sidebar {
    width: var(--sidebar-width);
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    padding: 16px 0;
    position: fixed;
    top: 0; left: 0; bottom: 0;
    overflow-y: auto;
    z-index: 10;
}

.sidebar-logo { padding: 0 16px 16px; border-bottom: 1px solid var(--border); margin-bottom: 8px; }
.sidebar-logo h1 { font-size: 16px; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
.sidebar-logo .logo-icon { width: 24px; height: 24px; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue)); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 14px; }
.sidebar-nav { padding: 8px 8px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: var(--radius); color: var(--text-secondary); cursor: pointer; transition: background var(--transition), color var(--transition); text-decoration: none; font-size: 14px; }
.nav-item:hover { background: var(--bg-tertiary); color: var(--text-primary); text-decoration: none; }
.nav-item.active { background: var(--bg-tertiary); color: var(--text-primary); font-weight: 500; }
.nav-item .nav-icon { width: 20px; text-align: center; font-size: 15px; }
.nav-section { padding: 16px 12px 6px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--border); margin-top: auto; }
.agent-badge { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.agent-avatar { width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue)); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }

.main-content { margin-left: var(--sidebar-width); flex: 1; padding: 24px 32px; max-width: 1200px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
.page-header h2 { font-size: 20px; font-weight: 600; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 20px; transition: border-color var(--transition); }
.stat-card:hover { border-color: var(--border-hover); }
.stat-label { font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.stat-value { font-size: 28px; font-weight: 600; font-family: var(--font-mono); }
.stat-value.green { color: var(--accent-green); }
.stat-value.blue { color: var(--accent-blue); }
.stat-value.orange { color: var(--accent-orange); }
.stat-value.purple { color: var(--accent-purple); }
.stat-value.cyan { color: var(--accent-cyan); }

.item-list { display: flex; flex-direction: column; gap: 1px; }
.item-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 20px; transition: border-color var(--transition); }
.item-card:hover { border-color: var(--border-hover); }
.item-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px; }
.item-title { font-size: 15px; font-weight: 500; color: var(--text-primary); }
.item-meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: var(--text-secondary); }
.item-meta span { display: flex; align-items: center; gap: 4px; }

.badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; line-height: 1.5; }
.badge-green { background: rgba(63,185,80,0.15); color: var(--accent-green); border: 1px solid rgba(63,185,80,0.3); }
.badge-red { background: rgba(248,81,73,0.15); color: var(--accent-red); border: 1px solid rgba(248,81,73,0.3); }
.badge-yellow { background: rgba(210,153,34,0.15); color: var(--accent-orange); border: 1px solid rgba(210,153,34,0.3); }
.badge-blue { background: rgba(88,166,255,0.15); color: var(--accent-blue); border: 1px solid rgba(88,166,255,0.3); }
.badge-purple { background: rgba(188,140,255,0.15); color: var(--accent-purple); border: 1px solid rgba(188,140,255,0.3); }
.badge-cyan { background: rgba(57,210,192,0.15); color: var(--accent-cyan); border: 1px solid rgba(57,210,192,0.3); }

.entity-tag { display: inline-flex; padding: 1px 6px; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 4px; font-size: 11px; font-family: var(--font-mono); color: var(--accent-cyan); margin: 1px; }

.confidence-bar { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-family: var(--font-mono); }
.confidence-track { width: 60px; height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.confidence-fill { height: 100%; border-radius: 2px; transition: width 0.3s ease; }

.provenance { display: flex; flex-direction: column; gap: 8px; padding: 12px 0 0; border-top: 1px solid var(--border); margin-top: 12px; }
.provenance-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 4px; }
.provenance-entry { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); padding-left: 12px; border-left: 2px solid var(--border); }
.provenance-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.provenance-dot.created { background: var(--accent-blue); }
.provenance-dot.attested { background: var(--accent-green); }
.provenance-dot.challenged { background: var(--accent-red); }
.provenance-dot.updated { background: var(--accent-orange); }

.quorum { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-family: var(--font-mono); }
.quorum-pip { width: 8px; height: 8px; border-radius: 2px; background: var(--bg-tertiary); border: 1px solid var(--border); }
.quorum-pip.filled { background: var(--accent-green); border-color: var(--accent-green); }
.quorum-pip.needed { background: var(--bg-tertiary); border-color: var(--text-muted); }

.trust-bar { display: flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 13px; }
.trust-track { flex: 1; max-width: 120px; height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; }
.trust-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--accent-red), var(--accent-orange), var(--accent-green)); }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }
.col-header { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }

.btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: var(--radius); font-size: 13px; font-weight: 500; border: 1px solid var(--border); background: var(--bg-tertiary); color: var(--text-primary); cursor: pointer; transition: all var(--transition); }
.btn:hover { border-color: var(--border-hover); background: var(--border); }
.btn-green { border-color: rgba(63,185,80,0.4); color: var(--accent-green); }
.btn-green:hover { background: rgba(63,185,80,0.15); }
.btn-red { border-color: rgba(248,81,73,0.4); color: var(--accent-red); }
.btn-red:hover { background: rgba(248,81,73,0.15); }

.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.tab { padding: 10px 16px; font-size: 13px; color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; transition: all var(--transition); }
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--text-primary); border-bottom-color: var(--accent-blue); font-weight: 500; }

.feed-item { display: flex; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--border); }
.feed-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.feed-time { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }

#graph-canvas { width: 100%; height: 500px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-lg); }

.login-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: var(--bg-primary); }
.login-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 40px; width: 380px; text-align: center; }
.login-card h1 { font-size: 22px; margin-bottom: 6px; }
.login-card p { color: var(--text-secondary); font-size: 14px; margin-bottom: 24px; }
.login-card input[type="text"], .login-card input[type="password"] { width: 100%; padding: 10px 14px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: var(--radius); color: var(--text-primary); font-family: var(--font-mono); font-size: 13px; margin-bottom: 12px; outline: none; transition: border-color var(--transition); }
.login-card input:focus { border-color: var(--accent-blue); }
.login-card button { width: 100%; padding: 10px; background: var(--accent-blue); color: #fff; border: none; border-radius: var(--radius); font-size: 14px; font-weight: 500; cursor: pointer; transition: opacity var(--transition); }
.login-card button:hover { opacity: 0.9; }
.error-msg { background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3); color: var(--accent-red); padding: 8px 12px; border-radius: var(--radius); font-size: 13px; margin-bottom: 16px; }

.activity-item { display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; font-size: 13px; color: var(--text-secondary); }
.activity-icon { width: 24px; height: 24px; border-radius: 50%; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }

.impact-low { color: var(--text-muted); }
.impact-medium { color: var(--accent-blue); }
.impact-high { color: var(--accent-orange); }
.impact-critical { color: var(--accent-red); font-weight: 600; }

@media (max-width: 900px) {
    .sidebar { display: none; }
    .main-content { margin-left: 0; padding: 16px; }
    .two-col { grid-template-columns: 1fr; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
"""

# ======================================================================
# JS — Graph explorer (uses safe DOM methods, no innerHTML)
# ======================================================================

_GRAPH_JS = """\
(function() {
    var canvas = document.getElementById('graph-canvas');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var W, H, nodes = [], edges = [], dragging = null, hovered = null;
    var TYPE_COLORS = {
        company: '#58a6ff', person: '#bc8cff', organization: '#3fb950',
        topic: '#d29922', location: '#f85149', default: '#39d2c0'
    };

    function resize() {
        var r = canvas.parentElement.getBoundingClientRect();
        W = canvas.width = r.width;
        H = canvas.height = r.height || 500;
    }

    function init(data) {
        nodes = data.nodes.map(function(n) {
            return {
                id: n.id, name: n.name, type: n.type, alias: n.alias,
                x: W/2 + (Math.random()-0.5)*W*0.6,
                y: H/2 + (Math.random()-0.5)*H*0.6, vx: 0, vy: 0, radius: 8
            };
        });
        edges = data.edges;
        nodes.forEach(function(n) {
            n.radius = Math.min(8 + edges.filter(function(e) { return e.source===n.id||e.target===n.id; }).length*2, 20);
        });
        animate();
    }

    function tick() {
        var k = 0.01, repulse = 800, damp = 0.85;
        for (var i = 0; i < nodes.length; i++) {
            for (var j = i+1; j < nodes.length; j++) {
                var dx = nodes[j].x - nodes[i].x, dy = nodes[j].y - nodes[i].y;
                var d = Math.sqrt(dx*dx + dy*dy) || 1;
                var f = repulse / (d*d);
                nodes[i].vx -= dx/d*f; nodes[i].vy -= dy/d*f;
                nodes[j].vx += dx/d*f; nodes[j].vy += dy/d*f;
            }
        }
        var nodeMap = {};
        nodes.forEach(function(n) { nodeMap[n.id] = n; });
        edges.forEach(function(e) {
            var s = nodeMap[e.source], t = nodeMap[e.target];
            if (!s || !t) return;
            var dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx*dx+dy*dy) || 1;
            var f = (d - 100) * k;
            s.vx += dx/d*f; s.vy += dy/d*f;
            t.vx -= dx/d*f; t.vy -= dy/d*f;
        });
        nodes.forEach(function(n) {
            if (n === dragging) return;
            n.vx *= damp; n.vy *= damp;
            n.x += n.vx; n.y += n.vy;
            n.x = Math.max(n.radius, Math.min(W-n.radius, n.x));
            n.y = Math.max(n.radius, Math.min(H-n.radius, n.y));
        });
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);
        var nodeMap = {};
        nodes.forEach(function(n) { nodeMap[n.id] = n; });
        edges.forEach(function(e) {
            var s = nodeMap[e.source], t = nodeMap[e.target];
            if (!s || !t) return;
            ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y);
            ctx.strokeStyle = 'rgba(48,54,61,0.8)'; ctx.lineWidth = 1;
            ctx.stroke();
        });
        nodes.forEach(function(n) {
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI*2);
            ctx.fillStyle = TYPE_COLORS[n.type] || TYPE_COLORS['default'];
            if (n === hovered) ctx.fillStyle = '#fff';
            ctx.fill();
            ctx.strokeStyle = 'rgba(255,255,255,0.1)';
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = n === hovered ? '#fff' : 'rgba(230,237,243,0.7)';
            ctx.font = (n === hovered ? 'bold ' : '') + '11px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(n.name, n.x, n.y + n.radius + 14);
        });
    }

    function animate() { tick(); draw(); requestAnimationFrame(animate); }

    canvas.addEventListener('mousemove', function(e) {
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left, my = e.clientY - rect.top;
        hovered = null;
        for (var i = 0; i < nodes.length; i++) {
            if (Math.hypot(nodes[i].x-mx, nodes[i].y-my) < nodes[i].radius+4) { hovered = nodes[i]; break; }
        }
        canvas.style.cursor = hovered ? 'pointer' : 'default';
        if (dragging) { dragging.x = mx; dragging.y = my; }
    });
    canvas.addEventListener('mousedown', function() {
        if (hovered) { dragging = hovered; dragging.vx = 0; dragging.vy = 0; }
    });
    canvas.addEventListener('mouseup', function() { dragging = null; });

    resize();
    window.addEventListener('resize', resize);

    fetch('/dashboard/api/graph-data')
        .then(function(r) { return r.json(); })
        .then(function(data) { if (!data.error) init(data); })
        .catch(function() {});
})();
"""

# ======================================================================
# JS — SSE live feed (uses safe DOM creation, no innerHTML)
# ======================================================================

_LIVE_FEED_JS = """\
(function() {
    var feed = document.getElementById('live-feed');
    if (!feed) return;
    var indicator = document.getElementById('live-indicator');

    var evtSource;
    function connect() {
        try {
            evtSource = new EventSource('/v1/stream/feed');
        } catch(e) { return; }
        evtSource.onopen = function() { if(indicator) indicator.style.background = '#3fb950'; };
        evtSource.onerror = function() { if(indicator) indicator.style.background = '#f85149'; };
        evtSource.addEventListener('CLAIM_CREATED', function(e) { addFeedItem(JSON.parse(e.data), 'claim_created'); });
        evtSource.addEventListener('CLAIM_REVIEWED', function(e) { addFeedItem(JSON.parse(e.data), 'claim_reviewed'); });
        evtSource.addEventListener('MEMORY_STORED', function(e) { addFeedItem(JSON.parse(e.data), 'memory_stored'); });
        evtSource.addEventListener('QUORUM_MET', function(e) { addFeedItem(JSON.parse(e.data), 'quorum_met'); });
    }

    function addFeedItem(data, type) {
        var colors = { claim_created: '#58a6ff', claim_reviewed: '#3fb950', memory_stored: '#bc8cff', quorum_met: '#d29922' };
        var labels = { claim_created: 'New claim', claim_reviewed: 'Reviewed', memory_stored: 'Stored', quorum_met: 'Quorum met' };

        var item = document.createElement('div');
        item.className = 'feed-item';

        var dot = document.createElement('div');
        dot.className = 'feed-dot';
        dot.style.background = colors[type] || '#8b949e';
        item.appendChild(dot);

        var content = document.createElement('div');

        var title = document.createElement('div');
        title.style.fontSize = '13px';
        title.style.color = 'var(--text-primary)';
        title.textContent = labels[type] || type;
        content.appendChild(title);

        var desc = document.createElement('div');
        desc.style.fontSize = '12px';
        desc.style.color = 'var(--text-secondary)';
        desc.textContent = (data.statement || data.content_preview || JSON.stringify(data)).substring(0, 80);
        content.appendChild(desc);

        var time = document.createElement('div');
        time.className = 'feed-time';
        time.textContent = new Date().toLocaleTimeString();
        content.appendChild(time);

        item.appendChild(content);
        feed.insertBefore(item, feed.firstChild);
        if (feed.children.length > 50) feed.removeChild(feed.lastChild);
    }

    connect();
})();
"""


# ======================================================================
# Page renderers
# ======================================================================


def _render_login(error: str = "") -> str:
    error_html = f'<div class="error-msg">{escape(error)}</div>' if error else ""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>ContextGraph - Login</title>
    <style>{_CSS}</style>
</head>
<body>
<div class="login-page">
    <div class="login-card">
        <div style="font-size:36px;margin-bottom:12px">&#x1F310;</div>
        <h1>ContextGraph</h1>
        <p>The Knowledge Layer for AI Agents</p>
        {error_html}
        <form method="POST" action="/dashboard/login">
            <input type="password" name="api_key" placeholder="Enter your API key" required autofocus>
            <button type="submit">Sign In</button>
        </form>
    </div>
</div>
</body>
</html>"""


def _render_app(graph: ContextGraphService, agent: Any, page: str = "overview", detail_id: str = "") -> str:
    nav_items = [
        ("overview", "&#x1F4CA;", "Overview"),
        ("agents", "&#x1F916;", "Agents"),
        ("knowledge", "&#x1F9E0;", "Knowledge"),
        ("feed", "&#x1F4E1;", "Feed"),
        ("graph", "&#x1F578;&#xFE0F;", "Graph Explorer"),
        ("notifications", "&#x1F514;", "Notifications"),
    ]
    nav_html = ""
    for key, icon, label in nav_items:
        active = "active" if page == key else ""
        nav_html += (
            f'<a href="/dashboard/{key}" class="nav-item {active}"><span class="nav-icon">{icon}</span>{label}</a>\n'
        )

    page_html = _render_page(graph, agent, page, detail_id)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>ContextGraph Dashboard</title>
    <style>{_CSS}</style>
</head>
<body>
<div class="app-layout">
    <nav class="sidebar">
        <div class="sidebar-logo">
            <h1><span class="logo-icon">&#x1F310;</span> ContextGraph</h1>
        </div>
        <div class="sidebar-nav">
            <div class="nav-section">Navigation</div>
            {nav_html}
        </div>
        <div class="sidebar-footer">
            <div class="agent-badge">
                <div class="agent-avatar">{escape(agent.name[:2].upper())}</div>
                <div>
                    <div style="font-size:13px;font-weight:500">{escape(agent.name)}</div>
                    <div style="font-size:11px;color:var(--text-muted)">{escape(agent.org_id)}</div>
                </div>
            </div>
            <a href="/dashboard-logout" style="font-size:12px;color:var(--text-muted);display:block;margin-top:8px">Sign out</a>
        </div>
    </nav>
    <main class="main-content">
        {page_html}
    </main>
</div>
<script>{_GRAPH_JS}</script>
<script>{_LIVE_FEED_JS}</script>
</body>
</html>"""


def _render_page(graph: ContextGraphService, agent: Any, page: str, detail_id: str) -> str:
    if page == "overview":
        return _render_overview(graph, agent)
    if page == "agents":
        return _render_agents(graph, agent)
    if page == "agent-detail":
        return _render_agent_detail(graph, agent, detail_id)
    if page == "knowledge":
        return _render_knowledge(graph, agent)
    if page == "claim-detail":
        return _render_claim_detail(graph, agent, detail_id)
    if page == "feed":
        return _render_feed(graph, agent)
    if page == "graph":
        return _render_graph_explorer(graph, agent)
    if page == "notifications":
        return _render_notifications(graph, agent)
    return _render_overview(graph, agent)


def _render_overview(graph: ContextGraphService, agent: Any) -> str:
    snapshot = graph.repository.snapshot()
    claims = graph.list_claims(requester_agent_id=agent.agent_id, limit=500)
    attested = sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED)
    pending_quorum = sum(1 for c in claims if not c.quorum_met)

    entries = graph.list_audit_entries(requester_agent_id=agent.agent_id)
    recent = sorted(entries, key=lambda e: e.timestamp, reverse=True)[:10]
    activity_html = ""
    for entry in recent:
        icon = "&#x2795;" if "store" in entry.action else "&#x2705;" if "review" in entry.action else "&#x1F50D;"
        activity_html += f"""\
<div class="activity-item">
    <div class="activity-icon">{icon}</div>
    <div>
        <span style="color:var(--text-primary)">{escape(entry.action)}</span>
        <span> by {escape(entry.actor_agent_id[:12])}...</span>
        <div class="feed-time">{entry.timestamp.strftime("%Y-%m-%d %H:%M")}</div>
    </div>
</div>"""

    entity_counts: dict[str, int] = {}
    for claim in claims:
        for eid in claim.entity_ids:
            entity = graph.repository.get_entity(eid)
            if entity:
                entity_counts[entity.name] = entity_counts.get(entity.name, 0) + 1
    top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    entities_html = ""
    for name, count in top_entities:
        entities_html += f"""\
<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">
    <span class="entity-tag">{escape(name)}</span>
    <span style="font-family:var(--font-mono);font-size:12px;color:var(--text-secondary)">{count} claims</span>
</div>"""

    return f"""\
<div class="page-header">
    <h2>Overview</h2>
    <span style="font-size:12px;color:var(--text-muted)">v0.3.0</span>
</div>
<div class="stats-grid">
    <div class="stat-card"><div class="stat-label">Agents</div><div class="stat-value blue">{snapshot.get("agents", 0)}</div></div>
    <div class="stat-card"><div class="stat-label">Claims</div><div class="stat-value cyan">{snapshot.get("claims", 0)}</div></div>
    <div class="stat-card"><div class="stat-label">Memories</div><div class="stat-value purple">{snapshot.get("memories", 0)}</div></div>
    <div class="stat-card"><div class="stat-label">Attested</div><div class="stat-value green">{attested}</div></div>
    <div class="stat-card"><div class="stat-label">Pending Quorum</div><div class="stat-value orange">{pending_quorum}</div></div>
    <div class="stat-card"><div class="stat-label">Entities</div><div class="stat-value cyan">{snapshot.get("entities", 0)}</div></div>
</div>
<div class="two-col">
    <div>
        <div class="col-header">Recent Activity</div>
        {activity_html or '<div style="color:var(--text-muted);font-size:13px">No activity yet</div>'}
    </div>
    <div>
        <div class="col-header">Top Entities</div>
        {entities_html or '<div style="color:var(--text-muted);font-size:13px">No entities yet</div>'}
    </div>
</div>"""


def _render_agents(graph: ContextGraphService, agent: Any) -> str:
    agents = graph.list_agents(requester_agent_id=agent.agent_id)
    cards_html = ""
    for a in agents:
        claims = [c for c in graph.repository.list_claims() if c.source_agent_id == a.agent_id]
        trust_color = "green" if a.reputation_score >= 0.7 else "orange" if a.reputation_score >= 0.4 else "red"
        cards_html += f"""\
<a href="/dashboard/agents/{a.agent_id}" class="item-card" style="text-decoration:none;display:block;margin-bottom:8px">
    <div class="item-header">
        <div style="display:flex;align-items:center;gap:10px">
            <div class="agent-avatar">{escape(a.name[:2].upper())}</div>
            <div>
                <div class="item-title">{escape(a.name)}</div>
                <div style="font-size:12px;color:var(--text-secondary)">{escape(a.org_id)}</div>
            </div>
        </div>
        <span class="badge badge-green">active</span>
    </div>
    <div class="item-meta">
        <span>Claims: <b>{len(claims)}</b></span>
        <span>Trust: <b style="color:var(--accent-{trust_color})">{a.reputation_score:.2f}</b></span>
        <span>Followers: <b>{a.followers_count}</b></span>
    </div>
</a>"""

    return f"""\
<div class="page-header">
    <h2>Agents</h2>
    <span style="font-size:13px;color:var(--text-secondary)">{len(agents)} registered</span>
</div>
<div class="item-list">{cards_html or '<div style="color:var(--text-muted)">No agents registered yet</div>'}</div>"""


def _render_agent_detail(graph: ContextGraphService, viewer: Any, agent_id: str) -> str:
    try:
        target = graph.get_agent(agent_id)
    except Exception:
        return '<div style="color:var(--accent-red)">Agent not found</div>'

    claims = [c for c in graph.repository.list_claims() if c.source_agent_id == agent_id]
    attested = sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED)
    challenged = sum(1 for c in claims if c.validation_status == ValidationStatus.CHALLENGED)
    trust_pct = int(target.reputation_score * 100)

    claims_html = ""
    for claim in sorted(claims, key=lambda c: c.created_at, reverse=True)[:20]:
        vis_badge = _visibility_badge(claim.visibility)
        status_badge = _validation_badge(claim.validation_status)
        impact_cls = f"impact-{claim.impact.value}"
        claims_html += f"""\
<a href="/dashboard/claims/{claim.claim_id}" class="item-card" style="text-decoration:none;display:block;margin-bottom:6px">
    <div style="font-size:13px;color:var(--text-primary)">&ldquo;{escape(claim.statement[:120])}&rdquo;</div>
    <div class="item-meta" style="margin-top:6px">
        {status_badge} {vis_badge}
        <span class="{impact_cls}">{claim.impact.value.upper()}</span>
        {_confidence_html(claim.confidence)}
        {_quorum_html(claim)}
        <span style="color:var(--text-muted)">{claim.created_at.strftime("%b %d")}</span>
    </div>
</a>"""

    return f"""\
<div class="page-header">
    <h2 style="display:flex;align-items:center;gap:12px">
        <div class="agent-avatar" style="width:40px;height:40px;font-size:16px">{escape(target.name[:2].upper())}</div>
        <div>
            {escape(target.name)}
            <div style="font-size:13px;color:var(--text-secondary);font-weight:400">{escape(target.org_id)} &middot; {escape(agent_id[:16])}...</div>
        </div>
    </h2>
</div>
<div class="stats-grid">
    <div class="stat-card"><div class="stat-label">Trust Score</div>
        <div class="trust-bar"><div class="trust-track"><div class="trust-fill" style="width:{trust_pct}%"></div></div> <b>{target.reputation_score:.2f}</b></div>
    </div>
    <div class="stat-card"><div class="stat-label">Claims</div><div class="stat-value cyan">{len(claims)}</div></div>
    <div class="stat-card"><div class="stat-label">Attested</div><div class="stat-value green">{attested}</div></div>
    <div class="stat-card"><div class="stat-label">Challenged</div><div class="stat-value orange">{challenged}</div></div>
    <div class="stat-card"><div class="stat-label">Followers</div><div class="stat-value purple">{target.followers_count}</div></div>
</div>
<div class="col-header">Claims</div>
<div class="item-list">{claims_html or '<div style="color:var(--text-muted)">No claims yet</div>'}</div>"""


def _render_knowledge(graph: ContextGraphService, agent: Any) -> str:
    claims = graph.list_claims(requester_agent_id=agent.agent_id, limit=200)
    claims = sorted(claims, key=lambda c: c.created_at, reverse=True)

    cards_html = ""
    for claim in claims[:50]:
        source = graph.repository.get_agent(claim.source_agent_id)
        source_name = source.name if source else claim.source_agent_id[:12]
        vis_badge = _visibility_badge(claim.visibility)
        status_badge = _validation_badge(claim.validation_status)
        impact_cls = f"impact-{claim.impact.value}"

        entities_html = ""
        for eid in claim.entity_ids:
            entity = graph.repository.get_entity(eid)
            if entity:
                entities_html += f'<span class="entity-tag">{escape(entity.name)}</span>'

        cards_html += f"""\
<div class="item-card" style="margin-bottom:8px">
    <div class="item-header">
        <a href="/dashboard/claims/{claim.claim_id}" class="item-title" style="flex:1">&ldquo;{escape(claim.statement[:150])}&rdquo;</a>
    </div>
    <div class="item-meta">
        <span>by <a href="/dashboard/agents/{claim.source_agent_id}">{escape(source_name)}</a></span>
        <span>{escape(claim.source_org_id)}</span>
        {status_badge} {vis_badge}
        <span class="{impact_cls}">{claim.impact.value.upper()}</span>
        {_confidence_html(claim.confidence)}
        {_quorum_html(claim)}
    </div>
    <div style="margin-top:8px">{entities_html}</div>
    <div style="margin-top:8px;display:flex;gap:6px">
        <form method="POST" action="/dashboard/review" style="display:inline">
            <input type="hidden" name="claim_id" value="{claim.claim_id}">
            <input type="hidden" name="decision" value="attested">
            <button type="submit" class="btn btn-green" style="font-size:11px;padding:3px 10px">Attest</button>
        </form>
        <form method="POST" action="/dashboard/review" style="display:inline">
            <input type="hidden" name="claim_id" value="{claim.claim_id}">
            <input type="hidden" name="decision" value="challenged">
            <button type="submit" class="btn btn-red" style="font-size:11px;padding:3px 10px">Challenge</button>
        </form>
    </div>
</div>"""

    total = len(claims)
    attested = sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED)
    challenged = sum(1 for c in claims if c.validation_status == ValidationStatus.CHALLENGED)
    unreviewed = sum(1 for c in claims if c.validation_status == ValidationStatus.UNREVIEWED)

    return f"""\
<div class="page-header">
    <h2>Knowledge</h2>
    <span style="font-size:13px;color:var(--text-secondary)">{total} claims</span>
</div>
<div class="tabs">
    <div class="tab active">All ({total})</div>
    <div class="tab">Pending ({unreviewed})</div>
    <div class="tab">Attested ({attested})</div>
    <div class="tab">Challenged ({challenged})</div>
</div>
<div class="item-list">{cards_html or '<div style="color:var(--text-muted)">No claims yet</div>'}</div>"""


def _render_claim_detail(graph: ContextGraphService, agent: Any, claim_id: str) -> str:
    claim = graph.repository.get_claim(claim_id)
    if claim is None:
        return '<div style="color:var(--accent-red)">Claim not found</div>'

    source = graph.repository.get_agent(claim.source_agent_id)
    source_name = source.name if source else claim.source_agent_id[:12]

    entities_html = ""
    for eid in claim.entity_ids:
        entity = graph.repository.get_entity(eid)
        if entity:
            entities_html += f'<span class="entity-tag">{escape(entity.name)}</span> '

    prov_html = ""
    for entry in claim.provenance:
        dot_cls = entry.action if entry.action in ("created", "attested", "challenged", "updated") else "created"
        detail_span = f'<span style="color:var(--text-muted)">{escape(entry.detail)}</span>' if entry.detail else ""
        prov_html += f"""\
<div class="provenance-entry">
    <div class="provenance-dot {dot_cls}"></div>
    <span><b>{escape(entry.action)}</b> by {escape(entry.agent_id[:12])}...</span>
    <span style="color:var(--text-muted)">{entry.timestamp.strftime("%Y-%m-%d %H:%M")}</span>
    <span style="font-family:var(--font-mono);font-size:11px">conf: {entry.confidence_at_action:.2f}</span>
    {detail_span}
</div>"""

    impact_cls = f"impact-{claim.impact.value}"
    expires_info = f" &middot; Expires: {claim.expires_at.strftime('%Y-%m-%d')}" if claim.expires_at else ""
    price_info = f" &middot; Price: ${claim.price:.4f}" if claim.price > 0 else ""
    derived_info = (
        f'<div style="font-size:12px;color:var(--text-secondary)">Derived from: {", ".join(claim.derived_from)}</div>'
        if claim.derived_from
        else ""
    )

    return f"""\
<div class="page-header">
    <h2>Claim Detail</h2>
    <a href="/dashboard/knowledge" style="font-size:13px">Back to Knowledge</a>
</div>
<div class="item-card">
    <div style="font-size:16px;font-weight:500;margin-bottom:12px">&ldquo;{escape(claim.statement)}&rdquo;</div>
    <div class="item-meta" style="margin-bottom:12px">
        <span>by <a href="/dashboard/agents/{claim.source_agent_id}">{escape(source_name)}</a></span>
        <span>{escape(claim.source_org_id)}</span>
        {_validation_badge(claim.validation_status)}
        {_visibility_badge(claim.visibility)}
        <span class="{impact_cls}">{claim.impact.value.upper()}</span>
    </div>
    <div style="margin-bottom:12px">
        {_confidence_html(claim.confidence)}
        &nbsp;&nbsp;
        {_quorum_html(claim)}
    </div>
    <div style="margin-bottom:12px">{entities_html}</div>
    <div style="font-size:12px;color:var(--text-secondary);margin-bottom:8px">
        Created: {claim.created_at.strftime("%Y-%m-%d %H:%M")} &middot;
        Updated: {claim.updated_at.strftime("%Y-%m-%d %H:%M")}
        {expires_info}{price_info}
    </div>
    {derived_info}
    <div class="provenance">
        <div class="provenance-label">Provenance Chain</div>
        {prov_html or '<div style="font-size:12px;color:var(--text-muted)">No provenance entries</div>'}
    </div>
    <div style="margin-top:16px;display:flex;gap:8px">
        <form method="POST" action="/dashboard/review">
            <input type="hidden" name="claim_id" value="{claim.claim_id}">
            <input type="hidden" name="decision" value="attested">
            <button type="submit" class="btn btn-green">Attest</button>
        </form>
        <form method="POST" action="/dashboard/review">
            <input type="hidden" name="claim_id" value="{claim.claim_id}">
            <input type="hidden" name="decision" value="challenged">
            <button type="submit" class="btn btn-red">Challenge</button>
        </form>
    </div>
</div>"""


def _render_feed(graph: ContextGraphService, agent: Any) -> str:
    feed_items = graph.get_feed(agent_id=agent.agent_id, limit=30, offset=0)
    feed_html = ""
    for item in feed_items:
        item_data = to_jsonable(item)
        agent_name = item_data.get("source_agent_name", "Unknown")
        preview = item_data.get("content_preview", item_data.get("statement", ""))
        visibility = item_data.get("visibility", "")
        locked = item_data.get("locked", False)

        dot_color = "#f85149" if locked else "#3fb950" if visibility == "published" else "#58a6ff"
        lock_icon = "&#x1F512; " if locked else ""
        feed_html += f"""\
<div class="feed-item">
    <div class="feed-dot" style="background:{dot_color}"></div>
    <div style="flex:1">
        <div style="font-size:13px"><b>{escape(str(agent_name))}</b> shared knowledge</div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:2px">{lock_icon}{escape(str(preview)[:150])}</div>
    </div>
</div>"""

    return f"""\
<div class="page-header">
    <h2>Feed</h2>
    <div style="display:flex;align-items:center;gap:8px">
        <div id="live-indicator" style="width:8px;height:8px;border-radius:50%;background:var(--text-muted)"></div>
        <span style="font-size:12px;color:var(--text-secondary)">Live</span>
    </div>
</div>
<div id="live-feed">
    {feed_html or '<div style="color:var(--text-muted);padding:20px 0">No feed items yet. Follow agents or topics to see activity.</div>'}
</div>"""


def _render_graph_explorer(graph: ContextGraphService, agent: Any) -> str:
    return """\
<div class="page-header">
    <h2>Graph Explorer</h2>
    <span style="font-size:12px;color:var(--text-secondary)">Drag nodes to rearrange &middot; Hover for details</span>
</div>
<canvas id="graph-canvas"></canvas>
<div style="margin-top:12px;display:flex;gap:16px;font-size:12px;color:var(--text-secondary)">
    <span><span style="color:#58a6ff">&#x25CF;</span> Company</span>
    <span><span style="color:#bc8cff">&#x25CF;</span> Person</span>
    <span><span style="color:#3fb950">&#x25CF;</span> Organization</span>
    <span><span style="color:#d29922">&#x25CF;</span> Topic</span>
    <span><span style="color:#f85149">&#x25CF;</span> Location</span>
    <span><span style="color:#39d2c0">&#x25CF;</span> Other</span>
</div>"""


def _render_notifications(graph: ContextGraphService, agent: Any) -> str:
    notifications = graph.get_notifications(agent_id=agent.agent_id, mark_delivered=False)
    notifs_html = ""
    for notif in notifications[:30]:
        claim = graph.repository.get_claim(notif.claim_id)
        statement = claim.statement[:100] if claim else "Unknown claim"
        delivered_badge = (
            '<span class="badge badge-green">delivered</span>'
            if notif.delivered
            else '<span class="badge badge-yellow">new</span>'
        )
        notifs_html += f"""\
<div class="item-card" style="margin-bottom:6px">
    <div class="item-header">
        <div class="item-title" style="font-size:13px">{escape(notif.event_type)}</div>
        {delivered_badge}
    </div>
    <div style="font-size:12px;color:var(--text-secondary)">&ldquo;{escape(statement)}&rdquo;</div>
    <div class="feed-time">{notif.created_at.strftime("%Y-%m-%d %H:%M")}</div>
</div>"""

    return f"""\
<div class="page-header">
    <h2>Notifications</h2>
    <span style="font-size:13px;color:var(--text-secondary)">{len(notifications)} total</span>
</div>
<div class="item-list">{notifs_html or '<div style="color:var(--text-muted)">No notifications</div>'}</div>"""


# ======================================================================
# Helper functions
# ======================================================================


def _visibility_badge(vis: Visibility) -> str:
    colors = {
        Visibility.PRIVATE: "badge-purple",
        Visibility.ORG: "badge-blue",
        Visibility.SHARED: "badge-cyan",
        Visibility.PUBLISHED: "badge-green",
    }
    return f'<span class="badge {colors.get(vis, "badge-blue")}">{vis.value}</span>'


def _validation_badge(status: ValidationStatus) -> str:
    colors = {
        ValidationStatus.ATTESTED: "badge-green",
        ValidationStatus.CHALLENGED: "badge-red",
        ValidationStatus.UNREVIEWED: "badge-yellow",
        ValidationStatus.EXPIRED: "badge-purple",
    }
    return f'<span class="badge {colors.get(status, "badge-yellow")}">{status.value}</span>'


def _confidence_html(confidence: float) -> str:
    pct = int(confidence * 100)
    color = (
        "var(--accent-green)"
        if confidence >= 0.8
        else "var(--accent-orange)"
        if confidence >= 0.5
        else "var(--accent-red)"
    )
    return f"""\
<span class="confidence-bar">
    <span class="confidence-track"><span class="confidence-fill" style="width:{pct}%;background:{color}"></span></span>
    {confidence:.2f}
</span>"""


def _quorum_html(claim: Any) -> str:
    if claim.quorum_required == 0:
        return ""
    pips = ""
    for i in range(claim.quorum_required):
        filled = "filled" if i < claim.attestation_count else "needed"
        pips += f'<span class="quorum-pip {filled}"></span>'
    check = "&#x2713;" if claim.quorum_met else "&#x23F3;"
    return f'<span class="quorum">{pips} {claim.attestation_count}/{claim.quorum_required} {check}</span>'
