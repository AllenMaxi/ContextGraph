/**
 * RoomDoor — Habbo-style simple doorway marker for project room entry.
 * Flat rectangular door with colored accent, clean label, agent count badge.
 */
import { getThemeSpec } from './roomThemes.js';

const HEADER_BG = 0x1B3047;
const DOOR_FRAME = 0x8C6F47;
const DOOR_WOOD = 0x6B4F2E;
const DOOR_DARK = 0x3D2A17;

export default class RoomDoor extends Phaser.GameObjects.Container {
  constructor(scene, x, y, room) {
    super(scene, x, y);

    this.roomId = room.room_id;
    this.roomName = room.name;
    this._agentCount = room.agent_count || 0;
    this._theme = getThemeSpec(room.room_id, room.theme_key);
    this._accent = this._theme.portal;

    this._build();
    this.setDepth(8);
    scene.add.existing(this);
  }

  _build() {
    const doorW = 44;
    const doorH = 64;
    const doorTop = -doorH;

    this._shadow = this.scene.add.graphics();
    this._shadow.fillStyle(0x000000, 0.22);
    this._shadow.fillEllipse(0, 8, doorW + 18, 12);
    this.add(this._shadow);

    this._frame = this.scene.add.graphics();
    this.add(this._frame);

    this._door = this.scene.add.graphics();
    this.add(this._door);

    this._drawDoor(1);

    this._plaque = this.scene.add.graphics();
    this.add(this._plaque);

    this._label = this.scene.add.text(0, doorTop - 12, this.roomName, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '10px',
      fontStyle: '700',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    this.add(this._label);

    this._drawPlaque(false);

    this._badge = this.scene.add.container(doorW / 2 + 4, doorTop + 8);
    this._badgeBg = this.scene.add.graphics();
    this._badgeText = this.scene.add.text(0, 0, '', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '9px',
      fontStyle: '800',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    this._badge.add(this._badgeBg);
    this._badge.add(this._badgeText);
    this.add(this._badge);
    this._updateBadge();

    this.setSize(doorW + 20, doorH + 40);
    this.setInteractive({ useHandCursor: true });

    this.on('pointerover', () => {
      this._drawDoor(1.15);
      this._drawPlaque(true);
      this.setScale(1.05);
    });

    this.on('pointerout', () => {
      this._drawDoor(1);
      this._drawPlaque(false);
      this.setScale(1);
    });

    this.on('pointerdown', () => {
      console.log('[RoomDoor] click →', this.roomId, '(name:', this.roomName + ')');
      this.scene.events.emit('enter-room', this.roomId);
    });
  }

  _drawDoor(intensity) {
    const doorW = 44;
    const doorH = 64;
    const doorTop = -doorH;

    this._frame.clear();
    this._frame.fillStyle(DOOR_FRAME, 1);
    this._frame.fillRoundedRect(-doorW / 2 - 3, doorTop - 3, doorW + 6, doorH + 3, { tl: 6, tr: 6, bl: 0, br: 0 });
    this._frame.lineStyle(1, DOOR_DARK, 0.6);
    this._frame.strokeRoundedRect(-doorW / 2 - 3, doorTop - 3, doorW + 6, doorH + 3, { tl: 6, tr: 6, bl: 0, br: 0 });

    this._door.clear();
    this._door.fillStyle(DOOR_WOOD, 1);
    this._door.fillRoundedRect(-doorW / 2, doorTop, doorW, doorH, { tl: 4, tr: 4, bl: 0, br: 0 });

    this._door.fillStyle(this._accent, 0.85 * intensity);
    this._door.fillRoundedRect(-doorW / 2, doorTop, doorW, 10, { tl: 4, tr: 4, bl: 0, br: 0 });

    this._door.lineStyle(1, DOOR_DARK, 0.5);
    this._door.strokeRect(-doorW / 2 + 6, doorTop + 16, doorW - 12, doorH - 22);

    this._door.fillStyle(0xE9AD58, 0.95);
    this._door.fillCircle(doorW / 2 - 8, doorTop + doorH / 2 + 4, 2.5);
  }

  _drawPlaque(isHovered = false) {
    this._plaque.clear();
    const labelW = Math.max(72, this.roomName.length * 6 + 16);
    const plaqueY = -86;

    this._plaque.fillStyle(0x000000, 0.3);
    this._plaque.fillRoundedRect(-labelW / 2 + 1, plaqueY + 1, labelW, 18, 3);
    this._plaque.fillStyle(HEADER_BG, isHovered ? 1 : 0.92);
    this._plaque.fillRoundedRect(-labelW / 2, plaqueY, labelW, 18, 3);
    this._plaque.fillStyle(this._accent, isHovered ? 0.9 : 0.7);
    this._plaque.fillRect(-labelW / 2, plaqueY, 3, 18);
    this._label.setPosition(0, plaqueY + 9);
  }

  setAgentCount(count) {
    this._agentCount = count;
    this._updateBadge();
  }

  _updateBadge() {
    this._badgeBg.clear();
    if (this._agentCount > 0) {
      this._badgeBg.fillStyle(0xE9AD58, 0.98);
      this._badgeBg.fillCircle(0, 0, 9);
      this._badgeBg.lineStyle(1.5, HEADER_BG, 0.8);
      this._badgeBg.strokeCircle(0, 0, 9);
      this._badgeText.setText(String(this._agentCount));
      this._badge.setVisible(true);
    } else {
      this._badge.setVisible(false);
    }
  }
}
