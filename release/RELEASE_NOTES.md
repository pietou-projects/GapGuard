# GapGuard 4.2.0

This is the **first stable public release** of GapGuard. The maintainer has accepted the existing runtime validation on the reference installation. No new physical test was performed for this documentation and packaging promotion.

GapGuard 4.2.0 uses the exact production module validated during 4.2.0-rc1. For reproducibility, the Python module was not modified solely to change its internal version string, so the reference printer still reports 'GapGuard 4.2.0-rc1 ready'. This cosmetic difference is intentional; no new software behavior was introduced for the stable release.

GapGuard was developed after normal Infinity Flow S1+ A→B spool changes were observed to produce unusually long motion-signal gaps that could trigger false motion alarms even though filament feeding resumed normally. It is designed to tolerate transient handoff behavior without simply delaying detection of genuine feed failures; these observations do not explain every historical PD3 silence.

The production module is exactly `cf239a52f65f345092946f2289a473c590244ced22c5f31c27e88e26b20473f1`. It monitors a BTT SFS V2.1 using PD4 presence and PD3 motion on the tested Elegoo OrangeStorm Giga with a ZNP GIGA V3.0 board and STM32F407VET6 MCU. The supplied profile is 9/20/20/2.

GapGuard-managed pauses use the native Elegoo PAUSE, set the nozzle target to zero and preserve all four bed targets. Their fan1 state is saved, switched off and restored after real printing resumes. Manual Elegoo PAUSE, RESUME and CANCEL_PRINT retain their behavior.

AutoRecovery after PD3_NO_MOTION with PD4 present waits for the pause to finish and then waits 30 seconds. It reheats the nozzle and commands 300 mm of extruder travel in 15 × 20 mm blocks at F200, requiring at least two genuine transitions across the full purge. Commanded extruder travel does not by itself prove that 300 mm of filament passed through the nozzle; PD3 transitions provide separate evidence of actual filament motion. It submits the continuous F15000 wipe, restores the saved state and sends one M24, then confirms actual active printing. See [AutoRecovery](../docs/AUTORECOVERY.md) for all checks and limitations.

The public interface has six commands: GAPGUARD_PAUSE, GAPGUARD_STATUS, GAPGUARD_STATUS_DEBUG, GAPGUARD_ENABLE_FULL, GAPGUARD_ENABLE_PARTIAL and GAPGUARD_DISABLE_ALL. Validated runtime messages remain French. The watcher is a separate optional project and is not included in this GapGuard release. The tested integrated installation currently uses an information-only watcher. The watcher repository's historical public v1.0.0 release used automatic pause behavior; a sanitized, live-derived public update is being prepared separately.

The package includes the production module, mergeable configuration, native dependency reference, English documentation, automated tests, five exact hardware photographs and the exact STL/3MF mount models. It excludes complete private configurations, mesh/SAVE_CONFIG, PID data, credentials and machine logs. Code is GPL-3.0-or-later; models are CC0 1.0 with voluntary credit to T.L.

The 223 public tests exercise simulated behavior. Passing them does not establish physical reliability on every printer or resolve the cause of every historical PD3 signal gap. Hardware identification is V2.1 for this installation; external V2.0 documentation does not imply universal equivalence.

## Known limitation

The underlying cause of every historical PD3 signal gap has not been identified. GapGuard is designed to detect and safely handle confirmed loss of filament-motion evidence, but it does not claim to resolve the electrical or physical origin of every PD3 gap.

## Development and release continuity

GapGuard was developed by Pierre Juillard with substantial assistance from ChatGPT by OpenAI for log analysis, diagnostic reasoning, Python/Klipper code development, tests, documentation, review and release preparation. The maintainer performed the hardware observations and physical runtime validation on the reference printer. AI assistance was a development tool, not a substitute for physical validation.

This stable package carries forward the corrected hardware documentation, five retained photographs, Why GapGuard exists context and AI assistance credit. The previous v4.2.0-rc1 tag and Pre-release are preserved. No configuration behavior, production code, reference-printer file or watcher is changed by this promotion.
