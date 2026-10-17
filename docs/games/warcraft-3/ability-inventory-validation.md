# Retail ability evidence inventory validation

The [ability function inventory](ability-function-investigation.json) is
research evidence for one exact `Warcraft III.exe` build. Run its offline
validator before using its address records as input to graph indexing,
Ghidra exports or Frida instrumentation. This does not require game assets,
Ghidra, Wine or Retail execution.

```sh
python3 tools/wc3_re/inventory.py
python3 tools/wc3_re/inventory.py --format json
python3 tools/wc3_re/inventory.py \
  --normalized-output build/ability-re/normalized-inventory.json
python3 -m unittest discover -s tests -p 'test_wc3_re_inventory.py'
```

The tool fails with exit code 1 on inventory errors, or 2 on unreadable inputs
and unsafe output requests. `--strict` additionally fails on warnings. It does
not edit the tracked inventory: its normalized output is a separate copy.
The JSON Schema in `tools/wc3_re/schema.json` also documents the supported
structure for other tooling, while `inventory.py` performs its own validation
without extra Python packages.

## Evidence boundaries

- The executable SHA-256 and preferred PE image base anchor address arithmetic.
  Check both before any native trace. A correct VA/RVA pair is not proof of
  function identity or executable code at that location.
- `function_va` means a researched function address; `vtable_va` and legacy
  `vtable` denote vtable addresses; `global_va` denotes a global; `constant`
  stores `value` and **must not** carry VA/RVA.
- Old `related_addresses` and relationship endpoints sometimes omit address
  kinds. The normalized copy labels these `untyped_va`, **not** `function_va`.
  Do not infer a callable function from an unspecified address kind.
- `related_addresses` records mentions in the source notes, **never** verified
  edges. Do not turn these into caller/callee relationships.
- `direct_call`, `virtual_dispatch`, `callback_dispatch`, `related_call_path`
  and `call` are distinct relationships. In particular, `call` preserves
  an asserted call whose dispatch mechanism is not classified, and
  `related_call_path` does not assert one immediate instruction-to-callee edge.
- Multiple records may establish the same `(from_rva, to_rva, kind)` with
  different sources, contexts and confidence. Preserve each evidence record;
  a graph renderer may coalesce edges for display but must retain their sources.
- `object_offsets` currently includes human-readable field descriptions and
  composite ranges, not just machine-readable numbers. Do not parse them as
  single verified fields without reviewing the text.
- A record with `record_kind=function_group` may contain several unrelated
  function entry points; `vtable_record` is not a function entry point.

## Current data migration

The original October 2026 inventory had two occurrences of `0x00BD70F0`
incorrectly paired with RVA `0x008D70F0`. Using the pinned preferred base
`0x00400000`, the correct RVA is `0x007D70F0`. Another entry treated the
internal tag `0x2B61676C` as if it were a module VA. These are corrected in
the tracked file; no behavior is inferred from the tag's value.

The existing 11 generic `call` edges remain unclassified; the existing 11
repeated-edge groups retain all their evidence. Untyped legacy address
references are preserved as `untyped_va` only in normalized output. This is a
foundation for later reviewed address classifications, not a substitute for
source-linked Ghidra proof.

When adding new evidence, prefer explicit `kind` fields on every address and
record the source document/section. Re-run validation and tests when changing
the schema or the investigation inventory. Do not hard-code historical record
counts in other documentation; derive them from the validator report.
