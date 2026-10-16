# General-purpose rerunnable ability probe scaffold

Copy this directory to `tools/retail_probes/<ability_or_question>/`, then
replace `manifest.example.json` with a manifest for the selected Retail map.
Use the normal probe runner to prepare the map once. Keep the JASS scaffold
small, and put ability-specific setup and the experiment schedule in
`helpers.j`.

## Structure

- `globals.j`: persistent handles, run counter, phase, measurements, and
  configurable constants. Avoid redeclaring globals on each run.
- `helpers.j`: one-time event/chat registration, idempotent `Start`, per-run
  reset/setup, measurement callbacks, sampling/position lock, and final report.
- `manifest.example.json`: runner edits, metadata, capture contract, and the
  optional JHCR allowlist. Initially allow only a passive logger or formatter;
  keep active timers and event callbacks out until their live replacement is
  specifically justified and validated.

## Rerun contract

The starter uses a single `-probe` chat trigger. Registration is one-time;
each invocation increments `runId`, tears down old timers/triggers/units,
resets counters and output, and starts a fresh scenario. Every log line carries
that ID. If a run is interrupted by a rerun, it writes a `DONE status=cancelled`
record before clearing output. The final `DONE` record includes counts and an
explicit completion marker. Preserve the old run output before clearing or
restarting if capturing it outside the JASS preload file.

Design each run as:

1. Emit metadata and `START` with build, ability rawcode, scenario, and run ID.
2. Create/configure entities and verify ability levels, positions, accepted
   orders, and relevant handles. Abort with a specific `SETUP_FAIL` marker if
   a precondition fails.
3. Register the event path once or replace its old trigger before each run.
4. Exercise a positive control through the same observation path. Verify it
   was seen, then restore target state and clear treatment counters.
5. Run baseline, treatment, and available negative/control cases, changing one
   factor at a time. Sample position and state throughout asynchronous phases.
6. Emit per-phase results and exactly one `DONE`; stop/pause timers and release
   temporary objects so `-probe` can start a clean next run.

Use `GetHandleId` to correlate JASS handles in evidence. Do not rely on `unit`
handle equality for source matching. If map AI or orders can move test entities,
actively lock coordinates on a timer and log measured coordinates/distance;
zero movement speed alone may not be sufficient. Filter observations by both
target and source identity to reject unrelated map activity.

## JHCR edit loop

Prepare and load the instrumented map once. For a JASS change, compile the
complete updated `war3map.j`, run `jhcr-update` using the same prepared
directory, then trigger one in-map reload. Confirm status `1`, a fresh marker,
and that the run reaches `DONE`; status `1` by itself is not a successful
experiment. Do not run a second reload without publishing the next sequence.
JHCR sequence, preload path, Wine-prefix, and active-callback constraints are
in the [runbook](../../../../docs/games/warcraft-3/ability-probes/jhcr.md).

If a runner failure recurs, fix the runner's preflight, process detection,
freshness check, or diagnostics before repeating the Retail experiment. This
reduces bad runs across all probes. Keep concrete evidence and failed setup
markers; do not hide a runner fault as an ability result.
