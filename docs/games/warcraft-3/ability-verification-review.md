# Ability verification and lifecycle fixes

## Scope and evidence

The September 2026 review at `41602e54` inspected all 39 Warcraft III
`game/skills/*.c` files. Three agents covered combat spells, orders/economy,
and passives/items/campaign handlers; the coordinator covered shared dispatch.
The original baseline passed 1,132 WC3 tests in each archive mode, but sixteen
new behavior scenarios failed and enabling Human autocast crashed. Registry
presence and status-record creation had overstated working functionality.

The fixes retain these reproductions as permanent tests, extend their inverse
and lifecycle coverage, and correct additional failures exposed by that work.
The four new suites contain 37 tests / 302 assertions, passing in both ROC and
TFT modes. Five save-schema tests additionally cover the new channel fields.
This verifies the named contracts, not exhaustive retail parity or rendered art.

## Fixed contracts

| Area | Previous failure | Owning fix and regression evidence |
|---|---|---|
| Human autocast | A boolean message was dereferenced as a target pointer; aliases used base data | Human, validated-spell, Avatar and bolt procedures decode only the current message's union member. The command/HUD/scheduler retain the actual rawcode. Alias cost/heal, runtime membership, switching, removal and unsupported-policy rollback are tested. |
| Repair autocast | Switching related procedures could clear their shared policy flag | Disable the old policy before enabling its replacement; disabling a nonselected alias has no effect. Rejected enable restores the previous policy. |
| Hold Position | Out-of-range acquisition walked toward enemies | Attack returns to stationary scanning; an in-range enemy can still be attacked. |
| Delayed damage | An old projectile kill replaced a newer Move or consumed its queue | Combat completion requires the current Attack procedure and matching target. Animationless post-hit fallback also requires unchanged move and target. |
| Explicit Attack/Smart | Replaced Follow/Patrol/Attack-move resumed after combat | `S_OrderAttack` clears retained movement only after accepting an explicit order. Autonomous acquisition keeps continuation; queued orders replace it only when executed. |
| Repair completion | `building->stand` erased the producer queue | Repair owns the worker's completion only; the target keeps its production behavior and queue. Tests advance the retained trainee. |
| Flame Strike | Damage was treated as a long cast delay; pulses ran every frame | Read Cast/HeroDur/Dur and Hfs1–Hfs6 correctly; preserve absolute fractional pulse deadlines, phases, building multiplier and aggregate cap. |
| Blizzard | Zero Dur truncated six authored waves to two | Wave count and authored interval determine completion, independently of the zero-duration sentinel. |
| Life Drain / Siphon Mana | Life Drain affected mana; channels survived cancellation | Separate authored health/mana fields and allied transfer; validate each cast, tether and entity incarnation at every pulse. |
| Channel lifecycle | No-target casts lacked state; old thinkers survived recasts or stopped new orders | Start all channel shapes consistently; capture a cast serial and owner/target incarnation; route move-leave to the active procedure and explicitly cancel on Stop. Stun, movement, recast, expiry, reuse and save continuation are tested. |
| Aerial Shackles | The caster buff was applied to the victim, so movement/attacks remained allowed | Read the target member of the authored buff pair. Remove its lock when that channel ends, preserving a replacement cast's lock. |
| Storm Bolt | Spell immunity blocked damage but not stun; creep level selected Hero duration | Check impact acceptance before applying stun and use actual Hero identity for HeroDur. |
| Frost Nova | A no-target burst damaged around the caster | Register a unit target; apply direct DataB damage and area DataA damage around that target. |
| Resurrection | Only Heroes were eligible | The no-target spell finds ordinary friendly corpses in the authored area/count, reuses their edicts, retires death state and restores unit/food activity. Reject an empty cast before committing resources. |
| Attribute items | Strength, Agility and Intelligence were rotated | Both permanent tomes and passive attribute aliases use DataA=Agility, DataB=Intelligence, DataC=Strength. |
| Passive items | Exact base-code comparisons discarded stock alias bonuses | `A_ITEM_ADD` / `A_ITEM_REMOVE` carry `abilityitem_t` to the owning passive procedure. Read each alias's amount on pickup/drop; no per-family global amount cache. Stacked items survive save/load and independent removal. |
| Natural creep sleep | Wake removed unrelated owned overlays | Tag sleep art with ACsp and require that identity during cleanup. Wake, move and disable preserve regeneration art. |

## Data and timing

Use the archive audit instead of inferring fields from tooltip prose:

```sh
build/bin/ability_audit -data 'data/Warcraft III' -roc -raw AIsm
build/bin/ability_audit -data 'data/Warcraft III' -tft -raw AHfs
python3 tools/wc3_ability_class_audit.py --format=coverage
```

The active TFT Flame Strike row uses Hfs1/DataA for full pulse damage,
Hfs2/DataB for its interval, Hfs3/DataC for lesser pulse damage, Hfs4/DataD
for its interval, Hfs5/DataE for the building multiplier, and Hfs6/DataF
for the aggregate damage cap. Cast is the initial delay; HeroDur supplies
the full-damage phase and Dur the damage lifetime. Deadlines advance from
the previous scheduled pulse, so a 0.33-second interval does not become
0.4 seconds on every 100 ms server tick. Positive sub-frame intervals are
caught up at the next simulation step; invalid intervals are rejected/logged.

Both ROC and TFT archive audits confirm AItg → AIat (attack bonus 1),
AId1 → AIde (armor 1), and the three tome attribute columns. Combat fixtures
include an explicit ROC numbered Data11/Data12 conversion test for Blizzard.
Running TFT numeric fixtures in ROC mode verifies runtime compatibility;
it does not independently verify every ROC authored value or TFT-only spell.

## Dispatch and persistence

`abilityCall_t` is a message-tagged union. `A_COMMAND` supplies a client,
`A_INIT` a classname, `A_AUTOCAST_SET` a boolean, and only target-bearing
messages supply a `spellTarget_t`. Never eagerly read the target union member
before deciding which message is being handled.

`edict.channel.code` is nonzero on the caster only. Each channel thinker
retains its spell rawcode in `class_id`, the cast `channel.serial`, and
`owner_spawn_time` / `target_spawn_time` where applicable. Reused owner/target
slots and replacement casts cannot inherit an old effect. `S_SpellEndChannel`
clears only a matching cast, then releases its thinker; cancellation does not
install Stand over an already accepted replacement order.

Save format **21** adds this channel identity state to the edict schema.
Older save versions are rejected. The new channel callbacks are appended to
`save_cfunctions[]`; never reorder existing callback indexes. The saved
channel origin is preserved for movement cancellation after loading. A live
drain and stacked passive item aliases have production WriteGame/ReadGame
continuation tests, in addition to the individual schema tests.

## Tests

```sh
make test-wc3-engine WC3_PATTERN='wc3_ability_*'
make test-wc3-engine WC3_PATTERN='wc3_order_lifecycle.*'
make test-wc3-engine WC3_PATTERN='wc3_item_lifecycle.*'
make test-wc3-engine WC3_PATTERN='wc3_save.*'
make test
make build
```

Permanent regression sources are `game/tests/t_ability_dispatch.c`,
`t_ability_lifecycle.c`, `t_order_lifecycle.c`, and `t_item_lifecycle.c`.
Existing combat, building, spell and save tests also check affected paths.
Final verification on 2026-09-13: `make test` passes 3,228 test invocations /
65,585 assertions across 20 suite invocations, including 1,174 WC3 tests /
25,316 assertions per archive mode. `make build` passes. Both builds emit no
compiler warnings; registry coverage remains 193 registered TFT class IDs.
Use full local socket access for the aggregate suite's UDP tests; sandbox
bind denial is not a gameplay failure. No interactive game launch was needed.

## Limits and history

The fixes address reproduced defects and their related lifecycle cases.
Previously documented partial implementations remain partial: Wisp/Acolyte
harvesting, mine transformations, general transport drop, Purchase Item,
Mirror Image's complete illusion semantics, several status-only spells,
and Siphon Mana's temporary above-maximum mana/decay behavior. Visual effects,
full target-mask vocabulary and comprehensive retail spell parity remain
separate work. Do not interpret a registered procedure as complete behavior.

Blame traced the unsafe Human union reads to `e12b63ad0`, Flame/Drain field
and timer errors to `22ff3692`, item alias/attribute errors to `85fd0906`,
attack continuation to `317fc09ae`, Repair completion to `6d5025e92`, and sleep
overlay cleanup to `ebbe30e2`. These histories explain why the new regressions
exercise caller/event order, authored aliases and inverse behavior rather
than only testing procedure lookup.

See [ability coverage](architecture/ability-coverage.md),
[ability implementation](ability-implementation.md),
[save/load](save-load.md), and [autocast](autocast.md).

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
procedure documented in [Retail Warcraft III camera tracing](retail-camera-tracing.md).
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
The replays used temporary maps and scripts under `/tmp/wc3-retail-tft-rechecks`
and did not modify repository or retail archives.

## Jaina / Archmage follow-up (September 19, 2026)

The Archmage review tightened three abilities without adding Hero-specific
branches. `AHwe` now treats DataA as the authored summon count, records the
creating ability on each summon, and emits TargetArt while retaining the shared
timed-life/event path. `AHbz` now evaluates its own authored target mask, applies
DataD to structures after the DataF per-wave cap, and emits DataC EffectArt
shards without using the visual positions for hit detection.

`AHmt` now participates in the shared channel lifecycle instead of relocating
immediately. DataB owns the completion delay; a thinker retains the destination
entity incarnation, temporarily pauses that destination, owns persistent area
effects, and cleans all of those resources on success or cancellation. Completion
uses the current destination position, keeps the caster inside the DataA total,
excludes allied-player armies and structures from the payload, honors DataC
clustering, and uses ordinary unstuck placement. The thinker callback is appended
to the save callback roster, and regression coverage includes delayed completion,
unit-cap/ownership filtering, structure destinations, destination death,
cancellation cleanup, Water Elemental DataA ownership, Blizzard structure
scaling, and production save/load continuation.

Brilliance Aura remains on the existing cached Hero-aura path. This follow-up
does not replace that path with the newer generic target-token helper because the
current unit `targtype` representation conflates movement class and
organic/mechanical classification; doing so here could regress stock mechanical
recipients. That broader target-model cleanup remains separate work.

### Jaina / Archmage remaining-fidelity follow-up (September 19, 2026)

A second conservative pass closes behavior that the bundled Warsmash source
makes explicit without broadening the shared damage/type model. Blizzard now
waits for its authored `Cast` interval before the first shard wave, then splits
each wave into shard presentation followed by damage 0.8 seconds later. The
phase is stored on the already-serialized thinker state, so saving between the
shards and impact resumes the pending damage phase rather than replaying art.
The existing target mask, DataD building multiplier and DataF aggregate cap
remain authoritative. Cold/spell damage typing and spell-sound parity are still
separate shared-system work.

Brilliance Aura now consumes the stock `air,ground,friend,self` target mask in
the cached Hero-aura path rather than treating every friendly entity in range as
a recipient. Rows that omit `targs` keep the historical friendly fallback for
sparse ROC/custom fixtures. This deliberately does not rewrite the engine-wide
organic/mechanical classification model; that broader cleanup is still separate.

Water Elemental keeps its existing DataA/UnitID/timed-life path but now preserves
the caster facing and relinks collision-displaced summons. Mass Teleport likewise
relinks every relocated unit (and dirties FOW blocker state where relevant), so
the server broad phase no longer retains the source position after the visual and
simulation coordinates have moved. Regression coverage documents Blizzard's
0.8-second phase timing and save/load continuation, Brilliance target filtering,
Water Elemental separation/facing, and Mass Teleport vacated-space relinking.

### Jaina / Archmage data-driven aura and targeting follow-up (September 19, 2026)

A third conservative pass closes two data-driven gaps that are explicit in the
bundled Warsmash implementation. Brilliance Aura now treats DataB as its
flat-versus-percentage switch: flat DataA remains MP/sec, while percentage DataA
scales the recipient's intrinsic mana regeneration (base unit regeneration,
ordinary mana-regeneration bonuses, and the current Intelligence regeneration
term). Flat and percentage Brilliance providers keep separate strongest-copy
slots, matching the separate non-stacking stat families used by Warsmash. The
Hero-aura cache also resolves the actual authored alias and rank before reading
Area, `targs`, DataA, and DataB, so custom Brilliance-derived abilities no longer
silently fall back to the stock `AHab` row.

The shared unit-target validator now reads `targs` from the caster's current
ability rank instead of always using level 1. This matters to Blizzard and Mass
Teleport when custom object data changes target classes across ranks, and it
preserves the requested alias as the data source. Focused regressions cover
rank-specific target masks and a custom percentage-mode Brilliance alias mixed
with a stock flat provider.

This pass still does not invent cold/spell damage typing, per-shard sound
semantics, or an engine-wide organic/mechanical target-class rewrite. Those
remain shared-system fidelity work because the current OpenRealm representations
do not model them cleanly enough for a low-risk Jaina-specific change.

### Jaina / Archmage summon identity and Blizzard effect-object follow-up (September 19, 2026)

A fourth conservative pass closes two presentation/lifecycle details that the
bundled Warsmash implementation makes explicit without extending OpenRealm's
shared damage model. Summon Water Elemental now also applies the ability's
authored BuffID to each created Elemental. OpenRealm deliberately keeps `BTLF`
as the authoritative timed-life clock because the existing timed-life bar and
`UnitPauseTimedLife` native are built around that status; the authored Water
Elemental buff supplies the WC3 ability-specific status/presentation identity
without introducing a second expiration timer. `BTLF` is now treated as
non-dispellable lifecycle state by the shared Dispel/Purge filter, so dispel
still deals its authored damage to summoned units but cannot accidentally turn
a surviving timed summon into a permanent unit.

Blizzard now resolves each shard's EffectArt through the level's authored
`EfctID` object, matching Warsmash's `effectId` path, instead of resolving the
visual directly from the casting ability alias. Focused regressions cover the
Water Elemental BuffID plus retained `BTLF`, preservation of timed life after
Dispel Magic, and the Blizzard EfctID art lookup.

That fourth pass intentionally left cold/spell damage typing and per-shard
ability sound alone because both required shared-system support. The following
pass adds the sound-data path; typed SPELLS/COLD damage still remains separate.

### Jaina / Archmage ability-sound follow-up (September 19, 2026)

A fifth conservative pass closes Blizzard's remaining high-confidence sound-data
gap without changing spell damage semantics. The typed metadata registry now loads
`UI\SoundInfo\AbilitySounds.slk` with the same sound-row schema already used for
unit/UI sounds, and ability/buff presentation exposes authored `Effectsound` /
`Effectsoundlooped` fields. `G_PlayAbilityEffectSound` resolves an alias from the
requested object or its base object and emits a positional world sound at the
requested effect point using the authored volume.

Blizzard now uses the level `EfctID` for both shard art and shard sound, matching
the bundled Warsmash implementation's `spawnSpellEffectOnPoint(effectId)` plus
`unitSoundEffectEvent(caster, effectId)` sequence. The sound fires once for each
DataC shard during the presentation phase, never during the delayed damage phase.
Regression coverage injects a synthetic `AbilitySounds.slk` row and verifies six
shard sounds, alias/path resolution, positioned playback, and 0-127 volume scaling.
The test MPQ also carries a minimal AbilitySounds fixture and verifies it is packed.

The server intentionally selects the first authored ability-sound file rather than
calling `rand()`: Warsmash performs variant selection in rendering/audio code, while
using OpenRealm's simulation RNG for presentation would perturb deterministic game
state. Client-side random variant selection plus authored pitch/pitch-variance are
still presentation refinements. SPELLS/COLD Blizzard damage typing, the broader
organic/mechanical target model, and finer Mass Teleport placement/order parity
remain separate shared-system work.

## Capturing Retail screenshots under Wine

Use Warcraft III's own Print Screen handling for Retail evidence. In a Wine
profile it writes a TGA under:

    $WINEPREFIX/drive_c/users/<wine-user>/Documents/Warcraft III/ScreenShots/

The filename is timestamped, for example
`WC3ScrnShot_100426_210616_01.tga`. The exact capitalization of `ScreenShots`
is not significant on the Wine filesystem. Preserve the TGA in the Wine
profile and convert a copy to PNG under the repository's ignored
`screenshots/tmp/` directory. Do not derive Retail evidence PNGs from XWD
captures: the earlier XWD conversion produced striped pixels even though its
PNG metadata reported RGB.

For an automated headless run, follow the map-specific launch procedure in
this document, then send `Print` to the focused Warcraft window with `xdotool`.
This exact input sequence successfully captured the prepared TFT Serpent Ward
rank comparison map on October 4, 2026:

```sh
export WINEPREFIX=/home/agent/.wine-war3
MAP=/tmp/wc3-serpentward-rank-compare-v3/run/OrcX01-SerpentWard-TFT-Ranks-v3.w3x
xvfb-run -a -s '-screen 0 1280x720x24' bash -lc '
  export WINEPREFIX=/home/agent/.wine-war3
  MAP=/tmp/wc3-serpentward-rank-compare-v3/run/OrcX01-SerpentWard-TFT-Ranks-v3.w3x
  wine "data/Warcraft III/Warcraft III.exe" -window -graphicsapi OpenGL2 \
    -loadfile "$(winepath -w "$MAP")" &
  game_pid=$!
  trap "kill $game_pid 2>/dev/null || true" EXIT
  sleep 30
  xdotool mousemove 642 600 click 1
  sleep 20
  xdotool key Escape
  sleep 10
  xdotool key Print
  sleep 5
  find "$WINEPREFIX/drive_c/users/agent/Documents/Warcraft III/ScreenShots" \
    -type f -iname "*.tga" -mmin -2 -printf "%TY-%Tm-%Td %TH:%TM %s %p\\n"
'
```

The click advances the campaign chapter card, Escape skips the cinematic, and
Print asks Warcraft itself to capture the gameplay screen. Keep the key event
focused on the game window. Confirm a newly timestamped TGA appears before
converting it; a command completing without that file is not a successful
capture. If the map does not reach the expected screen or no fresh file is
written, use the existing replay troubleshooting guidance above rather than
changing the launch route by guesswork.

Convert with Pillow, explicitly requesting RGB so an alpha channel in the TGA
does not carry into the PNG:

```sh
mkdir -p screenshots/tmp
/opt/openrealm-tools/frida-venv/bin/python - <<'PY'
from pathlib import Path
from PIL import Image

source = Path("/home/agent/.wine-war3/drive_c/users/agent/Documents/Warcraft III/ScreenShots/WC3ScrnShot_100426_210616_01.tga")
output = Path("screenshots/tmp/war3-retail-printscreen-2026-10-04.png")
with Image.open(source) as image:
    image.convert("RGB").save(output, format="PNG", optimize=True)
with Image.open(output) as image:
    image.verify()
with Image.open(output) as image:
    print(image.format, image.mode, image.size, output)
PY
```

Use the actual TGA filename for each run and choose a descriptive PNG filename.
The verified sample TGA was RGBA at 1024×576; its converted PNG was RGB at the
same dimensions. This is a property of that capture, not a guarantee about all
Retail window sizes. `screenshots/` is ignored by Git, so these local evidence
images are not committed by default.

The sample image showed the in-game JASS comparison output for the test:
rank 2 was accepted and produced unit type `1869836338` (`osp2`). The screenshot
is supplementary visual evidence; the saved JASS result and the written
ability observation remain the behavior record.
