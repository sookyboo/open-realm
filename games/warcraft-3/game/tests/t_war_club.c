/* Mountain Giant War Club: entity-targeted tree consumption, reversible
 * alternate weapon and committed-swing limits. */
#ifdef BZ_TESTS
#include "test.h"
#include "../g_local.h"
#include "../skills/s_skills.h"

void reset_entities(void);
void setup_test_world(void);
edict_t *alloc_test_unit(uint32_t class_id, float x, float y);

#define TEST_GRAB_TREE MAKEFOURCC('A','g','r','a')

static UnitAbilities_t war_club_abilities = { .abilList = "Agra" };
static UnitWeapons_t war_club_weapons = { .attacksEnabled = 1 };

static edict_t *make_war_club_giant(void) {
    edict_t *giant = alloc_test_unit(MAKEFOURCC('h','f','o','o'), 0, 0);
    giant->data.UnitAbilities = &war_club_abilities;
    giant->data.UnitWeapons = &war_club_weapons;
    giant->svflags |= SVF_MONSTER;
    giant->collision = 48.0f;
    giant->unit_state->attack1.type = ATK_NORMAL;
    giant->unit_state->attack1.range = 128.0f;
    giant->unit_state->attack2.type = ATK_SIEGE;
    giant->unit_state->attack2.range = 250.0f;
    giant->unit_state->attack1.targetsAllowed = 0xffffffffu;
    giant->unit_state->attack2.targetsAllowed = 0xffffffffu;
    return giant;
}

static edict_t *make_war_club_tree(void) {
    edict_t *tree = G_Spawn();
    tree->class_id = MAKEFOURCC('B','0','0','X');
    tree->s.class_id = tree->class_id;
    G_BindEntityData(tree);
    tree->targtype = TARG_TREE;
    tree->health.max_value = tree->health.value = 100.0f;
    tree->s.model = 1;
    tree->s.scale = 1.0f;
    tree->s.origin2 = (vec2_t){64, 0};
    tree->s.origin = (vec3_t){64, 0, 0};
    tree->collision = 16;
    G_AddDestructable(tree);
    return tree;
}

static bool grab_tree_message(edict_t *giant, edict_t *tree, abilityMsg_t msg) {
    abilityitem_t item = S_AbilityItem(TEST_GRAB_TREE);
    spellTarget_t target = MAKE(spellTarget_t, .type = SPELL_TARGET_UNIT, .entity = tree);
    abilityCall_t call = MAKE(abilityCall_t, .item = &item, .target = &target);
    return S_AbilityMessage(giant, msg, &call) != 0;
}

TEST(wc3_war_club, grab_consumes_only_a_living_tree_and_switches_attack_mask) {
    edict_t *giant, *tree;
    reset_entities(); setup_test_world();
    giant = make_war_club_giant();
    tree = make_war_club_tree();

    T_ASSERT(S_UnitAttackSlotEnabled(giant, 0));
    T_ASSERT(!S_UnitAttackSlotEnabled(giant, 1));
    T_ASSERT(grab_tree_message(giant, tree, A_VALIDATE));
    T_ASSERT(grab_tree_message(giant, tree, A_EXECUTE));
    T_ASSERT(G_GetDestructable(tree)->dead);
    T_FEQ(tree->health.value, 0.0f, 0.001f);
    T_ASSERT(S_WarClubActive(giant));
    T_EQ(giant->unit_state->war_club_ability, TEST_GRAB_TREE);
    T_EQ(giant->unit_state->war_club_attacks_remaining, 15u);
    T_ASSERT(!S_UnitAttackSlotEnabled(giant, 0));
    T_ASSERT(S_UnitAttackSlotEnabled(giant, 1));
    T_ASSERT(!grab_tree_message(giant, tree, A_VALIDATE));
    T_ASSERT(!grab_tree_message(giant, tree, A_EXECUTE));
}

TEST(wc3_war_club, committed_attacks_exhaust_club_then_restore_attack_one) {
    edict_t *giant;
    reset_entities(); setup_test_world();
    giant = make_war_club_giant();
    S_WarClubEquip(giant, TEST_GRAB_TREE);
    T_ASSERT(S_WarClubActive(giant));
    FOR_LOOP(i, 14) S_WarClubConsumeAttack(giant);
    T_EQ(giant->unit_state->war_club_attacks_remaining, 1u);
    T_ASSERT(S_UnitAttackSlotEnabled(giant, 1));
    S_WarClubConsumeAttack(giant);
    T_ASSERT(!S_WarClubActive(giant));
    T_EQ(giant->unit_state->war_club_ability, 0u);
    T_ASSERT(S_UnitAttackSlotEnabled(giant, 0));
    T_ASSERT(!S_UnitAttackSlotEnabled(giant, 1));
    S_WarClubConsumeAttack(giant);
    T_EQ(giant->unit_state->war_club_attacks_remaining, 0u);
}

TEST(wc3_war_club, invalid_targets_are_not_consumed) {
    edict_t *giant, *tree;
    reset_entities(); setup_test_world();
    giant = make_war_club_giant();
    tree = make_war_club_tree();
    tree->targtype = TARG_DEBRIS;
    T_ASSERT(!grab_tree_message(giant, tree, A_VALIDATE));
    T_ASSERT(!grab_tree_message(giant, tree, A_EXECUTE));
    T_ASSERT(!G_GetDestructable(tree)->dead);
    tree->targtype = TARG_TREE;
    G_SetUnitFlag(tree, UNIT_FLAG_INVULNERABLE, true);
    T_ASSERT(!grab_tree_message(giant, tree, A_VALIDATE));
    G_SetUnitFlag(tree, UNIT_FLAG_INVULNERABLE, false);
    T_ASSERT(grab_tree_message(giant, tree, A_VALIDATE));
}

TEST(wc3_war_club, another_giant_cannot_grab_a_consumed_tree) {
    edict_t *first, *second, *tree;
    reset_entities(); setup_test_world();
    first = make_war_club_giant();
    second = make_war_club_giant();
    tree = make_war_club_tree();
    T_ASSERT(grab_tree_message(first, tree, A_EXECUTE));
    T_ASSERT(!grab_tree_message(second, tree, A_EXECUTE));
    T_ASSERT(!S_WarClubActive(second));
}

TEST(wc3_war_club, death_clears_the_alternate_weapon) {
    edict_t *giant;
    abilityitem_t item = S_AbilityItem(TEST_GRAB_TREE);
    abilityCall_t call = MAKE(abilityCall_t, .item = &item);
    reset_entities(); setup_test_world();
    giant = make_war_club_giant();
    S_WarClubEquip(giant, TEST_GRAB_TREE);
    S_AbilityMessage(giant, A_DEATH, &call);
    T_ASSERT(!S_WarClubActive(giant));
    T_ASSERT(S_UnitAttackSlotEnabled(giant, 0));
}
#endif
