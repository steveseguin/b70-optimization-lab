#!/usr/bin/env python3
"""One coordinator-owned p198 process, six bounded real HTTP policy requests.

CPU --plan and mocks do not launch anything. Live execution requires the fixed
window unit, sealed readiness, fault review, whole-host lease and drain permit.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import shutil
import stat
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
P198 = P.parent / 'packet198-postreply-checkpoint'
INTEGRATION = P.parents[1] / 'integration'
ONE = P.parent / 'packet181-session-swap-v3/one-card'
OUTPUT = P / 'evidence/device-p199-chat-A-a'
CHECKPOINTS = P / 'evidence/runcheckpoints'
REVIEW = P / 'evidence/fault-review-device-a.json'
READY = P / 'READY-FOR-DEVICE.json'
UNIT = 'packet199-chat-parking-a'
PYTHON = Path('/home/steve/.venvs/vllm-xpu/bin/python')
QUEUE = P.parents[1] / 'ops/lane-queue'
IDS = ['a-park', 'b-park', 'a-chat-append', 'a-chat-fresh', 'a-edited', 'final-b-no-park']
CONTROLS = ['parking-' + str(i) for i in range(1, 7)]
HOST_REQUIRED = 98_990_252_032
COORDINATOR_MARGIN = 1024**3
DISK_FLOOR = 27_000_000_000
PLANNED_WRITES = 640 * 1024**2
SAVE_BOUND = 256 * 1024**2
PARKING_BUDGET = 512 * 1024**2
VOCAB = 248320
_PARENT = None


def require(value, reason):
    if not value:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    os.replace(temporary, path)


def parent():
    global _PARENT
    if _PARENT is None:
        spec = importlib.util.spec_from_file_location('p199_frozen_p198_safety', P198 / 'device_worker.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PARENT = module
    return _PARENT


def integration():
    if str(INTEGRATION) not in sys.path:
        sys.path.insert(0, str(INTEGRATION))
    if str(ROOT / 'tools/ctxkeeper') not in sys.path:
        sys.path.insert(0, str(ROOT / 'tools/ctxkeeper'))
    import chat_codec, chat_http, chat_service, checkpoint_engine, native_checkpoint_store, parking
    for module in (chat_codec, chat_http, chat_service, checkpoint_engine, native_checkpoint_store):
        require(Path(module.__file__).resolve().parent == INTEGRATION, 'integration namespace collision')
    require(Path(parking.__file__).resolve() == ROOT / 'tools/ctxkeeper/parking.py', 'parking namespace collision')
    return dict(codec=chat_codec.PinnedChatCodec, make_server=chat_http.make_server,
                service=chat_service.ChatService, engine=checkpoint_engine.CheckpointEngine,
                store=native_checkpoint_store.NativeCheckpointStore, parking=parking.Parking)


def require_interpreter():
    require(Path(sys.executable) == PYTHON and Path(sys.prefix) == PYTHON.parent.parent,
            'fixed vllm-xpu Python required for pinned regex/Jinja2')
    import regex, jinja2
    require((regex.__version__, jinja2.__version__) == ('2026.5.9', '3.1.6'), 'codec dependency versions changed')
    require(not any(name == 'torch' or name.startswith('torch.') for name in sys.modules), 'worker must not import Torch')


def configuration():
    spec, vectors = read(P / 'plan.json'), read(P / 'vectors.json')
    require(spec['vector_sha256'] == sha(P / 'vectors.json'), 'vector binding changed')
    require(spec['unit'] == UNIT and spec['output'] == str(OUTPUT), 'fixed worker identity')
    require(spec['storage']['checkpoint_root'] == str(CHECKPOINTS), 'fixed private ext4 checkpoint root')
    require([row['name'] for row in vectors['rows']] == IDS, 'six fixed HTTP rows')
    require(spec['request_budget']['requests'] == 6 and spec['request_budget']['controls'] == 6, 'six operations required')
    require(spec['parking']['main_budget_bytes'] == PARKING_BUDGET and
            spec['parking']['save_size_bound_bytes'] == SAVE_BOUND, 'parking peak admission')
    require(spec['parent_binary'] == str(P198 / 'build/device/own-rt-iq3') and
            sha(Path(spec['parent_binary'])) == spec['binary_sha256'], 'unchanged p198 binary')
    require(spec['identity'] == read(INTEGRATION / 'checkpoint-fixtures-p198/admitted-engine-identity.json'),
            'independently retained owner identity differs')
    require(spec['identity']['engine']['binary_sha256'] == spec['binary_sha256'], 'owner/identity digest mismatch')
    for relative, digest in vectors['source_files_sha256'].items():
        require(sha(ROOT / relative) == digest, 'vector source drift: ' + relative)
    return spec, vectors


def native_argv():
    argv = parent().native_argv()
    replacements = {'--output': OUTPUT / 'owner', '--request-front-checkpoints': CHECKPOINTS,
                    '--request-front-max-requests': 6}
    for flag, value in replacements.items():
        require(argv.count(flag) == 1, 'ambiguous inherited argv ' + flag)
        argv[argv.index(flag) + 1] = str(value)
    return argv


def storage(planned=0):
    free = shutil.disk_usage(P).free
    require(free - planned >= DISK_FLOOR, 'root free-after-write floor27GB')
    return dict(free_bytes=free, planned_write_bytes=planned, floor_bytes=DISK_FLOOR)


def create_checkpoint_root():
    require(not os.path.lexists(CHECKPOINTS), 'fresh checkpoint root required; no retry')
    require(CHECKPOINTS.parent.resolve() == CHECKPOINTS.parent, 'checkpoint parent must be real')
    require(CHECKPOINTS.parent.stat().st_dev == ROOT.stat().st_dev, 'checkpoint root must stay on local filesystem')
    CHECKPOINTS.mkdir(mode=0o700)
    state = CHECKPOINTS.lstat()
    require(stat.S_ISDIR(state.st_mode) and state.st_uid == os.getuid() and
            stat.S_IMODE(state.st_mode) == 0o700, 'private0700 checkpoint root required')
    fd = os.open(CHECKPOINTS.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(path=str(CHECKPOINTS), device=state.st_dev, inode=state.st_ino, uid=state.st_uid, mode='0700')


class Guarded:
    """Admitted front/store operations retain a before/after guard receipt."""
    def __init__(self, target, methods, guard, log, category):
        self._target, self._methods = target, frozenset(methods)
        self._guard, self._log, self._category = guard, log, category

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if name not in self._methods:
            return value
        def call(*args, **kwargs):
            label = self._category + '.' + name
            self._guard()
            self._log(dict(operation=label, phase='before', id=args[0] if args else None,
                           monotonic_ns=time.monotonic_ns()))
            result = value(*args, **kwargs)
            self._guard()
            self._log(dict(operation=label, phase='after', id=args[0] if args else None,
                           monotonic_ns=time.monotonic_ns()))
            return result
        return call


def start_owner(argv, environment, stderr, popen=None):
    require(argv == native_argv(), 'production argv mismatch')
    require(environment['OMP_NUM_THREADS'] == '2' and environment['FilterBdfPath'] == '0000:23:00.0',
            'fixed single card environment')
    parent().parent_modules()['exec_limits'].check()  # Requires unlimited AS; never changes limits.
    return (popen or subprocess.Popen)(argv, env=environment, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=stderr)


def build_services(front, store, codec, spec, guard, operation_log):
    modules = integration()
    class ObservedEngine(modules['engine']):
        def __init__(self, *args, **kwargs):
            self.turns = []
            super().__init__(*args, **kwargs)
        def run_turn(self, *args, **kwargs):
            result = super().run_turn(*args, **kwargs)
            self.turns.append(dict(request_id=kwargs['request_id'], response=result['response'],
                decision=asdict(result['decision']), parked=asdict(result['parked']) if result['parked'] else None,
                release=result['release']))
            return result
    gf = Guarded(front, ('request', 'save', 'release'), guard, operation_log, 'front')
    gs = Guarded(store, ('snapshot', 'delete'), guard, operation_log, 'store')
    engine = ObservedEngine(gf, gs, root=CHECKPOINTS, expected_identity=spec['identity'],
        admitted_contract='v1.2+p198', save_size_bound_bytes=SAVE_BOUND,
        storage_available=lambda path: shutil.disk_usage(path).free, floor_bytes=DISK_FLOOR)
    policy_events = []
    options = dict(accepted_contracts={('experimental-postreply-front', 'v1.2+p198')}, log=policy_events.append)
    parked = modules['parking'](engine, codec.render, codec.encode, budget_bytes=PARKING_BUDGET, **options)
    none = modules['parking'](engine, codec.render, codec.encode, budget_bytes=0, **options)
    model = read(P / 'vectors.json')['model']
    services = {name: modules['service'](engine, policy, codec, model=model,
                native_stop_token_ids={248044, 248046}) for name, policy in [('parked', parked), ('no-parking', none)]}
    return engine, services, parked, none, policy_events


def capture_state(store, checkpoint, output, name, guard):
    """Hash real state now; preserve compact evidence before later policy deletes."""
    guard()
    destination = output / 'checkpoint-captures' / name
    destination.mkdir(parents=True, exist_ok=False)
    # Reuse the pinned native-compatible lock across snapshot AND tensor hashes.
    with store._shared_lock(checkpoint):
        snapshot = store.snapshot(checkpoint)
        require(snapshot is not None, 'SAVE checkpoint disappeared before capture')
        manifest = json.loads(snapshot.manifest_bytes)
        folder = CHECKPOINTS / checkpoint
        (destination / 'manifest.json').write_bytes(snapshot.manifest_bytes)
        (destination / 'inspect.json').write_bytes(snapshot.inspect_stdout)
        (destination / 'tokens.bin').write_bytes(snapshot.tokens_bytes)
        (destination / 'next_token.bin').write_bytes(snapshot.next_token_bytes)
        states = {}
        total = 0
        entries = [('tokens.bin', manifest['token_state']['tokens_sha256'])] + [
            (blob['name'] + '.bin', blob['sha256']) for blob in manifest['blobs']]
        for filename, expected in entries:
            require(Path(filename).name == filename, 'unsafe native blob name')
            fd = os.open(folder / filename, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as file:
                before = os.fstat(file.fileno())
                require(stat.S_ISREG(before.st_mode), 'state file must be regular')
                total += before.st_size
                require(total <= SAVE_BOUND, 'state hash read exceeds admitted checkpoint bound')
                actual = hashlib.file_digest(file, 'sha256').hexdigest()
                after = os.fstat(file.fileno())
                require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                        (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'state changed during capture')
            require(actual == expected, 'native state blob hash mismatch: ' + filename)
            states[filename] = actual
        row = dict(checkpoint_id=checkpoint, manifest_sha256=hashlib.sha256(snapshot.manifest_bytes).hexdigest(),
                   storage_bytes=snapshot.storage_bytes, state_sha256=states,
                   raw_tensors_retained=False, scope='full blobs hashed while present; later policy deletion permitted')
        save(destination / 'state-proof.json', row)
    guard()
    return row


def http_request(address, row):
    request = row['http']
    connection = http.client.HTTPConnection(*address, timeout=900)
    try:
        connection.request(request['method'], request['path'],
            body=json.dumps(request['body'], ensure_ascii=False).encode(), headers=request['headers'])
        response = connection.getresponse()
        raw = response.read(4 * 1024**2 + 1)
        require(len(raw) <= 4 * 1024**2, 'HTTP response bound')
        require(response.status == 200 and response.version == 10, 'HTTP completion failed: ' + str(response.status))
        return json.loads(raw), raw
    finally:
        connection.close()


def lifecycle(front, store, codec, spec, vectors, output, guard, persist, operation_log,
              capture=capture_state, request=http_request):
    modules = integration()
    engine, services, main_policy, no_policy, policy_events = build_services(
        front, store, codec, spec, guard, operation_log)
    server = modules['make_server'](services['parked'])
    # One handler thread. The worker is the fixed HTTP client/coordinator.
    handler_lock = threading.Lock()
    original_finish = server.finish_request
    def finish_request(*args):
        with handler_lock:
            return original_finish(*args)
    server.finish_request = finish_request
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True,
                              name='p199-loopback-http')
    thread.start()
    rows, captures = [], {}
    primary_error = None
    try:
        for index, vector in enumerate(vectors['rows']):
            guard()
            require(codec.encode(codec.render(vector['http']['body']['messages'])) == vector['prompt_tokens'],
                    'HTTP rendered input differs from pinned vector')
            require(front.state == 'ready' and front.pending is None, 'coordinator cannot change service during active handler')
            require(len(engine.turns) == index, 'unexpected local HTTP intake')
            require(handler_lock.acquire(timeout=5), 'previous HTTP handler not finished')
            try:
                server.service = services[vector['service']]
            finally:
                handler_lock.release()
            event_start = len(policy_events)
            response, raw_response = request(server.server_address, vector)
            guard()
            require(len(engine.turns) == index + 1, 'HTTP must complete exactly one native RUN')
            turn = engine.turns[-1]
            native_id = response['id'].removeprefix('chatcmpl-')
            require(response['id'] == 'chatcmpl-' + turn['request_id'] and native_id == turn['request_id'],
                    'HTTP/native request ID mismatch')
            folder = output / 'owner/requests' / native_id
            native = read(folder / 'result.json')
            generated = turn['response']['tokens']
            require(native['passed'] is True and native['tokens'] == generated, 'stream/result exact token mismatch')
            require(native['request_front_scope'] == 'experimental-postreply-owner-v2', 'native front scope')
            restored = vector['expected_policy_action'] == 'restore'
            require(native['session_reuse'] is restored and turn['decision']['action'] == vector['expected_policy_action'],
                    'policy/restore path mismatch')
            require(read(folder / 'reset.json')['cached_tokens'] == 0, 'pre-restore reset must be fresh')
            expected_cached = vector.get('saved_prefix', {}).get('visible_tokens', 1) - 1 if restored else 0
            require(native['cached_tokens'] == expected_cached, 'restored-prefix cache accounting mismatch')
            maximum = vector['http']['body']['max_tokens']
            terminal = generated[-1] in {248044, 248046}
            require(0 < len(generated) <= maximum and (len(generated) == maximum or terminal), 'bounded generation count')
            expected_usage = dict(prompt_tokens=len(vector['prompt_tokens']), completion_tokens=len(generated),
                                  total_tokens=len(vector['prompt_tokens']) + len(generated))
            require(response['usage'] == expected_usage and response['choices'][0]['message'] ==
                    dict(role='assistant', content=codec.decode(generated[:-1] if terminal else generated)), 'HTTP content/usage mismatch')
            expected = vector['expected_output']
            if expected['kind'] == 'exact-recorded-p198':
                parent().exact(generated, expected['tokens'], vector['name'] + ' retained p198')
            disposition = 'SAVE' if turn['parked'] else 'RELEASE'
            require(disposition == vector['expected_disposition'], 'postreply policy disposition mismatch')
            operation = 'parking-' + str(index + 1)
            if disposition == 'SAVE':
                checkpoint = turn['parked']['checkpoint_id']
                event = read(output / 'owner/operations' / operation / 'save.json')
                require(event['request_id'] == native_id and event['checkpoint_id'] == checkpoint,
                        'save event/native identity mismatch')
                captures[vector['name']] = capture(engine.store, checkpoint, output, vector['name'], guard)
                require(event['manifest_sha256'] == captures[vector['name']]['manifest_sha256'], 'SAVE capture identity mismatch')
            else:
                event = turn['release']
                require(event is not None and event['event'] == 'request-released', 'normal RELEASE required')
            require(event['operation_id'] == operation and event['request_disposed'] is True and
                    event['request_quiesced'] is True and event['final_request'] is (index == 5), 'control completion identity')
            new_events = policy_events[event_start:]
            evictions = [r['session'] for r in new_events if r['event'] == 'checkpoint evicted']
            require(evictions == vector['expected_evictions'], 'parking budget eviction sequence')
            saved_row = dict(name=vector['name'], native_request_id=native_id, response=response,
                tokens=generated, decision=turn['decision'], control=event, policy_events=new_events,
                parking=main_policy.status(), no_parking=no_policy.status(),
                native_result_sha256=sha(folder / 'result.json'), cached_tokens=native['cached_tokens'],
                http_response_sha256=hashlib.sha256(raw_response).hexdigest())
            rows.append(saved_row)
            (output / (vector['name'] + '.http.json')).write_bytes(raw_response)
            save(output / 'http-requests.json', rows)
            persist(rows)
            if vector['name'] == 'a-chat-fresh':
                parent().exact(rows[2]['tokens'], generated, 'actual-chat append/fresh')
                require(captures['a-chat-append']['state_sha256'] == captures['a-chat-fresh']['state_sha256'],
                        'actual-chat append/fresh state mismatch')
        require(front.state == 'draining' and front.pending is None, 'final normal RELEASE before drain')
        require([row['control']['operation_id'] for row in rows] == CONTROLS, 'six controls exact order')
        require(all(row['parking']['bytes'] <= PARKING_BUDGET for row in rows), 'parking budget exceeded')
        return dict(A_parent_exact=True, B_parent_exact=True, append_restore_selected=True,
                    append_fresh_tokens_exact=True, append_fresh_state_exact=True, edited_prefill=True,
                    final_B_repeat=True, postreply_controls_exact=True, final_release_before_stopped=True,
                    http_usage_exact=True, parking_budget_respected=True), rows, captures
    except BaseException as error:
        primary_error = error
        try:
            limited = lambda value: None if value is None else str(value)[:4096]
            pending = front.pending
            incident = dict(error_type=type(error).__name__, error=limited(error),
                service_halted_reasons={name: limited(service.halted_reason) for name, service in services.items()},
                engine_halted_reason=limited(engine.halted_reason), front_state=front.state,
                front_pending=None if pending is None else {key:pending.get(key) for key in
                    ('request_id','visible_tokens','processed_tokens','pending_token')},
                parking=main_policy.status(), no_parking=no_policy.status(), completed_semantic_rows=[r['name'] for r in rows])
            raw = (json.dumps(incident, ensure_ascii=True, allow_nan=False, indent=2) + '\n').encode()
            require(len(raw) <= 65536, 'private incident receipt bound')
            temporary = output / 'http-incident.json.tmp'
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as file:
                file.write(raw);file.flush();os.fsync(file.fileno())
            os.replace(temporary, output / 'http-incident.json')
        except Exception as evidence_error:
            error.add_note('private HTTP incident capture failed: ' + str(evidence_error)[:1024])
        raise
    finally:
        server.intake_halted = True
        # Normal shutdown joins immediately. A wedged handler is never killed;
        # the outer worker retains owner/lease markers for one incident action.
        closer = threading.Thread(target=server.shutdown, daemon=True)
        closer.start(); closer.join(10); thread.join(10)
        server.server_close()
        if closer.is_alive() or thread.is_alive():
            if primary_error is not None:
                primary_error.add_note('HTTP handler retained after bounded shutdown')
            else:
                raise ValueError('HTTP handler retained after bounded shutdown')


parent_modules = lambda: parent().parent_modules()
capture_review = lambda: parent().capture_review()


def source_paths():
    paths = parent().source_paths() + [P198 / 'READY-FOR-DEVICE.json', P198 / 'evidence/independent-device-result.json']
    paths += [P / name for name in ('device_worker.py', 'device_fault_review.py', 'device_gates.py', 'tests/test_device_worker.py', 'tests/test_device_gates.py',
                                   'plan.json', 'vectors.json', 'prepare_vectors.py')]
    paths += [P.parents[1] / 'ops/packet199-window' / name for name in
              ('window.py', 'helpers.py', 'helper-pins.json', 'restore_guard.py', 'test_window.py')]
    paths += [INTEGRATION / name for name in ('chat_codec.py', 'chat_http.py', 'chat_service.py',
        'checkpoint_engine.py', 'checkpoint_bridge.py', 'native_checkpoint_store.py',
        'request_front/client_v2.py', 'chat_template-7c1460a9.jinja',
        'checkpoint-fixtures-p198/admitted-engine-identity.json', 'receipts/p198-checkpoint-size-bound.json')]
    paths += [ROOT / 'tools/ctxkeeper/parking.py', ROOT /
        'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/tokenizer.py',
        INTEGRATION.parent / 'stage1/packet1b/loaders/headers.py']
    return sorted(set(path.resolve() for path in paths))


def external_dependencies():
    require_interpreter()
    import regex, jinja2, jinja2.sandbox, markupsafe
    paths = {PYTHON.resolve(), PYTHON.parent.parent / 'pyvenv.cfg'}
    # Fixed package inventory, independent of which lazy modules were imported
    # before this call. Include source and extension binaries, never pycache.
    for package in (regex, jinja2, markupsafe):
        folder = Path(package.__file__).resolve().parent
        require(folder.is_relative_to(PYTHON.parent.parent), 'codec package outside fixed venv')
        paths.update(path.resolve() for path in folder.rglob('*')
                     if path.is_file() and path.suffix in {'.py', '.so'})
    return sorted(paths)


def verify_ready():
    require_interpreter()
    spec, vectors = configuration()
    parent().verify_ready()
    ready = read(READY)
    require(ready.get('passed') is True and ready.get('device_executed') is False, 'sealed CPU readiness required')
    require(ready['native_argv'] == native_argv(), 'sealed native argv mismatch')
    expected = {str(path.relative_to(ROOT)) for path in source_paths()}
    require(set(ready['files_sha256']) == expected, 'exact worker source closure required')
    for path, digest in ready['files_sha256'].items():
        require(sha(ROOT / path) == digest, 'worker source drift: ' + path)
    require(set(ready['external_files_sha256']) == {str(path) for path in external_dependencies()},
            'exact interpreter/codec dependencies required')
    for path, digest in ready['external_files_sha256'].items():
        require(sha(path) == digest, 'interpreter/codec dependency drift')
    gate = P / 'evidence/device-cpu-gates.json'
    require(read(gate)['passed'] is True and ready['gates_sha256'] == sha(gate), 'CPU gate binding mismatch')
    return ready


def plan():
    ready = verify_ready()
    spec, vectors = configuration()
    return dict(passed=True, device_executed=False, unit=UNIT, output=str(OUTPUT),
        fault_review=str(REVIEW), terminal_receipt=str(OUTPUT / 'worker.json'), ready=str(READY),
        ready_sha256=sha(READY), native_argv=native_argv(),
        worker_argv=[str(PYTHON), '-B', str(P / 'device_worker.py'), '--authorized-device-window',
                     '--output', str(OUTPUT), '--fault-review', str(REVIEW)],
        fault_review_command=[str(PYTHON), '-B', str(P / 'device_fault_review.py'), '--output', str(REVIEW)],
        cpu_affinity='0-3,16-19', nice=0, host_required_available_bytes=HOST_REQUIRED,
        planned_write_bytes=PLANNED_WRITES, disk_floor_bytes=DISK_FLOOR,
        checkpoint_root=str(CHECKPOINTS), protocol='ownrt.request-front.v2', expected_request_ids=IDS,
        expected_controls=CONTROLS, save_count=5, release_count=1, maximum_output_tokens=896,
        max_native_processes=1, max_requests=6, precision='full BF16 KV', context=4096,
        cache_bytes=21552729600, submission_eligible=False, source_count=len(ready['files_sha256']))


def unit_gate():
    require(any(line.endswith('/' + UNIT + '.service') for line in Path('/proc/self/cgroup').read_text().splitlines()),
            'fixed coordinator worker unit required')
    keys = ('Restart', 'SendSIGKILL', 'KillMode', 'ExitType', 'TimeoutStopUSec')
    cp = subprocess.run(['/usr/bin/systemctl', '--user', 'show', UNIT + '.service',
        *[arg for key in keys for arg in ('-p', key)]], stdin=subprocess.DEVNULL,
        env=dict(PATH='/usr/bin:/bin', XDG_RUNTIME_DIR='/run/user/' + str(os.getuid())),
        capture_output=True, text=True, timeout=15)
    props = dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)
    require(cp.returncode == 0 and props == dict(Restart='no', SendSIGKILL='no', KillMode='process',
            ExitType='cgroup', TimeoutStopUSec='infinity'), 'graceful nonrestarting unit required')
    return props


def verify_stopped(stopped, rows):
    require([row['control']['operation_id'] for row in rows] == CONTROLS, 'six postreply controls')
    require([row['control']['event'] for row in rows] == ['checkpoint-saved'] * 5 + ['request-released'],
            'five SAVE then final RELEASE required')
    wanted = dict(event='stopped', safe_to_exit=True, reason='request-limit', completed_requests=6,
                  completed_controls=6, discarded_pending=False, pending_request_id='')
    require(all(type(stopped.get(k)) is type(v) and stopped[k] == v for k, v in wanted.items()),
            'clean native terminal receipt required')


def execute(spec, fault_path):
    m = parent_modules(); devices = m['chain_devices']; common = m['common']
    require_interpreter(); m['conditions'].lane_gate('A'); m['exec_limits'].check()
    unit = unit_gate(); parent().memory(HOST_REQUIRED + COORDINATOR_MARGIN); storage(PLANNED_WRITES)
    require(not os.path.lexists(OUTPUT) and not os.path.lexists(CHECKPOINTS), 'fresh output and state roots; no retry')
    reviewed, initial, fresh, cursor = parent().validate_review(fault_path)
    OUTPUT.mkdir(mode=0o700)
    (OUTPUT / 'kernel-initial.jsonl').write_text(initial + fresh)
    record = dict(passed=False, device_executed=False, native_process_count=0, model_loads=0,
        completed_requests=[], child_still_running=False, safe_to_exit=False, devices_drained=False,
        submission_eligible=False, plan=spec, unit=unit, stop_reasons=[], started_utc_ns=time.time_ns())
    child = None; thread = None
    guard_lock = threading.RLock(); stop_monitor = threading.Event()
    monitor = devices.DeviceMonitor('A'); deadline = time.monotonic() + 7200
    stop_once = parent().IncidentStop(record, lambda: child)
    def persist():
        save(OUTPUT / 'worker.json', record)
    def check():
        nonlocal cursor
        with guard_lock:
            require(not record['stop_reasons'], 'intake halted: ' + str(record['stop_reasons']))
            require(time.monotonic() < deadline, 'worker absolute deadline')
            for path in (QUEUE / 'STOP-A', QUEUE / 'STOP-B', QUEUE / 'PAUSE-A', OUTPUT / 'STOP'):
                require(not os.path.lexists(path), 'admission latch ' + str(path))
            text, cursor = parent().journal(cursor)
            with (OUTPUT / 'kernel-window.jsonl').open('a') as log:
                log.write(text)
            require(not m['fault_review'].fault_lines(text), 'new GPU fault')
            storage(); parent().memory(parent().VIRTUAL_FLOOR)
            if child is not None:
                monitor.poll(force=True)
                require(all(fd['pci'] == '0000:23:00.0' for owner in monitor.owners.values() for fd in owner['fds']),
                        'owner escaped card0')
                devices.admit_clients('whole-host', owned=monitor.live_identities())
                if child.poll() is None:
                    sample = common.SUPPORT.process_tree_anon(child.pid)
                    record['anonymous_peak_bytes'] = max(record.get('anonymous_peak_bytes', 0), sample['anonymous_bytes'])
                    require(sample['anonymous_bytes'] < parent().HOST_REQUIRED - parent().VIRTUAL_FLOOR - 256 * 1024**2,
                            'native anonymous memory threshold')
    def background():
        try:
            os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 19)
            os.sched_setaffinity(threading.get_native_id(), set(range(8, 16)) | set(range(24, 32)))
            while not stop_monitor.wait(1):
                with guard_lock:
                    if parent().guarded_poll(check, stop_once):
                        continue
                    persist(); return
        except BaseException as error:
            with guard_lock:
                stop_once('passive monitor failed: ' + str(error)); persist()
    def operation_log(row):
        with guard_lock:
            with (OUTPUT / 'guard-operations.jsonl').open('a') as file:
                file.write(json.dumps(row, ensure_ascii=False) + '\n')
    handlers = {number: signal.signal(number, lambda n, f: stop_once('worker signal ' + str(n)))
                for number in (signal.SIGTERM, signal.SIGINT)}
    lease = m['lane_admission'].Reservation('A', window='screen', timing_claim=True, check=check)
    try:
        with lease:
            require(lease.scope == 'whole-host', 'whole-host lease required; no performance claim')
            devices.admit_clients('whole-host'); devices.topology_admit('A'); check()
            record['reservation'] = lease.record
            record['checkpoint_root'] = create_checkpoint_root()
            modules = integration(); codec = modules['codec']()
            config, vectors = configuration()
            env = devices.private_home(m['native_env'].environment('A'), OUTPUT / 'driver-home')
            record['environment'] = env; persist()
            with m['drain_gate'].DrainPermit(OUTPUT, check=check, reservation=lease.record) as permit:
                parent().memory(HOST_REQUIRED + COORDINATOR_MARGIN); storage(PLANNED_WRITES); check()
                with (OUTPUT / 'native.stderr.log').open('wb') as log:
                    child = start_owner(native_argv(), env, log)
                    record.update(device_executed=True, native_process_count=1, pid=child.pid, child_still_running=True)
                    monitor.register(child.pid); persist()
                    thread = threading.Thread(target=background, daemon=True, name='p199-passive-guard'); thread.start()
                    front = parent().client_module().NativeFront(child, context=4096, vocab=VOCAB, max_requests=6,
                        startup_timeout=900, request_timeout=900)
                    record['model_loads'] = front.ready['model_loads']; check()
                    require(front.ready['max_control_ops'] == 6 and monitor.owners[child.pid]['seen'], 'native ready/card proof')
                    def progress(rows):
                        with guard_lock:
                            record['requests'] = rows; record['completed_requests'] = [r['name'] for r in rows]; persist()
                    # Same DEVICE ELF for CPU metadata/delete mode, never a GNU-host identity substitute.
                    launch_env = __import__('launch_env')
                    require(Path(launch_env.__file__).resolve() == ONE / 'launch_env.py', 'loader environment namespace')
                    with modules['store'](CHECKPOINTS, Path(config['parent_binary']), config['binary_sha256'],
                                           launch_env.environment()) as store:
                        correctness, rows, captures = lifecycle(front, store, codec, config, vectors, OUTPUT,
                                                               check, progress, operation_log)
                    check(); operation_log(dict(operation='front.close', phase='before'))
                    stopped = front.close(timeout=120)
                    operation_log(dict(operation='front.close', phase='after')); check()
                    verify_stopped(stopped, rows)
                    stop_monitor.set(); thread.join(timeout=20)
                    require(not thread.is_alive(), 'passive guard retained')
                    proof = read(OUTPUT / 'owner/receipt.json')
                    require(proof['passed'] is True and proof['safe_to_exit'] is True and
                            proof['device_executed'] is True and child.returncode == 0, 'native shutdown proof')
                    monitor.finish(); devices.admit_clients('whole-host'); check()
                    permit.complete(); lease.complete(drained=True)
                    record.update(passed=True, safe_to_exit=True, devices_drained=True, child_still_running=False,
                        correctness=correctness, checkpoint_captures=captures, isolation=monitor.owners,
                        completed_controls=CONTROLS, controls=[r['control'] for r in rows], save_count=5, release_count=1,
                        total_output_tokens=sum(len(r['tokens']) for r in rows), maximum_output_tokens=896,
                        stopped=stopped, finished_utc_ns=time.time_ns())
                    persist(); return 0
    except BaseException as error:
        with guard_lock:
            stop_once(str(error)); record['error'] = str(error)
        stop_monitor.set()
        if thread is not None:
            thread.join(timeout=20)
        if child is not None and child.poll() is None:
            try:
                child.wait(timeout=65)
            except subprocess.TimeoutExpired:
                pass
        record.update(child_still_running=child is not None and child.poll() is None,
            child_returncode=child.returncode if child is not None else None,
            incident_sigterm_count=int(stop_once.sent), finished_utc_ns=time.time_ns())
        persist(); return 75 if record['child_still_running'] else 1
    finally:
        stop_monitor.set()
        for number, handler in handlers.items():
            signal.signal(number, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--authorized-device-window', action='store_true')
    parser.add_argument('--lane', choices=['A'], default='A')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--fault-review', type=Path)
    args = parser.parse_args(); spec = plan()
    if args.plan:
        require(not args.authorized_device_window, 'plan is CPU only')
        print(json.dumps(spec)); return 0
    require(args.authorized_device_window and args.output == OUTPUT and args.fault_review == REVIEW,
            'fixed coordinator authorization/output/review required')
    return execute(spec, args.fault_review)


if __name__ == '__main__':
    raise SystemExit(main())
