# Cheat commands

The engine exposes `sv_cheats`, defaulting to `0`. Game commands are server-authoritative and are rejected until cheats are enabled:

```
set sv_cheats 1
give ...
```

This follows the Quake 2 model: `give` is a game/server command, while `+give` is a late command-line command that runs after the map command when both are supplied. For example:

```
openwarcraft3 +set sv_cheats 1 +map Azeroth +give all
```

The Quake 2 reference implementation supports `give all`, health, weapons, ammo, armor and power items, plus `god`, `notarget`, and `noclip`; it also refuses these commands in deathmatch unless `sv_cheats` is enabled. See the [Quake 2 g_cmds.c source](https://unix.superglobalmegacorp.com/cgi-bin/cvsweb.cgi/quake2/game/g_cmds.c?cvsroot=quake2%3Bf%3Dh%3Bonly_with_tag%3DiD%3Bcontent-type%3Dtext%2Fx-cvsweb-markup%3Bln%3D1%3Brev%3D1.1.1.1).

## Warcraft III

For map-start resource testing, `wc3_cheat_starting_resources` is a session-only CVar. Set it before loading the map:

```
openwarcraft3 +set wc3_cheat_starting_resources 1 +map "Maps/Campaign/Human02.w3m"
```

When enabled, the map load arms a one-shot +5000 gold / +5000 lumber grant for each used human-controlled slot. The grant is not tied directly to `war3map.j main()`: OpenRealm waits until that human client is connected, user control is enabled, and the ordinary gameplay UI has returned from any intro cinematic, then adds the bonus to the resource values authored by the map at that boundary. Computer and neutral players are unchanged, values clamp to the player-state storage limit, and each human client can receive the grant only once per fresh map load. Save-game restoration preserves the saved resource totals and disables any still-pending map-start grant so loading cannot award another +5000. The CVar is sampled when the map is spawned; changing it mid-map does not grant resources until the next map load/restart. Because this is a pre-map CVar rather than a client cheat command, it does not require `sv_cheats`. The default is `0`.

The playable-state boundary is necessary for campaign maps. A Human02 runtime trace showed the generated initialization setting the human slot to `0` gold / `0` lumber, followed by a later `EVENT_PLAYER_END_CINEMATIC` path that authored the real starting values as `300` gold / `50` lumber. Applying the cheat immediately after `main()` therefore produced `5000/5000` only for the campaign trigger to overwrite it with `300/50`. Waiting until the cinematic returns control makes the same map resolve to `5300/5050`. Melee maps without an intro cinematic receive the grant on their first playable server frame after initialization.

Diagnostics use the `WC3_CHEAT_RESOURCES` prefix. With the CVar enabled, relevant lines are intentionally sparse: `armed` records that the map latched the cheat, `defer` records a connected human still held by cinematic/input state, human `SetPlayerState` resource writes expose map-authored late values, and `apply` records the final before/after totals. For Human02 the expected useful tail is conceptually:

```text
WC3_CHEAT_RESOURCES defer ... gold=0 lumber=0
WC3_CHEAT_RESOURCES SetPlayerState ... state=1 ... requested=300
WC3_CHEAT_RESOURCES SetPlayerState ... state=2 ... requested=50
WC3_CHEAT_RESOURCES apply ... gold=300->5300 lumber=50->5050
```

Resource commands target the issuing player and are additive, so they work even when no unit is selected:

```
give gold <amount>
give lumber <amount>
give res <amount>       # add the amount to both gold and lumber
```

Amounts are non-negative integers and clamp at the player-state resource storage limit rather than wrapping. These commands require `sv_cheats 1`; they are independent of `wc3_cheat_starting_resources`, which remains useful when a reproducible bonus should be applied automatically at map start.

Terminal result cheats also target the issuing player and do not require a selected unit:

```
win
lose
```

Both require `sv_cheats 1`. They intentionally use the same authoritative player-removal/result transition as JASS `RemovePlayer`: `win` records `PLAYER_GAME_RESULT_VICTORY` and publishes `EVENT_PLAYER_VICTORY`, while `lose` records `PLAYER_GAME_RESULT_DEFEAT` and publishes `EVENT_PLAYER_DEFEAT`. Existing map result triggers, ending cinematics, pause-aware result-event draining, and the normal campaign/result dialog continuation therefore remain in control; the cheats do not directly switch maps or force a UI screen. Repeating either command after the player has already been removed is a no-op, matching `RemovePlayer` idempotence.

Campaign quest/script debugging uses several related command families, all gated by `sv_cheats 1`. Their diagnostic/result lines are written both to stderr and to the issuing player's in-game console, so `quest list`, `trigger list`, `objective list`, and `cinematic list` are usable without watching the launch terminal:

The server console can dispatch one of these game commands directly to a spawned listen-server client with `sv_gamecmd <client> <command> [args...]`. For example, `sv_gamecmd 0 objective complete 53`, `sv_gamecmd 0 debugspawn hfoo 5200 -4300`, `sv_gamecmd 0 select 42`, and `sv_gamecmd 0 smartpoint 5664 -4128` use the same authoritative client-command handlers as normal gameplay input. This is a diagnostics bridge only; the dispatched game command retains its own cheat and control checks. `sv_gamecmd 0 haltai 1` pauses think callbacks for non-player-owned WC3 units while leaving player-owned test units and world/pathing state active; use `sv_gamecmd 0 haltai 0` to restore AI. The setting is runtime-only and resets on process restart.

## Headless runtime-agent workflow

An agent can run a listen-server map without a window and still drive the authoritative game command path. Use the offscreen SDL backend and enable bounded diagnostics at launch:

```sh
DISPLAY=:99 SDL_VIDEODRIVER=offscreen build/bin/openwarcraft3 \
  -data 'data/Warcraft III' \
  +set sv_cheats 1 +set skip_cutscene 1 \
  +set wc3_bridge_probe 1 +set wc3_bridge_debug 4 \
  +map 'Maps/Campaign/Prologue02.w3m' +com_frame_limit 12000 \
  > /tmp/wc3-headless.log 2>&1 &
game_pid=$!
```

Wait until `/tmp/wc3-headless.log` contains both `G_ClientBegin` and `CL_SetGameplayInput`. The listen-server client is then client `0`. Inject commands into the running process's existing command buffer with a debugger or an equivalent process-control wrapper:

```gdb
call Cbuf_AddText("sv_gamecmd 0 objective complete 53")
call Cbuf_AddText("sv_gamecmd 0 haltai 1")
call Cbuf_AddText("sv_gamecmd 0 debugspawn hfoo 5200 -4300")
call Cbuf_AddText("sv_gamecmd 0 smartpoint 5664 -4128")
```

Use `sv_gamecmd 0 haltai 0` before testing ordinary campaign AI again. `haltai` pauses non-player-owned unit think callbacks; it does not remove units, alter their collision, clear pathing, or freeze the bridge support/animation system. A player-owned `hfoo` spawned by `debugspawn` therefore remains available as the test mover.

Collect evidence from stderr rather than screenshots:

```sh
rg 'WC3_BRIDGE_(STATE|PROBE|PROBE_SAMPLE|PROBE_CORNER|MOVE|ROUTE|SUPPORT|GROUND)' \
  /tmp/wc3-headless.log
```

The headless renderer does not prove visual deck traversal. A traversal claim requires committed position/support sequences in the log: approach, `support_hit=1` entry, movement through the bridge center, `support_hit=1` movement, and exit onto terrain. `mask=1` alone is insufficient.

For deterministic code coverage, use the dedicated test binary instead:

```sh
build/bin/openwarcraft3-tests -data 'data/Warcraft III' \
  +dedicated 1 +test 'wc3_pathfinding*'
```

Dedicated mode has no spawned listen-server client, so `sv_gamecmd` and client-targeted commands are unavailable there; use in-engine tests for pathing logic and the offscreen listen-server workflow for map/runtime evidence.

## Headless Debian agent sandbox

The following packages are sufficient for a Debian-based agent that builds OpenRealm, runs the offscreen SDL/OpenGL client, attaches a debugger, and extracts bounded bridge logs:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  build-essential make \
  libsdl2-dev libegl1-mesa-dev libgl-dev zlib1g-dev \
  libgl1-mesa-dri libegl1 gdb ripgrep procps
```

`build-essential` supplies the compiler and standard C build tools. `libsdl2-dev`, EGL/GL development packages, and `zlib1g-dev` match the Linux linker inputs used by the normal OpenRealm build. The Mesa runtime packages provide a software OpenGL implementation suitable for an unaccelerated sandbox. `gdb` is used to inject `sv_gamecmd` into an already-running listen server, `ripgrep` extracts probe markers, and `procps` supplies `pgrep`/`ps` for lifecycle checks.

No Debian package supplies the Warcraft III data. Mount or copy data from a legal Warcraft III installation and verify the files needed by this test:

```sh
for f in War3.mpq War3Local.mpq War3x.mpq War3xLocal.mpq; do
  test -r "data/Warcraft III/$f" || { echo "missing data/Warcraft III/$f" >&2; exit 1; }
done
```

Movie MPQs are not required for the bridge run unless the selected campaign intro cannot proceed without them. Lua, XML, MPQ, and JPEG support used by this build is vendored or in-tree; `liblua5.4-dev`, `libxml2-dev`, and StormLib are not prerequisites.

Build and test from the repository root:

```sh
make openwarcraft3
build/bin/openwarcraft3-tests -data 'data/Warcraft III' +dedicated 1 +test 'wc3_pathfinding*'
```

For the agent run, `SDL_VIDEODRIVER=offscreen` avoids requiring an X server or window manager. `DISPLAY=:99` is harmless but is not a substitute for an SDL video backend. Install `xvfb` only when a separate visual/X11 automation step is required; it is not needed for log-only bridge evidence:

```sh
SDL_VIDEODRIVER=offscreen build/bin/openwarcraft3 \
  -data 'data/Warcraft III' +set sv_cheats 1 +set skip_cutscene 1 \
  +set wc3_bridge_probe 1 +set wc3_bridge_debug 0 \
  +map 'Maps/Campaign/Prologue02.w3m' +com_frame_limit 12000 \
  > /tmp/wc3-headless.log 2>&1 &
game_pid=$!
```

The current command-dispatch workflow attaches `gdb` to this process and calls `Cbuf_AddText`. A Debian sandbox must permit `ptrace` between the agent and its child process; restrictive containers may need `--cap-add=SYS_PTRACE` and a compatible seccomp profile. Without debugger attach permission, use the normal console/UI path or provide an equivalent in-process command-buffer bridge.

For example, after waiting for `G_ClientBegin` and `CL_SetGameplayInput`:

```sh
gdb -q -batch -p "$game_pid" \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 objective complete 53")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 haltai 1")' \
  -ex detach -ex quit
```

If `libgl-dev` is unavailable on an older Debian image, use `libgl1-mesa-dev` in its place. If the sandbox has no usable software GL despite the Mesa packages, the deterministic dedicated tests can still run, but a runtime traversal session requires a working SDL video/GL backend.

For JASS group-lifetime diagnostics, `wc3_group_debug 1` records each live group's creator, nested JASS call path, and trigger ordinal in a non-persistent growable side table. The group registry itself grows past the old 1024-handle ceiling and prints `WC3_GROUP_DEBUG grow ...` at each pointer-table expansion; if allocation genuinely fails, the engine prints grouped `WC3_GROUP_DEBUG chain` summaries with live/allocated/freed/outstanding counts. Use these to find pathological retention without adding map-specific cleanup rules.

With `wc3_quest_debug 1`, on-screen tutorial/message presentation also emits `WC3_TUTORIAL_TEXT` lines. `DisplayTextToPlayer`, both timed text natives, and `SetCinematicScene` include the active trigger ordinal, JASS caller, target player, raw `TRIGSTR_*` token, resolved text, and timing/position fields; `EndCinematicScene` logs the matching clear. Use this to distinguish a tutorial trigger that never emits its next instruction from text that was authored correctly but failed in presentation.

For the Prologue02 Burrow-to-lumber handoff, the same cvar also emits `WC3_TUTORIAL_FLOW` lines for trigger ordinals 120-165 and startup-only `WC3_TUTORIAL_SOURCE` blocks for `Trig_W2_BurrowComplete_Q`, its generated pre/post-wait helper predicates, the Burrow work-complete/check paths, the abort path, the later War Mill tutorial trigger, and any `gg_trg_*` triggers referenced by the Burrow action body. The source dump also discovers whichever authored functions reference narrator sounds `T02Narrator031` through `T02Narrator035`, covering the lumber-harvest and War Mill construction instructions without assuming their trigger names. The flow trace records definitions, registrations, enable/disable changes, direct evaluate/execute calls, JASS sleep/wait durations, `GetTriggeringTrigger` context reads, and `IsTriggerEnabled` results. `WC3_TUTORIAL_COROUTINE` additionally reports when one of those trigger coroutines becomes eligible to resume and whether that resume yields again or finishes. Runtime traces have confirmed that `WaitForSoundBJ` resumes normally for trigger 150 and reaches its queue-removal tail; the wider range is intended to identify the missing authored lumber-stage enqueue/event rather than diagnose coroutine wakeup.

```
quest list
quest complete <index>
quest complete all

trigger list [case-sensitive-function-filter]
trigger fire <index>
trigger fire <index> selected

objective list [case-sensitive-function-filter]
objective complete <trigger-index>
objective complete <trigger-index> selected

jass <zero-argument-function-name>

cinematic list [case-sensitive-function-filter]
cinematic play <trigger-index>
cinematic play <trigger-index> selected
cinematic stop
```

`quest list` prints the allocated quests in the same 0-based in-use order used by the existing `quest <index>` journal command. `quest complete` marks the chosen quest and every allocated objective item completed; `all` applies that state change to every allocated quest. This is intentionally a **quest-state/UI cheat only**: it does not execute map-authored completion actions, does not fire a synthetic quest-completed event, and does not alter `failed`, `discovered`, `enabled`, or `required`. Campaign scripts usually advance because their own gameplay trigger runs, not because `QuestSetCompleted` changed a journal flag.

`trigger list` prints the stable `level.triggers[]` index, enabled/disabled state, and registered condition/action function names. The optional filter matches those JASS function names. `trigger fire` deliberately behaves like direct `TriggerExecute`: it executes the trigger's registered actions as coroutines without evaluating its conditions and even when the trigger is disabled. This makes it suitable for invoking campaign completion/action triggers that normal progression has not armed yet. Without `selected`, event-response unit/player context is empty. With `selected`, the current primary selected unit is supplied as the trigger unit, which also derives `GetTriggerPlayer()` from that unit's owner. Event fields that require a distinct source unit (for example `GetKillingUnit`) remain unset.

`objective` is a convenience layer for the common campaign case where the map has a completion/victory trigger that performs the real progression work. `objective list` scans trigger **action** names for likely completion triggers. It accepts ordinary `Victory_*` actions and quest/objective names containing completion words such as `Complete`, `Finish`, or `Done`, while rejecting obvious `Cheat`, `Defeat`, cinematic, skip, intro/outro, and time-stop helpers. For the Prologue map observed during development this keeps `Trig_Victory_Found_Medivh_Actions` while rejecting `Trig_Victory_Cheat_Actions`, `Trig_Defeat_Thrall_Dies_Actions`, and `Trig_End_Cinematic_Actions`. `objective complete <trigger-index> [selected]` executes the chosen trigger through the same direct TriggerExecute-style path as `trigger fire`; the index is the stable trigger index printed by the list, not a separate objective ordinal. This remains heuristic discovery, so `trigger list [filter]` is the fallback for unusually named progression triggers.

`jass` starts a named map JASS function as a coroutine, so normal trigger sleeps/waits can yield and resume. It is intended for generated zero-argument functions such as `Trig_*_Actions`; calling functions that require arguments is unsupported. Unlike `trigger fire ... selected`, this command does not manufacture event-response context.

`cinematic` is a higher-level wrapper for in-map scripted cutscenes. `cinematic list` now classifies only trigger **action** names with strong cutscene markers (`cinematic`, `cutscene`, `intro`, `outro`, `ending`, `interlude`) and rejects obvious helper names containing `skip`, `time_stop`/`timestop`, or `cheat`. Generic `victory` and `defeat` markers are intentionally not cinematic evidence: they commonly describe ordinary progression/result triggers. This avoids the observed false positives `Trig_Intro_Cinematic_Skip_Actions`, `Trig_Intro_Time_Stop_Actions`, `Trig_Victory_Cheat_Actions`, `Trig_Defeat_Cheat_Actions`, `Trig_Victory_Found_Medivh_Actions`, and `Trig_Defeat_Thrall_Dies_Actions`, while retaining `Trig_Intro_Cinematic_Actions` and `Trig_End_Cinematic_Actions`. The optional filter further restricts the surviving candidates by JASS function name. Discovery is intentionally heuristic: a map may name a cinematic trigger without any of those words, so a failed candidate search must fall back to `trigger list [filter]` rather than assuming the map contains no cutscene.

`cinematic play <trigger-index> [selected]` uses the same direct TriggerExecute-style path as `trigger fire`: it runs the map-authored trigger actions even if the trigger is disabled and without evaluating its conditions. The index does not have to be one reported by `cinematic list`, which makes `trigger list` a reliable manual fallback. The optional `selected` context has the same GetTriggerUnit/GetTriggerPlayer behavior and limitations as `trigger fire selected`.

`cinematic stop` intentionally does **not** force camera/UI/control state back to gameplay. It publishes the normal `EVENT_PLAYER_END_CINEMATIC` event for the issuing player and other human map players, matching the existing Escape/cancel route. The map's authored skip trigger therefore owns its skip flag, camera reset, unit cleanup, user-control restoration, and termination of the main cinematic coroutine. If a map does not register an end-cinematic handler, the command cannot safely invent that cleanup.

These commands play **in-map JASS cinematics**, not prerendered `PlayCinematic` movie files. Movie decoding/playback remains a separate subsystem.

For campaign skipping, prefer `objective list` followed by `objective complete <trigger-index>` when it finds the relevant authored completion trigger; otherwise use `trigger list <part-of-name>` followed by `trigger fire <index>`. Both execute the map's authored actions so dialogue, spawning, trigger enable/disable changes, quest updates, and later mission state can advance together. For cutscenes, `cinematic list`/`cinematic play` provide the same execution path with narrower cutscene discovery and an authored `cinematic stop` escape route. `quest complete` remains useful when testing only the journal/UI state.

Instant build is an issuing-player cheat and requires `sv_cheats 1`:

```
instantbuild          # toggle
instantbuild on
instantbuild off
warpten               # Warcraft-style alias; same toggle
```

When enabled, structures owned by that player complete on the next construction work tick and ordinary trained units complete on the next producer tick. The cheat deliberately preserves the normal command path: the worker still travels to a valid site, placement and resource/food checks still run, the structure/unit is still created through the ordinary queue, and normal completion events, UI invalidation, sounds, rally orders, and exit-placement checks remain authoritative. Turning the cheat on also affects construction/training already in progress on their next tick. A blocked producer exit still keeps a completed trained unit queued until a legal exit position exists. Research and Hero revival timers are not changed by this command.

The state is per player rather than global, so enabling it for a human player does not accelerate computer opponents. Like the other runtime cheats it stays active until explicitly toggled off or the player state is replaced by a fresh map/client lifecycle.

Time-of-day phase cheats set the authoritative Warcraft clock directly and require `sv_cheats 1`:

```
day
night
```

The commands use the active map's authored `Dawn`, `Dusk`, and `DayHours` values and choose the midpoint of the requested phase. Stock Warcraft values therefore produce 12:00 for `day` and 00:00 for `night`, while maps that override their day/night thresholds still land inside their own authored phase. The write goes through `G_SetTimeOfDay()`, so HUD clock state, DNC lighting, sight/regeneration rules, and time-of-day trigger conditions consume the same authoritative change. Explicit time sets still apply while ordinary time-of-day progression is suspended.

For accelerated environment testing, `wc3_cheat_timeofday_scale` multiplies only ordinary Warcraft III day/night progression. `1` is normal speed; for example `set wc3_cheat_timeofday_scale 20` runs the clock at 20x while simulation movement, AI, timers, trigger sleeps, and cinematics retain normal timing. `SuspendTimeOfDay(true)` still freezes ordinary progression, explicit JASS/cheat time sets remain exact, and invalid/non-positive values fall back to 1x. This CVar does not require `sv_cheats`.

Unit-oriented commands target the first selected unit:

```
give item <rawcode>
give ability <rawcode>
give xp <amount>       # hero only
god                    # toggle selected player unit invulnerability
kill                   # kill the player unit
```

`give item` uses the normal item spawn and pickup path, so inventory capacity and passive item effects remain authoritative. `research <rawcode>` remains available for the existing non-cheat research/debug path.

## World of Warcraft

Commands target the player:

```
give all
give health [amount]
give mana [amount]
give gold <amount>      # copper
give xp <amount>
god                     # toggle player invulnerability
kill
```

WoW’s current prototype action bar is class-authored rather than a learned-spell container, so `give spell` and item creation by database entry are intentionally not claimed yet. They should be added only when the server has a real spell-known/item-entry model to mutate.

## Console ownership

The client owns the console/menu input destination. A `CLIENT_UI_GAME` player-state update must not overwrite `key_console` or `key_menu`; otherwise the console opens for one frame and is immediately hidden by the next server snapshot.
