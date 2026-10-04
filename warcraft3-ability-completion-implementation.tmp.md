# WC3 Ability Completion — Temporary Implementation Plan

Status: planning only. This temporary working plan does not change code or
replace the retained scope and preservation rules in
[`warcraft3-ability-completion-plan-logic-pass.md`](warcraft3-ability-completion-plan-logic-pass.md).
The committed baseline is the ability-family/lifecycle work through phase 30.

## Goal and boundaries

Complete only the named gameplay logic with strong retail evidence. Keep
behavior in the owning `games/warcraft-3/game/skills/s_*.c` procedures, use
the concrete ability rawcode for authored values, preserve working behavior,
and avoid intentional presentation changes. Reuse the existing corpse,
status, summon, spell, identity, relocation, and save/load lifecycle helpers.
Do not add parallel lifecycle systems or guessed constants.

Before changing each row, follow the ability workflow: read the applicable
`AGENTS.md`, `CONTRIBUTING.md`, ability architecture docs and owning code;
inspect the tests; poll ROC and TFT AbilityData aliases and relevant UnitData
/BuffData with `ability_audit`; then write/update the ability contract document.
Where evidence is still uncertain, defer only that narrow behavior and record
the unresolved question.

Keep similarly named ward abilities distinct. Retail JASS verifies **Sentry
Ward** (`Aeye`, order `evileye`) creates `oeye`, and separately verifies
**Serpent Ward** (`AOsw`, order `ward`) creates an owned rank 1 `osp1` that is
gone by 45 seconds after an initial count at 3 seconds. Stock `AOsw`
`Dur`/`HeroDur` is 40 seconds. Do not transfer Sentry Ward's unit or status
results to Serpent Ward. Higher Serpent Ward ranks, exact expiry timing and
combat behavior remain open. The observations are in
[`sentry-ward.md`](docs/games/warcraft-3/sentry-ward.md).

Retail lifecycle probes also verify Mana Flare (`Amfl`) `Bmfl` removal after
the accepted `manaflareoff` order and natural absence by 35 seconds (stock
`Dur=30`), and rank 1 Mana Shield (`ANms`) absorption/depletion with `BNms`
removed after mana reaches zero. These observations constrain existing
ability contracts; they do not add those abilities to this implementation
scope. Exact Mana Flare expiry timing, higher Mana Shield ranks and its
`ACmf` alias remain open. Evidence and limits are in
[`mana-flare.md`](docs/games/warcraft-3/mana-flare.md) and
[`mana-shield.md`](docs/games/warcraft-3/mana-shield.md).

## Implementation work

| Ability | Owning area / planned change | Required evidence and regression focus |
|---|---|---|
| Resurrection | `s_requested_abilities.c`: retain corpse eligibility/revival; enforce authored maximum; rank eligible corpses by the established corpse-power field; restore original owners and keep corpse identity. | Alias, area, count, mask, corpse ranking and raised-unit flags. Test over-limit selection, equal-rank existing tie behavior, allied-owner restoration and same-edict revival. |
| Phoenix Fire | `s_ability_stubs.c` plus attack/status hooks as appropriate: implement passive cooldown acquisition, instant hit and timed burn without issuing a cast/move order. | Alias, cooldown, radius, target mask, instant/periodic damage, duration, BuffID and damage classification. Test no legal target, eligible target, timer, burn refresh/stack and target choice. |
| Earthquake | `s_requested_abilities.c`: preserve fixed channel point; pulse authored building damage and ground-unit slow while channel lives; stop immediately on interruption. | Duration, area, target mask, damage/slow fields, cadence and any tree/destructible interaction. Test ground vs air, buildings and every channel-ending path. |
| Mirror Image | `s_mirror_image.c`: authored count/duration, illusion damage dealt/taken, illusion classification, and avoid copying persistent Hero state the retail image does not own; preserve placement/shuffle. | Count, duration, multipliers, illusion identity and field-copy contract. Test incoming/outgoing damage, dispel sensitivity, Hero state and identity/lifetime. |
| Purge | `s_orc_abilities.c`: preserve dispel and summon damage; hostile-only initial slow/brief stop with progressive recovery; keep Purge slow outside ordinary dispel. | **Retail JASS verified for stock TFT `Apg2`:** allied cast spent mana and target movement approximated its control at 1.5 s; hostile target was strongly suppressed relative to its control at 1.5 and 3.5 s, then moved by 6.5 s. Exact recovery, allied dispel, and other alias fields/behavior remain open. See [`ability-verification-review.md`](docs/games/warcraft-3/ability-verification-review.md#retail-purge-friendly-and-hostile-target-verification-october-4-2026). |
| Serpent Ward (`AOsw`) | `s_campaign_abilities.c`: point-cast authored per-level ward as an immobile, timed summoned Ward; let ward UnitData govern attacks and immunity. | **Retail JASS verified for TFT rank 1:** a learned stock cast creates owned `osp1`; one ward is present at 3 seconds and none at 45 seconds. TFT data authors `Dur`/`HeroDur=40`, `UnitID` by rank, range and cost. Still test ranks 2–3, exact expiry boundary, legal air/ground attacks, movement and immunity. Do not use Sentry Ward (`Aeye`/`AIsw`, `evileye`/`oeye`) as evidence for this ability. |
| Carrion Swarm | `s_area_spell.c`: replace point burst with caster-to-point travelling line/wave; damage each legal unit once, stop at authored total cap and honor alias masks. Do not use homing unit-target projectile helper. | Alias-specific target mask, width/range/speed, damage, cap and damage type. Test positions on/off path, one-hit behavior, cap and ward exclusions. |
| Immolation | `s_ability_stubs.c`: implement one authoritative toggle state; charge activation and recurring mana costs; pulse damage to legal nearby enemy ground units; stop on off/death/ability loss/failed next drain. | Activation cost, drain and damage cadence, area, mask and any mana buffer. Test boundary mana values, toggle, death and ability removal. |
| Faerie Fire | `s_melee_spells.c`: keep current armor/duration behavior; add source-owned vision of affected unit for exact status lifetime; refresh and dispel only this reveal contribution. | Alias BuffID/mask/duration and any reveal fields. Test refresh, expiry, dispel, multiple reveal sources and unrelated fog state. |
| Crow Form / Night Elf Form | `s_raven.c`: keep same unit identity and load each form's gameplay UnitData; preserve HP/mana/XP/inventory absent contrary evidence. | Both UnitData rows, form mapping and Mark of the Talon/Faerie Fire gating. Test movement/attacks/abilities and reversal. |
| Root / Uproot | `s_utility_abilities.c` and existing Ancient-root state: switch same identity between rooted structure functions and mobile uprooted combat state; reroot only at legal placement. | Every Ancient's two UnitData forms, attack/armor/movement, footprint, structure functions and exceptions. Test build/research/resource/repair gates, pathing, attack and reroot failure/success. |
| Shadow Strike | `s_warden_abilities.c`: immediate initial hit; periodic poison for full duration; independently expire movement slow; poison ticks do not refresh either status. | Alias damage, cadence, total/slow duration, mask, BuffID and damage classifications. Test exact event schedule, slow expiry, poison continuation and recast. |
| Cold Arrows | Attack-event hook with owning ability procedure: autocast attack modifier; spend mana once and apply authored bonus plus attack/movement slow only to eligible attacks with enough mana. | All aliases, per-shot cost, bonus, slow values/duration, mask and autocast metadata. Test enabled/disabled, insufficient mana, invalid target and ordinary attack preservation. |
| Cluster Rockets | Own implementation in Tinker/creep ability procedure: remove Flame Strike routing; author its bombardment schedule locally; apply legal damage, ground stun and building rule. | `ANcs` Area/Data fields, duration/cadence/count/cap, mask, building behavior and damage type. Test with controlled row variants and ground/air/building targets. |
| Engineering Upgrade | Existing ability/stat recomputation seams: compute rank-derived bonuses from base state, including Tinker damage/move, Cluster Rockets area, Pocket Factory production, and Robo-Goblin armor/Strength/Demolish; do not accumulate ranks. | `ANeg` plus every affected ability/unit alias and exact modification. Test rank changes, form transitions, repeated recomputation and removal/reset. |
| Charm | `s_utility_abilities.c`: retain same-edict owner/accounting transfer; enforce alias mask and creep-level limit; reject dead targets, Heroes, Resistant Skin and other authored uncharmable targets. | **Retail JASS verified for stock `ANch`:** ordinary level-3 `nftt` transfers; `Hpal`, dead `nftt`, and live `nftt` with `ACsk` remain Player 12. Boundary probe confirms stock-row level-5 override and organic levels 4–5 transfer, level 6 remains Player 12. Custom level-3 copy anomalously remained Player 12 and is unexplained. Alias coverage and source/destination resource accounting remain open. Add production-path regressions for verified outcomes and identity/accounting. Full capture and replay recipe: [`ability-verification-review.md`](docs/games/warcraft-3/ability-verification-review.md#retail-charm-target-verification-october-4-2026). |
| Permanent stat consumables | `s_item.c`: apply authored attributes once to permanent/base Hero stats, recompute derived values, consume normally; do not model as removable held-item bonus. | Every item alias/stat field/charge semantics. Test each stat, exact once, consumption and later item removal/save-load. |

## Registry/data audit findings to confirm before editing

- `ANcs` appears routed as Flame Strike; add/verify `ANc1`–`ANc3` Cluster
  Rockets aliases against active ROC/TFT data.
- Register concrete Serpent Ward `AOsw`; retain verified `Arsw`; `AOwd` is
  an internal code, not the concrete data row.
- `ANsl` is Soul Preservation (`UnitID=nzom`), not Resurrection.
- `AIco` is retail `CAbilityItemCommand`, not Charm.
- Verify stat-item aliases `AInm`, `AIgm`, `AItm` before sharing the permanent
  stat procedure.
- `APrl`, `APrr`, and `AIrx` share Resurrection's code but author different
  corpse limits; verify whether they belong in this scope before registering.

These findings are audit leads, not permission to guess or register rows
without checking both archive overlays.

## Tooltip data checked (TFT object data)

The `ability_audit -resolve-tooltip` command was run against the installed TFT
archive overlay. It resolves tooltip placeholders from AbilityData; this
confirms the authored descriptions and displayed values, not that the retail
runtime applies them exactly as described.

| Ability / rows checked | Authored tooltip facts confirmed | Still requires behavior evidence |
|---|---|---|
| Resurrection `AHre` | Tooltip says six friendly nearby corpses. Item `AIrs` independently authors DataA=6, but does not expose a matching Ubertip. | Corpse ranking/selection, valid corpse types, restoration ownership, same-edict identity and flags. `APrl`/`APrr` are not present in this installed AbilityData; do not assume their scope from the tooltip. |
| Mirror Image `AOmi` | 1/2/3 images by rank; dispels magic from the Blademaster; 60 seconds. | Damage dealt/taken factors, which Hero state images copy, dispel behavior, placement and shuffle. |
| Charm `ANch` | Takes control of an enemy; cannot target Heroes or creeps above level 5. | Previously recorded Retail JASS target checks cover the tested stock outcomes; aliases, transfer accounting and custom-unit edge cases remain. |
| Immolation `AEim`, `ACim` | Enemy land units; rank values 10/15/20 DPS for `AEim` and 10 DPS for `ACim`; mana drains until deactivated. | Drain amount/timing, activation cost, initial pulse, radius and exact eligible-target filtering. |
| Carrion Swarm `AUcs`, `ACca`, `ACcv`, `ACc2`, `ACc3` | `AUcs`: 75/125/200 per enemy unit in a cone. Creep rows describe enemy land units in a line with maximums: `ACca` 75/300, `ACcv` and `ACc2` 150/900, `ACc3` 100/300 (damage/max). `ACc1` is absent. | Travel path/width/speed, once-only hits, damage-cap accounting and actual target masks/runtime behavior. |
| Earthquake `AOeq` | Tooltip states 50 building DPS, 75% slow and 25 seconds. | Slow application, pulse cadence, target mask and tree/destructible effects. |
| Shadow Strike `AEsh`, `ACss` | `AEsh` ranks: 75/150/225 initial damage, 10/30/45 every 3 seconds for 15.1 seconds; movement slow is described only as “a short duration.” `ACss`: 75 initial, 10 every 3 seconds for 15.1 seconds; says attack-rate and movement slow for a short duration. | Exact tick schedule, slow values/lifetime, resistance, recast and damage classification. |
| Cold Arrows `ANfa` | Ranks add 5/10/15 damage, slow attacks and movement by 30/50/70%, and show 5 seconds. | Mana cost, eligible attacks/targets, autocast and actual stacking/refresh semantics. |
| Cluster Rockets `ANcs`, `ANc1`–`ANc3` | Each row displays rank maxima 45/75/110 and 1.01 seconds stun. | Bombardment schedule, area, cap interpretation, target masks and building behavior. Tooltip says “up to” damage, not how the cap is accumulated. |
| Engineering Upgrade `ANeg` | Ranks add 2/4/6 attack damage and 10/20/30% Tinker movement speed; says it improves other Tinker abilities. | Exact dependent ability/form changes represented by DataC–F and their runtime/stat recomputation. |
| Faerie Fire `Afae`, `ACff` | Both state armor −4 and vision; durations are 90 and 30 seconds respectively. | Vision ownership/expiry/refresh/dispel interaction and alias-specific target rules. |
| Storm Crow Form `Arav` | Transforms a Druid to a flying Storm Crow. | Form-specific UnitData, identity/state preservation, attacks/abilities and reversal. |
| Root/Uproot `Aro1`, `Aro2` | Rooted form is immobile, can build units, lets the Protector throw rocks and grants Fortified armor. `Aroo` has no AbilityData tooltip row. | Uprooted/mobile behavior and legal transition/placement/building restrictions; inspect the paired UnitData rows. |
| Mana Flare `Amfl` | Armor +12 for 30 seconds; tooltip describes damage when nearby enemies cast spells. | Retail JASS already confirms sampled buff end conditions; exact expiry and spell-triggered damage are still open. |
| Mana Shield `ANms` | Absorbs 1/1.5/2 damage per mana by rank. | Retail JASS already confirms sampled rank-1 absorption/depletion; exact damage math, higher ranks and `ACmf`. |
| Phoenix Fire `Apxf` | Tooltip only says it fires flame streams and lights nearby enemies on fire. | No displayed damage/cadence/target/cooldown/burn numbers. Data fields do not by themselves prove whether there is a distinct periodic burn. |

`AIlp` had no AbilityStrings `Ubertip` in this installation. Proposed stat
item IDs `AIab`, `AInm`, `AIgm` likewise do not resolve as AbilityData tooltip
rows; `AIrs` is a separate item-resurrection ability row and `AItm` resolves
to the tome class/data rather than a stat tooltip. Use ItemData/ItemStrings and
the corresponding parent/code aliases for these item questions. A missing
tooltip is not evidence that the behavior or item is absent.

## Suggested execution order and completion gates

1. Complete rawcode/field audits and ability contract docs; resolve registry
   ownership and alias-specific differences.
2. Implement focused procedure changes by owning module. Keep shared helper
   work limited to genuinely identical policy/lifecycle used by multiple
   callers. Existing working Resurrection, Purge, Serpent Ward, Crow Form,
   Root/Uproot, the now-retail-checked Charm target rules, level boundary and transfer behavior,
   and permanent-stat behavior should be changed only where focused evidence
   finds a gap. Charm alias differences and complete resource-accounting
   contract still need focused checks; investigate the custom level-3 copy
   anomaly before drawing conclusions from custom UnitData variants.
3. Add synthetic-fixture regressions through production ability/attack/order
   paths, including invalid target, inverse/interruption, timer expiry and
   save/load whenever persistent state changes. Fixtures must not depend on a
   developer's local retail extraction.
4. Run the focused WC3 tests, required broader test suite/build per
   `CONTRIBUTING.md`, and report any narrow behavior still unsupported by
   evidence. Do not claim complete retail parity from data or tests alone.

This temporary plan does not authorize presentation work or the explicit
non-goals listed in the retained logic-pass plan.
