"""Packet107: bounded timing metadata only; imports no tensor/driver library.

The caller supplies Event objects and existing streams. This module never waits,
synchronizes, reads a tensor, changes a queue, or catches backend exceptions.
"""
import copy
import hashlib
import math
from pathlib import Path
import re
import threading
import time

ELIGIBLE = frozenset(range(99907104, 99907110))
DEVICES = ('xpu:0', 'xpu:1')
MAX_OPS = 128
EVENTS_PER_DEVICE = 128
MAX_JOBS = 64
CLAIM_SCOPE = ('Two instrumented candidate jobs; second observed forward in each '
               'stage only. Stream intervals include submission gaps. No utilization, '
               'steady-state fraction, cross-device clock alignment, or FPS ceiling.')


class DisabledJob:
    selected = False
    recording = False

    def __init__(self, clip_index=None, worker_index=None, phase=None, reason='no-job', owner=None, audit=None):
        self.clip_index, self.worker_index = clip_index, worker_index
        self.phase, self.reason = phase, reason
        self.owner, self.audit, self.result = owner, audit, None

    def noop(self, *args, **kwargs):
        return None

    stage = block_enter = move_begin = move_d2h_end = wait_begin = wait_end = noop
    move_h2d_begin = move_end = fill_begin = fill_add = fill_end = noop
    move_alloc_begin = move_alloc_end = noop
    replay_begin = replay_end = noop

    def finish_after_existing_drains(self, success):
        if self.result is not None:
            return copy.deepcopy(self.result)
        self.result = {'schema': 'ltx.sparse-transport-job.v1', 'selected': False,
                'clip_index': self.clip_index, 'worker_index': self.worker_index,
                'phase': self.phase, 'disabled_reason': self.reason,
                'events_recorded': 0, 'operation_count': 0,
                'existing_drains_succeeded': bool(success)}
        if self.owner is not None:
            self.owner._finished(self.audit, self.result)
        return copy.deepcopy(self.result)


NOOP = DisabledJob()


class TraceManager:
    def __init__(self, workers, event_factory, identity, clock_ns=time.perf_counter_ns,
                 thread_info=None):
        if set(workers) != {0, 1}:
            raise ValueError('exactly two registered sampler workers required')
        for i, binding in workers.items():
            if (set(binding) != {'ident', 'name'} or type(binding['ident']) is not int
                    or binding['ident'] <= 0 or binding['name'] != 'ltx-sample-%d' % i):
                raise ValueError('invalid registered worker binding')
        if workers[0]['ident'] == workers[1]['ident']:
            raise ValueError('worker identities must differ')
        for field in ('plan_sha256', 'server_identity_sha256', 'source_sha256'):
            if not isinstance(identity.get(field), str) or not re.fullmatch('[0-9a-f]{64}', identity[field]):
                raise ValueError('missing identity binding: ' + field)
        self.workers, self.identity = copy.deepcopy(workers), copy.deepcopy(identity)
        self.event_factory, self.clock = event_factory, clock_ns
        self.thread_info = thread_info or (lambda: (threading.get_ident(), threading.current_thread().name))
        self.local, self.lock = threading.local(), threading.Lock()
        self.claims, self.receipts, self.disabled = {}, {}, {}
        # Keep at most two event pools alive even if a model/drain fails. No
        # destructor/lifetime assumption substitutes for an existing drain.
        self.retained_jobs = {}
        self.binding_failures = 0
        self.closed, self.audit_error = False, None
        self.audit = []

    def _finished(self, audit, result):
        with self.lock:
            if audit is not None:
                audit.update(finished=True, existing_drains_succeeded=result['existing_drains_succeeded'],
                             events_recorded=result['events_recorded'], selected=result['selected'])
            if not result['existing_drains_succeeded']:
                self.audit_error = self.audit_error or 'job-body-or-drain-failed'

    def invalidate(self, reason):
        with self.lock:
            if self.audit_error is None:
                self.audit_error = reason

    def begin_job(self, clip_index, worker_index, phase):
        if getattr(self.local, 'job', None) is not None:
            raise ValueError('nested sampler job; caller must clear context')
        ident, name = self.thread_info()
        binding = self.workers.get(worker_index)
        bound = binding == {'ident': ident, 'name': name}
        reason = 'outside-eligible-candidate'
        with self.lock:
            audit = None
            if len(self.audit) < MAX_JOBS:
                audit = {'clip_index': clip_index, 'worker_index': worker_index, 'phase': phase,
                         'thread_ident': ident, 'thread_name': name, 'finished': False,
                         'events_recorded': 0, 'selected': False}
                self.audit.append(audit)
            else:
                self.audit_error = 'job-audit-cap-exceeded'
            if not bound:
                self.binding_failures += 1
                self.audit_error = self.audit_error or 'worker-binding-mismatch'
                reason = 'worker-binding-mismatch'
            elif phase == 'candidate-check' and type(clip_index) is int and clip_index in ELIGIBLE:
                if self.closed:
                    self.audit_error = 'candidate-job-after-close'
                    reason = 'candidate-closed'
                elif worker_index not in self.claims and self.audit_error is None:
                    self.claims[worker_index] = clip_index
                    job = Job(self, clip_index, worker_index, phase, ident, name)
                    job.audit = audit
                    self.retained_jobs[worker_index] = job
                    audit['selected'] = True
                    self.local.job = job
                    return job
                else:
                    reason = 'worker-already-claimed' if worker_index in self.claims else 'diagnostic-invalid'
            # Fixed key set keeps even malformed/unknown phases bounded.
            category = phase if phase in ('candidate-check', 'timed-fast', 'timed', 'setup', 'native') else 'other'
            key = category + ':' + reason
            self.disabled[key] = self.disabled.get(key, 0) + 1
        job = DisabledJob(clip_index, worker_index, phase, reason, self, audit)
        self.local.job = job
        return job

    def current(self):
        return getattr(self.local, 'job', NOOP)

    def clear(self):
        # Clearing an exceptional/unfinished job does not touch the backend.
        job = self.current()
        if job is not NOOP and job.result is None:
            job.finish_after_existing_drains(False)
        if hasattr(self.local, 'job'):
            del self.local.job

    def census(self):
        with self.lock:
            return {'schema': 'ltx.sparse-transport-census.v1', 'identity': copy.deepcopy(self.identity),
                    'workers': copy.deepcopy(self.workers), 'claims': dict(self.claims),
                    'receipts': copy.deepcopy(self.receipts), 'disabled_counts': dict(self.disabled),
                    'binding_failures': self.binding_failures,
                    'candidate_closed': self.closed, 'audit_error': self.audit_error,
                    'jobs': copy.deepcopy(self.audit),
                    'active_jobs': sum(not j['finished'] for j in self.audit),
                    'phase_events': {phase: sum(j['events_recorded'] for j in self.audit if j['phase'] == phase)
                                     for phase in ('candidate-check', 'timed-fast', 'timed', 'setup', 'native')},
                    'phase_events_scope': 'Finalized jobs only; require active_jobs=0 at barriers.',
                    'complete': (set(self.receipts) == {0, 1} and not self.binding_failures and self.audit_error is None
                                 and all(j['finished'] and j.get('existing_drains_succeeded') for j in self.audit)
                                 and all(r['valid'] for r in self.receipts.values())),
                    'claim_scope': CLAIM_SCOPE}

    snapshot = census

    def close_candidate(self):
        with self.lock:
            self.closed = True
            if any(not j['finished'] for j in self.audit):
                self.audit_error = 'candidate-close-with-active-job'
        return self.census()


class Job:
    selected = True

    def __init__(self, owner, clip_index, worker_index, phase, ident, name):
        self.owner, self.clip_index, self.worker_index, self.phase = owner, clip_index, worker_index, phase
        self.ident, self.name = ident, name
        self.error, self.result = None, None
        self.stage_name, self.forward, self.block = None, -1, None
        self.active = False
        self.stage_seen, self.coverage = [], {}
        self.ops, self.pending, self.partitions = [], [], {}
        self.used = {d: 0 for d in DEVICES}
        self.recorded = 0
        self.audit, self.replay_token = None, None
        # Constructor allocation only; no record/query/wait/warmup. The backend
        # may still lazily initialize an event on its first record.
        self.pools = {d: [owner.event_factory(d) for _ in range(EVENTS_PER_DEVICE)] for d in DEVICES}

    def fail(self, reason):
        if self.error is None:
            self.error = reason
        self.active = False
        self.owner.invalidate(reason)

    @property
    def recording(self):
        return self._enabled()

    def _enabled(self):
        if self.error is not None or self.result is not None:
            return False
        if self.owner.audit_error is not None:
            self.fail('global-diagnostic-invalid')
            return False
        if self.owner.closed:
            self.fail('candidate-closed-during-job')
            return False
        if self.owner.thread_info() != (self.ident, self.name):
            self.fail('job-thread-binding-changed')
            return False
        return self.active

    def _check_finished_forward(self):
        if self.stage_name in self.coverage:
            c = self.coverage[self.stage_name]
            if c != {'blocks': 48, 'replays': 48, 'moves': 4, 'partitions': 2}:
                self.fail('selected-forward-coverage-incomplete')
            if self.pending or self.partitions or self.replay_token is not None:
                self.fail('unclosed-operation')

    def stage(self, name):
        if self.error is not None:
            return
        self._check_finished_forward()
        if name not in ('a', 'b') or self.stage_seen != ([] if name == 'a' else ['a']):
            self.fail('stage-order-mismatch')
            return
        self.stage_seen.append(name)
        self.stage_name, self.forward, self.block, self.active = name, -1, None, False

    def block_enter(self, index, device, primary, last, chain, img_components):
        if self.error is not None:
            return
        if index == 0:
            if self.active:
                self._check_finished_forward()
            self.forward += 1
            self.active = self.forward == 1
            self.block = None
            if self.active:
                self.coverage[self.stage_name] = {'blocks': 0, 'replays': 0, 'moves': 0, 'partitions': 0}
        if not self._enabled():
            return
        if (self.stage_name not in ('a', 'b') or type(index) is not int
                or index != (0 if self.block is None else self.block + 1)
                or not 0 <= index < 48 or device != ('xpu:0' if index < 23 else 'xpu:1')
                or primary != 'xpu:0' or last is not (index == 47)
                or type(chain) is not int or chain != 1 or img_components != 2):
            self.fail('block-route-mismatch')
            return
        self.block = index
        self.coverage[self.stage_name]['blocks'] += 1

    def _reserve(self, kind, devices, **fields):
        if not self._enabled():
            return None
        if len(self.ops) >= MAX_OPS or any(d not in DEVICES or self.used[d] + devices.count(d) > EVENTS_PER_DEVICE for d in devices):
            self.fail('trace-cap-exceeded')
            return None
        events = []
        for d in devices:
            events.append(self.pools[d][self.used[d]])
            self.used[d] += 1
        op = {'kind': kind, 'stage': self.stage_name, 'forward_ordinal': self.forward + 1,
              'block': self.block, 'events': events, 'event_devices': devices,
              'recorded_indices': [], 'cpu_start_ns': self.owner.clock(), **fields}
        self.ops.append(op)
        self.pending.append(op)
        return op

    def _record(self, op, index, stream):
        if not self._enabled():
            return
        if str(stream.device) != op['event_devices'][index]:
            self.fail('event-stream-device-mismatch')
            return
        op['events'][index].record(stream)  # Backend errors propagate unchanged.
        op['recorded_indices'].append(index)
        self.recorded += 1

    def _token(self, op, kind, expected):
        if op is None or not self._enabled():
            return False
        if not any(op is p for p in self.pending) or op['kind'] != kind or op['recorded_indices'] != expected:
            self.fail('operation-token-order-mismatch')
            return False
        return True

    def _close(self, op):
        op['cpu_end_ns'] = self.owner.clock()
        self.pending = [p for p in self.pending if p is not op]

    def move_begin(self, tag, src, dst, shape, dtype, nbytes, src_stream):
        if not self._enabled():
            return None
        # Other arguments/custom movers are deliberately outside scope.
        if isinstance(tag, tuple) and tag and tag[0] not in ('img', 'out'):
            return None
        c = self.coverage[self.stage_name]
        ordinal = c['moves']
        expected = ('img', ordinal) if ordinal < 2 else ('out', ordinal - 2)
        if (tag != expected or ordinal >= 4
                or c['replays'] != (23 if ordinal < 2 else 48)
                or (self.block, src, dst) != ((23, 'xpu:0', 'xpu:1') if ordinal < 2 else (47, 'xpu:1', 'xpu:0'))
                or type(nbytes) is not int or nbytes <= 0
                or not isinstance(shape, (tuple, list)) or len(shape) > 8
                or any(type(x) is not int or x <= 0 for x in shape)
                or not isinstance(dtype, str) or len(dtype) > 40):
            self.fail('activation-move-scope-mismatch')
            return None
        op = self._reserve('move', [src, src, dst, dst], tag=list(tag), src=src, dst=dst,
                           shape=list(shape), dtype=dtype, nbytes=nbytes)
        if op is not None:
            c['moves'] += 1
            self._record(op, 0, src_stream)
        return op

    def move_d2h_end(self, op, stream):
        if self._token(op, 'move', [0]):
            self._record(op, 1, stream)

    def wait_begin(self, op):
        if self._token(op, 'move', [0, 1]):
            if 'wait_start_ns' in op:
                self.fail('duplicate-host-wait')
            else:
                op['wait_start_ns'] = self.owner.clock()

    def wait_end(self, op):
        if self._token(op, 'move', [0, 1]):
            if 'wait_start_ns' not in op or 'wait_end_ns' in op:
                self.fail('host-wait-order-mismatch')
            else:
                op['wait_end_ns'] = self.owner.clock()

    def move_h2d_begin(self, op, stream):
        if self._token(op, 'move', [0, 1]):
            if 'wait_end_ns' not in op or 'alloc_end_ns' not in op:
                self.fail('missing-existing-host-wait-or-allocation')
            else:
                self._record(op, 2, stream)

    def move_alloc_begin(self, op):
        if self._token(op, 'move', [0, 1]):
            if 'wait_end_ns' not in op or 'alloc_start_ns' in op:
                self.fail('allocation-order-mismatch')
            else:
                op['alloc_start_ns'] = self.owner.clock()

    def move_alloc_end(self, op):
        if self._token(op, 'move', [0, 1]):
            if 'alloc_start_ns' not in op or 'alloc_end_ns' in op:
                self.fail('allocation-end-order-mismatch')
            else:
                op['alloc_end_ns'] = self.owner.clock()

    def move_end(self, op, stream):
        if self._token(op, 'move', [0, 1, 2]):
            self._record(op, 3, stream)
            self._close(op)

    def fill_begin(self, device, stream):
        if not self._enabled():
            return None
        if (device != ('xpu:0' if self.block < 23 else 'xpu:1')
                or any(p['kind'] in ('fill', 'move') for p in self.pending)
                or self.coverage[self.stage_name]['replays'] != self.block):
            self.fail('fill-scope-mismatch')
            return None
        if any(p['kind'] == 'fill' and p['stage'] == self.stage_name and p['block'] == self.block for p in self.ops):
            self.fail('duplicate-fill-call')
            return None
        op = self._reserve('fill', [device, device], device=device, tensor_count=0, nbytes=0)
        if op is not None:
            self._record(op, 0, stream)
        return op

    def fill_add(self, op, nbytes):
        if self._token(op, 'fill', [0]):
            if type(nbytes) is not int or nbytes <= 0:
                self.fail('invalid-fill-bytes')
            else:
                op['tensor_count'] += 1
                op['nbytes'] += nbytes

    def fill_end(self, op, stream):
        if self._token(op, 'fill', [0]):
            if not op['tensor_count']:
                self.fail('empty-fill-instrumented')
            else:
                self._record(op, 1, stream)
                self._close(op)

    def replay_begin(self, index, device, stream):
        if not self._enabled():
            return None
        c = self.coverage[self.stage_name]
        if (self.replay_token is not None or index != self.block or index != c['replays']
                or device != ('xpu:0' if index < 23 else 'xpu:1')):
            self.fail('replay-order-mismatch')
            return None
        if index in (0, 23):
            op = self._reserve('partition', [device, device], device=device,
                               first_block=index, last_block=22 if index == 0 else 47,
                               replay_cpu_ns=0, replay_count=0)
            if op is None:
                return None
            self.partitions[device] = op
            self._record(op, 0, stream)
        elif device not in self.partitions:
            self.fail('missing-partition-start')
            return None
        self.replay_token = (self.partitions[device], index, self.owner.clock())
        return self.replay_token

    def replay_end(self, token, index, device, stream):
        if token is None or not self._enabled():
            return
        op, saved_index, start = token
        if (token is not self.replay_token or saved_index != index or index != self.block or device not in self.partitions
                or self.partitions[device] is not op or index != self.coverage[self.stage_name]['replays']):
            self.fail('replay-end-mismatch')
            return
        op['replay_cpu_ns'] += self.owner.clock() - start
        self.replay_token = None
        op['replay_count'] += 1
        self.coverage[self.stage_name]['replays'] += 1
        if index in (22, 47):
            self._record(op, 1, stream)
            self._close(op)
            del self.partitions[device]
            self.coverage[self.stage_name]['partitions'] += 1

    def finish_after_existing_drains(self, success):
        if self.result is not None:
            return copy.deepcopy(self.result)
        if self.owner.audit_error is not None and self.error is None:
            self.fail('global-diagnostic-invalid')
        if not success:
            self.fail('existing-drains-not-confirmed')
        self._check_finished_forward()
        if self.stage_seen != ['a', 'b'] or set(self.coverage) != {'a', 'b'}:
            self.fail('missing-selected-stage-forward')
        out = []
        for op in self.ops:
            row = {k: copy.deepcopy(v) for k, v in op.items() if k != 'events'}
            if self.error is None:
                if op['recorded_indices'] != list(range(len(op['events']))):
                    self.fail('unpaired-events')
                    break
                elapsed = [op['events'][i].elapsed_time(op['events'][i + 1]) for i in range(0, len(op['events']), 2)]
                if any(not math.isfinite(x) or x < 0 for x in elapsed):
                    self.fail('invalid-event-duration')
                    break
                row['elapsed_ms'] = elapsed
                row['cpu_span_ns'] = op['cpu_end_ns'] - op['cpu_start_ns']
                if op['kind'] == 'move':
                    row.update(d2h_ms=elapsed[0], h2d_ms=elapsed[1],
                               host_wait_ns=op['wait_end_ns'] - op['wait_start_ns'],
                               destination_allocation_ns=op['alloc_end_ns'] - op['alloc_start_ns'])
                else:
                    row['stream_ms'] = elapsed[0]
            out.append(row)
        self.result = {'schema': 'ltx.sparse-transport-job.v1', 'selected': True,
                       'identity': copy.deepcopy(self.owner.identity), 'clip_index': self.clip_index,
                       'worker_index': self.worker_index, 'thread_ident': self.ident, 'thread_name': self.name,
                       'phase': self.phase, 'valid': self.error is None, 'error': self.error,
                       'existing_drains_succeeded': bool(success), 'events_reserved': dict(self.used),
                       'events_recorded': self.recorded, 'operation_count': len(self.ops),
                       'coverage': copy.deepcopy(self.coverage), 'operations': out, 'claim_scope': CLAIM_SCOPE}
        with self.owner.lock:
            self.owner.receipts[self.worker_index] = copy.deepcopy(self.result)
        self.owner._finished(self.audit, self.result)
        self.active = False
        return copy.deepcopy(self.result)


_manager = None
_configure_lock = threading.Lock()
_source_sha256 = None
_prepared_identity = None


def prepare(identity):
    global _source_sha256, _prepared_identity
    with _configure_lock:
        if _source_sha256 is None:
            _source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        identity = dict(identity)
        supplied = identity.setdefault('source_sha256', _source_sha256)
        if supplied != _source_sha256:
            raise ValueError('trace source binding mismatch')
        for field in ('plan_sha256', 'server_identity_sha256', 'source_sha256'):
            if not isinstance(identity.get(field), str) or not re.fullmatch('[0-9a-f]{64}', identity[field]):
                raise ValueError('missing identity binding: ' + field)
        if _prepared_identity is not None and _prepared_identity != identity:
            raise ValueError('trace identity cannot be replaced')
        _prepared_identity = copy.deepcopy(identity)
        return copy.deepcopy(identity)


def configure(workers, event_factory, identity=None):
    global _manager
    if identity is not None:
        identity = prepare(identity)
    elif _prepared_identity is None:
        raise ValueError('prepare identity before deferred worker binding')
    else:
        identity = copy.deepcopy(_prepared_identity)
    with _configure_lock:
        if _manager is not None:
            if _manager.workers != workers or _manager.identity != identity:
                raise ValueError('trace manager cannot be reconfigured')
            return _manager
        _manager = TraceManager(workers, event_factory, identity)
        return _manager


def begin_job(clip_index, worker_index, phase):
    if _manager is None:
        raise ValueError('trace manager not configured')
    return _manager.begin_job(clip_index, worker_index, phase)


def current():
    return NOOP if _manager is None else _manager.current()


def clear():
    if _manager is not None:
        _manager.clear()


def census():
    return {'configured': False, 'complete': False} if _manager is None else _manager.census()


snapshot = census


def close_candidate():
    if _manager is None:
        return {'configured': False, 'complete': False, 'error': 'no-worker-binding'}
    return _manager.close_candidate()
