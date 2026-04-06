/**
 * RoomDoor — Clickable door to enter a project room.
 */
export default class RoomDoor extends Phaser.GameObjects.Container {
  /**
   * @param {Phaser.Scene} scene
   * @param {number} x
   * @param {number} y
   * @param {object} room  — { room_id, name, agent_count }
   */
  constructor(scene, x, y, room) {
    super(scene, x, y);

    this.roomId = room.room_id;
    this.roomName = room.name;
    this._agentCount = room.agent_count || 0;

    this._build();

    scene.add.existing(this);
  }

  _build() {
    const doorW = 72;
    const doorH = 96;

    // Door shadow
    const shadow = this.scene.add.graphics();
    shadow.fillStyle(0x000000, 0.3);
    shadow.fillRoundedRect(-doorW / 2 + 3, -doorH / 2 + 3, doorW, doorH, 8);
    this.add(shadow);

    // Door frame (darker border)
    const frame = this.scene.add.graphics();
    frame.fillStyle(0x334155, 1);
    frame.fillRoundedRect(-doorW / 2 - 3, -doorH / 2 - 3, doorW + 6, doorH + 6, 10);
    this.add(frame);

    // Door body
    this._doorBg = this.scene.add.graphics();
    this._drawDoor(0x475569);
    this.add(this._doorBg);

    // Door knob
    const knob = this.scene.add.graphics();
    knob.fillStyle(0xfbbf24, 1);
    knob.fillCircle(doorW / 2 - 14, 6, 5);
    knob.fillStyle(0xffffff, 0.3);
    knob.fillCircle(doorW / 2 - 13, 4, 2);
    this.add(knob);

    // Door window (arch)
    const window = this.scene.add.graphics();
    window.fillStyle(0x1e293b, 0.6);
    window.fillRoundedRect(-20, -doorH / 2 + 10, 40, 28, { tl: 12, tr: 12, bl: 4, br: 4 });
    // Inner glow
    window.fillStyle(0x6366f1, 0.15);
    window.fillRoundedRect(-16, -doorH / 2 + 14, 32, 20, { tl: 10, tr: 10, bl: 2, br: 2 });
    this.add(window);

    // Room name label above door
    this._label = this.scene.add.text(0, -doorH / 2 - 18, this.roomName, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '12px',
      fontStyle: '700',
      color: '#cbd5e1',
      stroke: '#0f172a',
      strokeThickness: 3,
    }).setOrigin(0.5, 1);
    this.add(this._label);

    // Agent count badge
    this._badge = this.scene.add.container(doorW / 2 - 4, -doorH / 2 - 4);
    this._badgeBg = this.scene.add.graphics();
    this._badgeText = this.scene.add.text(0, 0, '', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '11px',
      fontStyle: '800',
      color: '#ffffff',
    }).setOrigin(0.5, 0.5);
    this._badge.add(this._badgeBg);
    this._badge.add(this._badgeText);
    this.add(this._badge);
    this._updateBadge();

    // Interaction area
    this.setSize(doorW + 10, doorH + 30);
    this.setInteractive({ useHandCursor: true });

    this.on('pointerover', () => {
      this._drawDoor(0x64748b);
      this._label.setColor('#f1f5f9');
    });

    this.on('pointerout', () => {
      this._drawDoor(0x475569);
      this._label.setColor('#cbd5e1');
    });

    this.on('pointerdown', () => {
      this.scene.events.emit('enter-room', this.roomId);
    });
  }

  _drawDoor(color) {
    const doorW = 72;
    const doorH = 96;
    this._doorBg.clear();
    this._doorBg.fillStyle(color, 1);
    this._doorBg.fillRoundedRect(-doorW / 2, -doorH / 2, doorW, doorH, 8);
  }

  setAgentCount(count) {
    this._agentCount = count;
    this._updateBadge();
  }

  _updateBadge() {
    this._badgeBg.clear();
    if (this._agentCount > 0) {
      this._badgeBg.fillStyle(0x6366f1, 1);
      this._badgeBg.fillCircle(0, 0, 11);
      this._badgeText.setText(String(this._agentCount));
      this._badge.setVisible(true);
    } else {
      this._badge.setVisible(false);
    }
  }
}
