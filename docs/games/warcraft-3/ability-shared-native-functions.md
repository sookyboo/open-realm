# Warcraft III shared native ability functions

This document records exact-build native helpers that may reduce repeated
ability verification work. Addresses below apply only to the Retail executable
with SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed` (PE32
x86, preferred image base `0x00400000`). Re-derive them for another executable.
For the larger picture of registration, instance identity, cast paths, and
evidence limits, see [Retail ability architecture](ability-retail-architecture.md).
For a reusable workflow to find and validate shared functions, see
[Retail shared-ability reverse engineering](retail-shared-ability-re.md).
The current machine-readable seed inventory is
[ability-function-investigation.json](ability-function-investigation.json).

## Confirmed starting points

The exact-build inventory is serialized in
[ability-function-investigation.json](ability-function-investigation.json): 48
records with VA/RVA pairs, evidence, uncertainty, and 27 verified relationships.
Use the compact map below to choose a path; open the matching database record
for caller, callee, and field-level details. Addresses apply only to the hash
above.

| Path | Established starting points | Remaining limit |
|---|---|---|
| Target validation | `0x00682180` common spell validation; `0x006AEA70` mask expansion; `0x006ADA20` mask/relation checks. | Numeric rejection meanings and some owner/target predicates need caller/data correlation. |
| Area target selection | `0x0068EA00` area enumeration; `0x00699FD0` indexed choice; Phoenix Fire reaches both. | Selection policy and ability field mapping are ability-owned. |
| Ability instances | `0x00AF3BA0` AbilityData factory; `0x006D4560` attach; `0x006D6570` attached-instance lookup. `UnitAddAbility`/`UnitRemoveAbility` wrappers expose the path. | Factory presence does not prove a class's gameplay behavior. |
| Rank and availability | JASS rank wrappers and shared one-rank hooks; disable/enable counters and `UnitMakeAbilityPermanent` bridge. | Some instance gates and permanence effects remain unnamed. |
| Status lifecycle | `0x006D87A0` filter/remove loop; `0x006D8530` attached-instance removal; `0x006D4B60` timed-life buff creation. | Removal cause, expiry callbacks, and other buff class predicates must be traced separately. |
| Damage | `UnitDamageTarget` wrapper, `0x006A9940` payload setup, CUnit/widget/destructable receiver paths, and damage-bonus lookup. | Ordinary attack-hit dispatch is not yet connected; receiver paths differ by target class. |
| Damage statuses | Spirit Link and Mana Shield receiver callbacks; poison `0x00BDCF70` creation/refresh path for `Bpoi`/`Bspo`. | Spirit Link values and poison event producer/arguments remain open. |
| Summon creation | `0x00687CA0` unit setup, reached by Spirit Wolf, Serpent Ward, and Pocket Factory paths. | Creation sharing does not establish common expiry or cleanup. |
| Timed life and events | `0x006F6820` / `0x006F6BD0` timed-life virtual path; `0x007FBE90` generic callback dispatch. | Event meanings and actual expiry-to-removal route remain caller-specific. |
| Candidate waypoints | `0x006ADB90`, `0x006D4A10`, `0x006ECA60`, and `0x006ECE00`. | Treat as candidates until caller paths establish their role. |

Phoenix Fire's scheduled target-acquisition path is traced from
`0x00C0D7D0` through `0x00C0D820` and `0x00C0ECD0`; it reaches area scan,
validation, `Bpxf` lookup, and effect setup. Damage ownership, interval/data
mapping, and missile/buff tick behavior remain open. See the
[Phoenix Fire native trace](ability-retail-probe-log.md#phoenix-fire-native-path-periodic-acquisition-and-target-gates)
for disassembly addresses and caveats.

## OpenRealm comparison cases and next shared-function targets

OpenRealm's implementations help identify the native contracts worth looking
for, but do not prove that Retail uses the same code or behavior. The useful
comparison cases currently in the game module are:

| OpenRealm implementation | Contract to look for in Retail | Current evidence / caveat |
|---|---|---|
| `CAbilityFaerieFire` and `melee_status_execute` in `games/warcraft-3/game/skills/s_melee_spells.c`; `S_SpellApplyTimedTargetStatus` in `s_spell.c` | Enemy/alive target validation, duplicate-status lookup, status creation or refresh, authored duration, and target effect | Retail `0x006D6570` is a proven shared attached-instance lookup and is the best starting point for the duplicate check. It does not prove how a status instance is created, refreshed, or expired. |
| `S_UnitStatusAbilityEvent` in `games/warcraft-3/game/skills/s_skills.c`, with status storage in `m_unit.c` | Ability/status attach, registration, and subsequent per-unit lifecycle notifications | Retail `0x006D4560` appears to be the analogous object-oriented attachment point: it registers the instance and sends virtual notifications. OpenRealm stores status rows in a unit array and dispatches opted-in events by ability procedure, so this is a contract-level comparison, not a structural match. |
| `unit_expirestatus` and `UnitDispatchStatus` in `games/warcraft-3/game/m_unit.c` | Removal inverse ordering for dispel, expiry, death, and cleanup | Retail `0x006D8530` is a shared attached-object removal path. OpenRealm dispatches `A_STATUS_REMOVE` before clearing the status row, while Retail removes an object from an attached-instance list and notifies sibling objects. Compare caller paths and callback effects; do not assume identical cleanup ordering. |
| `S_SpellApplyTimedLife` and `S_SummonAbilityUnits` in `games/warcraft-3/game/skills/s_spell.c` / `s_summon.c` | Spell-owned timed-life application and summon ownership | Retail `UnitApplyTimedLife` has a concrete BTLF object creation/attach path through `0x006D4B60`; the direct path is registered at `0x0049B3C0` and implemented at `0x004AED50`. The stock spell summon path has not yet been shown to call that native wrapper or the same constructor. |
| `S_SummonAbilityUnits`, `S_SummonAbilityAt`, and `S_SpellApplyTimedLife` in `s_summon.c` / `s_spell.c`; Serpent Ward calls the shared summon path from `s_campaign_abilities.c` | Common UnitID/count/duration reads, unit creation, owner/ability identity assignment, and timed-life attachment | This suggests a high-value Retail search across summon abilities such as Serpent Ward, Spirit Wolves, and Pocket Factory. No common Retail summon helper is identified yet; do not infer one from the OpenRealm helper. |
| `S_ResolveAttackHit` in `s_attack.c`, plus `S_UnitStatusAbilityEvent` and `S_SearingArrowDamage` | Shared attack-hit dispatch, ability callbacks, damage modification, and on-hit status application | This is a useful comparison for attack-triggered effects (including orb/arrow abilities). OpenRealm Cold Arrows in `s_ability_stubs.c` only toggles placeholder state, so it is not a behavior reference. Retail's `0x007FBE90` is a generic callback delivery primitive; a concrete attack-to-ability call chain still needs to be established. |
| `S_SpellDamageEnemiesInRadius` and status application in `s_spell.c` / `s_area_spell.c` | Common area enumeration followed by per-target filtering, damage, or status application | Retail `0x0068EA00` is a widely reused area-enumeration helper. Determine the callback and target predicates at each ability caller; enumeration alone does not establish the effect. |
| `S_SpellApplyTimedLife` / `S_SpellApplyTimedStatus` in `s_spell.c`, `S_SummonAbilityAt` in `s_summon.c`; Mirror Image and Pocket Factory | Timed-life initialization, pause/cancel, expiry, and the order between unit death/removal and attached-status cleanup | Retail JASS entry points to compare are `UnitApplyTimedLife`, `UnitPauseTimedLife`, and `BlzUnitCancelTimedLife`; `UnitRemoveBuffsEx` is a useful negative case because the inspected `BTLF` object reports false for both polarity predicates. OpenRealm keeps its timed status row on the unit and handles timed-life death in `unit_updatestatuses`, which is a behavioral checklist rather than proof of Retail internals. |
| `S_ResolveAttackHit` in `s_attack.c`; `S_OrbOnHit` / `S_PoisonOnHit` in `s_item_stats.c` / `s_status_spells.c`; Orb of Venom, Slow Poison, Searing Arrows | The ordered split between attack damage modifiers, on-hit status application, and projectile/spell damage | Compare Retail `UnitDamageTarget` and `EVENT_PLAYER_UNIT_DAMAGED` / `BlzGetEventDamage*` only for their damage-event semantics; the actual ordinary attack path is internal and needs class/callback tracing. In OpenRealm, `S_ResolveAttackHit` explicitly orders mitigation and post-hit handlers, so follow each handler's conditions and call sites. |
| `S_SpiritLinkRedirect` in `s_spirit_link.c` and `S_ManaShieldDamage` in `s_attack.c` / status abilities; Spirit Link and Mana Shield | Damage receiver callback ordering, redistribution/absorption amount, recursion guard, and attached-buff removal on depletion | `UnitDamageTarget` is a useful controlled Retail entry point because it reaches the same unit damage receiver; Spirit Link can also be inspected through `Aspl` / `Bspl`, while Mana Shield uses its ability and buff classes. OpenRealm's `S_SpiritLinkRedirect` and `S_ManaShieldDamage` provide concrete candidate state and expected control-flow questions; do not assume its fractions or ordering match Retail. |
| `unit_expirestatus`, `UnitDispatchStatus`, and `unit_updatestatuses` in `m_unit.c`; Purge and Dispel Magic | Expiry/dispel removal ordering, inverse callbacks, death behavior, and whether timed-life removal kills or preserves the unit | Retail entry points are `UnitRemoveBuffs`, `UnitRemoveBuffsEx`, `UnitApplyTimedLife`, and `BlzUnitCancelTimedLife`; ability paths to compare include Purge (`Apg2`) and Dispel/Disenchant (`Adis`/`Adch`). OpenRealm dispatches `A_STATUS_REMOVE` before clearing a status slot and applies timed-life death after expiry cleanup. |
| `S_SummonAbilityUnits` / `S_SummonAbilityAt` in `s_summon.c`; Serpent Ward, Spirit Wolves, Pocket Factory | Whether different summon classes share unit construction, owner/creator attribution, lifetime attachment, and timed removal | For Retail, follow those abilities' class callbacks to `0x00687CA0`, then compare their expiry path with JASS `UnitApplyTimedLife` and explicit `RemoveUnit`. OpenRealm routes summon creation through `S_SummonAbilityAt`, with `S_SpellApplyTimedLife` when duration is positive; Serpent Ward, Spirit Wolves, and Pocket Factory give distinct caller families. |
| `CAbilityAttackBonus` / `S_OrbOnHit` in `s_item_stats.c` and `CAbilityPoisonAttack` / `S_PoisonOnHit` in `s_status_spells.c` | Whether passive ability instances are queried in a common hit dispatcher and how their authored `BuffID`/level reach status creation | Use Retail item orbs (`AIob`, `Aven`, `Apoi`, `Apo2`) and the matching attack-buff objects as distinct classes. Relevant JASS observables include `UnitDamageTarget` and damage event natives; OpenRealm's attack handlers make a good map of where to look, but its Cold Arrows stub is not useful evidence. |
| Retail class registry: `Apoi`/`Aven`/`Aspo`/`Apo2`; OpenRealm `CAbilityPoisonAttack` and `S_PoisonOnHit` | Shared parent hooks versus subclass-specific hit behavior, plus the path from attacker ability to `Bpoi`/`Bpsd`/`BIpb`/`BIpd` attachment | Exact pinned registry maps `Apoi` to `CAbilityPoisonAttack` (`APas` parent), with `Aven` (`CAbilityVenomSpear`), `Aspo` (`CAbilitySlowPoison`), and `Apo2` (`CAbilityPoisonDamage`) below it. OpenRealm has one passive procedure and central on-hit handler. This is a focused class family for locating the Retail dispatch, but registration and inheritance alone do not prove a shared hit callback. |
| Retail `Apoi` attached-object hooks `+0xF8`/`+0xFC`; CUnit damage receiver `0x006677C0` | Whether the damage receiver's attached-object callback group includes passive poison abilities, and whether its event eventually applies the poison buff | `Apoi`'s vtable supplies `0x006EF9B0` at `+0xF8` and `0x006EF9D0` at `+0xFC`. The latter emits `0xD01E2` or `0xD01C1` through `0x007FBF80`, selected by object flag `0x08000000`. In the controlled TFT Retail ordinary-attack probe, Frida observed one `Apoi +0xFC` call and nine `Bpoi` status-callback entries while the Apoi attacker repeatedly damaged the target. This links Apoi attack activity to the Bpoi callback in this scenario. The trace does not establish whether `0x006677C0` is the producer of every observed Bpoi call, nor the exact `+0xF8` return category or callback argument meanings. |
| Retail poison projectile classes `Mpoi`/`Mpas`/`Mspo`/`Msss`; OpenRealm projectile impact in `S_ResolveAttackHit` | Whether poison attacks travel through a shared missile impact callback that creates the authored buff, and whether single-target/splash and slow-poison subclasses reuse that path | Exact pinned registry maps these missile classes as `Mpoi` (`CMissilePoisonAttack`, `BfMi` parent), `Mpas` (`CMissilePoisonAttackSplash`, `BfMs` parent), `Mspo` (`CMissileSlowPoison`, `Mpoi` parent), and `Msss` (`CMissileSlowPoisonSplash`, `Mpas` parent). The class tables reuse handler `0x006EF880` at different virtual offsets (`Mpoi +0x40`, `Mpas +0x2C`, `Mspo/Msss +0x1C`). Its code handles event IDs `0xD01E2` and `0xD01C1`: it clears a retained event/object reference, dispatches `0xD01C1` through virtual slot `+0x364`, then invokes slot `+0x36C`; on the `0xD01E2` branch it also clears object flag `0x08000000`. These virtual destinations vary by class: `Apoi +0x364` is `0x006F6BD0`, `Mpoi +0x364` is a no-op (`0x006F1E70`), and `Mpas +0x364` is `0x00BDEA70` (an effect/configuration callback); `Mpoi +0x36C` routes through `0x006F1EA0` to its virtual `+0x1D8` method `0x00BDEED0`. Other messages go to `0x006F6CC0`, whose observed `0xD01C4` path removes the object through `0x006D8530`. During the controlled Apoi ordinary-attack probe, Frida recorded 15 calls to `0x006EF880` on the poison projectile instance, interleaved with damage receiver calls, and the JASS target damage log showed periodic damage beyond the `4.000` base hits. This confirms the shared missile handler participates in the observed attack sequence but does not, by itself, establish the meaning of `0xD01E2`/`0xD01C1` or prove that it creates the poison buff. |
| Retail poison projectile classes `Mpoi`/`Mpas`/`Mspo`/`Msss`; OpenRealm projectile impact in `S_ResolveAttackHit` | Whether poison attacks travel through a shared missile impact callback that creates the authored buff, and whether single-target/splash and slow-poison subclasses reuse that path | Exact pinned registry maps these missile classes as `Mpoi` (`CMissilePoisonAttack`, `BfMi` parent), `Mpas` (`CMissilePoisonAttackSplash`, `BfMs` parent), `Mspo` (`CMissileSlowPoison`, `Mpoi` parent), and `Msss` (`CMissileSlowPoisonSplash`, `Mpas` parent). The class tables reuse handler `0x006EF880` at different virtual offsets (`Mpoi +0x40`, `Mpas +0x2C`, `Mspo/Msss +0x1C`). Its code handles event IDs `0xD01E2` and `0xD01C1`: it clears a retained event/object reference, dispatches `0xD01C1` through virtual slot `+0x364`, then invokes slot `+0x36C`; on the `0xD01E2` branch it also clears object flag `0x08000000`. These virtual destinations vary by class: `Apoi +0x364` is `0x006F6BD0`, `Mpoi +0x364` is a no-op (`0x006F1E70`), and `Mpas +0x364` is `0x00BDEA70` (an effect/configuration callback); `Mpoi +0x36C` routes through `0x006F1EA0` to its virtual `+0x1D8` method `0x00BDEED0`. Other messages go to `0x006F6CC0`, whose observed `0xD01C4` path removes the object through `0x006D8530`. `Apoi` has `0x006EF880` at vtable `+0x1C`, `0x006EF9B0` at `+0xF8`, and `0x006EF9D0` at `+0xFC`; the latter emits `0xD01E2` or `0xD01C1` through `0x007FBF80` based on flag `0x08000000`. `Aven` and `Aspo` replace the `+0x1C` handler with `0x006F6CC0`. The unit damage receiver `0x006677C0` invokes an attached object's `+0xFC` only when its `+0xF8` returns `1`, but whether `Apoi +0xF8` qualifies and whether this reaches poison application are unresolved. This establishes shared event/lifecycle hooks, but these event IDs and virtual destinations have not been identified as ordinary attack hits, and this callback itself does not attach a poison buff. |
| Retail orb rows `AIob` and `AIpb`; OpenRealm `CAbilityAttackBonus` and `S_OrbOnHit` | Whether Retail's distinct frost/poison bonus classes converge on shared attack dispatch and status application | The pinned registry maps `AIob` to `CAbilityFrostDamageBonus` and `AIpb` to `CAbilityPoisonDamageBonus`, both under `AIDB`; OpenRealm currently routes both through `CAbilityAttackBonus`. Their vtable `+0x364` hooks differ: `AIob` (`0x0083EDD0`) forwards the event to its parent object's `+0x14`, while `AIpb` (`0x006E5110`) switches on internal IDs `0xD0196`/`0xD019C`, `0xD0198`/`0xD019F`, and `0xD01A4` to invoke parent slots `+0xB4`, `+0x5C`, and `+0xB8`. These methods show class-specific event handling but no direct damage or status creation; the attack-dispatch relationship remains unproven. |

These OpenRealm analogues prioritize the remaining Retail investigations:

1. Locate status-instance creation and refresh adjacent to `0x006D6570`.
   Existing native paths now expose factory/attach (`0x00AF3BA0`,
   `0x006D4560`), removal (`0x006D8530`), buff filtering (`0x006D87A0`), rank
   updates (slots `+0x2E4` / `+0x2E8`), and disable/enable transitions
   (`0x0046E0C0` / `0x0046E630`). Start with Faerie Fire, Purge, or Dispel
   and compare `UnitRemoveBuffsEx` with their class-specific callbacks.
2. Finish mapping the `0x0067B920` lookup indices from payload offset `+0x20`
   and unit offset `+0x1EC` to the seven configured damage-bonus rows, and
   resolve the Spirit Link callback's event-referenced `+0x364` receiver plus
   its share-fraction/data mapping. Use `Aspl`/`Bspl` and `Amfl`/`Bmfl` as
   contrasting damage callbacks; OpenRealm's `S_SpiritLinkRedirect` and
   `S_ManaShieldDamage` show the candidate calculations. `UnitDamageTarget`
   reaches the shared receiver under a controllable source/target setup. The
   exact Retail field mappings remain open.
3. Resolve the clock argument, event `0xD01C4`, and removal consequence around
   `BTLF` vtable methods `0x006F6820` / `0x006F6BD0`. Spirit Wolf and Serpent
   Ward have now been shown to share unit construction at `0x00687CA0`, but
   neither uses the `UnitApplyTimedLife` route in its inspected spawn callback;
   trace their summon-specific expiry paths separately. Compare Mirror Image
   and Pocket Factory against JASS `UnitApplyTimedLife`,
   `UnitPauseTimedLife`, and `BlzUnitCancelTimedLife`; inspect
   `UnitRemoveBuffsEx` as a control for buff filtering.
4. Extend the ordinary attack-hit trace across distinct poison and bonus
   classes, and recover the Bpoi callback argument meanings. The first
   controlled TFT Retail run used `Apoi` on a spawned footman attacking a
   spawned target. JASS confirmed `UnitAddAbility` and `IssueTargetOrder`
   succeeded, and recorded repeated base `4.000` damage plus periodic
   approximately `10.7`–`11.6` events. Frida observed 55 calls to
   `0x006677C0`, 15 calls to shared poison missile handler `0x006EF880`, nine
   calls to Bpoi status callback `0x00BDCF70`, and one Apoi `+0xFC` hook call
   at `0x006EF9D0`. In this scenario, ordinary Apoi attack activity therefore
   reaches the Bpoi callback and poison missile lifecycle. The trace alone
   does not prove that each Bpoi callback is caused by the immediately
   preceding hit, nor identify its arguments, callback return meaning, or the
   exact internal mapping from damage amount to JASS events. Preserve those as
   open questions and compare `Aven`/`Aspo`/`Apo2`, plus `AIob`/`AIpb`, before
   generalizing the path. Use `S_ResolveAttackHit` as the OpenRealm map. The
   generated TFT inventory labels callback locations as file offsets; convert
   through the executable's PE sections before using one as a Ghidra VA. JASS
   `UnitDamageTarget` and damage-event natives can help exercise the damage
   receiver, but do not substitute for finding the ordinary attack callback
   path. The reproducible inputs, executable/map hashes, capture, Frida log,
   screenshot and exact run sequence are under `/tmp/wc3-poison-attack/run3`;
   screenshot is also retained at `screenshots/tmp/WC3ScrnShot_100526_172930_02.png`.
5. Extend the Pocket Factory trace from unit construction into the remaining
   factory and Clockwerk lifetime/removal callbacks. Impact callback
   `0x00C829F0` and periodic producer callback `0x00C831F0` both call shared
   constructor `0x00687CA0`, through separate `BNfy` and `BNcg` buff paths.
   Keep these paths distinct from `CAbilityFactory` callback `0x00C83940`
   (`ANfy`), which is not attached to Pocket Factory's factory unit. Compare
   OpenRealm's `AbilityPocketFactory` and `S_SummonAbilityAt` for the runtime
   owner chain and `UnitApplyTimedLife` for the separate native lifetime path.

For each investigation, follow references from known ability callers, inspect
the helper body, and compare at least two distinct classes before calling a
mechanism shared. Add an address here only after exact-build call-chain
evidence supports the connection.

## Current investigation

A full Ghidra analysis of the pinned executable completed successfully and is
stored in `data/wc3-ghidra-full/Wc3Retail1292Full`. Incoming references were
queried against that project with `tools/ghidra/Wc3Callers.java`. High call
count alone does not establish a gameplay contract: exclude generic
compiler/runtime helpers and separate direct code references from virtual
dispatch sites.

## Reproducible inspection

Use the cached full-analysis project for read-only call/reference inspection:

```sh
/opt/openrealm-tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  "$PWD/data/wc3-ghidra-full" Wc3Retail1292Full \
  -process 'Warcraft III.exe' -noanalysis \
  -scriptPath tools/ghidra \
  -postScript Wc3Callers.java 0x00682180 0x0068EA00 0x006D6570 \
  0x006D4560 0x00AF3BA0 0x006D61E0 0x0046E0C0 0x0046E630 \
  0x006D87A0 0x006D4B60 0x006D8530 0x006D4A10 \
  0x00687CA0 0x00CAF240 0x0068AB70 \
  0x006EC8F0 0x006ECA60 \
  0x006AEA70 0x006ADA20 0x00B28980 0x007F6360 0x007FBE90 \
  0x006A9940 0x006ADB90 \
  0x00BDCF70 0x00BE1A00 0x00BE1C00 0x006D4880 \
  0x006677C0 0x006EF730 0x006EF880 0x006EF9B0 0x006EF9D0 \
  0x006F6CC0 0x006F6D00 0x006F6D70 0x00BDEED0 0x00BDEA70 \
  0x0083EDD0 0x006E5110
```

Use `Wc3DumpFunction.java` alongside the caller query when the helper's body
or argument contract needs inspection. Use Frida only when static references
cannot resolve the runtime receiver or virtual slot; a trace of one exercised
path supplements, but does not replace, the static caller analysis.
