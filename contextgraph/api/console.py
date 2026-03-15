from __future__ import annotations

from html import escape
from typing import Any

from ..errors import AuthenticationError
from ..service import ContextGraphService
from ._compat import HTMLResponse, RedirectResponse, Request

_COOKIE_NAME = "cg_session"


def register_console_routes(app: Any, graph: ContextGraphService) -> None:
    @app.get("/console", response_class=HTMLResponse)
    async def console(request: Request) -> Any:
        api_key = request.cookies.get(_COOKIE_NAME, "")
        if not api_key:
            return HTMLResponse(_render_login())
        try:
            agent = graph.authenticate_agent(api_key)
        except AuthenticationError as exc:
            response = HTMLResponse(_render_login(error=str(exc)), status_code=401)
            response.delete_cookie(_COOKIE_NAME)
            return response

        return HTMLResponse(
            _render_console(
                agent_name=agent.name,
                agent_id=agent.agent_id,
                agent_org_id=agent.org_id,
                api_key=agent.api_key,
            )
        )

    @app.post("/console/login")
    async def console_login(request: Request) -> Any:
        form = await request.form()
        api_key = str(form.get("api_key", "")).strip()
        if not api_key:
            return HTMLResponse(_render_login(error="API key is required."), status_code=400)
        try:
            graph.authenticate_agent(api_key)
        except AuthenticationError as exc:
            return HTMLResponse(_render_login(error=str(exc)), status_code=401)
        response = RedirectResponse(url="/console", status_code=303)
        response.set_cookie(
            key=_COOKIE_NAME,
            value=api_key,
            httponly=True,
            samesite="lax",
            max_age=86400,
        )
        return response

    @app.get("/console/logout")
    async def console_logout() -> Any:
        response = RedirectResponse(url="/console", status_code=303)
        response.delete_cookie(_COOKIE_NAME)
        return response

    @app.post("/console/review")
    async def review_claim(request: Request) -> Any:
        api_key = request.cookies.get(_COOKIE_NAME, "")
        form = await request.form()
        claim_id = str(form.get("claim_id", ""))
        decision = str(form.get("decision", ""))
        reason = str(form.get("reason", ""))

        agent = graph.authenticate_agent(api_key)
        graph.review_claim(
            reviewer_agent_id=agent.agent_id,
            claim_id=claim_id,
            decision=decision,
            reason=reason,
        )
        return RedirectResponse(url="/console#reviews", status_code=303)

    @app.post("/console/maintenance/claim-expiry-sweep")
    async def trigger_claim_expiry_sweep(request: Request) -> Any:
        api_key = request.cookies.get(_COOKIE_NAME, "")
        agent = graph.authenticate_agent(api_key)
        graph.enqueue_claim_expiry_sweep(requester_agent_id=agent.agent_id)
        return RedirectResponse(url="/console#jobs", status_code=303)


def _render_login(error: str | None = None) -> str:
    error_html = ""
    if error:
        error_html = f"<p class='error'>{escape(error)}</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextGraph Console</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0a0a0c;
      color: #e4e4e7;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .login-card {{
      background: #111113;
      border: 1px solid #27272a;
      border-radius: 16px;
      padding: 40px;
      width: 100%;
      max-width: 420px;
      box-shadow: 0 25px 50px rgba(0,0,0,0.5);
    }}
    h1 {{
      font-size: 1.5rem;
      margin-bottom: 8px;
      color: #e4e4e7;
    }}
    .subtitle {{
      color: #71717a;
      font-size: 0.9rem;
      margin-bottom: 24px;
    }}
    label {{
      display: block;
      font-size: 0.85rem;
      color: #a1a1aa;
      margin-bottom: 6px;
    }}
    input {{
      width: 100%;
      padding: 10px 14px;
      background: #0a0a0c;
      border: 1px solid #27272a;
      border-radius: 8px;
      color: #e4e4e7;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s;
    }}
    input:focus {{
      border-color: #22c55e;
    }}
    button {{
      width: 100%;
      margin-top: 16px;
      padding: 10px 14px;
      background: #22c55e;
      color: #0a0a0c;
      border: none;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }}
    button:hover {{
      background: #16a34a;
    }}
    .error {{
      color: #ef4444;
      font-size: 0.85rem;
      margin-bottom: 12px;
    }}
  </style>
</head>
<body>
  <div class="login-card">
    <h1>ContextGraph Console</h1>
    <p class="subtitle">Paste an agent API key to open the dashboard.</p>
    {error_html}
    <form action="/console/login" method="post">
      <label for="api_key">API key</label>
      <input id="api_key" name="api_key" type="password" required
             placeholder="cg_..." autocomplete="off" />
      <button type="submit">Open Console</button>
    </form>
  </div>
</body>
</html>"""


def _render_console(*, agent_name: str, agent_id: str, agent_org_id: str, api_key: str) -> str:
    safe_name = escape(agent_name)
    safe_agent_id = escape(agent_id)
    safe_agent_org_id = escape(agent_org_id)
    safe_api_key = escape(api_key)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>ContextGraph Console</title>\n"
        "  <style>\n" + _dashboard_css() + "\n  </style>\n"
        "</head>\n"
        f'<body data-agent-id="{safe_agent_id}" data-org-id="{safe_agent_org_id}" data-api-key="{safe_api_key}">\n'
        '  <nav id="sidebar">\n'
        '    <div class="logo">CG</div>\n'
        '    <a href="#overview" class="nav-item" data-page="overview" title="Knowledge Overview">\n'
        "      <svg viewBox='0 0 24 24' width='22' height='22' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<path d='M3 12l9-8 9 8'/>"
        "<path d='M5 10.5V20h14v-9.5'/>"
        "<path d='M10 20v-5h4v5'/></svg>\n"
        "    </a>\n"
        '    <a href="#graph" class="nav-item" data-page="graph" title="Graph Explorer">\n'
        "      <svg viewBox='0 0 24 24' width='22' height='22' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<circle cx='5' cy='6' r='3'/><circle cx='19' cy='6' r='3'/>"
        "<circle cx='12' cy='19' r='3'/>"
        "<line x1='7.5' y1='7.5' x2='10.5' y2='17'/>"
        "<line x1='16.5' y1='7.5' x2='13.5' y2='17'/></svg>\n"
        "    </a>\n"
        '    <a href="#feed" class="nav-item" data-page="feed" title="Knowledge Feed">\n'
        "      <svg viewBox='0 0 24 24' width='22' height='22' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<path d='M4 11a9 9 0 0 1 9 9'/>"
        "<path d='M4 4a16 16 0 0 1 16 16'/>"
        "<circle cx='5' cy='19' r='1' fill='currentColor'/></svg>\n"
        "    </a>\n"
        '    <a href="#claims" class="nav-item" data-page="claims" title="Claims">\n'
        "      <svg viewBox='0 0 24 24' width='22' height='22' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<rect x='3' y='3' width='18' height='18' rx='2'/>"
        "<line x1='8' y1='8' x2='16' y2='8'/>"
        "<line x1='8' y1='12' x2='16' y2='12'/>"
        "<line x1='8' y1='16' x2='12' y2='16'/></svg>\n"
        "    </a>\n"
        '    <a href="#agents" class="nav-item" data-page="agents" title="Agents">\n'
        "      <svg viewBox='0 0 24 24' width='22' height='22' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<circle cx='9' cy='7' r='4'/>"
        "<path d='M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2'/>"
        "<circle cx='19' cy='7' r='3'/>"
        "<path d='M22 21v-1a3 3 0 0 0-3-3h-1'/></svg>\n"
        "    </a>\n"
        '    <a href="#settings" class="nav-item" data-page="settings" title="Settings">\n'
        "      <svg viewBox='0 0 24 24' width='22' height='22' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<circle cx='12' cy='12' r='3'/>"
        "<path d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 "
        "2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21"
        "a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82"
        ".33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15"
        "a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 "
        "4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06"
        ".06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 "
        "4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06"
        "a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 "
        "0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z'/></svg>\n"
        "    </a>\n"
        "  </nav>\n"
        '  <main id="main">\n'
        '    <header id="header">\n'
        f'      <h1 id="page-title">Knowledge Overview</h1>\n'
        f'      <span class="agent-name">{safe_name}</span>\n'
        "    </header>\n"
        '    <div id="content"></div>\n'
        "  </main>\n"
        '  <aside id="panel" class="closed">\n'
        '    <div class="panel-header">\n'
        '      <h2 id="panel-title"></h2>\n'
        '      <button id="panel-close" onclick="closePanel()">\n'
        "        <svg viewBox='0 0 24 24' width='18' height='18' fill='none' "
        "stroke='currentColor' stroke-width='2'>"
        "<line x1='18' y1='6' x2='6' y2='18'/>"
        "<line x1='6' y1='6' x2='18' y2='18'/></svg>\n"
        "      </button>\n"
        "    </div>\n"
        '    <div id="panel-body"></div>\n'
        "  </aside>\n"
        "  <script>\n" + _dashboard_js() + "\n  </script>\n"
        "</body>\n"
        "</html>"
    )


def _dashboard_css() -> str:
    return """
    :root {
      --bg: #0a0a0c;
      --surface: #111113;
      --surface-hover: #1a1a1e;
      --border: #27272a;
      --text: #e4e4e7;
      --text-sec: #a1a1aa;
      --text-muted: #71717a;
      --green: #22c55e;
      --green-h: #16a34a;
      --amber: #f59e0b;
      --red: #ef4444;
      --purple: #818cf8;
      --sidebar-w: 60px;
      --panel-w: 420px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      min-height: 100vh;
      overflow-x: hidden;
    }
    #sidebar {
      position: fixed; left: 0; top: 0; bottom: 0;
      width: var(--sidebar-w);
      background: var(--surface);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding-top: 12px;
      z-index: 100;
    }
    .logo {
      font-weight: 800;
      font-size: 1rem;
      color: var(--green);
      margin-bottom: 24px;
      letter-spacing: -0.5px;
    }
    .nav-item {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 42px; height: 42px;
      margin-bottom: 8px;
      border-radius: 10px;
      color: var(--text-muted);
      text-decoration: none;
      transition: all 0.15s;
    }
    .nav-item:hover { background: var(--surface-hover); color: var(--text); }
    .nav-item.active { background: var(--surface-hover); color: var(--green); }
    #main {
      margin-left: var(--sidebar-w);
      flex: 1;
      min-height: 100vh;
      transition: margin-right 0.3s;
    }
    body.panel-open #main { margin-right: var(--panel-w); }
    #header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 28px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      position: sticky;
      top: 0;
      z-index: 50;
    }
    #header h1 { font-size: 1.15rem; font-weight: 600; }
    .agent-name { color: var(--text-sec); font-size: 0.85rem; }
    #content { padding: 24px 28px; }

    /* Panel */
    #panel {
      position: fixed;
      right: 0; top: 0; bottom: 0;
      width: var(--panel-w);
      background: var(--surface);
      border-left: 1px solid var(--border);
      transform: translateX(100%);
      transition: transform 0.3s ease;
      z-index: 90;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }
    #panel.open { transform: translateX(0); }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      background: var(--surface);
    }
    .panel-header h2 { font-size: 1rem; font-weight: 600; }
    .panel-header button {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      padding: 4px;
    }
    .panel-header button:hover { color: var(--text); }
    #panel-body { padding: 20px; flex: 1; }

    /* Cards */
    .card-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .card:hover {
      border-color: #3f3f46;
      background: var(--surface-hover);
    }
    .card-statement {
      font-size: 0.92rem;
      line-height: 1.5;
      margin-bottom: 10px;
      color: var(--text);
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .card-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 0.78rem;
      color: var(--text-muted);
      align-items: center;
    }

    /* Badges */
    .badge {
      display: inline-flex;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .badge-published, .badge-PUBLISHED {
      background: rgba(34,197,94,0.15); color: var(--green);
    }
    .badge-private, .badge-PRIVATE {
      background: rgba(239,68,68,0.15); color: var(--red);
    }
    .badge-org, .badge-ORG {
      background: rgba(245,158,11,0.15); color: var(--amber);
    }
    .badge-shared, .badge-SHARED {
      background: rgba(129,140,248,0.15); color: var(--purple);
    }
    .badge-tone-locked {
      background: rgba(239,68,68,0.15); color: var(--red);
    }
    .badge-tone-paid {
      background: rgba(245,158,11,0.15); color: var(--amber);
    }
    .badge-tone-internal {
      background: rgba(34,197,94,0.15); color: var(--green);
    }
    .badge-tone-follow {
      background: rgba(129,140,248,0.15); color: var(--purple);
    }
    .badge-tone-open {
      background: rgba(228,228,231,0.08); color: var(--text-sec);
    }
    .badge-tone-review {
      background: rgba(245,158,11,0.15); color: var(--amber);
    }
    .badge-tone-verified {
      background: rgba(34,197,94,0.15); color: var(--green);
    }
    .badge-tone-challenged {
      background: rgba(239,68,68,0.15); color: var(--red);
    }
    .badge-tone-stale {
      background: rgba(239,68,68,0.15); color: #fca5a5;
    }
    .badge-tone-expiring {
      background: rgba(245,158,11,0.15); color: #fbbf24;
    }

    /* Stat cards */
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
    }
    .stat-card .label {
      font-size: 0.78rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 6px;
    }
    .stat-card .value {
      font-size: 1.6rem;
      font-weight: 700;
    }

    /* Tabs/filters */
    .tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }
    .filter-block {
      margin-bottom: 18px;
    }
    .filter-label {
      display: block;
      margin-bottom: 8px;
      font-size: 0.78rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .tab {
      padding: 6px 14px;
      border-radius: 8px;
      font-size: 0.82rem;
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-sec);
      cursor: pointer;
      transition: all 0.15s;
    }
    .tab:hover { background: var(--surface-hover); }
    .tab.active {
      background: var(--green); color: #0a0a0c; border-color: var(--green);
    }

    /* Buttons */
    .btn {
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      border: none;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-primary { background: var(--green); color: #0a0a0c; }
    .btn-primary:hover { background: var(--green-h); }
    .btn-danger { background: var(--red); color: white; }
    .btn-danger:hover { background: #dc2626; }
    .btn-secondary {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-sec);
    }
    .btn-secondary:hover { background: var(--surface-hover); }
    .btn-sm { padding: 5px 12px; font-size: 0.78rem; }

    /* Form controls */
    .form-group { margin-bottom: 14px; }
    .form-group label {
      display: block;
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 4px;
    }
    .form-group input, .form-group select, .form-group textarea {
      width: 100%;
      padding: 8px 12px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-size: 0.88rem;
      outline: none;
    }
    .form-group input:focus, .form-group select:focus,
    .form-group textarea:focus {
      border-color: var(--green);
    }
    .form-group select { cursor: pointer; }

    /* Reputation bar */
    .rep-bar {
      height: 6px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
      width: 100%;
    }
    .rep-fill {
      height: 100%;
      border-radius: 3px;
      transition: width 0.3s;
    }

    /* Entity tags */
    .entity-tag {
      display: inline-flex;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.72rem;
      background: rgba(129,140,248,0.1);
      color: var(--purple);
      margin: 2px;
    }

    /* Overview */
    .overview-grid {
      display: grid;
      gap: 18px;
    }
    .section-card {
      background: linear-gradient(180deg, rgba(26,26,30,0.96), rgba(17,17,19,0.96));
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 14px;
    }
    .section-head h3 {
      font-size: 0.96rem;
      font-weight: 600;
    }
    .section-head p {
      color: var(--text-muted);
      font-size: 0.82rem;
    }
    .section-meta {
      color: var(--text-muted);
      font-size: 0.78rem;
      white-space: nowrap;
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .mini-card {
      background: rgba(10,10,12,0.75);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      cursor: pointer;
      transition: border-color 0.15s, transform 0.15s;
    }
    .mini-card:hover {
      border-color: #3f3f46;
      transform: translateY(-1px);
    }
    .mini-card-title {
      font-size: 0.9rem;
      line-height: 1.45;
      margin: 10px 0 8px;
      color: var(--text);
    }
    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .following-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .follow-pill {
      background: rgba(10,10,12,0.75);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
    }
    .follow-pill strong {
      display: block;
      font-size: 0.88rem;
      margin-bottom: 6px;
      color: var(--text);
    }
    .follow-pill span {
      color: var(--text-muted);
      font-size: 0.8rem;
      word-break: break-word;
    }
    .locked-note {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 12px;
      padding: 8px 10px;
      border-radius: 10px;
      background: rgba(239,68,68,0.08);
      border: 1px solid rgba(239,68,68,0.22);
      color: #fca5a5;
      font-size: 0.8rem;
    }
    .muted-copy {
      color: var(--text-muted);
      font-size: 0.82rem;
      line-height: 1.5;
    }
    .inline-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    .detail-list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .detail-list-item {
      background: rgba(10,10,12,0.7);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
    }

    /* Loading */
    .loading {
      text-align: center;
      padding: 60px 0;
      color: var(--text-muted);
    }
    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
    }
    .empty-state h3 {
      color: var(--text-sec);
      margin-bottom: 8px;
    }

    /* Graph canvas */
    #graph-canvas {
      width: 100%;
      height: calc(100vh - 65px);
      display: block;
      cursor: grab;
    }
    #graph-canvas:active { cursor: grabbing; }

    /* Panel detail sections */
    .detail-section { margin-bottom: 16px; }
    .detail-section h4 {
      font-size: 0.78rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 6px;
    }
    .detail-section p, .detail-section pre {
      font-size: 0.88rem;
      line-height: 1.5;
      color: var(--text);
    }
    .detail-section pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: var(--bg);
      padding: 10px;
      border-radius: 8px;
      border: 1px solid var(--border);
      max-height: 300px;
      overflow-y: auto;
    }

    /* Health indicators */
    .health-row {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 0;
      font-size: 0.88rem;
    }
    .health-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .health-dot.ok {
      background: var(--green); box-shadow: 0 0 6px var(--green);
    }
    .health-dot.warn {
      background: var(--amber); box-shadow: 0 0 6px var(--amber);
    }
    .health-dot.err {
      background: var(--red); box-shadow: 0 0 6px var(--red);
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 3px; }

    @media (max-width: 800px) {
      #sidebar { width: 48px; }
      #main { margin-left: 48px; }
      .card-grid { grid-template-columns: 1fr; }
      .stat-grid { grid-template-columns: repeat(2, 1fr); }
      #panel { width: 100%; }
    }
    """


def _dashboard_js() -> str:
    return r"""
    // --- Auth helpers ---
    const API_KEY = document.body.dataset.apiKey || '';
    const CONSOLE_AGENT_ID = document.body.dataset.agentId || '';
    const CONSOLE_ORG_ID = document.body.dataset.orgId || '';
    const headers = {
      'X-Agent-Key': API_KEY,
      'Content-Type': 'application/json'
    };

    async function fetchJSON(url) {
      const r = await fetch(url, {headers});
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    }
    async function postJSON(url, body) {
      const r = await fetch(url, {
        method: 'POST', headers, body: JSON.stringify(body)
      });
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    }
    async function patchJSON(url, body) {
      const r = await fetch(url, {
        method: 'PATCH', headers, body: JSON.stringify(body)
      });
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    }
    async function deleteJSON(url) {
      const r = await fetch(url, {method: 'DELETE', headers});
      if (!r.ok && r.status !== 204) throw new Error(r.statusText);
    }

    // --- Panel ---
    function openPanel(title, contentHTML) {
      document.getElementById('panel-title').textContent = title;
      document.getElementById('panel-body').innerHTML = contentHTML;
      document.getElementById('panel').classList.add('open');
      document.body.classList.add('panel-open');
    }
    function closePanel() {
      document.getElementById('panel').classList.remove('open');
      document.body.classList.remove('panel-open');
    }

    // --- Utility ---
    function esc(s) {
      var d = document.createElement('div');
      d.textContent = s == null ? '' : String(s);
      return d.innerHTML;
    }
    function visibilityBadge(v) {
      return '<span class="badge badge-' + esc(v) + '">'
        + esc(v) + '</span>';
    }
    function statusBadge(label, tone) {
      return '<span class="badge badge-tone-' + esc(tone) + '">'
        + esc(label) + '</span>';
    }
    function parseDate(value) {
      return value ? new Date(value) : null;
    }
    function isExpiredDate(value) {
      var dt = parseDate(value);
      return !!(dt && dt.getTime() <= Date.now());
    }
    function isExpiringSoon(value) {
      var dt = parseDate(value);
      if (!dt || dt.getTime() <= Date.now()) return false;
      return (dt.getTime() - Date.now()) <= (3 * 24 * 60 * 60 * 1000);
    }
    function formatDateShort(value) {
      var dt = parseDate(value);
      if (!dt) return 'No expiry';
      return dt.toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric'
      });
    }
    function claimHealthBadges(claims) {
      if (!claims || !claims.length) return '';
      var badges = [];
      var hasExpired = claims.some(function(c) {
        return c.validation_status === 'expired' || isExpiredDate(c.expires_at);
      });
      var hasChallenged = claims.some(function(c) {
        return c.validation_status === 'challenged';
      });
      var hasAttested = claims.some(function(c) {
        return c.validation_status === 'attested';
      });
      var hasUnreviewed = claims.some(function(c) {
        return c.validation_status === 'unreviewed';
      });
      var hasExpiringSoon = claims.some(function(c) {
        return isExpiringSoon(c.expires_at);
      });

      if (hasExpired) {
        badges.push(statusBadge('stale', 'stale'));
      } else if (hasChallenged) {
        badges.push(statusBadge('challenged', 'challenged'));
      } else if (hasAttested) {
        badges.push(statusBadge('verified', 'verified'));
      } else if (hasUnreviewed) {
        badges.push(statusBadge('needs review', 'review'));
      }
      if (hasExpiringSoon) {
        badges.push(statusBadge('expiring soon', 'expiring'));
      }
      return badges.join('');
    }
    function matchesClaimHealth(claim, filter) {
      var expired = claim.validation_status === 'expired' || isExpiredDate(claim.expires_at);
      if (filter === 'all') return true;
      if (filter === 'review') return claim.validation_status === 'unreviewed' && !expired;
      if (filter === 'verified') return claim.validation_status === 'attested' && !expired;
      if (filter === 'challenged') return claim.validation_status === 'challenged' && !expired;
      if (filter === 'stale') return expired;
      if (filter === 'expiring') return !expired && isExpiringSoon(claim.expires_at);
      return true;
    }
    function repColor(score) {
      if (score >= 0.7) return 'var(--green)';
      if (score >= 0.4) return 'var(--amber)';
      return 'var(--red)';
    }
    function agentColor(agentId) {
      var h = 0;
      for (var i = 0; i < agentId.length; i++) {
        h = (h * 31 + agentId.charCodeAt(i)) & 0xffffff;
      }
      return 'hsl(' + (h % 360) + ', 65%, 55%)';
    }
    function entityTags(entities) {
      if (!entities || !entities.length) return '';
      return entities.map(function(e) {
        var name = typeof e === 'string'
          ? e : (e.name || e.entity_id || e);
        return '<span class="entity-tag">' + esc(name) + '</span>';
      }).join('');
    }
    function feedBadges(item) {
      var badges = [visibilityBadge(item.visibility)];
      var health = claimHealthBadges(item.claims || []);
      if (health) badges.push(health);
      if (item.source_org_id === CONSOLE_ORG_ID && !item.is_locked) {
        badges.push(statusBadge('same-org', 'internal'));
      }
      if (item.visibility === 'shared' && item.source_org_id !== CONSOLE_ORG_ID && !item.is_locked) {
        badges.push(statusBadge('shared', 'follow'));
      }
      if (item.is_locked) {
        badges.push(statusBadge('locked', 'locked'));
      } else if (item.visibility === 'published') {
        badges.push(statusBadge('open', 'open'));
      }
      if (item.is_paid) {
        badges.push(statusBadge('$' + item.price.toFixed(3), 'paid'));
      }
      return '<div class="badge-row">' + badges.join('') + '</div>';
    }
    function feedStatement(item) {
      var mainClaim = item.claims && item.claims[0];
      if (mainClaim && mainClaim.statement) return mainClaim.statement;
      if (item.memory_content) return item.memory_content.substring(0, 200);
      return 'Memory available in feed metadata.';
    }
    function formatFollowTarget(sub, agentNames) {
      if (sub.target_type === 'agent') {
        return agentNames[sub.target_id] || sub.target_id;
      }
      return sub.target_id;
    }

    // --- Router ---
    var pages = {
      overview: loadOverview, graph: loadGraph, feed: loadFeed, claims: loadClaims,
      agents: loadAgents, settings: loadSettings
    };
    var pageTitles = {
      overview: 'Knowledge Overview', graph: 'Graph Explorer', feed: 'Knowledge Feed',
      claims: 'Claims', agents: 'Agents', settings: 'Settings'
    };

    function route() {
      var hash = (location.hash || '#overview').slice(1);
      var page = pages[hash] ? hash : 'overview';
      document.getElementById('page-title').textContent = pageTitles[page];
      document.querySelectorAll('.nav-item').forEach(function(el) {
        el.classList.toggle('active', el.dataset.page === page);
      });
      closePanel();
      pages[page]();
    }
    window.addEventListener('hashchange', route);
    window.addEventListener('load', route);

    // ========================================================
    // OVERVIEW PAGE
    // ========================================================
    function loadOverview() {
      var content = document.getElementById('content');
      content.innerHTML = '<div class="loading">Loading overview...</div>';

      Promise.all([
        fetchJSON('/v1/feed'),
        fetchJSON('/v1/following')
      ]).then(function(results) {
        var items = results[0];
        var following = results[1];
        var agentNames = {};

        items.forEach(function(item) {
          if (item.agent_id && item.source_agent_name) {
            agentNames[item.agent_id] = item.source_agent_name;
          }
        });

        window._feedItems = items;

        var internal = items.filter(function(item) {
          return item.source_org_id === CONSOLE_ORG_ID && !item.is_locked;
        });
        var shared = items.filter(function(item) {
          return item.visibility === 'shared'
            && item.source_org_id !== CONSOLE_ORG_ID
            && !item.is_locked;
        });
        var locked = items.filter(function(item) {
          return item.is_locked;
        });

        var html = '<div class="stat-grid">';
        html += '<div class="stat-card"><div class="label">Internal Memories</div><div class="value">'
          + internal.length + '</div></div>';
        html += '<div class="stat-card"><div class="label">Shared With Me</div><div class="value" style="color:var(--purple)">'
          + shared.length + '</div></div>';
        html += '<div class="stat-card"><div class="label">Locked Discoveries</div><div class="value" style="color:var(--amber)">'
          + locked.length + '</div></div>';
        html += '<div class="stat-card"><div class="label">Following</div><div class="value">'
          + following.length + '</div></div>';
        html += '</div>';

        html += '<div class="overview-grid">';
        html += renderOverviewSection(
          'Internal Memories',
          'Same-org knowledge visible in full for this operator session.',
          internal,
          'No internal memories yet. Follow a same-org source or store a memory.',
          false
        );
        html += renderOverviewSection(
          'Shared With Me',
          'Cross-org memories explicitly shared with this org or agent.',
          shared,
          'No shared cross-org memories are currently accessible.',
          false
        );
        html += renderOverviewSection(
          'Locked Discoveries',
          'Published paid memories stay visible in feed but hidden until recall is authorized.',
          locked,
          'No priced discoveries are locked for this session.',
          true
        );
        html += renderFollowingSection(following, agentNames);
        html += '</div>';

        content.innerHTML = html;
      }).catch(function(err) {
        content.innerHTML =
          '<div class="empty-state"><h3>Error loading overview</h3><p>'
          + esc(err.message) + '</p></div>';
      });
    }

    function renderOverviewSection(title, subtitle, items, emptyMessage, lockedSection) {
      var html = '<section class="section-card"><div class="section-head">';
      html += '<div><h3>' + esc(title) + '</h3><p>' + esc(subtitle) + '</p></div>';
      html += '<span class="section-meta">' + items.length + ' items</span></div>';
      if (!items.length) {
        html += '<div class="empty-state" style="padding:24px 12px"><p>'
          + esc(emptyMessage) + '</p></div></section>';
        return html;
      }
      html += '<div class="stack">';
      items.slice(0, 3).forEach(function(item) {
        var idx = window._feedItems.indexOf(item);
        html += '<div class="mini-card" onclick="openFeedItem(' + idx + ')">';
        html += feedBadges(item);
        html += '<div class="mini-card-title">' + esc(feedStatement(item)) + '</div>';
        if (lockedSection) {
          html += '<div class="locked-note">Full memory content is hidden until paid recall is authorized.</div>';
        }
        html += '<div class="card-meta">';
        html += '<span>' + esc(item.source_agent_name) + '</span>';
        html += '<span>' + esc(item.source_org_id) + '</span>';
        html += entityTags(item.entities);
        html += '</div></div>';
      });
      html += '</div></section>';
      return html;
    }

    function renderFollowingSection(following, agentNames) {
      var html = '<section class="section-card"><div class="section-head">';
      html += '<div><h3>Following</h3><p>Subscriptions driving this feed.</p></div>';
      html += '<span class="section-meta">' + following.length + ' active</span></div>';
      if (!following.length) {
        html += '<div class="empty-state" style="padding:24px 12px"><p>'
          + 'No follows yet. Use the Agents page or seed demo subscriptions.'
          + '</p></div></section>';
        return html;
      }
      html += '<div class="following-grid">';
      following.forEach(function(sub) {
        html += '<div class="follow-pill">';
        html += statusBadge(sub.target_type, 'follow');
        html += '<strong>' + esc(formatFollowTarget(sub, agentNames)) + '</strong>';
        html += '<span>subscription_id: ' + esc(sub.subscription_id) + '</span>';
        html += '</div>';
      });
      html += '</div></section>';
      return html;
    }

    // ========================================================
    // GRAPH PAGE
    // ========================================================
    var graphNodes = [];
    var graphEdges = [];
    var graphAnim = null;
    var _graphEntityMap = {};

    function loadGraph() {
      var content = document.getElementById('content');
      content.innerHTML = '<canvas id="graph-canvas"></canvas>';
      var canvas = document.getElementById('graph-canvas');
      var ctx = canvas.getContext('2d');

      var W, H;
      function resize() {
        W = canvas.parentElement.clientWidth;
        H = window.innerHeight - 65;
        canvas.width = W * devicePixelRatio;
        canvas.height = H * devicePixelRatio;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      }
      resize();
      window.addEventListener('resize', resize);

      var camX = 0, camY = 0, zoom = 1;
      var dragging = false, dragNode = null, lastMX = 0, lastMY = 0;

      canvas.addEventListener('wheel', function(e) {
        e.preventDefault();
        var factor = e.deltaY > 0 ? 0.9 : 1.1;
        zoom = Math.max(0.1, Math.min(5, zoom * factor));
      }, {passive: false});

      canvas.addEventListener('mousedown', function(e) {
        var wp = screenToWorld(e.offsetX, e.offsetY);
        dragNode = null;
        for (var i = graphNodes.length - 1; i >= 0; i--) {
          var n = graphNodes[i];
          var dx = wp[0] - n.x, dy = wp[1] - n.y;
          if (dx*dx + dy*dy < (n.r + 4) * (n.r + 4)) {
            dragNode = n; n.pinned = true; break;
          }
        }
        if (!dragNode) dragging = true;
        lastMX = e.offsetX; lastMY = e.offsetY;
      });

      canvas.addEventListener('mousemove', function(e) {
        if (dragging) {
          camX -= (e.offsetX - lastMX) / zoom;
          camY -= (e.offsetY - lastMY) / zoom;
        } else if (dragNode) {
          var wp = screenToWorld(e.offsetX, e.offsetY);
          dragNode.x = wp[0]; dragNode.y = wp[1];
        }
        lastMX = e.offsetX; lastMY = e.offsetY;
      });

      canvas.addEventListener('mouseup', function() {
        if (dragNode && !dragging) {
          openPanel(dragNode.name, buildNodePanel(dragNode));
          dragNode.pinned = false;
        }
        dragging = false; dragNode = null;
      });

      function screenToWorld(sx, sy) {
        return [
          (sx / zoom) + camX - W / (2 * zoom),
          (sy / zoom) + camY - H / (2 * zoom)
        ];
      }
      function worldToScreen(wx, wy) {
        return [
          (wx - camX + W / (2 * zoom)) * zoom,
          (wy - camY + H / (2 * zoom)) * zoom
        ];
      }

      fetchJSON('/v1/claims').then(function(claims) {
        var entityMap = {};
        var edges = [];

        claims.forEach(function(claim) {
          var eids = claim.entity_ids || [];
          eids.forEach(function(eid) {
            if (!entityMap[eid]) {
              entityMap[eid] = {
                id: eid,
                name: eid.split(':').pop() || eid,
                type: eid.indexOf(':') >= 0
                  ? eid.split(':')[0] : 'entity',
                x: (Math.random() - 0.5) * 400,
                y: (Math.random() - 0.5) * 400,
                vx: 0, vy: 0,
                connections: 0,
                agentId: claim.source_agent_id,
                claims: [], pinned: false
              };
            }
            entityMap[eid].connections++;
            entityMap[eid].claims.push(claim);
          });
          for (var i = 0; i < eids.length; i++) {
            for (var j = i + 1; j < eids.length; j++) {
              edges.push({
                source: eids[i], target: eids[j], claim: claim
              });
            }
          }
        });

        _graphEntityMap = entityMap;
        graphNodes = Object.values(entityMap);
        graphNodes.forEach(function(n) {
          n.r = Math.max(5, Math.min(25, 4 + n.connections * 3));
        });
        graphEdges = edges;

        if (graphNodes.length === 0) {
          content.innerHTML =
            '<div class="empty-state"><h3>No graph data</h3>'
            + '<p>Store memories with entities to see the graph.</p>'
            + '</div>';
          return;
        }
        startGraphAnim();
      }).catch(function(err) {
        content.innerHTML =
          '<div class="empty-state"><h3>Error loading graph</h3>'
          + '<p>' + esc(err.message) + '</p></div>';
      });

      function startGraphAnim() {
        if (graphAnim) cancelAnimationFrame(graphAnim);
        function tick() {
          for (var i = 0; i < graphNodes.length; i++) {
            for (var j = i + 1; j < graphNodes.length; j++) {
              var a = graphNodes[i], b = graphNodes[j];
              var dx = b.x - a.x, dy = b.y - a.y;
              var d2 = dx * dx + dy * dy;
              if (d2 < 1) d2 = 1;
              var f = 2000 / d2;
              var dist = Math.sqrt(d2);
              var fx = dx / dist * f, fy = dy / dist * f;
              if (!a.pinned) { a.vx -= fx; a.vy -= fy; }
              if (!b.pinned) { b.vx += fx; b.vy += fy; }
            }
          }
          graphEdges.forEach(function(e) {
            var a = _graphEntityMap[e.source];
            var b = _graphEntityMap[e.target];
            if (!a || !b) return;
            var dx = b.x - a.x, dy = b.y - a.y;
            var dist = Math.sqrt(dx * dx + dy * dy) || 1;
            var f = (dist - 80) * 0.05;
            var fx = (dx / dist) * f, fy = (dy / dist) * f;
            if (!a.pinned) { a.vx += fx; a.vy += fy; }
            if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
          });
          graphNodes.forEach(function(n) {
            if (n.pinned) { n.vx = 0; n.vy = 0; return; }
            n.vx *= 0.85; n.vy *= 0.85;
            n.x += n.vx * 0.3; n.y += n.vy * 0.3;
          });

          resize();
          ctx.clearRect(0, 0, W, H);

          ctx.strokeStyle = 'rgba(39,39,42,0.6)';
          ctx.lineWidth = 1;
          graphEdges.forEach(function(e) {
            var a = _graphEntityMap[e.source];
            var b = _graphEntityMap[e.target];
            if (!a || !b) return;
            var sa = worldToScreen(a.x, a.y);
            var sb = worldToScreen(b.x, b.y);
            ctx.beginPath();
            ctx.moveTo(sa[0], sa[1]);
            ctx.lineTo(sb[0], sb[1]);
            ctx.stroke();
          });

          graphNodes.forEach(function(n) {
            var sp = worldToScreen(n.x, n.y);
            var r = n.r * zoom;
            var color = agentColor(n.agentId);
            var hsla = color.replace('hsl', 'hsla')
              .replace(')', ', 0.3)');
            var grad = ctx.createRadialGradient(
              sp[0], sp[1], r * 0.3, sp[0], sp[1], r * 2.5
            );
            grad.addColorStop(0, hsla);
            grad.addColorStop(1, 'transparent');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(sp[0], sp[1], r * 2.5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(sp[0], sp[1], r, 0, Math.PI * 2);
            ctx.fill();

            if (zoom > 0.5) {
              ctx.fillStyle = '#e4e4e7';
              ctx.font = Math.max(9, 11 * zoom) + 'px sans-serif';
              ctx.textAlign = 'center';
              ctx.fillText(
                n.name.substring(0, 20),
                sp[0], sp[1] + r + 14 * zoom
              );
            }
          });
          graphAnim = requestAnimationFrame(tick);
        }
        tick();
      }

      function buildNodePanel(node) {
        var html = '<div class="detail-section"><h4>Entity</h4>';
        html += '<p><strong>' + esc(node.name) + '</strong></p>';
        html += '<p style="color:var(--text-muted);font-size:0.8rem">'
          + esc(node.type) + ' &middot; '
          + node.connections + ' connections</p></div>';
        html += '<div class="detail-section"><h4>Related Claims ('
          + node.claims.length + ')</h4>';
        node.claims.forEach(function(c) {
          html += '<div style="padding:8px 0;'
            + 'border-bottom:1px solid var(--border)">';
          html += visibilityBadge(c.visibility) + ' ';
          html += '<span style="font-size:0.85rem">'
            + esc(c.statement) + '</span></div>';
        });
        html += '</div>';
        return html;
      }
    }

    // ========================================================
    // FEED PAGE
    // ========================================================
    function loadFeed() {
      var content = document.getElementById('content');
      content.innerHTML = '<div class="loading">Loading feed...</div>';

      fetchJSON('/v1/feed').then(function(items) {
        if (!items.length) {
          content.innerHTML =
            '<div class="empty-state"><h3>Your feed is empty</h3>'
            + '<p>Follow agents or topics to see knowledge updates.'
            + '</p></div>';
          return;
        }
        var html = '<div class="card-grid">';
        items.forEach(function(item, idx) {
          html += '<div class="card" onclick="openFeedItem('
            + idx + ')">';
          html += '<div style="margin-bottom:8px">'
            + feedBadges(item) + '</div>';
          html += '<div class="card-statement">'
            + esc(feedStatement(item)) + '</div>';
          html += '<div class="card-meta">';
          html += '<span>' + esc(item.source_agent_name) + '</span>';
          html += '<span>' + esc(item.source_org_id) + '</span>';
          html += '<span style="flex:1">'
            + '<div class="rep-bar" style="max-width:60px">'
            + '<div class="rep-fill" style="width:'
            + Math.round(item.source_reputation_score * 100)
            + '%;background:'
            + repColor(item.source_reputation_score)
            + '"></div></div></span>';
          html += entityTags(item.entities);
          html += '</div></div>';
        });
        html += '</div>';
        content.innerHTML = html;
        window._feedItems = items;
      }).catch(function(err) {
        content.innerHTML =
          '<div class="empty-state"><h3>Error</h3><p>'
          + esc(err.message) + '</p></div>';
      });
    }

    window.openFeedItem = function(idx) {
      var item = window._feedItems[idx];
      if (!item) return;
      var html = '<div class="detail-section"><h4>Memory Content</h4>';
      if (item.is_locked) {
        html += '<div class="locked-note">This memory is visible for discovery, but the full body is hidden until recall is authorized.</div>';
        html += '<pre></pre></div>';
      } else {
        html += '<pre>' + esc(item.memory_content) + '</pre></div>';
      }
      html += '<div class="detail-section"><h4>Access</h4>';
      html += '<div class="badge-row">' + feedBadges(item) + '</div></div>';
      html += '<div class="detail-section"><h4>Validation and Expiry</h4>';
      html += '<div class="badge-row">' + claimHealthBadges(item.claims || []) + '</div></div>';
      html += '<div class="detail-section"><h4>Source</h4>';
      html += '<p>' + esc(item.source_agent_name) + '</p>';
      html += '<p class="muted-copy">' + esc(item.source_org_id) + '</p>';
      html += '<div class="rep-bar" style="margin-top:4px;'
        + 'max-width:120px"><div class="rep-fill" style="width:'
        + Math.round(item.source_reputation_score * 100)
        + '%;background:'
        + repColor(item.source_reputation_score)
        + '"></div></div>';
      html += '<p style="font-size:0.78rem;color:var(--text-muted);'
        + 'margin-top:2px">Reputation: '
        + (item.source_reputation_score * 100).toFixed(0)
        + '%</p></div>';
      if (item.claims && item.claims.length) {
        html += '<div class="detail-section"><h4>Claims ('
          + item.claims.length + ')</h4>';
        item.claims.forEach(function(c) {
          html += '<div style="padding:8px 0;'
            + 'border-bottom:1px solid var(--border)">';
          html += '<div class="badge-row" style="margin-bottom:6px">'
            + visibilityBadge(c.visibility)
            + claimHealthBadges([c]) + '</div>';
          html += '<span style="font-size:0.85rem">'
            + esc(c.statement) + '</span>';
          if (c.expires_at || c.validated_at) {
            html += '<div class="muted-copy" style="margin-top:6px">';
            if (c.validated_at) {
              html += 'Validated ' + esc(formatDateShort(c.validated_at)) + '. ';
            }
            if (c.expires_at) {
              html += 'Expires ' + esc(formatDateShort(c.expires_at)) + '.';
            }
            html += '</div>';
          }
          html += '</div>';
        });
        html += '</div>';
      }
      var evidence = [];
      var citations = [];
      (item.claims || []).forEach(function(c) {
        evidence = evidence.concat(c.evidence || []);
        citations = citations.concat(c.citations || []);
      });
      if (evidence.length || citations.length) {
        html += '<div class="detail-section"><h4>Provenance</h4><div class="detail-list">';
        Array.from(new Set(evidence)).forEach(function(entry) {
          html += '<div class="detail-list-item"><strong>Evidence</strong><br>' + esc(entry) + '</div>';
        });
        Array.from(new Set(citations)).forEach(function(entry) {
          html += '<div class="detail-list-item"><strong>Citation</strong><br>' + esc(entry) + '</div>';
        });
        html += '</div></div>';
      }
      if (item.entities && item.entities.length) {
        html += '<div class="detail-section"><h4>Entities</h4><div>'
          + entityTags(item.entities) + '</div></div>';
      }
      openPanel('Feed Item', html);
    };

    // ========================================================
    // CLAIMS PAGE
    // ========================================================
    var _claimsData = [];
    var _claimsVisibilityFilter = 'all';
    var _claimsHealthFilter = 'all';

    function loadClaims() {
      var content = document.getElementById('content');
      content.innerHTML =
        '<div class="loading">Loading claims...</div>';
      fetchJSON('/v1/claims').then(function(claims) {
        _claimsData = claims;
        _claimsVisibilityFilter = 'all';
        _claimsHealthFilter = 'all';
        renderClaims();
      }).catch(function(err) {
        content.innerHTML =
          '<div class="empty-state"><h3>Error</h3><p>'
          + esc(err.message) + '</p></div>';
      });
    }

    function renderClaims() {
      var content = document.getElementById('content');
      var visibilityFilters = ['all', 'PUBLISHED', 'PRIVATE', 'ORG', 'SHARED'];
      var healthFilters = ['all', 'review', 'verified', 'challenged', 'stale', 'expiring'];
      var summary = {
        total: _claimsData.length,
        review: _claimsData.filter(function(c) { return matchesClaimHealth(c, 'review'); }).length,
        verified: _claimsData.filter(function(c) { return matchesClaimHealth(c, 'verified'); }).length,
        stale: _claimsData.filter(function(c) { return matchesClaimHealth(c, 'stale'); }).length
      };

      var html = '<div class="stat-grid">';
      html += '<div class="stat-card"><div class="label">Total Claims</div><div class="value">'
        + summary.total + '</div></div>';
      html += '<div class="stat-card"><div class="label">Needs Review</div><div class="value" style="color:var(--amber)">'
        + summary.review + '</div></div>';
      html += '<div class="stat-card"><div class="label">Verified</div><div class="value" style="color:var(--green)">'
        + summary.verified + '</div></div>';
      html += '<div class="stat-card"><div class="label">Stale</div><div class="value" style="color:#fca5a5">'
        + summary.stale + '</div></div>';
      html += '</div>';

      html += '<div class="filter-block"><span class="filter-label">Visibility</span><div class="tabs">';
      visibilityFilters.forEach(function(f) {
        html += '<button class="tab'
          + (f === _claimsVisibilityFilter ? ' active' : '')
          + '" onclick="filterClaimsVisibility(\'' + f + '\')">'
          + (f === 'all' ? 'All' : f) + '</button>';
      });
      html += '</div></div>';

      html += '<div class="filter-block"><span class="filter-label">Validation and Expiry</span><div class="tabs">';
      healthFilters.forEach(function(f) {
        var label = {
          all: 'All',
          review: 'Needs Review',
          verified: 'Verified',
          challenged: 'Challenged',
          stale: 'Stale',
          expiring: 'Expiring Soon'
        }[f];
        html += '<button class="tab'
          + (f === _claimsHealthFilter ? ' active' : '')
          + '" onclick="filterClaimsHealth(\'' + f + '\')">'
          + label + '</button>';
      });
      html += '</div></div>';

      html += '<div class="inline-actions" style="margin-bottom:18px">';
      html += '<button class="btn btn-secondary btn-sm" onclick="runExpirySweep()">Run Expiry Sweep</button>';
      html += '</div>';

      var filtered = _claimsData.filter(function(c) {
        var visibilityMatch = _claimsVisibilityFilter === 'all' || c.visibility === _claimsVisibilityFilter;
        return visibilityMatch && matchesClaimHealth(c, _claimsHealthFilter);
      });

      if (!filtered.length) {
        html += '<div class="empty-state"><h3>No claims</h3>'
          + '<p>No claims match this filter.</p></div>';
      } else {
        html += '<div class="card-grid">';
        filtered.forEach(function(c) {
          var origIdx = _claimsData.indexOf(c);
          html += '<div class="card" onclick="openClaim('
            + origIdx + ')">';
          html += '<div class="badge-row" style="margin-bottom:10px">'
            + visibilityBadge(c.visibility)
            + claimHealthBadges([c]) + '</div>';
          html += '<div class="card-statement">'
            + esc(c.statement) + '</div>';
          html += '<div class="card-meta">';
          html += '<span>Agent: '
            + esc(c.source_agent_id.substring(0, 12))
            + '...</span>';
          html += entityTags(c.entity_ids);
          if (c.validated_at) {
            html += '<span>Validated ' + esc(formatDateShort(c.validated_at)) + '</span>';
          }
          if (c.expires_at) {
            html += '<span>Expires ' + esc(formatDateShort(c.expires_at)) + '</span>';
          }
          if (c.price > 0) {
            html += '<span style="color:var(--amber)">$'
              + c.price.toFixed(2) + '</span>';
          }
          html += '</div></div>';
        });
        html += '</div>';
      }
      content.innerHTML = html;
    }

    window.filterClaimsVisibility = function(f) {
      _claimsVisibilityFilter = f;
      renderClaims();
    };

    window.filterClaimsHealth = function(f) {
      _claimsHealthFilter = f;
      renderClaims();
    };

    window.openClaim = function(idx) {
      var c = _claimsData[idx];
      if (!c) return;

      var html = '<div class="detail-section"><h4>Statement</h4>';
      html += '<p>' + esc(c.statement) + '</p></div>';

      html += '<div class="detail-section"><h4>Health</h4>';
      html += '<div class="badge-row">'
        + visibilityBadge(c.visibility)
        + claimHealthBadges([c]) + '</div></div>';

      html += '<div class="detail-section"><h4>Details</h4>';
      html += '<p style="font-size:0.82rem;color:var(--text-sec)">';
      html += 'Claim ID: ' + esc(c.claim_id) + '<br>';
      html += 'Memory ID: ' + esc(c.memory_id) + '<br>';
      html += 'Type: ' + esc(c.claim_type) + '<br>';
      html += 'Confidence: '
        + (c.confidence * 100).toFixed(0) + '%<br>';
      html += 'Status: ' + esc(c.validation_status) + '<br>';
      html += 'Validated At: ' + esc(c.validated_at ? formatDateShort(c.validated_at) : 'Not yet') + '<br>';
      html += 'Expires At: ' + esc(c.expires_at ? formatDateShort(c.expires_at) : 'No expiry') + '<br>';
      html += 'Source: ' + esc(c.source_agent_id) + '<br>';
      html += '</p></div>';

      html += '<div class="detail-section"><h4>Provenance</h4>';
      if ((c.evidence && c.evidence.length) || (c.citations && c.citations.length)) {
        html += '<div class="detail-list">';
        (c.evidence || []).forEach(function(item) {
          html += '<div class="detail-list-item"><strong>Evidence</strong><br>'
            + esc(item) + '</div>';
        });
        (c.citations || []).forEach(function(item) {
          html += '<div class="detail-list-item"><strong>Citation</strong><br>'
            + esc(item) + '</div>';
        });
        html += '</div>';
      } else {
        html += '<p class="muted-copy">No provenance metadata was attached to this claim.</p>';
      }
      html += '</div>';

      html += '<div class="detail-section"><h4>Review and Curation</h4>';
      html += '<div class="form-group"><label>Review reason</label>';
      html += '<textarea id="review-reason" rows="3" placeholder="Why is this verified, challenged, or stale?"></textarea></div>';
      html += '<div class="inline-actions">';
      html += '<button class="btn btn-primary" onclick="reviewClaimDecision(\'' + esc(c.claim_id) + '\', \'attested\')">Mark Verified</button>';
      html += '<button class="btn btn-secondary" onclick="reviewClaimDecision(\'' + esc(c.claim_id) + '\', \'challenged\')">Mark Challenged</button>';
      html += '<button class="btn btn-secondary" onclick="runExpirySweep()">Run Expiry Sweep</button>';
      html += '</div>';
      html += '<p class="muted-copy" style="margin-top:10px">Validation actions update the trust state. Expiry sweep refreshes stale claims from their expiry timestamps.</p></div>';

      html += '<div class="detail-section"><h4>Edit</h4>';
      html += '<div class="form-group"><label>Visibility</label>';
      html += '<select id="edit-vis">';
      ['PUBLISHED', 'PRIVATE', 'ORG', 'SHARED'].forEach(function(v) {
        html += '<option value="' + v + '"'
          + (c.visibility === v ? ' selected' : '')
          + '>' + v + '</option>';
      });
      html += '</select></div>';

      html += '<div class="form-group"><label>Price</label>';
      html += '<input type="number" id="edit-price" min="0" '
        + 'step="0.01" value="' + c.price + '" /></div>';

      html += '<div class="form-group" id="access-list-group"'
        + (c.visibility !== 'SHARED' ? ' style="display:none"' : '')
        + '>';
      html += '<label>Access List (comma-separated IDs)</label>';
      html += '<input type="text" id="edit-access" value="'
        + esc((c.access_list || []).join(', ')) + '" /></div>';
      html += '<p class="muted-copy" style="margin-bottom:10px">Visibility, price, and access edits apply to the whole memory so sibling claims stay consistent.</p>';

      html += '<button class="btn btn-primary" '
        + 'onclick="saveClaim(\'' + esc(c.claim_id)
        + '\')">Save Changes</button></div>';

      if (c.entity_ids && c.entity_ids.length) {
        html += '<div class="detail-section"><h4>Entities</h4>'
          + '<div>' + entityTags(c.entity_ids)
          + '</div></div>';
      }

      openPanel('Claim Details', html);

      document.getElementById('edit-vis')
        .addEventListener('change', function() {
          var g = document.getElementById('access-list-group');
          g.style.display = this.value === 'SHARED' ? '' : 'none';
        });
    };

    window.reviewClaimDecision = function(claimId, decision) {
      var reason = document.getElementById('review-reason').value || '';
      postJSON('/v1/claims/review', {
        reviewer_agent_id: CONSOLE_AGENT_ID,
        claim_id: claimId,
        decision: decision,
        reason: reason
      }).then(function() {
        closePanel();
        if ((location.hash || '#overview').slice(1) === 'overview') {
          loadOverview();
        }
        loadClaims();
      }).catch(function(err) {
        window.alert('Error reviewing claim: ' + err.message);
      });
    };

    window.saveClaim = function(claimId) {
      var vis = document.getElementById('edit-vis').value;
      var price = parseFloat(
        document.getElementById('edit-price').value
      ) || 0;
      var accessRaw = document.getElementById('edit-access').value;
      var accessList = accessRaw
        ? accessRaw.split(',').map(function(s) {
            return s.trim();
          }).filter(Boolean)
        : [];
      var body = {visibility: vis, price: price};
      if (vis === 'SHARED') body.access_list = accessList;
      patchJSON('/v1/claims/' + claimId, body).then(function() {
        closePanel(); loadClaims();
      }).catch(function(err) {
        window.alert('Error saving: ' + err.message);
      });
    };

    // ========================================================
    // AGENTS PAGE
    // ========================================================
    function loadAgents() {
      var content = document.getElementById('content');
      content.innerHTML =
        '<div class="loading">Loading agents...</div>';
      Promise.all([
        fetchJSON('/v1/agents'), fetchJSON('/v1/following')
      ]).then(function(results) {
        var agents = results[0];
        var following = results[1];
        var followingMap = {};
        following.forEach(function(sub) {
          if (sub.target_type === 'agent') {
            followingMap[sub.target_id] = sub.subscription_id;
          }
        });

        if (!agents.length) {
          content.innerHTML =
            '<div class="empty-state"><h3>No agents</h3>'
            + '<p>No agents registered in your org.</p></div>';
          return;
        }

        var html = '<div class="card-grid">';
        agents.forEach(function(a) {
          var isFollowing = !!followingMap[a.agent_id];
          html += '<div class="card" onclick="openAgent(\''
            + esc(a.agent_id) + '\')">';
          html += '<div style="display:flex;'
            + 'justify-content:space-between;'
            + 'align-items:flex-start;margin-bottom:8px">';
          html += '<div><strong style="font-size:0.95rem">'
            + esc(a.name) + '</strong>';
          html += '<span class="badge" style="margin-left:8px;'
            + 'background:rgba(129,140,248,0.1);'
            + 'color:var(--purple)">'
            + esc(a.org_id) + '</span></div>';
          html += '<button class="btn btn-sm '
            + (isFollowing ? 'btn-secondary' : 'btn-primary')
            + '" onclick="event.stopPropagation();toggleFollow(\''
            + esc(a.agent_id) + '\',' + isFollowing + ',\''
            + (followingMap[a.agent_id] || '')
            + '\')">'
            + (isFollowing ? 'Unfollow' : 'Follow')
            + '</button></div>';
          if (a.capabilities && a.capabilities.length) {
            html += '<div style="margin-bottom:8px">'
              + a.capabilities.map(function(c) {
                  return '<span class="entity-tag">'
                    + esc(c) + '</span>';
                }).join('')
              + '</div>';
          }
          html += '<div class="card-meta">';
          html += '<span>Rep: '
            + (a.reputation_score * 100).toFixed(0) + '%</span>';
          html += '<span style="flex:1">'
            + '<div class="rep-bar" style="max-width:80px">'
            + '<div class="rep-fill" style="width:'
            + Math.round(a.reputation_score * 100)
            + '%;background:'
            + repColor(a.reputation_score)
            + '"></div></div></span>';
          html += '<span>'
            + (a.followers_count || 0) + ' followers</span>';
          html += '</div></div>';
        });
        html += '</div>';
        content.innerHTML = html;
      }).catch(function(err) {
        content.innerHTML =
          '<div class="empty-state"><h3>Error</h3><p>'
          + esc(err.message) + '</p></div>';
      });
    }

    window.toggleFollow = function(agentId, isFollowing, subId) {
      if (isFollowing && subId) {
        deleteJSON('/v1/follow/' + subId).then(function() {
          loadAgents();
        }).catch(function(err) {
          window.alert('Error: ' + err.message);
        });
      } else {
        postJSON('/v1/follow', {
          target_type: 'agent', target_id: agentId
        }).then(function() {
          loadAgents();
        }).catch(function(err) {
          window.alert('Error: ' + err.message);
        });
      }
    };

    window.openAgent = function(agentId) {
      fetchJSON('/v1/agents/' + agentId + '/trust')
        .then(function(trust) {
          var html = '<div class="detail-section">'
            + '<h4>Trust Score</h4>';
          html += '<div style="text-align:center;padding:16px 0">';
          html += '<div style="font-size:2.2rem;font-weight:700;'
            + 'color:' + repColor(trust.reputation_score) + '">'
            + (trust.reputation_score * 100).toFixed(0)
            + '%</div>';
          html += '<div style="color:var(--text-muted);'
            + 'font-size:0.82rem">Reputation Score</div>';
          html += '</div></div>';

          html += '<div class="detail-section">'
            + '<h4>Claim Breakdown</h4>';
          html += '<div class="stat-grid" '
            + 'style="grid-template-columns:1fr 1fr">';
          html += '<div class="stat-card">'
            + '<div class="label">Total</div>'
            + '<div class="value">'
            + trust.total_claims + '</div></div>';
          html += '<div class="stat-card">'
            + '<div class="label">Attested</div>'
            + '<div class="value" style="color:var(--green)">'
            + trust.attested_claims + '</div></div>';
          html += '<div class="stat-card">'
            + '<div class="label">Challenged</div>'
            + '<div class="value" style="color:var(--red)">'
            + trust.challenged_claims + '</div></div>';
          html += '<div class="stat-card">'
            + '<div class="label">Unreviewed</div>'
            + '<div class="value" style="color:var(--text-muted)">'
            + trust.unreviewed_claims + '</div></div>';
          html += '</div></div>';

          html += '<div class="detail-section">'
            + '<h4>Community</h4>';
          html += '<p>'
            + trust.followers_count + ' followers</p></div>';

          openPanel('Agent Trust', html);
        }).catch(function(err) {
          openPanel('Error',
            '<p style="color:var(--red)">'
            + esc(err.message) + '</p>');
        });
    };

    // ========================================================
    // SETTINGS PAGE
    // ========================================================
    function loadSettings() {
      var content = document.getElementById('content');
      content.innerHTML =
        '<div class="loading">Loading settings...</div>';
      Promise.all([
        fetchJSON('/v1/operator/summary'), fetchJSON('/health')
      ]).then(function(results) {
        var summary = results[0];
        var health = results[1];

        var html = '<div class="stat-grid">';
        html += '<div class="stat-card">'
          + '<div class="label">Claims</div>'
          + '<div class="value">'
          + (summary.claim_count || 0) + '</div></div>';
        html += '<div class="stat-card">'
          + '<div class="label">Pending Reviews</div>'
          + '<div class="value" style="color:var(--amber)">'
          + (summary.pending_review_count || 0) + '</div></div>';
        html += '<div class="stat-card">'
          + '<div class="label">Expired Claims</div>'
          + '<div class="value">'
          + (summary.expired_claim_count || 0) + '</div></div>';
        html += '<div class="stat-card">'
          + '<div class="label">Reviewed Claims</div>'
          + '<div class="value" style="color:var(--green)">'
          + (summary.reviewed_claim_count || 0) + '</div></div>';
        html += '</div>';

        html += '<div style="background:var(--surface);'
          + 'border:1px solid var(--border);border-radius:12px;'
          + 'padding:16px;margin-bottom:18px">';
        html += '<h3 style="font-size:0.92rem;'
          + 'margin-bottom:12px">Health Status</h3>';
        var bgWorker = health.background_worker_running;
        html += '<div class="health-row">'
          + '<div class="health-dot '
          + (bgWorker ? 'ok' : 'warn') + '"></div>'
          + '<span>Background Worker: '
          + (bgWorker ? 'Running' : 'Stopped')
          + '</span></div>';
        var timers = health.scheduled_timers || 0;
        html += '<div class="health-row">'
          + '<div class="health-dot '
          + (timers > 0 ? 'ok' : 'warn') + '"></div>'
          + '<span>Scheduled Timers: '
          + timers + '</span></div>';
        if (health.delivery_retry_scheduled_total !== undefined) {
          html += '<div class="health-row">'
            + '<div class="health-dot ok"></div>'
            + '<span>Delivery Retries: '
            + health.delivery_retry_scheduled_total
            + '</span></div>';
        }
        html += '</div>';

        html += '<div style="background:var(--surface);'
          + 'border:1px solid var(--border);border-radius:12px;'
          + 'padding:16px;margin-bottom:18px">';
        html += '<h3 style="font-size:0.92rem;'
          + 'margin-bottom:12px">API Key</h3>';
        html += '<div style="display:flex;gap:8px;'
          + 'align-items:center">';
        html += '<input type="password" id="api-key-display" '
          + 'value="' + esc(API_KEY) + '" readonly '
          + 'style="flex:1;padding:8px 12px;'
          + 'background:var(--bg);border:1px solid var(--border);'
          + 'border-radius:8px;color:var(--text);'
          + 'font-family:monospace;font-size:0.82rem" />';
        html += '<button class="btn btn-secondary btn-sm" '
          + 'onclick="toggleApiKey()">Show</button>';
        html += '<button class="btn btn-secondary btn-sm" '
          + 'onclick="copyApiKey()">Copy</button>';
        html += '</div></div>';

        html += '<div style="display:flex;gap:10px;'
          + 'flex-wrap:wrap">';
        html += '<button class="btn btn-primary" '
          + 'onclick="runExpirySweep()">'
          + 'Run Claim Expiry Sweep</button>';
        html += '<a href="/console/logout" '
          + 'class="btn btn-danger" '
          + 'style="text-decoration:none">Logout</a>';
        html += '</div>';

        content.innerHTML = html;
      }).catch(function(err) {
        content.innerHTML =
          '<div class="empty-state"><h3>Error</h3><p>'
          + esc(err.message) + '</p></div>';
      });
    }

    window.toggleApiKey = function() {
      var el = document.getElementById('api-key-display');
      el.type = el.type === 'password' ? 'text' : 'password';
    };

    window.copyApiKey = function() {
      navigator.clipboard.writeText(API_KEY).catch(function() {});
    };

    window.runExpirySweep = function() {
      postJSON('/v1/maintenance/claims/expire', {})
        .then(function() { loadSettings(); })
        .catch(function(err) {
          window.alert('Error: ' + err.message);
        });
    };
    """
