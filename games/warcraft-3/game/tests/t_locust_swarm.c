#ifdef BZ_TESTS
#include "test.h"
#include "../skills/s_skills.h"

#define LS_ABILITY MAKEFOURCC('A','U','l','s')
#define LS_UNIT MAKEFOURCC('h','f','o','o') /* non-stock UnitID tests data resolution */

/* DataA=3, DataB=0.25, Dur=5 and UnitID=hfoo intentionally differ from
 * stock AUls 20/0.2/30/uloc. The cast must use the production ability row. */
static char const locust_test_slk[] =
    "ID;PWXL;N;EBB;Y2;X14\n"
    "C;Y1;X1;K\"alias\"\nC;Y1;X2;K\"code\"\nC;Y1;X3;K\"levels\"\n"
    "C;Y1;X4;K\"targs\"\nC;Y1;X5;K\"Dur1\"\nC;Y1;X6;K\"DataA1\"\n"
    "C;Y1;X7;K\"DataB1\"\nC;Y1;X8;K\"DataC1\"\nC;Y1;X9;K\"DataD1\"\n"
    "C;Y1;X10;K\"DataE1\"\nC;Y1;X11;K\"UnitID1\"\nC;Y1;X12;K\"Area1\"\n"
    "C;Y1;X13;K\"Cost1\"\nC;Y1;X14;K\"Cool1\"\n"
    "C;Y2;X1;K\"AUls\"\nC;Y2;X2;K\"AUls\"\nC;Y2;X3;K1\n"
    "C;Y2;X4;K\"\"\nC;Y2;X5;K5\nC;Y2;X6;K3\nC;Y2;X7;K0.25\n"
    "C;Y2;X8;K2\nC;Y2;X9;K0.5\nC;Y2;X10;K13\nC;Y2;X11;K\"hfoo\"\n"
    "C;Y2;X12;K420\nC;Y2;X13;K0\nC;Y2;X14;K0\nE\n";

typedef struct { slkTestData_t *rows, *old; edict_t *caster; } locustFix_t;

static locustFix_t locust_setup(void) {
    locustFix_t fix;
    reset_entities(); setup_test_world(); level.time = 1000;
    ((mapInfo_t *)level.mapinfo)->players[0].playerType = kPlayerTypeHuman;
    fix.rows = parse_slk_string(locust_test_slk);
    fix.old = G_SetSLKRows("AbilityData", fix.rows);
    fix.caster = alloc_test_unit(MAKEFOURCC('U','c','r','l'), 256, 256);
    fix.caster->s.player = 0;
    fix.caster->svflags |= SVF_MONSTER;
    fix.caster->targtype = TARG_GROUND;
    fix.caster->mana.value = fix.caster->mana.max_value = 300;
    fix.caster->health.value = fix.caster->health.max_value = 500;
    fix.caster->unit_state->ranks[0] = MAKE(heroability_t, .code = LS_ABILITY, .level = 1);
    return fix;
}
static void locust_done(locustFix_t fix) {
    G_SetSLKRows("AbilityData", fix.old);
    free_slk_rows(fix.rows);
}
static edict_t *locust_controller(edict_t const *caster) {
    FILTER_EDICTS(ent, ent->inuse && ent->think == locust_swarm_think && ent->owner == caster)
        return ent;
    return NULL;
}
static uint32_t locust_member_count(edict_t const *controller) {
    uint32_t count = 0;
    FILTER_EDICTS(ent, ent->inuse && G_GetLocustMember(ent)) {
        locustMember_t const *member = G_GetLocustMember(ent);
        if (member->controller == controller &&
            member->controller_spawn_time == controller->spawn_time) count++;
    }
    return count;
}

static uint32_t locust_all_members(void) {
    uint32_t count = 0;
    FILTER_EDICTS(ent, ent->inuse && G_GetLocustMember(ent)) count++;
    return count;
}

static uint32_t locust_dead_members(void) {
    uint32_t count = 0;
    FILTER_EDICTS(ent, ent->inuse && G_GetLocustMember(ent) && M_IsDead(ent)) count++;
    return count;
}

TEST(wc3_spell, locust_swarm_release_uses_authored_schedule_and_current_caster_position) {
    locustFix_t fix = locust_setup();
    abilityitem_t item = S_AbilityItem(LS_ABILITY);
    abilityCall_t call = MAKE(abilityCall_t, .item = &item);
    edict_t *controller, *first = NULL, *second = NULL;
    locustSwarm_t *state;
    T_NOT_NULL(item.ability);
    T_ASSERT(!(item.ability->flags & AB_CHANNEL));
    T_ASSERT(S_AbilityMessage(fix.caster, A_VALIDATE, &call));
    T_ASSERT(S_AbilityMessage(fix.caster, A_EXECUTE, &call));
    controller = locust_controller(fix.caster);
    T_NOT_NULL(controller);
    if (!controller) goto cleanup;
    state = G_GetLocustSwarm(controller);
    T_NOT_NULL(state);
    if (!state) goto cleanup;
    T_EQ(state->total, 3u);
    T_EQ(state->release_interval_ms, 250u);
    T_EQ(state->end_ms, 6000u);
    T_EQ(state->unit_id, LS_UNIT);
    T_FEQ(state->area, 420.0f, 0.001f);
    T_FEQ(state->target_cap, 2.0f, 0.001f);
    T_FEQ(state->heal_factor, 0.5f, 0.001f);
    T_FEQ(state->return_threshold, 13.0f, 0.001f);
    T_EQ(locust_member_count(controller), 0u);
    level.time = 1000; G_RunEntities();
    T_EQ(locust_member_count(controller), 1u);
    FILTER_EDICTS(ent, G_GetLocustMember(ent) && G_GetLocustMember(ent)->controller == controller) {
        first = ent; break;
    }
    T_NOT_NULL(first);
    if (!first) goto cleanup;
    T_EQ(first->summon_ability, LS_ABILITY);
    T_EQ(first->class_id, LS_UNIT);
    T_EQ(first->owner, fix.caster);
    T_NOT_NULL(unit_findstatus(first, MAKEFOURCC('B','T','L','F')));
    /* Moving the caster must not cancel the persistent controller. */
    fix.caster->s.origin2 = (vec2_t){ 720, 720 };
    level.time = 1249; G_RunEntities();
    T_EQ(locust_member_count(controller), 1u);
    level.time = 1250; G_RunEntities();
    T_EQ(locust_member_count(controller), 2u);
    FILTER_EDICTS(ent, G_GetLocustMember(ent) &&
                  G_GetLocustMember(ent)->controller == controller &&
                  G_GetLocustMember(ent)->state == 1u) { second = ent; break; }
    T_NOT_NULL(second);
    if (second) T_ASSERT(Vector2_distance(&second->s.origin2, &fix.caster->s.origin2) >= 0.0f);
    T_ASSERT(controller->inuse);
    /* A scheduler delay catches up, without ever duplicating release slots. */
    level.time = 1500; G_RunEntities();
    T_EQ(locust_member_count(controller), 3u);
    T_EQ(state->released, 3u);
    level.time = 1800; G_RunEntities();
    T_EQ(locust_member_count(controller), 3u);
cleanup:
    locust_done(fix);
}

TEST(wc3_spell, locust_swarm_expiry_and_owner_recycling_remove_only_owned_members) {
    locustFix_t fix = locust_setup();
    abilityitem_t item = S_AbilityItem(LS_ABILITY);
    abilityCall_t call = MAKE(abilityCall_t, .item = &item);
    edict_t *controller;
    T_ASSERT(S_AbilityMessage(fix.caster, A_EXECUTE, &call));
    controller = locust_controller(fix.caster);
    T_NOT_NULL(controller);
    if (!controller) goto cleanup;
    level.time = 1500; G_RunEntities();
    T_EQ(locust_member_count(controller), 3u);
    level.time = 6000; G_RunEntities();
    T_ASSERT(!controller->inuse);
    T_EQ(locust_dead_members(), 3u);
    T_EQ(locust_all_members(), 3u); /* death presentation owns edict retirement */
    level.time = 7000;
    T_ASSERT(S_AbilityMessage(fix.caster, A_EXECUTE, &call));
    controller = locust_controller(fix.caster);
    T_NOT_NULL(controller);
    if (!controller) goto cleanup;
    level.time = 7000; G_RunEntities();
    T_EQ(locust_member_count(controller), 1u);
    /* A caster pointer with the wrong generation must not own the swarm. */
    fix.caster->spawn_time++;
    level.time = 7101; G_RunEntities();
    T_ASSERT(!controller->inuse);
    T_ASSERT(locust_all_members() >= 1u); /* member cleanup follows its own think */
cleanup:
    locust_done(fix);
}

TEST(wc3_save, locust_swarm_controller_and_members_survive_mid_release_save) {
    locustFix_t fix = locust_setup();
    abilityitem_t item = S_AbilityItem(LS_ABILITY);
    abilityCall_t call = MAKE(abilityCall_t, .item = &item);
    cstring_t filename = Test_TempPath("wc3-locust-midrelease.bin");
    edict_t *controller;
    locustSwarm_t *state;
    T_ASSERT(S_AbilityMessage(fix.caster, A_EXECUTE, &call));
    controller = locust_controller(fix.caster);
    T_NOT_NULL(controller);
    if (!controller) goto cleanup;
    level.time = 1300; G_RunEntities();
    T_EQ(locust_member_count(controller), 1u);
    T_ASSERT(WriteGame(filename));
    state = G_GetLocustSwarm(controller);
    state->released = 0;
    state->next_release_ms = 0;
    T_ASSERT(ReadGame(filename));
    controller = locust_controller(fix.caster);
    T_NOT_NULL(controller);
    if (!controller) goto cleanup;
    state = G_GetLocustSwarm(controller);
    T_NOT_NULL(state);
    if (!state) goto cleanup;
    T_EQ(state->released, 1u);
    T_EQ(state->next_release_ms, 1500u);
    T_EQ(locust_member_count(controller), 1u);
    level.time = 1750; G_RunEntities();
    T_EQ(locust_member_count(controller), 3u);
    remove(filename);
cleanup:
    locust_done(fix);
}
#endif
