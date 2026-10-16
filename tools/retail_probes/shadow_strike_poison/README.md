# Shadow Strike poison timing probe

Retail 1.29.2.9231 probe for rank-1 hero `AEsh` and creep `ACss`. It logs
source/target-matched damage events and samples target movement speed every
250 ms for 25 seconds. The manifest and JASS inputs are reusable with the
[Retail probe runner](../../wc3_retail_probe.py); use the JHCR and persistent
Xvfb launch workflow in
[`docs/games/warcraft-3/ability-probes/jhcr.md`](../../../docs/games/warcraft-3/ability-probes/jhcr.md).

The cast lanes use separate Warden casters and high-health Footman targets.
Both target positions are reasserted every 50 ms. `AEsh` is cast at tick 100,
`ACss` at tick 130. The probe requires both accepted orders and matching
`EVENT_UNIT_SPELL_EFFECT` events. It records source and target handle IDs so
ambient damage can be excluded from the measured lane.

## Retail result

Two captures reproduced the same timings. From each `EVENT_UNIT_SPELL_EFFECT`
tick:

| Alias | Initial damage | 10-damage pulse ages (50 ms timer ticks) | Last pulse |
|---|---:|---|---:|
| `AEsh` | 75 at age 0 | 60, 120, 180, 240, 300 | 15.0 s |
| `ACss` | 75 at age 2 | 62, 122, 182, 242, 302 | 15.1 s |

Each alias therefore produced five 10-damage pulses, spaced 60 probe ticks
(nominally 3 seconds) apart. No further 10-damage events appeared during the
remaining capture: 4.5 seconds after the last `AEsh` pulse and 2.9 seconds after
the last `ACss` pulse. Event ticks are quantized by the 50 ms JASS timer; they
do not establish finer internal engine timing.

The same capture sampled movement speed at 250 ms intervals. `AEsh` was back
at 400 by age 14.25 s, before its final poison pulse at 15.0 s. `ACss` reported
398.089 at age 15.0 s, then 400 at age 15.25 s, after its final pulse at
15.1 s. Thus the sampled movement-slow recovery and poison-pulse endpoint are
close for `ACss`, while `AEsh` movement recovered earlier. Sampling does not
prove the exact continuous expiry boundary.

### Evidence limitation

The second-run harness set caster acquisition range to zero, but the campaign
run still produced other caster-sourced damage events, likely from ambient unit orders.
Those events had variable amounts and are preserved in the raw output. The
poison schedule above counts only the repeated exact `10.000` events; the
initial hit is the `75.000` event immediately associated with each spell-effect
marker. Do not use total damage-event counts as poison-tick counts.

Raw results:

- [Run 1](evidence/retail-1292-run1.txt), SHA-256
  `3284085dd9ce738eea65af033555eac4b9ddedc97b818fb21602d27c9a6d2260`
- [Run 2](evidence/retail-1292-run2.txt), SHA-256
  `bb3e6b710b8af4ee4d2c6892629041322749fffe083fde00698e3a203107b008`

The `capture.json` files alongside each result retain runner freshness and
marker status. Both report `ready_for_review`; that status is a capture gate,
not an ability verdict.
