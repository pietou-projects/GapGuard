# PD3 recovery: 4.2.1-rc1 test status

Updated 27 October 2026.

**The 4.2.1-rc1 candidate is installed and starts correctly on the reference OrangeStorm Giga. Its behavior during a real print still needs to be checked.** This page records progress on the PD3 recovery problem. The candidate is published as a [Pre-release for testing](https://github.com/pietou-projects/GapGuard/releases/tag/v4.2.1-rc1), not as a stable fix.

## What went wrong

During long prints with an Infinity Flow S1+ feeding the BTT SFS V2.1, the maintainer observed repeated `PD3_NO_MOTION` faults after AutoRecovery. A change from spool A to spool B often preceded the problem; the reverse change caused it less often or not at all.

The maintainer reported 108 faults between 22:48 and 08:37, with similar behavior on two prints lasting more than five hours. These are reported observations, not a claim that every event was independently reconstructed from the retained logs. Each recovery commanded 300 mm of extruder travel. The initial A/B junction alone does not account for the persistent sequence of repeated faults.

Switching to PARTIAL and then back to FULL had restored motion monitoring on the reference printer. This observation helped identify what needed to be checked in the software. It is not evidence that all PD3 signal gaps have the same cause.

## What the code review found

In 4.2.0, AutoRecovery counted PD3 transitions during its purge separately from the main motion detector. Because the print file was paused, those purge transitions did not go through the main detector's normal motion-processing path.

The main detector was rearmed when the file resumed. The problem was that the purge's motion evidence and the detector's new state were not tied together. Successful recovery therefore did not establish that both parts of the software agreed about the state of motion monitoring.

That inconsistency is established by the code review. The older logs do not contain enough internal state to prove exactly why each individual fault recurred. The physical or electrical cause of the first PD3 gap remains a separate, unresolved question.

## What the candidate changes

The candidate uses one shared rearming operation for both a manual return to FULL and AutoRecovery. Rearming gives the detector a fresh extrusion reference and clears the previous monitoring counters without inventing a sensor transition.

It also gives each monitoring period a number, called a **generation**. This lets the software distinguish events from before the pause, events during the purge, and events after resuming. An old event cannot be reused as new motion evidence.

During recovery, genuine PD3 transitions must be accepted by the main detector before they count toward recovery. Before the single `M24` resume command, the candidate prepares a fresh monitoring generation. When the file actually resumes, it keeps that prepared generation instead of resetting it again. The first valid motion transition after resuming moves the detector from `ARMING` to `NORMAL`.

The existing settings and operator controls are preserved:

- The configured motion thresholds remain **9 / 20 / 20 / 2**.
- Recovery still waits **30 seconds** after the pause has finished.
- It still commands **300 mm of extruder travel**, in **15 blocks of 20 mm at F200**, and requires at least **two genuine PD3 transitions across the full purge**.
- Commanded extruder travel does not by itself prove that 300 mm of filament passed through the nozzle.
- The continuous wipe remains at **F15000**, followed by one `M24` and passive confirmation that the file has resumed.
- The six public GapGuard commands, native Elegoo PAUSE / RESUME / CANCEL_PRINT, fan1 behavior, PD4 protection and pause heating behavior remain unchanged.

## What has been verified

| Check | Result |
|---|---|
| Automated candidate tests, including the extracted package | **258 / 258 passed** |
| Repeated recovery test | **100 simulated cycles passed** |
| Shared rearming behavior compared with returning to FULL manually | **Passed in automated tests** |
| Syntax check with the printer's Python 3.7.3 | **Passed** |
| Installation of the exact approved module | **Verified on 27 October 2026** |
| Loading after a physical power cycle | **Verified on 27 October 2026** |
| Klipper state after startup | **Ready** |
| New candidate tested through a real print and spool change | **Pending** |
| Repeated false faults eliminated in real printing | **Not yet established** |

The post-startup check found no exception in that startup sequence. GapGuard reported `4.2.1-rc1`, FULL mode and completed sensor acquisition. PD3 was LOW and PD4 reported filament present. The printer was in standby with no open file, no native pause, no active fault and AutoRecovery in `IDLE`. Inactive motion monitoring at that point was expected because no print was running.

The printer log contained:

```text
GapGuard 4.2.1-rc1 ready
```

The installed candidate's SHA-256 is:

```text
bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a
```

Only the GapGuard module was replaced for this test installation. The configuration, stock Klipper modules and FlowQ watcher were not changed. No connectors were swapped, and no upstream Klipper patches were applied. The startup check itself was read-only and sent no G-code.

## What remains to be tested

The maintainer will run the agreed print test in FULL mode and observe an A-to-B spool change. If it triggers a fault, the check must follow the entire recovery: one pause, the full purge, valid PD3 motion evidence, one resume command, the actual return to printing and healthy motion monitoring afterward.

The minimum acceptance check includes no unexplained recurrence for at least one hour after recovery, or until the file finishes if sooner. A B-to-A change must also be observed as part of the planned test sequence. The printer should no longer need a manual PARTIAL-to-FULL switch to restore monitoring.

Until those checks are complete, the issue remains open and **4.2.1-rc1 is a candidate under test**. Passing automated tests and reaching Ready do not prove that the recurring fault is fixed.

The published [4.2.0 release](https://github.com/pietou-projects/GapGuard/releases/tag/v4.2.0), its tag and download assets are unchanged. The source on `main` and the new `v4.2.1-rc1` tag now contain the exact candidate installed on the reference printer. Existing release tags and assets retain their original bytes.

For the existing release's behavior and limitations, see [AutoRecovery](AUTORECOVERY.md), [troubleshooting](TROUBLESHOOTING.md) and [test scope](TESTING.md).
