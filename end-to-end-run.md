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

The order is important. `debugspawn` may select the newly created unit, but
the run must explicitly select the recorded Footman edict before camera or
movement commands:

1. Spawn the destination Peasant first.
2. Spawn the crossing Footman second and record its `WC3_BRIDGE_DEBUGSPAWN
   unit=<N>` edict number.
3. Run `select <N>` and verify that the same Footman edict is selected.
4. Run `bridgeclear 768` while the Footman is explicitly selected. This removes nearby
   enemy units around the selected unit; it does not remove friendly units.
5. Run `haltai 1` after the Footman is explicitly selected. This pauses unselected unit
   AI, including player-0 campaign units, while preserving the selected
   Footman's explicit debug order.

```sh
gdb -q -batch -p "$pid" \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 debugspawn hpea 6080 -3584\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 debugspawn hfoo 4800 -4864\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 select <footman_edict>\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 bridgeclear 768\n")' \
  -ex 'call Cbuf_AddText("sv_gamecmd 0 haltai 1\n")' \
  -ex detach -ex quit
```

Wait at least one second after `cameraselected` before taking the screenshot;
the command updates the authoritative camera and the client needs a rendered
frame to receive/apply it. For the baseline, issue `cameraselected` separately,
wait one second, then issue `screenshot 5`.

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
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' -ex detach -ex quit
sleep 1
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("screenshot 5\n")' -ex detach -ex quit
sleep 3
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' -ex detach -ex quit
sleep 1
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("screenshot 5\n")' -ex detach -ex quit
sleep 3
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("sv_gamecmd 0 cameraselected\n")' -ex detach -ex quit
sleep 1
pid=$(ps -eo pid=,comm= | awk '$2 == "openwarcraft3" {print $1; exit}')
gdb -q -batch -p "$pid" -ex 'call Cbuf_AddText("screenshot 5\n")' -ex detach -ex quit
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

## Recorded thin-edge run: 0 degrees

The successful 0-degree thin-edge run used the normal launch above with these
additional arguments:

```text
+set wc3_bridge_clear_alive_pathtex 3
+set wc3_bridge_synthetic_line_angle 0
```

After `CL_SetGameplayInput`, it injected `cameraedge 0`, then injected
`objective complete 53` and `haltai 1`. After
`WC3_BRIDGE_STATE phase=restored_birth`, it spawned `hpea 6080 -3584` first
and `hfoo 4800 -4864` second, parsed the Footman edict from
`WC3_BRIDGE_DEBUGSPAWN`, and issued `select <footman_edict>`,
`bridgeclear 768`, and `haltai 1`. It then issued `cameraselected`, waited one
second, and captured the baseline. The only movement command was
`bridgeorder <footman_edict> 6080 -3584`. At approximately 2, 5, and 8 seconds
after ordering, it repeated `cameraselected`, waited one second, and captured
one screenshot.

The one-second camera wait is required: `WC3_CAMERA_SELECTED` is a server-side
marker, while the client applies the camera update on a later rendered frame.
