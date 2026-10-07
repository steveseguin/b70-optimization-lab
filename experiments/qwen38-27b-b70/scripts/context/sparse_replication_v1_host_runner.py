#!/usr/bin/env python3
"""Prepare, then execute ONE fresh sparse-state replication on an idle host.

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
import math
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
SEMANTIC = HERE / 'semantic_v1'
SPARSE = HERE / 'sparse_replication_v1'
DATA = LANE / 'data/2026-10-07-sparse-state-replication'
PRIOR_PACKET = LANE / 'data/2026-10-07-sparse-state-development'
PRIOR_AUDIT = LANE / 'data/2026-10-07-sparse-state-result/audit.json'
LAUNCHER = LANE / 'scripts/run-fp8-tp1-server.py'
HELPER = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
HEALTH = ROOT / 'scripts/check-qwen36-xpu-xccl-health.sh'
STRICT = ROOT / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh'
COMPARE = ROOT / 'scripts/compare-strict-attempt-outputs.py'
REFERENCE = Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-strict')
IMAGE = 'sha256:8b78916004ca6581822b6e1f06791f94586a6c1d265c3f63b81b49c09bee1525'
DEFAULT_PREVIOUS = Path('/mnt/fast-ai/bench-results/context-sparse-v1-20261007')
DEFAULT_LAUNCH = Path('/mnt/fast-ai/bench-results/context-planE-a1/tp2-planE-w262144/launch.json')
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
STOP_REQUESTED = False
HOST_LOCK = Path('/tmp/context-durable-host.lock')
MODEL_LOCK = Path('/tmp/context-durable-model.lock')
STAGE_LOCK = Path('/tmp/qwen-short-prefill-stage.lock')
CACHE_POLICY = {'prefix_cache': 'off', 'every_request_cached_tokens': 0,
                'cache_metadata_required': True, 'arms': ['archive', 'quoted']}
NATIVE_PROTOCOL = 'semantic-development-live-v1'
SPARSE_PROTOCOL = 'sparse-state-replication-v1'
ANSWER_GENERATION = {'enable_thinking': True, 'reasoning_effort': 'medium', 'max_tokens': 8192}
INGESTION_GENERATION = {'enable_thinking': False, 'max_tokens': 4096}
NATIVE_LIMITS = {'context_limit_utf8_bytes': 32768, 'memory_limit_utf8_bytes': 6553,
                 'max_retrieval': 24, 'max_answer_calls': 32, 'max_ingestion_attempts': 3}


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
    results = {name: str(out / relative) for name, relative in {
        'strict': 'strict-comparison.json', 'diagnostic': 'diagnostic/summary.json'
    }.items() if (out / relative).exists()}
    value = {'at': now(), 'phase': phase, 'available_results': results, **details}
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
        if (any(Path(a).name in {'harbor', LAUNCHER.name} for a in args)
                or (any(Path(a).name == 'supervise.sh' for a in args) and 'planE' in args)):
            found.append(int(path.parent.name))
    return sorted(found)


def profile_args(launch, *, prefix_cache='off'):
    rung = launch['rung']
    expected = {'tp': 2, 'mem': .95, 'max_model_len': 262144, 'batched': 832, 'seqs': 1,
                'mtp': 5, 'draft_int4': True, 'fa_verify_rows': True, 'prefix_cache': prefix_cache}
    if rung.get('image') != IMAGE or any(rung.get(k) != v for k, v in expected.items()):
        raise ValueError('launch is not the expected pinned profile and prefix-cache policy')
    if rung.get('cpu_embed') or rung.get('eager') or rung.get('mount_file') or rung.get('mount_dir'):
        raise ValueError('unsupported changes in protected launch')
    args = ['--image', IMAGE, '--tp', '2', '--mem', '.95', '--max-model-len', '262144',
            '--batched', '832', '--seqs', '1', '--mtp', '5', '--draft-int4',
            '--shortlist', rung['shortlist'], '--fa-verify-rows', '--prefix-cache', prefix_cache]
    for key in ('extra_env', 'overlay', 'env'):
        for value in rung.get(key, []):
            args.extend(['--' + key.replace('_', '-'), value])
    for value in rung.get('serve_arg', []):
        if 'prefix-cach' in value or 'mamba-cache' in value:
            if prefix_cache != 'align' or value != '--prefix-cache-retention-interval=13312':
                raise ValueError('unsupported cache override in server arguments')
        args.append('--serve-arg=' + value)
    return args



def derive_cold_launch(qualified):
    """Record a prospective profile; historical qualified evidence remains untouched."""
    profile_args(qualified, prefix_cache='align')
    cold = json.loads(json.dumps(qualified))
    cold['rung']['prefix_cache'] = 'off'
    # Validate actual launch.json before the first model request (strict qualification).
    cold['rung']['warmup'] = False
    cold['rung']['serve_arg'] = [arg for arg in cold['rung'].get('serve_arg', [])
                                if arg != '--prefix-cache-retention-interval=13312']
    profile_args(cold)
    return cold


def effective_profile(launch):
    return {key: value for key, value in launch['rung'].items() if key != 'out'}


def verify_cold_emission(launch):
    profile_args(launch)
    if launch['rung'].get('warmup') is not False:
        raise RuntimeError('owner warmup must be disabled before cold-profile validation')
    argv = launch.get('argv')
    if (not isinstance(argv, list) or any(not isinstance(x, str) for x in argv)
            or argv.count(IMAGE) != 1):
        raise RuntimeError('actual launch lacks unambiguous pinned image argv')
    command = argv[argv.index(IMAGE) + 1:]
    if command.count('--no-enable-prefix-caching') != 1:
        raise RuntimeError('cold launch must explicitly disable prefix caching once')
    for argument in command:
        if (argument.startswith('--enable-prefix-caching')
                or argument.startswith('--no-enable-prefix-caching=')
                or argument.startswith('--mamba-cache-mode')
                or argument.startswith('--prefix-cache-retention-interval')):
            raise RuntimeError('actual launch contains a prefix-cache enabling or mode override')


def dependencies(launch_path, launch, packet=DATA):
    files = {Path(__file__).resolve(), LAUNCHER, HELPER, HEALTH, STRICT, COMPARE,
             ROOT / 'tools/xccl_probe.py', LANE / 'scripts/host_memory_guard.py',
             ROOT / 'scripts/bench-openai-realistic-suite.py', ROOT / 'scripts/neural-download-canaries.py',
             ROOT / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json',
             LANE / 'notes/2026-10-07-sparse-state-replication-plan.md', Path(launch_path).resolve(),
             Path('/mnt/fast-ai/bench-results/optimization-validation-20260915/restored-service/container-inspect.json')}
    files.update(p for p in SEMANTIC.glob('*.py') if not p.name.startswith('test_'))
    files.update(p for p in SPARSE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                 and not p.name.startswith('test_'))
    files.update(Path(packet).rglob('*.json'))
    files.update(Path(packet).rglob('*.md'))
    files.update(PRIOR_PACKET/name for name in
                 ('sparse-n128-seed83-document.json','sparse-n128-seed83-task.json'))
    budget = json.loads((Path(packet) / 'budget-receipt.json').read_text())
    files.update((Path(budget['tokenizer_path']), Path(budget['tokenizer_python'])))
    files.update(p for p in REFERENCE.rglob('*') if p.is_file())
    for overlay in launch['rung']['overlay'] + ['b70-fa-verify-rows']:
        directory = LANE / 'overlays' / overlay
        if not directory.is_dir():
            raise ValueError(f'missing qualified overlay {overlay}')
        files.update(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and not p.name.startswith('test_'))
    return {str(path): sha(path) for path in sorted(files)}


def verify_dependencies(config):
    if socket.gethostname() != config['hostname']:
        raise RuntimeError('prepared host identity changed')
    for path, digest in config['previous_revision']['artifacts'].items():
        if not Path(path).is_file() or sha(path) != digest:
            raise RuntimeError('previous revision release evidence changed')
    changed = [path for path, digest in config['dependency_sha256'].items()
               if not Path(path).is_file() or sha(path) != digest]
    if changed:
        raise RuntimeError('frozen dependencies changed: ' + ', '.join(changed[:5]))
    launch = json.loads(Path(config['protected_launch']).read_text())
    if dependencies(config['protected_launch'], launch, config['packet']) != config['dependency_sha256']:
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


def previous_receipts(previous):
    previous = Path(previous).resolve()
    required = ('queue.json', 'status.json', 'lifecycle.jsonl', 'server-stop.json',
                'cards-released.json', 'server/state.json', 'server/launch.json',
                'diagnostic/summary.json', 'diagnostic-host-audit.json',
                'postflight-health.command.json', 'postflight-health.log', 'strict-comparison.json')
    frozen = {str(previous / name): sha(previous / name) for name in required}
    frozen[str(PRIOR_AUDIT)] = sha(PRIOR_AUDIT)
    queue = json.loads((previous / 'queue.json').read_text())
    stop = json.loads((previous / 'server-stop.json').read_text())
    state = json.loads((previous / 'server/state.json').read_text())
    cards = json.loads((previous / 'cards-released.json').read_text())
    status_value = json.loads((previous / 'status.json').read_text())
    diagnostic = json.loads((previous / 'diagnostic/summary.json').read_text())
    audit = json.loads(PRIOR_AUDIT.read_text())
    if (status_value.get('phase') != 'completed'
            or diagnostic.get('schema') != 'sparse-state-summary.v1'
            or diagnostic.get('protocol') != 'sparse-state-development-v1'
            or diagnostic.get('measurement_kind') != 'model'
            or diagnostic.get('status') != 'completed'
            or diagnostic.get('infrastructure_abort') is not False
            or any(type(diagnostic.get(key)) is not int or diagnostic[key] != 4
                   for key in ('expected_trials', 'observed_trials', 'completed_trials'))
            or type(diagnostic.get('failed_trials')) is not int or diagnostic['failed_trials'] != 0):
        raise RuntimeError('previous sparse diagnostic has not completed its full matrix')
    if (audit.get('schema') != 'sparse-native-audit.v1'
            or not isinstance(audit.get('output'), str) or Path(audit['output']).resolve() != previous
            or audit.get('measurement_kind') != 'model' or audit.get('infrastructure_abort') is not False
            or any(type(audit.get(key)) is not int for key in
                   ('planned_trials', 'completed_trials', 'failed_trials', 'unstarted_trials', 'incomplete_trials'))
            or audit['planned_trials'] != 4 or audit['completed_trials'] != 4
            or any(audit[k] != 0 for k in ('failed_trials','unstarted_trials','incomplete_trials'))
            or audit.get('packet_plan_sha256') != queue['dependency_sha256'].get(str(PRIOR_PACKET/'plan.json'))
            or audit.get('packet_plan_sha256') != sha(PRIOR_PACKET/'plan.json')
            or audit.get('speed_gate_passed') is not False or audit.get('holdout_admitted') is not False):
        raise RuntimeError('independent sparse audit receipt does not qualify this handoff')
    pair = audit.get('pairs', {}).get('128', {})
    if any(pair.get(key) is not True for key in ('paired_quality','cold_comparison_eligible',
                                                'at_least_10_percent_lower_elapsed','replication_signal')):
        raise RuntimeError('independent 128-counter replication signal is absent')
    expected = [('sparse-n8-seed83','archive'),('sparse-n8-seed83','quoted'),
                ('sparse-n128-seed83','quoted'),('sparse-n128-seed83','archive')]
    rows=audit.get('trials')
    if (not isinstance(rows,list) or [(r.get('case_id'),r.get('arm')) for r in rows] != expected
            or [(r.get('case_id'),r.get('arm')) for r in diagnostic.get('trials',[])] != expected):
        raise RuntimeError('independent sparse audit does not retain the four ordered trials')
    prior_elapsed={}
    for row in rows:
        native_audit=row['native_audit']
        case,arm=row['case_id'],row['arm']
        if type(row.get('counter_count')) is not int or row['counter_count'] != (128 if 'n128-' in case else 8):
            raise RuntimeError('independent prior counter-count identity differs')
        trial=previous/'diagnostic'/f'{case}-{arm}'
        native=trial/'native/result.json'
        bindings={trial/'result.json':row['outer_sha256'], native:row['native_sha256'],
                  trial/'native/calls.jsonl':native_audit['calls_sha256']}
        if (row.get('status') != 'completed' or native_audit.get('status') != 'completed'
                or native_audit.get('measurement_kind') != 'model'
                or native_audit.get('document_id') != case or native_audit.get('arm') != arm
                or native_audit.get('result_sha256') != row['native_sha256']):
            raise RuntimeError('independent prior native identity differs')
        if row.get('counter_count') == 128 and (
                any(row.get(k) is not True for k in ('quality_passed','reference_checks_passed','cold_cost_interpretation'))
                or any(native_audit.get(k) is not True for k in ('cold_cache_known','delivered_text_exact','source_delivery_complete'))
                or any(type(native_audit.get(k)) is not int or native_audit[k] != 24
                       for k in ('correct','asked','delivered_batches','checkpoints_checked','checkpoints_exact'))):
            raise RuntimeError('128-counter reference, exact-state or cold audit does not qualify')
        record=json.loads(native.read_text())
        if row['counter_count']==128:
            elapsed=record.get('wall_seconds')
            if (type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<=0
                    or type(row.get('total_trial_wall_seconds')) not in (int,float)
                    or row['total_trial_wall_seconds']!=elapsed):
                raise RuntimeError('prior elapsed cost is not bound to finite native wall time')
            prior_elapsed[arm]=elapsed
        for name, entry in record.get('artifacts',{}).items():
            path=trial/'native'/name
            if (Path(name).is_absolute() or not path.resolve().is_relative_to(trial/'native')
                    or entry.get('path') != name):
                raise RuntimeError('prior native artifact path is unsafe')
            bindings[path]=entry['sha256']
        for path,digest in bindings.items():
            if sha(path) != digest:
                raise RuntimeError('independent sparse audit artifact binding changed')
            frozen[str(path)]=digest
        for path in (trial/'native').iterdir():
            if path.is_file() and (path.suffix in ('.json','.jsonl') or path.name.startswith('canonical.sqlite')):
                frozen[str(path)]=sha(path)
    if set(prior_elapsed) != {'archive','quoted'} or prior_elapsed['quoted'] > .9*prior_elapsed['archive']:
        raise RuntimeError('native prior elapsed costs do not meet the registered replication trigger')
    frozen[str(PRIOR_PACKET/'plan.json')]=sha(PRIOR_PACKET/'plan.json')
    if not strict_passed(json.loads((previous/'strict-comparison.json').read_text())):
        raise RuntimeError('prior strict qualification is incomplete')
    verify_cold_emission(json.loads((previous/'server/launch.json').read_text()))
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if queue['boot_id'] != boot or stop.get('boot_id') != boot or state.get('boot_id') != boot:
        raise RuntimeError('previous experiment release receipts belong to a different boot')
    if (stop.get('stop_confirmed') is not True or state.get('stop_confirmed') is not True
            or cards.get('verified') is not True
            or any(stop.get(k) != state.get(k) for k in ('owner_pid', 'container_id', 'image_id'))):
        raise RuntimeError('previous experiment lacks consistent stop and card-release receipts')
    return queue, frozen


def prepare(out, previous=DEFAULT_PREVIOUS, launch_path=DEFAULT_LAUNCH, packet=DATA):
    """Freeze a new protocol revision after passive release checks; no GPU probes."""
    if socket.gethostname() != 'steve-TURIND8-2L2T':
        raise RuntimeError('this frozen lifecycle is for the two-card host only')
    with file_lock(HOST_LOCK), file_lock(MODEL_LOCK), file_lock(STAGE_LOCK):
        prior, receipts = previous_receipts(previous)
        verified_packet = validate_sparse_packet(packet)
        launch = json.loads(Path(launch_path).read_text())
        cold = derive_cold_launch(launch)
        previous_launch=json.loads((Path(previous)/'server/launch.json').read_text())
        if effective_profile(previous_launch) != effective_profile(cold) or prior.get('model') != 'qwen38-27b-fp8':
            raise RuntimeError('replication must preserve the previous exact cold profile and model')
        config = {'schema': 'sparse-replication-host-queue.v1', 'protocol': 'context-sparse-replication-live-v1',
                  'packet': str(Path(packet).resolve()),
                  'expected_trials': expected_trials(verified_packet),
                  'budget_receipt_sha256': sha(Path(packet) / 'budget-receipt.json'),
                  'cache_policy': dict(CACHE_POLICY),
                  'prepared_at': now(), 'hostname': socket.gethostname(),
                  'fault_baseline_at': prior.get('fault_baseline_at', prior['prepared_at']),
                  'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  'protected_launch': str(Path(launch_path).resolve()),
                  'previous_revision': {'directory': str(Path(previous).resolve()), 'artifacts': receipts},
                  'effective_profile': effective_profile(cold),
                  'server_args': profile_args(cold), 'port': 18196, 'model': 'qwen38-27b-fp8',
                  'expected_launch_identity': {key: launch[key] for key in
                      ('overlay_sha256', 'reference_sha256', 'guard_sha256')},
                  'guard_min_available_gib': 1.6, 'prelaunch_available_gib': 11,
                  'min_disk_free_gib': 5, 'max_wait_seconds': 180,
                  'dependency_sha256': dependencies(launch_path, launch, packet)}
        reason = release_reason(config)
        if reason:
            raise RuntimeError('host is not idle: ' + reason)
        # check_available only binds a socket and inspects Docker/fuser; no GPU work.
        load_helper().check_available(config['port'], 'sparse-replication-v1-prepare-no-container')
        out.mkdir(parents=True, exist_ok=False)
        atomic(out / 'queue.json', config)
        try:
            resource_check(config, out, load_helper())
            fault_check(config, out)
        except BaseException as error:
            status(out, 'prepare-failed', error=str(error), device_actions=False)
            raise
        status(out, 'prepared', protocol=config['protocol'], device_actions=False)
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
    conflicts = conflicting_processes()
    if conflicts:
        return f'protected supervisor, Harbor client or qualified server owner remains: {conflicts}'
    result = read_command(['systemctl', '--user', 'list-units', '--all', '--plain', '--no-legend',
                           '--no-pager', 'ctx-planE-*', 'ctx-watchdog-planE-*',
                           'ctx-durable-pilot-v1.service', 'ctx-durable-pilot-v2.service', 'ctx-durable-r2.service', 'ctx-durable-r3.service', 'ctx-durable-r4.service', 'ctx-semantic-v1.service', 'ctx-sparse-v1.service'])
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 4 and columns[2] in {'active', 'activating', 'deactivating', 'reloading'}:
            return 'a prior protected experiment unit remains active'
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
                '--keep', '--startup-timeout', '1800', *config['server_args']]
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


def generation_matches(actual, expected):
    return (isinstance(actual, dict) and actual.keys() == expected.keys()
            and all(type(actual[key]) is type(value) and actual[key] == value
                    for key, value in expected.items()))


def validate_sparse_packet(packet):
    """Run only the wrapper's pure CPU packet validator in an isolated interpreter."""
    code = ('import json,sys;sys.path.insert(0,sys.argv[1]);import runner;'
            'print(json.dumps(runner.validate_packet(sys.argv[2])))')
    result = subprocess.run([sys.executable, '-c', code, str(SPARSE), str(Path(packet).resolve())],
                            capture_output=True, text=True, timeout=120,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
                                     TRANSFORMERS_OFFLINE='1'))
    if result.returncode:
        raise RuntimeError('sparse CPU packet/budget validation failed: ' + result.stderr[-2000:])
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or set(value) != {'plan', 'budget', 'tasks'}:
        raise RuntimeError('sparse packet validator returned an invalid receipt')
    budget, plan = value['budget'], value['plan']
    if (budget.get('schema') != 'sparse-replication-budget-receipt.v1'
            or budget.get('measurement_kind') != 'cpu-oracle-wiring-budget-check'
            or budget.get('all_reference_prompts_fit') is not True
            or budget.get('all_reference_emissions_fit') is not True
            or plan.get('schema') != 'sparse-replication-plan.v1' or plan.get('protocol') != SPARSE_PROTOCOL
            or type(plan.get('expected_trials')) is not int or plan['expected_trials'] != 4
            or not generation_matches(plan.get('answer_generation'), ANSWER_GENERATION)
            or not generation_matches(plan.get('ingestion_generation'), INGESTION_GENERATION)
            or any(type(plan.get(key)) is not int or plan[key] != expected for key, expected in NATIVE_LIMITS.items())):
        raise RuntimeError('sparse packet CPU fit receipt or fixed policy is invalid')
    return value


def expected_trials(packet):
    plan, tasks = packet['plan'], packet['tasks']
    rows = plan.get('trials')
    order = [('report',83,'archive'),('report',83,'quoted'),
             ('dispatch',97,'quoted'),('dispatch',97,'archive')]
    if not isinstance(rows, list) or [(r.get('style'),r.get('seed'),r.get('arm')) for r in rows] != order:
        raise RuntimeError('sparse packet must contain the four fixed ordered trials')
    output = []
    for row in rows:
        case = 'sparse-n128-seed83' if row['style']=='report' else 'sparse-n128-seed97-dispatch'
        task = tasks[case]
        if (type(row.get('counter_count')) is not int or row['counter_count'] != 128
                or type(row.get('seed')) is not int
                or row.get('case_id') != case or row.get('task_sha256') != task.get('task_sha256')
                or task.get('document_id') != case or len(task.get('questions', [])) != 24):
            raise RuntimeError('sparse packet trial/task identity differs from the frozen design')
        output.append({**row, 'source_sha256': task['source_sha256'],
                       'adjudication_sha256': task.get('adjudication_sha256'),
                       'generated_provenance': task['generated_provenance']})
    return output


def verify_diagnostic(directory, expected, *, server_identity=None, source_code_sha256=None):
    """Model failures are evidence; missing, duplicated or mismatched evidence aborts."""
    directory = Path(directory).resolve()
    summary = json.loads((directory / 'summary.json').read_text())
    if (summary.get('schema') != 'sparse-replication-summary.v1'
            or summary.get('protocol') != SPARSE_PROTOCOL or summary.get('status') != 'completed'
            or summary.get('measurement_kind') != 'model'
            or summary.get('infrastructure_abort') is not False
            or summary.get('speed_gate_passed') is not False
            or summary.get('holdout_admitted') is not False):
        raise RuntimeError('diagnostic summary identity, infrastructure or claim status invalid')
    if any(type(summary.get(key)) is not int or summary[key] != 4
           for key in ('expected_trials', 'observed_trials')):
        raise RuntimeError('diagnostic summary must count exactly four native trials')
    if ((server_identity is not None and summary.get('server_identity') != server_identity)
            or (source_code_sha256 is not None and summary.get('engine_source_sha256') != source_code_sha256)):
        raise RuntimeError('sparse summary runtime or engine identity differs')
    rows = summary.get('trials')
    if (not isinstance(rows, list) or len(rows) != 4 or len(expected) != 4
            or len({(r['case_id'], r['arm']) for r in expected}) != 4):
        raise RuntimeError('diagnostic must retain all four unique planned trials')
    used_paths = set()
    completed = failed = 0
    cache_audit = []
    for row, planned in zip(rows, expected):
        if (not isinstance(row, dict) or row.get('case_id') != planned['case_id']
                or type(row.get('counter_count')) is not int or type(row.get('seed')) is not int
                or row.get('counter_count') != planned['counter_count'] or row.get('arm') != planned['arm']
                or row.get('task_sha256') != planned.get('task_sha256')
                or row.get('status') not in ('completed', 'failed')):
            raise RuntimeError('diagnostic trial identity, order or terminal status invalid')
        relative = row.get('result_path')
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise RuntimeError('diagnostic result path must be relative')
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or path in used_paths:
            raise RuntimeError('diagnostic result path escapes output or is duplicated')
        used_paths.add(path)
        outer = json.loads(path.read_text())
        if (outer.get('schema') != 'sparse-replication-trial.v1' or outer.get('protocol') != SPARSE_PROTOCOL
                or type(outer.get('counter_count')) is not int or type(outer.get('seed')) is not int
                or outer.get('measurement_kind') != 'model' or outer.get('status') != row['status']
                or outer.get('generated_provenance') != planned['generated_provenance']
                or outer.get('speed_gate_passed') is not False or outer.get('holdout_admitted') is not False
                or any(outer.get(key) != planned[key] or row.get(key) != planned[key] for key in
                       ('case_id', 'counter_count', 'style', 'seed', 'arm', 'task_sha256', 'result_path', 'native_result_path'))):
            raise RuntimeError('outer sparse result differs from the frozen generated study')
        relative = outer['native_result_path']
        path = (directory / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(directory) or path in used_paths:
            raise RuntimeError('native sparse result path escapes output or is duplicated')
        used_paths.add(path)
        if sha(path) != outer.get('native_sha256'):
            raise RuntimeError('outer sparse receipt does not bind the native result hash')
        result = json.loads(path.read_text())
        if outer.get('native_artifacts') != result.get('artifacts'):
            raise RuntimeError('outer sparse receipt and native artifact identities disagree')
        if (result.get('schema') != 'semantic-live-trial.v1'
                or result.get('protocol') != NATIVE_PROTOCOL or result.get('resumed') is not False
                or result.get('measurement_kind') != 'model'
                or result.get('document_id') != planned['case_id']
                or result.get('case_id') != planned['case_id']
                or result.get('arm') != planned['arm'] or result.get('status') != row['status']
                or any(not isinstance(planned.get(key), str) or result.get(key) != planned[key]
                       for key in ('task_sha256', 'source_sha256'))
                or result.get('adjudication_sha256') != planned.get('adjudication_sha256')
                or not generation_matches(result.get('answer_generation'), ANSWER_GENERATION)
                or not generation_matches(result.get('ingestion_generation'), INGESTION_GENERATION)
                or any(type(result.get(key)) is not int or result[key] != value
                       for key, value in NATIVE_LIMITS.items())
                or (server_identity is not None and result.get('server_identity') != server_identity)
                or (source_code_sha256 is not None and result.get('source_code_sha256') != source_code_sha256)
                or result.get('failure_kind') == 'infrastructure'):
            raise RuntimeError('native diagnostic result does not match its ordered manifest row')
        # Audit observations without converting a cache-contaminated diagnostic into an abort or a speed claim.
        calls_path = path.parent / 'calls.jsonl'
        cache = {'case_id': planned['case_id'], 'arm': planned['arm'], 'complete': False,
                 'cached_tokens': None, 'calls': 0}
        try:
            calls = [json.loads(line) for line in calls_path.read_text().splitlines() if line.strip()]
            cache['calls'] = len(calls)
            if type(result.get('calls')) is not int or result['calls'] != len(calls):
                raise ValueError('native call count differs from the retained log')
            counts = []
            for call in calls:
                usage = call.get('usage', {}); details = usage.get('prompt_tokens_details', {})
                cached = details.get('cached_tokens'); prompt = usage.get('prompt_tokens')
                if type(cached) is not int or type(prompt) is not int or not 0 <= cached <= prompt:
                    raise ValueError('missing or invalid cache counters')
                counts.append(cached)
            cache.update(calls=len(calls), complete=bool(calls), cached_tokens=sum(counts) if calls else None)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            cache['error'] = str(error)
        cache_audit.append(cache)
        completed += row['status'] == 'completed'
        failed += row['status'] == 'failed'
    if (type(summary.get('completed_trials')) is not int or summary['completed_trials'] != completed
            or type(summary.get('failed_trials')) is not int or summary['failed_trials'] != failed):
        raise RuntimeError('diagnostic completed/failed counts disagree with native records')
    return {**summary, 'host_cache_audit': {'trials': cache_audit,
            'all_trials_known_zero': all(c['complete'] and c['cached_tokens'] == 0 for c in cache_audit),
            'speed_gate_passed': False}}


def execute(out):
    config = json.loads((out / 'queue.json').read_text())
    if config.get('protocol') != 'context-sparse-replication-live-v1' or config.get('schema') != 'sparse-replication-host-queue.v1':
        raise RuntimeError('only a native sparse screen queue can execute')
    if not generation_matches(config.get('cache_policy'), CACHE_POLICY):
        raise RuntimeError('sparse cold-cache policy differs from the frozen experiment')
    with file_lock(HOST_LOCK), file_lock(out / 'coordinator.lock'):
        if (out / 'execution-started.json').exists():
            raise RuntimeError('one-shot coordinator was already executed; no retry/resume')
        if json.loads((out / 'status.json').read_text()).get('phase') != 'prepared':
            raise RuntimeError('queue preparation did not complete')
        atomic(out / 'execution-started.json', {'at': now(), 'pid': os.getpid()})
        server = None
        failure = None
        try:
            verify_dependencies(config)
            if expected_trials(validate_sparse_packet(config['packet'])) != config['expected_trials']:
                raise RuntimeError('sparse packet identity or CPU budget receipt changed before preflight')
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
                verify_cold_emission(identity)
                if effective_profile(identity) != config['effective_profile']:
                    raise RuntimeError('actual effective profile differs from the frozen cold profile')
                if (profile_args(identity) != config['server_args'] or any(
                        identity.get(key) != value for key, value in config['expected_launch_identity'].items())):
                    raise RuntimeError('actual server/overlay/reference identity differs from frozen qualified profile')
                base = f'http://127.0.0.1:{config["port"]}'
                strict_out = out / 'strict'
                status(out, 'strict-quality-gate')
                monitored_command(['bash', STRICT], 'strict', out, config, server=server, timeout=2400,
                                  env={'BASE_URL': base, 'MODEL_NAME': config['model'], 'OUT_DIR': str(strict_out),
                                       'PROFILE_LABEL': 'sparse-replication-v1-cold-profile', 'ATTEMPT_LABEL': 'sparse-one-server'})
                comparison = out / 'strict-comparison.json'
                monitored_command([sys.executable, COMPARE, strict_out, REFERENCE, '--output', comparison],
                                  'strict-compare', out, config, server=server, timeout=120)
                if not strict_passed(json.loads(comparison.read_text())):
                    raise RuntimeError('strict standing-reference qualification failed; diagnostic untouched')
            verify_dependencies(config)
            if expected_trials(validate_sparse_packet(config['packet'])) != config['expected_trials']:
                raise RuntimeError('frozen sparse trial order differs from the packet')
            status(out, 'sparse-replication', expected_trials=4)
            monitored_command([sys.executable, SPARSE / 'runner.py', '--packet', config['packet'], '--out', out / 'diagnostic',
                '--endpoint', base + '/v1', '--model', config['model'], '--execute', '--identity', launch],
                'diagnostic', out, config, server=server, timeout=14400)
            verify_dependencies(config)
            diagnostic = verify_diagnostic(out / 'diagnostic', config['expected_trials'],
                server_identity={'endpoint': base + '/v1', 'model': config['model'], 'launch_sha256': sha(launch)},
                source_code_sha256={p.name: sha(p) for p in SEMANTIC.glob('*.py') if not p.name.startswith('test_')})
            atomic(out / 'diagnostic-host-audit.json', diagnostic['host_cache_audit'])
            status(out, 'client-complete', summary=str(out / 'diagnostic/summary.json'),
                   completed_trials=diagnostic['completed_trials'], failed_trials=diagnostic['failed_trials'])
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
        status(out, 'completed', cards_released=True, server_restarts=0,
               diagnostic_summary=str(out / 'diagnostic/summary.json'),
               completed_trials=diagnostic['completed_trials'], failed_trials=diagnostic['failed_trials'],
               speed_gate_passed=False, holdout_admitted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true'); mode.add_argument('--execute', action='store_true')
    parser.add_argument('--previous-run', type=Path, default=DEFAULT_PREVIOUS)
    parser.add_argument('--packet', type=Path, default=DATA)
    parser.add_argument('--qualified-launch', type=Path, default=DEFAULT_LAUNCH)
    args = parser.parse_args()
    def stop(*_):
        global STOP_REQUESTED
        STOP_REQUESTED = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    if args.prepare:
        prepare(args.out.resolve(), args.previous_run, args.qualified_launch, args.packet)
    else:
        execute(args.out.resolve())


if __name__ == '__main__':
    main()
