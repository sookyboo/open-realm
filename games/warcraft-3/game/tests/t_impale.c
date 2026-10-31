#ifdef BZ_TESTS
#include "test.h"
#include "../g_local.h"
#include "../skills/s_skills.h"

static cstring_t const impale_slk =
    "ID;PWXL;N;EBB;Y3;X12\n"
    "C;Y1;X1;K\"alias\"\nC;Y1;X2;K\"code\"\nC;Y1;X3;K\"targs\"\n"
    "C;Y1;X4;K\"DataA1\"\nC;Y1;X5;K\"DataB1\"\nC;Y1;X6;K\"DataC1\"\n"
    "C;Y1;X7;K\"Area1\"\nC;Y1;X8;K\"BuffID1\"\nC;Y1;X9;K\"Dur1\"\n"
    "C;Y1;X10;K\"HeroDur1\"\nC;Y1;X11;K\"levels\"\nC;Y1;X12;K\"Rng1\"\n"
    "C;Y2;X1;K\"AUim\"\nC;Y2;X2;K\"AUim\"\nC;Y2;X3;K\"ground,enemy,organic\"\n"
    "C;Y2;X4;K600\nC;Y2;X5;K0.6\nC;Y2;X6;K73\nC;Y2;X7;K80\n"
    "C;Y2;X8;K\"BUim\"\nC;Y2;X9;K2\nC;Y2;X10;K1\nC;Y2;X11;K1\nC;Y2;X12;K700\n"
    "C;Y3;X1;K\"ACmp\"\nC;Y3;X2;K\"ACmp\"\nC;Y3;X3;K\"ground,enemy,organic\"\n"
    "C;Y3;X4;K400\nC;Y3;X5;K0.4\nC;Y3;X6;K37\nC;Y3;X7;K100\n"
    "C;Y3;X8;K\"BUim\"\nC;Y3;X9;K1\nC;Y3;X10;K1\nC;Y3;X11;K1\nC;Y3;X12;K700\nE\n";

static UnitBalance_t const impale_no_regen = { .healthRegenType = "none" };

static edict_t *impale_unit(float x, float y, uint32_t player, TARGTYPE type) {
    edict_t *unit = alloc_test_unit(MAKEFOURCC('h','f','o','o'), x, y);
    unit->s.player = player;
    unit->targtype = type;
    unit->svflags |= SVF_MONSTER;
    unit->data.UnitBalance = (UnitBalance_t *)&impale_no_regen;
    unit->health.value = unit->health.max_value = 500;
    return unit;
}

static bool impale_cast(edict_t *caster, cstring_t code, vec2_t point) {
    abilityitem_t item = S_AbilityItem(FS_SLKKey(code));
    spellTarget_t target = MAKE(spellTarget_t, .type = SPELL_TARGET_POINT, .point = point);
    abilityCall_t call = MAKE(abilityCall_t, .item = &item, .target = &target);
    return S_AbilityMessage(caster, A_EXECUTE, &call) != 0;
}

TEST(wc3_spell, impale_wave_hits_in_authored_travel_order_once_per_cast) {
    slkTestData_t *rows = parse_slk_string(impale_slk), *old;
    edict_t *caster, *near, *middle, *far, *behind, *beyond, *side;
    edict_t *ally, *flying, *mechanical, *wave = NULL;

    reset_entities(); setup_test_world();
    old = G_SetSLKRows("AbilityData", rows);
    ((mapInfo_t *)level.mapinfo)->players[0].playerType = kPlayerTypeHuman;
    ((mapInfo_t *)level.mapinfo)->players[1].playerType = kPlayerTypeHuman;
    caster = impale_unit(0, 0, 0, TARG_GROUND);
    near = impale_unit(80, 0, 1, TARG_GROUND);
    middle = impale_unit(260, 0, 1, TARG_GROUND);
    far = impale_unit(490, 0, 1, TARG_GROUND);
    behind = impale_unit(-80, 0, 1, TARG_GROUND);
    beyond = impale_unit(680, 0, 1, TARG_GROUND);
    side = impale_unit(260, 140, 1, TARG_GROUND);
    ally = impale_unit(150, 0, 0, TARG_GROUND);
    flying = impale_unit(210, 0, 1, TARG_AIR);
    mechanical = impale_unit(320, 0, 1, TARG_MECHANICAL);
    level.time = 1000;
    T_ASSERT(impale_cast(caster, "AUim", (vec2_t){ 700, 0 }));
    FILTER_EDICTS(ent, ent->think == impale_wave_think) { wave = ent; break; }
    T_NOT_NULL(wave);
    if (!wave) goto cleanup;
    T_NOT_NULL(G_GetImpaleWave(wave));
    T_FEQ(near->health.value, 500, 0.001f);
    level.time = 1100; G_RunEntities();
    T_FEQ(near->health.value, 427, 0.001f);
    T_FEQ(middle->health.value, 500, 0.001f);
    T_FEQ(far->health.value, 500, 0.001f);
    level.time = 1200; G_RunEntities();
    T_FEQ(near->health.value, 427, 0.001f);
    T_FEQ(middle->health.value, 500, 0.001f);
    level.time = 1300; G_RunEntities();
    T_FEQ(middle->health.value, 427, 0.001f);
    T_FEQ(far->health.value, 500, 0.001f);
    level.time = 1600; G_RunEntities();
    T_FEQ(far->health.value, 427, 0.001f);
    T_FEQ(near->health.value, 427, 0.001f);
    T_FEQ(middle->health.value, 427, 0.001f);
    T_FEQ(behind->health.value, 500, 0.001f);
    T_FEQ(beyond->health.value, 500, 0.001f);
    T_FEQ(side->health.value, 500, 0.001f);
    T_FEQ(ally->health.value, 500, 0.001f);
    T_FEQ(flying->health.value, 500, 0.001f);
    T_FEQ(mechanical->health.value, 500, 0.001f);
    T_ASSERT(!wave->inuse);
cleanup:
    G_SetSLKRows("AbilityData", old); free_slk_rows(rows);
}

TEST(wc3_spell, impale_creep_alias_uses_its_own_wave_data_and_owner_identity) {
    slkTestData_t *rows = parse_slk_string(impale_slk), *old;
    edict_t *caster, *hit, *out_of_range, *wave = NULL;
    reset_entities(); setup_test_world();
    old = G_SetSLKRows("AbilityData", rows);
    ((mapInfo_t *)level.mapinfo)->players[0].playerType = kPlayerTypeHuman;
    ((mapInfo_t *)level.mapinfo)->players[1].playerType = kPlayerTypeHuman;
    caster = impale_unit(0, 0, 0, TARG_GROUND);
    hit = impale_unit(150, 0, 1, TARG_GROUND);
    out_of_range = impale_unit(450, 0, 1, TARG_GROUND);
    level.time = 1000;
    T_ASSERT(impale_cast(caster, "ACmp", (vec2_t){ 700, 0 }));
    FILTER_EDICTS(ent, ent->think == impale_wave_think) { wave = ent; break; }
    T_NOT_NULL(wave);
    if (!wave) goto cleanup;
    T_EQ(G_GetImpaleWave(wave)->ability, MAKEFOURCC('A','C','m','p'));
    T_FEQ(G_GetImpaleWave(wave)->distance, 400, 0.001f);
    level.time = 1200; G_RunEntities();
    T_FEQ(hit->health.value, 463, 0.001f);
    T_FEQ(out_of_range->health.value, 500, 0.001f);
    /* Reusing the caster's entity identity must cancel the pending wave. */
    caster->spawn_time++;
    level.time = 1300; G_RunEntities();
    T_ASSERT(!wave->inuse);
    T_FEQ(out_of_range->health.value, 500, 0.001f);
cleanup:
    G_SetSLKRows("AbilityData", old); free_slk_rows(rows);
}

TEST(wc3_spell, impale_rejects_zero_direction_or_nonpositive_travel_data) {
    slkTestData_t *rows = parse_slk_string(impale_slk), *old;
    edict_t *caster;
    abilityitem_t item;
    spellTarget_t target;
    abilityCall_t call;
    reset_entities(); setup_test_world();
    old = G_SetSLKRows("AbilityData", rows);
    caster = impale_unit(0, 0, 0, TARG_GROUND);
    item = S_AbilityItem(MAKEFOURCC('A','U','i','m'));
    target = MAKE(spellTarget_t, .type = SPELL_TARGET_POINT, .point = caster->s.origin2);
    call = MAKE(abilityCall_t, .item = &item, .target = &target);
    T_ASSERT(!S_AbilityMessage(caster, A_VALIDATE, &call));
    T_ASSERT(!S_AbilityMessage(caster, A_EXECUTE, &call));
    FILTER_EDICTS(ent, ent->think == impale_wave_think)
        T_ASSERT(false);
    G_SetSLKRows("AbilityData", old); free_slk_rows(rows);
}
#endif
