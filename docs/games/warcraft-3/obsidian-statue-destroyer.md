# Obsidian Statue and Destroyer

Source baseline: `open-realm-main-2026-10-29-23-15.zip`. Reference:
[Blizzard's Obsidian Statue](https://classic.battle.net/war3/undead/units/obsidianstatue.shtml)
and [Destroyer](https://classic.battle.net/war3/undead/units/destroyer.shtml).
Visual evidence comes from the original MPQ/unit/ability table inspection supplied
by the project maintainer on 31 October 2026, not from guesses based on filenames.

## Owned game-side paths

- `skills/s_undead_abilities.c`: `Arpl` (Essence of Blight) and `Arpm` (Spirit Touch).
- `skills/s_requested_abilities.c`: permanent `Aave` Destroyer conversion and Morph presentation.
- `skills/s_hero_passives.c`, `skills/s_attack.c`: mana-paid `Afak` attack modifier.
- `skills/s_human_abilities.c`: area dispel / `Advm` target refund.
- `skills/s_creep_abilities.c`: `Aabs` friendly unit-target homing mana transfer.
- `skills/s_spell.c`: generic spell admission, mana commit, cooldown and attack-modifier manual order.

## Statue restoration

`Arpl` uses `DataA` HP; `Arpm` uses `DataB` mana. Both scan the
ability's authored area and target-mask using `S_SpellAllowsAreaTarget()`. Only
wounded/mana-depleted recipients qualify, up to six per casting in stable entity
order; the mask excludes mechanical recipients when `organic` is set.

The normal spell commit charges the first `Cost`; each additional recipient
through the fifth pays another `Cost`; a sixth receives restoration at no
additional cost. Existing caster mana constrains how many can be restored. The
authored `Brpl`/`Brpm` timed buff inhibits simultaneous restoration of the same
type on the same recipient. Unlike an ad-hoc global timestamp, this uses normal
status expiration and persistence. Maps omitting the buff do not receive that
suppression. If the status array is full, the candidate is skipped.

Each cast queues `CasterArt` at `origin`, `SpecialArt` at `overhead`, plus one
`TargetArt` for every recipient actually restored, and resolves the ability
sound alias through the shared sound layer.

The confirmed stock assignments are:

| Ability | Caster | Special | Target |
|---|---|---|---|
| `Arpl` | `ReplenishHealthCaster.mdx` | `ReplenishHealthCasterOverhead.mdx` | Human `HealTarget.mdx` |
| `Arpm` | `ReplenishManaCaster.mdx` | `ReplenishManaCasterOverhead.mdx` | `SpiritTouchTarget.mdx` |

The exact retail order of six recipients, target-art timing and overlap window
remain observational gaps. The current entity-order selection is deterministic,
not a claim that retail chooses the same recipients.

## Permanent Destroyer Form

`Aave` takes its source ID from `AbilityData.DataA` and destination from
`UnitID`. The conversion checks the authored research availability and the
**positive cost difference** between destination/source `UnitBalance`
(gold, lumber, extra food) before rebinding the same edict with
`G_TransformUnitType()`. Resources are charged only after successful rebind.
The destination begins with zero mana, keeps its JASS identity, is assigned its
own stats/attack/flight profile, and has no reversion thinker.

Both `uobs` and `ubsp` use
`Units\\Undead\\ObsidianStatue\\ObsidianStatue.mdx`. The destination has the
`alternate` unit animation property. The game starts an untagged `Morph`
animation and restores the destination's alternate Stand/Walk/Attack set after
the transition. The model also contains `Morph Alternate`, but detailed
visibility/event tracks have **not** been validated; the exact transition frame
and duration remain to be proven. Do not infer debris from the presence of
`rocks1.MDX` or `ObsidianFeather.MDX` in the archive.

## Destroyer abilities

- **Normal weapon**: `AvengerMissile.mdx`, homing, authored weapon speed 900.
- **`Afak` Orb of Annihilation**: manual one-shot and autocast use the same
  attack-modifier order, spend authored mana and add `DataA` damage on a
  successful shot; the missile uses the ability's authored `MissileArt`
  (stock: `AnnihilationMissile.mdx`). **Area-splash rings are still missing**;
  do not declare full Orb parity based only on projectile replacement.
- **`Advm` Devour Magic**: reuses the shared area-dispel inverse lifecycle. It
  now refunds `DataA` HP/`DataB` mana once per hostile buffed unit, rather than
  once per removed status; friendly buffs and Sentinel wards produce no refund.
  `DataE` damages hostile summons. It spawns authored special art and sound at
  the impact point. **Travel of the authored `DevourMagicBirthMissile.mdx` is
  still missing**.
- **`Aabs` Absorb Mana**: a unit-target spell with a homing projectile
  (`AbsorbManaBirthMissile.mdx` via authored MissileArt); on valid impact,
  transfers up to `DataB`, capped by source mana and the Destroyer's empty
  capacity, without creating mana. Cancellation, projectile save/load and
  mid-flight target disappearance need focused testing.

## Regression and verification

`game/tests/t_spell.c` covers the restoration recipient limit and masks, plus
the active Absorb Mana command's target admission. Remaining recommended
integration fixtures: full cast-pipeline mana accounting, overlapping-Statue
suppression, `Rusp`/resource/food rejections and permanent transformation,
projectile impact after target death or save/load, Orb mana/splash and Devour
Magic per-hostile-target refund. Custom values should be used in addition to
stock-shaped tests. The engine is validated separately by the project test
suite; this document records current implementation gaps rather than claiming
complete retail parity.
