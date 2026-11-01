# Experimental PD3 observer: pd3-observer-1-r2

This diagnostic variant investigates where PD3 events disappear before a motion fault. It does not attempt a functional fix. **It has not been installed or validated on the reference OrangeStorm Giga. Its real timing, memory and logging cost on that printer remain unmeasured.**

## Evidence behind the investigation

The read-only audit of the 1 November 2026 capture found that all nine completed AutoRecovery runs rearmed monitoring. PD3 transitions were already being processed before the later manual return to FULL. That capture contradicts the simple explanation that AutoRecovery merely leaves the detector disarmed. The cause of the missing intervals remains unknown. See [issue #1](https://github.com/pietou-projects/GapGuard/issues/1).

The observer records entry into `_gpio` before early returns, rejection conditions and compared values, enqueue/dequeue correlation, detector state and E references, and whether a recognized transition counts in VERIFY. It uses E positions already calculated by the normal path. The existing rearm and resume traces remain intact.

The intended distinction is between events delivered to GapGuard but rejected or not used, and intervals with no delivery to its callback. **No delivery to that callback does not prove a failure of the sensor, wiring or MCU.** Upstream filtering, transport and electrical evidence would still need investigation.

## What r2 changes

The previous offline reader could silently drop orphan batches or unreadable lines. Because dump numbers restart at 1, it could also join one instance's header to another instance's events and report a false complete capture.

Each observer instance now creates a UUID once. Headers and batches carry schema 2 and a capture ID consisting of that UUID and the dump number. The reader never matches solely on the dump counter. It reports orphan batches and unreadable diagnostic lines with their line numbers, validates offsets and final counts, and rejects inconsistent capture metadata. Legacy traces without capture identity cannot be certified complete. UUIDs distinguish independently generated instances; they are not authentication of deliberately forged logs.

## Files and review provenance

- Current diagnostic module: [src/gapguard.py](../src/gapguard.py).
- Offline reader: [tools/read_diagnostic.py](../tools/read_diagnostic.py).
- [Exact module diff from observer-1 to r2](diagnostics/pd3-observer-1-r2/review/observer-1-to-r2.module.diff).
- [Exact reader diff](diagnostics/pd3-observer-1-r2/review/observer-1-to-r2.reader.diff).
- [Detailed integrity review](diagnostics/pd3-observer-1-r2/review/READER-INTEGRITY.md).
- [311-test review evidence](diagnostics/pd3-observer-1-r2/review/results/suite.txt).
- [Simulated cross-instance collision example](diagnostics/pd3-observer-1-r2/review/results/integrity-examples/cross-instance-collision-SIMULATED.txt).

The `docs/diagnostics/pd3-observer-1-r2/review/` directory mirrors all 75 entries of the approved ZIP byte-for-byte, including its 74-file manifest. The original French engineering review is retained as reviewed evidence; this English guide explains its public use. The exact module, reader, tests and required baseline fixtures are also placed in the repository's normal working locations. The source-to-repository mapping is in [release/DIAGNOSTIC-PROVENANCE.json](../release/DIAGNOSTIC-PROVENANCE.json).

The release asset is the **original reviewed ZIP**, not a rebuilt archive of this branch. Repository-level notices and integration metadata are additional documentation; they do not change the ZIP, module or reader bytes.

```text
ZIP:    d7a6a388ee6bfc9863fff6bf365c4e451723f874bb75cfe2b5b0a5a5a8be6b5b
Module: 84b54310cc52a348131453ac8ad95db3bfe20dcd03d6cb639b65884e35e1eb61
Reader: 57df336bdf9fc9793cb787d03d6df4871760404f4ef9b79d70e2a4410b06a99c
```

## Offline verification and log reading

Use the offline environment described in [TESTING](TESTING.md); do not install these test dependencies on a printer.

```sh
python -B tests/run_tests.py
python -B tools/read_diagnostic.py path/to/copied-diagnostic.log
```

The reader exits with status 2 when it finds warnings, incomplete or unidentified diagnostic data; status 0 means no integrity warning was found. `COMPLETE=True` describes delivery of the identified bounded buffer, not complete electrical observation of PD3. The included example logs are simulated, not printer captures.

The reviewed 311 tests include 10,000 deterministic differential steps, complete simulated AutoRecovery sequences and the cross-instance reader regression. These are simulations, not a hardware reliability claim. The protected Settings, Native, Motion, Machine and AutoRecovery classes are unchanged. The r2 embedded delta from observer-1 is diagnostic identity metadata only. No extra E/native reads, G-code, rearming operation or timer was added.

## Limits and deployment status

Collection remains bounded to 128 event records, 32 checkpoints and two pending dumps, with at most four event records per monitor-tick output batch. Allocation, serialization, random-ID initialization and logging can perturb execution timing. PC measurements are not measurements on the Giga.

There is no deployment authorization or installation procedure in this publication. The review fixtures and full review directory are not printer configuration or deployment inputs. The six public commands, native Elegoo pause/resume/cancel behavior, configured thresholds and AutoRecovery policy are unchanged.

This remains an experimental pre-release on a dedicated branch, pending review. The PR must remain unmerged at this stage, and issue #1 remains open. The Giga and the separate FlowQ watcher are unchanged.
