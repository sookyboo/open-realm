# Historical ability implementation notes

These notes describe OpenRealm implementation work informed by historical investigation and bundled source. They are not Retail binary findings.

## Jaina / Archmage follow-up (September 19, 2026)

The Archmage review tightened three abilities without adding Hero-specific
branches. `AHwe` now treats DataA as the authored summon count, records the
creating ability on each summon, and emits TargetArt while retaining the shared
timed-life/event path. `AHbz` now evaluates its own authored target mask, applies
DataD to structures after the DataF per-wave cap, and emits DataC EffectArt
shards without using the visual positions for hit detection.

`AHmt` now participates in the shared channel lifecycle instead of relocating
immediately. DataB owns the completion delay; a thinker retains the destination
entity incarnation, temporarily pauses that destination, owns persistent area
effects, and cleans all of those resources on success or cancellation. Completion
uses the current destination position, keeps the caster inside the DataA total,
excludes allied-player armies and structures from the payload, honors DataC
clustering, and uses ordinary unstuck placement. The thinker callback is appended
to the save callback roster, and regression coverage includes delayed completion,
unit-cap/ownership filtering, structure destinations, destination death,
cancellation cleanup, Water Elemental DataA ownership, Blizzard structure
scaling, and production save/load continuation.

Brilliance Aura remains on the existing cached Hero-aura path. This follow-up
does not replace that path with the newer generic target-token helper because the
current unit `targtype` representation conflates movement class and
organic/mechanical classification; doing so here could regress stock mechanical
recipients. That broader target-model cleanup remains separate work.
