"""Small seal-time integration surface for packet61-style future windows."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import time

from chain_devices import (DeviceMonitor, admit_clients, foreign_clients,
                           process_identity, require, topology_admit)
from lane_admission import DEFAULT_ROOT, Reservation, atomic_json, window_scope
from drain_gate import DrainPermit, DEFAULT_DRAIN_ROOT


class WindowAdmission:
    def __init__(self, window, evidence, *, root=DEFAULT_ROOT, check=lambda: None,
                 proc=Path('/proc'), now=time.monotonic, topology=topology_admit,
                 drain_root=DEFAULT_DRAIN_ROOT):
        self.window, self.evidence, self.proc, self.now = window, Path(evidence), proc, now
        self.scope = window_scope(window)
        self.monitor = DeviceMonitor('A', proc, now)
        self.lease = Reservation('A', window=window, root=root, check=check)
        self.drain = DrainPermit(self.evidence, root=drain_root, check=check,
                                 reservation=self.lease.record)
        self.topology, self.last_scan, self.signature = topology, None, None
        self.record = dict(schema='own-runtime.chain-admission.v1', window=window,
                           scope=self.scope, timing_claim_eligible=self.scope == 'whole-host',
                           passed=False, owners={})

    def persist(self):
        self.record['owners'] = self.monitor.owners
        self.record['ready_checks'] = self.monitor.ready_checks
        signature = repr(self.record)
        if signature != self.signature:
            atomic_json(self.evidence, self.record)
            self.signature = signature

    def __enter__(self):
        self.lease.__enter__()
        try:
            self.record['coordination'] = self.lease.record
            self.record['topology'] = self.topology('A')
            self.record['clients'] = foreign_clients(self.scope, self.proc)
            self.persist()
            require(not self.record['clients']['blocked'], 'foreign Xe clients at admission')
            self.drain.__enter__()
            self.record['shared_drain'] = self.drain.record
            # A foreign client could appear while waiting for the drain gate.
            self.record['clients'] = foreign_clients(self.scope, self.proc)
            self.persist()
            require(not self.record['clients']['blocked'], 'foreign Xe clients after drain wait')
            return self
        except BaseException:
            self.drain.__exit__(None, None, None)
            self.lease.__exit__(None, None, None)  # markers deliberately retained
            raise

    def register(self, pid):
        try:
            self.monitor.register(pid)
        finally:
            self.persist()

    def ready(self, pids):
        try:
            self.monitor.ready(pids)
        finally:
            self.persist()

    def check(self):
        try:
            self.monitor.poll()
            # Detect an uncooperative client even after the initial check.
            # This is passive supervision; a failure uses the packet's own
            # cooperative stop path and invalidates the timing attempt.
            now = self.now()
            if self.last_scan is None or now - self.last_scan >= 1:
                self.last_scan = now
                self.record['clients_latest'] = foreign_clients(
                    self.scope, self.proc, self.monitor.live_identities())
                require(not self.record['clients_latest']['blocked'], 'foreign Xe client during window')
        finally:
            self.persist()

    def complete(self):
        try:
            self.monitor.finish()
            require(not self.window.startswith('W') or self.monitor.ready_checks > 0,
                    'model window lacks the before-request READY proof')
            self.record['clients_after_drain'] = admit_clients(self.scope, self.proc)
            self.drain.complete()
            self.lease.complete(drained=True)
            self.record['passed'] = True
        finally:
            self.persist()

    def __exit__(self, kind, value, trace):
        self.drain.__exit__(kind, value, trace)
        self.lease.__exit__(kind, value, trace)


def bind_receipt(path, admission):
    """Only a completed, drained admission can make the original receipt pass."""
    row = json.loads(path.read_text())
    require(row.get('passed') is True and row.get('window') == admission.window,
            'original window did not pass')
    try:
        require(set(row.get('launched_pids', [])) == set(admission.monitor.owners),
                'window launched owners differ from admission')
        admission.record['window_output'] = str(path.parent.resolve())
        admission.record['window_receipt_sha256_without_admission'] = receipt_digest(row)
        admission.complete()
        row['lane_admission'] = dict(passed=True, path=str(admission.evidence.resolve()),
                                    sha256=hashlib.sha256(admission.evidence.read_bytes()).hexdigest(),
                                    scope=admission.scope)
    except BaseException as error:
        row.update(passed=False, lane_admission_error=str(error))
        raise
    finally:
        atomic_json(path, row)


def receipt_digest(row):
    # Bind all original identity, quality and owner fields without a hash cycle.
    unsigned = {key: value for key, value in row.items() if key != 'lane_admission'}
    return hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def verify_receipt(row, *, data=None):
    """Use in BOTH prerequisite and queue-success gates of the adopting packet."""
    bound = row.get('lane_admission', {})
    require(bound.get('passed') is True, 'missing completed lane admission')
    # Portable submission replay supplies the exact collected bytes; live
    # prerequisite and queue checks read the hash-bound sidecar path.
    data = Path(bound['path']).read_bytes() if data is None else data
    require(hashlib.sha256(data).hexdigest() == bound['sha256'], 'lane admission evidence changed')
    proof = json.loads(data)
    require(proof.get('window_receipt_sha256_without_admission') == receipt_digest(row),
            'lane admission belongs to a different window receipt')
    scope = window_scope(row['window'])
    require(proof.get('schema') == 'own-runtime.chain-admission.v1'
            and proof.get('passed') is True and proof.get('window') == row['window']
            and proof.get('scope') == bound.get('scope') == scope,
            'lane admission policy/identity differs')
    require(proof.get('coordination', {}).get('boot_id') == row.get('boot_id'),
            'lane admission boot differs')
    require(proof.get('owners') and all(owner.get('seen') is True and owner.get('exited') is True
                                       for owner in proof['owners'].values()),
            'lane admission owners unproven')
    require(set(map(int, proof['owners'])) == set(row.get('launched_pids', [])),
            'lane admission owner set differs')
    require(not row['window'].startswith('W') or proof.get('ready_checks', 0) > 0,
            'lane admission READY proof missing')
    return proof


def run_lane_b_screen(main, output, *, wait_check, root=DEFAULT_ROOT, proc=Path('/proc')):
    """Driver hook around ONE existing sealed v3 screen, never around a batch.

    The existing entry point owns GPU supervision, signal handling, exactness,
    shared teardown and postflight. This hook starts no subprocess and sends no
    signal. A failed/retained screen leaves active-lane-B.json in place.
    """
    output = Path(output)
    require(not output.exists(), 'lane B needs a fresh screen output')
    lease = Reservation('B', root=root, check=wait_check)
    lease.record['output'] = str(output.resolve())
    with lease:
        # Check again after waiting; never consume another run's evidence.
        require(not output.exists(), 'lane B output appeared during wait')
        code = main()
        if code:
            return code
        row = json.loads((output / 'window.json').read_text())
        summary = json.loads((output / 'summary.json').read_text())
        require(row.get('schema') == 'own-runtime.screen.window.v3' and row.get('lane') == 'B'
                and row.get('passed') is True and row.get('device_executed') is True
                and row.get('child_still_running') is False and not row.get('child_retained'),
                'lane B screen did not confirm successful drain/postflight')
        require(summary.get('passed') is True and summary.get('device_isolation', {}).get('passed') is True,
                'lane B native isolation/teardown unproven')
        require(type(row.get('pid')) is int and type(row.get('process_start_ticks')) is int,
                'lane B process identity missing')
        require(process_identity(row['pid'], proc) != row['process_start_ticks'],
                'lane B worker still alive')
        clients = admit_clients('lane-B', proc)
        lease.complete(drained=True)
        atomic_json(output / 'lane-coordination.json', dict(
            schema='own-runtime.screen.lane-coordination.v1', passed=True,
            reservation=lease.record, clients_after_drain=clients,
            window_sha256=hashlib.sha256((output / 'window.json').read_bytes()).hexdigest()))
        return code


def run_window(main, *, wait_check, argv=None):
    """CLI adapter; original parser and every original gate still run in main.

    Caller supplies fresh kernel-fault checks for the wait. STOP and signals
    cancel waiting without signalling either lane. No child starts here.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--window', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--card', type=int, required=True)
    parser.add_argument('--authorized-device-window', action='store_true', required=True)
    args, _ = parser.parse_known_args(argv)
    require(args.card == 0, 'chain mask exposes native cards 0 and 1 only')
    require(not args.output.exists() and args.output.parent.is_dir(), 'fresh window under existing chain root required')
    cancelled = []
    def check():
        require(not cancelled, 'coordinator cancelled admission wait')
        require(not (args.output.parent / 'STOP').exists(), 'STOP during admission wait')
        wait_check()
    handlers = {s: signal.signal(s, lambda n, f: cancelled.append(n))
                for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        evidence = args.output.parent / (args.output.name + '-lane-admission.json')
        with WindowAdmission(args.window, evidence, check=check) as admission:
            # Main installs its existing cooperative handlers before launch.
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            code = main(admission=admission)
            if code == 0:
                bind_receipt(args.output / 'window.json', admission)
            return code
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
