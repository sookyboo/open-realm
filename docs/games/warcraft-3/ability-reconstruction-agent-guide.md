# Agent playbook: reconstruct a Warcraft III Retail ability

Use this playbook when asked to reverse engineer a Warcraft III ability and
produce the most exact implementable OpenRealm specification that the available
evidence supports. **Input:** an ability rawcode such as `Apxf` or `AOsw` and,
when known, ROC/TFT edition. **Output:** a source-linked reconstruction package,
reviewed gameplay/presentation contracts, an implementation specification, and
an explicit list of remaining unknowns. Do not treat a generated document as
proof that Retail behavior has been recovered completely.

Read [AGENTS.md](../../../AGENTS.md),
[CONTRIBUTING.md](../../../CONTRIBUTING.md), and the
[technical harness reference](ability-reconstruction-harness.md) before doing
work. This is the **current agent workflow**; the technical reference also
contains patch-by-patch history, CLI schemas, and the detailed Retail runbook.
The executable and proprietary Warcraft data belong in the user's local
installation, not in the repository or a patch.

Use `build-re/` as the standard workspace for all generated ability
reverse-engineering artifacts, Ghidra projects, temporary caches, and reports.
It is ignored by Git. Keep compiled game/tool outputs under `build/`; do not
mix RE evidence with build products.

## Non-negotiable evidence and efficiency rules

1. **Static first.** Reuse validated inventories, ability data, saved Ghidra
   scan/detail exports, previously reviewed helpers, and recorded Retail probes.
   Do not launch Retail merely to corroborate a resolved code/data contract.
2. **Version-pinned.** Native addresses apply only to Warcraft III Retail
   **1.29.2.9231, PE32 x86**, preferred image base `0x00400000`, with
   `Warcraft III.exe` SHA-256
   `3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.
   A mismatch is a hard stop for native-code/Frida claims. A different build
   requires its own inventory and analysis, not adjusted guessed addresses.
3. **Separate evidence kinds.** Authored data, decompiler pseudocode, possible
   call edges, a live native call, JASS samples, visible animation, and
   human-reviewed semantics are distinct. Never promote an unbound virtual
   call, art reference, function-entry count, or accepted order to a proven
   effect or algorithm. Preserve source RVAs, archive/field names and hashes.
4. **No guessed code.** Ghidra decompilation is *C-like pseudocode*, not
   Blizzard's original C++. The spec may only assert algorithms, state
   transitions, formulas and timing justified by inspected paths or sufficient
   controlled evidence. Keep missing steps explicitly unresolved.
5. **One reusable session where feasible.** Prepare/batch positive controls,
   negative controls and boundaries together. Reuse a compatible running
   Retail process; stop when an answer is settled. A failed setup, stale output,
   truncated Frida trace or timer callback that did not finish is **inconclusive**.
6. **Never mutate Retail assets in place.** Use a copied, validated map; retain
   the untouched control. Do not log excessively, enable wide unbounded traces,
   rewrite active JHCR callbacks, or commit proprietary data.
7. **Keep evidence reusable.** Cache expensive Ghidra scans once per binary;
   detail-export only newly needed functions. Keep one immutable output
   directory per run, so another agent can reproduce the analysis offline.

## Procedure: from rawcode to offline reconstruction

### 1. Confirm prerequisites and the exact identity

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_wc3_re_*.py'
python3 tools/wc3_re/inventory.py
python3 tools/wc3_ability_re.py ability-smoke \
  --output build-re/ability-re/smoke-<unique-run-id>
make ability_audit mpqtool mdxtool
python3 tools/wc3_ability_re.py doctor \
  --executable 'data/Warcraft III/Warcraft III.exe'
```

Replace `<unique-run-id>` with a new name, not literal angle brackets. The
synthetic smoke fixtures for `Apxf` and `AOsw` test pipeline integration,
**not** Blizzard logic, animations or live instrumentation. `make` builds the
existing diagnostic tools, not OpenRealm gameplay; respect the user's build
and test instructions if they forbid compilation. Inspect `--help` whenever
local CLI options differ. If Retail data or Ghidra is unavailable, continue
with cached evidence and clearly report what was not checked.

Choose the actual authored edition. TFT-only behavior is not proven using ROC
archives. `AOsw` is an authored rawcode whose implementation code is `AOwd`;
those keys must not be conflated.

```sh
python3 tools/wc3_ability_re.py lookup Apxf --edition tft --format json \
  --executable 'data/Warcraft III/Warcraft III.exe' \
  --output build-re/ability-re/Apxf-lookup-01.json
```

Examine every applicable rank and alias, including cost, targets, range,
projectiles, buffs, effect IDs, summoned units, art and sound. Values reported
by AbilityData/tooltip remain **authored data**, not proof of native use.

### 2. Reuse or create the Ghidra function index

Look for a completed `ghidra/scan` export, with `export-summary.json`, pinned
hash and a successful `ghidra-check`. **Do not re-import/analyze** the binary
for each ability. If no saved project exists, do the one-time import/scan:

```sh
python3 tools/wc3_ability_re.py ghidra-export \
  --headless /path/to/ghidra/support/analyzeHeadless \
  --project-dir build-re/ghidra-projects --project-name WC3Retail1292 \
  --executable 'data/Warcraft III/Warcraft III.exe' \
  --import-first --mode scan \
  --output build-re/ability-re/ghidra/scan-01
```

Omit `--import-first` when using an existing analyzed project. Check the scan:

```sh
python3 tools/wc3_ability_re.py ghidra-check \
  build-re/ability-re/ghidra/scan-01 --mode scan
```

Use `lookup` plus the curated function inventory to identify seed functions.
Trace the registration/factory and relevant vtable/receiver manually where
possible; the saved class table is a **hint**, not a verified factory binding.
Request `detail` exports only for specific missing functions (the following
Phoenix Fire RVAs are *known candidate waypoints*, not a complete ability):

```sh
python3 tools/wc3_ability_re.py ghidra-export \
  --headless /path/to/ghidra/support/analyzeHeadless \
  --project-dir build-re/ghidra-projects --project-name WC3Retail1292 \
  --executable 'data/Warcraft III/Warcraft III.exe' \
  --mode detail \
  --rva 0x0080d820 --rva 0x0080ecd0 --rva 0x0080f1e0 \
  --output build-re/ability-re/ghidra/Apxf-detail-01
```

Record failures and unresolved dispatch instead of silently choosing a
callee. A scan exports metadata and references, **not** decompiled bodies;
`detail` is necessary to get pseudocode. Read `pcode.jsonl` and actual
caller disassembly before naming state fields or return-value meanings.

### 3. Generate the static package (default path)

```sh
python3 tools/wc3_ability_re.py reconstruct Apxf --edition tft \
  --executable 'data/Warcraft III/Warcraft III.exe' \
  --ghidra-scan build-re/ability-re/ghidra/scan-01 \
  --ghidra-detail build-re/ability-re/ghidra/Apxf-detail-01 \
  --output-dir build-re/ability-re/Apxf-static-01

python3 tools/wc3_ability_re.py ability-readiness \
  --reconstruction build-re/ability-re/Apxf-static-01 \
  --check-tools --executable 'data/Warcraft III/Warcraft III.exe' \
  --ghidra-headless /path/to/ghidra/support/analyzeHeadless \
  --output build-re/ability-re/Apxf-readiness-01.json
```

Read, at minimum:

| Artifact | Review it for |
|---|---|
| `lookup.json` | Actual authored code, edition, rank fields, buffs, units |
| `graph/execution-graph.json` | Native paths, evidence-bearing edges, unresolved indirect calls, traversal truncation |
| `graph/native-code.json` | Which decompilation bodies are really available |
| `graph/memory-access-candidates.json` | P-code memory operations needing human field interpretation |
| `presentation/assets.json` | Authored model/attachment/sound dependencies and missing asset references |
| `offline/native/decompiled.c` | Recovered Ghidra C-like code with source RVAs |
| `offline/{coverage,questions,dependencies,provenance}.json` | Missing proof, dependency list, input hashes, scope limits |
| `offline/report.md` | Readable starting summary, *not* a parity certificate |

If the graph is empty or misses relevant paths, use an explicitly reviewed
`--seed-rva` with `--no-auto-seeds`, or export missing detail functions and
regenerate in a **new** directory. Review separate callback phases:
creation, cast validation, cast/activation, tick/update, hit/impact,
status/buff, timed expiration, interruption, cancellation, owner/target death,
dispel, removal, and shared engine interactions. Not every ability implements
all phases; absence must be established, not presumed.

For visuals, distinguish model dependency from actual playback. Inspect
`mdxtool --info-json` sequences/events and nested spawn/sound references;
confirm animation tags, source/target attachments, missile motion, launch,
impact, loops and cleanup only when the runtime code or an actual Retail
observation establishes them.

### 4. Prioritize unanswered questions *without* launching Retail

```sh
python3 tools/wc3_ability_re.py ability-analyze \
  --offline build-re/ability-re/Apxf-static-01/offline \
  --output build-re/ability-re/Apxf-static-questions-01
```

Classify each question: (a) code/data can settle it, (b) native receiver or
branch requires a small Frida trace, (c) observable behavior/presentation
requires controlled Retail probing, or (d) not answerable from the available
build. Inspect the same shared helper only once, linking all abilities that
reuse it. Generate *only* the additional Ghidra exports needed for (a) before
proceeding to (b) or (c). Preserve the question's status and evidence
requirements; the planner does not close questions automatically.

## Optional live branch: resolve a *specific* runtime uncertainty

Run this branch only when the exact code/data and existing Retail evidence
cannot answer an important question. It requires your **locally configured**
Wine installation, Frida server/client, a matching running Retail process, a
compatible **already prepared** probe map, and an audited JASS scenario.
Read the detailed [Retail experiment procedure](ability-reconstruction-harness.md#local-retail-integration-procedure--manual-focused-and-restart-minimizing)
and [probe preparation runbook](retail-camera-tracing.md).

1. Select a *small* group of candidate functions; create a bounded trace:

   ```sh
   python3 tools/wc3_ability_re.py ability-trace Apxf \
     --graph build-re/ability-re/Apxf-static-01/graph \
     --capture-id phoenix-acquisition-01 --max-hooks 12 \
     --max-events 600 --seconds 60 \
     --output build-re/ability-re/Apxf-trace-plan-01
   ```

   Inspect `trace-plan.json` and `agent.js` before attaching. Register values
   are raw values, not named arguments; indirect calls remain unbound.

2. Define scenarios in JSON with validated unit rawcodes, owner, coordinates,
   ability level, appropriate **edition-matched order string**, duration and
   controls. Generate the JASS laboratory:

   ```sh
   python3 tools/wc3_ability_re.py ability-scenarios Apxf \
     --spec /path/to/reviewed-phoenix-lab.json \
     --output build-re/ability-re/Apxf-lab-01
   ```

   This generates `lab-globals.j`, `lab-functions.j`, `lab-plan.json`,
   `lab-session-cases.json` and optionally `lab-probe.json`. **It does not
   install or compile them in Retail.** Inject into a verified copied map
   using `wc3_retail_probe.py` if installed; some checkouts lack that runner.
   Respect `globals` layout, restore gameplay before the probe, and verify
   the copied map loads. The chosen caster must actually support the ability.

3. After a prepared map is running, use one persistent session:

   ```sh
   python3 tools/wc3_ability_re.py ability-session-create \
     --plan build-re/ability-re/Apxf-trace-plan-01 \
     --probe-dir /path/to/verified-prepared-probe \
     --cases build-re/ability-re/Apxf-lab-01/lab-session-cases.json \
     --output build-re/ability-re/Apxf-session-01

   python3 tools/wc3_ability_re.py ability-session-check \
     --session build-re/ability-re/Apxf-session-01

   python3 tools/wc3_ability_re.py ability-session-run \
     --session build-re/ability-re/Apxf-session-01 \
     --remote 127.0.0.1:27043
   ```

   Trigger each announced `-re <run_id>` chat command **after** Frida arms it.
   Check fresh `SESSION_START`, `SESSION_DONE`, accepted/setup markers, all
   expected samples and capture bounds; allow delayed callbacks to finish
   before `SESSION_DONE`. The controller does not type chat or control UI.
   JHCR must not change live timer/event callback bodies: only reviewed
   allowlisted passive loggers may be hot-reloaded.

4. Analyze archived cases and matched controls (same session):

   ```sh
   python3 tools/wc3_ability_re.py ability-analyze \
     --offline build-re/ability-re/Apxf-static-01/offline \
     --lab build-re/ability-re/Apxf-lab-01 \
     --session build-re/ability-re/Apxf-session-01 \
     --comparisons /path/to/reviewed-comparisons.json \
     --output build-re/ability-re/Apxf-analysis-01
   ```

   Missing or incompatible comparisons are not negative observations. Capture
   visual evidence separately if effect timing/animation sequence remains in
   doubt: JASS samples and function-entry tracing cannot prove a rendered
   frame, animation, or selected sound variant.

## Final deliverable: implementation specification and handoff

Generate the draft from *immutable* reconstruction inputs:

```sh
python3 tools/wc3_ability_re.py ability-spec \
  --reconstruction build-re/ability-re/Apxf-static-01 \
  --output build-re/ability-re/Apxf-spec-01

# Only when an independently reviewed, evidence-linked contract exists:
python3 tools/wc3_ability_re.py ability-spec \
  --reconstruction build-re/ability-re/Apxf-static-01 \
  --analysis build-re/ability-re/Apxf-analysis-01 \
  --review /path/to/reviewed-Apxf-contract.json \
  --output build-re/ability-re/Apxf-spec-reviewed-01
```

The reviewed contract schema and evidence-reference rules are in
[the Patch 11 reference](ability-reconstruction-harness.md#optional-reviewed-contract-format).
The generator **does not author a semantic review for you**. If none exists,
`implementation.md` is an evidence inventory and draft, not a complete
implementation. `reference/ability.c` and `.h` are verbatim, reviewer-supplied
C fragments protected by `#if 0`, **not buildable OpenRealm modules**.

Before handing off, the agent must:

- State the requested rawcode, authored implementation code, edition/ranks,
  executable SHA-256 and exactly which source material was actually read.
- Produce `implementation.md`, `presentation-timeline.md`,
  `acceptance-tests.md`/`.json`, and `spec-evidence.json` with paths; attach
  or point to `offline/native/decompiled.c` and the relevant raw Ghidra exports.
- Write explicit algorithms, field meanings, state transitions and precise
  effect/animation/audio sequencing **only when evidenced**. Identify
  unknowns and their smallest useful next checks, including unverified
  aliases, levels, targets, boundary/tick conditions and cleanup.
- Distinguish `authored`, `static_code`, `runtime_trace`, `sampled_observation`,
  `reviewed_semantics`, and `unresolved` in any summary. Do not claim that
  `ready_for_review`, `offline_provenance_valid_not_retail_parity`, or a
  successful synthetic smoke means game fidelity was proven.
- For an OpenRealm implementation handoff, map the required behavior into
  `games/warcraft-3/game/` and its data-driven/shared systems, maintain the
  universal client boundary, identify deterministic regression tests and
  save/load or cancellation interactions, and explain remaining risks.
- Report commands that were run and those **not run**. Follow the user's
  requested restriction on compiling, launching, testing or editing runtime
  code; do not convert a reconstruction request into an unrequested gameplay
  patch.

### Stop conditions

Stop probing and hand off when all high-impact behavior and presentation
claims are supported, or when new runs would not change the implementation
specification. If evidence is incomplete, **deliver the supported partial
spec and the ranked unresolved queue**; never fill gaps with plausible but
unverified behavior. When a prerequisite is missing, fail narrowly, preserve
existing artifacts and explain the minimum missing input or tool instead of
rebuilding unrelated infrastructure or rerunning completed experiments.
