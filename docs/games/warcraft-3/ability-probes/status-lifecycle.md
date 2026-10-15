# Retail status lifecycle traces

Exact-build static evidence for attached ability/status removal in Warcraft III
1.29.2. Executable SHA-256:
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`
(PE32 x86, image base `0x00400000`). Re-derive addresses for another build.

## Attached status removal path

`0x006D8530` is the shared attached-instance removal routine. Its disassembly
shows that it:

1. Returns for a null or already-removed object, otherwise sets the removed
   state bit.
2. Walks sibling attached objects and calls their vtable slot `+0x1A8` with
   the object being removed. It then invokes the removed object's own
   `+0x1A8` hook.
3. Repairs the owner's linked attached-object list and cached metadata, then
   clears owner references for selected rawcodes before returning.

Three independent paths converge here:

| Caller | Route | Evidence |
|---|---|---|
| `UnitRemoveAbility` (`0x004AF590`) | Finds an instance by rawcode, then calls `0x006D8530`. | Wrapper disassembly and direct call. |
| `UnitRemoveBuffs` / `UnitRemoveBuffsEx` | Both call `0x006D87A0`; matching instances call `0x006D8530`. | Shared filter loop. |
| Mana Shield callback (`0x00C7A3F0`) | Calls `0x006D8530` on depletion branches. | Callback disassembly; exact field meanings remain unresolved. |

The common remover is therefore lifecycle infrastructure, while the caller
and attached-object class determine why a particular instance is removed.
Its notification hook is shared structurally; semantic meanings of sibling
callbacks at `+0x1A8` remain class-specific.

## Timed-life boundary

`UnitApplyTimedLife` (`0x004AED50`) creates and attaches a `BTLF` object
through `0x006D4B60`. The `BTLF` vtable's positive/negative polarity methods
at `+0x1E0` and `+0x1E4` resolve to `0x0046A9A0` and `0x0046A9C0`;
both return zero. The `0x006D87A0` filter requires one of those predicates
when either positive or negative buff removal is requested. Thus BTLF does not
match either polarity-selected path in `UnitRemoveBuffs` or
`UnitRemoveBuffsEx`, independent of the remaining category flags. This is a
class-specific static conclusion; do not generalize it to other timed statuses.

This does not identify BTLF's natural-expiry callback or prove that all summon
expiration uses this route. Summon-specific cleanup and entity deletion remain
separate investigations.

## Reproduce

```sh
r2 -q -c 'e scr.color=0; pd 150 @ 0x006d8530; pd 100 @ 0x006d87a0; pd 55 @ 0x004af590; pd 90 @ 0x00c7a3f0; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The machine-readable caller relationships are in
[`ability-function-investigation.json`](../ability-function-investigation.json).
See the compact [shared-helper map](../ability-shared-native-functions.md)
for other investigation targets.
