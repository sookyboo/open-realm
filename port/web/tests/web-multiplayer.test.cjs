/* Deterministic tests of the shipped WebRTC lifecycle and shared-memory bridge. */
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const SRC = path.resolve(__dirname, '../site/web-multiplayer.js');
const ID = '0123456789abcdef0123456789abcdef';
const RING = 2 * 1024 * 1024;

function harness() {
  let now = 1000;
  const heap = new SharedArrayBuffer(2 * (RING + 8) + 64);
  const window = {Module:{HEAP32:new Int32Array(heap)}};
  const timers = [];
  class FakeChannel {
    constructor() { this.readyState = 'connecting'; this.bufferedAmount = 0; this.sent = []; }
    send(value) { this.sent.push(value); }
    close() { this.readyState = 'closed'; }
  }
  class FakeConnection {
    constructor() {
      this.connectionState = 'new'; this.signalingState = 'stable';
      this.channel = new FakeChannel();
    }
    createDataChannel() { return this.channel; }
    close() { this.connectionState = 'closed'; }
    async createOffer() { return {type:'offer',sdp:'test-offer'}; }
    async setLocalDescription(value) { this.localDescription = value; this.signalingState = 'have-local-offer'; }
    async setRemoteDescription(value) { this.remoteDescription = value; }
    async createAnswer() { return {type:'answer',sdp:'test-answer'}; }
    async addIceCandidate() {}
  }
  const document = {readyState:'loading', addEventListener() {}, getElementById(){return null;}};
  const ctx = vm.createContext({window, document, crypto:webcrypto, TextEncoder,
    TextDecoder, URL, Uint8Array, Uint32Array, Int32Array, SharedArrayBuffer,
    Atomics, DataView, RTCPeerConnection:FakeConnection, Date:{now:()=>now},
    setInterval(fn) { timers.push(fn); return timers.length; },
    clearInterval() {}, setTimeout(){return 1;}, clearTimeout(){},
    console:{warn(){}}, WebSocket:{OPEN:1}});
  const original = fs.readFileSync(SRC, 'utf8');
  const source = original.replace('})(window);',
    'window.__test={state,record,pump,createPeer,dropPeer,reportReady,sweep,host,closeAdmission,onFragment,flushPeer};})(window);');
  assert.notEqual(source, original, 'test loader could not access private functions');
  vm.runInContext(source, ctx, {filename:SRC});
  const api = window.__test;
  return {api, window, heap, timers,
    setTime(value) { now = value; },
    attach() { window.openrealmWebMultiplayer.attach(heap, 0, RING + 8, 8, RING, RING + 8); }};
}

test('MQTT readiness loss does not tear down an established gameplay peer', () => {
  const {api} = harness();
  api.state.ready = true;
  const peer = api.createPeer(ID);
  peer.open = true;
  api.reportReady(false);
  assert.equal(api.state.ready, false);
  assert.equal(api.state.peers.get(ID), peer);
});

test('an unanswered offer times out and emits a failure instead of hanging forever', () => {
  const t = harness();
  const peer = t.api.createPeer(ID);
  t.setTime(30999); t.api.sweep();
  assert.equal(t.api.state.peers.get(ID), peer);
  t.setTime(31000); t.api.sweep();
  assert.equal(t.api.state.peers.has(ID), false);
  assert.ok(t.api.state.controls.some(e => e.kind === 8 && e.peerId === ID));
});

test('ICE disconnection gets a full grace period independent of last packet', () => {
  const t = harness();
  const peer = t.api.createPeer(ID);
  peer.open = true;
  peer.disconnectedAt = 2500;
  peer.lastMessage = 0;
  t.setTime(17499); t.api.sweep();
  assert.equal(t.api.state.peers.get(ID), peer);
  t.setTime(17500); t.api.sweep();
  assert.equal(t.api.state.peers.has(ID), false);
});

test('callbacks from replaced peers cannot resurrect their prior connection', () => {
  const {api} = harness();
  const old = api.createPeer(ID);
  const current = api.createPeer(ID);
  old.channel.onopen();
  assert.equal(old.open, false);
  assert.equal(api.state.peers.get(ID), current);
  current.channel.onopen();
  assert.equal(current.open, true);
});

test('packet writers reserve shared-memory capacity for terminal control events', () => {
  const t = harness(); t.attach();
  const frame = new Uint8Array(256 * 1024);
  let accepted = 0;
  for (let i = 0; i < 12; i++) {
    if (!t.api.record(1, ID, frame, 1)) break;
    accepted++;
  }
  assert.ok(accepted >= 6 && accepted < 12);
  assert.equal(t.api.record(5, ID), true); // CLOSED must not be starved by payloads.
  const words = new Int32Array(t.heap);
  assert.ok(Atomics.load(words, (RING + 8 + 4) / 4) > 0);
});

test('engine overflow close request tears down the JavaScript DataChannel', () => {
  const t = harness(); t.attach();
  const peer = t.api.createPeer(ID);
  peer.open = true;
  const header = new Uint8Array(t.heap, 8, 40);
  new DataView(t.heap, 8, 4).setUint32(0, 40, true);
  header[4] = 10; // WEB_DROP_PEER
  header.set(new TextEncoder().encode(ID), 8);
  Atomics.store(new Int32Array(t.heap), 1, 40);
  t.api.pump();
  assert.equal(t.api.state.peers.has(ID), false);
  assert.equal(peer.channel.readyState, 'closed');
});

test('identical host state does not repeatedly advance advertisement revision', () => {
  const {api} = harness();
  api.state.active = true; api.state.ready = true; api.state.code = 'ABCDEFGHJKLMNPQ2';
  api.host('Maps/Download/Test.w3x', 'Test', 1, 2, 1, 123);
  assert.equal(api.state.hostRevision, 1);
  api.host('Maps/Download/Test.w3x', 'Test', 1, 2, 1, 123);
  assert.equal(api.state.hostRevision, 1);
  api.host('Maps/Download/Test.w3x', 'Test', 2, 2, 1, 123);
  assert.equal(api.state.hostRevision, 2);
  api.closeAdmission();
  assert.equal(api.state.hostRevision, 3);
});


test('WebRTC fragments reassemble into a single exact gameplay packet', () => {
  const t = harness(); t.attach();
  const peer = t.api.createPeer(ID);
  peer.open = true; peer.channel.readyState = 'open';
  const payload = Uint8Array.from({length:40000}, (_, i) => i & 255);
  peer.queued.push({bytes:payload, source:1}); peer.queuedBytes = payload.length;
  t.api.flushPeer(peer);
  assert.ok(peer.channel.sent.length > 1, 'expected fragmentation');
  t.api.state.hosting = false; // Receiver is the client; accepts server source 1.
  for (const frame of peer.channel.sent) t.api.onFragment(peer, frame);
  const base = RING + 8;
  const mem = new DataView(t.heap);
  const readyLength = mem.getUint32(base + 8, true);
  const packetAt = base + 8 + readyLength;
  assert.equal(mem.getUint8(packetAt + 4), 1); // WEB_PACKET
  assert.equal(mem.getUint8(packetAt + 5), 0); // NS_CLIENT
  const result = new Uint8Array(t.heap, packetAt + 40, payload.length);
  assert.deepEqual(Buffer.from(result), Buffer.from(payload));
});

test('malformed fragment fails the peer instead of delivering partial gameplay', () => {
  const t = harness();
  const peer = t.api.createPeer(ID); peer.open = true;
  const bad = new Uint8Array(14);
  new DataView(bad.buffer).setUint32(0, 1, true);
  new DataView(bad.buffer).setUint32(8, 5, true); // offset beyond total
  bad[12] = 1;
  t.api.onFragment(peer, bad);
  assert.equal(t.api.state.peers.has(ID), false);
  assert.ok(t.api.state.controls.some(item => item.kind === 8 && item.peerId === ID));
});

test('explicitly leaving a room closes peers unlike a signalling outage', () => {
  const t = harness();
  const peer = t.api.createPeer(ID); peer.open = true;
  t.window.openrealmWebMultiplayer.deactivate();
  assert.equal(t.api.state.peers.has(ID), false);
  assert.equal(peer.channel.readyState, 'closed');
  assert.ok(t.api.state.controls.some(item => item.kind === 6)); // WEB_ROOM_CLOSED
});
