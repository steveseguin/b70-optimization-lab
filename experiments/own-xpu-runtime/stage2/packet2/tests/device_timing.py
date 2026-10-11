#!/usr/bin/env python3
"""CPU --dry-run/--prepare; explicit coordinator-only native timing window."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from device_window import journal, FAULT
from timing_plan import HERE, ROOT, OWNER, MODEL, make_plan, save, sha, summarize, validate_census

BUILD = HERE / 'build'
INPUTS = BUILD / 'timing-input'
COMPILE = BUILD / 'timing-compile'
BINARY = COMPILE / 'device-timing'
MANIFEST = INPUTS / 'prepared.json'
LATCH = BUILD / 'timing-fault-latch.json'


def priority():
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        raise ValueError('Require nice 19 and OMP_NUM_THREADS=2')
    if 'idle' not in subprocess.check_output(['ionice', '-p', str(os.getpid())], text=True):
        raise ValueError('Require ionice -c 3 for bounded model reads')


def sources():
    return sorted(set([HERE / 'CMakeLists.txt', HERE / 'roofline.json',
        ROOT / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json',
        ROOT / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json']
        + list((HERE / 'kernels').glob('*.cpp')) + list((HERE / 'kernels').glob('*.hpp'))
        + list((OWNER / 'src').glob('*'))
        + [HERE / 'tests' / n for n in ('timing.cpp', 'timing_owner.cpp', 'timing_plan.py', 'device_timing.py',
                                       'device_window.py', 'test_timing.py', 'timing.schema.json')]))


def prepare():
    priority()
    if BUILD.is_symlink() or INPUTS.exists() or COMPILE.exists():
        raise ValueError('timing-input and timing-compile must be new; preserve old receipts before cleanup')
    INPUTS.mkdir(parents=True)
    plan = make_plan()
    save(INPUTS / 'plan.json', plan)
    manifest = dict(schema='own-runtime.iq3.packet2.timing-prepared.v1', passed=False,
        device_executed=False, plan_sha256=sha(INPUTS / 'plan.json'), seeds=[], commands=[],
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sources()})
    lines = []
    try:
        for layer in plan['layers']:
            for j in layer['jobs']:
                path = MODEL / j['shard']
                # Bounded exact pread, no read-ahead, bulk mapping or payload scan.
                with path.open('rb', buffering=0) as f:
                    before = os.fstat(f.fileno())
                    data = os.pread(f.fileno(), j['seed_bytes'], j['absolute_offset'])
                    after = os.fstat(f.fileno())
                identity = lambda s: [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]
                if len(data) != j['seed_bytes'] or identity(before) != identity(after):
                    raise ValueError('short or changing tensor sample: ' + j['name'])
                seed = j['name'] + '.packed'
                (INPUTS / seed).write_bytes(data)
                manifest['seeds'].append(dict(name=j['name'], file=seed, sha256=sha(INPUTS / seed),
                    fill=j['fill'], sampled_bytes=len(data), tensor_offset=j['absolute_offset'],
                    source=str(path), source_stat=identity(before),
                    identity_scope='sample hash only; full payload admission is the retained packet1 receipt'))
                lines.append(' '.join(map(str, [layer['layer'], j['name'], j['type_id'], j['rows'],
                    j['columns'], j['experts'], j['weight_bytes'], len(data), seed])))
        (INPUTS / 'plan.tsv').write_text('\n'.join(lines) + '\n')
        for args in (["cmake", "-S", HERE, "-B", COMPILE, "-DCMAKE_BUILD_TYPE=Release", "-DIQ3_DEVICE=ON"],
                     ["cmake", "--build", COMPILE, "--target", "device-timing", "-j2"]):
            p = subprocess.run(list(map(str, args)), capture_output=True, text=True)
            manifest['commands'].append(dict(argv=list(map(str, args)), returncode=p.returncode,
                                            stdout=p.stdout, stderr=p.stderr))
            print(p.stdout, end='', flush=True)
            print(p.stderr, end='', flush=True)
            if p.returncode:
                raise ValueError('CPU compile failed')
        manifest.update(passed=True, binary_sha256=sha(BINARY), plan_tsv_sha256=sha(INPUTS / 'plan.tsv'),
                        compile_commands=json.loads((COMPILE / 'compile_commands.json').read_text()))
    finally:
        save(MANIFEST, manifest)
    return manifest


def check_prepared():
    m = json.loads(MANIFEST.read_text())
    if m['passed'] is not True or m['device_executed'] is not False:
        raise ValueError('preparation failed')
    for name, digest in m['source_sha256'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('source changed: ' + name)
    if set(m['source_sha256']) != {str(p.relative_to(ROOT)) for p in sources()}:
        raise ValueError('source coverage changed')
    plan = json.loads((INPUTS / 'plan.json').read_text())
    if plan != make_plan() or sha(INPUTS / 'plan.json') != m['plan_sha256'] or sha(INPUTS / 'plan.tsv') != m['plan_tsv_sha256']:
        raise ValueError('prepared plan identity mismatch')
    jobs = [j for l in plan['layers'] for j in l['jobs']]
    if [s['name'] for s in m['seeds']] != [j['name'] for j in jobs]:
        raise ValueError('seed coverage mismatch')
    for s, j in zip(m['seeds'], jobs):
        if s['file'] != j['name'] + '.packed' or sha(INPUTS / s['file']) != s['sha256'] or (INPUTS / s['file']).stat().st_size != j['seed_bytes']:
            raise ValueError('packed fixture changed')
    if sha(BINARY) != m['binary_sha256']:
        raise ValueError('native binary changed')
    return m, plan


def watch(command, out, seconds=120):
    """One child; one cooperative stop; retain ownership if native drain stalls."""
    pre, cursor = journal()
    out.mkdir(parents=True)
    (out / 'preflight-kernel.txt').write_text(pre)
    record = dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        initial_cursor=cursor, final_cursor=cursor, stop_reason=None, returncode=None,
        requested_deadline_seconds=seconds, external_idle_health_still_required=True)
    requested = []
    old = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    for sig in old:
        signal.signal(sig, lambda s, f: requested.append('watcher signal ' + str(s)))
    try:
        with (out / 'stdout.txt').open('w') as log, (out / 'kernel-window.txt').open('w') as kernel:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            record['pid'] = child.pid
            started = time.monotonic()
            sent = False
            save(out / 'window.json', record)
            while True:
                try:
                    fresh, cursor = journal(cursor)
                    kernel.write(fresh); kernel.flush()
                    if FAULT.search(fresh):
                        requested.append('new GPU fault signature')
                except Exception as e:
                    requested.append('journal failure: ' + str(e))
                if time.monotonic() - started >= seconds:
                    requested.append('window deadline')
                if requested and not sent:
                    record['stop_reason'] = requested[0]
                    save(LATCH, dict(reason=requested[0], output=str(out), pid=child.pid))
                    save(out / 'window.json', record)
                    if child.poll() is None:
                        child.send_signal(signal.SIGTERM)
                    sent = True
                if child.poll() is not None:
                    break
                time.sleep(.25)
            record['returncode'] = child.returncode
            # Same bounded postflight journal tail as the exactness window.
            for _ in range(20):
                time.sleep(.25)
                try:
                    fresh, cursor = journal(cursor)
                    kernel.write(fresh)
                    if FAULT.search(fresh):
                        requested.append('post-exit GPU fault')
                except Exception as e:
                    requested.append('postflight journal: ' + str(e))
            record['elapsed_seconds'] = time.monotonic() - started
            record['final_cursor'] = cursor
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
    if requested:
        record['stop_reason'] = requested[0]
    if record['stop_reason'] or record['returncode'] != 0:
        save(LATCH, record)
    save(out / 'window.json', record)
    return record


def execute(card, out):
    priority()
    if not 0 <= card < 4:
        raise ValueError('card 0..3 required')
    out = out.resolve()
    if BUILD.is_symlink() or BUILD not in out.parents or out.exists():
        raise ValueError('new directory inside packet build/ required')
    if LATCH.exists():
        raise ValueError('timing fault latch exists; coordinator must resolve it before another window')
    manifest, plan = check_prepared()
    command = [str(BINARY), '--authorized-device-window', str(card), str(INPUTS / 'plan.tsv'),
               str(out / 'native.json'), str(out / 'census.json')]
    window = watch(command, out)
    receipt = dict(schema='own-runtime.iq3.packet2.timing.v1', passed=False,
        device_executed=True, card=card, binary_sha256=manifest['binary_sha256'],
        prepared_manifest=manifest, plan=plan, window=window,
        environment={k: v for k, v in os.environ.items() if k.startswith(('SYCL_', 'ZE_', 'ONEAPI_', 'UR_')) or k == 'OMP_NUM_THREADS'},
        kernel_journal_sha256=sha(out / 'kernel-window.txt'), error='')
    try:
        raw = json.loads((out / 'native.json').read_text())
        receipt['native'] = raw
        receipt['census'] = json.loads((out / 'census.json').read_text())
        validate_census(receipt['census'], plan)
        receipt['summary'] = summarize(raw, plan)
        receipt['passed'] = window['returncode'] == 0 and window['stop_reason'] is None
    except Exception as e:
        receipt['error'] = str(e)
    if not receipt['passed']:
        save(LATCH, dict(output=str(out), reason=receipt['error'] or window['stop_reason'] or 'native failure'))
    save(out / 'timing.json', receipt)
    return receipt['passed']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--authorized-device-window', action='store_true')
    p.add_argument('--card', type=int)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.dry_run:
        print(json.dumps(make_plan(), indent=2))
    elif a.prepare:
        prepare()
    else:
        if a.card is None or a.output is None:
            p.error('device window needs --card and --output')
        raise SystemExit(0 if execute(a.card, a.output) else 1)


if __name__ == '__main__':
    main()
