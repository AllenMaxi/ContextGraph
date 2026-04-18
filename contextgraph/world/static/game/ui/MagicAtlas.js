/**
 * MagicAtlas — Room navigator overlay (Habbo-style).
 * Appears in both lobby and project rooms. Lists all rooms
 * with agent count badges. Toggled via M key or navigator button.
 */
import { getThemeSpec, roomTitleFromId } from './roomThemes.js';

const PANEL_BG = 0x34649C;
const HEADER_BG = 0x1B3047;
const BORDER = 0x0F1F33;
const BTN_BLUE = 0x4A90D9;
const ACCENT = 0xE9AD58;

export default class MagicAtlas {
  /**
   * @param {Phaser.Scene} scene
   * @param {object} socket — WorldSocket instance with joinRoom/leaveRoom
   * @param {string} currentRoom — 'lobby' or a room_id
   * @param {Array} rooms — [{room_id, name, agent_count}, ...]
   */
  constructor(scene, socket, currentRoom, rooms) {
    this.scene = scene;
    this.socket = socket;
    this.currentRoom = currentRoom;
    this._rooms = rooms || [];
    this._open = false;
    this._container = null;
    this._overlay = null;
    this._rowContainers = [];

    this._buildButton();
    this._bindKeys();
  }

  /* ================================================================ */
  /*  Navigator button (top-right corner)                              */
  /* ================================================================ */

  _buildButton() {
    const W = this.scene.scale.width;
    const btn = this.scene.add.container(W - 64, 24);
    btn.setDepth(10000);

    const bg = this.scene.add.graphics();
    bg.fillStyle(BTN_BLUE, 0.92);
    bg.fillRoundedRect(-48, -14, 96, 28, 4);
    bg.lineStyle(1, BORDER, 0.6);
    bg.strokeRoundedRect(-48, -14, 96, 28, 4);
    btn.add(bg);

    const label = this.scene.add.text(0, 0, 'Navigator', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '11px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    btn.add(label);

    btn.setSize(96, 28);
    btn.setInteractive({ useHandCursor: true });

    btn.on('pointerover', () => {
      bg.clear();
      bg.fillStyle(0x5BA0E6, 1);
      bg.fillRoundedRect(-48, -14, 96, 28, 4);
      bg.lineStyle(1, BORDER, 0.6);
      bg.strokeRoundedRect(-48, -14, 96, 28, 4);
    });

    btn.on('pointerout', () => {
      bg.clear();
      bg.fillStyle(BTN_BLUE, 0.92);
      bg.fillRoundedRect(-48, -14, 96, 28, 4);
      bg.lineStyle(1, BORDER, 0.6);
      bg.strokeRoundedRect(-48, -14, 96, 28, 4);
    });

    btn.on('pointerdown', () => this.toggle());

    this._btn = btn;
  }

  /* ================================================================ */
  /*  Keyboard shortcuts                                               */
  /* ================================================================ */

  _bindKeys() {
    this._keyM = this.scene.input.keyboard.addKey('M');
    this._keyEsc = this.scene.input.keyboard.addKey('ESC');

    this._keyM.on('down', () => this.toggle());
    this._keyEsc.on('down', () => { if (this._open) this.close(); });
  }

  /* ================================================================ */
  /*  Open / Close / Toggle                                            */
  /* ================================================================ */

  toggle() {
    if (this._open) this.close(); else this.open();
  }

  open() {
    if (this._open) return;
    this._open = true;
    this._buildOverlay();
  }

  close() {
    if (!this._open) return;
    this._open = false;
    if (this._overlay) { this._overlay.destroy(); this._overlay = null; }
    if (this._container) { this._container.destroy(); this._container = null; }
    this._rowContainers = [];
  }

  /* ================================================================ */
  /*  Update rooms list (from snapshots)                               */
  /* ================================================================ */

  updateRooms(rooms) {
    this._rooms = rooms || [];
    if (this._open) {
      this.close();
      this.open();
    }
  }

  /* ================================================================ */
  /*  Build the navigator overlay                                      */
  /* ================================================================ */

  _buildOverlay() {
    const W = this.scene.scale.width;
    const H = this.scene.scale.height;

    // Click-outside overlay to close
    this._overlay = this.scene.add.graphics();
    this._overlay.setDepth(9990);
    this._overlay.fillStyle(0x000000, 0.4);
    this._overlay.fillRect(0, 0, W, H);
    this._overlay.setInteractive(
      new Phaser.Geom.Rectangle(0, 0, W, H),
      Phaser.Geom.Rectangle.Contains
    );
    this._overlay.on('pointerdown', () => this.close());

    // Panel dimensions
    const panelW = 280;
    const rowH = 36;
    const headerH = 36;
    const entries = this._getEntries();
    const panelH = headerH + entries.length * rowH + 12;
    const px = W / 2 - panelW / 2;
    const py = H / 2 - panelH / 2;

    this._container = this.scene.add.container(0, 0);
    this._container.setDepth(9995);

    const bg = this.scene.add.graphics();
    // Shadow
    bg.fillStyle(0x000000, 0.3);
    bg.fillRoundedRect(px + 3, py + 3, panelW, panelH, 6);
    // Panel body
    bg.fillStyle(PANEL_BG, 0.97);
    bg.fillRoundedRect(px, py, panelW, panelH, 6);
    // Header bar
    bg.fillStyle(HEADER_BG, 1);
    bg.fillRoundedRect(px, py, panelW, headerH, { tl: 6, tr: 6, bl: 0, br: 0 });
    // Border
    bg.lineStyle(2, BORDER, 0.8);
    bg.strokeRoundedRect(px, py, panelW, panelH, 6);
    // Divider under header
    bg.lineStyle(1, 0x2C5A8A, 0.5);
    bg.lineBetween(px + 8, py + headerH, px + panelW - 8, py + headerH);
    this._container.add(bg);

    // Header title
    const title = this.scene.add.text(W / 2, py + headerH / 2, 'Navigator', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '13px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    this._container.add(title);

    // Close button (X)
    const closeBtn = this.scene.add.text(px + panelW - 16, py + headerH / 2, '\u2715', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '12px',
      fontStyle: '700',
      color: '#88b4d6',
    }).setOrigin(0.5, 0.5).setInteractive({ useHandCursor: true });
    closeBtn.on('pointerdown', () => this.close());
    closeBtn.on('pointerover', () => closeBtn.setColor('#ffffff'));
    closeBtn.on('pointerout', () => closeBtn.setColor('#88b4d6'));
    closeBtn.setDepth(9996);
    this._container.add(closeBtn);

    // Room rows
    this._rowContainers = [];
    entries.forEach((entry, i) => {
      const ry = py + headerH + 6 + i * rowH;
      const row = this._buildRow(px, ry, panelW, rowH - 4, entry);
      this._rowContainers.push(row);
    });

    // Pop-in animation
    this._container.setScale(0.92);
    this._container.setAlpha(0);
    this.scene.tweens.add({
      targets: this._container,
      scaleX: 1, scaleY: 1, alpha: 1,
      duration: 180,
      ease: 'Back.easeOut',
    });
  }

  _getEntries() {
    const entries = [
      {
        id: 'lobby',
        name: 'Lobby',
        count: null,
        isCurrent: this.currentRoom === 'lobby',
        accent: BTN_BLUE,
        badgeText: 'HUB',
      },
    ];
    const seen = new Set();
    const rooms = [...this._rooms].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    for (const r of rooms) {
      seen.add(r.room_id);
      const theme = getThemeSpec(r.room_id, r.theme_key);
      entries.push({
        id: r.room_id,
        name: r.name,
        count: r.agent_count || 0,
        isCurrent: this.currentRoom === r.room_id,
        accent: theme.portal,
        badgeText: theme.badgeText,
      });
    }
    if (this.currentRoom !== 'lobby' && !seen.has(this.currentRoom)) {
      const theme = getThemeSpec(this.currentRoom);
      entries.push({
        id: this.currentRoom,
        name: roomTitleFromId(this.currentRoom),
        count: 0,
        isCurrent: true,
        accent: theme.portal,
        badgeText: theme.badgeText,
      });
    }
    return entries;
  }

  _buildRow(px, ry, panelW, rowH, entry) {
    const rw = panelW - 16;
    const rx = px + 8;

    const rowContainer = this.scene.add.container(0, 0);

    const rowBg = this.scene.add.graphics();
    if (entry.isCurrent) {
      rowBg.fillStyle(0xffffff, 0.15);
      rowBg.fillRoundedRect(rx, ry, rw, rowH, 4);
      rowBg.lineStyle(1, 0xffffff, 0.2);
      rowBg.strokeRoundedRect(rx, ry, rw, rowH, 4);
    } else {
      rowBg.fillStyle(0xffffff, 0.05);
      rowBg.fillRoundedRect(rx, ry, rw, rowH, 4);
    }
    rowContainer.add(rowBg);

    // Colored indicator dot
    const dotX = rx + 14;
    const dotG = this.scene.add.graphics();
    dotG.fillStyle(entry.accent || BTN_BLUE, 1);
    dotG.fillCircle(dotX, ry + rowH / 2, 5);
    rowContainer.add(dotG);

    // Room name
    const nameX = rx + 28;
    const nameText = this.scene.add.text(nameX, ry + rowH / 2, entry.name, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '11px',
      fontStyle: entry.isCurrent ? '700' : '400',
      color: entry.isCurrent ? '#ffffff' : '#c8dce8',
    }).setOrigin(0, 0.5);
    rowContainer.add(nameText);

    // Agent count badge
    if (entry.count !== null && entry.count > 0) {
      const badgeX = rx + rw - 20;
      const badgeG = this.scene.add.graphics();
      badgeG.fillStyle(ACCENT, 0.9);
      badgeG.fillCircle(badgeX, ry + rowH / 2, 9);
      rowContainer.add(badgeG);

      const badgeText = this.scene.add.text(badgeX, ry + rowH / 2, String(entry.count), {
        fontFamily: 'Nunito, sans-serif',
        fontSize: '9px',
        fontStyle: '700',
        color: '#ffffff',
      }).setOrigin(0.5, 0.5);
      rowContainer.add(badgeText);
    }

    // Current room indicator
    if (entry.isCurrent) {
      const youText = this.scene.add.text(rx + rw - 20, ry + rowH / 2, 'HERE', {
        fontFamily: 'Nunito, sans-serif',
        fontSize: '7px',
        fontStyle: '800',
        color: '#88b4d6',
      }).setOrigin(0.5, 0.5);
      rowContainer.add(youText);
    }

    // Make non-current rows clickable
    if (!entry.isCurrent) {
      const hitZone = this.scene.add.zone(rx + rw / 2, ry + rowH / 2, rw, rowH);
      hitZone.setInteractive({ useHandCursor: true });

      hitZone.on('pointerover', () => {
        rowBg.clear();
        rowBg.fillStyle(0xffffff, 0.12);
        rowBg.fillRoundedRect(rx, ry, rw, rowH, 4);
        nameText.setColor('#ffffff');
      });
      hitZone.on('pointerout', () => {
        rowBg.clear();
        rowBg.fillStyle(0xffffff, 0.05);
        rowBg.fillRoundedRect(rx, ry, rw, rowH, 4);
        nameText.setColor('#c8dce8');
      });
      hitZone.on('pointerdown', () => {
        this._navigateTo(entry.id);
      });
      hitZone.setDepth(9996);
      rowContainer.add(hitZone);
    }

    this._container.add(rowContainer);
    return rowContainer;
  }

  /* ================================================================ */
  /*  Navigation                                                       */
  /* ================================================================ */

  _navigateTo(targetRoom) {
    this.close();

    if (targetRoom === this.currentRoom) return;

    this.scene.cameras.main.fadeOut(400, 27, 48, 71);
    this.scene.cameras.main.once('camerafadeoutcomplete', () => {
      if (this.currentRoom === 'lobby') {
        this.socket.joinRoom(targetRoom);
      } else if (targetRoom === 'lobby') {
        this.socket.leaveRoom();
      } else {
        this.socket.joinRoom(targetRoom);
      }
    });
  }

  /* ================================================================ */
  /*  Cleanup                                                          */
  /* ================================================================ */

  destroy() {
    this.close();
    if (this._btn) { this._btn.destroy(); this._btn = null; }
    if (this._keyM) { this._keyM.destroy(); this._keyM = null; }
    if (this._keyEsc) { this._keyEsc.destroy(); this._keyEsc = null; }
  }
}
