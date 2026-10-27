# Upgrading from the matching 4.2.0 installation

**4.2.1-rc1 is a test candidate.** Automated tests and startup on the reference Giga have passed. Whether it eliminates recurring faults during printing remains to be established. New installations should use [INSTALLATION](INSTALLATION.md); this page covers an existing, matching 4.2.0 setup.

## Before changing a file

Finish or cancel the print normally. Confirm that there is no active print, no paused print and no file open in Virtual SD. Keep the current wiring, sensor position, configuration and software environment unchanged while evaluating the correction.

The expected 4.2.0 production module has SHA-256:

```text
cf239a52f65f345092946f2289a473c590244ced22c5f31c27e88e26b20473f1
```

If your module differs, identify that difference before replacing it. This guide does not assume every Giga has the same private printer.cfg or calibration.

## Replace only the module

1. Back up the existing `gapguard.py` in a new, timestamped location. Record its SHA-256, owner, group and permissions. Preserve previous backups.
2. Use `src/gapguard.py` from this release. Transfer it to a temporary file in the same directory as the installed module, preserve the existing ownership and permissions, and verify its SHA-256 before replacing the target by an atomic rename.
3. On the reference layout, the destination is `/home/mks/klipper/klippy/extras/gapguard.py`. The approved candidate hash is:

```text
bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a
```

4. Read the installed file back and verify that hash. Keep `printer.cfg`, its mesh/SAVE_CONFIG, native macros, stock Klipper files, Moonraker, the watcher and firmware unchanged. The candidate adds no configuration parameter; the public example's version comment is informational.
5. Stop after copying. Do not issue RESTART, FIRMWARE_RESTART or a service restart. Physically switch the printer off, wait about 30 seconds, and switch it on.

The reference installation retained UID/GID 1000:1000 and mode 0644. Preserve your existing valid metadata rather than assuming those numeric IDs apply to every machine.

## Check the new startup

Use the two read-only checks from [INSTALLATION](INSTALLATION.md):

```bash
sha256sum /home/mks/klipper/klippy/extras/gapguard.py
grep -a "GapGuard .* ready" /home/mks/klipper_logs/klippy.log | tail
```

Confirm the candidate hash and a `GapGuard 4.2.1-rc1 ready` line from the new startup. Klipper must be Ready with no loading exception. Check initial sensor acquisition and the idle state before starting a print. Old matching log lines alone are not evidence of the new startup.

Successful loading confirms installation, not the print-time fix. Follow the [physical validation plan](VALIDATION-RUNTIME.md) while observing the printer.

## Rolling back

If the candidate behaves incorrectly, stop the test and establish that the printer is idle before changing files. Restore the exact module you backed up, using a temporary file in the same directory and an atomic rename. Verify its SHA-256 and metadata. Do not restore another machine's configuration or an old mesh.

Use another physical OFF / approximately 30-second wait / ON cycle, then verify loading. The stable 4.2.0 module intentionally reports `4.2.0-rc1`; that historical runtime string does not indicate a different rollback module.
