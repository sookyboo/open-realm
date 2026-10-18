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

**Verified runtime (new controlled cases):** a rank-one Amim level-1 secondary Footman and a secondary Footman after `SetUnitInvulnerable(target,true)` were each spatially delivered to the ANfl callback. In both cases the callback relationship gate returned `1`, then the callback's shared validator at RVA `0x00282180` (VA `0x00682180`) returned decimal `54` (`0x36`). Neither target reached a worker or damage receiver. Other selected targets received raw 85 damage. Amim was independently read back as ability level 1. The invulnerability setter call was recorded, but the fixture did not independently read back that state. Thus these captures establish callback rejection for the observed setups, while independent invulnerability-state introspection and the semantic name of rejection code `0x36` remain unresolved. These are callback-level validator rejections, not pre-callback query-mask exclusions or selected-but-suppressed damage.

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
a.vfunc(+0x20C) != 0
```

The candidate/source field ownership is established from the call frame: `+0x164`, `+0x264`, and `+0x268` are candidate CUnit fields; the listed virtual slots are on the source ability. **Verified runtime correlation:** the normal candidate returned zero and the Amim level-one candidate returned `0x36`, passed the relationship gate, and was not dispatched to a worker. No operand-level capture identifies the first divergence from normal, so the code must not be labeled a universal magic-immunity rule. The prior invulnerability case also returned `0x36`, but its state was not independently read back. The matching Retail JASS library declares `BlzIsUnitInvulnerable`; it was not called in that run. Separate built-in VA `0x006822E0` can return `0xBC`. Full analysis and pinned disassembly: `build-re/ability-re/ANfl-validator-36-static-01/validator-36-analysis.md` and `validator-disassembly-r2.txt`.

**Unresolved:** exact first query-stage exclusion for Player 1 allied and Player 15 Neutral Passive candidates; ordinary separately owned enemy behavior; independent invulnerability readback and its first divergent validator operand; runtime meaning of the `0x36` conjunction virtual returns and fields; flying, mechanical, structure, dead, hidden, and ethereal eligibility; and immunity behavior under other configuration. Do not generalize the Player 1 or Player 15 results to all owner relationships.

| Candidate setup | Spatial delivery | Query relation result | Callback gates | Worker/damage | Evidence |
|---|---|---|---|---|---|
| Neutral Hostile Player 12 living Footman | Yes | Accepted in tested setup | relation 1; validator 0 | selected according to sorted prefix | Runtime cases 19/21 and clean control |
| Same-owner Player 0 Footman | No callback delivery | Static same-owner rejection `0x84` when mask bit `0x2000` clear | Not reached | No worker | Callback absence runtime; exact return static |
| Magic-immune Player 12 Footman (`Amim` level 1) | Yes | Geometry passed | Relationship 1; shared validator `0x36` | No worker or receiver; no spell damage | `ANfl-state-alliance-ranks-01`, case 2 |
| Invulnerability requested on Player 12 Footman | Yes | Geometry passed | Relationship 1; shared validator `0x36` | No worker or receiver; no spell damage | `ANfl-state-alliance-ranks-01`, case 3; state operation issued, no independent readback |
| Mutually passive Player 1 Footman | No ANfl callback observed | Not narrowed; target absent at final-geometry and `0x006AD670` observations | No callback gates | No worker; other three selected targets received 85 | `ANfl-state-alliance-ranks-01`, case 4 |
| Neutral Passive Player 15 Footman | No callback observed | Absent at/before final geometry operands; broadphase vs earlier predicate unresolved | Not reached/observed | No worker; other three selected targets received 85 | `ANfl-neutral-passive-rank3-01`, case 5 |
| Separate ordinary enemy player | Untested | Unresolved | Unresolved | Unresolved | — |
| Other unit classes/states | Untested in controlled ANfl matrix | Unresolved | Unresolved | Unresolved | — |

Callback return `1` is continuation, not an eligibility result. A callback-level validator nonzero is a rejection code; zero continues candidate recording.

## Spatial geometry

**Authored data / corroborated rank-one model:** Area `A=125`, DataC `C=900`, DataD `D=300`.

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

This yields progress `[0,125,296.0526,475]`, radii `[125,171.0526,234.0720,300]`, and along-ray center offsets `[125,250,421.0526,600]`. The v3 trace captured acquisition-time caster `(-1072,-5968)` and target `(-880,-6084)`, then centers `(-965.01196,-6032.63867)`, `(-858.02386,-6097.27734)`, `(-711.61908,-6185.72998)`, and `(-558.45715,-6278.26563)` with radii `125`, `171.05263`, `234.07201`, and `299.99997`. These match within float rounding. JASS logged caster pre-order at `(-1180,-6084)`; it moved before acquisition, explaining why the earlier center formula was wrong. **Verified runtime rank three:** because Area/DataC/DataD are authored identically at all three ANfl ranks, rank-three case 7 generated the same four centers and radii, within float rounding. **Rank two:** authored inputs are also identical, but the bounded trace ended before case 6, so its query geometry is not runtime-confirmed. Exact float operation order, zero-length direction, and range clamps remain unresolved.

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

**Verified runtime (new):** the Amim and invulnerability treatments were rejected inside the candidate callback before list retention/worker dispatch, so these runs did not exercise damage suppression or mitigation. For both, the relationship gate passed and shared validator returned `54` (`0x36`). Amim level 1 was read back in JASS. Invulnerability was set by the supported JASS native but not independently read back. The normal matched control selected three targets and delivered raw 85 to each. **Unresolved:** meaning of `0x36`; receiver-side behavior if a defensive target reaches the worker; armor/defense category, spell reduction, ethereal, absorption, `MagicImmunesResistDamage` variation, adjusted amounts, and selected-but-suppressed damage. Do not describe the observed validator result as damage mitigation.

**Verified runtime rank three:** case 7 logged rank 3 and three receiver calls each carrying raw 250. Those targets had 210 maximum/current life and died; use the receiver payload, not life deltas, as the raw-damage result. Rank-three query radii were `125`, `171.05263`, `234.07201`, and `299.99997`; centers were `(-965.01196,-6032.63867)`, `(-858.02386,-6097.27734)`, `(-711.61908,-6185.72998)`, and `(-558.45715,-6278.26563)`. They match the rank-one progression because the three authored ranks share Area 125, DataC 900, DataD 300. Rank-two cast case 6 produced JASS 160 damage events, but native tracing had expired before that case; no new rank-two geometry result is claimed.

For the shared validator, a nonzero result is a rejection code. In particular, the statically proven `0x36` path is the exact conjunction documented above; runtime Amim correlation does not establish which term was decisive. The same-owner query rejection and early absences for different-owner allies and Neutral Passive must remain separate branches in an OpenRealm implementation until their native stages are distinguished.

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

## Evidence paths and next parity tests

- Clean control and trace: `build-re/ability-re/ANfl-clean-combat-01/` (map SHA-256 `4d4e664db24b81bd99f15343fc0163015e849cedbcd91ab34352c355023c76ce`).
- Exact built-in validator `0x36` analysis and pinned disassembly: `build-re/ability-re/ANfl-validator-36-static-01/`.
- Neutral Passive case 5, rank-three case 7, rank-two case 6, predictions, outputs, prepared map identity, and bounded trace: `build-re/ability-re/ANfl-neutral-passive-rank3-01/` (map SHA-256 `9ead2f225f2c8e625dd62d2a30091b2ae6dd6a03557c71ba8c848a987b3338c3`; embedded JASS SHA-256 `cbe5fd003ebf101d6dcdbc0a1915f74df53d8eeb1e348ba38fbc31597ed3157f`). Case 1/2 `*-validator-repeat.txt` files are stale copies and are not new evidence; `validator-detail-trace.jsonl` contains only `agent-ready` and is incomplete.
- Repaired geometry fixture, preflight, fresh JASS output, acquisition/query trace, and native comparison operands: `build-re/ability-re/ANfl-geometry-boundary-01/` (prepared-v3 map SHA-256 `9082fe582d52e7e4625a340f531ac77990b6bf4d74a98e45ebd139352bc54c1e`). The earlier failed distance fixture remains preserved at `build-re/ability-re/ANfl-geometry-distance-02/` and is not evidence.
- Query predicate Ghidra exports: `build-re/ability-re/ANfl-spatial-query-predicate-detail-03/`, `ANfl-spatial-query-shapes-detail-01/`, `ANfl-spatial-query-math-detail-01/`.
- Relation-filter evidence and prior same-owner observation: `build-re/ability-re/ANfl-target-eligibility-ally-01/`.
- Updated docs: `docs/games/warcraft-3/forked-lightning-retail.md`, `docs/games/warcraft-3/ability-probes/targeting.md`, `docs/games/warcraft-3/ability-probes/combat.md`.

Smallest useful next experiments: (1) add `BlzIsUnitInvulnerable` readback before/after setter and removal, then capture the first differing `0x36` operand against the matched normal target; (2) move the filtered trace to broadphase entry/shape dispatch and compare the same-position Player 1, Player 12, and Player 15 entries; (3) capture rank-two query geometry during an active trace window; (4) use one defense that remains callback-eligible and capture receiver-adjusted amount; (5) test an ordinary non-neutral enemy owner and distinguish it from Neutral Hostile/Passive. Rank-three raw damage and geometry are now verified. An exact comparator tie requires equal native metric bits and remains lower priority.

## Controlled immunity and startup follow-up (October 18, 2026)

The earlier `ANfl-state-alliance-ranks-01` attempt was called inconclusive because the Warcraft window was observed during the campaign transition. A reduced startup diagnostic based on the known-good clean-combat fixture then emitted `stage=map-initialization` and a separate handler result with `trigger_player=0`. Retrying the original prepared map after allowing its normal campaign intro to complete produced fresh case setup and cast outputs. No JASS or map correction was required to make the seven-case fixture enter gameplay; the earlier black window was a normal transition that had not finished. This identifies the earliest observed failing stage as **none in the script path**: the prior run ended before map/campaign initialization could be judged. The original failed trace remains preserved.

For normal case 1, JASS recorded an accepted order and three matching 85-damage events to targets 0, 1, and 2; the bounded native trace observed three workers and three receivers with payload amount 85. The case-2 Amim treatment (same Player 12 Footman type/position, `Amim` ability level read back as 1) produced an accepted order. Native geometry and callback traces show the treated spatial entry passed geometry and was delivered to ANfl callback. Its relationship gate returned 1 and shared validator returned decimal 54 (`0x36`) on each delivery. It was not retained for workers: the three workers/receivers addressed other eligible candidates. JASS left the treated Footman at 210 life while the three worker recipients received 85. This establishes callback-level rejection, not pre-callback filtering or receiver damage suppression.

Case 3 called `SetUnitInvulnerable(target,true)` on the matched secondary Footman. It too reached the callback, passed the relationship gate, and returned `0x36` from the shared validator; no worker or receiver targeted it. Three other targets received raw 85. The setup records the native call request, but there is no independent state readback in this fixture, so the exact invulnerability-state assurance is narrower than the Amim case. The exact static `0x36` return branch and conjunction were established in the later focused disassembly; the first runtime-divergent operand remains unknown. Raw output, predictions, map hashes, and bounded traces are under `build-re/ability-re/ANfl-state-alliance-ranks-01/`; startup sentinels and captured outputs are under `build-re/ability-re/ANfl-startup-diagnostic-01/`.

Case 4 changed target 1 to Player 1 and set mutual passive alliance with Player 0 (JASS confirmed both directional `IsPlayerAlly` checks). The target did not reach the ANfl callback or a worker; three Player 12 targets received raw 85. The target was absent from the captured final geometry comparator and from calls to VA `0x006AD670`; these hooks do not distinguish exclusion in broadphase enumeration from an earlier query predicate. Do not call this a confirmed owner-mask rejection until the earlier candidate path is observed.
