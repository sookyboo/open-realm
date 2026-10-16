# Retail JASS effect and animation natives

Pinned executable: Warcraft III 1.29.2.9231, PE32 x86, SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`, image
base `0x00400000`. Re-derive every address for another executable hash.

## Effect creation

Native registrations are in the JASS binding table around `0x004A0B20`:

| Native | Registered wrapper | Observed path |
|---|---:|---|
| `AddSpecialEffect` | `0x004898F0` | Converts path, tail-calls `0x004892B0` |
| `AddSpecialEffectLoc` | `0x00489910` | Converts location to coordinates, calls `0x004892B0` |
| `AddSpecialEffectTarget` | `0x00489960` | Converts widget handle, tail-calls attached-effect routine `0x00489320` |
| `AddSpellEffect` | `0x00489990` | Resolves ability/effect-type art, calls `0x004892B0` |
| `AddSpellEffectLoc` | `0x00489A90` | Resolves art and location, then common creation path |
| `AddSpellEffectById` | `0x004899F0` | Resolves ability ID/effect-type art, then common creation path |
| `AddSpellEffectByIdLoc` | `0x00489A30` | Resolves ability ID/effect-type art and location, then common creation path |
| `AddSpellEffectTarget` | `0x00489B20` | Resolves art and delegates to attached-effect routine `0x00489B70` |
| `AddSpellEffectTargetById` | `0x00489B70` | Resolves art and uses the target-attached creation path |

`0x004892B0` is the reusable world-effect constructor reached by both explicit
model-path and ability-art natives. It calls `0x006BBB70` to create the effect
object, then `0x004E72C0` to register/associate the resulting handle. The
target-attached path is separate: `0x00489320` performs widget/model setup and
calls `0x006BBC30`, then registers through `0x004E72C0`. Do not assume the
positioned and attached forms have identical lifetime or rendering behavior
without tracing those lower-level constructors.

The names and wrappers can be rechecked with:

```sh
r2 -q -c 'e scr.color=0; pd 35 @ 0x004A0B20; pd 55 @ 0x004892B0; pd 75 @ 0x00489320; pd 70 @ 0x00489990; pd 70 @ 0x00489B70; q' \
  'data/Warcraft III/Warcraft III.exe'
```

## Unit animation requests

Registrations are around `0x0049D60A`:

| Native | Wrapper | Observed delegation |
|---|---:|---|
| `SetUnitAnimation` | `0x004AAF70` | Calls common request path `0x004AAFC0` with mode 0 |
| `QueueUnitAnimation` | `0x004A4AE0` | Calls `0x004AAFC0` with mode 2 |
| `SetUnitAnimationWithRarity` | `0x004AB110` | Maps rarity to mode flags, then tail-calls `0x004AAFC0` |
| `SetUnitAnimationByIndex` | `0x004AAF90` | Resolves unit/model and calls index helper `0x00966F20` |

`0x004AAFC0` resolves the unit and model, expands the requested animation
string/properties, and calls `0x00966C10` with the resulting sequence/request
data. `0x00966C10` checks model availability and required-animation property
bits before applying the request. The registration and common caller paths are
verified; the complete renderer-side sequence selection and blending contract
remains open. By-index animation uses a distinct helper and must be followed
separately.

Reproduce the wrapper chain with:

```sh
r2 -q -c 'e scr.color=0; pd 30 @ 0x0049D60A; pd 30 @ 0x004AAF70; pd 35 @ 0x004AB110; pd 35 @ 0x004AAF90; pd 80 @ 0x004AAFC0; pd 70 @ 0x00966C10; q' \
  'data/Warcraft III/Warcraft III.exe'
```

These are native-triggered API paths, not proof that ability classes invoke the
same functions for their authored cast, impact, or buff visuals. To test that
sharing claim, compare a controlled JASS call and a known ability visual while
hooking the constructors and their callers.
