# ACss synchronized effect recovery probe

Retail 1.29.2.9231 probe measuring creep Shadow Strike (`ACss`) poison events,
movement speed, and attack-hit intervals together. It compares a treated
Mortar Team with an untreated control. The manifest and JASS inputs are
prepared through the [Retail probe runner](../../wc3_retail_probe.py); follow
the control-map, persistent-Xvfb, and JHCR workflow in
[`docs/games/warcraft-3/ability-probes/jhcr.md`](../../../docs/games/warcraft-3/ability-probes/jhcr.md).

Each lane uses an `hmtm` attacker owned by Player 1 and a paused, high-health
`hfoo` target owned by Player 12, 400 units away. Both attackers start at
400 speed and are position-locked every 50 ms. The Player 0 Warden caster has
rank-1 `ACss` and casts on the treated attacker after 15 seconds of baseline.
The event logger matches handle IDs for attack hits and caster-sourced spell
damage. Speed is sampled every 250 ms. The run lasts 50 seconds, leaving
35 seconds after the cast.

## Verified run

Run 3 is the corrected capture. Both lanes had three baseline intervals of
70 timer ticks (3.5 seconds); the control continued at 70 ticks throughout.
Retail accepted the cast order at tick 300 and confirmed the spell effect at
tick 311. The treated attacker then showed:

| Observation | Effect age | Result |
|---|---:|---|
| Initial spell damage | 5 ticks | 75 damage |
| Poison pulses | 65, 125, 185, 245, 305 ticks | Five 10-damage events, 60 ticks apart |
| Movement recovery | 309 ticks | First 400-speed sample; preceding sample at age 304 was 398.089 |
| Attack intervals after cast | Ends at ages 147, 233, 306 ticks | 149, 86, 73 ticks, against 70-tick baseline |
| First baseline attack interval | Starts at age 306, ends at 376 | 70 ticks; following intervals also remained 70 |

Thus the final poison pulse occurred at age 305 ticks (15.25 seconds). The
last lengthened attack interval ended one tick later; a full baseline interval
began at age 306. Movement speed was back to 400 by the age-309 sample
(15.45 seconds). In this run, all three observed endpoints cluster within
four 50 ms timer ticks. The timer and attack-hit samples do not reveal a finer
continuous expiry boundary.

### Failed and intermediate harness attempts

- Run 1 used `hfoo` attackers owned by Player 12. The control lane hit, but the
  treated lane recorded no attack hits even before casting, so it cannot
  answer the attack-rate question. Its capture is retained as
  `retail-1292-run1-inconclusive.txt`.
- Run 2 switched to the known-working `hmtm` lane and reproduced the events,
  but its summary mistakenly recorded the pre-slow 400-speed sample as
  recovery. The raw samples still show the real recovery at age 309; Run 3
  fixes the sentinel to require observing a slow first.

These attempts are kept with their runner `capture.json` files. Only Run 3 is
used for the verified conclusion.

Raw Run 3: [retail-1292-run3.txt](evidence/retail-1292-run3.txt), SHA-256
`d076ab15f6da3017c46c4aec8d3156f69391f9b112c414442f29ffe277cc1079`.
The corresponding `capture.json` reports `ready_for_review`; this is a
freshness and marker check, not a gameplay verdict.
