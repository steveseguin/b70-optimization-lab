#!/usr/bin/env python3
"""Campaign 64 full pi task client. Server lifecycle remains with the campaign runner.

Preflight freezes input hashes and verifies the existing image without building.
The client owns one proxy, runs a four-line guarded copy of the existing task
runner, then stops its proxy. Whole-history checking is deferred until --finalize,
which refuses while the model server is active. Completion and quality are separate.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[3]
BASE = Path('/mnt/fast-ai/bench-results/context-longrun-20261016')
CONTROL = BASE / 'campaign64-current-pi'
TASK = Path('/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/tasks/repair-n40-s2x')
RUNS = BASE / 'runs/c64/pi'
JOB = 'AB-pi__repair-n40-s2x'
CONTAINER = 'agentbench-' + JOB
TRIAL = RUNS / 'jobs' / JOB / 'trial'
STATE = BASE / 'proxy-state/c64-pi'
IMAGE_TAG = 'agentbench-pi:repair-n40-s2x'
IMAGE_ID = 'sha256:015ded922b7f05212e76d8cc0053e5d8411c8ac1bf39e1389ab43b2f6fd808be'
PROXY_UNIT = 'ctx-keeper-proxy'
SERVER_UNIT = 'ctx-fp8-tp2-server'
PROXY_URL = 'http://127.0.0.1:18200'
MODEL = 'qwen38-27b-fp8'
MIN_AVAILABLE_MIB = 1638 + 768 + 300
RUNNER = LAB / 'tools/agentbench/run-agent-job.sh'
HISTORY = LAB / 'tools/agentbench/check_history.py'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def read(path):
    return json.loads(path.read_text())


def command(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def inactive(unit):
    state = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '--value'],
                           text=True, capture_output=True)
    if state.returncode != 0 or not state.stdout.strip():
        raise RuntimeError(f'could not inspect {unit}')
    return state.stdout.strip() in ('inactive', 'failed')


def image_check():
    actual = command(['docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE_TAG])
    if actual != IMAGE_ID:
        raise RuntimeError(f'pi image identity mismatch: {actual}')
    return actual


def socket_dir():
    return Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'agentbench' / JOB


def fresh():
    for path in (RUNS, STATE, socket_dir()):
        if path.exists() or path.is_symlink():
            raise RuntimeError(f'refusing existing task/proxy/socket path: {path}')
    names = command(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    if CONTAINER in names:
        raise RuntimeError('refusing existing pi task container')
    if not inactive(PROXY_UNIT):
        raise RuntimeError('proxy unit is already active')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 18200))


def input_pins():
    scripts = [Path(__file__).resolve(), RUNNER, HISTORY,
        LAB / 'tools/agentbench/bridge.py', LAB / 'tools/agentbench/memwatch.py',
        LAB / 'tools/ctxkeeper/ctxkeeper.py', LAB / 'tools/ctxkeeper/notesdelta.py']
    task_files = sorted(path for path in TASK.rglob('*') if path.is_file())
    if not task_files or not (TASK / 'instruction.md').is_file() or not (TASK / 'tests/grade.py').is_file():
        raise RuntimeError('task inputs missing')
    if any(path.is_symlink() for path in TASK.rglob('*')):
        raise RuntimeError('task symlinks require an explicit identity review')
    return {'scripts': {str(path): sha(path) for path in scripts},
            'task': {str(path.relative_to(TASK)): sha(path) for path in task_files}}


def derive_runner(source):
    substitutions = [
        ('HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)', 'HERE=' + shlex.quote(str(RUNNER.parent))),
        ('IMG="agentbench-$AGENT:$TNAME"', 'IMG=' + IMAGE_ID),
        ('docker image inspect "$IMG" >/dev/null 2>&1 || "$HERE/build-agent-image.sh" "$AGENT" "$TASK" || die "image build failed"',
         'docker image inspect "$IMG" >/dev/null 2>&1 || die "pinned image missing; building is forbidden"'),
        ('python3 -I "$HERE/check_history.py" "$TRIAL/agent/requests.jsonl" > "$TRIAL/agent/history-check.json" 2>/dev/null || true',
         '# C64: original check_history.py runs only after the model server is down (--finalize).')]
    derived = source
    for old, new in substitutions:
        if derived.count(old) != 1:
            raise RuntimeError('task runner no longer has the one registered substitution site')
        derived = derived.replace(old, new)
    return derived, ''.join(difflib.unified_diff(source.splitlines(True), derived.splitlines(True),
                                               fromfile=str(RUNNER), tofile='c64-agent-driver.sh'))


def preflight(path):
    if path.exists():
        raise RuntimeError('refusing to overwrite a preflight receipt')
    image = image_check()
    fresh()
    derived, delta = derive_runner(RUNNER.read_text())
    receipt = {'preflight_ok': True, 'image_id': image, 'image_tag': IMAGE_TAG,
        'pins': input_pins(), 'task_path': str(TASK), 'driver_diff': delta,
        'driver_sha256': hashlib.sha256(derived.encode()).hexdigest(),
        'proxy_arguments': ['--recipe', 'qwen', '--notes-thinking', 'on'],
        'history_status': 'deferred-until-server-down', 'min_available_mib_at_client_start': MIN_AVAILABLE_MIB}
    dump(path, receipt)
    return receipt


def verify_pins(path):
    receipt = read(path)
    if receipt.get('preflight_ok') is not True or receipt.get('image_id') != IMAGE_ID:
        raise RuntimeError('missing successful exact-image preflight')
    if input_pins() != receipt['pins']:
        raise RuntimeError('pinned task or client source changed after preflight')
    return receipt


def require_memory(path=Path('/proc/meminfo')):
    values = {line.split(':', 1)[0]: int(line.split()[1]) for line in path.read_text().splitlines() if ':' in line}
    available = values['MemAvailable'] // 1024
    if available < MIN_AVAILABLE_MIB:
        raise RuntimeError(f'MemAvailable {available} MiB is below required {MIN_AVAILABLE_MIB} MiB')
    return available


def proxy_command(upstream):
    if upstream != 'http://127.0.0.1:18196/v1':
        raise ValueError('campaign 64 requires its registered local upstream')
    return ['systemd-run', '--user', '--unit=' + PROXY_UNIT, '--collect',
        '-p', 'WorkingDirectory=' + str(LAB), sys.executable, str(LAB / 'tools/ctxkeeper/ctxkeeper.py'),
        '--upstream', upstream[:-3], '--host', '127.0.0.1', '--port', '18200',
        '--recipe', 'qwen', '--notes-thinking', 'on', '--upstream-retries', '0',
        '--log-calls', '--state-dir', str(STATE)]


def get_status():
    with urllib.request.urlopen(PROXY_URL + '/ctxkeeper/status', timeout=3) as stream:
        return json.load(stream)


def wait_proxy():
    for _ in range(30):
        if inactive(PROXY_UNIT):
            raise RuntimeError('owned proxy exited before ready')
        try:
            return get_status()
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError('proxy readiness deadline expired')


def stop_proxy(invocation):
    current = command(['systemctl', '--user', 'show', PROXY_UNIT, '-p', 'InvocationID', '--value'])
    if current and current != invocation:
        raise RuntimeError('proxy ownership changed; refusing to stop another invocation')
    if current == invocation:
        command(['systemctl', '--user', 'stop', PROXY_UNIT])
    if not inactive(PROXY_UNIT):
        raise RuntimeError('owned proxy did not stop')


def collect_receipts(trial, proxy_status):
    ab = read(trial / 'agent/agentbench.json')
    exited = read(trial / 'agent/exit.json')
    details = read(trial / 'verifier/details.json')
    errors = []
    if ab.get('image_id') != IMAGE_ID or ab.get('agent') != 'pi' or ab.get('job') != JOB:
        errors.append('agent receipt identity mismatch')
    if ab.get('exec_rc') != 0 or exited.get('exit_code') != 0 or exited.get('timed_out') is not False:
        errors.append('agent execution failed or timed out')
    if ab.get('agent_exit') != exited:
        errors.append('agent exit receipts disagree')
    if details.get('void') is not False or details.get('kind') != 'repair' or details.get('n') != 40:
        errors.append('missing, void or unexpected grader result')
    for field in ('fixed', 'clean', 'tickets_fetched', 'rules', 'audit'):
        if field not in details or (ab.get('verifier') or {}).get(field) != details.get(field):
            errors.append(f'grader receipts disagree or omit {field}')
    if not proxy_status or any(state.get('restarts', 0) for state in proxy_status.values()):
        errors.append('missing proxy session or proxy history restart')
    requests = trial / 'agent/requests.jsonl'
    if not requests.is_file() or not requests.stat().st_size:
        errors.append('missing full request tap')
    else:
        with requests.open() as stream:
            chats = 0
            for line in stream:
                row = json.loads(line)
                if row.get('method') == 'POST' and row.get('path', '').split('?')[0].rstrip('/').endswith('/chat/completions'):
                    chats += 1
                    if not isinstance(row.get('body'), str) or not row['body']:
                        errors.append('request tap lacks a full chat body')
                        break
            if chats < 2:
                errors.append('fewer than two recorded model requests')
    quality = (details.get('fixed') == 40 and details.get('clean') == 40
        and details.get('tickets_fetched') == 44 and (details.get('audit') or {}).get('asked') == 7
        and (details.get('audit') or {}).get('right') == 7
        and bool(details.get('rules'))
        and all(rule.get('kept') == rule.get('applies') for rule in details.get('rules', {}).values()))
    return {'client_complete': not errors, 'complete': False, 'quality_pass': False,
        'task_quality_pass': quality and not errors, 'execution_errors': errors,
        'history_status': 'deferred-until-server-down', 'agentbench': ab, 'agent_exit': exited,
        'grader': {key: details.get(key) for key in ('n', 'fixed', 'clean', 'rules', 'audit', 'void', 'tickets_fetched', 'score')},
        'proxy_status': proxy_status,
        'receipts': {str(path): {'sha256': sha(path), 'bytes': path.stat().st_size} for path in
            (trial / 'agent/agentbench.json', trial / 'agent/exit.json', trial / 'verifier/details.json', requests)
            if path.is_file()}}


def run_client(args):
    if args.json.exists():
        raise RuntimeError('refusing an existing client result')
    receipt = verify_pins(args.pins)
    image_check()
    fresh()
    available = require_memory()
    derived, delta = derive_runner(RUNNER.read_text())
    if hashlib.sha256(derived.encode()).hexdigest() != receipt['driver_sha256']:
        raise RuntimeError('derived task runner differs from preflight')
    CONTROL.mkdir(parents=True, exist_ok=True)
    driver = CONTROL / 'agent-driver.sh'
    if driver.exists():
        raise RuntimeError('refusing an existing derived task driver')
    driver.write_text(derived)
    (CONTROL / 'agent-driver.diff').write_text(delta)
    command(['bash', '-n', str(driver)])
    result = {'schema': 'ctxkeeper.current-pi-probe.v1', 'complete': False, 'client_complete': False,
        'quality_pass': False, 'history_status': 'deferred-until-server-down', 'preflight_sha256': sha(args.pins),
        'available_mib_before_proxy': available, 'proxy_stopped': False, 'promotion': False}
    dump(args.json, result)
    invocation = None
    started = time.monotonic()
    try:
        command(proxy_command(args.base_url))
        invocation = command(['systemctl', '--user', 'show', PROXY_UNIT, '-p', 'InvocationID', '--value'])
        if not invocation:
            raise RuntimeError('proxy start gave no invocation identity')
        result['proxy_invocation'] = invocation
        wait_proxy()
        result['available_mib_before_container'] = require_memory()
        env = dict(os.environ, MODEL_NAME=MODEL, AGENT_MEM='768m', AGENT_MEM_SWAP='768m', TAP='full', KEEP_CONTAINER='0')
        with (CONTROL / 'agent-job.log').open('x') as log:
            subprocess.run(['bash', str(driver), 'pi', str(TASK), str(RUNS), JOB, PROXY_URL + '/v1', '3600'],
                cwd=LAB, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        result.update(collect_receipts(TRIAL, get_status()))
        if not result['client_complete']:
            raise RuntimeError('client/grader receipt checks failed')
    except BaseException as exc:
        result.update(error=f'{type(exc).__name__}: {exc}', client_complete=False)
        raise
    finally:
        try:
            if invocation is not None:
                stop_proxy(invocation)
                result['proxy_stopped'] = True
        finally:
            result['client_wall_s'] = round(time.monotonic() - started, 3)
            dump(args.json, result)


def finalize(args):
    verify_pins(args.pins)
    if not inactive(SERVER_UNIT) or not inactive(PROXY_UNIT):
        raise RuntimeError('whole-history check must wait until model and proxy are down')
    result = read(args.json)
    if not result.get('client_complete') or result.get('proxy_stopped') is not True:
        raise RuntimeError('client did not complete with confirmed proxy cleanup')
    if result.get('complete'):
        raise RuntimeError('refusing to finalize an already finalized result')
    history_path = TRIAL / 'agent/history-check.json'
    if history_path.exists():
        raise RuntimeError('history output exists before its deferred check')
    with history_path.open('x') as log:
        subprocess.run([sys.executable, '-I', str(HISTORY), str(TRIAL / 'agent/requests.jsonl')],
                       stdout=log, stderr=subprocess.PIPE, text=True, check=True)
    history = read(history_path)
    valid = (history.get('whole_history_ok') is True and history.get('responses_api') == 0
             and history.get('n_not_1') == 0 and history.get('chunked_bodies') == 0)
    result.update(history=history, history_status='checked-after-server-down',
        complete=valid, quality_pass=bool(valid and result['task_quality_pass']),
        history_receipt={'path': str(history_path), 'sha256': sha(history_path), 'bytes': history_path.stat().st_size})
    dump(args.json, result)
    if not valid:
        raise RuntimeError('whole-history or client protocol gate failed')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--finalize', action='store_true')
    ap.add_argument('--base-url')
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--json', type=Path, required=True)
    ap.add_argument('--pins', type=Path, default=CONTROL / 'preflight.json')
    args = ap.parse_args()
    if args.rounds != 1:
        ap.error('exactly one full pi task is registered')
    if args.preflight:
        preflight(args.json)
    elif args.finalize:
        finalize(args)
    else:
        if not args.base_url:
            ap.error('--base-url required for the task client')
        run_client(args)


if __name__ == '__main__':
    main()
