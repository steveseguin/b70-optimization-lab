#!/usr/bin/env python3
"""Prepared, explicitly admitted packet16 windows; never queues another run."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('packet2_window', HERE.parent / 'packet2/tests/device_window.py')
p2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2)
sha = p2.sha
AUTHORITY = 'iq3-p13-r234-sg32-split4-bf16-v1'
CONFIG = {
    'W1': dict(card=3, cards=1, memory='layer-streaming', stage='first-token', gemv='frozen', count=1, steps=1, context=128),
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
                cpu['real_model'][mode].get('layer_matches', 0) >= 48 and
                cpu['real_model'][mode].get('layer_matches') == cpu['real_model'][mode].get('layer_total') and
                cpu['real_model'][mode].get('token_matches', 0) >= 8 and
                len(cpu['real_model'][mode].get('tokens', [])) >= 8
                for mode in ('frozen', 'r5')), 'CPU oracle coverage incomplete')


def fixtures(root, steps):
    hashes = {}
    for step in range(1, steps + 1):
        for layer in range(48):
            rel = f'step{step}/layer-{layer:02}.bf16'
            path = root / rel
            require(path.is_file() and path.stat().st_size == 20480, 'fixture missing/wrong size: ' + str(path))
            hashes[rel] = sha(path)
    return hashes


def baseline_gate(path, input_hash):
    require(path is not None, 'W1 requires --baseline packet13 window.json')
    r = read(path)
    require(r.get('schema') == 'own-runtime.iq3.packet13.window.v1' and r.get('passed') is True and
            r.get('card') == 3 and r.get('cards') == 1 and r.get('stage') == 'first-token' and
            r.get('arithmetic') == AUTHORITY and r.get('input_sha256') == input_hash,
            'passing completed packet13 card-3 baseline with identical prompt required')
    native = read(path.parent / 'run/receipt.json')
    require(native.get('passed') is True and safe_teardown(native, 1), 'baseline native teardown failed')
    hashes = fixtures(path.parent / 'run', 1)
    require(all(r.get('layer_hashes', {}).get(k) == v for k, v in hashes.items()), 'baseline fixtures changed')
    require(r.get('tokens') and native.get('tokens') == r['tokens'], 'baseline token receipt mismatch')
    return hashes, r['tokens'][:1]


def oracle_gate(path, input_tokens, steps, count):
    require(path is not None, 'decode requires --oracle frozen CPU prompt root')
    meta = read(path / 'arithmetic.json')
    require(meta.get('arithmetic') == AUTHORITY, 'oracle arithmetic identity mismatch')
    # The frozen defining header is the identity authority. Packet16's source
    # set necessarily differs; do not require its source list to equal packet13.
    require(meta.get('defining_header_sha256') == sha(ROOT / meta['defining_header']), 'oracle defining arithmetic header changed')
    require(read(path / 'input.json').get('tokens') == input_tokens, 'oracle prompt mismatch')
    tokens = read(path / 'result.json').get('tokens', [])
    require(len(tokens) >= count, 'oracle token coverage missing')
    return fixtures(path, steps), tokens[:count]


def w1_gate(path, binary_hash, input_hash, boot):
    require(path is not None, 'W2/W3 require --w1 passing receipt')
    r = read(path)
    require(r.get('schema') == 'own-runtime.iq3.packet16.window.v1' and r.get('window') == 'W1' and
            r.get('passed') is True and r.get('oracle_exact') is True and r.get('boot_id') == boot and
            r.get('binary_sha256') == binary_hash and r.get('input_sha256') == input_hash and
            r.get('arithmetic') == AUTHORITY and r.get('nongemv') == 'parallel' and r.get('gemv') == 'frozen',
            'W1 failed or boot/binary/input identity changed')
    require(sha(path.parent / 'run/receipt.json') == r.get('native_receipt_sha256') and
            safe_teardown(read(path.parent / 'run/receipt.json'), 1), 'W1 native teardown changed')
    require(fixtures(path.parent / 'run', 1) == r.get('layer_hashes'), 'W1 fixtures changed')
    return r


def repeat_gate(path, identity):
    if path is None:
        return None
    prior = read(path)
    keys = ('window', 'boot_id', 'binary_sha256', 'input_sha256', 'input_manifest_sha256', 'gemv', 'nongemv', 'context', 'arithmetic', 'oracle_hashes', 'expected_tokens')
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


def compare_run(out, cfg, expected_hashes, expected_tokens):
    run = read(out / 'run/receipt.json')
    require(run.get('schema') == 'own-runtime.iq3.packet16.run.v1' and
            run.get('device_executed') is True and run.get('arithmetic') == AUTHORITY and
            run.get('owner_cards') == cfg['cards'] and run.get('context') == cfg['context'] and
            run.get('nongemv') == 'parallel' and run.get('gemv') == cfg['gemv'] and
            run.get('memory_mode') == cfg['memory'], 'native run identity does not match admitted window')
    actual = fixtures(out / 'run', cfg['steps'])
    mismatch = next((name for name, digest in expected_hashes.items() if actual.get(name) != digest), None)
    require(mismatch is None, 'first differing layer fixture: ' + str(mismatch))
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-device-window', action='store_true', required=True)
    parser.add_argument('--window', choices=CONFIG, required=True)
    for key in ('input', 'output', 'baseline', 'oracle', 'w1', 'repeat-of'):
        parser.add_argument('--' + key, type=Path, required=key in ('input', 'output'))
    parser.add_argument('--seconds', type=int, default=10800)
    a = parser.parse_args()
    require(1 <= a.seconds <= 10800, 'deadline must be 1..10800 seconds')
    require(os.environ.get('OMP_NUM_THREADS') == '2' and os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 OMP_NUM_THREADS=2 required')
    require('idle' in subprocess.check_output(['ionice', '-p', str(os.getpid())], text=True, timeout=2), 'ionice -c3 required')
    for variable in ('ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER','ZE_AFFINITY_MASK'):
        require(not os.environ.get(variable), 'physical card mapping must be unmasked: '+variable)
    cfg = CONFIG[a.window]
    build = (HERE / 'build').resolve()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch = build / 'FAULT.json'
    require(not latch.exists() or read(latch).get('boot_id') != boot, 'boot fault latch: coordinator recovery required')
    out = a.output.resolve()
    require(build in out.parents and not out.exists(), 'new output directory beneath packet16 build required')
    b = read(HERE / 'build-receipt.json')
    binary = build / 'device/own-rt-iq3'
    require(b.get('passed') is True and sha(binary) == b['artifacts_sha256']['device/own-rt-iq3'], 'build/binary mismatch')
    cpu_gate(HERE / 'cpu-tests.json', b)
    bindings = {ROOT / name: digest for name, digest in b['sources'].items()}
    bindings[HERE / 'cpu-tests.json'] = b['cpu_tests_sha256']
    bindings[binary] = sha(binary)
    bindings[HERE / 'build-receipt.json'] = sha(HERE / 'build-receipt.json')
    manifest = a.input / 'input.json'
    require(sha(manifest) == b['input_sha256'], 'input manifest changed')
    inp = read(manifest)
    bindings[manifest] = sha(manifest)
    for name, digest in inp['files'].items():
        bindings[a.input / name] = digest
    for path, digest in bindings.items():
        require(sha(path) == digest, 'source/binary/input changed: ' + str(path))
    input_hash = sha(a.input / 'tokens.txt')
    if a.window == 'W1':
        expected_hashes, expected_tokens = baseline_gate(a.baseline, input_hash)
    else:
        w1_gate(a.w1, sha(binary), input_hash, boot)
        expected_hashes, expected_tokens = oracle_gate(a.oracle, inp['tokens'], cfg['steps'], cfg['count'])
    if a.oracle:
        oracle_hashes, oracle_tokens = oracle_gate(a.oracle, inp['tokens'], cfg['steps'], cfg['count'])
        require(oracle_hashes == expected_hashes and oracle_tokens == expected_tokens, 'baseline differs from CPU oracle')
        for name in ('arithmetic.json', 'input.json', 'result.json'):
            bindings[a.oracle / name] = sha(a.oracle / name)
        for name, digest in oracle_hashes.items():
            bindings[a.oracle / name] = digest
    for path in (a.baseline, a.w1, a.repeat_of):
        if path:
            bindings[path] = sha(path)
    cmd = [str(binary), '--authorized-device-window', '--card', str(cfg['card']), '--cards', str(cfg['cards']),
           '--memory', cfg['memory'], '--stage', cfg['stage'], '--nongemv', 'parallel', '--gemv', cfg['gemv'],
           '--prompt-tokens', str((a.input / 'tokens.txt').resolve()), '--max-new', str(cfg['count']), '--context', str(cfg['context']),
           '--plan', str((a.input / 'plan.tsv').resolve()), '--identity', str((a.input / 'identity.tsv').resolve()),
           '--model-dir', inp['model_dir'], '--output', str(out / 'run'), '--seconds', str(a.seconds)]
    record = dict(schema='own-runtime.iq3.packet16.window.v1', window=a.window, boot_id=boot, **cfg,
                  nongemv='parallel', arithmetic=AUTHORITY, binary_sha256=sha(binary), input_sha256=input_hash,
                  input_manifest_sha256=sha(manifest), oracle_hashes=expected_hashes, expected_tokens=expected_tokens,
                  command=cmd, passed=False, device_executed=False, external_idle_health_still_required=True,
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
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        record.update(pid=child.pid, device_executed=True)
        persist()
        record.update(supervise(child, a.seconds, cursor, kernel, latch_fault, persist, requested))
    try:
        require(record['returncode'] == 0 and not requested, 'native child failed/stopped')
        for path, digest in bindings.items():
            require(sha(path) == digest, 'bound input/source changed during window: ' + str(path))
        run, actual = compare_run(out, cfg, expected_hashes, expected_tokens)
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
