/**
 * AgentSprite — Cute penguin-robot agent character.
 *
 * Built entirely with Phaser graphics primitives (no sprite sheets).
 * Each agent has a unique color, expressive face, floating idle animation,
 * speech bubbles, and a status glow.
 */

const COLORS = [
  0x6366f1, 0xf97316, 0x06b6d4, 0xec4899,
  0x10b981, 0xf59e0b, 0xf43f5e, 0x0ea5e9,
  0x8b5cf6, 0x14b8a6, 0x84cc16, 0xd946ef,
];

const GLOW_MAP = {
  green:  0x10b981,
  yellow: 0xf59e0b,
  red:    0xef4444,
  gray:   0x64748b,
  blue:   0x3b82f6,
};

export { COLORS };

export default class AgentSprite extends Phaser.GameObjects.Container {
  /**
   * @param {Phaser.Scene} scene
   * @param {object} data — AgentVisual dict from backend
   */
  constructor(scene, data) {
    const x = data.x || 100;
    const y = data.y || 100;
    super(scene, x, y);

    this.agentId = data.agent_id;
    this.agentName = data.name || data.agent_id;
    this.colorIndex = data.color_index ?? 0;
    this.bodyColor = COLORS[this.colorIndex % COLORS.length];
    this.currentExpression = 'happy';
    this.currentGlow = 'gray';

    this._bubbleTimer = null;
    this._walkTween = null;

    this._build();
    this._setExpression(data.expression || 'happy');
    this._setGlow(data.glow || 'gray');

    if (data.bubble) {
      this.showBubble(data.bubble);
    }

    // Interactivity
    this.setSize(64, 80);
    this.setInteractive({ useHandCursor: true });
    this.on('pointerdown', () => {
      scene.events.emit('inspect-agent', data.agent_id);
      window.dispatchEvent(new CustomEvent('inspect-agent', { detail: { agentId: data.agent_id } }));
    });

    scene.add.existing(this);

    // Idle float animation
    this._startIdleAnimation();
  }

  /* ================================================================== */
  /*  Build the character                                                */
  /* ================================================================== */

  _build() {
    const g = this.scene.add.graphics();
    this._bodyGfx = g;

    // --- Shadow / glow under feet ---
    this._glowGfx = this.scene.add.graphics();
    this._drawGlow(0x64748b);
    this.add(this._glowGfx);

    // --- Feet ---
    this._feetGfx = this.scene.add.graphics();
    this._feetGfx.fillStyle(this._darken(this.bodyColor, 0.6), 1);
    this._feetGfx.fillEllipse(-12, 30, 16, 10);
    this._feetGfx.fillEllipse(12, 30, 16, 10);
    this.add(this._feetGfx);
    this._leftFootBaseY = 30;
    this._rightFootBaseY = 30;

    // --- Body (main ellipse) ---
    g.fillStyle(this.bodyColor, 1);
    g.fillEllipse(0, 0, 52, 58);

    // --- Belly highlight ---
    g.fillStyle(0xffffff, 0.15);
    g.fillEllipse(0, 4, 36, 40);

    // --- Inner belly ---
    g.fillStyle(0xffffff, 0.08);
    g.fillEllipse(0, 6, 26, 30);

    this.add(g);

    // --- Eyes ---
    this._leftEye = this._createEye(-11, -8);
    this._rightEye = this._createEye(11, -8);

    // --- Mouth ---
    this._mouthGfx = this.scene.add.graphics();
    this.add(this._mouthGfx);

    // --- Name tag ---
    this._nameTag = this.scene.add.text(0, 44, this.agentName, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '12px',
      fontStyle: 'bold',
      color: '#e2e8f0',
      stroke: '#0f172a',
      strokeThickness: 3,
    }).setOrigin(0.5, 0);
    this.add(this._nameTag);
  }

  /* ================================================================== */
  /*  Eye helper                                                         */
  /* ================================================================== */

  _createEye(ox, oy) {
    const container = this.scene.add.container(ox, oy);

    // White sclera
    const sclera = this.scene.add.graphics();
    sclera.fillStyle(0xffffff, 1);
    sclera.fillEllipse(0, 0, 16, 18);
    container.add(sclera);

    // Pupil
    const pupil = this.scene.add.graphics();
    pupil.fillStyle(0x1e293b, 1);
    pupil.fillCircle(0, 1, 5);
    container.add(pupil);

    // Shine
    const shine = this.scene.add.graphics();
    shine.fillStyle(0xffffff, 0.9);
    shine.fillCircle(2, -2, 2);
    container.add(shine);

    container._sclera = sclera;
    container._pupil = pupil;
    container._shine = shine;

    this.add(container);
    return container;
  }

  /* ================================================================== */
  /*  Draw glow ellipse                                                  */
  /* ================================================================== */

  _drawGlow(color) {
    this._glowGfx.clear();
    this._glowGfx.fillStyle(color, 0.25);
    this._glowGfx.fillEllipse(0, 34, 56, 14);
    this._glowGfx.fillStyle(color, 0.10);
    this._glowGfx.fillEllipse(0, 34, 72, 20);
  }

  /* ================================================================== */
  /*  Color helper                                                       */
  /* ================================================================== */

  _darken(hex, factor) {
    const r = ((hex >> 16) & 0xff) * factor;
    const g = ((hex >> 8) & 0xff) * factor;
    const b = (hex & 0xff) * factor;
    return (Math.floor(r) << 16) | (Math.floor(g) << 8) | Math.floor(b);
  }

  /* ================================================================== */
  /*  Expressions                                                        */
  /* ================================================================== */

  setExpression(name) {
    this._setExpression(name);
  }

  _setExpression(name) {
    if (!name) return;
    this.currentExpression = name;

    // Reset eyes
    this._resetEye(this._leftEye);
    this._resetEye(this._rightEye);

    switch (name) {
      case 'happy':
        this._drawHappy();
        break;
      case 'worried':
        this._drawWorried();
        break;
      case 'sleepy':
        this._drawSleepy();
        break;
      case 'thinking':
        this._drawThinking();
        break;
      case 'focused':
        this._drawFocused();
        break;
      case 'social':
        this._drawSocial();
        break;
      default:
        this._drawHappy();
    }
  }

  _resetEye(eye) {
    eye._sclera.clear();
    eye._sclera.fillStyle(0xffffff, 1);
    eye._sclera.fillEllipse(0, 0, 16, 18);

    eye._pupil.clear();
    eye._pupil.fillStyle(0x1e293b, 1);
    eye._pupil.fillCircle(0, 1, 5);

    eye._shine.clear();
    eye._shine.fillStyle(0xffffff, 0.9);
    eye._shine.fillCircle(2, -2, 2);

    eye.setScale(1, 1);
  }

  _drawMouth(type) {
    this._mouthGfx.clear();
    this._mouthGfx.lineStyle(2, 0x1e293b, 0.8);

    switch (type) {
      case 'smile': {
        // Cute smile arc
        const curve = new Phaser.Curves.Spline([
          new Phaser.Math.Vector2(-6, 8),
          new Phaser.Math.Vector2(0, 12),
          new Phaser.Math.Vector2(6, 8),
        ]);
        curve.draw(this._mouthGfx, 16);
        break;
      }
      case 'bigsmile': {
        const curve = new Phaser.Curves.Spline([
          new Phaser.Math.Vector2(-8, 7),
          new Phaser.Math.Vector2(0, 14),
          new Phaser.Math.Vector2(8, 7),
        ]);
        curve.draw(this._mouthGfx, 16);
        break;
      }
      case 'frown': {
        const curve = new Phaser.Curves.Spline([
          new Phaser.Math.Vector2(-5, 12),
          new Phaser.Math.Vector2(0, 9),
          new Phaser.Math.Vector2(5, 12),
        ]);
        curve.draw(this._mouthGfx, 16);
        break;
      }
      case 'o': {
        this._mouthGfx.fillStyle(0x1e293b, 0.6);
        this._mouthGfx.fillCircle(0, 10, 3);
        break;
      }
      case 'flat': {
        this._mouthGfx.lineBetween(-4, 10, 4, 10);
        break;
      }
    }
  }

  _drawHappy() {
    this._drawMouth('smile');
  }

  _drawWorried() {
    // Wide eyes
    [this._leftEye, this._rightEye].forEach(eye => {
      eye._sclera.clear();
      eye._sclera.fillStyle(0xffffff, 1);
      eye._sclera.fillEllipse(0, 0, 18, 20);
    });
    this._drawMouth('frown');
  }

  _drawSleepy() {
    // Thin horizontal lines for eyes
    [this._leftEye, this._rightEye].forEach(eye => {
      eye._sclera.clear();
      eye._sclera.fillStyle(0xffffff, 0);
      eye._pupil.clear();
      eye._pupil.lineStyle(2.5, 0x1e293b, 0.7);
      eye._pupil.lineBetween(-6, 0, 6, 0);
      eye._shine.clear();
    });
    this._drawMouth('o');
  }

  _drawThinking() {
    // Pupils shifted right
    [this._leftEye, this._rightEye].forEach(eye => {
      eye._pupil.clear();
      eye._pupil.fillStyle(0x1e293b, 1);
      eye._pupil.fillCircle(3, 0, 5);
      eye._shine.clear();
      eye._shine.fillStyle(0xffffff, 0.9);
      eye._shine.fillCircle(5, -2, 2);
    });
    this._drawMouth('flat');
  }

  _drawFocused() {
    // Slightly squinted
    [this._leftEye, this._rightEye].forEach(eye => {
      eye._sclera.clear();
      eye._sclera.fillStyle(0xffffff, 1);
      eye._sclera.fillEllipse(0, 0, 16, 13);
    });
    this._drawMouth('flat');
  }

  _drawSocial() {
    // Big wide eyes, big smile
    [this._leftEye, this._rightEye].forEach(eye => {
      eye._sclera.clear();
      eye._sclera.fillStyle(0xffffff, 1);
      eye._sclera.fillEllipse(0, 0, 18, 21);
      eye._pupil.clear();
      eye._pupil.fillStyle(0x1e293b, 1);
      eye._pupil.fillCircle(0, 1, 6);
      eye._shine.clear();
      eye._shine.fillStyle(0xffffff, 0.9);
      eye._shine.fillCircle(2, -2, 2.5);
    });
    this._drawMouth('bigsmile');
  }

  /* ================================================================== */
  /*  Glow                                                               */
  /* ================================================================== */

  setGlow(colorName) {
    this._setGlow(colorName);
  }

  _setGlow(colorName) {
    this.currentGlow = colorName;
    const hex = GLOW_MAP[colorName] || GLOW_MAP.gray;
    this._drawGlow(hex);
  }

  /* ================================================================== */
  /*  Speech Bubble                                                      */
  /* ================================================================== */

  showBubble(text) {
    this.hideBubble();

    if (!text) return;

    // Truncate long text
    const display = text.length > 60 ? text.substring(0, 57) + '...' : text;

    const bubbleContainer = this.scene.add.container(0, -48);

    // Measure text
    const txt = this.scene.add.text(0, 0, display, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '11px',
      fontStyle: '600',
      color: '#1e293b',
      wordWrap: { width: 140 },
      align: 'center',
    }).setOrigin(0.5, 1);

    const padX = 12;
    const padY = 8;
    const bw = txt.width + padX * 2;
    const bh = txt.height + padY * 2;

    // Background rounded rect
    const bg = this.scene.add.graphics();
    bg.fillStyle(0xffffff, 0.95);
    bg.fillRoundedRect(-bw / 2, -bh, bw, bh, 10);
    // Triangle pointer
    bg.fillStyle(0xffffff, 0.95);
    bg.fillTriangle(-5, 0, 5, 0, 0, 7);
    // Subtle shadow
    bg.lineStyle(1, 0x94a3b8, 0.3);
    bg.strokeRoundedRect(-bw / 2, -bh, bw, bh, 10);

    txt.setY(-padY);

    bubbleContainer.add(bg);
    bubbleContainer.add(txt);
    this.add(bubbleContainer);

    this._bubble = bubbleContainer;

    // Auto-dismiss
    this._bubbleTimer = this.scene.time.delayedCall(8000, () => {
      this.hideBubble();
    });
  }

  hideBubble() {
    if (this._bubbleTimer) {
      this._bubbleTimer.remove(false);
      this._bubbleTimer = null;
    }
    if (this._bubble) {
      this._bubble.destroy();
      this._bubble = null;
    }
  }

  /* ================================================================== */
  /*  Movement                                                           */
  /* ================================================================== */

  moveTo(tx, ty, duration) {
    if (this._walkTween) {
      this._walkTween.stop();
    }

    const dist = Phaser.Math.Distance.Between(this.x, this.y, tx, ty);
    const dur = duration || Math.max(400, dist * 3);

    // Foot animation during walk
    const footTween = this.scene.tweens.add({
      targets: this._feetGfx,
      angle: { from: -8, to: 8 },
      duration: 150,
      yoyo: true,
      repeat: Math.floor(dur / 300),
      ease: 'Sine.easeInOut',
    });

    this._walkTween = this.scene.tweens.add({
      targets: this,
      x: tx,
      y: ty,
      duration: dur,
      ease: 'Sine.easeInOut',
      onComplete: () => {
        footTween.stop();
        this._feetGfx.setAngle(0);
        this._walkTween = null;
      },
    });
  }

  /* ================================================================== */
  /*  Idle animation                                                     */
  /* ================================================================== */

  _startIdleAnimation() {
    // Subtle breathing / floating
    this.scene.tweens.add({
      targets: this,
      y: this.y - 3,
      duration: 1800 + Math.random() * 400,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
  }

  /* ================================================================== */
  /*  Full state update                                                  */
  /* ================================================================== */

  updateFromData(data) {
    if (data.expression && data.expression !== this.currentExpression) {
      this._setExpression(data.expression);
    }
    if (data.glow && data.glow !== this.currentGlow) {
      this._setGlow(data.glow);
    }
    if (data.bubble) {
      this.showBubble(data.bubble);
    }
    if (data.name) {
      this.agentName = data.name;
      this._nameTag.setText(data.name);
    }

    // Move to new position if changed significantly
    if (data.x !== undefined && data.y !== undefined) {
      const dist = Phaser.Math.Distance.Between(this.x, this.y, data.x, data.y);
      if (dist > 5) {
        this.moveTo(data.x, data.y);
      }
    }
  }

  /* ================================================================== */
  /*  Cleanup                                                            */
  /* ================================================================== */

  destroy() {
    this.hideBubble();
    if (this._walkTween) this._walkTween.stop();
    super.destroy(true);
  }
}
