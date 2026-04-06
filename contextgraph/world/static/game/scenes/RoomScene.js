/**
 * RoomScene — A project room with 4 themed zones.
 * Agents appear in their assigned zones and can interact.
 */
import AgentSprite from '../sprites/AgentSprite.js';

const ZONES = {
  code_desk: {
    label: 'Code Desk',
    color: 0x92400e,
    bgColor: 0x1c1a10,
    borderColor: 0xf59e0b,
    icon: '{ }',
    x: 0, y: 0, // set dynamically
  },
  memory_library: {
    label: 'Memory Library',
    color: 0x581c87,
    bgColor: 0x1a1024,
    borderColor: 0xa78bfa,
    icon: '[ ]',
    x: 0, y: 0,
  },
  review_station: {
    label: 'Review Station',
    color: 0x1e3a5f,
    bgColor: 0x0f1a2e,
    borderColor: 0x3b82f6,
    icon: '< >',
    x: 0, y: 0,
  },
  debug_lab: {
    label: 'Debug Lab',
    color: 0x7f1d1d,
    bgColor: 0x1c0f0f,
    borderColor: 0xef4444,
    icon: '! !',
    x: 0, y: 0,
  },
};

export default class RoomScene extends Phaser.Scene {
  constructor() {
    super({ key: 'RoomScene' });
    /** @type {Map<string, AgentSprite>} */
    this.agents = new Map();
  }

  init(data) {
    this.socket = data.socket;
    this.snapshot = data.snapshot;
    this.roomId = data.snapshot?.room || 'unknown';
  }

  create() {
    // Point the socket at this scene so ws: events arrive here
    this.socket.setScene(this);

    const W = this.scale.width;
    const H = this.scale.height;

    // --- Background ---
    this._drawBackground(W, H);

    // --- Room title ---
    const roomTitle = this.roomId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    this.add.text(W / 2, 28, roomTitle, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '26px',
      fontStyle: '800',
      color: '#f1f5f9',
    }).setOrigin(0.5, 0);

    // --- Back button ---
    const backBtn = this.add.container(60, 32);

    const backBg = this.add.graphics();
    backBg.fillStyle(0x334155, 0.6);
    backBg.fillRoundedRect(-40, -12, 80, 28, 14);
    backBg.lineStyle(1, 0x475569, 0.5);
    backBg.strokeRoundedRect(-40, -12, 80, 28, 14);
    backBtn.add(backBg);

    const backText = this.add.text(0, 0, '\u2190 Lobby', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '13px',
      fontStyle: '700',
      color: '#94a3b8',
    }).setOrigin(0.5, 0.5);
    backBtn.add(backText);

    backBtn.setSize(80, 28);
    backBtn.setInteractive({ useHandCursor: true });

    backBtn.on('pointerover', () => {
      backBg.clear();
      backBg.fillStyle(0x475569, 0.8);
      backBg.fillRoundedRect(-40, -12, 80, 28, 14);
      backBg.lineStyle(1, 0x6366f1, 0.5);
      backBg.strokeRoundedRect(-40, -12, 80, 28, 14);
      backText.setColor('#e2e8f0');
    });

    backBtn.on('pointerout', () => {
      backBg.clear();
      backBg.fillStyle(0x334155, 0.6);
      backBg.fillRoundedRect(-40, -12, 80, 28, 14);
      backBg.lineStyle(1, 0x475569, 0.5);
      backBg.strokeRoundedRect(-40, -12, 80, 28, 14);
      backText.setColor('#94a3b8');
    });

    backBtn.on('pointerdown', () => {
      this.socket.leaveRoom();
    });

    // --- Zones ---
    this._drawZones(W, H);

    // --- Agents from snapshot ---
    if (this.snapshot && this.snapshot.agents) {
      for (const agentData of this.snapshot.agents) {
        this._spawnAgent(agentData);
      }
    }

    // --- Events ---
    this._bindEvents();
  }

  /* ================================================================== */
  /*  Background                                                         */
  /* ================================================================== */

  _drawBackground(W, H) {
    const bg = this.add.graphics();
    const steps = 16;
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      const r = Phaser.Math.Interpolation.Linear([0x1e, 0x0f], t);
      const g = Phaser.Math.Interpolation.Linear([0x29, 0x17], t);
      const b = Phaser.Math.Interpolation.Linear([0x3b, 0x2a], t);
      const color = (Math.floor(r) << 16) | (Math.floor(g) << 8) | Math.floor(b);
      bg.fillStyle(color, 1);
      bg.fillRect(0, (H / steps) * i, W, H / steps + 1);
    }

    // Subtle decorative particles
    const particles = this.add.graphics();
    particles.fillStyle(0xffffff, 0.03);
    for (let i = 0; i < 30; i++) {
      particles.fillCircle(
        Phaser.Math.Between(10, W - 10),
        Phaser.Math.Between(10, H - 10),
        Phaser.Math.Between(1, 2)
      );
    }
  }

  /* ================================================================== */
  /*  Zones                                                              */
  /* ================================================================== */

  _drawZones(W, H) {
    const pad = 30;
    const gap = 16;
    const topY = 68;
    const zoneW = (W - pad * 2 - gap) / 2;
    const zoneH = (H - topY - pad - gap) / 2;

    const layout = [
      { key: 'code_desk',       col: 0, row: 0 },
      { key: 'memory_library',  col: 1, row: 0 },
      { key: 'review_station',  col: 0, row: 1 },
      { key: 'debug_lab',       col: 1, row: 1 },
    ];

    this._zoneBounds = {};

    for (const { key, col, row } of layout) {
      const zx = pad + col * (zoneW + gap);
      const zy = topY + row * (zoneH + gap);
      const zone = ZONES[key];

      // Store bounds for agent positioning
      this._zoneBounds[key] = { x: zx, y: zy, w: zoneW, h: zoneH };

      const g = this.add.graphics();

      // Zone background fill
      g.fillStyle(zone.bgColor, 1);
      g.fillRoundedRect(zx, zy, zoneW, zoneH, 12);

      // Subtle inner gradient overlay
      g.fillStyle(zone.color, 0.08);
      g.fillRoundedRect(zx, zy, zoneW, zoneH, 12);

      // Border
      g.lineStyle(1.5, zone.borderColor, 0.25);
      g.strokeRoundedRect(zx, zy, zoneW, zoneH, 12);

      // Corner accent
      g.fillStyle(zone.borderColor, 0.08);
      g.fillRoundedRect(zx, zy, 80, 32, { tl: 12, tr: 0, bl: 0, br: 12 });

      // Zone icon
      this.add.text(zx + 12, zy + 8, zone.icon, {
        fontFamily: 'monospace',
        fontSize: '13px',
        fontStyle: '700',
        color: Phaser.Display.Color.IntegerToColor(zone.borderColor).rgba,
      }).setAlpha(0.5);

      // Zone label
      this.add.text(zx + 32, zy + 8, zone.label, {
        fontFamily: 'Nunito, sans-serif',
        fontSize: '13px',
        fontStyle: '700',
        color: Phaser.Display.Color.IntegerToColor(zone.borderColor).rgba,
      }).setAlpha(0.7);
    }
  }

  /* ================================================================== */
  /*  Agents                                                             */
  /* ================================================================== */

  _spawnAgent(data) {
    if (this.agents.has(data.agent_id)) {
      this.agents.get(data.agent_id).updateFromData(data);
      return;
    }

    // Position within zone bounds
    const agentData = { ...data };
    if (data.zone && this._zoneBounds && this._zoneBounds[data.zone]) {
      const zb = this._zoneBounds[data.zone];
      // Clamp to zone area
      agentData.x = Phaser.Math.Clamp(
        agentData.x || zb.x + zb.w / 2,
        zb.x + 40, zb.x + zb.w - 40
      );
      agentData.y = Phaser.Math.Clamp(
        agentData.y || zb.y + zb.h / 2,
        zb.y + 50, zb.y + zb.h - 40
      );
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
  /*  WebSocket events                                                   */
  /* ================================================================== */

  _bindEvents() {
    // Return to lobby on world_snapshot (after leaving room)
    this.events.on('ws:world_snapshot', (msg) => {
      this.scene.start('LobbyScene', {
        socket: this.socket,
        snapshot: msg,
      });
    });

    this.events.on('ws:room_snapshot', (msg) => {
      // Full refresh of this room
      if (msg.room === this.roomId) {
        const currentIds = new Set();
        for (const agentData of (msg.agents || [])) {
          currentIds.add(agentData.agent_id);
          this._spawnAgent(agentData);
        }
        for (const [id] of this.agents) {
          if (!currentIds.has(id)) {
            this._removeAgent(id);
          }
        }
      }
    });

    this.events.on('ws:agent_state', (msg) => {
      const agentData = msg.data?.agent || msg.data;
      if (!agentData) return;
      const id = msg.agent_id || agentData.agent_id;

      if (agentData.room === this.roomId) {
        this._spawnAgent({ ...agentData, agent_id: id });
      } else {
        this._removeAgent(id);
      }
    });

    this.events.on('ws:agent_spawn', (msg) => {
      const agentData = msg.data?.agent || msg.data;
      if (agentData && agentData.room === this.roomId) {
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
  }
}
