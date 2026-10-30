#include "s_skills.h"

/* Night Elf Warden (Maiev) hero abilities: Blink, Fan of Knives, Shadow Strike. */

#define ID_BLINK        MAKEFOURCC('A', 'E', 'b', 'l')

/* ---- Blink (AEbl): instant teleport to a target point within range -------- */

static bool blink_validate(edict_t *caster, spellTarget_t st, abilityitem_t const *spell) {
    uint32_t level = S_SpellLevel(caster, spell->code);
    float maxrange = S_SpellData(spell->code, level, 1);
    float minrange = S_SpellData(spell->code, level, 2);
    float dist = Vector2_distance(&caster->s.origin2, &st.point);

    if (maxrange > 0 && dist > maxrange) return false;
    if (minrange > 0 && dist < minrange) return false;
    return true;
}

static void blink_execute(edict_t *caster, spellTarget_t st, abilityitem_t const *spell) {
    G_SpawnAbilityEffectTarget(spell->code, WC3_EFFECT_SPECIAL, 0, caster, NULL, true);
    vec2_t dest = st.point;
    CM_ClosestPathablePointForRadiusFlags(&st.point, caster->collision, M_UnitStaticPathingFlags(caster), &dest);
    S_SpellCommitRelocation(caster, &dest);
    G_SpawnAbilityEffectTarget(spell->code, WC3_EFFECT_AREA_EFFECT, 0, caster, NULL, true);
}

/* ---- Registration -------------------------------------------------------- */

BZ_VALIDATED_SPELL_PROC(AbilityBlink, blink_validate, blink_execute)

/* ---- Fan of Knives (AEfk): capped enhanced-physical area damage ------- */

/* Fan of Knives is a magical *ability* with enhanced-physical *damage*.
 * It uses the Spells attack/defense multiplier (including Hero defense), but
 * neither numeric armor nor the magical spell-damage/Anti-Magic Shell path.
 * It cannot hit Ethereal targets and remains blocked by spell immunity. */
static bool fan_of_knives_can_damage(edict_t *target) {
    return !S_UnitSpellImmune(target) &&
           !unit_hasstatusstate(target, WC3_STATUS_STATE_ETHEREAL) &&
           !unit_hasstatusstate(target, WC3_STATUS_STATE_INVULNERABLE) &&
           !G_UnitHasFlag(target, UNIT_FLAG_INVULNERABLE);
}

static void fan_of_knives_damage(edict_t *target, edict_t *caster, int damage) {
    if (damage <= 0 || !fan_of_knives_can_damage(target)) return;
    uint32_t const defense = target->unit_state ? target->unit_state->defense_type : 0;
    float const multiplier = G_AttackTypeDamageMultiplier(ATK_SPELLS, defense);
    int const dealt = (int)((float)damage * multiplier);
    if (dealt > 0) T_Damage(target, caster, dealt);
}

/* The original models both carry Birth - 1/2/3 and Death. The numbered
 * Birth variants are selected by learned rank here (clamped to the three
 * shipped variants), pending a retail selection trace. No gameplay timing is
 * derived from their 1600 model-time-unit sequences. A custom model with
 * only a plain Birth clip continues to work through the generic effect path. */
static void fan_of_knives_set_visual_rank(edict_t *effect, uint32_t rank) {
    char clip[24];
    animation_t const *anim;
    if (!effect || !effect->inuse || !effect->s.model) return;
    snprintf(clip, sizeof(clip), "Birth - %u", (unsigned)MIN(MAX(rank, 1u), 3u));
    anim = G_GetAnimation(effect->s.model, clip);
    if (anim && G_AnimationHasPrimary(anim, "birth")) {
        effect->animation = anim;
        effect->s.frame = anim->interval[0];
    }
}

/* AEfk inflicts immediate area damage. Its MissileArt is presentation only:
 * the source MDX has a self-animated burst and ribbons, not a proven impact
 * travel time. Snapshot both models at the cast point; never spawn a gameplay
 * missile or effects on each individual victim. Missing art safely does
 * nothing. Stock paths are resolved in G_AbilityEffectArt, with overrides
 * retaining precedence for custom abilities. */
static void fan_of_knives_play_visuals(edict_t *caster, uint32_t code, uint32_t rank) {
    vec2_t const origin = caster->s.origin2;
    cstring_t const caster_art = G_AbilityEffectArt(code, WC3_EFFECT_CASTER, 0);
    cstring_t const knife_art = G_AbilityEffectArt(code, WC3_EFFECT_MISSILE, 0);
    edict_t *effect;

    if (caster_art && *caster_art) {
        effect = G_SpawnModelEffect(caster_art, &origin, NULL, NULL, true);
        fan_of_knives_set_visual_rank(effect, rank);
    }
    if (knife_art && *knife_art && (!caster_art || strcasecmp(knife_art, caster_art))) {
        effect = G_SpawnModelEffect(knife_art, &origin, NULL, NULL, true);
        fan_of_knives_set_visual_rank(effect, rank);
    }
    /* Use only the authored one-shot ability sound. The three inspected hit
     * WAVs do not by themselves establish a per-target playback contract. */
    G_PlayAbilityEffectSound(code, &origin);
}

BZ_SIMPLE_SPELL_PROC(AbilityFanOfKnives) {
    if (!caster) return;
    uint32_t const level = S_SpellLevel(caster, spell->code);
    float radius = S_SpellNumber(spell->code, ABILITY_NUMBER_AREA, level);
    float const per_target = MAX(0.0f, S_SpellData(spell->code, level, 1));
    int const damage = (int)per_target;
    float const maxtotal = S_SpellData(spell->code, level, 2);
    float remaining = maxtotal;
    if (radius <= 0.0f) radius = 400.0f;
    /* An empty or zero-damage cast still has its normal spell presentation. */
    fan_of_knives_play_visuals(caster, spell->code, level);
    if (damage <= 0) return;

    /* Maximum damage is a budget for full-strength victims, NOT an amount to
     * distribute over every unit inside the area. DataB <= 0 is uncapped.
     * Traverse stable edict order for deterministic casts; exact retail victim
     * selection among >cap candidates still needs a controlled comparison. */
#define FOK_HITS(t) ((t)->inuse && (t) != caster && S_SpellIsEnemy(caster, t) && \
                     S_SpellAllowsTarget(spell->code, caster, t) &&               \
                     fan_of_knives_can_damage(t) &&                              \
                     Vector2_distance(&(t)->s.origin2, &caster->s.origin2) <= radius)

    FILTER_EDICTS(target, FOK_HITS(target)) {
        if (maxtotal > 0.0f && remaining < per_target) break;
        fan_of_knives_damage(target, caster, damage);
        if (maxtotal > 0.0f) remaining -= per_target;
    }
#undef FOK_HITS
}

/* ---- Shadow Strike (AEsh): homing missile and initial damage -------------- */

static void shadow_strike_projectile_hit(edict_t *missile) {
    edict_t *target = S_SpellProjectileTarget(missile);
    edict_t *caster = S_SpellProjectileOwner(missile);

    if (caster && S_SpellIsAliveTarget(target) &&
        S_SpellAllowsTarget(missile->class_id, caster, target) &&
        !S_TryBlockSpellShield(caster, missile->class_id, target)) {
        S_SpellDamage(target, caster, missile->damage);
        /* TODO(1:1): Shadow Strike also applies a movement slow and a decaying
         * poison DoT via the BEsh buff. The status system needs periodic damage
         * and movement-speed modifiers first. */
    }
    G_FreeEdict(missile);
}

static umove_t shadow_strike_projectile_move = {
    "stand", NULL, shadow_strike_projectile_hit, CAbilityShadowStrike
};

BZ_ABILITY_PROC(CAbilityShadowStrike) {
    if (msg == A_EXECUTE && call && call->item && call->target && call->target->entity) {
        cstring_t speed_text = S_SpellString(call->item->code, "Missilespeed", 0);
        float speed = speed_text ? (float)atof(speed_text) : 1200.0f;
        uint32_t level = S_SpellLevel(ent, call->item->code);
        edict_t *missile = S_SpawnUnitTargetSpellMissile(ent, call->item->code,
            call->target->entity, speed, &shadow_strike_projectile_move);

        if (missile)
            missile->damage = (uint32_t)MAX(1.0f, S_SpellData(call->item->code, level, 5)); /* DataE */
        else
            S_SpellDamage(call->target->entity, ent,
                (int)MAX(1.0f, S_SpellData(call->item->code, level, 5)));
        return true;
    }
    return CAbilitySimpleSpell(ent, msg, call);
}
