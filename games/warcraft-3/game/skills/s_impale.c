#include "s_skills.h"

#define IMPALE_HIT_ID MAKEFOURCC('I', 'm', 'p', 'H')

/* Target identities are attached to the current wave instead of to the victim:
 * a unit can be hit once by each distinct cast, including simultaneous waves.
 * Edicts are reused; target spawn identity protects those reuse boundaries. */
static bool impale_already_hit(edict_t const *wave, edict_t const *target) {
    FILTER_EDICTS(mark, mark->class_id == IMPALE_HIT_ID && mark->owner == wave &&
                  mark->damage == wave->spawn_time && mark->goalentity == target &&
                  mark->resources == target->spawn_time)
        return true;
    return false;
}

static void impale_end_wave(edict_t *wave) {
    /* Release markers before recycling the wave slot. */
    FOR_LOOP(i, globals.num_edicts) {
        edict_t *mark = &globals.edicts[i];
        if (mark->inuse && mark->class_id == IMPALE_HIT_ID && mark->owner == wave &&
            mark->damage == wave->spawn_time) G_FreeEdict(mark);
    }
    G_FreeEdict(wave);
}

static bool impale_hit(edict_t *wave, impaleWave_t const *state, edict_t *target) {
    edict_t *mark;
    edict_t *caster = wave->owner;
    cstring_t buff;
    if (!S_SpellIsAliveTarget(target) || !S_SpellIsEnemy(caster, target) ||
        !S_SpellAllowsAreaTarget(state->ability, caster, target) ||
        impale_already_hit(wave, target)) return false;

    /* Record the hit before damage. This prevents repeated hits when damage
     * causes immediate unit events, and protects status refresh callbacks. */
    mark = G_Spawn();
    if (!mark) return false;
    mark->class_id = IMPALE_HIT_ID;
    mark->svflags |= SVF_NOCLIENT;
    mark->owner = wave;
    mark->goalentity = target;
    mark->damage = wave->spawn_time;
    mark->resources = target->spawn_time;
    S_SpellDamage(target, caster, (int)state->damage);
    buff = S_SpellBuffId(state->ability, state->level);
    if (!M_IsDead(target) && buff)
        S_SpellApplyTimedStatusFromAbility(target, state->ability, state->level, buff,
            S_SpellHeroDuration(state->ability, state->level, target));
    return true;
}

void impale_wave_think(edict_t *wave) {
    impaleWave_t *state = G_GetImpaleWave(wave);
    edict_t *caster = wave->owner;
    float elapsed, end, start;
    uint32_t count;
    if (!state || !caster || !caster->inuse || caster->spawn_time != state->caster_spawn_time) {
        impale_end_wave(wave);
        return;
    }
    elapsed = (float)(G_Time() - state->start_ms) / 1000.0f;
    end = state->duration > 0.0f
        ? state->distance * MIN(1.0f, MAX(0.0f, elapsed / state->duration))
        : state->distance;
    start = state->previous_distance;
    if (end < start) end = start;
    if (end > start) {
        /* Snapshot count before any hits spawn markers; only preexisting units
         * are eligible for this frame's sweep. Nearest-first ordering gives
         * deterministic progress when status or death callbacks spawn units. */
        float const step = end - start;
        uint32_t previous_index = 0;
        float previous_along = 0.0f;
        bool have_previous = false;
        count = globals.num_edicts;
        for (;;) {
            edict_t *best = NULL;
            uint32_t best_index = 0;
            float best_along = 0.0f;
            FOR_LOOP(i, count) {
                edict_t *target = &globals.edicts[i];
                vec2_t delta;
                float along, across;
                if (!S_SpellIsAliveTarget(target) || !S_SpellIsEnemy(caster, target) ||
                    !S_SpellAllowsAreaTarget(state->ability, caster, target) ||
                    impale_already_hit(wave, target)) continue;
                delta = Vector2_sub(&target->s.origin2, &state->origin);
                along = Vector2_dot(&delta, &state->direction) - start;
                if (along < 0.0f || along > step ||
                    (have_previous && (along < previous_along ||
                     (along == previous_along && i <= previous_index)))) continue;
                across = delta.x * state->direction.y - delta.y * state->direction.x;
                if (fabsf(across) > state->half_width + MAX(0.0f, target->collision)) continue;
                if (!best || along < best_along ||
                    (along == best_along && i < best_index)) {
                    best = target;
                    best_index = i;
                    best_along = along;
                }
            }
            if (!best) break;
            if (!impale_hit(wave, state, best)) break;
            previous_along = best_along;
            previous_index = best_index;
            have_previous = true;
        }
    }
    state->previous_distance = end;
    wave->s.origin2 = Vector2_mad(&state->direction, end, &state->origin);
    if (elapsed >= state->duration || end >= state->distance)
        impale_end_wave(wave);
}

/* Impale's impact stun and lift have separate, longer lifetimes. Patch 1
 * changes how and when the existing BUim status is applied, not its state
 * contribution; patch 2 will implement and test the stun/lift lifecycle. */
static bool impale_validate(edict_t *caster, spellTarget_t target, abilityitem_t const *spell) {
    uint32_t level;
    if (!caster || !spell || target.type != SPELL_TARGET_POINT) return false;
    level = S_SpellLevel(caster, spell->code);
    return Vector2_distance(&caster->s.origin2, &target.point) > 0.0f &&
           S_SpellData(spell->code, level, 1) > 0.0f &&
           S_SpellData(spell->code, level, 2) > 0.0f;
}

BZ_ABILITY_PROC(CAbilityImpale) {
    spellTarget_t target = call && call->target ? *call->target : MAKE(spellTarget_t, .type = SPELL_TARGET_NONE);
    abilityitem_t const *spell = call ? call->item : NULL;
    impaleWave_t *state;
    edict_t *wave;
    vec2_t offset;
    float direction_len;
    uint32_t level;
    if (msg == A_VALIDATE) return impale_validate(ent, target, spell);
    if (msg != A_EXECUTE) return CAbilitySimpleSpell(ent, msg, call);
    if (!impale_validate(ent, target, spell)) return false;
    level = S_SpellLevel(ent, spell->code);
    wave = G_Spawn();
    if (!wave) return false;
    state = G_AddImpaleWave(wave);
    wave->class_id = spell->code;
    wave->owner = ent;
    wave->spawn_time = G_Time();
    wave->s.player = ent->s.player;
    wave->s.origin2 = ent->s.origin2;
    wave->svflags |= SVF_NOCLIENT;
    state->origin = ent->s.origin2;
    offset = Vector2_sub(&target.point, &state->origin);
    direction_len = Vector2_distance(&target.point, &state->origin);
    state->direction = Vector2_scale(&offset, 1.0f / direction_len);
    state->distance = S_SpellData(spell->code, level, 1);
    state->duration = S_SpellData(spell->code, level, 2);
    state->half_width = MAX(0.0f, S_SpellNumber(spell->code, ABILITY_NUMBER_AREA, level) * 0.5f);
    state->damage = S_SpellData(spell->code, level, 3);
    state->start_ms = G_Time();
    state->caster_spawn_time = ent->spawn_time;
    state->ability = spell->code;
    state->level = level;
    wave->think = impale_wave_think;
    return true;
}
