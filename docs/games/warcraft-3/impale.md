# Impale — travelling wave, stun and airborne lift (patches 1–2)

Impale (`AUim`) and the independently authored creep ability (`ACmp`) run through
`CAbilityImpale` in `skills/s_impale.c`. Patch 1 replaced the old instantaneous
line-wide hit scan. Patch 2 adds the stun and airborne lift lifecycles.
Spike art and version-dependent airborne targetability remain future work.

## Game-data contract

- `DataA` gives wave travel distance; `DataB` gives the total travel time;
  `DataC` gives damage at each successful hit.
- `Area` is provisionally treated as the **full width**, so half the value
  is applied on either side of the line, extended by target collision radius.
  The precise retail width convention still requires verification.
- `targs` is evaluated by the shared `S_SpellAllowsAreaTarget` filter,
  in addition to the enemy/alive checks. A cast does not require visibility
  of every unit subsequently struck by its travelling area effect.
- `BuffID` (`BUim` if missing), `Dur` and `HeroDur` establish a timed stun
  when each target is struck. `BUim` contributes `WC3_STATUS_STATE_STUNNED`;
  the state is evaluated by the shared movement eligibility check, AI and spell execution independently
  of the unit's currently playing animation.
- `DataD` determines the separate air-time duration for ground and hero units.
  Landing does not end stun, and a shorter custom stun does not prematurely
  end the airborne presentation.

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
completion. The victim's `BUim` status owns stun while `COMPONENT_IMPALE_LIFT` (ID 32)
owns airborne presentation. Unlike ordinary Cyclone, Impale does **not**
reclassify the victim as `TARG_AIR`, nor make it immune to attacks/spells.
Full version-aware airborne targetability is deferred to patch 4.

The lifted position is `terrain/support + FlyHeight + S_ImpaleLiftOffset`.
This is important: flight, Raven Form, Ensnare and other lift owners continue
using their existing `FlyHeight` value; Impale never snapshots and restores
that mutable value. The temporary offset is computed from saved simulation
deadlines (`start_ms`, `end_ms`), peak and previous offset. A second Impale
restarts the curve from the current offset without a snap to ground.
`G_RunEntity` updates the lift even when `monster_think` skips movement while
stunned. A unit's death immediately retires the lift. Landing never wipes
any remaining BUim or independent stun status.

**Visual caveat:** The sinusoidal curve and 120-unit peak are isolated,
non-authoritative presentation approximations. `DataD` is authoritative for
its duration; the available asset report does not establish retail peak,
trajectory or any precise spike animation keys. No spike models are spawned
by patch 2; those belong to patch 3.

Status-slot exhaustion prevents creating BUim, but the physical hit and
independent lift still occur. A custom zero-duration stun similarly does not
prevent an authored nonzero `DataD` lift. Neither situation corrupts another
status owner.

## Persistence and regression coverage

`G_COMPONENTS`, the save component schema and the C callback roster include
the wave (save version 129) and the independent victim lift component
(save version **130**). Old saves are rejected, as the repository requires. `tests/t_impale.c` uses synthetic data for both `AUim` and `ACmp`,
with a deliberately nonstock 73/37 damage split, several sweep deadlines,
wrong-relationship/wrong-type units, and stale caster ownership.
The save round-trip regressions in `tests/t_game.c` verify wave callback and
hit-marker identity, plus victim lift deadlines, height continuity and
remaining stun after loading. The additional production-path cases in
`tests/t_impale.c` exercise launch, stun, landing, existing FlyHeight, overlapping
independent stun, repeated wave impact and victim death.

Build and execution of tests are intentionally delegated to the user.
