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
