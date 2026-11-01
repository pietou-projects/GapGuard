"""Offline construction from the exact captured module; never opens a network."""
from pathlib import Path
import hashlib
import difflib

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'baseline/gapguard.py').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a'
source = raw.decode('utf-8')
newline = '\r\n' if '\r\n' in source else '\n'
source = source.replace('\r\n', '\n')

def replace(old, new):
    global source
    assert source.count(old) == 1, (source.count(old), old)
    source = source.replace(old, new)

observer = (ROOT / 'tools/observer_block.py').read_text(encoding='utf-8')
replace('import math\n', 'import math\nimport uuid\n')
replace('class GapGuard:', observer.rstrip() + '\n\n\nclass GapGuard:')
replace('    def _commands(self):', '''    def _pd3_diag(self, method, *args):
        # Observation failure must never suppress or manufacture a real event.
        try:
            observer = getattr(self, '_pd3_observer', None)
            if observer is None:
                if method == 'flush':
                    return
                observer = self._pd3_observer = PD3Observer(self)
            return getattr(observer, method)(*args)
        except Exception:
            self._pd3_diag_errors = getattr(self, '_pd3_diag_errors', 0) + 1
            return None

    def _commands(self):''')
replace('                    self.machine.motion.acquire(mask)\n',
        "                    self._pd3_diag('bootstrap', epoch, generation, when, mask, pos)\n                    self.machine.motion.acquire(mask)\n")
replace('            epoch, generation, when, mask, pos = self._edges.popleft()',
        "            queued = self._edges.popleft()\n            epoch, generation, when, mask, pos = queued\n            self._pd3_diag('dequeue', queued)")
replace('            # An old epoch must not change',
        "            else:\n                self._pd3_diag('queue_reject')\n            # An old epoch must not change")
replace('        return eventtime + self.s.check_interval',
        "        self._pd3_diag('flush')\n        return eventtime + self.s.check_interval")
replace('        self.machine.observe(when, native, position, evaluate=evaluate)',
        "        self.machine.observe(when, native, position, evaluate=evaluate)\n        self._pd3_diag('observation', when, native, position, evaluate)")
replace('                       generation=None, epoch=None):\n        before',
        "                       generation=None, epoch=None):\n        diagnostic_event = self._pd3_diag('processing', when, mask, position, acquire_only, epoch, generation)\n        before")
replace('            self.machine.initialized = True\n        else:',
        "            self.machine.initialized = True\n            self._pd3_diag('effect', diagnostic_event, False, False)\n        else:")
replace('                                         epoch=epoch, recovery=recovery)\n            try:',
        "                                         epoch=epoch, recovery=recovery)\n            self._pd3_diag('effect', diagnostic_event, accepted, recovery)\n            try:")
replace("                logging.exception('GapGuard AutoRecovery GPIO observer ignored')\n        if before is None:",
        "                logging.exception('GapGuard AutoRecovery GPIO observer ignored')\n        self._pd3_diag('after_observers', diagnostic_event)\n        if before is None:")
replace('    def _trace_pd3_fault(self):\n', "    def _trace_pd3_fault(self):\n        self._pd3_diag('fault')\n")
replace('        self.machine.reset(self.now(), shutdown=True)\n        self._edges.clear()',
        "        self.machine.reset(self.now(), shutdown=True)\n        self._pd3_diag('clear', 'shutdown_queue_clear')\n        self._edges.clear()")
replace('        self.machine.reset(self.now(), pending_new=True)\n        self._edges.clear()',
        "        self.machine.reset(self.now(), pending_new=True)\n        self._pd3_diag('clear', 'reset_file_queue_clear')\n        self._edges.clear()")
replace('    def _gpio(self, eventtime, mask):\n        if self._dead:\n            return',
        "    def _gpio(self, eventtime, mask):\n        diagnostic_event = self._pd3_diag('entry', eventtime, mask)\n        if self._dead:\n            self._pd3_diag('reject', diagnostic_event, 'dead')\n            return")
replace('            self._boot_snapshot = mask\n            return',
        "            self._boot_snapshot = mask\n            self._pd3_diag('reject', diagnostic_event, 'not_ready_boot_snapshot_saved')\n            return")
replace('        if eventtime < max(self.machine.min_eventtime, self.machine.generation_time):\n            return',
        "        if eventtime < max(self.machine.min_eventtime, self.machine.generation_time):\n            self._pd3_diag('reject', diagnostic_event, 'eventtime_below_floor')\n            return")
replace('                            eventtime, mask, self.position(eventtime)))\n        self._drain_edges()',
        "                            eventtime, mask, self.position(eventtime)))\n        self._pd3_diag('enqueue', diagnostic_event, self._edges[-1])\n        self._drain_edges()")
# The captured module has mixed historical line endings. Preserve every
# unchanged original line byte-for-byte, including its individual newline.
old_lines = raw.decode('utf-8').splitlines(True)
new_lines = source.splitlines(True)
matcher = difflib.SequenceMatcher(a=[s.rstrip('\r\n') for s in old_lines],
                                 b=[s.rstrip('\r\n') for s in new_lines], autojunk=False)
out = []
for kind, a, b, c, d in matcher.get_opcodes():
    if kind == 'equal':
        out.extend(old_lines[a:b])
    else:
        out.extend(s.rstrip('\r\n') + newline for s in new_lines[c:d])
result = ''.join(out).encode('utf-8')
(ROOT / 'src/gapguard.py').write_bytes(result)
(ROOT / 'gapguard-live-to-observer.diff').write_text(''.join(difflib.unified_diff(
    raw.decode().splitlines(True), result.decode().splitlines(True),
    fromfile='baseline/gapguard.py', tofile='src/gapguard.py')), encoding='utf-8', newline='')
print('diagnostic SHA256', hashlib.sha256(result).hexdigest())
