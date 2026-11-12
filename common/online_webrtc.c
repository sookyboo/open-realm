/* Optional browser Internet transport. The only shared state is an SPSC
 * ring in each direction: the engine pthread never runs browser callbacks. */
#include "common.h"
#include "online.h"

#ifdef BZ_WEB_MULTIPLAYER
#ifndef __EMSCRIPTEN__
#error BZ_WEB_MULTIPLAYER requires Emscripten
#endif
#include <emscripten.h>
#include <stddef.h>
#include <string.h>
#include <zlib.h>

#define WEB_RING_BYTES (2u * 1024u * 1024u)
#define WEB_RECORD_HEADER 40u
#define WEB_MAX_GAMES 32
#define WEB_MAX_PEERS 32
#define WEB_RECEIVE_BUDGET 128

/* Record bytes, all little-endian: uint32 total size, byte event, byte
 * NETSOURCE, 2 reserved bytes, 32 ASCII hex bytes identifying the peer,
 * followed by a payload. Records never straddle a producer transaction. */
enum { WEB_PACKET = 1, WEB_READY, WEB_GAME, WEB_CONNECTED, WEB_CLOSED,
       WEB_ROOM_CLOSED, WEB_HOST_READY, WEB_FAILED, WEB_CLEAR_GAMES };

typedef struct {
    uint32_t read, write; /* atomic release/acquire, shared with JS Atomics */
    uint8_t bytes[WEB_RING_BYTES];
} webRing_t;

typedef struct {
    char name[80], map[80];
    uint32_t players, slots, speed, crc;
} webGameInfo_t;

typedef struct {
    onlineGame_t game;
    uint32_t crc;
} webGame_t;

static struct {
    webRing_t to_browser, from_browser;
    webGame_t games[WEB_MAX_GAMES];
    char closed_peers[WEB_MAX_PEERS][33];
    char host[33], status[192];
    uint32_t count, closed_count, budget[2], map_crc;
    onlineGame_t hosted;
    bool attached, enabled, ready, hosting, host_ready, in_lobby;
    bool connecting, connection_available, admission_closed;
} web;

static void Web_Status(char const *status) {
    snprintf(web.status, sizeof(web.status), "%s", status);
}

static bool Web_HexId(char const *peer) {
    if (!peer) return false;
    for (int i = 0; i < 32; ++i) {
        if (!((peer[i] >= '0' && peer[i] <= '9') || (peer[i] >= 'a' && peer[i] <= 'f'))) return false;
    }
    return peer[32] == 0;
}

static uint32_t Web_Read32(uint8_t const *bytes) {
    return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) |
           ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
}
static void Web_Write32(uint8_t *bytes, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) bytes[i] = (uint8_t)(value >> (i * 8));
}

static bool Web_Write(webRing_t *ring, uint8_t kind, NETSOURCE source,
                      char const *peer, void const *payload, uint32_t size) {
    uint32_t const total = WEB_RECORD_HEADER + size;
    if (total > WEB_RING_BYTES || (size && !payload)) return false;
    uint32_t write = __atomic_load_n(&ring->write, __ATOMIC_RELAXED);
    uint32_t const read = __atomic_load_n(&ring->read, __ATOMIC_ACQUIRE);
    if (write - read > WEB_RING_BYTES || total > WEB_RING_BYTES - (write - read)) return false;
    uint8_t header[WEB_RECORD_HEADER] = { 0 };
    Web_Write32(header, total);
    header[4] = kind;
    header[5] = (uint8_t)source;
    if (peer) memcpy(header + 8, peer, 32);
    uint8_t const *pieces[2] = { header, (uint8_t const *)payload };
    uint32_t lengths[2] = { WEB_RECORD_HEADER, size };
    for (int part = 0; part < 2; part++) {
        for (uint32_t i = 0; i < lengths[part]; ++i)
            ring->bytes[(write++) & (WEB_RING_BYTES - 1)] = pieces[part][i];
    }
    __atomic_store_n(&ring->write, write, __ATOMIC_RELEASE);
    return true;
}

static bool Web_Read(webRing_t *ring, uint8_t *kind, NETSOURCE *source,
                     char peer[33], uint8_t *payload, uint32_t capacity,
                     uint32_t *size) {
    uint32_t read = __atomic_load_n(&ring->read, __ATOMIC_RELAXED);
    uint32_t const write = __atomic_load_n(&ring->write, __ATOMIC_ACQUIRE);
    if (read == write) return false;
    if (write - read > WEB_RING_BYTES || write - read < WEB_RECORD_HEADER) {
        __atomic_store_n(&ring->read, write, __ATOMIC_RELEASE); return false;
    }
    uint8_t header[WEB_RECORD_HEADER];
    for (uint32_t i = 0; i < WEB_RECORD_HEADER; i++)
        header[i] = ring->bytes[(read + i) & (WEB_RING_BYTES - 1)];
    uint32_t total = Web_Read32(header);
    if (total < WEB_RECORD_HEADER || total > WEB_RING_BYTES || total > write - read) {
        __atomic_store_n(&ring->read, write, __ATOMIC_RELEASE); return false;
    }
    *kind = header[4]; *source = (NETSOURCE)header[5];
    memcpy(peer, header + 8, 32); peer[32] = 0;
    *size = total - WEB_RECORD_HEADER;
    if (*size <= capacity) for (uint32_t i = 0; i < *size; i++)
        payload[i] = ring->bytes[(read + WEB_RECORD_HEADER + i) & (WEB_RING_BYTES - 1)];
    __atomic_store_n(&ring->read, read + total, __ATOMIC_RELEASE);
    return true;
}

/* Called only on the engine thread. JS sees offsets into the shared heap;
 * there are no engine calls from WebRTC/MQTT browser callbacks. */
static void Web_Attach(void) {
    if (web.attached) return;
    MAIN_THREAD_EM_ASM({
        if (window.openrealmWebMultiplayer) {
            window.openrealmWebMultiplayer.attach(Module.HEAP32.buffer, $0, $1,
                $2, $3, $4);
        }
    }, (int)&web.to_browser, (int)&web.from_browser,
       (int)offsetof(webRing_t, bytes), (int)WEB_RING_BYTES, (int)sizeof(webRing_t));
    web.attached = true;
}

static void Web_ClearPackets(void);
static int Web_PopPacket(NETSOURCE source, netadr_t *from, sizeBuf_t *message);

static void Web_ClearClosed(char const *peer) {
    for (uint32_t i = 0; i < web.closed_count; i++) {
        if (strcmp(web.closed_peers[i], peer)) continue;
        memcpy(web.closed_peers[i], web.closed_peers[--web.closed_count], 33);
        return;
    }
}
static void Web_MarkClosed(char const *peer) {
    if (!Web_HexId(peer)) return;
    for (uint32_t i = 0; i < web.closed_count; ++i)
        if (!strcmp(web.closed_peers[i], peer)) return;
    if (web.closed_count < WEB_MAX_PEERS)
        memcpy(web.closed_peers[web.closed_count++], peer, 33);
}

bool Online_Begin(void) {
    Web_Attach();
    web.enabled = true;
    Web_Status("Choose a browser room code to host or join.");
    MAIN_THREAD_EM_ASM({ if (window.openrealmWebMultiplayer)
        window.openrealmWebMultiplayer.activate(); });
    return true;
}

void Online_Leave(void) {
    if (web.attached) MAIN_THREAD_EM_ASM({ if (window.openrealmWebMultiplayer)
        window.openrealmWebMultiplayer.deactivate(); });
    web.enabled = web.ready = web.hosting = web.host_ready = false;
    web.in_lobby = web.connecting = web.connection_available = web.admission_closed = false;
    web.host[0] = 0;
    web.count = web.closed_count = 0;
    Web_ClearPackets();
    __atomic_store_n(&web.from_browser.read,
        __atomic_load_n(&web.from_browser.write, __ATOMIC_ACQUIRE), __ATOMIC_RELEASE);
    Web_Status("Disconnected from browser multiplayer.");
}
void Online_Shutdown(void) { Online_Leave(); }

void Online_Refresh(void) {
    if (!web.enabled) return;
    web.count = 0;
    MAIN_THREAD_EM_ASM({ if (window.openrealmWebMultiplayer)
        window.openrealmWebMultiplayer.refresh(); });
}
uint32_t Online_NumGames(void) { return web.count; }
bool Online_Game(uint32_t index, onlineGame_t *out) {
    if (!out || index >= web.count) return false;
    *out = web.games[index].game;
    return true;
}

static bool Web_MapCRC(cstring_t map, uint32_t *crc) {
    void *data = NULL;
    int size = FS_ReadFileQ3(map, &data);
    if (size <= 0 || !data) {
        if (data) FS_FreeFile(data);
        Web_Status("The game map is not installed."); return false;
    }
    *crc = (uint32_t)crc32(0, data, (uInt)size);
    FS_FreeFile(data);
    return true;
}

void Online_Join(uint32_t index) {
    uint32_t crc;
    if (!web.ready || web.hosting || web.in_lobby || index >= web.count) return;
    webGame_t *game = &web.games[index];
    if (!Web_MapCRC(game->game.mapname, &crc)) return;
    if (crc != game->crc) { Web_Status("The installed map differs from the host's map."); return; }
    netadr_t adr;
    if (!NET_StringToAdr(game->game.address, 0, &adr) || adr.type != NA_WEBRTC) return;
    memcpy(web.host, adr.peer, sizeof(web.host));
    web.in_lobby = true; web.connecting = true;
    Web_Status("Connecting to browser host...");
    MAIN_THREAD_EM_ASM({ if (window.openrealmWebMultiplayer)
        window.openrealmWebMultiplayer.connectHost(UTF8ToString($0)); }, web.host);
}

bool Online_TakeConnection(netadr_t *address) {
    if (!web.connection_available || !web.in_lobby || web.hosting || !address) return false;
    web.connection_available = false;
    memset(address, 0, sizeof(*address)); address->type = NA_WEBRTC;
    memcpy(address->peer, web.host, sizeof(address->peer));
    return true;
}

void Online_Host(cstring_t map, cstring_t name, uint32_t players, uint32_t slots, uint32_t speed) {
    if (!web.enabled || !web.ready || !map || !slots || slots > WEB_MAX_PEERS) return;
    if (!web.hosting) {
        if (!Web_MapCRC(map, &web.map_crc)) return;
        web.hosting = true; web.in_lobby = true; web.admission_closed = false;
    } else if (strcmp(web.hosted.mapname, map)) {
        Web_Status("Leave the Internet lobby before changing maps."); return;
    }
    onlineGame_t next = { .players = players, .slots = slots, .maxPlayers = slots, .speed = speed };
    snprintf(next.hostname, sizeof(next.hostname), "%s", name ? name : "Browser Game");
    snprintf(next.mapname, sizeof(next.mapname), "%s", map);
    if (!memcmp(&next, &web.hosted, sizeof(next)) && web.host_ready) return;
    web.hosted = next;
    web.host_ready = false;
    MAIN_THREAD_EM_ASM({ if (window.openrealmWebMultiplayer)
        window.openrealmWebMultiplayer.host(UTF8ToString($0), UTF8ToString($1), $2, $3, $4, $5);
    }, map, name ? name : "Browser Game", players, slots, speed, web.map_crc);
}

void Online_CloseAdmission(void) {
    if (!web.hosting) return;
    web.admission_closed = true;
    web.host_ready = false;
    MAIN_THREAD_EM_ASM({ if (window.openrealmWebMultiplayer)
        window.openrealmWebMultiplayer.closeAdmission(); });
}

void Online_Send(NETSOURCE source, int length, void const *data, netadr_t const *to) {
    if (!web.enabled || !to || to->type != NA_WEBRTC || !Web_HexId(to->peer) ||
        length <= 0 || length > MAX_MSGLEN ||
        !Web_Write(&web.to_browser, WEB_PACKET, source, to->peer, data, (uint32_t)length)) {
        fprintf(stderr, "WebRTC: outgoing packet rejected (peer/size/queue)\n");
    }
}

int Online_Receive(NETSOURCE source, netadr_t *from, sizeBuf_t *message) {
    if (!web.enabled || !web.ready || !message || !from) return 0;
    /* Events are consumed in Online_Frame; packets remain in this single
     * producer queue until the requested netsource reads them. Only the
     * engine pthread may access either queue. */
    return Web_PopPacket(source, from, message);
}

/* Incoming records can target either side, so demultiplex once per frame.
 * A fixed bounded queue keeps WebRTC event floods from allocating engine
 * memory; overflow is a connection failure, never a silent packet loss. */
typedef struct {
    uint32_t size;
    char peer[33];
    uint8_t *bytes;
} webPacket_t;
static struct {
    webPacket_t items[WEB_RECEIVE_BUDGET];
    uint32_t read, write;
} packet_queues[2];

static void Web_ClearPackets(void) {
    for (int s = 0; s < 2; ++s) {
        while (packet_queues[s].read != packet_queues[s].write) {
            webPacket_t *p = &packet_queues[s].items[packet_queues[s].read++ % WEB_RECEIVE_BUDGET];
            free(p->bytes); p->bytes = NULL;
        }
        packet_queues[s].read = packet_queues[s].write = 0;
    }
}

static int Web_PopPacket(NETSOURCE source, netadr_t *from, sizeBuf_t *message) {
    if (source > NS_SERVER || !web.budget[source]) return 0;
    web.budget[source]--;
    if (packet_queues[source].read == packet_queues[source].write) return 0;
    webPacket_t *p = &packet_queues[source].items[packet_queues[source].read++ % WEB_RECEIVE_BUDGET];
    int result = 0;
    if (p->size && p->size <= message->maxsize) {
        memcpy(message->data, p->bytes, p->size);
        message->cursize = p->size; message->readcount = 0;
        memset(from, 0, sizeof(*from)); from->type = NA_WEBRTC;
        memcpy(from->peer, p->peer, sizeof(from->peer));
        result = (int)p->size;
    }
    free(p->bytes); p->bytes = NULL;
    return result;
}

void Online_Frame(uint32_t msec) {
    (void)msec;
    web.budget[0] = web.budget[1] = WEB_RECEIVE_BUDGET;
    if (!web.enabled) return;
    /* The JS writer updates ring.write with release ordering, so the engine
     * may inspect the record only after its entire body has been stored. */
    static uint8_t payload[MAX_MSGLEN]; /* engine-thread scratch, not per-frame heap allocation */
    for (uint32_t i = 0; i < WEB_RECEIVE_BUDGET; i++) {
        uint8_t kind; NETSOURCE source; char peer[33]; uint32_t size;
        if (!Web_Read(&web.from_browser, &kind, &source, peer, payload, MAX_MSGLEN, &size)) break;
        if (kind == WEB_READY) {
            web.ready = size && payload[0] != 0;
            if (!web.ready) web.host_ready = false;
            Web_Status(web.ready ? "Browser room connected." : "Browser signalling disconnected.");
        } else if (kind == WEB_FAILED) {
            Web_Status("Browser peer connection or signalling failed.");
        } else if (kind == WEB_CLEAR_GAMES) {
            web.count = 0;
        } else if (kind == WEB_GAME && Web_HexId(peer) && size == sizeof(webGameInfo_t)) {
            webGameInfo_t info; memcpy(&info, payload, sizeof(info));
            info.name[79] = info.map[79] = 0;
            webGame_t *result = NULL;
            char address[64]; snprintf(address, sizeof(address), "rtc:%s", peer);
            for (uint32_t j = 0; j < web.count; j++) {
                if (!strcmp(web.games[j].game.address, address)) { result = &web.games[j]; break; }
            }
            if (!result && web.count < WEB_MAX_GAMES) result = &web.games[web.count++];
            if (result) {
                memset(result, 0, sizeof(*result));
                snprintf(result->game.address, sizeof(result->game.address), "%s", address);
                snprintf(result->game.hostname, sizeof(result->game.hostname), "%s", info.name);
                snprintf(result->game.mapname, sizeof(result->game.mapname), "%s", info.map);
                result->game.players = info.players; result->game.maxPlayers = info.slots;
                result->game.slots = info.slots; result->game.speed = info.speed; result->crc = info.crc;
            }
        } else if (kind == WEB_HOST_READY) {
            if (web.hosting && !web.admission_closed) {
                web.host_ready = true; Web_Status("Hosting a browser game. Share your room link.");
            }
        } else if (kind == WEB_CONNECTED && Web_HexId(peer)) {
            Web_ClearClosed(peer);
            if (!web.hosting && web.in_lobby && !strcmp(web.host, peer)) {
                web.connecting = false; web.connection_available = true;
                Web_Status("Connected to browser host.");
            }
        } else if (kind == WEB_CLOSED && Web_HexId(peer)) {
            Web_MarkClosed(peer);
            if (!web.hosting && web.in_lobby && !strcmp(web.host, peer)) {
                web.in_lobby = false; web.connection_available = false;
                Web_Status("Connection to browser host closed.");
            }
        } else if (kind == WEB_ROOM_CLOSED) {
            web.ready = web.in_lobby = web.host_ready = web.connection_available = false;
            Web_Status("Browser room was closed.");
        } else if (kind == WEB_PACKET && source <= NS_SERVER && Web_HexId(peer) &&
                   size > 0 && size <= MAX_MSGLEN) {
            uint32_t count = packet_queues[source].write - packet_queues[source].read;
            if (count >= WEB_RECEIVE_BUDGET) {
                Web_MarkClosed(peer);
                Web_Status("Browser packet queue overflow; peer disconnected.");
            } else {
                webPacket_t *p = &packet_queues[source].items[packet_queues[source].write % WEB_RECEIVE_BUDGET];
                p->bytes = malloc(size);
                if (p->bytes) {
                    memcpy(p->bytes, payload, size);
                    p->size = size; memcpy(p->peer, peer, 33);
                    packet_queues[source].write++;
                } else Web_MarkClosed(peer);
            }
        }
    }
}

cstring_t Online_Status(void) { return web.status[0] ? web.status : "Browser room unavailable."; }
bool Online_Ready(void) { return web.enabled && web.ready; }
bool Online_IsHost(void) { return web.hosting; }
bool Online_HostReady(void) { return Online_Ready() && web.hosting && web.host_ready && !web.admission_closed; }
bool Online_InLobby(void) { return web.in_lobby; }
bool Online_ConnectionLost(NETSOURCE source, netadr_t const *address) {
    (void)source;
    if (!address || address->type != NA_WEBRTC) return false;
    for (uint32_t i = 0; i < web.closed_count; i++)
        if (!strcmp(web.closed_peers[i], address->peer)) return true;
    return false;
}
#endif
