# Purge recovery at the speed cap

Measures hostile stock TFT `Apg2` recovery against an untreated position-locked
control. The target and control request 400 movement speed; samples are taken
every 50 ms.
The setup is baked into the prepared map, so reruns use JHCR without replacing
the active `PG_Tick` callback.

Use the Retail 1.29 workflow in
[`docs/games/warcraft-3/ability-probes/jhcr.md`](../../../../docs/games/warcraft-3/ability-probes/jhcr.md).
Set the manifest `result_file` to the active prefix's
`CustomMapData/purge-speed-floor-run1.txt`, then prepare with the matching JHCR
binary, `common-1.29.2.j`, and campaign `Blizzard.j`:

```sh
python3 tools/wc3_retail_probe.py prepare \
  tools/retail_probes/purge_speed_floor/manifest.json /tmp/wc3-purge-speed-floor \
  --jhcr "$JHCR" --common-j "$COMMONJ" --blizzard-j "$BLIZZARDJ" \
  --jhcr-preload-path "$CUSTOM_MAP_DATA"
```

Load the prepared map once. The harness starts after the Intro Skipped trigger
starts Gameplay. To keep an existing Warcraft process alive, copy the prepared
map into a visible `Warcraft III/Maps/Probe/` folder, then use F10 → End Game →
Quit Mission (do not choose Exit Program), return to Single Player → Custom
Game, open `Probe`, select the map, and start it. Skip the opening cinematic
with Escape. This loads the prepared JHCR cookie into the same process and
resets the map's timer state.

A valid run has `PG_META`, `PG_SETUP`, `PG_CONFIG`, 440 samples, an accepted
Purge order, a matching spell-effect event, 400-speed control samples, and
`PG_DONE`, with no `PG_SETUP_FAIL`. Compare the first post-immobilize speed and
subsequent decay against the prior 300-speed curve. A first nonzero value of
150 at both baselines supports a 150-speed floor masking the underlying slow;
later steps show the recovery curve. Preserve the raw capture and matching
JHCR update record. Reload only passive logger functions; do not hot-reload
`PG_Tick`.

For a normal runner-launched map, use `capture` as documented in the JHCR
runbook. The runner currently requires its own `launch.json`; it cannot capture
a map loaded through the in-process Custom Game UI. For that path, copy the
result file to `evidence/retail-1292-runN.txt` immediately after completion,
before starting the next run, and write a matching JSON record with the run ID,
process/display, Retail build, raw result hash, sample/transition checks, and
JHCR sequence when applicable. The checked-in `evidence/` records show this
format. Do not infer success from a setup marker or JHCR status alone; require
all 440 samples and `PG_DONE`.

Avoid changing `PG_Start` through JHCR. In an earlier attempt, JHCR returned
status 1 and ran the changed setup, but the timer never produced samples. A
later update with the original body did not restore it because the body matched
the prepared baseline and was omitted from the payload. Bake setup changes into
a newly prepared map, or send an explicitly changed restoration function and
confirm its marker; loading a fresh map is the reliable reset.
