"""Packet123 streaming authority (installed as ltx_resolution_session). No device imports.

Packet123 (measurement only, no behaviour change): `healthy()` counts its calls and the time it spends (most
of it is the canonical-JSON SHA-256 of the in-memory plan, the plan-identity invariant) in `health_stats`;
each committed chunk records its `commit_ns` in the chain state, so the successor's receipt can split the
receipt -> next-submit turnaround. The launch's server-side options (snapshot mode, decoder-graph pool cap)
are carried for the status route only; they are not part of the variant or the qualification id.

Packet117: the launch variant also carries the three frame-anchor levers (anchor_decode, bencode_overlap,
prep_ahead); every request names them and must equal the launch. `wait_committed(name)` lets the decode
thread wait (bounded) for a chunk's receipt commit (prep-ahead starts the successor's stage-A encode then).

Order: two fixed setup graphs, then nine fixed qualification chunks (eager chain,
graph-replay chain, exact repeat of the graph chain in the streaming graph form),
then an explicit verdict. Only a passed verdict opens the unbounded streaming
phase. The stream is ONE anchor chain: stream_seq 0 is the only unanchored
request and every later chunk must name the anchor hash of stream_seq-1. The
prompt may change at any chunk. A stream chunk flagged reset (stream_seq > 0, packet113)
is admitted as an unanchored chunk in the stream_seq 0 form; it still takes the next
stream_seq and the chain restarts from its anchor. Since packet114 the anchor kind and the
chunk length (49 or 97) are launch parameters and part of the variant that selects the
pinned qualification graphs; packet115 added the mixed and guide anchor kinds; packet116 makes
frame the default anchor and adds the decoder-graph launch parameter (LTX_DECODER_GRAPH) to the
variant.
With the mixed anchor the chain anchor is the latent file; the decoded frame its stage B
also needs is bound to the predecessor's run name through the decode thread's record
(integration.mixed_condition_b). Anything else is refused before it is queued. Any failure
inside an admitted request latches the authority: all later requests are refused, nothing
is retried and no process is touched.
"""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import marshal
import threading
import time

import stream_contract as contract

PLAN_SHA256 = '0d24d0ff5446de8445d9774dd20057aaa284e34c2bedba0baba186b3b8af82ba'
MODE = contract.COMPARISON_MODE
PHASES = ('stream_setup', 'stream_qualification', 'stream')
ROUTES = 48
_authority = None


class Refusal(RuntimeError):
    """A request refused before it was queued. Not a fault; nothing is latched."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


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
    canonical(value)
    return value


def _safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe evidence path')
    return path


def read_regular(path, limit=8 * 1024 ** 2):
    path = _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size <= limit, 'Nonregular, linked or oversized evidence')
        raw = stream.read(limit + 1)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(raw) == before.st_size and identity(before) ==
                identity(os.fstat(stream.fileno())) == identity(path.lstat()),
                'Evidence changed during read')
    return raw


def write_exclusive(path, value):
    path = _safe_path(path)
    raw = canonical(value) + b'\n'
    import evidence_publication
    evidence_publication.publish_bytes(path, raw)
    return digest(raw)


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


def load_plan(plan_path):
    envelope = strict_json(read_regular(plan_path))
    require(type(envelope) is dict and set(envelope) == {'plan', 'plan_sha256'} and
            envelope['plan_sha256'] == PLAN_SHA256 == digest(canonical(envelope['plan'])),
            'Not the reviewed packet123 stream plan')
    return envelope['plan']


class StreamAuthority:
    def __init__(self, plan_path, runtime_manifest_sha256, server_identity_sha256,
                 run_dir, inspect_state, text_reuse, frames, placement=contract.DEFAULT_PLACEMENT,
                 anchor=contract.DEFAULT_ANCHOR, decoder_graph=contract.DEFAULT_DECODER_GRAPH, levers=None,
                 server_options=None):
        self.health_lock = threading.Lock()
        self.health_stats = {'calls': 0, 'seconds': 0.0, 'plan_digest_seconds': 0.0}   # packet123, measurement only
        self.plan = load_plan(plan_path)
        # Canonical SHA is verified by load_plan before caching the typed tree encoding.
        # marshal v2 has no reference-count-dependent reference flags; it compares
        # typed values only. Never load untrusted marshal bytes.
        self._plan_binary_guard = ((server_options or {}).get('storage_scan_mode', 'request') == 'background')
        self._plan_binary = marshal.dumps(self.plan, 2) if self._plan_binary_guard else None
        require(frames in contract.FRAME_CHOICES and type(frames) is int, 'frames must be 49, 97, 121 or 145')
        require(placement in contract.PLACEMENTS, 'Unknown placement')
        require(anchor in contract.ANCHORS, 'Unknown anchor mode')
        require(decoder_graph in contract.DECODER_GRAPH_CHOICES and type(decoder_graph) is int,
                'decoder_graph must be 0 or 1')
        self.frames, self.placement, self.anchor = frames, placement, anchor
        self.decoder_graph = decoder_graph
        self.levers = contract._levers(anchor, *(levers if levers is not None else (None, None, None)))
        self.anchor_decode, self.bencode_overlap, self.prep_ahead = self.levers
        self.variant = contract.variant(frames, placement, anchor, decoder_graph, *self.levers)
        self.qid = contract.qualification_id(frames, placement, anchor, decoder_graph, *self.levers)
        require(self.plan['qualification_ids'][self.variant] == self.qid, 'Qualification differs')
        for value in (runtime_manifest_sha256, server_identity_sha256):
            require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'Missing trusted identity')
        require(callable(inspect_state), 'Trusted state inspector required')
        require(text_reuse in (0, 1) and type(text_reuse) is int, 'text_reuse must be 0 or 1')
        self.run_dir = _safe_path(run_dir)
        require(self.run_dir.is_dir(), 'Run directory missing')
        self.receipt_dir = self.run_dir / 'receipts'
        self.anchor_dir = self.run_dir / 'anchors'
        for directory in (self.receipt_dir, self.anchor_dir):
            require(directory.is_dir() and not directory.is_symlink(), 'Evidence directory missing')
        self.text_reuse = text_reuse
        self.setup_rows = list(self.plan['setup'])
        self.qualification_rows = list(self.plan['qualification'])
        require([r['kind'] for r in self.setup_rows] == ['window-probe', 'prepare'] and
                len(self.qualification_rows) == 9, 'Plan request inventory differs')
        for row in self.setup_rows:
            require(digest(canonical(row['graph'])) == row['graph_sha256'], 'Setup graph pin differs')
        self.qualification_params = contract.qualification_params(frames, text_reuse, placement, anchor,
                                                                  decoder_graph, *self.levers)
        for row, params in zip(self.qualification_rows, self.qualification_params):
            graph = contract.build_chunk_graph(params)
            require(row['name'] == contract.run_name(params) and
                    row['graph_sha256'][self.variant + '/%d' % text_reuse] == digest(canonical(graph)),
                    'Qualification graph pin differs: ' + row['name'])
        self.requests = {r['name']: dict(r, phase='native-setup') for r in self.setup_rows}
        self.runtime_sha, self.identity_sha = runtime_manifest_sha256, server_identity_sha256
        self.inspect_state = inspect_state
        self.phase = 'stream_setup'
        self.lock = threading.RLock()
        self.active, self._active_signature = None, None
        self.failed, self.halt_receipt_error = None, None
        self.completed, self.prompt_ids, self.completed_prompt_ids = [], set(), set()
        self.request_prompt_ids = {}
        self.owner_thread = None
        self.chains = {}           # qualification scene id or 'stream' -> last committed chunk
        self.stream_seq_next = 0
        self.stream_completed = 0
        self.verdict_sha = None
        self.pending_receipt = None
        self.receipts = {}         # qualification receipts (nine, kept for the verdict)
        self.stream_receipts = {}
        self._busy = None
        self.committed = threading.Condition(self.lock)   # packet117: notified after every receipt commit
        self.committed_names = []                         # the newest 64 committed chunk names
        # Packet123: server-side launch options (status only; not in the variant or the qualification id).
        self.server_options = dict(server_options or {})

    # -- invariants ---------------------------------------------------------
    def healthy(self):
        started = time.perf_counter()
        require(self.failed is None, 'Session halted: ' + str(self.failed))
        planned = time.perf_counter()
        if self._plan_binary_guard:
            try:
                binary = marshal.dumps(self.plan, 2)
            except (ValueError, TypeError):
                binary = None
            # Equal typed encodings prove the sealed JSON tree unchanged. A change
            # (including benign alias/order changes) still takes the original gate.
            same = binary is not None and binary == self._plan_binary
            if not same:
                same = digest(canonical(self.plan)) == PLAN_SHA256
        else:
            same = digest(canonical(self.plan)) == PLAN_SHA256
        digested = time.perf_counter()
        with self.health_lock:     # packet123: measurement only (the checks below are unchanged)
            self.health_stats['calls'] += 1
            self.health_stats['plan_digest_seconds'] += digested - planned
        require(self.phase in PHASES and same,
                'Authority plan/phase changed')
        fixed = [r['name'] for r in self.setup_rows] + [r['name'] for r in self.qualification_rows]
        prefix = self.completed[:len(fixed)]
        require(prefix == fixed[:len(prefix)], 'Completion order changed')
        if self.active is not None:
            require(canonical(self.active) == self._active_signature, 'Active request changed')
        with self.health_lock:
            self.health_stats['seconds'] += time.perf_counter() - started

    def health_snapshot(self):
        """Packet123: a copy of the healthy() counters (the runtime reports per-chunk differences)."""
        with self.health_lock:
            return dict(self.health_stats)

    def halt(self, error):
        with self.lock:
            if self.failed is None:
                self.failed = str(error)[:4000]
                write_exclusive(self.run_dir / 'stream-halt.json', {
                    'schema': 'ltx.stream123-halt.v1', 'reason': self.failed,
                    'phase': self.phase, 'active': self.active, 'time_ns': time.time_ns(),
                    'completed_requests': len(self.completed), 'stream_completed': self.stream_completed})

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
                'qualification_id': self.qid, 'comparison_mode': MODE,
                'plan_sha256': PLAN_SHA256, 'runtime_manifest_sha256': self.runtime_sha,
                'server_identity_sha256': self.identity_sha,
                'reference_receipt_sha256': self.verdict_sha,
                'candidate_receipt_sha256': None}

    def require_phase(self, role, qualification_id, run_name):
        with self._operation('require_phase'):
            require(role in ('text', 'candidate'), 'Stream authority refuses role ' + str(role))
            require(qualification_id == self.qid and self.active is not None and
                    self.active['name'] == run_name, 'No matching active request')
            return self._metadata(role, run_name)

    # -- expected optimized state -------------------------------------------
    def graph_chain_started(self):
        first = self.qualification_rows[3]['name']
        return first in self.completed or (self.active is not None and self.active['name'] == first)

    def expected_routes(self):
        """'absent', 'installing' (first graph request) or 'pinned'."""
        first = self.qualification_rows[3]['name']
        if first in self.completed:
            return 'pinned'
        if self.active is not None and self.active['name'] == first:
            return 'installing'
        return 'absent'

    def expected_frozen(self):
        return self.phase == 'stream'

    def check_state(self, state, executing=False):
        require(type(state) is dict and state.get('fault') is False, 'Device or experiment fault')
        require(all(key in state for key in ('preview_pending', 'preview_failures', 'captures_frozen',
                                             'loads_frozen', 'sampler_routes')), 'Incomplete observation')
        require(all(type(state[k]) is int and state[k] == 0 for k in ('lean_state', 'decode_replicas')),
                'Lean memo or decoder replica present')
        routes = state['sampler_routes']
        expected = self.expected_routes()
        allowed = {'absent': (0,), 'installing': (0, ROUTES), 'pinned': (ROUTES,)}[expected]
        require(type(routes) is int and routes in allowed,
                'Sampler graph route count %r outside %s state' % (routes, expected))
        require(state['captures_frozen'] is self.expected_frozen() and state['loads_frozen'] is False,
                'Capture freeze state differs from phase')
        quiet = state
        if executing:
            require(type(state['queue_running']) is int and 0 <= state['queue_running'] <= 1,
                    'Overlapping prompt execution')
            quiet = dict(state, queue_running=0)
        require_quiescent(quiet, no_tails=True)
        return copy.deepcopy(state)

    # -- request classification (non-mutating) ------------------------------
    def classify(self, graph):
        if self.phase == 'stream_setup':
            index = len(self.completed)
            require(index < 2, 'Setup already complete')
            row = self.setup_rows[index]
            if digest(canonical(graph)) != row['graph_sha256']:
                raise Refusal('order', 'Next request must be setup graph ' + row['name'])
            return {'name': row['name'], 'kind': row['kind'], 'params': None}
        try:
            params = contract.parse_chunk_graph(graph, self.frames, self.placement, self.anchor,
                                                self.decoder_graph, self.levers)
        except ValueError as error:
            raise Refusal('contract', str(error))
        name = contract.run_name(params)
        if self.phase == 'stream_qualification':
            index = len(self.completed) - 2
            if index >= 9:
                raise Refusal('not-streaming', 'Qualification requests are done; the verdict action is next')
            row = self.qualification_rows[index]
            if params != self.qualification_params[index] or name != row['name']:
                raise Refusal('order', 'Next qualification request is ' + row['name'])
            self._check_chain(params, params['scene_id'])
            return {'name': name, 'kind': params['kind'], 'params': params, 'chain': params['scene_id']}
        if params['kind'] != 'stream':
            raise Refusal('order', 'Only stream chunks are admitted after qualification')
        if params['stream_seq'] != self.stream_seq_next:
            raise Refusal('order', 'stream_seq must be %d' % self.stream_seq_next)
        self._check_chain(params, 'stream')
        return {'name': name, 'kind': 'stream', 'params': params, 'chain': 'stream'}

    def _check_chain(self, params, chain):
        state = self.chains.get(chain)
        if params['chunk_index'] == 0:
            if state is not None:
                raise Refusal('order', 'Chain %s already started; only its next chunk is admitted' % chain)
            if params['reuse_text']:
                raise Refusal('text-reuse-rule', 'An unanchored chunk always encodes its prompt')
            return
        if state is None or state['last_chunk'] != params['chunk_index'] - 1:
            raise Refusal('order', 'Chain %s expects chunk %s next' % (
                chain, 0 if state is None else state['last_chunk'] + 1))
        if params['reset']:
            # Client-requested chain reset: unanchored, fresh encode. A named predecessor is
            # recorded, not consumed; a wrong one still shows a client bug and is refused.
            pred = params['predecessor_anchor_sha256']
            if pred and pred != state['anchor_sha256']:
                raise Refusal('stale-anchor', 'A reset chunk may name only the current anchor of %s (or nothing)'
                              % state['run_name'])
            if params['reuse_text']:
                raise Refusal('text-reuse-rule', 'A reset chunk always encodes its prompt')
            return
        if params['kind'] == 'stream' and params['predecessor_anchor_sha256'] != state['anchor_sha256']:
            raise Refusal('stale-anchor', 'predecessor_anchor_sha256 is not the anchor of %s' % state['run_name'])
        same_prompt = contract.text_sha256(params['prompt']) == state['text_sha256']
        expected = int(bool(self.text_reuse) and same_prompt and params['kind'] != 'qualify-eager')
        if params['reuse_text'] != expected:
            raise Refusal('text-reuse-rule', 'reuse_text must be %d for this chunk (server text_reuse=%d, '
                          'prompt %s)' % (expected, self.text_reuse, 'unchanged' if same_prompt else 'changed'))

    def precheck(self, graph, queue_running_ids, queue_pending):
        """Middleware admission. Raises Refusal; never latches or mutates."""
        with self.lock:
            if self.failed is not None:
                raise Refusal('halted', 'Server halted: ' + self.failed)
            if self._busy is not None or self.active is not None or queue_pending != 0 or \
                    any(pid not in self.completed_prompt_ids for pid in queue_running_ids):
                raise Refusal('busy', 'A request is still executing or queued')
            if self.phase == 'stream_qualification' and len(self.completed) == 11:
                raise Refusal('not-streaming', 'Qualification verdict pending')
            return self.classify(graph)

    # -- executor hooks -----------------------------------------------------
    def begin(self, name, graph, prompt_id):
        with self._operation('begin'):
            require(self.active is None, 'Overlapping request')
            require(type(prompt_id) is str and prompt_id and prompt_id not in self.prompt_ids,
                    'Missing or reused prompt identity')
            ident = threading.get_ident()
            require(self.owner_thread in (None, ident), 'Prompt executor thread changed')
            descriptor = self.classify(graph)
            require(descriptor['name'] == name, 'Executor request name differs')
            state = self.check_state(self.inspect_state(), executing=True)
            self.owner_thread = ident
            self.prompt_ids.add(prompt_id)
            self.request_prompt_ids[name] = prompt_id
            self.active = {'name': name, 'prompt_id': prompt_id, 'kind': descriptor['kind'],
                           'params': descriptor['params'], 'chain': descriptor.get('chain'),
                           'start_ns': time.time_ns(), 'thread': ident}
            self._active_signature = canonical(self.active)
            if descriptor['params'] is None or descriptor['kind'] != 'stream':
                write_exclusive(self.run_dir / ('stream-before-' + name + '.json'),
                                {**self._metadata('request', name), **self.active, 'state': state})
            row = {'name': name, 'kind': descriptor['kind'], 'params': copy.deepcopy(descriptor['params'])}
            if descriptor['params'] is not None:
                previous = self.chains.get(descriptor['chain'])
                row['chain'] = descriptor['chain']
                row['predecessor'] = copy.deepcopy(previous) if descriptor['params']['chunk_index'] else None
            return row

    def stage_receipt(self, name, receipt):
        with self.lock:
            require(self.active is not None and self.active['name'] == name and self.pending_receipt is None,
                    'Receipt does not belong to the active request')
            canonical(receipt)
            self.pending_receipt = copy.deepcopy(receipt)

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
            state = self.check_state(self.inspect_state(), executing=True)
            name, kind, params = self.active['name'], self.active['kind'], self.active['params']
            if params is not None:
                receipt = self.pending_receipt
                require(type(receipt) is dict and receipt.get('run_name') == name and
                        receipt.get('prompt_id') == pid, 'Chunk receipt missing for ' + name)
                anchor = receipt['anchor_out']
                path = self.receipt_dir / ('receipt-' + name + '.json')
                commit_started = time.time_ns()
                # The exclusive file becomes readable before fsync returns; route response-ready
                # timestamps can precede commit_written_ns. Timing retains that ordering.
                sha = write_exclusive(path, {**receipt, 'committed': True,
                                             'commit_ns': commit_started})
                chain = self.active['chain']
                previous = self.chains.get(chain)
                commit_ns = time.time_ns()
                self.chains[chain] = {
                    'commit_ns': commit_started, 'commit_written_ns': commit_ns,   # packet123: the predecessor commit for the turnaround split
                    'last_chunk': params['chunk_index'], 'run_name': name, 'anchor_kind': anchor['kind'],
                    'anchor_sha256': anchor['sha256'], 'anchor_path': anchor['path'],
                    'text_sha256': contract.text_sha256(params['prompt']),
                    'previous_anchor_path': previous['anchor_path'] if previous else None}
                target = self.receipts if kind != 'stream' else self.stream_receipts
                target[name] = {'path': str(path), 'sha256': sha}
                self.committed_names.append(name)
                del self.committed_names[:-64]
                self.committed.notify_all()
                if kind == 'stream':
                    self.stream_seq_next += 1
                    self.stream_completed += 1
                    stale = previous['previous_anchor_path'] if previous else None
                    if stale:
                        # Keep the two newest anchors of the stream chain; older ones
                        # can never be consumed again (strict predecessor rule).
                        _safe_path(stale).unlink()
            else:
                write_exclusive(self.run_dir / ('stream-after-' + name + '.json'), {
                    **self._metadata('request', name), **self.active, 'end_ns': time.time_ns(),
                    'state': state})
            self.pending_receipt = None
            if kind != 'stream':
                self.completed.append(name)
            self.completed_prompt_ids.add(pid)
            while len(self.stream_receipts) > 64:
                # Bounded in-memory index of recent stream receipts; all stay on disk.
                self.stream_receipts.pop(next(iter(self.stream_receipts)))
            if self.phase == 'stream_setup' and len(self.completed) == 2:
                self.phase = 'stream_qualification'
            self.active, self._active_signature = None, None

    def wait_committed(self, name, timeout_s):
        """Packet117 (decode thread): wait, bounded, until `name`'s receipt is committed. True when it is,
        False on the bound or after a halt (the caller then proceeds without the optional work)."""
        deadline = time.monotonic() + timeout_s
        with self.lock:
            while name not in self.committed_names:
                left = deadline - time.monotonic()
                if self.failed is not None or left <= 0:
                    return False
                self.committed.wait(min(left, 0.25))
            return True

    def accept_verdict(self, verdict, sha):
        with self._operation('accept_verdict'):
            require(self.phase == 'stream_qualification' and self.active is None and
                    len(self.completed) == 11, 'Verdict requires exactly the nine qualification requests')
            require(type(verdict) is dict and verdict.get('passed') is True and
                    verdict.get('plan_sha256') == PLAN_SHA256 and
                    re.fullmatch('[0-9a-f]{64}', sha or ''), 'Qualification verdict did not pass')
            self.verdict_sha = sha
            self.phase = 'stream'

    def status(self):
        with self.lock:
            return {'phase': self.phase, 'halted': self.failed, 'active': copy.deepcopy(self.active),
                    'completed_fixed_requests': list(self.completed), 'stream_completed': self.stream_completed,
                    'next_stream_seq': self.stream_seq_next, 'text_reuse': self.text_reuse,
                    'qualification_verdict_sha256': self.verdict_sha,
                    'last_stream_receipts': copy.deepcopy(list(self.stream_receipts.values())[-4:]),
                    'frames': self.frames, 'placement': self.placement, 'anchor': self.anchor,
                    'decoder_graph': self.decoder_graph, 'anchor_decode': self.anchor_decode,
                    'bencode_overlap': self.bencode_overlap, 'prep_ahead': self.prep_ahead,
                    'qualification_id': self.qid, 'server_options': dict(self.server_options),
                    'chain': (None if 'stream' not in self.chains else
                              {'last_stream_seq': self.chains['stream']['last_chunk'],
                               'last_run_name': self.chains['stream']['run_name'],
                               'anchor_sha256': self.chains['stream']['anchor_sha256'],
                               'prompt_sha256': self.chains['stream']['text_sha256']})}


def configure(*args, **kwargs):
    global _authority
    require(_authority is None, 'Authority may only be configured once')
    _authority = StreamAuthority(*args, **kwargs)
    return _authority


def require_phase(role, qualification_id, run_name):
    require(_authority is not None, 'No sealed stream authority configured')
    return _authority.require_phase(role, qualification_id, run_name)


def auxiliary_metadata():
    if _authority is None:
        return None
    with _authority.lock:
        result = _authority._metadata('auxiliary', None)
        result.update(output_parity_claimed=False, halted=_authority.failed is not None)
        return result
