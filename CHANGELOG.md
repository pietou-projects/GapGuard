# Changelog

## 4.2.1-rc1 — PD3 rearming candidate — 27 October 2026

This Pre-release is available for testing. Automated tests and loading on the reference Giga have passed; validation during real printing is still pending. The stable 4.2.0 release and all previous tags/assets are preserved.

- Use one shared PD3 rearming operation for a manual return to FULL and AutoRecovery.
- Give queued motion events an explicit generation so stale events cannot become new evidence.
- Require the main detector to accept recovery transitions and pass a consistency check before resuming.
- Prepare a fresh motion generation before M24 and retain it when the file actually resumes.
- Add generation-specific diagnostic log messages and 35 tests, including 100 complete simulated recovery cycles.
- Preserve the configured 9/20/20/2 profile, 300 mm in 15 × 20 mm at F200, minimum two cumulative transitions, 30-second wait, continuous F15000 wipe and one M24.
- Preserve native manual controls, fan1, four-bed target handling, PD4 and the information-only watcher boundary. No new configuration parameter is required.

See [issue #1](https://github.com/pietou-projects/GapGuard/issues/1), [test status](docs/PD3-REARM-STATUS.md) and [upgrading](docs/UPGRADING-4.2.1.md).

## 4.2.0 — First stable public release — 11 October 2026

- Promoted RC1 to stable after documentation and package validation, using the maintainer's existing runtime validation on the reference printer.
- No functional change to gapguard.py, configuration, thresholds, native macros or AutoRecovery. The module is byte-identical to RC1 and intentionally retains its internal 4.2.0-rc1 version string.
- Carries forward the removal of the duplicate mount-detail view, the Why GapGuard exists context and the Development and AI assistance credit.
- Packages the final stable documentation with five photographs, one STL and one 3MF. The seven hardware assets retain their original bytes.
- Preserves the unresolved historical PD3 root-cause limitation. Automated tests do not replace physical validation; no new physical test was run for this promotion.
- The historical v4.2.0-rc1 tag and Pre-release remain unchanged.

The entries below describe their historical release state.

## 4.2.0-rc1 — Release Candidate

The final preparation was archived on 9 October 2026. This release has not been promoted to stable.

### Fixed

- Genuine received PD3 transitions could be excluded from Motion by internal logic during an actual printing cycle.
- GapGuard pause origin and preservation of all four heated-bed targets, including after idle_timeout expires, without changing manual Elegoo pauses.
- False AutoRecovery failure after M24 when the mutex is busy: resume confirmation now observes the actual state passively.
- Wiping: six moves are submitted as one continuous sequence, without a worker step between individual moves.

### Changed

- AutoRecovery validation uses transitions accumulated over the entire 300 mm purge; the sliding window6 criterion has been removed.
- The minimum transition count is configurable, with two used in the reference configuration.
- Version identification and readable output identify 4.2.0-rc1.

### Known limitations

- The root cause of every historical PD3 signal loss has not been conclusively established. The transition fix does not prove a single cause.
- This is a release candidate, not a stable release; compatibility has primarily been investigated on the Elegoo reference setup.
- Automated tests use simulations and are distinct from physical tests.
- The guide, five retained photographs and STL/3MF models were recovered from the Library. The maintainer confirms that the installation has used an SFS V2.1 since testing began; earlier V2.0 labels for this installation have been corrected.

### Documentation reconciliation

English user documentation and a two-level configuration reference are prepared from the validated live implementation. No production code, runtime string, test, hardware binary or native macro behavior changes. These documentation files do not claim that any tag or release asset has been replaced.
