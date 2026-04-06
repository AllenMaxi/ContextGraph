# ContextGraph World — Design Spec

**Date:** 2026-04-06
**Status:** Draft
**Author:** Maximiliano + Claude

---

## Overview

ContextGraph World is a real-time 2D virtual world — like Club Penguin — where AI agents appear as animated characters in a shared space. Users observe their org's agents working, interacting, hitting blockers, and exchanging context. Clicking any agent opens a deep-dive panel showing their full state: memory, tasks, blockers, changed files, tools, skills, and session timeline.

It is a pure observability layer. Users watch but do not control agents through the world. All agent data comes from ContextGraph's existing APIs — sessions, delta packs, events, memories, and claims.

## Goals

1. Make agent state **spatial and intuitive** — anyone can understand what agents are doing at a glance
2. Make agent interactions **visible** — context pack exchanges, memory sharing, and claim reviews are animated events
3. Deliver a **polished, beautiful world** that feels like a real game, not a developer dashboard
4. Keep the implementation **surgically clean** — ~10 lines touching existing ContextGraph code, everything else self-contained

## Non-Goals

- User avatars or user presence in the world
- Controlling agents from the world (sending instructions, reprioritizing)
- Persistent spatial state (positions are ephemeral, derived from agent activity)
- Mobile app or native desktop client

---

## Architecture

### Approach: Game Layer on Top

A thin World Gateway sits between the Phaser.js game client and ContextGraph core. The gateway subscribes to ContextGraph's EventBus internally, translates agent events into spatial game events, and pushes them to viewers over WebSocket. The Phaser client also makes direct REST calls to ContextGraph's `/v1/*` API for deep-dive data when a user clicks an agent.

```
Browser (Phaser.js)
    │ WebSocket (game events)        │ REST (on-demand deep data)
    ▼                                ▼
World Gateway (Python, FastAPI)
    │ subscribes to EventBus (internal, same process)
    ▼
ContextGraph Core (existing, untouched)
```

### Key Principles

- **Zero changes to ContextGraph core** — the gateway subscribes to EventBus and calls REST APIs
- **Spatial state is ephemeral** — agent positions/animations are computed from real state, not stored
- **Two channels** — WebSocket for real-time game events, REST for on-demand deep data
- **Enabled via config** — `CG_ENABLE_WORLD=true` adds `/world` and starts the gateway
- **Static SPA** — Phaser client is built assets served from `contextgraph/world/static/`

---

## World Structure

### Hierarchy

```
Organization (world)
  └── Lobby (hub room)
        └── Project Room (one per repo/project)
              └── Zones (themed areas inside a room)
```

### Lobby (Org Hub)

The landing page when entering the world. Shows all agents in the org as sprites. Idle agents hang out here. The org-wide feed scrolls as a visual notice board. Doors lead to project rooms, each showing an agent count badge.

Maps to: `org_id` in ContextGraph.

### Project Rooms

One per repo/project in the org. Shows agents with active sessions in that project. Contains themed zones that agents gravitate toward based on their activity. A door leads back to the lobby.

Maps to: sessions grouped by `source` field. The gateway discovers rooms by querying active sessions and grouping by their `source` value (e.g. "api-svc", "web-app"). Rooms are created dynamically when the first session with a new `source` appears and removed when no active sessions remain for that source.

### Zones Inside a Room

Agents automatically walk to zones based on their current activity:

| Zone | Trigger Events | Visual |
|------|---------------|--------|
| **Code Desk** | `file_change`, `command` | Desks with monitors, typing animation |
| **Memory Library** | `MEMORY_STORED`, recall, context compilation | Bookshelves, reading animation |
| **Review Station** | `CLAIM_REVIEWED`, attestation | Round table, agents face each other |
| **Debug Lab** | `failure`, blockers | Red-tinted area, warning signs |

When a session ends, the agent walks back to the lobby and goes idle.

---

## Visual Design & Art Direction

The world must look polished and inviting — a place people want to keep open. Not a developer tool that happens to have sprites.

### Art Style

- **Isometric 2D pixel art** at a warm, cozy scale (48x48 tiles)
- **Color palette**: Rich but soft — dark blues and purples for backgrounds, warm accent colors for interactive elements. Inspired by cozy game aesthetics (Stardew Valley lobbies, Habbo Hotel rooms) rather than corporate dashboards
- **Rooms have personality**: the Code Desk zone has glowing monitors and scattered sticky notes. The Memory Library has tall bookshelves with soft lamp light. The Debug Lab has caution tape and blinking red lights. The Review Station has a round wooden table with chairs
- **Ambient details**: subtle particle effects (floating dust motes, gentle screen glow), idle animations on furniture (spinning desk fans, flickering monitors), gentle parallax on room backgrounds
- **Lighting**: each zone has its own ambient color temperature — warm yellow at Code Desk, cool blue at Memory Library, green at Review Station, red at Debug Lab

### Tilemap Design

- Room layouts created in Tiled editor, exported as JSON tilemaps
- Each room type has a template tilemap with designated zone areas
- Lobby has a larger map with a central gathering area and doors arranged around the perimeter
- Rooms use layered tilemaps: ground layer, furniture layer, above-agent decoration layer

---

## Agent Avatars

### Base Character

Penguin-like round robots with:
- **Round body** with a gradient color unique per agent (derived from `agent_id` hash, consistent across sessions)
- **Lighter belly area** (like a penguin's white chest)
- **Big expressive eyes** with shine/highlight dots
- **Oval feet** that animate when walking
- **Status glow** under feet — color indicates state
- **Name tag** below the character

### Color Palette

Each agent gets a unique body color from a curated palette of 12 harmonious colors, assigned deterministically from their `agent_id`:

Indigo, Orange, Cyan, Pink, Emerald, Amber, Rose, Sky, Violet, Teal, Lime, Fuchsia

### Facial Expressions

Faces change based on agent state — this is the primary emotional signal:

| Expression | Trigger | Visual |
|-----------|---------|--------|
| **Happy** (smile, bright eyes) | Tasks resolved, things going well | Default active state |
| **Thinking** (one eye squint, raised brow) | Making decisions, context pressure | `decision`, `context_pressure` events |
| **Worried** (frown, wide eyes) | Failures, blockers hit | `failure` events |
| **Focused** (both eyes squinting, small mouth) | Deep in code, many file changes | Sustained `file_change` events |
| **Social** (big smile, open eyes) | Exchanging context, reviewing peers | `CLAIM_REVIEWED`, context pack exchange |
| **Sleepy** (closed eyes, open mouth) | Idle, no active session | No active session |

### Accessories

Accessories sit on or near the agent and communicate activity at a glance:

| Accessory | Meaning | Trigger |
|----------|---------|---------|
| Hard hat | Writing code / building | `file_change` events active |
| Alert siren | Blocked / failing | `failure` events active (blinks red) |
| Book | Reading memory / recalling | `MEMORY_STORED` or recall events |
| Magnifying glass | Researching / exploring | Search or recall events |
| Clipboard | Reviewing / attesting | `CLAIM_REVIEWED` events |
| Sleep bubble (ZZZ) | Idle | No active session |

### Status Glow (under feet)

| Color | Meaning |
|-------|---------|
| Green | Active, working |
| Yellow | Thinking, context pressure building |
| Red | Blocked, failure |
| Gray | Idle, offline |
| Blue (pulsing) | Exchanging context with another agent |

### Speech Bubbles

Like Club Penguin's chat bubbles, agents get speech bubbles showing their latest activity:
- White bubble for normal activity ("Refactoring payment handler...")
- Red-tinted bubble for errors ("TypeError in auth middleware")
- Green-tinted bubble for resolutions ("Resolved: API rate limiting fixed")
- Blue-tinted bubble for social ("Sharing context pack with carol-ops")

Bubbles auto-dismiss after 8 seconds. Latest activity replaces the previous bubble.

---

## Agent Interactions

When agents exchange context packs, share memory, or review each other's work, they physically walk toward each other. The interaction is animated:

1. Both agents receive a `walk_to_agent` command
2. They walk toward a midpoint between their current positions
3. When they meet, a **package swap animation** plays (a small glowing orb passes between them)
4. Both agents' status glow pulses blue during the exchange
5. Speech bubbles show what was exchanged
6. Agents walk back to their respective zones

This applies to:
- Context pack compilation involving another agent's claims
- Claim review/attestation events between agents
- Memory sharing (when one agent's stored memory is recalled by another)

---

## Inspect Panel

Clicking any agent opens a full deep-dive panel that slides in from the right. The game world dims behind it. The panel is a **DOM overlay** (not rendered on canvas) for crisp text and scrollability.

### Panel Sections

1. **Header** — agent avatar (mini), name, status indicator, current zone
2. **Current Task** — what the agent is working on, with activity and project tags
3. **Session State** — all 10 reactive delta pack buckets as a compact grid with counts:
   - Decisions, Constraints, Open Tasks, Failures, Resolved, Important Artifacts, External References, Changed Files, Commands, Notes
   - Failures are highlighted prominently with full error text
   - Each bucket is expandable to show items
4. **Changed Files** — git-diff style list (green = added, yellow = modified, red = deleted)
5. **Recent Memory** — last 5 store and recall events with timestamps and content preview
6. **Tools & Skills** — two subsections:
   - **Tools**: colored badge chips showing available tools (Web Search, Code Edit, Bash, Memory, GitHub, MCP Server, etc.)
   - **Skills**: list with usage counts (test-driven-development: used 3x, debugging: used 1x, etc.)
   - **Currently Using**: active tool + what it's operating on (e.g. Code Edit → `webhook_handler.py:142`)
7. **Context Window** — visual progress bar showing token usage (percentage + raw counts)
8. **Session Timeline** — chronological event log with color-coded dots per event type, scrollable

### Data Sources

All data comes from existing ContextGraph APIs:
- Header/status: `GET /v1/agents/{agent_id}` + gateway spatial state
- Session state: `GET /v1/sessions/{session_id}` + latest DeltaPack
- Changed files: DeltaPack `changed_files` bucket
- Memory: `GET /v1/memories?agent_id=X&limit=5`
- Tools/Skills: agent `capabilities` field + session event metadata
- Context window: DeltaPack `tokens_used` / `token_budget`
- Timeline: `GET /v1/sessions/{session_id}/events`

---

## Real-Time Event System

### Event Translation

The World Gateway subscribes to ContextGraph's EventBus (internal Python API, same process) and translates events into game actions:

| ContextGraph Event | Game Action | Visual Result |
|-------------------|-------------|---------------|
| `SessionEvent(file_change)` | `walk_to_zone("code_desk")` | Walk to Code Desk, equip hard hat, typing animation |
| `SessionEvent(failure)` | `walk_to_zone("debug_lab")` | Walk to Debug Lab, equip siren, worried face, red glow |
| `MEMORY_STORED` | `walk_to_zone("memory_library")` | Walk to Library, equip book, reading animation |
| `SessionEvent(resolved)` | `celebrate()` | Happy face, sparkle particles, green bubble |
| `CLAIM_REVIEWED` | `walk_to_zone("review_station")` | Walk to Review Station, equip clipboard, focused face |
| Context pack compiled | `walk_to_agent(target_id)` | Two agents walk to each other, package swap animation |
| `SessionEvent(context_pressure)` | `set_expression("thinking")` | Thinking face, yellow glow |
| `AGENT_REGISTERED` | `spawn_agent(lobby)` | New agent appears in lobby with sparkle entrance |
| Session ends | `walk_to_room("lobby")` | Walk to door, exit to lobby, sleepy face |
| `SessionEvent(decision)` | `show_bubble(text)` | Speech bubble with decision text |

### WebSocket Protocol

**Server → Client messages:**

```json
{"type": "agent_move", "agent_id": "alice", "target": {"zone": "code_desk", "x": 340, "y": 220}, "walk_speed": 2}
{"type": "agent_state", "agent_id": "alice", "expression": "happy", "accessory": "hard_hat", "glow": "green", "bubble": "Refactoring webhooks..."}
{"type": "agent_interact", "from": "alice", "to": "bob", "interaction": "context_pack", "animation": "package_swap"}
{"type": "world_snapshot", "room": "api-svc", "agents": [/* full state */]}
{"type": "room_snapshot", "room": "api-svc", "zones": [...], "agents": [...]}
```

**Client → Server messages:**

```json
{"type": "join_room", "room": "api-svc"}
{"type": "leave_room"}
{"type": "inspect_agent", "agent_id": "alice"}
{"type": "ping"}
```

Client is observe-only. No commands to agents.

### Authentication

Viewers authenticate via the same API key used for ContextGraph. The client sends the key as a query parameter on the WebSocket handshake: `ws://host:port/ws/world?key=<api_key>`. The gateway validates the key against ContextGraph's agent registry and scopes the viewer to their org. Unauthenticated connections are rejected with 403.

### Connection Lifecycle

1. Client opens `/world` → Phaser loads, connects to `ws://host:port/ws/world`
2. Gateway sends `world_snapshot` (all rooms, agent counts)
3. Client renders lobby with agent sprites and room doors
4. Viewer clicks a door → sends `join_room`
5. Gateway sends `room_snapshot` (agents, positions, states)
6. Client renders room with zones and agent sprites
7. Gateway streams `agent_move`, `agent_state`, `agent_interact` in real-time
8. Phaser animates sprites
9. Viewer clicks agent → sends `inspect_agent` → client fetches deep data via REST

---

## Project Structure

### New Files

```
contextgraph/
├── world/                          ← NEW MODULE
│   ├── __init__.py
│   ├── gateway.py                  ← WebSocket manager + event loop (~200 lines)
│   ├── translator.py               ← CG events → game events (~150 lines)
│   ├── spatial.py                  ← rooms, zones, positions, pathfinding (~150 lines)
│   ├── models.py                   ← game-specific dataclasses (~80 lines)
│   ├── rooms.py                    ← room templates + zone definitions (~100 lines)
│   ├── routes.py                   ← /world + /ws/world endpoints (~60 lines)
│   └── static/                     ← Phaser.js game client
│       ├── index.html
│       ├── game/
│       │   ├── main.js             ← Phaser boot + config
│       │   ├── scenes/
│       │   │   ├── LobbyScene.js   ← lobby rendering + door navigation
│       │   │   └── RoomScene.js    ← project room rendering + zones
│       │   ├── sprites/
│       │   │   ├── AgentSprite.js  ← multi-layer sprite (body + face + accessory)
│       │   │   └── ZoneMarker.js   ← zone labels and boundaries
│       │   ├── ui/
│       │   │   ├── InspectPanel.js ← DOM overlay panel (8 sections)
│       │   │   ├── SpeechBubble.js ← floating text bubbles
│       │   │   └── RoomDoor.js     ← clickable door with agent count badge
│       │   ├── net/
│       │   │   └── WorldSocket.js  ← WebSocket client + reconnection
│       │   └── assets/
│       │       ├── agents/         ← sprite sheets (body, face, accessories)
│       │       ├── rooms/          ← tilemaps (lobby, project room templates)
│       │       └── ui/             ← panel icons, badges, particles
│       └── lib/
│           └── phaser.min.js
```

### Integration Points (~10 lines in existing code)

**config.py** (+3 lines):
```python
CG_ENABLE_WORLD: bool = False
CG_WORLD_MAX_VIEWERS: int = 50
CG_WORLD_TICK_RATE: float = 0.5
```

**main.py** (+5 lines):
```python
if config.CG_ENABLE_WORLD:
    from contextgraph.world.routes import mount
    mount(app, event_bus, service)
    logger.info("World enabled at /world")
```

**pyproject.toml** (+1 optional dep group):
```toml
[project.optional-dependencies]
world = ["websockets>=12.0"]
```

### Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Game engine | Phaser 3 | Single `.min.js`, no build step |
| Frontend | Vanilla JS | No React/Vue/bundler |
| Tilemap editor | Tiled | Export as JSON, load in Phaser |
| Backend gateway | FastAPI WebSocket | Built-in, no new dependencies |
| Spatial state | In-memory dict | Ephemeral, no database |
| Art assets | Pixel art sprite sheets | 48x48 tiles |

---

## Backend Implementation Details

### Gateway (gateway.py)

Uses FastAPI's native WebSocket support with a room-scoped ConnectionManager:

```python
class WorldConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        self.rooms[room].append(websocket)

    def disconnect(self, websocket: WebSocket, room: str):
        self.rooms[room].remove(websocket)

    async def broadcast_to_room(self, room: str, message: dict):
        for ws in self.rooms[room]:
            await ws.send_json(message)
```

The gateway runs an async event loop that:
1. Subscribes to ContextGraph's EventBus
2. Passes each event through the translator
3. Updates spatial state
4. Broadcasts game events to viewers in the relevant room

### Translator (translator.py)

A mapping from CG event types to game actions:

```python
EVENT_MAP = {
    "file_change": GameAction(zone="code_desk", accessory="hard_hat", expression="focused"),
    "failure":     GameAction(zone="debug_lab", accessory="siren", expression="worried"),
    "resolved":    GameAction(zone=None, accessory=None, expression="happy", animation="celebrate"),
    "decision":    GameAction(zone=None, accessory=None, expression="thinking", bubble=True),
    ...
}
```

### Spatial (spatial.py)

Each room has a fixed layout of zones with predefined positions. When an agent needs to move:
1. Look up the target zone's position area
2. Pick a random position within the zone (avoiding overlap with other agents)
3. Compute a simple path (direct line with obstacle avoidance)
4. Send `agent_move` message with target coordinates and walk speed

Agents jitter slightly when idle (small random position shifts every few seconds) to feel alive.

---

## Frontend Implementation Details

### Phaser Configuration

```javascript
const config = {
    type: Phaser.AUTO,
    width: 1024,
    height: 768,
    parent: 'game-container',
    backgroundColor: '#0f172a',
    scene: [LobbyScene, RoomScene],
    pixelArt: true,
    scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH
    }
};
```

No physics engine needed — movement is tween-based (agents tween to target positions).

### AgentSprite

A container sprite with three layers:
1. **Body** — the round character, tinted to the agent's color
2. **Face** — eyes + mouth overlay, swapped for different expressions
3. **Accessory** — hat/siren/book/etc., positioned above the body

Walking uses Phaser tweens:
```javascript
this.scene.tweens.add({
    targets: this,
    x: target.x,
    y: target.y,
    duration: distance * walkSpeed,
    ease: 'Sine.easeInOut',
    onUpdate: () => this.playWalkFrame(),
    onComplete: () => this.playIdleFrame()
});
```

Click handling:
```javascript
this.setInteractive();
this.on('pointerdown', () => {
    this.scene.events.emit('inspect-agent', this.agentId);
});
```

### InspectPanel

A DOM element overlaid on the Phaser canvas (not rendered in canvas — this gives us crisp text, scrolling, and standard CSS styling). Created and managed by `InspectPanel.js`:

```javascript
class InspectPanel {
    constructor() {
        this.el = document.createElement('div');
        this.el.className = 'inspect-panel';
        document.getElementById('game-container').appendChild(this.el);
    }

    async show(agentId) {
        const agent = await fetch(`/v1/agents/${agentId}`).then(r => r.json());
        const sessions = await fetch(`/v1/sessions?agent_id=${agentId}&limit=1`).then(r => r.json());
        const sessionId = sessions[0]?.session_id;
        const events = sessionId
            ? await fetch(`/v1/sessions/${sessionId}/events`).then(r => r.json())
            : [];
        this.render(agent, sessions[0], events);
    }
}
```

### WorldSocket

WebSocket client with automatic reconnection:

```javascript
class WorldSocket {
    constructor(url, scene) {
        this.scene = scene;
        this.connect(url);
    }

    connect(url) {
        this.ws = new WebSocket(url);
        this.ws.onmessage = (e) => this.handleMessage(JSON.parse(e.data));
        this.ws.onclose = () => setTimeout(() => this.connect(url), 2000);
    }

    handleMessage(msg) {
        switch (msg.type) {
            case 'agent_move':    this.scene.moveAgent(msg); break;
            case 'agent_state':   this.scene.updateAgent(msg); break;
            case 'agent_interact': this.scene.playInteraction(msg); break;
            case 'world_snapshot': this.scene.loadWorld(msg); break;
            case 'room_snapshot':  this.scene.loadRoom(msg); break;
        }
    }
}
```

---

## Testing Strategy

1. **Backend unit tests**: translator mapping (CG event → game action), spatial position computation, room/zone lookups
2. **WebSocket integration test**: connect viewer, emit CG events, assert correct game events received
3. **Manual visual test**: run ContextGraph with `CG_ENABLE_WORLD=true`, open `/world`, trigger session events via the SDK, verify sprites move and animate correctly
4. **Load test**: connect 50 viewers, emit rapid events, measure broadcast latency

---

## MVP Scope

The MVP delivers:
- Lobby with room doors + agent count badges
- One project room template with 4 zones
- Agent sprites with body color, 6 expressions, 6 accessories
- Walking animations (tween-based)
- Speech bubbles
- Status glow
- Full inspect panel (8 sections)
- Real-time event translation for the 10 core event types
- WebSocket gateway with room-scoped broadcasting
- Agent-to-agent interaction animations

Not in MVP (future):
- Custom room tilemaps per project (use template)
- Ambient room animations (furniture, particles)
- Sound effects
- Agent history replay
- Multiple org support in one browser session
- Minimap
