#!/usr/bin/env python3
"""Explicitly admitted, target-only contiguous pipeline; default operation is CPU planning.

The launch recipe is inherited from a recorded rank-adapter plan, not discovered by
running a service. Every stage runs once. No kill, restart, GPU API or power setting.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import mmap
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SLOT = 65536
SHARED = 4 * SLOT + 4096 + 64
REQUEST = struct.Struct('<8i')
REPLY = struct.Struct('<8i4d')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def save(path, value):
    with Path(path).open('x') as output:
        json.dump(value, output, indent=2)
        output.write('\n')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def option(argv, key):
    require(argv.count(key) == 1, f'exactly one {key} required')
    return argv[argv.index(key) + 1]


def replace_options(argv, changes, remove=()):
    # Only transform explicitly enumerated options; retain original arithmetic flags.
    require(all(argv.count(key) <= 1 for key in set(changes) | set(remove)), 'duplicate mutable argv option')
    result, i = [], 0
    no_value = {'--draft-mtp', '--tp-replicate'}
    while i < len(argv):
        arg = argv[i]
        if arg in changes or arg in remove:
            if arg in changes:
                result += [arg, str(changes.pop(arg))]
            i += 1 if arg in no_value else 2
        else:
            result.append(arg)
            i += 1
    for key, value in changes.items():
        result += [key, str(value)]
    return result


def make_plan(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    require(config.get('schema') == 'ownrt.pipeline-driver-config.v1', 'config schema')
    adapter_path = Path(config['adapter_plan']).resolve()
    adapter = json.loads(adapter_path.read_text())
    require(adapter.get('schema') == 'ownrt.gsq.rank-adapter-plan.v1', 'recorded adapter plan required')
    receipt_path = Path(config['build_receipt']).resolve()
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('schema') == 'ownrt.engine.build.v1', 'build receipt schema')
    binary = Path(receipt['binary']).resolve()
    require(digest(binary) == receipt['binary_sha256'], 'binary differs from build receipt')
    sources = receipt.get('sources', {})
    require('pipeline/layout.hpp' in sources, 'build receipt lacks pipeline-stage implementation')
    source_root = HERE.parent / 'src'
    for name, expected in sources.items():
        source = (source_root / name).resolve()
        require(source.is_relative_to(source_root.resolve()) and digest(source) == expected, 'compiled source differs from current engine: ' + name)
    cuts, bdfs = config['boundaries'], config['bdfs']
    require(len(cuts) >= 2 and cuts[0] == 0 and all(type(x) is int for x in cuts), 'integer boundaries from zero')
    require(all(a < b for a, b in zip(cuts, cuts[1:])), 'nonempty increasing stages')
    require(len(bdfs) == len(cuts) - 1 and len(set(bdfs)) == len(bdfs), 'one distinct BDF per stage')
    output = Path(config['output']).absolute()
    require(output == output.resolve() and output.parent.is_dir(), 'canonical existing output parent required')
    require(not output.exists(), 'fresh output required')
    require(output.parent.stat().st_uid == os.getuid(), 'output parent must be owned')
    tokens = config['prompt_tokens']
    context, maximum = int(config['context']), int(config['max_new'])
    vocab, eos = int(config['vocab']), int(config['eos'])
    require(tokens and all(type(t) is int and 0 <= t < vocab for t in tokens), 'prompt token bounds')
    require(1 <= maximum <= 512 and len(tokens) + maximum - 1 <= context <= 32768, 'context/output bounds')
    require(0 <= eos < vocab and 30 <= config['seconds'] <= 172800, 'EOS/lifetime bounds')
    require(config['memory_start_bytes'] >= config['memory_floor_bytes'] >= 8 * 1024**3, 'memory floors')
    require(config['root_floor_bytes'] >= 27000000000 and config['evidence_floor_bytes'] >= 2 * 1024**3, 'storage floors')
    require(config['grace_seconds'] >= 10 and config['grace_seconds'] <= 600, 'bounded cooperative grace')
    pins = {str(config_path): digest(config_path), str(adapter_path): digest(adapter_path), str(receipt_path): digest(receipt_path), str(binary): digest(binary), str(Path(__file__).resolve()): digest(__file__)}
    observe_path = ROOT / 'experiments/own-xpu-runtime/gsq-rco-iq3s/operating/observe.py'
    pins[str(observe_path)] = digest(observe_path)
    template = adapter['rank_argv'][0]
    placement_path, auth_path = Path(option(template, '--plan')).resolve(), Path(option(template, '--identity')).resolve()
    pins[str(placement_path)], pins[str(auth_path)] = digest(placement_path), digest(auth_path)
    planner = load_module(HERE.parent / 'planning/placement.py', 'pipeline_placement')
    pins[str(HERE.parent / 'planning/placement.py')] = digest(HERE.parent / 'planning/placement.py')
    tensors = planner.parse_placement(placement_path.read_bytes())
    require(cuts[-1] == max(t['layer'] for t in tensors) + 1, 'complete layer coverage')
    require(cuts[1] > max(t['layer'] for t in tensors if t['component'] == 'ple_lookup'), 'first stage must retain host PLE lookups')
    stages = []
    removes = {'--draft-mtp', '--draft-fault', '--draft-manifest', '--draft-model', '--draft-head', '--draft-experts', '--draft-capture', '--prefill-rows', '--prefill-shared', '--tp-replicate'}
    for i, bdf in enumerate(bdfs):
        first, final = i == 0, i == len(bdfs) - 1
        argv = list(adapter['rank_argv'][0 if first else 1])
        require(argv.count(adapter['binary']) == 1, 'recorded binary argv identity')
        argv[argv.index(adapter['binary'])] = str(binary)
        argv = replace_options(argv, {'--rank': 0 if first else 1, '--channel': '<channel-fd>', '--stop-fd': '<stop-fd>', '--shared': output / f'stage{i}/shared.bin', '--output': output / f'stage{i}/native', '--cards': 1, '--card': 0, '--context': context, '--max-new': maximum, '--seconds': config['seconds'], '--pipeline-boundaries': ','.join(map(str, cuts)), '--pipeline-stage': i, '--activations': 'f32', '--finish-dump': 'none', '--reset-dump': 'none'}, removes)
        require('--gsq-packed' in argv and '--authorized-device-window' in argv and option(argv, '--memory') == 'resident', 'resident native launch required')
        environment = dict(adapter['environment'][0 if first else 1])
        environment.update(NEOReadDebugKeys='1', FilterBdfPath=bdf, ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0', ONEAPI_DEVICE_SELECTOR='level_zero:0', OWNRT_DRAFT_DEPTH_PROBE='0', OWNRT_DRAFT_DEPTH_VERIFY='0', OWNRT_EARLY_RANK1='0')
        require('OWNRT_DECODE_PROFILE' not in environment, 'diagnostic timings refused')
        require(environment.get('OWNRT_GSQ_FUSE_NORM') != '1', 'cross-layer norm fusion refused')
        for key, sub in [('SYCL_CACHE_DIR', 'sycl'), ('NEO_CACHE_DIR', 'neo'), ('XDG_CACHE_HOME', 'xdg')]:
            environment[key] = str(output / f'stage{i}/cache/{sub}')
        owned = [t for t in tensors if t['component'] not in ('embedding', 'ple_lookup') and (cuts[i] <= t['layer'] < cuts[i+1] or (t['layer'] == -1 and final))]
        packed = sum(t['bytes'] for t in owned)
        require(packed <= 31000000000, f'stage {i} packed weights exceed 31 GB; this does not include runtime allocations')
        stages.append(dict(id=i, native_output=str(output / f'stage{i}/native'), first=first, final=final, begin=cuts[i], end=cuts[i+1], bdf=bdf, packed_weight_bytes=packed, argv=argv, environment=environment))
        for flag in ('--dispatch', '--selection'):
            if flag in argv:
                path = Path(option(argv, flag)).resolve()
                pins[str(path)] = digest(path)
    return dict(schema='ownrt.pipeline-driver-plan.v1', config=str(config_path), pins=pins, output=str(output), boundaries=cuts, stages=stages, prompt_tokens=tokens, context=context, max_new=maximum, vocab=vocab, eos=eos, seconds=config['seconds'], grace_seconds=config['grace_seconds'], memory_start_bytes=config['memory_start_bytes'], memory_floor_bytes=config['memory_floor_bytes'], root_floor_bytes=config['root_floor_bytes'], evidence_floor_bytes=config['evidence_floor_bytes'], observer=str(observe_path), model_identity_sha256=digest(auth_path), activation_dtype='F32', mode='target-only', device_execution_requested=False, limits='No speculative overlap or speedup claim. Packed weights exclude host lookups and runtime allocations; native arena cap remains enforced.')


class Guard:
    def __init__(self, plan, admission, stop_fd):
        self.plan, self.stop_fd = plan, stop_fd
        if stop_fd is not None:
            os.fstat(stop_fd)
        self.signal_stop = threading.Event()
        self.deadline = time.monotonic() + plan['seconds']
        self.obs = load_module(plan['observer'], 'pipeline_passive_observer')
        self.baseline = json.loads(Path(admission['baseline']).read_text())
        require(digest(admission['baseline']) == admission['baseline_sha256'], 'admission baseline hash')
        self.identities, self.stoppers, self.lock = {}, [], threading.Lock()
        self.tracked_processes = []
        self.failed, self.done = None, threading.Event()
        self.first_failure, self.failure_evidence_error = None, None
        self.targets = {s['bdf']: self.obs.target_nodes(self.baseline, s['bdf']) for s in plan['stages']}
        self.validate(self.obs.observe(), initial=True)
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def fail(self, reason, *, observation=None, phase=None):
        with self.lock:
            if self.failed is not None:
                return
            self.failed = str(reason)
            self.first_failure = dict(schema='ownrt.pipeline-guard-failure.v1',
                reason=self.failed, exception_type=type(reason).__name__ if isinstance(reason, BaseException) else None,
                phase=phase, utc=datetime.now(timezone.utc).isoformat(),
                monotonic_seconds=time.monotonic(), rejected_observation=None)
            for fd in self.stoppers:
                try:
                    os.write(fd, b'!')
                except OSError:
                    pass
        # Exactly the first writer records evidence, outside the admission lock.
        # Recording errors cannot replace the cause or prevent the stop above.
        try:
            output = Path(self.plan['output'])
            if observation is not None:
                path = output / 'guard-rejected-observation.json'
                try:
                    save(path, observation)
                    self.first_failure['rejected_observation'] = dict(path=str(path), sha256=digest(path))
                except Exception as error:
                    self.first_failure['observation_write_error'] = repr(error)
            save(output / 'guard-first-failure.json', self.first_failure)
        except Exception as error:
            self.failure_evidence_error = repr(error)

    def check(self):
        if time.monotonic() >= self.deadline:
            self.fail('bounded driver lifetime expired')
        if self.signal_stop.is_set():
            self.fail('coordinator signal stop')
        if self.stop_fd is not None and select.select([self.stop_fd], [], [], 0)[0]:
            self.fail('external coordinator stop/EOF')
        if self.failed is not None:
            raise RuntimeError(self.failed)

    def validate_or_stop(self, row, *, phase):
        try:
            self.validate(row)
        except Exception as error:
            self.fail(error, observation=row, phase=phase)
            raise

    def validate(self, row, initial=False):
        require(row['boot'] == self.baseline['boot'] and row['drm'] == self.baseline['drm'], 'boot/DRM changed')
        require(row['kernel']['faults'] == self.baseline['kernel']['faults'] and row['known_fault_baseline_matches'], 'kernel fault baseline changed')
        require(not row['inventory']['errors'] and not row['identity_races'], 'incomplete or identity-raced device holder inventory')
        require(row['memory']['MemAvailable'] >= self.plan['memory_start_bytes' if initial else 'memory_floor_bytes'], 'memory floor')
        require(row['root_free_bytes'] >= self.plan['root_floor_bytes'], 'root free floor')
        import shutil
        require(shutil.disk_usage(Path(self.plan['output']).parent).free >= self.plan['evidence_floor_bytes'], 'evidence free floor')
        with self.lock:
            for h in row['inventory']['holders']:
                node, pid = h['node'], h['pid']
                bdf = next((b for b, nodes in self.targets.items() if node in nodes), None)
                identity = (row['holders'].get(str(pid)) or {}).get('start_ticks')
                registered = self.identities.get(pid)
                if bdf is not None:
                    require(not initial and registered == (identity, bdf), 'foreign/wrong-stage/ambiguous GPU holder')
                if registered:
                    require(bdf == registered[1], 'stage opened non-target card')

    def watch(self):
        while not self.done.wait(3):
            row, phase = None, 'check'
            try:
                self.check()
                phase = 'observe'
                row = self.obs.observe()
                phase = 'validate'
                self.validate_or_stop(row, phase=phase)
                phase = 'record'
                with (Path(self.plan['output']) / 'observations.jsonl').open('a') as out:
                    out.write(json.dumps(row) + '\n')
            except Exception as error:
                self.fail(error, observation=row, phase=phase)
                return


class Stage:
    def __init__(self, spec, plan, guard):
        self.spec, self.guard, self.sequence, self.plan = spec, guard, 0, plan
        self.path = Path(plan['output']) / f"stage{spec['id']}"
        self.path.mkdir(mode=0o700)
        native_output = Path(spec['native_output'])
        require(native_output == self.path / 'native' and option(spec['argv'], '--output') == str(native_output), 'native output path identity')
        require(not os.path.lexists(native_output), 'native output must remain absent until engine creates it')
        self.file = (self.path / 'shared.bin').open('x+b')
        self.file.truncate(SHARED)
        self.shared = mmap.mmap(self.file.fileno(), SHARED)
        self.sock, child = socket.socketpair()
        self.sock.settimeout(0.2)
        read_stop, write_stop = os.pipe()
        argv = [str(child.fileno()) if x == '<channel-fd>' else str(read_stop) if x == '<stop-fd>' else x for x in spec['argv']]
        self.log = (self.path / 'process.log').open('xb')
        try:
            with guard.lock:
                guard.stoppers.append(write_stop)
                # Recheck admission atomically with registration: the observer may
                # have stopped work after execute()'s previous check. Do not call
                # check()/fail() under this nonrecursive lock.
                require(guard.failed is None and not guard.signal_stop.is_set() and time.monotonic() < guard.deadline, 'stage launch cancelled before Popen')
                require(guard.stop_fd is None or not select.select([guard.stop_fd], [], [], 0)[0], 'external stop before Popen')
                self.proc = subprocess.Popen(argv, env=spec['environment'], stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT, pass_fds=(child.fileno(), read_stop))
                # Retain ownership before identity capture or evidence writes can
                # fail. Every spawned child participates in cooperative teardown.
                guard.tracked_processes.append((spec['id'], self.proc))
                identity = guard.obs.process_identity(self.proc.pid)
                require(identity is not None, 'stage PID identity absent')
                guard.identities[self.proc.pid] = (identity['start_ticks'], spec['bdf'])
        finally:
            child.close()
            os.close(read_stop)
        save(self.path / 'launch.json', dict(argv=argv, environment=spec['environment'], pid=self.proc.pid, identity=identity))
        self.stream_bytes = None

    def receive(self, ready=False):
        data, end = bytearray(), time.monotonic() + self.plan['seconds']
        while len(data) < REPLY.size:
            self.guard.check()
            require(time.monotonic() < end, 'bounded stage reply timeout')
            try:
                piece = self.sock.recv(REPLY.size - len(data))
            except socket.timeout:
                continue
            require(piece, 'stage channel closed')
            data.extend(piece)
        r = REPLY.unpack(data)
        require(r[0] == 0 and r[2] == 0 and r[4] == self.sequence, 'stage error/sequence')
        require(r[5] == (0 if self.spec['first'] else 1) and r[6:8] == (self.spec['id'], int(self.spec['final'])), 'reply stage/final identity')
        if ready:
            require(0 < r[3] <= SLOT and r[3] % 4 == 0, 'F32 ready stream extent')
            self.stream_bytes = r[3]
        return r

    def command(self, op, token=0, position=0, fixture=0):
        self.guard.check()
        self.sequence += 1
        self.sock.sendall(REQUEST.pack(op, token, position, fixture, 0, self.sequence, self.spec['id'], int(self.spec['final'])))
        return None if op == 5 else self.receive()


def validate_unit(unit):
    invocation = os.environ.get('INVOCATION_ID')
    require(unit and invocation, 'run without external FD requires a named systemd unit')
    result = subprocess.run(['systemctl', '--user', 'show', unit, '--property=MainPID,InvocationID,Restart,KillMode,SendSIGKILL'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    require(result.returncode == 0 and not result.stderr.strip(), 'unit policy observation failed')
    fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    require(fields.get('InvocationID') == invocation and fields.get('MainPID') == str(os.getpid()), 'unit/driver ownership identity')
    require(fields.get('Restart') == 'no' and fields.get('KillMode') == 'process' and fields.get('SendSIGKILL') == 'no', 'unit must forbid restart and forced child teardown')
    return fields


def execute(plan, admission, stop_fd=None, unit=None):
    require(admission.get('schema') == 'ownrt.pipeline-admission.v1' and admission.get('owner_authorized') is True, 'explicit admission required')
    require(datetime.fromisoformat(admission['expires_utc']) > datetime.now(timezone.utc), 'admission expired')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'launch driver under nice -n 19')
    unit_identity = validate_unit(unit) if stop_fd is None else None
    output = Path(plan['output'])
    guard = Guard(plan, admission, stop_fd)
    prior_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in prior_handlers:
        signal.signal(sig, lambda *_: guard.signal_stop.set())
    output.mkdir(mode=0o700)
    save(output / 'plan.json', plan)
    save(output / 'admission.json', admission)
    if unit_identity is not None:
        save(output / 'unit.json', unit_identity)
    stages, emitted, failure = [], [], None
    started = time.monotonic()
    try:
        guard.thread.start()
        # One load per stage; readiness is checked before admitting token work.
        for spec in plan['stages']:
            guard.check()
            stage = Stage(spec, plan, guard)
            stages.append(stage)
            stage.receive(ready=True)
        require(len({s.stream_bytes for s in stages}) == 1, 'stage stream extents differ')
        guard.validate(guard.obs.observe())
        position, fixture = 0, 0
        token = plan['prompt_tokens'][0]
        with (output / 'tokens.jsonl').open('x') as token_log:
            while True:
                guard.check()
                is_prompt = position < len(plan['prompt_tokens'])
                if is_prompt:
                    token = plan['prompt_tokens'][position]
                fixture = max(0, position - len(plan['prompt_tokens']) + 2)
                step_start = time.monotonic()
                stage_times = []
                for i, stage in enumerate(stages):
                    if i:
                        stage.shared[SLOT:SLOT + stage.stream_bytes] = stages[i-1].shared[:stage.stream_bytes]
                    r = stage.command(1, token, position, fixture)
                    require((stage.spec['final'] and r[3] == 0) or (not stage.spec['final'] and r[3] == stage.stream_bytes and r[1] == -1), 'handoff bytes/token identity')
                    stage_times.append(r[8])
                    stage.command(2, token, position, fixture)
                position += 1
                if fixture:
                    token = r[1]
                    require(0 <= token < plan['vocab'], 'final token bounds')
                    emitted.append(token)
                    token_log.write(json.dumps(dict(position=position, token=token, elapsed_ms=(time.monotonic()-step_start)*1000, stage_ms=stage_times)) + '\n')
                    token_log.flush()
                    if len(emitted) >= plan['max_new'] or token == plan['eos']:
                        break
        for stage in stages:
            stage.command(4, position=2147483647)
        guard.validate(guard.obs.observe())
        for stage in stages:
            stage.command(5)
    except Exception as error:
        failure = repr(error)
        guard.fail(failure)
    finally:
        deadline = time.monotonic() + plan['grace_seconds']
        while any(proc.poll() is None for _, proc in guard.tracked_processes) and time.monotonic() < deadline:
            time.sleep(0.2)
        guard.done.set()
        guard.thread.join(timeout=35)
        if guard.thread.is_alive():
            guard.fail('passive monitor did not quiesce')
        if failure is None:
            try:
                guard.check()
                guard.validate(guard.obs.observe())
            except Exception as error:
                guard.fail(error)
        failure = failure or guard.failed
        # Never kill, restart, reset a driver or mutate host settings.
        alive = [proc.pid for _, proc in guard.tracked_processes if proc.poll() is None]
        codes = {str(stage_id): proc.poll() for stage_id, proc in guard.tracked_processes}
        if alive or any(rc != 0 for rc in codes.values()):
            failure = failure or 'stage failed to exit cleanly'
        for sig, handler in prior_handlers.items():
            signal.signal(sig, handler)
        save(output / 'result.json', dict(passed=failure is None, error=failure, live_pids=alive, returncodes=codes, output_ids=emitted, wall_seconds=time.monotonic()-started, mode='target-only', speed_claim=False, input_position=locals().get('position', 0)))
    require(failure is None, str(failure))
    return output / 'result.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--coordinator-stop-fd', type=int)
    parser.add_argument('--unit', help='own systemd unit; required when no external stop FD')
    args = parser.parse_args()
    if not args.run:
        require(args.config is not None, '--config required for CPU planning')
        plan = make_plan(args.config)
        save(args.plan, plan)
        print(json.dumps(dict(plan=str(args.plan), sha256=digest(args.plan), device_execution_requested=False)))
        return
    require(args.admission is not None and (args.coordinator_stop_fd is not None or args.unit), 'run requires admission and a unit or external coordinator stop fd')
    plan = json.loads(args.plan.read_text())
    require(plan == make_plan(plan['config']), 'plan/input/source/launch identity changed')
    admission = json.loads(args.admission.read_text())
    require(admission.get('plan_sha256') == digest(args.plan), 'admission plan hash mismatch')
    print(execute(plan, admission, args.coordinator_stop_fd, args.unit))


if __name__ == '__main__':
    main()
