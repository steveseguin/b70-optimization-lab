"""Packet58e's card-0 adapter for the existing chain-lanes-v1 protocol.

Imports are passive. Production coordination is entered only by window.py;
CPU tests supply temporary roots. Failed owners retain their markers.
"""
from pathlib import Path
import chain_devices as D
from lane_admission import Reservation, DEFAULT_ROOT, window_scope
from drain_gate import DrainPermit, DEFAULT_DRAIN_ROOT


class Admission:
    def __init__(self, window, output, check, *, root=DEFAULT_ROOT,
                 drain_root=DEFAULT_DRAIN_ROOT, proc=Path('/proc')):
        self.scope, self.proc = window_scope(window), proc
        self.lease = Reservation('A', window=window, root=root, check=check)
        self.drain = DrainPermit(output, root=drain_root, check=check,
                                 reservation=self.lease.record)
        self.owners = {}
        self.record = dict(passed=False, scope=self.scope, card=0,
                           timing_claim_eligible=window == 'WS128',
                           reservation=self.lease.record, owners=self.owners)

    def __enter__(self):
        self.lease.__enter__()
        try:
            self.record['clients'] = D.admit_clients(self.scope, self.proc)
            self.drain.__enter__()
            self.record['clients'] = D.admit_clients(self.scope, self.proc)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def observe(self, sample):
        owned = {}
        for process in sample['processes']:
            pid = process['pid']
            start = D.process_identity(pid, self.proc)
            if start is None:
                continue
            old = self.owners.setdefault(str(pid), dict(start_ticks=start, seen=False))
            D.require(old['start_ticks'] == start, 'owned PID reused')
            owned[pid] = start
            try:
                fds = D.xe_fds(pid, self.proc)
            except (FileNotFoundError, ProcessLookupError):
                D.require(D.process_identity(pid, self.proc) is None, 'owner fdinfo disappeared')
                continue
            D.require(all(r['driver'] == 'xe' and r['pci'] == D.LANES['A'][0] for r in fds),
                      'one-card owner opened another card')
            old['seen'] = old['seen'] or bool(fds)
        # Retain known live descendants while the root is exiting.
        for pid, owner in self.owners.items():
            current = D.process_identity(int(pid), self.proc)
            D.require(current in (None, owner['start_ticks']), 'owned PID reused')
            if current is not None:
                owned[int(pid)] = current
        self.record['clients_latest'] = D.admit_clients(self.scope, self.proc, owned)

    def complete(self):
        D.require(any(r['seen'] for r in self.owners.values()), 'card-0 ownership was not observed')
        D.require(all(D.process_identity(int(pid), self.proc) is None for pid in self.owners),
                  'owned process remains after drain')
        self.record['clients_after_drain'] = D.admit_clients(self.scope, self.proc)
        self.drain.complete()
        self.lease.complete(drained=True)
        self.record['passed'] = True

    def __exit__(self, kind, value, trace):
        self.drain.__exit__(kind, value, trace)
        self.lease.__exit__(kind, value, trace)


def verify(row):
    proof = row.get('lane_admission', {})
    D.require(proof.get('passed') is True and proof.get('card') == row.get('card') == 0
              and proof.get('scope') == window_scope(row['window'])
              and proof.get('timing_claim_eligible') is (row['window'] == 'WS128'),
              'missing completed card-0 lane admission')
    D.require(proof.get('reservation', {}).get('boot_id') == row.get('boot_id'),
              'lane admission boot differs')
