# Recovered technical history

This is a documentary history; it does not fabricate earlier Git commits.

- The public watcher repository has 21 commits from 29 August to 3 September 2026. Its v1.0.0 release is standalone and uses INFINITY_EMERGENCY_PAUSE/RESUME. The last commit documents the general S1+ error that FlowQ does not expose.
- The archived watcher from 14 September adds `SOURCE=FLOWQ` to its pause call, which was still active at that stage. The local public bundle from 14 September contains a guide incorrectly labeled SFS V2.0 for this installation, DET0/PD4 and DET1/PD3 mapping, and the old native filament_motion_sensor. That configuration and its detection_length are historical, not the current GapGuard installation.
- An archive from 28 September preserves the actual information-only watcher: A/B alerts no longer trigger a pause. The personal ID is replaced with a placeholder in its public proposal.
- The 4.1 archives preserve the initial acquisition, transaction and lifecycle audits. Early candidates implemented a broader custom recovery procedure. Candidate.7 returned to SFS detection with native Elegoo macros.
- Later candidates added readable output, configurable thresholds, transition tracing and fan1 management for GapGuard pauses. Candidate.10 is the basis of the current branch.
- RC11/12/13 diagnostic approaches were investigated; they are not installation instructions for 4.2.
- Candidate.14 added a separate AutoRecovery component: 300 mm in 20 mm blocks after pausing. The window6 variant evaluated the last six blocks; 4.2.0-rc1 replaces that rule with the total across the complete purge.
- The final preparation from 9 October fixes genuine-transition processing, pause origin/idle_timeout, M24 confirmation and continuous wiping. The final module is identified by its exact hash, not only by the RC1 name shared with an earlier preparation.

Physical test chronology and raw PD3 electrical identification are not reconstructed from memory. The complete guide, five retained photographs, models and documented GPIO readings were recovered from the Library and archives.

Some older notes and early drafts incorrectly identified the sensor as V2.0. The hardware used from the beginning was V2.1, explicitly confirmed by the maintainer on 11 October 2026. External V2.0 references retain their version designation; no universal V2.0/V2.1 equivalence is inferred.

## Publication and live-source reconciliation

The initial public commit `cebb24461ab55b483ccc89782ec507693bc8ba1b` included French documentation. The documentation correction was prepared locally; this review does not claim that a corrected tag or asset has already been published. The original release ZIP remains identified by SHA-256 `760b92aa959508034b63bce3733561b2496c49130f163577a88d84c27f9796fd`.

The 11 October live audit confirmed the exact production module and six current public commands. The former specification names GAPGUARD_RESUME_FULL, GAPGUARD_RESUME_PARTIAL, GAPGUARD_RESUME_BYPASS and GAPGUARD_CANCEL are historical; they must not be added to reproduce this release. Manual resume and cancellation remain Elegoo commands.

The live configuration includes a newer private mesh without changing the functional GapGuard configuration. The live v1.2.2 watcher supersedes the older archived information-only implementation as the source for a future watcher release. The previously prepared watcher v2.0.0 package is obsolete; its proposed release number does not select the next public version.

## Stable promotion — 11 October 2026

The English RC1 documentation update was published at commit `6577cc63049afb8312d2c137acee1b3cde8a2219`. Its tag `v4.2.0-rc1` remains on that commit as a historical Pre-release. The earlier review statements above record the status at the time they were written.

The maintainer approved promotion to the first stable public release, v4.2.0, after documentation and packaging validation. There is no functional code change: the production module, configuration and native macro dependencies are byte-identical to RC1. The internal runtime string remains 4.2.0-rc1 deliberately for reproducibility.

The stable package carries forward the removal of the duplicate mount-detail view, the Why GapGuard exists context and the Development and AI assistance credit. It contains five hardware photographs and the original STL/3MF models. Existing reference-printer validation supports this promotion; no new physical test was performed. The cause of every historical PD3 signal gap remains unresolved. Neither the reference Giga nor the separate watcher is changed by this publication.

## PD3 rearming candidate — 27 October 2026

After repeated PD3 faults following AutoRecovery, the code review identified separate recovery motion counting and main-detector rearming without a shared generation contract. The 4.2.1-rc1 candidate brings these paths together and adds explicit generations. This is distinct from the unresolved physical origin of some initial signal gaps.

The approved candidate passed 258 automated tests and was installed as a module-only change. After the maintainer's physical power cycle, Klipper reached Ready and reported 4.2.1-rc1 with acquired inputs and no active fault. Print validation remains pending. The candidate is published as a new Pre-release for testing; no previous tag or asset is moved or replaced, and stable 4.2.0 remains Latest.
