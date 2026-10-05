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

## Prefer exact-build code validation when it settles the question

Start with the evidence source that can answer the named question. Use the
TFT/ROC data audit for authored values, then inspect the exact Retail binary
with radare2 and Ghidra for target gates, field reads, and return branches.
When those paths establish the contract, record the static proof and skip a
Retail run. Use Frida when a dynamic branch, receiver identity, or execution
path is still ambiguous. Use JASS or visible state only when the question is
about an externally observable outcome that the code/data inspection does not
settle. A runtime trace is useful corroboration; it is not required solely to
repeat a conclusion already established by the exact-build implementation.

For each native claim, pin the executable SHA-256, map the rawcode to the
concrete implementation code using the same version's data, and verify any
candidate address in that executable. Use r2 for narrow disassembly and
string/reference discovery; use the cached Ghidra project for callers,
register/stack roles, branch conditions, and decompilation. Do not transfer
addresses from another executable hash. A Frida return value is a native
status code until its callers prove otherwise; do not treat zero or nonzero as
a JASS order-acceptance boolean without that proof.

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
Those Charm and Purge replays used temporary maps and scripts under
`/tmp/wc3-retail-tft-rechecks`; they did not modify repository or retail map
assets.

## TFT multi-ability Retail batch with Frida (October 4, 2026)

To compare several still-open ability behaviors in one Retail session, a
temporary JASS harness was injected into the same TFT OrcX01 map. The reusable
inputs are now kept in
[`tools/retail_probes/ability_batch_tft/`](../../../tools/retail_probes/ability_batch_tft/):
the manifest, declarations, and JASS helpers. The passive native trace is
[`tools/frida/wc3_simple_spell_validator_trace.js`](../../../tools/frida/wc3_simple_spell_validator_trace.js).
The tested executable SHA-256 was
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.

The manifest uses `War3xLocal.mpq` and
`Maps/FrozenThrone/Campaign/OrcX01.w3x`; before preparation, the source JASS
was checked for ability/tech gates and the gameplay callback. Its cinematic
gates affect `AIba`, `AIcd`, `AIad`, `AIae`, `AIgx`, and `Ashm`, not the five
probed rawcodes. The harness starts after
`Trig_Intro_Skipped_Actions` executes `gg_trg_Gameplay`, adds each stock
ability explicitly, and records observations through `PreloadGen*`. Its
sequence is Immolation (`AEim`), Shadow Strike (`AEsh`), Earthquake (`AOeq`),
Cluster Rockets (`ANcs`), then Carrion Swarm (`ACca`). The last case is a
stretch probe and is separately classified below.

To repeat the preparation, first set `result_file` in the manifest to the
`CustomMapData/ability-batch-tft-v1.txt` path under the selected Wine user's
Documents directory. Then run from the repository root:

```sh
make mpqtool
python3 tools/wc3_retail_probe.py prepare \
  tools/retail_probes/ability_batch_tft/manifest.json \
  /tmp/wc3-ability-batch/run
```

Preparation extracts an untouched control map, edits only the root
`war3map.j`, repacks that exact member, and verifies that its bytes and root
member list match expectations. Inspect `probe.json` and the staged JASS
before launching. The manifest's result path must name the same file as the
harness's `PreloadGenEnd` call.

### Wine display and launch sequence

This Wine prefix initially had no selected graphics driver. Retail and even
Wine's Notepad reported `nodrv_CreateWindow`, despite Xvfb running. Query and,
if absent, select Wine's X11 driver:

```sh
WINEPREFIX=/home/agent/.wine-war3 wine reg query \
  'HKCU\Software\Wine\Drivers' /v Graphics
WINEPREFIX=/home/agent/.wine-war3 wine reg add \
  'HKCU\Software\Wine\Drivers' /v Graphics /t REG_SZ /d x11 /f
```

Close any failed Retail process before retrying. Run the probe launcher from
inside the Xvfb shell and keep that shell alive: if `xvfb-run` exits as soon
as the probe launch tool returns, the background Retail process loses its
display. The control and prepared map use the same launch flags and input
sequence:

```sh
WINEPREFIX=/home/agent/.wine-war3 xvfb-run -a \
  -s '-screen 0 1280x720x24' bash -lc '
    export WINEPREFIX=/home/agent/.wine-war3 WAYLAND_DISPLAY= WINEDEBUG=-all
    python3 tools/wc3_retail_probe.py launch /tmp/wc3-ability-batch/run --control
    sleep 30
    xdotool mousemove 642 600 click 1
    sleep 20
    xdotool key Escape
    sleep 10
    xdotool key Print
    sleep 5
    find "$WINEPREFIX/drive_c/users/agent/Documents/Warcraft III/ScreenShots" \
      -type f -iname "*.tga" -mmin -2 -printf "%p\n"
    wine taskkill /IM "Warcraft III.exe" /F
  '
```

Confirm the untouched screenshot shows OrcX01's “To Tame a Land” chapter
card/gameplay, then exit Retail. Convert Warcraft's newly created TGA using
the project tool; do not use XWD conversion. For the prepared launch, use the
same persistent-Xvfb pattern, passing `--control-confirmed`. Start Frida server
and the trace before clicking the card; keep the shell/Xvfb alive until the
batch and bounded trace finish. For example, after the control was visually
confirmed and closed:

```sh
WINEPREFIX=/home/agent/.wine-war3 xvfb-run -a \
  -s '-screen 0 1280x720x24' bash -lc '
    export WINEPREFIX=/home/agent/.wine-war3 WAYLAND_DISPLAY= WINEDEBUG=-all
    PROBE=/tmp/wc3-ability-batch/run
    python3 tools/wc3_retail_probe.py launch "$PROBE" --control-confirmed
    sleep 30
    wine /opt/openrealm-tools/frida-server.exe --listen=127.0.0.1:27043 \
      >/tmp/wc3-ability-batch/frida-server.log 2>&1 &
    FRIDA_SERVER_PID=$!
    trap "kill $FRIDA_SERVER_PID 2>/dev/null || true" EXIT
    /opt/openrealm-tools/frida-venv/bin/python \
      tools/frida/wc3_retail_preflight.py "$PROBE" --remote 127.0.0.1:27043
    TRACE="$PROBE/frida-simple-spell.jsonl"
    /opt/openrealm-tools/frida-venv/bin/python \
      tools/frida/trace_wc3_retail.py "$PROBE" \
      --agent tools/frida/wc3_simple_spell_validator_trace.js --seconds 240 \
      --output "$TRACE" &
    TRACE_PID=$!
    until rg -q 'agent-ready' "$TRACE" 2>/dev/null; do sleep 0.2; done
    xdotool mousemove 642 600 click 1
    sleep 20
    xdotool key Escape
    sleep 50
    xdotool key Print
    wait "$TRACE_PID"
    wine taskkill /IM "Warcraft III.exe" /F
  '
python3 tools/wc3_retail_probe.py capture /tmp/wc3-ability-batch/run --timeout 180
/opt/openrealm-tools/frida-venv/bin/python tools/convert_wc3_retail_screenshot.py \
  --wine-prefix /home/agent/.wine-war3 --wine-user agent
```

The example uses the persistent shell's `DISPLAY` and Xauthority for both
Retail and `xdotool`; do not invoke `xvfb-run` only around the probe-launch
tool, because it backgrounds Retail and then tears down that display. The
Frida server and trace are bounded/passive; the preflight checks process,
map, executable hash, client version, and attach before continuing the map.
The reusable preflight and trace contract are described in
[`retail-camera-tracing.md`](retail-camera-tracing.md#optional-frida-attach-preflight).
The final prepared screenshot is
[`WC3ScrnShot_100426_234242_01.png`](../../../screenshots/tmp/WC3ScrnShot_100426_234242_01.png)
(RGB, 1024×576); it shows the expected TFT chapter card. The later gameplay
capture is
[`WC3ScrnShot_100426_234440_02.png`](../../../screenshots/tmp/WC3ScrnShot_100426_234440_02.png)
(RGB, 1024×576) and visibly includes the probe's JASS debug lines.

### Batch results and evidence limits

The capture tool read a fresh result containing `AB_META` and `AB_DONE` and
classified it `ready_for_review`. The first temporary manifest still listed
older setup-marker spellings, so it failed to notice the Carrion Swarm
`order=0`; the preserved manifest now marks any ability's `order=0` setup line
as inconclusive. This tool status is only a freshness/marker check. The
manually reviewed observations were:

| Probe | JASS observation | Review |
|---|---|---|
| Immolation (`AEim`) | Order accepted. Mana samples fell from 68.802 at 1 s to 44.006 at 5 s; the ground target took damage (life 210 to 38.034) while the air target remained at 413. | Supports mana drain and ground/air filtering for this sampled cast; it does not resolve near-zero-mana shutdown thresholds or exact payment cadence. |
| Shadow Strike (`AEsh`) | Order accepted. The target registered 10 damage events / 175.893 total damage by 16 s. A moving control was sampled, but the two units' paths diverged and starting coordinates were not logged. | Supports repeated post-cast damage for this target. The movement samples do not establish the slow amount or lifetime; poison-vs-direct damage attribution and expiry boundaries remain open. |
| Earthquake (`AOeq`) | Order accepted. Building life fell from 250 to 0 in five one-second samples; ground unit life stayed 210, and the channel order remained active until Stop. | Supports building damage and no damage to the sampled ground unit in this setup. |
| Cluster Rockets (`ANcs`) | Order accepted. By 3 s one ground unit had taken 34.579, the building 35, the second ground unit and air unit no damage. | Supports those sampled target outcomes only; the short observation does not establish the full duration, cap, or all target masks. |
| Carrion Swarm (`ACca`) | `IssuePointOrder` returned false, but later damage events were recorded on some watched units, including a same-owner unit. | Inconclusive: accepted-order status conflicts with observed damage. Use a fresh caster without an inherited `ACca`, log `OrderId("carrionswarm")` and caster state, then repeat before making a behavior claim. |

For the native trace, the executable was also checked with a targeted
radare2 disassembly (`s 0xB28980; pd 16`) rather than whole-image analysis.
At VA `0xB28980` (RVA `0x728980`, image base `0x400000`), the code saves
`ECX` as its receiver and calls `0xB4ADF0`. The read-only Frida agent logged
five validator entries for three order-ID values: `0xD0099` (also observed
as Earthquake's current JASS order), `0xD02AC`, and `0xD00FA`; all returned
zero. The hook intentionally logs pointer values without dereferencing game
objects and does not identify the receiver's concrete ability class. As
documented in [Retail return-value analysis](retail-camera-tracing.md#finding-ability-hooks-from-a-rawcode),
SimpleSpell's zero result selects further fallback validation; it does not
mean “order accepted.” The Frida trace therefore localizes shared native
validation for three order paths but does not add gameplay proof or map the
other two abilities to this function.

This one batch produced useful JASS observations for four of its five probes;
Carrion Swarm requires a corrected follow-up. It does not close the broader
open questions in the temporary ability plan, such as field meanings, caps,
aliases, expiry boundaries, or hidden target-selection rules. This batch did
add the documented JASS and Frida probe inputs to the repository but did not
modify Retail archives.

## TFT multi-ability native class and validator trace (October 5, 2026)

This follow-up kept the same five spell setup and instrumented an untouched
copy of `War3xLocal.mpq:Maps/FrozenThrone/Campaign/OrcX01.w3x`. Its retained
JASS inputs are in
[`tools/retail_probes/ability_rest_tft_v4/`](../../../tools/retail_probes/ability_rest_tft_v4/);
the class and validator agent is
[`tools/frida/wc3_ability_class_trace.js`](../../../tools/frida/wc3_ability_class_trace.js).
The Retail executable SHA-256 was
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`; the
prepared map SHA-256 was
`a37888360dede245e5dac068298dc20aa2a7a6390c745b3483bafa2fa0ee6597`.
The control screenshot
[`WC3ScrnShot_100526_113849_01.png`](../../../screenshots/tmp/WC3ScrnShot_100526_113849_01.png)
shows the untouched map in gameplay. The prepared capture
[`WC3ScrnShot_100526_114341_01.png`](../../../screenshots/tmp/WC3ScrnShot_100526_114341_01.png)
shows the final Carrion Swarm JASS report.

The exact-build data audit maps `ACca` to implementation code `AUcs` and
`CAbilityCarrionSwarm`; `AEim`, `AEsh`, `AOeq`, and `ANcs` map to their same-
named ability codes/classes. The TFT rows were read with
`build/bin/ability_audit -data 'data/Warcraft III' -tft -raw <rawcode>`.
Do not use the checked-in class registry as address authority here: it was
generated from a different executable hash.

The cached Ghidra project was reused without reanalysis. The local
`Wc3DumpFunction.java` accepts several preferred VAs in one pass:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  /tmp/wc3-ghidra-ability Wc3Retail1292 \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3DumpFunction.java \
  0x00B28980 0x00CB6200 0x00C2FA90 0x00C2F890 0x00C303C0 \
  0x00C2ED00 0x00C31430 0x00C31220 0x00C31120 0x006ADB90 \
  0x00C30BB0 0x006A9940
```

For narrow instruction checks, radare2 confirmed the validator and Carrion
call paths in the same executable:

```sh
r2 -q -e bin.relocs.apply=true -c \
  'e scr.color=0; pd 40 @ 0x00B28980; pd 40 @ 0x00C2FA90; pd 90 @ 0x00C31430; pd 24 @ 0x00C31220; pd 64 @ 0x00C30BB0; pd 18 @ 0x006A9940; q' \
  'data/Warcraft III/Warcraft III.exe'
```

Frida returned these runtime classes and expected vtables at the watched
factory addresses:

| Retail class | Factory VA | Returned vtable |
|---|---:|---:|
| `CAbilityImmolation` | `0x00B6C8B0` | `0x00F277EC` |
| `CAbilityShadowStrike` | `0x00C4EC20` | `0x00F98714` |
| `CAbilityEarthquake` | `0x00C2A0C0` | `0x00F85CF0` |
| `CAbilityClusterRockets` | `0x00C83570` | `0x00FB2C6C` |
| `CAbilityCarrionSwarm` | `0x00C2FC20` | `0x00F887B0` |

Every watched return in this trace matched its expected vtable. It also
observed the associated Immolation aura, Shadow Strike missile/buff,
Earthquake effect/buffs, and Cluster Rockets effect/artillery/buffs. The
hook counts calls and logs returned pointers; repeated calls can return the
same pointer (`CBuffImmolationAoe` did so ten times). Treat this as
class-path evidence, not a count of allocations or proof that every returned
object applied its effect.

Ghidra and radare2 show why the shared validator's integer result is not an
acceptance boolean. At `0x00B28980`, the x86 `thiscall` receiver is in `ECX`
and the first stack argument is the order ID. The function can return a
nonzero helper result directly; when that helper returns zero, it continues
through virtual target checks and fallback validation, then can return `0`,
`0x52`, or another helper result. Carrion Swarm's caller at `0x00C2FA90`
continues after a zero SimpleSpell result and checks target flags `0x2`,
`0x40`, and `0x80`; its status returns also include `0x41`. The generic call
site at `0x00CB6217` is in `FUN_00CB6200`; Carrion's direct call site is
`0x00C2FAA5` in `FUN_00C2FA90`. Preserve these values and call sites as raw
native evidence. Do not rename them “accepted” or infer behavior from zero
alone.

During this Retail run the Frida agent recorded two zero returns from
`0x00CB6217` for Earthquake and two for Cluster Rockets. For Carrion Swarm it
recorded `0xDD` at `0x00CB6217`, then `0` at `0x00C2FAA5`. The JASS
`IssuePointOrder` calls returned true for the first four abilities and false
for Carrion Swarm. Immolation spent 25 mana on activation and ended at
`913.013` mana after ten seconds; its sampled ground target took
`387.500` caster-sourced damage and the air target took none. Shadow Strike
recorded `440.178` caster-sourced damage by 18 seconds and the target's move
speed returned from 150 to 270 during that interval. Earthquake dealt 250
caster-sourced damage to the building by the five-second Stop; building life
did not fall further in the next two seconds. Cluster Rockets damaged its
sampled ground targets and building but not its sampled air or distant ground
target within the ten-second window.

The Carrion Swarm subprobe is explicitly inconclusive: `IssuePointOrder`
returned false, the JASS helper did not register `EVENT_PLAYER_UNIT_SPELL_EFFECT`,
and its damage-source samples include both a hostile target and a Player 0
target. The class construction and validator calls are proven, but these facts
do not link those damage events to a successfully accepted Carrion cast. The
capture tool marked the overall file `inconclusive` because it found the
`AR_CSW_SETUP accepted=0` marker, despite finding `AR_DONE`. Keep the separate
focused v6/v7 Carrion behavior results as the behavioral evidence; do not use
this batch to revise their target-filter conclusion.

The fresh JASS result SHA-256 is
`fea567f49a0c7aee6866ebc72ae8bfce563da332976d542ce1f3da856b6d4c66`; the
Frida JSONL SHA-256 is
`19d1e06d8251b42af38c16653cb7a3ca5856fe9e2b84e32a68e8ee38e6d28287`.
The screenshot conversion tool produced an RGB 1024×576 PNG. The preflight
record only proves attachment identity; `hooks_loaded=false` in that record
is expected because hooks are loaded by the separate trace controller.
Neither the retail archives nor their source map members were modified.

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

The retained probe inputs are in
[`tools/retail_probes/carrion_swarm_tft_v6/`](../../../tools/retail_probes/carrion_swarm_tft_v6/)
and
[`tools/retail_probes/carrion_swarm_tft_v7/`](../../../tools/retail_probes/carrion_swarm_tft_v7/).
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
[`WC3ScrnShot_100526_102322_01.png`](../../../screenshots/tmp/WC3ScrnShot_100526_102322_01.png)
(RGB, 1024×576). Control screenshots are
`WC3ScrnShot_100526_102154_01.png` and
`WC3ScrnShot_100526_103045_01.png` under `screenshots/tmp/`.

### Reproducing these Retail probes

Use the retained probe manifests rather than rebuilding the MPQ manually.
From the repository root, first make the map tool and prepare a fresh output
directory (replace the `result_file` in the manifest with the selected Wine
profile's path if needed):

```sh
make mpqtool
python3 tools/wc3_retail_probe.py prepare \
  tools/retail_probes/carrion_swarm_tft_v6/manifest.json \
  /tmp/wc3-carrion-v6
```

Preparation extracts the untouched control, stages the JASS edit, replaces
only the root `war3map.j` in a copy, checks the root member list, and byte
compares the embedded script to the staged script. Inspect `probe.json`,
`stage/war3map.j`, and the helper's exact trigger anchor before launch. To
reproduce the distal-only check, prepare the v7 manifest in a separate empty
output directory; do not reuse or overwrite a prior prepared run.

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

For a reproducible Ghidra inspection, import the exact executable once into a
temporary project and ask the checked-in script to print a target function's
references, instructions, signature, and decompilation. The first full PE
analysis was CPU intensive (715 seconds reported by Ghidra); keep the project
and use `-process -noanalysis` for subsequent address inspections instead of
reimporting or reanalyzing it:

```sh
mkdir -p /tmp/wc3-ghidra-ability
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  /tmp/wc3-ghidra-ability Wc3Retail1292 \
  -import 'data/Warcraft III/Warcraft III.exe' \
  -scriptPath tools/ghidra \
  -postScript Wc3DumpFunction.java 0x00B28980

# After that import, rerun the script at another preferred VA:
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  /tmp/wc3-ghidra-ability Wc3Retail1292 \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3DumpFunction.java 0x00C30BB0
```

`Wc3DumpFunction.java` is an inspection aid, not an automatic class or
behavior classifier. Follow string/RTTI references and registration paths,
compare the derived implementation with its base, then inspect callers to
establish parameter roles and return branches. If a candidate is a virtual
method, establish the receiver's concrete class before attaching. Ghidra's
decompiler is a navigation aid: confirm x86 `thiscall` usage, ECX, stack
arguments, and branch conditions in the disassembly.

For data and RTTI references, use the address inspector against the same
analyzed project. These addresses were found from the exact build's strings
with radare2 and then checked in Ghidra:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  /tmp/wc3-ghidra-ability Wc3Retail1292 \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3InspectAddresses.java \
  0x011B7F44 0x00F89084 0x0111F518 0x00F890D4
```

It reports the registration descriptor at `0x011B7F44`,
`CAbilityCarrionSwarm` at `0x00F89084`, its decorated RTTI name at
`0x0111F518`, and `CMissileCarrionSwarm::DamageTarget` at `0x00F890D4`, plus
incoming references and their containing functions. The class name is
referenced from `0x00C2FA40`; RTTI references lead to constructor
`0x00C2FC20` and cleanup `0x00C2FCC0`; the damage-target name is referenced
from `0x00C30BB0`. Ghidra shows the startup initializer at `0x00421610`
writing the `InstanceGenerator<CAbilityCarrionSwarm>` table pointer
`0x00F887A0` to descriptor `0x011B7F44`; registration function
`0x00C31370` passes that descriptor under FOURCC `AUcs`. The constructor at
`0x00C2FC20` writes the separate ability-instance vtable pointer
`0x00F887B0`. Keep the generator table and object vtable distinct.

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

To repeat the v7 single-target Frida check, first prepare a fresh directory
and start the matching server after the prepared Retail process is open:

```sh
python3 tools/wc3_retail_probe.py prepare \
  tools/retail_probes/carrion_swarm_tft_v7/manifest.json \
  /tmp/wc3-carrion-frida
```

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



## Exact-build static triage of remaining ability claims (October 5, 2026)

The remaining-claims inventory was cross-checked against the installed TFT
AbilityData and the exact Retail executable used above (SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`, PE32
x86, preferred image base `0x00400000`). The checked-in ability-class registry
is still unsuitable as address authority because it belongs to another hash.

### Exact-build class identities resolved

The TFT `ability_audit -raw` rows identify the implementation codes below.
Their class-name strings and reference functions were independently found in
the exact executable with radare2 `iz` and inspected in the cached Ghidra
project with `Wc3InspectAddresses.java`. The reference functions return the
matching `CAbility...` string, confirming these RTTI class identities. This
proves class naming and enables targeted method inspection; it does not prove
the ability's target or effect contract. The audit also resolves
`AHre` -> `CAbilityResurrection`, though its exact name-accessor VA was not
recovered in this pass.

| TFT row / code | Exact executable class | Name-reference function |
|---|---|---:|
| `Apxf` / `Apxf` | `CAbilityPhoenixFire` | `0x00C0D750` |
| `AOeq` / `AOeq` | `CAbilityEarthquake` | `0x00C29850` |
| `AOmi` / `AOmi` | `CAbilityMirrorImage` | `0x00C2C920` |
| `Apg2` / `Aprg` | `CAbilityPurge` | `0x00B9E2D0` |
| `AOsw` / `AOwd` | `CAbilityWard` | `0x00C340D0` |
| `Afae` / `Afae` | `CAbilityFaerieFire` | `0x00C3CC30` |
| `ANeg` / `ANeg` | `CAbilityEngineeringUpgrade` | `0x00C812B0` |
| `ANch` / `ANch` | `CAbilityCharm` | `0x00C54630` |
| `ANfa` / `ANfa` | `CAbilityColdArrows` | `0x00C5CBC0` |
| `Amfl` / `Amfl` | `CAbilityManaFlare` | `0x00C3E180` |
| `ANms` / `ANms` | `CAbilityManaShield` | `0x00C79C10` |
| `Aro1`, `Aro2` / `Aroo` | `CAbilityRoot` | `0x00B8D9D0` |
| `Arav`, `Amrf` / `Arav` | `CAbilityRavenForm` | RTTI confirmed, accessor not resolved |

The other listed string addresses were passed to Ghidra and reported as the
expected strings, with incoming references from the listed functions. These
are class-name accessors, not gameplay callbacks. Resurrection class RTTI is
present in radare2 output, but its name-reference function was not established
in this pass.

The already mapped batch classes are Immolation (`0x00B6C8B0`), Shadow Strike
(`0x00C4EC20`), Earthquake (`0x00C2A0C0`), Cluster Rockets (`0x00C83570`), and
Carrion Swarm (`0x00C2FC20`); their factory/vtable Frida trace is retained in
`tools/frida/wc3_ability_class_trace.js`. For a new live trace, use the
class-name accessor only to orient inspection. Locate the instance generator
and constructor, then identify the relevant virtual callback and call sites in
the same build. Do not hook a name accessor and present that as an executed
ability path.

### Data and contract distinctions captured

- TFT `Apxf` maps to `CAbilityPhoenixFire` (`APas` parent), DataA=20,
  DataB=2, Dur=10, HeroDur=7, Area=600, target mask ground/air/enemy. Those
  data values do not alone prove whether DataA is per-hit damage, DataB is
  cooldown, how target selection works, or whether a separate burn tick exists.
- TFT `AOmi` maps to `CAbilityMirrorImage` (`AAsp` parent). Rank DataA is
  1/2/3; DataC=2 and DataD=0.5 at every rank; Dur/HeroDur=60. Data fields
  and tooltip establish count/lifetime and authored factors only after their
  field semantics are tied to this class's reads.
- TFT `AOeq` maps to `CAbilityEarthquake` (`AAsm` parent): DataA=0.5,
  DataB=50, DataC=0.75, DataD=250, BUeq/BOea buff IDs, and 25/20 second
  Dur/HeroDur. Existing Retail observations prove building damage in one
  sampled case, but slow, mask and interruption require the class/effect
  update paths or a focused observable probe.
- TFT `AOsw` maps to `CAbilityWard` (`AAsm` parent), with `osp1`/`osp2`/`osp3`
  UnitIDs and 40-second Dur/HeroDur. This agrees with the verified rank-1
  summon and places rank-specific attack behavior in UnitData. Higher rank
  identity and creation path can be established statically if the constructor
  reads the current rawcode's UnitID; exact expiry callback semantics still
  need that path inspected.
- TFT `ANeg` DataC–F explicitly names the next-rank dependent codes
  (`ANsy`/`ANcs`/`ANrg`/`ANde`, then `ANs1`/`ANc1`/`ANg1`/`ANd1`), alongside
  movement and damage values in DataA/B. This establishes dependency aliases,
  not how the runtime applies/recomputes those upgrades; follow the upgrade
  class and recipient stat/ability paths.
- TFT `ANch` has target mask air/ground/nonhero/enemy/neutral/organic and
  DataA=5; alias `ACch` has its own mask, cost and DataA=6. The earlier JASS
  results establish stock `ANch` cases only. The alias is a concrete
  unresolved difference requiring class validation/data interpretation.
- The form rows resolve `Arav` -> `CAbilityRavenForm` with `DataA=edot`,
  `UnitID=edtm`; `Amrf` shares `Arav` and uses `DataA=nmed`, `UnitID=nmdm`.
  Root rows `Aro1` and `Aro2` share `Aroo` but reverse DataA/DataB
  (1/2 versus 2/1). This establishes the authored pairings; inspect the
  `CAbilityRoot` and `CAbilityRavenForm` transition code and paired UnitData
  before claiming preservation, legal placement, or form behavior.
- TFT `ANfa` is the concrete `CAbilityColdArrows` class; inspect attack
  event/launch callbacks for mana, bonus, autocast and target gates rather
  than infer them from the effect class names.
- TFT item rows resolve `AInm` -> `AIsm` (`CAbilityStrengthMod`, DataC=2),
  `AIgm` -> `AIam` (`CAbilityAgilityMod`, DataA=2), and `AItm` -> `AIim`
  (`CAbilityTome`, DataB=2). Their `CAbility...` family indicates passive
  object classes, but it does not prove permanent versus removable stat
  mutation; inspect their stat mutation callers and inverse/removal code.
- `ACff` shares `Afae` with `CAbilityFaerieFire` and shares BuffID `Bfae`,
  while its Dur/HeroDur and cooldown differ. The alias audit confirms `ACpu`
  shares `Aprg` with `Apg2`, Charm's `ACch`
  has a six-level limit while `ANch` has five, and Carrion aliases carry
  materially different masks/damage caps. Static class sharing must not be
  mistaken for identical authored behavior.

### Virtual callback reconnaissance completed

#### Phoenix Fire native path: periodic acquisition and target gates

For the exact executable hash above, `CAbilityPhoenixFire` has a concrete
scheduled event path. Function `0x00C0D7D0` reads the ability's configured
interval through virtual slot `+0x2EC`, then schedules event `0xD01B0` against
the member at `this+0x84`. The virtual event handler at `0x00C0D820` ignores
other event IDs and calls `0x00C0ECD0` only for `0xD01B0`. This establishes a
recurring native ability event; the exact interval field-to-AbilityData
mapping is still open.

`0x00C0ECD0` obtains the owning unit (`this+0x30`) and its current position,
then calls the area-unit enumerator `0x0068EA00` with callback `0x00C0F1E0`.
The scan is centered on the owner and takes its radius/configuration from the
ability's data object (`this+0x50`). If one or more candidates survive, the
handler selects one index through `0x00699FD0` and continues into a status
effect setup path (`0x006EC8F0`) using that selected unit. This is evidence of
periodic nearby target acquisition and one selected target per event; it does
not by itself prove the exact native damage payload or tick amount.

The callback and generic helpers establish these target gates:

- The callback rejects candidates whose field at `+0x1F4` is positive. The
  field's semantic name has not been recovered.
- It obtains the candidate's classification through vtable slot `+0x310` and
  passes it to `0x00682180`. That helper checks the two general spell-target
  rejection paths `0x00682210` and `0x006822E0`, followed by registered target
  validators. The first two paths consult target virtual predicates and the
  `MagicImmunesResistUltimates` setting; their numeric returns are internal
  rejection codes, not damage values.
- It queries the candidate for buff FOURCC `Bpxf` (`0x42707866`) through
  `0x006D6570` and rejects candidates where that buff is already present.
- It calls `0x0067FB80` with the owner and candidate context as a further
  target-relationship check. The helper consults owner/target flags and the
  shared target validator; its exact semantic label remains unresolved.

After selection, the setup path queries the shared `CBuffPhoenixFire`
definition by FOURCC `Bpxf` and passes the selected-unit context into
`0x006EC8F0`. Together with the duplicate-buff gate, this supports a
Phoenix-Fire-owned status/effect being installed on the selected target. The
binary also contains `CMissilePhoenixFire`, but this pass has not connected its
factory/update/hit path to the periodic handler or established whether damage
is applied by that missile, the buff's tick callback, or both. Therefore the
following remain unverified statically: DataA damage meaning, DataB cadence,
Dur/HeroDur relationship, exact radius field, damage type, and expiry/removal
behavior. Do not promote the tooltip or the presence of the missile class into
proof of those details.

The inspection can be reproduced in the cached exact-build Ghidra project by
dumping `0x00C0D7D0`, `0x00C0D820`, `0x00C0ECD0`, `0x00C0F1E0`, `0x00682180`,
`0x00682210`, `0x006822E0`, `0x006D6570`, `0x0067FB80`, and `0x006EC8F0` with
`Wc3DumpFunction.java`. Cross-check target constants and short branch sequences
with radare2 before assigning semantics, and retain the exact executable hash
when reporting these addresses.

A follow-up mapped actual vtable globals written by the exact-build
constructors, rather than reading the adjacent class-name / RTTI data as a
vtable. The inspected addresses below are for the executable hash above and
must be re-derived for another build.

| Class | Constructor / vtable VA | Inspected class-specific methods | Static conclusion |
|---|---|---|---|
| `CAbilityResurrection` | constructor `0x00C0F6E0`, vtable `0x00F76CC4` | `0x00C0F5A0`/`0x00C0F5C0` delegate to parent and serialize nested members; `0x00C0F520` forwards through a member at offset `0x13C`; rawcode getter `0x00C0F510` returns FOURCC `AHre` | The timer/member callback at `0x00C0F520` has not been assigned a gameplay role. This pass did not identify the corpse scan or restoration effect. |
| `CAbilityPhoenixFire` | constructor `0x00C0E570`, vtable `0x00F75CB0` | shared save/load virtuals `0x00C0F5A0`, `0x00C0F5C0`; rawcode getter not established in this table | The scheduled nearby-target acquisition and `Bpxf` status setup path are now identified below; damage, interval field mapping and missile/buff tick ownership remain unresolved. |
| `CAbilityMirrorImage` | constructor `0x00C2D370`, vtable `0x00F8764C` | `0x00C2CB60` save, `0x00C2CA80` load, `0x00C2CA30` cleanup; `0x00C2C930` returns FOURCC `AOmi` | The observed custom callbacks write/read owned state, nested data and a counted collection, then release that collection. They do not establish illusion creation, damage factors, copied Hero state, or dispel behavior. |
| `CAbilityRavenForm` | constructor `0x00BAE9E0`, derived vtable `0x00F4A000` | `0x00BADD40` dispatches ability event/order IDs; `0x00BAF000`, `0x00BAF2B0`, `0x00BAEF70` are called from that dispatch; `0x00BADF40`/`0x00BADFF0` serialize state | This class derives from the shared `CAbilityMorph` path and has form-state callbacks. The inspected branch uses unit/ability state flags, but this pass has not proven exact preservation or each rawcode's legal transition behavior. |
| `CAbilityRoot` | constructor `0x00B8E760`, vtable `0x00F36050` | `0x00B8E290`, `0x00B8E4A0`, `0x00B8E4E0` serialize/restore nested fields; `0x00B8D9E0` returns FOURCC `Aroo` | The class keeps persistent per-ability state. These callbacks do not prove the rooted/mobile transition rules or placement checks. |

**Correction to the preceding class-triage table:** Resurrection's verified
name-reference accessor is `0x00C0F500` (class string `0x00F7755C`), and its
constructor writes vtable `0x00F76CC4`. Phoenix Fire's name accessor is
`0x00C0D750`; its constructor is `0x00C0E570` and writes vtable
`0x00F75CB0`. The two neighboring vtables must not be conflated when writing
a Frida receiver filter. Both tables reference shared `0x00C0F5A0` and
`0x00C0F5C0` save/load virtuals.

The current cached Ghidra project does not provide trustworthy C++ types or
virtual method names. `Wc3DumpFunction.java` can decompile a requested VA, but
that alone does not assign a semantic role. For the inspected serialization
methods, the conclusion above comes from explicit calls to serializer
helpers, stream arguments and paired save/load callbacks. No executable
method in this batch established the remaining gameplay outcomes, so no
behavior claim was promoted to verified merely from class presence or member
layout. The class-name/registration mapping and object-data findings remain
valid independently of this method-role limitation.

### Remaining native inspection queue

No ability-specific runtime factories were hooked in this triage pass. The
class identities above came from exact-build binary data/RTTI and are enough
to choose native code for static work. Use Frida only where a static caller or
receiver remains ambiguous; prioritize these unresolved questions:

1. Phoenix Fire: map its configured interval/radius and DataA/B fields to
   concrete reads, then trace `CBuffPhoenixFire` and `CMissilePhoenixFire`
   callbacks through expiry and damage application.
2. Mirror Image: summon/clone creation, factor reads, copied unit state, and
   `CBuffMirrorImage`/dispel removal paths.
3. Resurrection: corpse candidate validator, ordering/limit reads, and
   restoration/owner semantics. Item `AIrs` is a separate item row.
4. Earthquake: effect tick cadence, structure/unit candidate masks, DataA–D
   reads, and interrupt cleanup.
5. Purge/Charm: alias-specific target/data checks and success-side ownership
   transfer; Charm's custom-unit level anomaly and resource accounting remain
   unexplained.
6. Ward/Faerie Fire: UnitID selection/expiry and reveal source ownership,
   refresh and removal paths.
7. Crow Form and Root: pair each order transition to the exact UnitData form,
   then inspect unit rebind/state-copy and placement predicates.
8. Shadow Strike, Immolation, Cluster Rockets, Mana Flare, Mana Shield and
   Carrion Swarm: continue from existing observations by mapping each field
   read to its row and tracing expiry/alias branches; Carrion's inner geometry
   and cap remain open as recorded above.
9. Cold Arrows and permanent stat items: inspect attack-event qualification,
   mana/stat mutation, and whether the inverse path exists for the item class.
10. Engineering Upgrade: follow DataC–F's next-rank FourCCs into rank
    replacement and Tinker form/stat recomputation.

Do not label an item/ability contract verified from RTTI or tooltip alone. For
static completion, record the native function/callsite, exact data field or
predicate, and resulting branch/effect together. If that is still ambiguous,
add a narrowly scoped exact-hash Frida trace and pair it with the corresponding
Ghidra caller path before deciding whether JASS can be skipped.

### Fast-candidate follow-up: data verified, native behavior still open (October 5, 2026)

This follow-up rechecked the most bounded candidates against the installed
AbilityData, resolved tooltips and exact Retail executable hash above. The
claims below are split by evidence type: authored values and class identity
are confirmed; runtime effect ownership/removal is not promoted to verified
where the native behavior callback has not been recovered.

| Candidate | Confirmed from installed data / exact-build binary | Still open |
|---|---|---|
| Serpent Ward (`AOsw` / `AOwd`) | The three ranks select UnitIDs `osp1`, `osp2`, `osp3`; each has 40-second Dur/HeroDur, cost 30, range 500, and buff `BOwd`. The resolved rank tooltips name each corresponding UnitData row for hit points and attack damage. Exact-build audit class is `CAbilityWard`, parent `AAsm`; exact-executable string accessor `0x00C340D0` returns `CAbilityWard`. | Constructor/vtable and cast callback not recovered in this pass. Thus the actual UnitID read, summon ownership, expiry timer and cleanup path remain open; the tooltip proves authored row references, not runtime consumption. |
| Faerie Fire (`Afae`) | AbilityData gives cost 45, range 700, DataA=4 armor reduction, Dur=90/HeroDur=60, and buff `Bfae`; its tooltip states armor reduction and vision. `ACff` shares class and BuffID but has distinct authored duration/cooldown. Exact-build audit class is `CAbilityFaerieFire`, parent `AAat`; accessor `0x00C3CC30` returns the class string. | Reveal source ownership, refresh behavior, hero-duration selection, and expiry/removal are not yet tied to native callbacks. |
| Frost Arrows (`ANfa` / `AHca`) | All three rank rows specify bonus damage 5/10/15, attack slow 30/50/70%, movement slow 30/50/70%, 5-second normal / 1.5-second Hero duration, cost 10, and `BHca`/`Bcsd`. Tooltip resolves those exact rank fields. Exact-build audit resolves implementation code `AHca` to `CAbilityColdArrows` (parent `AHRa`); accessor `0x00C5CBC0` returns the class string. | Attack-event qualification, mana payment, autocast target gates, damage application, stack/doT state (`Bcsd`), refresh rules, and inverse expiry callback remain open. `AHca` and `ANfa` are distinct raw rows even though they share the implementation code; compare the alias-specific values before claiming parity. |
| Engineering Upgrade (`ANeg`) | Three ranks author movement bonus 10/20/30%, attack bonus 2/4/6, and DataC–F dependent ability codes (`ANsy`/`ANcs`/`ANrg`/`ANde`, then `ANs1`/`ANc1`/`ANg1`/`ANd1`). Tooltip confirms movement and attack bonuses. Exact-build audit class is `CAbilityEngineeringUpgrade`, parent `APas`; accessor `0x00C812B0` returns the class string. | Whether the class actively replaces abilities/recomputes existing Tinker state or relies on other stat/dependency mechanisms is not proven. Constructor, vtable, rank-up callback and recipient stat path remain to be mapped. |
| Permanent stat items (`AInm`/`AIsm`, `AIgm`/`AIam`, `AItm`/`AIim`) | Installed AbilityData maps Strength Gain to `CAbilityStrengthMod` (DataC=2), Agility Gain to `CAbilityAgilityMod` (DataA=2), and Tome to `CAbilityTome` (DataB=2). TFT class registry lists the corresponding concrete registration codes and class parents. | This pass did not establish whether the item class mutates a base stat permanently, uses a removable ability modifier, or has a destruction inverse. The implementation/effect caller and item-removal path must be followed before calling permanence verified. |

The native class-name checks used here are exact-build RTTI string accessors,
not gameplay functions: Ward `0x00C340D0`, Faerie Fire `0x00C3CC30`,
Engineering Upgrade `0x00C812B0`, and Cold Arrows `0x00C5CBC0`. The RTTI
registry metadata in `games/warcraft-3/tft-ability-classes.txt` supplies
factory and registration addresses, but those fields are relative offsets in
its source executable and cannot be copied as preferred VAs into the Retail
1.29.2 executable. Attempting to treat RTTI generator records as native
constructors did not yield reliable method boundaries. Re-derive constructor
and vtable addresses from this exact executable before continuing static
callback inspection or setting Frida hooks.

No behavior claim in this batch is fully verified by native code. A follow-up
should prioritize one callback family at a time: (1) Ward cast → configured
UnitID → summon timed-life cleanup; (2) Faerie Fire hit → Bfae application →
vision/duration inverse; (3) Cold Arrows attack callback → mana/damage/buff
fields → buff expiry; (4) Engineering Upgrade rank reads → dependent ability
and stat updates; (5) item stat mutation → drop/remove/destroy inverse. The
data/tooltip evidence above can be reused without another Retail run, while a
runtime probe is needed only if those static paths cannot settle an observable
branch.

See [shared native ability functions](ability-shared-native-functions.md) for
exact-build helpers and Ghidra caller counts that can shorten these callback
investigations. See [Retail ability architecture](ability-retail-architecture.md)
for the recovered registration, instance, cast, and attached-status model.


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
is not significant on the Wine filesystem. Convert the newest TGA to PNG under
the repository's ignored `screenshots/tmp/` directory; the converter removes
the TGA only after validating the PNG. Do not derive Retail evidence PNGs from
XWD captures: the earlier XWD conversion produced striped pixels even though
its PNG metadata reported RGB.

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

Convert the newest TGA with the repository tool. It validates the output PNG
as RGB with the original dimensions and deletes the TGA only after validation
succeeds. By default it searches `$WINEPREFIX` (or `~/.wine-war3`) and writes
beside the repository under `screenshots/tmp/`:

```sh
/opt/openrealm-tools/frida-venv/bin/python tools/convert_wc3_retail_screenshot.py \
  --wine-prefix /home/agent/.wine-war3 --wine-user agent
```

The output keeps the TGA's timestamped basename with a `.png` extension. If
the corresponding PNG already exists, the tool stops and leaves the TGA in
place. The verified sample TGA was RGBA at 1024×576; its converted PNG was RGB
at the same dimensions. This is a property of that capture, not a guarantee
about all Retail window sizes. The tool needs Pillow; use a Python environment
that has it installed. `screenshots/` is ignored by Git, so these local
evidence images are not committed by default. See
[`tools/README.md`](../../../tools/README.md#convert_wc3_retail_screenshotpy)
for options and behavior.

The sample image showed the in-game JASS comparison output for the test:
rank 2 was accepted and produced unit type `1869836338` (`osp2`). The screenshot
is supplementary visual evidence; the saved JASS result and the written
ability observation remain the behavior record.
