/**
 * LobbyScene — The Great Hall where all wizard agents idle.
 * Magical illustrated background with parchment title,
 * stone portal doors, ambient sparkle particles, and wizard agents.
 * Now with anchor-based layout and meeting circle rendering.
 */
import AgentSprite from '../sprites/AgentSprite.js';
import RoomDoor from '../ui/RoomDoor.js';
import MagicAtlas from '../ui/MagicAtlas.js';


export default class LobbyScene extends Phaser.Scene {
  constructor() {
    super({ key: 'LobbyScene' });
    /** @type {Map<string, AgentSprite>} */
    this.agents = new Map();
    /** @type {Map<string, RoomDoor>} */
    this.doors = new Map();
    this._layout = null;
    this._meetings = [];
  }

  init(data) {
    this.socket = data.socket;
    this.snapshot = data.snapshot;
    this._layout = data.snapshot?.layout || null;
    this._meetings = data.snapshot?.meetings || [];
  }

  create() {
    this.socket.setScene(this);

    const W = this.scale.width;
    const H = this.scale.height;

    this.cameras.main.fadeIn(400, 27, 48, 71);

    const safe = (label, fn) => {
      try { fn(); } catch (err) {
        console.error('[LobbyScene] ' + label + ' failed:', err);
      }
    };

    // --- Background image ---
    safe('bg', () => {
      const bgImage = this.add.image(W / 2, H / 2, 'lobby_bg');
      bgImage.setDisplaySize(W, H);
    });

    // --- Meeting circle glow ---
    safe('meetingCircle', () => this._drawMeetingCircle());

    // --- Title scroll ---
    safe('titleScroll', () => this._drawTitleScroll(W));

    // --- Room doors ---
    safe('doors', () => this._buildDoors());

    // --- Agents from snapshot ---
    safe('agents', () => {
      if (this.snapshot && this.snapshot.agents) {
        for (const agentData of this.snapshot.agents) {
          if (agentData.room === 'lobby') {
            try { this._spawnAgent(agentData); }
            catch (e) { console.error('[LobbyScene] spawn failed for', agentData?.agent_id, e); }
          }
        }
      }
    });

    // --- Magic Atlas (navigation overlay) ---
    const rooms = (this.snapshot && this.snapshot.rooms) ? this.snapshot.rooms : [];
    safe('atlas', () => {
      this._atlas = new MagicAtlas(this, this.socket, 'lobby', rooms);
    });
    this.events.once('shutdown', () => {
      // Clean up all agents to prevent dangling tween/animation references
      for (const agent of this.agents.values()) {
        agent.destroy();
      }
      this.agents.clear();

      // Clean up doors
      for (const door of this.doors.values()) {
        door.destroy();
      }
      this.doors.clear();

      // Clean up rune orbit
      if (this._runeOrbit) {
        this._runeOrbit.destroy();
        this._runeOrbit = null;
      }

      if (this._atlas) {
        this._atlas.destroy();
        this._atlas = null;
      }
    });

    // --- WebSocket listeners ---
    this._bindEvents();
  }

  /* ================================================================== */
  /*  Side alcove dressing                                               */
  /* ================================================================== */

  _drawAlcoveDressing(W, H) {
    // Removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Ambient particles                                                  */
  /* ================================================================== */

  _createAmbientParticles(W, H) {
    // Removed — clean Habbo aesthetic
  }

  _scheduleAmbientBurst(W, H) {
    // Removed — clean Habbo aesthetic
  }

  _emitAmbientBurst(W, H) {
    // Removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Animated torches                                                   */
  /* ================================================================== */

  _drawTorches(W, H) {
    // Removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Center lighting                                                    */
  /* ================================================================== */

  _drawCenterLighting(W, H) {
    // Removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Moonlight shafts                                                   */
  /* ================================================================== */

  _drawMoonlightShafts(W, H) {
    // Removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Fog layer                                                          */
  /* ================================================================== */

  _drawFogLayer(W, H) {
    // Removed — clean Habbo aesthetic
  }

  _drawMeetingCircle() {
    if (!this._layout || !this._layout.meeting_circle) return;
    const mc = this._layout.meeting_circle;

    const g = this.add.graphics();
    g.setDepth(3);
    // Simple colored circle on floor
    g.fillStyle(0x4A90D9, 0.12);
    g.fillCircle(mc.x, mc.y, mc.radius + 8);
    g.fillStyle(0x4A90D9, 0.2);
    g.fillCircle(mc.x, mc.y, mc.radius);
    g.lineStyle(2, 0x4A90D9, 0.3);
    g.strokeCircle(mc.x, mc.y, mc.radius);

    // Seat markers
    const seatA = this._layout.anchors?.[mc.seat_a];
    const seatB = this._layout.anchors?.[mc.seat_b];
    if (seatA && seatB) {
      g.fillStyle(0x4A90D9, 0.25);
      g.fillCircle(seatA.x, seatA.y, 6);
      g.fillCircle(seatB.x, seatB.y, 6);
    }

    // Subtle pulse
    this.tweens.add({
      targets: g,
      alpha: { from: 0.7, to: 1 },
      duration: 2500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
  }

  /* ================================================================== */
  /*  Title scroll                                                       */
  /* ================================================================== */

  _drawTitleScroll(W) {
    const cx = W / 2;
    const barW = 220;
    const barH = 36;
    const barX = cx - barW / 2;
    const barY = 8;

    const g = this.add.graphics();
    g.setDepth(9999);

    g.fillStyle(0x000000, 0.3);
    g.fillRoundedRect(barX + 2, barY + 2, barW, barH, 6);
    g.fillStyle(0x1B3047, 0.95);
    g.fillRoundedRect(barX, barY, barW, barH, 6);
    g.fillStyle(0x4A90D9, 0.9);
    g.fillRect(barX, barY, 3, barH);
    g.lineStyle(1, 0x0F1F33, 0.6);
    g.strokeRoundedRect(barX, barY, barW, barH, 6);

    const titleText = this.add.text(cx, barY + 13, 'ContextGraph World', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '13px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    titleText.setDepth(9999);

    const subText = this.add.text(cx, barY + 26, 'Lobby', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '9px',
      fontStyle: '400',
      color: '#88b4d6',
    }).setOrigin(0.5, 0.5);
    subText.setDepth(9999);
  }

  /* ================================================================== */
  /*  Doors                                                              */
  /* ================================================================== */

  _buildDoors() {
    const rooms = (this.snapshot && this.snapshot.rooms) ? this.snapshot.rooms : [];
    this._syncDoors(rooms);

    this.events.on('enter-room', (roomId) => {
      this.cameras.main.fadeOut(400, 27, 48, 71);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.socket.joinRoom(roomId);
      });
    });
  }

  _syncDoors(rooms) {
    for (const door of this.doors.values()) {
      door.destroy();
    }
    this.doors.clear();

    const W = this.scale.width;
    const sortedRooms = [...rooms].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    const doorY = 112;
    const spacing = 120;
    const totalWidth = sortedRooms.length > 0 ? sortedRooms.length * spacing : spacing;
    const startX = W / 2 - totalWidth / 2 + spacing / 2;

    sortedRooms.forEach((room, i) => {
      const door = new RoomDoor(this, startX + i * spacing, doorY, room);
      this.doors.set(room.room_id, door);
    });
  }

  /* ================================================================== */
  /*  Agents                                                             */
  /* ================================================================== */

  _spawnAgent(data) {
    if (this.agents.has(data.agent_id)) {
      this.agents.get(data.agent_id).updateFromData(data);
      return;
    }

    const H = this.scale.height;
    const W = this.scale.width;
    const agentData = { ...data };

    // Use anchor positions from layout if available
    if (this._layout && agentData.anchor_id && this._layout.anchors[agentData.anchor_id]) {
      const anchor = this._layout.anchors[agentData.anchor_id];
      agentData.x = anchor.x;
      agentData.y = anchor.y;
    } else {
      // Fallback: spread agents across the visible floor area
      const minY = H * 0.28;
      const maxY = H - 40;
      const minX = 60;
      const maxX = W - 60;

      if (agentData.y < minY || agentData.y > maxY) {
        agentData.y = minY + Math.random() * (maxY - minY);
      }
      if (agentData.x < minX || agentData.x > maxX) {
        agentData.x = minX + Math.random() * (maxX - minX);
      }
    }

    const sprite = new AgentSprite(this, agentData);
    this.agents.set(data.agent_id, sprite);
  }

  _removeAgent(agentId) {
    const sprite = this.agents.get(agentId);
    if (sprite) {
      sprite.destroy();
      this.agents.delete(agentId);
    }
  }

  /* ================================================================== */
  /*  Path resolution                                                    */
  /* ================================================================== */

  _resolvePathWaypoints(fromAnchorId, toAnchorId) {
    if (!this._layout || !this._layout.anchors) return null;

    // Simple client-side Dijkstra on the layout graph
    const anchors = this._layout.anchors;
    const edges = this._layout.edges || [];
    if (!anchors[fromAnchorId] || !anchors[toAnchorId]) return null;

    // Build adjacency
    const adj = {};
    for (const id in anchors) { adj[id] = []; }
    for (const [a, b] of edges) {
      if (adj[a]) adj[a].push(b);
      if (adj[b]) adj[b].push(a);
    }

    // Dijkstra
    const dist = {};
    const prev = {};
    for (const id in anchors) { dist[id] = Infinity; prev[id] = null; }
    dist[fromAnchorId] = 0;
    const visited = new Set();

    while (true) {
      let u = null;
      let minD = Infinity;
      for (const id in dist) {
        if (!visited.has(id) && dist[id] < minD) {
          minD = dist[id];
          u = id;
        }
      }
      if (u === null || u === toAnchorId) break;
      visited.add(u);

      for (const nb of (adj[u] || [])) {
        const au = anchors[u], anb = anchors[nb];
        const w = Math.hypot(au.x - anb.x, au.y - anb.y);
        if (dist[u] + w < dist[nb]) {
          dist[nb] = dist[u] + w;
          prev[nb] = u;
        }
      }
    }

    // Reconstruct
    const path = [];
    let cur = toAnchorId;
    while (cur) {
      path.unshift(anchors[cur]);
      cur = prev[cur];
    }

    // Skip first point (current position)
    return path.length > 1 ? path.slice(1) : path;
  }

  /* ================================================================== */
  /*  WebSocket events                                                   */
  /* ================================================================== */

  _bindEvents() {
    this.events.on('ws:room_snapshot', (msg) => {
      console.log('[LobbyScene] room_snapshot →', msg.room || msg.room_id, 'theme:', msg.theme_key);
      this.scene.start('RoomScene', {
        socket: this.socket,
        snapshot: msg,
      });
    });

    this.events.on('ws:agent_state', (msg) => {
      const agentData = msg.data?.agent || msg.data;
      if (!agentData) return;
      const id = msg.agent_id || agentData.agent_id;
      if (agentData.room === 'lobby') {
        this._spawnAgent({ ...agentData, agent_id: id });
      } else {
        this._removeAgent(id);
      }
    });

    this.events.on('ws:agent_spawn', (msg) => {
      const agentData = msg.data?.agent || msg.data;
      if (!agentData) return;
      if (agentData.room === 'lobby') {
        this._spawnAgent({ ...agentData, agent_id: msg.agent_id || agentData.agent_id });
      }
    });

    this.events.on('ws:agent_despawn', (msg) => {
      this._removeAgent(msg.agent_id);
    });

    this.events.on('ws:agent_upgrade', (msg) => {
      const sprite = this.agents.get(msg.agent_id);
      const newRank = msg.data?.new_rank || msg.data?.rank;
      if (sprite && newRank && typeof sprite.playUpgradeBurst === 'function') {
        sprite.playUpgradeBurst(newRank);
      }
    });

    this.events.on('ws:handoff_orb', (msg) => {
      const from = this.agents.get(msg.data?.from_agent);
      const to = this.agents.get(msg.data?.to_agent);
      if (from && to && typeof from.playHandoffOrb === 'function') {
        from.playHandoffOrb(to);
      }
    });

    this.events.on('ws:agent_move', (msg) => {
      const id = msg.agent_id;
      const data = msg.data || {};
      const sprite = this.agents.get(id);
      if (sprite && data.x !== undefined && data.y !== undefined) {
        sprite.moveTo(data.x, data.y);
      }
    });

    // New: agent_path — walk along waypoints
    this.events.on('ws:agent_path', (msg) => {
      const id = msg.agent_id;
      const data = msg.data || {};
      const sprite = this.agents.get(id);
      if (!sprite) return;

      const waypoints = this._resolvePathWaypoints(data.from_anchor_id, data.to_anchor_id);
      if (waypoints && waypoints.length > 0) {
        sprite.walkPath(waypoints, data.speed || 1.0);
      }
    });

    this.events.on('ws:meeting_started', () => {
      // Clean Habbo — no burst effect
    });

    this.events.on('ws:meeting_updated', (msg) => {
      const data = msg.data || {};
      if (data.phase === 'bubble_a' && data.bubble_a) {
        const sprite = this.agents.get(data.agent_a);
        if (sprite) sprite.showBubble(data.bubble_a);
      }
      if (data.phase === 'bubble_b' && data.bubble_b) {
        const sprite = this.agents.get(data.agent_b);
        if (sprite) sprite.showBubble(data.bubble_b);
      }
    });

    this.events.on('ws:meeting_ended', () => {
      // Cleanup handled by agent_path (return to home) and agent_state
    });

    this.events.on('ws:world_snapshot', (msg) => {
      this.snapshot = msg;
      this._layout = msg.layout || this._layout;
      this._syncDoors(msg.rooms || []);
      // Update atlas with fresh room list
      if (this._atlas) {
        this._atlas.updateRooms(msg.rooms || []);
      }
      const lobbyAgents = new Set();
      for (const agentData of (msg.agents || [])) {
        if (agentData.room === 'lobby') {
          lobbyAgents.add(agentData.agent_id);
          this._spawnAgent(agentData);
        }
      }
      for (const [id] of this.agents) {
        if (!lobbyAgents.has(id)) {
          this._removeAgent(id);
        }
      }
    });
  }
}
