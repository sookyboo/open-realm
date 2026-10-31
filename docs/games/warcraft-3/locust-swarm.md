# Crypt Lord Locust Swarm — Patches 5–8 (controller, combat, lifecycle and presentation)

## Source and contract

`AUls` is a self-target ultimate. The active AbilityData row supplies `UnitID`,
`Dur`, `Area`, and `DataA`–`DataE`; the reference Warcraft data uses `uloc`,
30 seconds, 800 range, 20 locusts, 0.2-second release interval, seven attackers
per target, a 0.75 healing factor and a 20-health return threshold. **Gameplay
reads the concrete row**, so custom map values override those stock numbers.
`AOls` (Voodoo Spirits) now dispatches through `CAbilityLocustSwarm` too, but
reads its **own** `UnitID`, `Dur`, `Area`, `targs` and `DataA`–`DataE` values;
it must not inherit stock AUls counts, targeting or healing parameters.
The swarm applies the authored ability target-category mask alongside the
locust weapon mask; it intentionally does not exclude ordinary physical hits
merely because the victim is spell immune.

## Release lifecycle

`CAbilityLocustSwarm` is now an ordinary non-channelled no-target cast.
The ability validates presence of a summoned `UnitID`, positive `Dur`, positive
`DataA` and positive `DataB` before a committed cast. On execution it creates
one invisible `locust_swarm_think` controller, which retains the caster's
`spawn_time` identity and an authored release schedule. The first release occurs
one interval after the cast, then successive releases are interval-spaced.
This *first-release policy* is provisional until verified against retail.

The first release occurs immediately on the next simulation think, followed
by interval-spaced releases. This first-release policy remains provisional
until verified against retail. Each release uses the current caster location and the existing summon helper
`S_SummonAbilityAt` (food, spawn and ownership events). Each summoned unit
gets a `locustMember_t` with the controller pointer, its spawn generation and
its release index. Membership is distinct from the caster's generic `owner`
field. Summons have no individual `BTLF` timed-life status; the controller
removes its children at the 30-second expiry, or on caster removal/death/
identity change. The controller does **not** cancel when the Crypt Lord moves
or attacks. It catches up on elapsed simulation deadlines after a delayed tick,
with a per-tick release budget of 32 and a protective ceiling of 256 units
for malformed custom `DataA`. A release slot is spent even if a pool/spawn
allocation fails, preventing infinite retry loops.

## Saved state

The typed pools use component IDs 32 `LOCUST_SWARM` and 33 `LOCUST_MEMBER`;
ID 31 is Impale and ID 34 is the independent Impale lift. The save version
is 135. The component schemas serialize authored schedules, target identities,
attack deadlines, damage credit and recall phase/deadline. Controller and
member thinkers are registered for save/load. The controller is game-owned
and invisible (`SVF_NOCLIENT`), not a client-side simulation or a Warcraft
JASS channel.

## Remaining phases

Patches 5–8 implement release, target acquisition, authored attacker caps,
ordinary physical attack damage, damage-credit healing, expiry recall, caster
death/teleport cleanup, recast replacement, the `AOls` Voodoo Spirits alias,
and optional model-authored Walk animation and looping ability sound.

The implementation uses ordinary movement and attack orders, so the unit
model's available `Walk` sequence is selected by the shared movement system.
It does not create a separate locust missile: attacks apply through the shared
physical attack resolver. The controller resolves `SoundLooping` through the
generic ability sound path. Whether retail uses a separate `LocustMissile.mdx`
visual, exact orbit path, hit timing, recall grace and heal-threshold ordering
still needs comparison against retail. Missing art must not suppress simulation.

## Regression fixtures

`game/tests/t_locust_swarm.c` uses a deliberately non-stock `AUls` row with
`DataA=3`, `DataB=0.25`, `Dur=5`, `UnitID=hfoo`, a reduced target cap and
custom return fields. It tests delayed release, caster movement, catch-up,
identity cleanup, and save/load midway through release. The fixture is
synthetic and does not require the user's Warcraft archives.

Patch 8 adds alias-data and optional Walk-animation tests. Patch 7 adds tests
for expiry recall and credited healing, caster death, spell teleport,
successful recast and mid-recall save/load. Patch 6 tests attacker reservations,
normal physical damage and return healing, invulnerable/allied target rejection
and a member mid-flight save/load round-trip. These fixtures are synthetic and
do not require Warcraft archives. Retail orbit and missile presentation remain
visual verification gaps.
