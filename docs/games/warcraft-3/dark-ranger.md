# Dark Ranger — Silence (`ANsi`, `ACsi`)

## Scope and authoritative data

Silence is the first Dark Ranger parity patch. `CAbilitySilence` lives in
`games/warcraft-3/game/skills/s_requested_abilities.c`; both `ANsi` and the
creep `ACsi` alias are registered in `s_skills.c`. The executed ability alias
selects the current AbilityData fields and presentation data. The MPQ asset
audit supplied for this work confirms the stock Dark Ranger `ANsi` uses:

| Field | Stock TFT values (levels 1/2/3) |
|---|---|
| `Area` | 200 / 275 / 350 |
| `Dur` | 16 / 20 / 24 seconds |
| `HeroDur` | 8 / 10 / 12 seconds |
| Mana / cooldown / cast range | 75 mana / 15 seconds / 900 |
| Ability `EffectArt` | `SilenceAreaBirth.mdl`, ground burst |
| Buff `BNsi.TargetArt` | `SilenceTarget.mdl`, `overhead` attachment |

The audit observed non-looping `Birth` (0–567 ms) and `Death` (1700–1900 ms)
for the area effect. The target model has non-looping `Birth` (333–667 ms),
looping `Stand` (1000–1333 ms), and non-looping `Death` (1667–2000 ms).
These sequence times describe authored model data, not hardcoded lifetimes in
OpenRealm. `Silence1.wav` is present in MPQ but its ability/sound alias binding
was not established; this patch does not invent a sound mapping.

## Runtime lifecycle

A successful point cast emits `WC3_EFFECT_EFFECT` at its selected point
*once*, independent of how many targets pass filtering. Generic effect
animation handles the point burst; no Silence-specific think callback or save
field is required.

Eligible units must be alive enemy targets inside the authored radius and pass
`S_SpellAllowsAreaTarget()`. This shared predicate handles authored air/ground,
organic/mechanical, spell immunity, and resistant/hero mask restrictions, and
must not apply the unit-target visibility check: an area spell can affect units
in fog. The selected rank's first `BuffID` supplies the timed status (stock
`BNsi`). Normal/Hero timing uses `S_SpellHeroDuration()`; classifying
level-6 creeps as Heroes for duration is **not** part of this patch.

`S_SpellApplyTimedStatusFromAbility()` retains the actual source ability and
rank for custom aliases. Successful applications are classified as negative
magical buffs and call `unit_status_enabletargetart(..., "overhead")`. The
resulting target art belongs to the status rawcode, not the caster or the
ability's one-shot burst. `G_SpawnStatusEffectTarget()` ensures only one live
model is tagged for an active buff and target incarnation. Refresh and
reapplication therefore do not pile up overhead models. Dispel, expiry, and
replacement route through `unit_removestatus()` and
`G_DestroyStatusEffectTarget()`, clearing the model's live status tag and
playing the authored Death animation where available.

The runtime does not synthesize an area effect when a custom map omits
`EffectArt`, or a target model when its buff omits art.

## Verification

`games/warcraft-3/game/tests/t_dark_ranger_silence.c` exercises the production
`S_CastPointTargetSpell()` entry point with non-stock Area=183, Dur=13,
HeroDur=4. It verifies target ownership, range, immunity, organic filtering,
source-ability identity, buff classification, exactly one ground effect,
exactly one overhead model per affected unit, refresh without duplicates,
dispel removal, and timed expiry. The source-controlled
`tests/resources-src/Units/NeutralAbilityFunc.txt` supplies test art paths.

To run after building with the regular test targets:

```sh
make test
```

Neither compilation nor tests were run by the patch author. Validate
appearance with actual retail MPQs in both TFT and RoC as needed; the fixture
models verify effect selection and ownership, not pixel-level MDX rendering.

## Remaining Dark Ranger work

Charm target restrictions and short visual, Black Arrow per-attack resource
and summon lifecycle, and Life Drain attached visuals/lightning/looping audio
are separate planned changes. See
[ability coverage](architecture/ability-coverage.md) and
[spell presentation](ability-and-item-effects.md).
