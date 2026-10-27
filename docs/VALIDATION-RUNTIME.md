# Checking the candidate during real printing

The reference printer has loaded 4.2.1-rc1 successfully. The following print checks are still pending. Automated tests simulate motion, sensors and heating; they cannot establish physical reliability on the printer.

Keep the SFS location, PTFE path, wiring, thresholds and other software unchanged during this evaluation so the software correction can be assessed separately from hardware changes.

1. Run a normal file print in FULL mode and observe an A-to-B spool change.
2. If PD3_NO_MOTION is triggered while PD4 remains present, follow the complete sequence: one native pause, the full 300 mm commanded purge, genuine PD3 events accepted in the recovery generation, successful validation, a fresh generation prepared before one M24, actual printing resumed, and the first eligible new edge returning monitoring to NORMAL.
3. Check that a manual PARTIAL-to-FULL switch is not needed to restore monitoring.
4. Observe no unexplained recurrence for at least one hour after recovery, or until the file ends if sooner. Also observe a B-to-A change as part of the planned test sequence.

Retain the log from before the first fault through the resumed print. The generation messages are explained in [PD3 rearming](PD3-REARMING.md). A fault must be investigated, not automatically dismissed as false.

The issue remains open until these physical checks establish the outcome. The longer target before a future stable 4.2.1 is two prints lasting more than five hours, covering both A-to-B and B-to-A changes without repeated unexplained faults. No stable 4.2.1 release is claimed here.
