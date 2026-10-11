# GapGuard for the Elegoo OrangeStorm Giga

GapGuard monitors a BTT Smart Filament Sensor **V2.1** on the OrangeStorm Giga. It checks whether filament is present and whether it is moving during a real file print. When a fault is confirmed, it uses the existing Elegoo pause macro.

**4.2.0-rc1 is a release candidate, not a stable release.** It was developed against a specific Elegoo Klipper installation. Check the [installation guide](docs/INSTALLATION.md) and [native macro requirements](docs/ORANGESTORM-GIGA-REFERENCE.md) before installing it. Do not update Klipper or replace your complete configuration to make it fit this module.

## What you need

- An OrangeStorm Giga with the matching native Elegoo macro behavior.
- A BTT SFS V2.1, the [printed mount](hardware/README.md), and the wiring described in the [hardware guide](docs/hardware/BTT-SFS-V2.1-ORANGESTORM-GIGA.md).
- DET0 connected to filament presence (PD4), and DET1 to filament motion (PD3). Check the actual signal, ground and supply pins before connecting them.

Start with [INSTALLATION](docs/INSTALLATION.md). It covers the mount, wiring, configuration, physical power cycle and first checks. Your mesh and other calibration data remain your own.

## Everyday use

| Command | Purpose |
|---|---|
| `GAPGUARD_STATUS` | Show the current mode, sensors and protection state |
| `GAPGUARD_STATUS_DEBUG` | Show more detailed diagnostics |
| `GAPGUARD_PAUSE` | Use the Elegoo pause, then set the nozzle target to zero while preserving bed targets |
| `GAPGUARD_ENABLE_FULL` | Monitor presence and motion |
| `GAPGUARD_ENABLE_PARTIAL` | Monitor presence only |
| `GAPGUARD_DISABLE_ALL` | Select BYPASS, with both filament protections disabled |

Use the existing Elegoo **RESUME** to resume manually and **CANCEL_PRINT** to cancel. A manual Elegoo PAUSE keeps its existing behavior. GapGuard-managed pauses also save and switch off fan1, restoring its saved value after real printing resumes. Validated runtime messages remain in French; the documentation is in English.

The supplied FULL profile uses motion thresholds **9 / 20 / 20 / 2**: suspicion at 9 mm without a transition, verification starting at 20 mm, a 20 mm verification interval, and two required transitions. These are extrusion distances, not time delays. See [configuration](docs/CONFIGURATION.md) for the exact boundary rules and parameter meanings.

## Automatic recovery

When GapGuard confirms that PD3 has stopped reporting motion while PD4 still reports filament present, it runs the existing Elegoo PAUSE once. The nozzle target becomes zero and the four bed zones keep their targets.

After the pause movement has finished, it waits 30 seconds. If the printer is still paused and filament is still present, AutoRecovery reheats the nozzle to its saved target. It then commands **300 mm of extruder travel in 15 blocks of 20 mm at F200**. This does not by itself prove that 300 mm of filament passed through the nozzle; PD3 transitions provide separate evidence of filament motion. It observes PD3 throughout these blocks and requires at least **two genuine transitions in total**. The full purge still runs if those transitions arrive early.

If validation succeeds, it performs the existing wipe, restores the saved print state and sends **one M24**. Recovery is complete only after the file really returns to active printing. If recovery cannot complete, it does not resume the print automatically; the printer remains paused unless you or another command has taken control. The [detailed recovery guide](docs/AUTORECOVERY.md) explains the checks and limitations. PD4 faults and a voluntary GapGuard pause do not start AutoRecovery.

## Optional S1+ monitoring

The separate FlowQ watcher provides status and notifications. It is **information-only** with GapGuard: no pause, resume, cancel or mode change. GapGuard does not need FlowQ to protect the print. See [S1+ integration](docs/S1PLUS-INTEGRATION.md).

## More information

[Troubleshooting](docs/TROUBLESHOOTING.md) · [Tests](docs/TESTING.md) · [Architecture](docs/ARCHITECTURE.md) · [Release notes](release/RELEASE_NOTES.md) · [History](docs/HISTORY.md)

Code is [GPL-3.0-or-later](LICENSE). Mount models are [CC0 1.0](hardware/LICENSE), with voluntary credit to T.L. The separate watcher is MIT. See [licenses and credits](docs/LICENSES-AND-CREDITS.md).
