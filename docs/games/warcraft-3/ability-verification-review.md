# Warcraft III Retail ability verification status

This page summarizes exact-build Retail research. Detailed observations,
replay manifests, raw outputs, and native trace addresses are in the
[probe evidence index](ability-probes/README.md). The
[machine-readable function inventory](ability-function-investigation.json)
tracks 83 function records and 304 verified relationships for the pinned build.
Use the [shared-function workflow](retail-shared-ability-re.md) to extend it.

## Build and evidence policy

The October 2026 native traces use Warcraft III Retail 1.29.2.9231, PE32 x86,
preferred image base `0x00400000`, SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`. Recheck
the hash before using any address. Inspect matching AbilityData first, then the
exact executable; use Frida only for unresolved runtime branches or receivers,
and JASS only for externally visible behavior that static evidence cannot
settle. A native return, RTTI name, tooltip, or helper presence alone does not
prove gameplay behavior.

## Findings and open work

| Area | Established | Still open |
|---|---|---|
| Charm (`ANch`) | Probes establish tested stock target exclusions and a creep-level boundary. | Alias-specific limits/resource accounting; one custom level-3 result is anomalous. |
| Purge (`Apg2`) | Probes distinguish tested friendly and hostile movement effects. | Exact slow/recovery timing and aliases. |
| Carrion Swarm (`ACca`) | Stock TFT probes establish tested ground/air and ally/structure outcomes, a four-target sample cap, 160–240 unit width bracket, and a distal target hit at 600 units. | Data field mapping, full travel/collision rules, cap source, target-order effects, aliases. |
| Phoenix Fire (`Apxf`) | Native path reaches scheduled area acquisition, shared target validation, duplicate `Bpxf` filtering, and effect setup. A runner manifest probes damage at 300/550/650 units. | Standalone Retail probe has not completed; the live JHCR diagnostic was inconclusive. Interval/radius behavior, damage owner, missile/buff tick and expiry remain open. See [Phoenix Fire evidence](ability-probes/native-triage.md#live-probe-attempt-october-16-2026-inconclusive). |
| Shadow Strike (`AEsh` / `ACss`) | Controlled Retail captures verify the 75 initial hit, five source-matched 10-damage pulses 3 seconds apart, rank-1 movement-slow recovery for both aliases, and decaying attack-rate reduction for `ACss`. AbilityData confirms AEsh DataC=0 and ACss DataC=0.9. | Exact movement and attack-rate decay curves; see [Shadow Strike evidence](ability-probes/multi-ability-batch.md#shadow-strike-movement-speed-follow-up-october-16-2026) and [attack-cycle verification](ability-probes/multi-ability-batch.md#acss-attack-cycle-verification-october-16-2026). |
| Earthquake, Immolation, Cluster Rockets | The log records bounded sampled outcomes. | Their unsampled branches and authored field meanings; see the native inspection queue. |

## Repeatable workflow

1. Confirm the binary hash, version-matched data, and rawcode-to-class mapping.
2. Follow the class callback and helper path in Ghidra/radare2; record RVAs,
   call sites, receiver/slot, data reads, branches, and state writes.
3. Use a short Frida trace only when static callers or runtime values remain
   ambiguous.
4. For an open observable contract, start from the [Retail probe runner
   workflow](ability-probes/README.md#running-a-retail-probe). Reuse or add a
   manifest under `tools/retail_probes/`, prepare the map with
   `tools/wc3_retail_probe.py`, then run the controlled JASS probe. Use
   `tools/wc3_retail_probe_repeat.py` for independent repetitions. Preserve a
   control map and raw result; don't create an untracked one-off harness when
   the runner can manage the preparation and capture.
5. Record uncertainty and negative controls in the
   [function inventory](ability-function-investigation.json).

## Detailed evidence

- [Charm probe](ability-probes/targeting.md#retail-charm-target-verification-october-4-2026)
- [Purge probe](ability-probes/targeting.md#retail-purge-friendly-and-hostile-target-verification-october-4-2026)
- [Multi-ability batch](ability-probes/multi-ability-batch.md#tft-multi-ability-retail-batch-with-frida-october-4-2026)
- [Carrion Swarm probe and trace](ability-probes/combat.md#retail-carrion-swarm-target-cap-filters-and-line-width-october-5-2026)
- [Phoenix Fire native path](ability-probes/native-triage.md#phoenix-fire-native-path-periodic-acquisition-and-target-gates)
- [Remaining native inspection queue](ability-probes/native-triage.md#remaining-native-inspection-queue)

See also [ability lifecycle fixes and regression coverage](ability-lifecycle-review.md).
