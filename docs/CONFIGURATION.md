# Configuration

There are two complementary references:

1. [gapguard-example.cfg](../config/gapguard-example.cfg) contains the sections to add or merge: `[gapguard]`, six public macros and `[idle_timeout]`.
2. [OrangeStorm Giga dependency reference](ORANGESTORM-GIGA-REFERENCE.md) describes the existing native objects and saved states that must already behave as expected. Its excerpts are for comparison, not a complete configuration to install.

The overlay was compared with the live configuration observed on 11 October 2026, SHA-256 `5bb49d848ffeada5f21a611b8f16d163a1737dae6f641fd71531af85dcce358d`. The earlier validated file, `a018667f0ae1a7e20a19accbbd65bce103d8f83b4c323679e5f275aae5768bbc`, differs in its private calibration block and comment normalization, with no functional difference before SAVE_CONFIG. Neither complete file is distributed. English comments and descriptions change wording only; executable overlay settings and macro bodies match the live functional blocks.

The 4.2.1-rc1 update adds no configuration option and changes no functional value in this overlay. Its header identifies the candidate; all executable settings and macro bodies are unchanged. An existing matching 4.2.0 installation only needs the module update. See [Upgrading and rollback](UPGRADING-4.2.1.md).

## Detection settings

| Setting | Reference value | Meaning |
|---|---:|---|
| motion_pin | PD3 | Motion input, non-inverted |
| presence_pin | PD4 | Presence input; HIGH means present |
| extruder | extruder | Existing toolhead extruder object |
| default_mode | FULL | Both protections on at startup |
| suspect_distance | 9.0 | Extrusion without an edge before suspicion |
| verify_trigger | 20.0 | Verification starts this far from the E reference |
| verify_distance | 20.0 | Verification length; reference end is 40 mm |
| verify_transitions | 2 | Genuine transitions required during verification |
| check_interval | 0.250 | Monitoring timer period in seconds |
| init_guard | 0.250 | Minimum extra acquisition guard in seconds |
| motion_trace | 1 | Detailed PD3 logging enabled |

Distances use native extruder position history, not elapsed time, XY travel or a measured delivered filament length. The Python fallback values are 9/50/12/6: keep the explicit overlay values to reproduce the tested 9/20/20/2 profile. An edge at the verification entry boundary has priority; a qualifying final edge at the inclusive end boundary can still prevent a pause not yet dispatched. See [architecture](ARCHITECTURE.md).

## AutoRecovery settings

The overlay sets enabled=1, delay=30 seconds, distance=300 mm, chunk=20 mm, minimum transitions=2 and feedrate=200 mm/min. The module permits enabled 0/1 and a positive integer transition minimum. It validates the other four numeric values against the fixed implementation values; they are not freely adjustable merely because they appear in printer.cfg.

At least two transitions are counted cumulatively across the complete purge. This criterion is separate from the normal-print verification interval. The purge is not shortened when the count is reached. See [AutoRecovery](AUTORECOVERY.md).

## Pause and idle behavior

The `pause_origin == "gapguard"` idle branch sends only a nozzle-target-zero command. It neither changes nor restores bed targets. The existing four targets therefore remain in force, including when the native 1800-second pause timeout expires. This applies to PD3 faults, PD4 faults and voluntary GAPGUARD_PAUSE. Manual Elegoo pauses and CANCEL retain their existing paths.

The module saves fan1's normalized 0..1 value, turns it off for its own confirmed pause and restores the saved value multiplied by the output pin's scale after actual printing resumes. The reference uses scale 255. Keep the existing M106/M107 integration.

The overlay contains no bed mesh, SAVE_CONFIG data, PID settings, motor currents or unrelated calibration. It does not replace the user's PAUSE, RESUME, CANCEL_PRINT, homing or hardware definitions.
