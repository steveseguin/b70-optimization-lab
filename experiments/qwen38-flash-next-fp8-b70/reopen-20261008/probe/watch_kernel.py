#!/usr/bin/env python3
"""Coordinator-only, CPU journal watcher; never signals/restarts a GPU process."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import time
from single_rank_slab_probe import atomic_json, digest, lane, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-acceptance', type=Path)
    parser.add_argument('--health-receipt', type=Path, required=True)
    parser.add_argument('--receipt-dir', type=Path, required=True)
    args = parser.parse_args()
    require(args.receipt_dir.is_dir(), 'create a fresh receipt directory first')
    require(not (args.receipt_dir / 'watcher.json').exists(), 'watcher receipt exists; no retry')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    screen = lane()
    deadline = time.monotonic() + 150
    while True:
        audit = screen.admission_audit()
        try:
            if args.owner_acceptance is not None:
                screen.verify_owner_acceptance(args.owner_acceptance, boot, dt.datetime.now(dt.timezone.utc), audit)
            health_bytes = args.health_receipt.read_bytes()
            receipt = json.loads(health_bytes)
            require(time.monotonic() < deadline, '150-second watcher bound exceeded')
            require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot, 'boot changed')
            read_started = time.time()
            result = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'short-iso-precise'],
                                    capture_output=True, text=True, check=True, timeout=3)
            require(result.stdout.strip() and not result.stderr.strip(), 'complete kernel journal required')
            log = args.receipt_dir / 'kernel-latest.log'
            log.write_text(result.stdout)
            screen.admit_journal(result.stdout, receipt, boot_id=boot,
                                 owner_acceptance=args.owner_acceptance, audit=audit)
            atomic_json(args.receipt_dir / 'watcher.json', {'passed': True, 'boot_id': boot,
                        'updated_unix': time.time(), 'read_started_unix': read_started,
                        'health_sha256': digest(health_bytes), 'new_fault_lines': [],
                        'journal_admission': audit})
            probe = args.receipt_dir / 'receipt.json'
            if probe.exists():
                outcome = json.loads(probe.read_text())
                if ('worker_wait_status' in outcome
                        and read_started >= outcome['postflight_requested_unix']):
                    return
        except BaseException as exc:
            (args.receipt_dir / 'STOP').write_text(f'{type(exc).__name__}: {exc}\n')
            atomic_json(args.receipt_dir / 'watcher.json', {'passed': False, 'boot_id': boot,
                        'updated_unix': time.time(), 'journal_admission': audit, 'exception': f'{type(exc).__name__}: {exc}'})
            raise
        time.sleep(.5)


if __name__ == '__main__':
    main()
