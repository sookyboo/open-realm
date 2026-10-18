# Retail ability targeting probes

Detailed controlled JASS experiments and replay steps for target outcomes. For current conclusions and open questions, see [verification status](../ability-verification-review.md).

## Target validator static disassembly (Retail 1.29.2)

Executable SHA-256:
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`
(PE32 x86, image base `0x00400000`). In this build, `0x00682180` has a
two-stage structure:

1. It calls `0x00682210` and, only when that returns zero,
   `0x006822E0`, passing the same `this` context, candidate and extra
   argument. Either nonzero result short-circuits.
2. It traverses a global linked registry using accessor `0x007FC7E0`.
   For each entry, it calls virtual slot `+0x26C` with the candidate and
   extra argument; the first nonzero result is returned.
3. If all checks return zero, it returns zero.

The iterator accessor resolves the current node's stored pair through
`0x004707F0`, checks an entry state at `+0x20`, and returns its value at
`+0x54`. The registry's purpose and live membership are not established.
Phoenix Fire's candidate callback at `0x00C0F1E0` is a verified direct caller;
Ghidra full analysis recorded 64 direct call references from 64 functions.
Thus this is broad validation infrastructure, but the set of callers should
not all be assumed to represent spell casts. Return values are internal
rejection results, not a universal acceptance boolean.

The `CMissileLightningAttack` candidate callback `0x00BDB8E0` reaches
`0x00682180` indirectly through missile-specific predicate `0x00BDC070`.
Before that call, the predicate checks missile lifetime/state, candidate
relationship through `0x00682450`, candidate-specific virtual slot `+0x3F4`,
and another missile virtual check at `+0x3E4`. It then obtains a missile-side
value through slots `+0x350`/`+0x3F0` and calls `0x00682180` on the candidate
unit with that value. Thus the general rejection-code validator is reused
inside a missile candidate gate; it is not the entire projectile eligibility
decision. Confirmed statically from vtable `0x00F5D1B4` slot `+0x158` and
disassembly; runtime invocation remains unverified.

The two built-in predicates have more specific static behavior than their
provisional labels suggest. `0x00682210` returns zero for null candidates or
when candidate slot `+0xD8` reports nonzero. Otherwise it checks source flag
`+0x164 & 0x100`, candidate slots `+0x1F0`, `+0x1D8`, `+0x1F8`, `+0x1FC`,
and `+0x20C`, a source field selected from `+0x264/+0x268`, a candidate
context at `+0x30`, and the configured `MagicImmunesResistUltimates` value.

The latest Amim runtime operand capture is preserved at
`build-re/ability-re/ANfl-invulnerability-readback-01/runtime/trace-case2-amim-operands.jsonl`.
The treated candidate reached the callback and returned `0x36`; its candidate
fields `+0x264/+0x268` were `1/1`, compared with `0/0` for a normal candidate.
The source selector virtual `+0x1F0` was not measured reliably, so the trace
does not show which field participates in the return. Virtual-hook slot
aliasing prevents interpretation of repeated return events. For
invulnerability, the follow-up candidate passed the final geometry check but
was not observed at the callback; the JASS getter also returned true on
untreated units and false after the setter. This conflicts with the earlier
case-three callback-level `0x36` observation and leaves the state semantics
and first downstream filter unresolved. See the machine-readable summary at
`build-re/ability-re/ANfl-invulnerability-readback-01/results/followup-comparison.json`.
Only one conjunction returns rejection code `0x36`; all other paths return
zero. `0x006822E0` is a parallel predicate: it returns zero for null
candidates or nonzero candidate slot `+0xDC`, checks the same source flag and
candidate slots `+0x1DC`, `+0x1F4`, and `+0x1FC`, then can return code
`0xBC`. Candidate slot `+0x1FC` gates a context lookup in both routines. The
slot semantics and user-facing meanings of `0x36`/`0xBC` remain unmapped, so
retain these as structural contracts rather than naming them as a particular
immunity, Hero, or target-type rule.

Cold Arrow effect routine `0x00C5C9D0` also directly calls this same accessor
for its own `this+0x2C/+0x30` pair. This confirms reuse of the linked-pair
resolver outside the validator walk; the separate call site does not establish
that Cold Arrow applies the registry's target-validation rules.

Reproduce the disassembly against the pinned executable:

```sh
r2 -q -c 'e scr.color=0; pdf @ 0x00682180; pdf @ 0x007fc7e0; pd 60 @ 0x00682210; pd 60 @ 0x006822e0; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The common predicates' semantic names, rejection codes, and concrete
registered-validator implementations remain open. Record a runtime membership
or behavior claim only after tracing a controlled positive/negative candidate.

### RTTI-resolved `+0x26C` implementations

An exact-build RTTI/vtable scan found concrete `CAbility` implementations for
the callback slot used by the registry walk. The `CAbility` base vtable
`0x00E6DF38` points slot `+0x26C` to `0x0046AD80`, which returns zero. Several
derived classes override it:

- `CAbilityMetaDB` vtable `0x00EAC7D8` -> `0x00729400`, which returns `1`.
- Morph/form abilities (`Morph`, `Mount`, `RavenForm`, `StoneForm`,
  `AvengerForm`, `EtherealForm`, `CorporealForm`, `Phoenix`, `BearForm`,
  `Metamorphosis`, `Burrow`, `Submerge`, `RoboGoblin`, `ChemicalRage`) share
  `0x00BACF00`. Its observed checks include owner flag `+0x164 & 0x100`, virtual
  `+0x3F0`, ability fields `+0x3C/+0x20`, and the third argument's virtual
  `+0x214`; one conjunction returns `0xA3`, otherwise zero.
- `CAbilityGhost` vtable `0x00F68648` -> `0x00BF2AC0`. It checks a value
  derived from ability `+0x50` through `0x0046EE20`/`0x009A07B0`, then argument
  virtual `+0x208`; a passing conjunction returns `0xA7`.
- `CAbilityLocust` vtable `0x00FA790C` -> `0x00C6ACD0`, which returns `0x36`.

These are verified slot implementations and return contracts, not proof that
these instances are present in the linked registry during a particular cast.
The runtime registry's population and the user-facing meanings of `1`, `0x36`,
`0xA3`, and `0xA7` remain unresolved. This narrows the next dynamic probe:
capture `0x00682180`'s loop with a controlled target and resolve each entry's
vtable before assigning registry membership or rejection semantics.

Reproduce the vtable scan and callback bodies against the pinned Ghidra
project (the scan script is a temporary investigation aid):

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript FindVtablesWithSlot.java

/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java \
  0x0046AD80 0x00729400 0x00BACF00 0x00BF2AC0 0x00C6ACD0
```

## Shared unit-owner relationship predicate (Retail 1.29.2)

`0x006967A0` is a reusable Boolean gate with a relationship-specific call
chain. It reads a player index from its `this+0x160` context and takes a unit
as its stack argument. It passes those values to `0x00478E00`, which resolves
the argument unit's owner through virtual `+0xEC` and delegates to
`0x00478DA0`. That function validates the player indices, retrieves the
player record, and tests a bit in its relation mask. The helper normalizes
the result to zero/one. The bit's direction and exact ally/enemy meaning are
not established; keep the label neutral until checked against a controlled
Retail/JASS result.

### Forked Lightning relationship/mask gate and shared rejection validator

The ANfl candidate callback (`0x00C78FC0`, RVA `0x00878FC0`) uses a separate
gate before the shared spell-target validator. At callsite `0x00C78FDC`, it
passes the caster in `ECX`, candidate pointer as stack argument 1, then raw
arguments `0` and `4` to `0x0067FB80`. The exact downstream stack arguments
are detailed below; the earlier shorthand description of `0x00475150`'s
arguments is superseded by the instruction-level follow-up.

Candidates passing that gate proceed to `0x00682180`. For ANfl, zero is the
continue value; nonzero returns are rejection codes. Its built-in paths can
return `0x36` or `0xBC` after checking virtual slots and unit/context fields,
then it walks the registered validator list and stops on the first nonzero
callback. The exact virtual meanings, live registry membership, and the
gameplay categories represented by those codes remain unresolved. In the
ANfl callback, rejected candidates and already-recorded pointer duplicates
still return true to the spatial query; in normal accepted-order mode true
means “continue enumeration,” not “candidate eligible.”

The exact x86 call sequence is now recorded in
`build-re/ability-re/ANfl-followup-01-relation-disasm.txt`. The helper call
uses the shared player context, caster owner index, candidate pointer, a mode
bit derived from player 13's record flag `+0x04 & 0x200`, and trailing values
`4,0`. It consults a candidate-owner relation bit when candidate flag
`+0x164 & 0x01000000` requires that check, can run a point-based relation
predicate, and falls back to candidate masks at `+0x250/+0x254` using the
caster-owner bit. This resolves the numeric data flow, but not the JASS
enemy/ally/neutral meanings of those branches or raw mode `4`. No controlled
category matrix was run at the time of the static review. A subsequent
filtered case (`ANfl-target-selection-followup-01-gate-case-b-retry`) directly
observed all five living Player 12 `hfoo` candidates return 1 from
`0x0067FB80` and 0 from `0x00682180`. The cast's predicted workers and damage
receivers matched scenario indices `[0,3,2]`; this is a baseline-category
observation, not an enemy/allied/neutral matrix. See
`build-re/ability-re/ANfl-target-selection-followup-01/results/gate-case-b-comparison.json`.

The acquisition's static loop clamps progress to `max(A + D, C - (A + D))`
and executes the endpoint query. Type `0xB` consumes radius and center X/Y.
The query has a second, pre-callback target-mask stage. For ANfl, the `0x1D`
clause installs `0x00696BE0`; it calls `0x006ADB90(candidate, query+0x3C,
query+0x40, query+0x44)` and returns false when that shared filter returns a
nonzero rejection code. The shared filter reaches `0x006ADA20` and then
`0x006AD670`, before `0x00878FC0` can run. `0x006AD670` compares candidate and
source owner indices. For a same-owner pair it returns `0x84` unless normalized
target-mask bit `0x2000` permits that relation. ANfl passes mask word
`0x04010006`; `0x006AEA70` expands it to `0xF5D10006`, which lacks `0x2000`.
The historical same-owner Footman was absent from the callback, while enemy
Footmen were delivered. This is **verified static** and **runtime-correlated**
evidence for the pre-callback same-owner rejection. The internal `0x84` return
was not captured in the corrected live trace, so its runtime value remains
static-only.

The rank-one geometry samples support, but do not yet prove at native-point
precision, this model: `A=Area=125`, `C=DataC=900`, `D=DataD=300`, endpoint
progress `L=max(A+D,C-(A+D))=475`; radius at progress `p` is
`A + p*(D-A)/L`; then `p_next=min(p+radius,L)`. Query centers are consistent
with `caster + normalized(target-caster)*(p + D/4)`. The four measured radii
match that formula within the captured float precision; center positions track
the predicted ray within about 1.2 world units. This is **corroborated runtime**
for rank one, not a verified boundary rule. The native caster point was not
independently resolved in this capture, exact circle-edge inclusion is
untested, and no inside/outside boundary placements were made.

The receiver `0x002677C0` reads ANfl payload type `+0x14 = 0x400` and selector
`+0x20 = 0` under the runtime `MagicImmunesResistDamage` branch. It has a
zero-damage fast path for target state bit `+0x164 & 0x100`, checks payload
flags `+0x0C & 0x04`, then applies attached callbacks and amount adjustment
before virtual `+0x128`. These raw conditions are not yet named as specific
gameplay damage types, immunities, or defense categories, and no defensive
state comparison was run. The complete partial matrix and implementation
specification are in
[`ANfl-target-selection-followup-01/specification.md`](../../../../build-re/ability-re/ANfl-target-selection-followup-01/specification.md).

#### ANfl comparator sign and point conversion ABI

For five-target runs, sorter `0x00AB2000` takes its selection-sort path. It
selects the comparator maximum and places it at the end of the remaining
range. ANfl comparator `0x00878F60` returns the sign of `metricA - metricB`,
so the resulting primary order is ascending distance. When distances compare
equal, it returns the signed 32-bit subtraction `keyB - keyA` using candidate
object dword `+0x0C`; the five-entry result therefore orders larger signed key
values first. The field meaning is unresolved, and fully equal keys have no
stable-order guarantee. Static export `ANfl-comparator-helper-07/` verifies
the float subtraction helper `0x009A00B0`; `ANfl-target-selection-order-detail-03/`
contains the sorter.

The correct candidate coordinate path is also statically verified. CUnit
virtual `+0xB8` returns its point-handle object (`CUnit+0x26C`); observed point
vtable is `0x00E9D088`. The existing callback call at VA `0x00C7907F` enters
VA `0x007FCC50` (RVA `0x003FCC50`) as `thiscall`, with `ECX` equal to the
point-handle object and stack argument 1 equal to a caller-owned three-float
output buffer. The callee returns `ret 4`, resolves the pair at point-object
`+0x08/+0x0C` through `0x004707F0`, and writes transformed X/Y/Z via
`0x007FE810`. A filtered read-only observer is retained at
`build-re/ability-re/ANfl-deterministic-selection-03/`; it armed successfully,
and a retry produced an accepted rank-one cast. Its coordinate/identity
analysis is `case-01-analysis.json`. Four unique native candidates resolved to
four valid coordinate triples; JASS tick-3 coordinates correlate them with
scenario indices 0, 3, 1 and 4. The first three sorted distances to the
explicit target were 0.000, 154.727 and 175.163 and matched worker/receiver
order (indices 0, 3, 1); the fourth observed candidate at 229.871 was not
processed. Eleven callback deliveries included duplicates. The fifth JASS
unit, index 2, did not appear in callbacks, and the targets moved during the
case. The candidate callback's return value `1` means enumeration continues,
not that the candidate was accepted. This is useful runtime confirmation of
coordinate capture and ascending selection, but not a controlled five-target
prediction: the missing candidate's query/eligibility status and the moving
target placement leave the requested deterministic test open. Full raw data
is in `native-position-trace-retry.jsonl` and
`jass-anfl-r1-five-a-retry.txt`; the earlier failed activation trace is
preserved separately.

Two inspected callers use the same helper: `CAbilityAttack` vtable method
`0x00B1A100` calls it at `0x00B1A157` while filtering a unit target, and
`0x00C0D2F0` calls it at `0x00C0D2FD` before selecting a result-table entry.
An x86 direct-call byte scan found 62 candidate sites in the pinned image;
these two call instructions were checked in context. This is shared owner
relationship infrastructure, not proof that all callers implement the same
target rules.

Reproduce the inspected call chain and callers with:

```sh
r2 -q -c 'e scr.color=0; pdf @ 0x006967a0; pdf @ 0x00478e00; pdf @ 0x00478da0; pd 32 @ 0x00b1a100; pd 20 @ 0x00c0d2f0; q' \
  'data/Warcraft III/Warcraft III.exe'
```

## Attack target-mask and state-gate call paths

The exact-build `CAbilityAttack` target-selection routines `0x00B1EC60` and
`0x00B1EF60` both expand authored per-slot target masks through
`0x006AEA70`, then call `0x006ADA20`. Both treat return zero as a candidate
match and retain nonzero results as rejection codes. `0x006ADA20` rejects
malformed or empty masks, intersects the expanded mask with normalized
candidate flags, and delegates owner/type checks to `0x006AD670`. Its numeric
mask bits and rejection codes remain unmapped to AbilityData fields or
displayed text.

The lower-level owner/relation helper `0x006AD670` now has a concrete static
contract. It can accept the same object, compare candidate and source owner
indices, and query two player-relation bitsets through `0x00478DA0` and
`0x0047FAA0`. Bits in its first argument selectively turn each failed check
into acceptance; otherwise it returns distinct nonzero codes (including
`0x84`/`0x85` for owner/self cases and `0x86`–`0x88` for relation cases).
`GetPlayerAlliance` registration resolves to native wrapper `0x004944C0`.
That wrapper indexes a per-player relation row at base offset `+0x38` with a
16-byte stride per alliance type, then tests the other player's bit. Retail
`common.j` at `data/maps/War3xLocal/Scripts/common.j` maps type 0 to
`ALLIANCE_PASSIVE` and type 4 to `ALLIANCE_SHARED_SPELLS`. This identifies the
fixed table offsets used above:
`0x00478DA0` reads passive alliance (`+0x38`), while `0x0047FAA0` reads shared
spells (`+0x78`). Thus `0x006AD670` checks those specific alliance settings in
its two relation branches; it is not an abstract ally/enemy check. The
branch conditions are precise: after self/same-owner handling, absence of
passive alliance returns `0x88` unless policy bit `0x10000` allows it. A set
shared-spells bit returns `0x86` unless `0x4000` allows it; a clear bit returns
`0x87` unless `0x8000` allows it. Self and same-owner failures return `0x85`
and `0x84` unless bits `0x1000` and `0x2000` allow them, respectively. The
user-facing text for these codes remains unresolved. Reproduce the
registration wrapper and fixed relation checks with:

```sh
r2 -q -c 'e scr.color=0; pd 60 @ 0x004944c0; pd 90 @ 0x004a94a0; pd 40 @ 0x00478da0; pd 40 @ 0x0047faa0; pd 80 @ 0x006ad670; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The selector contract is now clearer from its callers: each routine examines
two authored target slots and writes the matching slot index through its
output pointer; `0xFFFFFFFF` means neither slot was selected. A zero result is
the validator success code, separate from that output slot. Ordinary attack
calculation `0x00B23C30` calls `0x00B1EC60`, and attack/order helper paths also
reach these selectors. Accessors `0x00B20440` and `0x00B20490` wrap the
respective selector and return the value at that selected slot through
`0x00B203A0`; if there is no selected slot, they return global game time at
`0x0112D88C`. The meaning of the selected value and which exact caller contexts
use each accessor remain unresolved.

The surrounding gate `0x006ADB90` is used by attack candidate filtering and
Carrion Swarm's candidate collector (`0x00C31220`). It tests candidate state
and relation context, has a status-specific branch using `0x006D6570`,
conditionally checks visibility/detection through `0x006D7DD0`, and then
delegates to `0x006ADA20`. This makes it a shared prefilter with concrete
attack and missile users; individual flags and return values still need
controlled behavioral mapping. It is separate from the general spell
validator `0x00682180` above.

Reproduce the caller bodies and mask helpers in the checked-in Ghidra project
with the inspection script used for this pass (kept under `/tmp`):

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath /tmp/wc3-ghidra-inspect \
  -postScript InspectFunctions.java \
  0x00B1EC60 0x00B1EF60 0x00B20440 0x00B20490 0x00B203A0 \
  0x006ADB90 0x006ADA20 0x006AEA70
```

The reusable machine-readable edges and unresolved meanings are in
[`ability-function-investigation.json`](../ability-function-investigation.json).

## Retail Charm target verification (October 4, 2026)

Retail behavior for Charm (`ANch`) was checked with a temporary JASS probe in
the Prologue campaign map under Wine. The retail installation was launched
with `-window -graphicsapi OpenGL2`; its untouched `Prologue01.w3m` extracted
from `War3Local.mpq` loaded to the chapter card before the instrumented map was
built. The retail executable SHA-256 was
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.

The probe used the stock `ANch` row and created four independent casts from a
Player 0 Blood Mage (`Hblm`) with Charm added. It issued `charm` against a
Player 12 level-3 neutral-hostile creep (`nftt`), a Player 12 Paladin Hero
(`Hpal`), a dead `nftt` corpse, and a live `nftt` given permanent Resistant
Skin (`ACsk`). After four seconds, it wrote the targets' owners, Hero type,
corpse life, and Resistant Skin level through `PreloadGen*` to
`Documents/Warcraft III/CustomMapData/charmtest.txt`.

The map was prepared using the retail-compatible in-place replacement
procedure documented in [Retail Warcraft III camera tracing](../retail-camera-tracing.md).
The short command sketch below only illustrates the archive update syntax; use
the complete replay procedure that follows to extract and instrument the map:

```sh
build/bin/mpqtool -mpq 'data/Warcraft III/War3Local.mpq' \
  cat 'Maps/Campaign/Prologue01.w3m' > /tmp/Prologue01-control.w3m
build/bin/mpqtool -mpq /tmp/Prologue01-control.w3m \
  cat war3map.j > /tmp/war3map.j
# Prepare the instrumented script as /tmp/charm-stage/war3map.j (full steps below).
cp /tmp/Prologue01-control.w3m /tmp/Prologue01-CharmTest.w3m
mkdir -p /tmp/charm-stage
(cd /tmp/charm-stage && \
  smpq -a -f /tmp/Prologue01-CharmTest.w3m war3map.j)
```

The original extracted map was kept unchanged. `mpqtool cat war3map.j` on the
result matched the staged test script byte-for-byte, and the archive retained
its 4096-byte sector size and 17 listed map members. The probe helpers were
placed before the cinematic skip callback that invokes them. It starts after
the skip callback enters gameplay. In the Wine/Xvfb run, clicking the Prologue
chapter card advanced into the cinematic; Escape skipped it and activated the
test. Sending Return before focusing/clicking the card had left the game on the
chapter screen, so those earlier attempts produced no report and are not test
failures.

### Complete replay procedure

The archive commands above are a summary; the following details fill in the
script edits, run command, and input timing. Start from a fresh extraction.
The untouched control must reach the chapter card before editing anything:

    export WINEPREFIX=/home/agent/.wine-war3
    WORK=/tmp/charm-retail-repro
    mkdir -p "$WORK/control" "$WORK/stage"
    build/bin/mpqtool -mpq 'data/Warcraft III/War3Local.mpq' \
      cat 'Maps/Campaign/Prologue01.w3m' > "$WORK/control/Prologue01.w3m"
    build/bin/mpqtool -mpq "$WORK/control/Prologue01.w3m" ls
    build/bin/mpqtool -mpq "$WORK/control/Prologue01.w3m" \
      cat war3map.j > "$WORK/control/war3map.j"
    xvfb-run -a -s '-screen 0 1280x720x24' bash -lc '
      export WINEPREFIX=/home/agent/.wine-war3
      wine "data/Warcraft III/Warcraft III.exe" -window -graphicsapi OpenGL2 \
        -loadfile "$(winepath -w /tmp/charm-retail-repro/control/Prologue01.w3m)"
    '

In the extracted JASS, add these declarations inside the existing globals
block:

    timer gg_timer_charmtest = null
    unit gg_unit_charm_valid = null
    unit gg_unit_charm_hero = null
    unit gg_unit_charm_corpse = null
    unit gg_unit_charm_resistant = null

Insert the following functions immediately before
function Trig_Intro_Cinematic_Skip_Actions. This ordering matters: the skip
callback calls CharmTestStart, so its helpers are placed before that callback.
The test runs after the callback has entered gameplay.

    function CharmTestMakeCaster takes real x, real y returns unit
        local unit caster
        set caster = CreateUnit(Player(0), 'Hblm', x, y, 270.0)
        call UnitAddAbility(caster, 'ANch')
        call SetUnitAbilityLevel(caster, 'ANch', 1)
        call SetUnitState(caster, UNIT_STATE_MANA, GetUnitState(caster, UNIT_STATE_MAX_MANA))
        return caster
    endfunction

    function CharmTestReport takes nothing returns nothing
        local string report
        set report = "CHARMTEST validOwner=" + I2S(GetPlayerId(GetOwningPlayer(gg_unit_charm_valid))) + " heroOwner=" + I2S(GetPlayerId(GetOwningPlayer(gg_unit_charm_hero))) + " corpseOwner=" + I2S(GetPlayerId(GetOwningPlayer(gg_unit_charm_corpse))) + " resistantOwner=" + I2S(GetPlayerId(GetOwningPlayer(gg_unit_charm_resistant))) + " heroType=" + I2S(GetUnitTypeId(gg_unit_charm_hero)) + " corpseLife=" + R2S(GetWidgetLife(gg_unit_charm_corpse)) + " resistantSkinLevel=" + I2S(GetUnitAbilityLevel(gg_unit_charm_resistant, 'ACsk'))
        call BJDebugMsg(report)
        call PreloadGenClear()
        call PreloadGenStart()
        call Preload(report)
        call PreloadGenEnd("charmtest.txt")
        call PauseTimer(gg_timer_charmtest)
        call DestroyTimer(gg_timer_charmtest)
        set gg_timer_charmtest = null
    endfunction

    function CharmTestStart takes nothing returns nothing
        local real x
        local real y
        local unit caster
        set x = GetStartLocationX(0) + 1800.0
        set y = GetStartLocationY(0) + 700.0
        set caster = CharmTestMakeCaster(x, y)
        set gg_unit_charm_valid = CreateUnit(Player(12), 'nftt', x + 240.0, y, 270.0)
        call IssueTargetOrder(caster, "charm", gg_unit_charm_valid)
        set caster = CharmTestMakeCaster(x + 1000.0, y)
        set gg_unit_charm_hero = CreateUnit(Player(12), 'Hpal', x + 1240.0, y, 270.0)
        call IssueTargetOrder(caster, "charm", gg_unit_charm_hero)
        set caster = CharmTestMakeCaster(x + 2000.0, y)
        set gg_unit_charm_corpse = CreateUnit(Player(12), 'nftt', x + 2240.0, y, 270.0)
        call KillUnit(gg_unit_charm_corpse)
        call IssueTargetOrder(caster, "charm", gg_unit_charm_corpse)
        set caster = CharmTestMakeCaster(x + 3000.0, y)
        set gg_unit_charm_resistant = CreateUnit(Player(12), 'nftt', x + 3240.0, y, 270.0)
        call UnitAddAbility(gg_unit_charm_resistant, 'ACsk')
        call UnitMakeAbilityPermanent(gg_unit_charm_resistant, true, 'ACsk')
        call IssueTargetOrder(caster, "charm", gg_unit_charm_resistant)
        set gg_timer_charmtest = CreateTimer()
        call TimerStart(gg_timer_charmtest, 4.00, false, function CharmTestReport)
        set caster = null
    endfunction

At the end of Trig_Intro_Cinematic_Skip_Actions, immediately after its
existing call to ConditionalTriggerExecute( gg_trg_Gameplay ), add:

    call CharmTestStart()

Save the edited script as "$WORK/stage/war3map.j", copy the untouched map, then
update only that exact archive member. Passing a differently named JASS file
adds another archive member. Do not rebuild the MPQ payload from scratch:

    cp "$WORK/control/Prologue01.w3m" "$WORK/Prologue01-CharmTest.w3m"
    (cd "$WORK/stage" && \
      smpq -a -f "$WORK/Prologue01-CharmTest.w3m" war3map.j)
    build/bin/mpqtool -mpq "$WORK/Prologue01-CharmTest.w3m" ls
    build/bin/mpqtool -mpq "$WORK/Prologue01-CharmTest.w3m" \
      cat war3map.j > "$WORK/embedded-war3map.j"
    cmp "$WORK/stage/war3map.j" "$WORK/embedded-war3map.j"
    smpq -i "$WORK/Prologue01-CharmTest.w3m"

The byte comparison must pass. mpqtool ls shows one war3map.j and 17 listed
map members. smpq -i reports 4096-byte sectors and 19 MPQ block entries; that
block count matches the original archive and is not an extra JASS member.
Updating in place on a copy preserves the wrapper and trailer.

Launch the instrumented copy. In this 1280x720 Xvfb display the chapter card's
continue button is near (642, 600). The reliable sequence is click the card,
wait until the cinematic is underway, then send Escape. A Return sent before
the card was focused left Retail on the chapter card; the test never started
in those attempts. After the skip, wait for the four-second timer and read:

    xvfb-run -a -s '-screen 0 1280x720x24' bash -lc '
      export WINEPREFIX=/home/agent/.wine-war3
      wine "data/Warcraft III/Warcraft III.exe" -window -graphicsapi OpenGL2 \
        -loadfile "$(winepath -w /tmp/charm-retail-repro/Prologue01-CharmTest.w3m)" &
      gamepid=$!
      sleep 14
      xdotool mousemove 642 600 click 1
      sleep 12
      xdotool key --clearmodifiers Escape
      sleep 20
      cat "$WINEPREFIX/drive_c/users/agent/Documents/Warcraft III/CustomMapData/charmtest.txt"
      kill "$gamepid" 2>/dev/null || true
    '

If the result file is missing, first check that the click left the chapter
card and Escape skipped the cinematic. A blank initialization dialog instead
means Retail rejected the map or script: confirm that the untouched control
loads, the archive contains exactly one war3map.j, the embedded script matches
the edited one, and the helper functions precede their first call. Use
-loadfile without -launch and -window -graphicsapi OpenGL2; other launch
combinations previously returned to the menu or showed a black screen under
Wine.

The recorded output was:

```text
CHARMTEST validOwner=0 heroOwner=12 corpseOwner=12 resistantOwner=12 heroType=1215324524 corpseLife=0.000 resistantSkinLevel=1
```

This directly confirms that the legal creep changed owner to Player 0, while
the Hero, corpse, and Resistant Skin target remained owned by Player 12. The
corpse life and skin-level fields confirm the latter two targets had the
intended setup. This establishes the tested retail target outcomes for these
four cases; it does not establish every Charm target-mask edge, level boundary,
ownership interaction, or other retail executable version. The JASS probe and
repacked map were temporary files under `/tmp/pathfinding/charm` and
`/tmp/charm-retail`, not shipped project assets.

### Creep-level boundary follow-up

A second controlled Retail run exercised the stock `ANch` level ceiling
(`DataA=5`). The test locally overrode the stock `nftt` UnitData level to 5,
and created organic copies at levels 3, 4, 5, and 6. The ordinary stock-row
level-5 target transferred to Player 0. Among the custom copies, levels 4 and
5 transferred, while level 6 stayed with Player 12. The recorded output was:

```text
CHARMTEST validOwner=0 validLevel=5 heroOwner=12 corpseOwner=12 resistantOwner=12 heroType=1215324524 corpseLife=0.000 resistantSkinLevel=1 L3=3 owner3=12 L4=4 owner4=0 L5=5 owner5=0 L6=6 owner6=12
```

This is direct evidence that the tested stock `ANch` accepts an organic creep
through level 5 and rejects level 6. The custom level-3 copy unexpectedly
remained Player 12 even though the ordinary stock level-3 `nftt` transferred in
the first probe. The reason is unknown; treat that single custom result as an
unexplained setup or behavior anomaly, not as evidence against level-3
acceptance. These probes do not establish alias-specific limits or complete
source/destination resource accounting.

## Retail Purge friendly and hostile target verification (October 4, 2026)

Stock TFT `Apg2` was exercised in the Prologue campaign map under Wine with
the same Warcraft III executable identified in the Charm probe above
(`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`).
`ability_audit` reports `DataA=5`, `DataC=400`, `DataD=3`, `DataE=1`, and the
target mask `air,ground,ward,vuln,invu,tree`. Two Player 0 Blood Mages (`Hblm`)
each received stock `Apg2`; one cast on a Player 0 Footman and one on a Player
12 Footman. Each target had a same-owner Footman control moving toward the
same destination on a nearby parallel lane. JASS issued the `purge` target
orders after two seconds of baseline movement and sampled X displacement at
1.5, 3.5, and 6.5 seconds after the orders. Results were written through
`PreloadGen*` to `CustomMapData/purgetest.txt` and
`CustomMapData/purgetest-ally.txt`.

The hostile-target run reported:

```text
PURGETEST allyAbility=1 enemyAbility=1 allyManaSpent=0.000 enemyManaSpent=69.111 s1=ally=0.000,allyctl=0.000,enemy=80.865,enemyctl=385.253 s2=ally=0.000,allyctl=0.000,enemy=108.837,enemyctl=608.150 s3ally=0.000 s3allyctl=0.000 s3enemy=390.058 s3enemyctl=608.1
```

The zero allied-lane values belong to an earlier placement where neither that
target nor its control moved; discard them. The valid hostile comparison is
that the enemy target moved 80.865 units versus 385.253 for its control at 1.5
seconds, and 108.837 versus 608.150 at 3.5 seconds. By 6.5 seconds the enemy
target had resumed moving. The control had already reached its destination, so
the last sample does not establish the recovery rate.

The corrected allied-target run used a path on which both allied units moved.
It reported:

```text
PURGETESTALLY allyAbility=1 enemyAbility=1 allyManaSpent=69.196 enemyManaSpent=69.168 s1=ally=382.881,allyctl=403.491,enemy=403.566,enemyctl=395.808 s2=ally=893.105,allyctl=750.494,enemy=737.043,enemyctl=549.672 s3ally=910.964 s3allyctl=750.494 s3enemy=737.04
```

The allied cast spent approximately 75 mana after regeneration, and the target
moved about as far as its control during the first 1.5-second sample. Later
lane/control divergence makes those samples unsuitable for a precise speed
ratio. Together, the runs support the stock `Apg2` contract that enemies are
immobilized/slowed while an allied target can receive the cast without that
movement effect. This probe does not establish whether the allied cast removes
buffs, exact pause/slow timing, or behavior of `Aprg` and item/creep aliases.

The untouched Prologue map was extracted from `War3Local.mpq`; each instrumented
copy replaced the exact `war3map.j` member in place with `smpq -a -f`. The
embedded script was compared byte-for-byte with the staged script. As with the
Charm probe above, helpers were placed before
`Trig_Intro_Cinematic_Skip_Actions`, the test started after the skip callback,
and Retail was launched with `-window -graphicsapi OpenGL2 -loadfile` (without
`-launch`). The familiar chapter-card click and Escape sequence was used. An
initial allied setup whose target and control could not move was discarded;
the corrected run is the allied evidence above.

### TFT campaign-map replay (October 4, 2026)

The Charm and both Purge cases were replayed on the TFT campaign map
`Maps/FrozenThrone/Campaign/OrcX01.w3x` extracted from `War3xLocal.mpq`, using
the same Retail executable. This distinguishes TFT runtime evidence from the
earlier Prologue-map probes, which used ROC map scripts even though they tested
TFT ability rows. The untouched OrcX01 control reached its “To Tame a Land”
chapter card and entered gameplay after the documented click/Escape sequence.
Probe helpers ran after `Trig_Intro_Skipped_Actions` executed the Gameplay
trigger. The map's cinematic ability gates disable `AIba`, `AIcd`, `AIad`,
`AIae`, `AIgx` and `Ashm`; they do not gate `ANch` or `Apg2`. The probes still
explicitly added the tested ability to each Blood Mage.

Charm reproduced the prior four-target result:

```text
CHARMTEST validOwner=0 heroOwner=12 corpseOwner=12 resistantOwner=12 heroType=1215324524 corpseLife=0.000 resistantSkinLevel=1
```

For hostile Purge, the allied lane continued moving (230.819 vs. 142.339 units
at 1.5 seconds; 661.818 vs. 564.891 at 3.5 seconds). The hostile target was
nearly stationary (-0.186 vs. -373.630 units; -0.420 vs. -823.889), while its
control moved. In the corrected all-allied setup, both tested targets moved at
roughly the same scale as their controls: 69.147 vs. 99.590 and -352.893 vs.
-384.113 at 1.5 seconds; 394.208 vs. 308.507 and -765.988 vs. -834.990 at 3.5
seconds. The negative values reflect travel along the map's X axis. As in the
Prologue measurements, lane and route differences make these qualitative
movement comparisons rather than exact speed measurements.

All three fresh Preload captures were classified `ready_for_review`, then
reviewed manually. That tool status only confirms probe markers and fresh
capture; the ownership and movement values above are the behavioral evidence.
Those Charm and Purge replays used temporary maps and scripts under
`/tmp/wc3-retail-tft-rechecks`; they did not modify repository or retail map
assets.

### Retail Purge hostile immobilize and recovery timing (October 17, 2026)

The rerunnable probe in
[`tools/retail_probes/purge_timing/`](../../../../tools/retail_probes/purge_timing/)
measured stock TFT `Apg2` on Retail 1.29.2.9231 (executable SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`). The
matching AbilityData row is `DataA=5`, `DataD=3`, `Dur=15`. The experiment
created a Player 0 Blood Mage with `Apg2`, a hostile Player 12 Footman target,
and an untreated hostile Footman control. Both units were set to 300 movement
speed and position-locked every 50 ms; JASS sampled effective speed every 100
ms. The harness starts after `Trig_Intro_Skipped_Actions` executes the Gameplay
trigger, avoiding casts during the opening cinematic.

Three runs completed in the same Retail process. Each had 19 baseline samples
at 300 speed, an accepted Purge order, a matching `EVENT_UNIT_SPELL_EFFECT` at
tick 46, 220 total samples, and a `PG_DONE accepted=1 effect=1` marker. The
untreated control stayed at 300 throughout. Runs 2 and 3 followed JHCR updates
and both report `PG_JHCR_STATUS=1`. Run 2 did not emit its expected
`PG_REVISION=2` marker. Run 3 changed only passive `PG_Log`; it emitted
`PG_LOG_REV2`, confirming the updated logger ran while the probe completed.
The JHCR sequences and reload-guard records are retained beside the raw
captures.

| First sampled target speed | Time after spell-effect event | Observation |
|---:|---:|---|
| 0 | 0.1 s | Immobilized; speed was still 300 at the event-tick sample. |
| 150 | 3.1 s | First nonzero sample; the 3.0 s sample remained 0. |
| 180 | 9.1 s | Recovery step. |
| 240 | 12.1 s | Recovery step. |
| 300 | 15.1 s | Full baseline speed; the 15.0 s sample remained 240 (about 12.0 s after speed first rose above zero). |

These observations bracket immobilization at 3.0–3.1 seconds after the effect
and full recovery at 15.0–15.1 seconds. The measured curve is consistent with
the authored 3-second immobilize and 15-second recovery. It does not establish
sub-100 ms boundaries. The initial 150 speed should not be read as proof that
`DataA=5` means a 50% slow: this experiment does not distinguish the authored
factor from a minimum movement-speed clamp. Repeat with a faster unit to
separate those effects. Allied dispel behavior and creep/item aliases also
remain untested.

Raw evidence: [run 1](../../../../tools/retail_probes/purge_timing/evidence/retail-1292-jhcr-confirmed-run1.txt),
[run 2](../../../../tools/retail_probes/purge_timing/evidence/retail-1292-jhcr-confirmed-run2.txt),
[run 3 with the updated logger marker](../../../../tools/retail_probes/purge_timing/evidence/retail-1292-jhcr-confirmed-run3.txt),
[JHCR sequence 1](../../../../tools/retail_probes/purge_timing/evidence/jhcr-update-seq1.json),
and [sequence 2](../../../../tools/retail_probes/purge_timing/evidence/jhcr-update-seq2.json).

### Retail Purge 150-speed floor at a 400-speed baseline (October 17, 2026)

The follow-up probe in
[`tools/retail_probes/purge_speed_floor/`](../../../../tools/retail_probes/purge_speed_floor/)
used the same stock TFT `Apg2` map on Retail 1.29.2.9231. It set both hostile
Footmen to 400 movement speed, position-locked them every 50 ms, and sampled
effective speed every 50 ms. `PG_CONFIG` and setup output confirmed both units
at 400. A matching hostile control stayed at 400 for all 440 samples.

Three runs completed in the same Warcraft process. Each recorded 39 baseline
samples, an accepted Purge order, the matching spell-effect event at tick 46,
440 samples, and `PG_DONE accepted=1 effect=1`; none reported `PG_SETUP_FAIL`.
Run 3 followed one JHCR update and includes `PG_JHCR_STATUS=1` plus the unique
`PG_LOG_REV3` marker. Its map was loaded through the Custom Game UI after
returning to the menu, preserving the same Retail process. Runs 1 and 2 also
contain `PG_LOG_REV2`, inherited from the copied starting script; that marker
does not indicate a JHCR update. The reusable checked-in source has since been
cleaned of it.

All three 400-speed runs produced the same transitions:

| First sampled target speed | Time after spell-effect event | Notes |
|---:|---:|---|
| 0 | 0.05 s | The target remained at 0 through 3.00 s. |
| 150 | 3.05 s | First nonzero speed; same absolute value as the prior 300-speed runs. |
| 160 | 6.05 s | 40% of the 400 baseline. |
| 240 | 9.05 s | 60% of baseline. |
| 320 | 12.05 s | 80% of baseline. |
| 400 | 15.05 s | Full baseline; the 15.00 s sample remained at 320. |

The 300- and 400-speed tests both first recover at 150, supporting a 150-speed
floor that masks the slower underlying value. The later 400-speed steps follow
40%, 60%, 80%, and 100% of baseline. This separates the observed floor
behavior from a direct 50% result at the first post-immobilize sample. It does
not establish whether the floor is the generic Retail movement clamp or a
Purge-specific minimum. The immobilize boundary is bracketed at 3.00–3.05 s;
full recovery is bracketed at 15.00–15.05 s. Sub-50 ms behavior, allied
dispel, and creep/item aliases remain open.

Raw captures and per-run JSON summaries are in the probe's `evidence/`
directory. The normal runner `capture` command requires its own launch record;
these runs were loaded through the in-process Custom Game UI, so the raw
PreloadGen result was copied before each rerun. The probe README documents that
path and the JHCR update step.

The activation failure was isolated in follow-up cases 06–08. Case 05's
launch record and map archive identify the prepared map, and its embedded
`war3map.j` byte-matches the generated script with `RE_Init()` in `main`. Case
06 proved startup execution with a fresh run-specific `PreloadGen` result;
case 07 proved exact-match chat-handler entry and chat-triggered output; case
08 emitted one target's handle, type, owner, position and health. Evidence is
in `build-re/ability-re/ANfl-startup-sentinel-06/` and
`ANfl-chat-sentinel-07/`.

Case 11 restored five stationary target placements and emitted complete JASS
identity records. It did not reach targeting: the caster wandered from
`(-1072,-5968)` at placement to `(-4896,-7296)` before the cast, so
`IssueTargetOrder` returned false. The bounded trace has no ANfl acquisition,
candidate, worker or damage events. Its pre-cast prediction is therefore not
a selection result. The immutable prediction and rejection comparison are in
`build-re/ability-re/ANfl-controlled-target-selection-11/predictions/` and
`results/case-a-comparison.json`. Case 12 adds a caster Hold Position order but
its JASS source references undeclared `ordersOk` inside `RE_SetupOne`; that
prepared script was defective, and the black-window run produced no usable
scenario result. These are preserved historical diagnostics. The earlier
four-candidate capture remains movement-confounded and does not diagnose its
missing fifth callback candidate.

### Controlled five-target selection verification (October 18, 2026)

Cases 19 and 21 completed two rank-one casts with five stationary Player 12
`hfoo` targets. Each map recorded five unique JASS handles, actual positions,
five stable 0.25-second placement samples, and a prediction written before the
cast. The caster was repositioned immediately before the order. Case 21 also
restored full mana and reset cooldown immediately before issuing the order
after case 20 showed a rejected order with only 105.991 mana. Its successful
cast logged 330 mana and ability level one.

| Case | Predicted sorted units | Predicted recipients | Observed workers | Native receivers | JASS damage events |
|---|---|---|---|---|---|
| 19 A | `[0,1,2,3,4]` | `[0,1,2]` | `[0,1,2]` | `[0,1,2]` at 85 | `[0,1,2]` at 85 |
| 21 B | `[0,3,2,1,4]` | `[0,3,2]` | `[0,3,2]` | `[0,3,2]` at 85 | `[0,3,2]` at 85 |

Both traces contain 13 candidate callback deliveries, five unique CUnit
pointers, five successful coordinate resolutions using the engine's existing
`0x007FCC50` call, three workers, and three matching damage receiver calls.
The resolved XYZ positions match the five live JASS positions one-to-one by
coordinates, owner and type. This is a coordinate-based correlation rather
than handle-registry proof. Callback entry establishes query delivery; the
three selected units' eligibility is directly established by their worker
calls. The relationship/shared-validator result was not instrumented for the
two unselected targets, so their gate passage remains inferred from the
identical target setup and static native path.

Case 19's prediction is
`build-re/ability-re/ANfl-controlled-target-selection-19/predictions/case-a-v1.json`;
its raw JASS and Frida captures and comparison are in that case's `results/`
and `traces/` directories. Case 21's immutable prediction is
`build-re/ability-re/ANfl-controlled-target-selection-21/predictions/case-b-v1.json`;
its raw captures and comparison are in the corresponding directories. Both
predictions precede their cast-result file timestamps. The full native pointer
to JASS correlation and per-unit distance/worker/damage tables are in
[`forked-lightning-retail.md`](../forked-lightning-retail.md#controlled-five-target-prediction-verification-october-18-2026).

The first case-19-B placement was rejected before casting: target 3 was on
blocked pathing and two targets shifted before the stable samples. Case 20
corrected the layout and verified five stationary targets, but its order was
rejected with 105.991 mana and produced no native acquisition. Case 21 used
that corrected, validated layout and restored full mana plus cooldown before
the order. Cases 19 and 21 verify the predicted DataB-limited prefix for
distinct per-unit distance rankings. Runtime tie ordering and exact query
boundaries remain untested; the same-owner probe below adds one narrow
pre-callback category observation.

### Same-owner secondary candidate (October 18, 2026)

The focused case `ANfl-target-eligibility-ally-01` retained case-21 target
types and coordinates while changing target index 3 to Player 0, the caster's
owner. The accepted order generated four type-0xB spatial queries. Four
scenario positions (indices 0, 1, 2 and 4) reached the callback; the same-owner
candidate at index 3 did not. Every delivered unique candidate passed the
relationship gate (`0x0027FB80` return 1) and shared validator
(`0x00282180` return 0). Workers and native receivers were `[0,2,1]` with raw
85 payloads. Thus this capture shows pre-callback exclusion for this same-owner
`hfoo`, not rejection by either callback gate. Exact-build static analysis
identifies query predicate `0x00696BE0` → `0x006ADB90` → `0x006ADA20` →
`0x006AD670` as the pre-callback path. ANfl mask `0x04010006` normalizes to
`0xF5D10006`; its missing `0x2000` bit causes `0x006AD670` to reject equal
owner indices with code `0x84`. The callback absence agrees with this branch,
but the `0x84` return itself was not captured live.

The map logged Footman-to-Footman attacks and stale unit sources before and
after the cast; its JASS life deltas are therefore not attributed to ANfl.
The exact map, coordinate-resolved trace, result files, screenshots and
preregistered conditional hypotheses are under
`build-re/ability-re/ANfl-target-eligibility-ally-01/`. The capture expands
only the same-owner case and does not establish allied/enemy relation rules
for other unit categories.

### Clean ANfl fixture and query predicate

The later `ANfl-clean-combat-01` fixture zeroed ordinary attack base damage
and dice on the caster and test Footmen, cleared nearby local units, and held
all targets stationary. A five-second no-cast interval kept every target at
210 life. A known-good cast then matched the saved `[0,1,2]` prediction with
three workers and three 85-point receiver/JASS damage events. See
`build-re/ability-re/ANfl-clean-combat-01/` for raw outputs and trace.

Static query-shape analysis now shows that the type-0xB path's final spatial
predicate is inclusive. The native path divides query radius by 32, adds the
spatial-entry scalar at `+0x90`, squares the sum, and accepts when
`distanceSquared <= (radius/32 + entry[+0x90])^2`. It also uses an earlier
bounds enumeration. In the repaired `ANfl-geometry-boundary-01` run,
`+0x90` was `0.96875` (`0x3f780000`) for observed Footman entries. One candidate
just inside query 2's boundary (`39.85868 <= 39.86842`) reached the callback;
another failed final-circle checks for queries 3 and 4 and received no callback.
Its correlation to JASS target index 3 is inferred from allocation stride.
Exact equality and broadphase boundaries remain untested, and the scalar's
gameplay meaning/writer remain unresolved.

The geometry harness failed earlier because stale scenario IDs left a chat
handler marker without a matching `RE_Finish` output branch. A preflight now
checks setup/chat/finish IDs, unique outputs, canonical manifest IDs, embedded
JASS, archive hash, and stale identifiers. Prepared-v3 passed and produced
fresh outputs. Acquisition-time native points also corrected the center model:
the caster moved before acquisition, so the ray starts at native position
`(-1072,-5968)`, not the earlier JASS pre-order point.

### Magic immunity and invulnerability callback outcomes

The controlled `ANfl-state-alliance-ranks-01` follow-up used the clean
stationary Footman layout. A normal rank-one control selected targets 0, 1,
and 2 and reached three workers/receivers with raw 85 damage. With Amim added
to secondary target 1 (JASS ability level read back as 1), native tracing
showed that its spatial entry passed geometry and reached the ANfl callback.
The relationship gate passed (`1`), then the shared target validator returned
`54` (`0x36`), so the target did not enter the retained/worker set. The
invulnerability setup produced the same callback and validator result after
`SetUnitInvulnerable(target,true)`; this fixture did not independently read
back that state. For both treatments, other candidates filled the three-worker
prefix and received 85. Thus these captures establish callback-level
eligibility rejection, not a query-mask exclusion or receiver-side damage
suppression. The meaning of validator code `0x36` remains unresolved.

The initial black screen was a campaign transition. The minimal diagnostic
derived from the known-good clean fixture produced separate startup and chat
handler outputs after the documented transition completed. The original
seven-case map then produced fresh setup/cast outputs without a script change.
Artifacts are in `build-re/ability-re/ANfl-startup-diagnostic-01/` and
`build-re/ability-re/ANfl-state-alliance-ranks-01/`.

A separately owned allied case changed the secondary Footman to Player 1 and
set mutual passive alliance with Player 0. The target did not reach the ANfl
callback; three Player 12 targets were selected and damaged. The candidate was
not seen at the final geometry comparison or the filtered VA `0x006AD670`
owner-relation hook. The evidence therefore establishes callback absence but
does not yet distinguish broadphase exclusion from an earlier query filter.
It does not justify extending the static same-owner `0x84` branch to all
different-owner allies. See case 4 and `runtime/state-trace-v5-allied.jsonl`.

### Exact static origin of validator code `0x36`

The pinned executable was rechecked with focused VA disassembly. The return
`0x36` is emitted by the built-in predicate VA `0x00682210` at VA
`0x006822CE`, before the shared validator's registered-callback walk. VA
`0x006822E0` is a separate path that can return `0xBC`.

The call frame maps `u` to the candidate CUnit and `a` to the source ability
object. The exact `0x36` conjunction is:

```text
a.vfunc(+0xD8) == 0
(u.raw[+0x164] & 0x100) == 0
field = a.vfunc(+0x1F0) != 0 ? u.signed[+0x268] : u.signed[+0x264]
field > 0
(a.vfunc(+0x1D8) != 0 || a.vfunc(+0x1F8) != 0)
a.vfunc(+0x1FC) == 0 || candidate_predicate(u, a[+0x30] ?? resolve(a)) == 0
GetConfigInt("Misc", "MagicImmunesResistUltimates", 0) == 0
a.vfunc(+0x20C) != 0
```

This corrects earlier descriptions that assigned candidate fields `+0x164`,
`+0x264`, and `+0x268` to the source. Runtime Amim level 1 plus validator
return `0x36` confirms the treatment reaches this rejecting result, but the
captured trace did not expose which operand first differs from a normal
Footman. The config name is one term in the conjunction; it does not establish
that it caused the observed return. The full branch account is in
`build-re/ability-re/ANfl-validator-36-static-01/validator-36-analysis.md`.

The matching `data/maps/War3xLocal/Scripts/common.j` declares
`BlzIsUnitInvulnerable` at line 2529. The prior case 3 did not call this
native, so invulnerability remains unconfirmed independently despite the
recorded setter and validator result.

### Neutral Passive and rank-three follow-up

The Player 15 Neutral Passive treatment used the same `hfoo` at
`(-720,-6160)`, owner read back as 15, and stable life 210 after five seconds.
The cast order was accepted. The final geometry trace had no entry at the
expected spatial-index point `(169.5,63.5)` in any of the four queries; a
matched Player 12 candidate and the Amim candidate at the same location did
reach that stage. The Player 15 target also had no owner-relation or callback
event. This establishes exclusion by or before the final geometry-operand
hook, but broadphase versus an earlier predicate remains unresolved. Other
selected targets generated three raw-85 receiver calls. See
`build-re/ability-re/ANfl-neutral-passive-rank3-01/`. The matched Player 12 `hfoo` at the same point did appear at the geometry/callback stage, but this does not distinguish broadphase from pregeometry filtering for Player 15.

In the same run, a rank-three case read back ANfl level 3 and was accepted.
The four observed query centers and radii matched the rank-one values for the
authored `Area=125`, `DataC=900`, `DataD=300`. Three workers and receivers
carried raw 250. Targets had 210 maximum life, so final life is overkill
limited and the receiver payload is the raw damage evidence. A separate
single-case rank-two capture at `build-re/ability-re/ANfl-rank2-geometry-03/`
read back rank 2, recorded four query centers/radii matching the corrected
`p+Area` center progression and radius progression, and captured three workers
and three raw-160 receivers. The retained precast prediction used `p+DataD/4`
and missed the observed centers; it remains unchanged as the preregistered
hypothesis. See `results/geometry-comparison.json` for observed values and
errors.


### Retail profile warning follow-up

The earlier profile warning coincided with the container overlay at 100% use
and zero available bytes. On October 18 follow-up, that same overlay had 3.8
GiB free and inode use was 7%. Wine resolved the Warcraft Documents path,
write/delete checks passed in CustomMapData and both save/profile directories,
and the Warcraft registry retained Allow Local Files=1. One control launch
reached the expected chapter card and gameplay HUD without the warning. The
exact profile operation that failed during the earlier full-overlay condition
was not recorded. Startup evidence is preserved in
`build-re/ability-re/ANfl-environment-diagnostic-02/`. The later rank-two
single-case trace used the Frida endpoint and is preserved separately under
`build-re/ability-re/ANfl-rank2-geometry-03/`.
