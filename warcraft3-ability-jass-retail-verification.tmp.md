# WC3 Ability Retail Verification — Temporary JASS Plan

Status: Charm's stock target exclusions and creep-level boundary, stock
`Apg2` friendly/hostile movement distinction, Serpent Ward ranks 1–2 summon
identity and rank 1 expiry, Mana Flare lifecycle end conditions, and Mana
Shield rank 1 depletion are verified as described below. Sentry Ward expiry
and placement offset remain unresolved; the remaining scenarios are proposed
follow-up work. This
is a scratch document for resolving the narrow retail-behavior questions in
[`warcraft3-ability-completion-implementation.tmp.md`](warcraft3-ability-completion-implementation.tmp.md).
It does not replace headless regression tests or the project test rules.

## What this can establish

A controlled retail map with JASS can establish externally visible ability
behavior. It cannot expose every internal field or exact callback order. Use
Frida or Ghidra/r2 only when a question remains ambiguous after controlled
observations, or asks about an internal detail JASS cannot query.

The repository already documents extracting/copying and instrumenting a retail
map, MPQ member replacement, and launching the copy under Wine in
[`retail-camera-tracing.md`](docs/games/warcraft-3/retail-camera-tracing.md).
An isolated stock-map construction and retail observation example is in
[`cursor-rendering.md`](docs/games/warcraft-3/cursor-rendering.md). Those are
precedents, not a ready-made ability test map. Keep the original retail map
unchanged and preserve an untouched control copy.

## Shared test-map method

1. Choose the exact retail executable/data version and record executable
   version/hash, map source, and ROC/TFT mode. A TFT-only ability needs a TFT
   reference map. Inspect `war3map.j` for ability availability changes and
   identify when cinematic restrictions are restored. Verify the untouched
   map loads before instrumenting it.
2. Create a small isolated scenario on a copied map: one caster, only the
   needed target classes, known owners/positions/stats, no unrelated AI or
   combat, and a fixed starting state. Use stock ability rows first. For field
   interpretation questions, make a second map with a copied ability row and
   change one candidate field at a time in the object editor.
3. Use JASS initialization to place/configure units and register triggers.
   Issue the ability or attack through ordinary orders. Do not call private
   implementation helpers. A periodic timer should record elapsed simulation
   time and observable state with `BJDebugMsg` (or another in-game text
   channel): unit identity/type/owner, position, life, mana, movement speed,
   ability rank, and the relevant order/lock observations available to JASS.
4. Sample densely enough for the question, then repeat with one variable
   changed: one target moved, different starting mana, one extra hit target,
   or one ability data field. Repeat symmetric-target cases to check whether
   the result is deterministic. Compare against an untouched control and
   retain the exact map/script and captured log outside source fixtures.
5. State the observation and its resolution. Timer sampling proves behavior
   only to its sampling/frame resolution; it does not reveal an exact native
   callback time. Convert confirmed contracts into deterministic synthetic
   fixture tests through OpenRealm's production paths.

Avoid deriving damage from uncontrolled combat. Use isolated targets, record
initial and sampled life, and account for authored armor/regen. For passives,
record that the caster's current order and position remain unchanged where
JASS exposes those observations; do not infer a hidden internal order state.

## Completed JASS case: Charm target acceptance

Retail Charm (`ANch`) was exercised on October 4, 2026, using the Prologue
campaign map and the Wine-installed Warcraft III executable with SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`. The
temporary JASS probe created four independent Player 0 Blood Mage casters with
`ANch` and issued the ordinary `charm` order at Player 12 targets: a level-3
neutral-hostile creep (`nftt`), a Paladin Hero (`Hpal`), a killed `nftt` corpse,
and a live `nftt` carrying permanent Resistant Skin (`ACsk`). A four-second
timer recorded target owners, Hero type, corpse life, and Resistant Skin level
through `PreloadGen*`.

Observed result:

    CHARMTEST validOwner=0 heroOwner=12 corpseOwner=12 resistantOwner=12 heroType=1215324524 corpseLife=0.000 resistantSkinLevel=1

The level-3 creep transferred to Player 0; the Hero, dead corpse, and Resistant
Skin target remained with Player 12. The zero corpse life and skin level 1
confirm those two setups.

## Completed JASS case: Charm creep-level boundary

A follow-up retail map tested stock `ANch` against its `DataA=5` level limit.
The stock `nftt` UnitData row was overridden locally to level 5, and separate
organic unit copies at levels 3, 4, 5, and 6 were also created. The stock-row
level-5 target and custom levels 4 and 5 transferred; the custom level-6 target
did not. The output was:

    CHARMTEST validOwner=0 validLevel=5 heroOwner=12 corpseOwner=12 resistantOwner=12 heroType=1215324524 corpseLife=0.000 resistantSkinLevel=1 L3=3 owner3=12 L4=4 owner4=0 L5=5 owner5=0 L6=6 owner6=12

This verifies acceptance through level 5 and rejection at level 6 for the
tested stock `ANch` configuration. The custom level-3 copy unexpectedly stayed
with Player 12, although the ordinary stock level-3 `nftt` transferred in the
earlier test. That discrepancy is unexplained; do not use the custom level-3
result to infer the boundary. Other aliases, resource accounting, and other
retail builds remain untested.

## Completed JASS case: Purge friendly versus hostile movement effect

Retail TFT `Apg2` was added to two Player 0 `Hblm` casters. One cast targeted a
Player 0 `hfoo`, the other a Player 12 `hfoo`; each moving target had an
unpurged same-owner `hfoo` control on a parallel lane. The orders spent about
75 mana after regeneration. At 1.5 seconds, the allied target moved 382.881
units versus 403.491 for its control. The hostile target moved 80.865 versus
385.253 for its control at 1.5 seconds, and 108.837 versus 608.150 at 3.5
seconds. This supports enemy-only immobilization/slow for stock `Apg2`; it does
not measure the exact recovery curve or whether an allied cast dispels buffs.
The complete setup and raw output are in
[`ability-verification-review.md`](docs/games/warcraft-3/ability-verification-review.md#retail-purge-friendly-and-hostile-target-verification-october-4-2026).

## Completed JASS case: Sentry Ward summon identity sample

This is **Sentry Ward** (`Aeye`), not Serpent Ward (`AOsw`). Retail TFT data
identifies the Sentry Ward command as `evileye`; `ward` is the Serpent Ward
order. The stock TFT Sentry Ward ability row authors `UnitID=oeye`, `Dur=600`,
and `HeroDur=600`. These data values do not establish Serpent Ward behavior.

The probe used Retail 1.29.2 (executable SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`) and the
TFT campaign map `War3xLocal.mpq:Maps/FrozenThrone/Campaign/OrcX01.w3x`. It
created a Player 0 Witch Doctor (`odoc`), issued a point order with
`IssuePointOrder(caster, "evileye", x + 300.0, y + 200.0)`, then enumerated
`bj_mapInitialPlayableArea` three seconds later. Retail returned:

    SENTRYWARD found=1 owner=0 unitType=1868921189 x=-780.000 y=-5884.000 BTLF=0 Beye=1 Adt1=1

The type value is `oeye`; the summoned unit belonged to Player 0 and had
`Beye` and `Adt1` at level 1. The requested point was `(-676, -5992)`; the
observed position was `(-780, -5884)`. The cause of that offset is unknown.
`GetUnitAbilityLevel(ward, 'BTLF')` returned 0 and does not prove whether
timed life was applied. Although the data duration is 600 seconds, expiry and
actual removal were not observed.

The map's cinematic-disable trigger temporarily hides `AIba`, `AIcd`, `AIad`,
`AIae`, `AIgx`, and `Ashm`, then cleanup re-enables them. The map JASS does not
mention `Aeye`/`AIsw` or call `UnitRemoveAbility`; the injected cast ran after
intro cleanup and gameplay start. The map's placed-unit and custom ability
files contained no `oeye`/`Aeye`, excluding a preplaced ward or map override
as the observed source.

The initial Reign of Chaos Prologue probe's `found=0` is invalid evidence for
this TFT ability. A separate exploratory run also used `ward` for `Aeye` and
was rejected; inspect the stock `Units/OrcAbilityFunc.txt` order before
issuing the JASS order. In the successful exploratory run, the manifest's
`result_file` did not match the filename passed to `PreloadGenEnd`, so the
tool's capture command was not used; the fresh raw Preload file was read
directly. Reproduce with matching filenames using
[`retail-camera-tracing.md`](docs/games/warcraft-3/retail-camera-tracing.md).
The retained ability contract and observation are in
[`sentry-ward.md`](docs/games/warcraft-3/sentry-ward.md#retail-jass-observation-tft).

This observation covers creation, owner, type, and a sampled position only.
It does not complete the separate Serpent Ward scenario in the table below.

## Completed JASS case: Serpent Ward rank 1 summon and expiry

Retail TFT `AOsw` was checked on the same OrcX01 map and Warcraft III 1.29.2
executable above. The probe inspected the map script for ability availability
gates, learned `AOsw` on a level 2 Shadow Hunter with `SelectHeroSkill`, and
issued the stock `ward` point order. At 3 seconds it found one owned `osp1`
near the cast point. A second probe sampled after 3 seconds and again at 45
seconds:

    SERPENTWARDEXPIRY probe=serpentward-tft-expiry-v1 accepted=true AOswLevel=1 initialSeconds=3 initialWardCount=1 finalSeconds=45 finalWardCount=0

This establishes rank 1 creation and that the ward was gone by 45 seconds,
after the authored `Dur`/`HeroDur=40`. It does not establish the exact expiry
second, higher-rank unit types/durations, combat behavior, or the reason for
the observed placement offset. The full observation and replay pitfalls are
in [`sentry-ward.md`](docs/games/warcraft-3/sentry-ward.md#serpent-ward-expiry-observation-tft).

## Completed JASS case: Mana Flare end conditions

Retail TFT `Amfl` was tested on OrcX01 after its intro cleanup. The map script
does not suppress `Amfl`/`Bmfl`; the only availability toggles name six
unrelated campaign abilities. Two Player 0 Faerie Dragons (`efdr`) received
stock `Amfl` and the stock `manaflareon` order. JASS found `Bmfl` on both at
3 seconds, issued `manaflareoff` to one, and found that buff absent on the
canceled unit at 5 seconds. The uninterrupted unit had no `Bmfl` at 35 seconds:

    MANAFLAREEND probe=manaflare-tft-endconditions-v2 naturalAccepted=true cancelAccepted=true stopAccepted=true naturalBuff3=1 naturalBuff35=0 cancelBuff3=1 cancelBuff5=0 cancelBuff35=0

The field named `stopAccepted` is the probe's acceptance boolean for
`manaflareoff`; the generic `stop` order was not tested. Natural removal by
35 seconds is consistent with stock `Dur=30`, but sampling did not isolate
the exact expiry second. Movement interruption and spell-triggered flare
damage remain unverified. Full details are in
[`mana-flare.md`](docs/games/warcraft-3/mana-flare.md#retail-lifecycle-observation-tft).

## Completed JASS case: Mana Shield depletion

Retail TFT rank 1 `ANms` was tested on OrcX01. JASS created three Player 0
Naga Sea Witches, learned rank 1 on each, and activated `manashieldon` on two.
The inactive unit was a damage control. After activation, the probe set mana
to 20 on one shielded unit, 1 on the other, and 1 on the inactive unit, then
applied an equal `UnitDamageTarget` hit to each. The short capture was:

    MS probe=manashield-tft-depletion-v2 L=111 ON=11 HIT=111 full(M=10.000,L=0.000,B=1) low(M=0.000,L=7.589,B=0) off(M=1.000,L=8.432,B=0)

`L=111`, `ON=11`, and `HIT=111` report all skills learned, both shield
activation orders accepted, and all damage calls accepted. In each tuple,
`M` is remaining mana, `L` is life lost, and `B` is the `BNms` level. With
ample mana the shield spent 10 mana without life loss; with 1 mana it spent
the last mana, reduced life loss relative to the inactive control, and was
removed. This verifies rank 1 absorption and depletion removal, not exact
fractional damage math, ranks 2–3, or the `ACmf` alias. See
[`mana-shield.md`](docs/games/warcraft-3/mana-shield.md#retail-depletion-observation-tft).

Reproduction pitfalls were material: first verify that a fresh map extracted
from the correct archive loads; update a copy by replacing the exact
`war3map.j` member in place with `smpq -a -f`; and place helper functions
before the exact cinematic-skip callback used by the scenario. A differently
named staged script may add a second member.

**Do not change the Retail launch route to Custom Game or another menu path
when reproducing a campaign-map probe.** Follow the complete replay procedure
in `ability-verification-review.md`: launch with `-loadfile` using
`winepath -w` on the prepared map, together with `-window -graphicsapi
OpenGL2`; focus and click the chapter card near `(642, 600)`, wait for the
cinematic, then press Escape. Passing a Unix path directly or omitting the
documented flags can leave Retail loading its stock campaign map. A run without
a fresh result file is not evidence and should not trigger an alternate launch
method by guesswork. If Retail does not reach the expected screen or the probe
does not produce fresh output, stop and review these verification docs and the
referenced complete replay procedure before retrying. Check the executable,
archive, map, prepared-map path, launch arguments, window focus, click sequence,
trigger name, insertion anchor, and result filename against the recorded
successful run. Do not improvise a different launch mode or trigger until that
review identifies a concrete reason to change it.

Use the exact callback for the selected map; similar trigger names are not
interchangeable. The Prologue procedure uses
`Trig_Intro_Cinematic_Skip_Actions`; the OrcX01 TFT probe uses
`Trig_Intro_Skipped_Actions` and inserts its call after that function's
`ConditionalTriggerExecute( gg_trg_Gameplay )` line. Verify the selected map's
callback and anchor in its extracted `war3map.j` before preparing the probe.

The complete JASS body, insertion locations, extraction/repack checks, launch
command, result path, and failure diagnosis are recorded in
[`ability-verification-review.md`](docs/games/warcraft-3/ability-verification-review.md#retail-charm-target-verification-october-4-2026).

## Scenarios for unresolved questions

| Ability / question | JASS scenario and observations | Binary-analysis trigger |
|---|---|---|
| Charm (`ANch`): target acceptance and creep-level boundary | **Verified:** stock level-3 `nftt` transferred; Hero, corpse and Resistant Skin target were rejected. Follow-up probe: stock-row level-5 override and organic levels 4–5 transferred, level 6 remained Player 12. Custom level-3 copy anomalously remained Player 12, unexplained. Alias coverage and resource accounting remain open. | Not needed for these outcomes; consider analysis only if controlled alias tests leave a hidden eligibility rule ambiguous. |
| Purge (`Apg2`): friendly/hostile movement effect | **Verified:** both casts spent mana; allied target moved about as far as its control at 1.5 s (382.881 vs 403.491); hostile target was strongly movement-suppressed (80.865 vs 385.253 at 1.5 s; 108.837 vs 608.150 at 3.5 s), then moved by 6.5 s. Exact recovery curve, allied dispel, and `Aprg`/item/creep alias behavior remain open. | Not needed for this observable distinction; binary work only if exact internal timing is required. |
| Carrion Swarm: wave geometry and cap | Cast along a known axis with isolated targets at several distances and lateral offsets. Log target life at short intervals. Add enough legal targets to exceed the suspected cap; verify each target is hit at most once and whether later damage is capped. Repeat with a ward/forbidden target and with each concrete alias. | Only if observations cannot distinguish collision/front rules or the cap's internal accounting, or exact sub-frame wave scheduling is required. |
| Cluster Rockets: `ANcs` field meanings, cap and building rule | Cast on separate ground, air and building groups. Log life, movement/lock response, and timing. For ambiguous fields, copy the ability row and vary one candidate Area/Data/duration/cap field at a time, keeping the caster/scene fixed. Include a stock-row control and each alias. | If custom-row perturbation still cannot isolate field semantics, or the claim needs the exact internal bombardment scheduler/class path rather than its effects. |
| Immolation: drain cadence/buffer | Start with mana just above, at, and below candidate payment thresholds. Toggle on; log caster mana and nearby ground/air targets' life over time. Test toggle-off, death, and ability removal. | If the stop threshold or payment ordering is not distinguishable at JASS timer resolution. |
| Phoenix Fire: burn refresh/stack and target selection | Use one legal enemy first; attack at controlled intervals and log life over time to separate instant damage from burn. Repeat with attacks faster/slower than burn expiry. Then use two symmetric legal enemies and record which one is hit on each cooldown; repeat the setup. Check that attack/movement orders are not replaced. | If target tie resolution is not reproducible from observable outcomes or a question asks for the hidden selection algorithm. |
| Shadow Strike: slow lifetime separate from poison | Cast once on a unit with known movement speed. Log movement speed and life at short intervals; establish when movement returns and when poison damage ends. Repeat with Hero and ordinary targets and each alias. | If exact expiry ordering within one simulation frame is material or the observable status cannot be attributed to this spell. |
| Mirror Image: copied Hero state | Cast on a Hero with known level, XP, attributes, ability ranks and inventory. Identify created images; query exposed Hero stats/XP/ability levels/inventory and observe life/mana. Repeat with one source value changed. Check image damage taken/dealt and illusion-sensitive dispel behavior separately. | For hidden constructor-copied fields with no JASS getter, or to explain an unobservable internal copy path. Scope the question to a named field before analysis. |
| Serpent Ward (`AOsw`) / form-specific exceptions | **Ranks 1–2 verified:** learned stock TFT ranks create owned `osp1`/`osp2` at a known-good point. Paired order-reversal probes show rank 2's earlier rejection followed the alternate target location: either rank fails there, while either rank succeeds at the known-good point. Frida: shared spell validation agrees; the Ward position fallback is `0` at the good point and `1` at the rejected point, mapping to Ward result `0`/`0x41`. The specific map property rejecting the alternate point remains unidentified. Follow up on rank 3, rank 2/3 expiry, exact expiry boundary, movement, attacks against ground/air, and spell-immunity response. Keep separate from Sentry Ward (`Aeye`/`AIsw`, `evileye`, `oeye`). For Crow Form, inspect available abilities and cast Faerie Fire with/without Mark of the Talon. | Only for internal classification not exposed through JASS and with no distinct gameplay test. Use AbilityData/UnitData for authored values. |
| Mana Flare (`Amfl`) end conditions | **Verified:** `Bmfl` is present at 3 seconds, absent at 5 seconds after `manaflareoff`, and absent at 35 seconds without interruption; stock `Dur=30`. Exact expiry boundary, generic Stop, move interruption and spell-triggered damage remain open. | Not needed for these sampled end states; exact hidden callback ordering below JASS timer resolution would require binary analysis. |
| Mana Shield (`ANms`) rank 1 depletion | **Verified:** with ample mana a hit spends mana without life loss; with 1 mana the shield spends it, reduces life loss versus an inactive control, and `BNms` is removed. Fractional exact damage and ranks 2–3/`ACmf` remain open. | Not needed for the depletion/removal result. Binary work only if the exact internal damage ordering is required. |

## What JASS does not prove by itself

- Internal data-field names and code paths where two candidate fields produce
  indistinguishable stock behavior. First try one-field-at-a-time map data
  variants; static analysis is the fallback.
- Private tie-breaking or scheduler algorithms when repeated external results
  do not uniquely reveal them.
- Hidden copied state with no JASS getter.
- Exact callback/instruction timing below the retail sampling/frame
  resolution.

For those residual questions, use the version-matched executable. The repo has
`r2`-based examples in `docs/games/warcraft-3/ability-inheritance-binary.md`
and retail trace precedents in `docs/games/warcraft-3/audio-retail-analysis.md`;
their addresses/tool configuration are subsystem- and build-specific. Record
the binary hash and do not transfer an address or conclusion across versions.

## Evidence record per scenario

Retain: question/hypothesis; executable hash/version; map and ability rawcodes;
ROC/TFT/object-data variant; starting unit/owner/stats/positions; exact JASS
orders and timer interval; raw timestamped observations; repeats; control
result; conclusion and remaining resolution limit. Promote only the confirmed
external contract into an OpenRealm regression test and the ability contract
doc.
