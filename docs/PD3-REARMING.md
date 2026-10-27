# How PD3 monitoring is rearmed

Rearming means giving motion monitoring a fresh starting point. It does not reset the SFS electronics or change the GPIO configuration. In 4.2.1-rc1, a manual return to FULL and AutoRecovery use the same `Machine.rearm_pd3()` operation.

## One starting point for both paths

The shared operation clears the old motion reference, verification interval, transition count and pause-request state. It obtains a fresh E position from Klipper's position history and puts the detector in ARMING. Known PD3/PD4 electrical levels remain known; keeping a level does not create a transition. `last_fault` remains diagnostic.

The current recovery's `PD3_NO_MOTION` active fault remains available to its existing checks while the file is paused. It is cleared when real printing resumes, rather than being treated as a new pause request.

## Keeping old events out of a new monitoring period

Each period has a generation number and a starting timestamp. A queued event carries the file-session epoch, motion generation, event timestamp, pin snapshot and observed E position. Before it can alter a level or reference, the event must belong to the current session and generation and be new enough for that generation. A delayed callback whose timestamp predates rearming is also rejected.

This separates three kinds of evidence: before the pause, during the recovery purge, and after resuming. Initial UNKNOWN-to-known acquisition still does not count as motion.

## The main detector sees the purge

After physical pause completion, the shared operation creates a recovery generation. The public mode remains FULL; no mode-change G-code is sent. The existing 30-second wait and heating sequence follow.

The processing path is `GapGuard._gpio → queued events → Machine.gpio → Motion.edge`. During a purge block, a genuine HIGH↔LOW transition can count only in the current recovery generation and physical block interval. E history must show positive advance from the block start, within the expected 20 mm with the existing 0.005 mm tolerance. An event beyond the known physical end, between blocks, from an earlier generation, caused only by PD4 or merely acquiring an UNKNOWN level does not count.

The main detector increments its accepted-edge count. AutoRecovery records changes in that count; its own descriptive counters cannot substitute for accepted evidence. The ordinary print-verification window is suspended during the purge. Recovery still requires two accepted transitions cumulatively over all 300 mm, and all 15 blocks run even if two transitions arrive early.

## Preparing the return to printing

Successful purge validation requires a current generation, the transition minimum, PD4 present and a coherent main detector in NORMAL with finite references and no leftover pause request or VERIFY window. After the existing wipe and state restoration, the shared operation creates a fresh resume generation in ARMING before the single M24.

The worker then observes the same file and session returning to active printing in that generation. The lifecycle keeps the prepared generation instead of arming again. The first eligible post-resume edge establishes NORMAL. An ordinary manual resume without a valid prepared generation still uses the normal rearming path.

## Failure and interruption

A failed or invalidated recovery retires only the generation it still owns. A failed M24 cannot leave a prepared generation for a later manual RESUME to reuse. An operation from an old session cannot rearm a new file. Cleanup respects external cancel/resume ownership; it does not overwrite another operation's heater or parser state. See [AutoRecovery](AUTORECOVERY.md) for the existing thermal and command checks.

## Log messages

| Message | Meaning |
|---|---|
| `PD3_REARM_BEGIN` | A fresh monitoring generation and E reference were created |
| `PD3_RECOVERY_EDGE` | The main detector accepted a recovery motion transition |
| `PD3_RECOVERY_VALIDATED` | Recovery motion evidence and detector consistency passed |
| `PD3_RESUME_GENERATION` | A fresh generation was prepared before M24 |
| `PD3_RESUME_ACTIVE` | The file returned to active printing with that generation |
| `PD3_FIRST_POST_RESUME_EDGE` | The first eligible motion edge after resuming was accepted |

These logs expose state changes; they are not a calibrated filament-length measurement or proof that every original PD3 gap has been explained. [Test scope](TESTING.md) and [current print-validation status](PD3-REARM-STATUS.md) describe the evidence available so far.
