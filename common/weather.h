#ifndef common_weather_h
#define common_weather_h

#include "common/shared.h"

#define MAX_WEATHER_EFFECTS 256 // effects; bounds the per-client weather snapshot and stable server registry
#define BZ_GAME_DATAGRAM_ENTITY_TINTS 0x8000u // bit mask; reserves the first weather-count bit for entity RGBA data
#define BZ_GAME_DATAGRAM_LIGHTNING    0x4000u // bit mask; reserves the next weather-count bit for WC3 lightning state
#define BZ_GAME_DATAGRAM_FLAGS (BZ_GAME_DATAGRAM_ENTITY_TINTS | BZ_GAME_DATAGRAM_LIGHTNING)
_Static_assert(MAX_WEATHER_EFFECTS < BZ_GAME_DATAGRAM_LIGHTNING, "weather count must leave extension bits free");

#define MAX_LIGHTNING_EFFECTS 128 // active WC3 lightning handles/ability bolts in the per-client presentation snapshot

typedef struct {
    DWORD handle;
    DWORD effect_id;
    BOX2 bounds;
    DWORD enabled;
} wc3WeatherEffect_t;

typedef struct {
    DWORD handle;
    DWORD effect_id; /* LightningData.slk fourcc, e.g. CLPB/CLSB */
    VECTOR3 source;
    VECTOR3 target;
    COLOR32 color;   /* multiplicative RGBA; white preserves LightningData colour */
    DWORD start_time;
    DWORD end_time;  /* 0 = persistent until removed */
} wc3LightningEffect_t;

#endif
