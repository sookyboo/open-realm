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

- Poison callback `0x00BDCF70` looks up existing `Bpoi`; on its creation
  branch it constructs/configures a poison object and attaches it through
  `0x006D4880`. Its refresh branch invokes the existing object's virtual
  `+0x388`. This locates poison status installation/refresh but does not
  identify the attack event producer.
- Pocket Factory missile impact callback `0x00C829F0` creates a `BNfy`
  `CBuffFactory` object after constructing the factory unit, then attaches
  it through the same wrapper. This is a different ability and buff class.

Reproduce the wrapper disassembly with:

```sh
r2 -q -c 'e scr.color=0; pd 12 @ 0x006d4880; pd 12 @ 0x006f6e80; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The exact attack-to-poison producer and argument meanings remain the next
combat investigation; do not infer them from this shared attachment path.

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
