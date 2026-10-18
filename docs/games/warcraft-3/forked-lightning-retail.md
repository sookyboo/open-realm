# Forked Lightning (`ANfl`) Retail native path

## Identity and source set

This analysis applies to Warcraft III Retail 1.29.2.9231, PE32 x86, image
base `0x00400000`, executable SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.
The exact-build Ghidra project was reused read-only. Relevant exports are in
`build-re/ability-re/ghidra/ANfl-method-followup-01/`,
`ANfl-algorithm-detail-01/`, `ANfl-shared-damage-detail-01/`,
`ANfl-lifecycle-followup-01/`, `ANfl-data-lifecycle-helpers-01/`,
`ANfl-ranking-helpers-01/`, and `ANfl-vtable-detail-512-01/`.
The saved execution graph remains at
`build-re/ability-re/ANfl-auto-graph-final-01/`; the updated focused graph and
static package are at `build-re/ability-re/ANfl-focused-native-graph-02/` and
`build-re/ability-re/ANfl-complete-static-reconstruction-01/`.

This document distinguishes authored configuration, static control flow, and
archived Retail observations. Pseudocode below summarizes Ghidra output; it is
not original source. RVA-to-VA translation for this build is `VA = RVA +
0x00400000`.

## Registration and relevant methods

The exact-build class registration identifies factory file offset `0x00877840`,
which translates to RVA `0x00878440`; Ghidra decompilation shows that factory
allocating and initializing an object with the symbol
`CAbilityForkedLightning::vftable`. The constructor writes table address
`0x00FAF280`. A read-only vtable export at RVA `0x00BAF280` contains the
functions below. This verifies the class-to-table static relationship for the
pinned executable; it does not prove that a particular archived runtime object
had this receiver type.

| VA / RVA | Static evidence | Interpretation and limits |
|---|---|---|
| `0x00C78080` / `0x00878080` | vtable slot `+0x310`; returns `0xD026B` | Order-ID getter; archived Frida saw this return during the tested order path. |
| `0x00C78090` / `0x00878090` | vtable slot `+0x42C`; direct call to `0x00C78A50(this, 0)` | Native callback enters the target acquisition/application path. Archived Frida observed entry/exit. Its raw `EAX` value is not a declared result contract. |
| `0x00C787D0` / `0x008787D0` | Direct call to `0x00C78A50(this, 1)` | Same acquisition routine with a mode that skips per-target processing; caller's exact lifecycle role is unresolved. |
| `0x00C78A50` / `0x00878A50` | Direct calls to query builder `0x0068EA00` and selected-target worker `0x00C788F0`; passes callback `0x00C78FC0` and comparator `0x00C78F60` | Core spatial search, candidate ordering, and dispatch loop. Frida observed this function; the archived raw `EAX` values were 1 and 3. Ghidra decompiles it as `void`, so these raw register values are not treated as returned counts. |
| `0x00C78FC0` / `0x00878FC0` | Callback supplied to `0x0068EA00` | Candidate gate, deduplication, candidate append, cap check. Static callback dispatch; not separately traced in archived sessions. |
| `0x00C78F60` / `0x00878F60` | Comparator passed to sort helper `0x00AB2000` | Compares a stored float metric; ties compare the integer at candidate `+0x0C`. The meaning of that integer field is not established. |
| `0x00C788F0` / `0x008788F0` | Directly called for each retained candidate | Builds a per-target context, resolves the `MNfl` missile class object, and dispatches through its vtable at `+0xA4` to `CMissileForkedLightning` method `0x00C781D0` / RVA `0x008781D0`. This concrete method starts a generic data-driven action/event handle; its connection to damage remains unresolved. |

## Target acquisition and selection

The statically recovered path in `0x00C78A50` is:

1. Read the owning unit from ability field `+0x30`; read positions through unit
   virtual slot `+0xB8` for the owner and the order target.
2. Read several rank-indexed values from the ability data object at `+0x50`.
   The accessors read distinct fields in the indexed data row. One value is
   converted to an integer and used as a hard candidate limit. In stock TFT
   `ANfl`, authored DataB is `3`; the live JASS case sampled three affected
   targets, consistent with that value. The raw `EAX=3` from the void callback
   is not used as count evidence. The native row-field-to-DataB mapping is not
   independently proven here, so treat the equality as strong corroboration,
   not a field-name proof.
3. Compute a forward spatial path from the owner toward the explicit order
   target. In a loop, invoke `0x0068EA00` (VA) with query type `0xB`, a radius
   and center derived from rank data and path geometry, flags/mask arguments,
   the owner, and callback `0x00C78FC0`. The callback receives each spatial
   candidate and the per-query context. The precise meanings of all query
   flags and rank values are not decoded in this ability-specific caller.
4. The callback only continues its candidate-record path when
   `0x0067FB80(candidate, 0, 4)` is nonzero. It then obtains a value by
   calling virtual slot `+0x350` on the context’s leading object and passes
   that value plus the context pointer to `0x00682180`; return zero continues
   candidate recording. The exact semantic roles of those latter arguments
   are not assigned here. It checks
   the retained array to avoid duplicate unit pointers, computes a 2D distance
   from the candidate position to the stored target-position pair, then appends
   the candidate and metric. The numeric meanings of `0x0067FB80`'s flags and
   the shared validator's internal return codes remain those documented in the
   shared targeting notes.
5. Once the retained count reaches the configured limit, the callback returns
   false. The shared query builder stops candidate processing on a zero
   callback result. The caller also bounds its later processing loop by
   `min(candidate_count, limit)`.
6. The caller sorts only the candidates collected before that early stop. The
   comparator orders by its stored floating-point metric and uses the integer
   at candidate `+0x0C` on ties. It then invokes `0x00C788F0` for those entries.

This is **not** a global nearest-target search: candidates are capped during
spatial enumeration, before the distance sort. The sort establishes per-target
processing order only for the already-retained subset. The repeated query
geometry is consistent with a forward cone/wedge but exact width, length,
spacing, boundary inclusivity, and traversal order are not fully decoded from
the caller. Do not implement an arbitrary nearest-neighbor policy from the
sort alone.

The callback and shared query builder apply native filtering, but this pass
has not tied each numeric condition to ground/air, alliance, structure,
immunity, life, hidden, or invulnerability semantics. Authored TFT
`ANfl` target mask is air/ground/enemy/neutral/organic; that is configuration,
not proof that every listed bit is tested by this callback.

## Per-target dispatch and action/event path

The `+0xA4` call is now resolved by exact-build static receiver analysis (not
by archived runtime tracing):

1. `0x00C788F0` / RVA `0x008788F0` calls `0x00C787F0` / RVA `0x008787F0`
   with FOURCC `MNfl`. That lookup resolves the registered missile-class
   descriptor and stores its constructed object in `local_14`; the worker then
   invokes `(*local_14->vtable + 0xA4)` at callsite VA `0x00C7894E` / RVA
   `0x0087894E` (see Ghidra export `ANfl-dispatch-damage-followup-17`).
2. The TFT class registry identifies `MNfl` as
   `CMissileForkedLightning`; the class factory at RVA `0x008790C0` writes
   vtable VA `0x00FAF6BC`. The pointer table at that exact address has a
   function entry at slot `+0xA4`: VA `0x00C781D0`, RVA `0x008781D0`.
   Together, the worker lookup, registered class/factory, constructor table
   assignment, and executable slot value establish a verified static
   receiver/vtable relationship. No archived Frida capture observed the
   receiver pointer or dynamic target, so this is not runtime-observed
   dispatch.
3. `0x008781D0` accepts the per-target context produced by the worker. It
   initializes the object's handle field at `this+0x78` (word index `0x1e`),
   calls `0x002E4840`, then selects `0x0006E210` or `0x0006E3E0` based on
   whether the context's second pointer is null. The selected helper performs
   virtual target/state checks and calls VA `0x00703220` (RVA `0x00303220`)
   with context values.
4. `0x00303220` directly calls VA `0x006FC9D0` (RVA `0x002FC9D0`). That
   routine resolves the supplied string/configuration key, reads the selected
   record fields at `+0x20` through `+0x34`, and calls VA `0x00703150` (RVA
   `0x00303150`). The latter initializes generic action-list state and calls
   VA `0x00977880` (RVA `0x00577880`) to append/populate an action record.
   These are direct static calls. The record is now identified as a
   `CVLightning` presentation object, not evidence of a gameplay damage action.
   `0x00577880` allocates an `0x8c`-byte record (the allocator metadata at
   `DAT_00E68B80` is unnamed here) and initializes it via `0x00577610`. The
   record writer receives its container as its `this` argument. Separately,
   the shared context returned by `0x00307650` has a `+0x34` list that is read
   by `0x002FE390`; that routine calls `0x00578630`, whose loop checks an
   active-entry word and calls `0x00577FC0` to generate lightning geometry and
   submit it through renderer helpers. The element type and record layout are
   consistent with this renderer path, but the available decompilation does
   not prove that the writer's container argument is exactly the context's
   `+0x34` list. Treat this as the leading presentation-consumer candidate,
   not a fully proven storage edge. It does not identify a damage action.
5. `0x008781D0` stores the returned handle in `this+0x78`, invokes vtable
   `+0x9C` when the handle is not `-1`, schedules event `0xD01D3` through
   `0x003FBE90`, calls `0x002BFFB0`, then invokes vtable `+0x84`. The same
   missile vtable maps `+0x0C` to event handler `0x00878390`; for event IDs
   `0xD01A0` and `0xD01D3`, it invokes `+0xA0`, releases the handle through
   `0x003051A0`, clears the field, invokes `+0x5C` (VA `0x007F2180`, RVA
   `0x003F2180`), and returns handled. This proves a statically wired handle
   and event lifecycle for the missile class, but not the event's gameplay
   meaning or which branch represents cast completion/interruption.

The relevant vtable values are exported in
`build-re/ability-re/ghidra/ANfl-missile-vtable-full-11/vtables.jsonl`; the
worker, method and event-handler decompilations are in
`build-re/ability-re/ghidra/ANfl-dispatch-damage-followup-17/`. Calls to
`0x002A9940` (damage-payload initializer) and `0x002677C0` (shared CUnit
damage receiver) are not present in the resolved ANfl/missile path. A targeted
exact-build caller triage (`ANfl-damage-caller-triage-24/`) confirms that the
initializer has many direct callers, but none is in the ANfl functions. The
shared CUnit receiver is reached through the target's virtual `+0x120` damage
dispatch, so its lack of direct callers in the global callsite export is
expected. This does not prove ANfl never reaches it through an indirect damage
dispatch. The missile vtable follow-up (`ANfl-damage-vtable-followup-25/`)
confirms the known methods and slots, but reveals no separately named direct
damage operation in `0x008781D0`, `0x00878170`, `0x008782A0`, `0x00878330`, or
`0x00878390`. The independent gameplay-damage callback therefore remains
unlocated; the last proven ANfl gameplay-side point is candidate dispatch into
`0x008788F0` and its per-target missile method. The lightning record is
presentation data and is not evidence of a damage action.

### Configured record layout and consumer

Targeted exports are in
`build-re/ability-re/ghidra/ANfl-action-consumer-followup-19/`,
`ANfl-action-consumer-followup-20/`,
`ANfl-action-lifecycle-followup-21/`,
`ANfl-lightning-render-consumer-22/`, and
`ANfl-lightning-manager-followup-23/`. They use the pinned executable and
cached Ghidra project; no full analysis was run.

`0x00577880` is a record/list writer, not an action interpreter. It updates the
container at its first argument, allocating a record of size `0x8c` when
needed. Its constructor `0x00577610` zeroes fields and sets defaults. The
adjacent pointer-vector resize helper `0x00577EC0` uses the allocator type
label `PAVCLightning`; the allocator metadata passed for the individual
`0x8c`-byte records is not independently named. The following field
assignments and consumers are directly visible:

| Offset | Stored value or observed use | Evidence and interpretation |
|---|---|---|
| `+0x00..+0x08` | First 12-byte endpoint copied from argument 2 | `0x00577880`; its identity is inherited from upstream context and is not named by the record writer. |
| `+0x0C..+0x14` | Second 12-byte endpoint copied from argument 3 | Same evidence; exact source/target identity is not assigned here. |
| `+0x18`, `+0x1C` | Scalar arguments 4 and 5 | Copied directly. `+0x1C` is used by `0x00577FC0` to expand geometry on both sides of each segment; a visual width-like interpretation is supported. |
| `+0x20` | Constant `0x16` | Set by `0x00577880`; no semantic enum name is established. |
| `+0x24` | Local flag value | Written from configuration/local state; exact meaning unresolved. |
| `+0x28`, `+0x2C` | Local/configuration values | `+0x2C` receives a queried value from the reference at `+0x80`; meanings unresolved. |
| `+0x30..+0x34` | Configuration pair; high word includes constant `3` | Written by the builder; representation unresolved. |
| `+0x38..+0x44` | Arguments 6 through 9 | Four words copied. Renderer uses byte `+0x3B` in color setup and reads the word at `+0x38` as render state; other meanings unresolved. |
| `+0x48` | Set to `1` | Initialization/validity-like value; semantic label unresolved. |
| `+0x4C` | Read as a loop bound by `0x00577FC0` | Count-like use over point data is proven; exact units unresolved. |
| `+0x50` | Read as point/path-data pointer | The renderer reads points through this pointer; ownership/allocation is outside this trace. |
| `+0x5C` | Read as generated geometry buffer | Geometry is written here and submitted to renderer helper `0x007D0E90`. |
| `+0x74`, `+0x7C` | Renderer state values | Read by `0x00577FC0`; exact semantics unresolved. |
| `+0x80` | Reference-counted object from argument 10 | Previous reference released; new reference stored and queried through `0x00972730`. Exact class/meaning unresolved. |
| `+0x84` | Optional callback pointer | `0x00577FC0` invokes it with stored endpoint values before rebuilding geometry; callback identity/registration unresolved. |

The established construction path and separate consumer candidate are:

```text
0x008781D0
  → 0x0006E210 / 0x0006E3E0 (endpoint/context setup)
  → 0x00303220 → 0x002FC9D0 → 0x00303150 → 0x00577880
  → container argument (identity not fully resolved)

shared context +0x34 list
  → 0x002FE390 → 0x00578630 (active-entry iteration)
  → 0x00577FC0 (lightning geometry and renderer submission)
```

Builder calls and renderer-loop calls are direct within their respective
paths. `0x00303150` initializes the shared context's `+0x34` list and then
calls `0x00577880`, but the call's first argument is not proven to alias that
list by the available ABI/data-flow export. The `PAVCLightning` vector label,
record size/layout and `0x00577FC0` field accesses make a renderer consumer
the strongest explanation, while the exact list-identity edge remains a
candidate. `0x00578630` checks a parallel active word before calling the
renderer. `0x00577FC0` optionally calls the record callback, builds segment
geometry from point data and the width-like field, then invokes renderer
helpers. None of these functions applies unit damage.

Missile event `0xD01D3` retains a statically established cleanup path:
`0x00878390` invokes missile callbacks, releases the handle at `this+0x78`
through `0x003051A0`, and clears that field. The handle lifetime is associated
with the missile, but the event's gameplay meaning is unproven. The renderer
record's removal/active-flag writer is not yet uniquely connected to this
missile callback or to the ANfl record's container argument.

## Damage path

Stock TFT data has rank damage values DataA `85`, `160`, and `250`; DataB is
`3` at all ranks. The archived multiple-target JASS capture records three
enemy targets at 210 health before the effect and approximately 125 health at
the `0.75s` sample. This is consistent with 85 damage per target. The same
capture records a 110-mana reduction by that sample, and later health changes
are contaminated by target movement, attacks, regeneration, and other map
activity.

The worker's virtual call is no longer unresolved: it reaches the missile
method described above. The generic record branch resolves to lightning
presentation. A targeted static caller triage found no direct ANfl call to
payload initializer RVA `0x002A9940`; the CUnit receiver RVA `0x002677C0` is
normally reached through a virtual `+0x120` damage dispatch and cannot be
located by direct call references alone. Inspection of all currently mapped
Forked Lightning missile methods found no verified damage-payload construction
or target damage call. Thus the archived health delta still cannot be causally
connected to a native ANfl callback or to the shared receiver. DataA's native
lookup, attack/damage type, mitigation path, immunity behavior, per-target
calculation, and exact damage commit callback remain unresolved.
The shared damage receiver contract is documented in [combat evidence](ability-probes/combat.md#damage-payload-and-receiver-path-retail-1292),
but ANfl's call edge to it has not been found.

## Timing, effect state, and cleanup

The archived JASS trace samples every 0.25 seconds. For the multiple-target
case, spell-effect was observed at sample tick 2 (`0.50s`); at tick 3 (`0.75s`)
the caster's mana had fallen from 330 to about 220 and all three target health
samples had fallen by about 85. Finish and endcast were recorded at tick 4
(`1.00s`). This brackets visible JASS state transitions but does not prove the
three native damage operations were simultaneous or identify cast-point timing.
The archived native trace observed the order getter and `0x00C78A50`, not the
later worker, effect methods, or damage receiver. The routine decompiles as
`void`; its captured `EAX` is incidental and is not a return-value contract.

The resolved `CMissileForkedLightning` table and its methods establish a
transient-handle/event lifecycle statically. They are associated with the
ANfl per-target path through its `MNfl` lookup and the `+0xA4` dispatch, but
none of these methods was observed in the archived Frida traces:

- `0x00C781D0` configures event data with `0x006E4840`, creates a handle via
  one of `0x0046E3E0` / `0x0046E210` depending on target-data shape, stores it
  at `this+0x78`, invokes virtual `+0x9C` when creation succeeds, schedules
  event `0xD01D3`, updates ability state, then calls virtual `+0x84`.
- `0x00C78390` treats event IDs `0xD01A0` and `0xD01D3` specially: when
  `this+0x78` is populated it invokes virtual `+0xA0`, releases the handle via
  `0x007051A0`, clears the field, invokes virtual `+0x5C`, and reports handled.
  Other IDs go through `0x006E4ED0`, which handles `0xD01A3` through virtual
  `+0x98`.
- The same `CMissileForkedLightning` table also binds `+0x34` to
  `0x00C78170`, `+0x3C` to `0x00C782A0`, and `+0x84` to `0x00C78330`.
  `0x00C78170` contains a related handle release/state-update path;
  `0x00C782A0` delegates an event and clears `this+0x78`; and `0x00C78330`
  performs a separate shared effect/state call through `0x006EB2B0`. The
  `+0x84` method is directly invoked by `0x008781D0` after handle setup.

These are now statically tied to the missile class through its constructor's
vtable assignment. Their branches still do not establish which conditions
mean successful completion, interruption, caster death/removal, target death,
or ability removal. Archived Frida traces did not observe these methods or
their receiver identities at runtime.

Authored presentation resolves `SpecialArt` to
`Abilities\Weapons\Bolt\BoltImpact.mdx`; its Stand sequence is 0–800 ms.
Its EVTS track has a `LightningBolt` sound event at 33 ms, whose authored sound
row resolves to `Abilities\Spells\Orc\LightningBolt\LightningBolt.wav`.
These files and event metadata do not prove runtime creation, sequence choice,
sound playback, lightning primitive creation, attachment, or lifetime. The
native handle create/release path above is not yet connected to this model or
sound. Presentation evidence remains authored/static only.

## Evidence levels and next questions

| Claim | Classification | Remaining evidence |
|---|---|---|
| Factory registration points at the ANfl class factory; that factory installs `CAbilityForkedLightning`'s table | Exact-build static relationship | No runtime receiver identity claim. |
| Order ID `0xD026B`; order string `forkedlightning` | Static getter plus authored data; order path also observed by Frida | None for this build's order identity. |
| Spatial candidate path, two native gates, duplicate prevention, early count cap, and post-cap sort | Exact-build static control flow | Decode every query parameter and target gate to name each gameplay predicate. |
| Three targets each sampled at ~85 loss | Authored-data agreement plus direct archived JASS observations | Identity-stable, stationary targets and a cap-boundary test are needed to resolve which candidates survive enumeration. The existing run does not discriminate target order. |
| `+0xA4` receiver and method | Exact-build static receiver lookup, factory/vtable assignment and slot target; not runtime-observed | A bounded Frida trace can independently confirm receiver/vtable/target if runtime confirmation is required. It will not by itself identify damage semantics. |
| DataA rank mapping and damage implementation | Authored data plus compatible live delta; resolved method begins presentation-handle/event setup | The mapped missile methods contain no verified damage call. Next resolve the callback behind the ability effect/per-target context, then trace its indirect `+0x120`-style damage dispatch. A focused Retail trace is warranted once static callback candidates are narrowed. |
| Mana/cast timing | Direct JASS samples, 250ms resolution | Finer timing only if exact ordering matters after static path inspection. |
| Effect/sound lifecycle | Authored model metadata plus candidate transient-handle code | Prove callback/receiver association, resolve data-to-model mapping; visible/audio confirmation only if static linkage remains ambiguous. |
| Interrupt/removal/target-death cleanup | Static branches have handle cleanup | Identify callback ownership and branch conditions; use focused runtime probes only for unresolved lifecycle events. |

No new Retail launch was needed for this static follow-up. Existing captures
remain unchanged and are reused from `ANfl-live-session-06/` and
`ANfl-live-session-07/`.

## Focused damage-path follow-up

For this follow-up, the cached Ghidra project and pinned executable identity were
reused; no full analysis or Retail launch was performed. Targeted exports are
`build-re/ability-re/ghidra/ANfl-damage-caller-triage-24/` and
`ANfl-damage-vtable-followup-25/`. The former examined selected direct callers of
`0x002A9940` and the initializer itself. Its callers demonstrate generic
damage-event construction patterns, including `0x000AEF70` for the JASS
`UnitDamageTarget` bridge, but none establish an ANfl edge. The initializer
writes an eight-word payload from its arguments; it does not itself apply
damage. The latter export revalidated missile slots and the mapped lifecycle
methods.

The most useful structural clue is the shared combat contract already
documented in [combat probes](ability-probes/combat.md#damage-payload-and-receiver-path-retail-1292):
CUnit damage is dispatched through virtual slot `+0x120` with a payload. No
Forked Lightning callback currently provides a proven callsite to that slot,
and no verified damage amount/data flow from ANfl DataA has been recovered.
The per-target worker's `+0xA4` missile call remains the last proven ability
edge; the concrete function `0x008781D0` creates presentation/configuration
state and schedules event `0xD01D3`, while its event handler clears/releases
the transient handle. Existing samples bracket health changes after the JASS
spell-effect sample, but are too coarse to identify the native invocation.

The lightning-container alias also remains unresolved. Existing Ghidra
decompilation establishes a writer call from `0x00303150` to `0x00577880` and
a separate renderer loop over the global context's `+0x34` list. It does not
establish that the first argument at the writer call equals the address of
that list. No pointer identity is promoted from matching element shape or
allocator label.
