# Experimental browser-to-browser multiplayer

OpenRealm's web build can optionally carry the existing Internet (`Online_*`)
client/server protocol over WebRTC DataChannels. It is **not Epic Online
Services**: native `EOS=1` and native UDP are unchanged, and there is no
native/browser cross-play or host migration in this version.

The browser build is still experimental; browser multiplayer has not yet been
verified by a complete two-player game. Source-level fixes and regression tests
are not a substitute for a two-browser playthrough. This feature is disabled by default.

## Build

```sh
make web-warcraft3-engine WEB_MULTIPLAYER=1
# Or: python3 port/web/build-engine.py --web-multiplayer
```

`WEB_MULTIPLAYER=0` (default) produces the original browser build and does not
include or load the WebRTC JavaScript. The flag adds `BZ_WEB_MULTIPLAYER=1` to
the WebAssembly engine, and includes `web-multiplayer.js` in its generated HTML.
It does not require the native EOS SDK, any EOS credentials, or a game backend.

Serve the web build over HTTPS, or localhost with the repository's
COOP/COEP-capable `port/web/serve.py`. Browser engine pthreads require
cross-origin isolation. The browsers must also provide WebRTC, Web Crypto,
WebSocket, SharedArrayBuffer, and WebGL 2/OffscreenCanvas (as required by the
normal game).

## Host and join

1. Both players install compatible Warcraft III data using the existing
   browser importer and launch the game. They need the *same* map bytes.
2. The host clicks **Create private room** in the new panel above the game.
   The room code is 16 high-entropy letters/digits. Click **Copy invite**.
3. Open **Internet Games** in OpenRealm. After the broker connects, create a
   multiplayer game and choose the map and slots. Host lobby publishing is
   handled by the existing engine `Online_Host` path.
4. The other player opens the invite link (or enters its room code and clicks
   **Use code**), opens **Internet Games**, refreshes the games list, selects
   the host's game, and clicks Join. The client connects to the host over
   WebRTC and runs the existing Quake II-style client/server handshake.
5. The host assigns slots and starts normally. The host's local client uses
   `NA_LOOPBACK`; remote browser clients use `NA_WEBRTC`.

The invite is a browser-room selection, **not** an automatic join of an engine
game. The in-game Internet Games list is deliberately reused. Changing the
room code while a match is active disconnects peers.

## Networking and trust

* **Signalling:** MQTT 3.1.1 over WSS. The default list of public brokers is
  EMQX; configure a shared MQTT endpoint for all participants. No
  public room directory is registered. Only participants knowing the same
  code receive the same MQTT topic and can decrypt its messages. MQTT only
  transports encrypted session descriptions, ICE candidates, room messages
  and game metadata, **not game traffic**.
* **Room security:** the room code is a random 80-bit value. PBKDF2-SHA256
  derives an AES-256-GCM key using a domain-specific salt. The topic is a
  domain-separated SHA-256 digest of the code. Peers deduplicate signals.
  A code is a shared capability, not an authenticated account: anyone who
  knows it can enter the signalling room and can impersonate a participant.
  Do not use this for trusted or ranked competitive matchmaking.
* **Gameplay:** one ordered, reliable DataChannel per guest, connected to
  the host browser's authoritative server (star topology). A 13-byte frame
  header carries packet length, message ID, offset and original net source.
  Fragments are assembled in order before an engine message is delivered.
  Maximum engine packet size is `MAX_MSGLEN` (256 KiB). No new Warcraft III
  message types, deltas, netchan fields, or protocol versions are required.
* **Engine/browser isolation:** the game runs on its Emscripten pthread.
  WebRTC and MQTT callbacks run in the browser main thread. Two 2 MiB SPSC
  rings, using C release/acquire and JS Atomics, exchange size-delimited
  records. The game thread does not call gameplay functions from JavaScript.
  Packet/event counts, buffer occupancy and fragmentation are bounded.
* **Authorisation:** the JS host accepts WebRTC offers only from peers who
  know the room key while the lobby is admitting players. Existing connections
  stay active after `Online_CloseAdmission`. The engine continues to validate
  map CRC and enforces its own slot and connection rules.

The browser transport is a reliable-ordered equivalent to `NA_EOS` rather than
`NA_IP`. It therefore preserves the existing unsequenced netchan behaviour;
WebRTC performs message retransmission/ordering. Native `NA_IP` remains
sequenced UDP. This can produce head-of-line blocking during packet loss.

### Optional signalling/TURN configuration

Before `web-multiplayer.js` loads, the HTML page may set:

```js
window.OPENREALM_WEB_MULTIPLAYER_CONFIG = {
  brokers: ['wss://your-mqtt.example/mqtt'],
  iceServers: [
    { urls: ['stun:stun.example.net:3478'] },
    { urls: ['turns:turn.example.net:5349'], username: 'user', credential: 'token' },
  ],
};
```

For production deployments, run an access-controlled broker and TURN service.
The default public MQTT and STUN services provide no availability or privacy
SLA. All room participants must reach the same MQTT broker; the list is an
ordered failover list, not a federation; WebRTC connections may fail across restrictive NATs without TURN. Never
embed permanent private TURN credentials in published JavaScript. Provision
short-lived credentials from a trusted service instead.

## Limitations

* Browser tabs may be suspended; the **host's browser is the game server**.
  A suspended host can stall the game, and closing it ends the match. There
  is no host migration or dedicated-server persistence.
* The experimental WebRTC backend does not join native EOS/UDP games.
* Users must select a room in the browser panel; Internet Games without a
  room is not ready. A private room has no public discoverability.
* A host can create the game only once the online room is ready. The game
  list is refreshed by an in-game refresh or host broadcasts; entries that
  are silent for more than 16 seconds are removed from the browser list.
* Signal brokers, TURN service, bandwidth and browser background scheduling
  can affect connectivity and latency.

## Verification checklist (to be run by developer)

Build and test both `WEB_MULTIPLAYER=0` and `=1`, and native `EOS=1`.
Verify two tabs on one machine, two machines on distinct networks (including
TURN-only NAT), host/client role separation, lobby slots, start, build/move/
attack, map CRC refusal, guest close/rejoin, host close, changed room code,
queue pressure, malformed signalling, packet size bounds and browser
suspension/resume. Verify the default web build contains no
`web-multiplayer.js` and behaves identically to the pre-patch build.

See [Browser runtime](browser-run.md), [GitHub Pages](browser-github-pages.md)
and [Architecture](../../ARCHITECTURE.md). Follow `AGENTS.md` and
`CONTRIBUTING.md`; builds and automated tests are deliberately not performed
by this patch author.

## Connection lifecycle and fault handling

The MQTT broker handles signalling and room discovery, not gameplay transport.
When it disconnects, the browser retries signalling while already-open WebRTC
DataChannels continue to carry game packets. New joins require signalling to
recover. Explicitly leaving/changing rooms still closes the active game session.

Unanswered offers and unopened channels time out after 30 seconds. ICE
`disconnected` has a separate 15-second grace window, and incomplete fragmented
messages also expire after 15 seconds. Fatal queue overflows cause both the C
engine and the JavaScript DataChannel to reject the peer; essential control
notifications have reserved ring capacity and a bounded retry mailbox.

Host metadata publishes on change and refreshes periodically (every eight
seconds) so discovered entries expire only when a host stops advertising.

## Automated checks

CI runs `node --test port/web/tests/*.test.cjs` and builds both the ordinary
browser engine and `WEB_MULTIPLAYER=1` with Emscripten. The default build must
not include the WebRTC script. A synthetic C filesystem regression verifies
that newer `Maps/Download` overlays take precedence over installed loose maps;
all unrelated archive and asset lookups retain their existing order. The
browser-specific `extra_data` overlay is enabled only for Emscripten startup.

CI and local builds still need an interactive, cross-network two-browser smoke
test before treating this feature as production-ready.
