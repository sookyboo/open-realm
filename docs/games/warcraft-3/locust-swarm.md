# Crypt Lord Locust Swarm — Patches 5–6 (controller, combat and return)

## Source and contract

`AUls` is a self-target ultimate. The active AbilityData row supplies `UnitID`,
`Dur`, `Area`, and `DataA`–`DataE`; the reference Warcraft data uses `uloc`,
30 seconds, 800 range, 20 locusts, 0.2-second release interval, seven attackers
per target, a 0.75 healing factor and a 20-health return threshold. **Gameplay
reads the concrete row**, so custom map values override those stock numbers.
The planned `AOls` Voodoo Spirits conversion remains in Patch 8: it is still
registered with `CAbilityVoodooSpirits` rather than this AUls controller.

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
is 133; the component schemas serialize the authored schedule,
controller/member identities, and the target/heal parameters already needed
by Patch 6. The `locust_swarm_think` callback is registered for save/load.
The controller is game-owned and invisible (`SVF_NOCLIENT`), not a client-side
simulation or a Warcraft JASS channel.

## Remaining phases

**Patch 5 does not implement locust combat, flight/orbit, seeking, return-to-
heal or specialized recast/teleport policy.** Existing spawned-unit behaviour
may still apply until Patch 6 replaces it with dedicated swarm movement.
Patch 7 will refine return-before-expiry/teleport/recast and cleanup semantics;
Patch 8 will integrate art, sound, and `AOls` alias behaviour. Do not claim
stock retail combat parity from a passing release-scheduler test.

## Regression fixtures

`game/tests/t_locust_swarm.c` uses a deliberately non-stock `AUls` row with
`DataA=3`, `DataB=0.25`, `Dur=5`, `UnitID=hfoo`, a reduced target cap and
custom return fields. It tests delayed release, caster movement, catch-up,
identity cleanup, and save/load midway through release. The fixture is
synthetic and does not require the user's Warcraft archives.

Patch 6 adds tests for attacker reservations, normal physical damage and
return healing, invulnerable/allied target rejection and a member mid-flight
save/load round-trip. No compiler or tests were run while authoring this patch. The owner should
run the test suite and verify real `uloc` visuals/flight after Patch 6–8.
