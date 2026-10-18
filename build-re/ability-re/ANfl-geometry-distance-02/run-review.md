# Geometry-distance-02 run review

- Prepared map SHA-256: `ef71af9577f3dc9a60dfb18fcfe100a0a30dc9154210b9a39eaf4709ec569e3d`.
- The pre-observation prediction is `predictions/geometry-distance-02-v2.json`; retain the superseded v1 arithmetic prediction.
- The prepared campaign control was visually confirmed at the expected “To Tame a Land” card, then the prepared map reached gameplay.
- Chat handler marker `ANFL_SCENARIO_HANDLER_ENTRY_A_21` appeared, but no geometry-specific result was written. Inspection of `lab/lab-functions.j` found stale run IDs (`anfl-clean-combat-01-no-cast`, prior ally case) and `RE_Finish` has no matching output branch for those IDs. Therefore the setup/cast result is invalid and no callback absence or presence from this attempt is geometry evidence.
- No Frida observer was attached and no cast result was interpreted. This is a rejected harness case, not a negative spatial result.
