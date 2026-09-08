# Retail Destructable Bridge Specification

## Purpose

This document specifies the retail Warcraft III behavior that OpenRealm should reproduce for walkable
destructables such as campaign bridge `LT05`. It distinguishes requirements confirmed from retail data and binary
inspection from implementation details that remain unresolved.

## Authoritative data

The destructable profile is loaded from `Units\\DestructableData.slk`. For `LT05` the retail row contains:

| Field | Retail value/meaning |
|---|---|
| `file` | `Doodads\\Terrain\\WoodBridgeLarge45\\WoodBridgeLarge45` |
| `pathTex` | `PathTextures\\CityBridgeLarge45.tga` |
| `pathTexDeath` | `PathTextures\\CityBridgeLarge45Death.tga` |
| `walkable` | `1` |
| `radius` | `200` |
| model sequences | `Stand`, `Death`, `Birth` |

The separate `CityBridgeLarge45Destroyed.mdx` is used by other destructable rows and is not LT05's death model.

Retail parses `pathTex`, `pathTexDeath`, `flyH`, `walkable`, `cliffHeight`, and `fixedRot` as profile fields. For
LT05 specifically, `walkable=1`, `cliffHeight=2`, `flyH=256`, `fixedRot=0`, and `radius=200`. A
walkable bridge is therefore a distinct data-driven surface type, not an ordinary circular destructable with a
special model.

## Lifecycle contract

### Creation

`CreateDestructableZ` and `CreateDeadDestructableZ` use different native constructor wrappers but share the main
destructable construction path. Dead creation supplies an additional profile-derived argument and initializes the
dead state during construction.

The dead state must:

1. retain a valid destructable object and model;
2. select the death presentation/pathing state;
3. remain non-crossable;
4. avoid treating the authored collision radius as a dynamic circular movement blocker.

### Restoration

`DestructableRestoreLife(d, life, birth)` is registered as:

```text
(Hdestructable, real, boolean) -> void
```

The retail implementation:

1. validates the destructable and clamps the requested life;
2. updates the destructable life/state through virtual object methods;
3. performs common state and presentation updates;
4. branches on the `birth` boolean;
5. uses a distinct birth transition when `birth=true`;
6. publishes the resulting destructable state and runs a state-dependent update.

The relevant retail addresses in the local 32-bit executable are:

| Address | Role |
|---|---|
| `0x0049d169` | native registration for `DestructableRestoreLife` |
| `0x0048f6f0` | JASS handle/argument wrapper |
| `0x006d2a30` | restore implementation |
| `0x006d2b2d` | `birth` branch point |
| `0x006d2ee0` | state publication/update |
| `0x006be6a0` | state-dependent follow-up update |

`KillDestructable` and `SetDestructableLife` share the retail life/state virtual method used by restoration. A
death transition is therefore a state change on the same object, not replacement by an unrelated invisible entity.

## Model presentation

`WoodBridgeLarge450.mdx` contains three sequences:

| Sequence | Role |
|---|---|
| `Stand` | intact steady state |
| `Death` | destroyed/broken presentation |
| `Birth` | restoration transition |

The required lifecycle is:

```text
dead: Death -> restored with birth=true: Birth -> Stand
alive: Stand
```

Animation selection must resolve tagged sequence names according to Warcraft III required-animation semantics. Exact
case-sensitive string lookup is insufficient when alternate tagged sequences are present. An unresolved death or
birth sequence must be reported; hiding the model is not retail behavior.

## Pathing contract

### Dead state

The death pathing texture is active while the destructable is dead. The bridge footprint must remain blocked for
ground units, including units whose route would otherwise cross the underlying water.

### Alive state

The alive pathing texture is active after restoration. Its clear support lane is usable by ground units, while
authored blocked cells such as rails remain restrictions where applicable.

Retail walkable handling is not equivalent to either of these incorrect implementations:

- stamping a radius-200 circular obstacle for the whole destructable;
- clearing every WPM `nowalk` bit inside the texture rectangle.

Retail parses `walkable=1` through a dedicated runtime branch. The observed branch calls a surface/context query and
also consults authored `cliffHeight`/height-related profile data. The exact retail map-grid update routine has not
yet been identified in the stripped executable.

OpenRealm's implementation must consequently keep these concepts separate:

1. ordinary destructable blocking;
2. walkable bridge support surface;
3. terrain/WPM restrictions outside the supported bridge lane;
4. unit collision-radius expansion;
5. movement height/support selection.

The bridge support lane may override the underlying water restriction only where retail's walkable-surface rules
permit it. It must not globally erase terrain pathing or bypass ordinary unit-radius and diagonal-corner rules.

### What the executable proves about pathing storage

The JASS registration for `SetTerrainPathable` points to `0x004aa920`, which forwards to `0x007f60b0`. That
routine converts the supplied world coordinates to a terrain cell, bounds-checks the cell, then modifies only the
packed pathing byte selected by the pathing-type argument. Setting a flag ORs its bit into that byte; clearing a
flag removes only that bit. It does not replace the cell and does not clear the other pathing channels.

This proves the retail terrain API has compositional channel semantics. It does not prove that a destructable
bridge calls this JASS-facing routine; the restore implementation at `0x006d2a30` does not call `0x007f60b0`
directly.

The destructable path is now traceable farther. Retail helper `0x006d30b0` selects one of two profile pathing
references based on a state boolean, then calls `0x00967800`. That helper obtains the destructable's shared pathing
surface object and forwards the selected reference to `0x00921450`, which dispatches through the pathing-surface
manager to add or remove the registered footprint. The same shared manager also maintains a list of pathing
surfaces and calls the footprint operation for each registered entry.

The restore-side call site is `0x006d2cd0`: after the state flag is changed, it calls `0x006d30b0` with the
current state bit. The creation path also calls `0x006d30b0` at `0x006d0da9`, which explains why a dead preplaced
bridge has pathing state before any JASS restoration. This is lifecycle evidence, not just a renderer-side model
change.

This is direct binary evidence for a dynamic destructable pathing overlay, separate from the JASS terrain-cell API.
It also explains why restoration must switch the profile pathing reference rather than merely toggle a collision
radius. The exact raster implementation below the shared manager is still unresolved, but the overlay ownership and
alive/death selection are no longer hypotheses.

The next layer does not resolve the raster semantics: `0x00921450` dispatches to `0x0091f590` or `0x0091f700`,
which search registered pathing-resource entries and call `0x009225f0` to update their references. These routines
do not visibly iterate terrain cells or perform radius expansion. The cell compositor is below this resource layer
or behind a virtual call, so the binary alone cannot establish whether a clear bridge pixel removes a WPM bit.

The reachable destructable/pathing call chain likewise contains no identifiable bridge-specific unit-radius or
diagonal-corner test. Those rules appear to belong to the general movement/path query layer and cannot be inferred
from the destructable overlay code.

## Height and movement

Alive walkable bridges provide a support surface for compatible ground units. Dead bridges do not provide that
surface. Floating/boat-style movement must remain governed by its own water rules rather than being treated as a
ground unit on the bridge deck.

Retail routine `0x006e3640` makes the height/support decision. It first tests the profile's `walkable` field and
passes through a dedicated surface/context query (`0x007ff460`, then `0x006eb160`). Only when that route does not
produce support does it test `cliffHeight`; a later branch uses the profile `flyH` value as another height-related
input. This proves `walkable` is a separate support mechanism and that `cliffHeight` is a fallback/step-height
input, not simply the unconditional deck Z. The executable still does not prove whether the successful walkable
surface height ultimately comes from model geometry, terrain height, or a combination; that requires a live sample
of the returned height against controlled terrain and model geometry.

`flyH` is read in the same support decision, but static inspection does not establish whether its result is visual
model elevation, flying-unit support, or a shared intermediate. It must not be conflated with `cliffHeight` in the
implementation until runtime samples distinguish them.

## Proof status

| Question | Status from local retail assets/binary | Consequence |
|---|---|---|
| LT05 data and model lifecycle | Confirmed: `walkable=1`, `cliffHeight=2`, `flyH=256`, `pathTex`/`pathTexDeath`, and `Stand`/`Death`/`Birth` | Keep the normal destructable lifecycle and data-driven profile fields. |
| Support-height source | Partially confirmed: dedicated walkable surface query precedes `cliffHeight` fallback | Do not make model intersection or a fixed offset the authoritative rule yet. |
| Alive pathing overlay | Confirmed: `0x006d30b0` selects alive/death profile references and `0x00967800`/`0x00921450` update a shared pathing-surface manager | Model the bridge as a registered dynamic overlay, not a circle blocker or JASS terrain edit. |
| Clearing underlying WPM | Not supported by evidence; terrain API is per-channel and compositional; overlay raster semantics remain unresolved | Never clear unrelated terrain channels as a side effect of bridge restoration. |
| Unit-radius expansion | No bridge-specific test found in the overlay call chain | Requires a boundary-fit retail experiment; do not infer it from the overlay raster. |
| Diagonal/corner handling | No bridge-specific test found in the overlay call chain | Requires a rail-grazing/diagonal retail experiment. |
| Birth/death pathing timing | State transition and overlay update call sites confirmed; animation-frame/event timing unresolved | Sample pathability and movement every frame during both animations. |
| Ground/amphibious/floating/flying interaction | Unresolved statically | Test each movement class independently. |

## Required OpenRealm behavior

An implementation is retail-compatible when all of the following are true:

- LT05 is dead before the campaign trigger and uses the broken/death presentation.
- Dead LT05 blocks a ground route across the river.
- `DestructableRestoreLife(..., true)` changes the object to alive state and performs the birth lifecycle.
- Alive LT05 uses the alive pathing data and exposes a connected ground route across its supported lane.
- Units receive the bridge support height while on the alive deck.
- The bridge does not create a radius-200 dynamic circle blocker.
- Terrain restrictions outside the supported lane remain authoritative.
- Unresolved MDX sequences, pathing textures, or profile fields are logged as errors.

## Verification plan

Use focused tests and one bounded campaign run:

1. inspect LT05 profile fields and MDX sequences;
2. assert dead-state model/pathing/life state;
3. assert dead-state route failure across the footprint;
4. restore with `birth=true` and assert birth-to-stand lifecycle;
5. assert alive-state route success for a collision-sized ground unit;
6. assert bridge support height while the unit is on the deck;
7. assert water and rail cells outside the support lane remain blocked;
8. capture `wc3_bridge_debug` output around the dead and restored bakes.

The three focused live-retail probes needed to finish the unresolved rows are:

1. restore and kill LT05 while sampling pathability and a unit's position/Z every frame through `Birth` and `Death`;
2. repeat the crossing with unit radii that fit the clear lane, exactly touch a rail, and are one cell wider;
3. repeat the same route with ground, amphibious, floating, and flying units.

## Static-analysis boundary

The local installation contains the retail executable and archives, but no compatible execution layer or debugger
for the 32-bit game process (`wine`, `winedbg`, and `qemu-i386` are unavailable). Static analysis has now traced
the destructable state transition into the shared pathing-surface manager, but that manager's final cell compositor
is reached through lower-level or virtual dispatch. The retail executable therefore cannot answer the following from
code inspection alone:

- whether a clear alive-bridge pixel subtracts a WPM restriction or supplies a separate walkable support bit;
- whether the movement query expands a unit radius before or after the walkable-surface test;
- whether diagonal corner validation is ordinary grid validation or surface-aware;
- the exact frame at which the overlay changes during Birth and Death.

Those are runtime-observation questions, not missing labels for the functions already recovered.

The height probe should compare the unit Z at several deck points with terrain Z, the model-intersection Z, and the
profile-derived `cliffHeight`/`flyH` candidates. Without a running retail process or an instrumented retail trace,
the remaining questions cannot be proven from the stripped executable alone.

Useful retail inspection commands:

```sh
build/bin/mpqtool -mpq 'data/Warcraft III/War3.mpq' cat 'Units/DestructableData.slk' | rg -n -C 4 'LT05|WoodBridgeLarge45|CityBridgeLarge45'
build/bin/mdxtool -mpq 'data/Warcraft III/War3.mpq' -model 'Doodads/Terrain/WoodBridgeLarge45/WoodBridgeLarge45.mdx' --info
r2 -q -e scr.color=false -c 'pd 180 @ 0x006d2a30; q' 'data/Warcraft III/Warcraft III.exe'
```

## Confirmed limitations

The exact semantic names of the retail `CDestructable` virtual-table slots and the final retail WPM update path
are unresolved because the executable is stripped. Those details must not be invented in code or documentation.
Any OpenRealm behavior that clears or overrides terrain cells should remain marked as a parity implementation or
explicit compatibility decision until the retail grid update is recovered.
