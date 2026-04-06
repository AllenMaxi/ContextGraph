/**
 * InspectPanel — DOM overlay showing detailed agent info.
 *
 * SAFE: Uses only document.createElement + textContent. Never innerHTML.
 */

const GLOW_COLORS = {
  green: '#10b981',
  yellow: '#f59e0b',
  red: '#ef4444',
  gray: '#64748b',
  blue: '#3b82f6',
};

const BUCKET_META = [
  { key: 'decisions', label: 'Decisions', cls: 'bucket-decisions' },
  { key: 'open_tasks', label: 'Open Tasks', cls: 'bucket-tasks' },
  { key: 'failures', label: 'Failures', cls: 'bucket-failures' },
  { key: 'resolved', label: 'Resolved', cls: 'bucket-resolved' },
  { key: 'commands', label: 'Commands', cls: 'bucket-commands' },
  { key: 'files', label: 'Files', cls: 'bucket-files' },
];

const EVENT_COLORS = {
  tool_call: '#06b6d4',
  decision: '#6366f1',
  error: '#ef4444',
  file_change: '#f59e0b',
  memory: '#a78bfa',
  default: '#64748b',
};

export default class InspectPanel {
  constructor() {
    this.el = document.getElementById('inspect-panel');
    this._agentId = null;
    this._bound = false;

    this._bind();
  }

  /* ------------------------------------------------------------------ */
  /*  Event binding                                                      */
  /* ------------------------------------------------------------------ */

  _bind() {
    if (this._bound) return;
    this._bound = true;

    window.addEventListener('inspect-agent', (evt) => {
      const agentId = evt.detail?.agentId;
      if (agentId) {
        this.show(agentId);
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /*  Show / Hide                                                        */
  /* ------------------------------------------------------------------ */

  async show(agentId) {
    this._agentId = agentId;
    document.body.classList.add('game-dimmed');
    this.el.classList.remove('hidden');

    // Clear old content
    this._clear();

    // Show loading
    const loading = this._createSection('Loading...');
    this.el.appendChild(loading);

    try {
      const [agent, sessions] = await Promise.all([
        this._fetch(`/v1/agents/${agentId}`),
        this._fetch(`/v1/sessions?agent_id=${agentId}&limit=1`),
      ]);

      let events = [];
      const session = sessions?.items?.[0] || sessions?.[0] || null;
      if (session) {
        const sessionId = session.session_id || session.id;
        if (sessionId) {
          const evtResp = await this._fetch(`/v1/sessions/${sessionId}/events`);
          events = evtResp?.items || evtResp || [];
        }
      }

      this._clear();
      this._render(agent, session, events);
    } catch (err) {
      console.warn('[InspectPanel] fetch error', err);
      this._clear();
      this._render({ agent_id: agentId, name: agentId }, null, []);
    }
  }

  hide() {
    this.el.classList.add('hidden');
    document.body.classList.remove('game-dimmed');
    this._agentId = null;
  }

  _clear() {
    while (this.el.firstChild) {
      this.el.removeChild(this.el.firstChild);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Fetch helper                                                       */
  /* ------------------------------------------------------------------ */

  async _fetch(url) {
    const resp = await fetch(url);
    if (!resp.ok) return null;
    return resp.json();
  }

  /* ------------------------------------------------------------------ */
  /*  Render                                                             */
  /* ------------------------------------------------------------------ */

  _render(agent, session, events) {
    if (!agent) agent = {};

    // 1. Header
    this._renderHeader(agent);

    // 2. Current Session
    this._renderSession(session);

    // 3. Session State / Buckets
    this._renderBuckets(session);

    // 4. Tools & Capabilities
    this._renderTools(agent);

    // 5. Timeline
    this._renderTimeline(events);
  }

  /* ------------------------------------------------------------------ */
  /*  1. Header                                                          */
  /* ------------------------------------------------------------------ */

  _renderHeader(agent) {
    const header = document.createElement('div');
    header.className = 'inspect-header';

    // Mini avatar
    const avatar = document.createElement('div');
    avatar.className = 'inspect-avatar';
    const colorIdx = agent.color_index ?? 0;
    const COLORS = [
      '#6366f1', '#f97316', '#06b6d4', '#ec4899',
      '#10b981', '#f59e0b', '#f43f5e', '#0ea5e9',
      '#8b5cf6', '#14b8a6', '#84cc16', '#d946ef',
    ];
    avatar.style.backgroundColor = COLORS[colorIdx % COLORS.length];
    header.appendChild(avatar);

    // Name + status
    const nameWrap = document.createElement('div');
    nameWrap.style.flex = '1';

    const name = document.createElement('div');
    name.className = 'inspect-name';
    name.textContent = agent.name || agent.agent_id || 'Agent';
    nameWrap.appendChild(name);

    if (agent.status || agent.glow) {
      const status = document.createElement('span');
      status.className = 'inspect-status';
      status.style.backgroundColor = GLOW_COLORS[agent.glow || agent.status] || GLOW_COLORS.gray;
      name.appendChild(status);
    }

    header.appendChild(nameWrap);

    // Close button
    const close = document.createElement('button');
    close.className = 'inspect-close';
    close.textContent = '\u2715';
    close.addEventListener('click', () => this.hide());
    header.appendChild(close);

    this.el.appendChild(header);
  }

  /* ------------------------------------------------------------------ */
  /*  2. Current Session                                                 */
  /* ------------------------------------------------------------------ */

  _renderSession(session) {
    const section = this._createSection('Current Session');

    if (!session) {
      const empty = document.createElement('div');
      empty.textContent = 'No active session';
      empty.style.color = '#64748b';
      empty.style.fontSize = '13px';
      section.appendChild(empty);
      this.el.appendChild(section);
      return;
    }

    const info = document.createElement('div');
    info.className = 'session-info';

    const rows = [
      ['Title', session.title || session.session_id || 'Untitled'],
      ['Events', String(session.event_count ?? '---')],
      ['Status', session.status || 'active'],
    ];

    for (const [key, val] of rows) {
      const row = document.createElement('div');
      row.className = 'session-info-row';

      const k = document.createElement('span');
      k.className = 'session-info-key';
      k.textContent = key;
      row.appendChild(k);

      const v = document.createElement('span');
      v.className = 'session-info-val';
      v.textContent = val;
      row.appendChild(v);

      info.appendChild(row);
    }

    section.appendChild(info);
    this.el.appendChild(section);
  }

  /* ------------------------------------------------------------------ */
  /*  3. Buckets                                                         */
  /* ------------------------------------------------------------------ */

  _renderBuckets(session) {
    const section = this._createSection('Session State');

    const grid = document.createElement('div');
    grid.className = 'bucket-grid';

    const state = session?.state || session?.buckets || {};

    for (const meta of BUCKET_META) {
      const item = document.createElement('div');
      item.className = `bucket-item ${meta.cls}`;

      const label = document.createElement('div');
      label.className = 'bucket-item-label';
      label.textContent = meta.label;
      item.appendChild(label);

      const value = document.createElement('div');
      value.className = 'bucket-item-value';
      value.textContent = String(state[meta.key] ?? 0);
      item.appendChild(value);

      grid.appendChild(item);
    }

    section.appendChild(grid);
    this.el.appendChild(section);
  }

  /* ------------------------------------------------------------------ */
  /*  4. Tools                                                           */
  /* ------------------------------------------------------------------ */

  _renderTools(agent) {
    const tools = agent.tools || agent.capabilities || [];
    if (!tools.length) return;

    const section = this._createSection('Tools & Capabilities');

    const wrap = document.createElement('div');
    wrap.className = 'tool-badges';

    for (const tool of tools) {
      const badge = document.createElement('span');
      badge.className = 'tool-badge';
      badge.textContent = typeof tool === 'string' ? tool : tool.name || 'tool';
      wrap.appendChild(badge);
    }

    section.appendChild(wrap);
    this.el.appendChild(section);
  }

  /* ------------------------------------------------------------------ */
  /*  5. Timeline                                                        */
  /* ------------------------------------------------------------------ */

  _renderTimeline(events) {
    const section = this._createSection('Timeline');

    const recent = Array.isArray(events) ? events.slice(-15).reverse() : [];

    if (recent.length === 0) {
      const empty = document.createElement('div');
      empty.textContent = 'No events yet';
      empty.style.color = '#64748b';
      empty.style.fontSize = '13px';
      section.appendChild(empty);
      this.el.appendChild(section);
      return;
    }

    const list = document.createElement('ul');
    list.className = 'timeline-list';

    for (const evt of recent) {
      const item = document.createElement('li');
      item.className = 'timeline-item';

      // Vertical line
      const line = document.createElement('div');
      line.className = 'timeline-line';
      item.appendChild(line);

      // Dot
      const dot = document.createElement('div');
      dot.className = 'timeline-dot';
      const evtType = evt.event_type || evt.type || 'default';
      dot.style.backgroundColor = EVENT_COLORS[evtType] || EVENT_COLORS.default;
      item.appendChild(dot);

      // Text
      const text = document.createElement('span');
      text.textContent = evt.summary || evt.description || evtType;
      item.appendChild(text);

      // Timestamp
      if (evt.created_at || evt.timestamp) {
        const time = document.createElement('span');
        time.className = 'timeline-time';
        const d = new Date(evt.created_at || evt.timestamp);
        time.textContent = d.toLocaleTimeString();
        item.appendChild(time);
      }

      list.appendChild(item);
    }

    section.appendChild(list);
    this.el.appendChild(section);
  }

  /* ------------------------------------------------------------------ */
  /*  Helpers                                                            */
  /* ------------------------------------------------------------------ */

  _createSection(title) {
    const section = document.createElement('div');
    section.className = 'inspect-section';

    if (title) {
      const label = document.createElement('div');
      label.className = 'inspect-label';
      label.textContent = title;
      section.appendChild(label);
    }

    return section;
  }
}
