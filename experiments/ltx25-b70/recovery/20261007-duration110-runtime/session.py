"""Pinned resolution experiment authority. CPU-only until trusted adapters attach.

The sealed launcher owns construction; graph inputs cannot construct an authority,
advance a phase, register graphs, or manufacture a successful comparison. Adapters
are still required before this component is a runnable experiment.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

PLAN_SHA256 = 'cafb272fcb182d80022a0e73eff838dc7fd0aeb5001704d0b9ccbd37fadeccab'
MODE = 'same-size-native-v1'
PHASES = ('native_reference', 'reference_verified', 'optimized_preparation',
          'candidate_verified', 'timing')
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
        for k, v in items:
            require(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def read_regular(path, limit=8 * 1024**2):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe evidence path')
    before = path.stat()
    require(path.is_file() and before.st_size <= limit, 'Nonregular or oversized evidence')
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Evidence changed during read')
    return raw


def write_exclusive(path, value):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def pipeline_snapshot(pipeline):
    """Observe actual jobs atomically; finished/uncollected tails remain visible."""
    with pipeline._LOCK:
        stages = {}
        for name, state in sorted(pipeline._STAGES.items()):
            stages[name] = {
                'queued_indices': [job.index for job in state['queue']],
                'jobs': [{'index': job.index, 'done': job.done.is_set(),
                          'error': job.error, 'tag': job.tag, 'target': job.target,
                          'started': job.started, 'finished': job.finished}
                         for _, job in sorted(state['jobs'].items())],
            }
        return {'running': pipeline._RUNNING[0], 'stages': stages}


def require_quiescent(snapshot, no_tails=False):
    require(snapshot.get('preview_pending', 0) == 0 and snapshot.get('preview_failures', 0) == 0,
            'Preview work pending or failed')
    require(snapshot['queue_pending'] == 0 and snapshot['queue_running'] == 0,
            'Prompt queue is not empty')
    pipe = snapshot['pipeline']
    require(type(pipe['running']) is int and pipe['running'] == 0,
            'Pipeline worker still executing')
    for stage in pipe['stages'].values():
        require(stage['queued_indices'] == [], 'Pipeline work still queued')
        for job in stage['jobs']:
            require(job['done'] is True and job['error'] is None,
                    'Pipeline unfinished or failed job')
        if no_tails:
            require(stage['jobs'] == [], 'Uncollected pipeline tail remains')


def retire_completed_tails(pipeline, receipt_path, queue_empty):
    """Release only completed nonfailed tails, after preserving their identities.

    This is deliberately not pipeline.clear(): unfinished work cannot disappear.
    The caller must own the phase barrier and prevent new request admission.
    No job is recomputed, no cached conditioning reused, no device cache flushed.
    """
    require(queue_empty(), 'Prompt queue changed at phase barrier')
    with pipeline._LOCK:
        snap = pipeline_snapshot_locked(pipeline)
        require_quiescent({'queue_pending': 0, 'queue_running': 0, 'pipeline': snap})
        write_exclusive(receipt_path, {'schema': 'ltx.completed-pipeline-tails.v1',
            'time_ns': time.time_ns(), 'pipeline': snap,
            'disposition': 'completed un-emitted tail values released; not scored clips'})
        # Still under the same lock: no worker can enqueue or begin a job here.
        for state in pipeline._STAGES.values():
            state['jobs'].clear()
        return snap


def pipeline_snapshot_locked(pipeline):
    # Called while the actual non-reentrant pipeline lock is already held.
    stages = {}
    for name, state in sorted(pipeline._STAGES.items()):
        stages[name] = {'queued_indices': [j.index for j in state['queue']],
                       'jobs': [{'index': j.index, 'done': j.done.is_set(),
                                 'error': j.error, 'tag': j.tag, 'target': j.target,
                                 'started': j.started, 'finished': j.finished}
                                for _, j in sorted(state['jobs'].items())]}
    return {'running': pipeline._RUNNING[0], 'stages': stages}


class Authority:
    def __init__(self, plan_path, runtime_manifest_sha256, server_identity_sha256,
                 run_dir, inspect_state, evidence_verifiers, setup_requests=()):
        envelope = strict_json(read_regular(plan_path))
        require(set(envelope) == {'plan', 'plan_sha256'} and
                envelope['plan_sha256'] == PLAN_SHA256 == digest(canonical(envelope['plan'])),
                'Plan is not the reviewed fixed plan')
        for sha in (runtime_manifest_sha256, server_identity_sha256):
            require(isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha), 'Missing trusted identity')
        self.plan = envelope['plan']
        self.run_dir = Path(run_dir)
        require(self.run_dir.is_dir() and not self.run_dir.is_symlink(), 'Run directory missing')
        self.runtime_sha = runtime_manifest_sha256
        self.identity_sha = server_identity_sha256
        self.inspect_state = inspect_state
        self.verifiers = evidence_verifiers
        self.phase = 'native_reference'
        self.active = None
        self.failed = None
        self.completed = []
        self.prompt_ids = set()
        self.references_sha = None
        self.candidate_sha = None
        self.capture_count = 0
        self.lock = threading.RLock()
        self.requests = {r['name']: r for r in self.plan['requests']}
        # Additional graphs come from the sealed integration schedule, never a node input.
        for row in setup_requests:
            require(row['name'] not in self.requests and row['phase'] in
                    ('native-setup', 'optimized-setup'), 'Bad setup request')
            require(row['graph_sha256'] == digest(canonical(row['graph'])), 'Setup graph hash differs')
            self.requests[row['name']] = row

    def healthy(self):
        require(self.failed is None, 'Session halted: ' + str(self.failed))

    def halt(self, error):
        if self.failed is None:
            self.failed = str(error)
            write_exclusive(self.run_dir / 'resolution-halt.json',
                            {'schema': 'ltx.resolution-halt.v1', 'reason': self.failed,
                             'phase': self.phase, 'active': self.active, 'time_ns': time.time_ns()})

    def _metadata(self, role, name):
        return {'role': role, 'run_name': name, 'phase': self.phase,
                'qualification_id': self.plan['qualification_id'], 'comparison_mode': MODE,
                'plan_sha256': PLAN_SHA256, 'runtime_manifest_sha256': self.runtime_sha,
                'server_identity_sha256': self.identity_sha,
                'reference_receipt_sha256': self.references_sha,
                'candidate_receipt_sha256': self.candidate_sha}

    def require_phase(self, role, qualification_id, run_name):
        with self.lock:
            self.healthy()
            try:
                return self._require_phase(role, qualification_id, run_name)
            except BaseException as error:
                self.halt(error)
                raise

    def _require_phase(self, role, qualification_id, run_name):
        with self.lock:
            require(role in ('text', 'sampler', 'decode', 'native'), 'Unknown resolution role')
            require(qualification_id == self.plan['qualification_id'], 'Workload ID mismatch')
            require(self.active is not None and self.active['name'] == run_name,
                    'No admitted active request matches node')
            allowed = {'text': ('native_reference', 'optimized_preparation', 'timing'),
                       'native': ('native_reference',),
                       'sampler': ('optimized_preparation', 'timing'),
                       'decode': ('optimized_preparation', 'timing')}
            require(self.phase in allowed[role], 'Role disallowed in current phase')
            return self._metadata(role, run_name)

    def begin(self, name, graph, prompt_id):
        with self.lock:
            self.healthy()
            try:
                require(self.active is None, 'Overlapping prompt execution')
                require(name in self.requests and name not in self.completed and
                        prompt_id not in self.prompt_ids and isinstance(prompt_id, str) and prompt_id,
                        'Unknown or reused request identity')
                row = self.requests[name]
                require(digest(canonical(graph)) == row['graph_sha256'], 'Submitted graph differs')
                expected = {'native-reference': 'native_reference', 'native-repeat': 'native_reference',
                            'native-setup': 'native_reference', 'optimized-setup': 'optimized_preparation',
                            'candidate-check': 'optimized_preparation', 'timed-fast': 'timing'}[row['phase']]
                require(self.phase == expected, 'Request submitted in wrong phase')
                planned = [r['name'] for r in self.plan['requests'] if r['phase'] == row['phase']]
                if planned:
                    todo = [n for n in planned if n not in self.completed]
                    require(todo and name == todo[0], 'Fixture execution order differs')
                if row['phase'] == 'native-repeat':
                    require(all(r['name'] in self.completed for r in self.plan['requests']
                                if r['phase'] == 'native-reference'), 'Native first pass incomplete')
                state = self.inspect_state()
                require(state['fault'] is False, 'Device or experiment fault')
                if self.phase == 'native_reference':
                    require(state['queue_pending'] == 0 and state['queue_running'] <= 1,
                            'Native requests must be submitted serially')
                    quiet = dict(state, queue_running=0)
                    require_quiescent(quiet, no_tails=True)
                    require(state['sampler_routes'] == 0 and state['lean_state'] == 0 and
                            state['decode_replicas'] == 0, 'Native reference would use optimized state')
                capture = any(n['class_type'] in ('LTXBaselineCapture', 'LTXPipelineSave')
                              for n in graph.values())
                if capture:
                    require(self.capture_count < 50, 'Bounded capture allowance exhausted')
                    self.capture_count += 1
                self.prompt_ids.add(prompt_id)
                self.active = {'name': name, 'prompt_id': prompt_id, 'start_ns': time.time_ns()}
                write_exclusive(self.run_dir / ('resolution-before-' + name + '.json'),
                                {**self._metadata('request', name), **self.active, 'state': state})
                return row
            except BaseException as error:
                self.halt(error)
                raise

    def finish(self, status_messages):
        with self.lock:
            self.healthy()
            try:
                require(self.active is not None, 'No active request to finish')
                pid = self.active['prompt_id']
                require(any(t == 'execution_success' and d.get('prompt_id') == pid
                            for t, d in status_messages), 'Request did not execute successfully')
                require(not any(t in ('execution_error', 'execution_interrupted') or
                                (t == 'execution_cached' and d.get('nodes'))
                                for t, d in status_messages), 'Failed or cached execution')
                state = self.inspect_state()
                require(state['fault'] is False, 'Fault after request')
                name = self.active['name']
                write_exclusive(self.run_dir / ('resolution-after-' + name + '.json'),
                                {**self._metadata('request', name), **self.active,
                                 'end_ns': time.time_ns(), 'state': state})
                self.completed.append(name)
                self.active = None
            except BaseException as error:
                self.halt(error)
                raise

    def advance(self, target, evidence_path=None, evidence_sha256=None):
        with self.lock:
            self.healthy()
            try:
                require(self.active is None and target in PHASES and
                        PHASES.index(target) == PHASES.index(self.phase) + 1,
                        'Phase transition is not the next barrier')
                state = self.inspect_state()
                require(state['fault'] is False, 'Fault at transition')
                require_quiescent(state, no_tails=True)
                if target in ('reference_verified', 'candidate_verified'):
                    expected_phases = ('native-reference', 'native-repeat') if target == 'reference_verified' else ('candidate-check',)
                    require(all(r['name'] in self.completed for r in self.plan['requests']
                                if r['phase'] in expected_phases), 'Required request executions incomplete')
                    raw = read_regular(evidence_path)
                    require(digest(raw) == evidence_sha256, 'Evidence hash changed')
                    # Verifier is supplied only by reviewed sealed integration; no bool shortcut.
                    checked = self.verifiers[target](evidence_path, evidence_sha256)
                    require(checked['plan_sha256'] == PLAN_SHA256 and
                            checked['runtime_manifest_sha256'] == self.runtime_sha and
                            checked['server_identity_sha256'] == self.identity_sha,
                            'Verified evidence belongs to another runtime')
                    if target == 'reference_verified':
                        require(state['sampler_routes'] == 0 and state['lean_state'] == 0 and
                                state['decode_replicas'] == 0, 'Native evidence came after optimized state')
                        self.references_sha = evidence_sha256
                    else:
                        require(checked['reference_receipt_sha256'] == self.references_sha,
                                'Candidate compared against different references')
                        self.candidate_sha = evidence_sha256
                old = self.phase
                write_exclusive(self.run_dir / ('resolution-phase-' + target + '.json'),
                                {'from': old, 'to': target, 'evidence_sha256': evidence_sha256,
                                 'state': state, 'time_ns': time.time_ns(),
                                 **self._metadata('barrier', target)})
                self.phase = target
            except BaseException as error:
                self.halt(error)
                raise


def configure(*args, **kwargs):
    global _authority
    require(_authority is None, 'Authority may only be configured once')
    _authority = Authority(*args, **kwargs)
    return _authority


def require_phase(role, qualification_id, run_name):
    require(_authority is not None, 'No sealed resolution authority configured')
    return _authority.require_phase(role, qualification_id, run_name)


def auxiliary_metadata():
    """Labels for asynchronous receipts; never grants numerical authorization."""
    if _authority is None:
        return None
    with _authority.lock:
        result = _authority._metadata('auxiliary', None)
        result.update(output_parity_claimed=False, halted=_authority.failed is not None)
        return result
