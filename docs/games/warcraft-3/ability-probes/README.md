# Retail ability probe evidence

This directory holds detailed records. Load only the report needed for the
current investigation; the overview and current work are in
[Retail ability verification status](../ability-verification-review.md).

## Running a Retail probe

Start with the [Retail probe runner](../../../../tools/wc3_retail_probe.py)
and its workflow in [combat.md](combat.md#reproducing-these-retail-probes).
For a new observable ability question, create a manifest under
[`tools/retail_probes/`](../../../../tools/retail_probes/) and use the runner's
`prepare`, `launch`, and `capture` commands. This keeps map edits, control-map
checks, result freshness, and evidence metadata reproducible. Adapt an existing
manifest when its map and setup fit; keep a one-off script only when the runner
cannot express the experiment, and document that limitation.
For repeated runs, use
[`tools/wc3_retail_probe_repeat.py`](../../../../tools/wc3_retail_probe_repeat.py):
it creates an isolated output directory and a unique result file per
iteration. Retail map confirmation and probe interaction remain manual unless
a scenario has a separately documented automation procedure.

The checked-in [Shadow Strike attack-cycle probe](../../../../tools/retail_probes/shadow_strike_attack_cycle/manifest.json)
is the ready-to-run example for this workflow.
The [Phoenix Fire radius/cadence probe](../../../../tools/retail_probes/phoenix_fire/manifest.json)
is prepared as a second example. It compares source-matched damage at 300,
550, and 650 units. Its standalone prepared map has not yet completed a Retail
run. A separate JHCR diagnostic attempt in the existing process was
inconclusive: the ability level was present, but attack orders were rejected
and target damage events were not captured. See the [Phoenix Fire native
trace](native-triage.md#live-probe-attempt-october-16-2026-inconclusive). The
runner now detects an active process in the selected Wine prefix and stops
before launching a second instance. It cannot inject this prepared map into
the existing process; use a separate configured prefix or load the prepared
map in the existing process when its current scenario permits.
For live JASS reload experiments without restarting Warcraft, follow the
[JHCR 1.29 runbook](jhcr.md), which includes when to prefer JHCR and how to
keep reloadable probes rerunnable and safe around active callbacks.

| Report | Contains |
|---|---|
| [Targeting probes](targeting.md) | Charm, Purge, and multi-ability JASS probes with replay steps. |
| [Multi-ability native batch](multi-ability-batch.md) | TFT batch harness, outcomes, and validator/class trace. |
| [Combat traces](combat.md) | Carrion Swarm, the Retail Poison Attack/Venom Spear impact-to-Bpoi chain, Cold Arrow splash-missile effect endpoint, and damage receiver convergence. |
| [Presentation natives](presentation-natives.md) | Retail JASS effect/animation native registrations, shared creation/request paths, and unresolved renderer behavior. |
| [Status lifecycle traces](status-lifecycle.md) | Shared attached-instance removal, buff filtering, and the BTLF timed-life polarity boundary. |
| [Native triage](native-triage.md) | Static class/callback reconnaissance, Phoenix Fire path, and remaining inspection queue. |
| [Historical implementation notes](historical-implementation.md) | Older Jaina/Archmage implementation work, separate from Retail findings. |
| [Evidence capture notes](evidence-capture.md) | Optional Retail screenshot capture procedure. |

Raw capture artifacts may have been temporary and absent from the checkout.
Each report states which inputs remain reproducible and which findings rely
on retained notes only.
