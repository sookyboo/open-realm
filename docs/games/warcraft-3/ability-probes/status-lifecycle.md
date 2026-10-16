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

### BTLF natural expiry

The exact-build BTLF vtable at `0x00EA63AC` overrides slot `+0x1D4` with
`0x006F2700` and slot `+0x1E4` with `0x006F2860`. Its base progress method
`0x006F6820` compares the supplied float with global game time at
`0x0112D88C`. When the supplied deadline is still later than current time, it
sets flag `0x80` and invokes slot `+0x354`; otherwise it updates two embedded
clock helpers and calls slot `+0xEC`.

The BTLF slot `+0x354` resolves to `0x006F6BD0`. That method dispatches event
`0xD01C4` through `0x007FBF80`; the BTLF slot `+0x36C` resolves to
`0x006F6CC0`. On event `0xD01C4`, `0x006F6CC0` invokes shared attached-object
removal `0x006D8530` and returns handled. Thus the exact-build BTLF path
confirms natural timed-life expiry removes the BTLF attached object. It does
not establish that expiry kills or removes the owner unit, nor that summon
cleanup uses this path.

The time comparison is direct evidence about the BTLF progress callback's
deadline behavior. It should not be generalized to other timed statuses merely
because they use similar clock objects.

### BTLF removal notification

Shared remover `0x006D8530` invokes the removed object's `+0x1A8` hook.
For exact-build `CBuffTimedLife` vtable `0x00EA63AC`, that slot resolves to
`0x006F2730`. The hook returns immediately unless its argument is the BTLF
object itself. On self-removal it resolves the owner and dispatches event
`0xD01A1` to the owner's event interface through `0x006C0010`. If the BTLF
expiry flag `+0x20 & 0x80` is set, the hook calls the BTLF object's vtable
slot `+0x360`. The BTLF implementation returns zero there, so generic later
owner-state and position-query logic is skipped (details below).

The expiry branch's virtual calls use the **BTLF object's** vtable (`ESI`),
not the owner's. For `CBuffTimedLife`, slot `+0x360` resolves to
`0x006F2680`, which returns zero unconditionally. The hook therefore exits
before the owner flag checks, position query through `0x00693650`, and the
later BTLF vtable call at `+0x364` can run. Those later operations are generic removal-hook
logic for classes whose `+0x360` returns nonzero; they are not part of the
verified BTLF expiry path. BTLF self-removal does dispatch owner event
`0xD01A1`, but the event's gameplay meaning remains unresolved. No direct
unit-death/removal call is established, so this is not evidence that timed-life
expiry kills or removes its owner.

## Timed-life callback boundary

The pinned `CBuffTimedLife` vtable at `0x00EA63AC` maps slot `+0x328` to
`0x006F6820`, slot `+0x354` to `0x006F6BD0`, and slot `+0x30C` to
`0x006F73D0`. The timed/progress callback can reach `+0x354`; that routine
dispatches event `0xD01C4` through `0x007FBF80`. When its second argument is
nonzero, it also calls `+0x30C`. In this vtable that resolves to
`0x006F73D0`, which walks an embedded child-object collection and sends
virtual callbacks at child slots `+0x8C` and `+0x90`.

This reveals a lifecycle notification/fan-out path inside timed-life objects.
The BTLF-specific event consumer and natural-expiry removal are established
above; the generic dispatcher alone does not establish owner death or summon
cleanup.

The two direct `+0x354` callers, `0x00BFC0C0` and `0x00C1A250`, are lifecycle
update wrappers, not removal routines. `0x00BFC0C0` invokes the callback and,
on a conditional branch, emits a separate event `0xD01C1` through
`0x007FBE90`; `0x00C1A250` invokes the callback, checks an embedded clock
against global game time `0x0112D88C`, may call its own virtual slot `+0x348`,
updates a clock helper, and conditionally emits `0xD01C1`. The event dispatcher
`0x007FBF80` forwards event IDs and arguments through its embedded callback
object's virtual `+0x8` method. Its generic nature means the event ID alone
does not imply owner deletion. The BTLF progress callback path does establish
removal of the BTLF instance; keep owner death/removal and summon cleanup
unresolved.

## Reproduce

```sh
r2 -q -c 'e scr.color=0; pd 150 @ 0x006d8530; pd 100 @ 0x006d87a0; pd 55 @ 0x004af590; pd 90 @ 0x00c7a3f0; pd 70 @ 0x006f6bd0; pd 55 @ 0x006f73d0; pd 80 @ 0x00bfc0c0; pd 70 @ 0x00c1a250; pd 80 @ 0x007fbf80; q' \
  'data/Warcraft III/Warcraft III.exe'
```

The machine-readable caller relationships are in
[`ability-function-investigation.json`](../ability-function-investigation.json).
See the compact [shared-helper map](../ability-shared-native-functions.md)
for other investigation targets.
