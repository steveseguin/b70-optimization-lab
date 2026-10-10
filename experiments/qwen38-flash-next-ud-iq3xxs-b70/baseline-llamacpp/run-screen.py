#!/usr/bin/env python3
"""Preregistered future native screen. Default prints commands; never launches."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = Path('/home/steve/build/flash-next-iq3-baseline-20261010')
FAULT_PATHS = [Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json'),
              REPO / 'experiments/qwen38-flash-next-fp8-b70/reopen-20261008/FAULT.json',
              REPO / 'experiments/own-xpu-runtime/stage1/packet4-prep/FAULT.json',
              HERE.parent / 'FAULT.json']
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|GPU HANG|GuC.*reset|coredump|timed.?out job|job.*timed.out|wedged', re.I)
STOP = False


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def stop(signum, frame):
    global STOP
    STOP = True  # never forward SIGINT: upstream completion uses _exit(130)


def journal(since):
    return subprocess.check_output(['journalctl', '-k', '-b', '--since', since,
                                    '--no-pager', '-o', 'short-iso-precise'], text=True, timeout=10)


def check_health(path):
    h = json.loads(path.read_text())
    assert h['schema'] == 'ltx.four-card-health.v1'
    assert h['passed'] is True and h['device_count'] == 4
    assert h['kernel'] == Path('/proc/sys/kernel/osrelease').read_text().strip()
    assert len(h['cards']) == 4 and all(c['pass'] is True for c in h['cards'])
    assert h['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert h['journal_fault_lines_during_probe'] == []
    ended = dt.datetime.strptime(h['end_utc'], '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=dt.timezone.utc)
    assert 0 <= time.time() - ended.timestamp() <= 900, 'health receipt older than 15 minutes'


def timings(text):
    result = {}
    for name, pattern in [('prefill', r'prompt eval time'), ('decode', r'(?<!prompt )\beval time')]:
        matches = re.findall(pattern + r'\s*=\s*([\d.]+) ms /\s*(\d+) (tokens|runs)\s*\(\s*([\d.]+) ms per token,\s*([\d.]+) tokens per second\)', text)
        assert len(matches) == 1, 'missing/ambiguous runtime timing: ' + name
        ms, count, unit, per_token, rate = matches[0]
        assert int(count) > 0 and float(ms) > 0
        result[name] = {'milliseconds': float(ms), 'count': int(count), 'count_unit': unit,
                        'reported_tokens_per_second': float(rate)}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs', type=Path, default=ROOT / 'window-inputs')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--health-receipt', type=Path)
    ap.add_argument('--execute-after-admission', action='store_true')
    a = ap.parse_args()
    commands = json.loads((a.inputs / 'commands.json').read_text())
    if not a.execute_after_admission:
        print(json.dumps(commands, indent=2))
        return
    # This switch is used only by the coordinator AFTER all run-identity.md gates.
    assert socket.gethostname() == 'steve-b70s'
    assert a.out and a.health_receipt
    assert not any(p.exists() for p in FAULT_PATHS), 'FAULT.json present; never clear it here'
    assert not a.out.exists(), 'fresh output directory required'
    check_health(a.health_receipt)
    receipt = json.loads((HERE / 'build-receipt.json').read_text())
    for item in receipt['artifacts']:
        assert sha(item['path']) == item['sha256'], 'built artifact changed'
    prompt_receipt = json.loads((HERE / 'prompt-receipt.json').read_text())
    manifest = json.loads((a.inputs / 'prompts.json').read_text())
    assert len(commands) == 24
    # Reconstruct the complete registered argv to reject injected/changed commands.
    import importlib.util
    spec = importlib.util.spec_from_file_location('prepare', HERE / 'prepare-prompts.py')
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    import tempfile
    import shutil
    scratch = Path(tempfile.mkdtemp(prefix='plan-check-', dir=ROOT))
    try:
        expected = scratch / 'inputs'
        expected_manifest = prep.prepare(expected)
        expected_commands = json.loads((expected / 'commands.json').read_text())
        for c, e in zip(commands, expected_commands):
            e['argv'][-1] = str((a.inputs / (e['id'] + '.txt')).resolve())
            assert c == e, 'command differs from preregistration'
        for m in (manifest, expected_manifest):
            for row in m['prompts']:
                row.pop('file')
            assert m == prompt_receipt, 'prompt/template identity changed'
    finally:
        shutil.rmtree(scratch)
    for row in prompt_receipt['prompts']:
        assert sha(a.inputs / (row['id'] + '.txt')) == row['rendered_sha256']
    a.out.mkdir(parents=True)
    write(a.out / 'health-receipt.json', json.loads(a.health_receipt.read_text()))
    # Authenticate complete local payloads; no network and no model-tree writes.
    model_root = Path(prep.MODEL).parent.parent
    files = json.loads((REPO / 'experiments/own-xpu-runtime/data/unsloth-flash-next-stage2-files.json').read_text())['files']
    verified = []
    for row in files:
        if row['path'].startswith('UD-IQ3_XXS/'):
            p = model_root / row['path']
            assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'model incomplete or wrong'
            verified.append(row)
    assert len(verified) == 3
    write(a.out / 'model-verification.json', verified)
    # Requiring another receipt if hashing took too long is intentional.
    check_health(a.health_receipt)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(a.out.resolve()), 'LANG': 'C.UTF-8',
           'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2',
           'LD_LIBRARY_PATH': '/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/tbb/2023.0/lib',
           'ONEAPI_DEVICE_SELECTOR': 'level_zero:0,1', 'GGML_SYCL_DYNAMIC_PRECISION': 'F32',
           'GGML_SYCL_DYNAMIC_REQUIRED_PRECISION': 'F32',
           'SYCL_CACHE_DIR': str(a.out.resolve() / 'sycl-cache'), 'XDG_CACHE_HOME': str(a.out.resolve() / 'cache')}
    write(a.out / 'environment.json', env)
    since = json.loads(a.health_receipt.read_text())['end_utc']
    start = time.monotonic()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    rows = []

    def watch():
        nonlocal rows
        text = journal(since)
        (a.out / 'kernel.log').write_text(text)
        lines = [l for l in text.splitlines() if FAULT.search(l) and 'coredump has been deleted' not in l]
        if lines:
            write(a.out / 'FAULT.json', {'since': since, 'lines': lines})
            if not FAULT_PATHS[-1].exists():
                with FAULT_PATHS[-1].open('x') as f:
                    json.dump({'since': since, 'lines': lines, 'evidence': str(a.out.resolve())}, f)
        return bool(lines or any(p.exists() for p in FAULT_PATHS) or (a.out / 'STOP').exists())

    for c in commands:
        if STOP or watch() or time.monotonic() - start >= 3.5 * 3600:
            raise RuntimeError('screen stopped before next launch; no retry')
        stem = f"repeat{c['repeat']}-{c['id']}"
        write(a.out / (stem + '-command.json'), c)
        began = time.monotonic()
        bad = False
        with (a.out / (stem + '.stdout')).open('wb') as out, (a.out / (stem + '.stderr')).open('wb') as err:
            p = subprocess.Popen(c['argv'], env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, start_new_session=True)
            (a.out / (stem + '.pid')).write_text(str(p.pid) + '\n')
            while p.poll() is None:
                try:
                    bad = watch() or bad
                except Exception as e:
                    bad = True
                    (a.out / 'watch-error.txt').write_text(repr(e))
                if time.monotonic() - began > 600 or STOP:
                    bad = True
                # Drain this bounded request; never signal/kill a busy GPU process.
                if bad:
                    (a.out / 'DRAINING').write_text('No further launches. Natural exit only; coordinator must handle a hang.\n')
                time.sleep(1)
        bad = watch() or bad
        row = {**c, 'returncode': p.returncode, 'wall_s': time.monotonic() - began,
               'stdout_sha256': sha(a.out / (stem + '.stdout')), 'failed': bad}
        if p.returncode == 0 and not bad:
            try:
                row['timings'] = timings((a.out / (stem + '.stderr')).read_text())
                assert (a.out / (stem + '.stdout')).read_bytes().strip(), 'empty output'
            except Exception as e:
                row['failed'] = bad = True
                row['timing_error'] = repr(e)
        rows.append(row)
        write(a.out / 'runs.json', rows)
        if p.returncode != 0 or bad:
            raise RuntimeError('failed process/postflight; no retry')
        # Quiet postflight and at least 305 seconds between native owners.
        for _ in range(305):
            if STOP or watch():
                raise RuntimeError('postflight/stop blocked next process')
            time.sleep(1)
    equality = {}
    for row in prompt_receipt['prompts']:
        x = (a.out / ('repeat1-' + row['id'] + '.stdout')).read_bytes()
        y = (a.out / ('repeat2-' + row['id'] + '.stdout')).read_bytes()
        equality[row['id']] = bool(x) and x == y
    write(a.out / 'comparison.json', {'byte_equal': equality, 'all_equal': all(equality.values()),
          'realistic_final_gate': {'passed': False, 'reason': '64-token screening cap; no CPU numerical oracle yet'}})
    if not all(equality.values()):
        raise RuntimeError('repeat mismatch; not an oracle')


if __name__ == '__main__':
    main()
