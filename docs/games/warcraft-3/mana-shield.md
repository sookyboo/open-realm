# Mana Shield

## Contract

`ANms` is TFT `CAbilityManaShield`, whose extracted parent is `AAsm`
(`CAbilitySimpleSpell`). Creep `ACmf` is a `code=ANms` alias (stock DataA=2, not
ANms L1's 1). Both rows share `mana_shield_orders`. It is a no-target toggle, not
a passive. Activation adds the authored `BuffID` status and deactivation removes
it. The stock TFT row uses `BNms`, and the stock immediate orders are
`manashieldon` (`852589`) and `manashieldoff` (`852590`). Those orders are
directional: issuing the on order twice must leave the shield on rather than
toggle it off. `S_ManaShieldDamage` and `A_ORDER` resolve the owner's alias
through `G_AbilityCode` so an `abilList` of `ACmf` is not ignored.

The TFT `AbilityData.slk` row has three levels:

| Field | Level 1 | Level 2 | Level 3 | Meaning |
| --- | ---: | ---: | ---: | --- |
| `DataA` | 1 | 1.5 | 2 | damage absorbed per mana |
| `DataB` | 1 | 1 | 1 | fraction of incoming damage offered to the shield |
| `BuffID` | `BNms` | `BNms` | `BNms` | active shield status |

`NeutralAbilityStrings.txt` confirms the DataA direction with “1/1.5/2 damage
per point of mana” and supplies the Activate/Deactivate presentation. Do not
interpret DataA as mana spent per absorbed damage; that reverses level scaling.

## Damage Flow

`CAbilityManaShield` owns status changes. `S_ManaShieldDamage()` runs at the
central `T_Damage()` boundary and only acts when the authored buff is active.
For incoming integer damage $D$, mana $M$, DataA ratio $r$, and clamped DataB
fraction $p$:

$$
A = \min(Dp, Mr), \qquad M' = M - A/r, \qquad D' = D - \lfloor A \rfloor
$$

If mana reaches zero, the buff is removed immediately. Learned-but-inactive,
explicitly deactivated, and zero-mana states leave ordinary damage unchanged.
No extra `edict_t` state is needed because `abilstatus` is the runtime source of
truth and remains covered by the existing save/load contract.

## Verification

Inspect the TFT class and normalized row with:

```sh
rg '"ANms"' games/warcraft-3/tft-ability-classes.txt
build/bin/ability_audit -data 'data/Warcraft III' -tft -raw ANms
```

The production-path regression casts and orders the toggle, checks `BNms`, and
drives partial and complete absorption through `T_Damage()`:

```sh
build/bin/openwarcraft3-tests -data build/tests +dedicated 1 \
  +test wc3_spell.mana_shield_toggle_status_controls_authored_damage_absorption
make test-wc3-engine WC3_PATTERN='wc3_spell.creep_mana_shield*'
```

### Retail depletion observation (TFT)

Rank 1 `ANms` was probed in Retail 1.29.2 on
`War3xLocal.mpq:Maps/FrozenThrone/Campaign/OrcX01.w3x`. The map script was
checked for `ANms`, `BNms`, `UnitRemoveAbility`, and player ability-availability
gates; it contains no Mana Shield restriction. The Retail executable SHA-256
was `3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`.

After gameplay began, the JASS probe created three Player 0 Naga Sea Witches
(`Nngs`) and learned rank 1 with `SetHeroLevel` and `SelectHeroSkill`. It
activated `manashieldon` on two units and left the third shield inactive. Two
seconds later, it set the shielded units to 20 and 1 mana, set the inactive
unit to 1 mana, then used the same `UnitDamageTarget` call against each. All
three damage calls and both shield orders were accepted. The fresh
`PreloadGen` result was:

```text
MS probe=manashield-tft-depletion-v2 L=111 ON=11 HIT=111 full(M=10.000,L=0.000,B=1) low(M=0.000,L=7.589,B=0) off(M=1.000,L=8.432,B=0)
```

`L=111`, `ON=11`, and `HIT=111` mean all three skills were learned, both
activation orders were accepted, and all three damage calls were accepted.
Within each tuple, `M` is remaining mana, `L` is life lost, and `B` is the
queried `BNms` level. With ample mana, the shield spent 10 mana, prevented
life loss, and remained active. With 1 mana, it spent the mana, reduced life
loss relative to the inactive control, and `BNms` was absent after the hit.
The inactive control retained its mana and took more life damage. This
confirms depletion removes the shield and the shield absorbs damage while
mana remains. The fractional life-loss values are recorded as observed; this
probe does not establish an exact damage formula independent of Retail armor
and regeneration. It covers rank 1 only, not ranks 2–3 or the `ACmf` creep
alias. The capture status was `ready_for_review`; the result above was
reviewed manually. Temporary map, JASS, launch records, and capture are under
`/tmp/wc3-retail-manashield-depletion/run-v2/`; the source fragments and
manifest are under `/tmp/wc3-retail-manashield-depletion/`.
