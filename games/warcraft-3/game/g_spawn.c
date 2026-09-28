#include "g_local.h"
#include "jass/jass.h"
#include <stdarg.h>

#define MAX_SPAWN_ITERATIONS 10
#define MAX_REPOSITION_BLOCKERS 256 // entities; bounded broad-phase results, any hit rejects the point

extern jassModule_t jass_funcs[];
static edict_t *reposition_unit;
static vec2_t const *reposition_point;

static bool G_TutorialFlowDebugEnabledForMapSource(void) {
    return WC3_TUTORIAL_DEBUG_ENABLED();
}

/* Keep generated war3map.j as the authoritative source for preplaced units and items. */
static bool G_LoadMapUnitData(void) {
    return atoi(gi.CvarString("wc3_load_units_from_map_data", "0")) != 0;
}

/* Unit/item placements are duplicated by the generated CreateAllUnits/CreateAllItems functions. */
static bool G_MapObjectCreatedByMapScript(uint32_t id) {
    if (id == MAKEFOURCC('s', 'l', 'o', 'c') || G_Doodad(id)->id || G_DestructableData(id)->file)
        return false;
    return G_UnitUI(id)->modelFile || G_ItemData(id)->file;
}

static char *G_Orc07SkipScriptSpace(char *cursor, char *end) {
    while (cursor < end && (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n')) cursor++;
    return cursor;
}

static bool G_Orc07TakeScriptToken(char **cursor, char *end, cstring_t token) {
    size_t length = strlen(token);
    size_t i;
    bool identifier = true;
    char *at = G_Orc07SkipScriptSpace(*cursor, end);

    if (length > (size_t)(end - at) || strncmp(at, token, length)) return false;
    for (i = 0; i < length; i++)
        if (!((token[i] >= 'a' && token[i] <= 'z') || (token[i] >= 'A' && token[i] <= 'Z') ||
              (token[i] >= '0' && token[i] <= '9') || token[i] == '_')) identifier = false;
    if (identifier && at + length < end) {
        char next = at[length];
        if ((next >= 'a' && next <= 'z') || (next >= 'A' && next <= 'Z') ||
            (next >= '0' && next <= '9') || next == '_') return false;
    }
    *cursor = at + length;
    return true;
}

/* HACK: The shipped Orc07 trigger asks the BJ last-created global for a
 * destructable max life even though its map initializer only calls the native
 * CreateDestructable. Rewrite that getter in the named bridge's restore call;
 * changing BJ last-created semantics would affect unrelated maps, and the
 * mounted campaign MPQ is read-only. */
static bool G_FixOrc07BridgeRestoreScript(char *script) {
    static cstring_t const function = "function Trig_GemstoneReturned_Actions takes";
    static cstring_t const ending = "endfunction";
    static cstring_t const restore = "DestructableRestoreLife";
    static cstring_t const max_life = "GetDestructableMaxLife";
    static cstring_t const last_created = "GetLastCreatedDestructable";
    static cstring_t const bridge = "gg_dest_DTsb_0099";
    char *start, *end, *cursor, *restore_call, *getter, *getter_end;
    size_t old_size, new_size = strlen(bridge);

    if (!script || !(start = strstr(script, function))) return false;
    end = strstr(start, ending);
    restore_call = strstr(start, restore);
    if (!end || !restore_call || restore_call >= end) goto unsupported;

    cursor = restore_call;
    if (!G_Orc07TakeScriptToken(&cursor, end, restore) ||
        !G_Orc07TakeScriptToken(&cursor, end, "(") ||
        !G_Orc07TakeScriptToken(&cursor, end, bridge) ||
        !G_Orc07TakeScriptToken(&cursor, end, ",") ||
        !G_Orc07TakeScriptToken(&cursor, end, max_life) ||
        !G_Orc07TakeScriptToken(&cursor, end, "(")) goto unsupported;

    getter = G_Orc07SkipScriptSpace(cursor, end);
    cursor = getter;
    if (G_Orc07TakeScriptToken(&cursor, end, bridge) &&
        G_Orc07TakeScriptToken(&cursor, end, ")")) return true;

    cursor = getter;
    if (!G_Orc07TakeScriptToken(&cursor, end, last_created) ||
        !G_Orc07TakeScriptToken(&cursor, end, "(") ||
        !G_Orc07TakeScriptToken(&cursor, end, ")")) goto unsupported;
    getter_end = cursor;
    old_size = (size_t)(getter_end - getter);
    if (new_size > old_size) goto unsupported;
    memcpy(getter, bridge, new_size);
    memset(getter + new_size, ' ', old_size - new_size);
    return true;

unsupported:
    fprintf(stderr, "G_SpawnEntities: Orc07 gemstone restore trigger has an unsupported script form\n");
    return false;
}


typedef struct campaignHeroBaseline_s {
    char rawcode[5];
    uint32_t level;
    uint32_t xp;
    char skills[32][5];
    uint32_t num_skills;
    char xp_calls[8][256];
    uint32_t num_xp_calls;
    char state_calls[12][1024];
    uint32_t num_state_calls;
    float health;
    float mana;
    bool has_health;
    bool has_mana;
    uint32_t merged_xp;
    uint32_t merged_skillpoints;
    bool found;
} campaignHeroBaseline_t;

static char *G_CampaignCallEnd(char *call, char *limit) {
    char *at = strchr(call, '(');
    int depth = 0;
    bool quoted = false;
    if (!at || at >= limit) return NULL;
    for (; at < limit; at++) {
        if (*at == '"' && (at == call || at[-1] != '\\')) quoted = !quoted;
        if (quoted) continue;
        if (*at == '(') depth++;
        else if (*at == ')' && --depth == 0) return at + 1;
    }
    return NULL;
}

static bool G_CampaignReadUnsigned(char *start, char *limit, uint32_t *value) {
    char *end;
    unsigned long parsed;
    while (start < limit && (*start == ' ' || *start == '\t' || *start == '\r' || *start == '\n')) start++;
    if (start >= limit || *start < '0' || *start > '9') return false;
    parsed = strtoul(start, &end, 10);
    if (end == start || end > limit || parsed > UINT32_MAX) return false;
    *value = (uint32_t)parsed;
    return true;
}

static int G_CampaignNestingAt(char *start, char *position) {
    int nesting = 0;
    for (char *line = start; line < position;) {
        char *line_end = strchr(line, '\n'), *text = line;
        if (!line_end || line_end > position) line_end = position;
        while (text < line_end && (*text == ' ' || *text == '\t' || *text == '\r')) text++;
        if (!strncmp(text, "if ", 3) || !strncmp(text, "if(", 3)) nesting++;
        else if (!strncmp(text, "endif", 5) && nesting > 0) nesting--;
        line = line_end < position ? line_end + 1 : position;
    }
    return nesting;
}

static char *G_CampaignHeroTarget(char *call, char *call_end, char *hero_global) {
    char *global = strstr(call, hero_global);
    char *created = strstr(call, "GetLastCreatedUnit");
    if (global && global >= call_end) global = NULL;
    if (created && created >= call_end) created = NULL;
    return !global ? created : (!created || global < created ? global : created);
}

static bool G_CampaignIsLastCreatedAssignment(char *global, char *lower_bound, char *limit) {
    char *line = global, *line_end, *at;
    while (line > lower_bound && line[-1] != '\n') line--;
    line_end = strchr(global, '\n');
    if (!line_end || line_end > limit) line_end = limit;
    at = strstr(line, "set ");
    if (!at || at >= global) return false;
    at = global + strlen("udg_");
    while (at < line_end && ((*at >= 'a' && *at <= 'z') || (*at >= 'A' && *at <= 'Z') ||
                              (*at >= '0' && *at <= '9') || *at == '_')) at++;
    while (at < line_end && (*at == ' ' || *at == '\t')) at++;
    if (at >= line_end || *at++ != '=') return false;
    while (at < line_end && (*at == ' ' || *at == '\t')) at++;
    return (size_t)(line_end - at) >= strlen("GetLastCreatedUnit()") &&
           !strncmp(at, "GetLastCreatedUnit()", strlen("GetLastCreatedUnit()"));
}

static bool G_CampaignIsDirectCreateAssignment(char *call, char *function_start, char *hero_global) {
    char *line = call, *global, *set;
    while (line > function_start && line[-1] != '\n') line--;
    global = strstr(line, hero_global);
    set = strstr(line, "set ");
    return global && global < call && set && set < global;
}

static bool G_CampaignCopyHeroCalls(char *context_start, char *start, char *limit, char *hero_global,
                                    char calls[][256], uint32_t *num_calls, uint32_t max_calls,
                                    size_t call_capacity, cstring_t const *names, size_t num_names) {
    char *cursor = start;
    while (cursor < limit) {
        char *call = NULL, *call_end, *target;
        size_t name_index;
        for (name_index = 0; name_index < num_names; name_index++) {
            char *candidate = strstr(cursor, names[name_index]);
            if (candidate && candidate < limit && (!call || candidate < call)) call = candidate;
        }
        if (!call) break;
        call_end = G_CampaignCallEnd(call, limit);
        if (!call_end) return false;
        target = G_CampaignHeroTarget(call, call_end, hero_global);
        if (target) {
            size_t length = (size_t)(call_end - call);
            if (G_CampaignNestingAt(context_start, call) > 0) return false;
            if (*num_calls >= max_calls || length >= call_capacity) return false;
            memcpy(calls[*num_calls], call, length);
            calls[*num_calls][length] = '\0';
            (*num_calls)++;
        }
        cursor = call_end;
    }
    return true;
}

static bool G_CampaignCopyGlobal(char *source, char *limit, char *global, size_t capacity) {
    char *start = strstr(source, "udg_"), *end;
    size_t length;
    if (!start || start >= limit) return false;
    end = start;
    while (end < limit && ((*end >= 'a' && *end <= 'z') || (*end >= 'A' && *end <= 'Z') ||
                           (*end >= '0' && *end <= '9') || *end == '_')) end++;
    length = (size_t)(end - start);
    if (!length || length >= capacity) return false;
    memcpy(global, start, length);
    global[length] = '\0';
    return true;
}

static char *G_CampaignFindFunction(char *script, char *name, char **end_out) {
    char needle[224];
    char *start, *end;
    if (end_out) *end_out = NULL;
    if (snprintf(needle, sizeof(needle), "function %s takes", name) >= (int)sizeof(needle)) return NULL;
    start = strstr(script, needle);
    end = start ? strstr(start, "endfunction") : NULL;
    if (!start || !end) return NULL;
    if (end_out) *end_out = end;
    return start;
}

static bool G_CampaignFindHeroBaseline(char *function_start, char *function_end,
                                       char *hero_global, campaignHeroBaseline_t *baseline) {
    char *create = function_start;
    memset(baseline, 0, sizeof(*baseline));
    while (create < function_end) {
        char *at_loc = strstr(create, "CreateNUnitsAtLoc");
        char *at_xy = strstr(create, "CreateUnit(");
        char *call, *call_end, *next_create, *assignment, *raw;
        if (at_loc && at_loc >= function_end) at_loc = NULL;
        if (at_xy && at_xy >= function_end) at_xy = NULL;
        call = !at_loc ? at_xy : (!at_xy || at_loc < at_xy ? at_loc : at_xy);
        if (!call) break;
        call_end = G_CampaignCallEnd(call, function_end);
        if (!call_end) return false;
        next_create = strstr(call_end, "CreateNUnitsAtLoc");
        {
            char *next_xy = strstr(call_end, "CreateUnit(");
            if (next_xy && next_xy < function_end && (!next_create || next_create >= function_end || next_xy < next_create))
                next_create = next_xy;
        }
        if (!next_create || next_create >= function_end) next_create = function_end;
        assignment = call_end;
        if (!G_CampaignIsDirectCreateAssignment(call, function_start, hero_global)) {
            while ((assignment = strstr(assignment, hero_global)) && assignment < next_create) {
                if (G_CampaignIsLastCreatedAssignment(assignment, function_start, next_create)) break;
                assignment += strlen(hero_global);
            }
        } else assignment = call;
        if (!assignment || assignment >= next_create) {
            create = call_end;
            continue;
        }
        for (raw = call; raw < call_end; raw++) {
            if (*raw == '\'' && raw + 5 < call_end && raw[5] == '\'') {
                memcpy(baseline->rawcode, raw + 1, 4);
                baseline->rawcode[4] = '\0';
                break;
            }
        }
        if (!baseline->rawcode[0]) return false;
        baseline->found = true;
        {
            char *level = call_end;
            while ((level = strstr(level, "SetHeroLevel")) && level < next_create) {
                char *level_end = G_CampaignCallEnd(level, next_create);
                char *target = level_end ? G_CampaignHeroTarget(level, level_end, hero_global) : NULL;
                char *comma;
                if (!level_end) return false;
                if (target && target < level_end && (comma = strchr(target, ',')) && comma < level_end &&
                    (G_CampaignNestingAt(function_start, level) > 0 ||
                     !G_CampaignReadUnsigned(comma + 1, level_end, &baseline->level))) return false;
                level = level_end;
            }
        }
        {
            char *xp = call_end;
            while ((xp = strstr(xp, "SetHeroXP")) && xp < next_create) {
                char *xp_end = G_CampaignCallEnd(xp, next_create);
                char *target = xp_end ? G_CampaignHeroTarget(xp, xp_end, hero_global) : NULL;
                char *comma;
                if (!xp_end) return false;
                if (target && target < xp_end && (comma = strchr(target, ',')) && comma < xp_end &&
                    (G_CampaignNestingAt(function_start, xp) > 0 ||
                     !G_CampaignReadUnsigned(comma + 1, xp_end, &baseline->xp))) return false;
                xp = xp_end;
            }
        }
        {
            static cstring_t const xp_calls[] = { "AddHeroXPSwapped", "AddHeroXP(" };
            if (!G_CampaignCopyHeroCalls(function_start, call_end, next_create, hero_global, baseline->xp_calls,
                    &baseline->num_xp_calls, sizeof(baseline->xp_calls) / sizeof(baseline->xp_calls[0]),
                    sizeof(baseline->xp_calls[0]), xp_calls, sizeof(xp_calls) / sizeof(xp_calls[0]))) return false;
        }
        {
            char *skill = call_end;
            while ((skill = strstr(skill, "SelectHeroSkill")) && skill < next_create) {
                char *skill_end = G_CampaignCallEnd(skill, next_create);
                char *target = skill_end ? G_CampaignHeroTarget(skill, skill_end, hero_global) : NULL;
                char *code;
                if (!skill_end) return false;
                if (target && target < skill_end) {
                    for (code = target; code < skill_end; code++) {
                        if (*code == '\'' && code + 5 < skill_end && code[5] == '\'') {
                            if (G_CampaignNestingAt(function_start, skill) > 0) return false;
                            if (baseline->num_skills >= sizeof(baseline->skills) / sizeof(baseline->skills[0])) return false;
                            memcpy(baseline->skills[baseline->num_skills], code + 1, 4);
                            baseline->skills[baseline->num_skills][4] = '\0';
                            baseline->num_skills++;
                            break;
                        }
                    }
                }
                skill = skill_end;
            }
        }
        {
            static cstring_t const setters[] = {
                "SetWidgetLife", "SetUnitState", "SetUnitManaBJ", "SetUnitLifeBJ",
                "SetUnitLifePercentBJ", "SetUnitManaPercentBJ", "SetUnitStateBJ"
            };
            char *setup = call_end;
            char *cursor = setup;
            int nesting;
            if (!setup) return false;
            while (cursor < next_create) {
                char *setter = NULL, *setter_end = NULL;
                size_t setter_index;
                for (setter_index = 0; setter_index < sizeof(setters) / sizeof(setters[0]); setter_index++) {
                    char *candidate = strstr(cursor, setters[setter_index]);
                    if (candidate && candidate < next_create && (!setter || candidate < setter)) setter = candidate;
                }
                if (!setter) break;
                setter_end = G_CampaignCallEnd(setter, next_create);
                if (!setter_end) return false;
                nesting = G_CampaignNestingAt(function_start, setter);
                if (nesting == 0 && G_CampaignHeroTarget(setter, setter_end, hero_global)) {
                    bool copy = true;
                    if (!strncmp(setter, "SetUnitState", strlen("SetUnitState")) &&
                        !strstr(setter, "UNIT_STATE_LIFE") && !strstr(setter, "UNIT_STATE_MANA")) copy = false;
                    if (copy) {
                        size_t length = (size_t)(setter_end - setter);
                        if (baseline->num_state_calls >= sizeof(baseline->state_calls) / sizeof(baseline->state_calls[0]) ||
                            length >= sizeof(baseline->state_calls[0])) return false;
                        memcpy(baseline->state_calls[baseline->num_state_calls], setter, length);
                        baseline->state_calls[baseline->num_state_calls][length] = '\0';
                        baseline->num_state_calls++;
                    }
                } else if (nesting > 0 && G_CampaignHeroTarget(setter, setter_end, hero_global)) {
                    fprintf(stderr, "G_SpawnEntities: campaign Hero %s has conditional health/mana fallback setup\n", hero_global);
                    return false;
                }
                cursor = setter_end;
            }
        }
        if (!baseline->level) baseline->level = 1;
        return true;
    }
    return false;
}

static bool G_CampaignFindHeroProgression(char *function_start, char *function_end,
                                          char *hero_global, campaignHeroBaseline_t *baseline) {
    bool found = false;
    uint32_t old_xp_calls = baseline->num_xp_calls;
    uint32_t old_state_calls = baseline->num_state_calls;
    static cstring_t const xp_calls[] = { "AddHeroXPSwapped", "AddHeroXP(" };
    char *at = function_start;
    while ((at = strstr(at, "SetHeroLevel")) && at < function_end) {
        char *call_end = G_CampaignCallEnd(at, function_end);
        char *target = call_end ? G_CampaignHeroTarget(at, call_end, hero_global) : NULL;
        char *comma;
        if (!call_end) return false;
        if (target && target < call_end && (comma = strchr(target, ',')) && comma < call_end) {
            if (G_CampaignNestingAt(function_start, at) > 0) return false;
            if (!G_CampaignReadUnsigned(comma + 1, call_end, &baseline->level)) return false;
            found = true;
        }
        at = call_end;
    }
    at = function_start;
    while ((at = strstr(at, "SetHeroXP")) && at < function_end) {
        char *call_end = G_CampaignCallEnd(at, function_end);
        char *target = call_end ? G_CampaignHeroTarget(at, call_end, hero_global) : NULL;
        char *comma;
        if (!call_end) return false;
        if (target && target < call_end && (comma = strchr(target, ',')) && comma < call_end) {
            if (G_CampaignNestingAt(function_start, at) > 0) return false;
            if (!G_CampaignReadUnsigned(comma + 1, call_end, &baseline->xp)) return false;
            found = true;
        }
        at = call_end;
    }
    at = function_start;
    while ((at = strstr(at, "SelectHeroSkill")) && at < function_end) {
        char *call_end = G_CampaignCallEnd(at, function_end);
        char *target = call_end ? G_CampaignHeroTarget(at, call_end, hero_global) : NULL;
        char *code;
        if (!call_end) return false;
        if (target && target < call_end) {
            for (code = target; code < call_end; code++) {
                if (*code == '\'' && code + 5 < call_end && code[5] == '\'') {
                    if (G_CampaignNestingAt(function_start, at) > 0) return false;
                    if (baseline->num_skills >= sizeof(baseline->skills) / sizeof(baseline->skills[0])) return false;
                    memcpy(baseline->skills[baseline->num_skills], code + 1, 4);
                    baseline->skills[baseline->num_skills][4] = '\0';
                    baseline->num_skills++;
                    found = true;
                    break;
                }
            }
        }
        at = call_end;
    }
    if (!G_CampaignCopyHeroCalls(function_start, function_start, function_end, hero_global, baseline->xp_calls,
            &baseline->num_xp_calls, sizeof(baseline->xp_calls) / sizeof(baseline->xp_calls[0]),
            sizeof(baseline->xp_calls[0]), xp_calls, sizeof(xp_calls) / sizeof(xp_calls[0]))) return false;
    if (baseline->num_xp_calls > old_xp_calls) found = true;
    {
        static cstring_t const setters[] = {
            "SetWidgetLife", "SetUnitState", "SetUnitManaBJ", "SetUnitLifeBJ",
            "SetUnitLifePercentBJ", "SetUnitManaPercentBJ", "SetUnitStateBJ"
        };
        char *cursor = function_start;
        while (cursor < function_end) {
            char *setter = NULL, *setter_end;
            size_t i;
            for (i = 0; i < sizeof(setters) / sizeof(setters[0]); i++) {
                char *candidate = strstr(cursor, setters[i]);
                if (candidate && candidate < function_end && (!setter || candidate < setter)) setter = candidate;
            }
            if (!setter) break;
            setter_end = G_CampaignCallEnd(setter, function_end);
            if (!setter_end) return false;
            if (G_CampaignHeroTarget(setter, setter_end, hero_global)) {
                bool copy = true;
                if (G_CampaignNestingAt(function_start, setter) > 0) return false;
                if (!strncmp(setter, "SetUnitState", strlen("SetUnitState")) &&
                    !strstr(setter, "UNIT_STATE_LIFE") && !strstr(setter, "UNIT_STATE_MANA")) copy = false;
                if (copy) {
                    size_t length = (size_t)(setter_end - setter);
                    if (baseline->num_state_calls >= sizeof(baseline->state_calls) / sizeof(baseline->state_calls[0]) ||
                        length >= sizeof(baseline->state_calls[0])) return false;
                    memcpy(baseline->state_calls[baseline->num_state_calls], setter, length);
                    baseline->state_calls[baseline->num_state_calls][length] = '\0';
                    baseline->num_state_calls++;
                }
            }
            cursor = setter_end;
        }
    }
    if (baseline->num_state_calls > old_state_calls) found = true;
    return found;
}

static bool G_CampaignHasHeroSetup(char *function_start, char *function_end, char *hero_global) {
    static cstring_t const setters[] = {
        "SetHeroLevel", "SetHeroXP", "AddHeroXPSwapped", "AddHeroXP(", "SelectHeroSkill",
        "SetWidgetLife", "SetUnitState", "SetUnitManaBJ", "SetUnitLifeBJ",
        "SetUnitLifePercentBJ", "SetUnitManaPercentBJ", "SetUnitStateBJ"
    };
    char *cursor = function_start;
    while (cursor < function_end) {
        char *call = NULL, *call_end;
        size_t i;
        for (i = 0; i < sizeof(setters) / sizeof(setters[0]); i++) {
            char *candidate = strstr(cursor, setters[i]);
            if (candidate && candidate < function_end && (!call || candidate < call)) call = candidate;
        }
        if (!call) return false;
        call_end = G_CampaignCallEnd(call, function_end);
        if (!call_end) return true;
        if (G_CampaignHeroTarget(call, call_end, hero_global)) return true;
        cursor = call_end;
    }
    return false;
}

static bool G_CampaignInsert(char **script_ptr, size_t offset, char *insert) {
    char *script = *script_ptr, *rewritten;
    size_t old_size = strlen(script), insert_size = strlen(insert);
    if (offset > old_size || old_size > SIZE_MAX - insert_size - 1) return false;
    rewritten = gi.MemAlloc(old_size + insert_size + 1);
    if (!rewritten) return false;
    memcpy(rewritten, script, offset);
    memcpy(rewritten + offset, insert, insert_size);
    memcpy(rewritten + offset + insert_size, script + offset, old_size - offset + 1);
    gi.MemFree(script);
    *script_ptr = rewritten;
    return true;
}

static bool G_CampaignRestoreBranch(char *script, char *function_start, char *function_end,
                                    char *restore_at, char *global, char **insert_at,
                                    char **fallback_start, char **fallback_end) {
    char *if_at = strstr(restore_at, "if ("), *then, *condition_end, *open;
    char helper[224] = {0}, needle[256], *helper_start = NULL, *helper_end = NULL, *relation, *line_end;
    char *scan, *else_at = NULL, *endif_at, *else_body = NULL, *after_endif = NULL;
    char *cache_start, *cache_end, *return_at;
    int depth = 1;
    bool then_is_null;
    (void)function_start;
    if (!if_at || if_at >= function_end || !(then = strstr(if_at, "then")) || then >= function_end)
        return false;
    condition_end = then;
    open = strchr(if_at, '(');
    if (open) open = strchr(open + 1, '(');
    if (open && open < condition_end) {
        char *name = open;
        while (name > if_at && (name[-1] == '_' || (name[-1] >= 'a' && name[-1] <= 'z') ||
                (name[-1] >= 'A' && name[-1] <= 'Z') || (name[-1] >= '0' && name[-1] <= '9'))) name--;
        if (name < open && (size_t)(open - name) < sizeof(helper)) {
            memcpy(helper, name, (size_t)(open - name));
            helper[open - name] = '\0';
        }
    }
    relation = NULL;
    if (helper[0] && snprintf(needle, sizeof(needle), "function %s takes", helper) < (int)sizeof(needle)) {
        helper_start = strstr(script, needle);
        helper_end = helper_start ? strstr(helper_start, "endfunction") : NULL;
        relation = helper_start && helper_end ? strstr(helper_start, global) : NULL;
        if (relation && relation < helper_end) {
            line_end = strchr(relation, '\n');
            if (!line_end || line_end > helper_end) line_end = helper_end;
        } else relation = NULL;
    }
    if (!relation) {
        relation = strstr(if_at, global);
        if (!relation || relation >= condition_end) relation = strstr(if_at, "GetLastRestoredUnitBJ");
        if (relation && relation < condition_end) {
            line_end = condition_end;
        } else if (helper[0] && helper_start && helper_end) {
            relation = strstr(helper_start, "GetLastRestoredUnitBJ");
            if (!relation || relation >= helper_end) return false;
            line_end = strchr(relation, '\n');
            if (!line_end || line_end > helper_end) line_end = helper_end;
        } else return false;
    }
    then_is_null = strstr(relation, "== null") && strstr(relation, "== null") < line_end;
    if (!then_is_null && !(strstr(relation, "!= null") && strstr(relation, "!= null") < line_end))
        return false;

    scan = then + 4;
    for (; scan < function_end;) {
        char *end_line = strchr(scan, '\n'), *line = scan;
        if (!end_line || end_line > function_end) end_line = function_end;
        while (line < end_line && (*line == ' ' || *line == '\t' || *line == '\r')) line++;
        if (!strncmp(line, "if ", 3) || !strncmp(line, "if(", 3)) depth++;
        else if (!strncmp(line, "endif", 5)) {
            if (--depth == 0) break;
        } else if (depth == 1 && !else_at && !strncmp(line, "else", 4)) {
            else_at = line;
        }
        scan = end_line < function_end ? end_line + 1 : function_end;
    }
    endif_at = scan;
    scan = strchr(endif_at, '\n');
    if (scan && scan < function_end) after_endif = scan + 1;
    if (else_at) {
        scan = strchr(else_at, '\n');
        if (scan && scan < function_end) else_body = scan + 1;
    }
    if (then_is_null) {
        *fallback_start = then + 4;
        *fallback_end = else_at ? else_at : endif_at;
        cache_start = else_at ? else_body : after_endif;
        cache_end = else_at ? endif_at : function_end;
    } else {
        *fallback_start = else_at ? else_body : after_endif;
        *fallback_end = function_end;
        cache_start = then + 4;
        cache_end = else_at ? else_at : endif_at;
    }
    if (!cache_start || !cache_end || !*fallback_start) return false;
    return_at = strstr(cache_start, "return");
    if (return_at && return_at < cache_end) *insert_at = return_at;
    else if (cache_end == function_end) *insert_at = cache_start;
    else *insert_at = cache_end;
    return *insert_at != NULL;
}

static bool G_CampaignFallbackFromTrigger(char *script, char *branch_start, char *branch_end,
                                          char *hero_global, campaignHeroBaseline_t *baseline,
                                          bool *baseline_found) {
    char *call = branch_start;
    while ((call = strstr(call, "TriggerExecute")) && call < branch_end) {
        char *end = G_CampaignCallEnd(call, branch_end), *trigger = end ? strstr(call, "gg_trg_") : NULL;
        char trigger_name[192], function_name[224], *name_end, *function_end, *function_start;
        size_t length;
        if (!end) return false;
        if (trigger && trigger < end) {
            name_end = trigger;
            while (name_end < end && ((*name_end >= 'a' && *name_end <= 'z') ||
                   (*name_end >= 'A' && *name_end <= 'Z') || (*name_end >= '0' && *name_end <= '9') ||
                   *name_end == '_')) name_end++;
            length = (size_t)(name_end - trigger);
            if (!length || length >= sizeof(trigger_name)) return false;
            memcpy(trigger_name, trigger, length);
            trigger_name[length] = '\0';
            if (strncmp(trigger_name, "gg_trg_", 7)) return false;
            snprintf(function_name, sizeof(function_name), "Trig_%s_Actions", trigger_name + 7);
            function_start = G_CampaignFindFunction(script, function_name, &function_end);
            if (function_start) {
                campaignHeroBaseline_t trigger_baseline;
                if (G_CampaignFindHeroBaseline(function_start, function_end, hero_global, &trigger_baseline)) {
                    if (!*baseline_found) *baseline = trigger_baseline;
                    *baseline_found = true;
                    return true;
                }
                if (G_CampaignFindHeroProgression(function_start, function_end, hero_global, baseline)) {
                    *baseline_found = true;
                    return true;
                }
                if (G_CampaignHasHeroSetup(function_start, function_end, hero_global)) {
                    fprintf(stderr, "G_SpawnEntities: campaign Hero %s fallback trigger has unsupported setup\n", hero_global);
                    *baseline_found = false;
                    return false;
                }
            }
        }
        call = end;
    }
    return false;
}

static char *G_CampaignContainingFunction(char *script, char *position, char **function_end) {
    char *scan = strstr(script, "function "), *last = NULL, *end;
    while (scan && scan < position) {
        last = scan;
        scan = strstr(scan + strlen("function "), "function ");
    }
    end = last ? strstr(last, "endfunction") : NULL;
    if (!last || !end || position >= end) return NULL;
    if (function_end) *function_end = end;
    return last;
}

static bool G_CampaignUsesCampaignCache(char *script) {
    return script && strstr(script, "InitGameCache") &&
           strstr(script, "GetLastRestoredUnitBJ");
}

static bool G_CampaignAppend(char *buffer, size_t capacity, size_t *used, char *format, ...) {
    va_list args;
    int length;
    if (*used >= capacity) return false;
    va_start(args, format);
    length = vsnprintf(buffer + *used, capacity - *used, format, args);
    va_end(args);
    if (length < 0 || (size_t)length >= capacity - *used) return false;
    *used += (size_t)length;
    return true;
}

static bool G_CampaignCallArgument(cstring_t call, uint32_t wanted, char *out, size_t capacity) {
    char const *at = strchr(call, '('), *start;
    uint32_t index = 0;
    int depth = 0;
    bool quoted = false;
    if (!at || !out || !capacity) return false;
    start = ++at;
    for (; *at; at++) {
        if (*at == '\'') quoted = !quoted;
        else if (!quoted && *at == '(') depth++;
        else if (!quoted && *at == ')') {
            if (!depth) {
                if (index == wanted) goto copy;
                return false;
            }
            depth--;
        } else if (!quoted && !depth && *at == ',') {
            if (index == wanted) goto copy;
            index++;
            start = at + 1;
        }
    }
    return false;
copy:
    while (start < at && isspace((unsigned char)*start)) start++;
    while (at > start && isspace((unsigned char)at[-1])) at--;
    if ((size_t)(at - start) >= capacity) return false;
    memcpy(out, start, (size_t)(at - start));
    out[at - start] = '\0';
    return true;
}

static bool G_CampaignParseReal(cstring_t text, float *value) {
    char *end;
    float parsed;
    if (!text || !*text) return false;
    parsed = strtof(text, &end);
    while (*end && isspace((unsigned char)*end)) end++;
    if (end == text || *end) return false;
    *value = parsed;
    return true;
}

static bool G_CampaignHeroBaselineStats(campaignHeroBaseline_t *baseline) {
    UnitBalance_t const *balance;
    float strength, intelligence;
    uint32_t added_xp = 0, base_xp;
    char arg[128];
    if (!baseline || !baseline->rawcode[0]) return false;
    balance = G_UnitBalance(MAKEFOURCC(baseline->rawcode[0], baseline->rawcode[1],
                                      baseline->rawcode[2], baseline->rawcode[3]));
    base_xp = MAX(G_HeroXPForLevel(baseline->level), baseline->xp);
    for (uint32_t i = 0; i < baseline->num_xp_calls; i++) {
        float amount = 0.0f;
        bool found_amount = false;
        FOR_LOOP(argument, 3) {
            if (G_CampaignCallArgument(baseline->xp_calls[i], argument, arg, sizeof(arg)) &&
                G_CampaignParseReal(arg, &amount)) {
                found_amount = true;
                break;
            }
        }
        if (!found_amount || amount < 0.0f || amount > (float)INT32_MAX) {
            fprintf(stderr, "G_SpawnEntities: campaign Hero %.4s has unsupported XP fallback expression: %s\n",
                    baseline->rawcode, baseline->xp_calls[i]);
            return false;
        }
        if (UINT32_MAX - added_xp < (uint32_t)amount) added_xp = UINT32_MAX;
        else added_xp += (uint32_t)amount;
    }
    baseline->merged_xp = UINT32_MAX - base_xp < added_xp ? UINT32_MAX : base_xp + added_xp;
    {
        uint32_t const final_level = MAX(baseline->level, G_HeroLevelForXP(baseline->merged_xp));
        baseline->merged_skillpoints = final_level > baseline->num_skills
                                     ? final_level - baseline->num_skills : 0;
    }

    if (balance) {
        strength = MAX(0, balance->strength + (int32_t)((baseline->level - 1) * balance->strengthPerLevel));
        intelligence = MAX(0, balance->intelligence + (int32_t)((baseline->level - 1) * balance->intelligencePerLevel));
        baseline->health = MAX(1.0f, balance->maxHealth + (strength - balance->strength) * 25.0f);
        /* Dynamic Hero creation starts at zero current mana. Level gains add
         * only the mana-capacity delta; an authored SetUnitManaBJ/max-mana
         * call below can raise this to the full capacity. */
        baseline->mana = MAX(0.0f, (intelligence - balance->intelligence) * 15.0f);
        baseline->has_health = true;
        baseline->has_mana = true;
    }

    for (uint32_t i = 0; i < baseline->num_state_calls; i++) {
        cstring_t call = baseline->state_calls[i];
        bool life = strstr(call, "SetWidgetLife") || strstr(call, "SetUnitLifeBJ") ||
                    strstr(call, "SetUnitLifePercentBJ");
        bool mana = strstr(call, "SetUnitManaBJ") || strstr(call, "SetUnitManaPercentBJ");
        uint32_t value_arg = 1;
        if (strstr(call, "SetUnitState")) {
            if (!G_CampaignCallArgument(call, 1, arg, sizeof(arg))) return false;
            life = !strcmp(arg, "UNIT_STATE_LIFE");
            mana = !strcmp(arg, "UNIT_STATE_MANA");
            value_arg = 2;
        }
        if (!life && !mana) continue;
        if (!G_CampaignCallArgument(call, value_arg, arg, sizeof(arg))) return false;
        if (life && strstr(call, "SetUnitLifePercentBJ")) {
            float percent;
            if (!balance || !G_CampaignParseReal(arg, &percent)) goto unsupported_state;
            baseline->health *= percent * 0.01f;
        } else if (mana && strstr(call, "SetUnitManaPercentBJ")) {
            float percent;
            if (!balance || !G_CampaignParseReal(arg, &percent)) goto unsupported_state;
            baseline->mana *= percent * 0.01f;
        } else if (!G_CampaignParseReal(arg, life ? &baseline->health : &baseline->mana)) {
            if (mana && strstr(arg, "GetUnitStateSwap(UNIT_STATE_MAX_MANA")) {
                /* This common campaign setup fills the fallback Hero's mana. */
                if (!balance) goto unsupported_state;
                baseline->mana = MAX(baseline->mana,
                    balance->maxMana + (intelligence - balance->intelligence) * 15.0f);
            } else {
                goto unsupported_state;
            }
        }
        if (life) baseline->has_health = true;
        if (mana) baseline->has_mana = true;
        continue;
unsupported_state:
        fprintf(stderr, "G_SpawnEntities: campaign Hero %.4s has unsupported health/mana fallback expression: %s\n",
                baseline->rawcode, call);
        return false;
    }
    return true;
}

static bool G_CampaignBuildMerge(char *global, campaignHeroBaseline_t const *baseline,
                                 char *buffer, size_t capacity) {
    size_t used = 0;
    if (!G_CampaignAppend(buffer, capacity, &used,
        "        if ( IsUnitType(%s, UNIT_TYPE_HERO) ) then\n"
        "        // Campaign fallback merge: %s\n"
        "        if ( GetHeroLevel(%s) < %u ) then\n"
        "            call SetHeroLevel( %s, %u, false )\n"
        "        endif\n"
        "        if ( GetHeroXP(%s) < %u ) then\n"
        "            call SetHeroXP( %s, %u, false )\n"
        "        endif\n",
        global, global, global, baseline->level, global, baseline->level,
        global, baseline->merged_xp, global, baseline->merged_xp)) return false;
    for (uint32_t i = 0; i < baseline->num_skills; i++) {
        uint32_t desired_rank = 0;
        for (uint32_t j = 0; j <= i; j++)
            if (!strcmp(baseline->skills[j], baseline->skills[i])) desired_rank++;
        if (!G_CampaignAppend(buffer, capacity, &used,
            "        if ( GetUnitAbilityLevel(%s, '%s') < %u ) then\n"
            "            if ( GetHeroSkillPoints(%s) <= 0 ) then\n"
            "                call UnitModifySkillPoints( %s, 1 )\n"
            "            endif\n"
            "            call SelectHeroSkill( %s, '%s' )\n"
            "        endif\n",
            global, baseline->skills[i], desired_rank, global, global, global, baseline->skills[i])) return false;
    }
    if (baseline->merged_skillpoints && !G_CampaignAppend(buffer, capacity, &used,
        "        if ( GetHeroSkillPoints(%s) < %u ) then\n"
        "            call UnitModifySkillPoints( %s, %u - GetHeroSkillPoints(%s) )\n"
        "        endif\n", global, baseline->merged_skillpoints, global,
        baseline->merged_skillpoints, global)) return false;
    if (baseline->has_health && !G_CampaignAppend(buffer, capacity, &used,
        "        if ( GetWidgetLife(%s) < %.6g ) then\n"
        "            call SetWidgetLife( %s, %.6g )\n"
        "        endif\n", global, (double)baseline->health, global, (double)baseline->health)) return false;
    if (baseline->has_mana && !G_CampaignAppend(buffer, capacity, &used,
        "        if ( GetUnitState(%s, UNIT_STATE_MANA) < %.6g ) then\n"
        "            call SetUnitState( %s, UNIT_STATE_MANA, %.6g )\n"
        "        endif\n", global, (double)baseline->mana, global, (double)baseline->mana)) return false;
    return G_CampaignAppend(buffer, capacity, &used, "        endif\n");
}


static bool G_FixCampaignHeroRestoreScripts(char **script_ptr) {
    char *script, *search_after;
    bool complete = true;
    if (!script_ptr || !(script = *script_ptr)) return false;
    if (!G_CampaignUsesCampaignCache(script)) return true;
    search_after = script;
    for (;;) {
        char *function_start, *function_end, *restore = strstr(search_after, "GetLastRestoredUnitBJ");
        char *statement;
        if (!restore) break;
        function_start = G_CampaignContainingFunction(script, restore, &function_end);
        if (!function_start) {
            fprintf(stderr, "G_SpawnEntities: RestoreUnit result appears outside a mapscript function\n");
            complete = false;
            search_after = restore + strlen("GetLastRestoredUnitBJ");
            continue;
        }
        statement = restore;
        while (statement > function_start && statement[-1] != '\n') statement--;
        {
            char global[192] = {0}, function_name[192] = {0}, merge[32768];
            char *insert_at, *fallback_start, *fallback_end;
            char *marker, *scan;
            size_t merge_offset;
            campaignHeroBaseline_t baseline;
            marker = strstr(statement, "set ");
            if (!marker || marker >= restore) {
                search_after = restore + strlen("GetLastRestoredUnitBJ");
                continue;
            }
            if (!G_CampaignCopyGlobal(statement, restore, global, sizeof(global))) {
                fprintf(stderr, "G_SpawnEntities: mapscript has an unsupported RestoreUnit result assignment\n");
                complete = false;
                search_after = restore + strlen("GetLastRestoredUnitBJ");
                continue;
            }
            marker = strstr(restore, "Campaign fallback merge: ");
            if (marker && marker < function_end &&
                !strncmp(marker + strlen("Campaign fallback merge: "), global, strlen(global)) &&
                marker[strlen("Campaign fallback merge: ") + strlen(global)] == '\n') {
                search_after = marker + strlen("Campaign fallback merge: ") + strlen(global);
                continue;
            }
            scan = function_start + strlen("function ");
            while (scan < function_end && *scan != ' ' && *scan != '\t' && *scan != '\n') scan++;
            if ((size_t)(scan - (function_start + strlen("function "))) >= sizeof(function_name)) return false;
            memcpy(function_name, function_start + strlen("function "), (size_t)(scan - (function_start + strlen("function "))));
            function_name[scan - (function_start + strlen("function "))] = '\0';
            if (!G_CampaignRestoreBranch(script, function_start, function_end, restore, global,
                                         &insert_at, &fallback_start, &fallback_end)) {
                fprintf(stderr, "G_SpawnEntities: campaign Hero %s restore has an unsupported cache branch\n", global);
                complete = false;
                search_after = restore + strlen("GetLastRestoredUnitBJ");
                continue;
            }
            bool baseline_found = G_CampaignFindHeroBaseline(fallback_start, fallback_end, global, &baseline);
            G_CampaignFallbackFromTrigger(script, fallback_start, fallback_end, global, &baseline, &baseline_found);
            if (!baseline_found) {
                fprintf(stderr, "G_SpawnEntities: campaign Hero %s has no readable cache-miss baseline\n", global);
                complete = false;
                search_after = restore + strlen("GetLastRestoredUnitBJ");
                continue;
            }
            if (!G_CampaignHeroBaselineStats(&baseline)) {
                complete = false;
                search_after = restore + strlen("GetLastRestoredUnitBJ");
                continue;
            }
            fprintf(stderr,
                    "Campaign Hero merge prepared: global=%s function=%s fallback=%.4s level=%u xp=%u skills=%u xp_calls=%u state_calls=%u\n",
                    global, function_name, baseline.rawcode, (unsigned)baseline.level,
                    (unsigned)baseline.xp, (unsigned)baseline.num_skills,
                    (unsigned)baseline.num_xp_calls, (unsigned)baseline.num_state_calls);
            if (!G_CampaignBuildMerge(global, &baseline, merge, sizeof(merge))) {
                fprintf(stderr, "G_SpawnEntities: campaign Hero %s fallback merge exceeds script buffer\n", global);
                complete = false;
                search_after = restore + strlen("GetLastRestoredUnitBJ");
                continue;
            }
            merge_offset = (size_t)(insert_at - script);
            if (!G_CampaignInsert(script_ptr, merge_offset, merge)) return false;
            script = *script_ptr;
            function_start = G_CampaignFindFunction(script, function_name, &function_end);
            if (!function_start || !function_end) return false;
            marker = strstr(function_start, "Campaign fallback merge: ");
            if (!marker || marker >= function_end) return false;
            search_after = marker + strlen("Campaign fallback merge: ") + strlen(global);
        }
    }
    return complete;
}

#ifdef BZ_TESTS
bool G_TestMapObjectCreatedByMapScript(uint32_t id) { return G_MapObjectCreatedByMapScript(id); }
bool G_TestFixOrc07BridgeRestoreScript(char *script) { return G_FixOrc07BridgeRestoreScript(script); }
bool G_TestFixCampaignHeroRestoreScripts(char **script) { return G_FixCampaignHeroRestoreScripts(script); }
#endif

static void G_JassCoroutineTrace(handle_t trigger_handle, cstring_t function, cstring_t phase,
                                 uint32_t now, uint32_t wake_time, bool yielded, bool done) {
    trigger_t *trigger = trigger_handle;
    int32_t ordinal;
    if (!G_TutorialFlowDebugEnabledForMapSource() || !trigger ||
        trigger < level.triggers || trigger >= level.triggers + level.num_triggers) {
        return;
    }
    ordinal = (int32_t)(trigger - level.triggers);
    if (ordinal < 120 || ordinal > 165) return;
    fprintf(stderr,
            "WC3_TUTORIAL_COROUTINE phase=%s trigger=%ld function=\"%s\" now=%u wake=%u yielded=%d done=%d\n",
            phase ? phase : "unknown", (long)ordinal,
            function ? function : "(none)", (unsigned)now, (unsigned)wake_time,
            (int)yielded, (int)done);
}

void G_InitJassHost(void) {
    jass_sethost(&MAKE(jassHost_t,
        .MemAlloc = gi.MemAlloc,
        .MemFree = gi.MemFree,
        .GetTime = gi.GetTime,
        .ReadFile = gi.ReadFile,
        .natives = jass_funcs,
        .GetPlayerByNumber = G_GetPlayerByNumber,
        .TimerCoroutineValid = G_TimerCoroutineValid,
        .SaveHandle = G_SaveJassHandle,
        .LoadHandle = G_LoadJassHandle,
        .CoroutineTrace = G_JassCoroutineTrace,
        .VariableChanged = G_JassVariableChanged,
    ));
}

static cstring_t G_FindJassMapFunction(cstring_t script, cstring_t name, cstring_t *finish) {
    char needle[192];
    cstring_t start, end;
    if (finish) *finish = NULL;
    if (!script || !name || !*name) return NULL;
    snprintf(needle, sizeof(needle), "function %s takes", name);
    start = strstr(script, needle);
    if (!start) return NULL;
    end = strstr(start, "endfunction");
    if (!end) return start;
    end += strlen("endfunction");
    while (*end == '\r' || *end == '\n') end++;
    if (finish) *finish = end;
    return start;
}

static void G_DumpTutorialJassFunction(cstring_t script, cstring_t name) {
    cstring_t start, finish;
    size_t length;
    start = G_FindJassMapFunction(script, name, &finish);
    if (!start) {
        fprintf(stdout, "WC3_TUTORIAL_SOURCE missing function=\"%s\"\n", name);
        return;
    }
    if (!finish) {
        fprintf(stdout, "WC3_TUTORIAL_SOURCE unterminated function=\"%s\"\n", name);
        return;
    }
    length = (size_t)(finish - start);
    fprintf(stdout, "WC3_TUTORIAL_SOURCE begin function=\"%s\"\n%.*s", name, (int)length, start);
    if (!length || start[length - 1] != '\n') fputc('\n', stdout);
    fprintf(stdout, "WC3_TUTORIAL_SOURCE end function=\"%s\"\n", name);
}

static bool G_JassRangeContains(cstring_t start, cstring_t finish, cstring_t needle) {
    cstring_t hit;
    if (!start || !finish || !needle || start >= finish) return false;
    hit = strstr(start, needle);
    return hit && hit < finish;
}

static void G_DumpTutorialJassFunctionsReferencing(cstring_t script, cstring_t needle) {
    cstring_t cursor = script;
    char function_name[160];
    if (!script || !needle || !*needle) return;
    while ((cursor = strstr(cursor, "function ")) != NULL) {
        cstring_t name_start = cursor + strlen("function ");
        cstring_t name_end = strstr(name_start, " takes");
        cstring_t finish = strstr(name_start, "endfunction");
        size_t name_len;
        if (!name_end || !finish) break;
        finish += strlen("endfunction");
        if (G_JassRangeContains(cursor, finish, needle)) {
            name_len = (size_t)(name_end - name_start);
            if (name_len > 0 && name_len < sizeof(function_name)) {
                memcpy(function_name, name_start, name_len);
                function_name[name_len] = '\0';
                fprintf(stdout,
                        "WC3_TUTORIAL_SOURCE reference token=\"%s\" function=\"%s\"\n",
                        needle, function_name);
                G_DumpTutorialJassFunction(script, function_name);
            }
        }
        cursor = finish;
    }
}

static void G_DumpReferencedTutorialTriggers(cstring_t script, cstring_t start, cstring_t finish) {
    cstring_t cursor = start;
    char seen[16][96] = {{0}};
    uint32_t seen_count = 0;
    while (cursor && cursor < finish && seen_count < 16) {
        cstring_t ref = strstr(cursor, "gg_trg_");
        size_t len;
        bool duplicate = false;
        char suffix[96];
        char function_name[160];
        if (!ref || ref >= finish) break;
        ref += strlen("gg_trg_");
        len = 0;
        while (ref + len < finish &&
               ((ref[len] >= 'A' && ref[len] <= 'Z') ||
                (ref[len] >= 'a' && ref[len] <= 'z') ||
                (ref[len] >= '0' && ref[len] <= '9') || ref[len] == '_')) {
            len++;
        }
        if (!len || len >= sizeof(suffix)) { cursor = ref + (len ? len : 1); continue; }
        memcpy(suffix, ref, len);
        suffix[len] = '\0';
        FOR_LOOP(i, seen_count) if (!strcmp(seen[i], suffix)) duplicate = true;
        if (!duplicate) {
            snprintf(seen[seen_count++], sizeof(seen[0]), "%s", suffix);
            fprintf(stdout, "WC3_TUTORIAL_SOURCE reference trigger=\"gg_trg_%s\"\n", suffix);
            snprintf(function_name, sizeof(function_name), "Trig_%s_Conditions", suffix);
            G_DumpTutorialJassFunction(script, function_name);
            snprintf(function_name, sizeof(function_name), "Trig_%s_Actions", suffix);
            G_DumpTutorialJassFunction(script, function_name);
            snprintf(function_name, sizeof(function_name), "InitTrig_%s", suffix);
            G_DumpTutorialJassFunction(script, function_name);
        }
        cursor = ref + len;
    }
}

static void G_DumpPrologue02BurrowHandoffSource(cstring_t script) {
    static cstring_t const root_names[] = {
        "Trig_W2_BurrowComplete_Q_Func002001",
        "Trig_W2_BurrowComplete_Q_Func007001",
        "Trig_W2_BurrowComplete_Q_Conditions",
        "Trig_W2_BurrowComplete_Q_Actions",
        "InitTrig_W2_BurrowComplete_Q",
        "Trig_W2_BurrowComplete_Abort_Conditions",
        "Trig_W2_BurrowComplete_Abort_Actions",
        "InitTrig_W2_BurrowComplete_Abort",
        "Trig_W_Burrow_Check_Conditions",
        "Trig_W_Burrow_Check_Actions",
        "InitTrig_W_Burrow_Check",
        "Trig_Done_Burrows_Q_Conditions",
        "Trig_Done_Burrows_Q_Actions",
        "InitTrig_Done_Burrows_Q",
        "Trig_U1_SelectWarMill_Q_Conditions",
        "Trig_U1_SelectWarMill_Q_Actions",
        "InitTrig_U1_SelectWarMill_Q",
    };
    cstring_t action_start, action_finish;
    if (!G_TutorialFlowDebugEnabledForMapSource()) return;
    FOR_LOOP(i, sizeof(root_names) / sizeof(root_names[0]))
        G_DumpTutorialJassFunction(script, root_names[i]);
    action_start = G_FindJassMapFunction(script, "Trig_W2_BurrowComplete_Q_Actions", &action_finish);
    if (action_start && action_finish)
        G_DumpReferencedTutorialTriggers(script, action_start, action_finish);
    G_DumpTutorialJassFunctionsReferencing(script, "gg_snd_T02Narrator031");
    G_DumpTutorialJassFunctionsReferencing(script, "gg_snd_T02Narrator032");
    G_DumpTutorialJassFunctionsReferencing(script, "gg_snd_T02Narrator033");
    G_DumpTutorialJassFunctionsReferencing(script, "gg_snd_T02Narrator034");
    G_DumpTutorialJassFunctionsReferencing(script, "gg_snd_T02Narrator035");
}

static uint32_t G_NormalizeMapObjectPlayer(uint32_t player) {
    if (player < MAX_PLAYERS) {
        return player;
    }
    return PLAYER_NEUTRAL_PASSIVE;
}

cstring_t targs[] = {
    "none", // NONE
    "air",  // AIR
    "aliv", // ALIVE
    "alli", // ALLIES
    "dead", // DEAD
    "debr", // DEBRIS
    "enem", // ENEMIES
    "grou", // GROUND
    "hero", // HERO
    "invu", // INVULNERABLE
    "item", // ITEM
    "mech", // MECHANICAL
    "neut", // NEUTRAL
    "nonh", // NONHERO
    "nons", // NONSAPPER
    "nots", // NOTSELF
    "orga", // ORGANIC
    "play", // PLAYERUNITS
    "sapp", // SAPPER
    "self", // SELF
    "stru", // STRUCTURE
    "terr", // TERRAIN
    "tree", // TREE
    "vuln", // VULNERABLE
    "wall", // WALL
    "ward", // WARD
    "anci", // ANCIENT
    "nona", // NONANCIENT
    "frie", // FRIEND
    "brid", // BRIDGE
    "deco", // DECORATION
};

/* Convert an internal target category to the authored UnitWeapons targetflag bit. */
uint32_t G_TargetFlagForType(TARGTYPE type) {
    switch (type) {
    case TARG_GROUND:     return WC3_TARGET_FLAG_GROUND;
    case TARG_AIR:        return WC3_TARGET_FLAG_AIR;
    case TARG_STRUCTURE:  return WC3_TARGET_FLAG_STRUCTURE;
    case TARG_WARD:       return WC3_TARGET_FLAG_WARD;
    case TARG_ITEM:       return WC3_TARGET_FLAG_ITEM;
    case TARG_TREE:       return WC3_TARGET_FLAG_TREE;
    case TARG_WALL:       return WC3_TARGET_FLAG_WALL;
    case TARG_DEBRIS:     return WC3_TARGET_FLAG_DEBRIS;
    case TARG_DECORATION: return WC3_TARGET_FLAG_DECORATION;
    case TARG_BRIDGE:     return WC3_TARGET_FLAG_BRIDGE;
    default:              return 0u;
    }
}

TARGTYPE G_GetTargetType(cstring_t str) {
    /* Missing target metadata means no target flags; strlen(NULL) previously crashed sparse unit transforms. */
    if (!str || !*str) return TARG_NONE;
    uint32_t const len = (uint32_t)strlen(str);
    if (len < 3) return TARG_NONE;
    char buf[64] = { 0 };
    FOR_LOOP(c, len) buf[c] = tolower(str[c]);
    FOR_LOOP(i, sizeof(targs)/sizeof(*targs)) {
        if (*(uint32_t *)buf == *(uint32_t *)targs[i])
            return i;
    }
    return TARG_NONE;
}

//struct spawn {
//    cstring_t name;
//    void (*func)(edict_t *edict);
//};

//static struct spawn spawns[] = {
//    { "opeo", SP_monster_unit },
//    { NULL, NULL }
//};

void SP_monster_unit(edict_t *edict);
void SP_monster_tree(edict_t *edict);

static void G_InitEdict(edict_t *e) {
    memset(e, 0, sizeof(edict_t));
    e->inuse = true;
    e->item.inventory_slot = -1;
    e->s.scale = 1;
    e->animation_speed = 1.0f;
    e->s.number = (int)(e - g_edicts);
}

edict_t *G_Spawn(void) {
    for (uint32_t i = game.max_clients; i < globals.num_edicts; i++) {
        edict_t *e = &g_edicts[i];
        if (!e->inuse && e->freetime + 1000 < level.time) {
            G_InitEdict(e);
            return e;
        }
    }
    if (globals.num_edicts >= globals.max_edicts) {
        gi.error("G_Spawn: no free edicts (%d max)\n", globals.max_edicts);
        return NULL;
    }
    edict_t *edict = &g_edicts[globals.num_edicts++];
    G_InitEdict(edict);
    return edict;
}

/* Confirm a candidate variation resolves through the authoritative VFS. */
static bool SP_DoodadModelExists(cstring_t filename) {
    uint32_t size = 0;
    handle_t data;

    if (!filename || !*filename) return false;
    data = gi.ReadFile(filename, &size);
    if (!data) return false;
    gi.MemFree(data);
    return true;
}

/* Resolve an authored doodad model and only use a variation file that exists. */
static void SP_DoodadModelFilename(Doodads_t const *row, uint32_t variation,
                                   string_t out, size_t out_size) {
    PATHSTR stem = { 0 };
    PATHSTR varied = { 0 };
    cstring_t file;
    char *dot;

    if (!out || !out_size) return;
    out[0] = '\0';
    if (!row || !(file = row->file) || !*file) return;

    /* RoC rows pair dir with a short file name; newer rows can store a full path. */
    if (strchr(file, '\\') || strchr(file, '/'))
        strlcpy(stem, file, sizeof(stem));
    else if (row->dir && *row->dir)
        snprintf(stem, sizeof(stem), "%s\\%s\\%s", row->dir, file, file);
    else
        strlcpy(stem, file, sizeof(stem));
    dot = strrchr(stem, '.');
    if (dot && (!strcasecmp(dot, ".mdx") || !strcasecmp(dot, ".mdl")))
        *dot = '\0';

    if (row->numVar > 1) {
        uint32_t const max_variation = (uint32_t)row->numVar - 1;
        char suffix[16];
        snprintf(suffix, sizeof(suffix), "%u.mdx", MIN(variation, max_variation));
        if (strlen(stem) + strlen(suffix) >= sizeof(varied)) {
            fprintf(stderr, "WC3 doodad model path is too long for '%.4s': %s%s\n",
                    (cstring_t)&row->id, stem, suffix);
            return;
        }
        strlcpy(varied, stem, sizeof(varied));
        strlcat(varied, suffix, sizeof(varied));
        if (SP_DoodadModelExists(varied)) {
            strlcpy(out, varied, out_size);
            return;
        }
        /* Some SLK rows advertise multiple variations even when a particular
         * suffixed file is absent.  Warcraft/Warsmash fall back to the base
         * model rather than registering a path that cannot be loaded. */
    }
    snprintf(out, out_size, "%s.mdx", stem);
}

static void SP_SpawnDoodad(edict_t *edict) {
    Doodads_t const *row = edict->data.Doodads;
    PATHSTR buffer;

    SP_DoodadModelFilename(row, edict->variation, buffer, sizeof(buffer));
    edict->s.model = G_RegisterModel(buffer);
    edict->movetype = MOVETYPE_NONE;
    edict->svflags |= SVF_STATIC_SCENERY;
    /* Frame zero may show portrait-only geometry. Start the authored world sequence. */
    G_DoodadSetAnimation(edict, "stand", false);
}

/* DestructableData may provide either a complete model stem (TFT/current
 * data) or the older dir + short file pair. As in Warsmash, a variation
 * suffix exists only when numVar > 1; appending "0" to a single-variation
 * bridge points the game-side animation loader at a file that is not in
 * War3.mpq even though the renderer can recover by stripping that digit. */
static void SP_DestructableModelFilename(DestructableData_t const *row,
                                         uint32_t variation,
                                         string_t out,
                                         size_t out_size) {
    PATHSTR stem = { 0 };
    cstring_t file;
    char *dot;

    if (!out || !out_size) return;
    out[0] = '\0';
    if (!row || !(file = row->file) || !*file) return;

    if (strchr(file, '\\') || strchr(file, '/'))
        strlcpy(stem, file, sizeof(stem));
    else if (row->dir && *row->dir)
        snprintf(stem, sizeof(stem), "%s\\%s\\%s", row->dir, file, file);
    else
        strlcpy(stem, file, sizeof(stem));

    dot = strrchr(stem, '.');
    if (dot && (!strcasecmp(dot, ".mdx") || !strcasecmp(dot, ".mdl")))
        *dot = '\0';

    if (row->numVar > 1) {
        uint32_t const max_variation = (uint32_t)row->numVar - 1;
        snprintf(out, out_size, "%s%u.mdx", stem, MIN(variation, max_variation));
    } else {
        snprintf(out, out_size, "%s.mdx", stem);
    }
}

static void SP_SpawnDestructable(edict_t *edict) {
    DestructableData_t const *row = edict->data.DestructableData;
    cstring_t path_tex = row->pathingTexture;
    float radius = row->radius;
    PATHSTR buffer;
    cstring_t tex = row->textureFile;
    /* texFile may include an extension; "_" means the model has no replacement texture. */
    edict->s.image = tex && *tex && strcmp(tex, "_") ? gi.ImageIndex(tex) : 0;
    SP_DestructableModelFilename(row, edict->variation, buffer, sizeof(buffer));
    edict->s.model = G_RegisterModel(buffer);
    edict->destructable.alive_pathtex = M_LoadPathTex(path_tex);
    edict->destructable.death_pathtex = M_LoadPathTex(row->deathPathingTexture);
    edict->pathtex = edict->destructable.alive_pathtex;
    edict->s.radius = radius > 0.0f ? radius : 50.0f;  /* selection/UI circle only */
    /* WC3 trees have collisionSize 0 and block solely via their baked pathing
     * footprint; only destructables with a real radius (bridges, gates) get a
     * collision circle.  Fabricating a 50-unit circle on every tree was a prime
     * cause of units sticking on trunks. */
    edict->collision = radius > 0.0f ? radius : 0.0f;
    edict->destructable.alive_collision = edict->collision;
    edict->destructable.initialized = true;
    edict->destructable.dead = false;
    edict->destructable.item_table = (uint32_t)-1;
    edict->destructable.placement_solid = true;
    edict->destructable.pathing_active = edict->pathtex || edict->collision > 0.0f;
#ifndef USE_SHADOWMAPS
    edict->s.shadow = G_LoadShadowTexture(row->shadow, false);
    edict->s.shadow_rect = 0;
#endif
    edict->health.value = row->maxHealth;
    edict->health.max_value = row->maxHealth;
    edict->targtype = G_GetTargetType(row->targetType);
    if (row->occluderHeight > 0 || edict->targtype == TARG_TREE) {
        edict->s.flags |= EF_FOW_BLOCKER;
        G_FowMarkBlockersDirty();
    }
    edict->movetype = MOVETYPE_NONE;
    edict->svflags |= SVF_STATIC_SCENERY;
    G_BlightInitializeDestructable(edict);
}

/* The destructable currently being visited by EnumDestructablesInRect, read
 * back by the GetEnumDestructable native inside the enum action (mirrors the
 * jass-lib `currentunit`/GetEnumUnit pair). */
edict_t *currentdestructable = NULL;

static bool G_ClassIdIsPrintable(uint32_t class_id) {
    uint8_t const *id = (uint8_t const *)&class_id;

    FOR_LOOP(i, 4) {
        if (id[i] < 32 || id[i] > 126) {
            return false;
        }
    }
    return true;
}

/* Bind immutable table rows after class_id is assigned and before entity-specific initialization. */
void G_BindEntityData(edict_t *edict) {
    edict->data.UnitProfile = G_UnitProfile(edict->class_id);
    edict->data.UnitBalance = G_UnitBalance(edict->class_id);
    edict->data.UnitData = G_UnitData(edict->class_id);
    edict->data.UnitUI = G_UnitUI(edict->class_id);
    edict->data.UnitWeapons = G_UnitWeapons(edict->class_id);
    edict->data.UnitAbilities = G_UnitAbil(edict->class_id);
    edict->data.Doodads = G_Doodad(edict->class_id);
    edict->data.ItemData = G_ItemData(edict->class_id);
    edict->data.DestructableData = G_DestructableData(edict->class_id);
}

/* Install class-owned unit/destructable lifecycle callbacks. Load restores the saved C callbacks
 * through F_CFUNCTION; this helper is for spawn/tests that have class data but have not assigned
 * those pointers yet. */
void G_BindEntityRuntime(edict_t *edict) {
    if (edict->data.DestructableData->file) {
        edict->stand = tree_stand; edict->birth = tree_birth; edict->pain = tree_pain; edict->die = tree_die;
        edict->think = monster_think;
    } else if (edict->data.UnitBalance->id || edict->data.UnitUI->modelFile) {
        edict->stand = unit_stand; edict->birth = unit_birth; edict->die = unit_die;
        edict->think = monster_think;
    }
}

void SP_CallSpawn(edict_t *edict) {
    if (!edict->class_id)
        return;
    edict->s.class_id = edict->class_id;
    G_BindEntityData(edict);
    if (edict->data.Doodads->id) {
        SP_SpawnDoodad(edict);
    } else if (edict->data.DestructableData->file) {
        SP_SpawnDestructable(edict);
        SP_monster_tree(edict);
    } else if (edict->data.UnitUI->modelFile) {
        SP_SpawnUnit(edict);
        SP_monster_unit(edict);
    } else if (edict->data.ItemData->file) {
        SP_SpawnItem(edict);
    } else if (MAKEFOURCC('s', 'l', 'o', 'c') == edict->class_id) {
        edict->svflags |= SVF_NOCLIENT;
    } else {
        if (edict->class_id == MAKEFOURCC('L', 'T', 'l', 't')) {
            (void)G_DestructableData(edict->class_id)->file; /* TODO: use model path */
        }
        edict->svflags |= SVF_NOCLIENT;
        if (!G_ClassIdIsPrintable(edict->class_id)) {
            fprintf(stderr, "Warning: Invalid map object ID %.4s\n", (char const *)&edict->class_id);
        }
    }
//    for (struct spawn *s = spawns; s->func; s++) {
//        if (*((int const *)s->name) == edict->class_id) {
//            s->func(edict);
//            return;
//        }
//    }
}

void SP_worldspawn(edict_t *ent) {
}

static uint32_t G_MapPlayerTeam(mapInfo_t const *mapinfo, uint32_t playernum) {
    if (!mapinfo || !mapinfo->teams) {
        return playernum;
    }
    FOR_LOOP(i, mapinfo->num_teams) {
        if (mapinfo->teams[i].playerMasks & (1u << playernum)) {
            return i;
        }
    }
    return playernum;
}

static uint32_t G_LocalMapPlayerNumber(mapInfo_t const *mapinfo) {
    if (!mapinfo) {
        return 0;
    }
    FOR_LOOP(i, MAX_PLAYERS) {
        if (mapinfo->players[i].used && mapinfo->players[i].playerType == kPlayerTypeHuman) {
            return i;
        }
    }
    return 0;
}

static uint32_t G_ClientSlotMapPlayerNumber(mapInfo_t const *mapinfo, uint32_t slot, uint32_t local_player) {
    uint32_t count = 1;

    if (slot == 0) {
        return local_player;
    }
    FOR_LOOP(i, MAX_PLAYERS) {
        if (i == local_player) {
            continue;
        }
        if (count++ == slot) {
            return i;
        }
    }
    return slot;
}

/* JASS mapcontrol values do not match W3I playerType values after computer. */
static uint32_t G_MapControl(mapPlayer_t const *player) {
    if (!player) return 5;
    switch (player->playerType) {
        case kPlayerTypeHuman: return 0;
        case kPlayerTypeComputer: return 1;
        case kPlayerTypeRescuable: return 2;
        case kPlayerTypeNeutral: return 3;
        default: return 5;
    }
}

/* Race preferences are bit flags, unlike the sequential W3I race enum. */
static uint32_t G_RacePreference(mapPlayer_t const *player) {
    if (!player) return 0;
    switch (player->playerRace) {
        case kPlayerRaceHuman: return 1;
        case kPlayerRaceOrc: return 2;
        case kPlayerRaceNightElf: return 4;
        case kPlayerRaceUndead: return 8;
        default: return 32;
    }
}

static void G_InitMapPlayer(edict_t *clent, mapInfo_t const *mapinfo, uint32_t playernum) {
    mapPlayer_t const *player = mapinfo ? mapinfo->players + playernum : NULL;
    cstring_t name = player && player->playerName ? G_LevelString(player->playerName) : NULL;
    player_t *ps = &clent->client->ps;
    G_SetClientConnected(clent, false);
    G_ResetSelectionFocus(clent->client);
    clent->client->commands_dirty = false;
    memset(&clent->client->jass, 0, sizeof(clent->client->jass));
    memset(clent->client->tech, 0, sizeof(clent->client->tech));
    memset(ps, 0, sizeof(player_t));
    ps->number = playernum;
    ps->team = G_MapPlayerTeam(mapinfo, playernum);
    ps->color = player ? player->color : playernum;
    if (playernum == PLAYER_NEUTRAL_PASSIVE) ps->color = WC3_PLAYER_COLOR_LIGHT_GRAY;
    ps->race = player ? player->playerRace : kPlayerRaceNone;
    ps->name = (string_t)name;
    ps->start_location = player ? (int32_t)playernum : -1;
    ps->stats[PLAYERSTATE_FOOD_CAP_CEILING] = (uint16_t)MIN(MAX(0, game.constants.foodCeiling), USHRT_MAX);
    ps->stats[PLAYERSTATE_GOLD_UPKEEP_RATE] = 100;
    ps->stats[PLAYERSTATE_LUMBER_UPKEEP_RATE] = 100;
    ps->vieworigin = G_MakeServerOrigin(player ? player->startingPosition.x : 0.0f, player ? player->startingPosition.y : 0.0f, 0.0f);
    {
        gameCamera_t cam;
        CL_GameDefaultCamera(&cam);
        ps->viewangles = (vec3_t){ cam.pitch, 0, cam.yaw };
        ps->distance = cam.distance;
        player_set_lens(ps, &cam);
        clent->client->camera.state.position = (vec2_t){ ps->vieworigin.x, ps->vieworigin.y };
        clent->client->camera.state.viewangles = ps->viewangles;
        clent->client->camera.state.fov = cam.fov;
        clent->client->camera.state.target_distance = cam.distance;
        clent->client->camera.state.z_offset = 0.0f;
        clent->client->camera.state.near_z = cam.znear;
        clent->client->camera.state.far_z = cam.zfar;
    }
    clent->client->camera.target_height = ps->vieworigin.z;
    clent->client->camera.old_state = clent->client->camera.state;
    clent->client->camera.target_inherit_orientation = false;
    if (mapinfo) {
        FOR_LOOP(i, mapinfo->num_techAvailabilities) {
            mapTechAvailability_t const *tech = mapinfo->techAvailabilities + i;
            if (tech->playerFlags & (1u << playernum)) {
                G_SetPlayerTechMaxAllowed(clent->client, tech->techID, 0);
            }
        }
    }
    clent->client->mapplayer = player;
    clent->client->jass.controller = G_MapControl(player);
    clent->client->jass.race_pref = G_RacePreference(player);
    clent->client->jass.race_selectable = true;
    clent->client->jass.handicap = clent->client->jass.handicap_xp = 100.0f;
    strlcpy(clent->client->jass.name, name ? name : "", sizeof(clent->client->jass.name));
    ps->name = clent->client->jass.name;
}

void G_SpawnEntities(void) {
    mapInfo_t const *mapinfo = CM_GetMapInfo();
    doodad_t const *entities = CM_GetDoodads();
    uint32_t local_player = G_LocalMapPlayerNumber(mapinfo);
    int32_t difficulty = 1;
    cstring_t map_path = gi.CvarString("map", "");

    /* Map replacement must release script roots before level pointers are cleared. */
    G_BotShutdown();
    if (level.vm) { jass_close(level.vm); level.vm = NULL; }
    G_ClearSaveRegistries();
    G_ClearJassGroupRegistry();
    G_ClearRegionRegistry();
    G_ClearHashtableRegistry();
    G_FowShutdown();
    G_BlightShutdown();
    memset(&level, 0, sizeof(level));
    G_ResetSelectionSoundState();
    G_ResetHeroPassiveCaches();
    FOR_LOOP(i, MAX_PLAYERS) level.player_leaderboards[i] = -1;
    G_ResetStartingResourceCheat();
    level.time = gi.GetTime();

    level.mapinfo = mapinfo;
    G_BlightInit();
    G_EnvironmentFogInitMap();
    G_InitPlayerAlliances(mapinfo);
    level.setup.teams = mapinfo ? mapinfo->num_teams : 0;
    if (mapinfo) FOR_LOOP(i, MAX_PLAYERS) level.setup.players += mapinfo->players[i].used;
    level.setup.game_type = 4;
    level.setup.speed = 2;
    if ((!strncasecmp(map_path, "Maps\\Campaign\\", 14) ||
         !strncasecmp(map_path, "Maps/Campaign/", 14) ||
         !strncasecmp(map_path, "Maps\\FrozenThrone\\Campaign\\", 26) ||
         !strncasecmp(map_path, "Maps/FrozenThrone/Campaign/", 26)) && gi.CvarString) {
        difficulty = atoi(gi.CvarString("wc3_campaign_difficulty", "1"));
    }
    if (difficulty < 0) difficulty = 0;
    if (difficulty > 3) difficulty = 3;
    level.setup.difficulty = (uint32_t)difficulty;
    level.setup.default_difficulty = (uint32_t)difficulty;
    level.setup.resource_density = level.setup.creature_density = 2;
    if (mapinfo) {
        strlcpy(level.setup.name, G_LevelString(mapinfo->mapName ? mapinfo->mapName : ""), sizeof(level.setup.name));
        strlcpy(level.setup.description, G_LevelString(mapinfo->mapDescription ? mapinfo->mapDescription : ""), sizeof(level.setup.description));
    }
    G_FowInit();
    G_InitJassHost();
    level.vm = jass_newstate();
    
    FOR_LOOP(p, MAX_PLAYERS) {
        gameClient_t *client = game.clients+p;
        uint32_t playernum = G_ClientSlotMapPlayerNumber(mapinfo, p, local_player);
        g_edicts[p].client = client;
        G_InitMapPlayer(g_edicts+p, mapinfo, playernum);
    }
    if (mapinfo)
        G_SetCameraBounds(mapinfo->cameraBounds.bounds);
    G_WeatherInitMap();

    globals.num_edicts = game.max_clients;
    /* Quake II's body queue reserves real edicts before map entities, keeping all entity pointers in one address domain. */
    G_InitWaypoints();

    uint32_t spawn_count = 0;
    FOR_EACH_LIST(doodad_t const, doodad, entities) {
        if ((spawn_count++ & 127u) == 0) gi.LoadingFrame();
        if (!G_LoadMapUnitData() && G_MapObjectCreatedByMapScript(doodad->doodID))
            continue;
//        if (doodad->doodID == MAKEFOURCC('h', 'C', '0', '2')) {
//            int a=0;
//            printf("%.4s", )
//        }
        edict_t *ent = G_Spawn();
        if (!ent) {
            break;
        }
        ent->class_id = doodad->doodID;
        ent->variation = doodad->variation;
        ent->hero = doodad->hero;
        ent->s.player = G_NormalizeMapObjectPlayer(doodad->player);
        ent->s.origin = doodad->position;
        ent->s.angle = doodad->angle;
        ent->s.scale = doodad->scale.x;
        SP_CallSpawn(ent);
        if ((S_GoldMineIsMine(ent) || S_GoldMineIsOverlay(ent)) && doodad->goldAmount != (uint32_t)-1)
            ent->resources = doodad->goldAmount;
        if (ent->svflags & SVF_MONSTER) G_ApplyMapUnitTeamColor(ent, doodad);
        if (G_IsDestructable(ent)) {
            G_InitializeDestructablePlacement(ent, doodad);
            G_RegisterGroundSurface(ent);
        }
        gi.LinkEntity(ent);
    }
    S_MineOverlayBindPreplaced();
    SP_worldspawn(NULL);
    
    jass_dofile(level.vm, "Scripts\\common.j");
    gi.LoadingFrame();
    jass_dofile(level.vm, "Scripts\\Blizzard.j");
    gi.LoadingFrame();
//    jass_dofilenative(level.vm, "/Users/igor/Desktop/war3map.j");
    G_DumpPrologue02BurrowHandoffSource(level.mapinfo->mapscript);
    if (level.mapinfo->mapscript) {
        G_FixOrc07BridgeRestoreScript(level.mapinfo->mapscript);
        /* mapinfo is const through level, but its owned mapscript buffer is
         * mutable and world-owned for this load. */
        if (strstr(level.mapinfo->mapscript, "GetLastRestoredUnitBJ")) {
            mapInfo_t *mutable_mapinfo = (mapInfo_t *)level.mapinfo;
            if (!G_FixCampaignHeroRestoreScripts(&mutable_mapinfo->mapscript))
                fprintf(stderr, "G_SpawnEntities: one or more campaign Hero restore branches could not be reconciled\n");
        }
        jass_dobuffer(level.vm, level.mapinfo->mapscript);
    } else
        fprintf(stderr, "G_SpawnEntities: missing mapscript; skipping jass_dobuffer\n");
    gi.LoadingFrame();

    /* Warcraft executes config before main; this phase owns authored player colors, teams, and slots. */
    if (!level.scriptsConfigured && level.mapinfo && level.mapinfo->mapscript &&
        strstr(level.mapinfo->mapscript, "function config")) {
        jass_callbyname(level.vm, "config", false);
        if (!jass_rterror_pending(level.vm)) level.scriptsConfigured = true;
    }

    UI_Init();
    CM_BakeStaticObstacles();
    /* Start simulation from the map load itself so dedicated and listen-server restores share one lifecycle. */
    level.started = true;
}
 
/* Spawn a unit at a point while allowing map-restoration paths to skip presentation-only birth. */
static edict_t *SP_SpawnAtLocationInternal(uint32_t class_id, uint32_t player, vec2_t const *location, bool play_birth) {
    edict_t *ent = G_Spawn();
    gameClient_t *client;
    if (!ent) {
        return NULL;
    }
    ent->class_id = class_id;
    ent->s.class_id = class_id;
    ent->spawn_time = G_Time();
    ent->s.origin2 = *location;
    ent->s.origin.x = location->x;
    ent->s.origin.y = location->y;
    ent->s.origin.z = CM_GetHeightAtPoint(location->x, location->y);
    ent->s.scale = 1;
    ent->s.angle = -M_PI / 2;
    ent->s.player = player;
    SP_CallSpawn(ent);
    /* SP_SpawnUnit fills collision and the server broad-phase bounds depend on
     * that value. Link only after the class-owned spawn initializer runs. */
    gi.LinkEntity(ent);
    /* Dynamic unit creation must establish Hero progression independently of
     * presentation data.  SP_SpawnUnit already initializes normal Heroes, but
     * custom/minimal data may omit UnitUI/model rows while still defining Hero
     * attributes in UnitBalance.  The helper is idempotent, so applying it here
     * also keeps CreateUnit/training at Level 1 with one initial skill point. */
    if (G_UnitIsHero(ent)) {
        G_HeroInitializeProgression(ent);
    }
    if (play_birth && ent->birth) {
        ent->birth(ent);
    }
    client = G_GetPlayerClientByNumber(player);
    if ((ent->svflags & SVF_MONSTER) && client && client->ps.number == player) {
        G_InvalidateCommands(client);
        G_InvalidateUnitShortcutsForUnit(ent);
    }
    return ent;
}

edict_t *SP_SpawnAtLocation(uint32_t class_id, uint32_t player, vec2_t const *location) {
    return SP_SpawnAtLocationInternal(class_id, player, location, true);
}

edict_t *SP_SpawnAtLocationNoBirth(uint32_t class_id, uint32_t player, vec2_t const *location) {
    return SP_SpawnAtLocationInternal(class_id, player, location, false);
}

static bool bind_map_destructables = false;

void G_SetDestructableScriptBinding(bool enabled) {
    bind_map_destructables = enabled;
}

/* Runtime (JASS CreateDestructable) spawn of a destructable.  Mirrors the
 * map-doodad spawn loop in G_SpawnEntities: set class_id/variation/origin/
 * facing/scale, then route through SP_CallSpawn (which sends a destructable
 * class_id to SP_SpawnDestructable + SP_monster_tree, giving it a model, life,
 * collision and the core destructable lifecycle; tree_die remains a legacy
 * callback entry point, but death does not depend on that callback).
 * Destructables are neutral-passive, like the map-placed ones.  facing is in
 * radians (the native converts from JASS degrees).
 *
 * Parity note (Ghidra): the original CreateDestructable (FUN_003f80b0 ->
 * worker FUN_00621d90) always creates a fresh instance — its hash lookup
 * resolves the destructable *type* by objectid, not an existing entity by
 * position.  We diverge with find-or-create because OUR engine already spawns
 * every war3map.doo destructable in G_SpawnEntities, and the map's generated
 * CreateAllDestructables then "creates" the 13 named ones again to bind their
 * gg_dest_* handles + death triggers.  Reusing the pre-placed entity (like
 * unit_createorfind does for CreateUnit) yields the same observable result as
 * the original — one crate/gate carrying the trigger — instead of a stacked
 * duplicate.  Match a same-type destructable within 10 units of the spot. */
/* HACK: Positional binding is required until the map parser exposes the
 * generated script variable's editor creation ID. */
edict_t *G_CreateDestructable(uint32_t class_id, float x, float y, float z, float facing, float scale, uint32_t variation) {
    if (bind_map_destructables) {
        edict_t *best = NULL;
        float best_distance = 10.0f;

        FOR_LOOP(i, globals.num_edicts) {
            edict_t *existing = &g_edicts[i];
            float distance;

            if (!existing->inuse ||
                existing->class_id != class_id ||
                !G_IsDestructable(existing) ||
                !existing->destructable.map_placed ||
                existing->destructable.script_bound) {
                continue;
            }

            distance = Vector2_distance(
                &MAKE(vec2_t, x, y),
                &existing->s.origin2);

            if (distance >= best_distance) {
                continue;
            }

            best = existing;
            best_distance = distance;
        }

        if (best) {
            best->destructable.script_bound = true;

            G_ActivateScriptedDestructable(best,
                                           x,
                                           y,
                                           z,
                                           facing,
                                           scale,
                                           variation);

            CM_BakeStaticObstacles();
            return best;
        }
    }
    edict_t *ent = G_Spawn();
    if (!ent) return NULL;
    ent->class_id = class_id;
    ent->variation = variation;
    ent->s.player = PLAYER_NEUTRAL_PASSIVE;
    ent->s.origin = MAKE(vec3_t, x, y, z);
    ent->s.angle = facing;
    ent->s.scale = scale;
    ent->spawn_time = G_Time();
    SP_CallSpawn(ent);
    G_RegisterGroundSurface(ent);
    gi.LinkEntity(ent);
    if (G_IsDestructable(ent)) CM_BakeStaticObstacles();
    return ent;
}

edict_t *G_CreateDeadDestructable(uint32_t class_id,
                                 float x,
                                 float y,
                                 float z,
                                 float facing,
                                 float scale,
                                 uint32_t variation) {
    edict_t *ent = G_CreateDestructable(class_id, x, y, z, facing, scale, variation);

    if (ent) {
        G_SetDestructableDeadState(ent, false);
    }
    return ent;
}

bool SP_FindEmptySpaceAround(edict_t *townhall, uint32_t class_id, vec2_t *out, float *angle) {
    float const colsize = G_UnitUI(class_id)->selectionScale * SEL_SCALE / 2;
    float const start_angle = M_PI * 1.25f;
    FOR_LOOP(i, MAX_SPAWN_ITERATIONS) {
        float const radius = townhall->s.radius + colsize * (i * 2 + 1);
        float const num_points = M_PI * radius / colsize;
        FOR_LOOP(j, num_points) {
            *angle = start_angle + 2 * M_PI * j / num_points;
            *out = MAKE(vec2_t,
                townhall->s.origin2.x + cosf(*angle) * radius,
                townhall->s.origin2.y + sinf(*angle) * radius,
            );
            if (M_CheckCollision(out, colsize))
                continue;
            return true;
        }
    }
    return false;
}

static bool SP_CanPlaceUnitAt(edict_t *unit, vec2_t const *point) {
    uint8_t const blocked_flags = M_UnitStaticPathingFlags(unit);
    if (!unit || !point) {
        return false;
    }
    if (!CM_PointIsPathableForRadiusFlags(point, unit->collision, blocked_flags)) {
        return false;
    }

    FOR_LOOP(i, globals.num_edicts) {
        edict_t *other = &globals.edicts[i];
        vec2_t delta;

        if (other == unit || IS_HOLLOW(other) || other->movetype == MOVETYPE_NONE || other->collision <= 0.0f) {
            continue;
        }
        if (!!(other->aiflags & AI_FLYING) != !!(unit->aiflags & AI_FLYING)) {
            continue;
        }
        delta = Vector2_sub(&other->s.origin2, point);
        if (Vector2_len(&delta) < unit->collision + other->collision) {
            return false;
        }
    }
    return true;
}

/* The old per-candidate full edict scan made crowded CreateUnit spawns costly.
 * BoxEdicts bounds include each linked entity's collision radius; keep the
 * same precise circle/layer rules while querying only nearby units. */
static bool G_RepositionBlocker(edict_t const *other) {
    float dx, dy, reach;
    edict_t *unit = reposition_unit;
    if (other == unit || (G_IsItem(unit) && other == unit->item.carrier) ||
        IS_HOLLOW(other) || other->collision <= 0.0f ||
        !!(other->aiflags & AI_FLYING) != !!(unit->aiflags & AI_FLYING)) return false;
    dx = other->s.origin2.x - reposition_point->x;
    dy = other->s.origin2.y - reposition_point->y;
    reach = unit->collision + other->collision;
    return dx * dx + dy * dy < reach * reach;
}

static bool G_CanRepositionUnitAt(edict_t *unit, vec2_t const *point) {
    edict_t *blockers[MAX_REPOSITION_BLOCKERS];
    float radius;
    box2_t area;
    if (!unit || !point) return false;
    if (!CM_PointIsPathableForRadiusFlags(point, unit->collision, M_UnitStaticPathingFlags(unit))) return false;
    radius = MAX(0.0f, unit->collision);
    area = MAKE(box2_t, .min = { point->x - radius, point->y - radius },
                      .max = { point->x + radius, point->y + radius });
    reposition_unit = unit; reposition_point = point;
    return gi.BoxEdicts(&area, blockers, MAX_REPOSITION_BLOCKERS, G_RepositionBlocker) == 0;
}

/* Warcraft III SetUnitPosition is not the raw X/Y setter. Warsmash models the
 * native through CUnit.setPointAndCheckUnstuck(): test the requested point,
 * then walk a deterministic 64-world-unit square spiral for at most 300
 * candidates. Keep the requested point as the fallback when no candidate is
 * legal, matching Warsmash's outputX/outputY initialization. */
bool G_FindUnitUnstuckPosition(edict_t *unit, vec2_t const *requested, vec2_t *out) {
    int check_x = 0, check_y = 0;

    if (!unit || !requested || !out) {
        return false;
    }
    *out = *requested;
    for (int i = 0; i < 300; i++) {
        vec2_t const candidate = {
            requested->x + check_x * 64.0f,
            requested->y + check_y * 64.0f,
        };
        int const phase = ((int)floor(sqrt((double)(4 * i + 1)))) % 4;

        if (G_CanRepositionUnitAt(unit, &candidate)) {
            *out = candidate;
            return true;
        }

        /* Equivalent to Warsmash's cardinal cos/sin update, without relying
         * on floating-point truncation around PI/2 and 3*PI/2. */
        switch (phase) {
        case 0: check_x--; break;
        case 1: check_y--; break;
        case 2: check_x++; break;
        default: check_y++; break;
        }
    }
    return false;
}

typedef struct {
    edict_t *producer;
    edict_t *unit;
    float     spacing;
    vec2_t *out;
    float    *angle;
} unitExitCtx_t;

static bool SP_TryUnitExitCandidate(unitExitCtx_t const *ctx, int grid_x, int grid_y) {
    vec2_t const candidate = {
        ctx->producer->s.origin2.x + (float)grid_x * ctx->spacing,
        ctx->producer->s.origin2.y + (float)grid_y * ctx->spacing,
    };

    /* MOVETYPE_NONE buildings are omitted from the dynamic collision scan;
     * their authored pathing footprint still owns the space the new unit
     * must clear before it becomes visible. */
    if (CM_DistanceToPathingFootprint(ctx->producer, &candidate) < ctx->unit->collision)
        return false;
    if (!SP_CanPlaceUnitAt(ctx->unit, &candidate)) {
        return false;
    }
    *ctx->out = candidate;
    *ctx->angle = atan2f(candidate.y - ctx->producer->s.origin2.y,
                         candidate.x - ctx->producer->s.origin2.x);
    return true;
}

/* Trained units are created at their producer and remain hidden until a legal
 * exit point is found. Search deterministic 64-world-unit square rings, using
 * the trained unit's real collision radius against both the baked static
 * pathmap and dynamic unit circles. */
bool SP_FindUnitExitPosition(edict_t *producer, edict_t *unit, vec2_t *out, float *angle) {
    uint32_t const max_candidates = 300;
    uint32_t tested = 0;
    unitExitCtx_t ctx;

    if (!producer || !unit || !out || !angle) {
        return false;
    }

    ctx = (unitExitCtx_t){ producer, unit, 64.0f, out, angle };

    for (int ring = 1; tested < max_candidates; ring++) {
        int const lo = -ring;
        int const hi = ring;

        for (int x = lo; x <= hi && tested < max_candidates; x++, tested++) {
            if (SP_TryUnitExitCandidate(&ctx, x, lo)) return true;
        }
        for (int y = lo + 1; y <= hi && tested < max_candidates; y++, tested++) {
            if (SP_TryUnitExitCandidate(&ctx, hi, y)) return true;
        }
        for (int x = hi - 1; x >= lo && tested < max_candidates; x--, tested++) {
            if (SP_TryUnitExitCandidate(&ctx, x, hi)) return true;
        }
        for (int y = hi - 1; y > lo && tested < max_candidates; y--, tested++) {
            if (SP_TryUnitExitCandidate(&ctx, lo, y)) return true;
        }
    }
    return false;
}
