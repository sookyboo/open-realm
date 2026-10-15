# Warcraft III Retail shared ability helpers

This is a quick map for the pinned Retail executable: Warcraft III 1.29.2.9231,
PE32 x86, SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`, preferred
image base `0x00400000`. Re-derive every address for a different hash.

The [machine-readable inventory](ability-function-investigation.json) is the
source of record: 49 functions, 39 verified relationships, explicit confidence
and unresolved semantics. This page gives only the starting points. For context
and procedures, see [ability research](ability-research.md), [Retail
architecture](ability-retail-architecture.md), and the [repeatable RE
workflow](retail-shared-ability-re.md).

## Choose a path

| Investigation | Useful starting points | Main unresolved question |
|---|---|---|
| Target validation | `0x00682180`, `0x00682210`, `0x006822E0`, pair accessor `0x007FC7E0` | Two shared gates then registered-validator vtable calls at +0x26C. The pair accessor is also called by Cold Arrow effect routine `0x00C5C9D0`; this confirms low-level reuse only. See [target validator disassembly](ability-probes/targeting.md#target-validator-static-disassembly-retail-1292). |
| Area target selection | `0x0068EA00`, `0x00699FD0` | Determine each ability's selection policy and field mapping. |
| Ability instances | `0x00AF3BA0` factory, `0x006D4560` attach, `0x006D6570` lookup | Poison (`Bpoi`) and Cold Arrow (`BHca`) both use this lookup before refresh-or-create; trace their still-unknown event producers. |
| Rank/availability | Shared rank hooks; enable/disable transitions | Identify remaining instance gates and permanence effects. |
| Status lifecycle | `0x006D87A0` filter, `0x006D8530` removal, `0x006D4B60` timed-life creation | `UnitRemoveAbility`, buff filtering, and Mana Shield depletion converge on removal; BTLF fails positive/negative buff predicates. Trace natural expiry and summon-specific cleanup. See [lifecycle evidence](ability-probes/status-lifecycle.md). |
| Attached object install | `0x006D4880` | Poison status and Pocket Factory buff paths attach class-specific instances through this wrapper, then notify the owner. See [combat evidence](ability-probes/combat.md#shared-attached-buff-installation-path). |
| Damage | `0x006A9940` payload setup; `0x006677C0` unit receiver | `UnitDamageTarget` and Carrion Swarm converge on this layer; connect ordinary attack-hit dispatch and decode payload fields. See [combat evidence](ability-probes/combat.md#damage-payload-and-receiver-path-retail-1292). |
| Poison/on-hit | `0x00BDCF70`, `0x006EF880`, Apoi hooks `+0xF8/+0xFC` | Compare poison classes and recover callback arguments/event producer. |
| Summons | `0x00687CA0` shared unit construction | Separate summon-specific expiry from generic timed life/removal. |
| Timed-life/events | `0x006F6820`, `0x006F6BD0`, `0x007FBE90` | Resolve event meanings and expiry-to-removal callers. |

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
4. Trace the ordinary attack/on-hit producer into poison callback
   `0x00BDCF70`; its Bpoi create/refresh and shared installation path are
   known, but the producer and argument meanings are not.

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
