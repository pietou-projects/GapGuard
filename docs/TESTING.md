# Tests and validation scope

The 4.2.1-rc1 public package contains **258 tests**: the 223 retained public tests plus 35 new tests for shared PD3 rearming, event generations and the recovery-to-printing transition. The [test changes](TEST-CHANGES-4.2.1.md) explain the adapted assertions individually.

## Run the offline suite

Use Python 3.10 or later for this test environment. Do not install test dependencies on the printer.

```sh
python -m venv .venv
# Activate the environment using the command for your operating system.
python -m pip install -r tests/requirements.txt
python -B tests/run_tests.py
```

The published [test results](../tests/results/4.2.1-rc1/test-results.txt), [100-cycle evidence](../tests/results/4.2.1-rc1/100_cycles.json) and [rearming equivalence comparison](../tests/results/4.2.1-rc1/equivalence.json) are automated evidence. The public package is also tested after ZIP extraction; its publication receipt records that separate check.

The 100-cycle test uses one simulated print session. Each cycle reaches a PD3 fault through normal detection, pauses, processes purge edges through the main detector, commands all 15 blocks, validates recovery, sends one M24, confirms actual simulated printing and accepts a new edge into NORMAL. It checks that references, counts, pause requests and old-generation events do not leak into the next cycle.

Movement, GPIOs, clocks, mutexes and heating are simulated. Expected error-injection cases may write ERROR messages while the test passes. Historical source/configuration fixtures are only test inputs and must never be installed. Only `src/gapguard.py` is the production module.

The historical private-configuration exclusions are listed in `tests/EXCLUDED_MACHINE_PRESERVATION_TESTS.json`. No complete private printer.cfg, mesh, credentials or printer log is distributed. Historical 9/50/12/6 tests check parameterization; the explicit public profile remains 9/20/20/2.

## What has been checked on the printer

On 27 October 2026, the exact candidate was installed and then loaded after a physical power cycle. Klipper reached Ready, logged `GapGuard 4.2.1-rc1 ready`, and reported completed PD3/PD4 acquisition with no active print or fault. Syntax also passed under the printer's Python 3.7.3. These are loading checks, not print-time validation of the correction.

See [current status](PD3-REARM-STATUS.md) and [the physical validation plan](VALIDATION-RUNTIME.md). No claim is made that repeated faults have already been eliminated or that every initial PD3 gap has a known cause.
