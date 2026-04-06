/**
 * LobbyScene — The cozy hub where all agents idle.
 * Shows room doors at the top and agents scattered below.
 */
import AgentSprite from '../sprites/AgentSprite.js';
import RoomDoor from '../ui/RoomDoor.js';

export default class LobbyScene extends Phaser.Scene {
  constructor() {
    super({ key: 'LobbyScene' });
    /** @type {Map<string, AgentSprite>} */
    this.agents = new Map();
    /** @type {Map<string, RoomDoor>} */
    this.doors = new Map();
  }

  init(data) {
    this.socket = data.socket;
    this.snapshot = data.snapshot;
  }

  create() {
    // Point the socket at this scene so ws: events arrive here
    this.socket.setScene(this);

    const W = this.scale.width;
    const H = this.scale.height;

    // --- Background gradient ---
    this._drawBackground(W, H);

    // --- Floor area ---
    this._drawFloor(W, H);

    // --- Decorative border ---
    const border = this.add.graphics();
    border.lineStyle(2, 0x6366f1, 0.15);
    border.strokeRoundedRect(16, 16, W - 32, H - 32, 16);
    border.lineStyle(1, 0x6366f1, 0.08);
    border.strokeRoundedRect(20, 20, W - 40, H - 40, 14);

    // --- Title ---
    this.add.text(W / 2, 40, 'ContextGraph World', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '32px',
      fontStyle: '800',
      color: '#f1f5f9',
    }).setOrigin(0.5, 0);

    this.add.text(W / 2, 76, 'Lobby', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '15px',
      fontStyle: '600',
      color: '#64748b',
    }).setOrigin(0.5, 0);

    // --- Decorative dots on each side of title ---
    const dots = this.add.graphics();
    dots.fillStyle(0x6366f1, 0.3);
    for (let i = 0; i < 5; i++) {
      dots.fillCircle(W / 2 - 160 + i * 12, 56, 2);
      dots.fillCircle(W / 2 + 120 + i * 12, 56, 2);
    }

    // --- Separator line ---
    const sep = this.add.graphics();
    sep.lineStyle(1, 0x334155, 0.6);
    sep.lineBetween(60, 100, W - 60, 100);

    // --- Room doors ---
    this._buildDoors();

    // --- Separator between doors and idle area ---
    const sep2 = this.add.graphics();
    sep2.lineStyle(1, 0x334155, 0.4);
    sep2.lineBetween(60, 230, W - 60, 230);

    this.add.text(W / 2, 240, 'Agents', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '13px',
      fontStyle: '600',
      color: '#475569',
    }).setOrigin(0.5, 0);

    // --- Agents from snapshot ---
    if (this.snapshot && this.snapshot.agents) {
      for (const agentData of this.snapshot.agents) {
        if (agentData.room === 'lobby') {
          this._spawnAgent(agentData);
        }
      }
    }

    // --- WebSocket listeners ---
    this._bindEvents();
  }

  /* ================================================================== */
  /*  Background rendering                                               */
  /* ================================================================== */

  _drawBackground(W, H) {
    // Dark gradient - top to bottom
    const bg = this.add.graphics();
    const steps = 20;
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      const r = Phaser.Math.Interpolation.Linear([0x1e, 0x0f], t);
      const g = Phaser.Math.Interpolation.Linear([0x29, 0x17], t);
      const b = Phaser.Math.Interpolation.Linear([0x3b, 0x2a], t);
      const color = (Math.floor(r) << 16) | (Math.floor(g) << 8) | Math.floor(b);
      bg.fillStyle(color, 1);
      bg.fillRect(0, (H / steps) * i, W, H / steps + 1);
    }

    // Subtle star-like sparkles
    const sparkles = this.add.graphics();
    sparkles.fillStyle(0xffffff, 0.04);
    for (let i = 0; i < 40; i++) {
      const sx = Phaser.Math.Between(20, W - 20);
      const sy = Phaser.Math.Between(20, H - 20);
      sparkles.fillCircle(sx, sy, Phaser.Math.Between(1, 2));
    }
  }

  _drawFloor(W, H) {
    const floorTop = 260;
    const floor = this.add.graphics();

    // Main floor area
    floor.fillStyle(0x1a2332, 1);
    floor.fillRoundedRect(40, floorTop, W - 80, H - floorTop - 30, 12);

    // Tile pattern
    const tileSize = 40;
    const startX = 44;
    const startY = floorTop + 4;
    const cols = Math.floor((W - 88) / tileSize);
    const rows = Math.floor((H - floorTop - 34) / tileSize);

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const isLight = (row + col) % 2 === 0;
        floor.fillStyle(isLight ? 0x1e2d3d : 0x1a2838, 1);
        const tx = startX + col * tileSize;
        const ty = startY + row * tileSize;
        const tw = Math.min(tileSize, (W - 84) - col * tileSize);
        const th = Math.min(tileSize, (H - floorTop - 30) - row * tileSize);
        if (tw > 0 && th > 0) {
          floor.fillRect(tx, ty, tw, th);
        }
      }
    }

    // Floor border
    floor.lineStyle(1, 0x334155, 0.4);
    floor.strokeRoundedRect(40, floorTop, W - 80, H - floorTop - 30, 12);
  }

  /* ================================================================== */
  /*  Doors                                                              */
  /* ================================================================== */

  _buildDoors() {
    const W = this.scale.width;
    const rooms = (this.snapshot && this.snapshot.rooms) ? this.snapshot.rooms : [];

    // Always show at least some doors
    const doorY = 168;
    const spacing = 130;
    const totalWidth = rooms.length > 0 ? rooms.length * spacing : spacing;
    const startX = W / 2 - totalWidth / 2 + spacing / 2;

    rooms.forEach((room, i) => {
      const door = new RoomDoor(this, startX + i * spacing, doorY, room);
      this.doors.set(room.room_id, door);
    });

    // Enter-room handler
    this.events.on('enter-room', (roomId) => {
      this.socket.joinRoom(roomId);
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

    // Clamp to idle area
    const agentData = { ...data };
    if (agentData.y < 280) agentData.y = 280 + Math.random() * 300;
    if (agentData.x < 80) agentData.x = 80 + Math.random() * 860;
    if (agentData.x > 940) agentData.x = 940;
    if (agentData.y > 700) agentData.y = 700;

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
  /*  WebSocket events                                                   */
  /* ================================================================== */

  _bindEvents() {
    // Room snapshot → transition to room scene
    this.events.on('ws:room_snapshot', (msg) => {
      this.scene.start('RoomScene', {
        socket: this.socket,
        snapshot: msg,
      });
    });

    // Agent state updates
    this.events.on('ws:agent_state', (msg) => {
      const agentData = msg.data?.agent || msg.data;
      if (!agentData) return;
      const id = msg.agent_id || agentData.agent_id;

      if (agentData.room === 'lobby') {
        this._spawnAgent({ ...agentData, agent_id: id });
      } else {
        this._removeAgent(id);
      }

      // Update door counts from overall state
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

    this.events.on('ws:agent_move', (msg) => {
      const id = msg.agent_id;
      const data = msg.data || {};
      const sprite = this.agents.get(id);
      if (sprite && data.x !== undefined && data.y !== undefined) {
        sprite.moveTo(data.x, data.y);
      }
    });

    this.events.on('ws:world_snapshot', (msg) => {
      // Full refresh
      this.snapshot = msg;

      // Update doors
      for (const room of (msg.rooms || [])) {
        const door = this.doors.get(room.room_id);
        if (door) {
          door.setAgentCount(room.agent_count);
        }
      }

      // Update agents
      const lobbyAgents = new Set();
      for (const agentData of (msg.agents || [])) {
        if (agentData.room === 'lobby') {
          lobbyAgents.add(agentData.agent_id);
          this._spawnAgent(agentData);
        }
      }

      // Remove agents no longer in lobby
      for (const [id] of this.agents) {
        if (!lobbyAgents.has(id)) {
          this._removeAgent(id);
        }
      }
    });
  }
}
