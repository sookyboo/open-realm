# ACss attack-cycle decay probe

Measures whether creep Shadow Strike (`ACss`) lengthens a target's attack
cycle, how the interval recovers, and whether an untreated lane stays stable.
The probe is tuned for Retail 1.29.2.9231.

## Setup and interpretation

- Two same-owner Footmen (`hfoo`) attack paused, high-health Footman dummies.
- The caster applies stock rank-1 `ACss` only to the treated Footman at probe
  tick 240. A 50 ms timer records damage events for 1200 ticks (60 seconds).
- Retail `UnitWeapons.slk` authors the Footman cooldown as 1.35 seconds. Do not
  use `BlzSetUnitAttackCooldown` here: this 1.29.2 setup returned zero from the
  getter and ignored the requested override. Mortar Team (`hmtm`) is 3.5 sec.
- The probe requires at least four baseline intervals. Check for accepted
  attack/cast orders, `SD_CAST_EFFECT`, and no `SD_SETUP_FAIL` before treating
  output as evidence. Compare the treated lane with the control lane.

## Re-run

Use the Retail probe runner documented in
[`ability-probes/jhcr.md`](../../../../docs/games/warcraft-3/ability-probes/jhcr.md).
Prepare with matching JHCR 1.29 inputs, visually preflight the control map,
launch the prepared map, advance the campaign intro, and capture the fresh
result. The manifest's result path is specific to the current Wine prefix and
must be changed for another machine.

JHCR allowlists only `SD_Log`. Do not hot-reload `SD_Tick` during a run; a
previous timer callback reload stopped its counter before completion.

## Recorded run

[`evidence/retail-1292-run1.txt`](evidence/retail-1292-run1.txt) is the raw
capture, SHA-256
`66eee38fef96a6705cf0dad298202d31401b364baffcfa739f1f798199014b4b`.
It recorded eight baseline intervals and steady 27-tick controls; after the
cast, treated intervals were 73, 53, 39, 34, 31, 29, then 27 ticks. The first
interval crosses the cast boundary. The spell-effect event was tick 259; the
first post-cast hit was tick 327. This supports a decaying attack-cycle delay,
but does not reveal the internal continuous decay formula.
