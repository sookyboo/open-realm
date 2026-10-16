# Retail ability native triage

Static class/callback reconnaissance and unresolved native inspection queue. Treat each address as specific to the executable hash in [verification status](../ability-verification-review.md).

## Exact-build static triage of remaining ability claims (October 5, 2026)

The remaining-claims inventory was cross-checked against the installed TFT
AbilityData and the exact Retail executable used above (SHA-256
`3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed`, PE32
x86, preferred image base `0x00400000`). The checked-in ability-class registry
is still unsuitable as address authority because it belongs to another hash.

### Exact-build class identities resolved

The TFT `ability_audit -raw` rows identify the implementation codes below.
Their class-name strings and reference functions were independently found in
the exact executable with radare2 `iz` and inspected in the cached Ghidra
project. The previously cited `Wc3InspectAddresses.java` script is absent from
this checkout; use the Ghidra GUI or radare2 to inspect the references. The
reference functions return the
matching `CAbility...` string, confirming these RTTI class identities. This
proves class naming and enables targeted method inspection; it does not prove
the ability's target or effect contract. The audit also resolves
`AHre` -> `CAbilityResurrection`, though its exact name-accessor VA was not
recovered in this pass.

| TFT row / code | Exact executable class | Name-reference function |
|---|---|---:|
| `Apxf` / `Apxf` | `CAbilityPhoenixFire` | `0x00C0D750` |
| `AOeq` / `AOeq` | `CAbilityEarthquake` | `0x00C29850` |
| `AOmi` / `AOmi` | `CAbilityMirrorImage` | `0x00C2C920` |
| `Apg2` / `Aprg` | `CAbilityPurge` | `0x00B9E2D0` |
| `AOsw` / `AOwd` | `CAbilityWard` | `0x00C340D0` |
| `Afae` / `Afae` | `CAbilityFaerieFire` | `0x00C3CC30` |
| `ANeg` / `ANeg` | `CAbilityEngineeringUpgrade` | `0x00C812B0` |
| `ANch` / `ANch` | `CAbilityCharm` | `0x00C54630` |
| `ANfa` / `ANfa` | `CAbilityColdArrows` | `0x00C5CBC0` |
| `Amfl` / `Amfl` | `CAbilityManaFlare` | `0x00C3E180` |
| `ANms` / `ANms` | `CAbilityManaShield` | `0x00C79C10` |
| `Aro1`, `Aro2` / `Aroo` | `CAbilityRoot` | `0x00B8D9D0` |
| `Arav`, `Amrf` / `Arav` | `CAbilityRavenForm` | RTTI confirmed, accessor not resolved |

The other listed string addresses were passed to Ghidra and reported as the
expected strings, with incoming references from the listed functions. These
are class-name accessors, not gameplay callbacks. Resurrection class RTTI is
present in radare2 output, but its name-reference function was not established
in this pass.

The already mapped batch classes are Immolation (`0x00B6C8B0`), Shadow Strike
(`0x00C4EC20`), Earthquake (`0x00C2A0C0`), Cluster Rockets (`0x00C83570`), and
Carrion Swarm (`0x00C2FC20`); their factory/vtable trace results are retained
in this log, but the original trace script is absent from this checkout. For a new live trace, use the
class-name accessor only to orient inspection. Locate the instance generator
and constructor, then identify the relevant virtual callback and call sites in
the same build. Do not hook a name accessor and present that as an executed
ability path.

### Data and contract distinctions captured

- TFT `Apxf` maps to `CAbilityPhoenixFire` (`APas` parent), DataA=20,
  DataB=2, Dur=10, HeroDur=7, Area=600, target mask ground/air/enemy. Those
  data values do not alone prove whether DataA is per-hit damage, DataB is
  cooldown, how target selection works, or whether a separate burn tick exists.
- TFT `AOmi` maps to `CAbilityMirrorImage` (`AAsp` parent). Rank DataA is
  1/2/3; DataC=2 and DataD=0.5 at every rank; Dur/HeroDur=60. Data fields
  and tooltip establish count/lifetime and authored factors only after their
  field semantics are tied to this class's reads.
- TFT `AOeq` maps to `CAbilityEarthquake` (`AAsm` parent): DataA=0.5,
  DataB=50, DataC=0.75, DataD=250, BUeq/BOea buff IDs, and 25/20 second
  Dur/HeroDur. Existing Retail observations prove building damage in one
  sampled case, but slow, mask and interruption require the class/effect
  update paths or a focused observable probe.
- TFT `AOsw` maps to `CAbilityWard` (`AAsm` parent), with `osp1`/`osp2`/`osp3`
  UnitIDs and 40-second Dur/HeroDur. This agrees with the verified rank-1
  summon and places rank-specific attack behavior in UnitData. Higher rank
  identity and creation path can be established statically if the constructor
  reads the current rawcode's UnitID; exact expiry callback semantics still
  need that path inspected.
- TFT `ANeg` DataC–F explicitly names the next-rank dependent codes
  (`ANsy`/`ANcs`/`ANrg`/`ANde`, then `ANs1`/`ANc1`/`ANg1`/`ANd1`), alongside
  movement and damage values in DataA/B. This establishes dependency aliases,
  not how the runtime applies/recomputes those upgrades; follow the upgrade
  class and recipient stat/ability paths.
- TFT `ANch` has target mask air/ground/nonhero/enemy/neutral/organic and
  DataA=5; alias `ACch` has its own mask, cost and DataA=6. The earlier JASS
  results establish stock `ANch` cases only. The alias is a concrete
  unresolved difference requiring class validation/data interpretation.
- The form rows resolve `Arav` -> `CAbilityRavenForm` with `DataA=edot`,
  `UnitID=edtm`; `Amrf` shares `Arav` and uses `DataA=nmed`, `UnitID=nmdm`.
  Root rows `Aro1` and `Aro2` share `Aroo` but reverse DataA/DataB
  (1/2 versus 2/1). This establishes the authored pairings; inspect the
  `CAbilityRoot` and `CAbilityRavenForm` transition code and paired UnitData
  before claiming preservation, legal placement, or form behavior.
- TFT `ANfa` is the concrete `CAbilityColdArrows` class; inspect attack
  event/launch callbacks for mana, bonus, autocast and target gates rather
  than infer them from the effect class names.
- TFT item rows resolve `AInm` -> `AIsm` (`CAbilityStrengthMod`, DataC=2),
  `AIgm` -> `AIam` (`CAbilityAgilityMod`, DataA=2), and `AItm` -> `AIim`
  (`CAbilityTome`, DataB=2). Their `CAbility...` family indicates passive
  object classes, but it does not prove permanent versus removable stat
  mutation; inspect their stat mutation callers and inverse/removal code.
- `ACff` shares `Afae` with `CAbilityFaerieFire` and shares BuffID `Bfae`,
  while its Dur/HeroDur and cooldown differ. The alias audit confirms `ACpu`
  shares `Aprg` with `Apg2`, Charm's `ACch`
  has a six-level limit while `ANch` has five, and Carrion aliases carry
  materially different masks/damage caps. Static class sharing must not be
  mistaken for identical authored behavior.

### Virtual callback reconnaissance completed

#### Phoenix Fire native path: periodic acquisition and target gates

For the exact executable hash above, `CAbilityPhoenixFire` has a concrete
scheduled event path. Function `0x00C0D7D0` reads the ability's configured
interval through virtual slot `+0x2EC`, then schedules event `0xD01B0` against
the member at `this+0x84`. The virtual event handler at `0x00C0D820` ignores
other event IDs and calls `0x00C0ECD0` only for `0xD01B0`. This establishes a
recurring native ability event; the exact interval field-to-AbilityData
mapping is still open.

`0x00C0ECD0` obtains the owning unit (`this+0x30`) and its current position,
then calls the area-unit enumerator `0x0068EA00` with callback `0x00C0F1E0`.
The scan is centered on the owner and takes its radius/configuration from the
ability's data object (`this+0x50`). If one or more candidates survive, the
handler selects one index through `0x00699FD0` and continues into a status
effect setup path (`0x006EC8F0`) using that selected unit. This is evidence of
periodic nearby target acquisition and one selected target per event; it does
not by itself prove the exact native damage payload or tick amount.

The callback and generic helpers establish these target gates:

- The callback rejects candidates whose field at `+0x1F4` is positive. The
  field's semantic name has not been recovered.
- It obtains the candidate's classification through vtable slot `+0x310` and
  passes it to `0x00682180`. That helper checks the two general spell-target
  rejection paths `0x00682210` and `0x006822E0`, followed by registered target
  validators. The first two paths consult target virtual predicates and the
  `MagicImmunesResistUltimates` setting; their numeric returns are internal
  rejection codes, not damage values.
- It queries the candidate for buff FOURCC `Bpxf` (`0x42707866`) through
  `0x006D6570` and rejects candidates where that buff is already present.
- It calls `0x0067FB80` with the owner and candidate context as a further
  target-relationship check. The helper consults owner/target flags and the
  shared target validator; its exact semantic label remains unresolved.

After selection, the setup path queries the shared `CBuffPhoenixFire`
definition by FOURCC `Bpxf` and passes the selected-unit context into
`0x006EC8F0`. Together with the duplicate-buff gate, this supports a
Phoenix-Fire-owned status/effect being installed on the selected target. The
binary also contains `CMissilePhoenixFire`, but this pass has not connected its
factory/update/hit path to the periodic handler or established whether damage
is applied by that missile, the buff's tick callback, or both. Therefore the
following remain unverified statically: DataA damage meaning, DataB cadence,
Dur/HeroDur relationship, exact radius field, damage type, and expiry/removal
behavior. Do not promote the tooltip or the presence of the missile class into
proof of those details.

The checked-in exact-build Ghidra project is `screenshots/ghidra/WarcraftIII`;
its `functions.csv` records function boundaries. `Wc3DumpFunction.java` is not
present in this checkout, so inspect these functions with the GUI and
cross-check target constants and short branch sequences with radare2 before
assigning semantics. Retain the exact executable hash when reporting these
addresses.

A follow-up mapped actual vtable globals written by the exact-build
constructors, rather than reading the adjacent class-name / RTTI data as a
vtable. The inspected addresses below are for the executable hash above and
must be re-derived for another build.

| Class | Constructor / vtable VA | Inspected class-specific methods | Static conclusion |
|---|---|---|---|
| `CAbilityResurrection` | constructor `0x00C0F6E0`, vtable `0x00F76CC4` | `0x00C0F5A0`/`0x00C0F5C0` delegate to parent and serialize nested members; `0x00C0F520` forwards through a member at offset `0x13C`; rawcode getter `0x00C0F510` returns FOURCC `AHre` | The timer/member callback at `0x00C0F520` has not been assigned a gameplay role. This pass did not identify the corpse scan or restoration effect. |
| `CAbilityPhoenixFire` | constructor `0x00C0E570`, vtable `0x00F75CB0` | shared save/load virtuals `0x00C0F5A0`, `0x00C0F5C0`; rawcode getter not established in this table | The scheduled nearby-target acquisition and `Bpxf` status setup path are now identified below; damage, interval field mapping and missile/buff tick ownership remain unresolved. |
| `CAbilityMirrorImage` | constructor `0x00C2D370`, vtable `0x00F8764C` | `0x00C2CB60` save, `0x00C2CA80` load, `0x00C2CA30` cleanup; `0x00C2C930` returns FOURCC `AOmi` | The observed custom callbacks write/read owned state, nested data and a counted collection, then release that collection. They do not establish illusion creation, damage factors, copied Hero state, or dispel behavior. |
| `CAbilityRavenForm` | constructor `0x00BAE9E0`, derived vtable `0x00F4A000` | `0x00BADD40` dispatches ability event/order IDs; `0x00BAF000`, `0x00BAF2B0`, `0x00BAEF70` are called from that dispatch; `0x00BADF40`/`0x00BADFF0` serialize state | This class derives from the shared `CAbilityMorph` path and has form-state callbacks. The inspected branch uses unit/ability state flags, but this pass has not proven exact preservation or each rawcode's legal transition behavior. |
| `CAbilityRoot` | constructor `0x00B8E760`, vtable `0x00F36050` | `0x00B8E290`, `0x00B8E4A0`, `0x00B8E4E0` serialize/restore nested fields; `0x00B8D9E0` returns FOURCC `Aroo` | The class keeps persistent per-ability state. These callbacks do not prove the rooted/mobile transition rules or placement checks. |

**Correction to the preceding class-triage table:** Resurrection's verified
name-reference accessor is `0x00C0F500` (class string `0x00F7755C`), and its
constructor writes vtable `0x00F76CC4`. Phoenix Fire's name accessor is
`0x00C0D750`; its constructor is `0x00C0E570` and writes vtable
`0x00F75CB0`. The two neighboring vtables must not be conflated when writing
a Frida receiver filter. Both tables reference shared `0x00C0F5A0` and
`0x00C0F5C0` save/load virtuals.

The current Ghidra project does not provide trustworthy C++ types or virtual
method names. Decompilation of a requested VA alone does not assign a semantic
role. For the inspected serialization
methods, the conclusion above comes from explicit calls to serializer
helpers, stream arguments and paired save/load callbacks. No executable
method in this batch established the remaining gameplay outcomes, so no
behavior claim was promoted to verified merely from class presence or member
layout. The class-name/registration mapping and object-data findings remain
valid independently of this method-role limitation.

### Remaining native inspection queue

No ability-specific runtime factories were hooked in this triage pass. The
class identities above came from exact-build binary data/RTTI and are enough
to choose native code for static work. Use Frida only where a static caller or
receiver remains ambiguous; prioritize these unresolved questions:

1. Phoenix Fire: map its configured interval/radius and DataA/B fields to
   concrete reads, then trace `CBuffPhoenixFire` and `CMissilePhoenixFire`
   callbacks through expiry and damage application.
2. Mirror Image: summon/clone creation, factor reads, copied unit state, and
   `CBuffMirrorImage`/dispel removal paths.
3. Resurrection: corpse candidate validator, ordering/limit reads, and
   restoration/owner semantics. Item `AIrs` is a separate item row.
4. Earthquake: effect tick cadence, structure/unit candidate masks, DataA–D
   reads, and interrupt cleanup.
5. Purge/Charm: alias-specific target/data checks and success-side ownership
   transfer; Charm's custom-unit level anomaly and resource accounting remain
   unexplained.
6. Ward/Faerie Fire: UnitID selection/expiry and reveal source ownership,
   refresh and removal paths.
7. Crow Form and Root: pair each order transition to the exact UnitData form,
   then inspect unit rebind/state-copy and placement predicates.
8. Shadow Strike, Immolation, Cluster Rockets, Mana Flare, Mana Shield and
   Carrion Swarm: continue from existing observations by mapping each field
   read to its row and tracing expiry/alias branches; Carrion's inner geometry
   and cap remain open as recorded above.
9. Cold Arrows and permanent stat items: inspect attack-event qualification,
   mana/stat mutation, and whether the inverse path exists for the item class.
10. Engineering Upgrade: follow DataC–F's next-rank FourCCs into rank
    replacement and Tinker form/stat recomputation.

Do not label an item/ability contract verified from RTTI or tooltip alone. For
static completion, record the native function/callsite, exact data field or
predicate, and resulting branch/effect together. If that is still ambiguous,
add a narrowly scoped exact-hash Frida trace and pair it with the corresponding
Ghidra caller path before deciding whether JASS can be skipped.

### Fast-candidate follow-up: data verified, native behavior still open (October 5, 2026)

This follow-up rechecked the most bounded candidates against the installed
AbilityData, resolved tooltips and exact Retail executable hash above. The
claims below are split by evidence type: authored values and class identity
are confirmed; runtime effect ownership/removal is not promoted to verified
where the native behavior callback has not been recovered.

| Candidate | Confirmed from installed data / exact-build binary | Still open |
|---|---|---|
| Serpent Ward (`AOsw` / `AOwd`) | The three ranks select UnitIDs `osp1`, `osp2`, `osp3`; each has 40-second Dur/HeroDur, cost 30, range 500, and buff `BOwd`. The resolved rank tooltips name each corresponding UnitData row for hit points and attack damage. Exact-build audit class is `CAbilityWard`, parent `AAsm`; exact-executable string accessor `0x00C340D0` returns `CAbilityWard`. | Constructor/vtable and cast callback not recovered in this pass. Thus the actual UnitID read, summon ownership, expiry timer and cleanup path remain open; the tooltip proves authored row references, not runtime consumption. |
| Faerie Fire (`Afae`) | AbilityData gives cost 45, range 700, DataA=4 armor reduction, Dur=90/HeroDur=60, and buff `Bfae`; its tooltip states armor reduction and vision. `ACff` shares class and BuffID but has distinct authored duration/cooldown. Exact-build audit class is `CAbilityFaerieFire`, parent `AAat`; accessor `0x00C3CC30` returns the class string. | Reveal source ownership, refresh behavior, hero-duration selection, and expiry/removal are not yet tied to native callbacks. |
| Frost Arrows (`ANfa` / `AHca`) | All three rank rows specify bonus damage 5/10/15, attack slow 30/50/70%, movement slow 30/50/70%, 5-second normal / 1.5-second Hero duration, cost 10, and `BHca`/`Bcsd`. Tooltip resolves those exact rank fields. Exact-build audit resolves implementation code `AHca` to `CAbilityColdArrows` (parent `AHRa`); accessor `0x00C5CBC0` returns the class string. | Attack-event qualification, mana payment, autocast target gates, damage application, stack/doT state (`Bcsd`), refresh rules, and inverse expiry callback remain open. `AHca` and `ANfa` are distinct raw rows even though they share the implementation code; compare the alias-specific values before claiming parity. |
| Engineering Upgrade (`ANeg`) | Three ranks author movement bonus 10/20/30%, attack bonus 2/4/6, and DataC–F dependent ability codes (`ANsy`/`ANcs`/`ANrg`/`ANde`, then `ANs1`/`ANc1`/`ANg1`/`ANd1`). Tooltip confirms movement and attack bonuses. Exact-build audit class is `CAbilityEngineeringUpgrade`, parent `APas`; accessor `0x00C812B0` returns the class string. | Whether the class actively replaces abilities/recomputes existing Tinker state or relies on other stat/dependency mechanisms is not proven. Constructor, vtable, rank-up callback and recipient stat path remain to be mapped. |
| Permanent stat items (`AInm`/`AIsm`, `AIgm`/`AIam`, `AItm`/`AIim`) | Installed AbilityData maps Strength Gain to `CAbilityStrengthMod` (DataC=2), Agility Gain to `CAbilityAgilityMod` (DataA=2), and Tome to `CAbilityTome` (DataB=2). TFT class registry lists the corresponding concrete registration codes and class parents. | This pass did not establish whether the item class mutates a base stat permanently, uses a removable ability modifier, or has a destruction inverse. The implementation/effect caller and item-removal path must be followed before calling permanence verified. |

The native class-name checks used here are exact-build RTTI string accessors,
not gameplay functions: Ward `0x00C340D0`, Faerie Fire `0x00C3CC30`,
Engineering Upgrade `0x00C812B0`, and Cold Arrows `0x00C5CBC0`. The RTTI
registry metadata in `games/warcraft-3/tft-ability-classes.txt` supplies
factory and registration addresses, but those fields are relative offsets in
its source executable and cannot be copied as preferred VAs into the Retail
1.29.2 executable. Attempting to treat RTTI generator records as native
constructors did not yield reliable method boundaries. Re-derive constructor
and vtable addresses from this exact executable before continuing static
callback inspection or setting Frida hooks.

No behavior claim in this batch is fully verified by native code. A follow-up
should prioritize one callback family at a time: (1) Ward cast → configured
UnitID → summon timed-life cleanup; (2) Faerie Fire hit → Bfae application →
vision/duration inverse; (3) Cold Arrows attack callback → mana/damage/buff
fields → buff expiry; (4) Engineering Upgrade rank reads → dependent ability
and stat updates; (5) item stat mutation → drop/remove/destroy inverse. The
data/tooltip evidence above can be reused without another Retail run, while a
runtime probe is needed only if those static paths cannot settle an observable
branch.

See [shared native ability functions](../ability-shared-native-functions.md) for
exact-build helpers and Ghidra caller counts that can shorten these callback
investigations. See [Retail ability architecture](../ability-retail-architecture.md)
for the recovered registration, instance, cast, and attached-status model.


### Jaina / Archmage remaining-fidelity follow-up (September 19, 2026)

A second conservative pass closes behavior that the bundled Warsmash source
makes explicit without broadening the shared damage/type model. Blizzard now
waits for its authored `Cast` interval before the first shard wave, then splits
each wave into shard presentation followed by damage 0.8 seconds later. The
phase is stored on the already-serialized thinker state, so saving between the
shards and impact resumes the pending damage phase rather than replaying art.
The existing target mask, DataD building multiplier and DataF aggregate cap
remain authoritative. Cold/spell damage typing and spell-sound parity are still
separate shared-system work.

Brilliance Aura now consumes the stock `air,ground,friend,self` target mask in
the cached Hero-aura path rather than treating every friendly entity in range as
a recipient. Rows that omit `targs` keep the historical friendly fallback for
sparse ROC/custom fixtures. This deliberately does not rewrite the engine-wide
organic/mechanical classification model; that broader cleanup is still separate.

Water Elemental keeps its existing DataA/UnitID/timed-life path but now preserves
the caster facing and relinks collision-displaced summons. Mass Teleport likewise
relinks every relocated unit (and dirties FOW blocker state where relevant), so
the server broad phase no longer retains the source position after the visual and
simulation coordinates have moved. Regression coverage documents Blizzard's
0.8-second phase timing and save/load continuation, Brilliance target filtering,
Water Elemental separation/facing, and Mass Teleport vacated-space relinking.

### Jaina / Archmage data-driven aura and targeting follow-up (September 19, 2026)

A third conservative pass closes two data-driven gaps that are explicit in the
bundled Warsmash implementation. Brilliance Aura now treats DataB as its
flat-versus-percentage switch: flat DataA remains MP/sec, while percentage DataA
scales the recipient's intrinsic mana regeneration (base unit regeneration,
ordinary mana-regeneration bonuses, and the current Intelligence regeneration
term). Flat and percentage Brilliance providers keep separate strongest-copy
slots, matching the separate non-stacking stat families used by Warsmash. The
Hero-aura cache also resolves the actual authored alias and rank before reading
Area, `targs`, DataA, and DataB, so custom Brilliance-derived abilities no longer
silently fall back to the stock `AHab` row.

The shared unit-target validator now reads `targs` from the caster's current
ability rank instead of always using level 1. This matters to Blizzard and Mass
Teleport when custom object data changes target classes across ranks, and it
preserves the requested alias as the data source. Focused regressions cover
rank-specific target masks and a custom percentage-mode Brilliance alias mixed
with a stock flat provider.

This pass still does not invent cold/spell damage typing, per-shard sound
semantics, or an engine-wide organic/mechanical target-class rewrite. Those
remain shared-system fidelity work because the current OpenRealm representations
do not model them cleanly enough for a low-risk Jaina-specific change.

### Jaina / Archmage summon identity and Blizzard effect-object follow-up (September 19, 2026)

A fourth conservative pass closes two presentation/lifecycle details that the
bundled Warsmash implementation makes explicit without extending OpenRealm's
shared damage model. Summon Water Elemental now also applies the ability's
authored BuffID to each created Elemental. OpenRealm deliberately keeps `BTLF`
as the authoritative timed-life clock because the existing timed-life bar and
`UnitPauseTimedLife` native are built around that status; the authored Water
Elemental buff supplies the WC3 ability-specific status/presentation identity
without introducing a second expiration timer. `BTLF` is now treated as
non-dispellable lifecycle state by the shared Dispel/Purge filter, so dispel
still deals its authored damage to summoned units but cannot accidentally turn
a surviving timed summon into a permanent unit.

Blizzard now resolves each shard's EffectArt through the level's authored
`EfctID` object, matching Warsmash's `effectId` path, instead of resolving the
visual directly from the casting ability alias. Focused regressions cover the
Water Elemental BuffID plus retained `BTLF`, preservation of timed life after
Dispel Magic, and the Blizzard EfctID art lookup.

That fourth pass intentionally left cold/spell damage typing and per-shard
ability sound alone because both required shared-system support. The following
pass adds the sound-data path; typed SPELLS/COLD damage still remains separate.

### Jaina / Archmage ability-sound follow-up (September 19, 2026)

A fifth conservative pass closes Blizzard's remaining high-confidence sound-data
gap without changing spell damage semantics. The typed metadata registry now loads
`UI\SoundInfo\AbilitySounds.slk` with the same sound-row schema already used for
unit/UI sounds, and ability/buff presentation exposes authored `Effectsound` /
`Effectsoundlooped` fields. `G_PlayAbilityEffectSound` resolves an alias from the
requested object or its base object and emits a positional world sound at the
requested effect point using the authored volume.

Blizzard now uses the level `EfctID` for both shard art and shard sound, matching
the bundled Warsmash implementation's `spawnSpellEffectOnPoint(effectId)` plus
`unitSoundEffectEvent(caster, effectId)` sequence. The sound fires once for each
DataC shard during the presentation phase, never during the delayed damage phase.
Regression coverage injects a synthetic `AbilitySounds.slk` row and verifies six
shard sounds, alias/path resolution, positioned playback, and 0-127 volume scaling.
The test MPQ also carries a minimal AbilitySounds fixture and verifies it is packed.

The server intentionally selects the first authored ability-sound file rather than
calling `rand()`: Warsmash performs variant selection in rendering/audio code, while
using OpenRealm's simulation RNG for presentation would perturb deterministic game
state. Client-side random variant selection plus authored pitch/pitch-variance are
still presentation refinements. SPELLS/COLD Blizzard damage typing, the broader
organic/mechanical target model, and finer Mass Teleport placement/order parity
remain separate shared-system work.
