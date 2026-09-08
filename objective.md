# Current Objective

Investigate and fix LT05 bridge traversal in `Maps\Campaign\Prologue02.w3m`.

## Current state

- The bridge is confirmed dead before objective 53: the runtime log records `WC3_BRIDGE phase=dead`.
- After `objective complete 53`, the runtime log records `WC3: completing objective via trigger 53 directly` and `WC3_BRIDGE phase=restored_birth`; this is the restored/alive pathing state.
- The alive bridge path texture is applied and the static pathing bake is rerun, but no run has yet proven a normal ground unit crossing the rendered bridge deck from one side to the other.
- Existing route attempts fail during waypoint generation. Treat `mask=1` or an `inside=1` ground-height sample as insufficient traversal proof unless the diagnostic also proves LT05 support selection and a complete side-A-to-side-B trajectory.
- A screenshot test using a created and selected unit and the added camera commands appeared to remain in a cinematic. With cinematics skipped, there may still be a delay of several seconds between completing objective 53, clearing the cinematic state, and the objective becoming fully effective. Wait for and log those transitions before judging the camera or bridge.
- The latest headless run created Footman edict 319 at `(4800,-4864)`, selected it, centered the camera near `(5440,-4224)`, and ordered it toward `(6080,-3584)`. `WC3_CAMERA_SELECTED` and `WC3_BRIDGE_DEBUGORDER` were emitted, but the screenshot showed the selected-unit HUD over a black world and is not traversal proof. The broad probe output was saturated by campaign units, so this run is inconclusive for edict 319.

## Unexpected command/test results

- Camera-edge scrolling was **not disabled** in the latest run. The launch command omitted `cameraedge 0`; therefore edge-scroll input was not isolated from the camera-command test. Add `+cameraedge 0` after initialization, or inject `cameraedge 0` before positioning the camera, and verify the cvar/command response in the log.
- The first GDB injection used a literal backslash-n and produced `WC3: objective complete requires a non-negative trigger index`; the command reached the handler with a malformed numeric token. In GDB, use a real newline escape (`Cbuf_AddText("... 53\\n")`) and terminate every injected command. The corrected injection emitted `completing objective via trigger 53` and `haltai=1`.
- `debugspawn hfoo 4800 -4864`, `bridgecamera 5440 -4224`, `cameraselected`, and `smartpoint 6080 -3584` worked and emitted the expected spawn/camera/order markers. `cameraselected` did not itself prove a visible bridge view.
- `screenshot 5` wrote a valid 1024x768 image and the screenshot workflow itself worked. The image contained the selected Footman HUD over a black world; record that as an unexpected visual result to investigate, but do not treat it as proof that the camera command failed or that a cinematic remained active.
- The first background launch exited before producing output because the shell-owned process did not persist. Use a persistent terminal session (or an equivalent `nohup`/session wrapper) and confirm `G_ClientBegin` plus `CL_SetGameplayInput` before injecting commands.
- The latest retry used `+cameraedge 0` successfully and confirmed the launch/client handshake. Footman 319 reached `(5157.3,-4504.8)` with `WC3_BRIDGE_SUPPORT hit=1 cached=1 support=403.6`, then stalled there while `WC3_BRIDGE_ROUTE_STATE` repeatedly reported `mode=direct path_valid=0`. Removing nearby units 321, 322, 341, and 343 in the disposable run did not yet produce a crossing. This proves valid LT05 support at the stall point, but not the cause of the remaining movement failure.
- The fresh end-to-end rerun produced `screenshots/shot0002.jpg` as the baseline before movement and `screenshots/shot0003.jpg` after the movement order. Both captures are valid; the baseline visibly shows the restored bridge deck and selected Footman, and the post-order capture visibly shows the bridge/deck area with units on or near it. These screenshots establish that camera positioning and capture work, but do not by themselves prove that Footman 319 completed a side-to-side crossing.
- Added the diagnostic command `bridgeclear [radius]`. It requires `sv_cheats 1`, uses the primary selected friendly unit as its center, and immediately deletes nearby non-building enemy units; the default radius is 768 world units. Use `sv_gamecmd 0 bridgeclear 768` after selecting the probe Footman and before the baseline screenshot/order. This is needed because `haltai` does not stop player-owned campaign units, which can remain near LT05 and interfere with collision/traversal evidence. The command does not delete the selected unit or modify bridge pathing.
- Fresh end-to-end run after the command was added: objective 53 completed, post-objective presentation was allowed to settle, `debugspawn hfoo 4800 -4864` created/selected Footman 319, and `bridgeclear 768` removed enemy Footmen 322 and 343. Baseline `screenshots/shot0004.jpg` was captured before movement; `bridgeorder 319 6080 -3584` was then issued and stall capture `screenshots/shot0005.jpg` was taken. Footman 319 still stalled at `(5497.8,-4454.3)` while candidates toward `(5509.9,-4430.2)` were rejected with `baked=0x02`, `mask=0`, `source=(9,13)`, and `source_nowalk=1`. This rules out nearby enemy units as the cause for this attempt; it remains a point/pathing rejection before complete crossing.
- Fix applied in `games/warcraft-3/common/routing.c`: alive walkable-destructable cells are now filtered through the existing rendered MDX support-height resolver during static baking. Previously every clear alive path-texture pixel became a route/support cell even when the rendered deck had no support there (`mask=1`, `support_hit=0`), which sent the mover off-deck and into a rail. The filter keeps authored blocked pixels and terrain restrictions intact; it only removes clear pixels lacking actual rendered support. `baked_open` changed from 856 to 689 on LT05 in the runtime verification.
- Added `wc3_collision.walkable_surface_query_filters_unsupported_alive_cells`, which verifies unsupported alive cells remain blocked while supported cells remain routable. Targeted run passed `4/4 assertions`.
- Post-fix runtime verification restored LT05 and produced support-backed movement for Footman 319 (`from_support_hit=1`, `to_support_hit=1`, support heights around 456), but it did not prove a complete side-to-side crossing: remaining friendly campaign units still occupied/oscillated on the bridge after enemy cleanup. Do not mark traversal complete until a fresh run isolates those friendly units or otherwise proves `ENTER -> center -> EXIT` for the probe unit.
- Latest fresh end-to-end rerun: after objective 53 and cinematic settling, `bridgeclear 768` removed nearby enemy units, `shot0006.jpg` was captured before `bridgeorder 319 6080 -3584`, and `shot0007.jpg` was captured at the movement stall. LT05 was restored with `origin=(5440,-4224,198.4)`, `angle=0`, and `pathtex=32x32`; the probe unit still did not complete side-A to side-B traversal. Focused output showed support-backed movement on LT05, while friendly campaign units 321 and 341 remained on/near the deck and oscillated. This run is therefore evidence that the screenshot protocol works and that enemy cleanup alone is insufficient, not evidence that the bridge crossing is fixed.
- Added gated move-state diagnostics in `games/warcraft-3/game/g_ai.c`, `games/warcraft-3/game/skills/s_move.c`, and `games/warcraft-3/game/g_local.h`. `WC3_BRIDGE_MOVE_STATE` now records the active move animation/ability, goal, position/Z, distance, route flags, and blocked-frame count when a unit is in the LT05 probe area; `bridgeorder` also logs explicit order rejection. The diagnostic build completed with only the existing unrelated snprintf warnings.
- Latest run used Footman 319 at `(4800,-4864)` and Peasant 320 at `(6080,-3584)` as the destination reference. `shot0008.jpg` is the pre-order view; `shot0009.jpg`, `shot0010.jpg`, and `shot0011.jpg` are successive observation frames. The Footman did move, reaching `(5497.8,-4454.3)`, then stopped visibly. The state log at the stall retained `goal=1`, `currentmove=walk`, `ability=move`, `flow_direct=0`, `path_valid=0`, `flow_generation=13`, `flow_unreachable=0`, and increasing `blocked_frames`; therefore the order was accepted and the behavior continued ticking, but no valid flow heading was available. This is the current earliest confirmed failure layer: route/steering resolution after entering the bridge approach, not command submission or screenshot timing.

## Screenshot and rerun protocol

- Take a baseline screenshot after `objective complete 53`, cinematic cleanup, `cameraedge 0`, camera positioning, and unit selection, but before issuing any movement command.
- If the unit stalls or any unexpected camera/world result occurs, immediately take a second screenshot while preserving the exact same simulation state, then collect the focused logs.
- Do not issue another movement command in the same contaminated run. Start a fresh process for the next hypothesis so route caches, unit positions, animation frames, and cinematic state cannot carry over.
- Label captures in the session notes as `baseline-before-move` and `stall-after-move`; the screenshot mechanism is considered working when the engine reports `Wrote screenshots/shotNNNN.jpg`.
- The latest capture labels are `shot0006.jpg` = `baseline-before-move` and `shot0007.jpg` = `stall-after-move`.
- Additional capture labels: `shot0008.jpg` = `baseline-before-move` with the Peasant destination reference, `shot0009.jpg` = approximately two seconds after ordering, `shot0010.jpg` = approximately five seconds after ordering, and `shot0011.jpg` = approximately eight seconds after ordering.
- Corrected setup run: spawned the target Peasant first at `(6080,-3584)`, spawned the crossing Footman second at `(4800,-4864)`, then ran `bridgeclear 768` while the Footman was selected and ran `haltai 1` after the Footman was selected. The Footman therefore remained selected for the camera and screenshots. `bridgeclear` was executed in this run and its prior behavior remains enemy-only; `haltai` now pauses all unselected units, including player-0 campaign units, while preserving the selected probe's explicit order. The Footman advanced to approximately `(5492,-4450)` and still stalled with `currentmove=walk`, `goal=1`, `flow_direct=0`, `path_valid=0`, `flow_generation=13`, `flow_unreachable=0`, and increasing `blocked_frames`; this rules out the previous crowd/selection confounder.
- Corrected-run screenshots: `shot0012.jpg` is the baseline with the Footman selected and the Peasant at the destination; `shot0013.jpg`, `shot0014.jpg`, and `shot0015.jpg` are successive post-order observation frames. The process was stopped after the final capture; no complete crossing was observed.
- Simplified ordinary-bridge baseline: temporarily removed LT05-specific MDX support filtering from alive-cell baking and removed the LT05 centre/radius exceptions from normal point and radius-expanded pathability. Clear alive pathing cells now open like a regular walkable bridge; authored blocked pixels and normal support-height/Z handling remain. Tests were intentionally skipped during this runtime iteration. The fresh run reported `baked_open=856` (previously 689), but Footman 320 still stalled earlier at approximately `(5405,-4454)` with an active move order, `flow_direct=0`, `path_valid=0`, `flow_generation=13`, `flow_unreachable=0`, and increasing `blocked_frames`. This disproves the support filter as the sole cause and does not prove a crossing.
- Simplified-baseline screenshots: `shot0016.jpg` is the baseline before movement; `shot0017.jpg`, `shot0018.jpg`, `shot0019.jpg`, and `shot0020.jpg` are successive post-order observation frames. The disposable process was stopped after capture.
- Restored the two radius allowances from the known-crossing `c263c776` baseline in `games/warcraft-3/common/routing.c`: a bridge-lane centre bypass for world-space radius samples, and acceptance of a radius-expanded bridge centre when only surrounding rail cells are blocked. No other simplified bridge behavior was restored, and automated tests were skipped.
- Fresh controlled run with those allowances: LT05 restored, Peasant spawned first, Footman 320 spawned second and remained selected, `bridgeclear 768` and `haltai 1` executed, then one order toward the Peasant was issued. The Footman advanced onto the supported deck to approximately `(5469.8,-4454.8)` with Z/support around `456`, but stalled before side B with `flow_direct=0`, `path_valid=0`, `flow_generation=15`, `flow_unreachable=0`, and increasing `blocked_frames`. This partial progress is not a complete crossing. Captures: `shot0021.jpg` baseline, `shot0022.jpg` first post-order, `shot0023.jpg` second post-order, `shot0024.jpg` final post-order.
- Camera-centered rerun: `cameraselected` was issued after the Footman was selected and again immediately before each screenshot, so the baseline and observation frames are centered on the Footman rather than only on the bridge origin. The Footman still stalled at approximately `(5468,-4454)` with support/Z around `456` and `flow_generation=15`; no crossing was proven. Captures: `shot0025.jpg` baseline, `shot0026.jpg`, `shot0027.jpg`, and `shot0028.jpg` successive post-order frames.
- Temporary open-bridge baseline: all `walkable=1` destructables now open their complete pathing footprint in both dead and alive states, skip authored bridge pathing blockers, and continue to provide support height for Z. This removes lifecycle/path-texture/rail blockers for the first crossing proof; it is intentionally not the final gameplay behavior. In the fresh end-to-end run, LT05 baked `1024` open cells, Footman 320 remained selected, and the unit moved continuously from `(4800,-4864)` across the bridge region to the Peasant target near `(6080,-3584)` without the previous route stall. The observed log had `flow_direct=1`, `flow_unreachable=0`, and no increasing blocked-frame stall through the crossing. Captures: `shot0029.jpg` baseline, `shot0030.jpg`, `shot0031.jpg`, and `shot0032.jpg` successive centered observation frames. This is the first successful simplified side-A-to-side-B runtime traversal baseline; automated tests were skipped.
- Alive-only bridge pass: changed the temporary baseline so only alive `walkable=1` destructables open the bridge footprint and bypass authored bridge blockers. Dead walkable destructables now retain their death path texture in the static path bake, and dead walkable destructables do not provide ground support in `M_CheckGround()`. A fresh run completed `objective complete 53`, logged LT05 as `dead=0` in `restored_birth`, and reported `source_blocked=168`, `terrain_open=857`, `baked_open=1024`. The selected Footman moved from `(4800,-4864)` through the LT05 region toward `(6080,-3584)`, reaching `(6068.7,-3606.9)` with `blocked_frames=0`, `flow_direct=1`, and `flow_unreachable=0`; this reproduces the successful alive traversal under the alive-only rule. Captures: `shot0033.jpg` baseline, `shot0034.jpg`, `shot0035.jpg`, and `shot0036.jpg` centered observation frames. Automated tests were skipped. A separate clean pre-objective runtime is still required to record dead-state movement rejection, so this run does not claim that evidence.
- Dead-state verification after the alive-only change: a fresh map-load log recorded LT05 as `dead=1`, `anim=Death`, with `pathtex=34x34`; the dead bake reported `source_blocked=652` and only `baked_open=312`. A movement probe near the bridge returned `mask=0`, `point_final=0` for blocked candidates, and `flow_direct=0` with the order remaining active but stationary. This confirms the dead bridge is not opened by the temporary alive bridge rule. The setup command selected newly spawned Footman 337, but the injected order addressed pre-existing edict 319 (a Peasant), so this is pathing evidence rather than a valid selected-Footman screenshot run; the next dead-state run should use the emitted spawn edict. `shot0037.jpg` is the baseline capture. Automated tests were skipped.
- Constraint 4 progress: restored alive authored path-texture stamping in `stamp_entity_obstacle()`. LT05 now opens the clear alive cells and reapplies its `168` authored blocked pixels, producing `baked_open=856` rather than `1024`. The fresh alive run still allowed bridge-region movement with support-backed commits and moved the newly spawned Footman toward the far-side target; no authored-blocker regression was observed in this run. `shot0038.jpg` is the centered baseline capture. Rail-specific rejection and reverse traversal remain to be verified; automated tests were skipped.
- End-to-end run with authored alive blockers enabled: launched with `+cameraedge 0`, completed `objective complete 53`, waited for the restored `Birth` state, spawned the Peasant first at `(6080,-3584)` and Footman second at `(4800,-4864)`, ran `bridgeclear 768` and `haltai 1`, then centered on the selected Footman before each capture. LT05 logged `source_blocked=168`, `terrain_open=857`, and `baked_open=856`. The run is inconclusive: movement logs for Footman edict 323 reached approximately `(6008.7,-3521.1)`, but visual comparison of `shot0039.jpg` and `shot0042.jpg` shows the selected Footman stayed in essentially the same position. The command/selection identity was not correlated correctly, so this run does not prove crossing or that authored blockers preserve it. Automated tests were skipped.
- Corrected-identity rerun: the fresh process again restored LT05 with `source_blocked=168` and `baked_open=856`, then used the same Peasant-first/Footman-second setup and centered the camera before each screenshot. Visual comparison of `shot0043.jpg` and `shot0045.jpg` again shows the selected Footman stationary, while movement diagnostics continued to report another unit moving. The “last spawned” selection assumption is therefore still invalid; this run is inconclusive and does not prove crossing. The next run must explicitly select and camera-track the exact edict passed to `bridgeorder`. Automated tests were skipped.
- Selection correction: confirmed the existing `select <edict>` cheat can explicitly replace the client selection and focus. Updated `end-to-end-run.md` to require `select <footman_edict>` after recording the Footman's `WC3_BRIDGE_DEBUGSPAWN` line, before `bridgeclear`, `cameraselected`, screenshots, and `bridgeorder`. This addresses the screenshot/log identity mismatch without changing gameplay selection code.
- Explicit-selection rerun: the run was still invalid because the manually supplied edict guesses were wrong: edict 323 selected a Captain, and edict 338 tracked a different unit. The screenshots `shot0049.jpg` through `shot0051.jpg` therefore do not show the commanded Footman crossing. The bridge bake and alive state were correct, but the `WC3_BRIDGE_DEBUGSPAWN` output was lost in saturated terminal output. The next diagnostic change should make the spawned Footman edict directly queryable or emit a bounded selection marker before any movement order; do not infer it from edict allocation order. Automated tests were skipped.
- Clean single-pair run with explicit edict identity: captured `WC3_BRIDGE_DEBUGSPAWN unit=319` for the Peasant and `unit=320` for the Footman, then explicitly selected edict 320 before `bridgeclear`, camera centering, screenshots, and `bridgeorder`. This time the screenshot and movement logs agree. The Footman visibly moved from the approach onto the bridge deck, but stalled at `(5497.8,-4454.3)` with `goal=1`, `flow_direct=0`, `flow_generation=13`, and increasing `blocked_frames`. This is valid evidence that restoring the authored alive blockers currently prevents a complete crossing at the lane/rail transition. Captures: `shot0052.jpg` baseline-before-move, `shot0053.jpg` intermediate movement, and `shot0054.jpg` stall observation. Automated tests were skipped.
- Synthetic alive path-texture diagnostic added: `wc3_bridge_clear_alive_pathtex 1` now replaces each alive walkable destructable's loaded alive TGA blocking channel with an all-clear in-memory texture of the same dimensions. The normal footprint opening and path-texture stamping pipeline still runs; the authored death TGA remains unchanged. This is temporary route isolation, disabled by default, and must be removed or replaced after the remaining layers are proven. Build succeeded with only the existing unrelated `snprintf` warnings; automated tests remain skipped.
- End-to-end synthetic-TGA run: launched with `+set wc3_bridge_clear_alive_pathtex 1`, completed objective 53, and verified `WC3_BRIDGE_PATHTEX mode=synthetic_clear unit=4244 size=32x32`. LT05 restored with `source_blocked=0`, `placed_blocked=0`, and `baked_open=1024`. The clean pair was Peasant edict 319 and Footman edict 320; edict 320 was explicitly selected and commanded. The screenshots now visibly track the same Footman from the approach onto and across LT05, while logs show movement through `(5703.7,-4236.7)` and to `(6067.8,-3605.1)`, with `flow_direct=1`, `flow_unreachable=0`, and `blocked_frames=0`. This proves the remaining route, radius, support, camera, and screenshot pipeline works when alive TGA blockers are falsified. Captures: `shot0055.jpg` baseline, `shot0056.jpg` intermediate, and `shot0057.jpg` far-side observation. Automated tests were skipped.
- Synthetic line diagnostic runs: mode `2` now generates a bounded 7-cell clear strip with blocked edges, and `wc3_bridge_synthetic_line_angle` selects 0° or 90°. The first diagonal implementation was corrected for the loader/stamper flip, then replaced with a world-X/world-Y strip based on LT05 support coordinates. Fresh angle-0 and angle-90 runs both moved the exact Footman edict 320 toward an off-deck route point near `(5697,-4786)` and did not produce the requested aligned-crosses/perpendicular-blocks distinction. The line’s placement or width still does not match the actual LT05 lane; these runs are diagnostic failures, not proof of either orientation. Automated tests were skipped.
- Added bounded level-3 footprint and movement diagnostics in `games/warcraft-3/common/routing.c` and retained them behind `wc3_bridge_debug`: the restored grid now marks baked walkable-surface cells as `S`, while `WC3_BRIDGE_POINT` records the transformed source pixel, source blocker value, terrain/baked flags, and surface-mask membership for rejected candidates. Fixed the logger’s uninitialized `min_x`/`min_y` setup and rebuilt successfully; only the existing unrelated `snprintf` warnings remain.
- Debug run `line_angle=0`: LT05 restored with `rotation=90`, `source_clear=224`, `source_axis=vertical`, `source_blocked=800`, and `baked_open=224`. The grid shows the synthetic support lane as a narrow vertical world strip. Footman 320 received the order and reached a real rendered support hit at `(5478.5,-4464.4)` (`support=455.3`), then steered to `(5542.3,-4435.6)`, where support was absent and the candidate point was rejected with `cell=(422,117)`, `baked=0x02`, `mask=0`, `source=(9,19)`, `source_b=255`. This proves the unit is leaving the synthetic lane before the stall; it is not a support-height failure.
- Debug run `line_angle=90`: LT05 restored with `rotation=90`, `source_clear=224`, `source_axis=horizontal`, `source_blocked=800`, and `baked_open=224`. The grid shows a horizontal world strip at rows 121–127. Footman 320 was redirected to the nearest reachable target `(5712,-4784)` and moved directly along the off-deck lower side, reaching `(5697.4,-4785.9)` without traversing LT05. The perpendicular case therefore also fails, but the two runs do not yet constitute the requested aligned/perpendicular proof because the chosen target/route does not force the unit through the bridge’s actual long axis.
- Changed the synthetic line generator to diagonal source patterns based on the successful all-clear trajectory: at angle 0 it emits the diagonal that should align with the observed side-A/side-B direction, and angle 90 emits the perpendicular diagonal. The first three-run harness had another setup error because it hard-coded edict 320; the line cases allocated the Footman as edict 4390, so those results were discarded. The retry harness now parses the Footman edict from `WC3_BRIDGE_DEBUGSPAWN` and uses that ID for selection and ordering.
- Corrected-identity rerun after the diagonal change: all-clear mode reached `(5927.8,-3932.8)` with `flow_direct=1`, no blocked frames, and continued toward the far-side Peasant. The aligned diagonal (`line_angle=0`) produced `source_clear=212`, `baked_open=212`, but the route selected nearest point `(5712,-4784)` outside LT05’s transformed footprint and stopped at `(5697.4,-4785.9)`; it therefore still does not prove aligned passage. The perpendicular diagonal (`line_angle=90`) also used `source_clear=212`, `baked_open=212`, and oscillated near `(5307,-4418)` with `flow_direct` alternating and `flow_generation=18`; rejected candidates included authored blocked cells with `baked=0x02`, `mask=0`, and `source_b=255`. Automated tests were skipped. The next change must widen/position the synthetic lane enough to satisfy a Footman-radius entrance while preserving blocked edges, or use exact deck-end targets derived from the transformed footprint.

## Final bridge constraints

The temporary alive-only crossing baseline must eventually satisfy all of these constraints:

1. Dead LT05 must block passage.
2. Alive LT05 must provide a continuous walkable lane from one entrance to the other.
3. Only valid deck cells may be opened over blocked terrain or water.
4. Authored rail and non-deck pathing cells must remain blocked.
5. Collision radius must still matter near bridge edges and rails.
6. Ordinary no-corner-cut rules must remain active except where the deck geometry proves a valid transition.
7. Ground units must receive bridge support height only while physically over the deck.
8. Units must not use bridge height when the bridge is dead, hidden, or unsupported.
9. Support-height changes must follow the rendered deck and animation state.
10. Bridge restoration must update routing immediately without a manual rebake.
11. Routes must enter the bridge, cross its center, and exit onto normal terrain.
12. The reverse direction must work as well.
13. Enemy and friendly units must not be mistaken for bridge pathing.
14. No model-name-specific gameplay exception should be required.
15. Debug logging must remain CVar-gated and disabled by default.
16. Runtime pathing must not rescan all entities or texture pixels every movement frame.
17. Tests must verify dead blocking, alive crossing, rails, collision radius, support selection, and restoration.

## Next session procedure

1. Launch the Debian headless sandbox with bridge probing enabled and cinematic/tutorial timing logs:
   `+set wc3_bridge_probe 1 +set wc3_bridge_debug 1 +set wc3_quest_debug 1 +cameraedge 0`.
2. Load `Maps\Campaign\Prologue02.w3m` and verify LT05 is dead before testing.
3. Run `objective complete 53`; verify the trigger, restored/alive bridge state, pathing bake, and cinematic-clearance/objective-completion timing in the log.
4. Inject `cameraedge 0`, then move the camera to approximately `(5440, -4224)` only after the restored/alive state is confirmed.
5. Determine LT05's actual bridge axis from its logged origin, angle, alive pathing dimensions, and transformed footprint. Choose deterministic opposite-side coordinates along that axis.
6. Halt campaign AI before creating/selecting one normal ground unit, position the camera, and take the baseline screenshot before issuing any movement order.
7. Issue a side-A-to-side-B order and capture movement diagnostics for that unit only. If it stalls, take the stall screenshot immediately, stop the run, and rerun from a fresh process with rejection-level logging enabled. Distinguish static path/radius rejection from `MOVE_COLLIDE_UNITS` or slide oscillation at the support point.
8. Require evidence of `ENTER -> MOVE through the bridge center -> EXIT`, including support hit/height and unit Z. Then repeat side B to side A in a separate clean run if necessary.
9. Identify the earliest failing layer: route connectivity, point/radius pathability, line/corner pathability, support selection, Z update, or stale cache invalidation.
10. Make the smallest evidence-based fix, add a deterministic regression test, and preserve dead-state blocking, alive authored blockers/rails, normal radius behavior, and no-corner-cut behavior.

## Evidence discipline

Do not claim that the radius exception is required, or that bridge crossing is fixed, without `support_hit=1` on the actual LT05 deck and a complete side-to-side trajectory. Keep exploratory logs gated or remove them after the root cause is established.

## Thin-edge orientation experiment

Before the next path-texture hypothesis, run four fresh end-to-end processes with `wc3_bridge_clear_alive_pathtex 3` and `wc3_bridge_synthetic_line_angle` set to `0`, `90`, `180`, and `270` degrees. Mode 3 clears every alive path-texture source row except `y=0`, leaving one thin blocked source edge while preserving the authored texture dimensions. Use the exact emitted Footman edict in each run, capture a baseline and timed post-order screenshots, and stop each process after the final observation or an immediate stall capture.

Record for every angle: `WC3_BRIDGE_PATHTEX`, `WC3_BRIDGE_SYNTH_EDGE`, LT05 bake counts, the Footman's `WC3_BRIDGE_MOVE_STATE`/`WC3_BRIDGE_ROUTE_STATE`, the first rejected or blocked transition, support hit/height, final position, and screenshot names. Compare the four angles for transformed edge orientation; do not treat a movement stall alone as proof that the source edge blocks the route unless the rejection is correlated with the edge and the unit has otherwise reached the deck transition.

The corrected 0-degree rerun used `+set wc3_bridge_clear_alive_pathtex 3`,
`+set wc3_bridge_synthetic_line_angle 0`, `+cameraedge 0`, and an explicit
post-handshake `cameraedge 0`. It waited one second after each
`cameraselected` command before capturing so the client could apply the
authoritative camera update. The Peasant was edict `337` and the Footman was
edict `4390`; edict `4390` was explicitly selected and commanded. LT05 logged
`source_clear=992`, `source_blocked=32`, `placed_blocked=32`, and
`baked_open=992`. The Footman moved from `(4800,-4864)` to `(6172.5,-3614.6)`
with `flow_direct=1`, support hits on the rendered deck, and
`blocked_frames=0`; the route reached the far-side destination region.
Captures were `shot0009.jpg` (baseline), `shot0010.jpg` (~2 seconds),
`shot0011.jpg` (~5 seconds), and `shot0012.jpg` (~8 seconds/far side). The
baseline and observation screenshots are valid camera-framed evidence. This
proves the 0-degree thin-edge run and camera protocol; the 90, 180, and 270
degree cases remain outstanding.

The mode-3 diagnostic was corrected before the next comparison: its angle now
rotates the synthetic blocked edge itself (`0=top`, `90=right`, `180=bottom`,
`270=left`) and rejects non-cardinal angles. The prior 90-degree attempt was
interrupted after the process had already produced a valid setup and partial
observations. It used `source_edge=right`, `source_blocked=32`,
`placed_blocked=32`, Footman edict `4392`, and screenshots `shot0017.jpg`
(baseline), `shot0018.jpg` (~2 seconds), and `shot0019.jpg` (~5 seconds). The
camera was correctly centered. The Footman reached `(5950.7,-3744.5)` before
the run was stopped, with `flow_direct=0`, `flow_generation=62`, and growing
`blocked_frames`; this is an interrupted/inconclusive 90-degree result, not a
confirmed edge block. The next run must be documented here before launch.

## Run checkpoint rule

Before every run, record the complete planned invocation and resume point in
this file: diagnostic mode and angle, launch flags, handshake wait, injected
commands, exact screenshot schedule, and the expected next command. Afterward,
record the actual Footman edict, bridge/bake state, captures, final position,
and earliest failure layer. If a session ends unexpectedly, leave the
checkpoint marked interrupted and start the next attempt from a fresh process.

The corrected 90-degree rerun used the same procedure with
`+set wc3_bridge_synthetic_line_angle 90`. The Peasant was edict `337` and the
Footman was edict `4390`; explicit selection and delayed camera centering were
verified. LT05 again logged `source_clear=992`, `source_blocked=32`,
`placed_blocked=32`, and `baked_open=992`. The Footman crossed to
`(6150.1,-3614.2)` with `flow_direct=1`, `blocked_frames=0`, and rendered-deck
support during the crossing. Captures were `shot0013.jpg` (baseline),
`shot0014.jpg` (~2 seconds), `shot0015.jpg` (~5 seconds), and
`shot0016.jpg` (~8 seconds/far side). The 90-degree transformed edge also did
not block the route; the 180 and 270 degree cases remain outstanding.

### Next run checkpoint: 180-degree thin edge

Planned hypothesis: mode 3 with the synthetic bottom source edge should reveal
whether that transformed edge blocks the LT05 route. Launch with
`+set wc3_bridge_clear_alive_pathtex 3`,
`+set wc3_bridge_synthetic_line_angle 180`, `+cameraedge 0`, and the standard
bridge/debug flags. After `CL_SetGameplayInput`, inject `cameraedge 0`, then
`objective complete 53` and `haltai 1`; wait for
`WC3_BRIDGE_STATE phase=restored_birth`. Spawn the Peasant first at
`(6080,-3584)` and the Footman second at `(4800,-4864)`, parse the Footman
edict, then issue `select <footman_edict>`, `bridgeclear 768`, and `haltai 1`.
Issue `cameraselected`, wait one second, and capture the baseline. Issue one
`bridgeorder <footman_edict> 6080 -3584`; capture at approximately 2, 5, and
8 seconds, issuing `cameraselected` and waiting one second before each capture.
If the process stalls, capture one same-state stall frame, stop it, and record
the actual state below. Expected next command after interruption: restart from
Launch with a new process; do not reuse route or unit state.

The 180-degree run used the checkpoint above and applied `source_edge=bottom`,
with `source_clear=992`, `source_blocked=32`, and `placed_blocked=32`. The exact
Footman was edict `4392`; selection, camera centering, and
`WC3_BRIDGE_DEBUGORDER` all identified that same unit. LT05 movement remained
`flow_direct=1` with `blocked_frames=0`; the Footman reached
`(6154.1,-3602.7)`, 6.5 units from the internally selected target
`(6160,-3600)`, so the bottom edge did not block traversal. Captures were
`shot0020.jpg` (baseline), `shot0021.jpg` (~2 seconds), and `shot0022.jpg`
(~5 seconds). The process/session ended before the final ~8-second capture
(`shot0023.jpg`) was written; this case is recorded as interrupted. The
270-degree case remains outstanding.

### Next run checkpoint: blocked center row

Planned hypothesis: a full-width blocked source row through the texture center
will act as a transverse barrier and reveal whether the route can cross a true
lane blocker. Add/use a dedicated synthetic mode that clears the alive texture
except for the center source row. Launch with the standard bridge/debug flags,
`+set wc3_bridge_clear_alive_pathtex 4`, and `+cameraedge 0`; after
`CL_SetGameplayInput`, inject `cameraedge 0`, then `objective complete 53` and
`haltai 1`, waiting for `WC3_BRIDGE_STATE phase=restored_birth`. Spawn the
Peasant first at `(6080,-3584)` and Footman second at `(4800,-4864)`, parse and
explicitly select the Footman edict, then run `bridgeclear 768` and `haltai 1`.
Center the camera, wait one second, and capture the baseline. Issue exactly one
`bridgeorder <footman_edict> 6080 -3584`; capture at approximately 2, 5, and
8 seconds with the one-second camera wait before each screenshot. If it stalls,
capture the same-state stall frame and record the first rejected transition.
Expected resume point after interruption: restart from Launch with a fresh
process; do not reuse route or unit state.

### Next run checkpoint: exact anti-diagonal TGA barrier

Planned hypothesis: use the exact pattern represented by
`screenshots/LT05_next_blocking_line.tga`—a 32×32 texture with 992 black clear
cells and 32 magenta blocked cells on `x+y=31`—as the alive LT05 diagnostic
texture. The runtime mode must preserve the same byte-level red blocking mask.
Launch a fresh process with `+set wc3_bridge_clear_alive_pathtex 5` and
`+cameraedge 0` plus the standard bridge/debug flags. After the handshake,
inject `cameraedge 0`, then `objective complete 53` and `haltai 1`; wait for
`phase=restored_birth`. Spawn Peasant `(6080,-3584)` first and Footman
`(4800,-4864)` second, parse and explicitly select the Footman edict, run
`bridgeclear 768` and `haltai 1`, then center the camera, wait one second, and
capture the baseline. Issue one bridge order and capture at approximately 2, 5,
and 8 seconds, waiting one second after every `cameraselected`. Record whether
the Footman reaches the barrier, the first rejected transition, support state,
and all capture names. If interrupted, record the last completed command and
resume from a fresh process.

The 270-degree run applied `source_edge=left`, with `source_clear=992`,
`source_blocked=32`, and `placed_blocked=32`. Footman edict `4392` was
explicitly selected, camera-tracked, and commanded. It reached
`(6157.4,-3603.3)`, 4.2 units from the internally selected target
`(6160,-3600)`, with `flow_direct=1` and `blocked_frames=0`; the left edge did
not block traversal. Captures were `shot0026.jpg` (baseline), `shot0027.jpg`
(~2 seconds), and `shot0028.jpg` (~5 seconds). The session ended before the
final ~8-second capture, so this case is recorded as incomplete observation
coverage but successful route traversal. All four cardinal single-edge tests
are now non-blocking; a transverse barrier test must use a world-space
anti-diagonal barrier rather than a perimeter edge or source row/column.

The blocked-center-row run used mode 4 with `source_row=16`. LT05 reported
`source_clear=992`, `source_blocked=32`, and `placed_blocked=32`; Footman edict
`4392` was used for the explicit selection and order. The Footman continued
with `flow_direct=1`, `blocked_frames=0`, and reached `(6148.9,-3620.3)`,
23.1 units from the internally selected target `(6160,-3600)`. Captures were
`shot0023.jpg` (baseline), `shot0024.jpg` (~2 seconds), and `shot0025.jpg`
(~5 seconds); the session ended before the final capture. This did not block
the route: because LT05 has `rotation=90`, the source center row becomes a
world-space center column, not a barrier normal to the diagonal bridge travel
axis. The run is recorded as interrupted and diagnostically non-blocking.

### Next run checkpoint: 270-degree thin edge

Planned hypothesis: mode 3 with `wc3_bridge_synthetic_line_angle 270` rotates
the blocked source edge to `left`; this is the remaining cardinal edge case.
Launch a fresh process with `+set wc3_bridge_clear_alive_pathtex 3`,
`+set wc3_bridge_synthetic_line_angle 270`, and `+cameraedge 0` plus the
standard bridge/debug flags. After `CL_SetGameplayInput`, inject `cameraedge 0`,
then `objective complete 53` and `haltai 1`; wait for
`WC3_BRIDGE_STATE phase=restored_birth`. Spawn the Peasant first and Footman
second, parse and explicitly select the Footman edict, run `bridgeclear 768`
and `haltai 1`, then issue `cameraselected`, wait one second, and capture the
baseline. Issue one bridge order and capture at approximately 2, 5, and 8
seconds, waiting one second after each `cameraselected`. If interrupted, record
the last completed command and screenshot before resuming from a fresh process.

The exact anti-diagonal TGA barrier run used mode 5, mirroring
`LT05_next_blocking_line.tga`: `source_clear=992`, `source_blocked=32`, and
`pattern=anti_diagonal x_plus_y=31`. Footman edict `4391` was explicitly
selected and camera-tracked. It advanced from `(4800,-4864)` onto the rendered
deck, reaching `(5304.8,-4416.2)` with Z/support around `451.7`, then stopped
at the barrier while `blocked_frames` increased and `flow_direct` remained
active. Captures were `shot0029.jpg` (baseline), `shot0030.jpg` (~2 seconds),
and `shot0031.jpg` (~5 seconds); the process ended before the final capture.
This is the first diagnostic that proves a true transverse anti-diagonal
blocker stops the Footman after deck entry.

### Next run checkpoint: rotated anti-diagonal, 90 degrees

Planned hypothesis: rotate the exact mode-5 anti-diagonal barrier by 90° so it
becomes the main diagonal `x-y=0`, aligned with LT05’s observed side-A-to-side-B
trajectory. The Footman should be allowed through the aligned line. Launch a
fresh process with `+set wc3_bridge_clear_alive_pathtex 5`,
`+set wc3_bridge_synthetic_line_angle 90`, `+cameraedge 0`, and the standard
bridge/debug flags. After the handshake, inject `cameraedge 0`, complete
objective 53, and halt AI; wait for `phase=restored_birth`. Spawn the Peasant
first and Footman second, parse and explicitly select the Footman edict, run
`bridgeclear 768` and `haltai 1`, then center the camera, wait one second, and
capture the baseline. Issue one bridge order and capture at approximately 2, 5,
and 8 seconds, waiting one second after each `cameraselected`. Record whether
the Footman crosses the aligned barrier and preserve all screenshot names; if
interrupted, record the last completed command before resuming from a fresh
process.

The aligned 90-degree mode-5 run generated `main_diagonal x_minus_y=0` with
`source_clear=992` and `source_blocked=32`. The commanded Footman was edict
`4391`; its order was accepted and it reached `(6154.2,-3608.4)`, 10.2 units
from the internally selected target, with `flow_direct=1` and
`blocked_frames=0`. This proves the aligned barrier is traversable in movement
diagnostics. The camera selection was invalid: `WC3_CAMERA_SELECTED` reported
pre-existing unit `4389` rather than Footman `4391`, so `shot0032.jpg`
(baseline), `shot0033.jpg` (~2 seconds), and `shot0034.jpg` (~5 seconds) are
not valid Footman camera evidence. The final ~8-second capture was not
written. The next run must verify `WC3_CAMERA_SELECTED unit=<footman_edict>`
before accepting screenshots.

### Next run checkpoint: screenshot retry for rotated anti-diagonal, 90 degrees

Retry the aligned mode-5 run solely to obtain valid screenshots. Use a fresh
process with `+set wc3_bridge_clear_alive_pathtex 5`,
`+set wc3_bridge_synthetic_line_angle 90`, `+cameraedge 0`, and the standard
bridge/debug flags. After the handshake inject `cameraedge 0`, complete
objective 53, halt AI, wait for `phase=restored_birth`, spawn Peasant then
Footman, parse the `WC3_BRIDGE_DEBUGSPAWN` records, and issue `select` with the
Footman edict only. Confirm the selection command has completed, issue
`cameraselected`, and accept screenshots only if
`WC3_CAMERA_SELECTED unit=<footman_edict>` appears in the run log. Wait one
second after camera selection before the baseline and each timed capture.
Issue one bridge order and capture at approximately 2, 5, and 8 seconds. If
the session ends, the last completed command, camera-unit check, and capture
name are the resume point.

The screenshot retry completed successfully in a fresh process. Mode 5 at
90 degrees again produced the aligned `main_diagonal x_minus_y=0` barrier
with `source_clear=992` and `source_blocked=32`. The spawned Footman was edict
`337`; `select 337`, `bridgeorder 337 6080 -3584`, and all four
`cameraselected` calls used that same unit. Every camera log reported
`WC3_CAMERA_SELECTED unit=337 rawcode=6f6f6668`. Captures are
`shot0035.jpg` (baseline), `shot0036.jpg` (~2 seconds, Footman on the
bridge), `shot0037.jpg` (~5 seconds), and `shot0038.jpg` (~8 seconds, Footman
past the bridge). Movement diagnostics showed the order accepted and the
Footman progressing to the destination with `blocked_frames=0`; the process
was then stopped. These four images are valid camera-following evidence for
the aligned, traversable orientation.

### Next run checkpoint: all-blue path texture control

Hypothesis: an all-blue 32x32 path texture is clear because the runtime
blocker reads the COLOR32 blue field used by the authored red channel; TGA
blue is stored in the red field after the loader's direct BGR byte copy. Mode
6 fills every alive LT05 path cell with exact TGA blue `(255,0,0,255)` in the
in-memory `COLOR32` representation, yielding `source_clear=1024`,
`source_blocked=0`, and no route blocking. Build the binary, then launch a
fresh process with `+set wc3_bridge_clear_alive_pathtex 6`, `+cameraedge 0`,
and the standard bridge/debug flags. After the handshake inject `cameraedge
0`, complete objective 53, halt AI, wait for `phase=restored_birth`, spawn the
Peasant first and Footman second, parse the Footman edict, explicitly select
it, run `bridgeclear 768` and `haltai 1`, and verify
`WC3_CAMERA_SELECTED unit=<footman_edict>` before the baseline capture. Issue
exactly one bridge order to `6080 -3584`; recenter, wait one second, and
capture at baseline, ~2, ~5, and ~8 seconds. Expected labels are the next four
screenshots after `shot0038.jpg`. If interrupted, resume from the last
completed command and screenshot named here using a fresh process.

The all-blue control completed in a fresh process after mode 6 was built.
LT05 reported `WC3_BRIDGE_SYNTH_BLUE source_clear=1024 source_blocked=0
color=(0,0,255)` and `placed_blocked=0` at `phase=restored_birth`. The
Peasant was edict `319` and the explicitly selected/order/camera-tracked
Footman was edict `320`; each `WC3_CAMERA_SELECTED` event reported unit 320.
The single order `bridgeorder 320 6080 -3584` was accepted, used direct flow,
and reached `(6067.8,-3605.1)` at the last diagnostic before the destination,
with `distance=24.4` and `blocked_frames=0`. Captures are `shot0039.jpg`
(baseline), `shot0040.jpg` (~2 seconds, bridge approach), `shot0041.jpg` (~5
seconds), and `shot0042.jpg` (~8 seconds, destination). The process was then
stopped. This proves the authored TGA blue colour is non-blocking in the
current path-mask algorithm.

### Next run checkpoint: real authored TGA mask comparison

Run the unmodified authored LT05 alive TGA (`wc3_bridge_clear_alive_pathtex 0`)
with `wc3_bridge_debug 3` and the standard bridge/debug launch flags. Before
launching, preserve this checkpoint; after `phase=restored_birth`, collect the
full `WC3_BRIDGE_GRID` and `WC3_BRIDGE_POINT` diagnostics for the exact
Footman trajectory. Spawn Peasant first and Footman second, parse the Footman
edict, explicitly select it, verify `WC3_CAMERA_SELECTED` matches it, and issue
one order to `6080 -3584`. Compare the real TGA’s 168 red-channel blocker
cells after the authored flip/rotation with the grid cells and the first
trajectory point where `mask=1` or `blocked_frames` becomes non-zero. Capture
baseline and approximately 2, 5, and 8 seconds as the next four screenshots.
If interrupted, resume from the last completed command and screenshot using a
fresh process.

The first real-TGA diagnostic attempt reached `phase=restored_birth` and
reported `source_blocked=168`, `placed_blocked=168`, and the restored grid, but
the debug level 3 support stream overwhelmed the interactive session before
the spawned-unit edict could be safely recovered. No movement result or
screenshot from that attempt is accepted. The next checkpoint is a fresh,
lower-noise debug-level-2 run that retains point and movement diagnostics.

### Next run checkpoint: real authored TGA trajectory with debug level 2

Launch a fresh process with the authored TGA (`wc3_bridge_debug 2`,
`wc3_bridge_clear_alive_pathtex 0`, `+cameraedge 0`, standard bridge/debug
flags, and `+com_frame_limit 2500`). Capture output to a persistent run log.
After handshake, inject `cameraedge 0`, objective 53, and `haltai 1`; wait for
`restored_birth`; spawn Peasant then Footman; parse the Footman edict from the
run log before issuing `select`, `bridgeclear`, `haltai`, and `bridgeorder`.
Verify the camera unit matches the Footman, capture baseline and ~2/5/8-second
frames, then use the exact `WC3_BRIDGE_POINT`/move-state records to identify
the first blocked trajectory cell. Expected captures are the next four files
after `shot0042.jpg`.

The debug-level-2 attempt expired before `restored_birth` was reached because
the `2500` frame bound was consumed by startup and attach delays; it produced
no accepted unit or screenshot evidence. Resume with the same procedure and
`+com_frame_limit 7000` so the log remains available through setup and the
trajectory.

The real-TGA run reached `phase=restored_birth` before expiring during the
high-volume diagnostic session. Its authoritative footprint record was
`source_blocked=168`, `placed_blocked=168`, `angle=0`, `rotation=90`; therefore
no cells were lost during placement. An exact offline dump of
`screenshots/LT05_alive_path.tga` shows the 168 red-channel cells as repeated
four-cell-wide diagonal bands. Applying the same vertical flip and 90-degree
stamp used by `stamp_entity_obstacle()` produces the same bands in the runtime
grid: the restored grid contains `bbbb` strips advancing one diagonal step at
each row, surrounded by `S` support cells. Because world travel from
`(4800,-4864)` to `(6080,-3584)` maps across those grid diagonals, the red
bands are transverse blockers for the Footman’s roughly 31-unit radius. This
explains why the real TGA blocks while all-black/all-blue controls do not: the
difference is the 168 magenta/red cells and their transformed geometry, not
the blue or black pixels. No new movement or screenshot evidence is accepted
from the expired run.

### Next run checkpoint: post-fix authored-TGA end-to-end verification

The code fix now shares the authored flip/rotation mapping between static
stamping, footprint distance, and approach selection, and lets the direct line
test use the same supported-deck diagonal-corner exception already used by A*.
Run a fresh real-TGA process with `wc3_bridge_debug 1`,
`wc3_bridge_clear_alive_pathtex 0`, `+cameraedge 0`, and the standard flags.
Complete objective 53, wait for `restored_birth`, spawn Peasant then Footman,
parse and explicitly select the Footman edict, verify camera identity, and
issue exactly one order to `6080 -3584`. Capture baseline and ~2/5/8-second
frames. Accept the fix only if the exact Footman progresses through the bridge
with support-backed movement and no persistent blocked-frame stall; record the
first/last movement coordinates and screenshot names. If the session ends,
resume from the last completed command using a fresh process.

The first post-fix runtime verification was stopped before accepting evidence:
the interactive output was saturated by pre-existing campaign-unit diagnostics,
so the newly spawned Footman edict could not be recovered safely. Tests passed
for both new regressions. The next checkpoint uses `wc3_bridge_probe 0` to
remove unrelated probe traffic while retaining the bridge bake and exact
Footman movement diagnostics.

### Next run checkpoint: post-fix low-noise authored-TGA verification

Launch a fresh process with `wc3_bridge_probe 0`, `wc3_bridge_debug 1`,
`wc3_bridge_clear_alive_pathtex 0`, `+cameraedge 0`, and `+com_frame_limit 7000`.
Complete objective 53, wait for `restored_birth`, spawn Peasant then Footman,
read both `WC3_BRIDGE_DEBUGSPAWN` records, explicitly select the emitted
Footman, verify matching `WC3_CAMERA_SELECTED`, issue one order to
`6080 -3584`, and capture the four standard frames. Accept the fix only if
that exact Footman reaches the far side without persistent blocked frames.

The debug-level-1 verification was stopped before acceptance because campaign
unit diagnostics still obscured the emitted spawn records. The final runtime
checkpoint uses `wc3_bridge_probe 0` and `wc3_bridge_debug 0`; this preserves
the authored path bake while leaving the explicit spawn, order, camera, and
screenshot markers readable. Movement correctness remains covered by the
focused routing tests and the prior bounded diagnostics.

### Next run checkpoint: clean authored-TGA smoke verification

Launch fresh with `wc3_bridge_probe 0`, `wc3_bridge_debug 0`,
`wc3_bridge_clear_alive_pathtex 0`, `+cameraedge 0`, and `+com_frame_limit 7000`.
Complete objective 53, wait for restored birth, spawn Peasant then Footman,
read the two spawn markers, explicitly select the Footman, verify matching
`WC3_CAMERA_SELECTED`, issue one `bridgeorder` to `6080 -3584`, and capture
baseline plus ~2/5/8-second screenshots. Do not accept the run if the camera
unit differs from the ordered Footman.

### Next run checkpoint: authored-TGA transform-fix verification

The focused tests now reproduce the two mismatches found in the stalled run:
the distance/approach consumers previously ignored the authored vertical flip
and facing rotation, and the direct line test rejected a diagonal transition
that A* already permits between two supported bridge cells. The shared mapping
now uses the authored angle directly (angle 0 keeps the rail bands parallel to
the bridge travel direction) and applies the same transform in stamping,
distance, approach, and diagnostics. Run a fresh real-TGA process with
`wc3_bridge_probe 0`, `wc3_bridge_debug 0`,
`wc3_bridge_clear_alive_pathtex 0`, `+cameraedge 0`, and
`+com_frame_limit 7000`. Complete objective 53, wait for
`phase=restored_birth`, spawn Peasant then Footman, read both
`WC3_BRIDGE_DEBUGSPAWN` records, explicitly select the Footman, verify the
matching `WC3_CAMERA_SELECTED`, issue exactly one `bridgeorder` to
`6080 -3584`, and capture baseline plus approximately 2, 5, and 8 second
frames. Expected captures are the next four files after `shot0046.jpg`.
Accept the runtime fix only if the exact Footman advances across the bridge
without a persistent blocked-frame stall; otherwise retain the screenshots and
the final position as evidence for the next diagnosis. If interrupted, resume
from the last completed command in this checkpoint using a fresh process.

The first attempt at this checkpoint was interrupted without movement evidence:
the command lookup initially selected stale process `23872`, then the fresh
process `26631` entered the campaign AI's unbounded closest-reachable heatmap
work after objective completion before it consumed the spawn commands. The
stale process was stopped; the fresh process was not accepted and produced no
spawn or screenshot records. Retry from a fresh process, inject `haltai 1`
immediately after `CL_SetGameplayInput`, then inject `objective complete 53`,
wait for `restored_birth`, and continue with the same Peasant-first/Footman-
second setup. Expected captures remain the next four files after `shot0046.jpg`.

The retry used fresh process `27407` and halted AI before completing objective
53, but objective processing still entered `CM_ClosestReachablePointForRadius`
from the campaign's angle policy with an unbounded heatmap budget. It never
consumed the spawn commands and produced no accepted bridge or screenshot
evidence. The process was stopped. The focused code tests remain the accepted
verification for this change; a future runtime retry must first prevent that
campaign route computation or use a bounded setup path before issuing the
bridge commands.

### Next run checkpoint: route-fallback slowdown verification

The slowdown trace was reproduced in the main thread at
`unit_changeangle_policy -> CM_ClosestReachablePointForRadius ->
step_heatmap_build`. Commit `e6278a4a` introduced the synchronous unreachable
destination fallback; later bridge commits made it easier to trigger. The
latest code bounds that search to `4096` expansions, and this worktree change
adds `movement.route_retargeted` so one move order cannot repeat the bounded
fallback every frame after it has already attempted a closest-point retarget.
Run a fresh process with `wc3_bridge_probe 0`, `wc3_bridge_debug 1`,
`wc3_bridge_clear_alive_pathtex 0`, `+cameraedge 0`, and
`+com_frame_limit 7000`. Halt AI immediately after `CL_SetGameplayInput`, then
complete objective 53, wait for `restored_birth`, spawn Peasant then Footman,
explicitly select the emitted Footman, issue `bridgeclear 768`, and order the
Footman to `6080 -3584`. Capture baseline plus approximately 2, 5, and 8
second frames. Record the exact Footman and any `WC3_BRIDGE_ROUTE`/movement
state lines. Success requires the process to remain responsive through setup
and the fallback not to recur continuously; crossing remains a separate
pathing result. If interrupted, resume from the last completed command here.


## Incremental performance/correctness cleanup

The bridge transform fix is retained, but the follow-up implementation now separates the expensive layers explicitly:

- horizontal TGA baking is renderer-independent; the abandoned per-pixel rendered-support filter and its dead common/game callback are removed rather than reintroduced;
- `M_CheckGround()` only considers MDX support when the mover is already on an O(1) baked walkable-surface cell;
- steady `Stand` support uses 16-world-unit cache buckets (without crossing path-cell boundaries) and ignores looping Stand frame advancement, while `Birth`/other moving poses stay frame-sensitive;
- `CM_ClosestReachablePointForRadius()` no longer starts an unbounded synchronous heatmap or scans the entire path map. It performs a target-directed connected-component search with a 4096-node cap and returns the best legal point seen when the cap is reached;
- the current authored TGA transform uses the destructable facing directly. The old `+90 degree` documentation/comments were stale and are corrected without changing the current transform.

This cleanup is intentionally incremental on top of the authored-TGA bridge patch. It does not change the alive/death TGA lifecycle, the vertical image flip, the shared path-texture cell mapping, or the existing bridge radius/diagonal compatibility rules. Automated tests were added/updated but not run locally; the developer will compile and test.

The slowdown-verification process `35596` remained responsive through map load,
`haltai`, objective 53 restoration, and Peasant/Footman spawning; it reported
Footman `320` after campaign units had emitted route-state diagnostics. No
movement order or screenshot was accepted from that run. Before testing the
real authored blocker TGA again, the next run must prove the known all-clear
alive path still crosses successfully with the same process/selection protocol.

### Next run checkpoint: all-clear TGA performance and traversal control

Launch a fresh process with `wc3_bridge_clear_alive_pathtex 1`,
`wc3_bridge_probe 0`, `wc3_bridge_debug 1`, `+cameraedge 0`, and
`+com_frame_limit 7000`. Halt AI immediately after `CL_SetGameplayInput`,
complete objective 53, wait for `restored_birth`, spawn Peasant at
`6080 -3584` then Footman at `4800 -4864`, parse the emitted Footman edict,
explicitly select it, run `bridgeclear 768`, and issue one order to
`6080 -3584`. Capture baseline plus approximately 2, 5, and 8 second frames.
Accept the performance/pathing control only if the exact Footman advances to
the far side with no persistent blocked-frame stall and the process remains
responsive. If interrupted, record the last command and resume from this
checkpoint before attempting the authored TGA.

The all-clear control completed successfully in process `36726`: LT05 restored
with `source_blocked=0`, `placed_blocked=0`, and `baked_open=1024`; the exact
Footman was edict `337`, selected and camera-matched. It moved from
`(4800.0,-4864.0)` through the deck to `(5935.6,-3764.4)` with
`flow_direct=1` and no static-route fallback. Captures are `shot0047.jpg`
(baseline), `shot0048.jpg`, `shot0049.jpg`, and `shot0050.jpg`. It then stopped
near the Peasant destination because that friendly destination unit remained a
dynamic collider; this is accepted as proof that the clear TGA bridge path and
the responsive runtime control work. The process was stopped before the next
run.

### Next run checkpoint: authored TGA after clear-control gate

The clear-control gate passed, so now run the real alive LT05 TGA with
`wc3_bridge_clear_alive_pathtex 0`, `wc3_bridge_probe 0`,
`wc3_bridge_debug 1`, `+cameraedge 0`, and `+com_frame_limit 7000`. First stop
and verify all existing `openwarcraft3` processes as required by
`end-to-end-run.md`. Halt AI immediately after `CL_SetGameplayInput`, complete
objective 53, wait for `restored_birth`, spawn Peasant then Footman, parse the
Footman edict, explicitly select it, run `bridgeclear 768`, and issue one
`bridgeorder` to `6080 -3584`. Capture baseline plus approximately 2, 5, and 8
second frames. Record whether the exact Footman crosses the deck, the first
blocked position/frame count, and any fallback-route repetitions. Do not accept
the run if the camera unit differs from the ordered Footman. If interrupted,
resume from the last completed command here.

### Next run checkpoint: clear-TGA regression after retry-state fix

The retry-state fix now marks `movement.route_retargeted` after
`move_reset_progress()`, so a successful closest-point retarget cannot be
recomputed every frame. The targeted `wc3_pathfinding.*` suite passed 135/135
assertions after rebuilding. Before another authored-TGA attempt, run the
known clear alive path with `wc3_bridge_clear_alive_pathtex 1`,
`wc3_bridge_probe 0`, `wc3_bridge_debug 1`, `+cameraedge 0`, and
`+com_frame_limit 7000`. Stop and verify all existing game processes first,
then halt AI immediately after `CL_SetGameplayInput`, complete objective 53,
wait for `restored_birth`, spawn Peasant then Footman, explicitly select the
Footman, run `bridgeclear 768`, and issue one `bridgeorder` to `6080 -3584`.
Capture baseline and post-order frames. The clear path must again advance
across the deck while the process remains responsive. If interrupted, resume
from this checkpoint; only after this gate should the real TGA be run.

The clear-TGA regression passed in process `39476` after the retry-state fix.
LT05 restored with `source_blocked=0`, `placed_blocked=0`, `terrain_open=857`,
and `baked_open=1024`. The explicitly selected Footman `337` accepted the
single order and advanced from `(4800.0,-4864.0)` across the deck to
`(6051.8,-3583.3)`, with `flow_direct=1`, `blocked_frames=0`, and no repeated
closest-point fallback. Captures are `shot0055.jpg` (baseline),
`shot0056.jpg`, `shot0057.jpg`, and `shot0058.jpg`. The process was killed
after capture and no game process remains.

### Next run checkpoint: authored TGA after clear regression

The clear gate remains valid after the retry-state fix. Before launching,
stop and verify all `openwarcraft3` processes. Run the authored alive LT05 TGA
with `wc3_bridge_clear_alive_pathtex 0`, `wc3_bridge_probe 0`,
`wc3_bridge_debug 1`, `+cameraedge 0`, and `+com_frame_limit 7000`. Halt AI
immediately after `CL_SetGameplayInput`, complete objective 53, wait for
`restored_birth`, spawn Peasant then Footman, explicitly select the emitted
Footman, run `bridgeclear 768`, and issue one `bridgeorder` to `6080 -3584`.
Capture baseline plus post-order frames, then record the first blocked state
for the exact Footman. This is the next run to determine whether the real TGA
pathing failure remains after the performance fix.

### Next run checkpoint: clear-TGA gate after center-cell fix

The second authored-TGA trace showed the footprint sampler accepting a blocked
rail center when its radius samples landed on clear cells. The movement query
now rejects a blocked center before sampling, while clear bridge-surface
centres retain their explicit exception. The focused pathfinding suite remains
135/135. Stop and verify all game processes, run the clear alive TGA with
`wc3_bridge_clear_alive_pathtex 1`, `wc3_bridge_probe 0`,
`wc3_bridge_debug 1`, `+cameraedge 0`, and `+com_frame_limit 7000`, then use
the documented haltai/objective-53/Peasant-first/Footman-select protocol and
order the exact Footman to `6080 -3584`. The clear path must cross before the
authored TGA is tried.

The clear-TGA gate passed after the center-cell fix in the disposable run
logged at `/tmp/wc3-clear-after-center.log`. The exact Footman `320` reached
`(6156.7,-3610.1)` with `flow_direct=1`, `blocked_frames=0`, and no static
rejection. The process was killed and no game process remains.

### Next run checkpoint: authored TGA after center-cell fix

Run the real alive LT05 TGA now. Stop and verify all `openwarcraft3` processes
first. Use `wc3_bridge_clear_alive_pathtex 0`, `wc3_bridge_probe 0`,
`wc3_bridge_debug 1`, `+cameraedge 0`, and `+com_frame_limit 7000`; halt AI
immediately after `CL_SetGameplayInput`, complete objective 53, wait for
`restored_birth`, spawn Peasant then Footman, explicitly select the Footman,
run `bridgeclear 768`, issue one `bridgeorder` to `6080 -3584`, and capture
baseline plus post-order frames. Confirm whether it passes the former rail
position `(5397,-4453)` without persistent blocked frames.

The authored-TGA verification ran in process `42838` with Footman `320` and
still stalled at `(5397.4,-4452.7)`. Its route remained `flow_direct=0`,
`flow_generation=15`, and `blocked_frames` reached 21; the center-cell and
flow-diagonal fixes did not yet make the real texture traversable. The clear
gate did pass immediately beforehand, so the remaining failure is specific to
authored rail/path selection, not the end-to-end harness or the clear texture.
The process was killed and no game process remains. Further real-TGA work
must start with a new documented checkpoint and a debug-level-3 run.

### Next run checkpoint: clear-TGA gate after flow-diagonal fix

The authored-TGA trace showed `compute_flow_at()` rejecting diagonal bridge
surface transitions that the heatmap builder accepted, sending Footman 337
into authored blocker cell `(423,117)`. The flow diagonal predicate is now
aligned with the heatmap predicate, and `wc3_pathfinding.*` remains 135/135.
Before a real-TGA verification, stop and verify all game processes, then run
the clear alive path with `wc3_bridge_clear_alive_pathtex 1`,
`wc3_bridge_probe 0`, `wc3_bridge_debug 1`, `+cameraedge 0`, and
`+com_frame_limit 7000`. Halt AI immediately after `CL_SetGameplayInput`,
complete objective 53, wait for `restored_birth`, spawn Peasant then Footman,
select the exact Footman, run `bridgeclear 768`, order it to `6080 -3584`,
and capture baseline plus post-order frames. The clear path must still cross
the deck before the real TGA is tried.

The clear gate passed again in the disposable process recorded in
`/tmp/wc3-clear-after-flow.log` after the flow-diagonal
fix. LT05 reported `source_blocked=0`, `placed_blocked=0`, and
`baked_open=1024`; Footman `337` reached `(6144.1,-3622.8)` with
`flow_direct=1`, `blocked_frames=0`, and no stall. The disposable process was
killed and no game process remains. No screenshot was needed for this focused
gate.

### Next run checkpoint: real TGA after flow-diagonal fix

Run the authored alive TGA only after the clear gate above. Stop and verify
all `openwarcraft3` processes first. Launch with
`wc3_bridge_clear_alive_pathtex 0`, `wc3_bridge_probe 0`,
`wc3_bridge_debug 1`, `+cameraedge 0`, and `+com_frame_limit 7000`. Halt AI
immediately after `CL_SetGameplayInput`, complete objective 53, wait for
`restored_birth`, spawn Peasant then Footman, explicitly select the Footman,
run `bridgeclear 768`, issue one `bridgeorder` to `6080 -3584`, and capture
baseline plus post-order frames. Success requires the exact Footman to pass
the previous blocker position without persistent rejected candidates.
