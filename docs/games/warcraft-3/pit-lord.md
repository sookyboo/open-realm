# Pit Lord (`Nplh`) — Howl and Cleave (Patch 1)

## Source evidence and scope

The stock MPQ/MDX inspection supplied for this task identifies `Nplh` with
`ANrf` (Rain of Fire), `ANht` (Howl of Terror), `ANca` (Cleaving Attack) and
`ANdo` (Doom). Patch 1 implements the remaining Howl target presentation and
secondary-hit Cleave presentation/eligibility. It **does not** complete Rain of
Fire or Doom; their gameplay and visuals are separate follow-up patches.

| Ability | Stock presentation data | Runtime ownership |
| --- | --- | --- |
| `ANht` | `CasterArt=Abilities\Spells\Other\HowlOfTerror\HowlCaster.mdl` | One-shot on caster via `G_SpawnAbilityEffectTarget` |
| `BNht` | `TargetArt=Abilities\Spells\Other\HowlOfTerror\HowlTarget.mdl` | Persistent per-unit `BNht` status effect, using default attachment (no authored `Targetattach`) |
| `ANca` / `ACce` | `SpecialArt=Abilities\Spells\Other\Cleave\CleaveDamageTarget.mdl`, `Specialattach=chest` | Temporary effect on each eligible **secondary** melee hit |

The reported Howl caster model has a single nonlooping `Birth` (~0.87 s).
The Howl target model has `Birth`, looping `Stand` and short `Death` sequences.
The Cleave effect has a nonlooping `Birth` (~0.5 s). These sequence descriptions
come from the MPQ/MDX report; the test fixture model is a synthetic animation
model, not the retail artwork. Animation selection and physical orientation still
need visual in-game verification.

## Gameplay and lifecycle

- `AbilityHowlOfTerror_Execute` reads area, duration, level and `BNht` from
  `AbilityData` and applies its authored *ground/enemy* target mask through
  `S_SpellAllowsAreaTarget`. Status application uses
  `S_SpellApplyTimedTargetStatus` so `BNht.TargetArt` belongs to the status,
  not to the cast. It also respects `HeroDur` when a target is a Hero.
- The incoming master series already installed `BNht` attack damage reduction
  through `WC3_STATUS_MOD_ATTACK_DAMAGE_PERCENT` and spawned `ANht.CasterArt`.
  Those remain untouched. Refresh/recast reuses a single attached visual per
  target and status ID; removal on dispel, expiry or death uses
  `unit_removestatus`/`unit_statusdeath` and `G_DestroyStatusEffectTarget`.
  When no `TargetArt` is configured, gameplay still applies the debuff.
- `S_ResolveAttackHit` applies Cleave only for melee weapon profiles. The
  secondary loop applies the authored `targs` mask (stock
  `ground,enemy,neutral`), excludes the primary target and attacker, and uses
  `DataA` as the physical splash fraction and `Area` as the impact radius.
  Cleave damage is a physical attack effect: spell immunity is **not** a reason
  to discard an otherwise eligible secondary target. Other targeting rules,
  including ethereal immunity to physical attacks, remain in effect.
- Each secondary hit requests `WC3_EFFECT_SPECIAL` from the applying ability
  rawcode, with the alias's `Specialattach`, then its base ability's field, and
  finally the stock `chest` socket when neither supplies it. One-shot art does
  not change damage, spawn gameplay units or introduce persistent state.

## Verification and known boundaries

`games/warcraft-3/game/tests/t_spell.c` includes:

- `howl_of_terror_reduces_enemy_attack_damage_by_authored_25_percent` —
  incoming-series damage modifier, now with grounded test targets.
- `pit_lord_howl_target_art_tracks_status_refresh_and_expiry` — one status
  visual, authored area filtering, fresh/recast duration, dispel and expiry.
- `pit_lord_cleave_hits_only_eligible_ground_secondaries_with_chest_art` —
  ground-only physical splash, no duplicate primary art, no allied/air/structure
  or distant victim, socket metadata, and absence of splash from ranged hits.

`TestUI\Models\anim_pulse.mdx` is loaded from the test archive. No retail MPQ
is required for automated regression tests. The actual retail caster animation
(`spell,slam`), model rendering, per-effect scaling/orientation and target
attachment geometry need short visual inspection after user compilation.

No saved persistent fields, callback function registrations or network state
are added by Patch 1. Existing status and effect serialization applies.
