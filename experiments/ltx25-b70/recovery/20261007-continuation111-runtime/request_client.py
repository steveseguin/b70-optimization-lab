#!/usr/bin/env python3
"""Finite, one-attempt request client; never starts, stops, retries or signals a server."""
import argparse
import asyncio
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import uuid

# CPU-only protocol primitives; no import of model/runtime modules.
import re
import stat
from types import SimpleNamespace
PLAN_SHA = '7944f8701244bd386c41bc5cdd6c4e9df1ea8fcf4d9dedf91e249f476105b2c5'
QUALIFICATION_ID = '705fa3d73c603833591ac5ae13b5f2d4d79c329b860794ff4d061c71e8942266'
MIN_FREE = 50 * 1024**3
WRITE_ALLOWANCE = 4 * 1024**3
CAPTURE_CAP = 6
ATTEMPT_CAP = 8
MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'Invalid SHA256')
    return value


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    def bad(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Absolute literal path required')
    for part in [path, *path.parents]:
        require(not part.is_symlink(), 'Symlink path refused')
    return path


def read_file(path):
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 16*1024**2,
                'Not a bounded single-link regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(16*1024**2 + 1)
        after = os.fstat(fd)
        key = lambda x: (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_nlink)
        require(key(before) == key(after) == key(path.lstat()) and len(raw) == before.st_size,
                'File changed while reading')
        return raw
    finally:
        os.close(fd)


G = SimpleNamespace(require=require, digest=digest, sha=sha, canonical=canonical,
                    strict_json=strict_json, safe_path=safe_path, read_file=read_file,
                    PLAN_SHA=PLAN_SHA, QUALIFICATION_ID=QUALIFICATION_ID)

def write_new(path, value):
    with G.safe_path(path).open('xb') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n')
        stream.flush(); os.fsync(stream.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def actual_process(identity):
    """Passive procfs only; no signal, driver query, or model operation."""
    pid = identity['pid']
    G.require(type(pid) is int and pid > 0, 'Invalid server PID')
    G.require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == identity['boot_id'], 'Server boot changed')
    fields = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
    G.require(fields[0] not in ('Z', 'X', 'x') and fields[19] == identity['proc_start_ticks'], 'Server process gone/reused')


def available(path):
    state = os.statvfs(path)
    return state.f_bavail * state.f_frsize


class AioTransport:
    """Fixed local endpoint. Dependencies/network are used only by explicit execution."""
    async def __aenter__(self):
        import aiohttp
        self.aiohttp = aiohttp
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        self.ws = None
        return self

    async def __aexit__(self, *exc):
        if self.ws is not None:
            await self.ws.close()
        await self.session.close()

    async def get(self, path):
        async with self.session.get('http://127.0.0.1:8188' + path) as response:
            response.raise_for_status(); return await response.json()

    async def subscribe(self, client_id):
        self.ws = await self.session.ws_connect('http://127.0.0.1:8188/ws', params={'clientId': client_id})
        hello = await self.ws.receive_json(timeout=10)
        G.require(hello.get('type') == 'status', 'Unexpected WebSocket handshake')

    async def submit(self, graph, client_id):
        async with self.session.post('http://127.0.0.1:8188/prompt',
                                     json={'prompt': graph, 'client_id': client_id}) as response:
            response.raise_for_status(); return await response.json()

    async def action(self, action):
        async with self.session.post('http://127.0.0.1:8188/ltx-resolution/action',
                                     json={'action': action}, timeout=self.aiohttp.ClientTimeout(total=600)) as response:
            response.raise_for_status(); return await response.json()

    async def receive(self, timeout):
        message = await self.ws.receive(timeout=timeout)
        if message.type == self.aiohttp.WSMsgType.TEXT:
            return G.strict_json(message.data)
        if message.type == self.aiohttp.WSMsgType.BINARY:
            return None  # Preview traffic is not request-execution evidence.
        raise RuntimeError('WebSocket disconnected; coordinator must inspect job')


class Client:
    def __init__(self, contract_path, contract_sha256, *, process_probe=actual_process, free_probe=available):
        self.contract_path = G.safe_path(contract_path)
        raw = G.read_file(self.contract_path)
        G.require(G.sha(raw) == G.digest(contract_sha256), 'Client contract hash differs')
        self.contract_sha = contract_sha256; self.contract = G.strict_json(raw); c = self.contract
        G.require(c.get('schema') == 'ltx.continuation111-request-client.v1' and c.get('plan_sha256') == G.PLAN_SHA, 'Client contract basis differs')
        G.require(c.get('min_free_bytes') == MIN_FREE and c.get('planned_write_bytes') == WRITE_ALLOWANCE and
                  type(c.get('max_captures')) is int and c['max_captures'] == CAPTURE_CAP and
                  type(c.get('max_attempts')) is int and c['max_attempts'] == ATTEMPT_CAP, 'Client budget contract differs')
        G.require(type(c.get('request_timeout_seconds')) is int and 1 <= c['request_timeout_seconds'] <= 1800,
                  'Unbounded request timeout')
        self.root = G.safe_path(c['root']); self.run = G.safe_path(c['server_run'])
        self.directory = G.safe_path(c['client_dir'])
        G.require(self.root.is_dir() and self.run.is_dir() and self.directory.parent.is_dir(), 'Client directories absent')
        G.require(os.stat(self.root).st_dev == os.stat(self.run).st_dev == os.stat(self.directory.parent).st_dev,
                  'Client evidence/run must use the admitted filesystem')
        requests = G.safe_path(self.root / 'requests')
        G.require(requests.is_dir() and requests.stat().st_dev == self.root.stat().st_dev,
                  'Request evidence filesystem differs')
        validation = G.safe_path(self.root / 'output/validation')
        if validation.exists():
            G.require(validation.is_dir() and validation.stat().st_dev == self.root.stat().st_dev,
                      'Tensor output filesystem differs')
        self.plan_path = G.safe_path(c['plan_path'])
        self.plan_raw = G.read_file(self.plan_path)
        envelope = G.strict_json(self.plan_raw)
        self.plan = envelope['plan']
        G.require(envelope['plan_sha256'] == PLAN_SHA == G.sha(G.canonical(self.plan)) and
                  self.plan['qualification_id'] == QUALIFICATION_ID, 'Unreviewed111 plan')
        self.rows = {r['name']: r for r in self.plan['requests']}
        self.ordered_names = self.plan['execution_order']
        G.require(len(self.rows) == ATTEMPT_CAP and
                  [r['name'] for r in self.plan['requests']] == self.ordered_names and
                  c['allowed_names'] == self.ordered_names and
                  sum(r['capture_role'] == 'full' for r in self.rows.values()) == CAPTURE_CAP,
                  'Fixed111 order/capture count differs')
        for row in self.rows.values():
            G.require(G.sha(G.canonical(row['graph'])) == row['graph_sha256'] and
                      row['client_checkpoint_policy'] == 'always', 'Pinned graph/policy differs')
        self.identity_raw = G.read_file(self.run / 'server-identity.json'); self.identity = G.strict_json(self.identity_raw)
        G.require(G.sha(self.identity_raw) == G.digest(c['server_identity_sha256']) and
                  self.identity['source_packet_manifest_sha256'] == G.digest(c['runtime_manifest_sha256']) and
                  self.identity['model_verification_sha256'] == MODEL_SHA, 'Client source/model/server identity differs')
        G.digest(self.identity['server_args_sha256'])
        G.require(type(self.identity.get('proc_start_ticks')) is str and self.identity['proc_start_ticks'].isdigit(),
                  'Server start ticks missing')
        self.process_probe = process_probe; self.free_probe = free_probe
        G.require(type(c.get('source_bindings')) is dict and c['source_bindings'] and
                  c.get('capture_guard_path') in c['source_bindings'] and
                  str(Path(__file__).resolve()) in c['source_bindings'] and
                  str(Path(__file__).resolve().with_name('campaign.py')) in c['source_bindings'],
                  'Missing sealed client/campaign source binding')
        G.require(G.safe_path(c['phase_observation_path']) == self.run / 'resolution-client-phase.json',
                  'Phase observation must be in the bound server run')
        self.manifest_path = G.safe_path(c['runtime_manifest_path'])
        self.check_fixed()

    def phase_observation(self, row):
        """Read trusted server observation; never create or advance a phase here."""
        raw = G.read_file(G.safe_path(self.contract['phase_observation_path']))
        value = G.strict_json(raw)
        G.require(value.get('schema') == 'ltx.resolution-client-phase.v1' and value.get('phase') == 'native_reference' and
                  value.get('plan_sha256') == G.PLAN_SHA and value.get('qualification_id') == G.QUALIFICATION_ID and
                  value.get('runtime_manifest_sha256') == self.contract['runtime_manifest_sha256'] and
                  value.get('server_identity_sha256') == self.contract['server_identity_sha256'] and
                  value.get('active_request') is None and value.get('fault') is False,
                  'Server phase observation refuses request')
        now = time.time_ns() // 1000000
        G.require(type(value.get('observed_at_ms')) is int and 0 <= now - value['observed_at_ms'] <= 30000,
                  'Server phase observation stale')
        return {'path': self.contract['phase_observation_path'], 'sha256': G.sha(raw), 'observation': value}

    def check_fixed(self):
        G.require(G.sha(G.read_file(self.contract_path)) == self.contract_sha, 'Client contract changed')
        G.require(not (self.root / 'FAULT.json').exists() and not (self.run / 'FAULT.json').exists() and not (self.run / 'resolution-halt.json').exists() and not (self.directory / 'HALT.json').exists(), 'Fault/halt present')
        G.require(G.read_file(self.run / 'server-identity.json') == self.identity_raw, 'Server identity changed')
        G.require(G.read_file(self.plan_path) == self.plan_raw, 'Pinned plan changed')
        G.require(G.sha(G.read_file(self.manifest_path)) == self.contract['runtime_manifest_sha256'],
                  'Runtime manifest changed')
        for path, digest in self.contract['source_bindings'].items():
            G.require(G.sha(G.read_file(G.safe_path(path))) == G.digest(digest), 'Sealed source changed')
        self.process_probe(self.identity)

    def checkpoint(self):
        self.check_fixed()
        now = self.free_probe(self.root)
        G.require(type(now) is int and now >= 0, 'Invalid filesystem reading')
        previous_storage = (self.state['charged_write_bytes'], self.state['last_available_bytes'])
        self.state['charged_write_bytes'] += max(0, self.state['last_available_bytes'] - now)
        self.state['last_available_bytes'] = now
        remaining = WRITE_ALLOWANCE - self.state['charged_write_bytes']
        G.require(remaining >= 0 and now >= MIN_FREE + remaining, 'Storage reserve/allowance exhausted')
        self.policy_counts['checkpoint_count'] += 1
        expected = 'always'
        G.require(self.active_row['client_checkpoint_policy'] == self.checkpoint_policy == expected,
                  'Client checkpoint policy differs from pinned request')
        changed = (self.state['charged_write_bytes'], self.state['last_available_bytes']) != previous_storage
        # Only a redundant storage-ledger write may be omitted. Every check above
        # still runs, and every other mutation retains its explicit durable save.
        if self.checkpoint_policy == 'always' or changed:
            self.save_state()
            self.policy_counts['storage_save_count'] += 1
        else:
            self.policy_counts['skipped_storage_save_count'] += 1

    def policy_readout(self, request):
        G.require(self.policy_counts['checkpoint_count'] == self.policy_counts['storage_save_count'] +
                  self.policy_counts['skipped_storage_save_count'], 'Checkpoint counters differ')
        source = str(Path(__file__).resolve())
        source_sha = G.sha(G.read_file(Path(source)))
        G.require(source_sha == self.contract['source_bindings'][source], 'Client policy source changed')
        write_new(request / 'client-policy.json', {
            'schema': 'ltx.client-checkpoint-policy.v1', 'name': self.active_row['name'],
            'phase': self.active_row['phase'], 'policy': self.checkpoint_policy,
            **self.policy_counts, 'source_sha256': source_sha,
            'plan_sha256': G.PLAN_SHA,
            'runtime_manifest_sha256': self.contract['runtime_manifest_sha256'],
            'server_identity_sha256': self.contract['server_identity_sha256'],
            'client_contract_sha256': self.contract_sha})

    def save_state(self):
        path = self.directory / 'state.json'; temp = self.directory / ('state-' + uuid.uuid4().hex + '.tmp')
        write_new(temp, self.state); os.replace(temp, path); sync_directory(self.directory)

    def acquire(self):
        # The coordinator creates this once; reconnecting reuses the durable bounded ledger.
        if not self.directory.exists():
            initial = self.free_probe(self.root)
            G.require(initial >= MIN_FREE + WRITE_ALLOWANCE, 'Initial storage admission refused')
            self.directory.mkdir(); sync_directory(self.directory.parent)
            write_new(self.directory / 'state.json', {'schema': 'ltx.finite-client-state.v1',
                      'contract_sha256': self.contract_sha, 'attempts': [], 'completed': [], 'prompt_ids': [],
                      'verified': [], 'halted': None, 'charged_write_bytes': 0, 'last_available_bytes': initial})
        G.safe_path(self.directory)
        self.lock_fd = os.open(self.directory / 'lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.state = G.strict_json(G.read_file(self.directory / 'state.json'))
            G.require(self.state['contract_sha256'] == self.contract_sha and self.state['halted'] is None,
                      'Client ledger halted or bound to another contract')
        except BaseException:
            os.close(self.lock_fd); self.lock_fd = None; raise

    def release(self):
        if getattr(self, 'lock_fd', None) is not None:
            os.close(self.lock_fd); self.lock_fd = None

    async def execute(self, name, transport=None):
        self.acquire(); request = None
        try:
            G.require(name in self.rows, 'Unknown request; no policy available')
            self.active_row = self.rows[name]
            self.checkpoint_policy = self.active_row['client_checkpoint_policy']
            self.policy_counts = dict(checkpoint_count=0, storage_save_count=0, skipped_storage_save_count=0)
            self.checkpoint()
            G.require(name in self.rows and name not in self.state['attempts'], 'Unknown/already attempted request; no retry')
            row = self.rows[name]
            G.require(name in self.ordered_names and self.state['completed'] == self.ordered_names[:self.ordered_names.index(name)],
                      'Sealed request sequence/order differs')
            self.phase_observation(row)
            G.require(self.state.get('verified', []) == self.state['completed'], 'Prior global proof barrier missing')
            G.require(len(self.state['attempts']) < ATTEMPT_CAP, 'Client attempt cap exhausted')
            self.state['attempts'].append(name); self.save_state()
            destination = self.root / 'requests' / name
            G.safe_path(destination); destination.mkdir(parents=False, exist_ok=False)
            request = destination; sync_directory(request.parent)
            graph = row['graph']
            G.require(G.sha(G.canonical(graph)) == row['graph_sha256'], 'Pinned graph changed')
            write_new(request / 'prompt.json', graph)
            write_new(request / 'identity.json', self.identity)
            client_id = 'ltx-resolution-' + uuid.uuid4().hex
            deadline = time.monotonic() + self.contract['request_timeout_seconds']
            async def bounded(awaitable):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    awaitable.close()
                    raise TimeoutError('Request deadline; coordinator must inspect any submitted job')
                return await asyncio.wait_for(awaitable, timeout=remaining)
            async with (transport if transport is not None else AioTransport()) as io:
                queue = await bounded(io.get('/queue'))
                G.require(queue.get('queue_running') == [] and queue.get('queue_pending') == [], 'Native queue not empty')
                await bounded(io.subscribe(client_id))
                self.checkpoint()
                queue = await bounded(io.get('/queue'))
                G.require(queue.get('queue_running') == [] and queue.get('queue_pending') == [], 'Queue changed before submit')
                observation = self.phase_observation(row)
                if observation is not None:
                    write_new(request / 'phase-observation.json', observation)
                wall_before = time.time_ns() // 1000000
                submission = await bounded(io.submit(graph, client_id))  # Exactly one POST; failures are terminal.
                write_new(request / 'submission.json', submission)
                pid = submission.get('prompt_id')
                G.require(isinstance(pid, str) and pid and pid not in self.state['prompt_ids'] and
                          not submission.get('node_errors'), 'Invalid/duplicate/error submission')
                self.state['prompt_ids'].append(pid); self.save_state()
                started = False; success = None; start_event = None
                with (request / 'events.jsonl').open('x') as log:
                    while True:
                        self.checkpoint()
                        remaining = deadline - time.monotonic()
                        G.require(remaining > 0, 'Request deadline; submitted job requires coordinator inspection')
                        try:
                            event = await io.receive(min(5, remaining))
                        except asyncio.TimeoutError:
                            continue  # No submission retry; finite receive/deadline check only.
                        if event is None or event.get('data', {}).get('prompt_id') != pid:
                            continue
                        record = {'seconds': self.contract['request_timeout_seconds'] - (deadline - time.monotonic()), **event}
                        log.write(json.dumps(record, allow_nan=False) + '\n'); log.flush(); os.fsync(log.fileno())
                        kind = event['type']; data = event['data']
                        if kind == 'execution_start':
                            G.require(not started and type(data.get('timestamp')) is int and data['timestamp'] >= wall_before,
                                      'Stale/duplicate execution start')
                            started = True
                            start_event = event
                        if kind == 'execution_cached':
                            G.require(not data.get('nodes'), 'Cached current request refused')
                        if kind in ('execution_error', 'execution_interrupted'):
                            raise RuntimeError('Current request failed; no further submissions')
                        if kind == 'execution_success':
                            G.require(started and type(data.get('timestamp')) is int and data['timestamp'] >= wall_before,
                                      'Stale terminal or success without execution start')
                            success = event; break
                    sync_directory(request)
                history = None
                for attempt in range(20):
                    self.checkpoint()
                    G.require(time.monotonic() < deadline, 'History deadline; preserve submitted job')
                    response = await bounded(io.get('/history/' + pid))
                    if pid in response:
                        history = response[pid]; break
                    await asyncio.sleep(.1)
                G.require(history is not None, 'Successful history unavailable after bounded polls')
                write_new(request / 'history.json', history)
                result = {'name': name, 'prompt_id': pid, 'seconds': self.contract['request_timeout_seconds'] - (deadline - time.monotonic()),
                          'status': history['status']}
                write_new(request / 'result.json', result)
                G.require(history['prompt'][1] == pid and history['prompt'][2] == graph and
                          history['prompt'][0] == submission['number'], 'History submission/graph differs')
                status = history['status']; messages = status['messages']
                G.require(status.get('completed') is True and status.get('status_str') == 'success' and
                          all(data.get('prompt_id') == pid for _, data in messages), 'History status/identity differs')
                G.require(not any(kind in ('execution_error', 'execution_interrupted') or
                                  (kind == 'execution_cached' and data.get('nodes')) for kind, data in messages), 'Failed/cached history')
                terminal = [data for kind, data in messages if kind == 'execution_success']
                beginnings = [data for kind, data in messages if kind == 'execution_start']
                G.require(terminal == [success['data']] and beginnings == [start_event['data']] and
                          beginnings[0]['timestamp'] >= wall_before and beginnings[0]['timestamp'] < terminal[0]['timestamp'],
                          'Stale/reordered history terminal')
            self.checkpoint()
            self.policy_readout(request)
            self.state['completed'].append(name); self.save_state()
            return result
        except BaseException as error:
            if hasattr(self, 'state'):
                self.state['halted'] = {'type': type(error).__name__, 'message': str(error), 'name': name,
                                        'action': 'No retry or signal; coordinator must inspect any submitted job'}
                self.save_state()
                if not (self.directory / 'HALT.json').exists():
                    write_new(self.directory / 'HALT.json', self.state['halted'])
                if request is not None and request.is_dir() and not (request / 'client-failure.json').exists():
                    write_new(request / 'client-failure.json', self.state['halted'])
            raise
        finally:
            self.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--request', required=True, help='One exact native plan name; no implicit retry or campaign')
    args = parser.parse_args()
    client = Client(args.contract, args.contract_sha256)
    result = asyncio.run(client.execute(args.request))
    print(json.dumps({'name': result['name'], 'prompt_id': result['prompt_id'], 'status': result['status']['status_str']}))


if __name__ == '__main__':
    main()
