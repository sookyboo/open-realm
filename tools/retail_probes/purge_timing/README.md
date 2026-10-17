# Purge hostile immobilize and recovery probe

Measures stock TFT `Apg2` effective movement speed at 100 ms intervals after a
hostile cast, against an untreated 300-speed control. Both targets are
position-locked every 50 ms. The probe starts only after OrcX01's Intro Skipped
trigger starts Gameplay.

## Prepare and launch

Use the [Retail 1.29 JHCR runbook](../../../../docs/games/warcraft-3/ability-probes/jhcr.md)
and keep one Xvfb display alive for the full session. Set `CUSTOM_MAP_DATA` to
the active prefix's `CustomMapData` directory. Set `result_file` in the manifest
to `$CUSTOM_MAP_DATA/purge-timing-run1.txt`, then prepare with the installed
JHCR binary plus matching `common-1.29.2.j` and the map's `Blizzard.j`:

```sh
python3 tools/wc3_retail_probe.py prepare \
  tools/retail_probes/purge_timing/manifest.json /tmp/wc3-purge-timing \
  --jhcr "$JHCR" --common-j "$COMMONJ" --blizzard-j "$BLIZZARDJ" \
  --jhcr-preload-path "$CUSTOM_MAP_DATA"
```

Launch `--control`, visually confirm the “To Tame a Land” chapter card, click
it, wait for the cinematic, press Escape, then exit Retail. Launch the prepared
map with `--control-confirmed` and repeat the same card/cinematic sequence.
Wait about 22 seconds after the Intro Skipped callback for `PG_DONE`, then run
the runner's `capture` command. A standalone run must contain `PG_META`,
`PG_SETUP`, `PG_BASELINE`, `PG_CAST_ORDER`, `PG_CAST_EFFECT`, `PG_SAMPLE`, and
`PG_DONE`, with no `PG_SETUP_FAIL`.

## Repeat in the same Retail process

- Type `-probe` to run a fresh measurement without consuming a JHCR sequence.
  `PG_Start` stops the prior timer, removes old test units and spell trigger,
  clears counters/output, and creates a new run ID.
- For a code update, change only an assessed reloadable function (the manifest
  currently allows only passive `PG_Log`), publish it with:

  ```sh
  python3 tools/wc3_retail_probe.py jhcr-update \
    /tmp/wc3-purge-timing /path/to/updated/war3map.j
  ```

  Then type `-jhcr` once. Require status `1`, a
  new `PG_META run=N`, all setup/cast markers, and `PG_DONE` before accepting
  the iteration.
- Copy `CustomMapData/purge-timing-run1.txt` to a unique evidence filename
  after every completed run; the next invocation overwrites it. Preserve the
  matching JHCR update JSON and sequence payload.

The three captured Retail runs are in `evidence/`. The first JHCR update
reported status `1` but did not emit its expected `PG_REVISION=2` marker. The
second changed only passive `PG_Log` to emit `PG_LOG_REV2` when it receives the
`PG_META` line; run 3 reports status `1`, emits that marker, and reaches
`PG_DONE`. The checked-in logger stays unmarked; use a new marker string for
each future reload check.
