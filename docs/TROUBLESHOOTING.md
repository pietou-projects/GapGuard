# Troubleshooting and limitations

## PD3 signal gaps

The cause of all historical PD3 signal gaps or losses has not been conclusively identified. Abnormal periods without a signal have been observed. The earlier 4.2.0 transition-processing correction is retained. The 4.2.1-rc1 candidate addresses the separate handoff between recovery motion evidence and the main detector after resuming; neither change establishes a single cause of all gaps or proves that every hardware incident is resolved.

Start with `GAPGUARD_STATUS`, then `GAPGUARD_STATUS_DEBUG` and the `[GAPGUARD_TRACE]` records covering the entire test window. Distinguish missing callbacks, repeated levels, genuine transitions, suspended monitoring, stale events and confirmed faults. A visible blue LED alone does not prove the level at the MCU. Do not immediately attribute the cause to the sensor, cable or Klipper.

## UNKNOWN at startup

The input has not yet been acquired. Do not treat it as LOW. Wait for the OID-dependent bound, then examine Ready/shutdown and acquisition. The old fixed 0.5-second delay is insufficient evidence.

## Missing macros or load errors

Each of the six public macros must appear exactly once and delegate to the Python backend. Historical GapGuard resume commands are not available in this build. The Elegoo macros and their saved states are prerequisites. Never add a `stats` attribute to the module: an earlier candidate collided with Klipper's automatic callback discovery.

## Heated beds turn off during a pause

Preserving bed targets depends on more than gapguard.py. Check the idle_timeout branch based on pause_origin. The Elegoo macro can set the timeout to 1800 s; without that branch, TURN_OFF_HEATERS also turned off the beds. Do not hide the problem by changing targets or reinstalling an old complete configuration.

## AutoRecovery failure

Read the exact phase and reason. Sending M24 alone does not establish success. A 300 mm purge that fails the transition criterion must not resume printing. Manual movement or external intervention can invalidate the operation. Do not remove physical guards merely to obtain a PASS.

## FlowQ and two red S1+ LEDs

A general S1+ error can leave an old FlowQ state that appears normal. The watcher cannot detect a fault not represented in the received data. REST/WS are undocumented interfaces, and freshness is not guaranteed. The information-only watcher is telemetry, not a replacement for PD3/PD4 filament protection.

## Repeated PD3 faults after AutoRecovery

See [issue #1](https://github.com/pietou-projects/GapGuard/issues/1) and the [current test status](PD3-REARM-STATUS.md). A normal startup is not proof that this print-time problem is fixed. Preserve the full sequence from the first fault through recovery and the next real motion transition. In 4.2.1-rc1 the generation and rearming log events help distinguish evidence from each stage; their meanings are documented in [PD3 rearming](PD3-REARMING.md).

Do not treat the next fault as automatically false or suppress a genuine feeding problem. If the candidate behaves incorrectly, stop the test and use [the module-only rollback procedure](UPGRADING-4.2.1.md#rolling-back). The physical source of an initial gap remains a separate question.
