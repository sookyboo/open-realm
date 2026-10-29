# Phoenix, Phoenix Fire, and Egg Rebirth

## Scope and external evidence

Stock Warcraft III Phoenix: <https://classic.battle.net/war3/human/units/phoenix.shtml>.
The Blood Mage's Phoenix spell is `AHpx`; stock Phoenix and Egg unit rawcodes
are `hphx` and `hpxe`. A Phoenix loses 25 HP/sec, can be healed, and is **not**
classified as a summoned unit. On death it produces a 200-HP, zero-armour egg.
The egg hatches in ten seconds if alive; if killed, rebirth stops. The normal
Phoenix/Egg stats, armour type, flight, passive skill lists, and spell immunity
come from the map's unit tables and the shared simulation.

Phoenix Fire `Apxf` automatically sends a projectile to a hostile unit in its
Area. Default reference behaviour: one target every 0.5 seconds, 20 initial
damage, then 2 damage per second, for 10 seconds or 7 seconds against Heroes.
See <https://warcraft.wiki.gg/wiki/Phoenix_(Warcraft_III)> and
<https://liquipedia.net/warcraft/Phoenix>. The ability data's `Area`, `Cool`,
`DataA`, `DataB`, `Dur`, `HeroDur`, `BuffID`, `targs`, and `MissileArt` remain
authoritative for altered maps; no retail damage numbers are in C.

## Current ownership

- `skills/s_requested_abilities.c`: `AHpx` routes to `S_SummonPhoenix`.
- `skills/s_phoenix.c`: uses the spell's authored `UnitID`, spawns an ordinary
  player-owned unit with no `summon_ability`/timed life/BTLF, and destroys the
  existing player's stock Phoenix or incubating Egg when recast. It does not
  give summoned-creature dispel/damage semantics to the Phoenix.
- `g_phys.c`: negative `healthRegen` drains even a fully healthy unit and
  dispatches its death callback when the drain is lethal. This is a general
  correction for other negative-regeneration unit data, not a Phoenix tick.
- `m_unit.c` + `skills/s_phoenix.c`: the real death event is published before
  rebirth, a separate egg is spawned, and the old corpse is retired. Eggs use
  a game-time ten-second deadline; `G_TransformUnitType` turns a surviving egg
  back into a full-health Phoenix (same egg entity/handle).
- `g_monster.c`: 1.29 `UnitUI.slk` assigns `Phoenix.mdx` to both `hphx` and
  `hpxe`, despite the separate `PhoenixEgg.mdx` asset. Unit spawn corrects this
  path only for stock `hpxe` rows; map/custom Egg model overrides are retained.
- `skills/s_phoenix.c`: `Apxf` uses the common homing spell missile, owns its
  cooldown per Phoenix, reads target flags and visibility policy, and applies
  independent per-source timed burns via the shared status scheduler. Refresh
  does not restart the next one-second tick. Expiry and target death remove the
  burn; if the Phoenix disappears before its burn expires, ticks continue with
  an unattributed source rather than claiming a recycled edict.
- `g_save.c`: saves fire cooldown and hatch deadline; new state bumps the save
  format, following the no-migration policy. In-flight spell missiles use the
  existing `F_MMOVE` offset contract.

In the stock `UnitAbilities.slk`, Phoenix Egg has `ACmi` and `ACrk`: the creep
aliases for `Amim` spell immunity and `Arsk` Resistant Skin. `S_UnitSpellImmune`
recognizes `ACmi`, and `S_UnitIsResistant` recognizes `ACrk` through its
`CAbilityResistantSkin` registration. The patch intentionally does not hardcode
200 HP, armour, or these passive abilities in C.

## Test coverage and remaining validation

Source regression tests check handler registration, negative full-health regen
with lethal transition, and persistence of the new timer fields. These tests
do not yet exercise Phoenix creation, Fire target acquisition, the complete
death-to-egg-to-Phoenix cycle, or authored presentation in a running game. The
following end-to-end behaviours need confirmation:

1. Cast Phoenix from Blood Mage; verify authored UnitID, flying motion, HP
   drain at full health, normal healing, and no generic summoned classification.
2. Allow HP to reach zero; check normal kill event, prompt egg creation at same
   location, no harvestable corpse, and 10-second rebirth with full HP.
3. Kill egg at 9.9 seconds; no hatch. Test healing/negative effects on the egg
   and the loaded `Amim`/`Arsk` passives.
4. Recast during Phoenix life and while egg is incubating; the prior form
   should not hatch and the new Phoenix should be controllable.
5. Place two valid enemy units, a friendly unit, an immune unit and a Hero
   near the Phoenix. Check target mask, projectile art, DataA initial damage,
   DataB one-second ticks, HeroDur, buff refresh, multiple sources and
   interrupted or destroyed source. Repeat using ROC-style Data11/Data12
   columns and custom non-stock damage/cooldown values.
6. Save and load with an egg incubating and a Fire missile/burn active. Ensure
   only one hatch happens, no repeated instant damage, and timers resume.

**Data cross-check (1.29):** `AHpx` UnitID1 is `hphx`; `Aphx` UnitID1 is
`hpxe`; Phoenix Balance has 1,250 HP and `regenHP=-25` with `regenType=always`;
Egg Balance has 200 HP, zero armor, and `regenType=none`. `Apxf` has
`targs=ground,air,enemy`, Area 600, Cool 0.5, Dur 10, HeroDur 7, DataA 20,
DataB 2. `HumanAbilityFunc.txt` supplies `Apxf`'s Phoenix mini-missile at speed
900 and `Bpxf`'s Breath of Fire damage target art. These references are in the
War3.mpq and duplicated in the 1.29 War3x.mpq. The Phoenix unit's ability list
contains `Aphx,ACmi,ACrk,Apxf`; the Egg contains `Aphx,ACrk,ACmi`. This
feature is TFT-only: the inspected RoC 1.0 War3.mpq has no `AHpx`, `Aphx`, or
`Apxf` rows. Maps that replace the stock Phoenix/Egg UnitIDs remain unverified.
The referenced models are present in War3x.mpq as `Phoenix_Missile_mini.mdx`,
`BreathOfFireDamage.mdx`, and `PhoenixEgg.mdx` (the data's `.mdl` names resolve
through the MDX model path).

Other potential retail parity work includes egg birth/hatch visual sequencing,
precise Fire missile re-targeting, stacked fire visuals, and the
ownership/event semantics of Phoenix creation and recasting.
