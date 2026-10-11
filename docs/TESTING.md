# Tests and scope

On 11 October 2026, the exact final preparation was retested offline: **231 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, using Python 3.14.7. Compilation and Python 3.7 syntax analysis passed. This is not an execution under Python 3.7 on the printer.

## Public suite

Use Python 3.10 or later for this public test environment (run here under 3.14.7). Do not install the test dependencies on the Giga.

```sh
python -m venv .venv
# Activate this environment using the command for your operating system.
python -m pip install -r tests/requirements.txt
python -B tests/run_tests.py
```

The public suite contains **223 tests**, all passing. Behavioral assertions are retained from the existing tests: acquisition, Motion, lifecycle, modes, pause, fan, thermal behavior, AutoRecovery, M24, cumulative transitions and wiping. Fixture paths were relocated; simulation configurations are excerpts without mesh or calibration data.

Eight tests that preserve complete private configurations and their hashes are not distributed. Their exact list is in `tests/EXCLUDED_MACHINE_PRESERVATION_TESTS.json`. They remain present and pass in the internal 231-test suite. No behavioral safety assertion was removed to obtain this result.

Historical Python sources in `tests/reference/` and `tests/fixtures/` are used only for non-regression comparisons and negative tests. Do not install them. Only `src/gapguard.py` is the production module. The fixture's G-code parser comes from the audited Klipper sources; movement, GPIOs, clocks, mutexes and heating are simulated. Deliberately injected errors can produce ERROR log entries while unittest still passes.

Historical 9/50/12/6 values in some tests verify parameterization; the explicit public profile remains 9/20/20/2. Historical test names do not change the current AutoRecovery criterion: cumulative transitions over 300 mm.

Earlier physical tests apply to their respective candidates. Even a complete offline suite does not guarantee detection or prove that every PD3 signal gap is resolved. No physical tests are performed during this GitHub publication or its documentation correction.

The live-source documentation review reruns the 223 public tests offline. The review archive is also tested after extraction. The production module, test code and hardware binaries remain unchanged. No watcher test result from an older preparation validates the live v1.2.2 watcher.
