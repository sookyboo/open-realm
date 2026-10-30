#include "s_skills.h"

/* ANto is a channeled summon, not an area-damage spell on the Sea Witch.
 * ntor owns Atdg, Atsp, Atwa and Aasl in UnitAbilities.slk. Simulation and
 * animation are separate: the spawned unit supplies its model, while this
 * channel thinker owns expiry and periodic actions. */
#define TORNADO MAKEFOURCC('A','N','t','o')
#define TORNADO_DAMAGE MAKEFOURCC('A','t','d','g')
#define TORNADO_SPIN MAKEFOURCC('A','t','s','p')
#define TORNADO_MARK MAKEFOURCC('T','s','p','M')
#define TORNADO_DAMAGE_INTERVAL_MS 1000u
#define TORNADO_SPIN_DEFAULT_INTERVAL_MS 3000u /* classic guide; overridden by Atsp DataA */
#define TORNADO_SPIN_REPEAT_MS 22000u /* classic guide; retail timer algorithm still under review */

static bool tornado_valid_unit(edict_t *unit) {
    return unit && unit->inuse && !M_IsDead(unit) &&
           unit->summon_ability && G_AbilityCode(unit->summon_ability) == TORNADO;
}

/* Each toss cooldown marker holds two generation-checked pointers. Markers
 * are private (no snapshot) and are freed when their parent thinker ends. */
static bool tornado_recent_target(edict_t *thinker, edict_t *target) {
    FILTER_EDICTS(mark, mark->class_id == TORNADO_MARK &&
                  S_SpellChannelOwner(mark) == thinker &&
                  S_SpellChannelTarget(mark) == target &&
                  (int32_t)(G_Time() - mark->resources) < 0)
        return true;
    return false;
}

static void tornado_mark_target(edict_t *thinker, edict_t *target) {
    edict_t *mark = S_SpellIdentityThinker(thinker, TORNADO_MARK, target);
    if (!mark) return;
    mark->svflags |= SVF_NOCLIENT;
    mark->resources = G_Time() + TORNADO_SPIN_REPEAT_MS;
}

static void tornado_release_markers(edict_t *thinker, bool all) {
    FILTER_EDICTS(mark, mark->class_id == TORNADO_MARK &&
                  S_SpellChannelOwner(mark) == thinker &&
                  (all || (int32_t)(G_Time() - mark->resources) >= 0))
        G_FreeEdict(mark);
}

/* Atdg: Area is the outer radius; DataA is its DPS. DataB/C give the
 * medium-radius/DPS and DataD/E the close-radius/DPS. A building belongs to
 * exactly one band. Read all values from its actual owned ability row. */
static void tornado_damage_buildings(edict_t *tornado) {
    abilityAliasRef_t ability = S_ResolveAbilityAlias(tornado, TORNADO_DAMAGE);
    abilityLevel_t const *row;
    float outer, medium, inner, outer_dps, medium_dps, inner_dps;
    if (!ability.alias || !(row = G_AbilityLevel(ability.alias, ability.level))) return;
    outer = MAX(0.0f, row->area);
    outer_dps = MAX(0.0f, S_SpellData(ability.alias, ability.level, 1));
    medium = MAX(0.0f, S_SpellData(ability.alias, ability.level, 2));
    medium_dps = MAX(0.0f, S_SpellData(ability.alias, ability.level, 3));
    inner = MAX(0.0f, S_SpellData(ability.alias, ability.level, 4));
    inner_dps = MAX(0.0f, S_SpellData(ability.alias, ability.level, 5));
    if (!outer) return;
    FILTER_EDICTS(target, target != tornado && G_UnitIsStructure(target) &&
                  S_SpellIsAliveTarget(target) && S_SpellIsEnemy(tornado, target)) {
        float const dist = Vector2_distance(&target->s.origin2, &tornado->s.origin2);
        float dps;
        if (dist > outer || !S_SpellAllowsAreaTarget(ability.alias, tornado, target)) continue;
        dps = inner > 0.0f && dist <= inner ? inner_dps :
              medium > 0.0f && dist <= medium ? medium_dps : outer_dps;
        if (dps > 0.0f) S_SpellDamage(target, tornado, (int)(dps + 0.5f));
    }
}

/* Atsp temporarily makes a nearby ground unit uncommandable through the
 * shared Cyclone status. Its own Btsp model is distinct from ntor's model.
 * The chooser is a persisted per-thinker PRNG, not process rand(). */
static void tornado_spin_one(edict_t *tornado, edict_t *thinker) {
    abilityAliasRef_t ability = S_ResolveAbilityAlias(tornado, TORNADO_SPIN);
    abilityLevel_t const *row;
    edict_t *choice = NULL;
    uint32_t seen = 0;
    if (!ability.alias || !(row = G_AbilityLevel(ability.alias, ability.level)) || row->area <= 0.0f) return;
    FILTER_EDICTS(target, target != tornado && S_SpellIsAliveTarget(target) &&
                  S_SpellIsEnemy(tornado, target) && G_UnitTargetType(target) == TARG_GROUND) {
        float const distance = Vector2_distance(&target->s.origin2, &tornado->s.origin2);
        if (distance > row->area || tornado_recent_target(thinker, target) ||
            !S_SpellAllowsAreaTarget(ability.alias, tornado, target) ||
            S_UnitIsCycloned(target)) continue;
        thinker->variation = thinker->variation * 1664525u + 1013904223u;
        if (thinker->variation % ++seen == 0) choice = target;
    }
    if (choice) {
        float const seconds = S_SpellResistantDuration(ability.alias, ability.level, choice);
        if (seconds > 0.0f) {
            heroabilitystatus_t *slot = S_SpellApplyTimedStatusFromAbility(
                choice, ability.alias, ability.level, "Bcyc", seconds);
            if (slot) {
                /* Bcyc is the simulation lock; Btsp supplies the separately
                 * authored small tornado effect, not the main unit model. */
                G_SpawnAbilityEffectTarget(MAKEFOURCC('B','t','s','p'),
                                           WC3_EFFECT_EFFECT, 0, choice, "sprite,first", true);
                choice->goalentity = NULL;
                choice->currentmove = &holdpos_move_stand;
                tornado_mark_target(thinker, choice);
            }
        }
    }
}

static void tornado_finish(edict_t *thinker, edict_t *tornado) {
    tornado_release_markers(thinker, true);
    if (tornado && tornado->inuse) {
        /* Do not explode the unit: its own Death sequence plays once and the
         * ordinary corpse/decay lifecycle then retires the rendered model. */
        if (!M_IsDead(tornado)) {
            if (tornado->die) tornado->die(tornado, thinker->owner);
            else unit_die(tornado, thinker->owner);
        }
    }
    S_SpellEndChannel(thinker);
}

void tornado_think(edict_t *thinker) {
    edict_t *tornado = S_SpellChannelTarget(thinker);
    uint32_t now = G_Time();
    if (!tornado_valid_unit(tornado) || !S_SpellChannelActive(thinker) ||
        (int32_t)(now - thinker->resources) >= 0) {
        tornado_finish(thinker, tornado);
        return;
    }
    tornado_release_markers(thinker, false);
    /* Catch up using fixed, authored one-second damage pulses, even when a
     * server frame was skipped; never apply damage at initial spawn time. */
    while ((int32_t)(now - thinker->freetime) >= 0 &&
           (int32_t)(thinker->resources - thinker->freetime) > 0) {
        tornado_damage_buildings(tornado);
        thinker->freetime += TORNADO_DAMAGE_INTERVAL_MS;
    }
    if ((int32_t)(now - thinker->damage) >= 0) {
        abilityAliasRef_t spin = S_ResolveAbilityAlias(tornado, TORNADO_SPIN);
        float const interval = spin.alias ? S_SpellData(spin.alias, spin.level, 1) : 0.0f;
        uint32_t const interval_ms = interval > 0.0f ? (uint32_t)(interval * 1000.0f) :
                                     TORNADO_SPIN_DEFAULT_INTERVAL_MS;
        tornado_spin_one(tornado, thinker);
        thinker->damage = now + MAX(FRAMETIME, interval_ms);
    }
}

BZ_ABILITY_PROC(CAbilityTornado) {
    edict_t *summon, *thinker;
    uint32_t unit_id, level;
    vec2_t location;
    float angle, duration;
    animation_t const *birth;
    if (msg != A_EXECUTE) return CAbilitySimpleSpell(ent, msg, call);
    if (!ent || !call || !call->item) return false;
    level = S_SpellLevel(ent, call->item->code);
    unit_id = S_SpellUnitId(call->item->code, level);
    duration = S_SpellDuration(call->item->code, level, false);
    if (!unit_id || duration <= 0.0f) return false;
    location = ent->s.origin2;
    angle = ent->s.angle;
    location.x += cosf(angle) * MAX(64.0f, ent->collision + 32.0f);
    location.y += sinf(angle) * MAX(64.0f, ent->collision + 32.0f);
    SP_FindEmptySpaceAround(ent, unit_id, &location, &angle);
    summon = S_SummonAbilityAt(ent, call->item->code, unit_id, &location, duration);
    if (!summon) return false;
    /* BNto is the authored summon buff, independent of the BTLF lifetime
     * marker. Respect custom BuffID aliases instead of hardcoding icon art. */
    {
        cstring_t buff = S_SpellBuffId(call->item->code, level);
        if (buff && strlen(buff) >= 4)
            S_SpellApplyTimedStatusFromAbility(summon, call->item->code, level,
                                               buff, duration);
    }
    /* The generic summoned-unit path calls stand immediately; ntor must first
     * play its actual Birth animation, then loop its combined Stand Walk. */
    birth = G_GetUnitAnimation(summon, "birth");
    if (birth) {
        unit_birth(summon);
        summon->wait = MAX(FRAMETIME / 1000.0f,
                           (float)(birth->interval[1] - birth->interval[0]) / 1000.0f);
    }
    thinker = S_SpellChannelThinker(ent, call->item->code);
    if (!thinker) {
        if (summon->die) summon->die(summon, ent);
        else unit_die(summon, ent);
        return false;
    }
    thinker->goalentity = summon;
    G_GetChannel(thinker)->target_spawn_time = summon->spawn_time;
    thinker->resources = G_Time() + (uint32_t)(duration * 1000.0f);
    thinker->freetime = G_Time() + TORNADO_DAMAGE_INTERVAL_MS;
    thinker->damage = G_Time() + TORNADO_SPIN_DEFAULT_INTERVAL_MS;
    thinker->variation = (summon->s.number + 1u) * 2654435761u ^ summon->spawn_time;
    thinker->svflags |= SVF_NOCLIENT;
    thinker->think = tornado_think;
    return true;
}

#ifdef BZ_TESTS
/* Test the actual damage-band evaluator with synthetic non-stock SLK values. */
void S_TestTornadoBuildingPulse(edict_t *tornado) { tornado_damage_buildings(tornado); }
#endif

BZ_ABILITY_PROC(CAbilityTornadoDamage) { return CAbilityPassive(ent, msg, call); }
BZ_ABILITY_PROC(CAbilityTornadoSpin) { return CAbilityPassive(ent, msg, call); }
