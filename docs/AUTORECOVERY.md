# AutoRecovery 4.2.1-rc1

This recovery procedure is specific to the audited Elegoo integration. It is not a universal Klipper resume implementation. This candidate has passed automated tests and loading on the reference Giga; its recovery behavior still needs validation during real printing.

1. After PD3_NO_MOTION with PD4 present, the existing public Elegoo PAUSE runs exactly once. Its completion hook arms AutoRecovery.
2. Wait for physical completion of the pause. Rearm the main PD3 detector using the shared operation and a dedicated recovery generation, then wait 30 seconds. If the printer is no longer paused or PD4 is absent, automatic purging does not start.
3. Reheat only the hotend to `RESUME.etemp`, the target already saved. The target must be finite, positive and within the heater's configured limits. Readiness requires a finite measured temperature between target − 4 °C and target + 50 °C, inclusive, together with Klipper's `can_extrude` flag. Heating has a 600-second deadline. The heater target must still match the saved target; thermal readiness is checked again during the purge, settling, wiping and finalization stages.
4. Temporarily save the G-code state, select relative extrusion, and neutralize the M220/M221 multipliers for the purge.
5. Submit 15 blocks of `G1 E20 F200`. Before submitting the next block, wait for Klipper's motion-completion indication and check that its executed extruder-position history advanced by 20 mm. The allowed difference is 0.005 mm to accommodate microstep quantization. The main detector accepts genuine PD3 transitions from the current recovery generation during the physical block. The executed E history must show positive travel within that block, and a transition after its physical end cannot count. AutoRecovery uses this accepted evidence; UNKNOWN acquisition and stale events do not count. A successful sequence therefore accounts for 300 mm of extruder travel; it does not prove that 300 mm of filament actually passed through the nozzle. PD3 provides separate evidence of filament motion, not a calibrated measurement of delivered length.
6. At the end of the 15 blocks, sum the accepted transitions: at least two are required by the published profile. Also verify that the main detector is coherent, the recovery generation is still current, PD4 is present and no obsolete pause request or verification window remains. A block with zero transitions is not itself a failure if the complete total meets the threshold. Reaching two transitions early does not shorten the purge.
7. Wait for the existing two-second SETTLE delay, then submit the following wipe as one continuous script, with a single overall completion check.
8. Restore E, the PAUSE/RESUME flags, and the saved timelapse states B then A (MOVE_SPEED=250 then 50), prepare a fresh PD3 generation in ARMING at the current E position, and send a single M24. Passively observe `printing` plus active Virtual SD for the same file, session and prepared generation. The print lifecycle retains this generation instead of resetting it again. A busy mutex immediately after M24 is not an automatic failure; confirmation retains its ten-second deadline.

```gcode
G1 X-20 F15000
G1 X20
G1 X-20
G1 X20
G1 X-20
G1 X20
```

G91 has already been sent before this sequence. The last five commands inherit F15000. Klipper still controls physical reversals and acceleration; “continuous” means that AutoRecovery inserts no wait between the six submissions, not that speed stays constant through direction changes.

PD4 becoming absent aborts the attempt, including during the initial wait; restoring presence does not revive that failed attempt. After the wait, the operation also checks that the active fault remains PD3_NO_MOTION and the mode remains FULL. It checks saved macro variables, saved G-code states, parser/position state, native pause ownership and macro flags before continuing. Shutdown, native errors or unconfirmed heating/motion completion can also terminate the attempt. These are existing implementation checks, not new conditions introduced by this documentation correction.

Before M24, a busy G-code mutex is treated as an external command taking control and aborts recovery. After M24, the worker instead observes resume confirmation without acquiring that mutex. These two cases must not be confused.

Failure does not issue a substitute M24. Cleanup sets the hotend target to zero only while the operation remains valid, the file is paused and the failure has not been classified as external intervention. An external cancellation, resume or other takeover retains control of thermal and parser state. Recovery cannot retract moves that have already been submitted to Klipper.

AutoRecovery does not call RESUME or BASE_RESUME. The manual Elegoo purge, `G1 E100 F200`, is therefore not added: automatic purging totals 300 mm, not 400 mm. Manual resumes retain the native macro. There is no per-session attempt limit.

The rearming change does not reconfigure the buttons group, GPIOs or MCU. It does not change PD4 acquisition, the six public commands, native manual pause/resume/cancel, fan1 handling or bed targets. [PD3 rearming](PD3-REARMING.md) explains the implementation; [the test status](PD3-REARM-STATUS.md) separates verified results from pending print validation.
