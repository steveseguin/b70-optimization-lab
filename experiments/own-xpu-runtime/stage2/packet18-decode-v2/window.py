#!/usr/bin/env python3
"""Prepared, explicitly admitted packet18 windows; never queues another run."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import time
from window_safety import environment_gate, memory_snapshot, memory_admission

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('packet2_window', HERE.parent / 'packet2/tests/device_window.py')
p2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2)
sha = p2.sha
AUTHORITY = 'iq3-p17-detmath-v2'
CONFIG = {
    'W0': dict(card=2, cards=2, memory='resident', stage='canary', gemv='frozen', count=0, steps=0, context=8),
    'W1': dict(card=3, cards=1, memory='layer-streaming', stage='first-token', gemv='frozen', count=8, steps=8, context=256),
    'W2': dict(card=2, cards=2, memory='resident', stage='decode', gemv='frozen', count=64, steps=8, context=256),
    'W3': dict(card=2, cards=2, memory='resident', stage='decode', gemv='r5', count=64, steps=8, context=256),
}


def read(path):
    return json.loads(path.read_text())


def require(test, reason):
    if not test:
        raise ValueError(reason)


def safe_teardown(run, cards):
    rows = run.get('teardown', [])
    coverage = len(rows) == cards or (len(rows) == 1 and run.get('owner_cards') == cards)
    return coverage and all(r.get('safe_to_exit') is True and
        r.get('live_bytes') == 0 and r.get('in_flight') == 0 for r in rows)


def cpu_gate(path, build_receipt):
    require(sha(path) == build_receipt.get('cpu_tests_sha256'), 'CPU receipt changed since build')
    cpu = read(path)
    require(cpu.get('passed') is True and cpu.get('device_executed') is False and
            cpu.get('binary_sha256') == build_receipt.get('artifacts_sha256', {}).get('host/own-rt-iq3'),
            'CPU gate failed or host binary identity mismatch')
    require(all(cpu.get('real_model', {}).get(mode, {}).get('passed') is True and
                cpu['real_model'][mode].get('layer_matches') == 384 and
                cpu['real_model'][mode].get('layer_total') == 384 and
                cpu['real_model'][mode].get('token_matches', 0) >= count and
                len(cpu['real_model'][mode].get('tokens', [])) >= count
                for mode, count in (('frozen', 64), ('r5', 8))), 'CPU oracle coverage incomplete')


def fixtures(root, steps):
    hashes = {}
    for step in range(1, steps + 1):
        for layer in range(48):
            rel = f'step{step}/layer-{layer:02}.bf16'
            path = root / rel
            require(path.is_file() and path.stat().st_size == 20480, 'fixture missing/wrong size: ' + str(path))
            hashes[rel] = sha(path)
    return hashes


def oracle_gate(path, input_tokens, steps, count):
    require(path is not None, 'every window requires --oracle v2 CPU prompt root')
    meta = read(path / 'arithmetic.json')
    require(meta.get('arithmetic') == AUTHORITY, 'oracle arithmetic identity mismatch')
    require(meta == read(HERE.parent / 'packet17-detmath/arithmetic.json'), 'oracle differs from v2 arithmetic authority')
    for name, digest in meta.get('arithmetic_sources', {}).items():
        require(sha(ROOT / name) == digest, 'oracle arithmetic source changed: ' + name)
    require(read(path / 'input.json').get('tokens') == input_tokens, 'oracle prompt mismatch')
    tokens = read(path / 'result.json').get('tokens', [])
    require(len(tokens) >= count, 'oracle token coverage missing')
    return fixtures(path, steps), tokens[:count]


def w1_gate(path, binary_hash, input_hash, boot):
    require(path is not None, 'W2/W3 require --w1 passing receipt')
    r = read(path)
    require(r.get('schema') == 'own-runtime.iq3.packet18.window.v1' and r.get('window') == 'W1' and
            r.get('passed') is True and r.get('oracle_exact') is True and r.get('boot_id') == boot and
            r.get('binary_sha256') == binary_hash and r.get('input_sha256') == input_hash and
            r.get('arithmetic') == AUTHORITY and r.get('nongemv') == 'parallel' and r.get('gemv') == 'frozen',
            'W1 failed or boot/binary/input identity changed')
    require(sha(path.parent / 'run/receipt.json') == r.get('native_receipt_sha256') and
            safe_teardown(read(path.parent / 'run/receipt.json'), 1), 'W1 native teardown changed')
    require(fixtures(path.parent / 'run', 8) == r.get('layer_hashes') and len(r.get('tokens', [])) == 8, 'W1 fixtures changed')
    return r


def repeat_gate(path, identity):
    if path is None:
        return None
    prior = read(path)
    keys = ('window', 'boot_id', 'binary_sha256', 'input_sha256', 'input_manifest_sha256', 'gemv', 'nongemv', 'context', 'arithmetic', 'oracle_hashes', 'expected_tokens', 'card', 'cards', 'memory', 'stage')
    require(prior.get('passed') is True and all(prior.get(k) == identity.get(k) for k in keys), 'invalid fresh-process repeat anchor')
    require(fixtures(path.parent / 'run', CONFIG[identity['window']]['steps']) == prior.get('layer_hashes'), 'repeat fixtures changed')
    return prior


def supervise(child, seconds, cursor, kernel, latch_fault, persist, requested,
              journal=p2.journal, now=time.monotonic, sleep=time.sleep, drain_seconds=60):
    """Every poll/drain has a deadline; only one SIGTERM, never hard-kill."""
    start = now()
    sent = None
    while True:
        try:
            fresh, cursor = journal(cursor)
            kernel.write(fresh)
            kernel.flush()
            if p2.FAULT.search(fresh):
                requested.append('new GPU fault signature')
        except Exception as error:
            requested.append('kernel journal unavailable: ' + str(error))
        if now() - start >= seconds:
            requested.append('window deadline')
        if requested and sent is None:
            latch_fault(requested[0])
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
            sent = now()
            persist()
        if child.poll() is not None:
            break
        if sent is not None and now() - sent >= drain_seconds:
            requested.append('cooperative drain deadline; child retained for coordinator')
            latch_fault(requested[-1])
            return dict(returncode=None, child_still_running=True, elapsed_seconds=now()-start, sigterm_sent=True)
        sleep(.25)
    # Five seconds of postflight, including journal subprocess time (2s bound).
    deadline = now() + 5
    while now() < deadline:
        sleep(min(.25, deadline - now()))
        try:
            fresh, cursor = journal(cursor)
            kernel.write(fresh)
            if p2.FAULT.search(fresh):
                requested.append('postflight GPU fault signature')
        except Exception as error:
            requested.append('postflight journal unavailable: ' + str(error))
    if requested:
        latch_fault(requested[0])
    return dict(returncode=child.returncode, child_still_running=False, elapsed_seconds=now()-start, sigterm_sent=sent is not None)


def value_statistics(actual, expected):
    """Interpret little-endian BF16 bytes without loading any device library."""
    if not actual.is_file() or not expected.is_file():
        return {'missing_actual': not actual.is_file(), 'missing_oracle': not expected.is_file()}
    a, b = actual.read_bytes(), expected.read_bytes()
    if len(a) % 2 or len(b) % 2:
        return dict(actual_bytes=len(a), oracle_bytes=len(b), malformed_bf16=True)
    av = [x[0] for x in struct.iter_unpack('<H', a)]
    bv = [x[0] for x in struct.iter_unpack('<H', b)]
    f = lambda x: struct.unpack('<f', struct.pack('<I', x << 16))[0]
    differences = [(i, x, y) for i, (x, y) in enumerate(zip(av, bv)) if x != y]
    finite = [abs(f(x)-f(y)) for _, x, y in differences if math.isfinite(f(x)) and math.isfinite(f(y))]
    first = differences[0] if differences else None
    return dict(actual_values=len(av), oracle_values=len(bv), unequal_values=len(differences)+abs(len(av)-len(bv)),
                finite_max_abs_difference=max(finite, default=0), finite_mean_abs_difference=sum(finite)/len(finite) if finite else 0,
                nonfinite_pairs=sum(not math.isfinite(f(x)) or not math.isfinite(f(y)) for _, x, y in differences),
                first_value_index=first[0] if first else None,
                first_actual_bf16=f'0x{first[1]:04x}' if first else None,
                first_oracle_bf16=f'0x{first[2]:04x}' if first else None)


def compare_layers(actual_root, oracle_root, expected_hashes):
    rows = []
    first = None
    actual = {}
    for name, digest in expected_hashes.items():
        path = actual_root / name
        observed = sha(path) if path.is_file() else None
        actual[name] = observed
        row = dict(fixture=name, step=int(name.split('/')[0][4:]), layer=int(name.split('-')[1][:2]),
                   exact=observed == digest, sha256=observed, oracle_sha256=digest)
        rows.append(row)
        if not row['exact'] and first is None:
            first = dict(row, site='layer_output', site_localization='earliest retained layer boundary; inner site not retained',
                         value_statistics=value_statistics(path, oracle_root / name) if oracle_root else {'oracle_path_unavailable': True})
    return dict(layers=rows, layer_matches=sum(row['exact'] for row in rows), layer_total=len(rows),
                first_differing_layer=first, layer_hashes=actual)


def ldd_preflight(binary, runner=subprocess.run):
    # Loader inspection only: never invoke the device program or discovery.
    result = runner(['ldd', str(binary)], capture_output=True, text=True, timeout=10)
    require(result.returncode == 0 and 'not found' not in result.stdout + result.stderr,
            'ldd dependency preflight failed: ' + result.stdout + result.stderr)
    return dict(argv=['ldd', str(binary)], returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def token_diagnostics(observed, expected):
    first = next((i + 1 for i in range(max(len(observed), len(expected)))
                  if i >= len(observed) or i >= len(expected) or observed[i] != expected[i]), None)
    return dict(tokens=observed, token_matches=sum(a == b for a, b in zip(observed, expected)),
                token_total=len(expected), first_differing_token=first)


def native_command(binary, cfg, input_root, model_dir, oracle, out, seconds):
    return [str(binary), '--authorized-device-window', '--card', str(cfg['card']), '--cards', str(cfg['cards']),
            '--memory', cfg['memory'], '--stage', cfg['stage'], '--nongemv', 'parallel', '--gemv', cfg['gemv'],
            '--prompt-tokens', str((input_root / 'tokens.txt').resolve()), '--max-new', str(cfg['count']),
            '--context', str(cfg['context']), '--plan', str((input_root / 'plan.tsv').resolve()),
            '--identity', str((input_root / 'identity.tsv').resolve()), '--model-dir', model_dir,
            '--oracle', str(oracle.resolve()), '--output', str(out / 'run'), '--seconds', str(seconds)]


def compare_run(out, cfg, expected_hashes, expected_tokens, oracle_root=None, diagnostics=None):
    run = read(out / 'run/receipt.json')
    require(run.get('schema') == 'own-runtime.iq3.packet18.run.v1' and
            run.get('device_executed') is True and run.get('arithmetic') == AUTHORITY and
            run.get('owner_cards') == cfg['cards'] and run.get('context') == cfg['context'] and
            run.get('nongemv') == 'parallel' and run.get('gemv') == cfg['gemv'] and
            run.get('memory_mode') == cfg['memory'], 'native run identity does not match admitted window')
    comparison = compare_layers(out / 'run', oracle_root, expected_hashes)
    comparison.update(token_diagnostics(run.get('tokens', []), expected_tokens))
    if diagnostics is not None:
        diagnostics.update(comparison)
    actual = comparison['layer_hashes']
    mismatch = comparison['first_differing_layer']
    require(mismatch is None, 'first differing layer fixture: ' + (mismatch['fixture'] if mismatch else 'none'))
    observed = run.get('tokens', [])
    if observed != expected_tokens:
        first = next((i for i in range(min(len(observed), len(expected_tokens))) if observed[i] != expected_tokens[i]), min(len(observed), len(expected_tokens)))
        raise ValueError(f'first differing/missing generated token: {first+1}')
    require(run.get('passed') is True and safe_teardown(run, cfg['cards']), 'native failure or unsafe teardown')
    rows = [json.loads(s) for s in (out / 'run/timings.jsonl').read_text().splitlines() if s.strip()]
    require(len(rows) == cfg['count'], 'timing row coverage differs from generated token count')
    fields = ('wall_ms', 'gemv_device_ms', 'non_gemv_device_ms', 'transfer_wall_ms', 'kernel_submissions', 'host_waits')
    require(all(all(isinstance(r.get(k), (int, float)) and math.isfinite(r[k]) and r[k] >= 0 for k in fields) for r in rows), 'invalid or missing token timing fields')
    require(all(r.get('kind') == 'generated_token' and r.get('generated_index') == i+1 and
                r.get('token_id') == expected_tokens[i] for i, r in enumerate(rows)), 'timing tokens omitted/reordered or misidentified')
    if cfg['count'] > 1:
        require(run.get('decode_tokens') == cfg['count']-1, 'decode throughput numerator is not tokens 2..N')
        duration, rate = run.get('decode_wall_ms'), run.get('decode_tok_s')
        require(isinstance(duration, (int, float)) and isinstance(rate, (int, float)) and
                math.isfinite(duration) and math.isfinite(rate) and duration > 0 and rate > 0,
                'missing finite whole-span decode timing')
        require(math.isclose(rate, (cfg['count']-1)*1000/duration, rel_tol=2e-5), 'decode rate differs from whole-span receipt')
    return run, actual



def canary_receipt_gate(run):
    require(run.get('schema') == 'own-runtime.iq3.packet18.canary.v1' and
            run.get('passed') is True and run.get('device_executed') is True and
            run.get('round_trips') == 100 and run.get('kernels_per_card') == 1000 and
            run.get('token_sequence') is True and safe_teardown(run, 2),
            'W0 canary coverage/teardown incomplete')
    require(0 < run.get('owned_device_bytes', 0) < 16*1024**2 and
            0 < run.get('wall_ms', 0) < 30000 and
            0 < run.get('max_submission_ns', 0) < 100000000,
            'W0 canary memory/time bounds failed')

def w0_gate(path, binary_hash, boot, card, environment):
    require(path is not None, 'W2/W3 require --w0 passing two-card canary receipt')
    row = read(path)
    require(row.get('schema') == 'own-runtime.iq3.packet18.window.v1' and
            row.get('window') == 'W0' and row.get('passed') is True and
            row.get('boot_id') == boot and row.get('binary_sha256') == binary_hash and
            row.get('card') == card and row.get('cards') == 2 and
            row.get('environment') == environment, 'W0 boot/binary/cards/environment changed')
    native = path.parent / 'run/receipt.json'
    require(sha(native) == row.get('native_receipt_sha256'), 'W0 native receipt changed')
    canary_receipt_gate(read(native))
    return row

def run_w0(a, cfg, binary, boot, out, latch, bindings, dependency_preflight, environment):
    require(a.seconds <= 30, 'W0 deadline must be <=30 seconds')
    require(a.repeat_of is None, 'W0 is a single canary; no automatic repeat')
    cmd = [str(binary), '--authorized-device-window', '--canary', '--cards', '2',
           '--card', str(cfg['card']), '--memory', 'resident', '--seconds', str(a.seconds),
           '--output', str(out / 'run')]
    record = dict(schema='own-runtime.iq3.packet18.window.v1', window='W0', boot_id=boot,
                  card=cfg['card'], cards=2, binary_sha256=sha(binary),
                  command=cmd, environment=environment, ldd_preflight=dependency_preflight,
                  passed=False, device_executed=False,
                  bindings={str(k): v for k, v in bindings.items()})
    pre, cursor = p2.journal()
    out.mkdir(parents=True)
    (out / 'preflight-kernel.txt').write_text(pre)
    requested = []
    def persist():
        if requested: record['stop_reason'] = requested[0]
        (out / 'window.json').write_text(json.dumps(record, indent=2)+'\n')
    def latch_fault(reason):
        latch.write_text(json.dumps(dict(boot_id=boot, window=str(out), reason=reason, pid=record.get('pid')))+'\n')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: requested.append('watcher signal '+str(s)))
    persist()
    with (out / 'stdout.txt').open('w') as log, (out / 'kernel-window.txt').open('w') as kernel:
        require(not requested, 'watcher stopped before child launch')
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=environment['native'])
        record.update(pid=child.pid, device_executed=True)
        persist()
        record.update(supervise(child, a.seconds, cursor, kernel, latch_fault, persist, requested))
    try:
        require(record['returncode'] == 0 and not requested, 'W0 child failed/stopped')
        for path, digest in bindings.items():
            require(sha(path) == digest, 'W0 binding changed: '+str(path))
        native = out / 'run/receipt.json'
        canary_receipt_gate(read(native))
        record.update(passed=True, native_receipt_sha256=sha(native), canary=read(native))
    except (OSError, ValueError, KeyError) as error:
        requested.append(str(error)); latch_fault(requested[0])
    persist()
    return 0 if record['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-device-window', action='store_true', required=True)
    parser.add_argument('--window', choices=CONFIG, required=True)
    for key in ('input', 'output', 'oracle', 'w0', 'w1', 'repeat-of'):
        parser.add_argument('--' + key, type=Path, required=key == 'output')
    parser.add_argument('--card', type=int, help='first physical card; W2/W3 use this and the next card')
    parser.add_argument('--seconds', type=int, default=10800)
    a = parser.parse_args()
    environment = environment_gate()
    require(1 <= a.seconds <= 10800, 'deadline must be 1..10800 seconds')
    require(os.environ.get('OMP_NUM_THREADS') == '2' and os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 OMP_NUM_THREADS=2 required')
    require('idle' in subprocess.check_output(['ionice', '-p', str(os.getpid())], text=True, timeout=2), 'ionice -c3 required')
    for variable in ('ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER','ZE_AFFINITY_MASK'):
        require(not os.environ.get(variable), 'physical card mapping must be unmasked: '+variable)
    cfg = dict(CONFIG[a.window])
    if a.card is not None:
        cfg['card'] = a.card
    require(0 <= cfg['card'] and cfg['card'] + cfg['cards'] <= 4, 'card indexes outside 0..3')
    build = (HERE / 'build').resolve()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch = build / 'FAULT.json'
    require(not latch.exists() or read(latch).get('boot_id') != boot, 'boot fault latch: coordinator recovery required')
    out = a.output.resolve()
    require(build in out.parents and not out.exists(), 'new output directory beneath packet18 build required')
    b = read(HERE / 'build-receipt.json')
    binary = build / 'device/own-rt-iq3'
    require(b.get('passed') is True and sha(binary) == b['artifacts_sha256']['device/own-rt-iq3'], 'build/binary mismatch')
    dependency_preflight = ldd_preflight(binary)
    cpu_gate(HERE / 'cpu-tests.json', b)
    bindings = {ROOT / name: digest for name, digest in b['sources'].items()}
    bindings[HERE / 'cpu-tests.json'] = b['cpu_tests_sha256']
    bindings[binary] = sha(binary)
    bindings[HERE / 'build-receipt.json'] = sha(HERE / 'build-receipt.json')
    for path, digest in bindings.items():
        require(sha(path) == digest, 'source changed: '+str(path))
    if a.window == 'W0':
        return run_w0(a, cfg, binary, boot, out, latch, bindings, dependency_preflight, environment)
    require(a.input is not None and a.oracle is not None, 'model windows require --input and --oracle')
    memory_before = memory_snapshot()
    memory_budget = None
    if a.window in ('W2', 'W3'):
        require(sha(HERE / 'census.json') == b.get('census_sha256'), 'memory census changed since seal')
        memory_budget = memory_admission(read(HERE / 'census.json'), cfg['gemv'], memory_before)
        w0_gate(a.w0, sha(binary), boot, cfg['card'], environment)
        bindings[HERE / 'census.json'] = sha(HERE / 'census.json')
    manifest = a.input / 'input.json'
    require(sha(manifest) == b['input_sha256'], 'input manifest changed')
    inp = read(manifest)
    bindings[manifest] = sha(manifest)
    for name, digest in inp['files'].items():
        bindings[a.input / name] = digest
    for path, digest in bindings.items():
        require(sha(path) == digest, 'source/binary/input changed: ' + str(path))
    input_hash = sha(a.input / 'tokens.txt')
    expected_hashes, expected_tokens = oracle_gate(a.oracle, inp['tokens'], cfg['steps'], cfg['count'])
    if a.window != 'W1':
        anchor = w1_gate(a.w1, sha(binary), input_hash, boot)
        require(anchor.get('oracle_hashes') == expected_hashes and anchor.get('layer_hashes') == expected_hashes and
                anchor.get('tokens') == expected_tokens[:8] and anchor.get('expected_tokens') == expected_tokens[:8],
                'W1 is not exact against the current v2 oracle')
        require(anchor.get('environment') == environment, 'W1 environment differs from admitted window')
        require(anchor.get('card') in range(cfg['card'], cfg['card'] + cfg['cards']), 'W1 card is not in admitted two-card topology')
    for name in ('arithmetic.json', 'input.json', 'result.json'):
        bindings[a.oracle / name] = sha(a.oracle / name)
    for name, digest in expected_hashes.items():
        bindings[a.oracle / name] = digest
    for path in (a.w0, a.w1, a.repeat_of):
        if path:
            bindings[path] = sha(path)
    cmd = native_command(binary, cfg, a.input, inp['model_dir'], a.oracle, out, a.seconds)
    record = dict(schema='own-runtime.iq3.packet18.window.v1', window=a.window, boot_id=boot, **cfg,
                  nongemv='parallel', arithmetic=AUTHORITY, binary_sha256=sha(binary), input_sha256=input_hash,
                  input_manifest_sha256=sha(manifest), oracle_hashes=expected_hashes, expected_tokens=expected_tokens,
                  environment=environment, memory_before_load=memory_before, memory_admission=memory_budget, ldd_preflight=dependency_preflight, oracle_path=str(a.oracle.resolve()), command=cmd, passed=False, oracle_exact=False, device_executed=False, external_idle_health_still_required=True,
                  bindings={str(k): v for k, v in bindings.items()}, real_model_qualified=False)
    prior = repeat_gate(a.repeat_of, record)
    pre, cursor = p2.journal()
    out.mkdir(parents=True)
    (out / 'preflight-kernel.txt').write_text(pre)
    requested = []
    def persist():
        if requested:
            record['stop_reason'] = requested[0]
        (out / 'window.json').write_text(json.dumps(record, indent=2) + '\n')
    def latch_fault(reason):
        latch.write_text(json.dumps(dict(boot_id=boot, window=str(out), reason=reason, pid=record.get('pid'))) + '\n')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: requested.append('watcher signal ' + str(s)))
    persist()
    with (out / 'stdout.txt').open('w') as log, (out / 'kernel-window.txt').open('w') as kernel:
        require(not requested, 'watcher stopped before child launch')
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=environment['native'])
        record.update(pid=child.pid, device_executed=True)
        persist()
        record.update(supervise(child, a.seconds, cursor, kernel, latch_fault, persist, requested))
    record['memory_end'] = memory_snapshot()
    memory_log = out / 'run/host-memory.jsonl'
    record['native_memory_samples'] = [json.loads(line) for line in memory_log.read_text().splitlines()] if memory_log.exists() else []
    try:
        if a.window in ('W2','W3'):
            require({r['phase'] for r in record['native_memory_samples']} >= {'before_load','after_load','end'}, 'load memory samples incomplete')
        record.update(compare_layers(out / 'run', a.oracle, expected_hashes))
        native_path = out / 'run/receipt.json'
        observed = read(native_path).get('tokens', []) if native_path.exists() else []
        record.update(token_diagnostics(observed, expected_tokens))
        require(record['returncode'] == 0 and not requested, 'native child failed/stopped')
        for path, digest in bindings.items():
            require(sha(path) == digest, 'bound input/source changed during window: ' + str(path))
        run, actual = compare_run(out, cfg, expected_hashes, expected_tokens, a.oracle, record)
        record.update(oracle_exact=True, layer_hashes=actual, tokens=run['tokens'], passed=True,
                      native_receipt_sha256=sha(out / 'run/receipt.json'))
        record['fresh_repeat_passed'] = bool(prior and prior.get('layer_hashes') == actual and prior.get('tokens') == run['tokens'])
        require(prior is None or record['fresh_repeat_passed'], 'fresh-process output mismatch')
    except (OSError, ValueError, KeyError) as error:
        record['passed'] = False
        requested.append(str(error))
        latch_fault(requested[0])
    persist()
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
