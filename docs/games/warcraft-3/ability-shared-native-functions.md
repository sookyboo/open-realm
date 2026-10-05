# Warcraft III shared native ability functions

This document records exact-build native helpers that may reduce repeated
ability verification work. Addresses below apply only to the Retail executable
with SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed` (PE32
x86, preferred image base `0x00400000`). Re-derive them for another executable.

## Confirmed starting points

Phoenix Fire (`CAbilityPhoenixFire`) provides a traced caller path into several
candidate shared mechanisms:

| Function | Observed role | Evidence / limits |
|---|---|---|
| `0x00682180` | General spell target validation | Phoenix Fire's candidate callback passes the candidate classification through this helper. It checks common target rejection paths and registered validators. Numeric returns are internal rejection codes, not damage or an order-acceptance boolean. Full-analysis Ghidra found 64 direct call references from 64 caller functions. |
| `0x00682210`, `0x006822E0` | Common target rejection predicates | Each has one direct call reference from `0x00682180`; they consult target predicates and `MagicImmunesResistUltimates`. Exact semantic names for each rejection branch are not fully recovered. |
| `0x006AEA70` | Grouped target-mask expansion | Its body expands several grouped bits into normalized bit sets; `0x006ADA20` intersects the result with a candidate's target mask before returning a validation code. Full-analysis Ghidra found 21 direct calls from 13 functions. This can accelerate target-category checks (including corpse/structure/organic eligibility), but the numeric categories must be mapped from the specific ability's data and caller path before assigning names. |
| `0x006ADA20` | Target-mask and relation validation | Checks input mask validity, intersects the requested mask with the expanded candidate mask from `0x006AEA70`, then checks further target/owner relations through `0x006AD670`; returns native rejection codes. It has six direct references from four functions and is reached through the broader gate `0x006ADB90`. Useful for tracing why a target class is accepted or rejected, but less widely reused than `0x00682180`. |
| `0x0068EA00` | Area-unit enumeration | Phoenix Fire invokes it centered on the owner's position with a radius/configuration from the ability data object and callback `0x00C0F1E0`. Full-analysis Ghidra found 133 direct call references from 118 caller functions. |
| `0x006D6570` | Attached ability/status instance lookup by rawcode | Function-body inspection shows fast paths for several fixed FOURCCs, then iteration over attached instances and comparison through their rawcode getter. Phoenix Fire queries `Bpxf` and rejects a candidate when the status instance is already present. Full-analysis Ghidra found 959 direct call references from 681 caller functions, making this the strongest high-reuse starting point. The lookup does not establish application, refresh, expiry, or dispel behavior. |
| `0x006EC8F0` | Shared ability/effect object initialization | Phoenix Fire reaches this after selecting a target with the `Bpxf` definition. Its body copies authored configuration into object fields, calls virtual setters, and delegates additional initialization; full-analysis Ghidra found 15 direct calls from 15 caller functions. The object type and complete lifecycle contract remain to be mapped at each caller. |
| `0x0067FB80` | Additional owner/target relation check | Called from Phoenix Fire's candidate callback. It examines owner/target flags and invokes shared validation; a stable semantic label is not established. Full-analysis Ghidra found 40 direct call references from 37 caller functions. |
| `0x00699FD0` | Indexed candidate selection | Phoenix Fire calls this to choose one candidate from the collected area targets. Full-analysis Ghidra found seven direct call references from five caller functions; this is a narrower helper than target validation, enumeration, and buff lookup. |
| `0x00B28980` | `CAbilitySimpleSpell` order validation | Full-analysis Ghidra found 23 direct calls plus 187 non-call references (including virtual/data references). Its return value is a native validation result, not an acceptance boolean. This function is already traced for Carrion Swarm and other simple-spell callers; use its result together with caller continuation and externally observable order/event state. |
| `0x007F6360` | Generic descriptor/registry registration | Full-analysis Ghidra found 1,077 direct calls from 1,076 functions. Known ability-registration code passes a class descriptor and rawcode here (for example `AUcs` at caller `0x00C31370`), so it can help prove rawcode-to-class registration in this executable. Its large count reflects a generic registry mechanism, not shared gameplay behavior. |
| `0x007FBE90` | Generic callback/event delivery | Full-analysis Ghidra found 390 direct calls from 345 functions. Its body forwards an event identifier and arguments through a callback object's virtual slot `+0x8`; Phoenix Fire uses it to deliver event `0xD01B0` to its owned event member. This is useful for tracing event-driven ability lifecycles, but does not alone prove a timer duration or expiry contract. |
| `0x006A9940` | Shared damage/event payload initializer | Full-analysis Ghidra found 49 direct calls from 47 functions. Its body writes the payload's fields and clears two counters/flags; Carrion Swarm initializes a target payload here and then dispatches through the target vtable at `+0x120`. It is an initializer, not the damage applier, and field meanings still require caller/vtable tracing. |
| `0x006ADB90` | Shared target/state gate candidate | Full-analysis Ghidra found 18 direct callers. The body checks target virtual state and flags and calls buff lookup `0x006D6570` on one branch. This is a promising adjacent predicate to compare across abilities, but its complete semantic contract has not been established. |
| `0x006ECE00` | Shared configuration / presentation initializer candidate | Called by `0x006EC8F0`; the body initializes virtual string/config fields, reads a target's state and position, and enters additional effect setup paths. It has 20 direct references from 19 caller functions. It is promising for tracing effect initialization, but the object family and caller-specific contract are not yet established. |

The counts are direct incoming call references and unique caller functions in
the full-analysis Ghidra database, not counts of unique abilities or runtime
executions. They are useful for deciding where to inspect next: use the
highest-reuse helpers for buff lookup and area enumeration, use the validation
helpers for target gates, and use the payload/event helpers to follow effect
and lifecycle delivery. Validate a candidate's gameplay meaning from its
callers and arguments before reusing its behavior contract.

The ability-specific Phoenix Fire path is documented in
[ability-verification-review.md](ability-verification-review.md#phoenix-fire-native-path-periodic-acquisition-and-target-gates).
These helpers are promising reuse points, not blanket proof for other
abilities. To reuse one in a verification, establish that the ability's own
call path reaches it with the same arguments and that the relevant authored
data and branch outcomes match.

## OpenRealm comparison cases and next shared-function targets

OpenRealm's implementations help identify the native contracts worth looking
for, but do not prove that Retail uses the same code or behavior. The useful
comparison cases currently in the game module are:

| OpenRealm implementation | Contract to look for in Retail | Current evidence / caveat |
|---|---|---|
| `CAbilityFaerieFire` and `melee_status_execute` in `games/warcraft-3/game/skills/s_melee_spells.c`; `S_SpellApplyTimedTargetStatus` in `s_spell.c` | Enemy/alive target validation, duplicate-status lookup, status creation or refresh, authored duration, and target effect | Retail `0x006D6570` is a proven shared attached-instance lookup and is the best starting point for the duplicate check. It does not prove how a status instance is created, refreshed, or expired. |
| `S_SummonAbilityUnits`, `S_SummonAbilityAt`, and `S_SpellApplyTimedLife` in `s_summon.c` / `s_spell.c`; Serpent Ward calls the shared summon path from `s_campaign_abilities.c` | Common UnitID/count/duration reads, unit creation, owner/ability identity assignment, and timed-life attachment | This suggests a high-value Retail search across summon abilities such as Serpent Ward, Spirit Wolves, and Pocket Factory. No common Retail summon helper is identified yet; do not infer one from the OpenRealm helper. |
| `S_ResolveAttackHit` in `s_attack.c`, plus `S_UnitStatusAbilityEvent` and `S_SearingArrowDamage` | Shared attack-hit dispatch, ability callbacks, damage modification, and on-hit status application | This is a useful comparison for attack-triggered effects (including orb/arrow abilities). OpenRealm Cold Arrows in `s_ability_stubs.c` only toggles placeholder state, so it is not a behavior reference. Retail's `0x007FBE90` is a generic callback delivery primitive; a concrete attack-to-ability call chain still needs to be established. |
| `S_SpellDamageEnemiesInRadius` and status application in `s_spell.c` / `s_area_spell.c` | Common area enumeration followed by per-target filtering, damage, or status application | Retail `0x0068EA00` is a widely reused area-enumeration helper. Determine the callback and target predicates at each ability caller; enumeration alone does not establish the effect. |

These analogues prioritize four Retail investigations: (1) locate the shared
status-instance creation/refresh path adjacent to `0x006D6570`; (2) trace a
timed-life status to its expiry scheduler; (3) find the attack-hit dispatch
that reaches concrete ability handlers; and (4) identify whether summon
abilities converge on a shared creation routine. For each, search cross
references from known ability callers, inspect the helper body, then compare
at least two distinct ability classes before calling it shared. Add a native
address here only after that exact-build call-chain evidence exists.

## Current investigation

A full Ghidra analysis of the pinned executable completed successfully and is
stored in `data/wc3-ghidra-full/Wc3Retail1292Full`. Incoming references were
queried against that project with `tools/ghidra/Wc3Callers.java`. High call
count alone does not establish a gameplay contract: exclude generic
compiler/runtime helpers and separate direct code references from virtual
dispatch sites.

## Reproducible inspection

Use the cached full-analysis project for read-only call/reference inspection:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/data/wc3-ghidra-full" Wc3Retail1292Full \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3Callers.java 0x00682180 0x0068EA00 0x006D6570 0x006EC8F0 \
  0x006AEA70 0x006ADA20 0x00B28980 0x007F6360 0x007FBE90 \
  0x006A9940 0x006ADB90
```

Use `Wc3DumpFunction.java` alongside the caller query when the helper's body
or argument contract needs inspection. Use Frida only when static references
cannot resolve the runtime receiver or virtual slot; a trace of one exercised
path supplements, but does not replace, the static caller analysis.
