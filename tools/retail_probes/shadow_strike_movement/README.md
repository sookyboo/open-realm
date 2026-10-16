# Shadow Strike movement-speed curves

This Retail 1.29.2.9231 probe compares hero Shadow Strike (`AEsh`), creep
Shadow Strike (`ACss`), and an untreated control. Three identical Footmen are
held at fixed coordinates; their effective speed is sampled every 0.25 seconds
for 35 seconds. A JASS timer records speed state, not unit displacement.

Each target is assigned 400 move speed before measurement. Confirm the initial
`MV_SETUP` and `MV_BASELINE` values are above 300 for all lanes. This puts
`AEsh`'s 50% and `ACss`'s 90% movement reductions above Warcraft's 150 speed
floor for at least part of the curve. If the requested baseline is clamped,
the run reports its actual value and may need a faster/custom target.

Cast orders occur after 5 seconds of baseline for `AEsh` and 6.5 seconds for
`ACss`; they are staggered to avoid overlapping the two same-name orders.
`EVENT_UNIT_SPELL_EFFECT` records the actual cast tick for each alias; samples
carry age relative to that event. Position locks counter campaign AI movement
without changing the speed query. The manifest gates capture on both accepted
orders, both spell-effect events, completion, and absence of `MV_SETUP_FAIL`.

Prepare and launch this manifest with the Retail probe runner as described in
[`ability-probes/jhcr.md`](../../../../docs/games/warcraft-3/ability-probes/jhcr.md).
The result path in `manifest.json` is specific to this Wine prefix. Keep JHCR
updates to `MV_Log`; do not reload the active timer callback.

## Recorded run

[`evidence/retail-1292-run1.txt`](evidence/retail-1292-run1.txt) is a complete
35-second capture, SHA-256
`f4df0b3182b480b98ecc796566e6272462125eee06cee5d381714f7f1be9fac1`. Both
casts were accepted and confirmed by `EVENT_UNIT_SPELL_EFFECT`; 19 baseline
samples were recorded, and the control stayed at 400 throughout. With ages
measured from each effect event, `AEsh` crossed speeds 250/300/350/390/400 at
2.25/4.25/6.25/10.25/14.25 seconds. `ACss` crossed 200/250/300/350/390/400 at
4.25/6.25/8.25/10.25/13.25/15.25 seconds. The first sample was at 0.25 sec:
200 for `AEsh` and 150 for `ACss` (the movement floor). This establishes
different sampled recovery curves, not the engine's continuous decay formula.
Retail executable SHA-256:
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.
