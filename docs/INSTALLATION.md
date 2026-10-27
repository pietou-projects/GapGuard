# Installing GapGuard on an OrangeStorm Giga

This guide reproduces the audited Giga integration. It is not a full replacement printer configuration. Work with the printer idle and keep a backup of your current module and configuration together. Preserve your mesh, SAVE_CONFIG, PID tuning and all unrelated settings.

**This guide accompanies the 4.2.1-rc1 Pre-release. Automated tests and loading on the reference printer have passed; validation during real printing is still pending.** If you already use the matching 4.2.0 integration, follow [Upgrading and rollback](UPGRADING-4.2.1.md) instead of repeating the installation or rewriting your configuration.

## 1. Check compatibility

The reference setup uses a ZNP GIGA V3.0 board, STM32F407VET6 and a BTT Smart Filament Sensor V2.1. The audited Klipper reports `v0.11.0-303-g67499853-dirty`; that identifies the observed installation, not a recommendation to install or update to another build. Compatibility depends on the [native dependency contract](ORANGESTORM-GIGA-REFERENCE.md), not just a version label.

The production module is [src/gapguard.py](../src/gapguard.py), version 4.2.1-rc1, SHA-256 `bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a`. Files under tests are not installation modules. No firmware flash, Klipper update or Moonraker update is part of this procedure.

## 2. Print the sensor mount

Use the exact STL or 3MF in [hardware](../hardware/README.md). The documented fasteners are three M3 × 16 mm screws with three M3 washers, and two M4 × 10 mm screws with two M4 washers. Follow the [hardware guide](hardware/BTT-SFS-V2.1-ORANGESTORM-GIGA.md) for the tested arrangement and source credits.

## 3. Mount the SFS V2.1

Secure the sensor and route filament through it toward the extruder. In the reference S1+ installation the path is S1+ → SFS → PTFE tube → Giga print head. The S1+ and its watcher are optional. Avoid cable strain and check that the filament path moves freely.

## 4. Connect DET0 and DET1

With power off, follow the hardware guide: DET0 is presence on PD4; DET1 is motion on PD3. The guide contains photographs of the connectors and board. Do not infer the wire order from the JST housing orientation.

## 5. Verify polarity and pin order

Identify SIGNAL, GND and +5V physically before applying power. The reference inputs are not inverted: PD4 HIGH means filament present, and PD3 alternates HIGH/LOW as filament moves. The documented electrical observations establish this installation's wiring; they do not establish universal equivalence between SFS V2.0 and V2.1. Stop if your hardware or polarity differs.

## 6. Copy the production module

Using your usual file-transfer tool, back up any existing module and place only `src/gapguard.py` at `/home/mks/klipper/klippy/extras/gapguard.py` on the reference layout. Preserve file ownership and permissions, then verify the SHA-256 above. Do not copy tests or replace stock Klipper sources. Do not restart yet: complete the configuration first.

Run this read-only command in the printer's SSH terminal to check the copied module:

```bash
sha256sum /home/mks/klipper/klippy/extras/gapguard.py
```

Expected SHA-256:

```text
bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a
```

## 7. Check the native Elegoo macros

Compare your existing PAUSE, RESUME and CANCEL_PRINT with the [dependency reference](ORANGESTORM-GIGA-REFERENCE.md) and its exact excerpts. Keep these macros; do not substitute generic Klipper macros. PAUSE must save the coordinates, temperature, flags and both G-code states needed by AutoRecovery. The tested native pause stops Virtual SD with M25 without assigning ownership to BASE_PAUSE. The manual native RESUME includes its own 100 mm purge. If your native contract differs, this configuration is not verified for it.

## 8. Remove duplicate sensor ownership

Remove the old `[filament_switch_sensor fila]` and `[filament_motion_sensor sfs_motion]` blocks if present, and check all included files for other owners of PD3 or PD4. Remove references that still require those removed objects. GapGuard must be the sole owner of both inputs. Do not add a duplicate-pin override for either pin. The unrelated historical PC0 override is outside this change.

## 9. Add the GapGuard sections

Merge `[gapguard]` and the six public macro sections from [gapguard-example.cfg](../config/gapguard-example.cfg). Do not create duplicate sections. These macros only delegate to the internal Python commands. They expose the six public controls in Fluidd without replacing PAUSE, RESUME or CANCEL_PRINT. Use the explicit 9/20/20/2 profile: the Python fallback defaults differ.

## 10. Merge idle_timeout

Merge the example's `[idle_timeout]` into your existing section; do not add a second one. The first branch recognizes a GapGuard-managed pause and sets only the nozzle target to zero, leaving all four bed targets unchanged. The remaining branches preserve the audited Elegoo behavior for other idle states. Compare your existing behavior before merging. Do not copy the private reference machine's complete printer.cfg or calibration.

## 11. Power the Giga off physically

After verifying the completed file changes, switch the printer fully off. Do not use RESTART, FIRMWARE_RESTART or a service restart to load this Python module as part of this procedure.

## 12. Wait approximately 30 seconds

Leave the printer off for about 30 seconds.

## 13. Power on

Switch it on normally. No flashing or software update is required.

## 14. Check loading

Wait for Klipper Ready and inspect klippy.log for `GapGuard 4.2.1-rc1 ready`. Check for configuration errors or exceptions. Confirm that the six public macros are present in Fluidd. Do not proceed with a print if loading failed.

After the physical power cycle, use the printer's SSH terminal to inspect the loading message:

```bash
grep -a "GapGuard .* ready" /home/mks/klipper_logs/klippy.log | tail
```

The output should contain `GapGuard 4.2.1-rc1 ready` for the new startup. Older matching lines alone do not confirm this startup.

## 15. Read the initial status

Run `GAPGUARD_STATUS`. Use `GAPGUARD_STATUS_DEBUG` if more detail is needed. Initial inputs may briefly be UNKNOWN while acquisition finishes. UNKNOWN is not a missing-filament fault or a motion transition. The acquisition deadline depends on the actual MCU object ID; see [architecture](ARCHITECTURE.md). At rest there should be no active print session or fault.

## 16. Understand the modes

FULL monitors PD4 presence and PD3 motion. PARTIAL monitors PD4 only. BYPASS disables both protections. The three public mode commands are `GAPGUARD_ENABLE_FULL`, `GAPGUARD_ENABLE_PARTIAL` and `GAPGUARD_DISABLE_ALL`. Mode changes reset the logical monitoring reference; they do not reset the sensor electronics. Return to FULL for the reference checks.

## 17. Check PD4 without printing

Insert and remove filament at the sensor and compare `GAPGUARD_STATUS` with the physical condition. Presence should change accordingly. A missing filament outside an actual print must not request a print pause. This check needs no heating, movement command or print.

## 18. Check PD3 without printing

Move filament through the sensor by hand and inspect the PD3 level in `GAPGUARD_STATUS_DEBUG`. PD3 is a level that toggles, not a continuously asserted motion flag; occasional status queries can miss transitions. The reference `motion_trace: 1` writes detailed `[GAPGUARD_TRACE]` records to klippy.log. Use those records to distinguish real HIGH→LOW/LOW→HIGH transitions from startup acquisition. Do not infer failure from a single unchanged snapshot.

## 19. Start a normal print

Only after the startup and sensor checks pass, start your usual known-good test file through the normal interface. GapGuard should report an actual file session, FULL monitoring and movement. This procedure does not supply an unvalidated test G-code file. Observe the printer; offline tests do not replace physical validation.

## 20. Understand pauses and recovery

Manual PAUSE remains Elegoo behavior. `GAPGUARD_PAUSE` and confirmed sensor faults use that pause, then set the nozzle target to zero while maintaining bed targets. GapGuard also saves and switches off fan1 and restores it after real printing resumes. Successful AutoRecovery resumes the file itself through one M24; do not also run RESUME after it succeeds. Manual Elegoo RESUME is used only when the operator intentionally takes over a paused print or automatic recovery has not resumed it. The reference Elegoo RESUME includes its native `G1 E100 F200` purge. CANCEL_PRINT remains the native cancel command.

Only confirmed PD3_NO_MOTION with PD4 present arms AutoRecovery. After physical pause completion and 30 seconds, it can reheat and run the full 300 mm purge. It requires at least two real PD3 transitions accepted by the main detector in the current recovery generation. It then checks detector consistency before wiping, prepares a fresh resume generation and sends one M24. It confirms actual printing afterward. Read [AUTORECOVERY](AUTORECOVERY.md) before deliberately testing this behavior; do not expect a manual GapGuard pause or PD4 fault to start it.

If any check fails, retain the logs and use [troubleshooting](TROUBLESHOOTING.md). Restore your own saved module/configuration pair if rollback is needed; never replace your mesh with another machine's data.
