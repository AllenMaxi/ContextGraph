/**
 * RoomScene — A magical project room staged as one coherent academy chamber.
 * The same 4 logical zones still exist for agent behavior, but the room reads
 * as a single themed social space instead of a strict 2x2 grid.
 */
import AgentSprite from '../sprites/AgentSprite.js';
import MagicAtlas from '../ui/MagicAtlas.js';
import { getThemeSpec, roomTitleFromId } from '../ui/roomThemes.js';

const ZONES = {
  code_desk: {
    label: 'Code Workshop',
    accentColor: 0x4A90D9,
    borderColor: 0x2C6EA0,
    icon: '<>',
  },
  memory_library: {
    label: 'Memory Archive',
    accentColor: 0x8B9DC3,
    borderColor: 0x5F7296,
    icon: '[]',
  },
  review_station: {
    label: 'Review Station',
    accentColor: 0x7EC8A4,
    borderColor: 0x519677,
    icon: '~',
  },
  debug_lab: {
    label: 'Debug Lab',
    accentColor: 0xE9AD58,
    borderColor: 0xB5832E,
    icon: '*',
  },
};

const THEME_ROOM_LAYOUTS = {
  library: {
    stations: {
      memory_library: { x: 88, y: 120, w: 308, h: 250 },
      code_desk: { x: 624, y: 156, w: 248, h: 142 },
      review_station: { x: 622, y: 326, w: 238, h: 138 },
      debug_lab: { x: 164, y: 332, w: 246, h: 138 },
    },
  },
  observatory: {
    stations: {
      review_station: { x: 390, y: 122, w: 252, h: 150 },
      memory_library: { x: 92, y: 310, w: 250, h: 154 },
      code_desk: { x: 694, y: 308, w: 244, h: 150 },
      debug_lab: { x: 116, y: 164, w: 232, h: 122 },
    },
  },
  alchemy: {
    stations: {
      debug_lab: { x: 390, y: 142, w: 260, h: 154 },
      memory_library: { x: 92, y: 316, w: 248, h: 146 },
      code_desk: { x: 686, y: 318, w: 244, h: 144 },
      review_station: { x: 696, y: 156, w: 220, h: 128 },
    },
  },
  workshop: {
    stations: {
      code_desk: { x: 390, y: 138, w: 260, h: 150 },
      memory_library: { x: 92, y: 314, w: 250, h: 148 },
      review_station: { x: 694, y: 154, w: 224, h: 126 },
      debug_lab: { x: 690, y: 330, w: 236, h: 136 },
    },
  },
};

export default class RoomScene extends Phaser.Scene {
  constructor() {
    super({ key: 'RoomScene' });
    /** @type {Map<string, AgentSprite>} */
    this.agents = new Map();
    this._layout = null;
    this._meetings = [];
  }

  init(data) {
    this.socket = data.socket;
    this.snapshot = data.snapshot;
    this.roomId = data.snapshot?.room || data.snapshot?.room_id || 'unknown';
    this.themeKey = data.snapshot?.theme_key || null;
    this._layout = data.snapshot?.layout || null;
    this._meetings = data.snapshot?.meetings || [];
  }

  create() {
    this.socket.setScene(this);

    const W = this.scale.width;
    const H = this.scale.height;
    this._theme = getThemeSpec(this.roomId, this.themeKey);

    this.cameras.main.fadeIn(400, 27, 48, 71);

    const safe = (label, fn) => {
      try { fn(); } catch (err) {
        console.error('[RoomScene] ' + label + ' failed:', err);
      }
    };

    // --- Themed background image (falls back to generic room_bg) ---
    safe('bg', () => {
      const themedKey = `room_bg_${this._theme?.key || 'library'}`;
      const bgKey = this.textures.exists(themedKey) ? themedKey : 'room_bg';
      const bgImage = this.add.image(W / 2, H / 2, bgKey);
      bgImage.setDisplaySize(W, H);
    });

    // Overlay removed — baked bg + bright walls carry the look

    // --- Zone props (builds _zoneBounds — required for agents) ---
    safe('zoneProps', () => this._drawZoneProps(W, H));

    // --- Meeting circle ---
    safe('meetingCircle', () => this._drawMeetingCircle());

    // --- Room title banner ---
    safe('titleBanner', () => this._drawTitleBanner(W));

    // --- Back button ---
    safe('backButton', () => this._drawBackButton());

    // --- Zone labels ---
    safe('zones', () => this._drawZones(W, H));

    // --- Agents from snapshot ---
    safe('agents', () => {
      if (this.snapshot && this.snapshot.agents) {
        for (const agentData of this.snapshot.agents) {
          try { this._spawnAgent(agentData); }
          catch (e) { console.error('[RoomScene] spawn failed for', agentData?.agent_id, e); }
        }
      }
    });

    // --- Magic Atlas ---
    const rooms = (this.snapshot && this.snapshot.rooms) ? this.snapshot.rooms : [];
    safe('atlas', () => {
      this._atlas = new MagicAtlas(this, this.socket, this.roomId, rooms);
    });
    this.events.once('shutdown', () => {
      // Clean up all agents to prevent dangling tween/animation references
      for (const agent of this.agents.values()) {
        agent.destroy();
      }
      this.agents.clear();

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

    // --- Events ---
    this._bindEvents();
  }

  /* ================================================================== */
  /*  Ambient particles                                                  */
  /* ================================================================== */

  _createAmbientParticles(W, H) {
    // Removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Torches                                                            */
  /* ================================================================== */

  _drawTorches(W, H) {
    // Removed
  }

  /* ================================================================== */
  /*  Fog layer                                                          */
  /* ================================================================== */

  _drawFogLayer(W, H) {
    // Removed
  }

  /* ================================================================== */
  /*  Zone props (furniture)                                             */
  /* ================================================================== */

  _drawZoneProps(W, H) {
    const themed = this._getThemeLayout();
    this._zoneBounds = {};
    for (const [zoneKey, bounds] of Object.entries(themed.stations)) {
      this._zoneBounds[zoneKey] = bounds;
    }

    this._drawThemeShell(W, H, themed);

    const stations = themed.stations;
    this._drawAncientLibrary(stations.memory_library.x, stations.memory_library.y, stations.memory_library.w, stations.memory_library.h);
    this._drawSpellWorkshop(stations.code_desk.x, stations.code_desk.y, stations.code_desk.w, stations.code_desk.h);
    this._drawDivinationChamber(stations.review_station.x, stations.review_station.y, stations.review_station.w, stations.review_station.h);
    this._drawPotionsLab(stations.debug_lab.x, stations.debug_lab.y, stations.debug_lab.w, stations.debug_lab.h);
  }

  _getThemeLayout() {
    return THEME_ROOM_LAYOUTS[this._theme?.key] || THEME_ROOM_LAYOUTS.library;
  }

  _drawThemeShell(W, H, themed) {
    // No-op. Baked texture carries the room look; vignette darkened bright walls.
  }

  /* ── Code Workshop (code_desk zone) ── */
  _drawSpellWorkshop(zx, zy, zoneW, zoneH) {
    const g = this.add.graphics();
    g.setDepth(2);
    const OUTLINE = 0x1A1A1A;
    // Standing desk
    const dx = zx + zoneW / 2 - 50, dy = zy + zoneH - 40;
    g.fillStyle(0x8C5A33, 1);
    g.fillRect(dx, dy, 100, 8);
    g.fillStyle(0x5A3418, 1);
    g.fillRect(dx + 6, dy + 8, 6, 22);
    g.fillRect(dx + 88, dy + 8, 6, 22);
    g.lineStyle(1, OUTLINE, 0.6);
    g.strokeRect(dx, dy, 100, 8);
    // Dual monitors
    g.fillStyle(0x1A1A1A, 1);
    g.fillRect(dx + 8, dy - 32, 38, 28);
    g.fillRect(dx + 54, dy - 32, 38, 28);
    g.strokeRect(dx + 8, dy - 32, 38, 28);
    g.strokeRect(dx + 54, dy - 32, 38, 28);
    // Blue screens
    g.fillStyle(0x4A90D9, 1);
    g.fillRect(dx + 11, dy - 29, 32, 22);
    g.fillRect(dx + 57, dy - 29, 32, 22);
    // Code lines
    g.fillStyle(0xFFFFFF, 0.7);
    for (let i = 0; i < 4; i++) {
      g.fillRect(dx + 13, dy - 27 + i * 5, 10 + (i * 3) % 18, 1);
      g.fillRect(dx + 59, dy - 27 + i * 5, 14 + (i * 5) % 14, 1);
    }
    // Keyboard
    g.fillStyle(0x1A1A1A, 1);
    g.fillRect(dx + 28, dy + 2, 44, 4);
    // Coffee mug
    g.fillStyle(0xC94F4F, 1);
    g.fillRect(dx + 80, dy - 6, 8, 8);
    g.strokeRect(dx + 80, dy - 6, 8, 8);
  }

  /* ── Memory Archive (memory_library zone) ── */
  _drawAncientLibrary(zx, zy, zoneW, zoneH) {
    const g = this.add.graphics();
    g.setDepth(2);
    const OUTLINE = 0x1A1A1A;
    // Long reading table
    const tx = zx + 10, ty = zy + zoneH - 48;
    g.fillStyle(0x8C5A33, 1);
    g.fillRect(tx, ty, 140, 10);
    g.fillStyle(0x5A3418, 1);
    g.fillRect(tx + 4, ty + 10, 6, 24);
    g.fillRect(tx + 130, ty + 10, 6, 24);
    g.lineStyle(1, OUTLINE, 0.6);
    g.strokeRect(tx, ty, 140, 10);
    // 4 chairs
    g.fillStyle(0x754726, 1);
    const chairY = ty + 16;
    for (const cx of [tx + 18, tx + 52, tx + 86, tx + 118]) {
      g.fillRect(cx, chairY, 14, 14);
      g.fillRect(cx, chairY - 12, 14, 4);
      g.strokeRect(cx, chairY, 14, 14);
    }
    // Open book on table
    g.fillStyle(0xF5E6C2, 1);
    g.fillRect(tx + 60, ty - 4, 20, 6);
    g.strokeRect(tx + 60, ty - 4, 20, 6);
    g.lineStyle(1, 0x5A3418, 0.7);
    g.lineBetween(tx + 70, ty - 4, tx + 70, ty + 2);
    g.lineBetween(tx + 63, ty - 1, tx + 68, ty - 1);
    g.lineBetween(tx + 72, ty - 1, tx + 77, ty - 1);
  }

  /* ── Analysis Room (review_station zone) ── */
  _drawDivinationChamber(zx, zy, zoneW, zoneH) {
    const g = this.add.graphics();
    g.setDepth(2);
    const OUTLINE = 0x1A1A1A;
    // Star-chart round rug
    const cx = zx + zoneW / 2, cy = zy + zoneH - 30;
    g.fillStyle(0x2E3A60, 1);
    g.fillCircle(cx, cy, 42);
    g.lineStyle(1, OUTLINE, 0.5);
    g.strokeCircle(cx, cy, 42);
    // Compass rose
    g.lineStyle(1, 0xFFE8A8, 0.9);
    g.lineBetween(cx - 34, cy, cx + 34, cy);
    g.lineBetween(cx, cy - 34, cx, cy + 34);
    g.fillStyle(0xFFE8A8, 0.9);
    g.fillTriangle(cx, cy - 34, cx - 4, cy - 24, cx + 4, cy - 24);
    g.fillTriangle(cx, cy + 34, cx - 4, cy + 24, cx + 4, cy + 24);
    g.fillTriangle(cx - 34, cy, cx - 24, cy - 4, cx - 24, cy + 4);
    g.fillTriangle(cx + 34, cy, cx + 24, cy - 4, cx + 24, cy + 4);
    g.fillStyle(0xC9A34E, 1);
    g.fillCircle(cx, cy, 4);
    // Small telescope on tripod
    const tx = zx + 20, ty = zy + zoneH - 50;
    g.fillStyle(0xC9A34E, 1);
    g.fillRect(tx, ty, 10, 34);
    g.strokeRect(tx, ty, 10, 34);
    g.fillStyle(0x8A6A2E, 1);
    g.fillRect(tx - 2, ty - 4, 14, 6);
    g.lineStyle(2, 0x1A1A1A, 1);
    g.lineBetween(tx, ty + 34, tx - 6, ty + 48);
    g.lineBetween(tx + 5, ty + 34, tx + 5, ty + 48);
    g.lineBetween(tx + 10, ty + 34, tx + 16, ty + 48);
  }

  /* ── Debug Lab (debug_lab zone) ── */
  _drawPotionsLab(zx, zy, zoneW, zoneH) {
    const g = this.add.graphics();
    g.setDepth(2);
    const OUTLINE = 0x1A1A1A;
    // Lab bench
    const bx = zx + 10, by = zy + zoneH - 44;
    g.fillStyle(0xE8E8E8, 1);
    g.fillRect(bx, by, 160, 10);
    g.fillStyle(0xBFC4CC, 1);
    g.fillRect(bx + 4, by + 10, 6, 22);
    g.fillRect(bx + 150, by + 10, 6, 22);
    g.lineStyle(1, OUTLINE, 0.6);
    g.strokeRect(bx, by, 160, 10);
    // 2 PCs with green screens
    for (const px of [bx + 24, bx + 104]) {
      g.fillStyle(0x1A1A1A, 1);
      g.fillRect(px, by - 26, 32, 22);
      g.strokeRect(px, by - 26, 32, 22);
      g.fillStyle(0x0D2818, 1);
      g.fillRect(px + 3, by - 23, 26, 16);
      g.fillStyle(0x34D399, 0.9);
      g.fillRect(px + 5, by - 21, 18, 1);
      g.fillRect(px + 5, by - 18, 12, 1);
      g.fillRect(px + 5, by - 15, 20, 1);
      g.fillRect(px + 5, by - 12, 14, 1);
      g.fillRect(px + 5, by - 9, 16, 1);
    }
    // Wheeled office chair
    const chX = bx + 70, chY = by + 18;
    g.fillStyle(0x333333, 1);
    g.fillRect(chX, chY, 20, 14);
    g.fillRect(chX + 4, chY - 14, 12, 14);
    g.strokeRect(chX, chY, 20, 14);
    g.strokeRect(chX + 4, chY - 14, 12, 14);
    g.fillStyle(0x1A1A1A, 1);
    g.fillCircle(chX + 4, chY + 18, 3);
    g.fillCircle(chX + 16, chY + 18, 3);
  }

  /* ================================================================== */
  /*  Zone glow pools                                                    */
  /* ================================================================== */

  _drawZoneGlowPools(W, H) {
    // Removed
  }

  /* ================================================================== */
  /*  Meeting circle                                                     */
  /* ================================================================== */

  _drawMeetingCircle() {
    if (!this._layout || !this._layout.meeting_circle) return;
    const mc = this._layout.meeting_circle;
    const accent = this._theme?.accent || 0x4A90D9;

    const g = this.add.graphics();
    g.setDepth(2);

    g.fillStyle(accent, 0.12);
    g.fillCircle(mc.x, mc.y, mc.radius + 8);
    g.fillStyle(accent, 0.2);
    g.fillCircle(mc.x, mc.y, mc.radius);
    g.lineStyle(2, accent, 0.3);
    g.strokeCircle(mc.x, mc.y, mc.radius);

    this.tweens.add({
      targets: g,
      alpha: { from: 0.7, to: 1 },
      duration: 2500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });

    this._meetingCircleGfx = g;
  }

  /* ================================================================== */
  /*  Title banner                                                       */
  /* ================================================================== */

  _drawTitleBanner(W) {
    const g = this.add.graphics();
    g.setDepth(9999);
    const roomTitle = roomTitleFromId(this.roomId);
    const themeTitle = this._theme?.label || 'Chamber';
    const cx = W / 2;
    const accent = this._theme?.accent || 0x4A90D9;

    const barW = 250;
    const barH = 40;
    const barX = cx - barW / 2;
    const barY = 8;

    g.fillStyle(0x000000, 0.3);
    g.fillRoundedRect(barX + 2, barY + 2, barW, barH, 6);
    g.fillStyle(0x1B3047, 0.95);
    g.fillRoundedRect(barX, barY, barW, barH, 6);
    g.fillStyle(accent, 0.9);
    g.fillRect(barX, barY, 3, barH);
    g.lineStyle(1, 0x0F1F33, 0.6);
    g.strokeRoundedRect(barX, barY, barW, barH, 6);

    const titleText = this.add.text(cx, barY + 14, roomTitle, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '13px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    titleText.setDepth(9999);

    const subtitleText = this.add.text(cx, barY + 28, themeTitle, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '9px',
      fontStyle: '400',
      color: '#88b4d6',
    }).setOrigin(0.5, 0.5);
    subtitleText.setDepth(9999);
  }

  /* ================================================================== */
  /*  Back button                                                        */
  /* ================================================================== */

  _drawBackButton() {
    const backBtn = this.add.container(56, 24);
    backBtn.setDepth(9999);

    const backBg = this.add.graphics();
    backBg.fillStyle(0x4A90D9, 0.92);
    backBg.fillRoundedRect(-44, -14, 88, 28, 4);
    backBg.lineStyle(1, 0x0F1F33, 0.6);
    backBg.strokeRoundedRect(-44, -14, 88, 28, 4);
    backBtn.add(backBg);

    const backText = this.add.text(0, 0, '\u2190 Lobby', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '11px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    backBtn.add(backText);

    backBtn.setSize(88, 28);
    backBtn.setInteractive({ useHandCursor: true });

    backBtn.on('pointerover', () => {
      backBg.clear();
      backBg.fillStyle(0x5BA0E6, 1);
      backBg.fillRoundedRect(-44, -14, 88, 28, 4);
      backBg.lineStyle(1, 0x0F1F33, 0.6);
      backBg.strokeRoundedRect(-44, -14, 88, 28, 4);
    });

    backBtn.on('pointerout', () => {
      backBg.clear();
      backBg.fillStyle(0x4A90D9, 0.92);
      backBg.fillRoundedRect(-44, -14, 88, 28, 4);
      backBg.lineStyle(1, 0x0F1F33, 0.6);
      backBg.strokeRoundedRect(-44, -14, 88, 28, 4);
    });

    backBtn.on('pointerdown', () => {
      this.cameras.main.fadeOut(400, 27, 48, 71);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.socket.leaveRoom();
      });
    });
  }

  /* ================================================================== */
  /*  Zone labels & boundaries                                           */
  /* ================================================================== */

  _drawZones(W, H) {
    for (const [key, bounds] of Object.entries(this._zoneBounds || {})) {
      const zone = ZONES[key];
      const g = this.add.graphics();
      g.setDepth(4);

      const labelW = 140;
      const labelH = 20;
      const labelX = Phaser.Math.Clamp(bounds.x + 10, 18, W - labelW - 18);
      const labelY = bounds.y < 220 ? bounds.y + 6 : bounds.y + bounds.h - 24;

      g.fillStyle(0x1B3047, 0.9);
      g.fillRoundedRect(labelX, labelY, labelW, labelH, 4);
      g.fillStyle(zone.accentColor, 0.9);
      g.fillRect(labelX, labelY, 3, labelH);
      g.lineStyle(1, 0x0F1F33, 0.5);
      g.strokeRoundedRect(labelX, labelY, labelW, labelH, 4);

      this.add.text(labelX + 12, labelY + 10, zone.icon, {
        fontFamily: 'Nunito, sans-serif',
        fontSize: '10px',
        fontStyle: '700',
        color: '#E9AD58',
      }).setOrigin(0.5, 0.5).setDepth(9999);

      this.add.text(labelX + 24, labelY + 10, zone.label, {
        fontFamily: 'Nunito, sans-serif',
        fontSize: '10px',
        fontStyle: '700',
        color: '#ffffff',
      }).setOrigin(0, 0.5).setDepth(9999);
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

    const agentData = { ...data };

    // Use anchor position from layout if available
    if (this._layout && agentData.anchor_id && this._layout.anchors[agentData.anchor_id]) {
      const anchor = this._layout.anchors[agentData.anchor_id];
      agentData.x = anchor.x;
      agentData.y = anchor.y;
    } else if (data.zone && this._zoneBounds && this._zoneBounds[data.zone]) {
      const zb = this._zoneBounds[data.zone];
      agentData.x = Phaser.Math.Clamp(
        agentData.x || zb.x + zb.w / 2,
        zb.x + 40, zb.x + zb.w - 40
      );
      agentData.y = Phaser.Math.Clamp(
        agentData.y || zb.y + zb.h / 2 + 20,
        zb.y + 60, zb.y + zb.h - 40
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
  /*  Path resolution                                                    */
  /* ================================================================== */

  _resolvePathWaypoints(fromAnchorId, toAnchorId) {
    if (!this._layout || !this._layout.anchors) return null;

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

    return path.length > 1 ? path.slice(1) : path;
  }

  /* ================================================================== */
  /*  Orb exchange effect                                                */
  /* ================================================================== */

  _playOrbExchange(agentA, agentB) {
    const spriteA = this.agents.get(agentA);
    const spriteB = this.agents.get(agentB);
    if (!spriteA || !spriteB) return;

    const startX = spriteA.x;
    const startY = spriteA.y - 20;
    const endX = spriteB.x;
    const endY = spriteB.y - 20;
    const accent = this._theme?.accent || 0x4A90D9;

    const orb = this.add.graphics();
    orb.setDepth(9000);
    orb.fillStyle(accent, 0.85);
    orb.fillCircle(0, 0, 5);
    orb.fillStyle(0xffffff, 0.5);
    orb.fillCircle(0, 0, 2);
    orb.setPosition(startX, startY);

    this.tweens.add({
      targets: orb,
      x: endX,
      y: endY,
      duration: 600,
      ease: 'Sine.easeInOut',
      onComplete: () => {
        orb.destroy();
        const ring = this.add.graphics();
        ring.setDepth(9000);
        ring.lineStyle(2, accent, 0.7);
        ring.strokeCircle(endX, endY, 8);
        this.tweens.add({
          targets: ring,
          alpha: 0,
          scaleX: 2.5,
          scaleY: 2.5,
          duration: 500,
          ease: 'Sine.easeOut',
          onComplete: () => ring.destroy(),
        });
      },
    });
  }

  /* ================================================================== */
  /*  WebSocket events                                                   */
  /* ================================================================== */

  _bindEvents() {
    this.events.on('ws:world_snapshot', (msg) => {
      this.scene.start('LobbyScene', {
        socket: this.socket,
        snapshot: msg,
      });
    });

    this.events.on('ws:room_snapshot', (msg) => {
      if (msg.room === this.roomId || msg.room_id === this.roomId) {
        this._layout = msg.layout || this._layout;
        // Update atlas with fresh room list
        if (this._atlas && msg.rooms) {
          this._atlas.updateRooms(msg.rooms);
        }
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
      if (this._meetingCircleGfx) {
        this.tweens.add({
          targets: this._meetingCircleGfx,
          alpha: { from: 1, to: 0.4 },
          duration: 300,
          yoyo: true,
          repeat: 2,
        });
      }
    });

    this.events.on('ws:meeting_updated', (msg) => {
      const data = msg.data || {};

      if (data.phase === 'facing') {
        // Face agents inward
        const spriteA = this.agents.get(data.agent_a);
        const spriteB = this.agents.get(data.agent_b);
        if (spriteA && spriteA._sprite) spriteA._sprite.setFlipX(false);
        if (spriteB && spriteB._sprite) spriteB._sprite.setFlipX(true);
      }

      if (data.phase === 'bubble_a' && data.bubble_a) {
        const sprite = this.agents.get(data.agent_a);
        if (sprite) sprite.showBubble(data.bubble_a);
      }

      if (data.phase === 'bubble_b' && data.bubble_b) {
        const sprite = this.agents.get(data.agent_b);
        if (sprite) sprite.showBubble(data.bubble_b);
      }

      if (data.phase === 'orb_exchange') {
        this._playOrbExchange(data.agent_a, data.agent_b);
      }
    });

    this.events.on('ws:meeting_ended', () => {
      // Agents return via agent_path events
    });
  }
}
