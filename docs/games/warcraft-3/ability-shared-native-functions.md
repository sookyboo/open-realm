# Warcraft III shared native ability functions

This document records exact-build native helpers that may reduce repeated
ability verification work. Addresses below apply only to the Retail executable
with SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed` (PE32
x86, preferred image base `0x00400000`). Re-derive them for another executable.
For the larger picture of registration, instance identity, cast paths, and
evidence limits, see [Retail ability architecture](ability-retail-architecture.md).

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
| `0x006D4560` | Ability/status instance attachment to a unit | The body registers an instance, caches selected special rawcodes on the unit, invokes virtual lifecycle hooks on the new instance, and notifies already attached instances. Full-analysis Ghidra found 54 direct calls from 34 caller functions. This is a useful point to verify whether an ability's resulting status object actually becomes attached and enters shared unit lifecycle dispatch; it does not itself prove the ability-specific creation rules or expiry behavior. |
| `0x006D87A0` | Shared JASS buff-filter and attached-instance removal loop | Both `UnitRemoveBuffs` (`0x004AF5E0`) and `UnitRemoveBuffsEx` (`0x004AF610`) resolve the unit and call this function. The extended wrapper reorders its category arguments into the helper's internal order; the simple wrapper supplies a fixed set of category switches. The helper walks attached instances, checks positive/negative and category predicates through virtual slots, and calls `0x006D8530` on matches. It fetches the next list entry before removal and returns a removal count internally. Full-analysis Ghidra found 27 direct calls from 22 functions. For the `BTLF` object created by `UnitApplyTimedLife`, vtable slots `+0x1E0` and `+0x1E4` point to `0x0046A9A0` and `0x0046A9C0`; both methods return zero. These are the two polarity predicates the loop requires when `removeNegative` or `removePositive` is enabled. Static flow therefore excludes this BTLF instance from both native removal calls, independent of the other category switches. Verify the concrete instance class before applying that conclusion to another timed status. |
| `0x006D4B60` | Buff-object creation path used by `UnitApplyTimedLife` | The JASS native wrapper at `0x004AED50` resolves the unit and passes the requested buff code and duration here. This routine selects a buff prototype/factory, initializes the created object through virtual slot `+0x324`, attaches it through `0x006D4560`, then runs a post-attach helper. Its only direct caller found is the `UnitApplyTimedLife` wrapper, so this is a confirmed native path, not yet a shared spell-cast helper. The default branch selects `BTLF` via `0x006F4C40`. |
| `0x006F6820` | Shared progress/timed-value callback in the `CBuffTimedLife` vtable | Constructor `0x006F0D60` installs vtable `0x00EA63AC`; slot `+0x328` points to this method. It reads the global game-time value at `0x0112D88C`, compares it with a float supplied by the caller, changes object flag `0x80`, and invokes slot `+0x354` on one branch. The concrete clock argument and branch meaning are not fully recovered; this is a useful timer/progress trace point, not proof of unit removal at expiry. |
| `0x006F6BD0` | Shared lifecycle callback emitting event `0xD01C4` | This is slot `+0x354` in the `CBuffTimedLife` vtable above. It resets shared state, registers/updates a callback against the game-time value, and calls generic dispatcher `0x007FBF80` with event `0xD01C4`; a nonzero argument also invokes virtual slot `+0x30C`. The callback is referenced by many class vtables, so it is a shared lifecycle primitive. The event's semantic name and whether a particular caller uses it for expiry remain unresolved. |
| `0x006D8530` | Attached ability/status instance removal | The body marks the instance as removed, notifies sibling attached objects through a virtual hook, unlinks it from the owner's attached-instance list, refreshes list metadata, and clears cached pointers for selected rawcodes. Full-analysis Ghidra found 221 direct calls from 174 functions. This is a strong shared path for tracing dispel, expiry, death cleanup, or ability removal, but caller and virtual-hook analysis is still needed to identify which cause initiated each removal. |
| `0x006D4A10` | Reference-counted attached-object state transition candidate | The body updates two counters on the owning object, performs work on transition conditions, looks up an attached instance through `0x006D6570`, and visits other attached objects through virtual predicates before applying another virtual operation. Full-analysis Ghidra found 20 direct calls from 20 functions. This could help trace shared state changes or cleanup, but the affected state and virtual operations are not semantically identified yet. Treat it as a call-chain waypoint, not a verified ability contract. |
| `0x006EC8F0` | Shared ability/effect object initialization | Phoenix Fire reaches this after selecting a target with the `Bpxf` definition. Its body copies authored configuration into object fields, calls virtual setters, and delegates additional initialization; full-analysis Ghidra found 15 direct calls from 15 caller functions. The object type and complete lifecycle contract remain to be mapped at each caller. |
| `0x006ECA60` | Sibling ability/effect object initializer candidate | The body has a similar authored-data copy and virtual-setter pattern to `0x006EC8F0`, but writes a different object-field layout and delegates to `0x006E7D00`. Full-analysis Ghidra found 13 direct calls from 13 caller functions. This may identify another reusable object family while tracing applied effects; caller evidence is still needed before assigning it a gameplay role. |
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
| `S_UnitStatusAbilityEvent` in `games/warcraft-3/game/skills/s_skills.c`, with status storage in `m_unit.c` | Ability/status attach, registration, and subsequent per-unit lifecycle notifications | Retail `0x006D4560` appears to be the analogous object-oriented attachment point: it registers the instance and sends virtual notifications. OpenRealm stores status rows in a unit array and dispatches opted-in events by ability procedure, so this is a contract-level comparison, not a structural match. |
| `unit_expirestatus` and `UnitDispatchStatus` in `games/warcraft-3/game/m_unit.c` | Removal inverse ordering for dispel, expiry, death, and cleanup | Retail `0x006D8530` is a shared attached-object removal path. OpenRealm dispatches `A_STATUS_REMOVE` before clearing the status row, while Retail removes an object from an attached-instance list and notifies sibling objects. Compare caller paths and callback effects; do not assume identical cleanup ordering. |
| `S_SpellApplyTimedLife` and `S_SummonAbilityUnits` in `games/warcraft-3/game/skills/s_spell.c` / `s_summon.c` | Spell-owned timed-life application and summon ownership | Retail `UnitApplyTimedLife` has a concrete BTLF object creation/attach path through `0x006D4B60`; the direct path is registered at `0x0049B3C0` and implemented at `0x004AED50`. The stock spell summon path has not yet been shown to call that native wrapper or the same constructor. |
| `S_SummonAbilityUnits`, `S_SummonAbilityAt`, and `S_SpellApplyTimedLife` in `s_summon.c` / `s_spell.c`; Serpent Ward calls the shared summon path from `s_campaign_abilities.c` | Common UnitID/count/duration reads, unit creation, owner/ability identity assignment, and timed-life attachment | This suggests a high-value Retail search across summon abilities such as Serpent Ward, Spirit Wolves, and Pocket Factory. No common Retail summon helper is identified yet; do not infer one from the OpenRealm helper. |
| `S_ResolveAttackHit` in `s_attack.c`, plus `S_UnitStatusAbilityEvent` and `S_SearingArrowDamage` | Shared attack-hit dispatch, ability callbacks, damage modification, and on-hit status application | This is a useful comparison for attack-triggered effects (including orb/arrow abilities). OpenRealm Cold Arrows in `s_ability_stubs.c` only toggles placeholder state, so it is not a behavior reference. Retail's `0x007FBE90` is a generic callback delivery primitive; a concrete attack-to-ability call chain still needs to be established. |
| `S_SpellDamageEnemiesInRadius` and status application in `s_spell.c` / `s_area_spell.c` | Common area enumeration followed by per-target filtering, damage, or status application | Retail `0x0068EA00` is a widely reused area-enumeration helper. Determine the callback and target predicates at each ability caller; enumeration alone does not establish the effect. |

These analogues prioritize four Retail investigations: (1) locate the shared
status-instance creation/refresh path adjacent to `0x006D6570`; `UnitRemoveBuffs`
and `UnitRemoveBuffsEx` now provide named entry points into the shared filter
and removal path at `0x006D87A0` / `0x006D8530`; (2) resolve the clock argument,
event `0xD01C4`, and removal consequence around the `BTLF` vtable methods
`0x006F6820` / `0x006F6BD0`, then determine whether spell summons reuse the
`UnitApplyTimedLife` construction route; (3) find the attack-hit dispatch that
reaches concrete ability handlers; and (4) identify whether summon abilities
converge on a shared creation routine. For each, search cross
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
  -postScript Wc3Callers.java 0x00682180 0x0068EA00 0x006D6570 \
  0x006D4560 0x006D87A0 0x006D4B60 0x006D8530 0x006D4A10 \
  0x006EC8F0 0x006ECA60 \
  0x006AEA70 0x006ADA20 0x00B28980 0x007F6360 0x007FBE90 \
  0x006A9940 0x006ADB90
```

Use `Wc3DumpFunction.java` alongside the caller query when the helper's body
or argument contract needs inspection. Use Frida only when static references
cannot resolve the runtime receiver or virtual slot; a trace of one exercised
path supplements, but does not replace, the static caller analysis.
