# Warcraft III shared native ability functions

This document records exact-build native helpers that may reduce repeated
ability verification work. Addresses below apply only to the Retail executable
with SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed` (PE32
x86, preferred image base `0x00400000`). Re-derive them for another executable.

## Confirmed starting points

Phoenix Fire (`CAbilityPhoenixFire`) provides a traced caller path into several
candidate shared mechanisms:

| Function | Observed role | Evidence / limits |
|---|---|---|
| `0x00682180` | General spell target validation | Phoenix Fire's candidate callback passes the candidate classification through this helper. It checks common target rejection paths and registered validators. Numeric returns are internal rejection codes, not damage or an order-acceptance boolean. Full-analysis Ghidra found 64 direct call references from 64 caller functions. |
| `0x00682210`, `0x006822E0` | Common target rejection predicates | Each has one direct call reference from `0x00682180`; they consult target predicates and `MagicImmunesResistUltimates`. Exact semantic names for each rejection branch are not fully recovered. |
| `0x0068EA00` | Area-unit enumeration | Phoenix Fire invokes it centered on the owner's position with a radius/configuration from the ability data object and callback `0x00C0F1E0`. Full-analysis Ghidra found 133 direct call references from 118 caller functions. |
| `0x006D6570` | Buff FOURCC presence lookup | Phoenix Fire's target callback queries `Bpxf` and rejects already affected candidates. Full-analysis Ghidra found 959 direct call references from 681 caller functions, making this the strongest high-reuse starting point. This lookup count does not establish buff application, refresh, expiry, or dispel behavior. |
| `0x006EC8F0` | Status/effect setup | Phoenix Fire reaches this after choosing a target, using the `Bpxf` definition. Full-analysis Ghidra found 15 direct call references from 15 caller functions; the exact shared API contract remains open. |
| `0x0067FB80` | Additional owner/target relation check | Called from Phoenix Fire's candidate callback. It examines owner/target flags and invokes shared validation; a stable semantic label is not established. Full-analysis Ghidra found 40 direct call references from 37 caller functions. |
| `0x00699FD0` | Indexed candidate selection | Phoenix Fire calls this to choose one candidate from the collected area targets. Full-analysis Ghidra found seven direct call references from five caller functions; this is a narrower helper than target validation, enumeration, and buff lookup. |

The counts are direct incoming call references and unique caller functions in
the full-analysis Ghidra database, not counts of unique abilities or runtime
executions. They are useful for deciding where to inspect next: start with
buff lookup, area enumeration, target validation, and relation validation.
Validate a candidate's gameplay meaning from its callers and arguments before
reusing its behavior contract.

The ability-specific Phoenix Fire path is documented in
[ability-verification-review.md](ability-verification-review.md#phoenix-fire-native-path-periodic-acquisition-and-target-gates).
These helpers are promising reuse points, not blanket proof for other
abilities. To reuse one in a verification, establish that the ability's own
call path reaches it with the same arguments and that the relevant authored
data and branch outcomes match.

## Current investigation

A full Ghidra analysis of the pinned executable completed successfully and is
stored in `data/wc3-ghidra-full/Wc3Retail1292Full`. Incoming references were
queried against that project with `tools/ghidra/Wc3Callers.java`. High call
count alone does not establish a gameplay contract: exclude generic
compiler/runtime helpers and separate direct code references from virtual
dispatch sites.

## Reproducible inspection

Use the cached full-analysis project for read-only call/reference inspection:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/data/wc3-ghidra-full" Wc3Retail1292Full \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3Callers.java 0x00682180 0x0068EA00 0x006D6570 0x006EC8F0
```

Use `Wc3DumpFunction.java` alongside the caller query when the helper's body
or argument contract needs inspection. Use Frida only when static references
cannot resolve the runtime receiver or virtual slot; a trace of one exercised
path supplements, but does not replace, the static caller analysis.
