#!/usr/bin/env python3
"""Coordinator-only, CPU journal watcher; never signals/restarts a GPU process."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
from single_rank_slab_probe import atomic_json, digest, lane, require


def admission_refused(outcome, read_started):
    """Only an explicit pre-spawn terminal receipt can end monitoring early."""
    return (outcome.get('schema') == 'neural.download.flashnext-first-forward.v1'
            and outcome.get('stage') == 'admission_refused'
            and outcome.get('passed') is False
            and outcome.get('worker_started') is False
            and not any(key in outcome for key in ('worker_pid', 'worker_wait_status', 'worker_returncode'))
            and isinstance(outcome.get('admission_refused_unix'), (int, float))
            and read_started >= outcome['admission_refused_unix'])


def latch_stop(directory, reason):
    try:
        with (directory / 'STOP').open('x') as stream:
            stream.write(reason + '\n')
    except FileExistsError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-acceptance', type=Path)
    parser.add_argument('--health-receipt', type=Path, required=True)
    parser.add_argument('--receipt-dir', type=Path, required=True)
    args = parser.parse_args(argv)
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
                if admission_refused(outcome, read_started):
                    # The clean read above still applies all fault/acceptance
                    # rules. This is a failed probe, never a successful run.
                    latch_stop(args.receipt_dir, 'harness refused before device work')
                    atomic_json(args.receipt_dir / 'watcher.json', {
                        'passed': False, 'status': 'harness refused before device work',
                        'boot_id': boot, 'updated_unix': time.time(),
                        'read_started_unix': read_started, 'health_sha256': digest(health_bytes),
                        'journal_admission': audit, 'new_fault_lines': [],
                        'probe_exception': outcome.get('exception')})
                    return 2
                if ('worker_wait_status' in outcome
                        and read_started >= outcome['postflight_requested_unix']):
                    return
        except BaseException as exc:
            latch_stop(args.receipt_dir, f'{type(exc).__name__}: {exc}')
            atomic_json(args.receipt_dir / 'watcher.json', {'passed': False, 'boot_id': boot,
                        'updated_unix': time.time(), 'journal_admission': audit, 'exception': f'{type(exc).__name__}: {exc}'})
            raise
        time.sleep(.5)


if __name__ == '__main__':
    sys.exit(main())
