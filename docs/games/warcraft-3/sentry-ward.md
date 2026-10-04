# Sentry Ward

## Contract

`Aeye` is ROC/TFT `CAbilityEvilEye` (parent `AAsm`). `AIsw` is an item alias whose
`code` is `Aeye`, so it shares the procedure and reads its own row through
`abilityitem_t.code`. `APwt` (Rune of the Watcher) is the same `code=` but remains
unregistered here.

| Rawcode | Archive | Notes |
| --- | --- | --- |
| `Aeye` | ROC and TFT | Witch Doctor Sentry Ward |
| `AIsw` | ROC and TFT | item Sentry Ward (`code=Aeye`) |
| `APwt` | TFT | Rune of the Watcher — unregistered |

Point cast summons an invisible timed detection ward. True sight comes from the
ward unit's `Adt1` (`CAbilityDetector`, `code=Adet`) detect range (`Rng`), not
from `Aeye` Data cells (`Aeye` has no DataA–I).

## Authoritative Fields

| Field | Meta | Stock Aeye TFT | Stock AIsw TFT | Runtime meaning |
| --- | --- | ---: | ---: | --- |
| `UnitID` | Ward Unit Type (`hwdu`, shared with Ahwd) | `oeye` | `oeye` | ward unit (`S_SpellUnitId`) |
| `Dur` / `HeroDur` | | `600` | `300` | ward timed life (`BTLF`) |
| `BuffID` | | `Beye` | `Beye` | summoned-ward presentation; not required for detect |
| `Cost` | | `50` | `0` | |

ROC omits `UnitID` / `BuffID` on both rows.

`oeye` UnitAbilities: `Adt1,Aeth`. Stock `Adt1` TFT: `Rng=1100`, `DataA=3`
(detectionType). OpenWarcraft exposes a player-aware `S_UnitIsDetectedByPlayer` query. A Sentry Ward contributes its stored `Adt1` range only to its owner and viewers receiving that owner's shared vision; the legacy `S_UnitIsDetected` helper remains as an aggregate compatibility query.

## Data Flow

```text
AbilityData.slk (Aeye / AIsw)
  -> UnitID, Dur
CAbilityEvilEye
  -> S_SummonAt(caster, UnitID, point, Dur)
  -> ward.summon_ability = cast rawcode; RF_HIDDEN
  -> ward.wait = Adt1 Rng (detect radius)
S_UnitIsDetectedByPlayer(unit, viewer)
  -> viewer owns/shares vision with detector
  -> target is enemy to detector and inside authored detection radius
  -> viewer-specific visibility/selection/targeting may reveal known gameplay invisibility
  -> outgoing snapshot clears RF_HIDDEN locally without changing authoritative entity state
```

FOW reveal while the ward itself is `RF_HIDDEN` is still a separate gap (invisible wards should still grant owner vision). Detection itself is no longer a global hidden-state toggle: Far Sight and passive detector abilities share the viewer-specific path, and non-invisibility `RF_HIDDEN` states remain hidden.

## Diagnostic Workflow

```sh
build/bin/ability_audit -data 'data/Warcraft III' -raw Aeye
build/bin/ability_audit -data 'data/Warcraft III' -raw AIsw
build/bin/ability_audit -data 'data/Warcraft III' -raw Adt1
```

## Verification

```sh
make test-wc3-engine WC3_PATTERN='wc3_spell.sentry_ward*'
```

### Retail JASS observation (TFT)

The stock TFT spell was probed in Retail 1.29.2 using
`War3xLocal.mpq:Maps/FrozenThrone/Campaign/OrcX01.w3x`. A Player 0 Witch
Doctor (`odoc`) with its stock `Aeye` ability was issued the point order
`evileye`; three seconds later JASS enumerated the playable map for `oeye`
units. The Retail executable SHA-256 was
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`. The
fresh `PreloadGen` result was:

```text
SENTRYWARD found=1 owner=0 unitType=1868921189 x=-780.000 y=-5884.000 BTLF=0 Beye=1 Adt1=1
```

`unitType=1868921189` is rawcode `oeye`. This confirms a stock Retail cast
created an `oeye` owned by the caster's player, and that the ward had its
`Beye` and `Adt1` abilities about three seconds after the order. The requested
point was `(-676, -5992)`; Retail reported `(-780, -5884)`. The reason for
that placement offset has not been established. `GetUnitAbilityLevel` returned
zero for `BTLF`, so that query does not establish timed-life presence or
remaining duration. The stock `Dur=600` field is data evidence; actual expiry
and removal have not been observed in Retail.

The probe caster was created at player 0's start location plus `(1800, 700)`;
the requested cast point was another `(300, 200)` from there. The JASS probe
issued `IssuePointOrder(caster, "evileye", x + 300.0, y + 200.0)`, then used
`GroupEnumUnitsInRect` over `bj_mapInitialPlayableArea` and recorded each
`oeye`'s owner, type, position, and queried `BTLF`, `Beye`, and `Adt1` levels.
The source map's `war3mapUnits.doo`, `war3map.w3u`, and `war3map.w3a` had no
`oeye` or `Aeye` rawcode entries, so the detected ward was runtime-created.

The TFT map's `war3map.j` was inspected before using it. Its cinematic
disable trigger temporarily hides `AIba`, `AIcd`, `AIad`, `AIae`, `AIgx`, and
`Ashm` from the campaign player, and its cleanup trigger re-enables those same
six abilities. It does not name `Aeye`/`AIsw`, call `UnitRemoveAbility`, or
change Sentry Ward availability. The map's `war3map.w3a` contains no `Aeye`
override. The probe hook runs after the intro cleanup and gameplay start.

An earlier attempt used the Reign of Chaos Prologue map from
`War3Local.mpq`; its `found=0` result is not evidence about Sentry Ward because
that map is not a TFT reference. Another failed attempt used order `ward`,
which belongs to Serpent Ward. The TFT stock `Units/OrcAbilityFunc.txt` rows
specify `Aeye Order=evileye` and `AOsw Order=ward`.

### Serpent Ward order verification (TFT)

The related stock Serpent Ward (`AOsw`) was separately checked on the same
TFT OrcX01 campaign map and Retail executable. The TFT audit identifies
`AOsw` as `CAbilityWard`, a three-rank Shadow Hunter Hero skill with order
`ward`, cost 30, range 500, cooldown 6.5, and 40-second `Dur`/`HeroDur` at all
ranks. Its authored summon IDs are `osp1`, `osp2`, and `osp3` for ranks 1–3.
`Units/UnitAbilities.slk` lists `AOsw` in the Shadow Hunter (`Oshd`)
`heroAbilList`; the probe therefore raised a fresh Shadow Hunter to level 2
and learned rank 1 with `SelectHeroSkill` before issuing the point order. It
used the documented OrcX01 chapter-card click and cinematic-skip sequence, and
cast at the point used by the accepted Sentry Ward probe.

After three seconds, a JASS probe searched within 700 units of the cast point.
The reviewed capture was:

```text
SERPENTWARD probe=serpentward-tft-learned-v2 addedViaSkill=true accepted=true casterType=1332963428 owner=0 heroLevel=2 skillPointsBefore=1 skillPointsAfter=1 AOswLevel=1 wardCount=1 wardType=1869836337 wardOwner=0 wardX=-780.000 wardY=-5884.000
```

The numeric IDs are `Oshd` and `osp1`, respectively. This verifies that the
learned stock TFT `AOsw` accepted the `ward` order and created an `osp1` ward
owned by Player 0 at the recorded position. The fresh capture passed its
marker gate and was reviewed manually; `ready_for_review` by itself is not a
gameplay verdict.

An earlier probe added `AOsw` with `UnitAddAbility` and set its rank directly;
Retail returned `accepted=false` at a different point. The successful replay
both learned the Hero skill through `SelectHeroSkill` and changed the cast
location, so the specific reason for that earlier rejection remains unknown.
This rank 1 observation by itself does not verify higher-rank behavior, ward
attacks, or the authored 40-second expiry. Rank 2 creation is verified by the
paired differential below; rank 3 remains open. The probe files remain temporary under
`/tmp/wc3-retail-serpentward-recheck/`.

### Serpent Ward rank 2 validation differential (TFT)

Retail rank 2 was compared with rank 1 in paired probes on the same TFT OrcX01
map and executable (`Warcraft III.exe` SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`). Both
heroes learned stock `AOsw` through `SelectHeroSkill`; the probe used the same
`ward` order and two nearby target points. At point A (the previously
successful rank 1 point), rank 1 first produced owned `osp1`, while rank 2
then failed at point B. Reversing cast order and assigning rank 2 to point A
made rank 2 succeed and create owned `osp2`; rank 1 then failed at point B:
the points were `(startX + 2100, startY + 900)` and
`(startX + 2600, startY + 900)`, respectively.

```text
SERPENTWARD_COMPARE probe=serpentward-tft-ranks-v2 rank1Level=1 rank1Accepted=true rank1WardCount=1 rank1WardType=1869836337 rank2Level=2 rank2SkillPoints=2 rank2Accepted=false rank2WardCount=0 rank2WardType=0
SERPENTWARD_COMPARE probe=serpentward-tft-ranks-v3 rank1Level=1 rank1Accepted=false rank1WardCount=0 rank1WardType=0 rank2Level=2 rank2SkillPoints=2 rank2Accepted=true rank2WardCount=1 rank2WardType=1869836338
```

The outcome follows the target point rather than the ability rank or cast
order: point A accepts either rank, while point B rejects either rank. This
resolves the earlier rank 2 rejection as a location-specific validation
failure, not a rank 2 summon/identity failure. The specific map property that
makes point B invalid has not been isolated, so do not label it blocked terrain
or unit collision without another differential.

A bounded Frida trace on the same executable observed the native reason code
change with the point. For the successful point, SimpleSpell validation
returned `0`, Ward's position fallback returned `0`, and `CAbilityWard`
returned `0`. For the rejected point, SimpleSpell still returned `0`, the
fallback returned `1`, and Ward returned `0x41`. The availability and owner
checks also had the same observed results for both requests. Disassembly shows
that this fallback result is what changes Ward's validation result; its exact
map-level predicate remains unknown. The rank 2 JASS sample confirms the
accepted summon was `osp2`, but does not test rank 2 expiry, attacks, or other
ward behavior. Probe maps, captures, and traces are under
`/tmp/wc3-serpentward-rank-compare-v2/run2/` and
`/tmp/wc3-serpentward-rank-compare-v3/run/`.

### Serpent Ward expiry observation (TFT)

The rank 1 expiry was checked in Retail 1.29.2 on the same OrcX01 TFT campaign
map and executable. The probe learned stock `AOsw` on a level 2 Shadow Hunter,
issued the `ward` point order, counted `osp1`/`osp2`/`osp3` units within 700
units of the cast point after 3 game seconds, and counted again after another
42 seconds. Retail wrote:

```text
SERPENTWARDEXPIRY probe=serpentward-tft-expiry-v1 accepted=true AOswLevel=1 initialSeconds=3 initialWardCount=1 finalSeconds=45 finalWardCount=0
```

This confirms that the accepted cast had one ward at the early sample and no
matching ward at 45 game seconds, after the authored 40-second rank 1
`Dur`/`HeroDur`. It supports the authored expiry behavior but does not identify
the exact removal time between the 3- and 45-second samples. This observation
does not cover rank 2 or 3 expiry, nor ward death/removal through combat or
other means. The probe map, staged JASS, launch records, and raw capture are
under `/tmp/wc3-retail-serpentward-expiry/run/`; the separate probe manifest
and source fragments are under `/tmp/wc3-retail-serpentward-expiry/`.

In the successful exploratory run, the manifest expected a differently named
result file than the name passed to `PreloadGenEnd`, so the probe tool's
`capture` command could not consume it. The raw `PreloadGen` file was inspected
directly; a reproducible run should use the same filename in both places.

The observation covers creation, owner, raw unit type, and sampled position.
It does not prove the 600-second expiry or explain the placement offset. The
probe source and unmodified output are temporary files under
`/tmp/wc3-retail-sentryward/` and the Wine `CustomMapData` directory; recreate
them using the map preparation workflow in
[retail-camera-tracing.md](retail-camera-tracing.md). Keep the manifest's
`result_file` identical to the filename passed to `PreloadGenEnd` so the
capture tool can enforce freshness.
