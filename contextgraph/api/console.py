from __future__ import annotations

from html import escape
from typing import Any

from ..errors import AuthenticationError
from ..models import BackgroundJob, Notification, ReviewQueueItem
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

        summary = graph.operator_snapshot(agent.agent_id)
        review_queue = graph.list_review_queue(agent.agent_id)
        jobs = graph.list_jobs(agent.agent_id)[:20]
        audits = graph.list_audit_entries(agent.agent_id)[:25]
        notifications = graph.get_notifications(agent.agent_id)[:10]
        return HTMLResponse(
            _render_console(
                agent_name=agent.name,
                summary=summary,
                review_queue=review_queue,
                jobs=jobs,
                audits=audits,
                notifications=notifications,
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
  <title>ContextGraph Console</title>
  <style>{_console_css()}</style>
</head>
<body>
  <main class="shell narrow">
    <section class="panel">
      <h1>ContextGraph Console</h1>
      <p>Paste an agent API key to open the operator control plane.</p>
      {error_html}
      <form action="/console/login" method="post" class="stack">
        <label for="api_key">API key</label>
        <input id="api_key" name="api_key" type="password" required />
        <button type="submit">Open Console</button>
      </form>
    </section>
  </main>
</body>
</html>"""


def _render_console(
    *,
    agent_name: str,
    summary: dict[str, object],
    review_queue: list[ReviewQueueItem],
    jobs: list[BackgroundJob],
    audits: list[Any],
    notifications: list[Notification],
) -> str:
    cards = [
        ("Org", str(summary["org_id"])),
        ("Pending Reviews", str(summary["pending_review_count"])),
        ("Claims", str(summary["claim_count"])),
        ("Expired Claims", str(summary["expired_claim_count"])),
        ("Reviewed Claims", str(summary["reviewed_claim_count"])),
        ("Open Jobs", str(sum(summary["job_status_counts"].get(key, 0) for key in ("queued", "running", "retrying")))),
        ("Dead Letters", str(summary["job_status_counts"].get("dead_lettered", 0))),
        ("Retry Events", str(summary["health"].get("delivery_retry_scheduled_total", 0))),
    ]
    review_html = "".join(_render_review_item(item) for item in review_queue) or "<p>No open review tasks.</p>"
    job_rows = "".join(_render_job_row(job) for job in jobs) or "<tr><td colspan='6'>No jobs yet.</td></tr>"
    audit_rows = (
        "".join(_render_audit_row(entry) for entry in audits) or "<tr><td colspan='4'>No audit entries yet.</td></tr>"
    )
    notification_rows = (
        "".join(_render_notification_row(item) for item in notifications)
        or "<tr><td colspan='4'>No notifications yet.</td></tr>"
    )
    cards_html = "".join(
        f"<article class='metric'><h2>{escape(label)}</h2><p>{escape(value)}</p></article>" for label, value in cards
    )
    health = summary["health"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ContextGraph Console</title>
  <style>{_console_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>ContextGraph Console</h1>
        <p>Operator view for <strong>{escape(agent_name)}</strong></p>
      </div>
      <div class="actions">
        <form action="/console/maintenance/claim-expiry-sweep" method="post">
          <button type="submit">Run Claim Expiry Sweep</button>
        </form>
        <a href="/console/logout" class="btn secondary">Logout</a>
      </div>
    </header>

    <section class="grid metrics">{cards_html}</section>

    <section class="panel" id="reviews">
      <h2>Review Queue</h2>
      {review_html}
    </section>

    <section class="panel" id="jobs">
      <h2>Recent Jobs</h2>
      <p class="muted">Background worker: {escape(str(health.get("background_worker_running")))}. Scheduled timers: {escape(str(health.get("scheduled_timers")))}.</p>
      <table>
        <thead><tr><th>Type</th><th>Status</th><th>Attempts</th><th>Next Run</th><th>Result</th><th>Error</th></tr></thead>
        <tbody>{job_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Notifications</h2>
      <table>
        <thead><tr><th>Event</th><th>Claim</th><th>Created</th><th>Delivered</th></tr></thead>
        <tbody>{notification_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Audit Feed</h2>
      <table>
        <thead><tr><th>Time</th><th>Action</th><th>Actor</th><th>Details</th></tr></thead>
        <tbody>{audit_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def _render_review_item(item: ReviewQueueItem) -> str:
    return f"""
    <article class="review-card">
      <div class="review-meta">
        <span class="badge">{escape(item.review.reason)}</span>
        <span>{escape(item.source_agent.name)}</span>
        <span>{escape(item.claim.validation_status.value)}</span>
        <span>{escape(item.review.created_at.isoformat(timespec="seconds"))}</span>
      </div>
      <p class="statement">{escape(item.claim.statement)}</p>
      <p class="muted">Claim {escape(item.claim.claim_id)} from memory {escape(item.claim.memory_id)}</p>
      <form action="/console/review" method="post" class="stack">
        <input type="hidden" name="claim_id" value="{escape(item.claim.claim_id)}" />
        <label>
          Review note
          <textarea name="reason" rows="2" placeholder="Why are you attesting or challenging this claim?"></textarea>
        </label>
        <div class="actions">
          <button type="submit" name="decision" value="attested">Attest</button>
          <button type="submit" name="decision" value="challenged" class="secondary">Challenge</button>
        </div>
      </form>
    </article>
    """


def _render_job_row(job: BackgroundJob) -> str:
    next_run = job.next_run_at.isoformat(timespec="seconds") if job.next_run_at else "-"
    result = ", ".join(f"{escape(str(key))}={escape(str(value))}" for key, value in job.result_summary.items()) or "-"
    error = escape(job.error or "-")
    return (
        "<tr>"
        f"<td>{escape(job.job_type.value)}</td>"
        f"<td><span class='badge badge-{escape(job.status.value)}'>{escape(job.status.value)}</span></td>"
        f"<td>{job.attempt_count}/{job.max_attempts}</td>"
        f"<td>{escape(next_run)}</td>"
        f"<td>{result}</td>"
        f"<td>{error}</td>"
        "</tr>"
    )


def _render_audit_row(entry: Any) -> str:
    detail = ", ".join(f"{escape(str(key))}={escape(str(value))}" for key, value in entry.details.items()) or "-"
    return (
        "<tr>"
        f"<td>{escape(entry.timestamp.isoformat(timespec='seconds'))}</td>"
        f"<td>{escape(entry.action)}</td>"
        f"<td>{escape(entry.actor_agent_id)}</td>"
        f"<td>{detail}</td>"
        "</tr>"
    )


def _render_notification_row(notification: Notification) -> str:
    return (
        "<tr>"
        f"<td>{escape(notification.event_type)}</td>"
        f"<td>{escape(notification.claim_id)}</td>"
        f"<td>{escape(notification.created_at.isoformat(timespec='seconds'))}</td>"
        f"<td>{escape(str(notification.delivered))}</td>"
        "</tr>"
    )


def _console_css() -> str:
    return """
    :root {
      color-scheme: light;
      --bg: #f5f2ea;
      --panel: #fffdf8;
      --line: #d8cfc0;
      --text: #1f1a14;
      --muted: #6b6257;
      --accent: #16423c;
      --danger: #8f3b2f;
      --warning: #9a6b10;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      background: radial-gradient(circle at top, #efe4d1, var(--bg));
      color: var(--text);
    }
    .shell {
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    .shell.narrow { max-width: 560px; }
    .topbar, .panel, .review-card, .metric {
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 0 10px 30px rgba(40, 28, 18, 0.06);
      border-radius: 18px;
    }
    .topbar, .panel {
      padding: 20px;
      margin-bottom: 20px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }
    .grid.metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .metric { padding: 16px; }
    .metric h2 {
      margin: 0 0 8px;
      font-size: 0.95rem;
      color: var(--muted);
    }
    .metric p {
      margin: 0;
      font-size: 1.7rem;
      font-weight: 700;
    }
    .review-card {
      padding: 16px;
      margin-top: 14px;
    }
    .review-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 10px;
    }
    .statement {
      font-size: 1.08rem;
      margin: 0 0 8px;
    }
    .muted {
      color: var(--muted);
      margin-top: 0;
    }
    .stack {
      display: grid;
      gap: 10px;
    }
    .actions {
      display: flex;
      gap: 10px;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 0.95rem;
    }
    input, textarea, button, .btn {
      font: inherit;
      border-radius: 12px;
    }
    input, textarea {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--line);
      background: #fff;
    }
    button, .btn {
      border: 0;
      padding: 10px 14px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      text-decoration: none;
      display: inline-block;
      text-align: center;
    }
    button.secondary, .btn.secondary { background: var(--danger); }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    .badge {
      display: inline-flex;
      padding: 4px 8px;
      border-radius: 999px;
      background: #efe8da;
      color: var(--text);
      font-size: 0.82rem;
    }
    .badge-dead_lettered, .badge-challenged { background: #f5ddd8; color: var(--danger); }
    .badge-retrying { background: #f6ebcf; color: var(--warning); }
    .badge-succeeded, .badge-attested { background: #dcebe4; color: var(--accent); }
    .error { color: var(--danger); }
    @media (max-width: 800px) {
      .topbar { flex-direction: column; }
      .actions { flex-direction: column; }
      table, thead, tbody, th, td, tr { display: block; }
      thead { display: none; }
      td { padding: 8px 0; }
    }
    """
