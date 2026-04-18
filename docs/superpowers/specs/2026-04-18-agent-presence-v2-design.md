# Agent Presence v2 — Design Spec

**Date:** 2026-04-18
**Scope:** Extend ContextGraph World so every Claude Code agent (main + subagents) spawns as a distinct, persistent Habbo-style wizard avatar that talks, moves, interacts, and upgrades as its skill/tool surface grows.

---

## 1. Goals

1. **Per-agent identity.** Every distinct agent (main Claude session, each subagent invocation, user) renders as its own wizard with a deterministic, persistent look.
2. **Visible spawning.** When Claude spawns a subagent (via the `Agent` tool), it enters the world, walks toward the parent, and interacts visibly.
3. **Speech.** User prompts and assistant responses appear as speech bubbles above the correct avatar in real time.
4. **Upgradeable avatars.** As the user installs more skills/tools, the main Claude avatar advances in rank (cape → crown → aura → familiar) with an on-screen upgrade burst.
5. **Movement.** Agents walk along anchor waypoints instead of teleporting.

## 2. Non-Goals

- No new sprite sheets beyond the existing 3 wizard base sprites. All class/rank differentiation is procedural overlay.
- No multi-user / multi-session merging. One server = one project's agents.
- No rewriting the existing `SpatialState`, `WorldGateway`, `Meeting`, or `RoomLayout` systems. We extend them.

## 3. Current State (verified 2026-04-18)

- `contextgraph/world/` already has: `models.py`, `spatial.py`, `gateway.py`, `meeting.py`, `rooms.py`, `translator.py`, `activity_bridge.py`, `routes.py`, and a Phaser 3 frontend under `static/game/`.
- `PostToolUse` hook in `.claude/hooks/world_activity.sh` POSTs to `/v1/world/activity`. Works, but currently tags every tool call with `actor=claude` — no subagent distinction.
- **Known bug:** The world server on port 8420 is not auto-started. The hook fires into the void when server is down. Mitigation is in §10.

## 4. Identity Model

### 4.1 AgentArchetype (new enum, `models.py`)

| Archetype | Trigger |
|---|---|
| `ARCHMAGE` | Main Claude session (`actor_id = claude`) |
| `SCOUT` | Subagent `subagent_type=Explore` |
| `ORACLE` | Subagent `subagent_type=Plan` |
| `SCRIBE` | Subagent `subagent_type=code-reviewer` or `superpowers:code-reviewer` |
| `APPRENTICE` | Subagent `subagent_type=general-purpose` |
| `ARTIFICER` | Subagent `subagent_type=statusline-setup` |
| `SAGE` | Subagent `subagent_type=claude-code-guide` |
| `USER` | User avatar (from `UserPromptSubmit`) |
| `UNKNOWN` | Fallback |

Extending the archetype list is a one-line change in a mapping table.

### 4.2 AgentRank (new enum, `models.py`)

Rank derives from `tools_count + skills_count` at the time of registration (or upgrade event):

| Rank | Threshold | Visual delta |
|---|---|---|
| `NOVICE` | 0–5 | plain robe |
| `ADEPT` | 6–15 | trim band on robe |
| `MAGE` | 16–30 | half-cape |
| `HIGH_MAGE` | 31–60 | full cape + staff topper |
| `AVATAR` | 61+ | cape + aura particles + floating familiar orb |

### 4.3 Actor ID convention

- Main: `actor_id = "claude"`
- Subagent: `actor_id = f"claude.{subagent_type}.{invocation_ordinal}"` — ordinal is per-session monotonic counter so each spawn gets a fresh character. Same type → same archetype → deterministic color variant by hash.
- User: `actor_id = "user"`

### 4.4 Persistence

- File: `<project_root>/.contextgraph/identities.json`
- Schema: `{ agent_id: {archetype, rank, color_index, tools_count, skills_count, created_at, last_seen} }`
- Loaded once at server boot into an in-memory dict held by `SpatialState`.
- Written through `save_identity()` after every registration or upgrade (atomic write via tempfile + rename).
- **Stable:** once `archetype` and `color_index` are assigned, they never change. Only `rank`, `tools_count`, `skills_count`, `last_seen` update.

### 4.5 AgentVisual extensions

Add four fields to `AgentVisual` (`models.py`):

```python
archetype: AgentArchetype = AgentArchetype.UNKNOWN
rank: AgentRank = AgentRank.NOVICE
parent_agent_id: str | None = None
tools_count: int = 0
skills_count: int = 0
```

All four round-trip through `to_dict()` so the frontend can render class + rank overlays.

## 5. Backend Architecture

### 5.1 New modules

- `contextgraph/world/identity_bridge.py` — `register_identity(actor_id, archetype, tools, skills)`, `upgrade_identity(actor_id, tools, skills)`, `spawn_subagent(parent, subagent_type, description)`, `despawn_subagent(actor_id, result_summary)`. Each emits the right gateway broadcast (`AGENT_SPAWN` / `AGENT_STATE` / `AGENT_DESPAWN` / new `AGENT_UPGRADE`).
- `contextgraph/world/message_bridge.py` — `user_prompt(text)`, `assistant_message(actor_id, text)`. Sets `bubble` field on agent, broadcasts `AGENT_STATE`. Bubbles auto-expire after 8s via existing gateway TTL plumbing (or new TTL field — see §5.3).

### 5.2 Routes (extend `routes.py`)

- `POST /v1/world/identity` — body `{actor, archetype, tools_count, skills_count}` → register or upsert.
- `POST /v1/world/identity/upgrade` — body `{actor, tools_count, skills_count}` → recompute rank, broadcast upgrade if changed.
- `POST /v1/world/spawn` — body `{parent, subagent_type, description, invocation_id}` → creates subagent, walks to parent anchor.
- `POST /v1/world/despawn` — body `{actor, result_summary}` → emits handoff orb event, fades out.
- `POST /v1/world/message` — body `{actor, role, text}` → sets bubble. `role` is `user` or `assistant`.

All endpoints idempotent, validate `actor` non-empty, use existing `_schedule` fire-and-forget pattern.

### 5.3 New event types (`models.py`)

```python
class GameEventType(StrEnum):
    # ...existing...
    AGENT_UPGRADE = "agent_upgrade"   # {new_rank, old_rank, tools, skills}
    HANDOFF_ORB = "handoff_orb"       # {from_agent, to_agent, color}
```

### 5.4 Movement upgrade

Currently `move_agent_to_zone` snaps `x,y` to anchor. Replacement:

1. `spatial.begin_walk(actor, target_anchor)` — computes `RoomLayout.shortest_path`, stores waypoint list on agent.
2. `gateway` broadcasts `AGENT_PATH` (event already exists in enum) with waypoints.
3. Frontend `AgentSprite` interpolates along waypoints at 180 px/s using existing walk animation.

Backend remains source of truth — if a new event arrives mid-walk, frontend lerp is cancelled and snaps to latest `x,y`.

## 6. Frontend (Phaser)

### 6.1 `AgentSprite.js` extension

Render layers (bottom → top):
1. Base sprite (existing, one of `wizard` / `wizard_fire` / `wizard_ice` chosen from `color_index % 3`).
2. Robe tint (Phaser `setTint` based on palette indexed by `color_index`).
3. Archetype hat + staff (procedural `Graphics` drawn once per archetype, rendered as `RenderTexture` overlay).
4. Rank cape (procedural, 5 variants).
5. Rank aura (particle emitter using existing `particle_rune` / `particle_sparkle`).

### 6.2 New visuals

- **Upgrade burst:** golden vertical beam + tween-in "RANK UP: MAGE" text, 1.2 s. Triggered by `AGENT_UPGRADE` event.
- **Handoff orb:** `particle_glow` tween from child x,y to parent x,y, 0.8 s, then parent flashes green via existing glow slot.
- **Speech bubbles:** extend existing bubble UI to support multi-line, user-role styling (blue border), assistant-role styling (purple). Expire after 8 s.

### 6.3 Subagent-parent linking

`AgentSprite` exposes `setParentSprite(parent)`. While idle, subagent walks to an anchor adjacent to parent. `RoomScene` passes the link when rendering based on `parent_agent_id`.

## 7. Hooks (new files in `.claude/hooks/`)

| Hook | Event | Action |
|---|---|---|
| `world_session_start.sh` | `SessionStart` | Count available tools + skills from env; POST `/v1/world/identity` for `claude` + `user` |
| `world_agent_pre.sh` | `PreToolUse` on `Agent` tool | Parse `subagent_type` + `description` + generate invocation ID; POST `/v1/world/spawn` |
| `world_agent_post.sh` | `PostToolUse` on `Agent` tool | Read tool result summary (first 100 chars); POST `/v1/world/despawn` |
| `world_user_prompt.sh` | `UserPromptSubmit` | POST `/v1/world/message` with role=user, text=prompt |
| `world_stop.sh` | `Stop` | Read last assistant message; POST `/v1/world/message` with role=assistant |

Each hook is fire-and-forget (backgrounded curl with 1s timeout) so tool latency never increases.

### 7.1 `settings.local.json` registration

Add a `hooks` block merging the 5 new entries with existing `world_activity.sh`. Matcher for `world_agent_pre.sh` / `world_agent_post.sh` must be `Agent` (exact tool name) so it only fires on subagent spawns, not every tool.

## 8. Data Flow Summary

```
UserPromptSubmit hook ─► POST /message
                             │
SessionStart hook ─► POST /identity                         Phaser
                             │                             ▲
PreToolUse(Agent) ─► POST /spawn    identity_bridge        │
                             │          │                  │
PostToolUse(Agent) ─► POST /despawn    message_bridge ── SpatialState ── WorldGateway ── WebSocket
                             │          │                  │                              │
PostToolUse(*) ─► POST /activity   activity_bridge         │                              │
                             │                              │                              │
Stop hook ─► POST /message ─┘                              │                              │
                                                          persist                         │
                                                          identities.json                 │
                                                                                          ▼
                                                                                       AgentSprite
```

## 9. Testing Strategy

- Unit tests:
  - `test_agent_archetype_assignment` — actor_id patterns map correctly.
  - `test_rank_threshold` — boundary values assign correct rank.
  - `test_identity_persistence` — save → load round trip, archetype/color_index stable.
  - `test_upgrade_event` — rank change emits `AGENT_UPGRADE`.
  - `test_spawn_despawn_flow` — parent/child link, handoff orb event emitted.
  - `test_message_bubble_ttl` — bubble clears after TTL.
- Integration: spin up server + drive via HTTP, assert WebSocket broadcasts.
- Manual: run CLI session, open `/world`, trigger subagent, verify spawn → bubble → despawn visible.

## 10. No-Spawn Bug Mitigation

Root cause: `/v1/world/activity` endpoint lives in `contextgraph.server` and is only reachable when user has started the server (e.g. `CG_ENABLE_WORLD=true python -m contextgraph.server`). The hook cannot know this and silently drops POSTs.

Fix (shipped as part of v2):
- Add `bin/cg-world` shell launcher (or reuse Makefile target) that spawns the server in background, writes PID to `.contextgraph/world.pid`, exposes `/world` at `http://127.0.0.1:8420/world`.
- `SessionStart` hook additionally checks if port 8420 responds; if not, launches the server in the background (disown) and waits 1.5 s before registering identity.
- Document in README.

## 11. Files Changed / Added

### New
- `contextgraph/world/identity_bridge.py`
- `contextgraph/world/message_bridge.py`
- `.claude/hooks/world_session_start.sh`
- `.claude/hooks/world_agent_pre.sh`
- `.claude/hooks/world_agent_post.sh`
- `.claude/hooks/world_user_prompt.sh`
- `.claude/hooks/world_stop.sh`
- `bin/cg-world` (or Makefile target)
- `tests/test_identity_bridge.py`
- `tests/test_message_bridge.py`

### Modified
- `contextgraph/world/models.py` — +`AgentArchetype`, +`AgentRank`, extend `AgentVisual`, +`AGENT_UPGRADE`/`HANDOFF_ORB` event types.
- `contextgraph/world/spatial.py` — identity load/save, archetype/rank fields, upgrade path, walking-path support.
- `contextgraph/world/routes.py` — +5 endpoints.
- `contextgraph/world/gateway.py` — broadcast handlers for new event types.
- `contextgraph/world/static/game/sprites/AgentSprite.js` — class+rank overlays, upgrade burst, handoff orb, waypoint interpolation.
- `contextgraph/world/static/game/scenes/RoomScene.js` — parent-child sprite linking.
- `contextgraph/world/static/game/net/WorldSocket.js` — dispatch new event types.
- `.claude/settings.local.json` — register 5 new hooks.

Estimated ~2500 LOC additions + edits.

## 12. Risks / Open Questions

- **Hook JSON parsing reliability:** Claude Code hook payload shape for `Agent` tool must include `subagent_type` under `tool_input`. Verified in current docs but we add a fallback `UNKNOWN` archetype when missing.
- **Session scoping for ordinals:** `invocation_ordinal` lives in the hook shell. We store it in `.contextgraph/session_counter` and rotate when a new `SessionStart` fires. Acceptable race if two sessions start simultaneously — collisions produce duplicate actor_ids which is harmless (idempotent spawn).
- **Assistant message extraction in `Stop` hook:** The hook payload does not include assistant text directly. We'll read the last message via the transcript file path provided by the hook (`transcript_path` field in payload).
- **Skill count detection:** In `SessionStart` hook we enumerate from the environment-injected skills list. If the list is empty (no plugin system), rank stays NOVICE — acceptable default.
