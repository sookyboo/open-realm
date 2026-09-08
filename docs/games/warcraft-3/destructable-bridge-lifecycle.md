# Destructable Bridge Lifecycle And Pathing

## Contract

`CreateDeadDestructableZ('LT05', ...)` binds the generated script handle to the preplaced map entity, leaves it dead, and starts the model's `Death` sequence. `DestructableRestoreLife(d, life, true)` clears the dead state, installs the alive pathing texture, and runs `Birth`; the normal `Stand` sequence follows when that transition completes. Dead and alive pathing are rebuilt into the static route map at each transition.

## Authoritative LT05 data

The ROC `Units\\DestructableData.slk` row is the source of truth:

| Field | Value |
|---|---|
| rawcode | `LT05` |
| model stem | `Doodads\\Terrain\\WoodBridgeLarge45\\WoodBridgeLarge45` |
| alive pathing | `PathTextures\\CityBridgeLarge45.tga` |
| death pathing | `PathTextures\\CityBridgeLarge45Death.tga` |
| walkable | `1` |
| collision size | `200` |

`WoodBridgeLarge45.mdx` contains `Stand`, `Death`, and `Birth` sequences. The separate `Doodads\\Cityscape\\Structures\\CityBridgeLarge45Destroyed\\CityBridgeLarge45Destroyed.mdx` is used by other object rows; it must not be substituted for LT05.

## Retail binary trace

The local retail executable is the 32-bit `data/Warcraft III/Warcraft III.exe`; this installation does not contain a
separate `Game.dll`. The JASS native registration table identifies these entries:

| Address | Meaning |
|---|---|
| `0x0049d169` | registers `DestructableRestoreLife` |
| `0x0048f6f0` | native argument/handle wrapper |
| `0x006d2a30` | destructable restore implementation reached by the wrapper |

The wrapper's registered signature is `(Hdestructable, real, boolean) -> void`. The implementation at `0x006d2a30`
uses the destructable object's virtual table rather than directly manipulating a pathing grid or model handle. The
observed calls include virtual slots `+0x13c`, `+0x130`, `+0x14c`, `+0x124`, `+0x0f4`, and `+0x148`; the requested
life is clamped before the life/state calls. The third argument is tested at `0x006d2b2d` and selects separate virtual
calls through slots `+0x8c` and `+0x90`, confirming that `birth=true` selects a distinct retail lifecycle branch.

This trace proves the native's state-transition shape, but not the semantic names of those virtual slots: the retail
binary is stripped and the `CDestructable` vtable has not yet been recovered. It is not evidence that
`DestructableRestoreLife` itself performs a model raycast or directly clears WPM cells; those operations may be inside
the virtual methods or in the subsequent world update.

Reproduce the wrapper trace with:

```sh
r2 -q -e scr.color=false -c 'pd 80 @ 0x0048f6f0; q' 'data/Warcraft III/Warcraft III.exe'
r2 -q -e scr.color=false -c 'pd 180 @ 0x006d2a30; q' 'data/Warcraft III/Warcraft III.exe'
```

The retail executable also registers `QueueDestructableAnimation`, `SetDestructableAnimation`, and
`SetDestructableAnimationSpeed`. The asset and native evidence support a single LT05 model lifecycle
(`Death`/`Birth`/`Stand`) with a separate pathing-state transition; the standalone
`CityBridgeLarge45Destroyed.mdx` object remains a different destructable type.

### Additional restore/death comparison

The nearby retail natives narrow the transition further:

| Address | Observation |
|---|---|
| `0x004a1c50` | `KillDestructable` resolves the handle and invokes the destructable virtual slot `+0x124` with the retail zero-real constant. |
| `0x004a7b90` | `SetDestructableLife` resolves the handle and invokes the same virtual slot `+0x124` with the requested real. |
| `0x006d2a30` | `DestructableRestoreLife` first obtains/clamps the requested life, then invokes `+0x14c`, `+0x124`, `0x006bef00`, `+0xf4`, and `+0x148` before its birth-sensitive branch. |
| `0x006d2b2d` | The registered boolean is tested here. `true` calls virtual `+0x8c` with zeroed transition arguments; `false` calls `+0x8c` with the death-style transition argument. Both branches then call `+0x90`. |
| `0x006d2b77` | The restore path publishes destructable state through `0x006d2ee0`, then dispatches a state-dependent update through `0x006be6a0`. One state branch also samples the object at `this+0x178` and calls `0x006cf8d0`. |

This comparison confirms that retail death and restoration share the destructable life/state virtual method,
while restoration with `birth=true` adds a separate presentation transition. The exact meaning of `+0x124`,
`+0x8c`, `+0x90`, and `+0x148` is still unresolved without the recovered `CDestructable` vtable, so these
slots must not be given guessed names. Neither `0x006d2a30` nor the short `KillDestructable` wrapper contains
a direct WPM-cell loop; pathing and support-height changes are therefore delegated to the object/world methods
or to a later world update.

The restore implementation also calls `0x007ffea0` on an auxiliary object at `this+0x178`. That helper changes
bit `0x100` in a flags word selected by two auxiliary-object fields. The bit operation is confirmed, but its
semantic name is not; it is not safe to label it as “walkable bridge height” or “pathing enabled” yet.

The shared pathing transition is visible at `0x006d2cd0`: after the destructable state bit is updated, retail calls
`0x006d30b0` with the current state. That helper selects the corresponding profile path reference and forwards it
through `0x00967800` and `0x00921450` into the shared pathing-surface manager. The creation path calls the same
helper at `0x006d0da9`, so dead creation and later restoration both register/update pathing through the same
overlay system.

### Retail walkable-data path

The destructable SLK schema loader at `0x006b2c80`–`0x006b30fc` registers these fields in one profile object:

| Profile offset | Field |
|---|---|
| `+0x80` | `pathTex` |
| `+0x84` | `pathTexDeath` |
| `+0xb8` | `flyH` |
| `+0xc0` | `walkable` |
| `+0xc8` | `cliffHeight` |
| `+0xd0` | `fixedRot` |

The retail routine at `0x006e3640` consumes the profile's `walkable` field in a separate branch from the ordinary
path/height checks. It calls `0x007ff460` with the walkable value and, when that test succeeds, proceeds through
the destructable surface/height path (`0x006eb160`). This is direct evidence that `walkable=1` selects special
runtime handling; it is not equivalent to stamping the alive TGA and clearing every underlying terrain bit.
The disassembly does not identify the final raster loop or the meaning of every helper argument, but the later
pathing ownership is now traceable: `0x006d30b0` selects the alive/death profile path reference and forwards it
through `0x00967800` and `0x00921450` to the shared pathing-surface manager. The current OpenRealm
`clear_walkable_surface()` implementation remains a compatibility hypothesis for raster semantics, not for the
existence of a dynamic overlay.

The same routine also reads the profile's `cliffHeight` field on the fallback branch. That is a second indication
that bridge support is coupled to the destructable's authored surface/height data, not only to collision radius.

### Dead creation is a separate constructor path

The native wrappers confirm that retail does not create a dead destructable and then simulate death with a normal
create call. `CreateDestructableZ` reaches `0x006d08e0`, while `CreateDeadDestructableZ` reaches `0x006d0fe0`.
Both feed the shared constructor at `0x006d09a0`, but the dead wrapper first resolves the profile's authored value
at `+0x6c` and passes that value through the dead-construction argument. This is separate from the later
`DestructableRestoreLife(..., true)` transition and explains why a dead preplaced LT05 can have a different initial
presentation/pathing state before any JASS restore call.

The dead constructor also performs the same profile/model setup work as the normal constructor; the binary does not
support treating a dead bridge as merely an invisible live model with a zero collision radius.

The helper reached from the walkable branch, `0x006eb160`, is a query-style routine: callers pass an output
structure plus an object/context, and it either writes a zero result or delegates to a virtual object method after
checking object flags. It does not contain a visible path-grid raster loop. Retail therefore separates
surface/object queries from the pathing-surface manager; the exact raster operation and radius rules remain open.

## Confirmed versus unresolved height/pathing behavior

Confirmed directly from retail data: LT05 has separate alive/death pathing textures and is marked walkable. Confirmed
directly from the MDX: `WoodBridgeLarge45.mdx` has `Stand`, `Death`, and `Birth` sequences. Confirmed from the native
disassembly: restore life has a birth-sensitive object transition.

Not yet directly recovered from the stripped executable: the exact map-grid operation, the semantic names of the
transition slots above, and whether the final support height comes from the authored `cliffHeight`/`flyH` data or a
later model/terrain query. The current model-trace and walkable-footprint behavior should therefore be described as
an OpenRealm/Warsmash parity implementation, not as a proven retail instruction-level equivalent.

## Diagnostics

Inspect the retail archive without extracting files:

```sh
build/bin/mpqtool -mpq 'data/Warcraft III/War3.mpq' cat 'Units/DestructableData.slk' | rg -n -C 4 'LT05|WoodBridgeLarge45|CityBridgeLarge45'
build/bin/mdxtool -mpq 'data/Warcraft III/War3.mpq' -model 'Doodads/Terrain/WoodBridgeLarge45/WoodBridgeLarge45.mdx' --info
```

The expected model output is three sequences: `Stand`, `Death`, and `Birth`. If a runtime log names `WoodBridgeLarge450.mdx`, model registration is appending a variation to an authored numeric stem and the animation lookup failure is downstream of that bad asset path.

Retail has a dynamic pathing-surface overlay for destructables, with separate alive/death profile references. The
binary does not yet prove whether clear overlay cells erase WPM restrictions or only add support in a separate
walkable-surface query. Do not describe OpenRealm's clear-cell behavior as retail-proven; compare the static WPM,
alive/death texture, and baked grid after each lifecycle transition. A restored bridge must have a connected
collision-sized route, not merely a nonzero `collision` field.

For the focused runtime trace, launch with `+set wc3_bridge_debug 2`. Level 2 prints the LT05 source/placed footprint and open-cell counts during the dead and restored bakes. Level 3 additionally prints the footprint grid (`.` open, `t` terrain-only blocked, `b` bridge-only blocked, `X` blocked by both) and bounded unit movement rejections near LT05. The trace is disabled at the default level `0`; capture the resulting `openwarcraft3.log` through the dead state and after the bridge cinematic.

Level 3 also prints bounded `WC3_BRIDGE_GROUND` records for units near LT05. For a walkable MDX, `surface_z` is the actual downward ray intersection with the rendered model at the unit's `(x,y)`, using the destructable origin, facing, scale, and animation frame. `inside=1` and `after` at least `surface_z` confirm that the unit is receiving the bridge deck as its support surface; `inside=0` or `dead=1` explains a unit that remains at the river terrain height.

The comparison points are Warsmash's [`PathingGrid.blitPathingOverlayTexture`](https://github.com/Retera/WarsmashModEngine/blob/main/core/src/com/etheller/warsmash/viewer5/handlers/w3x/environment/PathingGrid.java) and [`SequenceUtils`](https://github.com/Retera/WarsmashModEngine/blob/main/core/src/com/etheller/warsmash/viewer5/handlers/w3x/SequenceUtils.java), which respectively define the rotated/flipped overlay and primary-tag animation selection behavior.

## Verification

The WC3 engine tests cover the exact MDX sequence names, dead→restored route state, and Warsmash-compatible rotation/Y-flip placement. They require the configured ROC archive and are not run by this patch handoff; the user should run the affected suite locally.
