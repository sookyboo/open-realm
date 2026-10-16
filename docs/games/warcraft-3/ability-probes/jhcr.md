# JHCR hot reload on Warcraft III 1.29

Repeatable workflow for testing JASS updates in a live Warcraft III Retail
1.29.2.9231 process with [JHCR](https://github.com/lep/jhcr). It was verified
under Wine; it does not require Docker.

## Prefer JHCR for repeatable code iterations

When a compatible JHCR-instrumented test map is already loaded and the
experiment can be expressed by reloading its JASS functions, prefer JHCR over
rebuilding and relaunching Warcraft for each iteration. Keep the normal Retail
runner workflow for preparing/loading the map and recording evidence; JHCR
shortens the edit-run loop, but does not replace controls or result capture.
A newly prepared map cannot be injected into an arbitrary active map.

Make each probe rerunnable:

- Keep its manifest, source script, setup/scenario steps, and expected output
  together. Reuse the runner's prepared directory, JHCR state, and cookie for
  one loaded map; do not advance sequence state outside `jhcr-update`.
- Separate one-time setup from functions called by active timers/events. Prefer
  reloading a small logger or result formatter. Add a function to
  `jhcr_reloadable_functions` only after reviewing its runtime role; replacing
  a live callback has stalled a probe even when JHCR reported success.
- Record baseline and treatment runs with positive and negative controls.
  Change one hypothesis at a time, use unique run identifiers in output, and
  preserve raw results alongside a concise interpretation.
- For every reload, check status `1`, a newly changed marker, and completion
  of the expected probe. Then confirm control behavior and that timers/events
  continue. Status `1` alone only confirms payload application.
- Use `jhcr-update` for each compiled source revision, then trigger exactly
  one reload. A second reload without a matching update consumes the next
  sequence and produces `NO_DATA`.

If the active map or probe lifecycle is incompatible, prepare and load a map
with the Retail probe runner instead. JHCR is an iteration shortcut when its
preconditions fit, not a reason to force unrelated scenarios into a live map.

## Build and instrument the map once

Use the matching 1.29 `common.j` (`common-1.29.2.j`) and keep the JHCR state
file. State tracks the cookie, function map, and next sequence; use the same
state file for every `init` and `update` in this session.

```sh
git clone https://github.com/lep/jhcr /tmp/jhcr
cd /tmp/jhcr
cabal update
# Put common-1.29.2.j at the repository root.
COMMONJ=common-1.29.2.j PATCH_LVL=129 make clean build
JHCR="$(cabal list-bin jhcr)"
MAP_DIR=/path/to/extracted-map
BLIZZARD_J=/path/to/Blizzard.j
JHCR_STATE=/path/to/jhcr-129.bin

"$JHCR" init common-1.29.2.j "$BLIZZARD_J" "$MAP_DIR/war3map.j" \
  --jasshelper --state "$JHCR_STATE" --out "$MAP_DIR/jhcr_war3map.j"
```

Replace the map archive's `war3map.j` with `jhcr_war3map.j`, then load that
map. `Blizzard.j` and `war3map.j` must be the extracted files for that map;
pass every required JASS source to `init`, with `common.j` first and the map
script last. Repack/reload only when changing this instrumented script.

### Optional probe-runner integration

The Retail probe runner can initialize JHCR while it prepares an edited map.
Use the built JHCR program, matching 1.29 `common.j`, and that map's extracted
`Blizzard.j`:

```sh
python3 tools/wc3_retail_probe.py prepare MANIFEST.json /tmp/probe-run \
  --jhcr "$JHCR" --common-j /path/to/common-1.29.2.j \
  --blizzard-j /path/to/Blizzard.j \
  --jhcr-preload-path "$CUSTOM_MAP_DATA"
```

Preparation creates a per-probe `jhcr/state.bin`, instruments the edited
script, repacks the map, and verifies the embedded script. Load that prepared
map once. For each code change, compile the complete updated map script and
run:

```sh
python3 tools/wc3_retail_probe.py jhcr-update /tmp/probe-run /path/to/war3map.j
```

The command locks that probe's JHCR state during updates and requires exactly
one new or changed, nonempty `JHCR-<cookie>-<sequence>.txt` in `CustomMapData`.
Before invoking JHCR, it compares candidate function bodies with the
uninstrumented source saved during preparation. Only changed names listed in
the manifest's optional `jhcr_reloadable_functions` array are allowed. Unlisted
changes stop before JHCR runs, protecting active timer/event callbacks from
accidental replacement. The Shadow Strike probe allows `SS_Log` and blocks
`SS_Tick`. The comparison ignores formatting and `//` comments. This source
guard cannot prove an allowed function safe; add names only after assessing
their runtime role. Update JSON records changed names and
`reload_guard: passed`. Older prepared directories without a baseline need to
be prepared again with the current runner.

It writes a JSON record under `jhcr-updates/`. Trigger the map's reload action
(for example `-jhcr`) to consume the sequence. Keep using the same probe
directory for this loaded map; a new directory creates a new cookie and needs
its prepared map loaded. Pass `--preload-path` to `jhcr-update` if it was not
recorded at preparation. Avoid updating the same state concurrently outside
this command because JHCR advances the sequence as it writes the payload.

JHCR status `1` confirms payload application, not continued probe correctness.
In a live Shadow Strike run, changing active periodic callback `SS_Tick`
returned status `1` but stalled the timer. Updating only the logger `SS_Log`
allowed the probe to finish. Keep active callbacks out of the allowlist unless
there is a specific need and you verify the probe continues afterward.

Add a test trigger to the map before packing. Have it call
`ExecuteFunc("JHCR_Init_parse")` (in initialized output this may be
`JHCR_Wrap_ExecuteFunc(...)`), then display
`JHCR_API_GetLastStatus()` and a marker function. `ExecuteFunc` is important:
a direct JASS call to `JHCR_Init_parse()` failed static name resolution in our
test map. Registering a chat event such as `-jhcr` makes repeated manual runs
easy.

## Compile and apply each update

Edit the map's JASS source and compile it as usual to the updated
`war3map.j`. Then run:

```sh
CUSTOM_MAP_DATA="/path/to/Warcraft III/CustomMapData"
"$JHCR" update "$MAP_DIR/war3map.j" \
  --preload-path "$CUSTOM_MAP_DATA" \
  --jasshelper --state "$JHCR_STATE"
```

Use the same state file from `init`; do not recreate it between updates.
JHCR prints the sequence it wrote and creates
`JHCR-<cookie>-<sequence>.txt` in `CustomMapData`. Trigger one reload in the
already running map. Success is API status `1` plus the changed marker. Change
the marker and run `update` again to test another in-process reload; sequence
2 was verified after sequence 1 without restarting Warcraft.

JHCR statuses: `1` = update applied; `2` = no data for the expected sequence;
`3` = operation limit. An extra reload after success advances the expected
sequence, so status `2` is expected until an update for that next sequence is
compiled. Check both the marker and status for the same single reload; a later
empty retry can report `2` while the earlier marker remains updated.

## Wine path and 1.29 setting

Use the active Wine prefix. Resolve the real Documents path rather than
guessing it:

```sh
export WINEPREFIX=/path/to/active/prefix
wine cmd /c 'echo %USERPROFILE%'
winepath -u 'C:\Users\<user>\Documents\Warcraft III\CustomMapData'
```

Confirm the sequence file exists at that resolved path and that its cookie and
sequence match the JHCR output. Warcraft 1.29 needs **Allow Local Files** for
preloading; set it before launching the game because a running process may
cache the setting:

```sh
WINEPREFIX="$WINEPREFIX" wine reg add \
  'HKCU\Software\Blizzard Entertainment\Warcraft III' \
  /v 'Allow Local Files' /t REG_DWORD /d 1 /f
```

## Diagnose a `NO_DATA` result

Do not infer that `Preloader` failed just from status `2`: that status means
the runtime did not see the expected sequence in GameCache. First verify the
single reload, sequence, marker, state file, and file location.

- No expected-path lookup or `ENOENT`: fix the active prefix, Documents path,
  cookie/sequence filename, or 1.29 local-files setting.
- `NtReadFile = SUCCESS` but status `2`: inspect the generated file's
  `PreloadFiles` body and confirm it stores the expected sequence under cache
  `JHCR.w3v`, mission `seq`, key `0`. Avoid copying the file into more guessed
  folders.

For an already running process, attach `strace` only around one reload; tracing
from startup slowed map loading substantially in our run:

```sh
strace -f -p "$WARCRAFT_PID" -e trace=%file -s 256 \
  -o /tmp/jhcr-files.strace
# Trigger -jhcr once, then Ctrl-C to detach strace.
rg -n 'JHCR-|CustomMapData|ENOENT|EACCES' /tmp/jhcr-files.strace
```

For Wine's exact `CreateFileW`/`ReadFile` result, launch a short diagnostic
run with `WINEDEBUG=+file` and capture stderr:

```sh
WINEPREFIX="$WINEPREFIX" WINEDEBUG=+file wine Warcraft\ III.exe \
  -window -loadfile 'Z:\path\to\test-map.w3x' 2>/tmp/jhcr-wine-files.log
rg -n 'JHCR-|CustomMapData|NtReadFile|CreateFileW' \
  /tmp/jhcr-wine-files.log
```

Keep this capture short: `+file` is noisy and produced about 100 MB in nine
minutes in the verified run. A successful path check should resolve to
`C:\Users\<user>\Documents\Warcraft III\CustomMapData` and show
`NtReadFile = SUCCESS` for the expected sequence file. Failed probes under
the game install directory can precede a successful Documents-path read.

## Verified result

With `Allow Local Files=1`, Wine read sequence 1 (561 bytes) and sequence 2
(568 bytes) from the expected Documents `CustomMapData` directory. Both marker
updates applied in one live Warcraft process; the second reported status `1`.
The tested prefix was `/home/agent/.wine-war3`, resolving the directory to
`/home/agent/.wine-war3/drive_c/users/agent/Documents/Warcraft III/CustomMapData`.
The following retry looked for sequence 3 and correctly reported no data until
that update is generated. Evidence from the local run is under
`/tmp/jhcr-wc3-probe/` (`wine-files.log`, `preloader-live.strace`, and the
captured screenshots); those temporary files are not part of the checkout.
