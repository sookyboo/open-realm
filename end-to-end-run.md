# LT05 bridge end-to-end run

This is the repeatable headless procedure for observing LT05 traversal in
`Maps/Campaign/Prologue02.w3m`. It is intentionally disposable: start a fresh
process for every hypothesis so route caches, unit positions, animation state,
and cinematic state do not carry over.

During the current runtime investigation, do not run the automated test suite
between these runs; build the game binary if needed and use the end-to-end
runtime evidence only.

## Launch

From the repository root, run:

```sh
SDL_VIDEODRIVER=offscreen build/bin/openwarcraft3 \
  -data 'data/Warcraft III' \
  +set sv_cheats 1 \
  +set skip_cutscene 1 \
  +set wc3_bridge_probe 1 \
  +set wc3_bridge_debug 1 \
  +set wc3_quest_debug 1 \
  +cameraedge 0 \
  +map 'Maps/Campaign/Prologue02.w3m' \
  +com_frame_limit 7000
```

Use a persistent terminal session. Wait for both `G_ClientBegin` and
`CL_SetGameplayInput` before injecting commands. The bridge is LT05, centered
approximately at `(5440,-4224,198)`.

## Injecting commands

Find the running process:

```sh
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
```

Inject commands with GDB. The newline inside `Cbuf_AddText` must be a real
command terminator:

```sh
gdb -q -batch -p "$pid" \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 objective complete 53\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 haltai 1\n")' \
  -ex detach -ex quit
```

Wait several seconds after objective 53. With cinematics skipped there is
still a delay while the cinematic presentation clears and the objective/bridge
state becomes effective. Confirm the log contains trigger 53 completion and
`WC3_BRIDGE_STATE phase=restored_birth` before testing movement.

## Unit setup

The order is important because each `debugspawn` selects the newly created
unit:

1. Spawn the destination Peasant first.
2. Spawn the crossing Footman second, so it remains selected for the camera
   and screenshots.
3. Run `bridgeclear 768` while the Footman is selected. This removes nearby
   enemy units around the selected unit; it does not remove friendly units.
4. Run `haltai 1` after the Footman is selected. This pauses unselected unit
   AI, including player-0 campaign units, while preserving the selected
   Footman's explicit debug order.

```sh
gdb -q -batch -p "$pid" \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 debugspawn hpea 6080 -3584\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 debugspawn hfoo 4800 -4864\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 bridgeclear 768\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 haltai 1\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' \
  -ex 'call Cbuf_AddText("screenshot 5\n")' \
  -ex detach -ex quit
```

Do not assume edict numbers. Read `WC3_BRIDGE_DEBUGSPAWN` and use the Footman
edict printed there for the movement command. The Peasant is only a visible
destination reference and must not be used as the crossing unit.

## Movement and screenshots

Issue one explicit order to the Footman:

```sh
gdb -q -batch -p "$pid" \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 bridgeorder <footman_edict> 6080 -3584\n")' \
  -ex detach -ex quit
```

Recenter the camera on the selected Footman immediately before every
screenshot. Take the first post-order screenshot after roughly two seconds,
then take additional screenshots after roughly five and eight seconds:

```sh
sleep 2
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' -ex 'call Cbuf_AddText("screenshot 5\n")' -ex detach -ex quit
sleep 3
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' -ex 'call Cbuf_AddText("screenshot 5\n")' -ex detach -ex quit
sleep 3
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' -ex 'call Cbuf_AddText("screenshot 5\n")' -ex detach -ex quit
```

The engine should report `Wrote screenshots/shotNNNN.jpg`. Label the baseline
before movement and every post-order frame with its elapsed time. If the unit
stalls or the camera/world looks unexpected, take the next screenshot without
issuing another movement command, then stop the process and document the
state.

## Evidence to collect

For the Footman, correlate screenshots with these gated diagnostics:

```text
WC3_BRIDGE_DEBUGORDER
WC3_BRIDGE_MOVE_STATE
WC3_BRIDGE_ROUTE_STATE
WC3_BRIDGE_PROBE
WC3_BRIDGE_TRAVERSE_COMMIT
```

The move-state record distinguishes an unaccepted order from a route that is
pending or unreachable. A traversal is only proven by a complete trajectory
from side A through the bridge center to side B with `support_hit=1` and
support heights on the actual rendered deck. `mask=1` alone is not proof.

After the run, stop the disposable process:

```sh
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
test -z "$pid" || kill -9 "$pid"
```

Record the exact screenshot names, Footman edict, coordinates, bridge state,
earliest failure layer, and representative log lines in `objective.md`.
