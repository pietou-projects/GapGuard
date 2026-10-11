# GapGuard for the Elegoo OrangeStorm Giga

GapGuard monitors a BTT Smart Filament Sensor **V2.1** on the OrangeStorm Giga. It checks whether filament is present and whether it is moving during a real file print. When a fault is confirmed, it uses the existing Elegoo pause macro.

**4.2.0-rc1 is a release candidate, not a stable release.** It was developed against a specific Elegoo Klipper installation. Check the [installation guide](docs/INSTALLATION.md) and [native macro requirements](docs/ORANGESTORM-GIGA-REFERENCE.md) before installing it. Do not update Klipper or replace your complete configuration to make it fit this module.

## Why GapGuard exists

GapGuard grew out of filament-motion problems observed with an Infinity Flow S1+ feeding a BTT Smart Filament Sensor V2.1 upstream of an OrangeStorm Giga.

During an automatic A → B spool change, the filaments are not spliced together. The S1+ actively pushes filament B against the remaining end of filament A. Their B|A junction travels through the PTFE path and the SFS toward the printer.

```text
Spool B → Infinity Flow S1+ → B pushes the remaining A → BTT SFS V2.1 → Giga
                              B ─── B|A ─── A
```

This diagram illustrates the push relationship, not the physical scale or exact routing. B and A are not fused together.

Normal S1+ spool handoffs were observed to produce unusually long PD3 gaps, and this could trigger false motion alarms. PD4 could still report filament present throughout the gap. In one reproduced handoff, an earlier watchdog entered suspicion, received no PD3 transition within its then-too-short verification window and raised an alarm. PD3 started switching again shortly afterward as filament B resumed moving through the sensor. A temporary motion-signal gap therefore did not necessarily mean feeding had failed. These observations do **not** establish the cause of all historical PD3 silences.

The challenge was to tolerate legitimate handoff interruptions while still detecting a real jam, loss of motion or failed handoff promptly. Simply making a timeout, threshold or detection distance much larger could reduce false alarms at the cost of detecting genuine failures much later.

GapGuard uses two different pieces of local evidence: **PD4 / DET0** indicates physical filament presence; **PD3 / DET1** supplies genuine HIGH↔LOW motion transitions. Presence alone cannot establish motion, and a brief absence of motion transitions should not cause an immediate pause.

```text
Normal motion → real PD3 transitions → printing continues
Temporary gap → SUSPECT / verification
              → PD3 meets the verification rules in time → printing continues
Failed verification → native Elegoo PAUSE
                    → if eligible, controlled AutoRecovery feed test
                    → PD3 motion evidence and recovery checks pass
                    → resume and confirm actual printing
```

A returning transition must satisfy the existing verification rules; this does not promise that every temporary gap will be tolerated. Eligible recovery resumes only after validation. The current thresholds and recovery procedure are described below.

FlowQ is deliberately outside this safety decision. GapGuard relies on local PD3/PD4 signals, not cloud timing, a FlowQ state change or a reported A/B state. The optional watcher adds information, monitoring and notifications; GapGuard must protect the print without it.

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

## Development and AI assistance

GapGuard was developed by Pierre Juillard through extensive testing on a real Elegoo OrangeStorm Giga.

The project was developed with substantial assistance from ChatGPT by OpenAI, including log analysis, diagnostic reasoning, Python/Klipper code development, test design, documentation, code review and release preparation.

The hardware observations, printer modifications, physical tests and final runtime validation were performed by the maintainer on the reference OrangeStorm Giga.

AI assistance was used as a development tool, not as a substitute for physical validation on the printer.

## More information

[Troubleshooting](docs/TROUBLESHOOTING.md) · [Tests](docs/TESTING.md) · [Architecture](docs/ARCHITECTURE.md) · [Release notes](release/RELEASE_NOTES.md) · [History](docs/HISTORY.md)

Code is [GPL-3.0-or-later](LICENSE). Mount models are [CC0 1.0](hardware/LICENSE), with voluntary credit to T.L. The separate watcher is MIT. See [licenses and credits](docs/LICENSES-AND-CREDITS.md).
