# Mana Flare

## Contract

`Amfl` is TFT-only `CAbilityManaFlare` (parent `AAsm`). ROC `AbilityData`
has no `Amfl` row. It is **not** FrostNova (`AHfn` / `CAbilityFrostNova`);
ignore `ability_map.c` and the old TODO comment.

No-target channeled spell (`AB_SPELL | AB_CHANNEL`, `SPELL_TARGET_NONE`).
Activation spends Cost, starts the shared channel lock (movement cancels),
and applies `BuffID` token `Bmfl` for `Dur`/`HeroDur` seconds. `Untip` /
Stop / move cancel ends the channel and strips `Bmfl`. `Bmfl` expiry (via
`AB_UPDATE`) also clears `channel.code`. `Bmfa`
(`CBuffManaFlareAoe`, parent `BAOE`) is presentation-only and is not required
for damage or armor. Phase Shift (`Apsh`) is rejected during an active `Amfl`
channel without spending mana or interrupting it.

While `Bmfl` is active, nearby enemy units that successfully cast a spell
take damage proportional to that spell's mana cost. Friendly casts and
out-of-`Area` enemies are ignored.

| Field | Stock | AbilityMetaData | Runtime |
| --- | ---: | --- | --- |
| `DataA` | 3 | Unit - Damage Per Mana Point | unit damage = `min(DataC, cost * DataA)` |
| `DataB` | 1 | Hero - Damage Per Mana Point | hero damage = `min(DataD, cost * DataB)` |
| `DataC` | 90 | Unit - Maximum Damage | unit damage cap |
| `DataD` | 50 | Hero - Maximum Damage | hero damage cap |
| `DataE` | 12 | labeled "Damage Cooldown" | **armor bonus** while `Bmfl` is active (`Ubertip` binds `<Amfl,DataE1>`) |
| `DataF` | 1 | Caster Only Splash | non-zero → splash only hits units with a mana pool |
| `Area` | 750 | — | detection radius around the Faerie Dragon |
| `Rng` | 200 | — | splash radius around the primary victim |
| `Cast` | 0.75 | — | seconds between flares from one `Amfl` unit |
| `Dur`/`HeroDur` | 30 | — | `Bmfl` lifetime / channel length |
| `targs` | air,ground,enemy | — | flare victim filter (not the cast target) |
| `BuffID` | `Bmfl,Bmfa` | — | `Bmfl` on caster; `Bmfa` unused in gameplay |

`DataE` AbilityMetaData display name conflicts with the ubertip armor
binding. Stock `DataE=12` matches the documented armor bonus, and stock
`Cast=0.75` matches the documented flare interval, so runtime treats
`DataE` as armor and `Cast` as the fire cooldown.

## Data Flow

```text
AbilityData.slk (Amfl)
  -> Cost, Cool, Area, Rng, Cast, Dur, DataA-F, BuffID, targs
CAbilityManaFlare
  -> S_CastNoTargetSpell / A_EXECUTE: attributed Bmfl + AB_CHANNEL lock
  -> A_CANCEL: strip Bmfl
  -> A_UPDATE: if channel is Amfl and Bmfl is gone, S_SpellCancelChannel
spell_commit (successful cast)
  -> S_ManaFlareOnCast(caster, code, level)
     scan enemies-of-caster with Bmfl and an active Amfl channel in Area
     throttle per Bmfl instance using status.next_tick (first cast at time zero works)
     damage primary via S_SpellDamage; optional Rng splash
G_UnitArmorValue
  -> S_ManaFlareArmorBonus (DataE while Bmfl)
```

## Registry

```c
{ "Amfl", CAbilityManaFlare, AB_SPELL | AB_CHANNEL | AB_UPDATE, SPELL_TARGET_NONE },
```

## Persistence and remaining parity

The per-channel flare interval deadline uses `heroabilitystatus_t.next_tick`.
`data` remains reserved for the status payload/legacy origin rawcode; using it
for cast timestamps could dispatch an unrelated status ability. Save format 128
rejects older Mana Flare timestamp representations. `Bmfl` is explicitly
attributed to `Amfl` for status lifecycle dispatch.

`Apsh` currently delegates its non-channel behavior to the existing Divine
Shield implementation; true Phase Shift mechanics and any Mana Flare missile
visual effects are separate follow-up work.

## Diagnostic Workflow

```sh
build/bin/ability_audit -data 'data/Warcraft III' -raw Amfl
```

## Verification

```sh
make test-wc3-engine WC3_PATTERN='wc3_spell.mana_flare*'
```

Focused tests cover procedure registration, authored non-stock DataA damage,
enemy-cast trigger, out-of-area ignore, friendly-cast ignore, armor bonus,
Cast interval gating, channel/expiry cleanup (`channel.code == 0` after `Bmfl`
expires), splash mana-pool filter, time-zero cooldown, active channel gating, and
Phase Shift rejection without mana loss.
