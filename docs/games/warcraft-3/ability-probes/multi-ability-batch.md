# TFT multi-ability Retail batch and native trace

This focused report records the controlled JASS batch and exact-build class/validator trace. For a short outcome summary and open questions, see [Retail verification status](../ability-verification-review.md).

## TFT multi-ability Retail batch with Frida (October 4, 2026)

To compare several still-open ability behaviors in one Retail session, a
temporary JASS harness was injected into the same TFT OrcX01 map. The reusable
inputs are now kept in
[`tools/retail_probes/ability_batch_tft/`](../../../../tools/retail_probes/ability_batch_tft/):
the manifest, declarations, and JASS helpers. The passive native trace is
[`tools/frida/wc3_simple_spell_validator_trace.js`](../../../../tools/frida/wc3_simple_spell_validator_trace.js).
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
[`retail-camera-tracing.md`](../retail-camera-tracing.md#optional-frida-attach-preflight).
The final prepared screenshot is
[`WC3ScrnShot_100426_234242_01.png`](../../../../screenshots/tmp/WC3ScrnShot_100426_234242_01.png)
(RGB, 1024×576); it shows the expected TFT chapter card. The later gameplay
capture is
[`WC3ScrnShot_100426_234440_02.png`](../../../../screenshots/tmp/WC3ScrnShot_100426_234440_02.png)
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
| Shadow Strike (`AEsh`) | Order accepted. The initial batch recorded repeated target damage, but its moving control did not isolate slow or poison. See the controlled follow-ups below. | Earlier samples are superseded for slow and poison attribution by the source-filtered/stationary follow-ups below. |
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
documented in [Retail return-value analysis](../retail-camera-tracing.md#finding-ability-hooks-from-a-rawcode),
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
copy of `War3xLocal.mpq:Maps/FrozenThrone/Campaign/OrcX01.w3x`. The currently
checked-in JASS probe template is
[`tools/retail_probes/ability_batch_tft/manifest.json`](../../../../tools/retail_probes/ability_batch_tft/manifest.json);
the original `ability_rest_tft_v4` manifest and
`wc3_ability_class_trace.js` script are absent from this checkout. Class and
validator trace results are preserved below.
The Retail executable SHA-256 was
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`; the
prepared map SHA-256 was
`a37888360dede245e5dac068298dc20aa2a7a6390c745b3483bafa2fa0ee6597`.
The control screenshot
[`WC3ScrnShot_100526_113849_01.png`](../../../../screenshots/tmp/WC3ScrnShot_100526_113849_01.png)
shows the untouched map in gameplay. The prepared capture
[`WC3ScrnShot_100526_114341_01.png`](../../../../screenshots/tmp/WC3ScrnShot_100526_114341_01.png)
shows the final Carrion Swarm JASS report.

The exact-build data audit maps `ACca` to implementation code `AUcs` and
`CAbilityCarrionSwarm`; `AEim`, `AEsh`, `AOeq`, and `ANcs` map to their same-
named ability codes/classes. The TFT rows were read with
`build/bin/ability_audit -data 'data/Warcraft III' -tft -raw <rawcode>`.
Do not use the checked-in class registry as address authority here: it was
generated from a different executable hash.

The checked-in Ghidra project in `screenshots/ghidra/WarcraftIII` is the
exact-build project; its checked-in `functions.csv` provides function
boundaries. `Wc3DumpFunction.java` is not present in this checkout, so use the
Ghidra GUI for decompilation/references and radare2 for reproducible
instruction checks. Do not use the stale `/tmp/wc3-ghidra-ability` project.

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/screenshots/ghidra" WarcraftIII \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath "$PWD/screenshots/ghidra" \
  -postScript ExportFunctionInventory.java /tmp/wc3-functions-check.csv
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

### Shadow Strike movement-speed follow-up (October 16, 2026)

A focused replay used the same pinned Retail executable and OrcX01 campaign
map. It removed both movement orders from the Shadow Strike target/control
pair and logged `GetUnitMoveSpeed` alongside their positions once per second.
The JASS cast returned true; both units reported speed `270.000` before the
cast. The target remained at a fixed position. At the first one-second sample
after the cast, it reported `150.000` while the control remained `270.000`.
Subsequent target samples rose to `160.084`, `181.851`, `200.536`,
`216.374`, and `229.601`; the control stayed at `270.000`. This confirms a
cast-associated movement slow and a changing slow magnitude in this rank-1
scenario.

That first run's target died before the slow ended, so a second replay raised
both targets' max/current life to 10,000 and observed for 30 seconds. The
target remained at a fixed position and alive. Its reported speed rose through
`160.084`, `181.851`, `200.536`, `216.374`, `229.601`, `240.452`, `249.162`,
`255.966`, `261.100`, `264.799`, `267.297`, `268.832`, and `269.637`; at the
15-second sample it was `270.000`, matching the unchanged control. It stayed
at `270.000` through the 30-second sample. This confirms natural recovery to
baseline by 15 seconds in this rank-1 scenario. The initial `150.000` may be a
movement-speed floor, so it does not establish the underlying slow percentage
or exact internal decay formula.

#### Initial hit and poison pulse capture

A third replay logged each `EVENT_UNIT_DAMAGED` event's source, source owner,
and amount while the 10,000-life target remained stationary and alive. The
accepted rank-1 `AEsh` cast produced a `75.000`-damage event at the first
sample (`AB_SS_EVENT tick=1`); the event source was the caster (`Ewar`, Player
0). Further caster-sourced events of exactly `10.000` occurred at ticks 7, 13,
19, 25, and 31. The JASS timer advances every 0.5 seconds, so those five
equal-damage pulses are spaced by 3 seconds; the last observed pulse falls at
the end of the authored 15.1-second status window, within the timer's half-
second sampling phase. Other caster-sourced events had variable amounts,
consistent with ordinary combat damage; they are not counted as poison pulses.
This directly confirms the level-1 initial damage and five poison pulses for
this cast.

The installed TFT `AbilityData` audit independently gives `AEsh` DataA=10,
DataB=0.5, DataC=0, DataD=3, DataE=75, Cast=3, and Dur/HeroDur=15.1. Its
tooltip specifies DataE as initial damage and DataA every Cast seconds for
Dur; the event capture matches those values. Runtime speed starts at the
150-unit floor and recovers to 270 by the 15-second sample, consistent with
the authored 0.5 movement reduction decaying over the poison duration. The
exact internal decay curve is not established. The hero row has DataC=0, so it
does not author an attack-rate reduction; the attempted cooldown native query
returned 0 for both units and cannot test attack speed dynamically.

The creep alias `ACss` shares the `CAbilityShadowStrike` class and `BEsh` buff,
but its authored values differ: DataA=10, DataB=0.9, DataC=0.9, DataE=75,
Cast=2, Dur/HeroDur=15.1. A separate cast added `ACss` to the test caster and
used a mechanical `hmtm` target, which is compatible with the alias's authored
target mask. Retail accepted the order; the target received a caster-sourced
75 initial hit and five caster-sourced 10-damage pulses at 3-second intervals.
Its movement speed stayed at the engine floor initially, then recovered to
270 by the 16-second sample, while the untreated control stayed at 270. This
confirms the alias's hit, poison, and movement-slow path in this scenario. At
the time, its DataC=0.9 attack-rate reduction remained dynamically unverified
because the Retail `BlzGetUnitAttackCooldown` query returned zero for both
units. The focused attack-cycle result below supersedes that open item.

#### Shadow Strike movement-speed curve (October 16, 2026)

A separate 35-second Retail 1.29.2.9231 JASS probe compared rank-1 `AEsh`,
rank-1 `ACss`, and an untreated control. It used three Neutral Hostile
Footmen, set each reported movement speed to 400, position-locked them, and
sampled `GetUnitMoveSpeed` every 0.25 seconds. Both casts were accepted and
confirmed by `EVENT_UNIT_SPELL_EFFECT`; 19 baseline samples showed all three
lanes at 400. Speeds below 150 are clamped by Retail's movement floor.

| First sampled speed at or above | `AEsh` age after effect | `ACss` age after effect |
|---:|---:|---:|
| 200 | 0.25 s | 4.25 s |
| 250 | 2.25 s | 6.25 s |
| 300 | 4.25 s | 8.25 s |
| 350 | 6.25 s | 10.25 s |
| 390 | 10.25 s | 13.25 s |
| 400 | 14.25 s | 15.25 s |

At the first sample, `AEsh` reported 200 while `ACss` was clamped at 150;
the control stayed at 400 throughout. This directly measures distinct
movement-slow recovery curves consistent with their authored DataB values
(0.5 and 0.9). The 0.25-second samples do not prove the engine's continuous
decay formula or behavior between samples.

Raw result: [retail-1292-run1.txt](../../../../tools/retail_probes/shadow_strike_movement/evidence/retail-1292-run1.txt),
SHA-256 `f4df0b3182b480b98ecc796566e6272462125eee06cee5d381714f7f1be9fac1`.
The rerunnable manifest and JASS are in
[`tools/retail_probes/shadow_strike_movement/`](../../../../tools/retail_probes/shadow_strike_movement/).

Raw event capture: `/tmp/wc3-shadow-events-verify/run/result.txt`, SHA-256
`88aa2c6b6911224ffe0e3e8ba384bc65dae00d5fc49018cdca477499dd5e5e2b`.
The source-filtered event rows and long-lived speed samples can be reviewed
there. The earlier disposable captures remain under
`/tmp/wc3-shadow-slow-verify/` and `/tmp/wc3-shadow-final-verify/run3/`.
The `ACss` capture is `/tmp/wc3-shadow-alias-verify/run/result.txt`, SHA-256
`8022a1449fa57407f4404c8d2ab1fd270c362f458bd3cd433c9bd561f8956882`.

#### ACss attack-cycle verification (October 16, 2026)

A JASS run on Retail 1.29.2.9231 compared two Mortar Teams attacking paused,
high-health targets. The caster applied stock `ACss` to lane A only; both
attackers remained stationary at the 150-unit movement floor. Damage events
were sampled every 0.1 seconds. The cast order returned true, and
`EVENT_UNIT_SPELL_EFFECT` confirmed the cast at tick 105.

Both lanes had 3.5-second attack intervals before the cast (ticks 14–49–84).
The untreated control stayed at 3.5 seconds throughout. The treated lane's
intervals lengthened to 5.9 seconds (84–143), then 5.6 seconds (143–199), then
3.9 seconds (199–238), and recovered to 3.5 seconds by the next interval
(238–273). Both lanes continued to produce hits through the 55-second run;
position and life samples show neither attacker moved or died. This controlled
difference verifies that stock `ACss` reduces attack rate and that its effect
decays in this rank-1 scenario. The samples do not establish an exact internal
decay formula or percentage curve.

Raw result: `/tmp/wc3-shadow-attack-focused/run10/result.txt`, SHA-256
`cd0ed078eefa659bb01737b75df7c659e862fe8cedc46cb8e5d88d2f828b206a`.
The probe map and JASS sources remain temporary under
`/tmp/wc3-shadow-attack-focused/run10/` and were not committed.

#### ACss attack-cycle replay with a live JHCR update

A further Retail 1.29.2.9231 run used the probe runner's `prepare --jhcr`
path, then loaded that instrumented OrcX01 map. During the run, the runner's
`jhcr-update` command published sequence 1; the in-map reload trigger reported
`SS_JHCR_STATUS=1`. The update changed only the logging helper, and its
`SS_JHCR_SAFE_UPDATE` marker appeared 20 times in the completed result,
confirming that execution continued through the reloaded code.

The ability observations matched the earlier attack-cycle result: accepted
`ACss`, spell effect at tick 104, 35-tick baseline intervals in both lanes,
and control intervals fixed at 35 ticks. Treated-lane intervals stretched to
60, 55, and 39 ticks after the cast, then returned to 35 ticks. The run
finished at tick 550 with 14 treated-lane and 16 control-lane hits. This
independently reproduces the attack-rate reduction while exercising live JHCR
reload during the probe.

A mission-restart replay in the same Warcraft process produced the same
pattern: cast effect at tick 105, 35-tick baseline/control intervals, then
treated intervals of 59, 56, and 39 ticks before returning to 35. The run
completed at tick 550 with 14 treated and 16 control hits. The one-tick
differences from the earlier 60/55/39 sample are consistent with the 0.1-second
event sampling phase. This repeat confirms the discrete attack-cycle response;
it still does not identify the engine's continuous decay formula.

Raw replay: [jhcr-restart-run.txt](../../../../tools/retail_probes/shadow_strike_attack_cycle/evidence/jhcr-restart-run.txt), SHA-256
`a7769eab80b092252c06df4ad368409598e881d38e8556dbf259ac7ef5a5f04e`.

#### ACss focused decay-curve run (October 16, 2026)

A dedicated 50 ms JASS probe replaced the Mortar Team with a Footman, whose
Retail `UnitWeapons.slk` authored cooldown is 1.35 seconds. The earlier attempt
to use `BlzSetUnitAttackCooldown` was ineffective in this 1.29.2 setup: the
getter returned zero, and Mortar Teams kept their authored 3.5-second cycle.
The revised probe allowed eight baseline intervals before casting, then ran
for 60 seconds with a same-unit untreated control. Both orders were accepted;
the spell-effect event confirmed the cast at tick 259.

Baseline and control intervals stayed at 27 ticks (1.35 seconds). The treated
lane's first post-cast hit arrived 68 ticks (3.4 seconds) after the spell-effect
event; its interval crossing the cast boundary was 73 ticks. Subsequent
intervals were 53, 39, 34, 31, and 29 ticks, returning to 27 ticks by the next
hit. This confirms a substantial attack-cycle delay that decays over successive
attacks during stock rank-1 `ACss`. It does not establish the internal formula
or a continuously sampled attack-speed percentage.

Raw result: [retail-1292-run1.txt](../../../../tools/retail_probes/shadow_strike_decay/evidence/retail-1292-run1.txt),
SHA-256 `66eee38fef96a6705cf0dad298202d31401b364baffcfa739f1f798199014b4b`.
The rerunnable setup is in
[`tools/retail_probes/shadow_strike_decay/`](../../../../tools/retail_probes/shadow_strike_decay/).

Do not hot-reload an active periodic timer callback as part of this harness:
an attempted update to `SS_Tick` returned status 1 but stopped its counter at
tick 418, preventing `SS_DONE`. Updating the non-callback `SS_Log` helper left
the timer running to completion. Raw result:
`/tmp/jhcr-shadow-strike-safe/result.txt`, SHA-256
`b59597dd897a1f49bfb4de76c8b934a1228f1df890dc7e0918f835dd16936b4e`.

`AEsh` is closed for attack speed: its DataC=0, so it authors no attack-rate
reduction. For the creep alias, attack-rate reduction and discrete recovery
over successive attacks are verified above; only the internal decay formula
remains open.

The fresh JASS result SHA-256 is
`fea567f49a0c7aee6866ebc72ae8bfce563da332976d542ce1f3da856b6d4c66`; the
Frida JSONL SHA-256 is
`19d1e06d8251b42af38c16653cb7a3ca5856fe9e2b84e32a68e8ee38e6d28287`.
The screenshot conversion tool produced an RGB 1024×576 PNG. The preflight
record only proves attachment identity; `hooks_loaded=false` in that record
is expected because hooks are loaded by the separate trace controller.
Neither the retail archives nor their source map members were modified.
