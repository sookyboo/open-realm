# Destructable Bridge Lifecycle And Pathing

This note records the current evidence and compatibility rules for Warcraft III walkable destructable bridges, with LT05 (`WoodBridgeLarge45`) as the primary campaign fixture. It separates retail-confirmed data/lifecycle behavior from OpenRealm compatibility behavior that still needs retail runtime comparison.

## LT05 profile

The retail destructable row used by Prologue02 has these relevant values:

| Field | Value |
|---|---|
| `file` | `Doodads\Terrain\WoodBridgeLarge45\WoodBridgeLarge45` |
| `pathTex` | `PathTextures\CityBridgeLarge45.tga` |
| `pathTexDeath` | `PathTextures\CityBridgeLarge45Death.tga` |
| `walkable` | `1` |
| `radius` | `200` |
| `cliffHeight` | `2` |
| `flyH` | `256` |
| sequences | `Stand`, `Death`, `Birth` |

LT05 is a data-driven walkable destructable. The authored radius is not applied as a normal radius-200 circular movement blocker over the bridge deck.

## Lifecycle

The same destructable object persists through death and restoration. Dead LT05 uses its death presentation/pathing. `DestructableRestoreLife(..., true)` restores life, selects the alive pathing state, runs `Birth`, and settles on `Stand`.

OpenRealm tests cover the retail fixture fields, `Death`/`Birth`/`Stand` selection, dead route blocking, alive pathing restoration, and repeated death/restore transitions.

## Horizontal pathing

Alive walkable destructables contribute a support mask over their authored pathing footprint. OpenRealm opens only supported cells over otherwise unwalkable terrain and then reapplies the alive pathing texture's blocked cells, so rails/non-deck cells remain restricted. Dead LT05 uses the death pathing texture and blocks crossing.

### Collision radius compatibility

OpenRealm retains a supported-centre radius compatibility rule: when a mover's centre is on an open walkable-surface cell, collision-radius samples may touch authored rail pathing without invalidating the centre position.

This is **confirmed active in OpenRealm live gameplay**, not yet retail-confirmed. A Prologue02 run after `objective complete 53` exhausted the 256-probe diagnostic limit and captured six Footman (`hfoo`, collision radius `31.0`) candidates with:

```text
point_normal=0 point_final=1 radius_exception=1
```

Representative blocked samples landed on supported bridge cells with `flags=0x02` and `pathable=0` while the Footman centre remained on valid deck support. Nine blocked sample cells were observed in the run, all associated with radius testing. Removing this rule would therefore change current live LT05 traversal.

### Diagonal corners

Walkable bridge decks now use the ordinary no-corner-cut rule. A simultaneous diagonal cell step is rejected when either cardinal neighbour is blocked, even when both endpoints are supported deck cells.

The earlier bridge-only diagonal escape was removed because the same 256-probe Prologue02 run observed:

- `deck_diagonal=1`: 26 cases;
- `diagonal_exception=1`: 0 cases;
- corner diagnostics: 59 cases;
- blocked cardinal corner diagnostics: 0 cases.

All observed supported-deck diagonals already had `line_normal=1 line_final=1`. This is evidence that the exception was not required by that live OpenRealm run; it is not proof of retail behavior. Focused tests preserve the normal corner rule for a synthetic bridge case with blocked cardinal rail cells.

## Vertical support

Horizontal support/pathing and vertical ground height are separate contracts. OpenRealm keeps a sparse registry of active `walkable=1` destructables and currently obtains local support height from rendered-model intersection, with a bounded same-path-cell seam fallback and a small frame-aware cache. Retail inspection proves a dedicated walkable-surface query occurs before `cliffHeight` fallback and that `flyH` participates later, but the exact retail height source remains unresolved.

The same-cell fallback is therefore compatibility behavior rather than established retail semantics. It must never sample across a 32-unit path-cell boundary.

For performance, horizontal bridge baking never asks the renderer to validate individual TGA cells. The authored alive/death path texture owns horizontal membership. Vertical MDX tracing runs only for units whose current cell is already in the baked walkable-surface mask, and steady `Stand` results use a 16-world-unit cache constrained to the same pathing cell; non-steady poses such as `Birth` remain frame-sensitive.

## Probe

Enable the bounded movement probe with:

```text
+set wc3_bridge_probe 1
```

Keep the noisier bridge diagnostics off unless needed:

```text
+set wc3_bridge_debug 0
```

The probe emits `WC3_BRIDGE_PROBE_MOVE`, `WC3_BRIDGE_PROBE`, `WC3_BRIDGE_PROBE_SAMPLE`, and `WC3_BRIDGE_PROBE_CORNER`. Important fields include `from_mask`, `to_mask`, `point_normal`, `point_final`, `radius_exception`, `line_normal`, `line_final`, `diagonal_exception`, and `deck_diagonal`.

For Prologue02, LT05 appears for this test flow only after running:

```text
objective complete 53
```

Its approximate runtime centre is `(5440, -4224)`.

## Remaining retail probes

The highest-value unresolved comparisons are:

1. collision-radius behavior where a supported deck centre is valid but an authored rail cell is touched;
2. movement-class differences for ground, amphibious, floating, and flying units;
3. exact vertical support provenance versus terrain height, model intersection, `cliffHeight`, and `flyH`;
4. alive/death pathing transition timing during `Birth` and `Death` animation frames.

Do not label OpenRealm's radius rule or model-height fallback as retail-confirmed until equivalent retail runtime evidence is captured.
