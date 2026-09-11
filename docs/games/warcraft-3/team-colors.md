# Team Colors

Warcraft III keeps ownership, alliance team, and presentation color as separate state. OpenRealm follows that contract:

- `playerState_t.number` identifies the player slot/owner.
- `playerState_t.team` identifies the alliance/team assignment used by lobby/gameplay rules.
- `playerState_t.color` is the Warcraft player-color index used by MDX `TeamColor`/`TeamGlow` replaceable textures.

Do not derive one of these values from another after map/lobby initialization.

## Rendering data flow

The Warcraft game module resolves a unit's visible team color and publishes it in `entityState_t.effect_flags` using `EFX_TEAM_COLOR_MASK`. The payload stores `playercolor + 1`; zero remains the generic "no published override" value and therefore does not collide with `PLAYER_COLOR_RED` (`0`).

The client/renderer remains game-agnostic: it consumes the published color and the MDX renderer selects `ReplaceableTextures\\TeamColor\\TeamColorXX.blp` and `TeamGlowXX.blp` for replaceable texture IDs 1 and 2.

A newly spawned Warcraft unit resolves its initial color in this order:

1. `UnitUI.teamColor` (`utco`) when the unit type forces a color.
2. Otherwise the owning player's configured `playerState_t.color`.

For units authored in `war3mapUnits.doo`, the placement's custom team-color field takes precedence when `UnitUI.customTeamColor` (`utcc`) permits custom colors and the placement value is not `-1`. If it is unavailable/disallowed, the normal `utco` then owner-color rules apply.

## Runtime color changes

`SetUnitColor` changes presentation only; it does not change ownership. Explicit unit colors are stored with `WC3_UNIT_COLOR_OVERRIDE_FLAG`, allowing explicit red to remain distinguishable from the default/no-override state across campaign game-cache restore. Legacy nonzero raw `unit_color` values remain accepted when restoring older OpenRealm state.

`SetPlayerColor` updates the player's configured color and recolors existing units that are still displaying that player's previous color. Units already displaying a different explicit/custom color remain unchanged. This matches the Warsmash behavior used as the current compatibility reference.

`SetUnitOwner(unit, player, changeColor)` always transfers gameplay ownership. When `changeColor` is true, the unit is recolored to the new owner's configured player color. When false, its current visible color is preserved independently of the new owner.

## Lobby behavior

The game-setup lobby transports team and color independently. Maps with Fixed Player Settings disable both team and color controls; their slot colors cannot be cycled by the host.

## Known limits

OpenRealm currently exposes Warcraft player-color handles through the extended color range, but the active multiplayer/player and MDX texture contracts are still `MAX_PLAYERS == 16` / `MAX_TEAMS == 16`. Extending rendered/lobby colors past the classic 16 is separate work because it changes those shared limits and resource assumptions.

Map `config()` is also not yet executed as a distinct pre-lobby configuration phase. The JASS `SetPlayerColor` native is functional, but exact authored-map-before-lobby precedence depends on completing that lifecycle work described in [UI Flow](architecture/ui-flow.md).

## Verification

Focused in-engine coverage lives in `games/warcraft-3/game/tests/t_api.c` and covers:

- recoloring existing owner-colored units through `SetPlayerColor`;
- preserving an explicit unit color when the owner player's color changes;
- `SetUnitOwner` with both values of `changeColor`;
- `utco` / `utcc` / `war3mapUnits.doo` custom-color precedence;
- explicit red `SetUnitColor` state and campaign game-cache restore.
