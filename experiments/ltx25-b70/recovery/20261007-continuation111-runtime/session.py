"""Fixed native continuation authority. No device imports, retries or registration.

The sealed launcher supplies trusted state/proof inspectors. A successful prompt
does not authorize its successor until its separate, durable proof is accepted.
"""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time

PLAN_SHA256 = '7944f8701244bd386c41bc5cdd6c4e9df1ea8fcf4d9dedf91e249f476105b2c5'
QUALIFICATION_ID = '705fa3d73c603833591ac5ae13b5f2d4d79c329b860794ff4d061c71e8942266'
MODE = 'same-size-native-v1'
PHASES = ('native_reference',)
_authority = None


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: require(False, 'Nonfinite JSON'))
    canonical(value)  # Also reject overflowed exponent literals such as 1e999.
    return value


def _safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe evidence path')
    return path


def read_regular(path, limit=8*1024**2):
    path = _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size <= limit, 'Nonregular, linked or oversized evidence')
        raw = stream.read(limit+1)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(raw) == before.st_size and identity(before) ==
                identity(os.fstat(stream.fileno())) == identity(path.lstat()),
                'Evidence changed during read')
    return raw


def write_exclusive(path, value):
    path = _safe_path(path)
    raw = canonical(value) + b'\n'
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def pipeline_snapshot(pipeline):
    with pipeline._LOCK:
        stages = {}
        for name, state in sorted(pipeline._STAGES.items()):
            stages[name] = {
                'queued_indices': [job.index for job in state['queue']],
                'jobs': [{'index': job.index, 'done': job.done.is_set(),
                          'error': job.error, 'tag': job.tag, 'target': job.target,
                          'started': job.started, 'finished': job.finished}
                         for _, job in sorted(state['jobs'].items())]}
        return {'running': pipeline._RUNNING[0], 'stages': stages}


def require_quiescent(snapshot, no_tails=False):
    require(all(key in snapshot and type(snapshot[key]) is int and snapshot[key] == 0
                for key in ('preview_pending', 'preview_failures')),
            'Explicit zero integer preview counters required')
    require(type(snapshot['queue_pending']) is int and snapshot['queue_pending'] == 0 and
            type(snapshot['queue_running']) is int and snapshot['queue_running'] == 0,
            'Prompt queue is not empty')
    pipe = snapshot['pipeline']
    require(type(pipe['running']) is int and pipe['running'] == 0, 'Pipeline worker executing')
    for stage in pipe['stages'].values():
        require(stage['queued_indices'] == [], 'Pipeline work queued')
        for job in stage['jobs']:
            require(job['done'] is True and job['error'] is None, 'Unfinished or failed pipeline job')
        if no_tails:
            require(stage['jobs'] == [], 'Uncollected pipeline tail')


class Authority:
    def __init__(self, plan_path, runtime_manifest_sha256, server_identity_sha256,
                 run_dir, inspect_state, verify_proof):
        envelope = strict_json(read_regular(plan_path))
        require(type(envelope) is dict and set(envelope) == {'plan', 'plan_sha256'} and
                envelope['plan_sha256'] == PLAN_SHA256 == digest(canonical(envelope['plan'])),
                'Not the fixed reviewed continuation plan')
        require(envelope['plan']['qualification_id'] == QUALIFICATION_ID, 'Qualification differs')
        for value in (runtime_manifest_sha256, server_identity_sha256):
            require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'Missing trusted identity')
        require(callable(inspect_state) and callable(verify_proof), 'Trusted inspectors required')
        self.run_dir = _safe_path(run_dir)
        require(self.run_dir.is_dir(), 'Run directory missing')
        self.plan = envelope['plan']
        self.requests = {r['name']: r for r in self.plan['requests']}
        self.order = tuple(self.plan['execution_order'])
        require(len(self.order) == len(self.requests) == 8 and
                list(self.requests) == list(self.order), 'Exact eight requests required')
        self.runtime_sha, self.identity_sha = runtime_manifest_sha256, server_identity_sha256
        self.inspect_state, self.verify_proof = inspect_state, verify_proof
        self.phase = 'native_reference'
        self.lock = threading.RLock()
        self.active, self._active_signature = None, None
        self.failed, self.halt_receipt_error = None, None
        self.completed, self.prompt_ids = [], set()
        self.request_prompt_ids = {}
        self.capture_count = 0
        self.proofs, self.barriers = {}, {}
        self.references_sha, self.candidate_sha = None, None
        self._busy = None

    def healthy(self):
        require(self.failed is None, 'Session halted: ' + str(self.failed))
        require(self.phase == 'native_reference' and digest(canonical(self.plan)) == PLAN_SHA256 and
                self.requests == {r['name']: r for r in self.plan['requests']} and
                self.order == tuple(self.plan['execution_order']), 'Authority plan/phase changed')
        require(self.completed == list(self.order[:len(self.completed)]) and len(self.completed) <= 8,
                'Completion order changed')
        if self.active is not None:
            require(canonical(self.active) == self._active_signature and
                    len(self.completed) < 8 and self.active['name'] == self.order[len(self.completed)],
                    'Active request changed')

    def halt(self, error):
        with self.lock:
            if self.failed is None:
                self.failed = str(error)
                write_exclusive(self.run_dir/'resolution-halt.json', {
                    'schema': 'ltx.continuation111-halt.v1', 'reason': self.failed,
                    'phase': self.phase, 'active': self.active, 'time_ns': time.time_ns()})

    @contextmanager
    def _operation(self, label):
        with self.lock:
            entered = False
            try:
                self.healthy()
                require(self._busy is None, 'Reentrant authority operation: ' + label)
                self._busy, entered = label, True
                yield
                self.healthy()
            except BaseException as error:
                try:
                    self.halt(error)
                except Exception as receipt_error:
                    self.halt_receipt_error = repr(receipt_error)
                raise
            finally:
                if entered:
                    self._busy = None

    def _metadata(self, role, name):
        return {'role': role, 'run_name': name, 'phase': self.phase,
                'qualification_id': QUALIFICATION_ID, 'comparison_mode': MODE,
                'plan_sha256': PLAN_SHA256, 'runtime_manifest_sha256': self.runtime_sha,
                'server_identity_sha256': self.identity_sha,
                'reference_receipt_sha256': self.references_sha,
                'candidate_receipt_sha256': self.candidate_sha}

    def require_phase(self, role, qualification_id, run_name):
        with self._operation('require_phase'):
            require(role in ('text', 'native'), 'Native-only authority refuses role')
            require(qualification_id == QUALIFICATION_ID and self.active is not None and
                    self.active['name'] == run_name, 'No matching active qualified request')
            return self._metadata(role, run_name)

    def _state(self, executing=False):
        state = self.inspect_state()
        self.healthy()
        require(type(state) is dict and state['fault'] is False, 'Device or experiment fault')
        require(all(key in state for key in ('preview_pending', 'preview_failures',
                    'captures_frozen', 'loads_frozen')), 'Incomplete native observation')
        require(all(type(state[k]) is int and state[k] == 0
                    for k in ('sampler_routes', 'lean_state', 'decode_replicas')),
                'Optimized state in native execution')
        require(state['captures_frozen'] is False and state['loads_frozen'] is False,
                'Frozen optimized state')
        quiet = state
        if executing:
            require(type(state['queue_running']) is int and 0 <= state['queue_running'] <= 1,
                    'Overlapping prompt execution')
            quiet = dict(state, queue_running=0)
        require_quiescent(quiet, no_tails=True)
        return copy.deepcopy(state)

    def _check_proof(self, name, path, sha):
        require(name in self.completed and name in self.request_prompt_ids, 'Producer not completed')
        require(type(sha) is str and re.fullmatch('[0-9a-f]{64}', sha), 'Invalid proof digest')
        path = Path(path)
        require(path == self.run_dir/('continuation-proof-'+name+'.json'), 'Proof path is not fixed')
        raw = read_regular(path)
        require(digest(raw) == sha, 'Proof file changed')
        checked = copy.deepcopy(self.verify_proof(name, path, sha))
        self.healthy()
        expected = {'plan_sha256': PLAN_SHA256, 'runtime_manifest_sha256': self.runtime_sha,
                    'server_identity_sha256': self.identity_sha, 'name': name,
                    'prompt_id': self.request_prompt_ids[name], 'verified': True}
        require(type(checked) is dict and all(checked.get(k) == v for k, v in expected.items()) and
                checked.get('verified') is True, 'Trusted proof result identity/verdict differs')
        canonical(checked)
        require(read_regular(path) == raw, 'Proof changed during verification')
        return {'path': str(path), 'sha256': sha, 'checked': checked}

    def _revalidate(self, name):
        require(name in self.proofs, 'Proof not accepted: ' + name)
        binding = copy.deepcopy(self.proofs[name])
        fresh = self._check_proof(name, binding['path'], binding['sha256'])
        require(fresh == binding and self.proofs[name] == binding, 'Accepted proof result changed')
        return copy.deepcopy(fresh)

    def revalidate_proof(self, name):
        with self._operation('revalidate_proof'):
            if self.active is None:
                self._state()
            else:
                require(name in self.completed, 'Active request cannot consume its own/future proof')
            return self._revalidate(name)

    def _dependencies(self, row):
        names = []
        for dependency in row['requires_proofs']:
            if dependency.startswith('proof:'):
                name = dependency.split(':', 1)[1]
            else:
                require(dependency in self.barriers, 'Required proof barrier missing')
                name = self.barriers[dependency]
                require(dependency in self.requests[name].get('establishes', []), 'Barrier owner differs')
            if name not in names:
                names.append(name)
        for name in names:
            self._revalidate(name)

    def begin(self, name, graph, prompt_id):
        with self._operation('begin'):
            require(self.active is None and len(self.completed) < 8, 'Active or exhausted plan')
            require(name == self.order[len(self.completed)], 'Global request order differs')
            require(type(prompt_id) is str and prompt_id and prompt_id not in self.prompt_ids,
                    'Missing or reused prompt identity')
            row = self.requests[name]
            require(digest(canonical(graph)) == row['graph_sha256'], 'Submitted graph differs')
            require(row['authority_phase'] == self.phase, 'Request phase differs')
            self._dependencies(row)
            state = self._state(executing=True)
            if row['capture_role'] == 'full':
                require(self.capture_count < 6, 'Six-capture allowance exhausted')
                self.capture_count += 1
            self.prompt_ids.add(prompt_id)
            self.request_prompt_ids[name] = prompt_id
            self.active = {'name': name, 'prompt_id': prompt_id, 'start_ns': time.time_ns()}
            self._active_signature = canonical(self.active)
            write_exclusive(self.run_dir/('resolution-before-'+name+'.json'),
                            {**self._metadata('request', name), **self.active, 'state': state})
            return copy.deepcopy(row)

    def finish(self, status_messages):
        with self._operation('finish'):
            require(self.active is not None, 'No request to finish')
            pid = self.active['prompt_id']
            success = [d for t, d in status_messages if t == 'execution_success']
            require(len(success) == 1 and success[0].get('prompt_id') == pid,
                    'Exactly one matching execution success required')
            require(not any(t in ('execution_error', 'execution_interrupted') or
                            (t == 'execution_cached' and d.get('nodes')) for t, d in status_messages),
                    'Failed or cached execution')
            state = self._state(executing=True)
            name = self.active['name']
            write_exclusive(self.run_dir/('resolution-after-'+name+'.json'), {
                **self._metadata('request', name), **self.active, 'end_ns': time.time_ns(), 'state': state})
            self.completed.append(name)
            self.active, self._active_signature = None, None

    def accept_proof(self, name, path, sha):
        with self._operation('accept_proof'):
            require(self.active is None, 'Cannot accept proof during execution')
            pending = [n for n in self.completed if n not in self.proofs]
            require(pending and name == pending[0] and name not in self.proofs,
                    'Only next completed unproven request may be accepted')
            self._state()
            binding = self._check_proof(name, path, sha)
            self._state()
            require(digest(read_regular(binding['path'])) == sha, 'Proof changed before acceptance')
            established = self.requests[name].get('establishes', [])
            require(not any(b in self.barriers for b in established), 'Repeated barrier establishment')
            write_exclusive(self.run_dir/('continuation-proof-accepted-'+name+'.json'), {
                **self._metadata('proof', name), 'prompt_id': self.request_prompt_ids[name],
                'binding': binding, 'establishes': established, 'time_ns': time.time_ns()})
            self.proofs[name] = copy.deepcopy(binding)
            self.barriers.update({b: name for b in established})
            return copy.deepcopy(binding)


def configure(*args, **kwargs):
    global _authority
    require(_authority is None, 'Authority may only be configured once')
    _authority = Authority(*args, **kwargs)
    return _authority


def require_phase(role, qualification_id, run_name):
    require(_authority is not None, 'No sealed continuation authority configured')
    return _authority.require_phase(role, qualification_id, run_name)


def auxiliary_metadata():
    if _authority is None:
        return None
    with _authority.lock:
        result = _authority._metadata('auxiliary', None)
        result.update(output_parity_claimed=False, halted=_authority.failed is not None)
        return result
