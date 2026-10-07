#!/usr/bin/env python3
"""Prepare, then execute ONE durable experiment after protected plan-E releases the host.

Preparation is CPU/read-only with respect to devices. Execution requires a separate
systemd user unit with Restart=no, KillMode=process, SendSIGKILL=no and a generous
TimeoutStopSec. The qualified server owner alone manages its container/guard. No
server retries, device resets, power changes or service restoration. Coordinator
cleanup requests STOP only; the qualified owner retains its existing Docker stop
timeout and emergency memory-guard policy.
"""
import argparse
import errno
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
LANE = ROOT / 'experiments/qwen38-27b-b70'
HERE = Path(__file__).resolve().parent
DURABLE = HERE / 'durable'
DATA = LANE / 'data/2026-10-06-durable-context'
LAUNCHER = LANE / 'scripts/run-fp8-tp1-server.py'
HELPER = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
HEALTH = ROOT / 'scripts/check-qwen36-xpu-xccl-health.sh'
STRICT = ROOT / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh'
COMPARE = ROOT / 'scripts/compare-strict-attempt-outputs.py'
REFERENCE = Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-strict')
IMAGE = 'sha256:8b78916004ca6581822b6e1f06791f94586a6c1d265c3f63b81b49c09bee1525'
DEFAULT_LAUNCH = Path('/mnt/fast-ai/bench-results/context-planE-a1/tp2-planE-w262144/launch.json')
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
STOP_REQUESTED = False
HOST_LOCK = Path('/tmp/context-durable-host.lock')
MODEL_LOCK = Path('/tmp/context-durable-model.lock')
STAGE_LOCK = Path('/tmp/qwen-short-prefill-stage.lock')


@contextmanager
def file_lock(path):
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield handle


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as handle:
        json.dump(value, handle, indent=2); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)


def status(out, phase, **details):
    value = {'at': now(), 'phase': phase, **details}
    atomic(out / 'status.json', value)
    with (out / 'lifecycle.jsonl').open('a') as handle:
        handle.write(json.dumps(value) + '\n'); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps(value), flush=True)


def read_command(args, *, timeout=20, allow=(0,)):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=timeout)
    if result.returncode not in allow:
        raise RuntimeError(f'{args[0]} inspection failed (exit {result.returncode})')
    return result


def process_identity(pid, proc_root=Path('/proc')):
    try:
        raw = (proc_root / str(pid) / 'stat').read_text()
        tail = raw[raw.rfind(')')+2:].split()
        return {'pid': pid, 'start_ticks': tail[19], 'state': tail[0],
                'cmdline_sha256': sha(proc_root / str(pid) / 'cmdline')}
    except FileNotFoundError:
        return None


def same_process(original, current):
    return bool(current and current['state'] != 'Z' and current['start_ticks'] == original['start_ticks'])


def conflicting_processes(proc_root=Path('/proc')):
    found = []
    for path in proc_root.glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().decode(errors='replace').split('\0')
        except FileNotFoundError:
            continue
        # No command strings are persisted: they may contain credentials.
        if (any(Path(a).name == 'harbor' for a in args)
                or (any(Path(a).name == 'supervise.sh' for a in args) and 'planE' in args)):
            found.append(int(path.parent.name))
    return sorted(found)


def profile_args(launch):
    rung = launch['rung']
    expected = {'tp': 2, 'mem': .95, 'max_model_len': 262144, 'batched': 832, 'seqs': 1,
                'mtp': 5, 'draft_int4': True, 'fa_verify_rows': True, 'prefix_cache': 'align'}
    if rung.get('image') != IMAGE or any(rung.get(k) != v for k, v in expected.items()):
        raise ValueError('protected launch is not the expected qualified PlanE profile')
    if rung.get('cpu_embed') or rung.get('eager') or rung.get('mount_file') or rung.get('mount_dir'):
        raise ValueError('unsupported changes in protected launch')
    args = ['--image', IMAGE, '--tp', '2', '--mem', '.95', '--max-model-len', '262144',
            '--batched', '832', '--seqs', '1', '--mtp', '5', '--draft-int4',
            '--shortlist', rung['shortlist'], '--fa-verify-rows', '--prefix-cache', 'align']
    for key in ('extra_env', 'overlay', 'env'):
        for value in rung.get(key, []):
            args.extend(['--' + key.replace('_', '-'), value])
    args.extend('--serve-arg=' + value for value in rung.get('serve_arg', []))
    return args


def dependencies(launch_path, launch):
    files = {Path(__file__).resolve(), LAUNCHER, HELPER, HEALTH, STRICT, COMPARE,
             ROOT / 'tools/xccl_probe.py', LANE / 'scripts/host_memory_guard.py',
             ROOT / 'scripts/bench-openai-realistic-suite.py', ROOT / 'scripts/neural-download-canaries.py',
             ROOT / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json',
             LANE / 'notes/2026-10-06-durable-context-prereg.md', Path(launch_path).resolve(),
             Path('/mnt/fast-ai/bench-results/optimization-validation-20260915/restored-service/container-inspect.json')}
    files.update(p for p in DURABLE.glob('*.py') if not p.name.startswith('test_'))
    files.update(DATA.rglob('*.json'))
    files.update(p for p in REFERENCE.rglob('*') if p.is_file())
    for overlay in launch['rung']['overlay'] + ['b70-fa-verify-rows']:
        directory = LANE / 'overlays' / overlay
        if not directory.is_dir():
            raise ValueError(f'missing qualified overlay {overlay}')
        files.update(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and not p.name.startswith('test_'))
    return {str(path): sha(path) for path in sorted(files)}


def verify_dependencies(config):
    changed = [path for path, digest in config['dependency_sha256'].items()
               if not Path(path).is_file() or sha(path) != digest]
    if changed:
        raise RuntimeError('frozen dependencies changed: ' + ', '.join(changed[:5]))
    launch = json.loads(Path(config['protected_launch']).read_text())
    if dependencies(config['protected_launch'], launch) != config['dependency_sha256']:
        raise RuntimeError('frozen dependency inventory changed (including added runtime files)')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != config['boot_id']:
        raise RuntimeError('host rebooted since queue preparation; requalify manually')


def health_env():
    # Do not let ambient variables silently turn the two-card collective gate off.
    return {'PYTHON': str(Path.home() / '.venvs/vllm-xpu/bin/python'),
            'ROOT': str(ROOT), 'PHYSICAL_DEVICES': '0,1', 'XCCL_DEVICES': '0,1',
            'XCCL_NPROC': '2', 'XPU_HEALTH_SKIP_XCCL': '0', 'TIMEOUT_S': '90',
            'PYTHONOPTIMIZE': '', 'ONEAPI_DEVICE_SELECTOR': 'level_zero:0,1',
            'ZE_AFFINITY_MASK': '0,1', 'CCL_ATL_TRANSPORT': 'ofi',
            'CCL_TOPO_P2P_ACCESS': '1', 'FI_TCP_IFACE': 'lo',
            'CCL_KVS_IFACE': 'lo', 'XCCL_MASTER_PORT': '29500'}


def prepare(out, supervisor_pid, launch_path=DEFAULT_LAUNCH):
    if socket.gethostname() != 'steve-TURIND8-2L2T':
        raise RuntimeError('this frozen lifecycle is for the two-card host only')
    owner = process_identity(supervisor_pid)
    if not owner:
        raise RuntimeError('protected supervisor identity must be captured while it is running')
    args = Path(f'/proc/{supervisor_pid}/cmdline').read_bytes().decode(errors='replace').split('\0')
    if 'planE' not in args or not any(Path(a).name == 'supervise.sh' for a in args):
        raise RuntimeError('selected PID is not the protected planE supervisor')
    launch = json.loads(Path(launch_path).read_text())
    config = {'schema': 'durable-host-queue.v1', 'prepared_at': now(),
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'supervisor': owner, 'protected_launch': str(Path(launch_path).resolve()),
              'protected_root': str(Path(launch_path).parents[2]),
              'server_args': profile_args(launch), 'port': 18196, 'model': 'qwen38-27b-fp8',
              'expected_launch_identity': {key: launch[key] for key in
                  ('overlay_sha256', 'reference_sha256', 'guard_sha256')},
              'guard_min_available_gib': 1.6, 'prelaunch_available_gib': 11,
              'min_disk_free_gib': 5, 'max_wait_seconds': 172800,
              'dependency_sha256': dependencies(launch_path, launch)}
    out.mkdir(parents=True, exist_ok=False)
    atomic(out / 'queue.json', config)
    status(out, 'prepared', supervisor_pid=supervisor_pid, device_actions=False)
    return config


def prepare_after_prelaunch_failure(out, previous):
    """Explicit new attempt after a failed handoff; never restart a model trial."""
    previous = previous.resolve()
    with file_lock(HOST_LOCK), file_lock(previous / 'coordinator.lock'):
        prior = json.loads((previous / 'queue.json').read_text())
        last = json.loads((previous / 'status.json').read_text())
        if last.get('phase') != 'failed' or any((previous / name).exists() for name in
                ('preflight-health.command.json', 'server-owner.command.json', 'server')):
            raise RuntimeError('previous attempt is not a failed handoff before device work')
        if socket.gethostname() != 'steve-TURIND8-2L2T' or prior['boot_id'] != Path(
                '/proc/sys/kernel/random/boot_id').read_text().strip():
            raise RuntimeError('host/boot changed since previous attempt')
        launch = json.loads(Path(prior['protected_launch']).read_text())
        fresh = dependencies(prior['protected_launch'], launch)
        own = str(Path(__file__).resolve())
        if ({k: v for k, v in fresh.items() if k != own} !=
                {k: v for k, v in prior['dependency_sha256'].items() if k != own}):
            raise RuntimeError('dependencies other than the coordinator changed')
        reason = release_reason(prior)
        if reason:
            raise RuntimeError('protected work is not released: ' + reason)
        # Keep the original fault baseline, not just faults since this new attempt.
        fault_check(prior, previous)
        config = {**prior, 'prepared_at': now(),
                  'fault_baseline_at': prior.get('fault_baseline_at', prior['prepared_at']),
                  'dependency_sha256': fresh,
                  'previous_prelaunch_failure': {'directory': str(previous),
                      'artifacts': {name: sha(previous / name) for name in
                                    ('queue.json', 'status.json', 'lifecycle.jsonl')}}}
        out.mkdir(parents=True, exist_ok=False)
        atomic(out / 'queue.json', config)
        status(out, 'prepared', previous_prelaunch_failure=str(previous), device_actions=False)
        return config


def fault_check(config, out):
    result = read_command(['journalctl', '-k', '-b', '--no-pager', '-o', 'short-iso',
                           '--since', config.get('fault_baseline_at', config['prepared_at'])])
    if re.search(r'permission|not seeing messages|No journal files', result.stderr, re.I):
        raise RuntimeError('kernel journal access unavailable')
    faults = [line for line in result.stdout.splitlines() if FAULT.search(line)]
    if faults:
        atomic(out / 'FAULT-HALT.json', {'at': now(), 'lines': faults})
        (out / 'fault-kernel.log').write_text(result.stdout)
        raise RuntimeError('GPU fault since queue baseline; no launch/recovery/retry')


def release_reason(config):
    if same_process(config['supervisor'], process_identity(config['supervisor']['pid'])):
        return 'protected supervisor is still running'
    conflicts = conflicting_processes()
    if conflicts:
        return f'protected supervisor or Harbor clients remain: {conflicts}'
    result = read_command(['systemctl', '--user', 'list-units', '--all', '--plain', '--no-legend',
                           '--no-pager', 'ctx-planE-*', 'ctx-watchdog-planE-*'])
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 4 and columns[2] in {'active', 'activating', 'deactivating', 'reloading'}:
            return 'protected planE unit or watchdog is still active'
    root = Path(config['protected_root'])
    attempts = sorted(root.glob('context-planE-a*'), key=lambda p: int(p.name.rsplit('a', 1)[1]))
    if not attempts:
        raise RuntimeError('protected attempt evidence is missing')
    latest = attempts[-1]
    log = latest / 'tp2-planE-w262144-client.log'
    if not log.exists() or not any(line == '### plan complete' for line in log.read_text(errors='replace').splitlines()):
        raise RuntimeError('protected supervisor ended without a completed plan; no launch')
    for attempt in attempts:
        state_path = attempt / 'tp2-planE-w262144/state.json'
        if not state_path.exists():
            raise RuntimeError('protected server stop receipt is missing')
        state = json.loads(state_path.read_text())
        if state.get('status') not in {'stopped', 'failed', 'stopped-before-ready'} or state.get('stop_confirmed') is not True:
            return 'protected server has not confirmed a stop'
        owner_cmd = Path(f'/proc/{state["owner_pid"]}/cmdline')
        if owner_cmd.exists():
            args = owner_cmd.read_bytes().decode(errors='replace').split('\0')
            if str(state_path.parent) in args and any(Path(a).name == LAUNCHER.name for a in args):
                return 'protected server owner process remains'
    return None


def load_helper():
    spec = importlib.util.spec_from_file_location('durable_qualified_helper', HELPER)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def wait_available(config, out, helper, *, timeout=180, monitor_faults=True):
    """Allow bounded socket teardown; never evict a listener or ignore other conflicts."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            helper.check_available(config['port'], 'durable-preflight-no-container')
            return
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
            if STOP_REQUESTED:
                raise RuntimeError('stop requested during port release') from exc
            if time.monotonic() >= deadline:
                raise RuntimeError('server port did not release within 180 seconds') from exc
            if monitor_faults:
                fault_check(config, out)
            # Preserve the experiment phase in status.json; this detail lives in the log.
            print(f'Waiting for port {config["port"]} to release', flush=True)
            time.sleep(3)


def resource_check(config, out, helper):
    """Call under a held stage lease before/after the bounded GPU health probe."""
    wait_available(config, out, helper)
    info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(info['MemAvailable'].split()[0]) * 1024
    if available < config['prelaunch_available_gib'] * 1024**3:
        raise RuntimeError('insufficient host memory for the qualified two-card load')
    if shutil.disk_usage(out).free < config['min_disk_free_gib'] * 1024**3:
        raise RuntimeError('insufficient output storage')


def stop_client(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)  # only this coordinator's CPU client group
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise RuntimeError('owned client did not terminate gracefully; no forced kill')


def monitored_command(args, name, out, config, *, env=None, server=None, timeout=7200):
    atomic(out / (name + '.command.json'), {'argv': list(map(str, args)), 'at': now()})
    with (out / (name + '.log')).open('x') as handle:
        proc = subprocess.Popen(list(map(str, args)), cwd=ROOT, env=dict(os.environ, **(env or {})),
                                stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + timeout
            while proc.poll() is None:
                if STOP_REQUESTED:
                    raise RuntimeError('coordinator received stop signal')
                fault_check(config, out)
                if server is not None and server.proc.poll() is not None:
                    raise RuntimeError('owned server exited during client work')
                if time.monotonic() > deadline:
                    raise RuntimeError('client deadline exceeded; no retry')
                time.sleep(2)
            if proc.returncode:
                raise RuntimeError(f'{name} exited {proc.returncode}; no retry')
        finally:
            stop_client(proc)
    fault_check(config, out)


class OwnedServer:
    def __init__(self, out, config):
        self.out, self.config = out / 'server', config
        self.handle = (out / 'server-owner.log').open('x')
        argv = [sys.executable, str(LAUNCHER), '--out', str(self.out), '--port', str(config['port']),
                '--warmup', '--keep', '--startup-timeout', '1800', *config['server_args']]
        atomic(out / 'server-owner.command.json', {'argv': argv, 'at': now()})
        self.proc = subprocess.Popen(argv, cwd=ROOT, stdout=self.handle, stderr=subprocess.STDOUT,
                                     env=dict(os.environ, B70_GUARD_MIN_AVAILABLE_GIB='1.6'))

    def wait_ready(self, queue_out):
        deadline = time.monotonic() + 1900
        while time.monotonic() < deadline:
            fault_check(self.config, queue_out)
            if STOP_REQUESTED:
                raise RuntimeError('stop requested during startup')
            path = self.out / 'state.json'
            state = json.loads(path.read_text()) if path.exists() else {}
            if self.proc.poll() is not None or state.get('status') == 'failed':
                raise RuntimeError('server failed before ready; no restart')
            if state.get('status') == 'ready':
                return state
            time.sleep(3)
        raise RuntimeError('server startup timeout; no retry')

    def stop(self):
        if self.out.exists():
            (self.out / 'STOP').touch()
        try:
            self.proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            raise RuntimeError('owned server did not exit after STOP; no forced kill')
        finally:
            self.handle.close()
        path = self.out / 'state.json'
        if not path.exists():
            if self.proc.returncode:
                return {'status': 'never-started', 'stop_confirmed': True}
            raise RuntimeError('owned server exited without stop receipt')
        state = json.loads(path.read_text())
        if state.get('stop_confirmed') is not True:
            raise RuntimeError('owned server stop was not confirmed')
        return state


def strict_passed(result):
    comparison, qualification = result.get('comparison', {}), result.get('qualification', {})
    return (result.get('schema') == 'neural.download.strict-attempt-output-comparison.v1'
            and comparison.get('exact_prompts') == 12 and comparison.get('total_prompts') == 12
            and comparison.get('complete_token_arrays_exact') is True
            and qualification.get('all_workload_and_canary_gates_passed') is True
            and qualification.get('strict_pair_qualified') is True)


def execute(out):
    config = json.loads((out / 'queue.json').read_text())
    with file_lock(HOST_LOCK), file_lock(out / 'coordinator.lock'):
        if (out / 'execution-started.json').exists():
            raise RuntimeError('one-shot coordinator was already executed; no retry/resume')
        atomic(out / 'execution-started.json', {'at': now(), 'pid': os.getpid()})
        server = None
        failure = None
        try:
            verify_dependencies(config)
            deadline = time.monotonic() + config['max_wait_seconds']
            while True:
                if STOP_REQUESTED:
                    raise RuntimeError('stop requested while waiting')
                fault_check(config, out)
                reason = release_reason(config)
                if not reason:
                    break
                status(out, 'waiting', reason=reason)
                if time.monotonic() >= deadline:
                    raise RuntimeError('protected work did not release host before wait deadline')
                time.sleep(30)
            verify_dependencies(config)
            helper = load_helper()
            with file_lock(MODEL_LOCK):
                with file_lock(STAGE_LOCK):
                    resource_check(config, out, helper)
                    status(out, 'preflight')
                    monitored_command(['bash', HEALTH], 'preflight-health', out, config,
                        env=health_env(), timeout=180)
                    resource_check(config, out, helper)
                verify_dependencies(config)
                status(out, 'launching-one-server')
                server = OwnedServer(out, config)
                server.wait_ready(out)
                launch = server.out / 'launch.json'
                identity = json.loads(launch.read_text())
                if (profile_args(identity) != config['server_args'] or any(
                        identity.get(key) != value for key, value in config['expected_launch_identity'].items())):
                    raise RuntimeError('actual server/overlay/reference identity differs from frozen qualified profile')
                base = f'http://127.0.0.1:{config["port"]}'
                strict_out = out / 'strict'
                status(out, 'strict-quality-gate')
                monitored_command(['bash', STRICT], 'strict', out, config, server=server, timeout=2400,
                                  env={'BASE_URL': base, 'MODEL_NAME': config['model'], 'OUT_DIR': str(strict_out),
                                       'PROFILE_LABEL': 'durable-planE-profile', 'ATTEMPT_LABEL': 'durable-one-server'})
                comparison = out / 'strict-comparison.json'
                monitored_command([sys.executable, COMPARE, strict_out, REFERENCE, '--output', comparison],
                                  'strict-compare', out, config, server=server, timeout=120)
                if not strict_passed(json.loads(comparison.read_text())):
                    raise RuntimeError('strict standing-reference qualification failed; holdout untouched')
            calibration = []
            for style in ('report', 'dispatch'):
                verify_dependencies(config)
                dest = out / ('extraction-' + style)
                status(out, 'development-extraction', style=style)
                monitored_command([sys.executable, DURABLE / 'extraction.py', '--task',
                    DATA / f'development/{style}-seed7.json', '--out', dest, '--endpoint', base + '/v1',
                    '--model', config['model'], '--server-identity', launch],
                    'extract-' + style, out, config, server=server)
                result = dest / 'result.json'
                if json.loads(result.read_text()).get('gate_passed') is not True:
                    raise RuntimeError(f'{style} development gate failed; holdout untouched')
                calibration.append(result)
            verify_dependencies(config)
            status(out, 'heldout-pilot')
            monitored_command([sys.executable, DURABLE / 'campaign.py', '--suite', DATA / 'holdout/suite.json',
                '--out', out / 'pilot', '--execute', '--endpoint', base + '/v1', '--model', config['model'],
                '--server-identity', launch, '--calibration', *calibration],
                'pilot', out, config, server=server, timeout=43200)
            status(out, 'client-complete', summary=str(out / 'pilot/summary.json'))
        except BaseException as exc:
            failure = exc
            status(out, 'failed', error=f'{type(exc).__name__}: {exc}')
        finally:
            if server is not None:
                stop_attempted = False
                try:
                    # STOP is unconditional even if a noncooperating client now holds the model lock.
                    with file_lock(MODEL_LOCK):
                        stop_attempted = True
                        stopped = server.stop()
                        atomic(out / 'server-stop.json', stopped)
                        with file_lock(STAGE_LOCK):
                            wait_available(config, out, load_helper(), monitor_faults=False)
                        atomic(out / 'cards-released.json', {'at': now(), 'verified': True})
                except BaseException as cleanup_error:
                    if not stop_attempted:
                        try:
                            atomic(out / 'server-stop.json', server.stop())
                        except BaseException as stop_error:
                            status(out, 'cleanup-failed', error=str(stop_error), original_error=str(failure))
                    status(out, 'cleanup-failed', error=str(cleanup_error), original_error=str(failure))
                    if failure is None:
                        failure = cleanup_error
        if failure is not None:
            raise failure
        try:
            fault_check(config, out)
            with file_lock(MODEL_LOCK), file_lock(STAGE_LOCK):
                resource_check(config, out, load_helper())
                monitored_command(['bash', HEALTH], 'postflight-health', out, config,
                    env=health_env(), timeout=180)
        except BaseException as exc:
            status(out, 'failed', error=f'postflight: {type(exc).__name__}: {exc}')
            raise
        status(out, 'completed', cards_released=True, server_restarts=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true'); mode.add_argument('--execute', action='store_true')
    parser.add_argument('--supervisor-pid', type=int, default=1430254)
    parser.add_argument('--protected-launch', type=Path, default=DEFAULT_LAUNCH)
    parser.add_argument('--from-prelaunch-failure', type=Path,
                        help='explicit new queue from a preserved failure before any device work')
    args = parser.parse_args()
    def stop(*_):
        global STOP_REQUESTED
        STOP_REQUESTED = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    if args.prepare:
        if args.from_prelaunch_failure:
            prepare_after_prelaunch_failure(args.out.resolve(), args.from_prelaunch_failure)
        else:
            prepare(args.out.resolve(), args.supervisor_pid, args.protected_launch)
    else:
        if args.from_prelaunch_failure:
            parser.error('--from-prelaunch-failure is preparation only')
        execute(args.out.resolve())


if __name__ == '__main__':
    main()
