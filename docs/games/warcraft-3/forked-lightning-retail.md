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
   These are direct static calls, but the string key and action record's
   gameplay meaning are not yet mapped to a damage operation.
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
damage receiver) were not found on this resolved path. The method currently
reaches a generic action/event record, whose interpretation and later callback
are not established.

## Damage path

Stock TFT data has rank damage values DataA `85`, `160`, and `250`; DataB is
`3` at all ranks. The archived multiple-target JASS capture records three
enemy targets at 210 health before the effect and approximately 125 health at
the `0.75s` sample. This is consistent with 85 damage per target. The same
capture records a 110-mana reduction by that sample, and later health changes
are contaminated by target movement, attacks, regeneration, and other map
activity.

The worker's virtual call is no longer unresolved: it reaches the missile
method described above. However, that method currently leads only to a
data-driven action/event record and a scheduled callback. Neither the
ability-specific path nor the exported generic action builder has yet been
followed to the shared damage payload initializer `0x006A9940` or CUnit
receiver `0x006677C0`. Consequently, the archived health delta cannot yet be
causally connected to the generic damage receiver. DataA's native lookup,
attack/damage type, mitigation path, immunity behavior, per-target calculation,
and exact damage commit callback remain unresolved. The shared damage receiver
contract is documented in [combat evidence](ability-probes/combat.md#damage-payload-and-receiver-path-retail-1292),
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
| DataA rank mapping and damage implementation | Authored data plus compatible live delta; resolved method begins generic action/event setup | Follow the action-record consumer and event callback to a verified damage call site; only then decide whether a live run is needed. |
| Mana/cast timing | Direct JASS samples, 250ms resolution | Finer timing only if exact ordering matters after static path inspection. |
| Effect/sound lifecycle | Authored model metadata plus candidate transient-handle code | Prove callback/receiver association, resolve data-to-model mapping; visible/audio confirmation only if static linkage remains ambiguous. |
| Interrupt/removal/target-death cleanup | Static branches have handle cleanup | Identify callback ownership and branch conditions; use focused runtime probes only for unresolved lifecycle events. |

No new Retail launch was needed for this static follow-up. Existing captures
remain unchanged and are reused from `ANfl-live-session-06/` and
`ANfl-live-session-07/`.
