#!/usr/bin/env python3
"""Bounded public-source acceptance session for the two-card FP8 package (R310, MTP depth 5).

Everything a user would do, from an anonymous download of this repository at one pushed commit: verify the pinned
files, pull the image by digest, start one owned server through the package launcher, run the strict suite and the
six practical requests, stop it once through the package's stop command, and record health before and after.
The receipts feed collect-fp8-tp2-acceptance-evidence.py. Owns exactly one server; no restart, no retry.

usage: run-fp8-tp2-acceptance-session.py --commit <sha> --out /mnt/fast-ai/bench-results/<new dir>
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODEL = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
IMAGE = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
REFERENCE_STRICT = Path('/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-strict')
QUALIFIED_CONTAINER = Path('/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp5/container-final.json')
HEALTH = ROOT / 'scripts/check-qwen36-xpu-xccl-health.sh'
XPU_PYTHON = Path.home() / '.venvs/vllm-xpu/bin/python'
PINNED = ['packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows-0.1.0.dist-info/entry_points.txt',
          'packages/qwen38-27b-fp8-tp2-b70/package.json',
          'packages/qwen38-27b-fp8-tp2-b70/compose.yaml',
          'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py',
          'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh',
          'scripts/bench-openai-realistic-suite.py', 'scripts/neural-download-canaries.py',
          'scripts/compare-strict-attempt-outputs.py', 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json']
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
PORT = 18124
MODEL_NAME = 'qwen38-27b-fp8'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def host_snapshot():
    meminfo = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
    return {'at': now(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'mem_available_kb': int(meminfo['MemAvailable'].split()[0]), 'swap_free_kb': int(meminfo['SwapFree'].split()[0]),
            'docker_ps': subprocess.run(['docker', 'ps', '--format', '{{.Names}} {{.Image}}'], capture_output=True, text=True).stdout.split('\n'),
            'uptime_s': float(Path('/proc/uptime').read_text().split()[0])}


def listening(port):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    log = (out / 'session-runner.log').open('w')

    def say(message):
        line = f'[{dt.datetime.now().strftime("%H:%M:%S")}] {message}'
        print(line, flush=True); log.write(line + '\n'); log.flush()

    def sh(argv, stdout_path, cwd=None, env=None, timeout=3600):
        with open(stdout_path, 'w') as handle:
            proc = subprocess.run([str(x) for x in argv], cwd=cwd, stdout=handle, stderr=subprocess.STDOUT,
                                  env=dict(os.environ, **(env or {})), timeout=timeout)
        say(f'{Path(stdout_path).name}: rc={proc.returncode}')
        return proc.returncode

    rcs = {}
    dump(out / 'host-before.json', host_snapshot())
    journal_since = now()

    # 1. anonymous public source at the pushed commit
    public = out / 'public-source'; public.mkdir()
    url = f'https://codeload.github.com/steveseguin/b70-optimization-lab/tar.gz/{a.commit}'
    say(f'downloading {url}')
    archive = public / 'repository.tar.gz'
    with urllib.request.urlopen(url, timeout=600) as response, archive.open('wb') as handle:
        shutil.copyfileobj(response, handle)
    archive_bytes = archive.read_bytes()
    clean = out / 'clean-source'; clean.mkdir()
    with tarfile.open(archive) as tf:
        tf.extractall(clean, filter='data')
    source_dir = next(clean.iterdir())
    files = []
    for rel in PINNED:
        body = (source_dir / rel).read_bytes()
        files.append({'path': rel, 'sha256': sha(body), 'bytes': len(body), 'matches_working_tree': body == (ROOT / rel).read_bytes()})
    docker_auth = json.loads((Path.home() / '.docker/config.json').read_text()).get('auths', {}) if (Path.home() / '.docker/config.json').exists() else {}
    dump(public / 'source-receipt.json', {
        'commit': a.commit, 'url': url, 'archive_sha256': sha(archive_bytes), 'archive_bytes': len(archive_bytes),
        'source_dir': str(source_dir), 'new_directory': True, 'git_worktree': (source_dir / '.git').exists(),
        'anonymous_download': True, 'model_files_reused_after_fresh_verification': True, 'docker_layer_cache_reused': True,
        'registry_credentials_present_for_ghcr': any('ghcr.io' in k for k in docker_auth), 'files': files})
    say(f'source {source_dir.name}: pinned files match working tree: {all(f["matches_working_tree"] for f in files)}')

    # 2. model verification and image pull, exactly as the package guide says
    rcs['verify'] = sh([source_dir / 'packages/qwen38-27b-fp8-tp2-b70/scripts/verify.sh'], public / 'model-verify.log',
                       cwd=source_dir, env={'MODEL_DIR': str(MODEL)}, timeout=1800)
    rcs['pull'] = sh(['docker', 'pull', IMAGE], public / 'image-pull.log', timeout=1800)

    # 3. health preflight
    health = out / 'health'; health.mkdir()
    rcs['preflight'] = sh(['bash', HEALTH], health / 'preflight.log', env={'PYTHON': str(XPU_PYTHON)}, timeout=1200)
    if rcs['preflight'] != 0 or rcs['verify'] != 0 or rcs['pull'] != 0:
        say('preflight failed; no server started')
        dump(health / 'result.json', {'preflight_rc': rcs['preflight'], 'verify_rc': rcs['verify'], 'pull_rc': rcs['pull'], 'aborted': True})
        return 2

    # 4. one owned server through the downloaded package launcher
    serve = source_dir / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
    session = out / 'session'
    helper_out = (out / 'helper.stdout').open('w')
    helper = subprocess.Popen([sys.executable, str(serve), 'start', '--model-dir', str(MODEL), '--state-dir', str(session),
                               '--port', str(PORT)], cwd=source_dir, stdout=helper_out, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 1900
    state = {}
    while time.monotonic() < deadline:
        if (session / 'state.json').exists():
            state = json.loads((session / 'state.json').read_text())
            if state.get('status') in ('ready', 'failed', 'stopped'):
                break
        if helper.poll() is not None:
            break
        time.sleep(5)
    say(f'helper: {state.get("status")} {state.get("error") or ""}')
    if state.get('status') != 'ready':
        helper.wait(timeout=120)
        dump(health / 'result.json', {'preflight_rc': 0, 'helper_rc': helper.returncode, 'aborted': True, 'state': state})
        return 3

    def status(name):
        result = subprocess.run([sys.executable, str(serve), 'status', '--state-dir', str(session)], capture_output=True, text=True, cwd=source_dir)
        (out / f'{name}.json').write_text(result.stdout if result.returncode == 0 else json.dumps({'error': result.stderr}))
        return result.returncode
    status('status-ready')

    # 5. strict suite, comparison with the same-image no-MTP reference, six practical requests
    strict = out / 'strict'
    rcs['strict'] = sh(['bash', source_dir / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh'], out / 'strict.stdout',
                       cwd=source_dir, env={'OUT_DIR': str(strict), 'BASE_URL': f'http://127.0.0.1:{PORT}', 'MODEL_NAME': MODEL_NAME,
                                            'PROFILE_LABEL': 'two-card-depth5-acceptance', 'ATTEMPT_LABEL': f'acceptance-{a.commit[:9]}'})
    rcs['comparator'] = sh([sys.executable, source_dir / 'scripts/compare-strict-attempt-outputs.py', strict, REFERENCE_STRICT,
                            '--output', out / 'strict-comparison.json'], out / 'strict-comparison.stdout', cwd=source_dir, timeout=300)
    rcs['practical'] = sh([sys.executable, source_dir / 'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py',
                           '--base-url', f'http://127.0.0.1:{PORT}', '--model', MODEL_NAME, '--out-dir', out / 'practical'],
                          out / 'practical.stdout', cwd=source_dir, timeout=1800)
    status('status-after-requests')

    # 6. one graceful stop through the package command
    rcs['stop'] = sh([sys.executable, serve, 'stop', '--state-dir', session], out / 'stop.stdout', cwd=source_dir, timeout=120)
    try:
        helper.wait(timeout=180)
        rcs['helper'] = helper.returncode
    except subprocess.TimeoutExpired:
        rcs['helper'] = 'still running'
    helper_out.close()
    status('status-stopped')

    # 7. postflight
    rcs['postflight'] = sh(['bash', HEALTH], health / 'postflight.log', env={'PYTHON': str(XPU_PYTHON)}, timeout=1200)
    kernel = subprocess.run(['journalctl', '-k', '--since', journal_since, '--no-pager', '-o', 'short-iso'], capture_output=True, text=True).stdout
    faults = [line for line in kernel.splitlines() if FAULT.search(line)]
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    fuser = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, text=True)
    dump(health / 'result.json', {'preflight_rc': rcs['preflight'], 'postflight_rc': rcs['postflight'], 'helper_rc': rcs['helper'],
                                  'stop_command_rc': rcs['stop'], 'strict_client_rc': rcs['strict'], 'comparator_rc': rcs['comparator'],
                                  'practical_client_rc': rcs['practical'], 'model_verify_rc': rcs['verify'], 'image_pull_rc': rcs['pull'],
                                  'gpu_faults': faults, 'journal_since': journal_since,
                                  'owned_listener_absent': not listening(PORT),
                                  'render_devices_unowned': fuser.returncode == 1 and not fuser.stdout.strip()})

    # 8. runtime comparison with the qualified depth-5 research container
    actual = json.loads((session / 'container-inspect.json').read_text())
    qualified = json.loads(QUALIFIED_CONTAINER.read_text())
    qualified = qualified[0] if isinstance(qualified, list) else qualified

    def command(container):
        args = list(container['Config']['Cmd']); args[args.index('--served-model-name') + 1] = '<alias>'; return args
    env_a = dict(e.split('=', 1) for e in actual['Config']['Env']); env_q = dict(e.split('=', 1) for e in qualified['Config']['Env'])
    dump(out / 'runtime-comparison.json', {
        'matched_image': actual['Image'] == qualified['Image'],
        'matched_vllm_arguments_except_model_alias': command(actual) == command(qualified),
        'environment_differences': {k: [env_a.get(k), env_q.get(k)] for k in set(env_a) | set(env_q) if env_a.get(k) != env_q.get(k)},
        'reference_inspect': str(QUALIFIED_CONTAINER),
        'host_memory_bytes': [actual['HostConfig']['Memory'], qualified['HostConfig']['Memory']],
        'host_memory_plus_swap_bytes': [actual['HostConfig']['MemorySwap'], qualified['HostConfig']['MemorySwap']]})
    dump(out / 'host-after.json', host_snapshot())
    dump(out / 'session-rcs.json', rcs)
    say(f'done: {rcs}')
    return 0 if all(v == 0 for v in rcs.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
