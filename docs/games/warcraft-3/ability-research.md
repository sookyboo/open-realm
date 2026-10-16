# Warcraft III ability research

Use this page as the entry point for ability work. It is intentionally short;
open the supporting documents only when the task needs their evidence.

## Start here

- [Retail verification status](ability-verification-review.md): tested
  contracts, uncertainty, and the next native investigation.
- [Ability coverage](architecture/ability-coverage.md): implementation scope
  in OpenRealm.
- [Ability implementation](ability-implementation.md): local data, behavior,
  registration, and test workflow.

## Retail reverse engineering

- [Shared helper map](ability-shared-native-functions.md): compact index of
  recovered native paths and open questions.
- [Function inventory](ability-function-investigation.json): exact-build
  function and relationship records. Query by category/status before loading
  the full file; never treat an address as portable across executable hashes.
- [Retail architecture](ability-retail-architecture.md): registration,
  instances, cast dispatch, status attachment, and evidence limits.
- [Repeatable RE workflow](retail-shared-ability-re.md): Ghidra, radare2,
  Frida, and controlled JASS procedure.
- [Focused evidence logs](ability-probes/README.md): replay manifests,
  raw observations, and detailed traces by investigation. Start from the
  verification status page; do not load every probe report by default.
- [JHCR live reload runbook](ability-probes/jhcr.md): build, instrument, and
  apply repeatable in-process JASS updates on Retail 1.29 under Wine.
- [Presentation native trace](ability-probes/presentation-natives.md): Retail
  effect creation and unit animation JASS wrapper paths.

## Local ability behavior references

Open the focused page linked from the [WC3 documentation index](readme.md)
for the ability family being changed. Lifecycle-wide findings are in
[ability lifecycle review](ability-lifecycle-review.md); status and item
effects are summarized in [ability and item effects](ability-and-item-effects.md).

## Evidence rules

Retail addresses apply only to the executable SHA-256 recorded in the
inventory. Separate direct observations from hypotheses. A shared interface,
RTTI name, tooltip, address co-occurrence, or OpenRealm analogue alone does
not prove shared Retail behavior. Promote a helper only after recording its
exact-build caller path, arguments/state effects, and a controlled positive
and negative case where practical.
