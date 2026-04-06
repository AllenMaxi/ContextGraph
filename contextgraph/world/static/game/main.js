/**
 * ContextGraph World — Phaser 3 boot and main config.
 */
import WorldSocket from './net/WorldSocket.js';
import LobbyScene from './scenes/LobbyScene.js';
import RoomScene from './scenes/RoomScene.js';
import InspectPanel from './ui/InspectPanel.js';

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

    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x0f172a, 1);
    bg.fillRect(0, 0, W, H);

    // Decorative ring
    bg.lineStyle(2, 0x6366f1, 0.12);
    bg.strokeCircle(W / 2, H / 2 - 20, 80);
    bg.lineStyle(1, 0x6366f1, 0.06);
    bg.strokeCircle(W / 2, H / 2 - 20, 110);

    // Title
    this.add.text(W / 2, H / 2 - 30, 'ContextGraph', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '36px',
      fontStyle: '800',
      color: '#f1f5f9',
    }).setOrigin(0.5, 0.5);

    this.add.text(W / 2, H / 2 + 10, 'World', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '20px',
      fontStyle: '600',
      color: '#6366f1',
    }).setOrigin(0.5, 0.5);

    // Status text
    this._statusText = this.add.text(W / 2, H / 2 + 52, 'Connecting...', {
      fontFamily: 'Nunito, sans-serif',
      fontSize: '14px',
      fontStyle: '600',
      color: '#64748b',
    }).setOrigin(0.5, 0.5);

    // Pulsing dot
    const dot = this.add.graphics();
    dot.fillStyle(0x6366f1, 1);
    dot.fillCircle(W / 2, H / 2 + 80, 4);
    this.tweens.add({
      targets: dot,
      alpha: { from: 1, to: 0.2 },
      duration: 800,
      yoyo: true,
      repeat: -1,
    });

    // Create socket
    this.socket = new WorldSocket(this);
    this.socket.connect('viewer');

    // Listen for world_snapshot to transition
    this.events.on('ws:world_snapshot', (msg) => {
      this._statusText.setText('Entering world...');
      this.time.delayedCall(300, () => {
        this.scene.start('LobbyScene', {
          socket: this.socket,
          snapshot: msg,
        });
      });
    });

    // Handle reconnect feedback
    this.events.on('ws:close', () => {
      if (this._statusText) {
        this._statusText.setText('Reconnecting...');
      }
    });

    this.events.on('ws:open', () => {
      if (this._statusText) {
        this._statusText.setText('Connected! Waiting for data...');
      }
    });
  }
}

/* ================================================================== */
/*  Phaser Config                                                      */
/* ================================================================== */

const config = {
  type: Phaser.AUTO,
  width: 1024,
  height: 768,
  parent: 'game-container',
  backgroundColor: '#0f172a',
  pixelArt: true,
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: [BootScene, LobbyScene, RoomScene],
};

/* ================================================================== */
/*  Launch                                                             */
/* ================================================================== */

const game = new Phaser.Game(config);

// Init the inspect panel (DOM overlay)
const inspectPanel = new InspectPanel();
