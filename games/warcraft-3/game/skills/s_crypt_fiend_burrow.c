#include "s_skills.h"

cstring_t const crypt_fiend_burrow_orders[] = { "burrow", "unburrow", NULL };

#define FIEND_NORMAL MAKEFOURCC('u','c','r','y')
#define FIEND_BURROWED MAKEFOURCC('u','c','r','m')
#define FIEND_BURROW_ABILITY MAKEFOURCC('A','b','u','r')

static bool crypt_fiend_burrow_can_cast(edict_t const *unit) {
    return unit && (unit->class_id == FIEND_NORMAL || unit->class_id == FIEND_BURROWED) &&
           G_UnitAbilityResearchAvailable(unit, FIEND_BURROW_ABILITY);
}

BZ_ABILITY_PROC(CAbilityCryptFiendBurrow) {
    switch (msg) {
    case A_COMMAND: {
        gameClient_t *client;
        uint32_t subgroup;
        bool executed = false;
        if (!ent || !call || !call->entity || !(client = call->entity->client)) return false;
        subgroup = ent->class_id;
        FOR_CONTROLLABLE_SELECTED_UNITS(client, unit) {
            if (unit->class_id != subgroup || !crypt_fiend_burrow_can_cast(unit)) continue;
            if (S_CastNoTargetSpell(unit, FIEND_BURROW_ABILITY)) executed = true;
        }
        if (executed) Get_Commands_f(call->entity);
        return executed;
    }
    case A_ORDER:
        if (!call || !call->order || !crypt_fiend_burrow_can_cast(ent)) return false;
        if (!strcmp(call->order, "burrow") && ent->class_id != FIEND_NORMAL) return false;
        if (!strcmp(call->order, "unburrow") && ent->class_id != FIEND_BURROWED) return false;
        if (strcmp(call->order, "burrow") && strcmp(call->order, "unburrow")) return false;
        return S_CastNoTargetSpell(ent, FIEND_BURROW_ABILITY);
    case A_TOGGLE_ON:
        return ent && ent->class_id == FIEND_BURROWED;
    case A_VALIDATE:
        return crypt_fiend_burrow_can_cast(ent);
    case A_EXECUTE: {
        uint32_t target;
        if (!crypt_fiend_burrow_can_cast(ent)) return false;
        target = ent->class_id == FIEND_NORMAL ? FIEND_BURROWED : FIEND_NORMAL;
        if (!G_TransformUnitType(ent, target)) return false;
        ent->goalentity = NULL;
        if (ent->orders) ent->orders->resource_goal = NULL;
        move_reset_progress(ent);
        unit_stand(ent);
        return true;
    }
    default:
        return CAbilitySimpleSpell(ent, msg, call);
    }
}
