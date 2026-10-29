# Flame Strike

Flame Strike (`AHfs`, shared behavior `CAbilityFlameStrike`) has a point-target
warning, a rank-specific landing effect, an ongoing area fire, and a damage
effect on units hit by its pulses. The damage thinker already read the timed
pulse data, but previously emitted none of these presentation effects.

## Authored contract

In the TFT `AbilityData.slk` row, `AHfs` uses a 1.33 second `Cast` delay, a 200
area, a 9 second `Dur`, a 2.67 second `HeroDur`, `BuffID=BHfs`, and
`EfctID=XHfs`. `DataA`/`DataB` and `DataC`/`DataD` provide full and reduced
pulse damage and intervals; `DataE` is the structure multiplier and `DataF`
the aggregate cap. `AbilityStrings.txt` describes the full-damage phase followed
by residual damage.

The related `HumanAbilityFunc.txt` rows author these visuals:

- `AHfs.EffectArt`: `FlameStrikeTarget.mdl`, the warning art at the selected
  point during the cast delay.
- `AHfs.SpecialArt`: `FlameStrike1.mdl`, `FlameStrike2.mdl`, and
  `FlameStrike.mdl`, selected by rank for the landing effect.
- `BHfs.TargetArt`: `FlameStrikeDamageTarget.mdl`, emitted on units hit by a
  damage pulse.
- `XHfs.EffectArt`: `FlameStrikeEmbers.mdl`, the persistent ground field. The
  `XHfs` row also authors its looped fire sound.

RoC 1.0 has no `AHfs` `AbilityData` row, so Flame Strike has no RoC-only
fallback. The TFT `EfctID` field resolves the fire-field object without a
compatibility workaround.

## Runtime ownership

The warning and rank-specific impact use temporary effect entities so their
authored animations finish naturally. The ember field is owned by the Flame
Strike damage thinker; the thinker starts it at the cast-delay deadline and
destroys the owned field when the damage lifetime ends. Each successful pulse
emits the buff row's target art on affected units.

The regression test drives the production point-cast path, advances to the
authored cast deadline, and verifies the warning, rank-one impact, ember field,
and per-unit damage art in order. Its model paths come from the test archive's
`HumanAbilityFunc.txt` fixture rather than local Warcraft installation data.
