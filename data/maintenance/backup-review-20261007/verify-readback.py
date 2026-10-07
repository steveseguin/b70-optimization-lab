"""Monitor the read-only verification worker; stop on faults without retries."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import re
import signal
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
cursor = (OUT/'kernel-start-cursor.txt').read_text().strip().split('-- cursor: ')[1]
fault = re.compile(r'I/O error|uas_eh|USB disconnect|reset .*USB|ntfs.*error|Fault response|GPU HANG|timed.out job', re.I)


def guard():
    mount = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-o', 'SOURCE,FSTYPE,OPTIONS', '/mnt/usb-models'],
        text=True, timeout=10))['filesystems'][0]
    assert mount['source'] == '/dev/sda2' and mount['fstype'] == 'fuseblk'
    assert 'ro' in mount['options'].split(',')
    assert Path('/dev/disk/by-uuid/4E0E66ED0E66CD91').resolve() == Path('/dev/sda2')
    stats = os.statvfs('/tmp')
    assert stats.f_bavail*stats.f_frsize >= 50*1024**3, 'Internal reserve crossed'
    log = subprocess.check_output(['journalctl', '-k', '-b', '--after-cursor', cursor, '--no-pager'],
                                  text=True, timeout=10)
    (OUT/'kernel-during-readback.txt').write_text(log)
    assert not fault.search(log), 'New kernel fault; stop backup reads'


guard()
started = time.monotonic()
with (OUT/'readback.log').open('xb') as output:
    process = subprocess.Popen([sys.executable, '-B', str(OUT/'readback-worker.py')],
                               stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        while process.poll() is None:
            time.sleep(3)
            guard()
            assert time.monotonic()-started < 1800, '30-minute verification bound exceeded'
        assert process.returncode == 0, f'Readback worker failed: {process.returncode}'
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
        raise
guard()
receipt_path = OUT/'verification.json'
receipt = json.loads(receipt_path.read_text())
assert receipt['status'] == 'content-and-restore-checks-passed-awaiting-postflight'
receipt.update(status='full-readback-and-selected-restore-passed',
               kernel_postflight_passed=True, readonly_mount_postflight_passed=True,
               verified_at_utc=datetime.now(timezone.utc).isoformat())
with receipt_path.open('w') as output:
    json.dump(receipt, output, indent=2)
    output.write('\n')
    output.flush()
    os.fsync(output.fileno())
print('Readback worker passed; no new kernel storage/GPU faults.')
