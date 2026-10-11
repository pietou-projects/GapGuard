# Architecture

`Settings` validates parameters. `Motion` tracks acquisition, the E reference, SUSPECT/VERIFY and transitions. `Machine` manages modes, lifecycle, faults and pause requests. `GapGuard` connects these objects to the Reactor, buttons and native commands. `AutoRecovery` is a separate component that runs after the pause.

## Input acquisition

PD3 and PD4 belong to the same buttons group in this build, without pulse_counter interception or diagnostic reissuance of buttons_add. PD3 detects motion; PD4 detects presence. UNKNOWN means that an input has not yet been acquired; it is not LOW. The module accepts a real group snapshot, including one received before klippy:ready. If no snapshot arrives, it adopts the non-inverted LOW/LOW baseline after ready + 1.5 s + 0.01×OID + init_guard. The OID is the actual MCU_buttons object ID, and init_guard must be at least 0.250 s. Initial acquisition never counts as a transition.

Genuine HIGH↔LOW transitions reach Motion with the position returned by `find_past_position()` at the signal timestamp. This RC removes an internal rejection that could exclude these transitions during an actual printing cycle. Protection against stale events remains separate from this processing. Repeated levels are not transitions.

## Distance-based motion detection

With the 9/20/20/2 profile, a lack of transitions enters SUSPECT at 9 mm. VERIFY opens at reference+20 and ends at reference+40, without a sliding window. Two transitions qualify the window. A transition exactly at the entry boundary can rebase the reference and return to NORMAL, even if a timer has just opened VERIFY but no transitions have yet been counted. The end boundary is inclusive: a qualifying transition already received or queued can still cancel an unissued fault pause before the worker dispatches PAUSE. Scheduling can delay observation until beyond the boundary; this is not an instantaneous physical pause at exactly 40.000 mm. The historical internal state name `VERIFY_50` does not override the configured 20 mm trigger.

## Print lifecycle and modes

Normal monitoring requires `print_stats.state == "printing"`, active Virtual SD and a non-empty file path for the current session. A pause suspends monitoring; sending RESUME alone does not rearm it. On an actual return to active printing, FULL mode establishes a new E reference and enters ARMING. A transition received before the VERIFY trigger rebases to NORMAL; if the trigger has already been reached, the configured VERIFY rules still apply. `active_fault` is cleared on resume, while `last_fault` remains diagnostic. Completion, cancellation, error or a changed file path resets the session.

PARTIAL/FULL rebase the monitoring logic; they do not reconfigure GPIOs or the MCU. BYPASS disables protection. FlowQ is not an input to the detector. 

The mutex protects short command submissions. The recovery worker proceeds in stages and observes physical completion. After M24, passive confirmation must not depend on immediate mutex availability.
