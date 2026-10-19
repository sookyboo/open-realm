# Forked Lightning (`ANfl`) Retail 1.29.2.9231 implementation specification

Executable SHA-256: `3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`; image base `0x00400000`. VA/RVA are distinguished below. This specification is evidence-bounded: **verified static**, **verified runtime**, **authored data**, **corroborated inference**, and **unresolved** are explicit labels.

## Rank data and normal accepted-order path

- **Authored data:** stock TFT `ANfl` DataA = `85, 160, 250`; DataB = `3, 3, 3` at ranks 1–3.
- **Verified static:** accessor VA `0x0046ED70` reads active rank row `+0x20` (DataA); VA `0x0046EE20` reads `+0x24` (DataB). Acquisition RVA `0x00878A50` propagates DataA to the per-target worker and uses DataB as the worker-count bound.
- **Verified runtime:** raw receiver payload amounts were 85 at rank one, 160 at rank two, and 250 at rank three. The rank-three cast produced three native receiver calls carrying raw 250; its 210-life targets died, so life loss is not the damage measure for that case.
- **Verified static and runtime:** normal accepted-order mode constructs repeated type-`0xB` spatial queries. Each candidate passing pre-callback geometry and query-mask predicates reaches ANfl callback RVA `0x00878FC0`. Inside that callback, relationship/mask gate must be nonzero; shared target validator must return zero. Accepted unique candidates are deduplicated by CUnit pointer and assigned 2D distance to explicit order target. Sort complete retained set, then invoke worker RVA `0x008788F0` for first `min(unique_count, DataB)`.
- **Verified static/runtime:** small-array comparator VA `0x00C78F60` compares distance ascending and then signed candidate CUnit dword `+0x0C` descending. Fully equal keys are unstable. Tie key's semantic identity and a true runtime tie remain unresolved.
- **Verified runtime:** cases 19 and 21 each enumerated five enemy Footmen, made 13 callback deliveries over overlapping queries, and matched saved predictions for the three workers. Case 19 selected `[0,1,2]`; case 21 selected `[0,3,2]`.

## Query-level filtering and callback gates

**Verified static:** query builder VA `0x0068EA00` parses the type-`0xB` radial query and installs predicate VA `0x00696BE0`; predicate chain is `0x00696BE0 → 0x006ADB90 → 0x006ADA20 → 0x006AD670`, prior to ANfl callback. ANfl authored mask `0x04010006` normalizes through `0x006AEA70` to `0xF5D10006`. In `0x006AD670`, equal source/candidate owner indices reject with code `0x84` when normalized mask bit `0x2000` is clear.

**Verified runtime:** in the same-owner case, a Player 0 `hfoo` was not delivered to callback while four Player 12 `hfoo` candidates were. The four delivered candidates passed callback relationship gate (`0x0027FB80` return 1) and shared validator (`0x00282180` return 0). **Corroborated inference:** the absent same-owner candidate was excluded by the static equal-owner `0x84` branch. Candidate-specific `0x84` has not been captured live. Player 12 is Neutral Hostile; this evidence does not establish ordinary player-owner enemy behavior.

**Verified runtime:** the Amim level-one secondary Footman reached the callback, passed its relationship gate, and received validator code `0x36`; it was not sent to a worker or receiver. The older invulnerability case recorded the same callback/validator outcome after a setter call, but had no state readback. A later getter-false case passed final geometry without observed callback/owner-filter events. The new reversible native-correlated experiment established the setter state and ordinary-damage effect; a fresh accepted ANfl cast with that active state did not select the treated target, but its callback path was not instrumented. Preserve each result and do not collapse them into a single exclusion stage.

**Verified runtime (new alliance case):** a Player 1 Footman at the same secondary position, with mutual Player 0/Player 1 `ALLIANCE_PASSIVE=true`, did not appear in the ANfl callback and received no worker. The cast still selected three Player 12 Footmen. This differs from the same-owner case (statically rejected by the owner relation function) and does not establish that all different-owner allies behave alike. The target-specific pointer was not observed at the final geometry comparator or filtered `0x006AD670` hook, so the exact earliest exclusion stage remains unresolved: spatial enumeration/broadphase or an earlier query predicate are still possible.

**Verified runtime (Neutral Passive, new):** a Player 15 Footman (`hfoo`) at `(-720,-6160)` was alive, stationary, and at 210 life after the five-second setup. It was absent from the final geometry operand observations and from the target-specific owner-relation, callback, worker, and receiver observations. A matched Player 12 Footman at the same position was present in the geometry/callback trace. The cast selected the other three Player 12 targets. This narrows Neutral Passive exclusion to broadphase enumeration or a predicate at/before the final geometry operands; it does not identify which one. Player 12 is Neutral Hostile, so the observation must not be generalized to ordinary enemy owners.

**Verified static (`0x36`):** shared validator VA `0x00682180` invokes built-in predicate VA `0x00682210` before its registered-validator walk. That built-in returns `0x36` at VA `0x006822CE` only when this conjunction holds for candidate unit `u` and source ability `a`:

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

The candidate/source field ownership is established from the call frame: `+0x164`, `+0x264`, and `+0x268` are candidate CUnit fields; the listed virtual slots are on the source ability. **Verified runtime:** the same accepted case-2 cast in `ANfl-validator-operands-postcall-07/` delivered an ordinary Player 12 Footman with selected `+0x264=0` to the built-in validator, which returned zero at the early `jle`; its level-one Amim candidate had selected `+0x264=1` and returned `0x36` after source `+0x20C=0`. The `+0x20C` final term is equality to zero. The selected field is the first observed normal/Amim divergence, but its writer and semantic name remain unresolved. Separate built-in VA `0x006822E0` can return `0xBC`. Full analysis and pinned disassembly: `build-re/ability-re/ANfl-validator-36-static-01/validator-36-analysis.md` and `validator-disassembly-r2.txt`.

**Verified static and runtime (invulnerability natives):** exact-build registration VA `0x0049B3C0` binds JASS `SetUnitInvulnerable(Hunit;B)V` to VA `0x004AB600` / RVA `0x000AB600`, and `BlzIsUnitInvulnerable(Hunit;)B` to VA `0x00499FA0` / RVA `0x00099FA0`. The getter resolves the unit and returns `(~(dword[resolved+0x20] >> 3)) & 1`. A same-unit read-only Frida trace matched JASS handle `0x101DAA` to getter/setter-resolved CUnit `0x103F2350`; its `+0x20` changed `0x1646 → 0x164E → 0x1646` across setter true/false, and getter results changed `true → false → true`. The setter separately resolved attached object `0x0D7A4DF0`, tag `0x2B61676C`, with `+0x20 = 0`. The CUnit pointer and attached-object pointer are distinct. This establishes the getter's bit transition and setter/getter identity correlation. The exact vtable implementation/writer behind slot `+0xA8` and the tag's class meaning remain unresolved.

**Verified runtime gameplay effect:** in `ANfl-invulnerability-reversible-02`, ordinary `UnitDamageTarget` requested 20 normal damage against the same 210-life Footman before, during, and after the reversible setter sequence. Before: getter true, receiver/JASS event amount 17.857, life `210 → 192.143`; after setter true: getter false, event amount 0, life unchanged; after setter false: getter true, amount 17.857, life `192.143 → 174.286`. Thus in this tested configuration getter false plus bit 3 set corresponds to damage immunity, while getter true plus bit clear is damageable. `UnitDamageTarget` returned true in each phase and therefore did not itself distinguish applied damage. This is independent gameplay confirmation for this ordinary-damage case, not proof that every damage category is blocked.

**Unresolved:** exact first query-stage exclusion for Player 1 allied and Player 15 Neutral Passive candidates; ordinary separately owned enemy behavior; why the old setter-without-readback invulnerability case reached the callback; `+0x264/+0x268` native writer and meaning; source ability `+0x1F0` implementation; flying, mechanical, structure, dead, hidden, and ethereal eligibility; and immunity behavior under other configuration. The matched normal/Amim selected operand and executed branch path are now verified; do not generalize the Player 1 or Player 15 results to all owner relationships.

**Verified runtime operand observation (Amim follow-up):** in
`ANfl-invulnerability-readback-01`, the level-one Amim target at
`(-720,-6160)` was matched to native candidate `0x10875a74`. It passed the
final geometry check and callback relationship gate, then returned `0x36`
from the shared validator. Its candidate dword `+0x164` was `0x245`, while
signed `+0x264` and `+0x268` were both `1`. A normal Footman candidate in the
same cast had `+0x164 = 0x245`, `+0x264 = 0`, `+0x268 = 0`, and validator
return zero. The target remained at 210 life and had no worker/receiver call.
This is a measured field difference, not proof that either field is the
selected operand or the cause: the source `+0x1F0` selector was not captured
reliably. The virtual-return trace contains slot/address aliasing and
contradictory or missing returns, so it is not used to assign meanings to
those values. Raw trace, output, and bounded comparison are retained under
`build-re/ability-re/ANfl-invulnerability-readback-01/`.

**Verified runtime invulnerability state and damage effect (new):** a
reversible probe matched JASS handle `0x101DAA` to CUnit `0x103F2350`. Its
`+0x20` dword changed `0x1646 → 0x164E → 0x1646` across
`SetUnitInvulnerable(true/false)`, while the getter returned
`true → false → true`. The setter's attached object was distinct at
`0x0D7A4DF0`, with tag `0x2B61676C`. A matched ordinary-damage probe requested
20: normal damage applied 17.857, active setter state applied zero, and the
restored state again applied 17.857. The JASS native returned true in all
three phases, so actual life changes and event amounts establish the effect.
In a separate accepted rank-one cast, a getter-false treated target remained
at 210 and did not appear among the three 85-damage recipients. That run did
not instrument callback/validator delivery. An older setter case did reach
callback and return `0x36`, but had no independent getter/state readback; it
does not prove that the setter activated the same state. Native bit semantics
are now correlated with ordinary damage immunity; the active target's exact
ANfl exclusion stage and the discrepancy between the historical callback
trace and current case remain unresolved. Results are in
`build-re/ability-re/ANfl-invulnerability-reversible-02/`.

**Verified runtime rank-two geometry:** the single-case trace in
`ANfl-rank2-geometry-03` captured four queries, radii
`[125,171.05263,234.07201,299.99997]`, three workers, and three raw receiver
payloads of 160. Observed centers match `p + Area` along the acquisition ray;
the preregistered `p + DataD/4` centers missed by approximately 50 world units.
The immutable prediction and corrected comparison are both retained at
`ANfl-rank2-geometry-03/predictions/case-6-precast.json` and
`ANfl-rank2-geometry-03/results/geometry-comparison.json`.

| Candidate setup | Spatial delivery | Query relation result | Callback gates | Worker/damage | Evidence |
|---|---|---|---|---|---|
| Neutral Hostile Player 12 living Footman | Yes | Accepted in tested setup | relation 1; validator 0 | selected according to sorted prefix | Runtime cases 19/21 and clean control |
| Same-owner Player 0 Footman | No callback delivery | Static same-owner rejection `0x84` when mask bit `0x2000` clear | Not reached | No worker | Callback absence runtime; exact return static |
| Magic-immune Player 12 Footman (`Amim` level 1) | Yes | Geometry passed | Relationship 1; shared validator `0x36` | No worker or receiver; no spell damage | `ANfl-state-alliance-ranks-01`, case 2 |
| Active invulnerability state on Player 12 Footman | Fresh accepted cast; active state independently confirmed in matched reversible run | Not captured in the same trace | Callback/validator path not instrumented in fresh cast; older unconfirmed setter case reached validator `0x36` | No worker/receiver for treated target; other three got 85 | `ANfl-invulnerability-reversible-02/` plus historical cases |
| Mutually passive Player 1 Footman | No ANfl callback observed | Not narrowed; target absent at final-geometry and `0x006AD670` observations | No callback gates | No worker; other three selected targets received 85 | `ANfl-state-alliance-ranks-01`, case 4 |
| Neutral Passive Player 15 Footman | No callback observed | Absent at/before final geometry operands; broadphase vs earlier predicate unresolved | Not reached/observed | No worker; other three selected targets received 85 | `ANfl-neutral-passive-rank3-01`, case 5 |
| Separate ordinary enemy player | Untested | Unresolved | Unresolved | Unresolved | — |
| Other unit classes/states | Untested in controlled ANfl matrix | Unresolved | Unresolved | Unresolved | — |

Callback return `1` is continuation, not an eligibility result. A callback-level validator nonzero is a rejection code; zero continues candidate recording.

## Spatial geometry

**Authored data / runtime-verified ranks 1–3:** Area `A=125`, DataC `C=900`, DataD `D=300` at each rank. Runtime query traces exist for ranks 1, 2, and 3.

```text
L = max(A + D, C - (A + D)) = 475
p0 = 0
r(p) = A + p * (D - A) / L
center(p) = acquisitionCasterPosition
          + normalize(acquisitionTargetPosition - acquisitionCasterPosition)
            * (p + A)
pNext = min(p + r(p), L)
query at p; stop after query where p == L
```

This yields progress `[0,125,296.0526,475]`, radii `[125,171.0526,234.0720,300]`, and along-ray center offsets `[125,250,421.0526,600]`. Rank-one and rank-three traces captured the four centers and radii in the earlier boundary and rank-three fixtures. **Verified runtime rank two (new):** the single-case run captured four queries with radii `125`, `171.05263`, `234.07201`, and `299.99997`; observed centers were `(-965.01196,-6032.63867)`, `(-858.02386,-6097.27734)`, `(-711.61908,-6185.72998)`, and `(-558.45715,-6278.26563)`. With acquisition-time caster `(-1072,-5968)` and target `(-880,-6084)`, these match the `p + A` offsets within float rounding. The pre-cast rank-two file retained an older `p + DataD/4` center prediction; that prediction missed by about 50 world units along the query ray and is preserved as a historical prediction, not counted as a match. Exact float operation order, zero-length direction, and range clamps remain unresolved.

**Verified static query predicate:** type-`0xB` shape dispatch reaches VA `0x00807130` through `0x007F4CF0`. The query radius is normalized by 32 before comparison. The enumerator computes squared 2D center distance, adds spatial-entry dword `+0x90` to normalized radius, squares the sum, then accepts inclusively:

```text
dx = candidateX - centerX
dy = candidateY - centerY
s = spatialEntry[+0x90]  // internal query units; gameplay meaning unresolved
inside = dx*dx + dy*dy <= (radius/32 + s)*(radius/32 + s)
```

The earlier bounds pass is a broadphase. In `ANfl-geometry-boundary-01`, the native comparison operands show `s=0.96875` (`0x3f780000`) for observed Footman entries, making the tested effective radial extent 31 world units (`32*s`). A candidate at query 2 had native distance-squared `39.85868` against boundary-squared `39.86842` and reached the callback. Another candidate failed final-circle checks for queries 3 and 4 (`199.56389 > 68.61636`; `184.66995 > 106.99314`) and was not delivered. Correlation of that second native pointer to JASS target index 3 is inferred from allocation stride. Exact equality and the broadphase boundary remain untested. The scalar's gameplay name/source remain unresolved; do not call it collision radius without a producer link.

The harness preflight at `build-re/ability-re/ANfl-geometry-boundary-01/preflight.py` checked assignment, chat, finish/output IDs, unique filenames, canonical manifest IDs, embedded JASS identity, archive hash, and stale identifiers. It passed for prepared-v3.

## Damage and mitigation

Native flow: per-target worker → `CMissileForkedLightning` callback → shared damage helper RVA `0x002EB2B0` (VA `0x006EB2B0`) → payload initializer → CUnit receiver VA `0x006677C0` via virtual `+0x120` → negative adjusted amount via virtual `+0x128`.

| Payload field | Observed | Classification |
|---|---:|---|
| `+0x00` | caster CUnit pointer | Verified runtime |
| `+0x0C` | `1` | Verified runtime; flag meaning unresolved |
| `+0x10` | 85/160/250 | Verified runtime ranks 1/2/3 |
| `+0x14` | `0x400` | Verified runtime; named damage type unresolved |
| `+0x20` | `0` | Verified runtime; selector meaning unresolved |

**Verified static:** receiver checks target raw-state `+0x164 & 0x100`, payload flag `+0x0C & 0x04`, configuration `MagicImmunesResistDamage`, attached callbacks and adjustment helpers before life commit. These checks do not yet establish which named defense they represent for this payload.

**Verified runtime clean baseline:** `ANfl-clean-combat-01` zeroed ordinary attack base damage and dice on the caster and five targets, cleared nearby local units, held targets, and captured a five-second no-cast interval. All targets stayed at 210 life across 21 samples. A rank-one cast matched prediction `[0,1,2]`, reached three receivers with raw 85, emitted three matching JASS damage events, and reduced selected targets to about 125; nonselected targets remained at 210. Caster health changed during the run and is excluded as a clean measurement. This validates baseline attribution only.

**Verified runtime:** the Amim treatment was rejected by the callback validator and did not reach damage dispatch. The same accepted cast in `ANfl-validator-operands-postcall-07/` also recorded an ordinary candidate's selected-field early zero return; its JASS case-2 damage events were not a clean combat isolation. The earlier invulnerability case had the same observed callback/validator outcome without state readback, while the later confirmed active-state case was filtered earlier by query target mask. Neither run tests receiver mitigation. **Unresolved:** receiver-side behavior for an eligible defensive target; armor/defense category, spell reduction, ethereal, absorption, `MagicImmunesResistDamage` variation, adjusted amounts, and selected-but-suppressed damage. Do not describe the observed validator result as damage mitigation.

**Verified runtime rank three:** case 7 logged rank 3 and three receiver calls each carrying raw 250. Those targets had 210 maximum/current life and died; use the receiver payload, not life deltas, as the raw-damage result. Rank-three query values match the common progression. **Verified runtime rank two (new):** a fresh single-case accepted cast logged rank 2, four query centers/radii matching the `p + Area` progression, three workers, and three receiver calls carrying raw 160. Three JASS damage events also recorded 160. The targets remained alive; the native payload confirms raw damage. The immutable pre-cast prediction is `build-re/ability-re/ANfl-rank2-geometry-03/predictions/case-6-precast.json`; it predicted the older `p + DataD/4` center offset, so query centers did not match that part of the written prediction. `results/geometry-comparison.json` records the mismatch and comparison against the corrected center model.

For the shared validator, a nonzero result is a rejection code. In the matched runtime comparison, selector `+0x1F0=0` chose candidate `+0x264`: zero on the ordinary Footman returned early with zero, while positive one on the Amim-associated Footman continued through the later checks to `0x36`. This identifies the first observed normal/Amim divergence, but not the field's writer or semantic name. The same-owner query rejection and early absences for different-owner allies and Neutral Passive must remain separate branches in an OpenRealm implementation until their native stages are distinguished.

## Implementation pseudocode (proven portion)

```text
for each generated type-B query:
    enumerate broadphase spatial entries
    for each spatial entry passing inclusive expanded-radius predicate:
        if query-level target-mask predicate rejects: continue
        ANflCandidateCallback(candidate):
            if callback relationship gate == 0: return continue_enumeration
            if shared validator(candidate) != 0: return continue_enumeration
            if candidate pointer already retained: return continue_enumeration
            retain(candidate, distance2D(candidate, explicitOrderTarget))
            return continue_enumeration

sort retained by (distance ascending, signed candidate[+0x0C] descending)
for candidate in retained[0:min(count, DataB)]:
    dispatch ANfl worker with DataA
    dispatch observed damage payload (flags=1, type/category=0x400, selector=0)
```

Do not assume a stable tie, exact candidate scalar meaning, or named damage type.
The getter's state is tied to ordinary damage prevention: false while setter
state is active, true after clearing it. The confirmed active-state ANfl
candidate was rejected by query-level target-mask filtering (`0x96`) after
passing geometry and before callback validation. For validator `0x36`, retain
the static conjunction, and apply the observed early return when the selected
candidate field is nonpositive; for ANfl the captured selector was zero and
selected `+0x264`. The field's broader semantics and writer remain unresolved.

## Evidence paths and next parity tests

- Clean control and trace: `build-re/ability-re/ANfl-clean-combat-01/` (map SHA-256 `4d4e664db24b81bd99f15343fc0163015e849cedbcd91ab34352c355023c76ce`).
- Rank-two accepted cast, prediction, setup/cast outputs, and bounded native query/worker/receiver trace: `build-re/ability-re/ANfl-rank2-geometry-03/` (map SHA-256 `0bd800973a9f103d974d7a906ca85ad80e3a3a2b6198e00501ff8e79209b106e`; embedded JASS SHA-256 `acbab2178d12d3ec2bc17d4309c5c8f24493eeaa01fd35a2b785115b296a9d0a`; trace SHA-256 `a5929e6b0cab827cffb8dd427c79342c8342d99c069852ca2ee6feec3f0dfe06`). `results/geometry-comparison.json` records observed versus preregistered and corrected center models.
- Exact built-in validator `0x36` analysis and pinned disassembly: `build-re/ability-re/ANfl-validator-36-static-01/`.
- Exact-build invulnerability native registration and getter/setter decompilation: `build-re/ability-re/ANfl-invulnerability-static-followup-01/` and `build-re/ability-re/ANfl-invulnerability-native-impl-01/`; JASS getter and contradictory callback-stage trace: `build-re/ability-re/ANfl-invulnerability-readback-01/`.
- Reversible native-correlated state, ordinary-damage control, fresh accepted active-state cast, hashes, and machine-readable comparison: `build-re/ability-re/ANfl-invulnerability-reversible-02/`. Comparison: `results/invulnerability-comparison.json`; native setter/getter trace: `runtime/invulnerability-focused.jsonl`; direct damage output: `results/damage.txt`; accepted cast output: `results/anfl-cast-3.txt`.
- Neutral Passive case 5, rank-three case 7, rank-two case 6, predictions, outputs, prepared map identity, and bounded trace: `build-re/ability-re/ANfl-neutral-passive-rank3-01/` (map SHA-256 `9ead2f225f2c8e625dd62d2a30091b2ae6dd6a03557c71ba8c848a987b3338c3`; embedded JASS SHA-256 `cbe5fd003ebf101d6dcdbc0a1915f74df53d8eeb1e348ba38fbc31597ed3157f`). Case 1/2 `*-validator-repeat.txt` files are stale copies and are not new evidence; `validator-detail-trace.jsonl` contains only `agent-ready` and is incomplete.
- Repaired geometry fixture, preflight, fresh JASS output, acquisition/query trace, and native comparison operands: `build-re/ability-re/ANfl-geometry-boundary-01/` (prepared-v3 map SHA-256 `9082fe582d52e7e4625a340f531ac77990b6bf4d74a98e45ebd139352bc54c1e`). The earlier failed distance fixture remains preserved at `build-re/ability-re/ANfl-geometry-distance-02/` and is not evidence.
- Query predicate Ghidra exports: `build-re/ability-re/ANfl-spatial-query-predicate-detail-03/`, `ANfl-spatial-query-shapes-detail-01/`, `ANfl-spatial-query-math-detail-01/`.
- Relation-filter evidence and prior same-owner observation: `build-re/ability-re/ANfl-target-eligibility-ally-01/`.
- Updated docs: `docs/games/warcraft-3/forked-lightning-retail.md`, `docs/games/warcraft-3/ability-probes/targeting.md`, `docs/games/warcraft-3/ability-probes/combat.md`.

Smallest useful next experiments: (1) capture the active invulnerability target from spatial enumeration through query predicates, callback, validator, and retained-list insertion in one accepted cast; (2) use instruction-local validator post-call captures for matched normal and Amim candidates; (3) trace same-position Player 1, Player 12, Player 15, and ordinary hostile owner candidates from broadphase entry/shape dispatch; (4) choose one verified defensive modifier that remains callback-eligible and capture receiver-adjusted amount; (5) test an ordinary non-neutral enemy owner. Rank-one through rank-three query geometry and raw damage are complete. An exact comparator tie requires equal native metric bits and remains lower priority.

## Controlled immunity and startup follow-up (October 18, 2026)

The earlier `ANfl-state-alliance-ranks-01` attempt was called inconclusive because the Warcraft window was observed during the campaign transition. A reduced startup diagnostic based on the known-good clean-combat fixture then emitted `stage=map-initialization` and a separate handler result with `trigger_player=0`. Retrying the original prepared map after allowing its normal campaign intro to complete produced fresh case setup and cast outputs. No JASS or map correction was required to make the seven-case fixture enter gameplay; the earlier black window was a normal transition that had not finished. This identifies the earliest observed failing stage as **none in the script path**: the prior run ended before map/campaign initialization could be judged. The original failed trace remains preserved.

For normal case 1, JASS recorded an accepted order and three matching 85-damage events to targets 0, 1, and 2; the bounded native trace observed three workers and three receivers with payload amount 85. The case-2 Amim treatment (same Player 12 Footman type/position, `Amim` ability level read back as 1) produced an accepted order. Native geometry and callback traces show the treated spatial entry passed geometry and was delivered to ANfl callback. Its relationship gate returned 1 and shared validator returned decimal 54 (`0x36`) on each delivery. It was not retained for workers: the three workers/receivers addressed other eligible candidates. JASS left the treated Footman at 210 life while the three worker recipients received 85. This establishes callback-level rejection, not pre-callback filtering or receiver damage suppression.

Case 3 called `SetUnitInvulnerable(target,true)` on the matched secondary Footman. It too reached the callback, passed the relationship gate, and returned `0x36` from the shared validator; no worker or receiver targeted it. Three other targets received raw 85. The setup records the native call request, but there is no independent state readback in this fixture, so the exact invulnerability-state assurance is narrower than the Amim case. The exact static `0x36` return branch and conjunction were established in the later focused disassembly; the first runtime-divergent operand remains unknown. Raw output, predictions, map hashes, and bounded traces are under `build-re/ability-re/ANfl-state-alliance-ranks-01/`; startup sentinels and captured outputs are under `build-re/ability-re/ANfl-startup-diagnostic-01/`.

Case 4 changed target 1 to Player 1 and set mutual passive alliance with Player 0 (JASS confirmed both directional `IsPlayerAlly` checks). The target did not reach the ANfl callback or a worker; three Player 12 targets received raw 85. The target was absent from the captured final geometry comparator and from calls to VA `0x006AD670`; these hooks do not distinguish exclusion in broadphase enumeration from an earlier query predicate. Do not call this a confirmed owner-mask rejection until the earlier candidate path is observed.


## Environment follow-up and investigation status

The earlier Retail profile dialog occurred while the overlay containing
`/home/agent/.wine-war3` had zero available bytes. A later bounded check found
3.8 GiB free and 7% inode use; Wine Documents/save/profile path checks passed,
and the pinned Retail control map reached both chapter card and gameplay HUD.
No files were removed. The precise profile write that failed earlier is
unresolved. Evidence is in
`build-re/ability-re/ANfl-environment-diagnostic-02/`. The Frida endpoint
`127.0.0.1:27043` was unavailable during the environment-only control check, but
was subsequently available for the rank-two capture in
`ANfl-rank2-geometry-03`. Player 1/Player 15 first exclusion stage, invulnerability
readback and `0x36` operand divergence, earliest Player 1/Player 15 query
exclusion, and eligible-target damage mitigation remain open. Rank-two geometry
is now covered by `ANfl-rank2-geometry-03`; its comparison documents that the
pre-cast `DataD/4` center prediction was wrong and that observed centers match
the corrected `p + Area` model.

## October 19 native-binding follow-up

Verified the Retail executable hash again and inspected the existing exact-build Ghidra exports for native registration VA `0x0049B3C0`, getter VA `0x00499FA0`, and setter VA `0x004AB600`. No new Ghidra export, Retail launch, accepted cast, rejected cast, Frida hook, prepared map, or JASS output was created in this continuation. Reused evidence is under `ANfl-invulnerability-static-followup-01/`, `ANfl-invulnerability-native-impl-01/`, and `ANfl-invulnerability-readback-01/`. The four documentation/specification files listed above were modified. Documentation validation was `git diff --check`; it passed. `make test TEST_JOBS=4` was skipped because no C source, header, or relevant C build configuration changed.

## October 19 confirmed-invulnerability candidate-trace attempt

A fresh scenario and prepared map were created under
`build-re/ability-re/ANfl-invulnerability-candidate-trace-01/`. The generated
map embeds a unique scenario ID and its script was verified byte-for-byte by
the Retail probe runner. The bounded Frida agent correlates
`BlzIsUnitInvulnerable` calls through the resolver to a CUnit pointer, samples
that CUnit's `+0x20` bit 3, records query-predicate and filter arguments,
captures final-geometry candidates and their `+0x20/+0x164/+0x264/+0x268`
fields, and observes the callback, relationship gate, shared validator,
worker, and damage receiver. Its hook-load check passed for Retail image base
`0x00400000`.

No gameplay result was obtained. Two control-map launches left a Retail
process without a visible X window; no screenshot or gameplay HUD could be
confirmed, so the prepared map was not launched and no scenario chat command
or ANfl cast was issued. Treat this as an environment failure. It adds no
evidence about the active invulnerability target's first exclusion stage,
validator `0x36`, owner filtering, or mitigation. The launch attempts, hashes,
agent-load-only trace, and failure classification are recorded in
`build-re/ability-re/ANfl-invulnerability-candidate-trace-01/README.md` and
`runtime/attempt-manifest.json`. Earlier reversible-state and historical
callback observations remain unchanged.

## October 19 confirmed-invulnerability candidate trace (successful retry)

The follow-up trace is preserved at
`build-re/ability-re/ANfl-invulnerability-candidate-trace-02/`. Retail hash,
prepared map hash, and embedded JASS hash are recorded in its README and
scenario artifacts. The accepted rank-one cast treated secondary target index
1 without changing owner, type, or placement. JASS handle pointer `0x101d74`
resolved to CUnit `0x0f166128` and spatial entry `0x0fdb5b78`; before query
acquisition CUnit `+0x20` was `0x164e`, bit 3 was set, and the native getter
returned false. The target had life 210 and its spatial entry had `+0x90 =
0.96875`.

**Verified runtime:** the candidate passed final geometry in queries 2–4. In
each it reached query predicate `0x00696BE0`, filter `0x006ADB90`, and
target-mask function `0x006ADA20`. Candidate flags were `0x55a00002`; normal
Footmen in the same trace had `0x55900002`. ANfl raw mask was `0x04010006`,
normalized to `0xf5d10006`. The target-mask function returned `0x96`,
propagating to a zero query-predicate result. Exact-build static export
`ANfl-query-relation-helper-04/decompiled.jsonl` ties the `0x100000` versus
`0x200000` target class difference to CUnit `+0x20` bit 3 and shows the
normalized ANfl mask excludes the bit-3-set category. The first observed
exclusion is query-level target-mask filtering, before owner/relation
filtering, ANfl callback, relationship gate, shared validator, retention,
selection, worker, or receiver. Three other selected targets reached
worker/receiver with raw damage 85.

This explains why the confirmed active-state target does not reach validator
`0x36`. The historical callback-level `0x36` candidate lacked getter and bit
readback; its actual state remains unknown. A different state or candidate
path is possible but unproven. Preserve both observations with these limits.

The earlier sign on the last term was incorrect. Static instruction
`0x006822C3` tests the `+0x20C` return and branches on zero to the `0x36`
return at `0x006822CE`. The matched instruction-local comparison in
`ANfl-validator-operands-postcall-07/` has an ordinary candidate CUnit
`0x0fb559ec` with `+0x164=0x244`, `+0x264=0`, `+0x268=0`; source ability
`0x03067580` returned `+0xD8=0`, `+0x1F0=0`, selecting `+0x264`. It reached
the `jle` site at `0x0068225B`, no subsequent built-in predicate sites,
and validator return zero. The Amim-associated candidate `0x0fb55f08` had
`+0x164=0x245`, `+0x264=1`, `+0x268=1`; the source selector was again zero,
selecting the positive `+0x264`. It continued through `+0x1D8=1`,
`+0x1FC=0`, config value zero, and `+0x20C=0`, then returned `0x36`.
Candidate predicate and `+0x1F8` are short-circuited. Stalker did not expose
EFLAGS; branch flow follows the executed instruction sequence and exact
disassembly. The source map auto-ran case 2 (Amim on target index 1) despite
the initial manifest describing case 1; this provenance mismatch is recorded
in `results/validator-comparison.json`, and the corrected manifest intent was
not silently substituted. The ordinary candidate-to-JASS handle mapping is
not direct, while the CUnit pointer and validator invocation are correlated.
The runtime identifies `+0x264` as the first observed normal/Amim divergence,
but static raw-offset stores do not yet identify its CUnit writer. Field
semantics and writer, the `+0x1F0` implementation, Player 1/Player 15
earliest rejection, ordinary hostile-player behavior, and receiver-side
mitigation remain open. The invulnerable candidate was removed before the
receiver, so it supplies no mitigation measurement.

### Implementation-ready eligibility update

For candidates delivered by ANfl's spatial query, apply the query target-mask
test before owner/relation filtering and callback validation. In the verified
active invulnerability state, target classification derived from CUnit
`+0x20` bit 3 is the `0x200000` category; normalized ANfl mask `0xf5d10006`
does not include it, so the candidate fails target-mask filtering (`0x96`)
even after passing geometry. Do not route it to the callback or worker.
Keep target-flag construction and mask normalization as separate helpers; this
evidence does not establish every category mapping. Candidates that pass query
filtering still use the existing callback relationship gate and shared
validator. `0x36` operand semantics, allied/Neutral Passive rejection stage,
and receiver mitigation remain unresolved and must not be inferred from this
case.
