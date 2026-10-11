# Troubleshooting and limitations

## PD3 signal gaps

The cause of all historical PD3 signal gaps or losses has not been conclusively identified. Abnormal periods without a signal have been observed. This RC fixes an internal path that could exclude genuinely received transitions; it does not establish a single cause or demonstrate that every hardware incident is resolved.

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
