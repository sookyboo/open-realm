/* Optional OpenRealm browser multiplayer. Inspired by HCE-Mobile's (CC0)
 * encrypted MQTT signalling + WebRTC DataChannel virtual LAN, but with a
 * host-only topology and OpenRealm's existing Online_* service interface.
 * No Warcraft protocol messages are interpreted here. */
'use strict';
(function (global) {
  const RING_SIZE = 2 * 1024 * 1024;
  const HEADER = 40;
  const MAX_PACKET = 256 * 1024;
  const FRAGMENT = 12 * 1024;
  const MAX_BUFFERED = 4 * 1024 * 1024;
  const FLOW_HIGH = 96 * 1024; // bytes; prevent ordered snapshot latency growing indefinitely
  const FLOW_LOW = 24 * 1024; // bytes; hysteresis prevents per-frame pause/resume chatter
  const MAX_MQTT = 128 * 1024;
  const ROOM_LIMIT = 24;
  const CONTROL_RESERVE = 64 * 1024; // Reserve ring space for disconnect/failure events.
  const MAX_CONTROLS = 256; // Bounded retry mailbox for main-thread to engine events.
  const CONNECT_TIMEOUT = 30000; // ms; no answer or channel-open confirmation.
  const DISCONNECT_GRACE = 15000; // ms; ICE transient disconnection allowance.
  const HOST_PUBLISH_INTERVAL = 8000; // ms; keep listings fresh (<16s expiry).
  const RECORD = { PACKET: 1, READY: 2, GAME: 3, CONNECTED: 4, CLOSED: 5,
    ROOM_CLOSED: 6, HOST_READY: 7, FAILED: 8, CLEAR_GAMES: 9,
    DROP_PEER: 10, FLOW_PAUSE: 11, FLOW_RESUME: 12 };
  // All participants must use the same broker: independent MQTT brokers
  // are not bridged. Production deployments should configure one endpoint.
  const DEFAULT_BROKERS = ['wss://broker.emqx.io:8084/mqtt'];
  const DEFAULT_ICE = [{ urls: ['stun:stun.cloudflare.com:3478', 'stun:stun.l.google.com:19302'] }];
  const cfg = global.OPENREALM_WEB_MULTIPLAYER_CONFIG || {};
  const brokers = Array.isArray(cfg.brokers) && cfg.brokers.length ? cfg.brokers : DEFAULT_BROKERS;
  const iceServers = cfg.iceServers || DEFAULT_ICE;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const state = {
    id: hex(16), code: '', key: null, topic: '', active: false, ready: false,
    broker: null, brokerIndex: 0, ping: null, retry: null, heartbeat: null,
    generation: 0, shared: null, pump: null, seen: new Set(),
    peers: new Map(), games: new Map(), hostId: '', hosting: false,
    hosted: null, admissionClosed: false, messageId: 0, pendingIce: new Map(),
    status: 'Create a room or enter an invitation code.',
    controls: [], hostRevision: 0, publishedRevision: 0, lastPublished: 0,
    publishing: false,
  };

  function hex(size) {
    return Array.from(crypto.getRandomValues(new Uint8Array(size)),
      b => b.toString(16).padStart(2, '0')).join('');
  }
  function roomCode() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    const random = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(random, b => chars[b & 31]).join('');
  }
  function normalize(code) {
    code = String(code || '').trim().toUpperCase().replace(/[\s-]/g, '');
    if (!/^[A-Z2-9]{16}$/.test(code) || /[IO01]/.test(code)) throw Error('Expected a 16-character room code.');
    return code;
  }
  function shortText(text, len) {
    return String(text || '').replace(/[\x00-\x1f\x7f]/g, ' ').slice(0, len);
  }
  function updateStatus(text) {
    state.status = text;
    const element = document.getElementById('web-multiplayer-status');
    if (element) element.textContent = text;
    const badge = document.getElementById('web-multiplayer-code');
    if (badge) badge.textContent = state.code || 'Not selected';
  }
  function currentBuffer() {
    /* Emscripten refreshes HEAP32 if pthread Wasm memory grows. */
    return global.Module && global.Module.HEAP32 && global.Module.HEAP32.buffer;
  }
  function ring(index) {
    if (!state.shared) return null;
    const buffer = currentBuffer();
    if (!(buffer instanceof SharedArrayBuffer)) return null;
    return { bytes: new Uint8Array(buffer), words: new Int32Array(buffer),
      base: index ? state.shared.from : state.shared.to,
      data: state.shared.dataOffset, size: state.shared.size };
  }
  function load32(r, offset) { return Atomics.load(r.words, (r.base + offset) / 4) >>> 0; }
  function store32(r, offset, value) { Atomics.store(r.words, (r.base + offset) / 4, value | 0); }
  function copyRing(r, position, input) {
    const start = position & (r.size - 1);
    const base = r.base + r.data;
    const first = Math.min(input.length, r.size - start);
    r.bytes.set(input.subarray(0, first), base + start);
    if (first < input.length) r.bytes.set(input.subarray(first), base);
  }
  function readRing(r, position, length) {
    const result = new Uint8Array(length);
    const start = position & (r.size - 1);
    const base = r.base + r.data;
    const first = Math.min(length, r.size - start);
    result.set(r.bytes.subarray(base + start, base + start + first));
    if (first < length) result.set(r.bytes.subarray(base, base + length - first), first);
    return result;
  }
  /* A gameplay packet must never consume the last reserved capacity needed
   * for a CLOSED/FAILED notification. Control records retry in FIFO order on
   * the next pump rather than disappearing when the shared ring is full. */
  function writeRecord(entry, reserve = 0) {
    const r = ring(1);
    if (!r) return false;
    const bytes = entry.payload || new Uint8Array(0);
    const length = HEADER + bytes.length;
    const read = load32(r, 0), write = load32(r, 4);
    const occupied = (write - read) >>> 0;
    if (length + reserve > r.size || occupied > r.size ||
        length + reserve > r.size - occupied) return false;
    const header = new Uint8Array(HEADER);
    new DataView(header.buffer).setUint32(0, length, true);
    header[4] = entry.kind; header[5] = entry.source;
    if (/^[0-9a-f]{32}$/.test(entry.peerId)) header.set(encoder.encode(entry.peerId), 8);
    copyRing(r, write, header);
    if (bytes.length) copyRing(r, write + HEADER, bytes);
    store32(r, 4, (write + length) >>> 0);
    return true;
  }
  function flushControls() {
    while (state.controls.length && writeRecord(state.controls[0])) state.controls.shift();
  }
  function record(kind, peerId = '', payload = null, source = 0) {
    const entry = { kind, peerId, payload, source };
    if (kind === RECORD.PACKET) {
      flushControls();
      // Packet overflow is fatal to the peer, not an acceptable lost message.
      return !state.controls.length && writeRecord(entry, CONTROL_RESERVE);
    }
    flushControls();
    if (!state.controls.length && writeRecord(entry)) return true;
    if (state.controls.length >= MAX_CONTROLS) {
      updateStatus('Browser control queue exhausted; leave and reload the room.');
      return false;
    }
    state.controls.push(entry);
    return true;
  }
  function pump() {
    flushControls();
    const r = ring(0);
    if (!r) return;
    let read = load32(r, 0);
    const write = load32(r, 4);
    let processed = 0;
    while (read !== write && processed++ < 128) {
      if ((write - read >>> 0) < HEADER) break;
      const header = readRing(r, read, HEADER);
      const view = new DataView(header.buffer);
      const length = view.getUint32(0, true);
      if (length < HEADER || length > MAX_PACKET + HEADER || length > (write - read >>> 0)) {
        read = write;
        updateStatus('Browser network queue contained a malformed record.');
        break;
      }
      if (header[4] === RECORD.DROP_PEER) {
        const peerId = decoder.decode(header.subarray(8, 40));
        const peer = state.peers.get(peerId);
        if (peer) dropPeer(peer, 'Engine rejected browser packet stream.');
      } else if (header[4] === RECORD.PACKET && (header[5] === 0 || header[5] === 1)) {
        const peerId = decoder.decode(header.subarray(8, 40));
        const peer = state.peers.get(peerId);
        if (peer && peer.open && ((state.hosting && header[5] === 1) ||
                                   (!state.hosting && header[5] === 0))) {
          const packet = readRing(r, read + HEADER, length - HEADER);
          peer.queued.push({ bytes: packet, source: header[5] });
          peer.queuedBytes += packet.length;
          if (peer.queuedBytes > MAX_BUFFERED) dropPeer(peer, 'Outgoing network queue overflow.');
        }
      }
      read = (read + length) >>> 0;
    }
    store32(r, 0, read);
    flushControls();
    for (const peer of state.peers.values()) flushPeer(peer);
  }
  function attach(_unusedBuffer, to, from, dataOffset, size, stride) {
    if (size !== RING_SIZE || stride !== size + dataOffset ||
        to % 4 || from % 4 || dataOffset % 4) throw Error('Invalid OpenRealm network ring layout.');
    state.shared = { to, from, dataOffset, size };
    flushControls();
    if (!state.pump) state.pump = setInterval(pump, 4);
    record(RECORD.READY, '', new Uint8Array([state.ready ? 1 : 0]));
    if (state.hosting && state.ready) record(RECORD.HOST_READY);
    for (const game of state.games.values()) announceGame(game);
  }

  async function derive(code) {
    const raw = encoder.encode(code);
    const material = await crypto.subtle.importKey('raw', raw, 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({ name: 'PBKDF2',
      salt: encoder.encode('openrealm-browser-room-v1'), iterations: 100000, hash: 'SHA-256' },
      material, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256',
      encoder.encode('openrealm-browser-topic-v1:' + code)));
    return { key, topic: 'openrealm/web/v1/' + hexBytes(digest.subarray(0, 16)) };
  }
  function hexBytes(bytes) { return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join(''); }
  async function encrypt(message) {
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce },
      state.key, encoder.encode(JSON.stringify(message))));
    const result = new Uint8Array(nonce.length + cipher.length);
    result.set(nonce); result.set(cipher, nonce.length);
    return result;
  }
  async function decrypt(payload) {
    if (payload.length < 29 || payload.length > MAX_MQTT) return null;
    try {
      const bytes = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: payload.subarray(0, 12) },
        state.key, payload.subarray(12));
      return JSON.parse(decoder.decode(bytes));
    } catch (_) { return null; }
  }
  function mqttString(value) {
    const bytes = encoder.encode(value);
    if (bytes.length > 65535) throw Error('MQTT string too long.');
    return new Uint8Array([bytes.length >>> 8, bytes.length & 255, ...bytes]);
  }
  function packet(type, chunks) {
    const bodySize = chunks.reduce((sum, b) => sum + b.length, 0);
    let rest = bodySize, length = [];
    do { let b = rest % 128; rest = Math.floor(rest / 128); if (rest) b |= 128; length.push(b); } while (rest);
    const bytes = new Uint8Array(1 + length.length + bodySize);
    bytes[0] = type; bytes.set(length, 1);
    let p = length.length + 1;
    for (const chunk of chunks) { bytes.set(chunk, p); p += chunk.length; }
    return bytes;
  }
  function publishRaw(payload) {
    const b = state.broker;
    if (!b || !b.subscribed || b.socket.readyState !== WebSocket.OPEN) return false;
    b.socket.send(packet(0x30, [mqttString(state.topic), payload]));
    return true;
  }
  async function signal(message) {
    if (!state.ready || !state.key) return false;
    const epoch = state.generation;
    const payload = await encrypt({ ...message, from: state.id, nonce: hex(12) });
    return epoch === state.generation && publishRaw(payload);
  }
  function reportReady(ready) {
    if (state.ready === ready) return;
    state.ready = ready;
    record(RECORD.READY, '', new Uint8Array([ready ? 1 : 0]));
    updateStatus(ready ? 'Room connected. Open Internet Games inside OpenRealm.' :
      'Signalling unavailable; retrying broker connection.');
    if (ready) {
      signal({ type: 'hello' });
      if (state.hosted) publishHost(true);
    }
  }
  function connectBroker(epoch) {
    if (!state.active || !state.code || epoch !== state.generation) return;
    const url = brokers[state.brokerIndex++ % brokers.length];
    if (typeof url !== 'string' || !url.startsWith('wss://')) {
      updateStatus('Configured MQTT broker must use wss://.'); return;
    }
    const b = { socket: null, subscribed: false, buffer: new Uint8Array(0) };
    state.broker = b;
    try { b.socket = new WebSocket(url, 'mqtt'); } catch (_) { reconnect(epoch); return; }
    b.socket.binaryType = 'arraybuffer';
    b.socket.onopen = () => {
      b.socket.send(packet(0x10, [mqttString('MQTT'), new Uint8Array([4, 2, 0, 45]),
        mqttString('or-' + hex(8))]));
    };
    b.socket.onmessage = event => {
      if (epoch !== state.generation || b !== state.broker) return;
      const input = new Uint8Array(event.data);
      if (b.buffer.length + input.length > MAX_MQTT) { b.socket.close(); return; }
      const bytes = new Uint8Array(b.buffer.length + input.length);
      bytes.set(b.buffer); bytes.set(input, b.buffer.length);
      b.buffer = bytes;
      while (b.buffer.length >= 2) {
        let length = 0, factor = 1, pos = 1, digit;
        do {
          if (pos >= b.buffer.length) return;
          digit = b.buffer[pos++]; length += (digit & 127) * factor; factor *= 128;
          if (pos > 5 || length > MAX_MQTT) { b.socket.close(); return; }
        } while (digit & 128);
        if (b.buffer.length < pos + length) break;
        const type = b.buffer[0] & 0xF0;
        const body = b.buffer.slice(pos, pos + length);
        const flags = b.buffer[0] & 0x0F;
        b.buffer = b.buffer.slice(pos + length);
        if (type === 0x20 && body.length >= 2 && body[1] === 0) {
          b.socket.send(packet(0x82, [new Uint8Array([0, 1]), mqttString(state.topic), new Uint8Array([0])]));
        } else if (type === 0x90 && body.length >= 3 && body[2] !== 0x80) {
          b.subscribed = true; reportReady(true);
        } else if (type === 0x30 && body.length >= 2) {
          const topicLen = (body[0] << 8) | body[1];
          const offset = topicLen + 2 + ((flags & 6) ? 2 : 0);
          if (offset <= body.length && decoder.decode(body.subarray(2, 2 + topicLen)) === state.topic)
            receiveSignal(body.subarray(offset), epoch);
        }
      }
    };
    b.socket.onerror = () => {};
    b.socket.onclose = () => {
      if (b !== state.broker) return;
      state.broker = null;
      clearInterval(state.ping); state.ping = null;
      reportReady(false);
      reconnect(epoch);
    };
    state.ping = setInterval(() => {
      if (b.socket.readyState === WebSocket.OPEN && b.subscribed)
        b.socket.send(new Uint8Array([0xC0, 0]));
    }, 25000);
  }
  function reconnect(epoch) {
    clearTimeout(state.retry);
    if (epoch === state.generation && state.active)
      state.retry = setTimeout(() => connectBroker(epoch), 4000);
  }
  async function receiveSignal(payload, epoch) {
    const message = await decrypt(payload);
    if (epoch !== state.generation || !message || message.from === state.id ||
        !/^[0-9a-f]{32}$/.test(message.from) ||
        !/^[0-9a-f]{24}$/.test(message.nonce) ||
        state.seen.has(message.from + message.nonce) ||
        (message.to && message.to !== state.id)) return;
    state.seen.add(message.from + message.nonce);
    if (state.seen.size > 2048) state.seen.clear();
    try { await handleSignal(message); } catch (err) {
      /* Failed SDP/ICE operations must close the peer so the join attempt
       * terminates instead of remaining stuck in Connecting forever. */
      const peer = state.peers.get(message.from);
      if (peer && ['offer', 'answer', 'ice'].includes(message.type))
        dropPeer(peer, 'Browser signalling negotiation failed.');
      console.warn('OpenRealm signalling message rejected:', err);
    }
  }

  function announceGame(game) {
    if (!game || !/^[0-9a-f]{32}$/.test(game.id)) return;
    const data = new Uint8Array(176);
    data.set(encoder.encode(shortText(game.name, 79)).subarray(0, 79), 0);
    data.set(encoder.encode(shortText(game.map, 79)).subarray(0, 79), 80);
    const v = new DataView(data.buffer);
    v.setUint32(160, game.players >>> 0, true);
    v.setUint32(164, game.slots >>> 0, true);
    v.setUint32(168, game.speed >>> 0, true);
    v.setUint32(172, game.crc >>> 0, true);
    record(RECORD.GAME, game.id, data);
  }
  function rebuildGameList() {
    record(RECORD.CLEAR_GAMES);
    for (const game of state.games.values()) announceGame(game);
  }
  function publishHost(force = false) {
    if (!state.hosted || !state.ready || state.publishing) return;
    const now = Date.now();
    if (!force && state.publishedRevision === state.hostRevision &&
        now - state.lastPublished < HOST_PUBLISH_INTERVAL) return;
    const epoch = state.generation, revision = state.hostRevision;
    const advertised = { type: 'host', ...state.hosted, closed: state.admissionClosed };
    state.publishing = true;
    signal(advertised).then(sent => {
      if (epoch !== state.generation) return;
      if (sent) {
        state.lastPublished = Date.now();
        state.publishedRevision = revision;
        if (!state.admissionClosed && revision === state.hostRevision) record(RECORD.HOST_READY);
      }
    }).catch(() => updateStatus('Could not publish browser lobby.')).finally(() => {
      if (epoch === state.generation) state.publishing = false;
    });
  }
  function acceptHost(message) {
    if (state.hosting || message.closed ||
        typeof message.map !== 'string' || !message.map || message.map.length > 79 ||
        typeof message.name !== 'string' || message.name.length > 79 ||
        !Number.isInteger(message.crc) || !Number.isInteger(message.slots) ||
        message.slots < 1 || message.slots > ROOM_LIMIT ||
        !Number.isInteger(message.players) || message.players < 0 || message.players > message.slots ||
        !Number.isInteger(message.speed)) return;
    const game = { id: message.from, map: message.map, name: message.name,
      crc: message.crc, slots: message.slots, players: message.players,
      speed: message.speed, heard: Date.now() };
    state.games.set(message.from, game);
    announceGame(game);
  }
  function createPeer(id) {
    if (state.peers.has(id)) dropPeer(state.peers.get(id));
    const pc = new RTCPeerConnection({ iceServers });
    const peer = { id, pc, channel: pc.createDataChannel('openrealm',
      { negotiated: true, id: 0, ordered: true }), pending: [], open: false,
      queued: [], queuedBytes: 0, incoming: null, lastMessage: Date.now(),
      started: Date.now(), disconnectedAt: null, flowPaused: false,
      sentPackets: 0, receivedPackets: 0 };
    /* queued is the bounded C-to-JS packet queue; queue stores pending fragments. */
    state.peers.set(id, peer);
    peer.channel.binaryType = 'arraybuffer';
    peer.channel.onopen = () => {
      if (state.peers.get(id) !== peer) return;
      peer.open = true;
      peer.disconnectedAt = null;
      record(RECORD.CONNECTED, id);
      flushPeer(peer);
      updateStatus('Connected to browser player.');
    };
    peer.channel.onmessage = event => {
      if (state.peers.get(id) !== peer || !peer.open) return;
      peer.lastMessage = Date.now();
      onFragment(peer, new Uint8Array(event.data));
    };
    peer.channel.onclose = () => dropPeer(peer);
    pc.onconnectionstatechange = () => {
      if (state.peers.get(id) !== peer) return; // Ignore callbacks from replaced connections.
      if (pc.connectionState === 'failed') dropPeer(peer, 'Browser peer negotiation failed.');
      else if (pc.connectionState === 'closed') dropPeer(peer);
      else if (pc.connectionState === 'disconnected' && peer.disconnectedAt === null)
        peer.disconnectedAt = Date.now();
      else if (pc.connectionState === 'connected') peer.disconnectedAt = null;
    };
    pc.onicecandidate = event => {
      if (event.candidate) signal({ type: 'ice', to: id, candidate: event.candidate.toJSON() });
    };
    return peer;
  }
  function dropPeer(peer, error) {
    if (state.peers.get(peer.id) !== peer) return;
    state.peers.delete(peer.id);
    peer.open = false;
    try { peer.channel.close(); } catch (_) { /* already closed */ }
    try { peer.pc.close(); } catch (_) { /* already closed */ }
    /* Error events are terminal for a joining browser, while ordinary close
     * events are still sent to the server to reap a connected player slot. */
    record(error ? RECORD.FAILED : RECORD.CLOSED, peer.id);
    if (error) updateStatus(error);
  }
  function updatePeerFlow(peer) {
    if (!peer.open || peer.channel.readyState !== 'open') return;
    const pending = peer.queuedBytes + peer.channel.bufferedAmount;
    if (!peer.flowPaused && pending >= FLOW_HIGH) {
      if (record(RECORD.FLOW_PAUSE, peer.id)) peer.flowPaused = true;
    } else if (peer.flowPaused && pending <= FLOW_LOW) {
      if (record(RECORD.FLOW_RESUME, peer.id)) peer.flowPaused = false;
    }
  }
  function flushPeer(peer) {
    if (!peer.open || peer.channel.readyState !== 'open') return;
    /* Keep only a small amount in the ordered DataChannel: once queued,
     * old snapshots cannot be discarded without breaking delta bases. */
    while (peer.queued.length && peer.channel.bufferedAmount < FLOW_HIGH) {
      const next = peer.queued.shift();
      peer.queuedBytes -= next.bytes.length;
      const messageId = ++state.messageId >>> 0;
      for (let pos = 0; pos < next.bytes.length; pos += FRAGMENT) {
        const payload = next.bytes.subarray(pos, pos + FRAGMENT);
        const frame = new Uint8Array(payload.length + 13);
        const v = new DataView(frame.buffer);
        v.setUint32(0, next.bytes.length, true);
        v.setUint32(4, messageId, true);
        v.setUint32(8, pos, true);
        frame[12] = next.source;
        frame.set(payload, 13);
        peer.channel.send(frame);
      }
      peer.sentPackets++;
    }
    updatePeerFlow(peer);
    if (peer.channel.bufferedAmount > MAX_BUFFERED) dropPeer(peer, 'Browser network congestion.');
  }
  function onFragment(peer, frame) {
    if (state.peers.get(peer.id) !== peer || !peer.open || frame.length <= 13) return;
    const view = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
    const total = view.getUint32(0, true), id = view.getUint32(4, true);
    const offset = view.getUint32(8, true), source = frame[12];
    const expectedSource = state.hosting ? 0 : 1;
    if (!total || total > MAX_PACKET || source !== expectedSource ||
        offset + frame.length - 13 > total) { dropPeer(peer, 'Invalid browser game packet.'); return; }
    if (!peer.incoming || peer.incoming.id !== id) {
      if (offset !== 0 || (peer.incoming && peer.incoming.received !== peer.incoming.total)) {
        dropPeer(peer, 'Incomplete browser game packet.'); return;
      }
      peer.incoming = { id, total, received: 0, bytes: new Uint8Array(total) };
    }
    const item = peer.incoming;
    if (offset !== item.received || item.total !== total) { dropPeer(peer, 'Out-of-order browser packet.'); return; }
    item.bytes.set(frame.subarray(13), offset);
    item.received += frame.length - 13;
    if (item.received === total) {
      peer.incoming = null;
      peer.receivedPackets++;
      if (!record(RECORD.PACKET, peer.id, item.bytes, state.hosting ? 1 : 0))
        dropPeer(peer, 'Browser receive queue overflow.');
    }
  }
  async function handleSignal(message) {
    if (message.type === 'hello' || message.type === 'request') {
      if (state.hosted && !state.admissionClosed) publishHost();
      return;
    }
    if (message.type === 'host') {
      if (message.closed) {
        if (state.games.delete(message.from)) rebuildGameList();
      } else acceptHost(message);
      return;
    }
    if (message.type === 'bye') {
      const peer = state.peers.get(message.from);
      if (peer) dropPeer(peer);
      if (state.games.delete(message.from)) rebuildGameList();
      if (!state.hosting && message.from === state.hostId) record(RECORD.ROOM_CLOSED);
      return;
    }
    if (message.type === 'offer') {
      if (!state.hosting || state.admissionClosed || state.peers.size >= ROOM_LIMIT - 1 ||
          typeof message.sdp !== 'string' || message.sdp.length > 20000) return;
      const peer = createPeer(message.from);
      peer.pending.push(...(state.pendingIce.get(peer.id) || []));
      state.pendingIce.delete(peer.id);
      await peer.pc.setRemoteDescription({ type: 'offer', sdp: message.sdp });
      for (const candidate of peer.pending.splice(0)) await peer.pc.addIceCandidate(candidate).catch(() => {});
      const answer = await peer.pc.createAnswer();
      await peer.pc.setLocalDescription(answer);
      signal({ type: 'answer', to: peer.id, sdp: peer.pc.localDescription.sdp });
    } else if (message.type === 'answer') {
      const peer = state.peers.get(message.from);
      if (!peer || peer.pc.signalingState !== 'have-local-offer' ||
          typeof message.sdp !== 'string' || message.sdp.length > 20000) return;
      await peer.pc.setRemoteDescription({ type: 'answer', sdp: message.sdp });
      for (const candidate of peer.pending.splice(0)) await peer.pc.addIceCandidate(candidate).catch(() => {});
    } else if (message.type === 'ice') {
      const peer = state.peers.get(message.from);
      if (!message.candidate || typeof message.candidate.candidate !== 'string' ||
          message.candidate.candidate.length > 4096) return;
      if (!peer) {
        if (!state.hosting || state.pendingIce.size > ROOM_LIMIT) return;
        const pending = state.pendingIce.get(message.from) || [];
        if (pending.length < 32) pending.push(message.candidate);
        state.pendingIce.set(message.from, pending);
      } else if (peer.pc.remoteDescription) await peer.pc.addIceCandidate(message.candidate).catch(() => {});
      else if (peer.pending.length < 32) peer.pending.push(message.candidate);
    }
  }

  async function setupRoom(code) {
    const epoch = ++state.generation;
    state.ready = false;
    state.controls = state.controls.filter(item => item.kind === RECORD.ROOM_CLOSED);
    state.seen.clear(); state.games.clear(); state.pendingIce.clear();
    record(RECORD.CLEAR_GAMES);
    for (const peer of [...state.peers.values()]) dropPeer(peer);
    state.hostRevision = state.publishedRevision = state.lastPublished = 0;
    state.publishing = false;
    state.hosting = false; state.hostId = ''; state.hosted = null; state.admissionClosed = false;
    const { key, topic } = await derive(code);
    if (epoch !== state.generation) return;
    state.code = code; state.key = key; state.topic = topic;
    if (state.active) connectBroker(epoch);
    updateStatus('Room selected. Open Internet Games inside OpenRealm.');
  }
  async function selectRoom(code) {
    code = normalize(code);
    const changed = state.code !== code;
    if (changed) {
      const wasActive = state.active;
      shutdownSignalling(false);
      await setupRoom(code);
      if (wasActive) { activate(); setHeartbeat(); }
    }
    updateStatus('Invitation code: ' + code);
    return code;
  }
  function activate() {
    state.active = true;
    if (state.code && !state.broker) connectBroker(state.generation);
    else if (!state.code) updateStatus('Create or enter a room code above before hosting/joining.');
    else if (state.ready) record(RECORD.READY, '', new Uint8Array([1]));
  }
  function shutdownSignalling(keepCode) {
    ++state.generation;
    state.active = false;
    reportReady(false);
    clearInterval(state.ping); state.ping = null;
    clearInterval(state.heartbeat); state.heartbeat = null;
    clearTimeout(state.retry); state.retry = null;
    if (state.broker) {
      const broker = state.broker;
      state.broker = null;
      broker.socket.onclose = null;
      try { broker.socket.close(); } catch (_) { /* not connected */ }
    }
    for (const peer of [...state.peers.values()]) dropPeer(peer);
    state.hosted = null; state.hosting = false; state.hostId = '';
    state.games.clear(); state.pendingIce.clear(); state.admissionClosed = false;
    state.hostRevision = state.publishedRevision = state.lastPublished = 0;
    state.publishing = false;
    record(RECORD.ROOM_CLOSED);
    record(RECORD.CLEAR_GAMES);
    if (!keepCode) { state.code = ''; state.key = null; state.topic = ''; }
    updateStatus(keepCode ? 'Room selected. Open Internet Games to connect.' : 'Left browser multiplayer room.');
  }
  function deactivate() { shutdownSignalling(true); }
  function host(map, name, players, slots, speed, crc) {
    if (!state.active || !state.ready || !state.code) return;
    state.hosting = true;
    const updated = { map: shortText(map, 79), name: shortText(name, 79),
      players, slots, speed, crc };
    if (JSON.stringify(state.hosted) !== JSON.stringify(updated)) {
      state.hosted = updated;
      state.hostRevision++;
    }
    publishHost();
  }
  function closeAdmission() {
    if (state.admissionClosed) return;
    state.admissionClosed = true;
    state.hostRevision++;
    if (state.hosted) publishHost(true);
  }
  function refresh() { state.games.clear(); record(RECORD.CLEAR_GAMES); signal({ type: 'request' }); }
  async function connectHost(id) {
    if (!state.active || !state.ready || state.hosting || !/^[0-9a-f]{32}$/.test(id)) return;
    state.hostId = id;
    const peer = createPeer(id);
    try {
      const offer = await peer.pc.createOffer();
      await peer.pc.setLocalDescription(offer);
      if (!(await signal({ type: 'offer', to: id, sdp: peer.pc.localDescription.sdp })))
        dropPeer(peer, 'Could not send browser host offer.');
    } catch (_) { dropPeer(peer, 'Could not connect to browser host.'); }
  }
  function sweep() {
    const now = Date.now();
    let changed = false;
    for (const [id, game] of state.games) {
      if (now - game.heard > 16000) { state.games.delete(id); changed = true; }
    }
    if (changed) rebuildGameList();
    for (const peer of state.peers.values()) {
      if ((!peer.open && now - peer.started >= CONNECT_TIMEOUT) ||
          (peer.disconnectedAt !== null && now - peer.disconnectedAt >= DISCONNECT_GRACE) ||
          (peer.incoming && now - peer.lastMessage >= DISCONNECT_GRACE)) {
        dropPeer(peer, 'Browser peer connection timed out.');
      }
    }
  }
  function setHeartbeat() {
    if (state.heartbeat) return;
    state.heartbeat = setInterval(() => {
      /* An existing DataChannel still needs timeouts/cleanup when MQTT is down. */
      sweep();
      flushControls();
      if (state.ready) {
        signal({ type: 'hello' });
        if (state.hosted) publishHost();
      }
    }, 4000);
  }

  function installControls() {
    const page = document.getElementById('page-content');
    if (!page || document.getElementById('web-multiplayer-controls')) return;
    const section = document.createElement('section');
    section.id = 'web-multiplayer-controls';
    section.style.cssText = 'border:1px solid #557399;border-radius:.5rem;padding:.7rem;margin:.8rem 0;';
    section.innerHTML = '<strong>Experimental browser multiplayer</strong>' +
      '<p id="web-multiplayer-status" role="status"></p>' +
      '<label for="web-multiplayer-input">Room code</label> ' +
      '<input id="web-multiplayer-input" maxlength="16" autocomplete="off" placeholder="16-character invite code"> ' +
      '<button type="button" id="web-multiplayer-join">Use code</button> ' +
      '<button type="button" id="web-multiplayer-create">Create private room</button> ' +
      '<button type="button" id="web-multiplayer-copy">Copy invite</button>' +
      '<p>Selected room: <code id="web-multiplayer-code">Not selected</code>. ' +
      'Open <b>Internet Games</b> in the game, then create or join a match.</p>';
    page.insertBefore(section, page.querySelector('h1').nextSibling);
    document.getElementById('web-multiplayer-create').addEventListener('click', () => {
      selectRoom(roomCode()).catch(e => updateStatus(e.message));
    });
    document.getElementById('web-multiplayer-join').addEventListener('click', () => {
      selectRoom(document.getElementById('web-multiplayer-input').value)
        .catch(e => updateStatus(e.message));
    });
    document.getElementById('web-multiplayer-copy').addEventListener('click', async () => {
      if (!state.code) { updateStatus('Create a room first.'); return; }
      const url = new URL(location.href); url.searchParams.set('room', state.code);
      try { await navigator.clipboard.writeText(url.toString()); updateStatus('Invite link copied.'); }
      catch (_) { updateStatus('Copy the room code shown above.'); }
    });
    updateStatus(state.status);
    const preselected = new URL(location.href).searchParams.get('room');
    if (preselected) {
      document.getElementById('web-multiplayer-input').value = preselected;
      selectRoom(preselected).catch(e => updateStatus(e.message));
    }
  }
  global.openrealmWebMultiplayer = {
    attach, activate() { activate(); setHeartbeat(); }, deactivate,
    host, closeAdmission, refresh, connectHost, selectRoom,
    status() { return state.status; },
    stats() {
      const bridge = ring(0);
      const bridgeBytes = bridge ? (load32(bridge, 4) - load32(bridge, 0)) >>> 0 : 0;
      return {visibility:document.visibilityState || 'unknown', bridgeBytes,
        peers:Array.from(state.peers.values(), p => ({peer:p.id.slice(0, 8), open:p.open,
          bufferedBytes:p.channel.bufferedAmount, queuedBytes:p.queuedBytes,
          sentPackets:p.sentPackets, receivedPackets:p.receivedPackets,
          paused:p.flowPaused}))};
    },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installControls);
  else installControls();
})(window);
