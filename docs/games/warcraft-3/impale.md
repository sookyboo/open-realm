# Impale — travelling wave (patch 1)

Impale (`AUim`) and the independently authored creep ability (`ACmp`) run through
`CAbilityImpale` in `skills/s_impale.c`. This patch replaces the old instantaneous
line-wide hit scan. It does **not** claim to implement stun, lift, spike art,
or version-dependent airborne targetability; those are subsequent patches.

## Game-data contract

- `DataA` gives wave travel distance; `DataB` gives the total travel time;
  `DataC` gives damage at each successful hit.
- `Area` is provisionally treated as the **full width**, so half the value
  is applied on either side of the line, extended by target collision radius.
  The precise retail width convention still requires verification.
- `targs` is evaluated by the shared `S_SpellAllowsAreaTarget` filter,
  in addition to the enemy/alive checks. A cast does not require visibility
  of every unit subsequently struck by its travelling area effect.
- `BuffID`, `Dur`, and `HeroDur` continue to be consumed when a wave hits,
  but `BUim` currently does not establish the full disabling/airborne state.

## Simulation ownership and timing

The non-rendered wave thinker has one `impaleWave_t` optional component
(`COMPONENT_IMPALE_WAVE`). It snapshots cast origin, direction, damage, width,
travel parameters, ability/rank and the caster's spawn identity. Its previous
travel distance is saved so skipped simulation frames cannot cause missed hits.
Distance travelled is `DataA * clamp(elapsed / DataB, 0, 1)`; the thinker
resolves the finite swept interval between its last and new distances. Targets
are processed by projected distance and stable edict index for exact ties.

An invisible `ImpH` identity edict tracks each hit with the wave pointer,
wave incarnation timestamp, victim pointer and victim incarnation timestamp.
Markers are retired when their wave finishes or its original caster slot is
recycled. Multiple waves can hit the same target independently; one wave
cannot hit it again on later simulation frames.

The wave remains authoritative if its visual assets are missing. It does not
use a projectile model and is independent of camera, frame rate and animation
completion. Spikes and the actual airborne/stun state are intentionally owned
by later ability-specific patches.

## Persistence and regression coverage

`G_COMPONENTS`, the save component schema and the C callback roster include
this wave. The save version advances to 129 (reserved after the prior combined TFT ability series); old save compatibility is not
retained. `tests/t_impale.c` uses synthetic data for both `AUim` and `ACmp`,
with a deliberately nonstock 73/37 damage split, several sweep deadlines,
wrong-relationship/wrong-type units, and stale caster ownership.
The save round-trip regression in `tests/t_game.c` verifies active state,
callback identity and hit marker references.

Build and execution of tests are intentionally delegated to the user.
