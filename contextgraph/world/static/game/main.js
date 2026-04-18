/**
 * ContextGraph World — Phaser 3 boot and main config.
 * Magical wizard school theme.
 */
import WorldSocket from './net/WorldSocket.js';
import LobbyScene from './scenes/LobbyScene.js';
import RoomScene from './scenes/RoomScene.js';
import InspectPanel from './ui/InspectPanel.js';

const GOLD = 0xd4a54a;

/* ================================================================== */
/*  Preload Scene — loads assets + generates particle textures         */
/* ================================================================== */

class PreloadScene extends Phaser.Scene {
  constructor() {
    super({ key: 'PreloadScene' });
  }

  preload() {
    const W = this.scale.width;
    const H = this.scale.height;

    // Habbo-style dark blue background
    const bg = this.add.graphics();
    bg.fillStyle(0x1B3047, 1);
    bg.fillRect(0, 0, W, H);

    const barW = 300;
    const barH = 16;
    const barX = W / 2 - barW / 2;
    const barY = H / 2 + 40;

    // Bar outline — blue
    bg.lineStyle(2, 0x4A90D9, 0.6);
    bg.strokeRoundedRect(barX, barY, barW, barH, 4);

    // Progress bar fill
    const progressBar = this.add.graphics();
    this.load.on('progress', (value) => {
      progressBar.clear();
      progressBar.fillStyle(0x4A90D9, 0.9);
      progressBar.fillRoundedRect(barX + 2, barY + 2, (barW - 4) * value, barH - 4, 3);
    });

    this.add.text(W / 2, H / 2 - 10, 'ContextGraph World', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '28px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);

    this.add.text(W / 2, H / 2 + 20, 'Loading...', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '14px',
      fontStyle: '400',
      color: '#88b4d6',
    }).setOrigin(0.5, 0.5);

    // Load all background images
    this.load.image('boot_bg', '/world/static/game/assets/boot_bg.jpg');
    this.load.image('lobby_bg', '/world/static/game/assets/lobby_bg.jpg');
    this.load.image('room_bg', '/world/static/game/assets/room_bg.jpg');

    // Load wizard sprite frames (3 types × 14 frames each)
    const WIZARD_TYPES = ['wizard', 'wizard_fire', 'wizard_ice'];
    const SPRITE_ANIMS = { idle: 4, walk: 4, attack: 3, hurt: 3 };
    for (const type of WIZARD_TYPES) {
      for (const [anim, count] of Object.entries(SPRITE_ANIMS)) {
        for (let i = 1; i <= count; i++) {
          this.load.image(
            `${type}_${anim}_${i}`,
            `/world/static/game/assets/sprites/${type}/${anim}_${i}.png`
          );
        }
      }
    }
  }

  create() {
    // Generate particle textures for use throughout the game
    this._generateParticleTextures();
    // Generate procedural fallback backgrounds only when curated assets are missing
    this._generateFallbackBackgrounds();
    // Register wizard sprite animations globally
    this._createWizardAnimations();
    this.scene.start('BootScene');
  }

  _createWizardAnimations() {
    const WIZARD_TYPES = ['wizard', 'wizard_fire', 'wizard_ice'];
    for (const type of WIZARD_TYPES) {
      this.anims.create({
        key: `${type}_idle`,
        frames: [1, 2, 3, 4].map(i => ({ key: `${type}_idle_${i}` })),
        frameRate: 5,
        repeat: -1,
      });
      this.anims.create({
        key: `${type}_idle_slow`,
        frames: [1, 2, 3, 4].map(i => ({ key: `${type}_idle_${i}` })),
        frameRate: 2,
        repeat: -1,
      });
      this.anims.create({
        key: `${type}_walk`,
        frames: [1, 2, 3, 4].map(i => ({ key: `${type}_walk_${i}` })),
        frameRate: 8,
        repeat: -1,
      });
      this.anims.create({
        key: `${type}_attack`,
        frames: [1, 2, 3].map(i => ({ key: `${type}_attack_${i}` })),
        frameRate: 6,
        repeat: 0,
      });
      this.anims.create({
        key: `${type}_hurt`,
        frames: [1, 2, 3].map(i => ({ key: `${type}_hurt_${i}` })),
        frameRate: 6,
        repeat: 0,
      });
    }
  }

  _generateParticleTextures() {
    // Sparkle particle — 4-point star shape (8x8)
    const sparkle = this.make.graphics({ x: 0, y: 0, add: false });
    sparkle.fillStyle(0xffffff, 1);
    // Diamond shape
    sparkle.fillTriangle(4, 0, 6, 4, 4, 8);
    sparkle.fillTriangle(0, 4, 4, 2, 8, 4);
    sparkle.fillTriangle(0, 4, 4, 6, 8, 4);
    sparkle.fillStyle(0xffffff, 0.8);
    sparkle.fillCircle(4, 4, 1.5);
    sparkle.generateTexture('particle_sparkle', 8, 8);
    sparkle.destroy();

    // Soft glow particle — feathered circle (16x16)
    const glow = this.make.graphics({ x: 0, y: 0, add: false });
    glow.fillStyle(0xffffff, 0.15);
    glow.fillCircle(8, 8, 8);
    glow.fillStyle(0xffffff, 0.3);
    glow.fillCircle(8, 8, 5);
    glow.fillStyle(0xffffff, 0.6);
    glow.fillCircle(8, 8, 3);
    glow.generateTexture('particle_glow', 16, 16);
    glow.destroy();

    // Dust mote — tiny bright dot (4x4)
    const dust = this.make.graphics({ x: 0, y: 0, add: false });
    dust.fillStyle(0xffffff, 0.8);
    dust.fillCircle(2, 2, 2);
    dust.fillStyle(0xffffff, 1);
    dust.fillCircle(2, 2, 1);
    dust.generateTexture('particle_dust', 4, 4);
    dust.destroy();

    // Flame particle — teardrop shape (8x12)
    const flame = this.make.graphics({ x: 0, y: 0, add: false });
    flame.fillStyle(0xffffff, 0.9);
    flame.fillTriangle(4, 0, 7, 8, 1, 8);
    flame.fillStyle(0xffffff, 0.6);
    flame.fillCircle(4, 9, 3);
    flame.generateTexture('particle_flame', 8, 12);
    flame.destroy();

    // Fog particle — large soft circle (32x32)
    const fog = this.make.graphics({ x: 0, y: 0, add: false });
    fog.fillStyle(0xffffff, 0.05);
    fog.fillCircle(16, 16, 16);
    fog.fillStyle(0xffffff, 0.1);
    fog.fillCircle(16, 16, 10);
    fog.fillStyle(0xffffff, 0.15);
    fog.fillCircle(16, 16, 5);
    fog.generateTexture('particle_fog', 32, 32);
    fog.destroy();

    // Trail particle — small halo (6x6)
    const trail = this.make.graphics({ x: 0, y: 0, add: false });
    trail.fillStyle(0xffffff, 0.6);
    trail.fillCircle(3, 3, 3);
    trail.fillStyle(0xffffff, 1);
    trail.fillCircle(3, 3, 1.5);
    trail.generateTexture('particle_trail', 6, 6);
    trail.destroy();

    // Rune particle — diamond shape (10x10)
    const rune = this.make.graphics({ x: 0, y: 0, add: false });
    rune.fillStyle(0xffffff, 0.8);
    rune.fillTriangle(5, 0, 10, 5, 5, 10);
    rune.fillTriangle(0, 5, 5, 0, 5, 10);
    rune.fillStyle(0xffffff, 0.4);
    rune.fillCircle(5, 5, 2);
    rune.generateTexture('particle_rune', 10, 10);
    rune.destroy();
  }

  _generateFallbackBackgrounds() {
    this._ensureBackgroundTexture('boot_bg', () => this._genBootBg());
    this._ensureBackgroundTexture('lobby_bg', () => this._genLobbyBg());
    // Always regenerate themed backgrounds (ignore curated room_bg.jpg)
    // Habbo palette: bright saturated walls, high contrast vs canvas 0x1B3047.
    this._genRoomBgTheme('library',     0x8C5A33, 0x754726, 0xC94F4F, 0xA63C3C, 0xF5E6C2);
    this._genRoomBgTheme('observatory', 0x3D4A7A, 0x2E3A60, 0x6B8FC9, 0x4E6FA8, 0xFFE8A8);
    this._genRoomBgTheme('alchemy',     0xE8E8E8, 0xBFC4CC, 0x9FE4C8, 0x7CC8A8, 0xFFFFFF);
    this._genRoomBgTheme('workshop',    0x9E6B3D, 0x8A5A30, 0xE8C89B, 0xC9A878, 0x6B3A22);
    // Keep legacy room_bg as fallback
    this._ensureBackgroundTexture('room_bg', () => this._genRoomBg());
  }

  _ensureBackgroundTexture(key, generator) {
    if (this.textures.exists(key)) {
      const texture = this.textures.get(key);
      if (texture && texture.key !== '__MISSING') {
        return;
      }
    }
    generator();
  }

  _genBootBg() {
    const g = this.make.graphics({ x: 0, y: 0, add: false });
    const W = 1024, H = 576;
    // Habbo dark blue background
    g.fillStyle(0x1B3047, 1);
    g.fillRect(0, 0, W, H);
    // Subtle lighter center
    g.fillStyle(0x234060, 0.4);
    g.fillEllipse(W / 2, H / 2, 500, 300);
    g.generateTexture('boot_bg', W, H);
    g.destroy();
  }

  _genLobbyBg() {
    const g = this.make.graphics({ x: 0, y: 0, add: false });
    const W = 1024, H = 576;

    const TILE_W = 64;
    const TILE_H = 32;
    const FLOOR_A = 0x889F69;
    const FLOOR_B = 0x7A9160;
    const WALL_BACK = 0x6B8EB5;
    const WALL_LEFT = 0x7DA0C4;
    const WALL_TOP = 0x5A7A9E;
    const BG_COLOR = 0x1B3047;

    // Sky/background fill
    g.fillStyle(BG_COLOR, 1);
    g.fillRect(0, 0, W, H);

    // Isometric floor grid
    const COLS = 16;
    const ROWS = 12;
    const originX = W / 2;
    const originY = 140;

    // Draw back wall
    const wallH = 90;
    // Back wall runs along the top edge of the floor
    for (let col = 0; col < COLS; col++) {
      const tx = originX + (col - 0) * (TILE_W / 2);
      const ty = originY + (col + 0) * (TILE_H / 2);
      const tx2 = originX + (col + 1 - 0) * (TILE_W / 2);
      const ty2 = originY + (col + 1 + 0) * (TILE_H / 2);

      // Wall face
      g.fillStyle(WALL_BACK, 1);
      g.fillPoints([
        { x: tx, y: ty },
        { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH },
        { x: tx, y: ty - wallH },
      ], true);
      // Wall outline
      g.lineStyle(1, 0x4A6A8A, 0.5);
      g.strokePoints([
        { x: tx, y: ty },
        { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH },
        { x: tx, y: ty - wallH },
        { x: tx, y: ty },
      ], false);
    }

    // Left wall
    for (let row = 0; row < ROWS; row++) {
      const tx = originX + (0 - row) * (TILE_W / 2);
      const ty = originY + (0 + row) * (TILE_H / 2);
      const tx2 = originX + (0 - (row + 1)) * (TILE_W / 2);
      const ty2 = originY + (0 + (row + 1)) * (TILE_H / 2);

      g.fillStyle(WALL_LEFT, 1);
      g.fillPoints([
        { x: tx, y: ty },
        { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH },
        { x: tx, y: ty - wallH },
      ], true);
      g.lineStyle(1, 0x5A8AAA, 0.4);
      g.strokePoints([
        { x: tx, y: ty },
        { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH },
        { x: tx, y: ty - wallH },
        { x: tx, y: ty },
      ], false);
    }

    // Wall top edge (thickness)
    const topCorner = { x: originX, y: originY - wallH };
    const topRight = { x: originX + COLS * (TILE_W / 2), y: originY + COLS * (TILE_H / 2) - wallH };
    const topLeft = { x: originX - ROWS * (TILE_W / 2), y: originY + ROWS * (TILE_H / 2) - wallH };
    const wallThick = 8;
    g.fillStyle(WALL_TOP, 1);
    // Back wall top
    g.fillPoints([
      { x: topCorner.x, y: topCorner.y },
      { x: topRight.x, y: topRight.y },
      { x: topRight.x, y: topRight.y - wallThick },
      { x: topCorner.x, y: topCorner.y - wallThick },
    ], true);
    // Left wall top
    g.fillPoints([
      { x: topCorner.x, y: topCorner.y },
      { x: topLeft.x, y: topLeft.y },
      { x: topLeft.x, y: topLeft.y - wallThick },
      { x: topCorner.x, y: topCorner.y - wallThick },
    ], true);

    // Floor tiles — isometric diamonds
    for (let row = 0; row < ROWS; row++) {
      for (let col = 0; col < COLS; col++) {
        const cx = originX + (col - row) * (TILE_W / 2);
        const cy = originY + (col + row) * (TILE_H / 2);
        const shade = (col + row) % 2 === 0 ? FLOOR_A : FLOOR_B;

        g.fillStyle(shade, 1);
        g.fillPoints([
          { x: cx, y: cy - TILE_H / 2 },
          { x: cx + TILE_W / 2, y: cy },
          { x: cx, y: cy + TILE_H / 2 },
          { x: cx - TILE_W / 2, y: cy },
        ], true);
        // Tile outline
        g.lineStyle(1, 0x5A7A4A, 0.3);
        g.strokePoints([
          { x: cx, y: cy - TILE_H / 2 },
          { x: cx + TILE_W / 2, y: cy },
          { x: cx, y: cy + TILE_H / 2 },
          { x: cx - TILE_W / 2, y: cy },
          { x: cx, y: cy - TILE_H / 2 },
        ], false);
      }
    }

    // Door alcoves in back wall (4 doors)
    const doorCols = [3, 6, 10, 13];
    for (const dc of doorCols) {
      const dx = originX + (dc - 0) * (TILE_W / 2) + TILE_W / 4;
      const dy = originY + dc * (TILE_H / 2) - wallH + 20;
      // Dark doorway
      g.fillStyle(0x0F1F33, 0.9);
      g.fillRoundedRect(dx - 16, dy, 32, 50, { tl: 10, tr: 10, bl: 0, br: 0 });
      // Door frame
      g.lineStyle(2, 0x4A6A8A, 0.7);
      g.strokeRoundedRect(dx - 16, dy, 32, 50, { tl: 10, tr: 10, bl: 0, br: 0 });
    }

    g.generateTexture('lobby_bg', W, H);
    g.destroy();
  }

  /**
   * Themed background generator — each theme gets distinct floor + wall colors
   * plus signature baked-in decor (bookshelves, telescopes, lab counters, etc.)
   * to make rooms read as different spaces at a glance.
   */
  _genRoomBgTheme(themeKey, floorA, floorB, wallBack, wallLeft, trim) {
    const g = this.make.graphics({ x: 0, y: 0, add: false });
    const W = 1024, H = 576;
    const TILE_W = 54;
    const TILE_H = 27;
    const BG_COLOR = 0x1B3047;
    const WALL_TOP = 0x0F1F33;

    g.fillStyle(BG_COLOR, 1);
    g.fillRect(0, 0, W, H);

    const COLS = 18;
    const ROWS = 14;
    const originX = W / 2;
    const originY = 80;
    const wallH = 90;

    // Back wall
    for (let col = 0; col < COLS; col++) {
      const tx = originX + col * (TILE_W / 2);
      const ty = originY + col * (TILE_H / 2);
      const tx2 = originX + (col + 1) * (TILE_W / 2);
      const ty2 = originY + (col + 1) * (TILE_H / 2);
      g.fillStyle(wallBack, 1);
      g.fillPoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH }, { x: tx, y: ty - wallH },
      ], true);
    }

    // Left wall
    for (let row = 0; row < ROWS; row++) {
      const tx = originX - row * (TILE_W / 2);
      const ty = originY + row * (TILE_H / 2);
      const tx2 = originX - (row + 1) * (TILE_W / 2);
      const ty2 = originY + (row + 1) * (TILE_H / 2);
      g.fillStyle(wallLeft, 1);
      g.fillPoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH }, { x: tx, y: ty - wallH },
      ], true);
    }

    // Wall top caps (thick rim)
    const topCorner = { x: originX, y: originY - wallH };
    const topRight = { x: originX + COLS * (TILE_W / 2), y: originY + COLS * (TILE_H / 2) - wallH };
    const topLeft = { x: originX - ROWS * (TILE_W / 2), y: originY + ROWS * (TILE_H / 2) - wallH };
    g.fillStyle(WALL_TOP, 1);
    g.fillPoints([topCorner, topRight, { x: topRight.x, y: topRight.y - 6 }, { x: topCorner.x, y: topCorner.y - 6 }], true);
    g.fillPoints([topCorner, topLeft, { x: topLeft.x, y: topLeft.y - 6 }, { x: topCorner.x, y: topCorner.y - 6 }], true);

    // Trim band running along wall bottom (skirting)
    g.fillStyle(trim, 0.6);
    for (let col = 0; col < COLS; col++) {
      const tx = originX + col * (TILE_W / 2);
      const ty = originY + col * (TILE_H / 2);
      const tx2 = originX + (col + 1) * (TILE_W / 2);
      const ty2 = originY + (col + 1) * (TILE_H / 2);
      g.fillPoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - 10 }, { x: tx, y: ty - 10 },
      ], true);
    }
    for (let row = 0; row < ROWS; row++) {
      const tx = originX - row * (TILE_W / 2);
      const ty = originY + row * (TILE_H / 2);
      const tx2 = originX - (row + 1) * (TILE_W / 2);
      const ty2 = originY + (row + 1) * (TILE_H / 2);
      g.fillPoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - 10 }, { x: tx, y: ty - 10 },
      ], true);
    }

    // Theme-specific wall decoration (baked into the bg so every room reads distinct)
    this._decorateWalls(g, themeKey, { originX, originY, COLS, ROWS, TILE_W, TILE_H, wallH, trim });

    // Floor tiles
    for (let row = 0; row < ROWS; row++) {
      for (let col = 0; col < COLS; col++) {
        const cx = originX + (col - row) * (TILE_W / 2);
        const cy = originY + (col + row) * (TILE_H / 2);
        const shade = (col + row) % 2 === 0 ? floorA : floorB;

        g.fillStyle(shade, 1);
        g.fillPoints([
          { x: cx, y: cy - TILE_H / 2 },
          { x: cx + TILE_W / 2, y: cy },
          { x: cx, y: cy + TILE_H / 2 },
          { x: cx - TILE_W / 2, y: cy },
        ], true);
      }
    }

    // Subtle tile grid
    g.lineStyle(1, 0x000000, 0.08);
    for (let row = 0; row < ROWS; row++) {
      for (let col = 0; col < COLS; col++) {
        const cx = originX + (col - row) * (TILE_W / 2);
        const cy = originY + (col + row) * (TILE_H / 2);
        g.strokePoints([
          { x: cx, y: cy - TILE_H / 2 },
          { x: cx + TILE_W / 2, y: cy },
          { x: cx, y: cy + TILE_H / 2 },
          { x: cx - TILE_W / 2, y: cy },
          { x: cx, y: cy - TILE_H / 2 },
        ], false);
      }
    }

    g.generateTexture(`room_bg_${themeKey}`, W, H);
    g.destroy();
  }

  _decorateWalls(g, themeKey, ctx) {
    const { originX, originY, COLS, ROWS, TILE_W, TILE_H, wallH } = ctx;
    const HW = TILE_W / 2;
    const HH = TILE_H / 2;
    const OUTLINE = 0x1A1A1A;

    const backWallY = (col) => originY + col * HH;
    const leftWallY = (row) => originY + row * HH;

    if (themeKey === 'library') {
      // 3 tall bookshelves evenly spaced across back wall
      const shelfColors = [0x6B2020, 0xC9A34E, 0x2E4A6B, 0x3A6B3A, 0x7A4E8C];
      const shelfCols = [3, 8, 14];
      for (const col of shelfCols) {
        const x = originX + col * HW;
        const y = backWallY(col) - wallH + 12;
        g.fillStyle(0x3D2817, 1);
        g.fillRect(x - 30, y, 60, wallH - 22);
        g.lineStyle(1, OUTLINE, 0.6);
        g.strokeRect(x - 30, y, 60, wallH - 22);
        for (let r = 0; r < 5; r++) {
          const shelfY = y + 6 + r * 12;
          g.fillStyle(0x1E1408, 0.7);
          g.fillRect(x - 28, shelfY + 10, 56, 1);
          for (let b = 0; b < 11; b++) {
            g.fillStyle(shelfColors[(r * 3 + b) % shelfColors.length], 1);
            g.fillRect(x - 28 + b * 5, shelfY, 4, 10);
          }
        }
      }
      // Grand fireplace between shelves (col ~11)
      {
        const col = 11;
        const x = originX + col * HW;
        const y = backWallY(col) - wallH + 20;
        // Stone hearth
        g.fillStyle(0x8A7A6B, 1);
        g.fillRect(x - 30, y, 60, wallH - 32);
        g.lineStyle(1, OUTLINE, 0.6);
        g.strokeRect(x - 30, y, 60, wallH - 32);
        // Stone block pattern
        g.lineStyle(1, 0x5E5245, 0.6);
        for (let r = 0; r < 3; r++) {
          g.lineBetween(x - 30, y + 14 + r * 14, x + 30, y + 14 + r * 14);
        }
        // Dark opening
        g.fillStyle(0x1A0E06, 1);
        g.fillRect(x - 18, y + 10, 36, 30);
        // Ember glow
        g.fillStyle(0xFFB06B, 0.9);
        g.fillEllipse(x, y + 38, 24, 8);
        g.fillStyle(0xFFE8A8, 0.7);
        g.fillEllipse(x, y + 36, 14, 4);
        // Mantel
        g.fillStyle(0xF5E6C2, 1);
        g.fillRect(x - 34, y - 4, 68, 5);
        g.lineStyle(1, OUTLINE, 0.5);
        g.strokeRect(x - 34, y - 4, 68, 5);
      }
      // 3 framed portraits on left wall
      const portraitRows = [2, 6, 10];
      for (const row of portraitRows) {
        const x = originX - row * HW;
        const y = leftWallY(row) - wallH + 18;
        g.fillStyle(0xE9AD58, 1);
        g.fillRect(x - 22, y, 44, 34);
        g.lineStyle(1, OUTLINE, 0.6);
        g.strokeRect(x - 22, y, 44, 34);
        g.fillStyle(0xF5E6C2, 1);
        g.fillRect(x - 18, y + 4, 36, 26);
        g.fillStyle(0x754726, 0.8);
        g.fillCircle(x, y + 14, 5);
        g.fillRect(x - 6, y + 18, 12, 10);
      }
    } else if (themeKey === 'observatory') {
      // ~30 larger stars, back wall
      const rng = this._seededRand(1337);
      for (let i = 0; i < 30; i++) {
        const col = rng() * COLS;
        const sx = originX + col * HW;
        const sy = backWallY(col) - wallH + 8 + rng() * (wallH - 16);
        g.fillStyle(0xFFFFFF, 0.9);
        g.fillCircle(sx, sy, rng() < 0.3 ? 3 : 2);
      }
      // Stars on left wall
      for (let i = 0; i < 20; i++) {
        const row = rng() * ROWS;
        const sx = originX - row * HW;
        const sy = leftWallY(row) - wallH + 8 + rng() * (wallH - 16);
        g.fillStyle(0xFFFFFF, 0.85);
        g.fillCircle(sx, sy, rng() < 0.3 ? 3 : 2);
      }
      // Huge round window on back wall (radius 80) around col 11
      {
        const col = 11;
        const winX = originX + col * HW;
        const winY = backWallY(col) - wallH / 2 - 6;
        // Deep space
        g.fillStyle(0x0E1B3D, 1);
        g.fillCircle(winX, winY, 48);
        // Window frame
        g.lineStyle(4, 0xFFE8A8, 0.9);
        g.strokeCircle(winX, winY, 48);
        g.lineStyle(2, OUTLINE, 0.6);
        g.strokeCircle(winX, winY, 48);
        // Orbit rings
        g.lineStyle(1, 0xFFE8A8, 0.3);
        g.strokeCircle(winX, winY, 36);
        g.strokeCircle(winX, winY, 24);
        g.strokeCircle(winX, winY, 14);
        // Moon
        g.fillStyle(0xFFF0B8, 1);
        g.fillCircle(winX + 14, winY - 8, 14);
        g.fillStyle(0xD4C48A, 0.7);
        g.fillCircle(winX + 20, winY - 4, 3);
        g.fillCircle(winX + 10, winY - 14, 2);
        g.fillCircle(winX + 18, winY - 12, 1.5);
        // Inner stars in window
        g.fillStyle(0xFFFFFF, 1);
        g.fillCircle(winX - 20, winY + 12, 1.5);
        g.fillCircle(winX - 10, winY - 20, 1.5);
        g.fillCircle(winX - 28, winY - 6, 1);
      }
      // Tall brass telescope silhouette on left wall
      {
        const row = 7;
        const x = originX - row * HW;
        const y = leftWallY(row) - wallH + 14;
        // Barrel
        g.fillStyle(0xC9A34E, 1);
        g.fillRect(x - 8, y, 16, 60);
        g.lineStyle(1, OUTLINE, 0.7);
        g.strokeRect(x - 8, y, 16, 60);
        // Eyepiece
        g.fillStyle(0x8A6A2E, 1);
        g.fillRect(x - 4, y - 6, 8, 8);
        // Lens cap
        g.fillStyle(0x6B5020, 1);
        g.fillRect(x - 10, y + 56, 20, 6);
        // Tripod
        g.lineStyle(2, 0x1A1A1A, 0.9);
        g.lineBetween(x - 8, y + 62, x - 16, y + 80);
        g.lineBetween(x, y + 62, x, y + 80);
        g.lineBetween(x + 8, y + 62, x + 16, y + 80);
      }
      // Constellation lines on back wall left of window
      g.lineStyle(1, 0xFFE8A8, 0.6);
      const winXRef = originX + 11 * HW;
      const winYRef = backWallY(11) - wallH / 2 - 6;
      const constel = [
        [winXRef - 140, winYRef - 20],
        [winXRef - 120, winYRef - 38],
        [winXRef - 100, winYRef - 22],
        [winXRef - 80, winYRef - 40],
        [winXRef - 68, winYRef - 18],
      ];
      for (let i = 0; i < constel.length - 1; i++) {
        g.lineBetween(constel[i][0], constel[i][1], constel[i + 1][0], constel[i + 1][1]);
      }
      g.fillStyle(0xFFFFFF, 1);
      for (const [cx, cy] of constel) g.fillCircle(cx, cy, 2);
    } else if (themeKey === 'alchemy') {
      // Vent strips above monitors
      g.fillStyle(0x8A8A8A, 1);
      for (let col = 1; col < COLS; col += 1) {
        const tx = originX + col * HW;
        const ty = backWallY(col) - wallH + 6;
        g.fillRect(tx - 18, ty, 36, 2);
      }
      // Monitor bank: 4 CRTs evenly spaced
      const mCols = [4, 8, 12, 16];
      for (const col of mCols) {
        const x = originX + col * HW;
        const y = backWallY(col) - wallH + 18;
        // Bezel
        g.fillStyle(0x1A1A1A, 1);
        g.fillRect(x - 30, y, 60, 45);
        g.lineStyle(1, OUTLINE, 0.6);
        g.strokeRect(x - 30, y, 60, 45);
        // Screen
        g.fillStyle(0x0D2818, 1);
        g.fillRect(x - 26, y + 4, 52, 32);
        // Green terminal bars
        g.fillStyle(0x34D399, 0.9);
        g.fillRect(x - 23, y + 7, 34, 2);
        g.fillRect(x - 23, y + 12, 22, 2);
        g.fillRect(x - 23, y + 17, 40, 2);
        g.fillRect(x - 23, y + 22, 28, 2);
        g.fillRect(x - 23, y + 27, 36, 2);
        g.fillRect(x - 23, y + 32, 18, 2);
        // White glow highlight
        g.fillStyle(0xFFFFFF, 0.15);
        g.fillRect(x - 26, y + 4, 52, 4);
        // Stand
        g.fillStyle(0x333333, 1);
        g.fillRect(x - 4, y + 45, 8, 4);
        g.fillRect(x - 12, y + 49, 24, 2);
      }
      // Periodic-table poster on left wall
      {
        const row = 6;
        const x = originX - row * HW;
        const y = leftWallY(row) - wallH + 14;
        g.fillStyle(0xF5F5F5, 1);
        g.fillRect(x - 35, y, 70, 50);
        g.lineStyle(1, OUTLINE, 0.6);
        g.strokeRect(x - 35, y, 70, 50);
        for (let r = 0; r < 6; r++) {
          for (let c = 0; c < 9; c++) {
            g.fillStyle(0x333333, 0.85);
            g.fillRect(x - 32 + c * 7, y + 4 + r * 7, 5, 5);
          }
        }
      }
    } else {
      // workshop
      // Exposed brick strip on left wall base
      g.fillStyle(0x8A3E2A, 1);
      for (let row = 0; row < ROWS; row++) {
        const tx = originX - row * HW;
        const ty = leftWallY(row) - 20;
        const tx2 = originX - (row + 1) * HW;
        const ty2 = leftWallY(row + 1) - 20;
        g.fillPoints([
          { x: tx, y: ty }, { x: tx2, y: ty2 },
          { x: tx2, y: ty2 - 20 }, { x: tx, y: ty - 20 },
        ], true);
      }
      // Brick mortar lines
      g.lineStyle(1, 0x5A2416, 0.7);
      for (let row = 0; row <= ROWS; row++) {
        const tx = originX - row * HW;
        const ty = leftWallY(row) - 20;
        g.lineBetween(tx, ty, tx, ty - 20);
      }
      // Workbench baseboard band along back wall bottom
      g.fillStyle(0x5A3418, 1);
      for (let col = 0; col < COLS; col++) {
        const tx = originX + col * HW;
        const ty = backWallY(col) - 18;
        const tx2 = originX + (col + 1) * HW;
        const ty2 = backWallY(col + 1) - 18;
        g.fillPoints([
          { x: tx, y: ty }, { x: tx2, y: ty2 },
          { x: tx2, y: ty2 - 16 }, { x: tx, y: ty - 16 },
        ], true);
      }
      // Saw-blade silhouette centered on baseboard
      {
        const col = 11;
        const x = originX + col * HW;
        const y = backWallY(col) - 26;
        g.fillStyle(0x9A9A9A, 1);
        g.fillCircle(x, y, 9);
        g.lineStyle(1, OUTLINE, 0.7);
        g.strokeCircle(x, y, 9);
        g.fillStyle(0x1A1A1A, 1);
        g.fillCircle(x, y, 2);
        // Teeth (simple triangles)
        for (let t = 0; t < 12; t++) {
          const a = (t / 12) * Math.PI * 2;
          const px = x + Math.cos(a) * 10;
          const py = y + Math.sin(a) * 10;
          g.fillCircle(px, py, 1.2);
        }
      }
      // Large pegboard with tools on back wall (col ~7)
      {
        const col = 7;
        const x = originX + col * HW;
        const y = backWallY(col) - wallH + 14;
        g.fillStyle(0xD4A36C, 1);
        g.fillRect(x - 60, y, 120, 64);
        g.lineStyle(1, OUTLINE, 0.6);
        g.strokeRect(x - 60, y, 120, 64);
        for (let pr = 0; pr < 7; pr++) {
          for (let pc = 0; pc < 13; pc++) {
            g.fillStyle(0x6A4A1E, 0.55);
            g.fillCircle(x - 55 + pc * 9, y + 6 + pr * 8, 1);
          }
        }
        // Hammer
        g.fillStyle(0x8A5A33, 1);
        g.fillRect(x - 50, y + 12, 4, 26);
        g.fillStyle(0x333333, 1);
        g.fillRect(x - 54, y + 8, 14, 8);
        g.lineStyle(1, OUTLINE, 0.7);
        g.strokeRect(x - 54, y + 8, 14, 8);
        // Wrench
        g.fillStyle(0x6B6B6B, 1);
        g.fillRect(x - 20, y + 12, 4, 30);
        g.fillCircle(x - 18, y + 42, 6);
        g.fillStyle(0xD4A36C, 1);
        g.fillCircle(x - 18, y + 42, 3);
        // Saw
        g.fillStyle(0xC0C0C0, 1);
        g.fillTriangle(x + 10, y + 14, x + 46, y + 14, x + 46, y + 22);
        g.fillStyle(0x8A5A33, 1);
        g.fillRect(x + 2, y + 12, 10, 8);
        g.lineStyle(1, OUTLINE, 0.7);
        g.strokeRect(x + 2, y + 12, 10, 8);
      }
      // Hanging bulb top-center back wall
      {
        const col = 11;
        const x = originX + col * HW;
        const top = backWallY(col) - wallH;
        g.lineStyle(1, 0x1A1A1A, 0.9);
        g.lineBetween(x, top, x, top + 24);
        g.fillStyle(0xFFE8A8, 1);
        g.fillCircle(x, top + 28, 5);
        g.lineStyle(1, OUTLINE, 0.7);
        g.strokeCircle(x, top + 28, 5);
        // Warm halo
        g.fillStyle(0xFFE8A8, 0.2);
        g.fillCircle(x, top + 28, 14);
      }
    }
  }

  _seededRand(seed) {
    let s = seed;
    return () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
  }

  _genRoomBg() {
    const g = this.make.graphics({ x: 0, y: 0, add: false });
    const W = 1024, H = 576;

    const TILE_W = 54;
    const TILE_H = 27;
    const FLOOR_A = 0xC4A882;
    const FLOOR_B = 0xB89A6E;
    const WALL_BACK = 0x6B8EB5;
    const WALL_LEFT = 0x7DA0C4;
    const WALL_TOP = 0x5A7A9E;
    const BG_COLOR = 0x1B3047;

    g.fillStyle(BG_COLOR, 1);
    g.fillRect(0, 0, W, H);

    const COLS = 18;
    const ROWS = 14;
    const originX = W / 2;
    const originY = 80;

    // Back wall
    const wallH = 70;
    for (let col = 0; col < COLS; col++) {
      const tx = originX + (col - 0) * (TILE_W / 2);
      const ty = originY + (col + 0) * (TILE_H / 2);
      const tx2 = originX + (col + 1 - 0) * (TILE_W / 2);
      const ty2 = originY + (col + 1 + 0) * (TILE_H / 2);
      g.fillStyle(WALL_BACK, 1);
      g.fillPoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH }, { x: tx, y: ty - wallH },
      ], true);
      g.lineStyle(1, 0x4A6A8A, 0.3);
      g.strokePoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH }, { x: tx, y: ty - wallH }, { x: tx, y: ty },
      ], false);
    }

    // Left wall
    for (let row = 0; row < ROWS; row++) {
      const tx = originX + (0 - row) * (TILE_W / 2);
      const ty = originY + (0 + row) * (TILE_H / 2);
      const tx2 = originX + (0 - (row + 1)) * (TILE_W / 2);
      const ty2 = originY + (0 + (row + 1)) * (TILE_H / 2);
      g.fillStyle(WALL_LEFT, 1);
      g.fillPoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH }, { x: tx, y: ty - wallH },
      ], true);
      g.lineStyle(1, 0x5A8AAA, 0.3);
      g.strokePoints([
        { x: tx, y: ty }, { x: tx2, y: ty2 },
        { x: tx2, y: ty2 - wallH }, { x: tx, y: ty - wallH }, { x: tx, y: ty },
      ], false);
    }

    // Wall top edges
    const topCorner = { x: originX, y: originY - wallH };
    const topRight = { x: originX + COLS * (TILE_W / 2), y: originY + COLS * (TILE_H / 2) - wallH };
    const topLeft = { x: originX - ROWS * (TILE_W / 2), y: originY + ROWS * (TILE_H / 2) - wallH };
    g.fillStyle(WALL_TOP, 1);
    g.fillPoints([
      topCorner, topRight,
      { x: topRight.x, y: topRight.y - 6 },
      { x: topCorner.x, y: topCorner.y - 6 },
    ], true);
    g.fillPoints([
      topCorner, topLeft,
      { x: topLeft.x, y: topLeft.y - 6 },
      { x: topCorner.x, y: topCorner.y - 6 },
    ], true);

    // Windows in back wall
    const winCols = [4, 9, 14];
    for (const wc of winCols) {
      const wx = originX + (wc + 0.5) * (TILE_W / 2);
      const wy = originY + (wc + 0.5) * (TILE_H / 2) - wallH + 15;
      g.fillStyle(0x88C8E8, 0.3);
      g.fillRoundedRect(wx - 12, wy, 24, 30, { tl: 8, tr: 8, bl: 0, br: 0 });
      g.lineStyle(2, 0x4A6A8A, 0.6);
      g.strokeRoundedRect(wx - 12, wy, 24, 30, { tl: 8, tr: 8, bl: 0, br: 0 });
    }

    // Floor tiles
    for (let row = 0; row < ROWS; row++) {
      for (let col = 0; col < COLS; col++) {
        const cx = originX + (col - row) * (TILE_W / 2);
        const cy = originY + (col + row) * (TILE_H / 2);
        const shade = (col + row) % 2 === 0 ? FLOOR_A : FLOOR_B;

        g.fillStyle(shade, 1);
        g.fillPoints([
          { x: cx, y: cy - TILE_H / 2 },
          { x: cx + TILE_W / 2, y: cy },
          { x: cx, y: cy + TILE_H / 2 },
          { x: cx - TILE_W / 2, y: cy },
        ], true);
        g.lineStyle(1, 0x8C7246, 0.25);
        g.strokePoints([
          { x: cx, y: cy - TILE_H / 2 },
          { x: cx + TILE_W / 2, y: cy },
          { x: cx, y: cy + TILE_H / 2 },
          { x: cx - TILE_W / 2, y: cy },
          { x: cx, y: cy - TILE_H / 2 },
        ], false);
      }
    }

    g.generateTexture('room_bg', W, H);
    g.destroy();
  }
}

/* ================================================================== */
/*  Boot Scene                                                         */
/* ================================================================== */

class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // Background image (or fallback)
    const bgImage = this.add.image(W / 2, H / 2, 'boot_bg');
    bgImage.setDisplaySize(W, H);

    // Dark blue overlay
    const overlay = this.add.graphics();
    overlay.fillStyle(0x1B3047, 0.6);
    overlay.fillRect(0, 0, W, H);

    // Habbo-style panel
    const panelG = this.add.graphics();
    const panelW = 340;
    const panelH = 110;
    const panelX = W / 2 - panelW / 2;
    const panelY = H / 2 - 70;

    // Panel shadow
    panelG.fillStyle(0x000000, 0.25);
    panelG.fillRoundedRect(panelX + 3, panelY + 3, panelW, panelH, 6);
    // Panel body
    panelG.fillStyle(0x34649C, 0.95);
    panelG.fillRoundedRect(panelX, panelY, panelW, panelH, 6);
    // Title bar
    panelG.fillStyle(0x1B3047, 1);
    panelG.fillRoundedRect(panelX, panelY, panelW, 32, { tl: 6, tr: 6, bl: 0, br: 0 });
    // Border
    panelG.lineStyle(2, 0x0F1F33, 0.8);
    panelG.strokeRoundedRect(panelX, panelY, panelW, panelH, 6);

    // Title text
    this.add.text(W / 2, panelY + 16, 'ContextGraph World', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '16px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);

    this.add.text(W / 2, panelY + 56, 'Agent Headquarters', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '22px',
      fontStyle: '800',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);

    // Status text
    this._statusText = this.add.text(W / 2, panelY + 86, 'Connecting...', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '13px',
      fontStyle: '400',
      color: '#88b4d6',
    }).setOrigin(0.5, 0.5);

    // Pulsing dot
    const dot = this.add.graphics();
    dot.fillStyle(0x4A90D9, 1);
    dot.fillCircle(W / 2, H / 2 + 62, 4);
    this.tweens.add({
      targets: dot,
      alpha: { from: 1, to: 0.2 },
      duration: 800,
      yoyo: true,
      repeat: -1,
    });

    // Create socket
    this.socket = new WorldSocket(this);
    this.socket.connect();

    // Listen for world_snapshot to transition
    this.events.on('ws:world_snapshot', (msg) => {
      this._statusText.setText('Entering...');
      this.cameras.main.fadeOut(400, 27, 48, 71);
      this.cameras.main.once('camerafadeoutcomplete', () => {
        this.scene.start('LobbyScene', {
          socket: this.socket,
          snapshot: msg,
        });
      });
    });

    this.events.on('ws:close', () => {
      if (this._statusText) {
        this._statusText.setText('Reconnecting...');
      }
    });

    this.events.on('ws:open', () => {
      if (this._statusText) {
        this._statusText.setText('Connected!');
      }
    });
  }

  _createAmbientDust() {
    // Removed — Habbo-style clean aesthetic
  }
}

/* ================================================================== */
/*  Phaser Config                                                      */
/* ================================================================== */

const config = {
  type: Phaser.AUTO,
  width: 1024,
  height: 576,
  parent: 'game-container',
  backgroundColor: '#1B3047',
  pixelArt: true,
  roundPixels: true,
  scale: {
    mode: Phaser.Scale.ENVELOP,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: [PreloadScene, BootScene, LobbyScene, RoomScene],
};

/* ================================================================== */
/*  Launch                                                             */
/* ================================================================== */

const game = new Phaser.Game(config);

// Init the inspect panel (DOM overlay)
const inspectPanel = new InspectPanel();
