"""One bounded passive accounting child. No server/device controls or retries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

COLLECTOR_SHA = 'abee1ac0c0e2a47ec9d622f4639bfaec45c7bd45272380dba4c51f7a195fc480'
READY_SECONDS = 10
FINISH_SECONDS = 130
SCOPE = ('Raw collection integrity and observed process/render coverage only; '
         'no utilization, sampler attribution, throughput ceiling, or assurance '
         'of usable intervals inside the ten scored clips.')


class AccountingError(RuntimeError):
    """Observer-only failure; never a request to stop the healthy application."""


def require(ok, message):
    if not ok:
        raise AccountingError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, cap):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe accounting path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), 'Nonregular accounting evidence')
        raw = stream.read(cap + 1)
    require(len(raw) <= cap, 'Accounting evidence cap exceeded')
    return raw, info


class DriverAccounting:
    def __init__(self, client):
        self.client = client
        self.run = Path(client.run)
        self.collector_path = Path(__file__).resolve().with_name('driver_accounting.py')
        self.path = self.run / 'driver-accounting-contract.json'
        self.output = self.run / 'driver-accounting.jsonl'
        self.child = None
        self.owned = False
        self.attempted = self.ready = False
        self.started = None
        self.prefix = b''
        self.output_identity = None
        self.output_fd = None
        self.result = None
        self.module = None

    def check(self):
        c = self.client.contract
        client_raw, _ = read(self.client.contract_path, 2**21)
        require(sha(client_raw) == self.client.contract_sha, 'Client contract changed')
        require(json.loads(client_raw) == c, 'In-memory client contract differs')
        require(c.get('driver_accounting_contract_path') == str(self.path), 'Accounting contract path differs')
        require(c['server_run'] == str(self.run) and Path(c['root']) == self.run.parent, 'Accounting run differs')
        for path in (Path(__file__).resolve(), self.collector_path):
            raw, _ = read(path, 65536)
            require(c['source_bindings'].get(str(path)) == sha(raw), 'Unbound accounting source')
            if path == self.collector_path:
                require(sha(raw) == COLLECTOR_SHA, 'Unreviewed collector source')
        if self.module is None:
            spec = importlib.util.spec_from_file_location('sealed_driver_accounting', self.collector_path)
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.accounting_sha = c['driver_accounting_contract_sha256']
        contract = self.module.load_contract(self.path, self.accounting_sha)
        identity = self.client.identity
        require(contract['collector_sha256'] == COLLECTOR_SHA and
                contract['pid'] == identity['pid'] and contract['start_ticks'] == identity['proc_start_ticks'] and
                contract['boot_id'] == identity['boot_id'] and
                contract['runtime_manifest_sha256'] == c['runtime_manifest_sha256'] and
                contract['plan_sha256'] == c['plan_sha256'] and
                contract['qualification_id'] == self.client.plan['qualification_id'], 'Accounting/server identity differs')
        require(contract['bindings']['server_identity'] == {
                    'path': str(self.run / 'server-identity.json'), 'sha256': c['server_identity_sha256']} and
                contract['bindings']['plan']['path'] == c['plan_path'], 'Accounting evidence bindings differ')
        faults = {str(self.run.parent / 'FAULT.json'), str(self.run / 'FAULT.json'),
                  str(self.run / 'resolution-halt.json')}
        require(faults <= set(contract['fault_paths']), 'Accounting fault paths differ')
        self.contract = contract

    def records(self, final=False):
        raw, info = read(self.output, self.module.MAX_OUTPUT)
        identity = (info.st_dev, info.st_ino)
        if self.output_identity is None:
            self.output_fd = os.open(self.output, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            pinned = os.fstat(self.output_fd)
            require((pinned.st_dev, pinned.st_ino) == identity, 'Accounting output changed during open')
            self.output_identity = identity
        require(identity == self.output_identity and raw.startswith(self.prefix), 'Accounting output replaced or rewritten')
        self.prefix = raw
        require(not final or raw.endswith(b'\n'), 'Incomplete accounting output tail')
        lines = raw.split(b'\n')[:-1]
        require(len(lines) <= self.module.MAX_SAMPLES + 2, 'Accounting record count exceeded')
        rows = [self.module.strict(line) for line in lines]
        if not rows:
            return rows
        expected = {'schema': 'ltx.raw-drm-snapshots.v1', 'contract_sha256': self.accounting_sha,
                    'collector_sha256': COLLECTOR_SHA, 'bindings': self.contract['bindings'],
                    'ordered_xpu_mapping': self.contract['ordered_xpu_mapping'],
                    **{k: self.contract[k] for k in ('pid', 'start_ticks', 'boot_id')},
                    'limits': {'seconds': self.module.DURATION, 'samples': self.module.MAX_SAMPLES,
                               'bytes': self.module.MAX_OUTPUT, 'interval': self.module.INTERVAL}}
        require(rows[0] == expected, 'Accounting header identity/source binding differs')
        terminals = [i for i, row in enumerate(rows) if 'terminal' in row]
        require(not terminals or terminals == [len(rows)-1], 'Misplaced or duplicate accounting terminal')
        last_end = self.started_ns
        for row in rows[1:]:
            if 'terminal' in row or row.get('incomplete') == 'missed-cadence':
                continue
            require(type(row.get('complete')) is bool and isinstance(row.get('issues'), list) and
                    isinstance(row.get('clients'), dict), 'Malformed accounting sample')
            begin, end = row.get('monotonic_start_ns'), row.get('monotonic_end_ns')
            require(type(begin) is int and type(end) is int and last_end <= begin <= end,
                    'Accounting sample chronology differs')
            last_end = end
            require(row['complete'] == (not row['issues']), 'Accounting completeness differs')
            if row['complete']:
                require({r['pci'] for r in row['clients'].values()} == set(self.contract['render_nodes'].values()),
                        'Complete sample lacks admitted render coverage')
        return rows

    def start(self):
        try:
            require(not self.attempted and self.child is None, 'Accounting child already owned or attempted')
            self.attempted = True
            self.check()
            require(not os.path.lexists(self.output), 'Accounting output already exists; ownership refused')
            self.started = time.monotonic()
            self.started_ns = time.monotonic_ns()
            self.child = subprocess.Popen([sys.executable, '-B', str(self.collector_path),
                '--contract', str(self.path), '--contract-sha256', self.accounting_sha, '--output', str(self.output)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                shell=False, close_fds=True)
            require(type(self.child.pid) is int and self.child.pid > 1 and self.child.pid != self.client.identity['pid'],
                    'Invalid accounting child ownership')
            self.owned = True
            while time.monotonic() < self.started + READY_SECONDS:
                self.check()
                require(self.child.poll() is None, 'Accounting child exited before readiness')
                try:
                    rows = self.records()
                except FileNotFoundError:
                    rows = []
                require(not any('terminal' in row for row in rows), 'Accounting terminated before readiness')
                if any(row.get('complete') is True for row in rows[1:]):
                    self.ready = True
                    return {'ready': True, 'child_pid': self.child.pid, 'output_path': str(self.output),
                            'contract_sha256': self.accounting_sha, 'claim_scope': SCOPE}
                time.sleep(min(.2, max(0, self.started + READY_SECONDS - time.monotonic())))
            raise AccountingError('Accounting readiness timeout; no signal or retry')
        except KeyboardInterrupt:
            raise
        except Exception as error:
            if self.output_fd is not None:
                os.close(self.output_fd)
                self.output_fd = None
            raise AccountingError(str(error)) from error

    def finish(self):
        if self.result is not None:
            return self.result
        result = {'valid': False, 'reason': None, 'terminal': None, 'child_returncode': None,
                  'samples_recorded': 0, 'complete_samples': 0, 'incomplete_samples': 0,
                  'missed_slots': 0, 'issues': [], 'files': {}, 'claim_scope': SCOPE,
                  'ready': self.ready, 'child_owned': self.owned, 'child_running': None,
                  'child_pid': self.child.pid if self.owned else None}
        try:
            if self.owned:
                result['child_returncode'] = self.child.poll()
                result['child_running'] = result['child_returncode'] is None
            require(self.ready and self.owned, 'Accounting never became ready')
            deadline = self.started + FINISH_SECONDS
            while self.child.poll() is None and time.monotonic() < deadline:
                time.sleep(min(1, max(0, deadline - time.monotonic())))
            result['child_returncode'] = self.child.poll()
            result['child_running'] = result['child_returncode'] is None
            self.check()
            require(result['child_returncode'] is not None, 'Accounting child exceeded original deadline; left unsignalled')
            rows = self.records(final=True)
            require(len(rows) >= 3 and 'terminal' in rows[-1], 'Accounting terminal missing')
            terminal = rows[-1]; result['terminal'] = terminal
            samples = [row for row in rows[1:-1] if 'complete' in row]
            missed = [row for row in rows[1:-1] if row.get('incomplete') == 'missed-cadence']
            result.update(samples_recorded=len(samples), complete_samples=sum(row['complete'] for row in samples),
                          incomplete_samples=sum(not row['complete'] for row in samples), missed_slots=len(missed),
                          issues=sorted({issue for row in samples for issue in row['issues']}))
            require(type(terminal.get('samples_recorded')) is int and terminal['samples_recorded'] == len(samples) and
                    type(terminal.get('missed_slots')) is int and terminal['missed_slots'] == len(missed), 'Accounting terminal counts differ')
            require(result['child_returncode'] == 0 and terminal['terminal'] in ('duration-cap', 'sample-cap', 'output-cap'),
                    'Accounting failed or stopped early')
            require(result['complete_samples'] > 0 and not result['incomplete_samples'] and not missed,
                    'Accounting coverage incomplete')
            result['valid'] = True
        except KeyboardInterrupt:
            raise
        except BaseException as error:
            result['reason'] = str(error)[:300]
        for name, path, cap in (('contract', self.path, 65536), ('output', self.output, 131072)):
            try:
                raw, _ = read(path, cap)
                if name == 'contract':
                    require(sha(raw) == self.client.contract.get('driver_accounting_contract_sha256'), 'Accounting contract changed after validation')
                elif result['valid']:
                    require(raw == self.prefix, 'Accounting output changed after validation')
                result['files'][name] = {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}
            except Exception as error:
                result['files'][name] = {'path': str(path), 'unavailable': str(error)[:160]}
                result['valid'] = False
                result['reason'] = result['reason'] or 'Accounting evidence unavailable'
        if self.output_fd is not None:
            try:
                os.close(self.output_fd)
            except OSError as error:
                result['valid'] = False
                result['reason'] = result['reason'] or str(error)[:300]
            self.output_fd = None
        self.result = result
        return result
