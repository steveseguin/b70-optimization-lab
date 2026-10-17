"""Single recorded incident admission, never a configurable fault waiver."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'driver'))
import window_driver as w

RESOLUTION = HERE / 'resolved-fault.json'

def journal():
    # The preserved kernel-window.log uses this exact journal representation.
    result = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'short-iso'],
                            capture_output=True, text=True, check=True, timeout=3,
                            env={**os.environ, 'TZ': 'America/Toronto'})
    w.require(result.stdout.strip() and not result.stderr.strip(), 'complete kernel journal unavailable')
    return result.stdout

def line_sha(lines):
    return hashlib.sha256(('\n'.join(lines) + '\n').encode()).hexdigest()

def validate_resolution(owner, health, boot, kernel_log):
    lines = w.fault_lines(kernel_log)
    resolution = owner.get('resolved_fault')
    if resolution is None:
        w.require(not lines and health.get('fault_lines_earlier_this_boot') == 0, 'fault-bearing boot refused')
        return None
    expected = w.read(RESOLUTION)
    w.require(type(resolution) is dict and resolution == expected, 'only the sealed single resolution is allowed')
    w.require(boot == resolution['boot_id'] == health.get('boot_id'), 'resolved fault wrong boot')
    recorded = [row['text'] for row in resolution['fault_lines']]
    w.require(len(recorded) == resolution['count'] == 2 and len(set(recorded)) == 2, 'single two-line incident required')
    w.require(all(hashlib.sha256(row['text'].encode()).hexdigest() == row['sha256']
                  for row in resolution['fault_lines']), 'fault line hash')
    w.require(line_sha(recorded) == resolution['fault_lines_sha256'], 'fault set hash')
    w.require(Counter(lines) == Counter(recorded), 'boot faults differ from exact resolved set; additional or missing fault')
    evidence = w.REPO / resolution['kernel_window_path']
    w.require(w.sha(evidence) == resolution['kernel_window_sha256'], 'fault evidence hash')
    w.require(w.fault_lines(evidence.read_text()) == recorded, 'fault evidence lines')
    probe_path = w.REPO / resolution['probe_receipt_path']
    w.require(probe_path.is_file(), 'resolved probe missing')
    w.require(w.sha(probe_path) == resolution['probe_receipt_sha256'], 'resolved probe hash')
    probe = w.read(probe_path)
    # Immutable driver checks all four cards, kernel, passed, no during-probe lines.
    # The old probe is historical evidence; freshness applies separately to launch health.
    w.verify_health(dict(probe, fault_lines_earlier_this_boot=0), boot, w.timestamp(probe['end_utc']))
    w.require(probe['fault_lines_earlier_this_boot'] == 2, 'probe prior count differs')
    w.require(probe['end_utc'] == resolution['probe_end_utc']
              and probe['start_utc'] == resolution['probe_start_utc'], 'probe time binding')
    start, end = w.timestamp(probe['start_utc']), w.timestamp(probe['end_utc'])
    w.require(all(datetime.fromisoformat(line.split()[0]).timestamp() < start for line in recorded),
              'fault does not precede probe start')
    w.require(health.get('fault_lines_earlier_this_boot') == 2
              and health.get('journal_fault_lines_during_probe') == []
              and health.get('passed') is True, 'launch health does not match resolved set')
    w.require(w.timestamp(health['start_utc']) >= start and w.timestamp(health['end_utc']) >= end,
              'launch health precedes resolution')
    return resolution

class ResolvedWatch(w.Watch):
    """Exclude exactly the approved historical multiset; every new occurrence trips."""
    def __init__(self, root, baseline, boot, owner, health):
        validate_resolution(owner, health, boot, baseline)
        super().__init__(root, baseline, boot)

    def poll(self):
        w.require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot, 'boot changed')
        log = journal()
        (self.root / 'kernel-latest.log').write_text(log)
        current = Counter(w.fault_lines(log))
        new = list((current - self.baseline).elements())
        if new:
            w.write(self.root / 'FAULT.json', {'boot_id': self.boot, 'lines': new, 'unix': time.time()})
        w.require(not new, 'new kernel fault; second incident on resolved boot; no retry; owner reboot needed')
        w.require(current == self.baseline, 'kernel fault history missing or changed')
        w.require(not any((p / 'FAULT.json').exists() for p in w.FAULT_ROOTS), 'external FAULT.json')
        w.write(self.root / 'watcher.json', {'passed': True, 'updated_unix': time.time(),
                'boot_id': self.boot, 'excluded_fault_lines': sum(self.baseline.values())})
