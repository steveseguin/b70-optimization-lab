#!/usr/bin/env python3
"""All selectable actual submitters; fresh CPU repeats, immutable closure receipts.

The ordered output stream contains SHA256 digests of allocations after direct
byte comparison, keeping retained results small. selection.json is deliberately
outside this gate's input: every selectable choice is tested before selection.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import build
from cpu_gates import host

P = Path(__file__).resolve().parent
B = P / 'build'
ROOT = P.parents[3]
CHOICES = {
    'route': ('production', 'route-rank4', 'route-exp32-rank4'),
    'recurrence': ('production', 'rows4-shared', 'rows8-shared'),
    'hc.a.mix': ('production', 'mix-vector4'),
    'hc.f.mix': ('production', 'mix-vector4'),
    'expsgate': ('production', 'virtual8-split-stream'),
    'expsdown': ('production', 'virtual16'),
    'small.ffn.q6': ('production', 'virtual4'),
}
MODES = ('gnu-host', 'asan')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(value, message):
    if not value:
        raise ValueError(message)

def source_bindings():
    paths = tuple(P/name for name in ('p49d_cpu_gate.py', 'test_p49d_cpu_gate.py',
                  'dispatch-speed6.json', 'build.py', 'cpu_gates.py', 'retain_sanitizers.py'))
    return build.compiled_sources() | {str(p.relative_to(ROOT)): sha(p) for p in paths}

def validate_cases(rows):
    expected = set()
    for cls, choices in CHOICES.items():
        scenarios = (0, 6, 7, 8) if cls == 'small.ffn.q6' else range(9)
        for choice in choices:
            for m in (1, 2):
                for row in range(m):
                    for scenario in scenarios:
                        expected.add((cls, choice, m, row, scenario))
    actual = []
    for row in rows:
        require(row.get('passed') is True, 'fixture case failed')
        actual.append(tuple(row.get(k) for k in ('class', 'candidate', 'm', 'row', 'scenario')))
    require(len(actual) == len(set(actual)), 'duplicate fixture case')
    require(set(actual) == expected, 'incomplete selectable/control/M2 coverage')
    return len(actual)

def check_native(receipt, case_rows):
    require(receipt.get('schema') == 'packet49d.all-choice-fixtures.v1', 'fixture schema')
    for name in ('passed', 'reference_exact', 'serial_m2_state_carried'):
        require(receipt.get(name) is True, 'fixture missing '+name)
    require(receipt.get('device_executed') is False and receipt.get('timing') is False,
            'fixture must be CPU exact only')
    require(receipt.get('arithmetic') == 'iq3-p49-split32-v1', 'arithmetic identity')
    require(receipt.get('canonical_excluded_scenarios') == [6,7], 'NaN/Inf portable identity exclusion')
    require(receipt.get('output_format') == 'ordered-sha256-per-compared-allocation', 'output digest format')
    teardown = receipt.get('teardown', {})
    require(teardown.get('safe_to_exit') is True and all(teardown.get(k) == 0 for k in
            ('exit_code', 'live_bytes', 'in_flight')), 'fixture unsafe teardown')
    count = validate_cases(case_rows)
    expected = {cls+':'+choice: (12 if cls == 'small.ffn.q6' else 27)
                for cls, choices in CHOICES.items() for choice in choices}
    require(receipt.get('coverage') == expected, 'native choice counts')
    require(receipt.get('checks', 0) > count, 'missing admission refusals')
    return count

def validate_native(root, device=False, card=0):
    """Validate a CPU exact receipt or coordinator exact/timing device window."""
    root = Path(root)
    receipt = read_json(root/'receipt.json')
    require(receipt.get('schema') == 'packet49d.all-choice-fixtures.v1', 'fixture schema')
    require(receipt.get('passed') is True and receipt.get('reference_exact') is True,
            'native byte gate failed')
    require(receipt.get('device_executed') is device and receipt.get('card') == card,
            'native execution owner')
    require(receipt.get('serial_m2_state_carried') is True, 'native serial M2 contract')
    require(receipt.get('arithmetic') == 'iq3-p49-split32-v1', 'native arithmetic')
    teardown = receipt.get('teardown', {})
    require(teardown.get('safe_to_exit') is True and all(teardown.get(k) == 0 for k in
            ('exit_code', 'live_bytes', 'in_flight')), 'native teardown')
    require(sha(root/'output.bin') == receipt.get('output_sha256'), 'native output hash')
    if receipt.get('timing') is True:
        require(device, 'CPU timing prohibited')
        rows = [json.loads(line) for line in (root/'timings.jsonl').read_text().splitlines()]
        expected = {(cls, choice, i) for cls, choices in CHOICES.items()
                    for choice in choices for i in range(210)}
        actual = []
        for row in rows:
            actual.append((row['class'], row['candidate'], row['iteration']))
            require(row['m'] == 1 and row['row'] == 0 and row['byte_exact'] is True,
                    'ordinary M1 matched timing only')
            require(row['warmup'] is (row['iteration'] < 10), 'timing warmup label')
            events = row['events']
            require(len(events) == row['passes'] and len(events) > 0, 'timing event count')
            require(all(type(e['start_ns']) is int and e['start_ns'] > 0 and
                        type(e['end_ns']) is int and e['end_ns'] > e['start_ns'] for e in events),
                    'timing interval')
            require(row['gpu_ns'] == sum(e['end_ns']-e['start_ns'] for e in events), 'timing sum')
        require(len(actual) == len(set(actual)) and set(actual) == expected,
                'timing candidate dispatch coverage')
    else:
        require(receipt.get('timing') is False, 'native fixture mode')
        rows = [json.loads(line) for line in (root/'cases.jsonl').read_text().splitlines()]
        # Shared structural proof; check_native additionally enforces CPU mode.
        validate_cases(rows)
        require(receipt.get('coverage') == {
            cls+':'+choice: (12 if cls == 'small.ffn.q6' else 27)
            for cls, choices in CHOICES.items() for choice in choices}, 'native choice counts')
        if not device:
            check_native(receipt, rows)
    return receipt

def read_json(path):
    return json.loads(Path(path).read_text())

def file_pins(paths):
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}

def verify(receipt_path=None, *, verified_retention=None):
    """Fail closed without compiling or executing a fixture; called by fast reseal."""
    # The packet seal may pass its already fully verified archive inventory to
    # avoid decompressing the same sanitizer closure twice during fast reseal.
    retained = None
    def artifact_sha(path):
        nonlocal retained
        path = Path(path)
        if path.exists():
            return sha(path)
        require(path == B/'asan/p49d-fixtures', 'missing CPU receipt artifact: '+str(path))
        if retained is None:
            if verified_retention is None:
                from retain_sanitizers import verify_retention
                retention = verify_retention()
            else:
                retention = verified_retention
                require(retention == read_json(P/'asan-artifact-retention.json'),
                        'validated retention inventory changed')
                require(retention['build_receipt_sha256'] == sha(P/'build-asan-receipt.json'),
                        'validated retention build changed')
            retained = {row['original']: row['original_sha256'] for row in retention['artifacts']}
        require('asan/p49d-fixtures' in retained, 'CPU fixture absent from retained archive')
        return retained['asan/p49d-fixtures']

    receipt = read_json(receipt_path or P/'p49d-cpu-gates.json')
    require(receipt.get('schema') == 'packet49d.all-choice-cpu-gate.v1', 'CPU gate schema')
    require(receipt.get('passed') is True and receipt.get('device_executed') is False,
            'CPU gate result')
    require(receipt.get('source_hashes') == source_bindings(), 'CPU gate immutable source closure changed')
    compiled = build.compiled_sources()
    require(receipt.get('compiled_sources_sha256') == compiled, 'CPU compiled closure changed')
    for rel, expected in receipt['files_sha256'].items():
        require(artifact_sha(ROOT/rel) == expected, 'CPU receipt artifact changed: '+rel)
    rows = receipt['rows']
    require([(r['mode'], r['repeat']) for r in rows] == [(m,r) for m in MODES for r in range(2)],
            'CPU fresh-process modes/repeats')
    for mode in MODES:
        mode_receipt = read_json(P/f'build-{mode}-receipt.json')
        require(mode_receipt['compiled_sources_sha256'] == compiled, 'mode compiled closure changed')
        binary = B/mode/'p49d-fixtures'
        require(mode_receipt['artifacts_sha256'][mode+'/p49d-fixtures'] == artifact_sha(binary),
                'mode binary binding changed')
    for row in rows:
        dest = ROOT/row['output']
        native = read_json(dest/'receipt.json')
        cases = [json.loads(line) for line in (dest/'cases.jsonl').read_text().splitlines()]
        require(check_native(native, cases) == row['cases'], 'case count changed')
        require(sha(dest/'output.bin') == native['output_sha256'] == row['output_sha256'], 'output identity')
        require(artifact_sha(B/row['mode']/'p49d-fixtures') == row['binary_sha256'], 'fixture binary changed')
    require(len({r['output_sha256'] for r in rows}) == 1, 'fresh-process byte determinism')
    require(receipt.get('output_sha256') == rows[0]['output_sha256'], 'aggregate output identity')
    require(receipt['p49d_fixture_host_sha256'] == sha(B/'gnu-host/p49d-fixtures'), 'host fixture hash')
    return receipt

def main():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'reserved CPU cores')
    require(os.environ.get('OMP_NUM_THREADS') == '2', 'OMP_NUM_THREADS=2 required')
    compiled = build.compiled_sources()
    source_hashes = source_bindings()
    root = B/('p49d-all-choice-'+str(time.time_ns()))
    root.mkdir()
    rows = []
    files = []
    for mode in MODES:
        binary = B/mode/'p49d-fixtures'
        host(binary)
        mode_receipt = P/f'build-{mode}-receipt.json'
        require(read_json(mode_receipt)['compiled_sources_sha256'] == compiled, 'stale mode build')
        files += [binary, mode_receipt]
        env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        for repeat in range(2):
            dest = root/(mode+'-'+str(repeat))
            log = root/(mode+'-'+str(repeat)+'.log')
            command = [str(binary), '--output', str(dest)]
            with log.open('w') as stream:
                subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
            require('runtime error:' not in log.read_text() and 'ERROR: AddressSanitizer' not in log.read_text(),
                    'sanitizer failure')
            native = read_json(dest/'receipt.json')
            cases = [json.loads(line) for line in (dest/'cases.jsonl').read_text().splitlines()]
            count = check_native(native, cases)
            rows.append(dict(mode=mode, repeat=repeat, command=command,
                             sanitizer_options={k:env[k] for k in ('ASAN_OPTIONS','UBSAN_OPTIONS')},
                             output=str(dest.relative_to(ROOT)), cases=count,
                             binary_sha256=sha(binary), output_sha256=sha(dest/'output.bin')))
            files += [log, dest/'receipt.json', dest/'cases.jsonl', dest/'output.bin']
            print(mode, repeat, count, 'actual selectable-submit byte cases PASS', flush=True)
    require(compiled == build.compiled_sources() and source_hashes == source_bindings(),
            'source closure changed during fixtures')
    result = dict(schema='packet49d.all-choice-cpu-gate.v1', passed=True,
                  device_executed=False, model_weights_read=False,
                  compiled_sources_sha256=compiled, source_hashes=source_hashes,
                  files_sha256=file_pins(files), rows=rows,
                  p49d_fixture_host_sha256=sha(B/'gnu-host/p49d-fixtures'),
                  output_sha256=rows[0]['output_sha256'],
                  scope='All selected production submitters; fixed banked choices; M1 and serial M2 BF16 state; controls, position, invalid routes and admission refusal; no model/device claim')
    (P/'p49d-cpu-gates.json').write_text(json.dumps(result, indent=2)+'\n')
    verify()
    return result

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        verify()
        print('packet49d immutable CPU gate bindings PASS')
    else:
        main()
