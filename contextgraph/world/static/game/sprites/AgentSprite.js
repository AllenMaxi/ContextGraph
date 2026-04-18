/**
 * AgentSprite — Wizard agent using real sprite sheet art.
 *
 * Uses the 2D Game Wizard Character Sprite pack (OGA-BY 3.0)
 * with 3 wizard variants and frame-by-frame animations:
 * idle, walk, attack, hurt.
 *
 * Movement: organic curved wander, walk bob + lean, landing sparkles.
 * Personality: idle behaviors (glancing, spell casting, stretching).
 * Effects: ambient aura, wand trail, expression transitions.
 *
 * Art credit: CraftPix / OpenGameArt — OGA-BY 3.0 License
 */

const COLORS = [
  0x6366f1, 0xf97316, 0x06b6d4, 0xec4899,
  0x10b981, 0xf59e0b, 0xf43f5e, 0x0ea5e9,
  0x8b5cf6, 0x14b8a6, 0x84cc16, 0xd946ef,
];

const WIZARD_TYPES = ['wizard', 'wizard_fire', 'wizard_ice'];

const GLOW_MAP = {
  green:  0x10b981,
  yellow: 0xf59e0b,
  red:    0xef4444,
  gray:   0x64748b,
  blue:   0x3b82f6,
};

const GOLD = 0xd4a54a;

// Display size for the wizard sprite on screen
const SPRITE_W = 64;
const SPRITE_H = 68;

export { COLORS };

export default class AgentSprite extends Phaser.GameObjects.Container {
  constructor(scene, data) {
    const x = data.x || 100;
    const y = data.y || 100;
    super(scene, x, y);

    this.agentId = data.agent_id;
    this.agentName = data.name || data.agent_id;
    this.colorIndex = data.color_index ?? 0;
    this.bodyColor = COLORS[this.colorIndex % COLORS.length];
    this.wizardType = WIZARD_TYPES[this.colorIndex % WIZARD_TYPES.length];
    this.currentExpression = 'happy';
    this.currentGlow = 'gray';
    this.currentActivity = data.activity || 'idle';
    this.anchorId = data.anchor_id || null;
    this.homeAnchorId = data.home_anchor_id || null;
    this.meetingId = data.meeting_id || null;

    this._bubbleTimer = null;
    this._walkTween = null;
    this._bobTween = null;
    this._isWalking = false;
    this._wanderTimer = null;
    this._wanderRadius = 40;
    this._trailEmitter = null;
    this._auraEmitter = null;
    this._idleBehaviorTimer = null;
    this._wanderHomeX = x;
    this._wanderHomeY = y;

    this._build();
    this._setExpression(data.expression || 'happy');
    this._setGlow(data.glow || 'gray');

    if (data.bubble) {
      this.showBubble(data.bubble);
    }

    // Y-sort depth: updated every frame
    this.setDepth(y);

    // Interactivity
    this.setSize(SPRITE_W + 12, SPRITE_H + 34);
    this.setInteractive({ useHandCursor: true });
    this.on('pointerdown', () => {
      scene.events.emit('inspect-agent', data.agent_id);
      window.dispatchEvent(new CustomEvent('inspect-agent', { detail: { agentId: data.agent_id } }));
    });

    this.on('pointerover', () => {
      this.setScale(1.06);
    });
    this.on('pointerout', () => {
      this.setScale(1.0);
    });

    scene.add.existing(this);

    // Start behaviors
    this._startIdleWander();
    this._startIdleBehaviors();
    // Ambient aura removed — clean Habbo aesthetic
  }

  /* ================================================================== */
  /*  Build the character                                                */
  /* ================================================================== */

  _build() {
    // ── Ground shadow ──
    this._shadowGfx = this.scene.add.graphics();
    this._drawShadow();
    this.add(this._shadowGfx);

    // ── Magical aura / glow ring ──
    this._glowGfx = this.scene.add.graphics();
    this._drawGlow(0x64748b);
    this.add(this._glowGfx);

    // ── The actual wizard sprite ──
    const firstFrame = `${this.wizardType}_idle_1`;
    this._sprite = this.scene.add.sprite(0, 0, firstFrame);
    this._sprite.setDisplaySize(SPRITE_W, SPRITE_H);
    this._sprite.setOrigin(0.5, 0.5);
    this.add(this._sprite);

    // Play idle animation
    this._sprite.play(`${this.wizardType}_idle`);

    // ── Name tag ──
    this._nameTagBg = this.scene.add.graphics();
    this.add(this._nameTagBg);

    this._nameTag = this.scene.add.text(0, SPRITE_H / 2 + 20, this.agentName, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '10px',
      fontStyle: 'bold',
      color: '#4b311e',
    }).setOrigin(0.5, 0.5);
    this.add(this._nameTag);
    this._refreshNameTag();
  }

  /* ================================================================== */
  /*  Y-Sort Depth                                                       */
  /* ================================================================== */

  _updateDepth() {
    this.setDepth(this.y);
  }

  /* ================================================================== */
  /*  Organic Idle Wander                                                */
  /* ================================================================== */

  _startIdleWander() {
    if (this._wanderTimer) return;
    this._scheduleWander();
  }

  _scheduleWander() {
    // Longer intervals: 4-12 seconds (feels more natural)
    const delay = 4000 + Math.random() * 8000;
    this._wanderTimer = this.scene.time.delayedCall(delay, () => {
      this._doWander();
    });
  }

  _doWander() {
    if (this._isWalking || this.meetingId) {
      this._scheduleWander();
      return;
    }

    // 30% chance: pause and look around before moving (anticipation)
    const doPause = Math.random() < 0.3;
    const startMove = () => {
      // Pick target within wander radius
      const angle = Math.random() * Math.PI * 2;
      const dist = 15 + Math.random() * this._wanderRadius * 0.5;
      const tx = this._wanderHomeX + Math.cos(angle) * dist;
      const ty = this._wanderHomeY + Math.sin(angle) * dist;

      // Compute a curved path via Bezier midpoint
      const mx = (this.x + tx) / 2;
      const my = (this.y + ty) / 2;
      // Perpendicular offset for the curve
      const dx = tx - this.x;
      const dy = ty - this.y;
      const perpX = -dy;
      const perpY = dx;
      const perpLen = Math.sqrt(perpX * perpX + perpY * perpY) || 1;
      const curveAmount = (Math.random() - 0.5) * 40;
      const midX = mx + (perpX / perpLen) * curveAmount;
      const midY = my + (perpY / perpLen) * curveAmount;

      // Walk through midpoint then to target
      this._wanderCurved(midX, midY, tx, ty);
    };

    if (doPause) {
      // Quick glance before moving
      this._sprite.setFlipX(!this._sprite.flipX);
      this.scene.time.delayedCall(400 + Math.random() * 600, () => {
        this._sprite.setFlipX(!this._sprite.flipX);
        startMove();
      });
    } else {
      startMove();
    }

    this._scheduleWander();
  }

  _wanderCurved(midX, midY, tx, ty) {
    if (this._isWalking) return;

    const totalDist = Phaser.Math.Distance.Between(this.x, this.y, midX, midY)
      + Phaser.Math.Distance.Between(midX, midY, tx, ty);
    const totalDur = Math.max(800, totalDist * 4);

    // Flip sprite based on overall direction
    if (tx < this.x) {
      this._sprite.setFlipX(true);
    } else if (tx > this.x) {
      this._sprite.setFlipX(false);
    }

    this._isWalking = true;
    this._sprite.play(`${this.wizardType}_walk`);
    this._startBob();

    // Lean into walk direction
    const leanAngle = tx < this.x ? -0.04 : 0.04;
    this.scene.tweens.add({
      targets: this._sprite,
      rotation: leanAngle,
      duration: 200,
      ease: 'Sine.easeOut',
    });

    // Phase 1: walk to midpoint
    if (this._walkTween) this._walkTween.stop();
    this._walkTween = this.scene.tweens.add({
      targets: this,
      x: midX, y: midY,
      duration: totalDur * 0.5,
      ease: 'Cubic.easeIn',
      onUpdate: () => this._updateDepth(),
      onComplete: () => {
        // Phase 2: walk to target
        this._walkTween = this.scene.tweens.add({
          targets: this,
          x: tx, y: ty,
          duration: totalDur * 0.5,
          ease: 'Cubic.easeOut',
          onUpdate: () => this._updateDepth(),
          onComplete: () => {
            this._finishWalk();
          },
        });
      },
    });
  }

  _finishWalk() {
    this._isWalking = false;
    this._walkTween = null;
    this._stopBob();
    this._stopTrail();
    this._updateDepth();

    // Lean back to upright
    this.scene.tweens.add({
      targets: this._sprite,
      rotation: 0,
      duration: 150,
      ease: 'Sine.easeOut',
    });

    // Landing sparkle burst
    this._emitLandingSparkle();

    // Return to expression-appropriate animation
    this._setExpression(this.currentExpression);
  }

  _stopIdleWander() {
    if (this._wanderTimer) {
      this._wanderTimer.remove(false);
      this._wanderTimer = null;
    }
  }

  /* ================================================================== */
  /*  Walk Bob (vertical bounce during walking)                          */
  /* ================================================================== */

  _startBob() {
    if (this._bobTween) return;
    this._bobTween = this.scene.tweens.add({
      targets: this._sprite,
      y: { from: 0, to: -2 },
      duration: 150,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
  }

  _stopBob() {
    if (this._bobTween) {
      this._bobTween.stop();
      this._bobTween = null;
      this._sprite.y = 0;
    }
  }

  /* ================================================================== */
  /*  Landing Sparkle                                                    */
  /* ================================================================== */

  _emitLandingSparkle() {
    // Removed
  }

  /* ================================================================== */
  /*  Idle Personality Behaviors                                          */
  /* ================================================================== */

  _startIdleBehaviors() {
    this._scheduleIdleBehavior();
  }

  _scheduleIdleBehavior() {
    const delay = 8000 + Math.random() * 12000;
    this._idleBehaviorTimer = this.scene.time.delayedCall(delay, () => {
      this._doIdleBehavior();
    });
  }

  _doIdleBehavior() {
    if (this._isWalking || this.meetingId) {
      this._scheduleIdleBehavior();
      return;
    }

    const roll = Math.random();

    if (roll < 0.5) {
      // Look around: flip sprite briefly
      this._sprite.setFlipX(!this._sprite.flipX);
      this.scene.time.delayedCall(800 + Math.random() * 400, () => {
        if (!this._isWalking) {
          this._sprite.setFlipX(!this._sprite.flipX);
        }
      });
    } else if (roll < 0.8) {
      // Idle gesture: attack anim (no sparkles)
      this._sprite.play(`${this.wizardType}_attack`);
      this._sprite.once('animationcomplete', () => {
        if (!this._isWalking) {
          this._sprite.play(`${this.wizardType}_idle`);
        }
      });
    } else {
      // Small stretch
      this.scene.tweens.add({
        targets: this._sprite,
        scaleY: this._sprite.scaleY * 1.05,
        duration: 400,
        yoyo: true,
        ease: 'Sine.easeInOut',
      });
    }

    this._scheduleIdleBehavior();
  }

  _stopIdleBehaviors() {
    if (this._idleBehaviorTimer) {
      this._idleBehaviorTimer.remove(false);
      this._idleBehaviorTimer = null;
    }
  }

  /* ================================================================== */
  /*  Ambient Aura (per-character magic emanation)                       */
  /* ================================================================== */

  _startAmbientAura() {
    // Removed — clean Habbo aesthetic
  }

  _stopAmbientAura() {
    if (this._auraEmitter) {
      this._auraEmitter.destroy();
      this._auraEmitter = null;
    }
  }

  /* ================================================================== */
  /*  Magical Aura / Glow                                                */
  /* ================================================================== */

  _drawGlow(color) {
    this._glowGfx.clear();
    this._glowGfx.fillStyle(color, 0.15);
    this._glowGfx.fillEllipse(0, SPRITE_H / 2 + 6, SPRITE_W * 0.8, 16);
  }

  /* ================================================================== */
  /*  Expressions → Animation mapping (with transitions)                 */
  /* ================================================================== */

  setExpression(name) { this._setExpression(name); }

  _setExpression(name) {
    if (!name) return;
    const prev = this.currentExpression;
    this.currentExpression = name;

    // Don't interrupt walk animation
    if (this._isWalking) return;

    // Subtle cross-fade when expression changes
    if (prev !== name) {
      this.scene.tweens.add({
        targets: this._sprite,
        alpha: { from: 0.85, to: 1 },
        duration: 200,
      });
    }

    switch (name) {
      case 'worried':
        this._sprite.play(`${this.wizardType}_hurt`);
        this._sprite.once('animationcomplete', () => {
          if (!this._isWalking) {
            this._sprite.play(`${this.wizardType}_idle`);
          }
        });
        break;
      case 'focused':
      case 'thinking':
        this._sprite.play(`${this.wizardType}_idle_slow`);
        break;
      case 'sleepy':
        this._sprite.play(`${this.wizardType}_idle_slow`);
        break;
      case 'social':
        this._sprite.play(`${this.wizardType}_attack`);
        // Sparkle burst for social expression
        const offsetX = this._sprite.flipX ? -12 : 12;
        if (this.scene.textures.exists('particle_sparkle')) {
          const burst = this.scene.add.particles(this.x + offsetX, this.y - 10, 'particle_sparkle', {
            speed: { min: 10, max: 25 },
            angle: { min: 0, max: 360 },
            scale: { start: 0.4, end: 0 },
            alpha: { start: 0.6, end: 0 },
            lifespan: 400,
            tint: this.bodyColor,
            quantity: 8,
            blendMode: 'ADD',
          }).setDepth(this.y + 1);
          this.scene.time.delayedCall(600, () => burst.destroy());
        }
        this._sprite.once('animationcomplete', () => {
          if (!this._isWalking) {
            this._sprite.play(`${this.wizardType}_idle`);
          }
        });
        break;
      case 'happy':
      default:
        this._sprite.play(`${this.wizardType}_idle`);
        break;
    }
  }

  /* ================================================================== */
  /*  Glow (with smooth transition)                                      */
  /* ================================================================== */

  setGlow(colorName) { this._setGlow(colorName); }

  _setGlow(colorName) {
    const prev = this.currentGlow;
    this.currentGlow = colorName;
    const hex = GLOW_MAP[colorName] || GLOW_MAP.gray;

    if (prev !== colorName) {
      // Smooth transition: fade out → redraw → fade in
      this.scene.tweens.add({
        targets: this._glowGfx,
        alpha: 0,
        duration: 150,
        onComplete: () => {
          this._drawGlow(hex);
          this.scene.tweens.add({
            targets: this._glowGfx,
            alpha: 1,
            duration: 150,
          });
        },
      });
    } else {
      this._drawGlow(hex);
    }
  }

  /* ================================================================== */
  /*  Speech Bubble                                                      */
  /* ================================================================== */

  showBubble(text) {
    this.hideBubble();
    if (!text) return;

    const display = text.length > 60 ? text.substring(0, 57) + '...' : text;
    const bubbleContainer = this.scene.add.container(0, -SPRITE_H / 2 - 14);

    const txt = this.scene.add.text(0, 0, display, {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '11px',
      fontStyle: '600',
      color: '#1e293b',
      wordWrap: { width: 140 },
      align: 'center',
    }).setOrigin(0.5, 1);

    const padX = 14;
    const padY = 10;
    const bw = txt.width + padX * 2;
    const bh = txt.height + padY * 2;

    const bg = this.scene.add.graphics();
    bg.fillStyle(0x000000, 0.15);
    bg.fillRoundedRect(-bw / 2 + 3, -bh + 3, bw, bh, 14);
    bg.fillStyle(0xffffff, 0.98);
    bg.fillRoundedRect(-bw / 2, -bh, bw, bh, 14);
    bg.fillStyle(0xffffff, 0.98);
    bg.fillTriangle(-7, 0, 7, 0, 0, 10);
    bg.lineStyle(1, 0xcccccc, 0.6);
    bg.strokeRoundedRect(-bw / 2, -bh, bw, bh, 14);

    txt.setY(-padY);
    bubbleContainer.add(bg);
    bubbleContainer.add(txt);
    this.add(bubbleContainer);
    this._bubble = bubbleContainer;

    bubbleContainer.setScale(0);
    this.scene.tweens.add({
      targets: bubbleContainer,
      scaleX: 1, scaleY: 1,
      duration: 300,
      ease: 'Back.easeOut',
    });

    this._bubbleTimer = this.scene.time.delayedCall(8000, () => {
      this.hideBubble();
    });
  }

  hideBubble() {
    if (this._bubbleTimer) { this._bubbleTimer.remove(false); this._bubbleTimer = null; }
    if (this._bubble) { this._bubble.destroy(); this._bubble = null; }
  }

  /* ================================================================== */
  /*  Walking trail particles                                            */
  /* ================================================================== */

  _startTrail() {
    // Removed
  }

  _stopTrail() {
    if (this._trailEmitter) {
      this._trailEmitter.destroy();
      this._trailEmitter = null;
    }
  }

  /* ================================================================== */
  /*  Movement                                                           */
  /* ================================================================== */

  moveTo(tx, ty, duration, isWander = false) {
    if (this._walkTween) this._walkTween.stop();

    const dist = Phaser.Math.Distance.Between(this.x, this.y, tx, ty);
    const dur = duration || Math.max(400, dist * 3);

    // Flip sprite based on direction
    if (tx < this.x) {
      this._sprite.setFlipX(true);
    } else if (tx > this.x) {
      this._sprite.setFlipX(false);
    }

    // Play walk animation
    this._isWalking = true;
    if (!isWander) this._startTrail();
    this._sprite.play(`${this.wizardType}_walk`);
    this._startBob();

    // Lean into walk direction
    const leanAngle = tx < this.x ? -0.04 : 0.04;
    this.scene.tweens.add({
      targets: this._sprite,
      rotation: leanAngle,
      duration: 200,
      ease: 'Sine.easeOut',
    });

    this._walkTween = this.scene.tweens.add({
      targets: this,
      x: tx, y: ty,
      duration: dur,
      ease: 'Cubic.easeInOut',
      onUpdate: () => {
        this._updateDepth();
      },
      onComplete: () => {
        this._finishWalk();
      },
    });
  }

  /**
   * Walk along a series of waypoints (anchor positions).
   */
  walkPath(waypoints, speed = 1.0) {
    if (!waypoints || waypoints.length === 0) return;

    this._stopIdleWander();
    this._startTrail();

    const walkNext = (index) => {
      if (index >= waypoints.length) {
        this._finishWalk();
        this._startIdleWander();
        return;
      }

      const wp = waypoints[index];
      const dist = Phaser.Math.Distance.Between(this.x, this.y, wp.x, wp.y);
      const dur = Math.max(300, (dist * 3) / speed);

      if (wp.x < this.x) {
        this._sprite.setFlipX(true);
      } else if (wp.x > this.x) {
        this._sprite.setFlipX(false);
      }

      this._isWalking = true;
      this._sprite.play(`${this.wizardType}_walk`);
      this._startBob();

      const leanAngle = wp.x < this.x ? -0.04 : 0.04;
      this.scene.tweens.add({
        targets: this._sprite,
        rotation: leanAngle,
        duration: 150,
        ease: 'Sine.easeOut',
      });

      if (this._walkTween) this._walkTween.stop();
      this._walkTween = this.scene.tweens.add({
        targets: this,
        x: wp.x, y: wp.y,
        duration: dur,
        ease: 'Cubic.easeInOut',
        onUpdate: () => {
          this._updateDepth();
        },
        onComplete: () => {
          this._walkTween = null;
          this._updateDepth();
          walkNext(index + 1);
        },
      });
    };

    walkNext(0);
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
      this._refreshNameTag();
    }
    if (data.activity !== undefined) {
      this.currentActivity = data.activity;
    }
    if (data.anchor_id !== undefined) {
      this.anchorId = data.anchor_id;
    }
    if (data.home_anchor_id !== undefined) {
      this.homeAnchorId = data.home_anchor_id;
    }
    if (data.meeting_id !== undefined) {
      this.meetingId = data.meeting_id;
    }
    if (data.x !== undefined && data.y !== undefined) {
      this._wanderHomeX = data.x;
      this._wanderHomeY = data.y;
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
    this._stopIdleWander();
    this._stopIdleBehaviors();
    this._stopTrail();
    this._stopBob();
    this._stopAmbientAura();
    if (this._walkTween) this._walkTween.stop();
    super.destroy(true);
  }

  _drawShadow() {
    this._shadowGfx.clear();
    this._shadowGfx.fillStyle(0x000000, 0.18);
    this._shadowGfx.fillEllipse(0, SPRITE_H / 2 + 7, SPRITE_W * 1.04, 22);
    this._shadowGfx.fillStyle(0x000000, 0.28);
    this._shadowGfx.fillEllipse(0, SPRITE_H / 2 + 7, SPRITE_W * 0.84, 16);
  }

  _refreshNameTag() {
    const y = SPRITE_H / 2 + 12;
    const labelW = Math.max(58, this.agentName.length * 7 + 18);

    this._nameTagBg.clear();
    this._nameTagBg.fillStyle(0x000000, 0.16);
    this._nameTagBg.fillRoundedRect(-labelW / 2 + 2, y + 2, labelW, 18, 9);
    this._nameTagBg.fillStyle(0xffffff, 0.92);
    this._nameTagBg.fillRoundedRect(-labelW / 2, y, labelW, 18, 9);
    this._nameTagBg.lineStyle(1, 0xcccccc, 0.4);
    this._nameTagBg.strokeRoundedRect(-labelW / 2, y, labelW, 18, 9);

    this._nameTag.setPosition(0, y + 9);
    this._nameTag.setColor('#4b311e');
  }
}
