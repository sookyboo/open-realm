# Retail ability combat traces

Detailed attack, damage, and area-impact observations. For current conclusions, see [verification status](../ability-verification-review.md).

## Shared attached-buff installation path

For the pinned Retail executable (SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`),
`0x006D4880` is a shared wrapper that attaches a constructed object and
performs the post-attach owner notification:

```text
0x006D4880: call 0x006D4560(owner, object)
0x006D488B: call 0x006F6E80(object)
```

`0x006D4560` links the object into the owner's attached-instance list.
`0x006F6E80` obtains the owner from object offset `+0x30` (or resolves a
fallback owner), then calls `0x005F5A20`. This is shared attachment
infrastructure; the final notification's semantic name remains unresolved.

Two independently identified buff paths use the wrapper after class-specific
creation/configuration:

- Poison application callback `0x00BDCF70` is vtable slot `+0x354` for both
  `CAbilityPoisonAttack` (vtable `0x00F5DB18`) and `CAbilityVenomSpear`
  (vtable `0x00F5DE8C`), as identified by exact-build RTTI and vtable entries.
  It looks up existing `Bpoi`, refreshes it through virtual `+0x388`, or
  creates/configures and attaches a new status through `0x006D4880`. The
  callback is now established as shared ability-side poison application; the
  ordinary weapon-hit dispatcher that invokes slot `+0x354` remains unknown.
- Pocket Factory missile impact callback `0x00C829F0` creates a `BNfy`
  `CBuffFactory` object after constructing the factory unit, then attaches
  it through the same wrapper. This is a different ability and buff class.
- Cold Arrow effect routine `0x00C5C9D0` rejects selected target states,
  builds the configured effect context, and looks up `BHca`. It refreshes an
  existing status through virtual `+0x388`, or creates/configures a new
  status and attaches it through `0x006D4880`. The preceding accessor
  `0x00C5C9B0` returns `CMissileColdArrowSplash`; its RTTI-linked vtable is
  `0x00FA0D70`, where `0x00C5C9D0` is slot `+0x80`. The separate
  `CAbilityColdArrows` accessor `0x00C5CBC0` is at slot `+0xE4` of ability
  vtable `0x00FA0E54`. Thus the buff-application callback belongs to the
  splash-missile class, not the ability class. Static inspection did not find
  xrefs to either vtable global, so the upstream missile construction/impact
  caller is still unresolved. Treat this as the class-specific effect endpoint,
  not proof that it shares Poison's attack-event dispatcher.
- This effect routine also calls `0x007FC7E0` with the pair at `this+0x2C`,
  after checking the paired fields at `+0x2C/+0x30`. The same helper is used
  by general target validation `0x00682180` to walk its validator registry.
  Disassembly shows `0x007FC7E0` resolves a stored pair through `0x004707F0`,
  rejects a missing or inactive entry, and returns the value at `+0x54`.
  This is verified helper reuse, but does not prove the Cold Arrow call makes
  the same target-validation decision or identifies the attack-event producer.
- Poison and Cold Arrow also converge on attached-instance lookup
  `0x006D6570`: Poison callback `0x00BDCF70` calls it at `0x00BDD088` while
  looking for `Bpoi`, and Cold Arrow effect routine `0x00C5C9D0` calls it at
  `0x00C5CA74` while looking for `BHca`. Both refresh an existing object via
  virtual `+0x388` or construct and attach a new one. This verifies shared
  lookup across two status classes; it does not identify their event producer.

Reproduce the wrapper disassembly with:

```sh
r2 -q -c 'e scr.color=0; pd 12 @ 0x006d4880; pd 12 @ 0x006f6e80; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The poison producer is resolved below. Cold Arrows' attack-event producer and
the argument meanings remain open; do not infer them from this shared
attachment path.

## Weapon impact ability dispatch: poison and Venom Spear

The Retail hit-processing path now reaches the poison application callback.
In `0x00B1CCB0`, the accepted target-hit branch calls `0x0068F950` before its
ordinary target damage fallback. That helper walks attached instances in
category IDs `0x1B` through `0x29`, queries each instance's category through
slot `+0x138`, and invokes slot `+0x154` for matching categories. The poison
and Venom Spear vtables both return category `0x28` from `+0x138` and resolve
`+0x154` to `0x00BDD5C0`.

`0x00BDD5C0` obtains the target object, checks it against the ability's stored
target configuration with `0x00682450`, then invokes the ability's slot
`+0x354` with the target and damage context. On either poison ability vtable,
that slot resolves to `0x00BDCF70`, which refreshes or creates `Bpoi` through
`0x006D4880`. After the callback, `0x00BDD5C0` dispatches the damage payload
through target slot `+0x120`; for a CUnit target that reaches receiver
`0x006677C0`. A handled return from `0x0068F950` skips the branch's ordinary
fallback damage call, avoiding a second application. This establishes the
Retail poison/Venom Spear impact route. Exact argument field meanings and
other category IDs remain open.

Cold Arrow is a separate missile-side effect endpoint. Its accessor at
`0x00C5C9B0` returns `CMissileColdArrowSplash`; the associated vtable begins
at `0x00FA0D70` and places effect callback `0x00C5C9D0` at `+0x80`. The
`CAbilityColdArrows` accessor `0x00C5CBC0` belongs to a distinct vtable at
`0x00FA0E54` (`+0xE4`). The callback rejects target flags, forms the effect
context, refreshes an existing `BHca` via target slot `+0x388` or creates and
attaches a new one through `0x006D4880`. This maps the class-specific effect
endpoint; it does not establish how a Cold Arrow missile is created or how its
impact callback is dispatched. Ghidra reports no references to either vtable
global, so static xrefs do not resolve that upstream path.

### Ordinary attack projectile branch handoff (exact-build static pass)

Follow-up inspection of `0x00B1CCB0` confirms that attack types 2, 3, and
5–8 prepare distinct effect records before entering the shared effect scheduler
`0x0046EB20`. The preparation helpers write fields at offsets `+0x6C..+0x7C`;
some capture a target object's point through virtual `+0xB8`, while others
store explicit coordinates. This is a common scheduling handoff, not evidence
that the resulting effects share an impact implementation.

The attack routine then calls a type-specific `0x0068F9F0`–`0x0068FD10`
helper. These helpers walk source-attached instances and query category slot
`+0x138`, but use impact-related slots `+0x13C`, `+0x140`, `+0x144`, `+0x148`,
`+0x14C`, or `+0x150`, depending on the helper. They are separate from the
confirmed direct-hit dispatcher `0x0068F950` (`+0x138` / `+0x154`). Their
class-specific consumers and semantic relationship to missile impact remain
unresolved.

The `0x00B1CCB0` switch maps each non-direct attack type to a specific helper
and callback slot:

| Attack type | Helper | Attached ability slot | Caller RVA in `0x00B1CCB0` |
|---:|---:|---:|---:|
| 2 | `0x0068FD10` | `+0x150` | `0x0071D118` |
| 3 | `0x0068FA90` | `+0x140` | `0x0071D589` |
| 5 | `0x0068FC70` | `+0x14C` | `0x0071D1FD` |
| 6 | `0x0068FB30` | `+0x148` | `0x0071D345` |
| 7 | `0x0068FBD0` | `+0x144` | `0x0071D456` |
| 8 | `0x0068F9F0` | `+0x13C` | `0x0071D6E3` |

Each helper checks the source ability registry, iterates category values
`0x1B..0x29`, compares each attached object’s `+0x138` result, then invokes the
slot shown above. The first nonzero handler result marks the ability path
handled. If no handler returns nonzero, the attack switch constructs and
schedules its type-specific effect record. This is a verified source-side
attack hook protocol; it does not by itself identify the eventual projectile
impact handler.

RTTI and exact vtable entries identify two concrete clients. The
`CAbilityPoisonArrows` vtable `0x00F5E574` maps `+0x14C` to `0x00BDE440` and
`+0x150` to `0x00BDE250`. The primary `CAbilityColdArrows` vtable
`0x00FA0DFC` maps those same slots to `0x00C5CE10` and `0x00C5CC20`. Each
callback clears ability flag `+0x20` bit `0x400000` and returns zero when that
bit was previously clear; otherwise it resolves owner/target context and
builds a hit record. The Cold Arrows handlers additionally query virtual
`+0x484` and write the returned value at record `+0x48`, setting record `+0x40`
to `0x200`. The precise meanings of these fields and how the resulting record
reaches the missile are still open.

Reproduce the branch mapping and vtable entries against this exact executable
with radare2:

```sh
r2 -q -c 'e scr.color=0; pd 110 @ 0x00b1ccb0; pd 55 @ 0x0068f9f0; pd 55 @ 0x0068fa90; pd 55 @ 0x0068fb30; pd 55 @ 0x0068fbd0; pd 55 @ 0x0068fc70; pd 55 @ 0x0068fd10; pxw 0x18 @ 0x00f5e6b0; pxw 0x18 @ 0x00fa0f38; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The two vtable dumps begin at `+0x13C`; the `+0x14C` and `+0x150` words
resolve to the Poison Arrows and Cold Arrows callbacks listed above.

The known Carrion Swarm path provides a comparison point: its missile update
`0x00C31430` calls `0x00C30BB0`, which prepares damage payload `0x006A9940`
and dispatches through target virtual `+0x120`. The known Cold Arrow splash
endpoint is `0x00C5C9D0` on vtable `0x00FA0D70` slot `+0x80`, but its upstream
producer remains unresolved. Neither endpoint is yet tied by verified call or
vtable evidence to the type-specific attack helper families above. Therefore
the generic projectile landing dispatcher and ordinary projectile attack
convergence remain open.

### Shared missile interaction gate and attached callbacks

`0x006ED680` is a shared two-object gate reached directly by four exact-build
callers: `0x006ECE00`, `0x006E2EB0`, `0x006ED140`, and the ordinary attack
effect routine `0x00B1CCB0`. It rejects null objects and a nonzero fourth
argument. Otherwise it first calls `0x006EEC90`, then `0x006D5ED0`; a nonzero
result from either returns handled. If neither handles the pair and the third
argument is nonzero, the routine enters a fallback branch containing the
Retail `CMissile.cpp` `::Missed` diagnostic and further time/position checks.
The final position predicate remains unnamed. This gate is therefore a useful
shared missile interaction/impact waypoint, but not yet the generic damage
dispatcher.

The two scans dispatch through linked object registries. `0x006EEC90` resolves
an interaction object and calls `0x006D64D0`, which walks a registry and
invokes virtual slots `+0x158` and `+0x164`; it retains a selected result and
returns whether that object's second callback handles the pair. `0x006D5ED0`
walks a related registry using slots `+0x15C` and `+0x168`. In each scan the
first callback returns a float used to retain the greatest-valued candidate;
the selected object's second callback determines the handled result. The
registry membership, float meaning, and the precise callback contract are not
established. These are shared collision/interception-style extension points,
not proof that a callback applies damage.

Caller argument setup distinguishes the attack route from two other missile
paths. `0x00B1CCB0` passes `this` plus its two objects, zero as the third
argument, and `impactRecord.flags & 0x400` as the fourth; the gate rejects
when that fourth argument is nonzero. Callers `0x006ECE00` and `0x006ED140`
pass the same third-argument value `1` and their object field `+0x68` as the
fourth argument, so they can enter the diagnostic/fallback branch when scans
do not handle the pair. At `0x006ECE00`, the gate result controls a
`MissDamageReduction` path; at `0x006ED140`, it controls the corresponding
miss path. These raw argument relationships are established statically;
the semantic meaning of bit `0x400` and field `+0x68` remains unknown.

RTTI and the exact `CMissileDeathCoil` vtable (`0x00F752A0`) identify a
concrete client of the second scan: slots `+0x15C` and `+0x168` resolve to
`0x00B28A00` and `0x00B28B00`. The first callback returns the sentinel
`0xDD` unless missile state/target checks pass; on its accepted route it
compares the candidate unit's point with missile state, queries the missile's
damage/category data, and dispatches through unit virtual slots `+0x308` or
`+0x30C`. The paired callback checks missile flags and target eligibility,
then copies candidate point data into missile state and changes missile flags;
some branches also call `0x00B492A0`. This demonstrates that the shared scan
can dispatch missile-specific target/impact behavior. It does not establish
that the float score is damage, nor does it prove all classes in the scan use
the same behavior. The Death Coil callback's full branch semantics remain
partially unresolved.

For comparison, `CMissileLightningAttack` vtable `0x00F5D1B4` has
`0x00BDB8E0` at `+0x158`; that callback validates a candidate through
`0x00BDC070`, sets missile flag `0x400000`, and invokes missile virtual slots
`+0x480`/`+0x484` before calling `0x006AEB40`. This is a distinct callback
family for the first scan, not evidence that the Death Coil and Lightning
callbacks share an implementation. Vtable-derived slot targets are exact;
their runtime registry participation is not yet confirmed dynamically.

Reproduction: inspect `0x00F752A0` and `0x00F5D1B4` using the RTTI/vtable
scan described in `screenshots/ghidra/README.md`, then disassemble
`0x00B28A00`, `0x00B28B00`, and `0x00BDB8E0` in the pinned executable.

Reproduce the callers and direct helper paths against the pinned executable:

```sh
r2 -q -c 'e scr.color=0; pd 100 @ 0x006ed680; pd 55 @ 0x006eec90; pd 55 @ 0x006d64d0; pd 55 @ 0x006d5ed0; pd 100 @ 0x006ece00; pd 100 @ 0x006e2eb0; pd 100 @ 0x006ed140; q' \
  'data/Warcraft III/Warcraft III.exe'
```

### Shared on-hit ability hook families (exact-build static pass)

The exact-build RTTI/vtable scan identifies additional clients of attack
callback slots. Critical Strike (`CAbilityCriticalStrike`, vtable
`0x00F6FB34`), Drunken Brawler (`0x00F70048`), and Bash (`0x00F7055C`) share
identical entries at slots `+0x13C..+0x150`: `+0x144 → 0x00C00450`,
`+0x148 → 0x00C00460`, `+0x14C → 0x00C00440`, and `+0x150 → 0x00C00430`.
The first two are 7-byte thunks to `0x00C01610`; the latter two are thunks to
`0x00C017A0`. Those destination routines both test ability flag `+0x20` bit
`0x200`, clear stored state at `+0x84`, resolve a target from the callback
argument, and build a hit/effect record. They use owner/target state and invoke
virtual methods, so the record's fields and downstream semantics remain
unresolved. This is strong evidence for shared implementations across three
distinct attack abilities, but not yet proof of the precise critical, bash, or
evasion rules.

Damage-bonus abilities expose a second family. Exact vtables map
`CAbilityDamageBonusBase` (`0x00FBF7BC`) and `CAbilityDamageBonusBaseEx`
(`0x00FBFBF4`) to callbacks `0x00C9E780` and `0x00C9E810` at `+0x138` and
`+0x13C`; `CAbilityFireDamageBonus` (`0x00FBFF38`),
`CAbilitySpellEffectBonus` (`0x00FC026C`), and
`CAbilityLightningDamageBonus` (`0x00FC0EC4`) override nearby slots with
class-specific implementations. The four functions `0x00C9E5D0`,
`0x00C9E6A0`, `0x00C9E720`, and `0x00C9E750` are byte-identical handlers:
check ability flag `+0x20 & 0x100`, clear it when present, set callback record
`+0x64 = 1`, and return 1; otherwise return 0. This common record-consumption
protocol is verified, but the originating event and the record field's meaning
are not. Extended callbacks such as `0x00C9FBA0`, `0x00CA0AC0`, and
`0x00CA11C0` use the same flag/record prefix and then continue through
ability-specific state and virtual calls. Treat them as specialized behavior,
not as a single shared damage application helper.

The RTTI scan and callback disassembly are reproducible against the pinned
project with the temporary scripts listed in `screenshots/ghidra/README.md`;
the vtable words and callback bodies can also be checked with radare2. During
this pass, Ghidra headless script startup failed because the full filesystem
prevented OSGi cache initialization, so callback bodies were checked with
radare2 and the earlier captured RTTI inventory. No runtime Frida capture has
yet confirmed these callbacks execute in the named gameplay scenarios.

### Shared level-indexed owner-data accessors

Several distinct ability paths share the same low-level readers for owner
data. Poison/Venom Spear impact handling (`0x00BDCF70`), Cold Arrow attack
callbacks (`0x00C5CC20`, `0x00C5CE10`), and Phoenix Fire's scheduled candidate
callback (`0x00C0F1E0`) all use members of the `0x0046Exxx`/`0x0046Fxxx`
reader family before constructing an effect/status context. The poison and
Cold Arrow callbacks also use the same `0x0046F3A0` and `0x0046F500` readers
for a branch-selected field. Phoenix Fire's caller follows the same general
sequence, including `0x0046EE20` and `0x0046F3A0`. This establishes reuse
across poison, cold-arrow, and periodic area-effect paths.

The directly inspected functions `0x0046EE20`, `0x0046EED0`, `0x0046EF80`,
`0x0046F030`, `0x0046F3A0`, and `0x0046F500` read offsets `+0x24`, `+0x28`,
`+0x2C`, `+0x30`, `+0x08`, and `+0x0C`, respectively, from an indexed `0x70`
byte record. They derive the data table from the supplied owner/player context,
validate the requested rank against its configured level count, and return the
global zero value on invalid context or out-of-range rank. The table can be
inline or indirectly based on a pointer field, depending on its `+0x1C0`
control value. `0x0046EA70` is a related two-dimensional accessor: it checks
both dimensions, indexes the same `0x70` byte record stride and then reads a
rank-indexed element. The helper code establishes storage mechanics and raw
field offsets; it does not establish which AbilityData columns those fields
represent.

Several callback bodies use these readers to build a compact set of values
passed to a status constructor or callback record. Phoenix Fire's callback
uses the resulting fields in its periodic effect setup; Poison/Venom Spear
and Cold Arrow use them in their on-hit paths. This is a high-value shared
data-access layer, but not itself damage application or target validation.
Exact retail-to-AbilityData column mappings and per-class interpretation are
still open. Reproduce the inspected functions with `pd 100 @ <VA>` in radare2
and compare call sites in `0x00BDCF70`, `0x00C5CC20`, `0x00C5CE10`, and
`0x00C0F1E0`; the original Ghidra caller captures are under
`/tmp/wc3-ghidra-inspect/`.

The reader family also appears outside an attack or damage callback. Factory
construction setup `0x00C82310` calls `0x0046F030`, `0x0046EF80`, and
`0x0046EED0` using its owner data context, then combines those returned values
with an authored `DataB` lookup. This confirms the helpers serve general
player-owned ability data, not a damage-specific table. The data column names
and gameplay meaning of those construction parameters still require the class
caller and matching AbilityData row to be traced together.

On a missing cached table, these readers route through `0x006AEFB0`. Its
static path queries the global cache through `0x006B7DE0` and calls
`0x006ACE00` to build/cache data on a miss. That extends the shared path from
field readers into data-table resolution, though the cache key encoding and
record schema remain unresolved.

### Shared area-query builder and generated predicates

`0x0068EA00` is a shared clause-driven candidate query builder/executor, not a
projectile impact dispatcher. The pinned project shows 133 direct references
from 118 functions. Phoenix Fire's periodic acquisition `0x00C0ECD0` uses it
with callback `0x00C0F1E0`, an owner-centered query, and a radius/configuration
from its ability object. Carrion Swarm missile update `0x00C31430` uses the
same routine with callback `0x00C31220` to gather path candidates, then applies
attack target gates and calls its own damage callback `0x00C30BB0` for selected
missiles. This is shared candidate enumeration, not shared hit resolution.

The query builder installs reusable generated predicates based on typed
clauses:

- `0x00696CF0`: candidate's required flags at `+0x34` are all set in unit
  flags `+0x164`, and forbidden flags at `+0x38` are clear.
- `0x00696A00`: candidate field `+0x20`, bit 3, is clear.
- `0x00696D20`: candidate byte `+0x37` is within `0x41..0x5A` and unit flag
  `+0x164` bit `0x40000000` is clear.
- `0x00696DD0`: unit flag `+0x164` has bit `0x10000` set and masked bits
  `0x8000080` are not exactly `0x80`.

These machine-level conditions are confirmed; their numeric flag names remain
unmapped. In Carrion Swarm, the enumeration callback `0x00C31220` caps
collected candidates at 64 and uses `0x006ADB90` before appending each one.
That prefilter is separate from the ability-specific target callback and the
later missile damage routine.

Additional predicates installed by the same builder confirm its clause-driven
shape. `0x00696D80` is the inverse of `0x00696DD0`; `0x00696C60` returns
candidate `+0x454 & 0x40`; `0x00696A20` compares the candidate value to query
`+0x14`; `0x006967E0` calls candidate virtual `+0xEC` and tests the resulting
index in query mask `+0x0C`; `0x00696DB0` compares candidate `+0x34` with query
`+0x2C`; and `0x00696BE0` rejects candidates when `0x006ADB90(candidate,
query+0x3C, query+0x40, query+0x44)` returns nonzero. `0x00696AB0` looks up a
candidate field `+0x34` through `0x006993A0`, then compares the result's
`+0x1C0` with query `+0x30` (or accepts only query value zero when lookup
fails). These are observed data contracts; the field meanings are not
established.

After parsing clauses, `0x0068EA00` runs the selected spatial enumerator and
applies its generated predicates in order to each candidate. Only candidates
passing all generated predicates reach the caller callback. A zero callback
result stops further candidate processing. The routine uses separate callback
lists for candidate filters and geometry/selection work; for example,
`0x00696370` keeps the closest candidate by comparing a computed distance with
query state. Do not interpret that nearest-candidate path as the ordinary
append-all behavior used by Carrion Swarm.

Reproduce the caller and predicate inspection with the temporary Ghidra script
used for this pass:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java \
  0x00C0ECD0 0x00C0F1E0 0x00C31220 0x00C31430 \
  0x0068EA00 0x00696CF0 0x00696A00 0x00696D20 0x00696DD0
```

Reproduce the exact-build static inspection with the temporary script used in
this investigation (not a repository dependency):

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java \
  0x0046EB20 0x0068F9F0 0x0068FA90 0x0068FB30 0x0068FBD0 \
  0x0068FC70 0x0068FD10 0x00C31430 0x00C30BB0 0x00C5C9D0
```

The call-site and vtable evidence can be reproduced with:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java \
  0x00B1CCB0 0x0068F950 0x00BDD5B0 0x00BDD5C0 0x00BDCF70 \
  0x00682450 0x006D4880 0x006677C0
```

`DumpVtableSlots.java` in the same temporary script directory confirms the
poison and Venom Spear entries at `+0x138`, `+0x154`, and `+0x354`. Those
scripts are inspection aids, not checked-in project dependencies.

## Damage payload and receiver path (Retail 1.29.2)

Executable SHA-256:
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`
(PE32 x86, image base `0x00400000`). This exact-build static pass confirms a
shared damage-event layer for `UnitDamageTarget` and Carrion Swarm:

- `0x004AEF70` resolves source/target handles and checks damage, attack, and
  weapon indices. It initializes a stack payload with `0x006A9940`, then
  dispatches through the target object's vtable slot `+0x120`.
- `0x006A9940` stores five stack arguments into payload fields at
  `+0x00..+0x14`, takes the payload destination in ECX, zeroes `+0x1C/+0x20`,
  and returns the payload pointer. It is an initializer, not the applier.
- For CUnit targets, slot `+0x120` resolves to `0x006677C0`. This receiver
  handles unit flags, damage immunity/resistance, attached-object hooks, and
  configured damage bonuses before applying a negative life delta through
  slot `+0x128` (`0x00668DB0`). Generic widget targets use different
  overrides, so the unit path must not be generalized to destructables.
- Carrion Swarm's `0x00C30BB0` independently calls `0x006A9940` and
  dispatches through slot `+0x120`, after missile candidate selection and
  ability-specific checks. JASS damage and Carrion Swarm therefore converge
  on common payload and receiver infrastructure. This does not establish the
  ordinary weapon attack-hit producer.

### Reproduce

From the repository root, verify the executable hash, then run:

```sh
r2 -q -c 'e scr.color=0; af @ 0x004aef70; pdf @ 0x004aef70; pd 28 @ 0x006a9940; pd 100 @ 0x006677c0; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The Ghidra project can independently confirm the CUnit vtable at
`0x00E9C504`, whose slot `+0x120` points to `0x006677C0`. RVAs and
disassembly are only valid for the hash above. The argument semantics and
ordinary attack caller remain unresolved; next compare an attack/on-hit
producer against this receiver and a negative control with no hit.

## UnitDamagePoint and direct life/state setters

The same Retail build shows a second JASS entry path into the damage payload
and CUnit receiver:

- `UnitDamagePoint` wrapper `0x004AEEA0` selects the immediate area processor
  `0x006EB640` or the timestamp-aware dispatcher `0x006EC000`.
- `0x006EC000` queues the supplied operation through `0x006ECBF0` when the
  timestamp is in the future; otherwise it calls `0x006EB640` directly.
  The queued object is initialized with the same argument set, and replay
  reaches `0x006EB640`. Scheduler timing and exact argument semantics remain
  unresolved.
- `0x006EB640` enumerates area candidates, prepares `WidgetDamageData`, and
  passes accepted candidates to `0x006E9ED0`. For positive damage, that helper
  calls the candidate target's `+0x120` virtual method. In the nonpositive
  branch it calls `+0x128`; it also has an ethereal-heal adjustment path.
- Positive UnitDamagePoint damage therefore converges with
  UnitDamageTarget/Carrion Swarm at `+0x120` and, for CUnit, receiver
  `0x006677C0`.

Other inspected setters do not currently establish that same mitigation
path. `KillUnit` (`0x004A1CA0`) and `SetWidgetLife` (`0x004ABEC0`) dispatch
through `+0x124`, which resolves for CUnit to `0x00668CB0`; that method writes
through unit field `+0x1A0` and calls `0x00800FF0` and `0x006BEE40`.
`SetUnitState` (`0x004ABBA0`) reaches `0x0069DD90`; state index 0 also uses
`+0x124`, while index 2 takes another path. The meaning of `+0x1A0` and
whether these paths cause death/events remain unresolved. Do not treat them
as equivalent to damage mitigation or as proof of the ordinary weapon-hit
producer.

Reproduce the key area-damage convergence with:

```sh
r2 -q -c 'e scr.color=0; pd 150 @ 0x006eb640; pd 180 @ 0x006ec000; pd 100 @ 0x006ecbf0; pd 120 @ 0x006e9ed0; q' \
  'data/Warcraft III/Warcraft III.exe'
```

## Shared damage-bonus matrix and attack convergence

Both the CUnit damage receiver `0x006677C0` and ordinary attack calculation
`0x00B23C30` call `0x0067B920`. The helper lazily loads seven eight-entry
Misc rows (`DamageBonusSpells`, `Normal`, `Pierce`, `Siege`, `Magic`, `Chaos`,
and `Hero`) and returns `row[param2 * 8 + param3]`. The exact-build base
`Units\\MiscGame.txt` labels columns `SMALL, MEDIUM, LARGE, FORT, NORMAL,
HERO, DIVINE, NONE`; in the weapon calculation, `param2` is the selected
attack-type row and `param3` is the defender-class column. This confirms a
shared configured damage-multiplier helper across ordinary attacks and the
CUnit spell/direct-damage receiver. The receiver-side type derivation and
whether its event mask selects the spell row or a weapon row remain open.

This identifies shared mitigation configuration, not the poison/on-hit event
producer. Ethereal handling is a separate adjacent path in
`0x006677C0`. The helper `0x006A0630`, also called from the receiver, compares
incoming damage with a unit maximum-value accessor and delegates to
`0x0067B0A0`; it should not be treated as another generic damage-type
multiplier.

Reproduce the caller/decompiler evidence and read the base row labels with:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java 0x0067B920 0x006677C0 0x00B23C30
build/bin/mpqtool -mpq 'data/Warcraft III/War3.mpq' \
  cat Units/MiscGame.txt > /tmp/wc3-MiscGame.txt
rg -n 'DamageBonus|Damage bonus lists' /tmp/wc3-MiscGame.txt
```

## Retail Carrion Swarm target cap, filters, and line width (October 5, 2026)

The follow-up used the same Warcraft III 1.29.2 Retail executable (SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`) and
TFT source map `War3xLocal.mpq:Maps/FrozenThrone/Campaign/OrcX01.w3x`.
`War3xLocal.mpq` SHA-256 was
`ba7b928c7bf34fb2a1675aeddfdadcfdc7146966ae7ebf36b0980486b7dd9c57`.
The map's six cinematic availability gates do not name `ACca`; the probe
started after `Trig_Intro_Skipped_Actions` entered gameplay and explicitly
made `ACca` available to Player 0. Retail archives were never edited.

### Controlled result

The original Carrion Swarm v6/v7 manifests are absent from this checkout. The
setup, placements, timing, controls, and results are recorded below; the
checked-in `ability_batch_tft` manifest is a template for preparing a fresh
map copy.
Each test used a new map extracted from the same source archive, injected
helpers before `Trig_Intro_Skipped_Actions`, and called the probe immediately
after its `ConditionalTriggerExecute( gg_trg_Gameplay )`. The tool verified
that each prepared MPQ contained exactly one root `war3map.j` whose bytes
matched the staged JASS. The untouched map reached OrcX01's “To Tame a Land”
chapter card before the prepared copy was launched.

The caster was a newly created Player 0 `nnwq` with native stock `ACca` at
rank 1. Both weapon slots were set to zero, acquisition range was reduced, and
the caster was held in place. Targets were paused `hfoo`, `hgry`, or `hhou`
units with 10,000 life. A spell-effect trigger recorded the ability rawcode
and target point; per-target `EVENT_UNIT_DAMAGED` triggers recorded caster
source, current order, damage amount, and sampled life. The point-order
boolean was recorded but was not used by itself as proof of acceptance.
Successful casts also emitted `EVENT_PLAYER_UNIT_SPELL_EFFECT` for rawcode
`1094935393` (`ACca`) with current order `852218` (`carrionswarm`).

The v6 probe searched candidate origins on a 128-unit grid from −768 to +768
on both axes around Rexxar. For each candidate it tried east, west, north and
south, in that order. Its lane validator checked the caster, point, all six
line positions, the mixed-target positions, and every symmetric lateral
position before it accepted a candidate. It found origin `(-3584,-7328)`
facing west. `IsTerrainPathable`
returns false for walkable positions, so the probe used its negation for the
pathable flag. It also logged both requested and actual `GetUnitX/Y` after
`CreateUnit`; this catches Warcraft moving a unit that was requested on
unpathable terrain.

The v6 cast phases waited 15 seconds between orders. An earlier iteration
which retried after six seconds got `IssuePointOrder=false` and no spell-effect
event; all six v6 casts spaced 15 seconds apart were accepted and each fired
the spell-effect event. This establishes a working repeat interval for this
probe, not the exact native cooldown rule.

| Probe phase | Setup | Retail observation |
|---|---|---|
| Six hostile ground units | Six Player 12 `hfoo` centers on the pathable axis, 100–600 units from the recorded origin. Requested and actual positions matched. | The first four targets each took 75 damage; the last two took none. The four hits sum to 300. |
| Mixed on-axis target types | Enemy ground at 150, allied ground at 300, enemy flying `hgry` at 450, and enemy structure `hhou` at 600. | Enemy ground and enemy air each took 75; allied ground and structure life did not decrease. The structure was displaced about 40 units from its requested position by placement, still within the separately demonstrated hit lane. |
| Symmetric lateral controls | A centered enemy `hfoo` and a pair at ±80, ±160, ±240, or ±320 units from the axis, one pair per cast. Actual positions matched the requested points. | Center and ±80/±160 targets each took 75. At ±240 and ±320 only the centered unit took 75. For this unit type and terrain, the effective centerline reach is bracketed between 160 and 240 units; this is not an exact collision-radius measurement. |
| Distal target alone | One Player 12 `hfoo` at the exact 600-unit location left untouched in the six-target phase; no nearer targets were present. | The target took 75 damage. `EVENT_PLAYER_UNIT_SPELL_EFFECT` was at 0.507 s and the damage event at 0.906 s on the probe clock (about 0.399 s later). This rules out the six-target result being caused only by the wave ending before that distal point. |

The combined evidence supports a four-target per-cast cap for stock TFT
`ACca`: six pathable hostile ground targets were in reach, the first four
received the authored 75 damage, and the fifth and sixth were untouched; the
600-unit target was then damaged when tested alone. The 300 total agrees with
the stock `ACca` resolved tooltip. The tested runtime mask admits enemy ground
and enemy air, while excluding the tested allied ground unit and structure;
the tooltip's “enemy land units” wording does not describe the observed air
result. These conclusions apply to the tested stock TFT `ACca` row and Retail
build only.

This does not determine exact `DataC`/`DataD` travel-field meanings or velocity,
the exact line-width boundary, reversed target-creation ordering, repeat hits
across a longer wave, or behavior of `ACcv`, `ACc2`, `ACc3`, and the absent
`ACc1` row. The isolated distal measurement is a coarse travel observation,
not a full trajectory or exact speed measurement. Frida was unnecessary for
these externally visible outcomes. A zero from the shared SimpleSpell
validator remains fallback-validation evidence, not cast acceptance; JASS
spell-effect and damage-source events are the behavioral evidence here.

The retained run artifacts were under `/tmp/wc3-ability-rest/run15/` and
`/tmp/wc3-ability-rest/run16b/`. The reviewed raw Preload outputs were
`run15/result.txt` (SHA-256
`3f0f1b445d0fe09972f8e0785c362cbfc9284f09b3ef8d9c216e8282dd18a44c`) and
`run16b/result.txt` (SHA-256
`37d017903aa376a6f24fa69bb754402fd1a60f123666a19a9f12270c78f06f65`). The
gameplay screenshot for the six-phase lane probe is
[`WC3ScrnShot_100526_102322_01.png`](../../../../screenshots/tmp/WC3ScrnShot_100526_102322_01.png)
(RGB, 1024×576). Control screenshots are
`WC3ScrnShot_100526_102154_01.png` and
`WC3ScrnShot_100526_103045_01.png` under `screenshots/tmp/`.

### Reproducing these Retail probes

The exact Carrion Swarm v6/v7 manifests are not checked in, so those runs cannot
be replayed byte-for-byte from this checkout. For a new probe, create a
scenario-specific manifest and JASS fragments under a new
`tools/retail_probes/<scenario>/` directory, using the checked-in
[`ability_batch_tft` manifest and helpers](../../../../tools/retail_probes/ability_batch_tft/manifest.json)
as a template. Keep archive and executable paths relative to that manifest,
set a fresh `result_file`, and prepare a new output directory:

```sh
make mpqtool
python3 tools/wc3_retail_probe.py prepare \
  tools/retail_probes/carrion_swarm_replay/manifest.json \
  /tmp/wc3-carrion-v6
```

Preparation extracts the untouched control, stages the JASS edit, replaces
only the root `war3map.j` in a copy, checks the root member list, and byte
compares the embedded script to the staged script. Inspect `probe.json`,
`stage/war3map.j`, and the helper's exact trigger anchor before launch. Use a
separate manifest and fresh output directory for the distal-only scenario.

Launch the control first and visually check the expected chapter card. Then
exit Retail, launch the prepared map with `--control-confirmed`, click near
`(642,600)`, wait for the cinematic, press Escape, and let the JASS timer
finish. Use one persistent Xvfb shell for both launches and the manual inputs;
the inner shell must stay open until Retail exits or the virtual display goes
away. The path below is the prefix used for the recorded run; substitute the
selected Wine prefix and Wine user on another machine:

```sh
WINEPREFIX=/home/agent/.wine-war3 xvfb-run -a \
  -s '-screen 0 1280x720x24' bash --noprofile --norc -i
```

Run these commands inside that shell. The first launch is the untouched
control; print and inspect a Retail screenshot of the expected “To Tame a
Land” chapter card before recording the confirmation:

```sh
export WINEPREFIX=/home/agent/.wine-war3 WAYLAND_DISPLAY= WINEDEBUG=-all
PROBE=/tmp/wc3-carrion-v6
python3 tools/wc3_retail_probe.py launch "$PROBE" --control \
  --wine-prefix "$WINEPREFIX"
sleep 30
xdotool key Print
```

Convert and inspect the fresh control screenshot in another shell. Continue
only after it shows the expected chapter card; then return to the persistent
Xvfb shell and start the prepared map:

```sh
wine taskkill /IM "Warcraft III.exe" /F
python3 tools/wc3_retail_probe.py launch "$PROBE" --control-confirmed \
  --wine-prefix "$WINEPREFIX"
```

The tool runs the Retail executable with `-window -graphicsapi OpenGL2
-loadfile` and converts the map path with `winepath -w`. Do not switch to
Custom Game or pass a Unix map path directly. Wait for the chapter card,
click near `(642,600)`, wait for the cinematic, then press Escape:

```sh
sleep 30
xdotool mousemove 642 600 click 1
sleep 20
xdotool key Escape
```

If using an already-running Xvfb instead, export both its `DISPLAY` and
matching Xauthority file. For the persistent display used here they were
`DISPLAY=:101` and `XAUTHORITY=/tmp/xvfb-run.4Y8qBw/Xauthority`. Omitting
`XAUTHORITY` produced `Authorization required` and `nodrv_CreateWindow` even
though Xvfb and Retail existed. That authorization path is session-specific;
obtain it from the active Xvfb command line. Keep the Xvfb shell alive until
the prepared map finishes.

For Retail screenshots, focus the game window, send `xdotool key Print`,
confirm a newly timestamped TGA under
`$WINEPREFIX/drive_c/users/<user>/Documents/Warcraft III/ScreenShots/`, then
run:

```sh
/opt/openrealm-tools/frida-venv/bin/python \
  tools/convert_wc3_retail_screenshot.py \
  --wine-prefix /home/agent/.wine-war3 --wine-user agent
```

The converter validates an RGB PNG under `screenshots/tmp/` before deleting
the TGA. Do not use XWD conversion for Retail evidence. After the timer's
result is written, run:

```sh
python3 tools/wc3_retail_probe.py capture /tmp/wc3-carrion-v6
```

`ready_for_review` only means the result is fresh and required markers exist;
inspect raw `result.txt` and check target positions, spell-effect events,
nonzero damage events, mana, and life yourself. Retail often remains running
after `PreloadGenEnd` and can consume a full CPU core. Close that exact
`Warcraft III.exe` process before another launch; do not kill the shared Wine
server or Frida server.

### Native analysis for the tested Carrion Swarm order

Use native tools to localize and inspect code paths; use the JASS events and
damage observations above to establish the visible game behavior. Record and
check the exact executable hash before using any address. This run used the
1.29.2 Retail executable SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`, PE32
x86, preferred image base `0x00400000`. The checked-in TFT class registry was
generated from a different executable hash (`a1950f...`), and
`tools/extract_wc3_ability_classes.py` correctly rejects this run's hash.
Treat that registry as a lead; re-check the relevant bytes and addresses in
the executable being traced.

First resolve the rawcode to the implementation code from the same game data:

```sh
build/bin/ability_audit -data 'data/Warcraft III' -raw ACca
```

The TFT row reports `ACca code=AUcs`, and the registry associates `AUcs` with
`CAbilityCarrionSwarm`, whose parent is `CAbilitySimpleSpell`. A rawcode hit
alone is not enough to choose a native hook. Confirm the registration in the
exact executable. For this run, the relevant radare2 output is reproducible
with:

```sh
r2 -q -c 'e scr.color=0; iI; iS; pd 18 @ 0x00C31370; pd 32 @ 0x00B28980; q' \
  'data/Warcraft III/Warcraft III.exe'
```

At `0x00C31370`, the registration setup passes descriptor `0x011B7F44`, calls
the parent getter at `0x00B2B1F0`, pushes the immediate FOURCC `AUcs`, and calls
the registry at `0x007F6360`. This is an exact-build check of the mapping, not
a claim that adjacent abilities share behavior. `iS` also reports the current
PE section ranges; derive file-offset-to-VA conversions from those ranges
rather than assuming another executable has the same layout. The current
`.text`, `.rdata`, and `.data` mappings are respectively `+0x400C00`,
`+0x401200`, and `+0x401400` from file offset. Confirm each derived mapping
against the section table for the current file.

For a reproducible Ghidra inspection, reuse the checked-in exact-build project
and function inventory in `screenshots/ghidra/`. Its project is
`screenshots/ghidra/WarcraftIII`; its checked-in `functions.csv` confirms
function boundaries but does not contain decompilation or cross-references.
The previously referenced `Wc3DumpFunction.java` and
`Wc3InspectAddresses.java` scripts are not present in this checkout. The
inventory was exported with `ExportFunctionInventory.java`; do not reimport
or reanalyze the executable merely to inspect addresses:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath "$PWD/screenshots/ghidra" \
  -postScript ExportFunctionInventory.java /tmp/wc3-functions-check.csv
```

The export script only enumerates functions. Use the Ghidra GUI on this same
project for decompilation and references; use radare2 for reproducible
instruction/cross-reference checks until focused Ghidra inspection scripts
are checked in. Always verify x86 `thiscall` receiver (`ECX`), stack argument
order, and branch conditions in disassembly.

For data and RTTI references, use the Ghidra GUI or radare2 against the same
exact-build project/binary. The formerly cited `Wc3InspectAddresses.java`
helper is absent from this checkout:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath "$PWD/screenshots/ghidra" \
  -postScript ExportFunctionInventory.java /tmp/wc3-functions-check.csv
```

The native Carrion Swarm path can be followed farther than the target-hit
method. Factory `0x00C2F890` creates a `CMissileCarrionSwarm` through
constructor `0x00C303C0`, which installs missile vtable `0x00F88334`. Setup
function `0x00C2ED00` populates the missile state and calls update routine
`0x00C31430`. The vtable callback at `0x00C2F040` also calls that routine for
event value `0xD01C1`. In `0x00C31430`, candidate units are collected through
`0x00C31290`/`0x00C31220`; the callback has a 64-entry candidate-list guard,
checks `0x00C31120` and `0x006ADB90`, and the update loops the resulting list
and calls `0x00C30BB0` for each candidate. This statically verifies the
missile scan and per-candidate damage path in this executable. The 64-entry
buffer guard is not the ability's observed 300 total damage cap.

The name-reference function at `0x00C30BB0` performs another target check,
selects an indexed per-level value, initializes a damage/event payload with
`0x006A9940`, then dispatches that payload through the target object's vtable
slot `0x120`. `0x006A9940` is a payload initializer, not the damage-applier.
The opaque predicates, payload fields, field-to-AbilityData mapping, exact
travel/width rules, and source of the 300 cap remain unresolved. Static
inspection has not yet settled those contracts, so the existing JASS results
remain useful for the observed cap, target classes, and width bracket. To
reproduce the path, run the addresses above in the cached Ghidra project.

## Ordinary weapon hit investigation status

The ordinary attack producer has not yet been shown to converge on
`0x006A9940` / target slot `+0x120`. Exact-build inspection of attack
calculation `0x00B23C30` finds calls to target-slot selection `0x00B1EC60`,
attack-state helpers, and the shared configured damage-bonus lookup
`0x0067B920`; its body does not call `0x006A9940` or the CUnit receiver
`0x006677C0`. This is a static negative for this calculation routine, not a
claim that no later attack-impact routine builds a damage payload. Its direct
callers include `0x00B1BFD0`, `0x00B1C1E0`, and `0x00B249C0` (the latter calls
it in two branches). The split remains: attack calculation is confirmed, the
subsequent ordinary impact producer is not.

The next attack-state stage `0x00B1BFD0` stores a 64-bit score and selected
target in a shared state record; its default scorer is `0x00B23C30`, with an
optional per-record callback override. The impact-effect routine is
`0x00B1CCB0`, reached from attack update callback `0x00B21DD0`. It initializes
a damage payload with `0x006A9940` before switching on the attack-type field
at ability object `+0xE0 + slot*4`; the payload's configured damage value is
read from `+0xEC + slot*4`, with attack/weapon flags and type-specific fields
also supplied. For attack types 1 and 4, it calls `0x006ED680` (impact gate),
then source attached-ability dispatcher `0x0068F950`. A handled ability
callback suppresses the normal damage fallback. If unhandled, the routine
dispatches the prepared payload through target slot `+0x120` (CUnit target:
`0x006677C0`); a separate target route may apply when the extra target
pointer is present. This establishes a normal, direct attack impact path to
the shared CUnit receiver. Other attack types 2, 3, and 5–8 construct or
schedule missile/other effect objects, so their eventual impact paths still
need individual tracing.

The attack update wrapper and type switch can be reproduced with the existing
Ghidra project:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java 0x00B1BFD0 0x00B21DD0 0x00B1CCB0
```

Further exact-build inspection confirms these adjacent dispatch points:

- Attack event `0xD01C1` is dispatched by `0x006EF880` to attached objects
  through virtual slot `+0x364`; it later invokes slot `+0x36C` on the same
  attached object. Carrion Swarm's concrete slot implementation is
  `0x00C2F040`, which calls its missile update `0x00C31430`. This confirms a
  scheduled missile-update route, not ordinary weapon damage.
- Poison callback `0x00BDCF70` is slot `+0x354` on the RTTI-identified
  `CAbilityPoisonAttack` and `CAbilityVenomSpear` vtables. The ordinary hit
  route is established: `0x00B1CCB0` calls `0x0068F950`, which dispatches
  category `0x28` to `0x00BDD5C0`; this invokes ability slot `+0x354`, then
  sends the damage payload through target slot `+0x120` unless handled.
- CUnit damage receiver `0x006677C0` walks a linked set of attached objects
  and invokes slots `+0xF8/+0xFC` for objects that pass its predicates before
  applying further damage adjustments. This is a promising on-hit extension
  point for recipient-side damage modifiers. Poison Attack/Venom Spear use
  inherited no-op methods at these slots, so their source-side on-hit path is
  the separate ability `+0x354` callback dispatched by `0x0068F950`. Known
  recipient-side implementations include Spirit Link (group 2, sharing path)
  and Mana Shield (group 5, depletion/absorption path). The registered-group
  identities and exact phase semantics remain partly unresolved.
- The receiver's bitset parameter accumulates nonzero `+0xF8` return values.
  Later it checks matching phase IDs 0 through 8, re-enumerates attached
  objects, and calls `+0xFC` for objects returning that phase. This is a
  recipient callback protocol, not proof of the ordinary attack source's
  impact producer.
- RTTI confirms `CBuffAuraThorns` vtable `0x00F93DB0` returns group `1` from
  `+0xF8` (`0x00C46E20`), so the receiver invokes `+0xFC` (`0x00C46E30`)
  immediately. That callback checks the event-referenced object, calls general
  validation `0x00682180`, derives an amount from the damage/event context and
  clamps it against global float `0x0112D810`, then initializes a payload with
  flag `0x00100000` and dispatches it through the referenced object's `+0x120`.
  This is a concrete recipient-side
  damage redispatch path (consistent with Thorns reflection); exact payload
  flag semantics and amount scaling remain unresolved. It can therefore
  recurse into the shared damage receiver when the referenced object is a
  CUnit, unlike Poison/Venom's source-side `+0x354` application callback.
- RTTI confirms `CBuffFrostArmor` vtable `0x00FA606C` also returns group `1`
  (`+0xF8 = 0x00C67D50`, `+0xFC = 0x00C67D60`). Its handler proceeds only when
  the payload's byte at `+0x0C` has bit 0 clear, its field at `+0x14` is
  `0x10`, the event-referenced object passes virtual `+0x11C`, and the
  `0x00682180` validation call returns zero. It then uses the referenced
  object as the buff recipient: the default rawcode helper returns `Bfro`
  (overridden by the buff object's `+0xE0` value when nonzero), lookup
  `0x006D6570` refreshes an existing instance through `+0x368`, or a new object
  is created/configured through `0x00C11C90` / `+0x32C`, applied through
  `+0x364`, and attached by `0x006D4880`. This verifies a damage-phase
  recipient callback that applies or refreshes Frost Armor on the event
  referenced unit; the event-field semantics and exact eligibility meaning
  remain unresolved.
- RTTI confirms `CBuffAntiMagicShellTwo` vtable `0x00F46B14` returns group `5`
  from `+0xF8` (`0x00BABCD0`), with handler `0x00BABCE0` at `+0xFC`. The
  handler runs when event field `+0x20` is `0` or `4`, provided event field
  `+0x14` is not `0x04000000` and the owner lacks unit flag
  `+0x164 & 0x40000000`. It caps event amount at buff float `+0xD4`, subtracts
  that amount from the buff's `+0xD4` value through its numeric wrapper, then
  calls `0x0046D630` and removes the attached status through `0x006D8530` when
  that helper reports its terminal condition. This establishes the Retail Bam2
  recipient-side damage-consumption path. Exact event field meanings, terminal
  condition semantics, overflow behavior at this callback boundary, and the
  relationship to higher-level spell damage processing remain open.
- `CBuffRegeneration`, `CBuffRegenLife`, and `CBuffRegenMana` vtables
  `0x00F663AC`, `0x00F66730`, and `0x00F66ABC` share `0x00BEE5C0/0x00BEE5D0`.
  The phase callback returns 1. The handler removes the attached instance
  through `0x006D8530` only when buff flags `+0x20 & 0x201` are set and payload
  fields pass its bit/enum/float checks. Field semantics are unresolved, so
  this is a callback/removal contract, not a verified regeneration-on-damage
  behavior.
- `CBuffDrainBonus`, `CBuffDrainBonusLife`, and `CBuffDrainBonusMana` vtables
  `0x00F72A28`, `0x00F72D90`, and `0x00F730F8` share
  `0x00C07630/0x00C07640`; the phase callback returns 5. The handler gates on
  buff flags `+0x20 & 0x100`, resolves an object from payload
  `+0x00`, rejects when payload byte `+0x0C & 0x10` or helper `0x00B48580`
  says so, and computes a clamped numeric update using payload `+0x10`, buff
  `+0x114`, and helpers `0x0099FFE0`, `0x009A00B0`, `0x00800D80`,
  `0x006B80E0`, and `0x00C0AF90`. It does not call damage dispatch or removal;
  a drain-related damage role remains an RTTI-based inference.
- `0x006B80E0` is a shared bounded numeric-state update used by recipient
  callbacks. It compares an incoming float against the state object at `this+0x10`;
  one branch updates `+0x10` from a second input, while the other computes a
  difference through `0x009A00B0`. Both paths update `this+0x18` relative to
  the sentinel global `0x0112D88C`. Confirmed callers in this callback set are
  Anti-Magic Shell Two (`0x00BABCE0`), DrainBonus (`0x00C07640`), Sanctuary
  (`0x00C701C0`), and base Anti-Magic Shell (`0x00BAB860`). This establishes
  shared numeric-state behavior; the wrapper's higher-level meaning remains
  unresolved.
- `CBuffSleep` vtable `0x00F1D15C` uses `0x00B38A90/0x00B38AA0`; phase callback
  `+0xF8` returns 1. The handler compares payload float `+0x10` with global
  `0x0112D88C`, resolves the owner (or fallback owner), and checks attached
  rawcodes `BUst` and `BUps` through `0x006D6570`. If neither lookup succeeds,
  it invokes the buff object's virtual `+0x354` with zero and the same global
  pointer. The callback's event meaning and effect are unresolved. The
  RTTI-linked `CBuffDarkConversion` vtable shares the phase method but uses a
  separate `+0xFC` implementation `0x00B39260`, which is a zero-return stub.
- `CBuffBerserkerRage` vtable `0x00F7C1F4` uses `0x00C17140/0x00C17150`;
  the phase callback returns 8. The handler reads buff float `+0xF8`, clamps it
  to the interval bounded by global floats `0x0112D88C` and `0x0112D810`, then
  adds that value through numeric helper `0x0099FFE0` to incoming payload
  fields `+0x10` and `+0x18`. The incoming payload is modified in place; exact
  damage-field names and value interpretation remain unverified.
- `CBuffAntiMagicShell` vtable `0x00F4679C` uses `0x00BAB850/0x00BAB860`;
  the phase callback returns 5. The handler resolves payload object `+0x00`,
  checks owner flag `+0x164 & 0x40000000` clear and payload enum `+0x20 == 4`,
  then sends buff numeric state `+0xD4` through shared updater `0x006B80E0`.
  The exact effect of this state write remains unresolved; it is structurally
  distinct from Bam2's amount-capped depletion callback at `0x00BABCE0`.
- `CBuffAvatar` vtable `0x00F6EFA8` uses `0x00BFEAE0/0x00BFEAF0`; the phase
  callback returns 5. The handler resolves the event object, checks owner flag
  `+0x164 & 0x40000000` clear and payload enum `+0x20 == 4`, then passes buff
  value `+0xF0` to `0x006B80E0`. Its gameplay role and payload meaning remain
  unresolved.
- `CBuffSanctuary` vtable `0x00FAA6C8` uses `0x00C701B0/0x00C701C0`; the phase
  callback returns 5. The handler resolves payload object `+0x00`, requires
  owner flag `+0x164 & 0x40000000` clear and payload enum `+0x20 == 4`, then
  clamps buff value `+0xDC` through `0x006B80E0`. Exact payload semantics and
  whether this is a healing or damage adjustment remain unresolved.
- `CBuffMirrorImage` and `CBuffItemIllusion` vtables `0x00F86E90` and
  `0x00F87204` share `0x00C2C160/0x00C2C1F0`; the phase callback returns 3.
  The handler reads buff value `+0xE4` and adds it through `0x0099FFE0` to
  incoming payload fields `+0x10` and `+0x18`. This confirms shared in-place
  payload modification across both RTTI classes; value semantics remain open.
- `CBuffIncinerate` vtable `0x00FB86B4` uses `0x00C8EA00/0x00C8EA10`; the
  phase callback returns 8. Its
  handler accepts payload enum `+0x14` values `0x10` or `0x20`, resolves the
  referenced object at payload `+0x00`, and looks up rawcodes `ANic` and
  `ANia` through `0x006D6570`. Existing candidates must pass `+0x3C` and
  virtual `+0x268` checks. It then updates a numeric value at payload `+0x10`
  using buff values `+0xE0/+0xE8` and helpers `0x009A1620`, `0x0099FFE0`, and
  `0x009A01C0`. The exact payload meaning and gameplay effect remain open.
- Carrion Swarm impact `0x00C30BB0` does converge on `0x006A9940` and slot
  `+0x120`, but it is an ability-specific projectile path.

Inspect the recipient callbacks and verify their RTTI-linked slots with the
cached project. `DumpVtableSlots.java` reports `+0xF8/+0xFC` for each vtable:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java \
  0x00C46E20 0x00C46E30 0x00C67D50 0x00C67D60 \
  0x00BABCD0 0x00BABCE0 0x00BEE5C0 0x00BEE5D0 \
  0x00C07630 0x00C07640 0x00C8EA00 0x00C8EA10 \
  0x00682180 0x006A9940 \
  0x006D6570 0x00C11C90 0x006D4880 0x006D8530 0x006677C0

/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript DumpVtableSlots.java \
  0x00F93DB0:0 0x00FA606C:0 0x00F46B14:0 0x00F663AC:0 \
  0x00F66730:0 0x00F66ABC:0 0x00F72A28:0 0x00F72D90:0 \
  0x00F730F8:0 0x00FB86B4:0
```

Ordinary direct-hit types 1/4 are confirmed to reach the shared receiver when
source ability dispatch does not handle the event; ordinary projectile attack
impact remains unresolved. Poison and Cold Arrow `+0xF8/+0xFC` slots have
already been inspected: Poison/Venom inherit no-op base callbacks, while Cold
Arrow's splash-missile entries are unrelated missile methods. Next resolve
concrete `+0x364` callback implementations, then compare their source/target
and damage call sequences with melee hits and normal ranged projectile
impacts. A weaponless or paused-unit negative control will help separate
attack scheduling from hit resolution. Do not equate event `0xD01C1`, the
poison callback, or Carrion Swarm impact with the ordinary hit dispatcher.

Reproduce the current event bridge and callback sites with:

```sh
r2 -q -c 'e scr.color=0; pd 70 @ 0x006ef880; pd 175 @ 0x00bdcf70; pd 64 @ 0x00c30bb0; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The shared `CAbilitySimpleSpell` validation function for this exact build is
VA `0x00B28980`, RVA `0x00728980`. `tools/frida/wc3_carrion_swarm_order_trace.js`
hooks that function read-only, filters the first stack argument to
`OrderId("carrionswarm")` (`0x000D00FA`), and records pointer values and the
integer return. The disassembly shows a zero result can select further
validation; it does **not** mean the order was accepted. The JASS
`EVENT_PLAYER_UNIT_SPELL_EFFECT` and damage-source events are the acceptance
and effect evidence. On the later v7 single-target run the order-validator
trace saw two caller paths, each twice: caller `0x00CB6217` returned `0xDD`,
and caller `0x00C2FAA5` returned `0`. The successful JASS cast shows these
values cannot be read as a single “accepted” boolean. The direct caller at
`0x00C2FAA5` tests the SimpleSpell result and sends zero into a position
fallback; the other caller is a separate virtual-validation path. This trace
does not identify the receiver's concrete class or prove missile travel or
collision behavior.

The v7-specific JASS manifest is not checked in. To repeat the single-target
Frida check, first prepare that scenario with a new manifest based on the
ability-batch template, then start the matching server after Retail is open.

Run the rest of this sequence inside the same persistent Xvfb shell. For this
fresh output directory, launch its own untouched control and inspect a Retail
Print screenshot before continuing:

```sh
export PROBE=/tmp/wc3-carrion-frida
python3 tools/wc3_retail_probe.py launch "$PROBE" --control \
  --wine-prefix "$WINEPREFIX"
sleep 30
xdotool key Print
```

Convert and inspect the fresh control TGA in another shell. Continue only
after confirming the expected “To Tame a Land” chapter card, then return to
the persistent Xvfb shell:

```sh
wine taskkill /IM "Warcraft III.exe" /F
python3 tools/wc3_retail_probe.py launch "$PROBE" --control-confirmed \
  --wine-prefix "$WINEPREFIX"
sleep 30
wine /opt/openrealm-tools/frida-server.exe --listen=127.0.0.1:27043 \
  >"$PROBE/frida-server.log" 2>&1 &
FRIDA_SERVER_PID=$!
/opt/openrealm-tools/frida-venv/bin/python \
  tools/frida/wc3_retail_preflight.py "$PROBE" \
  --remote 127.0.0.1:27043 --output "$PROBE/frida-preflight.json"
TRACE="$PROBE/frida-carrion.jsonl"
/opt/openrealm-tools/frida-venv/bin/python \
  tools/frida/trace_wc3_retail.py "$PROBE" \
  --agent tools/frida/wc3_carrion_swarm_order_trace.js --seconds 45 \
  --output "$TRACE" &
TRACE_PID=$!
until rg -q 'agent-ready' "$TRACE" 2>/dev/null; do sleep 0.2; done

After `agent-ready`, perform the chapter-card click and Escape sequence, wait
for the probe timer, send Print if a screenshot is needed, and wait for the
trace. Then capture the fresh `PreloadGen` result and inspect both raw files:

```sh
wait "$TRACE_PID"
python3 tools/wc3_retail_probe.py capture "$PROBE" --timeout 180
rg 'carrionswarm-validator|agent-ready' "$TRACE"
```

For this probe the native evidence is only that the stock `carrionswarm`
order reached the shared validator and which return value it produced. Pair
it with the JASS record for `ACca`, current order `852218`, spell-effect event,
target damage, and target positions. Keep the validator result, order-issue
boolean, spell-effect event, and actual damage as four separately recorded
observations; none is a substitute for another. The passive trace records
addresses/pointers and results but does not dereference game objects or
change arguments.

To trace the class-specific damage routine, prepare another fresh output
directory from the same v7 manifest, launch and visually check its control,
then launch the prepared map and start the same Frida server and identity
preflight. Use a new trace filename and this agent:

```sh
TRACE="$PROBE/frida-carrion-damage.jsonl"
/opt/openrealm-tools/frida-venv/bin/python \
  tools/frida/trace_wc3_retail.py "$PROBE" \
  --agent tools/frida/wc3_carrion_swarm_damage_trace.js --seconds 45 \
  --output "$TRACE" &
TRACE_PID=$!
until rg -q 'agent-ready' "$TRACE" 2>/dev/null; do sleep 0.2; done
```

After `agent-ready`, click the chapter card, wait for the cinematic, press
Escape, and allow the probe timer to finish. Then collect the JASS result and
check the trace:

```sh
wait "$TRACE_PID"
python3 tools/wc3_retail_probe.py capture "$PROBE" --timeout 180
rg 'carrion-damage-target|agent-ready' "$TRACE"
```

The agent hooks VA `0x00C30BB0` / RVA `0x00830BB0`, logs the receiver and three
stack argument pointers without dereferencing them, and is pinned to the
executable hash above. In the observed run it entered and left this routine
once (caller `0x00C317AF`, elapsed 7 ms). The paired JASS record showed an
accepted point order, a spell-effect event at 0.508 s, and 75 damage at
0.907 s to the single distal target. This confirms the candidate Carrion
damage routine ran during the tested hit. It does not establish the native
argument structures, exact cap or line boundary, or behavior of other
ability aliases.

The focused trace artifacts were in `/tmp/wc3-carrion-frida/`. The JASS
result has SHA-256
`c21dee8b7ca2da6091d4fb0fdf64c568068b7d3648a397cc81e8b824050ff7a2`; the
damage-target trace has SHA-256
`808a2b0ee2007c8f21c91f9bdee78405b9d1e120069a7b8f34d725a1060eba30`. The
preflight checks transport and process identity only; spell-effect and damage
records remain the gameplay evidence. The v7 helper logs every damage event
for the watched target, without filtering its source, so the later zero-amount
events with source order 0 must not be counted as Carrion Swarm hits.

### Reusing the method for another ability

Start by extracting the actual campaign map and reading its `.j`/`.jass`
script. Check ability-availability and tech gates, identify the callback that
enters gameplay, and use that map's exact callback name and post-gameplay
anchor. Similar callback names are not interchangeable. The OrcX01 probe
starts after `Trig_Intro_Skipped_Actions` calls the Gameplay trigger; the
Prologue uses a different callback.

Build one controlled group per question. Add stock ability rows to a new
caster after gameplay begins, pause unrelated units and each target, remove
caster weapon damage when testing spell damage, and record starting owners,
rawcodes, positions, life, mana, ability rank, order, and the requested target
point. Register `EVENT_PLAYER_UNIT_SPELL_EFFECT` and per-target
`EVENT_UNIT_DAMAGED`, including `GetEventDamageSource`, `GetEventDamage`, and
the source's current order. Use a separate long-running timer with
`TimerGetElapsed` when event-to-event timing matters; periodic samples alone
only bound the event to the timer interval. `EVENT_PLAYER_UNIT_SPELL_EFFECT`
proves a cast reached that event; `IssuePointOrder`'s boolean alone does not.
Do not infer attack-versus-spell solely from current order. The installed
1.29.2 `common.j` lacks `BlzGetEventIsAttack`.

Check `not IsTerrainPathable(x,y,PATHING_TYPE_WALKABILITY)` at every intended
ground position before spawning. Immediately log `GetUnitX/Y` after
`CreateUnit`; Retail relocates units requested on blocked ground, which can
invalidate a lane or radius comparison. For a target mask, put one candidate
of each type on the same verified line and keep the count below any suspected
cap. For a cap, compare a dense group with a distal target tested alone. For
line width, put a center control and only one symmetric pair per cast, keeping
the number of targets below the known cap. Compare distances in both
directions and report a bracket unless intermediate points are tested.

Set cast separation from observed cooldown recovery; do not interpret a
rejected retry as a target-mask result. A temporary Carrion Swarm iteration
used a southbound fallback even though the path was blocked after 400 units.
Retail moved the later targets and rejected the next cast. That run was
discarded. The v6 lane search instead tested all intended points before
selecting the origin. If setup markers are present but the behavior is
unexpected, review the raw output, object data, map gates, and verification
docs before changing the launch route or drawing a conclusion.
