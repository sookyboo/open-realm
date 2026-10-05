# Warcraft III Retail ability architecture: recovered evidence

This document summarizes the native ability structure recovered from local
Retail binaries. It is a working map for static verification, not a complete
reconstruction of Blizzard's source architecture. Native addresses and counts
are build-specific.

## Build identity and evidence rules

The current shared-helper and recent class-path analysis uses the PE32 x86
Retail executable with preferred image base `0x00400000` and SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`. The
cached full Ghidra project is `data/wc3-ghidra-full/Wc3Retail1292Full`.
Earlier binary inheritance work used a different executable hash. Keep those
addresses separate; a version label alone does not make VAs, RVAs, or section
file offsets interchangeable.

Evidence in this file is labeled by what the tools established:

- **Registration evidence** ties a rawcode and descriptor to a class factory
  in the exact executable.
- **Static path evidence** ties a concrete class or caller to functions,
  fields, callbacks, and branches in that executable.
- **Runtime class evidence** confirms a factory return and vtable during the
  observed run. It does not prove that an effect executed.
- **Behavior evidence** requires a complete static branch/data path or a
  suitable JASS-observed effect. A class name, tooltip, helper presence, or
  native return by itself is not enough.

## Identity: rawcode, implementation code, descriptor, instance

AbilityData rows can have an authored row rawcode and a separate `code=`
implementation code. For example, the exact-build data audit maps Carrion
Swarm row `ACca` to implementation code `AUcs`. The executable's registration
path at `0x00C31370` passes the `AUcs` FOURCC and class descriptor
`0x011B7F44` to the generic registry at `0x007F6360`.

Keep these identities distinct while tracing:

1. **AbilityData row**: authored row values, strings, target fields and
   aliases.
2. **Implementation code**: the code used to select the native class in a
   registration path.
3. **Class descriptor / generator**: registration metadata used to create
   instances.
4. **Instance vtable**: constructor-installed dispatch table for an
   individual ability object.
5. **Buff/status FOURCC**: a separate attached instance that may be queried,
   created, or removed by an ability.

The Carrion Swarm constructor at `0x00C2FC20` writes instance vtable
`0x00F887B0`; this is distinct from the generator table pointer
`0x00F887A0` stored in its registration descriptor. Frida confirmed the
observed `CAbilityCarrionSwarm` factory result had the expected instance
vtable. The five-class TFT trace also matched the expected vtables for
Immolation, Shadow Strike, Earthquake, Cluster Rockets, and Carrion Swarm.
These results establish class paths for that run, not full ability behavior.

Always resolve the data row using the same game data and edition as the
executable, then confirm its implementation code and registration in that
executable. A generated registry from a different hash is a search aid only.

## Shared runtime structure

The strongest currently recovered cross-ability mechanisms are:

| Concern | Exact-build entry point | Recovered role |
|---|---|---|
| Class registration | `0x007F6360` | Generic descriptor/registry insertion; high call count is generic infrastructure, not gameplay evidence. |
| Simple-spell validation | `0x00B28980` | Shared `CAbilitySimpleSpell` order validation reached directly by many classes. Its integer result is a native result code, not a boolean acceptance value. Concrete callers can continue with more validation after a zero result. |
| Candidate target validation | `0x00682180`, `0x006AEA70`, `0x006ADA20` | Shared target rejection and target-mask/relation checks. Numeric target-mask categories and rejection values must be decoded in the ability's caller context. |
| Area candidates | `0x0068EA00` | Shared area-unit enumeration. The caller-supplied center, radius, callback, and callback predicates determine the actual ability behavior. |
| Attached instance lookup | `0x006D6570` | Looks up attached ability/status instances by rawcode; Phoenix Fire queries `Bpxf` and avoids a duplicate. Lookup alone says nothing about application or expiry. |
| Ability construction | `0x00AF3BA0`, `0x006D4560` | `UnitAddAbility` enters an AbilityData implementation-code switch that creates a concrete class instance, initializes it, and attaches it through the shared instance lifecycle. |
| Ability rank update | `0x004971C0`, `0x004AAE20`, virtual `+0x2E4` / `+0x2E8` | Get/Set and Inc/Dec read or mutate the level field on the existing attached instance. The common up/down callbacks refresh level-indexed values; selected classes append their own virtual work. |
| Ability disable/enable | `0x006D61E0`, `0x0046E0C0`, `0x0046E630` | `BlzUnitDisableAbility` changes disable counters on the existing attached object. Shared transition routines invoke class virtual hooks only when the counter crosses the enabled/disabled boundary. |
| Attach and removal | `0x006D4560`, `0x006D8530`, `0x006D87A0` | Register an attached object, filter attached objects for JASS buff-removal natives, and notify/unlink selected objects. `UnitRemoveAbility` directly removes a rawcode-matched instance; `UnitRemoveBuffs` and `UnitRemoveBuffsEx` share the filter loop, where class virtual predicates decide per-instance eligibility. |
| Callback delivery | `0x007FBE90` | Generic callback/event forwarding through a virtual slot. An event ID or callback site must be traced to establish its lifecycle meaning. |
| Damage/effect payload | `0x006A9940`, target vtable `+0x120` | Both the registered JASS `UnitDamageTarget` wrapper (`0x004AEF70`) and Carrion Swarm (`0x00C30BB0`) initialize an event payload and dispatch it through this target slot. For unit targets, `CUnit`'s implementation (`0x006677C0`) contains immunity/resistance checks, attached-object callbacks, configured damage bonuses and a negative value update through its `+0x128` method (`0x00668DB0`). `CWidget` (`0x006BD260`) and `CDestructable` (`0x006CE850`) have distinct overrides; generic dispatch does not imply CUnit mitigation for every widget. |

Full call counts and caveats are in
[shared native ability functions](ability-shared-native-functions.md).
Treat each helper as a waypoint. To reuse it for a second ability, prove that
the concrete caller reaches it with relevant arguments and data, then inspect
the branch and resulting virtual operation.

## Cast and effect paths

Evidence so far supports layered execution rather than one universal
`cast -> effect` function:

- `CAbilitySimpleSpell` supplies a shared order-validation path, while
  concrete classes may add checks afterward. Carrion Swarm's caller at
  `0x00C2FA90` checks additional target flags after calling
  `0x00B28980`.
- A concrete class can own its scan, event, missile, status, or effect
  callbacks. Carrion Swarm's native path creates a `CMissileCarrionSwarm`,
  scans candidates, applies per-candidate predicates, initializes a payload,
  and dispatches it to the target. Phoenix Fire instead has a scheduled event
  that enumerates nearby units, rejects already-affected candidates, selects
  one, and enters a status/effect setup path.
- Ability instances may own nested callback/event members. Phoenix Fire's
  code schedules event `0xD01B0`; the generic callback helper is involved in
  delivery. The configured interval's exact AbilityData field and the
  resulting damage/tick ownership remain unresolved.
- Similar class names or shared parent classes do not imply identical target
  masks, data-field meanings, damage, duration, or interruption behavior.

For casts, preserve the native result values and continuation branches. A
zero or nonzero from an order validator cannot be translated into
accepted/rejected without following the caller and checking the observed
JASS spell event or effect. The concrete class trace and the behavior trace
are separate evidence.

## Attached status and object lifecycle

Retail stores ability/status objects as attached instances on a unit rather
than the flat status rows used by OpenRealm. The exact-build helpers establish
these common lifecycle operations:

1. `0x006D4560` attaches/registers an instance, updates special cached
   pointers, invokes virtual lifecycle hooks, and notifies existing attached
   objects.
2. `0x006D6570` searches attached instances by rawcode; Phoenix Fire uses it
   to check for `Bpxf` before applying another effect.
3. `0x006D8530` marks an object removed, notifies other attached objects,
   unlinks it, updates list metadata, and clears selected cached pointers.
4. JASS `UnitAddAbility` (`0x004AE8F0`) resolves the unit, uses
   `0x006D6570` to reject a duplicate rawcode, then calls
   `0x00AF3BA0`. That factory reads the AbilityData row and switches on its
   implementation code at `+0x30`, invokes the concrete constructor,
   initializes the resulting instance through virtual slot `+0x80`, and
   attaches it through `0x006D4560`. The factory has 10 direct callers in this
   build. `UnitRemoveAbility` (`0x004AF590`) uses the same rawcode lookup,
   removes the found instance through `0x006D8530`, and reports whether it
   found one. Both wrappers notify via `0x005F6D00` after a successful change.
5. `GetUnitAbilityLevel` (`0x004971C0`) returns the attached object's
   zero-based rank field at `+0x50`, plus one, or zero when no eligible object
   is found. `SetUnitAbilityLevel` (`0x004AAE20`) clamps to level one through
   the data maximum and invokes rank-up slot `+0x2E4` or rank-down slot
   `+0x2E8` repeatedly on that existing object; it does not replace the
   instance. `IncUnitAbilityLevel` and `DecUnitAbilityLevel` use the same
   callbacks and respect the max/level-one bounds. The shared methods
   `0x00B498D0` / `0x00B498F0` update the stored rank through `0x0046B3C0` /
   `0x0046B3E0` and refresh the level-indexed value through `0x0046FA80`.
   Immolation (`0x00F277EC`), Carrion Swarm (`0x00F887B0`), Shadow Strike
   (`0x00F98714`), and Cluster Rockets (`0x00FB2C6C`) use these common methods
   directly at slots `+0x2E4` / `+0x2E8`; Earthquake (`0x00F85CF0`) uses
   methods `0x00C298D0` / `0x00C298F0`, which call them and then invoke an
   extra virtual slot `+0x434`. All four level natives share a preflight
   internal tag `0x2B61676C` and field check `+0x20 == 0`; that gate's meaning
   is not yet established.
6. The pinned executable registers `BlzUnitDisableAbility` (`0x004AF020`);
   no `UnitDisableAbility` native is registered. Its wrapper resolves the
   unit and calls `0x006D61E0` with rawcode, `hideUI`, and `flag`. The helper
   locates the attached ability through `0x006D6570` and selects disable
   (`flag != 0`) or enable (`flag == 0`) state mutation. `0x0046E0C0` increments
   the per-instance disable counter at `+0x3C`; on the zero-to-positive
   transition it invokes vtable slot `+0xE0`, clears instance flag bit `0x2`,
   and invokes `+0xC4`. `0x0046E630` decrements the counter; on the positive-to-
   zero transition it invokes `+0xE4`, and may restore flag bit `0x2` and call
   `+0xC8` when the owning unit has flag `+0x164 & 4`. A secondary per-instance
   counter at `+0x40` is adjusted by the wrapper's hideUI-derived argument;
   the enable path passes `hideUI == false` to that adjustment, so follow the
   native argument through the wrapper before concluding presentation behavior.
   Both shared functions refresh UI state and have 107 / 99 direct call
   references respectively. In the sampled exact-build vtables, Carrion
   Swarm, Shadow Strike, and Cluster Rockets use default transition methods;
   Immolation overrides `+0xC4` and `+0xE4`; Earthquake overrides `+0xC4` and
   `+0xC8`. `UnitMakeAbilityPermanent` (`0x004AF460`) separately increments
   or decrements instance field `+0x38`; its downstream effect is not yet
   traced.
7. `0x006D87A0` is the shared filter loop called by both JASS natives
   `UnitRemoveBuffs` (`0x004AF5E0`) and `UnitRemoveBuffsEx` (`0x004AF610`).
   The extended wrapper passes `physical`, `magic`, `timedLife`, `aura`,
   `autoDispel`, `removePositive`, and `removeNegative` into the helper in
   that internal order; the simple wrapper supplies fixed category switches
   and forwards only its positive/negative arguments. The helper tests object
   virtual predicates, calls `0x006D8530` for matches, and returns the number
   removed internally. Several predicate slots are not semantically named
   yet, so the branch conditions and concrete object's vtable must be checked
   before claiming a class-specific filter result. For the `BTLF` instance
   created by `UnitApplyTimedLife`, vtable slots `+0x1E0` and `+0x1E4` point
   to `0x0046A9A0` and `0x0046A9C0`; both methods return zero. Since the loop
   requires one of these polarity predicates to match, this `BTLF` instance
   is statically excluded from both native removal paths even when the other
   category switches allow timed life and auras.
8. Concrete buff/ability callbacks and the code that invokes these helpers
   determine the actual duration, stacking, dispel, death, or inverse rules.

The native `UnitApplyTimedLife` path is now partly recovered in this exact
build. Registration at `0x0049B3C0` maps the JASS native to wrapper
`0x004AED50`; the wrapper resolves the unit and calls `0x006D4B60` with the
requested buff code and duration. `0x006D4B60` selects a buff prototype,
initializes its instance through virtual slot `+0x324`, attaches it through
`0x006D4560`, and runs a post-attach helper. The default code path selects
`BTLF` through `0x006F4C40`. Constructor `0x006F0D60` sets up a
`CBuffTimedLife` instance on the `CBuffProgressBar` base and initializes an
embedded `FloatMini` member. This maps native timed-life object creation and
attachment. Its vtable slot `+0x328` points to `0x006F6820`, which compares a
caller-provided float with the global game-time value at `0x0112D88C` and may
invoke slot `+0x354` (`0x006F6BD0`). That callback dispatches event `0xD01C4`
through `0x007FBF80` and conditionally invokes another virtual method. This
connects timed-life objects to shared timed/progress lifecycle machinery, but
the float's exact meaning, event semantics, final removal consequence, and
whether stock spell summons use the native construction route remain open. See
the [shared-helper map](ability-shared-native-functions.md) for the addresses
and evidence limits.

OpenRealm provides useful contract comparisons in `unit_addtimedstatus`,
`unit_expirestatus`, `UnitDispatchStatus`, and `S_UnitStatusAbilityEvent`.
Those implementations use fixed status rows and procedure dispatch, so they
help frame questions (apply/refresh/remove/tick/death) but do not establish
Retail's object layout or callback behavior.

## Serialization and mutable state

Retail ability instances have class-specific save/load and cleanup methods.
Exact class inspection found paired serializer callbacks for classes such as
Carrion Swarm, Phoenix Fire, Mirror Image, Resurrection, Raven Form, and Root.
The existence of a save/load override proves owned state is serialized, but
not the gameplay role of every serialized field. Identify serializer helper
calls, stream direction, member offsets, and the matching restore path before
claiming persistence for a behavior.

Do not treat a factory pointer, instance vtable, registry descriptor, or
runtime object address as persistent identity. Reacquire the concrete class
and attached object relationships after load when tracing saved state.

## Using OpenRealm abilities as comparison cases

OpenRealm is useful for choosing the native question to investigate:

- Faerie Fire suggests examining enemy/alive validation, duplicate status,
  duration, and target art.
- Serpent Ward and `S_SummonAbilityUnits` suggest looking for shared
  UnitID/count/duration reads, ownership, and timed life.
- `S_ResolveAttackHit` and attack-bonus status callbacks suggest following
  Retail attack-hit dispatch for orb/arrow effects. OpenRealm Cold Arrows is a
  placeholder toggle and is not a behavior-equivalent reference.
- `unit_expirestatus` suggests checking whether Retail removal invokes the
  status's inverse before unlinking it.

These are search hypotheses, not Retail evidence. Current gaps include a
confirmed shared Retail summon constructor/timed-life path, the concrete
attack-to-ability dispatch for on-hit effects, the buff creation/refresh and
expiry scheduler, and complete virtual-hook meanings for attach/removal.

## Reproducible inspection

Verify the binary hash before using any address. Reuse the cached project for
read-only inspection:

```sh
sha256sum 'data/Warcraft III/Warcraft III.exe'
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/data/wc3-ghidra-full" Wc3Retail1292Full \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3DumpFunction.java \
  0x004AE8F0 0x004AF590 0x004AF020 0x004AF460 \
  0x004971C0 0x004AAE20 \
  0x00498B20 0x0048F150 0x00AF3BA0 0x00B28980 \
  0x006D61E0 0x0046E0C0 0x0046E630 \
  0x00C2FA90 0x00C31430 0x00C30BB0 \
  0x00682180 0x006AEA70 0x006ADA20 0x0068EA00 \
  0x006D4560 0x006D6570 0x006D8530 0x006A9940 \
  0x006756D0 0x00676940 0x006CF320 \
  0x006677C0 0x00668DB0 0x006BD260 0x006CE850 0x006CEF00 \
  0x006A0630 0x0067B920
```

Use `Wc3Callers.java` for direct incoming references and caller sites. Confirm
the decompiler's x86 `thiscall` receiver in `ECX`, stack argument order,
virtual slot offsets, and branch results in disassembly. Use Frida only when
static analysis cannot settle a runtime receiver or virtual target. A hook
should filter the ability order/object, preserve raw return values, and be
paired with static caller evidence.

For the full JASS/Frida workflow and known failure modes, see
[ability verification review](ability-verification-review.md). For the
separately recovered demo/TFT inheritance details and their build scope, see
[ability inheritance binary evidence](ability-inheritance-binary.md).
