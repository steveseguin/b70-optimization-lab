#!/usr/bin/env python3
"""Bounded public-source acceptance session for the two-card FP8 package (R310, MTP depth 5).

Everything a user would do, from an anonymous download of this repository at one pushed commit: verify the pinned
files, pull the image by digest, start one owned server through the package launcher, run the strict suite and the
six practical requests, stop it once through the package's stop command, and record health before and after.
The receipts feed collect-fp8-tp2-acceptance-evidence.py. Owns exactly one server; no restart, no retry.

With `--multi-user` the same session then covers the package's `multi-user` profile (64 users, no speculation,
overlays b70_exclusive_prefill + b70_fa_decode_per_seq, prefix cache off): after the recommended-profile server is
stopped and the cards are free again, it starts ONE second server through the same downloaded package launcher
(`serve.py start --profile multi-user`), runs the research campaign's client (scripts/bench-openai-concurrency-oracle.py)
on the short ladder suite and on the long-prompt suite, each as one sequential pass plus two passes at 16, 32 and 64
users at once, compares every answer token for token with the frozen single-user no-MTP answers the 2026-10-04
campaign used (compare-ladder-oracles.py's compare_rows), and stops that server through `serve.py stop`. Each
server is started once; nothing is retried; no server is left running. Results: <out>/multi-user/summary.json.

usage: run-fp8-tp2-acceptance-session.py --commit <sha> --out /mnt/fast-ai/bench-results/<new dir> [--multi-user]
"""
import argparse
import datetime as dt
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
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODEL = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
IMAGE = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
REFERENCE_STRICT = Path('/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-strict')
# The qualified fresh server this replay must match (image, arguments, environment). Default: the review campaign's
# depth-5 server; QUALIFIED_CONTAINER selects another qualified receipt (the comm-2 allgather server since 2026-09-17).
QUALIFIED_CONTAINER = Path(os.environ.get('QUALIFIED_CONTAINER', '/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp5/container-final.json'))
HEALTH = ROOT / 'scripts/check-qwen36-xpu-xccl-health.sh'
XPU_PYTHON = Path.home() / '.venvs/vllm-xpu/bin/python'
PINNED = ['packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows-0.1.0.dist-info/entry_points.txt',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_allgather_allreduce.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_allgather_allreduce-0.1.0.dist-info/entry_points.txt',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_chunked_upload.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_chunked_upload-0.1.0.dist-info/entry_points.txt',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_exclusive_prefill.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_exclusive_prefill-0.1.0.dist-info/entry_points.txt',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_decode_per_seq.py',
          'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_decode_per_seq-0.1.0.dist-info/entry_points.txt',
          'scripts/bench-openai-concurrency-oracle.py',
          'experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py',
          'experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json',
          'experiments/qwen38-27b-b70/data/2026-10-04-fp8-multiuser/long-prompt-suite.json',
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


def cgroup_memory(container):
    """The container's own memory counters, read from cgroup v2 while the server is still up.

    Since 2026-09-19 the launcher runs `--memory 12g --memory-swap 12g`, so the container has no swap allowance and
    cgroup reclaim can only drop clean file pages. That is safe exactly as long as *anonymous* memory stays under
    the ceiling: a cgroup with nothing left to reclaim OOM-kills inside itself. `oom_kill` must be 0, while
    `events.max` going up is expected and is the point of the change. Recorded, not gated -- the acceptance gates
    are unchanged. See experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md.
    """
    candidates = [Path('/sys/fs/cgroup/system.slice') / f'docker-{container}.scope', Path('/sys/fs/cgroup/docker') / container]
    candidates += sorted(Path('/sys/fs/cgroup').glob(f'**/docker-{container}.scope'))
    base = next((p for p in candidates if (p / 'memory.events').exists()), None)
    if base is None:
        return {'read': False, 'reason': f'no cgroup v2 directory for container {container[:12]}'}

    def pairs(name):
        try:
            return {k: int(v) for k, v in (line.split(' ', 1) for line in (base / name).read_text().splitlines() if ' ' in line)}
        except (OSError, ValueError):
            return {}

    def value(name):
        try:
            text = (base / name).read_text().strip()
        except OSError:
            return None
        return int(text) if text.isdigit() else text

    events, stat = pairs('memory.events'), pairs('memory.stat')
    anon, ceiling = stat.get('anon'), value('memory.max')
    return {'read': True, 'cgroup': str(base), 'events': events, 'oom_kill': events.get('oom_kill'),
            'max_events': events.get('max'), 'memory_max': ceiling, 'memory_peak': value('memory.peak'),
            'swap_max': value('memory.swap.max'), 'swap_peak': value('memory.swap.peak'),
            'anon': anon, 'file': stat.get('file'), 'file_dirty': stat.get('file_dirty'),
            'pswpout': stat.get('pswpout'), 'pswpin': stat.get('pswpin'), 'pgscan_direct': stat.get('pgscan_direct'),
            'anon_headroom_bytes': (ceiling - anon) if isinstance(ceiling, int) and isinstance(anon, int) else None,
            'no_swap_configured': value('memory.swap.max') == 0, 'oom_kill_free': events.get('oom_kill') == 0}


def listening(port):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True


# ---------------------------------------------------------------------------------------------------------------
# Optional multi-user stage (--multi-user). Same client, suites, request settings and frozen references as the
# 2026-10-04 research campaign (run-20261004-fp8-multiuser-campaign.py: R.LADDER, R.LADDER_SUITE and the arguments
# of its `oracle`/long-suite calls; REF_LADDER; LONG_REF), so a pass here means what "exact" meant there
# (notes/2026-10-04-fp8-multiuser-prereg.md): every answer, in BOTH passes, at 16, 32 and 64 users, equal token
# for token to the frozen single-user no-MTP answer. Totals are recorded, never gated.
MULTI_USER_PROFILE = 'multi-user'
MULTI_USER_LEVELS = (16, 32, 64)
MULTI_USER_REPEATS = 2
MULTI_USER_DIR = 'multi-user'
LADDER = 'scripts/bench-openai-concurrency-oracle.py'
COMPARE_LADDER = 'experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py'
STAGE_LOCK = Path('/tmp/qwen-short-prefill-stage.lock')  # held by every FP8 launcher while it owns a server
MULTI_USER_SUITES = {
    # 64 short chat prompts. Reference: the comm-2 campaign's two-card no-MTP server (R310, allgather overlay),
    # one request at a time -- the campaign's REF_LADDER ("frozen single-user no-MTP answers").
    'short': {'suite': 'experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json',
              'reference': Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-ladder.json'),
              'reference_sha256': '843ef0c2e053f03deb94b74390b3df5bdddde2fd0ef6e44e3a0fa3758ecc1878',
              'request_timeout': 1800, 'client_timeout': 5400},
    # 2K-8K-token prompts. Reference: the one-request-at-a-time pass of the 2026-10-04 64-user run, no speculation
    # -- the campaign's LONG_REF (no older single-user answers exist for these prompts).
    'long': {'suite': 'experiments/qwen38-27b-b70/data/2026-10-04-fp8-multiuser/long-prompt-suite.json',
             'reference': Path('/mnt/fast-ai/bench-results/fp8-multiuser-three-s64-20261004/'
                               'tp2-pure-faseq-head4-mtp0-s64-long-concurrency.json'),
             'reference_sha256': '680167246a80d7f95f07d5b79c582ea07a6523a05e5b8825c97eb82e1e5e31dc',
             'request_timeout': 3600, 'client_timeout': 7200},
}


def load_compare(source_dir):
    """compare-ladder-oracles.py as a module: its compare_rows is the campaign's token-for-token comparator."""
    spec = importlib.util.spec_from_file_location('compare_ladder_oracles', Path(source_dir) / COMPARE_LADDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def multi_user_client_argv(source_dir, key, base_url, out_path):
    """The campaign's client call: one sequential pass, then 16, 32 and 64 requests at once, twice."""
    suite = MULTI_USER_SUITES[key]
    return [sys.executable, Path(source_dir) / LADDER, '--base-url', base_url, '--model', MODEL_NAME,
            '--api-mode', 'completions', '--suite', Path(source_dir) / suite['suite'],
            '--concurrency', ','.join(str(n) for n in MULTI_USER_LEVELS), '--repeats', str(MULTI_USER_REPEATS),
            '--max-tokens', '128', '--seed', '42', '--timeout', str(suite['request_timeout']), '--return-token-ids',
            '--out', out_path]


def suite_result(ladder, reference, compare_rows):
    """Every answer of one client run (its sequential pass and each batch) against the frozen single-user answers.

    Recomputed from token ids, so the collector can run it again from the packet alone. JSON-native values only:
    the collector compares this with the frozen summary.json.
    """
    ref = {row['prompt_id']: row for row in reference['oracle']['rows']}

    def divergences(mismatches):
        return [[m['prompt_id'], m.get('first_divergence', m.get('reason'))] for m in mismatches][:8]
    exact, mismatches = compare_rows(ladder['oracle']['rows'], ref)
    sequential = {'answers': len(ladder['oracle']['rows']), 'reference_answers': len(ref), 'exact_vs_reference': exact,
                  'cache_zero': ladder['oracle'].get('cached_tokens_all_zero') is True,
                  'first_divergences': divergences(mismatches)}
    passes = []
    for batch in ladder.get('batches', []):
        exact, mismatches = compare_rows(batch['rows'], ref)
        rate = batch.get('aggregate_tok_s_wall')
        passes.append({'users': batch['concurrency'], 'repeat': batch['repeat'], 'answers': len(batch['rows']),
                       'exact_vs_reference': exact, 'exact_vs_own_solo': batch.get('oracle_exact_count'),
                       'tok_s_together': round(rate, 2) if isinstance(rate, (int, float)) else None,
                       'generated_tokens': batch.get('total_completion_tokens'), 'elapsed_s': batch.get('elapsed_s'),
                       'cache_zero': batch.get('cached_tokens_all_zero') is True,
                       'first_divergences': divergences(mismatches)})
    passes.sort(key=lambda p: (p['users'], p['repeat']))
    expected = sorted([u, r] for u in MULTI_USER_LEVELS for r in range(1, MULTI_USER_REPEATS + 1))
    passed = (sequential['answers'] == sequential['reference_answers'] == sequential['exact_vs_reference'] > 0
              and sequential['cache_zero'] and [[p['users'], p['repeat']] for p in passes] == expected
              and all(p['answers'] == p['users'] == p['exact_vs_reference'] == p['exact_vs_own_solo'] and p['cache_zero']
                      for p in passes))
    return {'passed': passed, 'sequential': sequential, 'passes': passes}


def cards_free(port):
    """(free, reason): the port, the render nodes and the launchers' stage lock, as serve.py's start will see them.

    The port probe binds without SO_REUSEADDR, exactly like serve.py's check_available, so a just-stopped server's
    socket in TIME_WAIT counts as busy here too (a start inside that window fails with Errno 98).
    """
    if listening(port):
        return False, f'port {port} is still bound'
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    busy = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, text=True)
    if busy.returncode != 1 or busy.stdout.strip():
        return False, 'a render device is open'
    with STAGE_LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lock, fcntl.LOCK_UN)
        except BlockingIOError:
            return False, 'the stage lock is held'
    return True, 'free'


def wait_cards_free(port, timeout=300, probe=cards_free, clock=time.monotonic, sleep=time.sleep):
    """Bounded wait for the previous server's teardown; one answer, no retry of anything else."""
    deadline = clock() + timeout
    while True:
        free, reason = probe(port)
        if free or clock() >= deadline:
            return free, reason
        sleep(5)


def wait_ready(session, helper, timeout, clock=time.monotonic, sleep=time.sleep):
    """The launcher's state receipt once it says ready/failed/stopped, or once the helper exits or time runs out."""
    deadline = clock() + timeout
    state = {}
    while clock() < deadline:
        if (session / 'state.json').exists():
            state = json.loads((session / 'state.json').read_text())
            if state.get('status') in ('ready', 'failed', 'stopped'):
                break
        if helper.poll() is not None:
            break
        sleep(5)
    return state


def run_multi_user(source_dir, out, say, sh, popen=subprocess.Popen, ready_timeout=1900, free_timeout=300):
    """The multi-user stage: one `multi-user` server through the downloaded package launcher, both suites, one stop.

    Returns 0 when every answer at every level in both passes of both suites equals the frozen single-user answer
    and the server stopped cleanly; 1 when it ran and did not; a short string when it could not start. Writes
    <out>/multi-user/summary.json in every case. Never leaves the server running: the stop is in a `finally`.
    """
    stage = out / MULTI_USER_DIR
    stage.mkdir()
    serve = Path(source_dir) / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
    summary = {'schema': 'neural.download.fp8-tp2-multi-user-stage.v1', 'profile': MULTI_USER_PROFILE,
               'users': list(MULTI_USER_LEVELS), 'repeats': MULTI_USER_REPEATS, 'started_at': now(), 'ran': False,
               'passed': False, 'rcs': {}, 'references': {}, 'suites': {}, 'speed_gated': False}
    rcs = summary['rcs']

    def finish(result):
        summary['finished_at'] = now()
        dump(stage / 'summary.json', summary)
        return result

    for key, suite in MULTI_USER_SUITES.items():
        body = suite['reference'].read_bytes() if suite['reference'].exists() else b''
        summary['references'][key] = {'path': str(suite['reference']), 'sha256': sha(body),
                                      'expected_sha256': suite['reference_sha256']}
    bad = sorted(k for k, r in summary['references'].items() if r['sha256'] != r['expected_sha256'])
    if bad:
        summary['reason'] = f'frozen single-user reference missing or changed: {bad}; no server started'
        say(f'multi-user: {summary["reason"]}')
        return finish('reference missing')
    free, reason = wait_cards_free(PORT, timeout=free_timeout)
    if not free:
        summary['reason'] = f'cards not free after the first server: {reason}; no server started'
        say(f'multi-user: {summary["reason"]}')
        return finish('cards not free')

    session = stage / 'session'

    def serve_status(name):
        result = subprocess.run([sys.executable, str(serve), 'status', '--state-dir', str(session)], capture_output=True,
                                text=True, cwd=source_dir)
        (stage / f'{name}.json').write_text(result.stdout if result.returncode == 0 else json.dumps({'error': result.stderr}))

    with (stage / 'helper.stdout').open('w') as helper_out:
        helper = popen([sys.executable, str(serve), 'start', '--profile', MULTI_USER_PROFILE, '--model-dir', str(MODEL),
                        '--state-dir', str(session), '--port', str(PORT)], cwd=source_dir, stdout=helper_out,
                       stderr=subprocess.STDOUT)
        state = {}
        try:
            state = wait_ready(session, helper, ready_timeout)
            summary['server'] = {k: state.get(k) for k in ('status', 'error', 'ready_at', 'container_id', 'profile')}
            say(f'multi-user helper: {state.get("status")} {state.get("error") or ""}')
            if state.get('status') == 'ready':
                summary['ran'] = True
                serve_status('status-ready')
                for key, suite in MULTI_USER_SUITES.items():
                    argv = multi_user_client_argv(source_dir, key, f'http://127.0.0.1:{PORT}', stage / f'{key}-ladder.json')
                    try:
                        rcs[f'{key}_client'] = sh(argv, stage / f'{key}-ladder.stdout', cwd=source_dir,
                                                  timeout=suite['client_timeout'])
                    except subprocess.TimeoutExpired:
                        rcs[f'{key}_client'] = 'timeout'
                        say(f'multi-user {key}: client timed out after {suite["client_timeout"]} s')
                serve_status('status-after-requests')
                dump(stage / 'cgroup-memory.json', cgroup_memory(state.get('container_id') or ''))
        finally:
            if state.get('status') == 'ready':
                try:
                    rcs['stop'] = sh([sys.executable, serve, 'stop', '--state-dir', session], stage / 'stop.stdout',
                                     cwd=source_dir, timeout=120)
                except subprocess.TimeoutExpired:
                    rcs['stop'] = 'timeout'
            elif helper.poll() is None:
                helper.send_signal(signal.SIGINT)  # the launcher's own graceful Ctrl+C path; it stops what it owns
                rcs['stop'] = 'interrupt'
            try:
                helper.wait(timeout=180)
                rcs['helper'] = helper.returncode
            except subprocess.TimeoutExpired:
                rcs['helper'] = 'still running'
    serve_status('status-stopped')
    final = json.loads((session / 'state.json').read_text()) if (session / 'state.json').exists() else {}
    summary.setdefault('server', {})['final_status'] = final.get('status')
    if summary['ran']:
        compare = load_compare(source_dir)
        for key, suite in MULTI_USER_SUITES.items():
            ladder = stage / f'{key}-ladder.json'
            if ladder.exists():
                try:
                    summary['suites'][key] = suite_result(json.loads(ladder.read_text()),
                                                          json.loads(suite['reference'].read_text()), compare.compare_rows)
                except (ValueError, KeyError, TypeError) as exc:
                    summary['suites'][key] = {'passed': False, 'reason': f'unreadable client output: {exc!r}'}
            else:
                summary['suites'][key] = {'passed': False, 'reason': 'no client output'}
            for row in summary['suites'][key].get('passes', []):
                say(f"multi-user {key}: {row['users']} users, pass {row['repeat']}: {row['exact_vs_reference']}/{row['answers']} "
                    f"equal to the single-user answers, {row['tok_s_together']} tok/s together")
    summary['passed'] = (summary['ran'] and set(summary['suites']) == set(MULTI_USER_SUITES)
                         and all(s['passed'] for s in summary['suites'].values())
                         and all(rcs.get(f'{k}_client') == 0 for k in MULTI_USER_SUITES)
                         and rcs.get('stop') == 0 and rcs.get('helper') == 0 and final.get('status') == 'stopped')
    say(f"multi-user stage: {'PASSED, every answer exact' if summary['passed'] else 'NOT passed'}; rcs {rcs}")
    return finish(0 if summary['passed'] else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--multi-user', action='store_true', help='after the single-user gates, also run the multi-user profile stage')
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
    dump(out / 'cgroup-memory.json', cgroup_memory(state.get('container_id') or ''))
    rcs['stop'] = sh([sys.executable, serve, 'stop', '--state-dir', session], out / 'stop.stdout', cwd=source_dir, timeout=120)
    try:
        helper.wait(timeout=180)
        rcs['helper'] = helper.returncode
    except subprocess.TimeoutExpired:
        rcs['helper'] = 'still running'
    helper_out.close()
    status('status-stopped')
    if a.multi_user:  # second server, the `multi-user` profile; starts only once the first one's teardown is complete
        rcs['multi_user'] = run_multi_user(source_dir, out, say, sh)

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
