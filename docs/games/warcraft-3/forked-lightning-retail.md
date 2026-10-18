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
| `0x00C78FC0` / `0x00878FC0` | Callback supplied to `0x0068EA00` | Candidate gates, deduplication and candidate append; normal-order cap is applied by the caller after sorting. Runtime callback returns were captured in the new cases. |
| `0x00C78F60` / `0x00878F60` | Comparator passed to sort helper `0x00AB2000` | Compares a stored float metric; ties compare the integer at candidate `+0x0C`. The meaning of that integer field is not established. |
| `0x00C788F0` / `0x008788F0` | Directly called for each selected candidate | Loads rank DataA into the per-target context, resolves the `MNfl` missile class object, and dispatches through its vtable at `+0xA4`; the runtime callback path proceeds to shared damage helper `0x002EB2B0`. |

## Target acquisition and selection

The statically recovered path in `0x00C78A50` is:

1. Read the owning unit from ability field `+0x30`; read positions through unit
   virtual slot `+0xB8` for the owner and the order target.
2. Read rank-indexed ability data from the object at ability `+0x50`. Accessor
   `0x0046EE20` reads the active row's dword at `+0x24`; `0x00878A50`
   converts it with `0x009A07B0` into `local_124`. The caller later uses that
   value as the maximum number of workers. The row layout and authored
   `AbilityData.slk` identify `+0x24` as DataB. Accessor `0x0046ED70` reads
   row `+0x20` (DataA); the per-target worker loads that value into its
   temporary missile context. Runtime rank-one and rank-two casts observed
   payload `+0x10` as 85 and 160 respectively, proving this authored DataA
   mapping for those ranks. The rank-three value 250 remains authored/static
   only.
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
5. In the accepted order path, `0x00C78090` calls acquisition with mode
   `param_3=0`. In this mode callback `0x00C78FC0` records accepted unique
   candidates and returns true; its mode-dependent cap return is used only
   when `param_3` is nonzero. The acquisition loop continues its repeated
   spatial queries until its geometric termination condition. Runtime Frida
   observed 12 callback entries per cast across the overlapping queries, five
   distinct candidate pointers, and return value 1 for all 12 entries in each
   of three casts. The duplicate candidate pointers show that the query
   regions overlap and the callback deduplicates across them.
6. After query enumeration, normal mode sorts the collected records when the
   count exceeds one. The comparator orders by the stored floating-point
   metric and uses the record integer at `+0x0C` for ties. The caller then
   computes `min(candidate_count, local_124)` and invokes `0x00C788F0` only
   for that prefix. Thus the accepted Retail path sorts the complete unique
   candidate set before applying the DataB worker limit. The other mode
   (`param_3 != 0`) has separate early-stop behavior and does not run the
   normal sort/worker loop; its lifecycle caller remains unresolved.

The accepted-order path is a nearest-first selection among candidates
enumerated by the repeated forward spatial queries, subject to the callback
filters and comparator tie-break. It is not a global search over every map
unit: only units delivered by those queries can enter the sorted set. The
exact query radius, forward spacing, boundary inclusivity, shared spatial
traversal order, and all comparator tie cases are not fully decoded. The
runtime callback order is recorded, but because the five test units were
relocated by pathing at creation, the reverse-creation experiment does not
isolate creation order from actual position changes.

The callback and shared query builder apply native filtering, but this pass
has not tied each numeric condition to ground/air, alliance, structure,
immunity, life, hidden, or invulnerability semantics. Authored TFT
`ANfl` target mask is air/ground/enemy/neutral/organic; that is configuration,
not proof that every listed bit is tested by this callback.

### Rank-two and five-target runtime follow-up

Fresh evidence is under `build-re/ability-re/ANfl-targeting-rank2-01/`.
The prepared map and executable hashes are pinned in `prepared/launch.json`;
the control-map bytes match the earlier visually confirmed control map. One
new Warcraft process was launched at 640×480 after advancing the campaign
intro to the gameplay HUD. A bounded read-only Frida agent hooked the candidate
callback, ANfl acquisition/worker, missile method/callback, damage helper,
payload initializer and CUnit receiver. The three JASS files are copied into
the session directory and preserve full 250 ms sampling output.

| Case | Rank | Targets | Unique callback pointers | Workers / damage calls | Payload | JASS targets losing life by effect sample |
|---|---:|---:|---:|---:|---:|---|
| `anfl-r2-five-a` | 2 | 5 | 5 | 3 / 3 | 160 each | 0, 1, 3; 210 → 50.002 |
| `anfl-r1-five-a` | 1 | 5 | 5 | 3 / 3 | 85 each | 0, 1, 3; 210 → 125.000 |
| `anfl-r1-five-reverse` | 1 | 5 | 5 | 3 / 3 | 85 each | 0, 3, 4; 210 → 125.001 |

Each case produced 12 callback invocations across repeated queries, with
return value 1 on every callback; five distinct pointers were seen per cast.
The worker target pointer equaled each corresponding damage receiver `ECX`.
All nine damage receiver calls came from return address `0x006EB5F9` (RVA
`0x002EB5F9`), used vtable `0x00E9C504`, and carried the corresponding caster
pointer at payload `+0x00`. This establishes the rank-to-payload values and
the three-worker cap for both tested ranks. JASS health changes identify the
three affected scenario units as a set; the native callback records do not yet
provide a pointer-to-individual-JASS-handle mapping for all five units.

The reverse-creation case changed actual initial positions because placement
resolved collisions differently (for example, secondary units spawned at
different snapped coordinates). Its changed selected set therefore cannot
attribute the difference to creation order alone. This is consistent with a
position-ranked retained prefix, but the exact candidate-to-JASS mapping and
spatial traversal implementation remain open.

## Per-target dispatch and action/event path

The `+0xA4` call is resolved by exact-build static receiver analysis and was
also observed in the new rank/target runtime traces:

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
   receiver/vtable relationship. New Frida captures observed three worker
   target pointers entering this concrete method in each accepted cast.
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
damage receiver) are reached indirectly. The live trace and targeted static
caller export below now establish a path through `0x00878330` to
`0x006EB2B0`, which constructs the payload and dispatches through the target's
virtual `+0x120`. The CUnit receiver is `0x006677C0`; its lack of direct
callers in the global callsite export is expected because the dispatch is
virtual. The lightning record remains presentation data and is a separate
path from the now-observed damage dispatch.

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
`3` at all ranks. Exact-build accessor `0x0046ED70` reads the active row at
`+0x20` (DataA), and the worker puts that result in the per-target context
before missile dispatch. Accessor `0x0046EE20` reads row `+0x24` (DataB),
which acquisition converts to the worker-count bound. Three new accepted
Retail cases observed payload amounts 160 at rank two and 85 at rank one;
each dispatched three receiver calls. Five-target JASS cases observed three
targets losing the rank-matching amount by the 0.75-second sample. The exact
native-pointer-to-each-JASS-handle map remains incomplete.

The worker's virtual call is no longer unresolved: it reaches the missile
method described above. The generic record branch resolves to lightning
presentation. A targeted static caller triage found no direct ANfl call to
payload initializer RVA `0x002A9940`; the CUnit receiver RVA `0x002677C0` is
reached through virtual `+0x120`. A fresh Retail trace now observes that edge
from affected targets during accepted rank-one and rank-two casts. Payload
category/type interpretation, full mitigation behavior, and behavior for
other target classes and rank three remain open. The shared receiver
contract is documented in [combat evidence](ability-probes/combat.md#damage-payload-and-receiver-path-retail-1292).

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
| Candidate filtering, repeated query deduplication, full-set sort, then DataB-bounded worker prefix | Exact-build static control flow; corroborated by three live casts with five distinct callback pointers and three workers each | Decode every query parameter and target gate to name each gameplay predicate; isolate creation-order effects from placement. |
| Rank-one and rank-two amounts | Runtime payload floats 85 and 160; static row accessors read DataA; JASS samples show matching losses on five-target tests | Rank three and other target defenses remain untested; raw amount can differ from life delta after mitigation. |
| Shared receiver and selected targets | Runtime worker target equals receiver ECX for all nine damage calls; three of five JASS targets lose the rank-matching amount per case | Native-pointer-to-individual-JASS-handle mapping remains incomplete for all five candidate pointers. |
| DataB target limit | Static DataB row accessor and post-sort `min(candidate_count, DataB)` worker bound; live cases produced three workers at ranks 1 and 2 | DataB is 3 at all authored ranks, so rank-varying limit behavior is not tested. |
| Mana/cast timing | Direct JASS samples, 250ms resolution | Finer timing only if exact ordering matters after static path inspection. |
| Effect/sound lifecycle | Authored model metadata plus candidate transient-handle code | Prove callback/receiver association, resolve data-to-model mapping; visible/audio confirmation only if static linkage remains ambiguous. |
| Interrupt/removal/target-death cleanup | Static branches have handle cleanup | Identify callback ownership and branch conditions; use focused runtime probes only for unresolved lifecycle events. |

For the preceding damage-path follow-up, no new Warcraft process was launched;
that session reused its already-running prepared probe process. The current
rank/target follow-up below launched one prepared-map process. Captures from
`ANfl-live-session-06/` and `ANfl-live-session-07/` remain preserved.

## Focused damage-path follow-up

The cached exact-build Ghidra project was reused read-only; no full analysis
was run. A single targeted detail export,
`build-re/ability-re/ghidra/ANfl-observed-damage-caller-26/`, decompiled the
actual observed caller at RVA `0x002EB2B0`.

### Live accepted/control trace

The evidence is in
`build-re/ability-re/ANfl-damage-execution-01/`: `jass-valid-01.txt` and
`jass-valid-02.txt` are two completed accepted rank-one runs;
`jass-reject-01.txt` is the completed expected-rejection control
(`accepted=false`). Both Frida traces are complete and have `trace-end` with no
errors. The first trace covers the accepted and rejected cases in one
90-second window; the second accepted run adds the focused callback and helper
hooks. The prepared Retail process was reused, and all captures are separate
from the prior Oct 17 outputs.

In the first accepted run, JASS reports the sole Player 12 `hfoo` target at
`(-880,-6084)`, life `210` at tick 0 and `125.001` at tick 3 (0.75 s), with
spell-effect sampled at tick 2 (0.50 s). Frida records one ANfl acquisition
and one target-worker invocation. The worker's target argument equals the
receiver's `ECX`; the receiver uses CUnit vtable `0x00E9C504`. The matching
receiver call's payload source pointer equals the ability owner's verified
`this+0x30` pointer. This identifies the native target and source without
assuming JASS handle IDs are native pointers.

The focused second accepted run reproduces the same path and values. In one
thread, Frida records these entries 5 ms apart: ANfl acquisition at
`0x00C78A50`; target worker at `0x00C788F0`; its virtual `+0xA4` missile method
at `0x00C781D0`; missile `+0x84` callback `0x00C78330`; helper
`0x006EB2B0`; then the target's virtual `+0x120` call into `0x006677C0`.
Payload initialization at `0x006A9940` occurs inside the helper. The actual
receiver return address is VA `0x006EB5F9` (RVA `0x002EB5F9`).

The expected-rejection control has `accepted=false`, no spell-effect event,
and no additional ANfl acquisition/worker entry in the shared trace. Generic
receiver traffic continues during the window, so the other receiver entries
are not attributed to Forked Lightning. There is exactly one accepted-cast
receiver call with the worker's target pointer and amount `85` per capture;
the initial and later background calls carry different amounts/callers.

### Observed helper and payload

The observed receiver callsite is VA `0x006EB5F3`, instruction `call
[eax+0x120]`, inside helper `0x006EB2B0`. Its decompilation at
`build-re/ability-re/ghidra/ANfl-observed-damage-caller-26/decompiled.jsonl`
shows it constructs `WidgetDamageData` with `0x006A9940`, then dispatches
through the target's `+0x120` slot. The exact callsite RVA is `0x002EB5F3`;
the return address recorded by Frida is five bytes later at `0x002EB5F9`.

The runtime words for the rank-one payload are:

| Offset | Raw value | Supported reading |
|---:|---:|---|
| `+0x00` | target-independent pointer, equal to ability owner `0x00FF9D6AC` in the focused run | Source CUnit; verified by receiver behavior and equality to ability `+0x30`. |
| `+0x04` | `0` | Meaning unresolved. |
| `+0x08` | `0` | Meaning unresolved. |
| `+0x0C` | `1` | Receiver flags word; flag semantics unresolved. |
| `+0x10` | rank 1: float `85` (`0x42AA0000`); rank 2: float `160` (`0x43200000`) | Raw amount supplied to receiver; static row accessor and worker context map these tested values to DataA. Rank three is untested. |
| `+0x14` | `0x400` | Category/type field candidate; semantic mapping unresolved. |
| `+0x18` | `0` | Initializer's global value. |
| `+0x1C` | `0` | Zeroed by initializer. |
| `+0x20` | `0` | Receiver selector word; semantic mapping unresolved. |

The initializer entry recorded raw stack words
`[0x12F58C, 0x400, source, 1, 0]`; its instructions dereference the first
pointer into payload `+0x10` and place the remaining words at their verified
offsets. The receiver's output pointer is a separate writable float pointer.
Its successful branch applies resistance/bonus handling and calls target
virtual `+0x128` (`0x00668DB0`) with a negative adjusted amount. The JASS
sampled life change from 210 to about 125 supports 85 actual loss on this
single `hfoo`; later life samples include unrelated damage and are not used to
infer the spell amount. Damage type label, attack type, armor multiplier,
immunity branches for other targets, and the exact post-mitigation commit
value remain open.

### Receiver ABI (static contract, live arguments observed)

The shared receiver contract is now specified in
[combat probes](ability-probes/combat.md#receiver-abi-and-payload-fields).
VA `0x006677C0` / RVA `0x002677C0` is an x86 `__thiscall`: target CUnit in
`ECX`, writable `float *` result at stack argument 1, `WidgetDamageData *` at
stack argument 2, then two scalar stack arguments; it returns with `ret 0x10`.
The payload amount is `+0x10`; runtime observations confirm `85`. The output
pointer contains receiver output, not an input parameter. At the trace entry,
Frida safely read the 36-byte payload from validated readable memory and
recorded raw words, receiver vtable, caller, and argument pointers. No return
value was interpreted for the receiver because it decompiles as `void`.

### `mdxtool` fixture discrepancy check

The isolated `test_wc3_re_mdx_events.py` fixture passed (1 test). It generated
a two-event synthetic MDX in a temporary directory, packed it with
`build/bin/mpqtool`, and read it through `build/bin/mdxtool --info-json`; no
external Warcraft asset was required. `build/bin/mdxtool` was present with
SHA-256 `14e87eacb198218a480838a2850e396de9ae55c5d4c9d1926e5ebaaefa762b1a`.
The full `python3 -m unittest discover -s tests -p 'test_wc3_re_*.py' -v`
run also passed all 176 tests, and `make test TEST_JOBS=4` passed. The prior
reported single failure did not reproduce, so no production or fixture change
is justified from the available evidence. The original failing test name and
stdout/stderr were not present in the checkout and remain necessary to explain
that historical discrepancy conclusively.

The lightning-container alias also remains unresolved. Existing Ghidra
decompilation establishes a writer call from `0x00303150` to `0x00577880` and
a separate renderer loop over the global context's `+0x34` list. It does not
establish that the first argument at the writer call equals the address of
that list. No pointer identity is promoted from matching element shape or
allocator label.
