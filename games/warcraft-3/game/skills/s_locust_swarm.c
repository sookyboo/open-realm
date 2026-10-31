#include "s_skills.h"

#define LOCUST_SEEKING 1u
#define LOCUST_ATTACKING 2u
#define LOCUST_RETURNING 3u
#define LOCUST_REACQUIRE_MS 250u
#define LOCUST_MAX_ATTACKERS_PER_TARGET 256u
#define LOCUST_RECALL_GRACE_MS 8000u

static void locust_begin_return(edict_t *member, locustMember_t *state, edict_t *caster);

static bool locust_reference_valid(edict_t *ent, uint32_t spawn_time) {
    return ent && ent->inuse && ent->spawn_time == spawn_time;
}

static bool locust_member_in_swarm(edict_t *member, edict_t *controller) {
    locustMember_t *state = G_GetLocustMember(member);
    return state && state->controller == controller &&
           state->controller_spawn_time == controller->spawn_time;
}

static void locust_member_die(edict_t *member) {
    if (!member || !member->inuse || M_IsDead(member)) return;
    if (member->die) member->die(member, member->owner);
    else unit_die(member, member->owner);
}

static void locust_swarm_end(edict_t *controller) {
    locustSwarm_t *swarm = G_GetLocustSwarm(controller);
    if (swarm) swarm->active = false;
    FILTER_EDICTS(member, locust_member_in_swarm(member, controller))
        locust_member_die(member);
    G_FreeEdict(controller);
}

static void locust_swarm_begin_recall(edict_t *controller, locustSwarm_t *swarm) {
    swarm->active = false;
    swarm->recalling = true;
    swarm->recall_deadline_ms = G_Time() + LOCUST_RECALL_GRACE_MS;
    FILTER_EDICTS(member, locust_member_in_swarm(member, controller)) {
        locustMember_t *state = G_GetLocustMember(member);
        if (state->damage_credit > 0.0f) locust_begin_return(member, state, controller->owner);
        else locust_member_die(member);
    }
}

void S_LocustSwarmCancelForCaster(edict_t *caster) {
    uint32_t const count = globals.num_edicts;
    FOR_LOOP(i, count) {
        edict_t *controller = &globals.edicts[i];
        if (controller->inuse && controller->think == locust_swarm_think && controller->owner == caster)
            locust_swarm_end(controller);
    }
}

static void locust_spawn_one(edict_t *controller, locustSwarm_t *swarm) {
    edict_t *caster = controller->owner;
    float const angle = (float)swarm->released * 2.39996323f;
    vec2_t point = caster->s.origin2;
    edict_t *locust;
    locustMember_t *member;
    point.x += cosf(angle) * 48.0f;
    point.y += sinf(angle) * 48.0f;
    locust = S_SummonAbilityAt(caster, swarm->ability, swarm->unit_id, &point,
                               (float)(swarm->end_ms - G_Time()) / 1000.0f);
    if (!locust) return;
    member = G_AddLocustMember(locust);
    if (!member) { locust_member_die(locust); return; }
    member->controller = controller;
    member->controller_spawn_time = controller->spawn_time;
    member->release_index = swarm->released;
    member->state = LOCUST_SEEKING;
    member->next_acquire_ms = G_Time();
    locust->owner = caster;
    locust->summon_ability = swarm->ability;
    locust->think = locust_member_think;
    locust->s.player = caster->s.player;
    if (locust->stand) locust->stand(locust);
    swarm->released++;
}

void locust_swarm_think(edict_t *controller) {
    locustSwarm_t *swarm = G_GetLocustSwarm(controller);
    edict_t *caster = controller->owner;
    uint32_t now = G_Time();
    if (!swarm || !locust_reference_valid(caster, swarm->caster_spawn_time) || M_IsDead(caster)) {
        locust_swarm_end(controller);
        return;
    }
    if (swarm->active && now >= swarm->end_ms) locust_swarm_begin_recall(controller, swarm);
    if (swarm->recalling) {
        bool any_alive = false;
        FILTER_EDICTS(member, locust_member_in_swarm(member, controller) && !M_IsDead(member)) any_alive = true;
        if (!any_alive || now >= swarm->recall_deadline_ms) {
            locust_swarm_end(controller);
            return;
        }
    }
    if (!swarm->active) return;
    controller->s.origin = caster->s.origin;
    controller->s.origin2 = caster->s.origin2;
    gi.LinkEntity(controller);
    while (swarm->released < swarm->total && now >= swarm->next_release_ms) {
        locust_spawn_one(controller, swarm);
        if (swarm->release_interval_ms == 0) break;
        swarm->next_release_ms += swarm->release_interval_ms;
    }
}

static uint32_t locust_target_occupancy(edict_t *controller, edict_t *target) {
    uint32_t count = 0;
    FILTER_EDICTS(member, locust_member_in_swarm(member, controller) && S_SpellIsAliveTarget(member)) {
        locustMember_t const *state = G_GetLocustMember(member);
        if (state->state == LOCUST_ATTACKING && state->target == target &&
            state->target_spawn_time == target->spawn_time) count++;
    }
    return count;
}

static bool locust_target_full(edict_t *controller, locustSwarm_t const *swarm, edict_t *target) {
    return locust_target_occupancy(controller, target) >=
           (uint32_t)MAX(1.0f, MIN((float)LOCUST_MAX_ATTACKERS_PER_TARGET, swarm->target_cap));
}

static edict_t *locust_find_target(edict_t *member, locustSwarm_t *swarm) {
    edict_t *caster = member->owner, *best = NULL;
    float best_distance = FLT_MAX;
    FILTER_EDICTS(target, target != caster && S_SpellIsAliveTarget(target) &&
                  S_SpellIsEnemy(caster, target) &&
                  !G_UnitHasFlag(target, UNIT_FLAG_INVULNERABLE) &&
                  !unit_hasstatusstate(target, WC3_STATUS_STATE_INVULNERABLE) &&
                  S_SpellAllowsAreaTarget(swarm->ability, caster, target)) {
        float distance = Vector2_distance(&target->s.origin2, &caster->s.origin2);
        if (distance > swarm->area || locust_target_full(G_GetLocustMember(member)->controller, swarm, target)) continue;
        if (!best || distance < best_distance ||
            (distance == best_distance && target->s.number < best->s.number)) {
            best = target;
            best_distance = distance;
        }
    }
    return best;
}

static void locust_begin_return(edict_t *member, locustMember_t *state, edict_t *caster) {
    state->state = LOCUST_RETURNING;
    state->target = NULL;
    state->target_spawn_time = 0;
    if (caster && caster->inuse) order_move(member, caster);
}

void locust_member_think(edict_t *member) {
    locustMember_t *state = G_GetLocustMember(member);
    edict_t *controller, *caster, *target;
    locustSwarm_t *swarm;
    uint32_t now = G_Time();
    if (!member || !member->inuse || M_IsDead(member)) return;
    if (!state || !(controller = state->controller) ||
        !locust_reference_valid(controller, state->controller_spawn_time) ||
        !(swarm = G_GetLocustSwarm(controller)) || (!swarm->active && !swarm->recalling)) {
        locust_member_die(member);
        return;
    }
    caster = controller->owner;
    if (!locust_reference_valid(caster, swarm->caster_spawn_time) || M_IsDead(caster)) {
        locust_member_die(member);
        return;
    }
    if (state->state == LOCUST_RETURNING) {
        float const arrival = MAX(48.0f, member->collision + caster->collision);
        if (Vector2_distance(&member->s.origin2, &caster->s.origin2) <= arrival) {
            if (state->damage_credit > 0.0f)
                S_SpellHeal(caster, state->damage_credit * swarm->heal_factor);
            state->damage_credit = 0.0f;
            if (swarm->recalling) { locust_member_die(member); return; }
            state->state = LOCUST_SEEKING;
            state->next_acquire_ms = now;
        }
        return;
    }
    target = state->target;
    if (swarm->recalling) {
        if (state->damage_credit <= 0.0f) { locust_member_die(member); return; }
        if (Vector2_distance(&member->s.origin2, &caster->s.origin2) <= MAX(48.0f, member->collision + caster->collision)) {
            S_SpellHeal(caster, state->damage_credit * swarm->heal_factor);
            locust_member_die(member);
        } else if (state->state != LOCUST_RETURNING) locust_begin_return(member, state, caster);
        return;
    }
    if (!locust_reference_valid(target, state->target_spawn_time) || !S_SpellIsAliveTarget(target) ||
        !S_SpellIsEnemy(caster, target) ||
        Vector2_distance(&target->s.origin2, &caster->s.origin2) > swarm->area ||
        locust_target_full(controller, swarm, target)) {
        state->target = NULL;
        state->target_spawn_time = 0;
        state->state = LOCUST_SEEKING;
        if (state->damage_credit >= swarm->return_threshold && state->damage_credit > 0.0f) {
            locust_begin_return(member, state, caster);
            return;
        }
    }
    if (state->state == LOCUST_SEEKING && now >= state->next_acquire_ms) {
        target = locust_find_target(member, swarm);
        state->next_acquire_ms = now + LOCUST_REACQUIRE_MS;
        if (target && S_OrderAttack(member, target)) {
            state->state = LOCUST_ATTACKING;
            state->target = target;
            state->target_spawn_time = target->spawn_time;
            state->next_attack_ms = now;
        }
    }
    if (state->state == LOCUST_ATTACKING && state->target &&
        locust_reference_valid(state->target, state->target_spawn_time) && now >= state->next_attack_ms) {
        unitAttack_t const *weapon = S_LocustAttackWeapon(member, state->target);
        float actual;
        if (!weapon || !S_AttackCanTarget(member, state->target)) {
            state->state = LOCUST_SEEKING;
            state->target = NULL;
            state->target_spawn_time = 0;
            state->next_acquire_ms = now + LOCUST_REACQUIRE_MS;
            return;
        }
        state->next_attack_ms = now + (uint32_t)MAX(100.0f, weapon->cooldown * 1000.0f);
        actual = S_LocustAttackHit(member, state->target);
        state->damage_credit += actual;
        if (state->damage_credit >= swarm->return_threshold && state->damage_credit > 0.0f)
            locust_begin_return(member, state, caster);
    }
}

void S_LocustSwarmAttackLanded(edict_t *attacker, edict_t *target, float actual_damage) {
    locustMember_t *member = G_GetLocustMember(attacker);
    locustSwarm_t *swarm;
    if (!member || member->state != LOCUST_ATTACKING || actual_damage <= 0.0f ||
        !locust_reference_valid(member->target, member->target_spawn_time) || member->target != target ||
        !locust_reference_valid(member->controller, member->controller_spawn_time) ||
        !(swarm = G_GetLocustSwarm(member->controller)) || !swarm->active) return;
    member->damage_credit += actual_damage;
    if (member->damage_credit >= swarm->return_threshold)
        locust_begin_return(attacker, member, attacker->owner);
}

static bool locust_swarm_validate(edict_t *caster, abilityitem_t const *spell) {
    uint32_t level;
    return caster && spell && S_SpellIsAliveTarget(caster) &&
           (level = S_SpellLevel(caster, spell->code)) > 0 &&
           S_SpellUnitId(spell->code, level) && S_SpellDuration(spell->code, level, false) > 0.0f;
}

static void locust_swarm_cast(edict_t *caster, abilityitem_t const *spell) {
    uint32_t level = S_SpellLevel(caster, spell->code);
    float duration = S_SpellDuration(spell->code, level, false);
    edict_t *controller = G_Spawn();
    locustSwarm_t *swarm;
    if (!controller) return;
    controller->owner = caster;
    controller->class_id = spell->code;
    controller->s.player = caster->s.player;
    controller->s.origin = caster->s.origin;
    controller->s.origin2 = caster->s.origin2;
    swarm = G_AddLocustSwarm(controller);
    if (!swarm) { G_FreeEdict(controller); return; }
    swarm->caster_spawn_time = caster->spawn_time;
    swarm->ability = spell->code;
    swarm->level = level;
    swarm->start_ms = G_Time();
    swarm->end_ms = G_Time() + (uint32_t)(duration * 1000.0f);
    swarm->release_interval_ms = (uint32_t)MAX(FRAMETIME, S_SpellData(spell->code, level, 2) * 1000.0f);
    swarm->next_release_ms = G_Time();
    swarm->total = (uint32_t)MAX(1.0f, S_SpellData(spell->code, level, 1));
    swarm->unit_id = S_SpellUnitId(spell->code, level);
    swarm->area = MAX(0.0f, S_SpellNumber(spell->code, ABILITY_NUMBER_AREA, level));
    swarm->target_cap = MAX(1.0f, S_SpellData(spell->code, level, 3));
    swarm->heal_factor = MAX(0.0f, S_SpellData(spell->code, level, 4));
    swarm->return_threshold = MAX(0.0f, S_SpellData(spell->code, level, 5));
    swarm->active = true;
    controller->s.sound = (uint16_t)G_AbilityEffectSoundIndex(spell->code, true);
    controller->think = locust_swarm_think;
}

BZ_ABILITY_PROC(CAbilityLocustSwarm) {
    abilityitem_t const *spell = call ? call->item : NULL;
    if (msg == A_VALIDATE) return locust_swarm_validate(ent, spell);
    if (msg == A_EXECUTE && locust_swarm_validate(ent, spell)) {
        S_LocustSwarmCancelForCaster(ent);
        locust_swarm_cast(ent, spell);
        return true;
    }
    return CAbilitySimpleSpell(ent, msg, call);
}
