# Warcraft III Retail shared ability helpers

This is a quick map for the pinned Retail executable: Warcraft III 1.29.2.9231,
PE32 x86, SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`, preferred
image base `0x00400000`. Re-derive every address for a different hash.

The [machine-readable inventory](ability-function-investigation.json) is the
source of record: 83 functions, 304 verified relationships, explicit confidence
and unresolved semantics. This page gives only the starting points. For context
and procedures, see [ability research](ability-research.md), [Retail
architecture](ability-retail-architecture.md), and the [repeatable RE
workflow](retail-shared-ability-re.md).

## Choose a path

| Investigation | Useful starting points | Main unresolved question |
|---|---|---|
| Target validation | `0x00682180`, `0x006ADB90`, `0x006ADA20`, `0x006AD670`, selectors `0x00B1EC60` / `0x00B1EF60`, virtual callback `+0x26C` | Shared two-slot selection also feeds ordinary weapon resolution. RTTI identifies concrete CAbility overrides of the general validator's callback slot, including form/morph, Ghost, Locust, and MetaDB implementations; runtime registry membership and rejection meanings remain unverified. See [targeting evidence](ability-probes/targeting.md). |
| Area candidate enumeration | `0x0068EA00`, generated predicates `0x00696xxx`, `0x00699FD0` | The clause-driven builder is shared by Phoenix Fire and Carrion Swarm; its raw candidate filters and callback stop behavior are documented in [combat evidence](ability-probes/combat.md#shared-area-query-builder-and-generated-predicates). Numeric field/flag meanings and each ability's selection policy remain open. |
| Ability instances | `0x00AF3BA0` factory, `0x006D4560` attach, `0x006D6570` lookup | Poison (`Bpoi`) and Cold Arrow (`BHca`) both use this lookup before refresh-or-create; Poison's producer is mapped, while Cold Arrow's `CMissileColdArrowSplash` callback is mapped to its vtable but its upstream producer remains open. |
| Rank/availability | Shared rank hooks; enable/disable transitions | Identify remaining instance gates and permanence effects. |
| Status lifecycle | `0x006D87A0` filter, `0x006D8530` removal, `0x006D4B60` timed-life creation | Natural BTLF expiry now has a verified callback chain to `0x006D8530`; BTLF still fails positive/negative buff predicates. Summon-specific owner cleanup remains open. See [lifecycle evidence](ability-probes/status-lifecycle.md). |
| Attached object install | `0x006D4880` | Poison status and Pocket Factory buff paths attach class-specific instances through this wrapper, then notify the owner. See [combat evidence](ability-probes/combat.md#shared-attached-buff-installation-path). |
| Damage | `0x006A9940` payload setup; `0x006677C0` unit receiver; `0x0068F950` source ability dispatcher | `UnitDamageTarget`, positive `UnitDamagePoint`, Carrion Swarm, Poison/Venom Spear, and direct attack types 1/4 converge on target slot `+0x120`. RTTI confirms recipient callback families for regeneration, drain bonuses, illusions, and classes including Berserker Rage, Anti-Magic Shell, Mana Shield, Sanctuary, Thorns, Frost Armor, Incinerate, Avatar, and Sleep. `0x006B80E0` is a shared bounded numeric-state updater. Several payload fields remain unnamed. Projectile attack types 2/3/5–8 still need impact tracing. See [combat evidence](ability-probes/combat.md#damage-payload-and-receiver-path-retail-1292). |
| Poison/on-hit | `0x00B1CCB0` impact processing; `0x0068F950` attached-ability dispatch; `0x00BDD5C0` class handler; `0x00BDCF70` Bpoi application | Poison Attack and Venom Spear have a verified impact-to-Bpoi chain. Cold Arrow effect endpoint `0x00C5C9D0` is slot `+0x80` on `CMissileColdArrowSplash` vtable `0x00FA0D70`; its upstream producer and relation to the poison dispatcher remain open. |
| Summons | `0x00687CA0` shared unit construction | Separate summon-specific expiry from generic timed life/removal. |
| Timed-life/events | `0x006F6820`, `0x006F6BD0`, `0x006F6CC0`, update wrappers `0x00BFC0C0` / `0x00C1A250`, generic event dispatchers `0x007FBF80` / `0x007FBE90` | BTLF deadline branch dispatches `0xD01C4`; its `+0x36C` handler removes the timed-life instance through `0x006D8530`. This does not establish owner death/removal or summon cleanup. |
| Presentation natives | `0x004892B0` effect creation; `0x004AAFC0` animation request; `0x00966C10` unit animation application | Effect natives converge on positioned or target-attached constructors; animation string/rarity/queue natives converge on one request path. Ability-authored visuals still need caller comparison. See [presentation native trace](ability-probes/presentation-natives.md). |

Phoenix Fire's scheduled callback reaches area enumeration, common validation,
duplicate `Bpxf` lookup, and effect setup. Its damage owner and interval/data
mapping remain open; see the [focused native trace](ability-probes/native-triage.md#phoenix-fire-native-path-periodic-acquisition-and-target-gates).

## Next investigations

1. Trace status creation/refresh beside `0x006D6570`; compare Faerie Fire,
   Purge, and Dispel with `UnitRemoveBuffsEx`.
2. Finish Spirit Link damage-share fields and configured damage-bonus indices;
   use Mana Shield as a contrast.
3. Follow Spirit Wolf, Serpent Ward, Mirror Image, and Pocket Factory from
   construction through their distinct expiry/removal routes.
4. Decode the poison callback payload fields and find the producer of the
   `CMissileColdArrowSplash` impact callback; do not assume it shares Poison
   Attack's category or handler path.

Open the matching records in the [inventory](ability-function-investigation.json)
and relevant [probe report](ability-probes/README.md). OpenRealm code is a
contract checklist, never evidence that Retail shares the implementation.

## Query the inventory

Use `jq` to inspect only the records needed for a task:

```sh
jq -r '.functions[] | select(.category == "targeting") | [.id, .status, .confidence, .evidence_summary] | @tsv' \
  docs/games/warcraft-3/ability-function-investigation.json
jq '.verified_relationships[] | select(tostring | test("00687ca0"; "i"))' \
  docs/games/warcraft-3/ability-function-investigation.json
```

Record new discoveries in the JSON with exact-hash addresses, callers/callees,
evidence, uncertainty, and relationships. A repeated address or shared vtable
slot alone is not proof of shared gameplay behavior.
