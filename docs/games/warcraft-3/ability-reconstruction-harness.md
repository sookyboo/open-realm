# Warcraft III Retail ability reconstruction harness

For an **agent-facing step-by-step procedure** from rawcode to a reviewed
OpenRealm implementation spec, use the
[ability reconstruction agent playbook](ability-reconstruction-agent-guide.md).
This document is the technical reference and patch-by-patch CLI runbook;
older sections describe earlier milestones and are not a claim that native
logic or visual parity is automatically complete.

The long-term interface is `python3 tools/wc3_ability_re.py reconstruct Apxf`.
**Patch 2 is the rawcode lookup foundation, not a native-code reconstructor.**
It resolves *authored* ability rows through the project's existing SLK/DDX
`ability_audit` implementation. Native code, execution graphs, presentation
lifetimes, and runtime verification remain separate later stages.

## Local setup and discovery

Follow the repository root [AGENTS.md](../../../AGENTS.md) and
[CONTRIBUTING.md](../../../CONTRIBUTING.md); no proprietary data is committed.
The repository already provides `ability_audit`, a pinned exact-build
[Retail function inventory](ability-function-investigation.json), and an
extracted [TFT ability class reference](../../../games/warcraft-3/tft-ability-classes.txt).

Use `build-re/` as the standard location for generated reverse-engineering
evidence, Ghidra projects, caches, and reports. Git ignores this directory;
`build/` remains for compiled tools and normal build products.

```sh
make ability_audit
python3 tools/wc3_re/inventory.py
python3 tools/wc3_ability_re.py doctor
python3 tools/wc3_ability_re.py lookup Apxf --edition tft
python3 tools/wc3_ability_re.py lookup AOsw --edition both --format json \
  --output build-re/ability-re/serpent-ward-lookup.json
python3 tools/wc3_ability_re.py index
python3 tools/wc3_ability_re.py reconstruct Apxf
python3 -m unittest discover -s tests -p 'test_wc3_ability_re.py'
```

By default the tool expects `build/bin/ability_audit` and the user's
`data/Warcraft III` directory. Override with `--audit` and `--data-dir`.
For this repository, `data/Warcraft III/` is the standard local location for
the installed Retail data: `Warcraft III.exe`, `War3.mpq`, `War3x.mpq`, and
their locale archives. Keep these local/proprietary files out of commits. Run
Retail with that directory as its working directory so the executable resolves
its archives; a Wine prefix is for the user's registry, Documents, and other
writable state, not a second copy of the game data.

Use this location map for repeatable runs:

| Input or output | Standard location |
|---|---|
| Retail executable and archives | `data/Warcraft III/` |
| Ghidra projects | `build-re/ghidra-projects/` |
| Ghidra user settings and temporary files | `build-re/ghidra-user/` and `build-re/ghidra-tmp/` |
| Ability lookup, exports, graphs, assets, traces, scenarios, sessions, reports | `build-re/ability-re/<rawcode>-<run-id>/` (or a named child directory) |
| Compiled tools and ordinary build products | `build/` |
| Wine registry, user profile, and writable game state | The selected `$WINEPREFIX`; do not copy the game installation there |
| JASS result files and prepared maps needed by Retail | Under the active Wine profile's `Documents/Warcraft III/CustomMapData/` and `Maps/Probe/` |

Resolve the Wine profile from the environment or the active launch record; do
not copy machine-specific absolute paths into checked-in scenario specs. For
example, set `WINEPREFIX` for commands that launch Retail and use
`winepath -u 'C:\\users\\<user>\\Documents\\Warcraft III\\CustomMapData'`
to obtain the host path for a case manifest. Store the generated manifest,
map-preparation record, launch record, Frida plan, and captured outputs under
the corresponding `build-re/ability-re/` run directory. Use a new run ID and
output directory for each immutable capture. Temporary files should also live
under `build-re/`, not scattered `/tmp` locations, unless a tool requires a
specific external writable directory.

For live Retail experiments, use **640×480 for both the X11/Xvfb screen and
the Warcraft III game resolution**. Set the Retail `Video\reswidth` and
`Video\resheight` values to 640 and 480 in the selected Wine prefix before
launching, and start Xvfb with a 640×480 screen. Keep the same `DISPLAY` and
`XAUTHORITY` in the Wine, Frida-server, and input-tool environment. Do not rely
on a centered 640×480 game viewport inside a larger X screen: UI coordinates
and scripted input can then target the wrong location. Verify the Retail
window geometry before using mouse coordinates. The [JHCR runbook](ability-probes/jhcr.md#resolution-and-mouse-input)
has the registry commands and display checks.

For native address work, pass `--executable 'data/Warcraft III/Warcraft III.exe'`;
the command refuses a hash different from the pinned inventory. An omitted
executable is **not** considered checked. A valid inventory or class table
alone does not prove that any address is executable or reachable.

`doctor` reports which local inputs are present and whether lookup is ready.
`lookup` fails for missing data/tools, bad rawcodes, or inconsistent JSON.
The `--edition both` mode performs independent ROC and TFT lookups and reports
absence separately; it does not silently fall back from one edition to another.
Missing object data is not a negative Retail gameplay result.

## AbilityData JSON export

`ability_audit -tft -json -raw Apxf -data 'data/Warcraft III'` outputs
one JSON object with `schema_version=1`, `edition`, `rawcode`, `found`,
archive candidates, metadata (`id`, `code`, `uber_alias`, rank count),
per-rank targeting/cost/cooldown/range/duration/cast/data A-I, unit/effect/buff
identities, available string data, linked buffs/art and other authored aliases.
`wc3_ability_re.py lookup` narrows that archive list to the selected edition;
in particular, ROC presentation resolution excludes `War3x`/Frozen Throne
overlays even though `ability_audit` reports all discovered archive candidates.
Four-character data slots are tagged `rawcode` rather than forced to a float.
The current underlying `AbilityData_t` schema exports up to four ranks;
`levels` separately reports the authored count. The export is intentionally
not a comprehensive presentation resolver or a full variable-length rank
parser. Do not fill unsupported ranks with copies of rank 4.

The exported `ability.code` is the authored implementation code. It is
not automatically replaced with `uber_alias`, and the requested rawcode
is preserved. `retail_class_reference` resolves that code against the saved
TFT `tft-ability-classes.txt` **only in TFT mode**. For example, stock
Serpent Ward `AOsw` may resolve through `AOwd` to `CAbilityWard`; this is
labelled `offline_reference_hint`, not a confirmed factory/vtable binding.
The lookup preserves the audit's raw quote-stripped `strings` object and adds
`strings_by_rank`, which splits quoted rank lists into authored per-level
strings without mutating the source. Malformed rank lists fail closed. The `index`
command writes a *class reference* index, not a Ghidra index.

`reconstruct` currently creates only `lookup.json` and `manifest.json`
under `build-re/ability-re/<rawcode>/`; its `status` is `seed_only` and it lists
pending Ghidra, graph, presentation, verification and specification phases.
It refuses to overwrite an existing output directory. `verify` exits with
code 3 and a clear not-implemented message until runtime orchestration exists.
No generated report claims exact ability behavior on Patch 2 alone.

## Evidence and testing rules

- Use the correct ROC/TFT source and retain both authored `rawcode` and `code`.
- Preserve executable hashes and tool/source paths in JSON output. The audit's
  archive list reports discovered sources, not per-row provenance or full MPQ
  hashes. Runtime claims require source-linked Ghidra/Frida/JASS evidence.
- Prefer structured `ability_audit` output to parsing its human-readable
  report. Keep existing human output and `-resolve-tooltip` unchanged.
- Run offline tests without Retail archives by mocking the audit's JSON
  boundary; integration with proprietary MPQs is a separately run local check.
- Don't confuse authoring fields or a tooltip with verified game effects or
  animation timing. Later patches must preserve these boundaries.

## Patch 3: exact-build headless Ghidra static export

Patch 3 adds `tools/ghidra/Wc3AbilityExport.java` (Ghidra 12.1.4 Java script)
with a Python launcher/validator in `tools/wc3_re/ghidra.py`. This is **not**
a complete ability-specific execution graph: Patch 4 will traverse the export
and associate the correct class/factory/receiver with the requested rawcode.
`reconstruct Apxf` remains the lookup-only seed command from Patch 2.

Always use the *same* Retail executable as the inventory: 1.29.2.9231, PE32
little-endian x86, preferred image base `0x00400000`, SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.
`ghidra-export` checks the file hash before starting headless Ghidra; the
Java script independently checks the imported program's hash, language and
image base **before writing any output**. A different binary requires its
own separately reviewed research inventory and export.

### One-time import and metadata scan

Create a project parent directory and set local paths as needed. In a
container with a small home or temporary filesystem, keep the launcher cache on
the same workspace mount before importing:

```sh
mkdir -p build-re/ghidra-user build-re/ghidra-tmp
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:+$JAVA_TOOL_OPTIONS }-Duser.home=$PWD/build-re/ghidra-user -Djava.io.tmpdir=$PWD/build-re/ghidra-tmp"
```

```sh
mkdir -p build-re/ghidra-projects
GHIDRA_HEADLESS=/path/to/ghidra_12.1.4_PUBLIC/support/analyzeHeadless
RETAIL_EXE="$PWD/data/Warcraft III/Warcraft III.exe"
python3 tools/wc3_ability_re.py ghidra-export \
  --headless "$GHIDRA_HEADLESS" \
  --project-dir build-re/ghidra-projects --project-name WC3Retail1292 \
  --executable "$RETAIL_EXE" --import-first --mode scan \
  --output build-re/ability-re/ghidra/scan-initial
```

`--import-first` creates and analyzes a **new** Ghidra project and refuses a
pre-existing `.gpr` project. This initial import persists the analyzed
program, unlike subsequent read-only exports. Existing analyzed projects
should omit `--import-first`; the launcher uses `-process ... -noanalysis
-readOnly` to avoid modifying the database. `scan` exports the complete
analyzed function inventory plus instruction-level call/data references; it
**does not decompile every function**. Ghidra must already have completed
function discovery for that project; an empty function scan is rejected.

### Targeted decompilation and vtable candidate export

```sh
python3 tools/wc3_ability_re.py ghidra-export \
  --headless "$GHIDRA_HEADLESS" \
  --project-dir build-re/ghidra-projects --project-name WC3Retail1292 \
  --executable "$RETAIL_EXE" --mode detail \
  --rva 0x0080d820 --rva 0x0080ecd0 --rva 0x0080f1e0 \
  --output build-re/ability-re/ghidra/phoenix-fire-detail

# Or use only explicitly typed inventory function/vtable entries as seeds:
python3 tools/wc3_ability_re.py ghidra-export \
  --headless "$GHIDRA_HEADLESS" \
  --project-dir build-re/ghidra-projects --project-name WC3Retail1292 \
  --executable "$RETAIL_EXE" --mode detail --inventory-seeds \
  --output build-re/ability-re/ghidra/inventory-detail

# Check an export independently without running Ghidra:
python3 tools/wc3_ability_re.py ghidra-check \
  build-re/ability-re/ghidra/phoenix-fire-detail --mode detail
```

Each export is an immutable, new directory; repeated exports require unique
paths. It contains `invocation.json` and `ghidra.log` and the following
JSONL streams:

| Output | Meaning |
|---|---|
| `functions.jsonl` | Function entries, signatures, namespaces, thunk hints, body boundaries |
| `callsites.jsonl` | Instruction call references and unresolved computed/indirect calls, with instruction RVAs |
| `datarefs.jsonl` | Non-flow instruction references; **not** call edges or proven field semantics |
| `decompiled.jsonl` | Ghidra C-like text with requested RVA, actual function RVA, success/failure |
| `pcode.jsonl` | High p-code operations with instruction location and textual varnodes; no inferred state writes |
| `vtables.jsonl` | Explicitly seeded sequences of pointers to executable memory and references to table seed |

`export-summary.json` is written **last** on successful completion; the CLI
checks every JSONL row and record count, hash, base, architecture and mode.
Do not treat an incomplete output directory as a valid export. A decompiler
failure becomes an explicit failed row, not invented native code. A seed
inside an existing analyzed function identifies that containing function in
the output; an unknown seed appears in `unresolved_seeds`.

Vtable scans deliberately produce `pointer_table_candidate_only` records.
Pointer sequences are not enough to prove a C++ class, virtual-call slot or
receiver identity. `unresolved_indirect_call` and `CALLIND` are not assigned
callees. No `related_addresses` mention or generic inventory `call` is
promoted to an observed direct call. Per-ability class mapping and graph
traversal arrive in Patch 4, and observed runtime dispatch in Patch 7.

Offline adapter regression tests (no Ghidra, game data or Wine required):

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_ghidra.py'
```

The Java exporter must be exercised against your local Ghidra installation;
this repository's offline tests validate only Python launch/format contracts.

## Patch 4: bounded static ability execution graphs

Patch 4 adds `tools/wc3_re/graph.py`. The **one-time** Patch 3 Ghidra scan is
reused for subsequent abilities. Graph generation itself never launches
Ghidra, Wine or Retail. To obtain actual pseudocode, provide one or more
Patch 3 `detail` exports; `scan` alone contains function metadata and calls,
not decompiled bodies.

```sh
# First make a Patch 2 lookup (requires installed matching object data).
python3 tools/wc3_ability_re.py lookup Apxf --edition tft --format json \
  --output build-re/ability-re/Apxf-lookup.json

# Use cached Ghidra exports; no new game launch or decompilation.
python3 tools/wc3_ability_re.py ability-graph Apxf \
  --lookup build-re/ability-re/Apxf-lookup.json \
  --scan build-re/ability-re/ghidra/scan-initial \
  --detail build-re/ability-re/ghidra/phoenix-fire-detail \
  --output build-re/ability-re/Apxf-static-graph

# When a native binding is not in the curated labels, specify exact seeds.
python3 tools/wc3_ability_re.py ability-graph Apxf \
  --scan build-re/ability-re/ghidra/scan-initial \
  --seed-rva 0x0080d820 --no-auto-seeds \
  --output build-re/ability-re/Apxf-handler-graph

# Alternatively include the graph in a newly created reconstruction package:
python3 tools/wc3_ability_re.py reconstruct Apxf --edition tft \
  --ghidra-scan build-re/ability-re/ghidra/scan-initial \
  --ghidra-detail build-re/ability-re/ghidra/phoenix-fire-detail \
  --output-dir build-re/ability-re/Apxf-package
```

`ability-graph` does not require installed retail MPQs or `ability_audit`
**if** its lookup JSON has already been generated or function RVA seeds are
provided explicitly. When the lookup provides a class hint, the tool searches
*curated inventory function labels only* for matching whole class-name or
rawcode tokens, selects their **typed function entry addresses**, and labels
them `curated_label_match_only`. These are merely candidate entry points; a
class name from `tft-ability-classes.txt` alone is not proof of a factory or
runtime receiver. With an exact-build lookup and matching executable, the
graph can also use the extracted registration's factory, destroy and pool
callback file offsets. It translates offsets through the PE section table,
requires a unique matching Ghidra function body, and records each as a
`high_static_registration_candidate`; runtime dispatch remains unproven.
Exact-build references from Ghidra to class/RTTI strings are separately labelled
medium-confidence candidates. A stale class table, ambiguous function mapping,
or unsupported build contributes no registration seeds. Unknown/missing seeds
fail closed. Use `--no-auto-seeds` with `--seed-rva` for precisely scoped graph
reviews.

When a validated detail export contains a candidate vtable and a selected
exact-build registration callback has a Ghidra data reference to that table,
the graph keeps its function-entry slots in `vtable_method_candidates` with
table RVA, slot offset, source export and an explicit candidate confidence.
These methods are surfaced in the review report and considered by bounded
trace-plan prioritization when they are graph nodes. They are not call edges,
do not expand traversal, and do not establish dynamic receiver identity or
runtime dispatch. Use them to choose targeted detail exports or bounded hooks
for a hypothesis-driven experiment.

The output is a **new** directory; existing output is never overwritten:

| File | Content / evidence limits |
|---|---|
| `execution-graph.json` | Visited functions, depth, typed relationships, independent source records, unresolved calls, vtable *candidates* and truncation/gaps |
| `native-code.json` | C-like decompiler text only for functions actually exported in `detail`; missing or failed bodies stay missing/failed |
| `data-references.json` | Ghidra static data xrefs for visited functions; no inferred state-field or presentation meaning |
| `memory-access-candidates.json` | Untyped `LOAD`/`STORE` p-code sites; these are not identified object fields or proven gameplay state writes |
| `branch-candidates.json` | Uninterpreted `CBRANCH`/`BRANCHIND` p-code sites for targeted manual review |
| `review.md` | Small review report with addresses, evidence boundaries and missing decompilations/dispatch |

Traversal follows Ghidra **static** calls, static thunk hints, and the
inventory's documented `direct_call`/`callback_dispatch` relations when both
endpoints are known analyzed functions. It does **not** follow generic `call`,
`virtual_dispatch`, `related_call_path`, computed call targets, unknown
function targets, or `related_addresses` mentions. Candidate relations are
preserved in the output with their original contexts but do not count as
traversed runtime execution. Duplicate relationships retain every independent
evidence record. Unbound vtable pointer sequences retain a distinct candidate
status; no receiver or class membership is inferred.

Default exploration is depth 4, at most 120 visited functions and 1,000
logical edges. Configure `--max-depth`, `--max-nodes`, `--max-edges`; hard
ceilings prevent inadvertently expanding the whole engine. A truncated graph
reports frontier omissions instead of claiming completion. No `STORE` or
branch p-code instruction is automatically converted to a named field or an
established branch outcome. The scan is the reusable function/metadata cache;
future detail exports can be added without rerunning it.

Run the offline regressions:

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_graph.py'
```

**Still pending:** verified factory/class-to-vtable binding, comprehensive
indirect dispatch resolution, executable state-field semantics, runtime animation/effect selection (Patch 7+), Frida/JASS correlation (Patches 7–10), and an exact
implementation-ready code specification (Patch 11). A graph is a map of
static possibilities, not a proof that any cast executed every edge.


## Patch 5: authored presentation and static MDX dependencies

Patch 5 adds `tools/wc3_re/presentation.py` and extends the existing
`ability_audit -json` and `mdxtool --info` interfaces. This stage **does not
reconstruct a verified runtime visual timeline**: the data identifies *possible*
art/sound sources; native code and, where necessary, tracing establish the
actual effects, attachment points, sequence choice, and when they fire.

```sh
make ability_audit mpqtool mdxtool
python3 tools/wc3_ability_re.py lookup Apxf --edition tft --format json \
  --output build-re/ability-re/Apxf-lookup.json
python3 tools/wc3_ability_re.py ability-presentation \
  --lookup build-re/ability-re/Apxf-lookup.json \
  --output build-re/ability-re/Apxf-presentation

# Reconstruct also writes presentation/assets.json and presentation/review.md:
python3 tools/wc3_ability_re.py reconstruct Apxf --edition tft \
  --output-dir build-re/ability-re/Apxf-with-presentation

# Analyze one model without SDL/OpenGL and without extracting asset files:
build/bin/mdxtool -mpq 'data/Warcraft III/War3x.mpq' \
  -model 'Abilities\\Spells\\Other\\SomeSpell\\SomeSpell.mdx' --info-json
```

`--no-asset-inspection` skips archive/MDX queries, retaining authored references
only. `ability-presentation` can run solely from an existing Patch 2 `lookup.json`
and needs no Ghidra, Wine, Frida or Retail executable. It respects the lookup's
edition-specific archive list, searches those archives only, and records the
archive satisfying each resolved path; it does not accidentally take a TFT model
from a global all-edition asset search during a ROC investigation.
ROC filtering classifies supported expansion archive basenames (`War3x*.mpq`
and known Frozen Throne archive names), never arbitrary parent-directory text.
SLK overlay resolution follows the existing tool loader: it selects the first
matching whole table in archive priority order. It does not merge missing rows
from lower-priority copies of an SLK, and `table_archive` records that selected
file's source.

The enhanced audit reads `*AbilityFunc.txt` keys separately from localized
`*AbilityStrings.txt`, exposes BuffID and EfctID presentation rows from
`AbilityBuffData.slk`, and retains rank links to `UnitID`/BuffID/EfctID. For a
rank `UnitID`, the resolver follows the matching `Units\\UnitUI.slk` row,
records its authored fields and archive, and inspects its model with the same
bounded MDX dependency traversal. This is an authored data dependency, not
proof that the ability spawns or plays the model at a particular time.
Missing or unsupported authoring fields remain `null` rather than being
filled with likely paths. The bounded `mdxtool --info-json` command returns
sequence names/intervals, texture paths and replaceable IDs, chunk presence,
and supported `EVTS` keyframe events (including SND/SPN/SPL/FPT/UBR names).
EVTS event nodes are size-prefixed; the decoder validates that prefix and the
full node/keytrack bounds before emitting events. A malformed or unsupported
track leaves the event payload undecoded instead of guessing its layout.
Unsupported/corrupt event payloads are **not guessed**; the exporter marks
them undecoded.

For supported event nodes, the resolver consults `AnimLookups.slk`,
`SpawnData.slk`, `SplatData.slk` and `UberSplatData.slk`; SPN child model
references are followed with a depth/model budget. Ability sound aliases
consult `AbilitySounds.slk`, retaining authored `FileNames`, `DirectoryBase`,
pitch/volume and other fields without asserting which variant plays. Event
sound aliases from SND nodes resolve through the animation lookup, but their
source is distinct from ability effect sounds. Archive members, models, audio,
and other proprietary data are not written to the source tree.

The independent output has `assets.json` and `review.md`. Within
`assets.json`, each reference identifies its source row, field, rank (where
applicable), original value, normalized path and evidence kind. Models contain
nested event dependencies and available metadata; missing rows/assets and
traversal budgets remain visible as gaps. The generated `review.md` is **not**
a validated animation timeline.

Limitations: ability-specific display/attachment selection, sequence transitions,
impact timing, status-effect lifetime, custom map object overrides, animation
variation/pitch runtime selection, and exact presentation synchronization.
AbilityFunc `Art` is treated as an icon/texture, never as a spawned 3D model.
The current audit exports at most the four ranks supported by its decoded
AbilityData structure, so higher ranks remain unresolved. Native-call evidence
from the Patch 4 graph and Frida from Patch 7 are needed to classify which
presentations execute and with what timing.

Synthetic offline tests (no installed retail assets) are in:

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_presentation.py'
```

Run the three tools against your installed Warcraft data locally to validate
the game archive and C diagnostic-tool integration; that integration was not
exercised by the Python mock-only tests.

## Patch 6: offline reconstruction bundle from cached evidence

Patch 6 introduces `tools/wc3_re/package.py`, which joins the previous
stages into a single **offline, static-evidence report**. It does not
invent ability logic, convert untyped p-code into semantic state fields, or
claim observed animation/effect timing. The input lookup must match the graph
rawcode and pinned Retail SHA-256, and its available editions must match the
presentation report. A mismatch fails before an output directory is created.

```sh
# All stages in one command, provided local audit, MPQ tools and cached Ghidra
# scan/detail outputs are available. This NEVER launches Retail or Ghidra.
python3 tools/wc3_ability_re.py reconstruct Apxf --edition tft \
  --ghidra-scan build-re/ability-re/ghidra/scan-initial \
  --ghidra-detail build-re/ability-re/ghidra/phoenix-fire-detail \
  --output-dir build-re/ability-re/Apxf-offline

# Or repackage already exported evidence, without ability_audit, MPQ tools,
# installed Warcraft data, Ghidra, Wine, or Frida. All three inputs are
# immutable Patch 2 / Patch 4 / Patch 5 artifacts; --graph and --presentation
# can be omitted for a lookup-only partial report.
python3 tools/wc3_ability_re.py ability-package \
  --lookup build-re/ability-re/Apxf-offline/lookup.json \
  --graph build-re/ability-re/Apxf-offline/graph \
  --presentation build-re/ability-re/Apxf-offline/presentation \
  --output build-re/ability-re/Apxf-offline-review
```

`reconstruct` also writes `offline/` inside its new output directory.
`ability-package` writes the same content directly to a new directory:

| Output | Content / interpretation |
|---|---|
| `report.md` | Authored class/rank summary, functions available, model/audio dependency counts, and open questions |
| `coverage.json` | Evidence-presence dimensions and counts; **not** a Retail parity percentage |
| `dependencies.json` | Graph nodes, original relationship **evidence arrays**, static data references, untyped memory/branch candidates, unbound vtables and rank-linked presentation metadata |
| `questions.json` | Unresolved native, presentation and timing questions with their source and suggested next action |
| `native/decompiled.c` | Only successful Ghidra decompiled C-like bodies with function RVA and export provenance; never fabricated implementation code or original Blizzard source |
| `provenance.json` | Pinned Retail executable SHA-256, canonical SHA-256 digests of the three input objects, and Ghidra input paths |
| `README.md` | Local index for the package |

All report files are reproducible for identical input objects and refuse to
overwrite existing output. The bundle is suitable for native/presentation
review and follow-up prioritization, **not yet** a verified behavior spec or
portable C implementation. Patch 7 adds targeted runtime dispatch evidence;
Patch 11 builds a full implementation-oriented spec from settled semantics.

Offline regression tests (synthetic fixtures only):

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_package.py'
```

## Patch 7: generated read-only Frida function-entry traces

Patch 7 adds `wc3_re/frida.py` and a Frida 17 agent template. The input is a
saved **Patch 4 graph directory**. It does not need installed MPQs, Ghidra, or
the Retail executable to generate the agent, because the graph pins the exact
executable SHA-256. Pass `--executable` to independently verify that the file
installed locally matches the pinned build before planning. Its purpose is
**observing candidate function entry/exit execution**, not reconstructing
argument types, assigning an unbound vtable to a class, or proving an ability
was responsible for an observed call.

```sh
python3 tools/wc3_ability_re.py ability-trace Apxf \
  --graph build-re/ability-re/Apxf-offline/graph \
  --capture-id phoenix-probe-01 --max-hooks 24 \
  --max-events 1200 --per-hook-events 120 --seconds 60 \
  --output build-re/ability-re/Apxf-trace-plan-01
```

The new output directory contains `trace-plan.json` (complete graph-derived
selection and review-only unresolved dispatch sites), `agent.js` (read-only,
bounded Frida script), and `review.md` (interpretation limits). Explicit
`--include-rva 0x0080ecd0` can prioritize a function **only if it is already
in the saved graph**. The selection algorithm prioritizes explicit RVAs,
curated seeds, unresolved call owners, then nearby shared functions. Omitted
functions, candidate vtables, and unresolved callsite RVAs are preserved for
review; **the generator never hooks an arbitrary indirect call instruction**
or assumes that a raw ECX register is a confirmed `this` pointer.

For a selected function that is called frequently by unrelated engine paths,
`--include-return-address FUNCTION_RVA=RETURN_RVA` filters its events to the
listed in-module callers before they consume the event budget. For example,
Serpent Ward's position fallback can be limited to calls returning into its
validator with `--include-return-address 0x003f6a00=0x00834133`. Choose these
return addresses from a matching-build trace and corroborate the corresponding
caller in static disassembly. The filter narrows observation; it does not
prove that caller arguments, receiver identity, or gameplay meaning are known.
The normalized hook plan and agent retain the filter, and unmatched calls do
not count toward per-hook or total event limits.

Each entry/exit event records the function RVA, invocation ID, thread/depth,
raw `ECX`/`EDX`/`ESP`/`EIP`, caller *return-address* RVA where inside the
Retail module, and raw return value. Use `--stack-words N` (0–8) to read raw
stack pointers only when necessary; they are not typed/decoded ABI parameters.
The agent starts armed so it works with the existing attach-only controller;
it also exposes Frida RPC `arm`, `disarm`, `status`, and `setrunid` for the
Patch 8 session coordinator. It stops emitting after its bounded duration,
per-hook cap or total event cap. An event/hook limit leaves incomplete data,
not negative evidence. The host/controller also has its own duration bound.

**Run only against an already prepared, confirmed Retail map**, with the
existing `tools/frida/trace_wc3_retail.py` controller present in the checkout
and its matching Frida client/server setup. The archived Oct 14 repo may not
contain that later controller; if it is absent, the bridge fails explicitly.
Its original documented command works with the generated `agent.js` too.

```sh
python3 tools/wc3_ability_re.py ability-trace-run \
  --plan build-re/ability-re/Apxf-trace-plan-01 \
  --probe-dir build-re/ability-re/Apxf-prepared-probe-01 \
  --seconds 60 --output build-re/ability-re/Apxf-frida-01.jsonl

python3 tools/wc3_ability_re.py ability-trace-review \
  --plan build-re/ability-re/Apxf-trace-plan-01 \
  --trace build-re/ability-re/Apxf-frida-01.jsonl \
  --output build-re/ability-re/Apxf-frida-review-01.json
```

The controller validates the live Retail process and prepared-map SHA,
checks the agent's embedded `WC3_RETAIL_SHA256`, and saves its raw JSONL. The
review checks matching executable and agent fingerprints from the controller's
`trace-metadata` record, a completed `trace-end`, the agent `start`, and any
Frida errors or truncation. It reports **raw native reachability only**:
`bounded_native_trace`, `partial_native_trace`, or
`inconclusive_trace_setup`; never a gameplay pass. Captures in the first two
states still require matching an accepted JASS scenario and identifying
receiver/ABI semantics before making ability-specific claims. Preserve the raw
JSONL; no script modifies or overwrites it. No actual game instrumentation is
performed by generation or the offline tests.

Run focused offline regressions (synthetic graphs; no Frida or game data):

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_frida.py'
```

**Known limits:** A function-entry trace cannot directly reconstruct an
indirect CALL target, classify a register as an argument, or identify a state
field. It provides evidence to choose the next small receiver-filtered or
callsite-specific reviewed trace. Runtime session automation, JASS correlation
and automatic question-driven reruns are Patches 8–10.

## Patch 8: persistent Retail session coordination

Patch 8 introduces `tools/wc3_re/session.py` and the `ability-session-*`
commands. They **do not launch Retail or prepare a JASS map**. The requirement
is a running **previously validated, prepared** map with `probe.json` and a
matching prepared `launch.json` produced by the newer retail probe runner.
The Patch 7-generated `trace-plan.json` and `agent.js` must be unchanged.
Use a local Frida Python client and a matching `frida-server.exe` under the
same Wine prefix. Neither is downloaded by the harness.

This coordinator uses a direct Frida remote session; it does **not** require
`tools/frida/trace_wc3_retail.py`, which is absent from some older checkouts.
It verifies pinned executable and prepared-map file hashes, the launch record,
a matching active Wine host command line and unique Frida process before
attachment. If Linux Wine and Frida report different PIDs, the coordinator
additionally requires a unique localhost Frida server in the same Wine prefix;
otherwise it fails closed instead of guessing the mapping. The compatible Retail executable remains SHA-pinned to
the Patch 7 graph, and the generated JS checks x86 executable page addresses.

Create a case manifest outside the repository, for example:

```json
{
  "cases": [
    {
      "run_id": "phoenix-300",
      "result_file": "/path/to/Wine/Documents/Warcraft III/CustomMapData/phoenix-300.txt",
      "timeout_seconds": 45,
      "required_markers": ["accepted=true"],
      "inconclusive_markers": ["accepted=false", "setup_failed=true"]
    },
    {
      "run_id": "phoenix-650",
      "result_file": "/path/to/Wine/Documents/Warcraft III/CustomMapData/phoenix-650.txt",
      "timeout_seconds": 45,
      "required_markers": ["accepted=true"],
      "inconclusive_markers": ["accepted=false", "setup_failed=true"]
    }
  ]
}
```

Each **already installed JASS scenario** must write a fresh `PreloadGen`
result using that distinct filename, including both exact strings
`SESSION_START run_id=phoenix-300` and
`SESSION_DONE run_id=phoenix-300` (substitute the case's run ID). Emit
`SESSION_DONE` only after all timed callbacks and observations are complete;
mark setup failures as inconclusive. For an order case, put `accepted=false`
in `required_markers` only when that case is an explicitly expected rejection;
otherwise put it in `inconclusive_markers`. A case result without the
proper unique start/done pair, fresh modification timestamp and required
markers cannot pass the capture-readiness gate. The Patch 8 runner **does not
automatically generate JASS scenarios or click through map UI**. Trigger the
prepared scenario at the announced run ID; Patch 9 will automate generic
ability scenario construction and input control.

Patch 9 manifests declare `acceptance_semantics` and
`expected_order_accepted`. For active abilities, the JASS `accepted` marker is
the return value of its `Issue*Order` call; it is separate from native
validation return codes, spell/effect events, and observed spawned units. An
intentionally rejected order is a successful negative-control capture when
the expected `accepted=false` marker, setup/completion markers, fresh result,
and required native evidence are all present. A cast intended to succeed but
rejected is an expectation mismatch. `UNIT_COUNT` and `UNIT` rows provide
independent, bounded JASS observations; do not infer summon creation from the
order return alone.

```sh
python3 tools/wc3_ability_re.py ability-session-create \
  --plan build-re/ability-re/Apxf-trace-plan-01 \
  --probe-dir build-re/ability-re/Apxf-prepared-probe-01 \
  --cases build-re/ability-re/Apxf-lab-01/lab-session-cases.json \
  --output build-re/ability-re/Apxf-session-01

python3 tools/wc3_ability_re.py ability-session-check \
  --session build-re/ability-re/Apxf-session-01

python3 tools/wc3_ability_re.py ability-session-run \
  --session build-re/ability-re/Apxf-session-01 --remote 127.0.0.1:27043
```

The session attaches **once**, then loads a fresh *initially disarmed* copy of
the immutable Patch 7 agent per case. Arming resets its bounded time/event
budget; the underlying Retail process stays running. The agent adaptation
changes only the initial `let armed = true;` declaration in memory; both the
original and adapted JS hashes are recorded in each `trace.jsonl`. Frida RPC
sets the run ID, arms, waits for the corresponding complete JASS output,
disarms and unloads. No memory writes, spawning, hot reloading, or game
manipulation is performed by this coordinator. JHCR `state.bin` and original
baseline presence are verified when the prepared probe declares JHCR; only
previously reviewed allowlisted updates through the existing runner should be
performed, **not by** this session controller.

Per-case immutable outputs are `<session>/<run-id>/trace.jsonl`, optional
`result.txt`, and `review.json`. `run-summary.json` records readiness across
all cases. On missing/different process identity, changed hash, Frida error,
stale/mismatched JASS result, agent event overflow, truncation, timeout, or
missing completion marker, the affected case is **inconclusive** and later
cases are not attempted. Reusing an output directory is forbidden; create a
new session for a new run. `ready_for_review` confirms capture integrity only;
it **does not mean Retail gameplay, animation, buff lifecycle or ability
receiver identity has been proven**. Correlating semantic results belongs to
Patches 9–11.

Offline-only regression checks:

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_session.py'
```

## Patch 9: reusable JASS ability laboratory scenarios

`tools/wc3_re/scenarios.py` creates *offline* JASS fragments and a Patch 8
`lab-session-cases.json` from a declarative scenario specification. It does not
launch Retail, compile JASS, prepare a map, type chat, simulate the native ability,
or prove visual/runtime semantics. It deliberately does not infer the order string
from the ability rawcode; consult edition-matched `Units/*AbilityFunc.txt` and the
existing [Retail probe workflow](retail-camera-tracing.md) before configuring
an active ability.

Example `phoenix-lab.json` (replace positions with safe open ground on the
selected map and replace `result_dir` with the active Wine profile's real
`CustomMapData` directory):

```json
{
  "schema_version": 1,
  "rawcode": "Apxf",
  "chat_player": 0,
  "result_dir": "/absolute/path/to/Wine/Documents/Warcraft III/CustomMapData",
  "cases": [
    {
      "run_id": "phoenix-300",
      "kind": "passive",
      "caster": {"unit_id": "hfoo", "player": 0, "x": 0, "y": 0},
      "targets": [{"unit_id": "hfoo", "player": 12, "x": 300, "y": 0}],
      "ability_level": 1,
      "duration_seconds": 3,
      "sample_interval_seconds": 0.25
    },
    {
      "run_id": "phoenix-650",
      "kind": "passive",
      "caster": {"unit_id": "hfoo", "player": 0, "x": 1500, "y": 0},
      "targets": [{"unit_id": "hfoo", "player": 12, "x": 2150, "y": 0}],
      "duration_seconds": 3,
      "sample_interval_seconds": 0.25
    }
  ]
}
```

The example is **not** a confirmed executable Phoenix Fire probe: the chosen
caster type, target type, coordinates, and active map must be checked against
Retail, and a regular combat or map event may confound measured life changes.
Stock and custom Hero abilities may require `learn_mode: "hero_skill"` with an
explicit `hero_level` rather than the default `unit_add` path.

```sh
python3 tools/wc3_ability_re.py ability-scenarios Apxf \
  --spec /path/to/phoenix-lab.json \
  --output build-re/ability-re/Apxf-lab-01
python3 -m unittest discover -s tests -p 'test_wc3_re_scenarios.py'
```

Outputs:

| File | Meaning |
|---|---|
| `lab-plan.json` | Fully validated inputs with normalized per-case units/tick budgets |
| `lab-globals.j` | Declarations to add inside **the existing** `globals` block |
| `lab-functions.j` | Stable JASS helpers, reset/capture callbacks and a chat-driven case dispatcher |
| `lab-session-cases.json` | Drop-in `--cases` input to `ability-session-create` |
| `README.md` | Exact chat commands and case/sample overview |
| `lab-probe.json` | Optional: existing probe-runner map-preparation manifest if `map` hooks are specified |

The optional `map` object requires `archive`, `member`, `retail_executable`,
`hook_function` (a `takes nothing returns nothing` map function), and exact
whole-line `hook_anchor`. It accepts `hook_where` (`after` default or `before`)
and `edition` (`tft` default or `roc`). The archive and executable must be
absolute paths. Example:

```json
"map": {
  "archive": "/absolute/path/to/War3xLocal.mpq",
  "member": "Maps/FrozenThrone/Campaign/OrcX01.w3x",
  "retail_executable": "/absolute/path/to/Warcraft III.exe",
  "edition": "tft",
  "hook_function": "Trig_Intro_Skipped_Actions",
  "hook_anchor": "call ConditionalTriggerExecute( gg_trg_Gameplay )",
  "hook_where": "after"
}
```

The generated probe manifest is suitable for the newer
`tools/wc3_retail_probe.py prepare` when available in the user's checkout.
Some historic Patch 8 baselines do **not** contain that separate tool; in that
case insert the fragments using the documented copied-map workflow, or bring
in the newer runner. The hook **must** execute after the map restores gameplay
and cinematic restrictions. Confirm an untouched control map before relying
on an instrumented one. Never modify the stock MPQ/map in place.

Generated scenarios default to a 60-second session timeout so there is time
for manual activation after Frida arms; the measured scenario duration can be
longer and increases that timeout accordingly. Set `timeout_seconds` explicitly
when a case needs a different bound. Each case review stores native calls for
that run ID as a per-case RVAs-to-return-records map, matching the differential
analyzer's validation contract.

Create and check the Patch 8 session using the same trace plan and prepared-map
records. The Frida plan's `--seconds` limit must cover the longest scenario
`timeout_seconds` in the generated case manifest:

```sh
python3 tools/wc3_ability_re.py ability-session-create \
  --plan build-re/ability-re/Apxf-trace-plan-01 \
  --probe-dir build-re/ability-re/Apxf-prepared-probe-01 \
  --cases build-re/ability-re/Apxf-lab-01/lab-session-cases.json \
  --output build-re/ability-re/Apxf-session-01
python3 tools/wc3_ability_re.py ability-session-check \
  --session build-re/ability-re/Apxf-session-01
python3 tools/wc3_ability_re.py ability-session-run \
  --session build-re/ability-re/Apxf-session-01
```

When the session runner announces that `phoenix-300` is armed, type
`-re phoenix-300` into the prepared map's chat as `chat_player`; repeat for
`phoenix-650` when it arms that case. The generated JASS starts the experiment
only on an exact chat-command match. **Patch 9 does not inject keystrokes**:
Frida capture boundaries are therefore set before the player types the command.
One running map can execute all cases, with newly created units for each case,
a paused/reused timer, per-case buffers and distinct `PreloadGenEnd` literals.
Each case records `SESSION_START`, setup and order status, sampled unit
life/mana/position/speed/owner (including a baseline **before** issuing an active order), optional queried BuffIDs, caster spell cast/effect/finish/endcast event markers, and `SESSION_DONE`
only after its observation interval completes. The results are used by the
existing strict file-freshness and completion-marker checks.

### Supported scenario kinds and limits

- `passive`: install ability, no order; `accepted=true` means **setup**, not a cast.
- `target`, `projectile`, `buff`: issue an explicitly named `IssueTargetOrder`
  against `targets[0]`; other targets are controls/candidates.
- `point`, `area`: issue an explicitly named `IssuePointOrder` at `point.x/y`.
- `immediate`: issue `IssueImmediateOrder` with the provided order string.

Ordered cases may set `expected_order_accepted` to `false` for an intentionally
rejected-order control. The generated session manifest then requires
`accepted=false` and treats `accepted=true` as inconclusive. The default is
`true`. This controls capture classification only; it does not make the
expected order result true or provide evidence that the ability behaved
correctly. This field is invalid for `passive` scenarios, where
`accepted=true` only records successful setup.

Use `learn_mode: "hero_skill"` with `hero_level` for learned Hero spells;
otherwise the default `unit_add` uses `UnitAddAbility` and, for higher ranks,
`SetUnitAbilityLevel`. In both cases the generated code verifies the resulting
ability level. A successful `Issue*Order` return is **not proof of a completed
cast**; use native trace and observed outcomes. An observable BuffID query
returning 0 does **not** prove absence of native buff state.

The validator caps a plan at 32 cases, eight targets per case, 120 timer steps
per case, eight observed buff IDs and 1,400 observation lines. Sampling
interval is at least 50 ms. Logged time is **nominal JASS timer time**, not a
native callback timestamp. A setup failure, rejected order or observation
buffer overflow emits an inconclusive marker. Stale/missing output, mismatched
case IDs and incomplete native traces remain inconclusive under Patch 8.

**Isolation limit:** The generated lab creates and removes its own caster and
target handles, but does not remove campaign AI, terrain/pathing hazards,
non-owned map units, or lingering projectiles/effects. Select safe areas and
use controls. JHCR must not hot-reload its active timer or scenario callbacks;
prepare those functions before launching the map. This patch does not prove
that generated JASS compiles under the user's Retail map—run the copied-map
JASS preparation/compiler checks locally before treating it as a valid probe.

Patch 10 will use these explicit case/observation contracts for differential
analysis and selecting only the runtime follow-ups still required by static
evidence.

## Patch 10: evidence-bounded differential analysis and static-first follow-ups

`ability-analyze` is **offline**. It consumes an immutable Patch 6 `offline/`
package, optionally a Patch 9 `lab-plan.json`, completed Patch 8 session
folders, and an **explicit** comparison manifest. It does not attach Frida,
launch Retail, change JASS maps, edit the permanent inventory, automatically
close unanswered questions, or invent additional experiments.

Generate a static-only question queue without any Retail runs:

```sh
python3 tools/wc3_ability_re.py ability-analyze \
  --offline build-re/ability-re/Apxf-offline/offline \
  --output build-re/ability-re/Apxf-static-followups
```

For a paired case/control investigation, keep each compared case **in the same
Patch 8 session** and generate explicit hypotheses. Example comparison manifest
(`phoenix-comparisons.json`), after creating the named lab cases and preparing
and running the corresponding session:

```json
{
  "schema_version": 1,
  "comparisons": [
    {
      "id": "phoenix-vs-control-life",
      "case": "phoenix-550",
      "control": "phoenix-control",
      "metric": "life_change",
      "target_index": 0,
      "relation": "different",
      "tolerance": 0.5
    },
    {
      "id": "phoenix-acquisition-entry",
      "case": "phoenix-550",
      "control": "phoenix-control",
      "metric": "function_enter_count",
      "function_rva": "0x0080ecd0",
      "relation": "different"
    }
  ]
}
```

The case IDs above are illustrative: both must exist in the lab and session
manifests. `function_rva` must be a traced **function entry** present in the
Frida plan; native entry counts alone do not establish the ability's owning
receiver. The `life_change` metric is **end minus initial sample**, not raw
end life. The other supported metrics are `mana_change`, `speed_change`,
`distance_moved` (straight-line displacement from sampled XY), `owner_end`,
`buff_level_end` (requires `buff_rawcode` sampled in both cases), and
`function_enter_count`.

```sh
python3 tools/wc3_ability_re.py ability-analyze \
  --offline build-re/ability-re/Apxf-offline/offline \
  --lab build-re/ability-re/Apxf-lab-01 \
  --session build-re/ability-re/Apxf-session-01 \
  --comparisons /path/to/phoenix-comparisons.json \
  --output build-re/ability-re/Apxf-differential-01
```

Repeat `--session` for independent sessions if necessary. Each comparison
pairs the two named cases **within the same session only**: samples from
separate maps/processes are not silently combined. The output contains
`analysis.json` (source hashes, capture readiness, observed values, comparison
statuses, deduplicated prioritized question actions) and `review.md`.
All outputs are new directories; regenerating from the same immutable inputs
does not need a new Retail run.

### Evidence semantics

- A `usable_observation` case requires validated immutable session provenance,
  a bounded nontruncated native trace, an accepted/setup-ready JASS result,
  start/done markers, and **every expected timer tick** for the generated lab.
  `accepted=true` is an order API return, or passive initialization, **not** a
  cast or gameplay success claim.
- A comparison is `observed_consistent` only when every participating session
  contains a complete paired observation matching the explicitly requested
  `same`/`different` relation within tolerance. `observed_not_matching` is a
  counterexample **to that sampled relation**, not evidence about the full
  Retail algorithm. Incomplete/missing/truncated/rejected cases yield
  `inconclusive`, never a negative ability behavior verdict.
- JASS time is nominal timer time, not a native effect timestamp. Life change
  may include regeneration, armor and unrelated combat unless the laboratory
  setup isolates those factors. Buff ability-level 0 does not prove that a
  native status is absent. Never infer projectile ownership or animation
  playback from static art references or function-entry counts.
- Offline unanswered questions are **never automatically resolved** by
  comparisons. The planner groups repeated static gaps, prioritizes Ghidra
  detail and factory/vtable review, then presentation source inspection,
  before suggesting another Retail capture. Incomplete runs get a diagnostic
  action, **not an automatic retry**.
- A session directory remains linked to the original probe, map, agent, trace
  plan and executable. Mutated or missing provenance fails closed. The tool
  can analyze archived session files without a *running* Retail process, but
  its pinned source files must remain available for identity verification.

Run the offline-only regression suite with:

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_differential.py'
```

This patch collects and compares **sampled evidence** and plans efficient
follow-up work. Patch 11 will generate implementation-oriented algorithms and
test drafts from *reviewed* semantic claims; Patch 10 cannot declare exact
Retail parity on its own.

## Patch 11: evidence-linked implementation specifications and guarded C references

`ability-spec` consumes the immutable `reconstruct` output, optionally a Patch 10
`ability-analyze` output, and optionally an **explicit human-reviewed semantic
contract**. It is fully offline: it does not re-run Ghidra, Wine, Frida, JASS,
or MPQ/model tooling. Run it after reconstructing the ability, e.g.:

```sh
python3 tools/wc3_ability_re.py ability-spec \
  --reconstruction build-re/ability-re/Apxf-offline \
  --output build-re/ability-re/Apxf-implementation-01

# After collecting/reviewing independent evidence:
python3 tools/wc3_ability_re.py ability-spec \
  --reconstruction build-re/ability-re/Apxf-offline \
  --analysis build-re/ability-re/Apxf-differential-01 \
  --review /path/to/reviewed-Apxf-contract.json \
  --output build-re/ability-re/Apxf-implementation-02
```

A reconstruction root has `lookup.json`, `offline/{coverage,dependencies,
questions,provenance}.json`, `offline/native/decompiled.c`, and optionally
`graph/` and `presentation/`. The command checks the lookup's original content
digest, the original graph/presentation digests when those inputs were used,
the identity of the executable and any Patch 10 analysis input hashes. An
inconsistent or mutated source is rejected rather than reported as a new
finding. Existing output directories are never overwritten.

Output files are:

| Output | Scope |
|---|---|
| `implementation.md` | Per-edition/rank authored values, source locations, reviewed algorithms/state transitions, unresolved questions |
| `presentation-timeline.md` | **Authored** art/sound/model sequences distinguished from explicitly reviewed runtime events |
| `acceptance-tests.md`, `acceptance-tests.json` | Reviewed acceptance scenarios, plus sampled comparisons clearly labelled as non-specification observations |
| `reference/ability.c`, `reference/ability.h` | Optional **verbatim reviewer-supplied C fragments**, guarded by `#if 0`; never a compiled OpenRealm module |
| `spec-evidence.json` | Claims, provenance hashes, unresolved questions, explicit limits on asserted parity |

### Optional reviewed-contract format

The manually reviewed JSON requires `schema_version=1`, `rawcode`, matching
`executable_sha256`, and arrays for `claims`, `logic_steps`,
`state_transitions`, `presentation_events`, `acceptance_tests`, and
`reference_c`. Empty arrays are allowed. Minimal illustrative shape (the
`area` field name below must actually be present in the selected
`lookup.json`; the semantic statement must be independently investigated):

```json
{
  "schema_version": 1,
  "rawcode": "Apxf",
  "executable_sha256": "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed",
  "claims": [
    {
      "id": "radius_source",
      "domain": "targeting",
      "statement": "[REVIEWER MUST REPLACE: exact targeting semantics and constraints]",
      "evidence": [
        {"type": "native", "rva": "0x0080d820"},
        {"type": "authored", "edition": "tft", "rank": 1, "field": "area"}
      ]
    }
  ],
  "logic_steps": [
    {"id": "acquisition", "stage": "periodic",
     "description": "[REVIEWER MUST REPLACE: data reads, filters and call ordering]",
     "claim_ids": ["radius_source"]}
  ],
  "state_transitions": [],
  "presentation_events": [],
  "acceptance_tests": [],
  "reference_c": []
}
```

The `native` evidence type must reference a function *present in the offline
execution graph*; this alone proves function presence, **not** the asserted
algorithm. An `authored` evidence type must reference an actually exported
rank field. A `comparison` evidence reference requires an included Patch 10
analysis with an `observed_consistent` comparison and complete paired samples.
Even this supports only a sampled relationship: it cannot prove the native
formula, the effect's owner or all rank behavior. Inconclusive or nonmatching
comparisons cannot underwrite a reviewed claim.

The human reviewer is responsible for checking semantic interpretations against
exact native instructions/data and/or controlled measurements. The harness
checks reference integrity; it does **not** certify review quality. It never
automatically closes earlier questions, derives numeric C formulas from two
samples, invents missing branch semantics, or creates runtime animation
timestamps from model sequences. `reference_c` entries have `id`, `code` and
`claim_ids`; the C fragment is reproduced verbatim **inside `#if 0`** and
preprocessor directives are rejected. Copying it into game code is a separate,
manual review and implementation step.

Run fixture-only tests with:

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_spec.py'
```

The output is the evidence-linked **implementation draft**; the full parity
and executable code-generation acceptance milestone remains Patch 12 and
subsequent investigation of unresolved Retail native and presentation paths.

## Patch 12: end-to-end harness readiness and smoke procedure

Patch 12 connects the **existing** data/graph/presentation/trace/differential/spec
formats through `tools/wc3_re/readiness.py`. It does not remove the human review
boundary, add ability implementations to OpenRealm, or automatically interact
with Retail. There are two distinct milestones:

1. **Offline pipeline smoke** — synthetic fixtures prove that the tools can
   exchange artifacts, preserve identities/hashes, generate a read-only Frida
   plan, rank static-first questions and render guarded implementation specs.
2. **Local live smoke** — a separately executed, reviewed Retail/JASS/Frida run
   for an actual ability and source map. It must be performed on a machine with
   the exact pinned Retail executable and matching archives. A tool-presence
   report is not a successful Retail launch or probe.

### Synthetic end-to-end smoke (no Warcraft data needed)

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_*.py'
python3 tools/wc3_ability_re.py ability-smoke \
  --output build-re/ability-re/patch12-smoke-01
```

Use a **new** output directory on every smoke run. The two committed fixtures
under `tests/fixtures/wc3_ability_re/` represent `Apxf` (Phoenix Fire, passive
periodic chain) and `AOsw` (Serpent Ward, authored `AOwd` implementation code,
active cast). They contain invented demonstration pseudocode, a synthetic
function-edge relationship and invented `Synthetic*.mdx` paths. **None is
Retail game evidence.** They do not test Ghidra's Java exporter, C asset tools,
Frida attachment, Wine, JASS compilation, runtime animation playback or game
logic parity. They contain no Blizzard binaries, archive files or models.

A successful result writes `smoke-summary.json` **last** and separate immutable
`Apxf/` and `AOsw/` folders containing `lookup.json`, `graph/`, `presentation/`,
`offline/`, `trace/`, `analysis/`, `spec/` and `readiness.json`. Success means
`synthetic_offline_pipeline_passed` only. In particular, the fixture analysis
has zero real comparisons, the generated specs contain zero reviewed claims,
and the reference C stays under `#if 0`.

### Verify a real reconstructed ability before attempting Retail

Use Patch 6 `reconstruct` with the **correct** authored edition and saved
Ghidra scan/detail exports (Patch 3). If working from caches, `ability-package`
can regenerate the offline report without launching Retail. Run:

```sh
python3 tools/wc3_ability_re.py ability-readiness \
  --reconstruction build-re/ability-re/Apxf-offline \
  --check-tools \
  --executable 'data/Warcraft III/Warcraft III.exe' \
  --ghidra-headless /path/to/ghidra/support/analyzeHeadless \
  --output build-re/ability-re/Apxf-readiness-01.json
```

`ability-readiness` checks the offline package's lookup/graph/presentation
content digests and source identities. With optional `--trace`, `--analysis`,
`--specification`, `--review`, and `--session`, it also checks the matching
Frida plan/agent, analysis inputs, generated spec evidence and saved prepared
map/session provenance:

```sh
python3 tools/wc3_ability_re.py ability-readiness \
  --reconstruction build-re/ability-re/Apxf-offline \
  --trace build-re/ability-re/Apxf-trace-plan-01 \
  --analysis build-re/ability-re/Apxf-differential-01 \
  --specification build-re/ability-re/Apxf-implementation-01
```

`--specification` must be generated from the same offline reconstruction and
analysis. If it was generated using a reviewed contract, pass that same
`--review` to the readiness check. Unmodified source dependencies are required;
any mutation of graph, asset metadata, Frida plan/agent or spec evidence must
fail rather than silently change the conclusion. `--check-tools` verifies
paths, environment presence and optional executable SHA-256 only: it does
**not** run Ghidra, audit binaries, check map validity, attach Frida or check
that the game is on the expected screen. `not_configured` and `missing` are
recorded separately. `--session` validates an already-created session's saved
hashes and launch record, **not the live process or gameplay result**.

If `ability-readiness` reports `offline_provenance_valid_not_retail_parity`,
that confirms only integrity of the supplied artifacts. The returned
`open_questions` and `evidence_boundary` remain authoritative; do not
change these to “verified” from a smoke test.

### Local Retail integration procedure — manual, focused and restart-minimizing

This is a **runbook**, not a recorded passing Retail test. Before interpreting
any result, confirm the executable SHA-256 is exactly
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`
(1.29.2.9231 x86), Ghidra uses its saved analyzed project, and the ROC/TFT
archives match the requested ability. Follow the map/probe and JHCR safety
rules earlier in this document and in
[retail-camera-tracing.md](retail-camera-tracing.md):

1. **Static Apxf pass.** Confirm `lookup Apxf --edition tft`, the exact
   implementation code/class hint, Ghidra graph seeds and availability of
   the Phoenix Fire native acquisition/periodic path. Generate the offline
   package and a bounded `ability-trace` plan from that graph. Do not hook an
   unreviewed indirect call instruction or interpret an unknown x86 register
   as a verified target pointer.
2. **Static AOsw pass.** Confirm `lookup AOsw --edition tft` resolves the
   authored `AOwd` implementation code. Review the `CAbilityWard` order
   validator/fallback path. Generate an independent graph and trace plan:
   never reuse a Phoenix Fire trace or inferred receiver identity.
3. **Prepare one suitable TFT map for each ability lab.** Generate
   `ability-scenarios` from a carefully reviewed JSON spec (see Patch 9
   example). For Phoenix Fire, use passive cases at known distances and
   controls. For Serpent Ward, use explicit point-order `ward`, valid and
   invalid placement controls, and `hero_skill` learning when testing stock
   Hero behavior. Verify caster type, map availability, gameplay location,
   order name and source edition in each case. Campaign triggers or a skipped
   introduction must not silently invalidate the experiment.
4. **Validate the copied map before testing the modification.** Use
   `wc3_retail_probe.py prepare/launch` where installed, load an untouched
   control first, visually confirm the known map screen, then launch the
   prepared map. Install generated global/function fragments only at audited
   anchors and compile/validate the script locally. `ability-scenarios` itself
   **does not** install JASS, start Warcraft or send clicks/keys.
5. **Capture cases without process restarts.** Create the Patch 8 session from
   the exact Patch 7 trace plan, the matching prepared probe directory, and
   generated `lab-session-cases.json`. Run `ability-session-check` before live
   attach; use `ability-session-run` only when the prepared map is actually
   running and the compatible Frida server is available. Issue the exact
   `-re <run_id>` chat command after the controller arms each case. Observe
   actual cast/effect/finish markers, per-case start/done markers, result-file
   freshness and bounded native completion. A JHCR sequence update is permitted
   only for allowlisted passive logger functions, not active callbacks.
6. **Analyze and stop early when appropriate.** Run `ability-analyze` against
   the archived cases and explicitly named controls. Examine unmatched
   results and confounds before designing another experiment. Prefer Ghidra
   static review for unknown data reads or dispatch; use another Retail run
   only when it answers an outstanding observable question. Preserve the raw
   trace, output and source map for subsequent offline replay.
7. **Write the spec from evidence.** Generate `ability-spec` with the resulting
   offline package and optional differential review. Fill reviewed claims only
   after checking the supporting native code and/or valid measurements. Runtime
   animation timing, effect lifetimes, damage formulas and state transitions
   that remain unresolved must stay open. C reference fragments are guarded
   notes, not a drop-in OpenRealm implementation.

**Minimum real smoke acceptance:** for both abilities, a correct identified
Retail process and map; a completed, nontruncated Frida capture; JASS
start/done/sample markers tied to the matching case; a controlled positive
scenario and a controlled negative scenario; correctly classified inconclusive
cases; a repeatable offline re-analysis; and an evidence-linked spec that does
not assert unsampled behavior. Add no fixed FPS, damage, timeline, projectile
or animation assertions without inspecting the relevant executable/data.

**Current scope boundary:** The harness is suitable for staged local
integration, but the actual Ghidra 12.1.4 Java exporter, version-matched MPQs,
Wine launch, Frida server/target compatibility, JASS compilation, and real
Phoenix Fire/Serpent Ward experiments have not been tested by this patch.
Until those checks are performed, do not describe the entire harness as
live-validated or able to recover complete exact implementation automatically.
