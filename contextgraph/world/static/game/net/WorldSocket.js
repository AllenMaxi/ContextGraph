/**
 * WorldSocket — WebSocket client for ContextGraph World.
 * Dispatches received messages as Phaser scene events: `ws:<type>`.
 *
 * Use `setScene(scene)` when transitioning between scenes so events
 * are dispatched to the currently active scene.
 */
export default class WorldSocket {
  constructor(scene) {
    /** @type {Phaser.Scene} */
    this.scene = scene;
    this.ws = null;
    this._key = null;
    this._reconnectTimer = null;
    this._intentionallyClosed = false;
  }

  /**
   * Switch the target scene for event dispatch.
   * Called automatically by scenes that receive the socket.
   */
  setScene(scene) {
    this.scene = scene;
  }

  /* ------------------------------------------------------------------ */
  /*  Connection                                                         */
  /* ------------------------------------------------------------------ */

  connect(key) {
    this._key = key || 'viewer';
    this._intentionallyClosed = false;

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/world?key=${encodeURIComponent(this._key)}`;

    this.ws = new WebSocket(url);

    this.ws.addEventListener('open', () => {
      console.log('[WorldSocket] connected');
      this._emit('ws:open');
    });

    this.ws.addEventListener('message', (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type) {
          this._emit(`ws:${msg.type}`, msg);
        }
      } catch (e) {
        console.warn('[WorldSocket] bad message', e);
      }
    });

    this.ws.addEventListener('close', () => {
      console.log('[WorldSocket] closed');
      this._emit('ws:close');
      if (!this._intentionallyClosed) {
        this._scheduleReconnect();
      }
    });

    this.ws.addEventListener('error', (err) => {
      console.warn('[WorldSocket] error', err);
    });
  }

  /* ------------------------------------------------------------------ */
  /*  Internal emit — always targets the current scene                   */
  /* ------------------------------------------------------------------ */

  _emit(event, data) {
    try {
      if (this.scene && this.scene.events) {
        this.scene.events.emit(event, data);
      }
    } catch (e) {
      // Scene may have been destroyed during transition
      console.warn('[WorldSocket] emit failed', event, e);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Messaging                                                          */
  /* ------------------------------------------------------------------ */

  send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  joinRoom(roomId) {
    this.send({ action: 'join_room', room: roomId });
  }

  leaveRoom() {
    this.send({ action: 'leave_room' });
  }

  /* ------------------------------------------------------------------ */
  /*  Reconnect                                                          */
  /* ------------------------------------------------------------------ */

  _scheduleReconnect() {
    if (this._reconnectTimer) return;
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      console.log('[WorldSocket] reconnecting...');
      this.connect(this._key);
    }, 2000);
  }

  disconnect() {
    this._intentionallyClosed = true;
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
