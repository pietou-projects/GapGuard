# Optional Infinity Flow S1+ monitoring

GapGuard monitors the physical SFS inputs on the printer. The separate watcher monitors the S1+ through FlowQ REST/WebSocket and reads GapGuard status through Moonraker. **GapGuard does not depend on FlowQ, the watcher or ntfy for filament protection.**

The current reference watcher runs as v1.2.2 on the audited installation. It tracks A/B state, confirms unloaded/unloaded for ten seconds, writes a status file, sends notifications through an ntfy helper and polls GapGuard active_fault for PD3/PD4 notifications. Its console output is informational RESPOND only. It sends no pause, resume, cancel or mode-change command.

The [watcher repository](https://github.com/pietou-projects/infinity-flow-s1plus-klipper-watcher) still has a historical [v1.0.0 release](https://github.com/pietou-projects/infinity-flow-s1plus-klipper-watcher/releases/tag/v1.0.0) that used an automatic pause. Do not assume that historical release is the information-only integration described here. The live-derived public update needs removal of installation-specific constants and separate release validation before publication.

FlowQ state can be stale or incomplete. A general S1+ error with two red LEDs has not been reliably exposed by those interfaces. Remote status is not evidence that filament is physically moving. The watcher is optional telemetry and notifications; it does not make PD3/PD4 decisions.
