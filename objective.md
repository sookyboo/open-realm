# Current Objective

Investigate and fix LT05 bridge traversal in `Maps\Campaign\Prologue02.w3m`.

## Current state

- The bridge is confirmed dead before objective 53: the runtime log records `WC3_BRIDGE phase=dead`.
- After `objective complete 53`, the runtime log records `WC3: completing objective via trigger 53 directly` and `WC3_BRIDGE phase=restored_birth`; this is the restored/alive pathing state.
- The alive bridge path texture is applied and the static pathing bake is rerun, but no run has yet proven a normal ground unit crossing the rendered bridge deck from one side to the other.
- Existing route attempts fail during waypoint generation. Treat `mask=1` or an `inside=1` ground-height sample as insufficient traversal proof unless the diagnostic also proves LT05 support selection and a complete side-A-to-side-B trajectory.
- A screenshot test using a created and selected unit and the added camera commands appeared to remain in a cinematic. With cinematics skipped, there may still be a delay of several seconds between completing objective 53, clearing the cinematic state, and the objective becoming fully effective. Wait for and log those transitions before judging the camera or bridge.
- The latest headless run created Footman edict 319 at `(4800,-4864)`, selected it, centered the camera near `(5440,-4224)`, and ordered it toward `(6080,-3584)`. `WC3_CAMERA_SELECTED` and `WC3_BRIDGE_DEBUGORDER` were emitted, but the screenshot showed the selected-unit HUD over a black world and is not traversal proof. The broad probe output was saturated by campaign units, so this run is inconclusive for edict 319.

## Next session procedure

1. Launch the Debian headless sandbox with bridge probing enabled and cinematic/tutorial timing logs:
   `+set wc3_bridge_probe 1 +set wc3_bridge_debug 1 +set wc3_quest_debug 1`.
2. Load `Maps\Campaign\Prologue02.w3m` and verify LT05 is dead before testing.
3. Run `objective complete 53`; verify the trigger, restored/alive bridge state, pathing bake, and cinematic-clearance/objective-completion timing in the log.
4. Move the camera to approximately `(5440, -4224)` only after the restored/alive state is confirmed.
5. Determine LT05's actual bridge axis from its logged origin, angle, alive pathing dimensions, and transformed footprint. Choose deterministic opposite-side coordinates along that axis.
6. Halt campaign AI before creating/selecting one normal ground unit, issue a side-A-to-side-B order, wait for all cinematic and objective transitions to finish, and capture movement diagnostics for that unit only.
7. Require evidence of `ENTER -> MOVE through the bridge center -> EXIT`, including support hit/height and unit Z. Then repeat side B to side A.
8. Identify the earliest failing layer: route connectivity, point/radius pathability, line/corner pathability, support selection, Z update, or stale cache invalidation.
9. Make the smallest evidence-based fix, add a deterministic regression test, and preserve dead-state blocking, alive authored blockers/rails, normal radius behavior, and no-corner-cut behavior.

## Evidence discipline

Do not claim that the radius exception is required, or that bridge crossing is fixed, without `support_hit=1` on the actual LT05 deck and a complete side-to-side trajectory. Keep exploratory logs gated or remove them after the root cause is established.
