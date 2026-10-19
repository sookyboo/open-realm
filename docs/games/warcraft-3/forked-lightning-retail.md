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

The rank-two single-case capture and the October 18 validator/readback
follow-up are summarized in the implementation specification and
`build-re/ability-re/ANfl-invulnerability-readback-01/results/followup-comparison.json`.
Rank-two geometry now has a runtime trace; `p+Area` matches and the original
`p+DataD/4` prediction remains archived as a failed hypothesis. The Amim
candidate's `+0x264/+0x268` values differ from the normal candidate, but the
selector and virtual returns were not measured reliably. The reversible
October 19 probe now correlates setter/getter state with a resolved CUnit bit
and independent ordinary-damage prevention. A fresh active-state ANfl cast
did not select the treated target, but did not trace its callback path; the
older case-three callback observation remains uncorrelated to an independently
confirmed state. The precise ANfl exclusion stage and discrepancy remain
unresolved.

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
   payload `+0x10` as 85, 160, and 250 respectively, confirming the authored
   DataA mapping at all three ranks.
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

The query-level relation filter is now identified separately from those
callback gates. `0x0028EA00` parses ANfl's `0x1D` clause and installs
`0x00696BE0`. That predicate calls `0x006ADB90` before the ANfl callback;
`0x006ADA20` then delegates owner/relation decisions to `0x006AD670`. The
ANfl mask `0x04010006` expands to `0xF5D10006`. In `0x006AD670`, candidate and
source owner indices that match produce rejection `0x84` unless mask bit
`0x2000` is set. That bit is clear in ANfl's normalized mask. The historical
same-owner Player 0 Footman did not reach the callback, consistent with this
exact static branch. The corrected runtime trace did not capture the
candidate-specific return, so the branch's `0x84` value remains verified
static rather than verified runtime.

### Target-selection detail follow-up (exact-build static)

Focused exports were added under
`build-re/ability-re/ghidra/ANfl-target-selection-detail-02/` and
`ANfl-target-selection-order-detail-03/`. They use the cached
`WC3Retail1292-G21` Ghidra project with `-noanalysis`; no full executable
analysis or Retail launch was performed for this static follow-up. The
executable hash was rechecked against the pinned value. The exports cover the
acquisition/candidate/comparator routines, query builder, shared predicates,
rank-row readers, numeric helpers, and the generic sort helper.

The callback's filtering contract is more specific than the earlier report,
but it still does not provide a complete gameplay-category matrix:

| Stage | Exact-build operation | Supported interpretation | Remaining uncertainty |
|---|---|---|---|
| Relationship/mask gate | `0x00878FC0` calls `0x0067FB80` with caster in `ECX`, candidate stack argument 1, then `0` and `4`. The helper resolves caster owner through virtual `+0xEC`, derives a low mode bit from player 13's record flag, and calls `0x00475150` with shared player context, owner index, candidate, derived mode, and trailing `4,0`. It may run candidate-owner and point-based relation checks; on helper failure, it tests candidate `+0x250/+0x254` against the owner bit. | The branch and bit flow are verified, including fallback through either candidate mask. | The flags/masks, raw `4` mode, and branch-to-enemy/ally/neutral mapping are not established by controlled category tests. |
| Shared target validator | On passing the first gate, the callback calls candidate virtual `+0x350`, then `0x00682180`; zero is required to continue. `0x00682180` first runs `0x00682210` and `0x006822E0`, then scans its linked validator registry and returns the first nonzero result. | A zero result means no rejection code was returned by these paths. Nonzero is a rejection result for this ANfl callback, not an acceptance boolean. | The dynamic `+0x350` contract and live registry membership for each tested candidate are not resolved. |
| Built-in rejection paths | In the call from `0x00682180`, `0x00682210` receives the candidate CUnit, the source ability's `+0x350` return, and the source ability object. It returns `0x36` only for the exact conjunction recorded below. `0x006822E0` is a separate built-in predicate returning `0xBC` under its own conditions. | `0x36` originates at VA `0x006822CE` in the built-in predicate, before the registered-validator walk. Candidate `+0x164`, `+0x264`, and `+0x268` fields belong to the candidate CUnit. A matched instruction-local normal/Amim trace identifies the selected field and final `+0x20C` branch. | Virtual-slot meanings and field writers remain unresolved. Do not name `0x36` as a universal immunity rule from the code or correlated treatment alone. |
| Deduplication | After both gates pass, the callback compares the candidate pointer for equality against every already-recorded candidate pointer. | Exact pointer duplicates from overlapping queries do not append a second record. | No identity aliasing beyond pointer equality was tested. |
| Candidate continuation result | Rejected candidates and duplicates return true. In normal accepted-order mode, a newly appended candidate also returns true. The alternate mode returns whether the current count is still below its limit. | The callback result is query continuation control, not candidate eligibility. Normal mode therefore continues enumeration after each rejection, duplicate, or append. | Gate return values were directly captured for five candidates in the follow-up case only; category meanings remain unresolved. |

The `0x36` result has one built-in static origin: `0x00682210` returns it at
VA `0x006822CE`, before the registered-validator walk. The call frame passes
the candidate CUnit, the source ability's `+0x350` result, and the source
ability object. The exact conjunction is:

```text
a.vfunc(+0xD8) == 0
(u.raw[+0x164] & 0x100) == 0
field = a.vfunc(+0x1F0) != 0 ? u.signed[+0x268] : u.signed[+0x264]
field > 0
(a.vfunc(+0x1D8) != 0 || a.vfunc(+0x1F8) != 0)
a.vfunc(+0x1FC) == 0 || candidate_predicate(u, a[+0x30] ?? resolve(a)) == 0
GetConfigInt("Misc", "MagicImmunesResistUltimates", 0) == 0
a.vfunc(+0x20C) == 0
```

The earlier written sign on the last term was incorrect. At VA `0x006822C3`,
the zero test branches to the `0x36` return at `0x006822CE`. In the matched
same-cast capture `ANfl-validator-operands-postcall-07/`, ordinary candidate
CUnit `0x0fb559ec` had `+0x164=0x244`, `+0x264=0`, `+0x268=0`; source ability
`0x03067580` returned `+0xD8=0`, `+0x1F0=0` selecting `+0x264`, and the
validator returned zero after the early `jle` at `0x0068225B`. Amim-associated
candidate `0x0fb55f08` had `+0x164=0x245`, `+0x264=1`, `+0x268=1`; source
returns were `+0xD8=0`, `+0x1F0=0`, `+0x1D8=1`, `+0x1FC=0`, config value
zero, and `+0x20C=0`, reaching `0x36`. Candidate predicate and `+0x1F8` were
short-circuited. Stalker did not sample EFLAGS, so path interpretation uses
executed sites, returns, and exact-build disassembly. Case 07's map auto-ran
case 2 although the original manifest described case 1; this is called out in
its comparison JSON. The run summary also records that candidate-to-JASS
handle correlation is not direct. The `postcall-05` no-instruction trace was
caused by 50 Stalker iterator-exhaustion errors and embeds run ID `postcall-04`.
The selected candidate field is now the first observed runtime divergence, but
the fields' meanings and actual CUnit writer remain unresolved.

Here `u` is candidate CUnit and `a` is the source ability object. The other
built-in predicate at VA `0x006822E0` returns `0xBC` through a distinct branch.
Runtime Amim level 1 correlates with `0x36`; the matched instruction-local
trace identifies the selected field as the earliest observed divergence and
the zero `+0x20C` return as the final decisive branch. The configured
`MagicImmunesResistUltimates` value is one term in this conjunction; its name
does not prove that it caused the observed return. The matching JASS library
declares `BlzIsUnitInvulnerable` at
`data/maps/War3xLocal/Scripts/common.j:2529`; the earlier invulnerability
case did not read it back, so state confirmation remains pending. See
`build-re/ability-re/ANfl-validator-36-static-01/validator-36-analysis.md`.

The exact-build call sequence further constrains the relationship gate without
giving its modes gameplay names. `0x0067FB80` is called with the caster in
`ECX`, candidate as its first stack argument, and raw trailing values `0`
and `4`. It resolves the caster owner through virtual `+0xEC`, derives a low
mode bit from player index 13's record flag `+0x04 & 0x200`, and calls
`0x00475150` with the shared player context, caster owner index, candidate,
that derived mode, and trailing values `4, 0`. The helper consults the
candidate owner's bit in a player relation mask when candidate flag
`+0x164 & 0x01000000` requires it; it can also run a point-based relation
predicate at the candidate's resolved point. If the shared helper returns
false, `0x0067FB80` accepts the candidate only when the caster-owner bit is
present in either candidate dword `+0x250` or `+0x254`. These branches and bit
operations are verified. The flag meanings, point predicate's raw `4` mode,
and which branches correspond to enemy/allied/neutral JASS targets have not
been verified by a controlled category case.

This static trace does **not** prove the requested gameplay outcomes for enemy,
ally, neutral, ground, air, organic, mechanical, structure, dead, hidden,
invulnerable, magic-immune, caster-self, or explicit-primary candidates. The
authored ANfl target configuration names air, ground, enemy, neutral and
organic; those authored flags are not substituted for the native outcomes.
There is no explicit `candidate == caster` or `candidate == primary` special
case in `0x00878FC0`; both can only enter through the query builder and gates.

### Metric, tie handling, and sorted prefix

Candidate records contain a unit pointer and a floating-point metric.
`0x00878FC0` obtains the candidate point through its virtual `+0xB8` method,
converts the point pair with `0x007FCC50`, and calls `0x009A1110` against the
position pair stored at candidate context `+0x0C`. The helper performs the
two-coordinate difference, square, sum, and square-root operations. The
metric is therefore the 2D Euclidean distance from the candidate to the
explicit order target, not distance to the caster or to an individual query
center. This establishes an ascending nearest-to-primary-target comparator
for unequal finite metrics.

Comparator `0x00878F60` calls `0x009A00B0` to calculate `metricA - metricB`,
then returns `+1` for a nonnegative nonzero difference and `-1` for a negative
difference. The small-array path in sorter `0x00AB2000` chooses the comparator
maximum and moves it to the end of the range; for five candidates this
produces ascending primary metric order. When metrics compare equal, the
comparator returns signed 32-bit subtraction `keyB - keyA`, where each key is
the candidate object's dword at `+0x0C`. The selection-sort path therefore
places larger signed key values earlier, subject to 32-bit subtraction
behavior. That dword's semantic identity is unresolved. Equal values compare
as zero and have no stable-order guarantee.

The generic sorter at RVA `0x006B2000` is not stable. For up to eight records
it repeatedly selects a comparator maximum and swaps it with the end of the
remaining range; for larger ranges it uses a partitioning quicksort path.
Consequently, two candidates with equal metric and equal `+0x0C` values have
no stable-order guarantee. Runtime tie behavior, NaN handling, and a unit
pointer-to-JASS-handle map were not captured. The accepted path still sorts
the complete deduplicated set before taking its first `min(count, DataB)`
records. Spatial traversal order can affect only ties or the candidate set
delivered by the repeated queries; it does not preempt the sort for unequal
metrics.

### Query geometry: recovered structure and limits

`0x00878A50` reads the caster and explicit-target positions through their
virtual `+0xB8` accessors. It computes target-minus-caster coordinate deltas,
forms a normalized forward vector, and repeatedly builds query type `0xB`
with a center advanced along that vector. The type-`0xB` parser in
`0x0028EA00` consumes a radius and two center coordinates. The raw query tail
passed by ANfl is `0x1D`, the ability-derived mask word, the caster pointer,
`-1`, and `0x1F`; the meanings of these query flags have not been proven.

The rank-row readers used by acquisition access raw row offsets `+0x18`,
`+0x28`, and `+0x2C` through RVAs `0x0006E900`, `0x0006EED0`, and `0x0006EF80`.
The rank-one lookup values align these with `Area=125`, `DataC=900`, and
`DataD=300`; the endpoint is `L=max(Area+DataD, DataC-(Area+DataD))=475`.
For the recorded rank-one case, the four query radii agree with
`r(p)=Area + p*(DataD-Area)/L`, and successive progress is
`p_next=min(p+r(p),L)`. The initially considered center offset
`p+DataD/4` was falsified by acquisition-time point and query observations.
The corrected model is `caster + normalize(primary-caster)*(p+Area)`. Runtime
query traces for ranks 1, 2, and 3 match that center progression and the radius
formula within captured float precision. Exact center rounding, circle-edge
inclusion, collision extent, and coincident caster/target zero-vector behavior
remain unresolved. The endpoint query is issued before termination.

Coincident caster/target positions pass through the native reciprocal-length
calculation; the exact zero-vector fallback and resulting query centers have
not been verified. No boundary-placement run has been completed. Historical
Frida captures that read floats at `CUnit+0x26C` remain invalid: static
disassembly shows `+0x26C` is the point object returned by virtual `+0xB8`, not
a pair of coordinate floats. Treat those old `candidate_x/candidate_y` JSON
values as invalid. Cases 19 and 21 below observe the engine's existing point
resolver call and correlate its live coordinates with JASS positions. Earlier
JASS observations remain valid for their recorded positions and health, but
they do not supply the missing native candidate identity,
enumeration-order, or boundary measurements.

The detailed implementation-level target-selection specification and exact
unresolved experiment list are retained in
`build-re/ability-re/ANfl-target-selection-semantics-02/specification.md`.

The acquisition's authored-rank inputs are read through row accessors at
`0x0046E900`, `0x0046EED0`, `0x0046EF80`, and `0x0046EE20`; the last is the
DataB worker bound. The acquisition computes a terminal progress value from
three of the first accessors and uses `max(A + D, C - (A + D))` in the current
decompilation, then clamps each next progress step to that endpoint and still
issues the endpoint query. It forms the query center from the normalized
caster-to-primary direction and that progress. The type-`0xB` query builder
stores a radius and center X/Y and dispatches a spatial query. The rank-one
observations corroborate the radius and progress model below; they do not prove
the final candidate boundary comparison. The rank-one values align with
`Area=125`, `DataC=900`, and `DataD=300`, yielding endpoint `L=475`,
`r(p)=Area+p*(DataD-Area)/L`, `p_next=min(p+r(p),L)`, and center progress
`p+Area`. Runtime query traces now verify this model for all three ranks.
Circle-edge inclusion, unit footprint effects, native-point rounding,
zero-vector behavior, and other range clamps remain unresolved.

### Shared damage receiver behavior relevant to ANfl

Static receiver `0x006677C0` confirms that ANfl's observed payload values
enter the general CUnit damage path, but numeric `+0x14 = 0x400` is not yet
mapped to a named JASS damage or attack type. With payload `+0x0C = 1`, the
receiver's early `flags & 0x04` suppression branch is not taken, and the
ordinary damage branch can proceed. The receiver can still return zero damage
before life adjustment due to target state, shared attached callbacks,
damage-type/immunity checks, or later damage adjustment.

The receiver reads payload `+0x20` and `+0x14` while consulting runtime
configuration `MagicImmunesResistDamage`. When that configuration is false,
its built-in classification treats raw type values `0x10`, `0x20`,
`0x04000000`, and `0x00400000` specially; ANfl's observed `0x400` is not one
of those four values, so it enters the other branch. That branch tests target
virtual slot `+0x11C` and target dword `+0x264`; their semantics are not named
here without a verified vtable/data mapping. When the configuration is true,
the receiver calls helpers `0x006B6DB0`, `0x006B6DE0`, `0x006B6E00`, and
`0x006B6E50` with payload selector/type values before choosing those state
checks. A separate branch can also inspect target dword `+0x260`.

After those gates, the receiver performs attached-object callbacks, invokes
damage adjustment helpers, and calls target virtual `+0x128` with the negative
computed amount; it reports the resulting life delta through the output
pointer. Thus raw payload 85 is verified for the controlled baseline, while
damage after mitigation depends on receiver state and configuration. No
controlled ANfl case has varied armor/defense type, spell reduction, magic
immunity, ethereal state, invulnerability, or absorption. The exact meaning
of flags `+0x0C = 1`, type `+0x14 = 0x400`, and selector `+0x20 = 0` remains
unresolved.

### Eligibility outcomes currently established

The two five-target selection cases establish callback delivery for five
identical, living Player 12 `hfoo` targets, and directly establish that the
three worker recipients reached the damage path. A separate filtered capture
reused the case-21 layout and observed the relation gate return 1 and validator
return 0 for all five unique targets, including the two outside the selected
prefix. No controlled category/state case has yet separated query delivery,
relationship gating, shared validation, selection, and damage for
enemy/allied/neutral, flying, mechanical, structure, dead, hidden,
invulnerable, or magic-immune units.
Authored target-mask labels remain data evidence, not a substitute for these
runtime outcomes. The detailed partial matrix and static conditions are in
`build-re/ability-re/ANfl-target-selection-followup-01/specification.md`.

#### Native point resolution and target identity follow-up

The CUnit virtual `+0xB8` method at VA `0x0066E0A0` returns the point-handle
object stored at CUnit `+0x26C`; it does not return inline X/Y floats. The
observed point-handle vtable is `0x00E9D088`, with its registry pair at
`+0x08/+0x0C`. Focused Ghidra export `ANfl-point-resolver-abi-04/` and callsite
assembly verify that VA `0x007FCC50` (RVA `0x003FCC50`) is `thiscall`: `ECX`
is the point-handle object, stack argument 1 is a caller-owned three-float
output buffer, and the function returns with `ret 4`. It initializes the
output and calls VA `0x007FE810`, which resolves the handle pair through
`0x004707F0` and writes transformed X/Y/Z. Candidate callback VA `0x00C7907F`
uses this ordinary conversion path, then reads the first two output floats for
the distance calculation.

A bounded Frida NativeFunction probe in the prior same-process follow-up used
that point-handle/output-buffer ABI and reported three nonzero coordinate
outputs. These are historical same-process observations, not a controlled
five-unit identity match:

| Native candidate | Resolved point | JASS correspondence | Status |
|---|---|---|---|
| `0x02497488` | `(-1040.013, -6055.627, 0)` | Scenario target 3 is a plausible match from tick-12 JASS position `(-1037.754, -6057.930)`; the coordinate samples are not simultaneous. | Correlated candidate; not identity proof |
| `0x02496A50` | `(-851.316, -5976.288, 0)` | No reliable mapping | Unresolved |
| `0x02496534` | `(-870.396, -6091.953, 0)` | No reliable mapping | Unresolved |
| `0x02496018` | `(0, 0, 0)` | Consistent with failed handle resolution after output initialization; no match asserted | Unresolved |
| `0x02496F6C` | `(0, 0, 0)` | Consistent with failed handle resolution after output initialization; no match asserted | Unresolved |

Workers ran for `0x02496018`, `0x02497488`, and `0x02496F6C`; the native damage
receiver target matched each worker pointer. The JASS case reported target
indices 0, 3, and 4 losing life. This does not map all five native pointers to
JASS handles, and the two zero resolver outputs preclude treating the mapping
as complete. The old raw `candidate_x/y` trace fields remain invalid.

The fresh filtered observer is preserved under
`build-re/ability-re/ANfl-deterministic-selection-03/`. After two failed chat
activation attempts, a retry activated `anfl-r1-five-a`; retain both traces.
The successful trace hooks the existing resolver callsite and records the
point object, handle-table resolution result, resolved XYZ, candidate pointer,
and callback invocation. Four unique candidates resolved successfully. This
confirms the corrected instrumentation path against live candidate objects;
the older `candidate_x/y` fields and earlier zero resolver outputs remain
invalid as world-position evidence.

The successful historical case is summarized in
`case-01-analysis.json`, with raw Frida and JASS captures adjacent to it. JASS
records five scenario handles and their positions; callback-time native
coordinates correlate to indices 0, 3, 1 and 4. The first three worker and
damage receiver pointers were indices 0, 3 and 1. Their native distances to
the explicit target were 0.000, 154.727 and 175.163; the fourth observed
candidate (index 4) was 229.871 and received no worker. Index 2 did not occur
in the candidate callback trace. The four observed distances retrospectively
match ascending worker order and the JASS life changes. This is not a complete
five-candidate result: the missing index 2 could reflect query coverage, and
the targets were moving during the case. Index 4 is a coordinate-proximity
match, not a handle-registry proof. Do not treat this as the requested
stationary, pre-predicted selection experiment.

Runtime counts for this case are 11 callback deliveries, four unique native
candidate pointers, four successful coordinate resolutions, three workers,
and three matching `0x002677C0` receiver calls. Callback return value `1`
means continue spatial enumeration; it is not an acceptance result. The
callback-time position plus worker/receiver identity and JASS handle/life
samples provide a one-case identity correlation, with the limits above. Cases
19 and 21 below later meet the stationary, pre-predicted selection requirement
with five native/JASS-correlated targets.

No category eligibility matrix or controlled boundary/sorting matrix has yet
been run. A later filtered gate case is summarized below; it does not change
the unresolved category matrix. The historical four-candidate case verifies only four of its five
expected scenario targets and does not predict all five identities. Cases 19
and 21 below verify exact target choices for two controlled placements, while
the exact eligibility outcomes, query boundary behavior, and equal-key target
choices remain unresolved. Do not implement unverified target-category
predicates from authored mask labels alone.

### Current implementation-level algorithm and evidence boundary

```text
ownerPos = GetPoint(caster)
primaryPos = GetPoint(explicitOrderTarget)
direction = Normalize(primaryPos - ownerPos)  // zero-length behavior unresolved

for each native forward query generated by 0x00878A50:
    for candidate delivered by query type 0xB:
        if owner/target relation and candidate masks fail: continue
        if shared target validator returns a nonzero rejection code: continue
        if candidate pointer is already recorded: continue
        metric = EuclideanDistance2D(candidatePos, primaryPos)
        append(candidate, metric)

sort all appended records using comparator/sorter composition:
    primary metric ascending
    then signed candidate dword [+0x0C] descending for <=8 candidates
    // sorter is unstable when both keys compare equal

for candidate in sorted[0 : min(count, DataB)]:
    process through the verified per-target worker and damage path
```

Verified static: gate order, pointer deduplication, metric inputs and math,
comparator key order, unstable generic sort behavior, full-set sort, and
post-sort DataB bound. Verified runtime: earlier captures recorded five
distinct candidate pointers and three workers for DataB=3. Cases 19 and 21
each recorded 13 callback deliveries, five distinct candidates, five
successful point resolutions, three workers, and three matching damage
receivers. Their unique native positions correlate one-to-one with all five
JASS scenario units by exact coordinates, owner, and type; no native handle-
registry mapping was used. Both pre-cast predictions matched worker order,
receiver pointers, and JASS damage. Unresolved: individual gate outcomes for
the two non-selected candidates, specific unit-state/category outcomes, exact
rank-one query geometry beyond the corroborated model, boundary inclusion,
registry-based handle mapping, equal-key target determinism, and category/type
damage semantics.

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
provide a pointer-to-individual-JASS-handle mapping for all five units in
these archived rank-two/rank-one cases. Cases 19 and 21 below add that
coordinate-based mapping for their controlled rank-one casts.

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
targets losing the rank-matching amount by the 0.75-second sample. In the
controlled rank-one cases 19 and 21, all five native candidate positions were
correlated one-to-one with JASS handles; the three selected native receiver
pointers map to the three JASS damage events. This is coordinate-based
correlation, not a verified native handle-registry mapping.

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
| Rank-one through rank-three amounts | Runtime receiver payloads 85, 160, and 250; static row accessors read DataA; rank-one/two JASS samples show matching damage events | A same-owner +10 armor comparison showed no measurable reduction at rank one; spell-reduction and other receiver modifiers remain untested; rank-three life loss was overkill-limited. |
| Shared receiver and selected targets | Runtime worker target equals receiver ECX; cases 19 and 21 correlate all five native candidate coordinates one-to-one with JASS targets and match the predicted three damage recipients | Correlation uses exact live coordinates, owner, and type; a handle-registry mapping and individual gate outcomes for non-selected targets remain open. |
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
| `+0x10` | rank 1: float `85` (`0x42AA0000`); rank 2: float `160` (`0x43200000`); rank 3: float `250` (`0x437A0000`) | Raw amount supplied to receiver; static row accessor and worker context map these tested values to DataA. Rank-three target deaths make life loss unsuitable as the raw amount. |
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

## Controlled five-target follow-up: activation and placement recovery

A later attempt is preserved under
`build-re/ability-re/ANfl-controlled-target-selection-04/` and
`ANfl-controlled-target-selection-05/`. Case 04 reached the gameplay HUD, but
its chat scenario produced no fresh JASS placement result. The first map wired
chat registration to the campaign intro-skip action; that registration point
was not shown to have executed. Case 05 moved the registration call into map
`main` immediately before `RunInitializationTriggers`, verified the call in
the generated `war3map.j`, launched the prepared map, advanced it to the
expected gameplay HUD, and displayed `-re anfl-prepare-a` in chat. It still
produced no fresh placement result. See `investigation-status.json`,
`investigation-notes.md`, launch records, and `failure-screen.png` in case 05.

The later activation checks isolated a working pipeline. Case 05's launch
record and archive identify the exact prepared map; its embedded `war3map.j`
byte-matches the generated script with `RE_Init()` in `main`. A direct startup
sentinel in case 06 wrote a fresh run-specific `PreloadGen` file. Case 07's
exact-match chat trigger wrote a separate output containing the current run
ID, command, and triggering player. Case 08 emitted a one-unit identity
record. This verifies map `main` → startup PreloadGen and chat registration →
handler → PreloadGen. Evidence is retained in
`build-re/ability-re/ANfl-startup-sentinel-06/` and
`ANfl-chat-sentinel-07/`.

The first five-unit output failures were localized to scenario preparation.
Case 09 checkpoints reached `after_targets` but not the end of the target
loop. Case 10 completed the loop after shortening its per-target JASS record
expression and adding checkpoints; it recorded five units but detected
pathing relocation, so that layout was rejected. The precise reason case
08/09 stopped remains unresolved; expression size is only a hypothesis.

Case 11 used five pathable positions and reproduced all five requested target
coordinates. Their handles were `1055960`, `1056238`, `1056242`, `1056234`, and
`1056211`; all were Player 12 `hfoo` units. Five 0.25-second samples showed
each target stationary. The caster was not given Hold Position, however: it
moved from `(-1072,-5968)` at placement to `(-4896,-7296)` by the cast sample.
`IssueTargetOrder` returned false, and the bounded Frida trace contained no
ANfl acquisition, candidate, worker, or damage events. Case 11 is an
order-rejected movement-confounded diagnostic, not a target-selection
comparison. Its pre-cast prediction is retained but marked invalid for
comparison in
`build-re/ability-re/ANfl-controlled-target-selection-11/results/case-a-comparison.json`.

Case 12 changed caster setup to a previously successful coordinate and issued
Hold Position. Its prepared map is retained, but the restarted Retail window
rendered black on the new Xvfb session. No gameplay command, placement result,
or cast was observed, so that launch is inconclusive. The complete session
manifest and artifacts are in
`build-re/ability-re/ANfl-controlled-target-selection-11/` and
`ANfl-controlled-target-selection-12/`. These remain rejected/inconclusive
historical cases. Case 12's script references `ordersOk` in `RE_SetupOne`
while declaring `holdOk` there, so its prepared JASS setup was defective; the
control map and later prepared cases render correctly on the recovered display.
The historical four-candidate trace remains incomplete; it does not establish
why its intended fifth target was absent.

### Controlled five-target prediction verification (October 18, 2026)

The previously active case 19 Retail process was reused for baseline case A.
Case 19 used the case 11/19 five-point layout, Player 12 `hfoo` targets,
caster attack damage and dice set to zero, zero acquisition range, and
accepted Hold Position orders. All five targets had their requested actual
coordinates and remained stationary across five 0.25-second samples. The
prediction `predictions/case-a-v1.json` was written at 14:52:20 UTC; the
PreloadGen cast result was written at 14:52:25 UTC. Its prepared map SHA-256 is
`3e14dbfb556d8aa4221fc0d2fd98abf4fa6ac779fc68829e7bbf7a29ca7f2483`.

| Index | JASS handle | Native CUnit | Actual X,Y | Distance | Rank | Worker | Damage |
|---:|---:|---|---|---:|---:|---:|---|
| 0 | 1056216 | `0xfadcb64` | `(-880,-6084)` | 0.000 | 1 | 1 | 85; life 125.000 |
| 1 | 1056217 | `0xfadd080` | `(-720,-6160)` | 177.133 | 2 | 2 | 85; life 125.000 |
| 2 | 1056127 | `0xfadd59c` | `(-656,-6096)` | 224.321 | 3 | 3 | 85; life 125.000 |
| 3 | 1056047 | `0xfaddab8` | `(-656,-6160)` | 236.542 | 4 | — | none; life 210.000 |
| 4 | 1055982 | `0xfaddfd4` | `(-592,-6224)` | 320.225 | 5 | — | none; life 210.000 |

The order was accepted at rank one with 330 mana. Caster position was set to
`(-1030,-5994)` immediately before the order; after order acceptance the JASS
sample recorded it at `(-1072,-5968)` with current order `0xD026B`. The spell
effect arrived at 0.5 seconds. Native Frida observed 13 callback deliveries,
five unique CUnit pointers, five successful coordinate resolutions through
the engine's existing `0x007FCC50` calls, three workers, and three receiver
calls of 85. All five native XYZ coordinates exactly matched one unique JASS
target position, owner and type. This is a one-to-one coordinate correlation,
not a native handle-registry mapping. The worker and receiver sequence was
`[0,1,2]`, exactly matching the saved prediction.

The first case-19-B placement attempt is preserved but was discarded before a
cast: target 3's requested `(-760,-6084)` position was pathing-blocked, and
targets 3 and 4 shifted before the first stable sample. Case 20 corrected the
layout by using already validated positions; all five actual positions matched
the prediction and remained stationary. Its pre-cast prediction is retained,
but `IssueTargetOrder` returned false with caster mana 105.991 and native
acquisition did not run. Case 20 does not distinguish mana from cooldown as
the sole order rejection cause.

For the independent rank variation, case 21 swapped target identities 1 and 3
between already verified case 19 positions. All five requested positions were
walkable, reproduced exactly, and remained stationary in five samples. The
prediction was written at 15:06:00 UTC, before the cast result at 15:06:43 UTC.
The prepared map SHA-256 is
`25323133e7d824622a96ccd3d9e66b00b03c3ed2aff230ca9f1dd3a3ac91c59e`.
Immediately before order issuance, the harness restored caster mana to its
330 maximum and called `UnitResetCooldown`; the logged caster was alive at
92.968 life, rank one, with current order zero.

| Index | JASS handle | Native CUnit | Actual X,Y | Distance | Rank | Worker | Damage |
|---:|---:|---|---|---:|---:|---:|---|
| 0 | 1056016 | `0xe358870` | `(-880,-6084)` | 0.000 | 1 | 1 | 85; life 125.002 |
| 1 | 1055866 | `0xe358d8c` | `(-656,-6160)` | 236.542 | 4 | — | none; life 210.000 |
| 2 | 1056020 | `0xe3592a8` | `(-656,-6096)` | 224.321 | 3 | 3 | 85; life 125.002 |
| 3 | 1055943 | `0xe3597c4` | `(-720,-6160)` | 177.133 | 2 | 2 | 85; life 125.002 |
| 4 | 1055970 | `0xe359ce0` | `(-592,-6224)` | 320.225 | 5 | — | none; life 210.000 |

This order was accepted; native acquisition resolved five unique candidate
positions from 13 callback deliveries. Workers and damage receivers were
`[0,3,2]`, matching the new prediction and the JASS `amount=85` events.
Across both valid cases, the native coordinates, JASS identities, distinct
distance order, DataB=3 worker prefix, receiver order, and life changes agree.
The prediction changed from `[0,1,2]` to `[0,3,2]` when target identities 1
and 3 exchanged their validated coordinates. The tie-break key values were
captured, but these distinct-distance cases do not runtime-test tie ordering.

The exact callback-level relationship/shared-validator decisions and candidate
array append were not separately hooked. All five identical living targets
were delivered to the callback; the selected three's gate passage is directly
established by their workers, while gate passage for the two non-selected
targets is inferred from the identical setup and static callback path. Exact
rejection-category behavior and spatial boundaries remain open. Full raw
traces, predictions, placement/cast PreloadGen captures, and machine-readable
comparisons are retained in
`build-re/ability-re/ANfl-controlled-target-selection-19/` and
`ANfl-controlled-target-selection-21/`.

### Follow-up gate observation

A fresh accepted case reused the case-21 layout and saved a separate prediction
before casting. All five unique callback pointers had resolved coordinates;
each relationship gate returned 1 and each shared-validator call returned 0.
The three workers and receiver pointers correlated to predicted indices
`[0,3,2]`; each native payload carried 85 and JASS recorded matching life
changes. Thirteen callback deliveries deduplicated to five pointers. The two
non-selected candidates also passed both observed gates, so their exclusion in
this case is consistent with the post-sort DataB prefix. Identity remains
coordinate/owner/type correlated, without a native-handle registry proof.

The immutable prediction, placement/cast JASS outputs, filtered trace, map
hash, and machine comparison are retained under
`build-re/ability-re/ANfl-target-selection-followup-01/`. The result extends
gate evidence only to this living Player 12 `hfoo` setup; it does not identify
the gameplay meanings of the relation flags or rejection codes, or establish
eligibility for other categories.

### Same-owner secondary target probe (October 18, 2026)

An additional rank-one cast changed only secondary scenario index 3 from
Player 12 to Player 0 (the caster owner), retaining `hfoo` and the case-21
requested coordinate `(-720,-6160)`. The map recorded all five actual target
coordinates and handles before the cast. Its damage log shows ordinary
Footman-to-Footman attacks while the targets hold position. Later replay logs
also include old/stale `hfoo` and `Nngs` source handles not present in that
replay's placement list. The logs therefore establish ordinary combat
contamination but do not identify every source as a campaign unit or as a
current scenario unit.

The accepted cast's type-0xB query trace delivered four of the five scenario
positions: indices 0, 1, 2 and 4. Index 3 was never delivered to the ANfl
candidate callback, so this run does **not** show a relationship-gate or
shared-validator rejection for that allied unit. All four delivered unique
units returned 1 from `0x0027FB80` and 0 from `0x00282180`; workers and damage
receivers were indices `[0,2,1]`, with raw payload 85. The same-owner unit's
exclusion is now explained by exact-build static evidence: the query's `0x1D`
clause installs predicate `0x00696BE0`, which calls
`0x006ADB90` → `0x006ADA20` → `0x006AD670` before the callback. The authored
mask `0x04010006` normalizes to `0xF5D10006`; same-owner rejection code `0x84`
applies when bit `0x2000` is absent. The observed callback absence agrees with
that branch. The follow-up live hooks did not capture the candidate-specific
`0x84` result; the mask-filtered captures either hit generic-query limits or
filtered on another query's mask. This return-value link is static, not runtime
proof.

This single same-owner case is category-specific runtime evidence, not a full
alliance matrix. Selected units' JASS life observations were confounded by
ordinary attacks and stale unit/projectile sources; native receiver calls
establish the ANfl worker recipients in the original capture. Three later
same-map Frida attempts are preserved:
the first saturated on general query traffic; the second recorded a different
query mask (`0x0400F006`) and saturated; the third emitted only `agent-ready`
because its filter did not match that mask. None captured this ANfl query's
candidate-specific return. The raw map, JASS outputs, bounded traces,
follow-up outputs, static exports and query inputs are preserved in
`build-re/ability-re/ANfl-target-eligibility-ally-01/`. The four query centers
and radii are recorded in its `results.json`; together with the pre-cast caster
and primary-target coordinates, they corroborate the rank-one progression and
radius model described above. The native caster point and exact circle-edge
inclusion remain unverified.

The current implementation-level specification, including evidence labels,
the limited eligibility matrix, query measurements, numeric damage payload
and remaining gaps, is retained at
`build-re/ability-re/ANfl-target-eligibility-ally-01/specification.md`.

### Clean damage control and query-shape predicate (October 18, 2026)

`ANfl-clean-combat-01` used a fresh prepared-map run, removed nearby local
units, set ordinary attack damage and dice to zero for the caster and five
test Footmen, issued Hold Position, and sampled the targets every 0.25 seconds
for five seconds before casting. All five remained at 210 life over 21
samples; the no-cast output contains no nonzero damage event. This establishes
a clean target-life control for that fixture. The accepted rank-one cast then
produced three receiver calls and three JASS damage events of 85 against the
predicted `[0,1,2]` prefix; those targets fell from 210 to approximately 125,
while the two unselected targets stayed at 210. This is the first clean
life-delta confirmation for ANfl in this investigation. The caster itself
lost health while exposed during the trace interval, so caster life is not a
clean control. Artifacts and hashes are in
`build-re/ability-re/ANfl-clean-combat-01/`.

Focused exact-build exports under
`build-re/ability-re/ANfl-spatial-query-predicate-detail-03/`,
`ANfl-spatial-query-shapes-detail-01/`, and
`ANfl-spatial-query-math-detail-01/` resolve the type-0xB final geometric
predicate. Query construction at VA `0x0068EA00` passes the radial shape to
`0x007F4CF0`, which dispatches the relevant shape to `0x00807130`. That path
uses spatial bounds enumeration, computes squared 2D center distance,
computes `radius + candidateEntry[+0x90]`, squares that sum, and accepts when
`distanceSquared <= expandedRadiusSquared`. Thus the final comparison is
inclusive and candidate-entry-extent-adjusted; the scalar at spatial entry
`+0x90` is not yet mapped to a gameplay property. This does not prove the
broadphase returns every matching unit or that the scalar is WC3 collision
radius.

The repaired `ANfl-geometry-boundary-01` fixture fixed the stale scenario-ID
and output-branch mismatch. Its preflight checked run IDs at chat dispatch,
setup, finish/output, manifest and generated JASS; rejected duplicate output
names and stale IDs; and verified archive/script hashes before launch. Fresh
placement and cast outputs were produced. The exact prepared-v3 map SHA-256 is
`9082fe582d52e7e4625a340f531ac77990b6bf4d74a98e45ebd139352bc54c1e`.

The trace resolved the relevant position timing: native acquisition sampled
the caster at `(-1072,-5968)` and explicit target at `(-880,-6084)`, after the
caster moved from its JASS pre-order location `(-1180,-6084)`. Observed query
centers match `center(p)=acquisitionCaster + normalize(target-caster)*(p+Area)`.
For `Area=125`, `DataC=900`, `DataD=300`, `L=475`, the observed progress,
radii and along-ray offsets are `[0,125,296.0526,475]`,
`[125,171.05263,234.07201,299.99997]`, and `[125,250,421.0526,600]`.
Native centers were `(-965.01196,-6032.63867)`, `(-858.02386,-6097.27734)`,
`(-711.61908,-6185.72998)`, and `(-558.45715,-6278.26563)`. The earlier
`DataD/4` center-offset expression was incorrect; the checked-in specification
has been corrected. Higher-rank geometry, zero-vector handling and other
range clamps remain open.

The type-0xB predicate normalizes query radius by 32, reads spatial entry
`+0x90`, adds that scalar and compares squared 2D distance inclusively. The
native comparison operands observed `+0x90 = 0.96875` (`0x3f780000`) for tested
Footman entries, equivalent to 31 world units after the query-radius scaling.
One candidate just inside a query-2 boundary had `distance²=39.85868` versus
`boundary²=39.86842` and reached the callback. A second candidate failed the
query-3 and query-4 final-circle tests (`199.56389 > 68.61636`,
`184.66995 > 106.99314`) and had no callback delivery. Its correlation to JASS
target index 3 is inferred from allocation stride. These results verify one
inside and one outside prediction for the final predicate, not exact equality
or the broadphase edge. The gameplay meaning/writer of `+0x90` remains
unresolved; do not label it collision size based on the numeric value alone.

Player 12 is Neutral Hostile; prior reports calling it a generic enemy player
are corrected here. At this point in the investigation, separately allied
Player 1, neutral passive Player 15, magic immunity, invulnerability, and
another caster-to-target distance had not yet been tested. The later immunity
and Player 1 findings are recorded in the follow-up section below. Neutral
Passive Player 15 and another caster-to-target distance remain untested. The
clean-combat fixture alone does not establish mitigation.

The prepared follow-up `ANfl-geometry-distance-02` did not produce valid
geometry results. Its script retained stale chat run IDs/output branches from
the earlier ally probe, so the chat handler marker appeared but no matching
geometry scenario result was written. The preserved map hash and corrected
pre-observation prediction are setup evidence only; this attempt is not
counted as a boundary test.

### Immunity callback validation and prepared-map transition (October 18, 2026)

The first `ANfl-state-alliance-ranks-01` launch was stopped while the OrcX01
campaign intro/transition was still in progress. A minimal diagnostic derived
from the working clean-combat fixture emitted a startup PreloadGen result and,
after the map reached gameplay, a separate `-re anfl-startup-check` handler
result for Player 0. A subsequent launch of the original seven-case map
completed its normal campaign sequence and produced fresh setup and cast
outputs. No script or archive fix was needed; the earlier black screen was a
normal transition, not an observed JASS startup failure. The diagnostic and
capture are preserved in `build-re/ability-re/ANfl-startup-diagnostic-01/`.

The normal rank-one control (case 1) had an accepted order, three native
workers and three CUnit receivers with raw payload 85, plus matching JASS
damage events. The saved prediction was matched by target indices 0, 1 and 2.

In case 2, the secondary Player 12 Footman had `Amim` ability level 1 in the
JASS setup/cast records. Its spatial entry passed the geometric predicate and
was delivered to the ANfl callback. The callback relationship gate returned
1, but the shared target validator returned decimal 54 (`0x36`). It did not
reach a worker or damage receiver; the selected replacement candidates did.
Its life remained 210 while the three recipients received 85. This is
callback-level rejection, not pre-callback filtering or damage suppression.

In case 3, the same secondary Footman received a `SetUnitInvulnerable(...,
true)` call. The callback delivered it, the relationship gate returned 1, and
the shared validator again returned `0x36`; it reached no worker or receiver.
Three other selected targets received raw 85. This fixture did not separately
read back the invulnerability state, so that treatment's state verification is
less direct than the Amim level readback. The `0x36` validator code's general
semantic name is unresolved. Runtime traces and per-case outputs are in
`build-re/ability-re/ANfl-state-alliance-ranks-01/runtime/` and `results/`.

Case 4 changed target 1 to Player 1 and explicitly set mutual passive
alliance with Player 0; the setup output confirms both directional alliance
checks. The target did not reach the ANfl callback or a worker, while three
Player 12 targets received 85. The target-specific pointer was absent from
the final geometry-comparator and `0x006AD670` observations, so these captures
do not distinguish broadphase omission from rejection in an earlier query
predicate. The exact exclusion stage remains open. Trace and JASS output are
`runtime/state-trace-v5-allied.jsonl`, `results/case-4-setup.txt`, and
`results/case-4-cast.txt`.

The later Neutral Passive case used Player 15 for the same `hfoo` at
`(-720,-6160)`. JASS confirmed owner 15, position, and 210 life after the
five-second hold, and accepted the rank-one order. The final geometry trace
did not contain the target's expected spatial-index point `(169.5,63.5)` in
any query; the matched Player 12 control and Amim candidate at this location
did reach the geometry stage. No Player 15 candidate was seen at
`0x006AD670` or the ANfl callback. This places its exclusion at or before the
final geometry-operand hook, without distinguishing broadphase omission from
a pregeometry candidate predicate. The other selected candidates received
three raw-85 receiver calls. Raw files and trace are under
`build-re/ability-re/ANfl-neutral-passive-rank3-01/`.

That run also completed a rank-three cast. JASS read back ability level 3;
the accepted cast generated four type-`0xB` queries with radii
`125, 171.05263, 234.07201, 299.99997` and centers
`(-965.01196,-6032.63867)`, `(-858.02386,-6097.27734)`,
`(-711.61908,-6185.72998)`, and `(-558.45715,-6278.26563)`. These match the
rank-one progression because authored `Area=125`, `DataC=900`, and `DataD=300`
are the same. Three workers and CUnit receivers carried raw 250, confirming
rank-three DataA at runtime. Target maximum life was 210, so the receiver
payload—not final life loss—is the raw damage measurement. A separate
single-case rank-two run is now captured at
`build-re/ability-re/ANfl-rank2-geometry-03/`. It recorded rank 2, the same
four query radii and centers as ranks 1 and 3, three workers, and three
receiver payloads of raw 160. Its saved pre-cast prediction contains the older
`p+DataD/4` center expression; measured centers miss that prediction and
match the corrected `p+Area` model. The prediction is preserved, and this
discrepancy is recorded in `results/geometry-comparison.json`.


### Retail disk/profile warning follow-up (October 18, 2026)

The failed Retail launch coincided with the container overlay backing the Wine
prefix reporting zero available bytes and 100% use. It now reports 3.8 GiB
free and 7% inode use. Wine's Warcraft Documents path resolved correctly;
write/delete checks passed in CustomMapData and save/Profile1 directories, and
the registry reports Allow Local Files enabled. A bounded launch of the known
OrcX01 control map reached its chapter card and gameplay HUD without a profile
warning. The exact profile operation that failed during exhaustion was not
captured. No files were deleted to resolve it. Evidence is in
`build-re/ability-re/ANfl-environment-diagnostic-02/`. A later rank-two run
used the available Frida endpoint at `127.0.0.1:27043` and produced a bounded
native capture under `build-re/ability-re/ANfl-rank2-geometry-03/`. This does
not resolve owner filtering, invulnerability readback, `0x36` operand
differences, or receiver mitigation.

### Reversible invulnerability native and damage probe (October 19, 2026)

The single-unit reversible run in
`build-re/ability-re/ANfl-invulnerability-reversible-02/` used Retail
1.29.2.9231 (executable SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`), a
prepared OrcX01 map (SHA-256
`0440b71cbda30eaeff0aca19e54d2e7478c4b9cbba0f72e3acf2cf21e9f00b4a`), and
embedded `war3map.j` SHA-256
`fdb6c9a25641cc9066a1d3f95de5414b56e525436d80467cc8e6f395161ad973`.

**Verified runtime native state:** JASS handle `0x101DAA` resolved in both
`BlzIsUnitInvulnerable` and `SetUnitInvulnerable` to CUnit `0x103F2350`.
Its dword `+0x20` transitioned `0x1646 → 0x164E → 0x1646` for setter
true then false; the getter returned `true → false → true`. The setter's
attached object was a different pointer (`0x0D7A4DF0`) with tag
`0x2B61676C` and `+0x20 = 0`. This ties the getter's inverse bit-3 calculation
to the exact state changed on the same resolved CUnit. The attached tag's
class meaning and the implementation behind virtual slot `+0xA8` remain
unknown.

**Verified runtime gameplay effect:** the same Player 12 Footman received
three ordinary `UnitDamageTarget` requests for 20 damage. Before setter true,
getter true and life fell `210 → 192.143` (damage event 17.857). With setter
true, getter false and life stayed `192.143` (event amount 0). After setter
false, getter true and life fell `192.143 → 174.286` (event amount 17.857).
`UnitDamageTarget` returned true in all three phases, demonstrating that its
return value means the request was accepted, not that life changed. This
confirms damage prevention in this ordinary-damage configuration; it does not
establish behavior for every damage category.

**Verified runtime ANfl observation, stage unresolved:** a fresh rank-one
cast was accepted with target index 1 actively treated (getter false before
and throughout the cast). That target stayed at 210 and was not one of the
three 85-damage JASS recipients (indices 0, 2, and 4 were hit). This run did
not trace that candidate through the callback and validator, so its earliest
exclusion remains unknown. The older case that reached callback and returned
`0x36` had no getter or native-state readback; it does not establish that the
setter had activated the state. Preserve both cases: actual active state now
has independent damage confirmation, while the old callback observation and
the new recipient omission remain unreconciled at the ANfl stage level. The
JASS outputs, native JSONL, prepared map, and machine-readable comparison are
in the fixture's `results/` and `runtime/` directories.

## October 19 confirmed-invulnerability candidate trace

The candidate-correlated accepted cast in
`build-re/ability-re/ANfl-invulnerability-candidate-trace-02/` identifies the
first exclusion stage. The treated Player 12 Footman (JASS handle pointer
`0x101d74`, CUnit `0x0f166128`, spatial entry `0x0fdb5b78`) had CUnit
`+0x20 = 0x164e`, bit 3 set, and `BlzIsUnitInvulnerable == false` immediately
before acquisition. Its spatial entry was registered (`+0x90 = 0.96875`) and
it passed final geometry in queries 2–4. It then reached query predicate
`0x00696BE0`, shared filter `0x006ADB90`, and target-mask function
`0x006ADA20` with flags `0x55a00002`. ANfl raw mask `0x04010006` normalizes to
`0xf5d10006`; the target-mask function returned `0x96`, causing the enclosing
query predicate to return zero. Owner/relation filtering, ANfl callback,
relationship gate, shared validator, retention, worker, and receiver were not
reached. Three normal targets reached the receiver with raw damage 85.

Exact-build static evidence in `ANfl-query-relation-helper-04/decompiled.jsonl`
shows the target classification uses CUnit `+0x20` bit 3 to choose the
`0x100000` versus `0x200000` category, and the normalized ANfl mask excludes
the latter. Thus the confirmed active state is rejected at query-level
masking, before callback validation. The earlier callback-level `0x36` case
has no independent getter/bit readback and cannot be assigned this same
confirmed state. The earlier matched normal/Amim attempt in
`ANfl-validator-operands-postcall-02/` was incomplete: Frida recorded only
agent readiness. The same-cast repaired comparison is in
`ANfl-validator-operands-postcall-07/`; the ordinary candidate selected
`+0x264=0` and returned zero early, while the Amim-associated candidate
selected `+0x264=1`, then source returns `+0x1D8=1`, `+0x1FC=0`, config value
zero, and `+0x20C=0`, reaching validator return `0x36`. Static branch
`0x006822C3` confirms the zero `+0x20C` condition. Candidate field semantics
and writer remain unresolved. The older `postcall-05` mismatch and Stalker
errors are preserved in the comparison report.

### Owner matrix follow-up (October 19, 2026)

The corrected accepted-cast matrix at
`build-re/ability-re/ANfl-owner-filter-matrix-02/` correlates live JASS
handles, CUnits and spatial entries. Its Frida trace observes shape-entry
iteration at VA `0x008073C0` (RVA `0x004073C0`), before final geometry at
`0x0080740A`. Player 12 and an ordinary non-neutral hostile Player 2 entered
this loop. Both passed geometry on applicable queries, target-mask filtering
(return 0), owner/relation filtering (return 0), callback relationship gate
(return 1), and shared validator (return 0); both reached the ANfl worker and
CUnit receiver with raw payload 85. Player 2 was explicitly non-allied to
Player 0 in both passive-alliance directions in this scenario.

Player 1 (mutually passive allied with Player 0 in both directions) and Player
15 Neutral Passive had valid live CUnits, expected positions, and bit-3-clear
`+0x20=0x1646`, but neither appeared at the shape-entry iteration site in any
of four queries. They therefore diverged before final geometry in this trace.
The trace does not distinguish missing spatial registration/list membership
from an earlier shape-candidate-list construction filter; no target-mask or
owner/relation return code was captured for them. Their different CUnit
`+0x164` values are correlation only. The Player 0 reference also was not
observed at this site, but its position was not established as inside the
query coverage, so this run does not test same-owner rejection. See
`results/owner-matrix.json` for identities, per-query evidence, hashes and
limits. No new Player 1/Player 15 owner predicate is specified from these
observations.

Retail's exact-build native registry lists `BlzGetUnitArmor` at VA
`0x00497280` (RVA `0x00097280`) and `BlzSetUnitArmor` at VA `0x004AB130`
(RVA `0x000AB130`). The exact-build registration is used in the matched test at
`build-re/ability-re/ANfl-armor-mitigation-02/`: Player 12 Footman armor rose
from 2 to 12 and was read back. The treated target and untreated same-owner
controls all passed targeting and reached the receiver with raw 85; JASS events
reported 85 and paired life samples showed identical loss. No measurable armor
mitigation was found for this payload/configuration. Other defensive modifiers
and payload categories remain unresolved.
