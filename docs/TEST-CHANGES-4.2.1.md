# Test changes for 4.2.1-rc1

The candidate retains the 223 public tests and adds 35 tests. No retained test was deleted or skipped. Some assertions and fixtures had to change because they described the old independent recovery counter or allowed pre-rearm evidence to enter a new monitoring period.

| Test or fixture | Change and reason |
|---|---|
| Recovery Rig initialization, tick and GPIO | Simulated events now use the adapter queue and main detector after physical block start. The 100-cycle test triggers faults through normal detection rather than directly injecting a pause request. |
| `test_23_only_real_edges_unknown_excluded` | UNKNOWN is set on the authoritative main detector, not a separate AutoRecovery baseline. Acquisition still cannot count as a transition. |
| `test_58_sfs_lifecycle_unchanged` | Retains Settings/Native and adapter lifecycle comparisons, with an exact method allowlist for the necessary PD3 recovery changes. Ordinary threshold/boundary tests remain. |
| `test_76_config_delta_only` | Keeps the historical configuration fixture intact instead of requiring a new module version string in it. This is a module-only upgrade. |
| `test_88_fan_restored_only_on_real_lifecycle` | Reconnects the real fan observer after the Rig change; restoration assertions are unchanged. |
| Old `test_89_epoch_is_diagnostic_only` | Replaced by rejection of old-session recovery evidence, with no M24. |
| Adapter and old-epoch queue fixtures | Supply the new generation field and edge-window adapter while retaining rejection without level/reference mutation. |
| Old queued-edge-survives-resume assertion | An old-generation event must not establish motion after rearming. The valid first-callback-on-resume case remains tested. |
| Version/default assertion | Expects 4.2.1-rc1 while checking unchanged fallback defaults. |
| Exact-scope assertions | First verify the historical diff against the exact 4.2.0 source, then enforce the candidate's changed/added method allowlist. |
| Old epoch/path-change-during-wait assertion | A changed session invalidates recovery; no command or M24 may follow. |
| Old ban on epoch/path comparisons | Keeps the bans on fan-state authorization and per-session quotas, while requiring the new explicit generation and same-file contract. |
| Purge/wipe/finalization identity checks | Preserve historical comparisons and add the strict current delta. The unchanged wipe branch and all distances, delays and commands remain checked. |
| Negative wipe mutation test | Replaces only the WIPE branch, so it still rejects six separate submissions without substituting the old PD3 architecture. |

`tests/scope421.py` lists the exact allowed method changes. Any additional method change fails that test. `tests/test_pd3_generation.py` covers stale events, shared rearming, physical block timing, detector consistency, one M24, manual resume after failure and 100 complete simulated recovery cycles in one session.

The eight private configuration-preservation tests excluded from the older public suite remain listed in `tests/EXCLUDED_MACHINE_PRESERVATION_TESTS.json`. That file records historical exclusions; the public 4.2.1-rc1 result is 258 tests, not a claim that a private 266-test suite was run.
