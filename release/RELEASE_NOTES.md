# GapGuard 4.2.1-rc1

**Pre-release for testing the PD3 monitoring handoff after AutoRecovery.** Automated tests and startup checks have passed. Validation during real printing is still pending.

## Why this candidate exists

The reference Giga sometimes reported repeated PD3 motion faults after an S1+ spool change and AutoRecovery. Returning manually from PARTIAL to FULL had restored monitoring. The code review found that recovery counted purge transitions separately from the main detector, so successful purge evidence was not tied to a consistently rearmed detector when printing resumed.

This candidate uses one shared rearming operation and explicit motion generations. The main detector must accept the purge evidence, and a fresh generation is prepared before the single M24 and retained when the file resumes. This addresses the software inconsistency; it does not establish the physical cause of every original PD3 signal gap.

## Validation so far

- 258 automated tests passed, including 100 simulated recovery cycles in one session.
- The exact module was installed on the reference OrangeStorm Giga and loaded after a physical power cycle on 27 October 2026.
- Klipper reached Ready and logged `GapGuard 4.2.1-rc1 ready`; sensor acquisition completed with no active fault.
- Recovery behavior and the absence of repeated faults during real printing remain to be verified. [Issue #1](https://github.com/pietou-projects/GapGuard/issues/1) stays open.

## What stays the same

The configured 9/20/20/2 thresholds, 30-second delay, 300 mm of commanded extruder travel in 15 × 20 mm blocks at F200, minimum two cumulative PD3 transitions, continuous F15000 wipe and one M24 are unchanged. Commanded travel is not proof of filament length delivered through the nozzle; accepted PD3 transitions provide separate motion evidence.

The six public GapGuard commands and native Elegoo PAUSE / RESUME / CANCEL_PRINT are preserved. A GapGuard pause sets the nozzle target to zero and keeps the four bed targets. Fan1 and PD4 behavior are retained. The FlowQ watcher remains a separate information-only project and is not included or changed by this release.

## Installation and rollback

For the matching 4.2.0 installation, this is a **module-only upgrade**. Keep your printer.cfg, mesh/SAVE_CONFIG, native macros, stock Klipper, Moonraker, watcher and firmware unchanged. Back up the current module, verify the new file, and use a physical OFF / approximately 30-second wait / ON cycle. Follow [Upgrading and rollback](../docs/UPGRADING-4.2.1.md). New users should read [INSTALLATION](../docs/INSTALLATION.md) and the native dependency requirements first.

The production module's SHA-256 is:

```text
bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a
```

This is exactly the module installed on the reference printer. Publishing it does not deploy anything to a printer.

## Scope and release continuity

Read [the status report](../docs/PD3-REARM-STATUS.md), [PD3 rearming](../docs/PD3-REARMING.md), [tests](../docs/TESTING.md) and [physical validation plan](../docs/VALIDATION-RUNTIME.md). The package contains the module, mergeable configuration, tests, English documentation and the unchanged five photographs, STL and 3MF. It excludes private configurations and raw machine logs.

Code remains GPL-3.0-or-later. Mount models remain CC0 1.0, with credit to T.L. The historical v4.2.0-rc1 Pre-release and stable v4.2.0 remain unchanged. **v4.2.0 remains Latest; v4.2.1-rc1 is not a stable 4.2.1 release.**
