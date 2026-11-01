# GapGuard pd3-observer-1-r2 — Experimental diagnostics

**Experimental Pre-release. Not installed or runtime-validated on the reference Giga. Not a functional fix for intermittent PD3 gaps.** This publication does not replace stable v4.2.0 or the existing v4.2.1-rc1 release, and is not Latest.

The observer follows incoming `_gpio` events, early rejections, the edge queue and detector effects through VERIFY counting, using E positions already calculated by the normal code. Existing rearm/resume traces are preserved. Revision r2 gives each capture an instance-specific identity and reports orphan or damaged diagnostic data instead of joining unrelated captures by a reused dump number.

The audited print showed that all nine completed AutoRecovery runs rearmed monitoring and that PD3 transitions were already present before the manual return to FULL. The cause of the missing intervals remains unknown. Absence of delivery to the callback alone does not prove a fault in the sensor, wiring or MCU.

## Validation and limits

- The reviewed package passed **311 offline simulation tests**, including the cross-instance reader regression and unchanged-decision comparisons.
- The protected detector/recovery classes remain unchanged. No additional E/native read, G-code, rearming operation or timer is introduced.
- This observer has not been installed or validated on the Giga. Its real overhead remains unmeasured; instrumentation itself may affect timing.
- Configuration, firmware, stock Klipper, the Giga and the separate watcher were not changed by publication.
- [Issue #1](https://github.com/pietou-projects/GapGuard/issues/1) stays open; no resolution is claimed.

## Exact reviewed asset

The attached `GapGuard-4.2.1-rc1-pd3-observer-1-r2-OFFLINE-REVIEW.zip` is uploaded without rebuilding. It contains the reviewed module, offline reader, tests, simulated evidence and review documentation. Its 74-file manifest remains intact. Baseline/configuration fixtures are test inputs, never installation instructions.

```text
d7a6a388ee6bfc9863fff6bf365c4e451723f874bb75cfe2b5b0a5a5a8be6b5b  GapGuard-4.2.1-rc1-pd3-observer-1-r2-OFFLINE-REVIEW.zip
84b54310cc52a348131453ac8ad95db3bfe20dcd03d6cb639b65884e35e1eb61  src/gapguard.py
57df336bdf9fc9793cb787d03d6df4871760404f4ef9b79d70e2a4410b06a99c  tools/read_diagnostic.py
```

Read the [diagnostic guide](../docs/PD3-OBSERVER-1-R2.md), [integrity review](../docs/diagnostics/pd3-observer-1-r2/review/READER-INTEGRITY.md) and [review test output](../docs/diagnostics/pd3-observer-1-r2/review/results/suite.txt). Code remains GPL-3.0-or-later; the existing hardware license and credits are unchanged.
